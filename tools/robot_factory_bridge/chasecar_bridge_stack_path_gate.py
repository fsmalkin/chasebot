#!/usr/bin/env python3
"""Prove the offboard Chasecar command path reaches the locked factory bridge."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from typing import Any

import chasecar_bridge_behavior_runner as behavior_runner
import chasecar_bridge_client as bridge_client
import chasecar_bridge_object_pose_observation as object_pose
import chasecar_bridge_yolo_onnx_probe as yolo_probe


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import brain_supervisor_policy as supervisor_policy  # noqa: E402

DEFAULT_RUNTIME_SOURCE_PATH = "$HOME/ros2_ws/src/chasecar_runtime"
DEFAULT_ARTIFACT_STEM = "factory_bridge_stack_path_gate"
POLICY_FIXED_COMMAND_V0 = "fixed_command_v0"
POLICY_JETBOT_VISUAL_TARGET_TURN_V0 = "jetbot_visual_target_turn_v0"
POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0 = "chasecar_stack_fetch_adapter_v0"
SAFE_TERMINAL_ZERO_STOP_REASONS = {
    "target_inside_stack_forward_stop_area",
    "target_inside_stack_forward_stop_bbox_height",
    "target_inside_stack_forward_stop_distance",
}
MOTION_CONTROL_MODES = ("auto", "http", "deploy")
CAMERA_FETCH_MODES = ("http", "ssh", "auto")
POLICY_ENTRYPOINTS = (
    POLICY_FIXED_COMMAND_V0,
    POLICY_JETBOT_VISUAL_TARGET_TURN_V0,
    POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0,
)
DEFAULT_POLICY_ENTRYPOINT = POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0


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


def repo_display_path(path: Path | str) -> str:
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(resolved)


def sh_quote(value: str) -> str:
    return "'" + str(value).replace("'", "'\"'\"'") + "'"


def camera_fetch_timeout_s(args: argparse.Namespace) -> float:
    return max(1.0, float(getattr(args, "camera_fetch_timeout_s", getattr(args, "timeout_s", 10.0)) or 10.0))


def ssh_connect_timeout_arg(args: argparse.Namespace) -> str:
    return "ConnectTimeout=%d" % max(1, min(10, int(camera_fetch_timeout_s(args))))


def ssh_camera_target(args: argparse.Namespace) -> str:
    return "%s@%s" % (str(getattr(args, "robot_user", "jetson")), str(getattr(args, "robot_host", "192.168.1.11")))


def command_nonzero(command: dict[str, float]) -> bool:
    return abs(float(command.get("linear_x", 0.0) or 0.0)) > 1.0e-6 or abs(
        float(command.get("angular_z", 0.0) or 0.0)
    ) > 1.0e-6


def safe_terminal_zero_stop(stop_reason: str, command: dict[str, Any]) -> bool:
    return str(stop_reason or "") in SAFE_TERMINAL_ZERO_STOP_REASONS and not command_nonzero(command)


def safe_terminal_policy_decision(policy_decision: dict[str, Any]) -> bool:
    command = policy_decision.get("command") if isinstance(policy_decision.get("command"), dict) else {}
    return safe_terminal_zero_stop(str(policy_decision.get("stop_reason", "") or ""), command)


def command_from_args(args: argparse.Namespace) -> dict[str, float]:
    return {"linear_x": float(args.command_linear_x), "angular_z": float(args.command_angular_z)}


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def bound_policy_command(command: dict[str, Any], args: argparse.Namespace) -> dict[str, float]:
    return {
        "linear_x": clamp(
            float(command.get("linear_x", 0.0) or 0.0),
            -float(args.max_runtime_linear_x),
            float(args.max_runtime_linear_x),
        ),
        "angular_z": clamp(
            float(command.get("angular_z", 0.0) or 0.0),
            -float(args.max_runtime_angular_z),
            float(args.max_runtime_angular_z),
        ),
    }


def command_bounds(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "max_runtime_linear_x": float(args.max_runtime_linear_x),
        "max_runtime_angular_z": float(args.max_runtime_angular_z),
        "max_bridge_linear_x": float(args.max_bridge_linear_x),
        "max_bridge_angular_z": float(args.max_bridge_angular_z),
        "linear_scale": float(args.linear_scale),
        "angular_scale": float(args.angular_scale),
        "command_duration_s": float(args.command_duration_s),
        "post_rate_hz": float(args.post_rate_hz),
    }


def runtime_payload(
    sequence: int,
    command: dict[str, float],
    *,
    enabled: bool,
    policy_decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not enabled:
        command = {"linear_x": 0.0, "angular_z": 0.0}
    payload = {
        "manual_drive": {
            "enabled": bool(enabled),
            "sequence": int(sequence),
            "mode": "stack_path_locked_gate",
            "updated_utc": utc_now(),
            "command": command,
            "rationale": "Locked stack-through-bridge transport proof.",
            "source": "chasecar_bridge_stack_path_gate",
        }
    }
    if policy_decision:
        payload["policy"] = {
            "entrypoint": policy_decision.get("entrypoint", ""),
            "decision_id": policy_decision.get("decision_id", ""),
            "stop_reason": policy_decision.get("stop_reason", ""),
            "command_bounds": policy_decision.get("command_bounds", {}),
        }
    return payload


def build_visual_policy_args(args: argparse.Namespace) -> argparse.Namespace:
    argv = [
        "--mode",
        "visual-advisor",
        "--target-profile",
        args.target_profile,
        "--target-min-luma",
        str(args.target_min_luma),
        "--target-min-saturation",
        str(args.target_min_saturation),
        "--target-min-value",
        str(args.target_min_value),
        "--target-min-area-ratio",
        str(args.target_min_area_ratio),
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
        str(getattr(args, "target_min_centroid_y_ratio", 0.0)),
        "--target-max-centroid-y-ratio",
        str(getattr(args, "target_max_centroid_y_ratio", 1.0)),
        "--visual-center-deadband",
        str(args.visual_center_deadband),
        "--visual-turn-sign",
        str(args.visual_turn_sign),
        "--visual-angular-gain",
        str(args.visual_angular_gain),
        "--max-visual-angular-z",
        str(args.max_policy_angular_z),
        "--visual-command-duration-s",
        str(args.command_duration_s),
        "--visual-forward-x",
        "0",
        "--max-visual-linear-x",
        "0",
    ]
    return behavior_runner.build_parser().parse_args(argv)


def build_stack_fetch_policy_args(args: argparse.Namespace) -> argparse.Namespace:
    argv = [
        "--mode",
        "visual-advisor",
        "--target-profile",
        args.target_profile,
        "--target-min-luma",
        str(args.target_min_luma),
        "--target-min-saturation",
        str(args.target_min_saturation),
        "--target-min-value",
        str(args.target_min_value),
        "--target-min-area-ratio",
        str(args.target_min_area_ratio),
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
        str(getattr(args, "target_min_centroid_y_ratio", 0.0)),
        "--target-max-centroid-y-ratio",
        str(getattr(args, "target_max_centroid_y_ratio", 1.0)),
        "--visual-center-deadband",
        str(args.visual_center_deadband),
        "--visual-turn-sign",
        str(args.visual_turn_sign),
        "--visual-angular-gain",
        str(args.visual_angular_gain),
        "--max-visual-angular-z",
        str(args.max_policy_angular_z),
        "--visual-command-duration-s",
        str(args.command_duration_s),
        "--allow-forward",
        "--visual-forward-x",
        str(args.stack_forward_x),
        "--max-visual-linear-x",
        str(args.max_stack_linear_x),
        "--forward-stop-area-ratio",
        str(args.stack_forward_stop_area_ratio),
    ]
    return behavior_runner.build_parser().parse_args(argv)


def analyze_yolo_onnx_policy_image(
    image_path: Path,
    args: argparse.Namespace,
    *,
    annotated_path: Path,
    allow_forward: bool,
) -> dict[str, Any]:
    import_error = yolo_probe.load_detector_dependencies(require_onnx=True)
    if import_error or yolo_probe.ort is None:
        return {
            "detected": False,
            "issues": ["yolo_onnx_import_failed:%s" % import_error],
            "image_path": str(image_path),
            "annotated_image_path": "",
            "detector_backend": "yolo_onnx",
            "target_profile": "yolo_onnx",
        }

    model_path = Path(args.yolo_onnx_model)
    if not model_path.is_file():
        return {
            "detected": False,
            "issues": ["yolo_onnx_model_missing:%s" % model_path],
            "image_path": str(image_path),
            "annotated_image_path": "",
            "detector_backend": "yolo_onnx",
            "target_profile": "yolo_onnx",
        }

    image = yolo_probe.Image.open(image_path).convert("RGB")
    attempts = [
        run_yolo_onnx_model(
            image,
            args,
            model_path=model_path,
            confidence_threshold=float(args.yolo_onnx_confidence_threshold),
            role="primary",
        )
    ]
    fallback_model = str(getattr(args, "yolo_onnx_fallback_model", "") or "").strip()
    if attempts[0].get("best_detection") is None and fallback_model:
        fallback_path = Path(fallback_model)
        if fallback_path != model_path:
            attempts.append(
                run_yolo_onnx_model(
                    image,
                    args,
                    model_path=fallback_path,
                    confidence_threshold=float(getattr(args, "yolo_onnx_fallback_confidence_threshold", 0.03)),
                    role="fallback",
                )
            )
    selected_attempt = next((attempt for attempt in attempts if attempt.get("best_detection") is not None), attempts[-1])
    detections = list(selected_attempt.get("detections", []))
    yolo_probe.annotate(image, detections, annotated_path)

    best = selected_attempt.get("best_detection")
    attempts_summary = [
        {
            "role": attempt.get("role"),
            "model": attempt.get("model"),
            "confidence_threshold": attempt.get("confidence_threshold"),
            "detection_count": int(attempt.get("detection_count", len(attempt.get("detections", []))) or 0),
            "candidate_count": int(attempt.get("candidate_count", len(attempt.get("candidates", []))) or 0),
            "best_detection": attempt.get("best_detection"),
            "issues": list(attempt.get("issues", [])),
        }
        for attempt in attempts
    ]

    width, height = image.size
    issues: list[str] = []
    missing_model_issues = [issue for attempt in attempts for issue in attempt.get("issues", []) if str(issue).startswith("yolo_onnx_model_missing:")]
    if missing_model_issues and all(attempt.get("best_detection") is None for attempt in attempts):
        issues.extend(missing_model_issues)
    if best is None:
        any_detections = any(attempt.get("detections") for attempt in attempts)
        issues.append("target_not_detected" if not any_detections else "target_shape_or_area_below_threshold")
        return {
            "detected": False,
            "issues": issues,
            "image_path": str(image_path),
            "annotated_image_path": str(annotated_path),
            "detector_backend": "yolo_onnx",
            "target_profile": "yolo_onnx:%s" % ",".join(args.yolo_target_class or ["bottle"]),
            "image_width": width,
            "image_height": height,
            "matched_pixels": 0,
            "total_matched_pixels": 0,
            "area_ratio": 0.0,
            "bbox": None,
            "component_count": len(detections),
            "component_candidates": detections[:8],
            "center_error": None,
            "centered": False,
            "recommendation": {
                "linear_x": 0.0,
                "angular_z": 0.0,
                "duration_s": float(args.command_duration_s),
                "source": "factory_behavior_runner:yolo_onnx_advisor",
            },
            "detections": detections,
            "yolo_onnx_attempts": attempts_summary,
        }

    x0, y0, x1, y1 = [float(value) for value in best["bbox_xyxy"]]
    bbox_width = max(0.0, x1 - x0)
    bbox_height = max(0.0, y1 - y0)
    area_ratio = float(best.get("area_ratio", 0.0) or 0.0)
    center_error = float(best.get("center_error", 0.0) or 0.0)
    centered = abs(center_error) <= float(args.visual_center_deadband)
    angular_z = clamp(
        -float(args.visual_turn_sign) * center_error * float(args.visual_angular_gain),
        -float(args.max_policy_angular_z),
        float(args.max_policy_angular_z),
    )
    linear_x = 0.0
    if allow_forward and centered and area_ratio < float(args.stack_forward_stop_area_ratio):
        linear_x = clamp(float(args.stack_forward_x), 0.0, float(args.max_stack_linear_x))
    bbox = {"x0": int(round(x0)), "y0": int(round(y0)), "x1": int(round(x1)), "y1": int(round(y1))}
    matched_pixels = int(round(bbox_width * bbox_height))
    return {
        "detected": True,
        "issues": [],
        "image_path": str(image_path),
        "annotated_image_path": str(annotated_path),
        "detector_backend": "yolo_onnx",
        "target_profile": "yolo_onnx:%s" % ",".join(args.yolo_target_class or ["bottle"]),
        "image_width": width,
        "image_height": height,
        "matched_pixels": matched_pixels,
        "total_matched_pixels": matched_pixels,
        "area_ratio": area_ratio,
        "bbox_width_ratio": bbox_width / float(width),
        "bbox_height_ratio": bbox_height / float(height),
        "bbox_aspect_ratio": bbox_width / max(bbox_height, 1.0),
        "centroid": {"x": float(best["center_x_px"]), "y": float(best["center_y_px"])},
        "bbox": bbox,
        "component_count": len(detections),
        "component_candidates": detections[:8],
        "center_error": center_error,
        "centered": bool(centered),
        "confidence": float(best["confidence"]),
        "detections": detections,
        "yolo_onnx_model": selected_attempt.get("model"),
        "yolo_onnx_model_role": selected_attempt.get("role"),
        "yolo_onnx_confidence_threshold_used": selected_attempt.get("confidence_threshold"),
        "yolo_onnx_attempts": attempts_summary,
        "recommendation": {
            "linear_x": linear_x,
            "angular_z": angular_z,
            "duration_s": float(args.command_duration_s),
            "source": "factory_behavior_runner:yolo_onnx_advisor",
        },
    }


def detector_annotated_path(annotated_path: Path, detector_name: str) -> Path:
    return annotated_path.with_name("%s_%s%s" % (annotated_path.stem, detector_name, annotated_path.suffix))


def yolo_candidate_detections(detections: list[dict[str, Any]], args: argparse.Namespace, width: int, height: int) -> list[dict[str, Any]]:
    candidates = []
    for detection in detections:
        x0, y0, x1, y1 = [float(value) for value in detection["bbox_xyxy"]]
        bbox_width = max(0.0, x1 - x0)
        bbox_height = max(0.0, y1 - y0)
        aspect_ratio = bbox_width / max(bbox_height, 1.0)
        area_ratio = float(detection.get("area_ratio", 0.0) or 0.0)
        center_y_ratio = ((y0 + y1) / 2.0) / max(float(height), 1.0)
        if area_ratio < float(args.yolo_target_min_area_ratio):
            continue
        if aspect_ratio < float(args.target_min_bbox_aspect_ratio):
            continue
        if float(args.target_max_bbox_aspect_ratio) > 0.0 and aspect_ratio > float(args.target_max_bbox_aspect_ratio):
            continue
        if center_y_ratio < float(getattr(args, "target_min_centroid_y_ratio", 0.0)):
            continue
        if center_y_ratio > float(getattr(args, "target_max_centroid_y_ratio", 1.0)):
            continue
        candidates.append(detection)
    return candidates


def run_yolo_onnx_model(
    image,
    args: argparse.Namespace,
    *,
    model_path: Path,
    confidence_threshold: float,
    role: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "role": role,
        "model": str(model_path),
        "confidence_threshold": float(confidence_threshold),
        "detections": [],
        "candidates": [],
        "issues": [],
    }
    if not model_path.is_file():
        result["issues"].append("yolo_onnx_model_missing:%s" % model_path)
        return result
    session = yolo_probe.ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    model_input = session.get_inputs()[0]
    input_dtype = yolo_probe.np.float16 if "float16" in str(model_input.type).lower() else yolo_probe.np.float32
    input_tensor, scale, pad = yolo_probe.letterbox(image, int(args.yolo_onnx_input_size), dtype=input_dtype)
    outputs = session.run(None, {model_input.name: input_tensor})
    detections = yolo_probe.decode_yolov5_output(
        outputs[0],
        width=image.size[0],
        height=image.size[1],
        scale=scale,
        pad=pad,
        confidence_threshold=float(confidence_threshold),
        class_names=set(args.yolo_target_class or ["bottle"]),
        iou_threshold=float(args.yolo_onnx_iou_threshold),
    )
    candidates = yolo_candidate_detections(detections, args, image.size[0], image.size[1])
    best = yolo_probe.select_best_detection(candidates, min_area_ratio=0.0)
    result.update(
        {
            "detections": detections,
            "candidates": candidates,
            "candidate_count": len(candidates),
            "detection_count": len(detections),
            "best_detection": best,
            "model_input": {"name": model_input.name, "type": str(model_input.type), "shape": list(model_input.shape)},
        }
    )
    return result


def color_analysis_should_override_yolo(yolo_analysis: dict[str, Any], color_analysis: dict[str, Any], args: argparse.Namespace) -> bool:
    if not bool(color_analysis.get("detected", False)):
        return False
    if not bool(yolo_analysis.get("detected", False)):
        return True
    yolo_area = float(yolo_analysis.get("area_ratio", 0.0) or 0.0)
    color_area = float(color_analysis.get("area_ratio", 0.0) or 0.0)
    override_area = max(
        float(args.target_min_area_ratio),
        yolo_area * float(args.yolo_color_override_area_multiplier),
    )
    return color_area >= override_area


def analyze_policy_image(
    image_path: Path,
    args: argparse.Namespace,
    behavior_args: argparse.Namespace,
    *,
    annotated_path: Path,
    allow_forward: bool,
) -> dict[str, Any]:
    if args.detector_backend == "yolo_onnx":
        return analyze_yolo_onnx_policy_image(
            image_path,
            args,
            annotated_path=annotated_path,
            allow_forward=allow_forward,
        )
    if args.detector_backend == "yolo_onnx_or_color":
        yolo_analysis = analyze_yolo_onnx_policy_image(
            image_path,
            args,
            annotated_path=detector_annotated_path(annotated_path, "yolo"),
            allow_forward=allow_forward,
        )
        color_analysis = behavior_runner.analyze_target_image(
            image_path,
            behavior_args,
            annotated_path=detector_annotated_path(annotated_path, "color"),
        )
        if color_analysis_should_override_yolo(yolo_analysis, color_analysis, args):
            color_analysis["detector_backend"] = "yolo_onnx_or_color:color"
            color_analysis["yolo_onnx_primary_detected"] = bool(yolo_analysis.get("detected", False))
            color_analysis["yolo_onnx_primary_issues"] = list(yolo_analysis.get("issues", []))
            color_analysis["yolo_onnx_primary_area_ratio"] = yolo_analysis.get("area_ratio")
            color_analysis["yolo_onnx_primary_center_error"] = yolo_analysis.get("center_error")
            color_analysis["yolo_onnx_primary_detections"] = list(yolo_analysis.get("detections", []))
            color_analysis["detector_arbitration"] = {
                "selected": "color",
                "reason": "color_target_larger_than_yolo_candidate"
                if bool(yolo_analysis.get("detected", False))
                else "yolo_target_not_detected",
                "yolo_area_ratio": yolo_analysis.get("area_ratio"),
                "color_area_ratio": color_analysis.get("area_ratio"),
                "yolo_color_override_area_multiplier": float(args.yolo_color_override_area_multiplier),
            }
            return color_analysis
        if bool(yolo_analysis.get("detected", False)):
            yolo_analysis["detector_backend"] = "yolo_onnx_or_color:yolo_onnx"
            yolo_analysis["color_fallback_detected"] = bool(color_analysis.get("detected", False))
            yolo_analysis["color_fallback_area_ratio"] = color_analysis.get("area_ratio")
            yolo_analysis["color_fallback_center_error"] = color_analysis.get("center_error")
            yolo_analysis["detector_arbitration"] = {
                "selected": "yolo_onnx",
                "reason": "yolo_candidate_not_smaller_than_color_target",
                "yolo_area_ratio": yolo_analysis.get("area_ratio"),
                "color_area_ratio": color_analysis.get("area_ratio"),
                "yolo_color_override_area_multiplier": float(args.yolo_color_override_area_multiplier),
            }
            return yolo_analysis
        color_analysis["detector_backend"] = "yolo_onnx_or_color:color"
        color_analysis["yolo_onnx_primary_detected"] = False
        color_analysis["yolo_onnx_primary_issues"] = list(yolo_analysis.get("issues", []))
        color_analysis["yolo_onnx_primary_detections"] = list(yolo_analysis.get("detections", []))
        return color_analysis
    return behavior_runner.analyze_target_image(image_path, behavior_args, annotated_path=annotated_path)


def selected_annotated_image_path(analysis: dict[str, Any], fallback_path: Path) -> str:
    annotated_path = str(analysis.get("annotated_image_path", "") or "")
    return annotated_path or str(fallback_path)


def chasecar_stack_lineage(args: argparse.Namespace) -> dict[str, Any]:
    detector_weights = REPO_ROOT / "yolov8m.pt"
    checkpoint = str(args.stack_policy_checkpoint or "").strip()
    return {
        "adapter": POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0,
        "upstream_policy": "scripts/brain_supervisor_policy.py:build_policy_snapshot",
        "stack_family": "planner_routed_fetch_to_pose",
        "control_contract": "runtime_json_to_ros_cmd_vel_to_factory_bridge",
        "runtime_target_reference": "robot_fidelity_orin",
        "inference_backend_reference": "tensorrt_int8",
        "detector_weights": repo_display_path(detector_weights) if detector_weights.is_file() else "",
        "detector_weights_present": detector_weights.is_file(),
        "stack_policy_checkpoint": checkpoint,
        "stack_policy_checkpoint_present": bool(checkpoint and Path(checkpoint).is_file()),
        "learned_low_level_fetch_policy_loaded": bool(checkpoint and Path(checkpoint).is_file()),
        "claim_boundary": (
            "Bridge adapter uses the current deterministic/planner Chasecar policy contract. "
            "No learned low-level fetch controller checkpoint is loaded unless stack_policy_checkpoint_present=true."
        ),
    }


_OBJECT_POSE_CALIB_CACHE: dict[tuple, dict[str, Any]] = {}


def _load_object_pose_calibration(path: str, size_key: str = "equiv_diameter_px") -> dict[str, Any]:
    key = (path, size_key)
    if key not in _OBJECT_POSE_CALIB_CACHE:
        _OBJECT_POSE_CALIB_CACHE[key] = object_pose.load_calibration(path, size_key=size_key)
    return _OBJECT_POSE_CALIB_CACHE[key]


def attach_object_pose(analysis: dict[str, Any], args: argparse.Namespace) -> None:
    """Additively attach a calibrated object pose to ``analysis`` (opt-in, YOLO only).

    No-op unless a calibration is configured AND a positive metric stop distance is
    set, and only on a YOLO-sourced detection (the calibration is fit on the YOLO
    bbox equivalent diameter). Any error is recorded but never raised, so the proven
    area-ratio path is untouched when pose is unavailable.
    """
    cal_path = str(getattr(args, "calibration", "") or "")
    stop_distance_m = float(getattr(args, "stack_forward_stop_distance_m", 0.0) or 0.0)
    if not cal_path or stop_distance_m <= 0.0:
        return
    if not bool(analysis.get("detected", False)):
        return
    if not str(analysis.get("target_profile", "") or "").startswith("yolo"):
        return
    bbox = analysis.get("bbox") if isinstance(analysis.get("bbox"), dict) else {}
    if not bbox:
        return
    try:
        width_px = float(bbox.get("x1", 0.0)) - float(bbox.get("x0", 0.0))
        height_px = float(bbox.get("y1", 0.0)) - float(bbox.get("y0", 0.0))
        if width_px <= 0.0 or height_px <= 0.0:
            return
        equiv_diameter_px = math.sqrt(width_px * height_px)
        cal = _load_object_pose_calibration(cal_path)
        focal_px = (cal["k_px_m"] / cal["object_size_m"]) if cal["object_size_m"] > 0.0 else 0.0
        image_width = float(analysis.get("image_width", 320) or 320)
        hfov_deg = math.degrees(2.0 * math.atan((image_width / 2.0) / focal_px)) if focal_px > 0.0 else 62.2
        analysis["object_pose"] = object_pose.estimate_object_pose(
            equiv_diameter_px,
            k_px_m=cal["k_px_m"],
            sigma_s_px=cal["sigma_s_px"],
            object_size_m=cal["object_size_m"],
            center_error=float(analysis.get("center_error", 0.0) or 0.0),
            horizontal_fov_deg=hfov_deg,
            max_reliable_range_m=cal["max_reliable_range_m"],
        )
    except Exception as exc:  # never let pose wiring break the proven path
        analysis["object_pose_error"] = repr(exc)[:200]


def stack_state_from_analysis(analysis: dict[str, Any], *, decision_id: str) -> dict[str, Any]:
    detected = bool(analysis.get("detected", False))
    centered = bool(analysis.get("centered", False))
    return {
        "control_plane_ready": True,
        "environment_state": "environment_ready",
        "session_id": decision_id,
        "sim_gate_ready": True,
        "belief": {
            "robot_pose_available": True,
            "latest_robot_pose": {
                "source": "factory_bridge_camera_relative",
                "frame": "base_link",
                "pose_kind": "bridge_adapter_placeholder_pose",
            },
        },
        "perception": {
            "detection_topic_seen": True,
            "target_visible_now": detected,
            "target_profile": analysis.get("target_profile"),
            "target_center_error": analysis.get("center_error"),
            "target_area_ratio": analysis.get("area_ratio"),
            "target_bbox": analysis.get("bbox"),
            "target_z_m_forward": (analysis.get("object_pose") or {}).get("z_m_forward"),
            "target_bearing_rad": (analysis.get("object_pose") or {}).get("bearing_rad_right_positive"),
            "target_sigma_d_m": (analysis.get("object_pose") or {}).get("sigma_d_m"),
            "target_pose_status": (analysis.get("object_pose") or {}).get("pose_status"),
            "camera_source": "factory_bridge_csi_snapshot",
        },
        "brain": {
            "target_locked": bool(detected and centered),
            "target_visible_recent": detected,
            "goal_in_progress": False,
            "track_active": False,
            "search_active": False,
        },
        "mission": {
            "route_planning_active": False,
            "objective": "fetch_to_pose",
        },
    }


def stack_command_from_policy(
    analysis: dict[str, Any],
    policy_snapshot: dict[str, Any],
    args: argparse.Namespace,
) -> tuple[dict[str, float], list[str], str]:
    detected = bool(analysis.get("detected", False))
    preferred_intent = str(policy_snapshot.get("preferred_intent", "") or "")
    stage = str(policy_snapshot.get("stage", "") or "")
    raw_recommendation = analysis.get("recommendation") if isinstance(analysis.get("recommendation"), dict) else {}
    command = {
        "linear_x": float(raw_recommendation.get("linear_x", 0.0) or 0.0),
        "angular_z": float(raw_recommendation.get("angular_z", 0.0) or 0.0),
    }
    issues: list[str] = []
    stop_reason = "stack_policy_noop"

    if stage in ("blocked", "stop") or preferred_intent in ("safe_stop", "abort", ""):
        issues.append("stack_policy_safe_stop")
        return {"linear_x": 0.0, "angular_z": 0.0}, issues, "stack_policy_safe_stop"

    if not detected:
        if preferred_intent == "search_for_target":
            command = {
                "linear_x": 0.0,
                "angular_z": float(args.stack_search_angular_z) * (1.0 if float(args.visual_turn_sign) >= 0.0 else -1.0),
            }
            command = bound_policy_command(command, args)
            if not command_nonzero(command):
                issues.append("policy_command_zero")
            return command, issues, "search_for_target_turn_command"
        issues.append("target_not_detected")
        return {"linear_x": 0.0, "angular_z": 0.0}, issues, "target_not_detected"

    if preferred_intent == "acquire_target":
        command["linear_x"] = 0.0
        center_error = analysis.get("center_error")
        if center_error is not None:
            max_acquire_angular_z = float(args.stack_acquire_max_angular_z)
            if max_acquire_angular_z <= 0.0:
                max_acquire_angular_z = float(args.max_policy_angular_z)
            command["angular_z"] = clamp(
                -float(args.stack_acquire_turn_sign) * float(center_error) * float(args.visual_angular_gain),
                -max_acquire_angular_z,
                max_acquire_angular_z,
            )
            min_acquire_angular_z = max(0.0, float(args.stack_acquire_min_angular_z))
            if min_acquire_angular_z > 0.0 and abs(command["angular_z"]) > 0.0:
                turn_sign = 1.0 if command["angular_z"] > 0.0 else -1.0
                command["angular_z"] = turn_sign * min(
                    max_acquire_angular_z,
                    max(min_acquire_angular_z, abs(command["angular_z"])),
                )
        stop_reason = "acquire_target_turn_command"
    elif preferred_intent == "plan_to_target":
        if bool(analysis.get("centered", False)):
            command["angular_z"] = 0.0
        area_ratio = float(analysis.get("area_ratio", 0.0) or 0.0)
        bbox_height_ratio = float(analysis.get("bbox_height_ratio", 0.0) or 0.0)
        stop_bbox_height_ratio = float(args.stack_forward_stop_bbox_height_ratio)
        stop_distance_m = float(getattr(args, "stack_forward_stop_distance_m", 0.0) or 0.0)
        object_pose_obs = analysis.get("object_pose") if isinstance(analysis.get("object_pose"), dict) else {}
        metric_z = object_pose_obs.get("z_m_forward")
        metric_stop = (
            stop_distance_m > 0.0
            and object_pose_obs.get("pose_status") == "metric"
            and metric_z is not None
            and float(metric_z) <= stop_distance_m
        )
        if metric_stop:
            command = {"linear_x": 0.0, "angular_z": 0.0}
            stop_reason = "target_inside_stack_forward_stop_distance"
        elif area_ratio >= float(args.stack_forward_stop_area_ratio):
            command = {"linear_x": 0.0, "angular_z": 0.0}
            stop_reason = "target_inside_stack_forward_stop_area"
        elif stop_bbox_height_ratio > 0.0 and bbox_height_ratio >= stop_bbox_height_ratio:
            command = {"linear_x": 0.0, "angular_z": 0.0}
            stop_reason = "target_inside_stack_forward_stop_bbox_height"
        else:
            command["linear_x"] = max(float(command.get("linear_x", 0.0) or 0.0), float(args.stack_forward_x))
            stop_reason = "fetch_to_pose_approach_command"
    elif preferred_intent == "track_target":
        stop_reason = "track_target_bridge_command"
    else:
        issues.append("unsupported_stack_intent:%s" % preferred_intent)
        command = {"linear_x": 0.0, "angular_z": 0.0}
        stop_reason = "unsupported_stack_intent"

    command = bound_policy_command(command, args)
    if not command_nonzero(command) and not safe_terminal_zero_stop(stop_reason, command):
        issues.append("policy_command_zero")
    return command, issues, stop_reason


def run_visual_target_turn_policy(
    client: bridge_client.BridgeClient,
    args: argparse.Namespace,
    artifact_dir: Path,
) -> dict[str, Any]:
    ensure_dir(artifact_dir)
    frame_path = artifact_dir / "policy_observation.jpg"
    annotated_path = artifact_dir / "policy_observation_annotated.jpg"
    snapshot = save_snapshot(client, frame_path, args)
    behavior_args = build_visual_policy_args(args)
    analysis = analyze_policy_image(
        frame_path,
        args,
        behavior_args,
        annotated_path=annotated_path,
        allow_forward=False,
    )
    raw_command = analysis.get("recommendation") if isinstance(analysis.get("recommendation"), dict) else {}
    command = bound_policy_command(raw_command, args)
    detected = bool(analysis.get("detected", False))
    issues = list(analysis.get("issues", [])) if isinstance(analysis.get("issues"), list) else []
    stop_reason = "target_detected_turn_command" if detected and command_nonzero(command) else "no_bounded_motion_command"
    if not detected:
        stop_reason = "target_not_detected"
    if not detected and "target_not_detected" not in issues:
        issues.append("target_not_detected")
    if detected and not command_nonzero(command):
        issues.append("policy_command_zero")
    decision = {
        "entrypoint": POLICY_JETBOT_VISUAL_TARGET_TURN_V0,
        "decision_id": "%s:%s" % (POLICY_JETBOT_VISUAL_TARGET_TURN_V0, utc_stamp()),
        "pass": bool(not issues and command_nonzero(command)),
        "issues": issues,
        "stop_reason": stop_reason,
        "observation": {
            "snapshot": snapshot,
            "target_profile": args.target_profile,
            "detected": detected,
            "center_error": analysis.get("center_error"),
            "area_ratio": analysis.get("area_ratio"),
            "bbox": analysis.get("bbox"),
            "annotated_image_path": selected_annotated_image_path(analysis, annotated_path),
        },
        "raw_recommendation": raw_command,
        "command": command,
        "command_bounds": command_bounds(args),
        "analysis": analysis,
    }
    write_json(artifact_dir / "policy_decision.json", decision)
    return decision


def run_chasecar_stack_fetch_adapter_policy(
    client: bridge_client.BridgeClient,
    args: argparse.Namespace,
    artifact_dir: Path,
) -> dict[str, Any]:
    ensure_dir(artifact_dir)
    frame_path = artifact_dir / "policy_observation.jpg"
    annotated_path = artifact_dir / "policy_observation_annotated.jpg"
    snapshot = save_snapshot(client, frame_path, args)
    behavior_args = build_stack_fetch_policy_args(args)
    analysis = analyze_policy_image(
        frame_path,
        args,
        behavior_args,
        annotated_path=annotated_path,
        allow_forward=True,
    )
    attach_object_pose(analysis, args)
    decision_id = "%s:%s" % (POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0, utc_stamp())
    stack_state = stack_state_from_analysis(analysis, decision_id=decision_id)
    policy_snapshot = supervisor_policy.build_policy_snapshot(stack_state, sim_gate_ready=True)
    command, command_issues, stop_reason = stack_command_from_policy(analysis, policy_snapshot, args)
    safe_terminal_stop = safe_terminal_zero_stop(stop_reason, command)
    analysis_issues = list(analysis.get("issues", [])) if isinstance(analysis.get("issues"), list) else []
    issues = (
        analysis_issues
        if not bool(analysis.get("detected", False)) and stop_reason != "search_for_target_turn_command"
        else []
    )
    for issue in command_issues:
        if issue not in issues:
            issues.append(issue)
    decision = {
        "entrypoint": POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0,
        "decision_id": decision_id,
        "pass": bool(not issues and (command_nonzero(command) or safe_terminal_stop)),
        "issues": issues,
        "stop_reason": stop_reason,
        "safe_terminal_stop": safe_terminal_stop,
        "observation": {
            "snapshot": snapshot,
            "target_profile": args.target_profile,
            "detected": bool(analysis.get("detected", False)),
            "centered": bool(analysis.get("centered", False)),
            "center_error": analysis.get("center_error"),
            "area_ratio": analysis.get("area_ratio"),
            "bbox": analysis.get("bbox"),
            "annotated_image_path": selected_annotated_image_path(analysis, annotated_path),
        },
        "stack_state": stack_state,
        "stack_policy": policy_snapshot,
        "stack_lineage": chasecar_stack_lineage(args),
        "raw_recommendation": analysis.get("recommendation", {}),
        "command": command,
        "command_bounds": command_bounds(args),
        "analysis": analysis,
    }
    write_json(artifact_dir / "policy_decision.json", decision)
    return decision


def run_policy_entrypoint(
    client: bridge_client.BridgeClient,
    args: argparse.Namespace,
    artifact_dir: Path,
) -> dict[str, Any]:
    ensure_dir(artifact_dir)
    if args.policy_entrypoint == POLICY_FIXED_COMMAND_V0:
        command = bound_policy_command(command_from_args(args), args)
        issues: list[str] = []
        if not command_nonzero(command):
            issues.append("policy_command_zero")
        decision = {
            "entrypoint": POLICY_FIXED_COMMAND_V0,
            "decision_id": "%s:%s" % (POLICY_FIXED_COMMAND_V0, utc_stamp()),
            "pass": bool(not issues),
            "issues": issues,
            "stop_reason": "fixed_command_loaded" if not issues else "fixed_command_invalid",
            "observation": {"source": "operator_cli"},
            "raw_recommendation": command_from_args(args),
            "command": command,
            "command_bounds": command_bounds(args),
        }
        write_json(artifact_dir / "policy_decision.json", decision)
        return decision
    if args.policy_entrypoint == POLICY_JETBOT_VISUAL_TARGET_TURN_V0:
        return run_visual_target_turn_policy(client, args, artifact_dir)
    if args.policy_entrypoint == POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0:
        return run_chasecar_stack_fetch_adapter_policy(client, args, artifact_dir)
    raise RuntimeError("unsupported_policy_entrypoint:%s" % args.policy_entrypoint)


def deploy_health_from_stdout(stdout: str) -> dict[str, Any] | None:
    for index, char in enumerate(stdout or ""):
        if char != "{":
            continue
        try:
            payload = json.loads(stdout[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "motion_enabled" in payload:
            return payload
    return None


def deploy_bridge(args: argparse.Namespace, artifact_dir: Path, *, enable_motion: bool) -> dict[str, Any]:
    if args.skip_deploy:
        payload = {"skipped": True, "enable_motion": bool(enable_motion)}
        write_json(artifact_dir / ("deploy_motion.json" if enable_motion else "deploy_locked.json"), payload)
        return payload
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
        "-MaxLinearX",
        str(args.max_bridge_linear_x),
        "-MaxAngularZ",
        str(args.max_bridge_angular_z),
        "-Start",
        "-Camera",
        "-CameraBackend",
        args.camera_backend,
        "-CameraWidth",
        str(args.camera_width),
        "-CameraHeight",
        str(args.camera_height),
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
    health = deploy_health_from_stdout(result.stdout)
    if health is not None:
        payload["health"] = health
    write_json(artifact_dir / ("deploy_motion.json" if enable_motion else "deploy_locked.json"), payload)
    if result.returncode != 0:
        raise RuntimeError("deploy_bridge_failed:%s" % result.returncode)
    if health is not None and bool(health.get("motion_enabled", False)) != bool(enable_motion):
        raise RuntimeError(
            "deploy_bridge_motion_state_mismatch:expected=%s actual=%s"
            % (bool(enable_motion), bool(health.get("motion_enabled", False)))
        )
    return payload


def deploy_bridge_locked(args: argparse.Namespace, artifact_dir: Path) -> dict[str, Any]:
    return deploy_bridge(args, artifact_dir, enable_motion=False)


def set_bridge_motion_state(
    client: bridge_client.BridgeClient,
    args: argparse.Namespace,
    artifact_dir: Path,
    *,
    enable_motion: bool,
    phase: str,
) -> dict[str, Any]:
    artifact_dir = ensure_dir(artifact_dir)
    mode = str(args.motion_control_mode)
    http_payload: dict[str, Any] = {
        "mode": "http",
        "phase": str(phase),
        "enable_motion": bool(enable_motion),
        "pass": False,
    }
    if mode in ("auto", "http"):
        try:
            status, response = client.set_motion_enabled(
                bool(enable_motion),
                "chasecar_bridge_stack_path_gate:%s" % phase,
            )
            http_payload.update({"http_status": status, "response": response})
            if bool(response.get("motion_enabled", False)) != bool(enable_motion):
                raise RuntimeError(
                    "http_motion_state_mismatch:expected=%s actual=%s"
                    % (bool(enable_motion), bool(response.get("motion_enabled", False)))
                )
            http_payload["pass"] = True
            write_json(artifact_dir / "motion_control.json", http_payload)
            return http_payload
        except bridge_client.BridgeHttpError as exc:
            http_payload.update(
                {
                    "http_status": exc.status_code,
                    "response": exc.payload,
                    "error": "bridge_http_%s" % exc.status_code,
                }
            )
            write_json(artifact_dir / "motion_control.json", http_payload)
            if mode == "http":
                raise RuntimeError("http_motion_control_failed:%s" % exc.status_code) from exc
        except Exception as exc:
            http_payload["error"] = repr(exc)
            write_json(artifact_dir / "motion_control.json", http_payload)
            if mode == "http":
                raise
    return deploy_bridge(args, artifact_dir, enable_motion=bool(enable_motion))


def camera_readiness_summary(client: bridge_client.BridgeClient, args: argparse.Namespace, phase: str) -> dict[str, Any]:
    deadline = time.monotonic() + max(0.0, float(args.camera_ready_timeout_s))
    checks: list[dict[str, Any]] = []
    while True:
        check: dict[str, Any] = {"checked_utc": utc_now()}
        try:
            status, health = client.health()
            camera = health.get("camera", {}) if isinstance(health, dict) else {}
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
            check.update({"http_status": status, "ok": bool(health.get("ok", False)), "camera": camera, "ready": ready})
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
    issues: list[str] = []
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
    return {
        "phase": phase,
        "pass": bool(latest.get("ready", False)),
        "checks": checks,
        "latest": latest,
        "issues": issues,
    }


def safe_final_state(final_health: dict[str, Any]) -> bool:
    response = final_health.get("response") if isinstance(final_health.get("response"), dict) else final_health
    return bool(
        response.get("motion_enabled") is False
        and abs(float(response.get("left_motor", 0.0) or 0.0)) < 1.0e-6
        and abs(float(response.get("right_motor", 0.0) or 0.0)) < 1.0e-6
    )


def wait_for_safe_locked_health(
    client: bridge_client.BridgeClient,
    *,
    timeout_s: float = 2.0,
    interval_s: float = 0.10,
) -> dict[str, Any]:
    deadline = time.monotonic() + max(0.0, float(timeout_s))
    last_result: dict[str, Any] = {}
    while True:
        status, payload = client.health()
        last_result = {"http_status": status, "response": payload, "checked_utc": utc_now()}
        if safe_final_state(last_result) or time.monotonic() >= deadline:
            return last_result
        time.sleep(max(0.02, float(interval_s)))


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
  --max-linear-x {args.max_runtime_linear_x} \\
  --max-angular-z {args.max_runtime_angular_z} \\
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
    args: argparse.Namespace,
    artifact_dir: Path,
    runtime_path: Path,
    *,
    require_motion_enabled: bool = False,
) -> dict[str, Any]:
    ensure_dir(artifact_dir)
    script_path = artifact_dir / "stack_path_relay.sh"
    script_path.write_text(
        relay_bash(args, artifact_dir, runtime_path, require_motion_enabled=require_motion_enabled),
        encoding="utf-8",
        newline="\n",
    )
    stdout_path = artifact_dir / "wsl_stdout.log"
    stderr_path = artifact_dir / "wsl_stderr.log"
    relay_summary_path = artifact_dir / "relay_summary.json"
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(
            ["wsl", "-d", args.distro, "--", "bash", windows_path_to_wsl(script_path)],
            cwd=str(REPO_ROOT),
            stdout=stdout,
            stderr=stderr,
        )
        try:
            total_timeout_s = float(args.relay_start_timeout_s) + float(args.relay_finish_timeout_s)
            exit_code = process.wait(timeout=total_timeout_s)
            if exit_code != 0:
                raise RuntimeError("relay_process_failed:%s" % exit_code)
            if not relay_summary_path.exists():
                raise RuntimeError("relay_summary_not_created")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
    return load_json(relay_summary_path)


def relay_counters(relay_summary: dict[str, Any]) -> dict[str, Any]:
    relay = relay_summary.get("relay") if isinstance(relay_summary.get("relay"), dict) else {}
    counters = relay.get("counters") if isinstance(relay.get("counters"), dict) else {}
    return counters


def relay_nonzero_success_events(relay_summary: dict[str, Any]) -> list[dict[str, Any]]:
    relay = relay_summary.get("relay") if isinstance(relay_summary.get("relay"), dict) else {}
    events = relay.get("events") if isinstance(relay.get("events"), list) else []
    successes: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict) or int(event.get("http_status", 0) or 0) != 200:
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if not command_nonzero(
            {
                "linear_x": float(payload.get("linear_x", 0.0) or 0.0),
                "angular_z": float(payload.get("angular_z", 0.0) or 0.0),
            }
        ):
            continue
        response = event.get("response") if isinstance(event.get("response"), dict) else {}
        last_command = response.get("last_command") if isinstance(response.get("last_command"), dict) else {}
        if abs(float(last_command.get("left", 0.0) or 0.0)) > 1.0e-6 or abs(
            float(last_command.get("right", 0.0) or 0.0)
        ) > 1.0e-6:
            successes.append(event)
    return successes


def bridge_command_from_runtime(command: dict[str, float], args: argparse.Namespace) -> dict[str, float]:
    return {
        "linear_x": clamp(
            float(command.get("linear_x", 0.0) or 0.0) * float(args.linear_scale),
            -float(args.max_bridge_linear_x),
            float(args.max_bridge_linear_x),
        ),
        "angular_z": clamp(
            float(command.get("angular_z", 0.0) or 0.0) * float(args.angular_scale),
            -float(args.max_bridge_angular_z),
            float(args.max_bridge_angular_z),
        ),
    }


def direct_http_motion_phase(
    client: bridge_client.BridgeClient,
    args: argparse.Namespace,
    command: dict[str, float],
) -> dict[str, Any]:
    bridge_command = bridge_command_from_runtime(command, args)
    error = ""
    try:
        status, response = client.cmd_vel(
            bridge_command["linear_x"],
            bridge_command["angular_z"],
            float(args.command_duration_s),
            "chasecar_bridge_stack_path_gate:direct_http_cmd_vel",
        )
    except bridge_client.BridgeHttpError as exc:
        status = int(exc.status_code)
        response = exc.payload if isinstance(exc.payload, dict) else {"raw_body": exc.raw_body.decode("utf-8", "replace")}
        error = "bridge_http_%s" % status
    except bridge_client.BridgeClientError as exc:
        status = 0
        response = {"error": str(exc)}
        error = str(exc)
    event = {
        "action": "cmd_vel",
        "at_utc": utc_now(),
        "http_status": status,
        "payload": {
            "linear_x": bridge_command["linear_x"],
            "angular_z": bridge_command["angular_z"],
            "duration_s": float(args.command_duration_s),
            "raw": dict(command),
            "source": "chasecar_bridge_stack_path_gate:direct_http_cmd_vel",
        },
        "response": response,
    }
    if error:
        event["error"] = error
    return {
        "base_url": args.base_url,
        "direct_http": True,
        "relay": {
            "config": {
                "linear_scale": float(args.linear_scale),
                "angular_scale": float(args.angular_scale),
                "max_bridge_linear_x": float(args.max_bridge_linear_x),
                "max_bridge_angular_z": float(args.max_bridge_angular_z),
                "command_duration_s": float(args.command_duration_s),
            },
            "counters": {
                "messages_received": 1,
                "cmd_vel_posts": 1,
                "http_errors": 0 if int(status) == 200 else 1,
                "http_refusals": 1 if int(status) == 423 else 0,
                "dry_run_actions": 0,
                "stop_posts": 0,
            },
            "events": [event],
            "last_input": {
                "topic": "/cmd_vel",
                "message_type": "geometry_msgs/msg/Twist",
                "raw_linear_x": float(command.get("linear_x", 0.0) or 0.0),
                "raw_angular_z": float(command.get("angular_z", 0.0) or 0.0),
                "bridge_linear_x": bridge_command["linear_x"],
                "bridge_angular_z": bridge_command["angular_z"],
                "received_utc": event["at_utc"],
            },
        },
    }


def fetch_camera_frame_http(client: bridge_client.BridgeClient, path: Path, args: argparse.Namespace) -> dict[str, Any]:
    status, image_bytes = bridge_client.snapshot_with_retries(
        client,
        attempts=args.snapshot_attempts,
        interval_s=args.snapshot_retry_interval_s,
    )
    ensure_dir(path.parent)
    path.write_bytes(image_bytes)
    return {
        "camera_fetch_mode": str(getattr(args, "camera_fetch_mode", "http")),
        "camera_fetch_mode_selected": "http",
        "source": "bridge_http_camera",
        "http_status": status,
        "output": str(path),
        "bytes": len(image_bytes),
    }


def parse_curl_camera_status(stdout: str) -> tuple[int, int]:
    tokens = str(stdout or "").strip().split()
    if len(tokens) < 2:
        return 0, 0
    try:
        return int(tokens[-2]), int(float(tokens[-1]))
    except ValueError:
        return 0, 0


def fetch_camera_frame_ssh(path: Path, args: argparse.Namespace) -> dict[str, Any]:
    ensure_dir(path.parent)
    target = ssh_camera_target(args)
    timeout_s = camera_fetch_timeout_s(args)
    remote_path = "/tmp/chasebot_bridge_camera_%s_%d.jpg" % (utc_stamp(), int(time.time() * 1000) % 1000000000)
    remote_url = "http://127.0.0.1:%d/camera.jpg" % int(getattr(args, "port", 8765))
    ssh_base = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        ssh_connect_timeout_arg(args),
        target,
    ]
    curl_remote = " ".join(
        [
            "curl",
            "--http1.0",
            "--no-keepalive",
            "--silent",
            "--show-error",
            "--max-time",
            str(timeout_s),
            "--output",
            sh_quote(remote_path),
            "--write-out",
            sh_quote("%{http_code} %{size_download}"),
            sh_quote(remote_url),
        ]
    )
    curl_run = subprocess.run(
        ssh_base + [curl_remote],
        capture_output=True,
        text=True,
        timeout=timeout_s + 2.0,
        check=False,
    )
    if curl_run.returncode != 0:
        raise RuntimeError("ssh_camera_curl_failed:%s:%s" % (curl_run.returncode, curl_run.stderr.strip()))
    http_status, remote_bytes = parse_curl_camera_status(curl_run.stdout)
    if http_status != 200 or remote_bytes <= 0:
        raise RuntimeError("ssh_camera_curl_bad_status:%s:%s" % (http_status, remote_bytes))

    scp_run = subprocess.run(
        [
            "scp",
            "-q",
            "-o",
            "BatchMode=yes",
            "-o",
            ssh_connect_timeout_arg(args),
            "%s:%s" % (target, remote_path),
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=timeout_s + 2.0,
        check=False,
    )
    cleanup_run = subprocess.run(
        ssh_base + ["rm -f %s" % sh_quote(remote_path)],
        capture_output=True,
        text=True,
        timeout=max(2.0, min(timeout_s, 5.0)),
        check=False,
    )
    if scp_run.returncode != 0:
        raise RuntimeError("ssh_camera_scp_failed:%s:%s" % (scp_run.returncode, scp_run.stderr.strip()))
    local_bytes = path.stat().st_size
    if local_bytes <= 0:
        raise RuntimeError("ssh_camera_empty_local_frame")
    return {
        "camera_fetch_mode": str(getattr(args, "camera_fetch_mode", "ssh")),
        "camera_fetch_mode_selected": "ssh",
        "source": "ssh_local_bridge_camera",
        "http_status": http_status,
        "output": str(path),
        "bytes": local_bytes,
        "remote_bytes": remote_bytes,
        "ssh_target": target,
        "remote_path": remote_path,
        "cleanup_returncode": cleanup_run.returncode,
    }


def save_snapshot(client: bridge_client.BridgeClient, path: Path, args: argparse.Namespace) -> dict[str, Any]:
    mode = str(getattr(args, "camera_fetch_mode", "http") or "http").lower()
    if mode == "http":
        return fetch_camera_frame_http(client, path, args)
    if mode == "ssh":
        return fetch_camera_frame_ssh(path, args)
    if mode == "auto":
        try:
            return fetch_camera_frame_http(client, path, args)
        except Exception as exc:  # pylint: disable=broad-except
            result = fetch_camera_frame_ssh(path, args)
            result["http_fetch_error"] = repr(exc)
            return result
    raise RuntimeError("unsupported_camera_fetch_mode:%s" % mode)


def score_visual_motion(before_path: Path, after_path: Path, artifact_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    score_args = SimpleNamespace(
        min_visual_shift_px=args.min_visual_shift_px,
        min_visual_shift_score_gain=args.min_visual_shift_score_gain,
        max_static_visual_similarity=args.max_static_visual_similarity,
    )
    score = behavior_runner.analyze_visual_motion(before_path, [after_path], ["after_post_relock"], score_args)
    contact = behavior_runner.maybe_make_contact_sheet(
        [before_path, after_path],
        ["before stack-path motion", "after post-relock"],
        artifact_dir / "before_after_stack_path_motion.jpg",
    )
    score["contact_sheet_path"] = contact.get("output", "") if isinstance(contact, dict) else ""
    score["contact_sheet_result"] = contact
    write_json(artifact_dir / "visual_motion_score.json", score)
    return score


def compute_pass(summary: dict[str, Any]) -> bool:
    if summary.get("issues"):
        return False
    if not bool(summary.get("camera_readiness_gate", {}).get("pass", False)):
        return False
    command = summary.get("command") if isinstance(summary.get("command"), dict) else {}
    policy_decision = summary.get("policy_decision") if isinstance(summary.get("policy_decision"), dict) else {}
    if not bool(policy_decision.get("pass", False)):
        return False
    safe_terminal_stop = bool(summary.get("safe_terminal_stop", False)) or safe_terminal_policy_decision(policy_decision)
    if safe_terminal_stop:
        if not safe_final_state(summary.get("final_locked_health", {})):
            return False
        if not bool(summary.get("final_camera_readiness_gate", {}).get("pass", False)):
            return False
        return True
    if not command_nonzero(command):
        return False
    counters = relay_counters(summary.get("relay_summary", {}))
    if int(counters.get("messages_received", 0) or 0) <= 0:
        return False
    if int(counters.get("cmd_vel_posts", 0) or 0) <= 0:
        return False
    if int(counters.get("http_refusals", 0) or 0) <= 0:
        return False
    if relay_nonzero_success_events(summary.get("relay_summary", {})):
        return False
    if int(counters.get("dry_run_actions", 0) or 0) != 0:
        return False
    if not safe_final_state(summary.get("final_locked_health", {})):
        return False
    if not bool(summary.get("final_camera_readiness_gate", {}).get("pass", False)):
        return False
    if bool(summary.get("execute_motion", False)):
        motion = summary.get("motion_proof") if isinstance(summary.get("motion_proof"), dict) else {}
        if not bool(motion.get("pass", False)):
            return False
    return True


def validate_args(args: argparse.Namespace) -> list[str]:
    issues: list[str] = []
    if args.policy_entrypoint == POLICY_FIXED_COMMAND_V0:
        command = command_from_args(args)
        if not command_nonzero(command):
            issues.append("nonzero_command_required")
        if abs(float(args.command_linear_x)) > float(args.max_runtime_linear_x):
            issues.append("command_linear_x_above_runtime_limit")
        if abs(float(args.command_angular_z)) > float(args.max_runtime_angular_z):
            issues.append("command_angular_z_above_runtime_limit")
    if args.execute_motion and not args.confirm_operator_ready:
        issues.append("operator_ready_confirmation_required")
    if float(args.max_bridge_linear_x) > 0.36:
        issues.append("max_bridge_linear_x_above_conservative_limit")
    if float(args.max_bridge_angular_z) > 0.8:
        issues.append("max_bridge_angular_z_above_locked_gate_limit")
    if args.execute_motion and args.policy_entrypoint == POLICY_FIXED_COMMAND_V0 and abs(float(args.command_linear_x)) > 1.0e-6:
        issues.append("live_stack_motion_requires_turn_only")
    if float(args.max_motor_speed) > 1.0:
        issues.append("max_motor_speed_above_1")
    if float(args.max_policy_angular_z) > float(args.max_runtime_angular_z):
        issues.append("max_policy_angular_z_above_runtime_limit")
    if args.policy_entrypoint == POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0:
        if float(args.max_stack_linear_x) > float(args.max_runtime_linear_x):
            issues.append("max_stack_linear_x_above_runtime_limit")
        if float(args.stack_forward_x) > float(args.max_stack_linear_x):
            issues.append("stack_forward_x_above_stack_limit")
    if str(getattr(args, "camera_fetch_mode", "http")) in {"ssh", "auto"}:
        if not str(getattr(args, "robot_host", "") or "").strip():
            issues.append("camera_fetch_robot_host_required")
        if not str(getattr(args, "robot_user", "") or "").strip():
            issues.append("camera_fetch_robot_user_required")
    return issues


def live_motion_command_issues(command: dict[str, Any], args: argparse.Namespace) -> list[str]:
    issues: list[str] = []
    if not bool(args.execute_motion):
        return issues
    if bool(args.live_motion_require_turn_only) and abs(float(command.get("linear_x", 0.0) or 0.0)) > 1.0e-6:
        issues.append("live_stack_motion_requires_turn_only")
    return issues


def run_motion_phase(
    client: bridge_client.BridgeClient,
    args: argparse.Namespace,
    artifact_root: Path,
    command: dict[str, float],
) -> dict[str, Any]:
    motion_dir = ensure_dir(artifact_root / "live_motion")
    runtime_path = motion_dir / "runtime" / "stack_path_runtime.json"
    summary: dict[str, Any] = {
        "artifact_dir": str(motion_dir),
        "issues": [],
        "pass": False,
    }
    try:
        summary["before_snapshot"] = save_snapshot(client, motion_dir / "before_locked.jpg", args)
        set_bridge_motion_state(client, args, motion_dir / "enable_motion", enable_motion=True, phase="enable_motion")
        if args.camera_warmup_s > 0:
            time.sleep(float(args.camera_warmup_s))
        motion_camera_ready = camera_readiness_summary(client, args, "motion_enabled")
        summary["camera_readiness_gate"] = motion_camera_ready
        if not motion_camera_ready["pass"]:
            summary["issues"].append("motion_camera_readiness_gate_not_pass")
            return summary
        write_json(runtime_path, runtime_payload(1, command, enabled=True))
        if args.motion_control_mode == "http":
            relay_summary = direct_http_motion_phase(client, args, command)
            write_json(motion_dir / "relay_summary.json", relay_summary)
        else:
            relay_summary = run_relay_phase(args, motion_dir / "relay", runtime_path, require_motion_enabled=True)
        summary["relay_summary"] = relay_summary
        summary["nonzero_success_event_count"] = len(relay_nonzero_success_events(relay_summary))
        time.sleep(max(0.05, min(float(args.relay_window_s), float(args.command_duration_s) + 0.10)))
    except Exception as exc:
        summary["issues"].append("motion_runner_exception:%r" % (exc,))
    finally:
        write_json(runtime_path, runtime_payload(99, command, enabled=False))
        try:
            client.stop("chasecar_bridge_stack_path_gate:motion_finally_stop")
        except Exception as exc:
            summary["issues"].append("motion_finally_stop_failed:%r" % (exc,))
        try:
            set_bridge_motion_state(
                client,
                args,
                motion_dir / "restore_locked",
                enable_motion=False,
                phase="motion_restore_locked",
            )
        except Exception as exc:
            summary["issues"].append("motion_restore_locked_failed:%r" % (exc,))
        try:
            summary["motion_final_locked_health"] = wait_for_safe_locked_health(
                client,
                timeout_s=max(2.0, float(args.command_duration_s) + 1.0),
            )
            if not safe_final_state(summary["motion_final_locked_health"]):
                summary["issues"].append("motion_final_locked_health_not_safe")
        except Exception as exc:
            summary["issues"].append("motion_final_locked_health_failed:%r" % (exc,))
        if args.camera_warmup_s > 0:
            time.sleep(float(args.camera_warmup_s))
        try:
            summary["after_snapshot"] = save_snapshot(client, motion_dir / "after_post_relock.jpg", args)
            summary["visual_motion"] = score_visual_motion(
                Path(summary["before_snapshot"]["output"]),
                Path(summary["after_snapshot"]["output"]),
                motion_dir,
                args,
            )
        except Exception as exc:
            summary["issues"].append("motion_visual_evidence_failed:%r" % (exc,))

    counters = relay_counters(summary.get("relay_summary", {}))
    summary["relay_counters"] = counters
    if int(counters.get("http_refusals", 0) or 0) > 0:
        summary["issues"].append("motion_http_refusals:%s" % int(counters.get("http_refusals", 0) or 0))
    summary["pass"] = bool(
        not summary["issues"]
        and int(counters.get("cmd_vel_posts", 0) or 0) > 0
        and int(counters.get("http_refusals", 0) or 0) == 0
        and int(summary.get("nonzero_success_event_count", 0) or 0) > 0
        and bool(summary.get("visual_motion", {}).get("movement_detected", False))
    )
    write_json(motion_dir / "motion_summary.json", summary)
    return summary


def run(args: argparse.Namespace) -> dict[str, Any]:
    artifact_root = ensure_dir(args.artifact_dir or default_artifact_dir())
    command = {"linear_x": float(args.command_linear_x), "angular_z": float(args.command_angular_z)}
    summary: dict[str, Any] = {
        "generated_utc": utc_now(),
        "type": "factory_bridge_stack_path_gate",
        "artifact_dir": str(artifact_root),
        "base_url": args.base_url,
        "policy_entrypoint": args.policy_entrypoint,
        "command": command if args.policy_entrypoint == POLICY_FIXED_COMMAND_V0 else {},
        "execute_motion": bool(args.execute_motion),
        "issues": validate_args(args),
        "pass": False,
    }
    write_json(artifact_root / "gate_summary.json", summary)
    if summary["issues"] or args.dry_run:
        summary["plan_only"] = bool(args.dry_run)
        summary["pass"] = not summary["issues"]
        write_json(artifact_root / "gate_summary.json", summary)
        return summary

    client = bridge_client.BridgeClient(args.base_url, args.timeout_s)
    runtime_path = artifact_root / "runtime" / "stack_path_runtime.json"
    relay_dir = artifact_root / "relay"
    try:
        summary["start_locked_control"] = set_bridge_motion_state(
            client,
            args,
            artifact_root / "start_locked",
            enable_motion=False,
            phase="start_locked",
        )
        summary["start_locked_health"] = wait_for_safe_locked_health(client, timeout_s=2.0)
        if not safe_final_state(summary["start_locked_health"]):
            summary["issues"].append("start_locked_health_not_safe")
            return summary
        if args.camera_warmup_s > 0:
            time.sleep(float(args.camera_warmup_s))
        camera_ready = camera_readiness_summary(client, args, "start_locked")
        summary["camera_readiness_gate"] = camera_ready
        if not camera_ready["pass"]:
            summary["issues"].append("camera_readiness_gate_not_pass")
            return summary
        policy_decision = run_policy_entrypoint(client, args, artifact_root / "policy")
        summary["policy_decision"] = policy_decision
        if not bool(policy_decision.get("pass", False)):
            summary["issues"].append("policy_decision_not_pass")
            return summary
        command = dict(policy_decision.get("command", {}))
        summary["command"] = command
        summary["safe_terminal_stop"] = safe_terminal_policy_decision(policy_decision)
        if summary["safe_terminal_stop"]:
            summary["locked_transport_pass"] = None
            summary["terminal_evidence"] = {
                "reason": policy_decision.get("stop_reason", ""),
                "relay_skipped": True,
                "command": command,
            }
        else:
            write_json(runtime_path, runtime_payload(1, command, enabled=True, policy_decision=policy_decision))
            relay_summary = run_relay_phase(args, relay_dir, runtime_path)
            summary["relay_summary"] = relay_summary
            locked_acceptance_events = relay_nonzero_success_events(relay_summary)
            summary["locked_transport_nonzero_success_event_count"] = len(locked_acceptance_events)
            if locked_acceptance_events:
                summary["locked_transport_nonzero_success_events"] = locked_acceptance_events
                summary["issues"].append("locked_transport_accepted_motion")
                try:
                    client.stop("chasecar_bridge_stack_path_gate:locked_transport_unexpected_acceptance_stop")
                except Exception as exc:
                    summary["issues"].append("locked_transport_acceptance_stop_failed:%r" % (exc,))
                try:
                    set_bridge_motion_state(
                        client,
                        args,
                        artifact_root / "locked_transport_unexpected_acceptance_relock",
                        enable_motion=False,
                        phase="locked_transport_unexpected_acceptance_relock",
                    )
                except Exception as exc:
                    summary["issues"].append("locked_transport_acceptance_relock_failed:%r" % (exc,))
            locked_ok = compute_pass(
                {
                    **summary,
                    "final_locked_health": {"response": {"motion_enabled": False, "left_motor": 0.0, "right_motor": 0.0}},
                    "final_camera_readiness_gate": {"pass": True},
                    "execute_motion": False,
                }
            )
            summary["locked_transport_pass"] = bool(locked_ok)
            if args.execute_motion and locked_ok:
                summary["live_motion_command_issues"] = live_motion_command_issues(command, args)
                summary["issues"].extend(summary["live_motion_command_issues"])
            if args.execute_motion and locked_ok and not summary.get("live_motion_command_issues"):
                summary["motion_proof"] = run_motion_phase(client, args, artifact_root, command)
    except Exception as exc:
        summary["issues"].append("runner_exception:%r" % (exc,))
    finally:
        write_json(runtime_path, runtime_payload(99, command, enabled=False, policy_decision=summary.get("policy_decision")))
        try:
            set_bridge_motion_state(
                client,
                args,
                artifact_root / "final_restore_locked",
                enable_motion=False,
                phase="final_restore_locked",
            )
        except Exception as exc:
            summary["issues"].append("final_restore_locked_failed:%r" % (exc,))
        if args.camera_warmup_s > 0:
            time.sleep(float(args.camera_warmup_s))
        try:
            summary["final_locked_health"] = wait_for_safe_locked_health(client, timeout_s=2.0)
            summary["final_camera_readiness_gate"] = camera_readiness_summary(client, args, "final_locked")
        except Exception as exc:
            summary["issues"].append("final_health_failed:%r" % (exc,))

    summary["pass"] = compute_pass(summary)
    write_json(artifact_root / "gate_summary.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a locked stack-through-bridge command transport gate.")
    parser.add_argument("--base-url", default=bridge_client.DEFAULT_BASE_URL)
    parser.add_argument("--timeout-s", type=float, default=bridge_client.DEFAULT_TIMEOUT_S)
    parser.add_argument("--artifact-dir", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--execute-motion", action="store_true")
    parser.add_argument("--confirm-operator-ready", action="store_true")
    parser.add_argument(
        "--live-motion-require-turn-only",
        action="store_true",
        help="Fail closed before live motion when the selected policy command includes forward velocity.",
    )
    parser.add_argument("--policy-entrypoint", choices=POLICY_ENTRYPOINTS, default=DEFAULT_POLICY_ENTRYPOINT)

    parser.add_argument("--distro", default="Ubuntu-24.04")
    parser.add_argument("--ros-distro", default="jazzy")
    parser.add_argument("--runtime-source-path", default=DEFAULT_RUNTIME_SOURCE_PATH)
    parser.add_argument("--robot-host", default="192.168.1.11")
    parser.add_argument("--robot-user", default="jetson")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--skip-deploy", action="store_true")
    parser.add_argument(
        "--motion-control-mode",
        choices=MOTION_CONTROL_MODES,
        default="auto",
        help="Use direct HTTP motion lock/unlock when available, deploy-only, or auto fallback.",
    )
    parser.add_argument("--deploy-timeout-s", type=float, default=45.0)
    parser.add_argument("--max-motor-speed", type=float, default=0.7)
    parser.add_argument("--camera-backend", choices=["gstreamer", "jetbotmini", "v4l2_bayer"], default="gstreamer")
    parser.add_argument("--camera-width", type=int, default=320)
    parser.add_argument("--camera-height", type=int, default=240)
    parser.add_argument("--camera-fps", type=float, default=5.0)
    parser.add_argument("--camera-jpeg-quality", type=int, default=55)
    parser.add_argument("--camera-v4l2-device", default="/dev/video0")
    parser.add_argument("--camera-v4l2-raw-width", type=int, default=3264)
    parser.add_argument("--camera-v4l2-raw-height", type=int, default=2464)
    parser.add_argument("--camera-v4l2-pixelformat", default="RG10")

    parser.add_argument("--camera-warmup-s", type=float, default=1.0)
    parser.add_argument("--camera-ready-timeout-s", type=float, default=8.0)
    parser.add_argument("--camera-min-fps", type=float, default=2.0)
    parser.add_argument("--camera-max-frame-age-s", type=float, default=1.0)
    parser.add_argument("--camera-min-frame-bytes", type=int, default=100)
    parser.add_argument("--snapshot-attempts", type=int, default=10)
    parser.add_argument("--snapshot-retry-interval-s", type=float, default=0.15)
    parser.add_argument(
        "--camera-fetch-mode",
        choices=CAMERA_FETCH_MODES,
        default="http",
        help="Fetch camera frames from the bridge over host HTTP, robot-local SSH curl/scp, or HTTP with SSH fallback.",
    )
    parser.add_argument("--camera-fetch-timeout-s", type=float, default=12.0)

    parser.add_argument("--command-linear-x", type=float, default=0.0)
    parser.add_argument("--command-angular-z", type=float, default=0.2)
    parser.add_argument("--max-runtime-linear-x", type=float, default=0.10)
    parser.add_argument("--max-runtime-angular-z", type=float, default=0.40)
    parser.add_argument("--gather-loop-rate-hz", type=float, default=10.0)

    parser.add_argument("--relay-window-s", type=float, default=2.5)
    parser.add_argument("--relay-start-timeout-s", type=float, default=8.0)
    parser.add_argument("--relay-finish-timeout-s", type=float, default=12.0)
    parser.add_argument("--linear-scale", type=float, default=3.0)
    parser.add_argument("--angular-scale", type=float, default=4.0)
    parser.add_argument("--max-bridge-linear-x", type=float, default=0.0)
    parser.add_argument("--max-bridge-angular-z", type=float, default=0.8)
    parser.add_argument("--command-duration-s", type=float, default=0.20)
    parser.add_argument("--post-rate-hz", type=float, default=8.0)
    parser.add_argument("--stale-stop-s", type=float, default=0.35)
    parser.add_argument("--min-visual-shift-px", type=float, default=2.0)
    parser.add_argument("--min-visual-shift-score-gain", type=float, default=0.03)
    parser.add_argument("--max-static-visual-similarity", type=float, default=0.975)
    parser.add_argument("--target-profile", choices=behavior_runner.DEFAULT_VISUAL_SCAN_PROFILES, default="blue")
    parser.add_argument("--target-min-luma", type=float, default=180.0)
    parser.add_argument("--target-min-saturation", type=float, default=0.25)
    parser.add_argument("--target-min-value", type=float, default=0.20)
    parser.add_argument("--target-min-area-ratio", type=float, default=0.05)
    parser.add_argument("--target-max-area-ratio", type=float, default=0.55)
    parser.add_argument("--target-max-bbox-width-ratio", type=float, default=1.0)
    parser.add_argument("--target-max-bbox-height-ratio", type=float, default=1.0)
    parser.add_argument("--target-border-margin-ratio", type=float, default=0.0)
    parser.add_argument("--target-min-bbox-aspect-ratio", type=float, default=0.0)
    parser.add_argument("--target-max-bbox-aspect-ratio", type=float, default=0.0)
    parser.add_argument("--target-min-centroid-y-ratio", type=float, default=0.0)
    parser.add_argument("--target-max-centroid-y-ratio", type=float, default=1.0)
    parser.add_argument("--detector-backend", choices=["color", "yolo_onnx", "yolo_onnx_or_color"], default="color")
    parser.add_argument("--yolo-onnx-model", default="runtime/yolo/yolov5s.onnx")
    parser.add_argument("--yolo-onnx-fallback-model", default="runtime/yolo/yolov5m.onnx")
    parser.add_argument("--yolo-target-class", action="append", default=[])
    parser.add_argument("--yolo-onnx-confidence-threshold", type=float, default=0.25)
    parser.add_argument("--yolo-onnx-fallback-confidence-threshold", type=float, default=0.03)
    parser.add_argument("--yolo-onnx-iou-threshold", type=float, default=0.45)
    parser.add_argument("--yolo-onnx-input-size", type=int, default=640)
    parser.add_argument("--yolo-target-min-area-ratio", type=float, default=0.0)
    parser.add_argument("--yolo-color-override-area-multiplier", type=float, default=1.35)
    parser.add_argument("--visual-center-deadband", type=float, default=0.16)
    parser.add_argument("--visual-turn-sign", type=float, default=1.0)
    parser.add_argument("--visual-angular-gain", type=float, default=4.0)
    parser.add_argument("--max-policy-angular-z", type=float, default=0.4)
    parser.add_argument("--stack-forward-x", type=float, default=0.025)
    parser.add_argument("--stack-search-angular-z", type=float, default=0.18)
    parser.add_argument("--stack-acquire-turn-sign", type=float, default=1.0)
    parser.add_argument("--stack-acquire-min-angular-z", type=float, default=0.0)
    parser.add_argument("--stack-acquire-max-angular-z", type=float, default=0.0)
    parser.add_argument("--max-stack-linear-x", type=float, default=0.04)
    parser.add_argument("--stack-forward-stop-area-ratio", type=float, default=0.48)
    parser.add_argument("--stack-forward-stop-bbox-height-ratio", type=float, default=0.0)
    parser.add_argument("--stack-forward-stop-distance-m", type=float, default=0.0,
                        help="If >0 and --calibration set, stop the forward approach when calibrated object distance <= this (metres).")
    parser.add_argument("--calibration", default="",
                        help="Path to a mono distance calibration_summary.json; enables the calibrated metric forward-stop.")
    parser.add_argument("--stack-policy-checkpoint", default="")
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
