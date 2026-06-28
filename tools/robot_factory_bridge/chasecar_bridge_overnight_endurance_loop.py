#!/usr/bin/env python3
"""Run repeated safe JetBot Mini stack proofs with optional inverse reset pulses."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from typing import Any

import chasecar_bridge_behavior_runner as behavior_runner
import chasecar_bridge_client as bridge_client
import chasecar_bridge_stack_closed_loop_runner as closed_loop_runner
import chasecar_bridge_stack_path_gate as stack_gate


DEFAULT_ARTIFACT_STEM = "factory_bridge_overnight_endurance_loop"
SUCCESS_STOP_REASONS = {"max_cycles_reached", "max_runtime_reached"}
TARGET_PRESETS: dict[str, dict[str, Any]] = {
    "basement_green_v0": {
        "target_profile": "green",
        "target_min_luma": 20.0,
        "target_min_saturation": 0.12,
        "target_min_value": 0.08,
        "target_min_area_ratio": 0.005,
        "target_max_area_ratio": 0.20,
        "target_max_bbox_width_ratio": 0.35,
        "target_max_bbox_height_ratio": 0.80,
        "target_border_margin_ratio": 0.0,
        "target_min_bbox_aspect_ratio": 0.10,
        "target_max_bbox_aspect_ratio": 0.75,
        "target_min_centroid_y_ratio": 0.0,
        "target_max_centroid_y_ratio": 0.86,
        "yolo_target_min_area_ratio": 0.005,
        "camera_min_fps": 1.0,
        "visual_center_deadband": 0.12,
        "visual_turn_sign": 1.0,
        "stack_acquire_turn_sign": 1.0,
    }
}


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


def default_artifact_dir() -> Path:
    return Path("artifacts") / "session" / ("%s_%s" % (DEFAULT_ARTIFACT_STEM, utc_stamp()))


def safe_health(health: dict[str, Any]) -> bool:
    return bool(
        health.get("motion_enabled") is False
        and abs(float(health.get("left_motor", 0.0) or 0.0)) < 1.0e-6
        and abs(float(health.get("right_motor", 0.0) or 0.0)) < 1.0e-6
    )


def live_motion_approved(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "execute_motion", False) and getattr(args, "confirm_operator_ready", False))


def apply_target_preset(args: argparse.Namespace) -> argparse.Namespace:
    preset_name = str(getattr(args, "target_preset", "") or "").strip()
    if not preset_name:
        return args
    preset = TARGET_PRESETS[preset_name]
    for name, value in preset.items():
        setattr(args, name, value)
    return args


def operator_stop_requested(args: argparse.Namespace) -> bool:
    stop_file = str(getattr(args, "operator_stop_file", "") or "").strip()
    return bool(stop_file and Path(stop_file).exists())


def validate_args(args: argparse.Namespace) -> list[str]:
    issues: list[str] = []
    if bool(getattr(args, "execute_motion", False)):
        if not bool(getattr(args, "confirm_operator_ready", False)):
            issues.append("operator_ready_confirmation_required")
        if not str(getattr(args, "operator_stop_file", "") or "").strip():
            issues.append("live_motion_operator_stop_file_required")
        if int(getattr(args, "max_accepted_motor_events_per_cycle", 0) or 0) <= 0:
            issues.append("live_motion_motor_event_budget_required")
        if float(getattr(args, "max_accepted_motor_duration_s_per_cycle", 0.0) or 0.0) <= 0.0:
            issues.append("live_motion_motor_duration_budget_required")
    return issues


def wait_for_safe_health(
    client: bridge_client.BridgeClient,
    *,
    timeout_s: float = 2.0,
    interval_s: float = 0.10,
) -> dict[str, Any]:
    deadline = time.monotonic() + max(0.0, float(timeout_s))
    last_health: dict[str, Any] = {}
    while True:
        status, health = client.health()
        last_health = {"http_status": status, "response": health, "checked_utc": utc_now()}
        if safe_health(health) or time.monotonic() >= deadline:
            return last_health
        time.sleep(max(0.02, float(interval_s)))


def camera_ready(health: dict[str, Any], args: argparse.Namespace) -> bool:
    camera = health.get("camera") if isinstance(health.get("camera"), dict) else {}
    return bool(
        bool(camera.get("enabled", False))
        and bool(camera.get("loaded", False))
        and float(camera.get("cached_fps", 0.0) or 0.0) >= float(args.camera_min_fps)
        and int(camera.get("cached_bytes", 0) or 0) >= int(args.camera_min_frame_bytes)
        and camera.get("frame_age_s") is not None
        and float(camera.get("frame_age_s")) <= float(args.camera_max_frame_age_s)
    )


def stop_and_relock(client: bridge_client.BridgeClient, source: str, issues: list[str]) -> None:
    try:
        client.stop("%s:stop" % source)
    except Exception as exc:
        issues.append("%s_stop_failed:%r" % (source, exc))
    try:
        client.set_motion_enabled(False, "%s:relock" % source)
    except Exception as exc:
        issues.append("%s_relock_failed:%r" % (source, exc))
    try:
        health = wait_for_safe_health(client, timeout_s=2.0)
        if not safe_health(health.get("response", {})):
            issues.append("%s_final_health_not_safe" % source)
    except Exception as exc:
        issues.append("%s_final_health_failed:%r" % (source, exc))


def accepted_motor_events(loop_summary: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for step in loop_summary.get("steps", []):
        if not isinstance(step, dict):
            continue
        for attempt in step.get("attempts", []):
            if not isinstance(attempt, dict):
                continue
        step_dir = Path(str(step.get("artifact_dir", "")))
        motion_summary_path = step_dir / "live_motion" / "motion_summary.json"
        if not motion_summary_path.is_file():
            continue
        try:
            motion = json.loads(motion_summary_path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        relay = motion.get("relay_summary", {}).get("relay", {})
        for event in relay.get("events", []):
            if not isinstance(event, dict) or int(event.get("http_status", 0) or 0) != 200:
                continue
            response = event.get("response") if isinstance(event.get("response"), dict) else {}
            last_command = response.get("last_command") if isinstance(response.get("last_command"), dict) else {}
            left = float(last_command.get("left", 0.0) or 0.0)
            right = float(last_command.get("right", 0.0) or 0.0)
            if abs(left) <= 1.0e-6 and abs(right) <= 1.0e-6:
                continue
            events.append(
                {
                    "source_step": str(step.get("artifact_dir", "")),
                    "left": left,
                    "right": right,
                    "duration_s": float(last_command.get("duration_s", 0.0) or 0.0),
                    "source": str(last_command.get("source", "")),
                }
            )
    return events


def accepted_motor_duration_s(events: list[dict[str, Any]]) -> float:
    return sum(max(0.0, float(event.get("duration_s", 0.0) or 0.0)) for event in events if isinstance(event, dict))


def motor_event_budget_issues(events: list[dict[str, Any]], args: argparse.Namespace) -> list[str]:
    issues: list[str] = []
    max_events = int(getattr(args, "max_accepted_motor_events_per_cycle", 0) or 0)
    if max_events > 0 and len(events) > max_events:
        issues.append("accepted_motor_event_count_exceeded:%d>%d" % (len(events), max_events))
    max_duration_s = float(getattr(args, "max_accepted_motor_duration_s_per_cycle", 0.0) or 0.0)
    duration_s = accepted_motor_duration_s(events)
    if max_duration_s > 0.0 and duration_s > max_duration_s:
        issues.append("accepted_motor_duration_exceeded:%.3f>%.3f" % (duration_s, max_duration_s))
    return issues


def detector_evidence_summary(loop_summary: dict[str, Any]) -> dict[str, Any]:
    steps = loop_summary.get("steps") if isinstance(loop_summary.get("steps"), list) else []
    backend_counts: dict[str, int] = {}
    arbitration_counts: dict[str, int] = {}
    yolo_primary_detected_steps = 0
    for step in steps:
        if not isinstance(step, dict):
            continue
        backend = str(step.get("detector_backend", "") or "")
        if backend:
            backend_counts[backend] = backend_counts.get(backend, 0) + 1
        selected = str(step.get("detector_arbitration_selected", "") or "")
        if selected:
            arbitration_counts[selected] = arbitration_counts.get(selected, 0) + 1
        if bool(step.get("yolo_onnx_primary_detected", False)):
            yolo_primary_detected_steps += 1
    return {
        "step_count": len([step for step in steps if isinstance(step, dict)]),
        "detector_backend_counts": backend_counts,
        "detector_arbitration_selected_counts": arbitration_counts,
        "yolo_onnx_primary_detected_steps": yolo_primary_detected_steps,
    }


def reverse_reset(client: bridge_client.BridgeClient, events: list[dict[str, Any]], args: argparse.Namespace, artifact_dir: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "generated_utc": utc_now(),
        "type": "factory_bridge_inverse_reset",
        "events_to_reverse": events,
        "posted": [],
        "issues": [],
        "pass": False,
    }
    if not events:
        summary["pass"] = True
        summary["skipped"] = "no_accepted_motor_events"
        write_json(artifact_dir / "inverse_reset_summary.json", summary)
        return summary
    if not live_motion_approved(args):
        summary["issues"].append("inverse_reset_motion_not_authorized")
        try:
            client.stop("overnight_loop:reset_unauthorized_stop")
        except Exception as exc:
            summary["issues"].append("reset_unauthorized_stop_failed:%r" % (exc,))
        try:
            client.set_motion_enabled(False, "overnight_loop:reset_unauthorized_relock")
        except Exception as exc:
            summary["issues"].append("reset_unauthorized_relock_failed:%r" % (exc,))
        try:
            summary["final_health"] = wait_for_safe_health(client, timeout_s=2.0)
        except Exception as exc:
            summary["issues"].append("reset_unauthorized_final_health_failed:%r" % (exc,))
        summary["pass"] = False
        write_json(artifact_dir / "inverse_reset_summary.json", summary)
        return summary
    try:
        client.stop("overnight_loop:pre_reset_stop")
    except Exception as exc:
        summary["issues"].append("pre_reset_stop_failed:%r" % (exc,))
    try:
        client.set_motion_enabled(True, "overnight_loop:reset_enable")
        for index, event in enumerate(reversed(events), start=1):
            duration_s = min(float(args.reset_max_duration_s), max(0.0, float(event["duration_s"])))
            if duration_s <= 0.0:
                continue
            left = max(-float(args.reset_max_motor_abs), min(float(args.reset_max_motor_abs), -float(event["left"])))
            right = max(-float(args.reset_max_motor_abs), min(float(args.reset_max_motor_abs), -float(event["right"])))
            source = "overnight_loop:inverse_reset:%02d" % index
            try:
                status, response = client.motors(left, right, duration_s, source)
            except bridge_client.BridgeHttpError as exc:
                if exc.status_code != 423:
                    raise
                client.set_motion_enabled(True, "overnight_loop:reset_reenable:%02d" % index)
                status, response = client.motors(left, right, duration_s, source)
            summary["posted"].append(
                {
                    "http_status": status,
                    "left": left,
                    "right": right,
                    "duration_s": duration_s,
                    "response_motion_enabled": response.get("motion_enabled"),
                    "response_left_motor": response.get("left_motor"),
                    "response_right_motor": response.get("right_motor"),
                }
            )
            time.sleep(max(0.05, duration_s + float(args.reset_settle_s)))
    except Exception as exc:
        summary["issues"].append("inverse_reset_failed:%r" % (exc,))
    finally:
        try:
            client.stop("overnight_loop:reset_final_stop")
        except Exception as exc:
            summary["issues"].append("reset_final_stop_failed:%r" % (exc,))
        try:
            client.set_motion_enabled(False, "overnight_loop:reset_relock")
        except Exception as exc:
            summary["issues"].append("reset_relock_failed:%r" % (exc,))
        try:
            summary["final_health"] = wait_for_safe_health(
                client,
                timeout_s=max(2.0, float(args.reset_max_duration_s) + float(args.reset_settle_s) + 1.0),
            )
        except Exception as exc:
            summary["issues"].append("reset_final_health_failed:%r" % (exc,))
    final_health = summary.get("final_health", {}).get("response", {})
    summary["pass"] = bool(not summary["issues"] and safe_health(final_health))
    write_json(artifact_dir / "inverse_reset_summary.json", summary)
    return summary


def scan_detection_args(args: argparse.Namespace) -> argparse.Namespace:
    return SimpleNamespace(
        detector_backend=args.detector_backend,
        target_profile=args.target_profile,
        target_min_luma=args.target_min_luma,
        target_min_saturation=args.target_min_saturation,
        target_min_value=args.target_min_value,
        target_min_area_ratio=args.target_min_area_ratio,
        target_max_area_ratio=args.target_max_area_ratio,
        target_max_bbox_width_ratio=args.target_max_bbox_width_ratio,
        target_max_bbox_height_ratio=args.target_max_bbox_height_ratio,
        target_border_margin_ratio=args.target_border_margin_ratio,
        target_min_bbox_aspect_ratio=args.target_min_bbox_aspect_ratio,
        target_max_bbox_aspect_ratio=args.target_max_bbox_aspect_ratio,
        target_min_centroid_y_ratio=args.target_min_centroid_y_ratio,
        target_max_centroid_y_ratio=args.target_max_centroid_y_ratio,
        yolo_onnx_model=args.yolo_onnx_model,
        yolo_onnx_fallback_model=args.yolo_onnx_fallback_model,
        yolo_onnx_input_size=640,
        yolo_onnx_confidence_threshold=args.yolo_confidence_threshold,
        yolo_onnx_fallback_confidence_threshold=args.yolo_fallback_confidence_threshold,
        yolo_onnx_iou_threshold=0.45,
        yolo_target_class=["bottle"],
        yolo_target_min_area_ratio=args.yolo_target_min_area_ratio,
        yolo_color_override_area_multiplier=args.yolo_color_override_area_multiplier,
        visual_center_deadband=args.visual_center_deadband,
        visual_turn_sign=args.visual_turn_sign,
        visual_angular_gain=args.visual_angular_gain,
        max_policy_angular_z=args.max_policy_angular_z,
        stack_acquire_turn_sign=args.stack_acquire_turn_sign,
        command_duration_s=args.command_duration_s,
        stack_forward_stop_area_ratio=args.stack_forward_stop_area_ratio,
        stack_forward_x=0.025,
        max_stack_linear_x=0.04,
    )


def capture_scan_observation(
    client: bridge_client.BridgeClient,
    args: argparse.Namespace,
    artifact_dir: Path,
    label: str,
) -> dict[str, Any]:
    ensure_dir(artifact_dir)
    image_path = artifact_dir / ("%s.jpg" % label)
    annotated_path = artifact_dir / ("%s_annotated.jpg" % label)
    snapshot = stack_gate.save_snapshot(client, image_path, args)
    detector_args = scan_detection_args(args)
    analysis = stack_gate.analyze_policy_image(
        image_path,
        detector_args,
        stack_gate.build_stack_fetch_policy_args(detector_args),
        annotated_path=annotated_path,
        allow_forward=False,
    )
    return {
        "label": label,
        "http_status": snapshot.get("http_status"),
        "image_path": str(image_path),
        "snapshot": snapshot,
        "camera_fetch_mode_selected": snapshot.get("camera_fetch_mode_selected"),
        "annotated_image_path": stack_gate.selected_annotated_image_path(analysis, annotated_path),
        "detected": bool(analysis.get("detected", False)),
        "area_ratio": analysis.get("area_ratio"),
        "center_error": analysis.get("center_error"),
        "centered": bool(analysis.get("centered", False)),
        "issues": list(analysis.get("issues", [])) if isinstance(analysis.get("issues"), list) else [],
        "analysis": analysis,
    }


def scan_reacquire_target(
    client: bridge_client.BridgeClient,
    args: argparse.Namespace,
    artifact_dir: Path,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "generated_utc": utc_now(),
        "type": "factory_bridge_scan_reacquire",
        "artifact_dir": str(artifact_dir),
        "observations": [],
        "commands": [],
        "accepted_motor_events": [],
        "issues": [],
        "pass": False,
    }
    if not bool(args.scan_before_cycle):
        summary["pass"] = True
        summary["skipped"] = "scan_before_cycle_disabled"
        write_json(artifact_dir / "scan_reacquire_summary.json", summary)
        return summary
    try:
        first = capture_scan_observation(client, args, artifact_dir, "scan_00")
        summary["observations"].append(first)
        if first["detected"]:
            summary["pass"] = True
            summary["stop_reason"] = "target_visible_initially"
            write_json(artifact_dir / "scan_reacquire_summary.json", summary)
            return summary
        if not live_motion_approved(args):
            summary["stop_reason"] = "scan_reacquire_requires_live_motion_approval"
            summary["issues"].append("live_scan_motion_not_authorized")
        else:
            for index in range(1, int(args.scan_steps) + 1):
                client.set_motion_enabled(True, "overnight_loop:scan_enable:%02d" % index)
                status, response = client.motors(
                    float(args.scan_left_motor),
                    float(args.scan_right_motor),
                    float(args.scan_duration_s),
                    "overnight_loop:scan:%02d" % index,
                )
                event = {
                    "source_step": str(artifact_dir),
                    "left": float(args.scan_left_motor),
                    "right": float(args.scan_right_motor),
                    "duration_s": float(args.scan_duration_s),
                    "source": "overnight_loop:scan:%02d" % index,
                }
                summary["commands"].append(
                    {
                        "index": index,
                        "http_status": status,
                        "left": event["left"],
                        "right": event["right"],
                        "duration_s": event["duration_s"],
                        "response_motion_enabled": response.get("motion_enabled"),
                        "response_left_motor": response.get("left_motor"),
                        "response_right_motor": response.get("right_motor"),
                    }
                )
                if int(status) == 200:
                    summary["accepted_motor_events"].append(event)
                time.sleep(max(0.05, float(args.scan_duration_s) + float(args.scan_settle_s)))
                client.stop("overnight_loop:scan_stop:%02d" % index)
                client.set_motion_enabled(False, "overnight_loop:scan_relock:%02d" % index)
                scan_step_health = wait_for_safe_health(client, timeout_s=2.0)
                if not safe_health(scan_step_health.get("response", {})):
                    summary["issues"].append("scan_step_final_health_not_safe:%02d" % index)
                    break
                observation = capture_scan_observation(client, args, artifact_dir, "scan_%02d" % index)
                summary["observations"].append(observation)
                if observation["detected"]:
                    summary["pass"] = True
                    summary["stop_reason"] = "target_reacquired"
                    break
        if not summary["pass"] and not summary.get("stop_reason"):
            summary["stop_reason"] = "scan_steps_exhausted"
            summary["issues"].append("target_not_reacquired")
    except Exception as exc:  # pylint: disable=broad-except
        summary["issues"].append("scan_reacquire_failed:%r" % (exc,))
    finally:
        stop_and_relock(client, "overnight_loop:scan_final", summary["issues"])
        try:
            summary["final_health"] = wait_for_safe_health(client, timeout_s=2.0)
        except Exception as exc:
            summary["issues"].append("scan_final_health_failed:%r" % (exc,))
    summary["pass"] = bool(summary["pass"] and not summary["issues"])
    write_json(artifact_dir / "scan_reacquire_summary.json", summary)
    return summary


def build_closed_loop_args(args: argparse.Namespace, artifact_dir: Path) -> argparse.Namespace:
    argv = [
        "--base-url",
        args.base_url,
        "--timeout-s",
        str(args.timeout_s),
        "--robot-host",
        args.robot_host,
        "--robot-user",
        args.robot_user,
        "--port",
        str(args.port),
        "--artifact-dir",
        str(artifact_dir),
        "--skip-deploy",
        "--motion-control-mode",
        "http",
        "--policy-entrypoint",
        "chasecar_stack_fetch_adapter_v0",
        "--detector-backend",
        args.detector_backend,
        "--yolo-onnx-model",
        args.yolo_onnx_model,
        "--yolo-onnx-fallback-model",
        args.yolo_onnx_fallback_model,
        "--yolo-target-class",
        "bottle",
        "--yolo-onnx-confidence-threshold",
        str(args.yolo_confidence_threshold),
        "--yolo-onnx-fallback-confidence-threshold",
        str(args.yolo_fallback_confidence_threshold),
        "--camera-fetch-mode",
        args.camera_fetch_mode,
        "--camera-fetch-timeout-s",
        str(args.camera_fetch_timeout_s),
        "--snapshot-attempts",
        str(args.snapshot_attempts),
        "--snapshot-retry-interval-s",
        str(args.snapshot_retry_interval_s),
        "--yolo-target-min-area-ratio",
        str(args.yolo_target_min_area_ratio),
        "--yolo-color-override-area-multiplier",
        str(args.yolo_color_override_area_multiplier),
        "--target-min-area-ratio",
        str(args.target_min_area_ratio),
        "--target-profile",
        str(args.target_profile),
        "--target-min-luma",
        str(args.target_min_luma),
        "--target-min-saturation",
        str(args.target_min_saturation),
        "--target-min-value",
        str(args.target_min_value),
        "--target-max-area-ratio",
        str(args.target_max_area_ratio),
        "--target-max-bbox-width-ratio",
        str(args.target_max_bbox_width_ratio),
        "--target-max-bbox-height-ratio",
        str(args.target_max_bbox_height_ratio),
        "--target-border-margin-ratio",
        str(args.target_border_margin_ratio),
        "--target-min-bbox-aspect-ratio",
        str(args.target_min_bbox_aspect_ratio),
        "--target-max-bbox-aspect-ratio",
        str(args.target_max_bbox_aspect_ratio),
        "--target-min-centroid-y-ratio",
        str(args.target_min_centroid_y_ratio),
        "--target-max-centroid-y-ratio",
        str(args.target_max_centroid_y_ratio),
        "--visual-center-deadband",
        str(args.visual_center_deadband),
        "--visual-turn-sign",
        str(args.visual_turn_sign),
        "--visual-angular-gain",
        str(args.visual_angular_gain),
        "--max-policy-angular-z",
        str(args.max_policy_angular_z),
        "--stack-search-angular-z",
        str(args.stack_search_angular_z),
        "--stack-acquire-turn-sign",
        str(args.stack_acquire_turn_sign),
        "--max-progress-center-error",
        str(args.visual_center_deadband),
        "--stack-forward-stop-area-ratio",
        str(args.stack_forward_stop_area_ratio),
        "--nav-target-success-area-ratio",
        str(args.nav_target_success_area_ratio),
        "--nav-target-success-max-center-error",
        str(args.visual_center_deadband),
        "--steps",
        str(args.steps),
        "--min-completed-steps",
        str(args.min_completed_steps),
        "--step-retries",
        str(args.step_retries),
        "--max-bridge-linear-x",
        str(args.max_bridge_linear_x),
        "--max-bridge-angular-z",
        str(args.max_bridge_angular_z),
        "--max-motor-speed",
        str(args.max_motor_speed),
        "--max-runtime-linear-x",
        str(args.max_runtime_linear_x),
        "--max-runtime-angular-z",
        str(args.max_runtime_angular_z),
        "--linear-scale",
        str(args.linear_scale),
        "--angular-scale",
        str(args.angular_scale),
        "--relay-window-s",
        str(args.relay_window_s),
        "--command-duration-s",
        str(args.command_duration_s),
        "--post-rate-hz",
        str(args.post_rate_hz),
        "--stale-stop-s",
        str(args.stale_stop_s),
        "--camera-ready-timeout-s",
        str(args.camera_ready_timeout_s),
        "--camera-min-fps",
        str(args.camera_min_fps),
        "--camera-max-frame-age-s",
        str(args.camera_max_frame_age_s),
        "--camera-min-frame-bytes",
        str(args.camera_min_frame_bytes),
        "--camera-width",
        str(args.camera_width),
        "--camera-height",
        str(args.camera_height),
        "--camera-jpeg-quality",
        str(args.camera_jpeg_quality),
    ]
    if bool(args.require_nav_target_success):
        argv.append("--require-nav-target-success")
    else:
        argv.append("--no-require-nav-target-success")
    if live_motion_approved(args):
        argv.extend(["--execute-motion", "--confirm-operator-ready"])
    return closed_loop_runner.parse_args(argv)


def rollup_passed(rollup: dict[str, Any]) -> bool:
    cycles = rollup.get("cycles", [])
    if not isinstance(cycles, list):
        return False
    completed_cycles = sum(1 for cycle in cycles if isinstance(cycle, dict) and cycle.get("pass"))
    failed_cycles = [cycle for cycle in cycles if isinstance(cycle, dict) and not cycle.get("pass")]
    final_health = rollup.get("final_health", {})
    final_response = final_health.get("response", {}) if isinstance(final_health, dict) else {}
    return bool(
        completed_cycles > 0
        and not failed_cycles
        and not rollup.get("issues")
        and rollup.get("stop_reason") in SUCCESS_STOP_REASONS
        and safe_health(final_response)
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    artifact_root = ensure_dir(args.artifact_dir or default_artifact_dir())
    client = bridge_client.BridgeClient(args.base_url, args.timeout_s)
    rollup: dict[str, Any] = {
        "generated_utc": utc_now(),
        "type": "factory_bridge_overnight_endurance_loop",
        "artifact_dir": str(artifact_root),
        "base_url": args.base_url,
        "cycles": [],
        "issues": [],
        "pass": False,
    }
    write_json(artifact_root / "overnight_loop_summary.json", rollup)
    validation_issues = validate_args(args)
    if validation_issues:
        rollup["issues"].extend(validation_issues)
        rollup["stop_reason"] = "argument_validation_failed"
        try:
            rollup["final_health"] = wait_for_safe_health(client, timeout_s=2.0)
        except Exception as exc:
            rollup["issues"].append("final_health_failed:%r" % (exc,))
        rollup["completed_utc"] = utc_now()
        rollup["completed_cycles"] = 0
        rollup["pass"] = False
        write_json(artifact_root / "overnight_loop_summary.json", rollup)
        return rollup
    started = time.monotonic()
    cycle_index = 0
    try:
        while True:
            if operator_stop_requested(args):
                rollup["stop_reason"] = "operator_stop_requested"
                stop_and_relock(client, "overnight_loop:operator_stop", rollup["issues"])
                break
            if args.max_cycles > 0 and cycle_index >= args.max_cycles:
                rollup["stop_reason"] = "max_cycles_reached"
                break
            if args.max_runtime_s > 0 and time.monotonic() - started >= args.max_runtime_s:
                rollup["stop_reason"] = "max_runtime_reached"
                break
            cycle_index += 1
            cycle_dir = ensure_dir(artifact_root / ("cycle_%04d" % cycle_index))
            cycle_record: dict[str, Any] = {"index": cycle_index, "started_utc": utc_now(), "artifact_dir": str(cycle_dir)}
            try:
                status, health = client.health()
                cycle_record["start_health"] = {"http_status": status, "response": health}
                if not safe_health(health):
                    cycle_record["stop_reason"] = "unsafe_start_bridge_state"
                    stop_and_relock(client, "overnight_loop:unsafe_start", rollup["issues"])
                    rollup["cycles"].append(cycle_record)
                    rollup["stop_reason"] = "unsafe_start_bridge_state"
                    break
                if not camera_ready(health, args):
                    cycle_record["stop_reason"] = "camera_not_ready"
                    stop_and_relock(client, "overnight_loop:camera_not_ready", rollup["issues"])
                    rollup["cycles"].append(cycle_record)
                    rollup["stop_reason"] = "camera_not_ready"
                    break
                scan_summary = scan_reacquire_target(client, args, cycle_dir / "scan_reacquire")
                cycle_record["scan_reacquire_summary_path"] = str(cycle_dir / "scan_reacquire" / "scan_reacquire_summary.json")
                cycle_record["scan_reacquire_pass"] = bool(scan_summary.get("pass", False))
                cycle_record["scan_reacquire_stop_reason"] = str(scan_summary.get("stop_reason", ""))
                scan_events = (
                    list(scan_summary.get("accepted_motor_events", []))
                    if isinstance(scan_summary.get("accepted_motor_events"), list)
                    else []
                )
                if not cycle_record["scan_reacquire_pass"]:
                    reset_summary = reverse_reset(client, scan_events, args, cycle_dir / "scan_inverse_reset")
                    cycle_record["scan_inverse_reset_summary_path"] = str(
                        cycle_dir / "scan_inverse_reset" / "inverse_reset_summary.json"
                    )
                    cycle_record["scan_inverse_reset_pass"] = bool(reset_summary.get("pass", False))
                    cycle_record["stop_reason"] = "scan_reacquire_not_passed"
                    rollup["cycles"].append(cycle_record)
                    rollup["stop_reason"] = (
                        "scan_inverse_reset_not_passed"
                        if not cycle_record["scan_inverse_reset_pass"]
                        else "scan_reacquire_not_passed"
                    )
                    break
                loop_args = build_closed_loop_args(args, cycle_dir / "closed_loop")
                loop_summary = closed_loop_runner.run(loop_args)
                cycle_record["closed_loop_summary_path"] = str(cycle_dir / "closed_loop" / "closed_loop_summary.json")
                cycle_record["closed_loop_pass"] = bool(loop_summary.get("pass", False))
                cycle_record["terminal_reason"] = loop_summary.get("terminal_reason", "")
                cycle_record["nav_target_success"] = bool(loop_summary.get("nav_target_success", {}).get("pass", False))
                cycle_record["detector_evidence"] = detector_evidence_summary(loop_summary)
                events = scan_events + accepted_motor_events(loop_summary)
                cycle_record["accepted_motor_event_count"] = len(events)
                cycle_record["accepted_motor_duration_s"] = round(accepted_motor_duration_s(events), 6)
                reset_summary = reverse_reset(client, events, args, cycle_dir / "inverse_reset")
                cycle_record["inverse_reset_summary_path"] = str(cycle_dir / "inverse_reset" / "inverse_reset_summary.json")
                cycle_record["inverse_reset_pass"] = bool(reset_summary.get("pass", False))
                budget_issues = motor_event_budget_issues(events, args)
                if budget_issues:
                    cycle_record["motor_event_budget_issues"] = budget_issues
                if not cycle_record["closed_loop_pass"]:
                    cycle_record["stop_reason"] = "closed_loop_not_passed"
                    rollup["cycles"].append(cycle_record)
                    rollup["stop_reason"] = "closed_loop_not_passed"
                    break
                if not cycle_record["inverse_reset_pass"]:
                    cycle_record["stop_reason"] = "inverse_reset_not_passed"
                    rollup["cycles"].append(cycle_record)
                    rollup["stop_reason"] = "inverse_reset_not_passed"
                    break
                if budget_issues:
                    cycle_record["stop_reason"] = "accepted_motor_budget_exceeded"
                    rollup["cycles"].append(cycle_record)
                    rollup["stop_reason"] = "accepted_motor_budget_exceeded"
                    break
                status, health = client.health()
                cycle_record["end_health"] = {"http_status": status, "response": health}
                if not safe_health(health):
                    cycle_record["stop_reason"] = "unsafe_end_bridge_state"
                    rollup["cycles"].append(cycle_record)
                    rollup["stop_reason"] = "unsafe_end_bridge_state"
                    break
                cycle_record["completed_utc"] = utc_now()
                cycle_record["pass"] = True
                rollup["cycles"].append(cycle_record)
                write_json(artifact_root / "overnight_loop_summary.json", rollup)
                time.sleep(max(0.0, float(args.cycle_sleep_s)))
            except Exception as exc:  # pylint: disable=broad-except
                cycle_record["exception"] = repr(exc)
                cycle_record["pass"] = False
                rollup["cycles"].append(cycle_record)
                rollup["issues"].append("cycle_exception:%r" % (exc,))
                rollup["stop_reason"] = "cycle_exception"
                try:
                    stop_and_relock(client, "overnight_loop:exception", rollup["issues"])
                except Exception:
                    pass
                break
    except KeyboardInterrupt:
        rollup["stop_reason"] = "operator_interrupt"
        rollup["operator_stop"] = {"source": "keyboard_interrupt", "at_utc": utc_now()}
        stop_and_relock(client, "overnight_loop:operator_interrupt", rollup["issues"])
    rollup["completed_utc"] = utc_now()
    try:
        rollup["final_health"] = wait_for_safe_health(client, timeout_s=2.0)
        if not safe_health(rollup["final_health"].get("response", {})):
            rollup["issues"].append("final_health_not_safe")
    except Exception as exc:
        rollup["issues"].append("final_health_failed:%r" % (exc,))
    rollup["completed_cycles"] = sum(1 for cycle in rollup["cycles"] if cycle.get("pass"))
    rollup["pass"] = rollup_passed(rollup)
    write_json(artifact_root / "overnight_loop_summary.json", rollup)
    return rollup


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run repeated JetBot Mini closed-loop stack proofs with inverse reset.")
    parser.add_argument("--base-url", default=bridge_client.DEFAULT_BASE_URL)
    parser.add_argument("--timeout-s", type=float, default=10.0)
    parser.add_argument("--robot-host", default="192.168.1.11")
    parser.add_argument("--robot-user", default="jetson")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--artifact-dir", default="")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--execute-motion", action="store_true")
    parser.add_argument("--confirm-operator-ready", action="store_true")
    parser.add_argument("--operator-stop-file", default="")
    parser.add_argument("--max-cycles", type=int, default=0)
    parser.add_argument("--max-runtime-s", type=float, default=0.0)
    parser.add_argument("--cycle-sleep-s", type=float, default=10.0)
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument("--min-completed-steps", type=int, default=1)
    parser.add_argument("--step-retries", type=int, default=1)
    parser.add_argument("--yolo-onnx-model", default="runtime/yolo/yolov5s.onnx")
    parser.add_argument("--yolo-onnx-fallback-model", default="runtime/yolo/yolov5m.onnx")
    parser.add_argument("--detector-backend", choices=["yolo_onnx", "yolo_onnx_or_color", "color"], default="yolo_onnx_or_color")
    parser.add_argument("--target-preset", choices=[""] + sorted(TARGET_PRESETS), default="")
    parser.add_argument("--yolo-confidence-threshold", type=float, default=0.10)
    parser.add_argument("--yolo-fallback-confidence-threshold", type=float, default=0.03)
    parser.add_argument("--yolo-target-min-area-ratio", type=float, default=0.02)
    parser.add_argument("--yolo-color-override-area-multiplier", type=float, default=1.35)
    parser.add_argument("--target-profile", choices=behavior_runner.DEFAULT_VISUAL_SCAN_PROFILES, default="blue")
    parser.add_argument("--target-min-luma", type=float, default=180.0)
    parser.add_argument("--target-min-saturation", type=float, default=0.25)
    parser.add_argument("--target-min-value", type=float, default=0.20)
    parser.add_argument("--target-min-area-ratio", type=float, default=0.025)
    parser.add_argument("--target-max-area-ratio", type=float, default=0.55)
    parser.add_argument("--target-max-bbox-width-ratio", type=float, default=1.0)
    parser.add_argument("--target-max-bbox-height-ratio", type=float, default=1.0)
    parser.add_argument("--target-border-margin-ratio", type=float, default=0.03)
    parser.add_argument("--target-min-bbox-aspect-ratio", type=float, default=0.0)
    parser.add_argument("--target-max-bbox-aspect-ratio", type=float, default=0.9)
    parser.add_argument("--target-min-centroid-y-ratio", type=float, default=0.45)
    parser.add_argument("--target-max-centroid-y-ratio", type=float, default=1.0)
    parser.add_argument("--visual-center-deadband", type=float, default=0.24)
    parser.add_argument("--visual-turn-sign", type=float, default=1.0)
    parser.add_argument("--visual-angular-gain", type=float, default=0.8)
    parser.add_argument("--max-policy-angular-z", type=float, default=0.18)
    parser.add_argument("--stack-search-angular-z", type=float, default=0.18)
    parser.add_argument("--stack-acquire-turn-sign", type=float, default=1.0)
    parser.add_argument("--stack-forward-stop-area-ratio", type=float, default=0.09)
    parser.add_argument("--nav-target-success-area-ratio", type=float, default=0.09)
    parser.add_argument("--require-nav-target-success", dest="require_nav_target_success", action="store_true", default=True)
    parser.add_argument("--no-require-nav-target-success", dest="require_nav_target_success", action="store_false")
    parser.add_argument("--max-bridge-linear-x", type=float, default=0.04)
    parser.add_argument("--max-bridge-angular-z", type=float, default=0.8)
    parser.add_argument("--max-motor-speed", type=float, default=0.35)
    parser.add_argument("--max-runtime-linear-x", type=float, default=0.10)
    parser.add_argument("--max-runtime-angular-z", type=float, default=0.40)
    parser.add_argument("--linear-scale", type=float, default=3.0)
    parser.add_argument("--angular-scale", type=float, default=4.0)
    parser.add_argument("--relay-window-s", type=float, default=2.5)
    parser.add_argument("--command-duration-s", type=float, default=0.35)
    parser.add_argument("--post-rate-hz", type=float, default=8.0)
    parser.add_argument("--stale-stop-s", type=float, default=0.35)
    parser.add_argument("--camera-ready-timeout-s", type=float, default=8.0)
    parser.add_argument("--camera-min-fps", type=float, default=2.0)
    parser.add_argument("--camera-max-frame-age-s", type=float, default=1.0)
    parser.add_argument("--camera-min-frame-bytes", type=int, default=100)
    parser.add_argument("--camera-width", type=int, default=320)
    parser.add_argument("--camera-height", type=int, default=240)
    parser.add_argument("--camera-jpeg-quality", type=int, default=40)
    parser.add_argument("--snapshot-attempts", type=int, default=10)
    parser.add_argument("--snapshot-retry-interval-s", type=float, default=0.15)
    parser.add_argument("--camera-fetch-mode", choices=stack_gate.CAMERA_FETCH_MODES, default="http")
    parser.add_argument("--camera-fetch-timeout-s", type=float, default=12.0)
    parser.add_argument("--reset-max-motor-abs", type=float, default=0.25)
    parser.add_argument("--reset-max-duration-s", type=float, default=0.25)
    parser.add_argument("--reset-settle-s", type=float, default=0.10)
    parser.add_argument("--max-accepted-motor-events-per-cycle", type=int, default=0)
    parser.add_argument("--max-accepted-motor-duration-s-per-cycle", type=float, default=0.0)
    parser.add_argument("--scan-before-cycle", dest="scan_before_cycle", action="store_true", default=True)
    parser.add_argument("--no-scan-before-cycle", dest="scan_before_cycle", action="store_false")
    parser.add_argument("--scan-steps", type=int, default=24)
    parser.add_argument("--scan-left-motor", type=float, default=-0.20)
    parser.add_argument("--scan-right-motor", type=float, default=0.20)
    parser.add_argument("--scan-duration-s", type=float, default=0.18)
    parser.add_argument("--scan-settle-s", type=float, default=0.10)
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return apply_target_preset(build_parser().parse_args(argv))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run(args)
    print(json.dumps(summary, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if summary.get("pass", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
