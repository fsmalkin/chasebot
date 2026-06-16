#!/usr/bin/env python3
"""Small HTTP bridge for the factory Yahboom/JetBot Mini runtime.

The bridge keeps Chasecar logic outside the robot image and adapts commands to
the factory `jetbotmini` motor/camera APIs. It is intentionally manual: copy it
to the robot, run it in the foreground or with nohup, and remove the file to
return to the factory state.
"""

import argparse
import base64
import http.server
import json
import math
import socketserver
import sys
import threading
import time
import traceback
import urllib.parse


VERSION = "0.1.0"


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def finite_float(value, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return number


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class DryRunRobot(object):
    def __init__(self):
        self.left = 0.0
        self.right = 0.0

    def set_motors(self, left, right):
        self.left = float(left)
        self.right = float(right)

    def stop(self):
        self.set_motors(0.0, 0.0)


class RobotAdapter(object):
    def __init__(self, dry_run=False):
        self.dry_run = bool(dry_run)
        self.robot = None
        self.error = None
        self.load()

    def load(self):
        if self.dry_run:
            self.robot = DryRunRobot()
            return
        try:
            from jetbotmini import Robot

            self.robot = Robot()
        except Exception as exc:
            self.error = repr(exc)
            raise

    def set_motors(self, left, right):
        self.robot.set_motors(float(left), float(right))

    def stop(self):
        self.robot.stop()


class CameraAdapter(object):
    def __init__(self, enabled=False, dry_run=False, width=640, height=480):
        self.enabled = bool(enabled)
        self.dry_run = bool(dry_run)
        self.width = int(width)
        self.height = int(height)
        self.camera = None
        self.error = None
        self.lock = threading.Lock()

    def snapshot_jpeg(self):
        if not self.enabled:
            raise RuntimeError("camera_disabled")
        if self.dry_run:
            return base64.b64decode(
                b"/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
                b"////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////"
                b"////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAH/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAEFAqf/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/ASP/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/ASP/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAY/Aqf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/IX//2gAMAwEAAgADAAAAEP/EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQMBAT8QH//EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQIBAT8QH//EABQQAQAAAAAAAAAAAAAAAAAAABD/2gAIAQEAAT8QH//Z"
            )

        with self.lock:
            if self.camera is None:
                try:
                    from jetbotmini import Camera, bgr8_to_jpeg

                    self._bgr8_to_jpeg = bgr8_to_jpeg
                    self.camera = Camera.instance(width=self.width, height=self.height)
                    time.sleep(0.4)
                except Exception as exc:
                    self.error = repr(exc)
                    raise
            return self._bgr8_to_jpeg(self.camera.value)

    def status(self):
        return {
            "enabled": self.enabled,
            "loaded": self.camera is not None,
            "error": self.error,
            "width": self.width,
            "height": self.height,
        }


class BridgeState(object):
    def __init__(self, args):
        self.args = args
        self.lock = threading.RLock()
        self.robot = RobotAdapter(dry_run=args.dry_run)
        self.camera = CameraAdapter(
            enabled=args.camera,
            dry_run=args.dry_run,
            width=args.camera_width,
            height=args.camera_height,
        )
        self.started_monotonic = time.monotonic()
        self.last_command_monotonic = 0.0
        self.command_deadline_monotonic = 0.0
        self.commands_received = 0
        self.last_command = None
        self.left_motor = 0.0
        self.right_motor = 0.0
        self.last_stop_reason = "startup"
        self.stop("startup")

    def now_age(self):
        if self.last_command_monotonic <= 0:
            return None
        return max(0.0, time.monotonic() - self.last_command_monotonic)

    def status(self):
        with self.lock:
            return {
                "ok": True,
                "version": VERSION,
                "dry_run": bool(self.args.dry_run),
                "motion_enabled": bool(self.args.enable_motion),
                "deadman_timeout_s": float(self.args.deadman_timeout_s),
                "max_command_duration_s": float(self.args.max_command_duration_s),
                "max_motor_speed": float(self.args.max_motor_speed),
                "max_linear_x": float(self.args.max_linear_x),
                "max_angular_z": float(self.args.max_angular_z),
                "turn_gain": float(self.args.turn_gain),
                "uptime_s": round(time.monotonic() - self.started_monotonic, 3),
                "commands_received": int(self.commands_received),
                "last_command_age_s": self.now_age(),
                "last_command": self.last_command,
                "left_motor": self.left_motor,
                "right_motor": self.right_motor,
                "last_stop_reason": self.last_stop_reason,
                "camera": self.camera.status(),
            }

    def stop(self, reason):
        with self.lock:
            self.robot.stop()
            self.left_motor = 0.0
            self.right_motor = 0.0
            self.command_deadline_monotonic = 0.0
            self.last_stop_reason = str(reason)

    def cmd_vel_to_motors(self, linear_x, angular_z):
        max_linear = max(0.001, abs(float(self.args.max_linear_x)))
        max_angular = max(0.001, abs(float(self.args.max_angular_z)))
        linear_unit = clamp(float(linear_x) / max_linear, -1.0, 1.0)
        angular_unit = clamp(float(angular_z) / max_angular, -1.0, 1.0)

        left = linear_unit - (float(self.args.turn_gain) * angular_unit)
        right = linear_unit + (float(self.args.turn_gain) * angular_unit)
        max_abs = max(1.0, abs(left), abs(right))
        left = left / max_abs
        right = right / max_abs
        return self.scale_motor_units(left, right)

    def scale_motor_units(self, left, right):
        max_speed = clamp(abs(float(self.args.max_motor_speed)), 0.0, 1.0)
        left = clamp(finite_float(left), -1.0, 1.0) * max_speed
        right = clamp(finite_float(right), -1.0, 1.0) * max_speed
        left *= float(self.args.left_sign)
        right *= float(self.args.right_sign)
        return clamp(left, -1.0, 1.0), clamp(right, -1.0, 1.0)

    def clamp_motor_values(self, left, right):
        max_speed = clamp(abs(float(self.args.max_motor_speed)), 0.0, 1.0)
        left = clamp(finite_float(left), -max_speed, max_speed)
        right = clamp(finite_float(right), -max_speed, max_speed)
        left *= float(self.args.left_sign)
        right *= float(self.args.right_sign)
        return clamp(left, -1.0, 1.0), clamp(right, -1.0, 1.0)

    def apply_prepared_motors(self, left, right, duration_s, source):
        if not self.args.enable_motion:
            self.stop("motion_disabled")
            raise RuntimeError("motion_disabled")
        with self.lock:
            duration_s = finite_float(duration_s, self.args.deadman_timeout_s)
            duration_s = clamp(duration_s, 0.0, float(self.args.max_command_duration_s))
            now = time.monotonic()
            self.robot.set_motors(left, right)
            self.left_motor = left
            self.right_motor = right
            self.last_command_monotonic = now
            self.command_deadline_monotonic = now + duration_s if duration_s > 0 else 0.0
            self.commands_received += 1
            self.last_command = {
                "source": str(source),
                "left": left,
                "right": right,
                "duration_s": duration_s,
            }
            return self.status()

    def apply_motors(self, left, right, duration_s, source):
        left, right = self.clamp_motor_values(left, right)
        return self.apply_prepared_motors(left, right, duration_s, source)

    def apply_cmd_vel(self, linear_x, angular_z, duration_s, source):
        left, right = self.cmd_vel_to_motors(linear_x, angular_z)
        status = self.apply_prepared_motors(left, right, duration_s, source)
        status["cmd_vel"] = {"linear_x": linear_x, "angular_z": angular_z}
        return status

    def enforce_deadman_once(self):
        with self.lock:
            now = time.monotonic()
            moving = abs(self.left_motor) > 0.0001 or abs(self.right_motor) > 0.0001
            if not moving:
                return
            stale = self.last_command_monotonic > 0 and (
                now - self.last_command_monotonic > float(self.args.deadman_timeout_s)
            )
            expired = self.command_deadline_monotonic > 0 and now >= self.command_deadline_monotonic
            if stale:
                self.stop("deadman_timeout")
            elif expired:
                self.stop("command_duration_elapsed")

    def deadman_loop(self):
        while True:
            try:
                self.enforce_deadman_once()
            except Exception:
                traceback.print_exc()
                try:
                    self.stop("deadman_error")
                except Exception:
                    pass
            time.sleep(0.05)


class BridgeHandler(http.server.BaseHTTPRequestHandler):
    server_version = "ChasecarFactoryBridge/%s" % VERSION

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - - [%s] %s\n" % (
            self.client_address[0],
            self.log_date_time_string(),
            fmt % args,
        ))

    @property
    def bridge(self):
        return self.server.bridge

    def write_json(self, payload, status=200):
        data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/health", "/state"):
            self.write_json(self.bridge.status())
            return
        if parsed.path == "/camera.jpg":
            try:
                jpeg = self.bridge.camera.snapshot_jpeg()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(jpeg)))
                self.end_headers()
                self.wfile.write(jpeg)
            except Exception as exc:
                self.write_json({"ok": False, "error": repr(exc)}, status=503)
            return
        self.write_json({"ok": False, "error": "not_found"}, status=404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        try:
            payload = self.read_json()
            if parsed.path == "/stop":
                self.bridge.stop("api_stop")
                self.write_json(self.bridge.status())
                return
            if parsed.path == "/motors":
                status = self.bridge.apply_motors(
                    finite_float(payload.get("left")),
                    finite_float(payload.get("right")),
                    finite_float(payload.get("duration_s"), self.bridge.args.deadman_timeout_s),
                    payload.get("source", "api_motors"),
                )
                self.write_json(status)
                return
            if parsed.path == "/cmd_vel":
                status = self.bridge.apply_cmd_vel(
                    finite_float(payload.get("linear_x")),
                    finite_float(payload.get("angular_z")),
                    finite_float(payload.get("duration_s"), self.bridge.args.deadman_timeout_s),
                    payload.get("source", "api_cmd_vel"),
                )
                self.write_json(status)
                return
            self.write_json({"ok": False, "error": "not_found"}, status=404)
        except RuntimeError as exc:
            self.write_json({"ok": False, "error": str(exc), "state": self.bridge.status()}, status=423)
        except Exception as exc:
            traceback.print_exc()
            try:
                self.bridge.stop("api_error")
            except Exception:
                pass
            self.write_json({"ok": False, "error": repr(exc), "state": self.bridge.status()}, status=500)


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Run the Chasecar factory robot bridge.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--enable-motion", action="store_true")
    parser.add_argument("--camera", action="store_true")
    parser.add_argument("--camera-width", type=int, default=640)
    parser.add_argument("--camera-height", type=int, default=480)
    parser.add_argument("--deadman-timeout-s", type=float, default=0.5)
    parser.add_argument("--max-command-duration-s", type=float, default=1.0)
    parser.add_argument("--max-motor-speed", type=float, default=0.35)
    parser.add_argument("--max-linear-x", type=float, default=0.6)
    parser.add_argument("--max-angular-z", type=float, default=2.5)
    parser.add_argument("--turn-gain", type=float, default=0.7)
    parser.add_argument("--left-sign", type=float, default=1.0)
    parser.add_argument("--right-sign", type=float, default=1.0)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def run_self_test():
    args = parse_args(["--dry-run", "--enable-motion"])
    bridge = BridgeState(args)
    left, right = bridge.cmd_vel_to_motors(0.6, 0.0)
    assert abs(left - 0.35) < 1e-6
    assert abs(right - 0.35) < 1e-6
    left, right = bridge.cmd_vel_to_motors(0.0, 2.5)
    assert abs(left + 0.245) < 1e-6
    assert abs(right - 0.245) < 1e-6
    bridge.apply_motors(1.0, -1.0, 0.1, "self_test")
    assert bridge.left_motor == 0.35
    assert bridge.right_motor == -0.35
    time.sleep(0.15)
    bridge.enforce_deadman_once()
    assert bridge.left_motor == 0.0
    assert bridge.right_motor == 0.0
    print("SELF_TEST_OK=1")


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    if args.self_test:
        run_self_test()
        return 0

    bridge = BridgeState(args)
    deadman_thread = threading.Thread(target=bridge.deadman_loop)
    deadman_thread.daemon = True
    deadman_thread.start()

    server = ThreadingHTTPServer((args.host, args.port), BridgeHandler)
    server.bridge = bridge
    print("CHASECAR_FACTORY_BRIDGE_READY=1 host=%s port=%s motion_enabled=%s camera=%s" % (
        args.host,
        args.port,
        bool(args.enable_motion),
        bool(args.camera),
    ))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        bridge.stop("shutdown")
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
