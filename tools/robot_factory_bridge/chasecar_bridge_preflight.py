#!/usr/bin/env python3
"""Safe one-command preflight for the Chasecar factory bridge."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import time

import chasecar_bridge_client as bridge_client


def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def utc_stamp():
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def ensure_dir(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path, payload):
    path = Path(path)
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def default_artifact_dir():
    return Path("artifacts") / "session" / ("factory_bridge_safe_preflight_%s" % utc_stamp())


def build_summary(args, artifact_dir):
    return {
        "generated_utc": utc_now(),
        "base_url": bridge_client.normalize_base_url(args.base_url),
        "artifact_dir": str(artifact_dir),
        "pass": False,
        "issues": [],
        "steps": [],
        "artifacts": {},
    }


def append_issue(summary, issue):
    summary.setdefault("issues", []).append(issue)


def motor_value(health, key):
    try:
        return float(health.get(key, 0.0))
    except Exception:
        return 0.0


def check_health(summary, label, status, health, require_motion_locked=True):
    if status != 200 or not bool(health.get("ok", False)):
        append_issue(summary, "%s_health_not_ok" % label)
    if require_motion_locked and bool(health.get("motion_enabled", False)):
        append_issue(summary, "%s_motion_enabled" % label)
    if abs(motor_value(health, "left_motor")) > 0.0001:
        append_issue(summary, "%s_left_motor_nonzero" % label)
    if abs(motor_value(health, "right_motor")) > 0.0001:
        append_issue(summary, "%s_right_motor_nonzero" % label)
    camera = health.get("camera") if isinstance(health, dict) else None
    if not isinstance(camera, dict) or not bool(camera.get("enabled", False)):
        append_issue(summary, "%s_camera_not_enabled" % label)


def camera_diag_args(args, output_dir):
    return SimpleNamespace(
        frames=args.camera_frames,
        interval_s=args.camera_interval_s,
        output_dir=str(output_dir),
        min_fps=args.min_camera_fps,
        max_frame_age_s=args.max_frame_age_s,
        min_frame_bytes=args.min_frame_bytes,
    )


def video_args(args, output_dir):
    return SimpleNamespace(
        seconds=args.video_seconds,
        fps=args.video_fps,
        output_dir=str(output_dir),
        min_frame_bytes=args.min_frame_bytes,
        skip_mp4=args.skip_mp4,
    )


def save_snapshot(client, output_path):
    status, image = client.snapshot()
    output_path = Path(output_path)
    ensure_dir(output_path.parent)
    output_path.write_bytes(image)
    return {
        "http_status": status,
        "output": str(output_path),
        "bytes": len(image),
    }


def run_command_refusal_check(client, summary, initial_health):
    if bool(initial_health.get("motion_enabled", False)):
        summary["steps"].append(
            {
                "label": "command_refusal_skipped",
                "reason": "motion_enabled_at_start",
            }
        )
        append_issue(summary, "command_refusal_skipped_motion_enabled")
        return

    try:
        status, payload = client.cmd_vel(
            0.0,
            0.0,
            0.1,
            "factory_bridge_safe_preflight:zero_cmd_vel_refusal",
        )
        summary["steps"].append(
            {
                "label": "zero_cmd_vel_refusal",
                "http_status": status,
                "response": payload,
                "expected_refusal": False,
            }
        )
        append_issue(summary, "zero_cmd_vel_refusal_unexpected_success")
    except bridge_client.BridgeHttpError as exc:
        expected = exc.status_code == 423
        summary["steps"].append(
            {
                "label": "zero_cmd_vel_refusal",
                "http_status": exc.status_code,
                "response": exc.payload,
                "expected_refusal": expected,
            }
        )
        if not expected:
            append_issue(summary, "zero_cmd_vel_refusal_status_unexpected:%s" % exc.status_code)


def run_preflight(args):
    artifact_dir = ensure_dir(args.artifact_dir or default_artifact_dir())
    summary = build_summary(args, artifact_dir)
    client = bridge_client.BridgeClient(args.base_url, args.timeout_s)

    initial_status, initial_health = client.health()
    summary["artifacts"]["initial_health"] = {
        "http_status": initial_status,
        "response": initial_health,
    }
    summary["steps"].append({"label": "initial_health", "http_status": initial_status})
    check_health(summary, "initial", initial_status, initial_health)

    diagnostics = bridge_client.run_camera_diagnostics(
        client,
        camera_diag_args(args, artifact_dir / "camera_diagnostics"),
    )
    summary["artifacts"]["camera_diagnostics"] = diagnostics
    summary["steps"].append(
        {
            "label": "camera_diagnostics",
            "pass": bool(diagnostics.get("pass", False)),
            "captured_frames": diagnostics.get("captured_frames"),
            "observed_request_fps": diagnostics.get("observed_request_fps"),
        }
    )
    if not bool(diagnostics.get("pass", False)):
        append_issue(summary, "camera_diagnostics_failed")

    snapshot = save_snapshot(client, artifact_dir / "snapshot.jpg")
    summary["artifacts"]["snapshot"] = snapshot
    summary["steps"].append({"label": "snapshot", "bytes": snapshot["bytes"]})

    if not args.skip_video:
        video = bridge_client.run_camera_video_capture(
            client,
            video_args(args, artifact_dir / "camera_video"),
        )
        summary["artifacts"]["camera_video"] = video
        summary["steps"].append(
            {
                "label": "camera_video",
                "pass": bool(video.get("pass", False)),
                "captured_frames": video.get("captured_frames"),
                "gif": video.get("gif", {}),
                "mp4": video.get("mp4", {}),
            }
        )
        if not bool(video.get("pass", False)):
            append_issue(summary, "camera_video_failed")

    if args.skip_command_refusal:
        summary["steps"].append({"label": "command_refusal_skipped", "reason": "operator_requested"})
    else:
        run_command_refusal_check(client, summary, initial_health)

    final_status, final_health = client.health()
    summary["artifacts"]["final_health"] = {
        "http_status": final_status,
        "response": final_health,
    }
    summary["steps"].append({"label": "final_health", "http_status": final_status})
    check_health(summary, "final", final_status, final_health)

    summary["pass"] = not summary["issues"]
    summary_path = artifact_dir / "safe_preflight_summary.json"
    summary["summary_path"] = str(summary_path)
    write_json(summary_path, summary)
    return summary


def build_parser():
    parser = argparse.ArgumentParser(description="Run the safe Chasecar factory bridge preflight.")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("CHASECAR_FACTORY_BRIDGE_URL", bridge_client.DEFAULT_BASE_URL),
    )
    parser.add_argument("--timeout-s", type=float, default=bridge_client.DEFAULT_TIMEOUT_S)
    parser.add_argument("--artifact-dir", default="")
    parser.add_argument("--pretty", action="store_true")

    parser.add_argument("--camera-frames", type=int, default=8)
    parser.add_argument("--camera-interval-s", type=float, default=0.2)
    parser.add_argument("--min-camera-fps", type=float, default=2.0)
    parser.add_argument("--max-frame-age-s", type=float, default=1.0)
    parser.add_argument("--min-frame-bytes", type=int, default=100)

    parser.add_argument("--video-seconds", type=float, default=3.0)
    parser.add_argument("--video-fps", type=float, default=5.0)
    parser.add_argument("--skip-video", action="store_true")
    parser.add_argument("--skip-mp4", action="store_true")
    parser.add_argument("--skip-command-refusal", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        summary = run_preflight(args)
    except Exception as exc:
        artifact_dir = ensure_dir(getattr(args, "artifact_dir", "") or default_artifact_dir())
        summary = {
            "generated_utc": utc_now(),
            "base_url": bridge_client.normalize_base_url(getattr(args, "base_url", bridge_client.DEFAULT_BASE_URL)),
            "artifact_dir": str(artifact_dir),
            "pass": False,
            "issues": ["preflight_exception:%r" % (exc,)],
            "summary_path": str(artifact_dir / "safe_preflight_summary.json"),
        }
        write_json(summary["summary_path"], summary)
    print(json.dumps(summary, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if summary.get("pass", False) else 1


if __name__ == "__main__":
    sys.exit(main())
