from __future__ import annotations

import contextlib
import http.server
import io
import json
import socketserver
import sys
import threading
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_TOOLS_DIR = REPO_ROOT / "tools" / "robot_factory_bridge"
if str(BRIDGE_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_TOOLS_DIR))

import chasecar_bridge_client as client  # noqa: E402


def make_jpeg(width=160, height=120):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (width, height), (40, 45, 50))
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 16, width - 16, height - 16), outline=(230, 210, 40), width=3)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


FAKE_JPEG = make_jpeg()


class _TestHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_handler(post_status=200, post_payload=None, camera_failures=0):
    class Handler(http.server.BaseHTTPRequestHandler):
        requests = []
        camera_failures_remaining = int(camera_failures)

        def log_message(self, _fmt, *_args):
            return

        def write_json(self, payload, status=200):
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            self.requests.append({"method": "GET", "path": self.path, "payload": None})
            if self.path == "/health":
                self.write_json(
                    {
                        "ok": True,
                        "motion_enabled": False,
                        "camera": {
                            "enabled": True,
                            "loaded": True,
                            "cached_fps": 5.0,
                            "frame_age_s": 0.1,
                            "cached_bytes": len(FAKE_JPEG),
                        },
                    }
                )
                return
            if self.path == "/events":
                self.write_json({"ok": True, "events": []})
                return
            if self.path == "/camera.jpg":
                if self.camera_failures_remaining > 0:
                    type(self).camera_failures_remaining -= 1
                    self.write_json({"ok": False, "error": "camera_not_ready"}, status=503)
                    return
                image = FAKE_JPEG
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(image)))
                self.end_headers()
                self.wfile.write(image)
                return
            self.write_json({"ok": False, "error": "not_found"}, status=404)

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            self.requests.append({"method": "POST", "path": self.path, "payload": payload})
            response = post_payload or {"ok": True, "path": self.path, "payload": payload}
            self.write_json(response, status=post_status)

    return Handler


@contextlib.contextmanager
def run_server(handler):
    server = _TestHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    try:
        host, port = server.server_address
        yield "http://%s:%s" % (host, port), handler
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_cmd_vel_refuses_without_motion_confirmation(capsys):
    code = client.main(
        [
            "--base-url",
            "http://127.0.0.1:1",
            "cmd-vel",
            "--linear-x",
            "0.1",
            "--angular-z",
            "0.0",
        ]
    )

    assert code == 2
    summary = json.loads(capsys.readouterr().out)
    assert "without_confirmation" in summary["error"]


def test_cmd_vel_confirm_motion_posts_payload(capsys):
    handler = make_handler()
    with run_server(handler) as (base_url, recorded):
        code = client.main(
            [
                "--base-url",
                base_url,
                "cmd-vel",
                "--linear-x",
                "0.12",
                "--angular-z",
                "-0.3",
                "--duration-s",
                "0.2",
                "--confirm-motion",
            ]
        )

    assert code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["http_status"] == 200
    request = recorded.requests[-1]
    assert request["path"] == "/cmd_vel"
    assert request["payload"]["linear_x"] == 0.12
    assert request["payload"]["angular_z"] == -0.3
    assert request["payload"]["duration_s"] == 0.2


def test_cmd_vel_expect_refusal_accepts_motion_disabled_response(capsys):
    handler = make_handler(post_status=423, post_payload={"ok": False, "error": "motion_disabled"})
    with run_server(handler) as (base_url, recorded):
        code = client.main(
            [
                "--base-url",
                base_url,
                "cmd-vel",
                "--linear-x",
                "0.1",
                "--angular-z",
                "0.0",
                "--expect-refusal",
            ]
        )

    assert code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["http_status"] == 423
    assert summary["error"] == "expected_refusal"
    assert recorded.requests[-1]["path"] == "/cmd_vel"


def test_snapshot_writes_camera_frame(tmp_path, capsys):
    handler = make_handler()
    output = tmp_path / "camera.jpg"
    with run_server(handler) as (base_url, recorded):
        code = client.main(["--base-url", base_url, "snapshot", "--output", str(output)])

    assert code == 0
    assert output.read_bytes() == FAKE_JPEG
    summary = json.loads(capsys.readouterr().out)
    assert summary["response"]["bytes"] == len(FAKE_JPEG)
    assert recorded.requests[-1]["path"] == "/camera.jpg"


def test_camera_diagnostics_scores_camera_readiness(tmp_path, capsys):
    handler = make_handler()
    output_dir = tmp_path / "camera_diag"
    with run_server(handler) as (base_url, recorded):
        code = client.main(
            [
                "--base-url",
                base_url,
                "camera-diagnostics",
                "--frames",
                "3",
                "--interval-s",
                "0",
                "--output-dir",
                str(output_dir),
            ]
        )

    assert code == 0
    summary = json.loads(capsys.readouterr().out)
    response = summary["response"]
    assert response["pass"] is True
    assert response["captured_frames"] == 3
    assert (output_dir / "camera_001.jpg").exists()
    assert (output_dir / "camera_diagnostics.json").exists()
    paths = [request["path"] for request in recorded.requests]
    assert paths.count("/camera.jpg") == 3
    assert paths.count("/health") >= 2


def test_camera_diagnostics_retries_camera_warmup_503(tmp_path, capsys):
    handler = make_handler(camera_failures=1)
    output_dir = tmp_path / "camera_diag"
    with run_server(handler) as (base_url, recorded):
        code = client.main(
            [
                "--base-url",
                base_url,
                "camera-diagnostics",
                "--frames",
                "2",
                "--interval-s",
                "0",
                "--output-dir",
                str(output_dir),
            ]
        )

    assert code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["response"]["pass"] is True
    assert summary["response"]["captured_frames"] == 2
    paths = [request["path"] for request in recorded.requests]
    assert paths.count("/camera.jpg") == 3


def test_record_video_writes_gif_without_motion_requests(tmp_path, capsys):
    handler = make_handler()
    output_dir = tmp_path / "camera_video"
    with run_server(handler) as (base_url, recorded):
        code = client.main(
            [
                "--base-url",
                base_url,
                "record-video",
                "--seconds",
                "0.6",
                "--fps",
                "5",
                "--output-dir",
                str(output_dir),
                "--skip-mp4",
            ]
        )

    assert code == 0
    summary = json.loads(capsys.readouterr().out)
    response = summary["response"]
    assert response["pass"] is True
    assert response["captured_frames"] == 3
    assert response["gif"]["ok"] is True
    assert response["mp4"]["skipped"] is True
    assert (output_dir / "camera.gif").exists()
    assert (output_dir / "frames" / "camera_001.jpg").exists()
    assert (output_dir / "camera_video_summary.json").exists()
    paths = [request["path"] for request in recorded.requests]
    assert paths.count("/camera.jpg") == 3
    assert paths.count("/health") >= 2
    assert all(request["method"] != "POST" for request in recorded.requests)
