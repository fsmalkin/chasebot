#!/usr/bin/env python3
"""Laptop-side client for the Chasecar factory robot bridge."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_BASE_URL = "http://192.168.1.11:8765"
DEFAULT_TIMEOUT_S = 3.0
MOTION_ACTIONS = {"cmd-vel", "motors"}


class BridgeClientError(RuntimeError):
    pass


class BridgeHttpError(BridgeClientError):
    def __init__(self, status_code, payload, raw_body):
        super().__init__("bridge_http_%s" % status_code)
        self.status_code = int(status_code)
        self.payload = payload
        self.raw_body = raw_body


def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def normalize_base_url(base_url):
    value = str(base_url or "").strip()
    if not value:
        raise BridgeClientError("base_url_required")
    return value.rstrip("/")


def default_snapshot_path():
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return Path("artifacts") / "session" / ("factory_bridge_snapshot_%s" % stamp) / "camera.jpg"


def default_camera_diagnostics_dir():
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return Path("artifacts") / "session" / ("factory_bridge_camera_diagnostics_%s" % stamp)


def default_camera_video_dir():
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return Path("artifacts") / "session" / ("factory_bridge_camera_video_%s" % stamp)


def decode_json(raw):
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


class BridgeClient:
    def __init__(self, base_url=DEFAULT_BASE_URL, timeout_s=DEFAULT_TIMEOUT_S):
        self.base_url = normalize_base_url(base_url)
        self.timeout_s = float(timeout_s)

    def url(self, path):
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def request(self, method, path, payload=None, expect_json=True):
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload, sort_keys=True).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.url(path), data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                raw = response.read()
                if expect_json:
                    decoded = decode_json(raw)
                    if decoded is None:
                        raise BridgeClientError("invalid_json_response")
                    return int(response.status), decoded
                return int(response.status), raw
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            decoded = decode_json(raw)
            raise BridgeHttpError(exc.code, decoded, raw)
        except urllib.error.URLError as exc:
            raise BridgeClientError("bridge_unreachable: %s" % exc)

    def health(self):
        return self.request("GET", "/health")

    def events(self):
        return self.request("GET", "/events")

    def operator_event(self, event, note=None):
        payload = {"event": str(event)}
        if note:
            payload["note"] = str(note)
        return self.request("POST", "/operator_event", payload)

    def stop(self, source):
        return self.request("POST", "/stop", {"source": str(source)})

    def cmd_vel(self, linear_x, angular_z, duration_s, source):
        payload = {
            "linear_x": float(linear_x),
            "angular_z": float(angular_z),
            "duration_s": float(duration_s),
            "source": str(source),
        }
        return self.request("POST", "/cmd_vel", payload)

    def motors(self, left, right, duration_s, source):
        payload = {
            "left": float(left),
            "right": float(right),
            "duration_s": float(duration_s),
            "source": str(source),
        }
        return self.request("POST", "/motors", payload)

    def snapshot(self):
        return self.request("GET", "/camera.jpg", expect_json=False)


def build_summary(args, request_payload, http_status=None, response=None, error=None):
    return {
        "generated_utc": utc_now(),
        "action": args.action,
        "base_url": normalize_base_url(args.base_url),
        "dry_run": bool(args.dry_run),
        "request": request_payload or {},
        "http_status": http_status,
        "response": response,
        "error": error,
    }


def write_summary(summary_path, summary):
    if not summary_path:
        return
    path = Path(summary_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def print_summary(args, summary):
    text = json.dumps(summary, indent=2 if args.pretty else None, sort_keys=True)
    print(text)
    write_summary(args.summary_path, summary)


def require_motion_confirmation(args):
    if args.action not in MOTION_ACTIONS:
        return
    if args.dry_run or args.confirm_motion or args.expect_refusal:
        return
    raise BridgeClientError(
        "refusing_%s_without_confirmation: add --confirm-motion for a held-in-air "
        "motion test, or --expect-refusal when deliberately checking that the "
        "bridge rejects motion while motion is disabled" % args.action
    )


def common_request_payload(args):
    if args.action == "cmd-vel":
        return {
            "linear_x": float(args.linear_x),
            "angular_z": float(args.angular_z),
            "duration_s": float(args.duration_s),
            "source": args.source,
        }
    if args.action == "motors":
        return {
            "left": float(args.left),
            "right": float(args.right),
            "duration_s": float(args.duration_s),
            "source": args.source,
        }
    if args.action == "event":
        payload = {"event": args.event}
        if args.note:
            payload["note"] = args.note
        return payload
    if args.action == "stop":
        return {"source": args.source}
    if args.action == "snapshot":
        return {"output": str(args.output or default_snapshot_path())}
    if args.action == "camera-diagnostics":
        return {
            "frames": int(args.frames),
            "interval_s": float(args.interval_s),
            "output_dir": str(args.output_dir or default_camera_diagnostics_dir()),
            "min_fps": float(args.min_fps),
            "max_frame_age_s": float(args.max_frame_age_s),
            "min_frame_bytes": int(args.min_frame_bytes),
        }
    if args.action == "record-video":
        return {
            "seconds": float(args.seconds),
            "fps": float(args.fps),
            "frames": int(max(1, round(float(args.seconds) * float(args.fps)))),
            "output_dir": str(args.output_dir or default_camera_video_dir()),
            "skip_mp4": bool(args.skip_mp4),
        }
    return {}


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def camera_block(health):
    if isinstance(health, dict) and isinstance(health.get("camera"), dict):
        return health["camera"]
    return {}


def run_camera_diagnostics(client, args):
    frames_requested = max(1, int(args.frames))
    interval_s = max(0.0, float(args.interval_s))
    output_dir = Path(args.output_dir or default_camera_diagnostics_dir())
    output_dir.mkdir(parents=True, exist_ok=True)

    start_status, start_health = client.health()
    start_monotonic = time.monotonic()
    frames = []
    for index in range(frames_requested):
        frame_status, image = client.snapshot()
        frame_path = output_dir / ("camera_%03d.jpg" % (index + 1))
        frame_path.write_bytes(image)
        frames.append(
            {
                "index": index + 1,
                "http_status": frame_status,
                "bytes": len(image),
                "output": str(frame_path),
                "elapsed_s": round(time.monotonic() - start_monotonic, 3),
            }
        )
        if index < frames_requested - 1 and interval_s > 0:
            time.sleep(interval_s)
    end_status, end_health = client.health()
    elapsed_s = max(time.monotonic() - start_monotonic, 0.001)

    start_camera = camera_block(start_health)
    end_camera = camera_block(end_health)
    frame_bytes = [int(frame["bytes"]) for frame in frames]
    min_frame_bytes = min(frame_bytes) if frame_bytes else 0
    observed_fps = len(frames) / elapsed_s
    cached_fps = end_camera.get("cached_fps")
    frame_age_s = end_camera.get("frame_age_s")

    issues = []
    if not bool(start_health.get("ok", False)):
        issues.append("health_not_ok")
    if not bool(end_camera.get("enabled", False)):
        issues.append("camera_not_enabled")
    if len(frames) != frames_requested:
        issues.append("missing_camera_frames")
    if min_frame_bytes < int(args.min_frame_bytes):
        issues.append("camera_frame_too_small")
    if is_number(cached_fps) and float(cached_fps) < float(args.min_fps):
        issues.append("cached_fps_below_threshold")
    if is_number(frame_age_s) and float(frame_age_s) > float(args.max_frame_age_s):
        issues.append("frame_age_above_threshold")
    if not is_number(cached_fps):
        issues.append("cached_fps_missing")
    if not is_number(frame_age_s):
        issues.append("frame_age_missing")

    payload = {
        "ok": True,
        "pass": not issues,
        "issues": issues,
        "output_dir": str(output_dir),
        "summary_path": str(output_dir / "camera_diagnostics.json"),
        "requested_frames": frames_requested,
        "captured_frames": len(frames),
        "elapsed_s": round(elapsed_s, 3),
        "observed_request_fps": round(observed_fps, 3),
        "min_frame_bytes": min_frame_bytes,
        "thresholds": {
            "min_fps": float(args.min_fps),
            "max_frame_age_s": float(args.max_frame_age_s),
            "min_frame_bytes": int(args.min_frame_bytes),
        },
        "start_health_status": start_status,
        "end_health_status": end_status,
        "start_camera": start_camera,
        "end_camera": end_camera,
        "frames": frames,
    }
    Path(payload["summary_path"]).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def write_animated_gif(frame_paths, output_path, fps):
    try:
        from PIL import Image
    except Exception as exc:
        return {
            "ok": False,
            "error": "pillow_unavailable:%r" % (exc,),
        }
    if not frame_paths:
        return {
            "ok": False,
            "error": "no_frames",
        }
    images = []
    try:
        for frame_path in frame_paths:
            images.append(Image.open(frame_path).convert("RGB"))
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        duration_ms = max(1, int(round(1000.0 / max(float(fps), 0.001))))
        images[0].save(
            output_path,
            save_all=True,
            append_images=images[1:],
            duration=duration_ms,
            loop=0,
        )
        return {
            "ok": True,
            "output": str(output_path),
            "bytes": output_path.stat().st_size,
            "frames": len(frame_paths),
            "fps": float(fps),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": repr(exc),
        }
    finally:
        for image in images:
            try:
                image.close()
            except Exception:
                pass


def write_mp4_with_ffmpeg(frames_dir, output_path, fps, skip_mp4=False):
    if skip_mp4:
        return {
            "ok": False,
            "skipped": True,
            "error": "skip_mp4_requested",
        }
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {
            "ok": False,
            "skipped": True,
            "error": "ffmpeg_not_found",
        }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    input_pattern = str(Path(frames_dir) / "camera_%03d.jpg")
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-framerate",
        str(max(float(fps), 0.001)),
        "-i",
        input_pattern,
        "-vf",
        "format=yuv420p",
        "-c:v",
        "libx264",
        str(output_path),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
        if completed.returncode != 0:
            return {
                "ok": False,
                "command": command,
                "error": (completed.stderr or completed.stdout or "ffmpeg_failed").strip(),
            }
        return {
            "ok": True,
            "output": str(output_path),
            "bytes": output_path.stat().st_size,
            "fps": float(fps),
        }
    except Exception as exc:
        return {
            "ok": False,
            "command": command,
            "error": repr(exc),
        }


def run_camera_video_capture(client, args):
    seconds = max(0.1, float(args.seconds))
    fps = max(0.1, float(args.fps))
    frames_requested = max(1, int(round(seconds * fps)))
    interval_s = 1.0 / fps
    output_dir = Path(args.output_dir or default_camera_video_dir())
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    start_status, start_health = client.health()
    start_monotonic = time.monotonic()
    frames = []
    for index in range(frames_requested):
        target_time = start_monotonic + (index * interval_s)
        sleep_s = target_time - time.monotonic()
        if sleep_s > 0:
            time.sleep(sleep_s)
        frame_status, image = client.snapshot()
        frame_path = frames_dir / ("camera_%03d.jpg" % (index + 1))
        frame_path.write_bytes(image)
        frames.append(
            {
                "index": index + 1,
                "http_status": frame_status,
                "bytes": len(image),
                "output": str(frame_path),
                "elapsed_s": round(time.monotonic() - start_monotonic, 3),
            }
        )
    end_status, end_health = client.health()
    elapsed_s = max(time.monotonic() - start_monotonic, 0.001)
    observed_fps = len(frames) / elapsed_s
    frame_paths = [frame["output"] for frame in frames]
    gif = write_animated_gif(frame_paths, output_dir / "camera.gif", fps)
    mp4 = write_mp4_with_ffmpeg(frames_dir, output_dir / "camera.mp4", fps, skip_mp4=args.skip_mp4)

    start_camera = camera_block(start_health)
    end_camera = camera_block(end_health)
    frame_bytes = [int(frame["bytes"]) for frame in frames]
    min_frame_bytes = min(frame_bytes) if frame_bytes else 0
    issues = []
    if not bool(start_health.get("ok", False)):
        issues.append("health_not_ok")
    if not bool(end_camera.get("enabled", False)):
        issues.append("camera_not_enabled")
    if len(frames) != frames_requested:
        issues.append("missing_camera_frames")
    if min_frame_bytes < int(args.min_frame_bytes):
        issues.append("camera_frame_too_small")
    if not gif.get("ok", False) and not mp4.get("ok", False):
        issues.append("video_output_failed")
    if bool(end_health.get("motion_enabled", False)):
        issues.append("motion_enabled_during_video_capture")
    if abs(float(end_health.get("left_motor", 0.0))) > 0.0001:
        issues.append("left_motor_nonzero")
    if abs(float(end_health.get("right_motor", 0.0))) > 0.0001:
        issues.append("right_motor_nonzero")

    payload = {
        "ok": True,
        "pass": not issues,
        "issues": issues,
        "output_dir": str(output_dir),
        "summary_path": str(output_dir / "camera_video_summary.json"),
        "requested_seconds": seconds,
        "requested_fps": fps,
        "requested_frames": frames_requested,
        "captured_frames": len(frames),
        "elapsed_s": round(elapsed_s, 3),
        "observed_request_fps": round(observed_fps, 3),
        "min_frame_bytes": min_frame_bytes,
        "start_health_status": start_status,
        "end_health_status": end_status,
        "start_camera": start_camera,
        "end_camera": end_camera,
        "gif": gif,
        "mp4": mp4,
        "frames_dir": str(frames_dir),
        "frames": frames,
    }
    Path(payload["summary_path"]).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def run_action(args):
    require_motion_confirmation(args)
    request_payload = common_request_payload(args)
    if args.dry_run:
        return build_summary(args, request_payload, response={"ok": True, "dry_run": True})

    client = BridgeClient(args.base_url, args.timeout_s)
    try:
        if args.action == "health":
            status, payload = client.health()
        elif args.action == "events":
            status, payload = client.events()
        elif args.action == "event":
            status, payload = client.operator_event(args.event, args.note)
        elif args.action == "stop":
            status, payload = client.stop(args.source)
        elif args.action == "cmd-vel":
            status, payload = client.cmd_vel(args.linear_x, args.angular_z, args.duration_s, args.source)
        elif args.action == "motors":
            status, payload = client.motors(args.left, args.right, args.duration_s, args.source)
        elif args.action == "snapshot":
            status, image = client.snapshot()
            output_path = Path(args.output or default_snapshot_path())
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image)
            payload = {
                "ok": True,
                "output": str(output_path),
                "bytes": len(image),
            }
        elif args.action == "camera-diagnostics":
            status = 200
            payload = run_camera_diagnostics(client, args)
        elif args.action == "record-video":
            status = 200
            payload = run_camera_video_capture(client, args)
        else:
            raise BridgeClientError("unsupported_action:%s" % args.action)
        if getattr(args, "expect_refusal", False):
            raise BridgeClientError("expected_refusal_but_request_succeeded")
        return build_summary(args, request_payload, http_status=status, response=payload)
    except BridgeHttpError as exc:
        if getattr(args, "expect_refusal", False) and exc.status_code == 423:
            return build_summary(
                args,
                request_payload,
                http_status=exc.status_code,
                response=exc.payload,
                error="expected_refusal",
            )
        raise


def add_common(parser):
    parser.add_argument(
        "--base-url",
        default=os.environ.get("CHASECAR_FACTORY_BRIDGE_URL", DEFAULT_BASE_URL),
        help="Factory bridge URL. Default: %(default)s",
    )
    parser.add_argument("--timeout-s", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--summary-path", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pretty", action="store_true")


def build_parser():
    parser = argparse.ArgumentParser(description="Talk to the Chasecar factory bridge from the laptop.")
    add_common(parser)
    subparsers = parser.add_subparsers(dest="action", required=True)

    subparsers.add_parser("health", help="Read bridge health.")
    subparsers.add_parser("events", help="Read recent bridge events.")

    snapshot = subparsers.add_parser("snapshot", help="Save one camera frame.")
    snapshot.add_argument("--output", default="", help="JPEG output path.")

    camera_diagnostics = subparsers.add_parser(
        "camera-diagnostics",
        help="Capture several camera frames and score camera readiness before movement.",
    )
    camera_diagnostics.add_argument("--frames", type=int, default=8)
    camera_diagnostics.add_argument("--interval-s", type=float, default=0.2)
    camera_diagnostics.add_argument("--output-dir", default="")
    camera_diagnostics.add_argument("--min-fps", type=float, default=2.0)
    camera_diagnostics.add_argument("--max-frame-age-s", type=float, default=1.0)
    camera_diagnostics.add_argument("--min-frame-bytes", type=int, default=100)

    record_video = subparsers.add_parser(
        "record-video",
        help="Record a short camera clip without sending any motion command.",
    )
    record_video.add_argument("--seconds", type=float, default=3.0)
    record_video.add_argument("--fps", type=float, default=5.0)
    record_video.add_argument("--output-dir", default="")
    record_video.add_argument("--min-frame-bytes", type=int, default=100)
    record_video.add_argument("--skip-mp4", action="store_true")

    event = subparsers.add_parser("event", help="Record an operator event on the bridge.")
    event.add_argument("--event", required=True)
    event.add_argument("--note", default="")

    stop = subparsers.add_parser("stop", help="Send a safety stop.")
    stop.add_argument("--source", default="chasecar_bridge_client:stop")

    cmd_vel = subparsers.add_parser("cmd-vel", help="Send one bounded Chasecar-style cmd_vel command.")
    cmd_vel.add_argument("--linear-x", type=float, required=True)
    cmd_vel.add_argument("--angular-z", type=float, required=True)
    cmd_vel.add_argument("--duration-s", type=float, default=0.25)
    cmd_vel.add_argument("--source", default="chasecar_bridge_client:cmd_vel")
    cmd_vel.add_argument("--confirm-motion", action="store_true")
    cmd_vel.add_argument("--expect-refusal", action="store_true")

    motors = subparsers.add_parser("motors", help="Send one bounded direct motor command.")
    motors.add_argument("--left", type=float, required=True)
    motors.add_argument("--right", type=float, required=True)
    motors.add_argument("--duration-s", type=float, default=0.25)
    motors.add_argument("--source", default="chasecar_bridge_client:motors")
    motors.add_argument("--confirm-motion", action="store_true")
    motors.add_argument("--expect-refusal", action="store_true")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        summary = run_action(args)
        print_summary(args, summary)
        return 0
    except BridgeHttpError as exc:
        summary = build_summary(
            args,
            common_request_payload(args),
            http_status=exc.status_code,
            response=exc.payload,
            error="bridge_http_%s" % exc.status_code,
        )
        print_summary(args, summary)
        return 1
    except BridgeClientError as exc:
        summary = build_summary(args, common_request_payload(args), error=str(exc))
        print_summary(args, summary)
        return 2


if __name__ == "__main__":
    sys.exit(main())
