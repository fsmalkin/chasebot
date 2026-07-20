#!/usr/bin/env python3
"""Run a reusable color-target closed-loop smoke against the factory bridge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import time
from typing import Any

import chasecar_bridge_behavior_runner as behavior_runner
import chasecar_bridge_client as bridge_client


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_SOURCE_PATH = "$HOME/ros2_ws/src/chasecar_runtime"
DEFAULT_ARTIFACT_STEM = "factory_bridge_color_target_smoke"
CONSERVATIVE_MAX_BRIDGE_ANGULAR_Z = 0.8
STRONG_TURN_MAX_BRIDGE_ANGULAR_Z = 2.5
STRONG_TURN_MAX_RELAY_WINDOW_S = 4.5
STRONG_TURN_MAX_COMMAND_DURATION_S = 0.25
PROFILE_DEFAULTS: dict[str, dict[str, float]] = {
    "blue": {
        "target_min_saturation": 0.25,
        "target_min_value": 0.20,
        "target_border_margin_ratio": 0.02,
        "target_max_area_ratio": 0.25,
        "target_max_bbox_width_ratio": 0.85,
        "target_max_bbox_height_ratio": 0.90,
    },
    "red": {
        "target_border_margin_ratio": 0.02,
        "target_max_area_ratio": 0.05,
        "target_max_bbox_height_ratio": 0.25,
        "target_min_bbox_aspect_ratio": 1.30,
        "target_max_bbox_aspect_ratio": 5.00,
    },
    "yellow": {
        "target_border_margin_ratio": 0.08,
        "target_max_area_ratio": 0.06,
        "target_max_bbox_height_ratio": 0.30,
        "target_min_bbox_aspect_ratio": 0.80,
        "target_max_bbox_aspect_ratio": 6.00,
    },
}


class GateFailed(Exception):
    pass


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def utc_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def ensure_dir(path: Path | str) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path | str, payload: dict[str, Any]) -> None:
    path = Path(path)
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def replace_with_retries(source: Path, target: Path, *, timeout_s: float = 2.0) -> None:
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            source.replace(target)
            return
        except PermissionError as exc:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.05)


def load_json(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def default_artifact_dir() -> Path:
    return Path("artifacts") / "session" / ("%s_%s" % (DEFAULT_ARTIFACT_STEM, utc_stamp()))


def windows_path_to_wsl(path: Path | str) -> str:
    resolved = Path(path).resolve()
    drive = resolved.drive.rstrip(":").lower()
    if not drive:
        return resolved.as_posix()
    parts = [part for part in resolved.parts[1:]]
    return "/mnt/%s/%s" % (drive, "/".join(parts))


def profile_value(args: argparse.Namespace, name: str) -> str:
    override = getattr(args, name, None)
    if override is not None:
        return str(override)
    defaults = PROFILE_DEFAULTS.get(args.target_profile, {})
    if name in defaults:
        return str(defaults[name])
    behavior_defaults = behavior_runner.build_parser().parse_args(["--mode", "visual-advisor"])
    return str(getattr(behavior_defaults, name))


def build_behavior_args(args: argparse.Namespace) -> argparse.Namespace:
    argv = [
        "--mode",
        "visual-advisor",
        "--target-profile",
        args.target_profile,
        "--target-min-saturation",
        profile_value(args, "target_min_saturation"),
        "--target-min-value",
        profile_value(args, "target_min_value"),
        "--target-min-luma",
        profile_value(args, "target_min_luma"),
        "--target-border-margin-ratio",
        profile_value(args, "target_border_margin_ratio"),
        "--target-min-area-ratio",
        profile_value(args, "target_min_area_ratio"),
        "--target-max-area-ratio",
        profile_value(args, "target_max_area_ratio"),
        "--target-max-bbox-width-ratio",
        profile_value(args, "target_max_bbox_width_ratio"),
        "--target-max-bbox-height-ratio",
        profile_value(args, "target_max_bbox_height_ratio"),
        "--target-min-bbox-aspect-ratio",
        profile_value(args, "target_min_bbox_aspect_ratio"),
        "--target-max-bbox-aspect-ratio",
        profile_value(args, "target_max_bbox_aspect_ratio"),
        "--visual-center-deadband",
        str(args.visual_center_deadband),
        "--visual-turn-sign",
        str(args.visual_turn_sign),
        "--visual-angular-gain",
        str(args.visual_angular_gain),
        "--max-visual-angular-z",
        str(args.max_visual_angular_z),
        "--visual-forward-x",
        str(args.visual_forward_x),
        "--max-visual-linear-x",
        str(args.max_visual_linear_x),
        "--forward-stop-area-ratio",
        str(args.forward_stop_area_ratio),
        "--visual-command-duration-s",
        str(args.command_duration_s),
    ]
    if args.allow_forward:
        argv.append("--allow-forward")
    return behavior_runner.build_parser().parse_args(argv)


def command_from_analysis(analysis: dict[str, Any]) -> dict[str, float]:
    if not bool(analysis.get("detected", False)):
        return {"linear_x": 0.0, "angular_z": 0.0}
    recommendation = analysis.get("recommendation") if isinstance(analysis.get("recommendation"), dict) else {}
    return {
        "linear_x": float(recommendation.get("linear_x", 0.0) or 0.0),
        "angular_z": float(recommendation.get("angular_z", 0.0) or 0.0),
    }


def runtime_payload(
    *,
    sequence: int,
    mode: str,
    source: str,
    analysis: dict[str, Any] | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    detected = bool(analysis and analysis.get("detected", False))
    command = command_from_analysis(analysis or {})
    drive_enabled = detected if enabled is None else bool(enabled)
    if not drive_enabled:
        command = {"linear_x": 0.0, "angular_z": 0.0}
    return {
        "manual_drive": {
            "enabled": drive_enabled,
            "sequence": int(sequence),
            "mode": mode,
            "updated_utc": utc_now(),
            "command": command,
            "rationale": "Live color-target camera detection drives Chasecar-style cmd_vel.",
            "source": source,
        },
        "perception": {
            "target_profile": (analysis or {}).get("target_profile", ""),
            "detected": detected,
            "analysis": analysis or {},
        },
    }


def zero_runtime_payload(sequence: int, mode: str, source: str) -> dict[str, Any]:
    return runtime_payload(sequence=sequence, mode=mode, source=source, analysis=None, enabled=False)


def nonzero_relay_events(relay_summary: dict[str, Any]) -> list[dict[str, Any]]:
    events = relay_summary.get("relay", {}).get("events", [])
    nonzero = []
    for event in events if isinstance(events, list) else []:
        payload = event.get("payload") if isinstance(event, dict) else {}
        if not isinstance(payload, dict):
            continue
        if abs(float(payload.get("linear_x", 0.0) or 0.0)) > 1.0e-6:
            nonzero.append(event)
            continue
        if abs(float(payload.get("angular_z", 0.0) or 0.0)) > 1.0e-6:
            nonzero.append(event)
    return nonzero


def phase_records_detected(loop_summary: dict[str, Any]) -> bool:
    records = loop_summary.get("records", [])
    summary = phase_detection_summary(loop_summary)
    return bool(summary["stable"])


def phase_detection_summary(loop_summary: dict[str, Any]) -> dict[str, Any]:
    records = loop_summary.get("records", [])
    total = len(records) if isinstance(records, list) else 0
    detected = sum(1 for record in records if isinstance(record, dict) and bool(record.get("detected", False)))
    final_detected = bool(records and isinstance(records[-1], dict) and records[-1].get("detected", False))
    required = max(1, total - 1) if total else 0
    return {
        "total_frames": total,
        "detected_frames": detected,
        "required_detected_frames": required,
        "final_frame_detected": final_detected,
        "stable": bool(total > 0 and detected >= required and final_detected),
    }


def phase_center_error_summary(loop_summary: dict[str, Any]) -> dict[str, Any]:
    records = loop_summary.get("records", [])
    values = [
        abs(float(record["center_error"]))
        for record in records
        if isinstance(record, dict) and record.get("center_error") is not None
    ]
    if not values:
        return {
            "available": False,
            "max_abs_center_error": None,
            "start_abs_center_error": None,
            "end_abs_center_error": None,
            "improved_or_controlled": False,
        }
    return {
        "available": True,
        "max_abs_center_error": max(values),
        "start_abs_center_error": values[0],
        "end_abs_center_error": values[-1],
        "improved_or_controlled": bool(values[-1] <= values[0] or max(values) <= 0.35),
    }


def append_issue(summary: dict[str, Any], issue: str) -> None:
    issues = summary.setdefault("issues", [])
    if issue not in issues:
        issues.append(issue)


def safe_final_state(final_health: dict[str, Any]) -> bool:
    response = final_health.get("response") if isinstance(final_health.get("response"), dict) else final_health
    return bool(
        response.get("motion_enabled") is False
        and abs(float(response.get("left_motor", 0.0) or 0.0)) < 1.0e-6
        and abs(float(response.get("right_motor", 0.0) or 0.0)) < 1.0e-6
    )


def camera_readiness_summary(client: bridge_client.BridgeClient, args: argparse.Namespace, phase: str) -> dict[str, Any]:
    deadline = time.monotonic() + max(0.0, float(args.camera_ready_timeout_s))
    checks = []
    while True:
        check: dict[str, Any] = {"checked_utc": utc_now()}
        try:
            status, health = client.health()
            camera = health.get("camera", {}) if isinstance(health, dict) else {}
            check.update(
                {
                    "http_status": status,
                    "camera": camera,
                    "ok": bool(health.get("ok", False)) if isinstance(health, dict) else False,
                }
            )
            cached_fps = float(camera.get("cached_fps", 0.0) or 0.0)
            frame_age_s = camera.get("frame_age_s")
            cached_bytes = int(camera.get("cached_bytes", 0) or 0)
            ready = (
                status == 200
                and bool(camera.get("enabled", False))
                and bool(camera.get("loaded", False))
                and cached_fps >= float(args.camera_min_fps)
                and cached_bytes >= int(args.camera_min_frame_bytes)
                and frame_age_s is not None
                and float(frame_age_s) <= float(args.camera_max_frame_age_s)
            )
            check["ready"] = bool(ready)
            checks.append(check)
            if ready:
                break
        except Exception as exc:
            check.update({"ready": False, "error": repr(exc)})
            checks.append(check)
        if time.monotonic() >= deadline:
            break
        time.sleep(0.25)

    latest = checks[-1] if checks else {}
    latest_camera = latest.get("camera", {}) if isinstance(latest.get("camera"), dict) else {}
    issues = []
    if not latest.get("ready", False):
        if not bool(latest_camera.get("enabled", False)):
            issues.append("camera_not_enabled")
        if not bool(latest_camera.get("loaded", False)):
            issues.append("camera_not_loaded")
        if int(latest_camera.get("cached_bytes", 0) or 0) < int(args.camera_min_frame_bytes):
            issues.append("camera_frame_too_small")
        if float(latest_camera.get("cached_fps", 0.0) or 0.0) < float(args.camera_min_fps):
            issues.append("camera_fps_below_min")
        frame_age_s = latest_camera.get("frame_age_s")
        if frame_age_s is None or float(frame_age_s) > float(args.camera_max_frame_age_s):
            issues.append("camera_frame_stale_or_missing")
        if latest_camera.get("error"):
            issues.append("camera_error:%s" % latest_camera.get("error"))
        if latest.get("error"):
            issues.append("health_error:%s" % latest.get("error"))

    return {
        "phase": phase,
        "pass": bool(latest.get("ready", False)),
        "checks": checks,
        "latest": latest,
        "issues": issues,
        "limits": {
            "timeout_s": float(args.camera_ready_timeout_s),
            "min_fps": float(args.camera_min_fps),
            "max_frame_age_s": float(args.camera_max_frame_age_s),
            "min_frame_bytes": int(args.camera_min_frame_bytes),
        },
    }


def compute_pass(summary: dict[str, Any]) -> bool:
    if summary.get("issues"):
        return False
    locked = summary.get("locked_relay_proof", {})
    locked_counters = locked.get("relay_counters", {})
    locked_ok = (
        phase_records_detected(locked)
        and int(locked_counters.get("messages_received", 0) or 0) > 0
        and int(locked_counters.get("http_refusals", 0) or 0) > 0
    )
    if not locked_ok:
        return False
    if not bool(summary.get("execute_motion", False)):
        return True
    motion = summary.get("motion_proof", {})
    motion_counters = motion.get("relay_counters", {})
    motion_ok = (
        phase_records_detected(motion)
        and bool(motion.get("center_error_summary", {}).get("improved_or_controlled", False))
        and int(motion_counters.get("http_errors", 0) or 0) == 0
        and int(motion_counters.get("cmd_vel_posts", 0) or 0) > 0
        and int(motion.get("nonzero_event_count", 0) or 0) > 0
        and bool(summary.get("visual_motion", {}).get("movement_detected", False))
        and safe_final_state(summary.get("final_locked_health", {}))
    )
    return bool(motion_ok)


def run_camera_loop(
    *,
    client: bridge_client.BridgeClient,
    args: argparse.Namespace,
    behavior_args: argparse.Namespace,
    artifact_dir: Path,
    runtime_path: Path,
    mode: str,
    source: str,
) -> dict[str, Any]:
    frames_dir = ensure_dir(artifact_dir / "camera_loop")
    records = []
    annotated_paths = []
    for index in range(1, int(args.loop_frames) + 1):
        status, image_bytes = bridge_client.snapshot_with_retries(
            client,
            attempts=args.snapshot_attempts,
            interval_s=args.snapshot_retry_interval_s,
        )
        frame_path = frames_dir / ("frame_%03d.jpg" % index)
        annotated_path = frames_dir / ("annotated_%03d.jpg" % index)
        frame_path.write_bytes(image_bytes)
        analysis = behavior_runner.analyze_target_image(frame_path, behavior_args, annotated_path=annotated_path)
        payload = runtime_payload(
            sequence=index,
            mode=mode,
            source=source,
            analysis=analysis,
        )
        tmp_path = runtime_path.with_suffix(".tmp")
        write_json(tmp_path, payload)
        replace_with_retries(tmp_path, runtime_path)
        records.append(
            {
                "index": index,
                "http_status": status,
                "frame_path": str(frame_path),
                "annotated_path": str(annotated_path),
                "detected": bool(analysis.get("detected", False)),
                "command": payload["manual_drive"]["command"],
                "center_error": analysis.get("center_error"),
                "area_ratio": analysis.get("area_ratio"),
                "bbox": analysis.get("bbox"),
                "issues": analysis.get("issues", []),
            }
        )
        annotated_paths.append(annotated_path)
        if index < int(args.loop_frames) and args.loop_interval_s > 0:
            time.sleep(float(args.loop_interval_s))

    write_json(runtime_path, zero_runtime_payload(99, "%s_complete" % mode, "%s:complete" % source))
    labels = ["%s %02d" % (args.target_profile, index) for index in range(1, len(annotated_paths) + 1)]
    contact_sheet = behavior_runner.maybe_make_contact_sheet(
        annotated_paths,
        labels,
        frames_dir / "annotated_contact_sheet.jpg",
    )
    summary = {
        "records": records,
        "detection_summary": phase_detection_summary({"records": records}),
        "center_error_summary": phase_center_error_summary({"records": records}),
        "runtime_path": str(runtime_path),
        "contact_sheet": contact_sheet.get("output", "") if isinstance(contact_sheet, dict) else "",
        "contact_sheet_result": contact_sheet,
    }
    write_json(artifact_dir / "visual_chase_loop_summary.json", summary)
    return summary


def relay_bash(args: argparse.Namespace, artifact_dir: Path, runtime_path: Path, *, require_motion_enabled: bool) -> str:
    artifact_wsl = windows_path_to_wsl(artifact_dir)
    runtime_wsl = windows_path_to_wsl(runtime_path)
    require_flag = " \\\n  --require-motion-enabled" if require_motion_enabled else ""
    relay_start_poll_count = max(1, int(float(args.relay_start_timeout_s) * 2.0 + 0.999))
    return f"""set -eo pipefail
source /opt/ros/{args.ros_distro}/setup.bash
cd "{args.runtime_source_path}"
ART="{artifact_wsl}"
RUNTIME="{runtime_wsl}"
mkdir -p "$ART"
stop_child() {{
  child_pid="$1"
  if ! kill -0 "$child_pid" 2>/dev/null; then
    return 0
  fi
  kill -INT "$child_pid" 2>/dev/null || true
  for _ in 1 2 3 4 5; do
    if ! kill -0 "$child_pid" 2>/dev/null; then
      return 0
    fi
    sleep 0.2
  done
  kill -TERM "$child_pid" 2>/dev/null || true
  for _ in 1 2 3 4 5; do
    if ! kill -0 "$child_pid" 2>/dev/null; then
      return 0
    fi
    sleep 0.2
  done
  kill -KILL "$child_pid" 2>/dev/null || true
}}
python3 scripts/gather_motion_bridge.py \\
  --runtime-json "$RUNTIME" \\
  --loop-rate-hz {args.gather_loop_rate_hz} \\
  --max-linear-x {args.max_visual_linear_x} \\
  --max-angular-z {args.max_visual_angular_z} \\
  --no-use-sim-time \\
  > "$ART/gather_motion_bridge_stdout.log" 2> "$ART/gather_motion_bridge_stderr.log" &
gather_pid=$!
python3 ros2_scripts/factory_bridge_cmd_vel_relay.py \\
  --base-url {args.base_url} \\
  --summary-path "$ART/relay_summary.json" \\
  --twist-topics /cmd_vel \\
  --twist-stamped-topics "" \\
  --linear-scale {args.linear_scale} \\
  --angular-scale {args.angular_scale} \\
  --max-bridge-linear-x {args.max_bridge_linear_x} \\
  --max-bridge-angular-z {args.max_bridge_angular_z} \\
  --command-duration-s {args.command_duration_s} \\
  --post-rate-hz {args.post_rate_hz} \\
  --stale-stop-s {args.stale_stop_s}{require_flag} \\
  > "$ART/relay_stdout.log" 2> "$ART/relay_stderr.log" &
relay_pid=$!
for _ in $(seq 1 {relay_start_poll_count}); do
  if [ -s "$ART/relay_summary.json" ]; then
    break
  fi
  if ! kill -0 "$relay_pid" 2>/dev/null; then
    break
  fi
  sleep 0.5
done
sleep {args.relay_window_s}
stop_child "$gather_pid"
stop_child "$relay_pid"
wait "$gather_pid" 2>/dev/null || true
wait "$relay_pid" 2>/dev/null || true
"""


def run_relay_phase(
    *,
    client: bridge_client.BridgeClient,
    args: argparse.Namespace,
    behavior_args: argparse.Namespace,
    artifact_dir: Path,
    mode: str,
    source: str,
    require_motion_enabled: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    ensure_dir(artifact_dir)
    runtime_path = artifact_dir / "visual_chase_runtime.json"
    write_json(runtime_path, zero_runtime_payload(0, "%s_idle" % mode, "%s:init" % source))
    relay_summary_path = artifact_dir / "relay_summary.json"
    bash = relay_bash(args, artifact_dir, runtime_path, require_motion_enabled=require_motion_enabled)
    script_path = artifact_dir / "relay_phase.sh"
    script_path.write_text(bash, encoding="utf-8", newline="\n")
    stdout_path = artifact_dir / "wsl_stdout.log"
    stderr_path = artifact_dir / "wsl_stderr.log"
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(
            ["wsl", "-d", args.distro, "--", "bash", windows_path_to_wsl(script_path)],
            cwd=str(REPO_ROOT),
            stdout=stdout,
            stderr=stderr,
        )
        try:
            deadline = time.monotonic() + float(args.relay_start_timeout_s)
            while not relay_summary_path.exists():
                if process.poll() is not None:
                    raise RuntimeError("relay_process_exited_before_summary")
                if time.monotonic() >= deadline:
                    raise RuntimeError("relay_summary_not_created")
                time.sleep(0.2)
            loop_summary = run_camera_loop(
                client=client,
                args=args,
                behavior_args=behavior_args,
                artifact_dir=artifact_dir,
                runtime_path=runtime_path,
                mode=mode,
                source=source,
            )
            exit_code = process.wait(timeout=float(args.relay_finish_timeout_s))
            if exit_code != 0:
                raise RuntimeError("relay_process_failed:%s" % exit_code)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
    relay_summary = load_json(relay_summary_path)
    return loop_summary, relay_summary


def deploy_bridge(args: argparse.Namespace, artifact_dir: Path, *, enable_motion: bool) -> dict[str, Any]:
    if args.skip_deploy:
        return {"skipped": True, "enable_motion": bool(enable_motion)}
    command = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(REPO_ROOT / "scripts" / "deploy_robot_factory_bridge.ps1"),
        "-RobotHost",
        args.robot_host,
        "-RobotUser",
        args.robot_user,
        "-Port",
        str(args.port),
        "-Start",
        "-Camera",
        "-CameraBackend",
        args.camera_backend,
        "-CameraFps",
        str(args.camera_fps),
        "-CameraJpegQuality",
        str(args.camera_jpeg_quality),
        "-CameraV4l2Device",
        args.camera_v4l2_device,
        "-CameraV4l2RawWidth",
        str(args.camera_v4l2_raw_width),
        "-CameraV4l2RawHeight",
        str(args.camera_v4l2_raw_height),
        "-CameraV4l2Pixelformat",
        args.camera_v4l2_pixelformat,
    ]
    if enable_motion:
        command.extend(["-EnableMotion", "-MaxMotorSpeed", str(args.max_motor_speed)])
    result = subprocess.run(command, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=args.deploy_timeout_s)
    payload = {
        "skipped": False,
        "enable_motion": bool(enable_motion),
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    write_json(artifact_dir / ("deploy_motion.json" if enable_motion else "deploy_locked.json"), payload)
    if result.returncode != 0:
        raise RuntimeError("deploy_bridge_failed:%s" % result.returncode)
    return payload


def save_snapshot(client: bridge_client.BridgeClient, path: Path, args: argparse.Namespace) -> dict[str, Any]:
    status, image_bytes = bridge_client.snapshot_with_retries(
        client,
        attempts=args.snapshot_attempts,
        interval_s=args.snapshot_retry_interval_s,
    )
    ensure_dir(path.parent)
    path.write_bytes(image_bytes)
    return {"http_status": status, "output": str(path), "bytes": len(image_bytes)}


def score_visual_motion(before_path: Path, after_path: Path, artifact_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    score_args = SimpleNamespace(
        min_visual_shift_px=args.min_visual_shift_px,
        min_visual_shift_score_gain=args.min_visual_shift_score_gain,
        max_static_visual_similarity=args.max_static_visual_similarity,
    )
    score = behavior_runner.analyze_visual_motion(before_path, [after_path], ["after_post_relock"], score_args)
    contact = behavior_runner.maybe_make_contact_sheet(
        [before_path, after_path],
        ["before color-target smoke", "after post-relock"],
        artifact_dir / "before_after_color_target_smoke.jpg",
    )
    score["contact_sheet_path"] = contact.get("output", "") if isinstance(contact, dict) else ""
    score["contact_sheet_result"] = contact
    write_json(artifact_dir / "visual_motion_score.json", score)
    return score


def summarize_phase(loop_summary: dict[str, Any], relay_summary: dict[str, Any], artifact_dir: Path) -> dict[str, Any]:
    return {
        "artifact_dir": str(artifact_dir),
        "records": loop_summary.get("records", []),
        "contact_sheet": loop_summary.get("contact_sheet", ""),
        "detection_summary": phase_detection_summary(loop_summary),
        "center_error_summary": phase_center_error_summary(loop_summary),
        "relay_counters": relay_summary.get("relay", {}).get("counters", {}),
        "last_input": relay_summary.get("relay", {}).get("last_input", {}),
        "issues": relay_summary.get("issues", []),
    }


def validate_safety_args(args: argparse.Namespace) -> list[str]:
    issues = []
    if args.execute_motion and not args.confirm_operator_ready:
        issues.append("operator_ready_confirmation_required")
    if args.max_motor_speed > 1.0:
        issues.append("max_motor_speed_above_1")
    if args.max_bridge_linear_x > 0.36:
        issues.append("max_bridge_linear_x_above_conservative_limit")
    if args.allow_strong_turn_proof:
        forward_enabled = (
            bool(args.allow_forward)
            or float(args.max_bridge_linear_x) > 1.0e-6
            or float(args.max_visual_linear_x) > 1.0e-6
            or float(args.visual_forward_x) > 1.0e-6
        )
        if forward_enabled:
            issues.append("strong_turn_proof_requires_no_forward")
        if args.max_bridge_angular_z > STRONG_TURN_MAX_BRIDGE_ANGULAR_Z:
            issues.append("max_bridge_angular_z_above_strong_turn_limit")
        if args.relay_window_s > STRONG_TURN_MAX_RELAY_WINDOW_S:
            issues.append("relay_window_s_above_strong_turn_limit")
        if args.command_duration_s > STRONG_TURN_MAX_COMMAND_DURATION_S:
            issues.append("command_duration_s_above_strong_turn_limit")
    elif args.max_bridge_angular_z > CONSERVATIVE_MAX_BRIDGE_ANGULAR_Z:
        issues.append("max_bridge_angular_z_above_conservative_limit")
    return issues


def run(args: argparse.Namespace) -> dict[str, Any]:
    artifact_root = ensure_dir(args.artifact_dir or default_artifact_dir())
    behavior_args = build_behavior_args(args)
    summary: dict[str, Any] = {
        "generated_utc": utc_now(),
        "type": "factory_bridge_color_target_smoke",
        "artifact_dir": str(artifact_root),
        "base_url": args.base_url,
        "target_profile": args.target_profile,
        "execute_motion": bool(args.execute_motion),
        "issues": validate_safety_args(args),
        "pass": False,
    }
    if args.dry_run:
        summary["pass"] = not summary["issues"]
        summary["plan_only"] = True
        write_json(artifact_root / "goal_summary.json", summary)
        return summary
    if summary["issues"]:
        write_json(artifact_root / "goal_summary.json", summary)
        return summary

    client = bridge_client.BridgeClient(args.base_url, args.timeout_s)
    final_health: dict[str, Any] = {}
    try:
        deploy_bridge(args, artifact_root / "start_locked", enable_motion=False)
        if args.camera_warmup_s > 0:
            time.sleep(float(args.camera_warmup_s))
        start_camera_ready = camera_readiness_summary(client, args, "start_locked")
        summary["camera_readiness_gate"] = start_camera_ready
        if not start_camera_ready["pass"]:
            append_issue(summary, "camera_readiness_gate_not_pass")
            raise GateFailed()
        detection_dir = ensure_dir(artifact_root / "detection_gate")
        detection_runtime = detection_dir / "visual_chase_runtime.json"
        write_json(detection_runtime, zero_runtime_payload(0, "detection_gate_idle", "color_target_smoke:detection_gate:init"))
        detection_loop = run_camera_loop(
            client=client,
            args=args,
            behavior_args=behavior_args,
            artifact_dir=detection_dir,
            runtime_path=detection_runtime,
            mode="detection_gate",
            source="color_target_smoke:detection_gate",
        )
        summary["detection_gate"] = detection_loop
        if not phase_records_detected(detection_loop):
            append_issue(summary, "detection_gate_target_not_stable")
        else:
            locked_dir = ensure_dir(artifact_root / "locked_relay")
            locked_loop, locked_relay = run_relay_phase(
                client=client,
                args=args,
                behavior_args=behavior_args,
                artifact_dir=locked_dir,
                mode="locked_color_target_chase",
                source="color_target_smoke:locked_loop",
                require_motion_enabled=False,
            )
            summary["locked_relay_proof"] = summarize_phase(locked_loop, locked_relay, locked_dir)

            if args.execute_motion:
                motion_dir = ensure_dir(artifact_root / "motion_run")
                summary["motion_before_snapshot"] = save_snapshot(client, motion_dir / "before_locked.jpg", args)
                try:
                    deploy_bridge(args, motion_dir / "enable_motion", enable_motion=True)
                    if args.camera_warmup_s > 0:
                        time.sleep(float(args.camera_warmup_s))
                    motion_camera_ready = camera_readiness_summary(client, args, "motion_enabled")
                    summary["motion_camera_readiness_gate"] = motion_camera_ready
                    if not motion_camera_ready["pass"]:
                        append_issue(summary, "motion_camera_readiness_gate_not_pass")
                    else:
                        motion_loop, motion_relay = run_relay_phase(
                            client=client,
                            args=args,
                            behavior_args=behavior_args,
                            artifact_dir=motion_dir,
                            mode="motion_color_target_chase",
                            source="color_target_smoke:motion_loop",
                            require_motion_enabled=True,
                        )
                        summary["motion_proof"] = summarize_phase(motion_loop, motion_relay, motion_dir)
                        summary["motion_proof"]["nonzero_event_count"] = len(nonzero_relay_events(motion_relay))
                        summary["motion_proof"]["first_nonzero_event"] = (
                            nonzero_relay_events(motion_relay)[0] if nonzero_relay_events(motion_relay) else None
                        )
                finally:
                    try:
                        status, payload = client.stop("color_target_smoke:finally_stop")
                        summary["finally_stop"] = {"http_status": status, "response": payload}
                    except Exception as exc:
                        append_issue(summary, "finally_stop_failed:%r" % (exc,))
                    deploy_bridge(args, motion_dir / "restore_locked", enable_motion=False)
                if "motion_proof" in summary:
                    if args.camera_warmup_s > 0:
                        time.sleep(float(args.camera_warmup_s))
                    summary["motion_after_snapshot"] = save_snapshot(client, motion_dir / "after_post_relock.jpg", args)
                    summary["visual_motion"] = score_visual_motion(
                        Path(summary["motion_before_snapshot"]["output"]),
                        Path(summary["motion_after_snapshot"]["output"]),
                        motion_dir,
                        args,
                    )
    except GateFailed:
        pass
    except Exception as exc:
        append_issue(summary, "runner_exception:%r" % (exc,))
    finally:
        try:
            deploy_bridge(args, artifact_root / "final_restore_locked", enable_motion=False)
        except Exception as exc:
            append_issue(summary, "final_restore_locked_failed:%r" % (exc,))
        try:
            status, payload = client.health()
            final_health = {"http_status": status, "response": payload}
            summary["final_locked_health"] = final_health
        except Exception as exc:
            append_issue(summary, "final_health_failed:%r" % (exc,))

    summary["pass"] = compute_pass(summary)
    write_json(artifact_root / "goal_summary.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a reusable color-target smoke through the factory bridge.")
    parser.add_argument("--base-url", default=bridge_client.DEFAULT_BASE_URL)
    parser.add_argument("--timeout-s", type=float, default=bridge_client.DEFAULT_TIMEOUT_S)
    parser.add_argument("--artifact-dir", default="")
    parser.add_argument("--target-profile", choices=behavior_runner.DEFAULT_VISUAL_SCAN_PROFILES, default="blue")
    parser.add_argument("--execute-motion", action="store_true")
    parser.add_argument("--confirm-operator-ready", action="store_true")
    parser.add_argument("--allow-strong-turn-proof", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pretty", action="store_true")

    parser.add_argument("--distro", default="Ubuntu-24.04")
    parser.add_argument("--ros-distro", default="jazzy")
    parser.add_argument("--runtime-source-path", default=DEFAULT_RUNTIME_SOURCE_PATH)
    parser.add_argument("--robot-host", default="192.168.1.11")
    parser.add_argument("--robot-user", default="jetson")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--skip-deploy", action="store_true")
    parser.add_argument("--deploy-timeout-s", type=float, default=45.0)
    parser.add_argument("--camera-backend", choices=["gstreamer", "jetbotmini", "v4l2_bayer"], default="gstreamer")
    parser.add_argument("--camera-fps", type=float, default=5.0)
    parser.add_argument("--camera-jpeg-quality", type=int, default=55)
    parser.add_argument("--camera-v4l2-device", default="/dev/video0")
    parser.add_argument("--camera-v4l2-raw-width", type=int, default=3264)
    parser.add_argument("--camera-v4l2-raw-height", type=int, default=2464)
    parser.add_argument("--camera-v4l2-pixelformat", default="RG10")

    parser.add_argument("--loop-frames", type=int, default=4)
    parser.add_argument("--loop-interval-s", type=float, default=0.32)
    parser.add_argument("--snapshot-attempts", type=int, default=10)
    parser.add_argument("--snapshot-retry-interval-s", type=float, default=0.15)
    parser.add_argument("--camera-warmup-s", type=float, default=2.0)
    parser.add_argument("--camera-ready-timeout-s", type=float, default=8.0)
    parser.add_argument("--camera-min-fps", type=float, default=2.0)
    parser.add_argument("--camera-max-frame-age-s", type=float, default=1.0)
    parser.add_argument("--camera-min-frame-bytes", type=int, default=100)

    parser.add_argument("--relay-window-s", type=float, default=6.0)
    parser.add_argument("--relay-start-timeout-s", type=float, default=8.0)
    parser.add_argument("--relay-finish-timeout-s", type=float, default=15.0)
    parser.add_argument("--gather-loop-rate-hz", type=float, default=10.0)
    parser.add_argument("--linear-scale", type=float, default=4.0)
    parser.add_argument("--angular-scale", type=float, default=3.0)
    parser.add_argument("--max-bridge-linear-x", type=float, default=0.32)
    parser.add_argument("--max-bridge-angular-z", type=float, default=0.6)
    parser.add_argument("--command-duration-s", type=float, default=0.20)
    parser.add_argument("--post-rate-hz", type=float, default=8.0)
    parser.add_argument("--stale-stop-s", type=float, default=0.45)
    parser.add_argument("--max-motor-speed", type=float, default=0.8)

    parser.add_argument("--allow-forward", dest="allow_forward", action="store_true", default=True)
    parser.add_argument("--no-allow-forward", dest="allow_forward", action="store_false")
    parser.add_argument("--visual-center-deadband", type=float, default=0.16)
    parser.add_argument("--visual-turn-sign", type=float, default=1.0)
    parser.add_argument("--visual-angular-gain", type=float, default=0.8)
    parser.add_argument("--max-visual-angular-z", type=float, default=0.25)
    parser.add_argument("--visual-forward-x", type=float, default=0.08)
    parser.add_argument("--max-visual-linear-x", type=float, default=0.08)
    parser.add_argument("--forward-stop-area-ratio", type=float, default=0.08)

    parser.add_argument("--target-min-luma", type=float, default=None)
    parser.add_argument("--target-min-saturation", type=float, default=None)
    parser.add_argument("--target-min-value", type=float, default=None)
    parser.add_argument("--target-min-area-ratio", type=float, default=None)
    parser.add_argument("--target-max-area-ratio", type=float, default=None)
    parser.add_argument("--target-max-bbox-width-ratio", type=float, default=None)
    parser.add_argument("--target-max-bbox-height-ratio", type=float, default=None)
    parser.add_argument("--target-border-margin-ratio", type=float, default=None)
    parser.add_argument("--target-min-bbox-aspect-ratio", type=float, default=None)
    parser.add_argument("--target-max-bbox-aspect-ratio", type=float, default=None)

    parser.add_argument("--min-visual-shift-px", type=float, default=2.0)
    parser.add_argument("--min-visual-shift-score-gain", type=float, default=0.03)
    parser.add_argument("--max-static-visual-similarity", type=float, default=0.975)
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run(args)
    print(json.dumps(summary, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if summary.get("pass", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
