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

import chasecar_bridge_preflight as preflight  # noqa: E402


def make_jpeg(width=160, height=120):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (width, height), (30, 35, 40))
    draw = ImageDraw.Draw(image)
    draw.ellipse((55, 35, 105, 85), fill=(240, 220, 40))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


FAKE_JPEG = make_jpeg()


class _TestHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_handler(*, motion_enabled=False):
    class Handler(http.server.BaseHTTPRequestHandler):
        requests = []

        def log_message(self, _fmt, *_args):
            return

        def write_json(self, payload, status=200):
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def health_payload(self):
            return {
                "ok": True,
                "motion_enabled": motion_enabled,
                "left_motor": 0.0,
                "right_motor": 0.0,
                "camera": {
                    "enabled": True,
                    "cached_fps": 5.0,
                    "frame_age_s": 0.05,
                    "cached_bytes": len(FAKE_JPEG),
                },
            }

        def do_GET(self):
            self.requests.append({"method": "GET", "path": self.path, "payload": None})
            if self.path == "/health":
                self.write_json(self.health_payload())
                return
            if self.path == "/camera.jpg":
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(FAKE_JPEG)))
                self.end_headers()
                self.wfile.write(FAKE_JPEG)
                return
            self.write_json({"ok": False, "error": "not_found"}, status=404)

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            self.requests.append({"method": "POST", "path": self.path, "payload": payload})
            if self.path == "/cmd_vel" and not motion_enabled:
                self.write_json({"ok": False, "error": "motion_disabled", "state": self.health_payload()}, status=423)
                return
            self.write_json({"ok": True, "payload": payload})

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


def test_preflight_captures_camera_and_expected_refusal(tmp_path, capsys):
    handler = make_handler(motion_enabled=False)
    with run_server(handler) as (base_url, recorded):
        code = preflight.main(
            [
                "--base-url",
                base_url,
                "--artifact-dir",
                str(tmp_path / "preflight"),
                "--camera-frames",
                "2",
                "--camera-interval-s",
                "0",
                "--video-seconds",
                "0.4",
                "--video-fps",
                "5",
                "--skip-mp4",
            ]
        )

    assert code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["pass"] is True
    labels = [step["label"] for step in summary["steps"]]
    assert "camera_diagnostics" in labels
    assert "camera_video" in labels
    refusal = [step for step in summary["steps"] if step["label"] == "zero_cmd_vel_refusal"][0]
    assert refusal["expected_refusal"] is True
    assert (tmp_path / "preflight" / "snapshot.jpg").exists()
    assert (tmp_path / "preflight" / "camera_video" / "camera.gif").exists()
    assert (tmp_path / "preflight" / "safe_preflight_summary.json").exists()
    paths = [request["path"] for request in recorded.requests]
    assert "/cmd_vel" in paths
    assert all(request["path"] != "/motors" for request in recorded.requests)


def test_preflight_fails_closed_when_motion_enabled(tmp_path, capsys):
    handler = make_handler(motion_enabled=True)
    with run_server(handler) as (base_url, recorded):
        code = preflight.main(
            [
                "--base-url",
                base_url,
                "--artifact-dir",
                str(tmp_path / "preflight"),
                "--camera-frames",
                "1",
                "--camera-interval-s",
                "0",
                "--skip-video",
            ]
        )

    assert code == 1
    summary = json.loads(capsys.readouterr().out)
    assert "initial_motion_enabled" in summary["issues"]
    assert "command_refusal_skipped_motion_enabled" in summary["issues"]
    assert all(request["path"] != "/cmd_vel" for request in recorded.requests)
