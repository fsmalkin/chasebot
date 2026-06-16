from __future__ import annotations

import contextlib
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_TOOLS_DIR = REPO_ROOT / "tools" / "robot_factory_bridge"
if str(BRIDGE_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_TOOLS_DIR))

import chasecar_bridge_behavior_runner as runner  # noqa: E402


FAKE_JPEG = b"\xff\xd8" + (b"behavior-frame" * 24) + b"\xff\xd9"


class _TestHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_handler(*, motion_enabled=False):
    class Handler(http.server.BaseHTTPRequestHandler):
        requests = []
        left_motor = 0.0
        right_motor = 0.0

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
                "left_motor": self.left_motor,
                "right_motor": self.right_motor,
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
            if self.path == "/stop":
                self.left_motor = 0.0
                self.right_motor = 0.0
                self.write_json(self.health_payload())
                return
            if self.path == "/cmd_vel":
                if not motion_enabled:
                    self.write_json({"ok": False, "error": "motion_disabled", "state": self.health_payload()}, status=423)
                    return
                self.left_motor = -0.1
                self.right_motor = 0.1
                response = self.health_payload()
                response["cmd_vel"] = {
                    "linear_x": float(payload.get("linear_x", 0.0)),
                    "angular_z": float(payload.get("angular_z", 0.0)),
                }
                response["last_command"] = dict(payload)
                self.write_json(response)
                return
            self.write_json({"ok": False, "error": "not_found"}, status=404)

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


def test_no_motion_command_passes_when_bridge_refuses_motion(tmp_path, capsys):
    handler = make_handler(motion_enabled=False)
    with run_server(handler) as (base_url, recorded):
        code = runner.main(
            [
                "--base-url",
                base_url,
                "--artifact-dir",
                str(tmp_path / "run"),
                "--mode",
                "no-motion-command",
            ]
        )

    assert code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["pass"] is True
    assert summary["steps"][0]["expected_refusal"] is True
    assert summary["steps"][0]["http_status"] == 423
    paths = [request["path"] for request in recorded.requests]
    assert "/cmd_vel" in paths
    assert (tmp_path / "run" / "behavior_summary.json").exists()


def test_tiny_turn_requires_execute_confirmation(tmp_path, capsys):
    handler = make_handler(motion_enabled=True)
    with run_server(handler) as (base_url, _recorded):
        code = runner.main(
            [
                "--base-url",
                base_url,
                "--artifact-dir",
                str(tmp_path / "run"),
                "--mode",
                "tiny-turn",
            ]
        )

    assert code == 1
    summary = json.loads(capsys.readouterr().out)
    assert "execute_motion_required" in summary["issues"]


def test_tiny_turn_executes_bounded_plan_and_stops(tmp_path, capsys):
    handler = make_handler(motion_enabled=True)
    with run_server(handler) as (base_url, recorded):
        code = runner.main(
            [
                "--base-url",
                base_url,
                "--artifact-dir",
                str(tmp_path / "run"),
                "--mode",
                "tiny-turn",
                "--execute-motion",
                "--confirm-operator-ready",
                "--camera-frames",
                "2",
                "--camera-interval-s",
                "0",
            ]
        )

    assert code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["pass"] is True
    assert summary["plan"]["name"] == "tiny_turn_v1"
    assert summary["steps"][0]["request"]["linear_x"] == 0.0
    assert summary["artifacts"]["finally_stop"]["response"]["left_motor"] == 0.0
    paths = [request["path"] for request in recorded.requests]
    assert "/cmd_vel" in paths
    assert "/stop" in paths
    assert (tmp_path / "run" / "before.jpg").exists()
    assert (tmp_path / "run" / "behavior_summary.json").exists()


def test_tiny_turn_plan_limits_fail_closed(tmp_path, capsys):
    plan = tmp_path / "too_fast.json"
    plan.write_text(
        json.dumps(
            {
                "name": "too_fast",
                "steps": [
                    {
                        "linear_x": 0.2,
                        "angular_z": 0.0,
                        "duration_s": 0.2,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    handler = make_handler(motion_enabled=True)
    with run_server(handler) as (base_url, recorded):
        code = runner.main(
            [
                "--base-url",
                base_url,
                "--artifact-dir",
                str(tmp_path / "run"),
                "--mode",
                "tiny-turn",
                "--execute-motion",
                "--confirm-operator-ready",
                "--plan-file",
                str(plan),
            ]
        )

    assert code == 1
    summary = json.loads(capsys.readouterr().out)
    assert "step_linear_x_above_limit:step_01" in summary["issues"]
    assert all(request["path"] != "/cmd_vel" for request in recorded.requests)
