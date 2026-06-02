#!/usr/bin/env python3
"""Hybrid fetch stage supervisor helpers.

The first v1 helper is intentionally conservative: it does not learn or drive
directly. It produces the same shape of decision a later small learned model
will produce, then deterministic guards decide whether a known routine may run.
"""

from __future__ import annotations

import math
import time
from typing import Any

from gather_mission_helpers import PlaceControlCommand
from gather_mission_helpers import clamp
from gather_mission_helpers import normalize_angle
from gather_mission_helpers import world_pose_xyyaw


AI_PUSH_COAST_SERVO_CONTROL_FAMILY = "ai_push_coast_servo_v1"
AI_PUSH_COAST_MODE_SHADOW = "shadow"
AI_PUSH_COAST_MODE_GUARDED_LIVE = "guarded_live"
ALLOWED_AI_PUSH_COAST_MODES = (
    AI_PUSH_COAST_MODE_SHADOW,
    AI_PUSH_COAST_MODE_GUARDED_LIVE,
)

AI_PUSH_COAST_MAX_TERMINAL_MISS_M = 0.55
AI_PUSH_COAST_MAX_LATERAL_ERROR_M = 0.22
AI_PUSH_COAST_MAX_SETUP_YAW_ERROR_DEG = 18.0
AI_PUSH_COAST_PREDICTED_TERMINAL_GAIN_M = 0.22
AI_PUSH_COAST_PREDICTED_TERMINAL_TOLERANCE_M = 0.015
AI_PUSH_COAST_CAPTURE_YAW_WATCH_DEG = 60.0
AI_PUSH_COAST_CAPTURE_YAW_SIGN_CROSSING_WATCH_COUNT = 2
AI_PUSH_COAST_CAPTURE_YAW_SIGN_CROSSING_DEADBAND_DEG = 5.0
AI_PUSH_READINESS_MIN_STANDOFF_M = 0.12
AI_PUSH_READINESS_MAX_STANDOFF_M = 0.80
AI_PUSH_READINESS_MAX_LATERAL_ERROR_M = 0.12
AI_PUSH_READINESS_MAX_YAW_ERROR_DEG = 20.0
AI_PUSH_READINESS_DELIVERY_MARGIN_M = 0.02
AI_PUSH_READINESS_SETUP_TARGET_STANDOFF_M = 0.24
AI_PUSH_READINESS_SETUP_MAX_LINEAR_X_MPS = 0.08
AI_PUSH_READINESS_SETUP_MAX_ANGULAR_Z_RPS = 0.45
AI_PUSH_READINESS_SETUP_YAW_ONLY_DEG = 25.0
AI_PUSH_READINESS_SETUP_MIN_CORRECTION_MPS = 0.012
AI_PUSH_COAST_FLAG_STAGE_LABELS = {
    "pre_contact_lateral_error": "setup",
    "pre_contact_yaw_error": "setup",
    "capture_geometry_gate_failed": "setup",
    "capture_yaw_watch": "setup",
    "capture_yaw_sign_crossing_watch": "setup",
    "ball_lateral_knock_away": "first_contact",
    "contact_trajectory_angle_error": "push_coast",
}


def _finite_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _target_basis(
    ball_pose: dict[str, Any] | None,
    fetch_pose_world: dict[str, Any] | None,
) -> tuple[float, float, float, float, float, float] | None:
    ball_xyyaw = world_pose_xyyaw(ball_pose or {})
    fetch_xyyaw = world_pose_xyyaw(fetch_pose_world or {})
    if ball_xyyaw is None or fetch_xyyaw is None:
        return None
    ball_x, ball_y, _ball_yaw = ball_xyyaw
    fetch_x, fetch_y, _fetch_yaw = fetch_xyyaw
    dx = float(fetch_x) - float(ball_x)
    dy = float(fetch_y) - float(ball_y)
    distance_m = math.hypot(dx, dy)
    if distance_m <= 1.0e-6:
        return None
    ux = dx / distance_m
    uy = dy / distance_m
    return ux, uy, -uy, ux, math.atan2(uy, ux), distance_m


def _relative_errors(
    robot_pose: dict[str, Any] | None,
    ball_pose: dict[str, Any] | None,
    fetch_pose_world: dict[str, Any] | None,
) -> dict[str, Any]:
    basis = _target_basis(ball_pose, fetch_pose_world)
    robot_xyyaw = world_pose_xyyaw(robot_pose or {})
    ball_xyyaw = world_pose_xyyaw(ball_pose or {})
    if basis is None or robot_xyyaw is None or ball_xyyaw is None:
        return {}
    push_ux, push_uy, normal_x, normal_y, push_yaw, ball_target_distance_m = basis
    robot_x, robot_y, robot_yaw = robot_xyyaw
    ball_x, ball_y, _ball_yaw = ball_xyyaw
    robot_from_ball_x = float(robot_x) - float(ball_x)
    robot_from_ball_y = float(robot_y) - float(ball_y)
    longitudinal = (robot_from_ball_x * push_ux) + (robot_from_ball_y * push_uy)
    lateral = (robot_from_ball_x * normal_x) + (robot_from_ball_y * normal_y)
    yaw_error = normalize_angle(float(robot_yaw) - float(push_yaw))
    return {
        "robot_longitudinal_projection_m": round(float(longitudinal), 6),
        "robot_standoff_m": round(float(-longitudinal), 6),
        "robot_lateral_signed_m": round(float(lateral), 6),
        "robot_lateral_error_m": round(abs(float(lateral)), 6),
        "robot_yaw_error_deg": round(math.degrees(float(yaw_error)), 6),
        "push_yaw_deg": round(math.degrees(float(push_yaw)), 6),
        "ball_target_distance_m": round(float(ball_target_distance_m), 6),
    }


def evaluate_fetch_push_readiness(
    *,
    robot_pose: dict[str, Any] | None,
    ball_pose: dict[str, Any] | None,
    fetch_pose_world: dict[str, Any] | None,
    delivery_radius_m: float,
    min_standoff_m: float = AI_PUSH_READINESS_MIN_STANDOFF_M,
    max_standoff_m: float = AI_PUSH_READINESS_MAX_STANDOFF_M,
    max_lateral_error_m: float = AI_PUSH_READINESS_MAX_LATERAL_ERROR_M,
    max_yaw_error_deg: float = AI_PUSH_READINESS_MAX_YAW_ERROR_DEG,
    delivery_margin_m: float = AI_PUSH_READINESS_DELIVERY_MARGIN_M,
) -> dict[str, Any]:
    errors = _relative_errors(robot_pose, ball_pose, fetch_pose_world)
    thresholds = {
        "min_standoff_m": round(max(float(min_standoff_m), 0.0), 6),
        "max_standoff_m": round(max(float(max_standoff_m), 0.0), 6),
        "max_lateral_error_m": round(max(float(max_lateral_error_m), 0.0), 6),
        "max_yaw_error_deg": round(max(float(max_yaw_error_deg), 0.0), 6),
        "delivery_radius_m": round(max(float(delivery_radius_m), 0.0), 6),
        "delivery_margin_m": round(max(float(delivery_margin_m), 0.0), 6),
    }
    flags: list[str] = []
    if not errors:
        flags.append("missing_push_readiness_geometry")
        return {
            "pass": False,
            "reason": "missing_push_readiness_geometry",
            "flags": flags,
            "stage_label": "setup",
            "relative_errors": {},
            "thresholds": thresholds,
        }

    longitudinal_m = _finite_float(errors.get("robot_longitudinal_projection_m"))
    standoff_m = _finite_float(errors.get("robot_standoff_m"))
    lateral_error_m = _finite_float(errors.get("robot_lateral_error_m"))
    yaw_error_deg = _finite_float(errors.get("robot_yaw_error_deg"))
    ball_target_distance_m = _finite_float(errors.get("ball_target_distance_m"))
    min_standoff = float(thresholds["min_standoff_m"])
    max_standoff = float(thresholds["max_standoff_m"])
    max_lateral = float(thresholds["max_lateral_error_m"])
    max_yaw = float(thresholds["max_yaw_error_deg"])
    delivery_floor = float(thresholds["delivery_radius_m"]) + float(thresholds["delivery_margin_m"])

    if longitudinal_m is None or standoff_m is None:
        flags.append("missing_robot_ball_projection")
    elif longitudinal_m >= 0.0:
        flags.append("robot_not_behind_ball")
    elif standoff_m < min_standoff:
        flags.append("robot_too_close_for_push")
    elif standoff_m > max_standoff:
        flags.append("robot_too_far_for_push")
    if lateral_error_m is None:
        flags.append("missing_robot_lateral_error")
    elif lateral_error_m > max_lateral:
        flags.append("robot_lateral_error_out_of_bounds")
    if yaw_error_deg is None:
        flags.append("missing_robot_yaw_error")
    elif abs(float(yaw_error_deg)) > max_yaw:
        flags.append("robot_yaw_error_out_of_bounds")
    if ball_target_distance_m is None:
        flags.append("missing_ball_target_distance")
    elif ball_target_distance_m <= delivery_floor:
        flags.append("ball_already_at_delivery_margin")

    passed = not flags
    return {
        "pass": bool(passed),
        "reason": "push_ready" if passed else "push_readiness_gate_failed",
        "flags": flags,
        "stage_label": "" if passed else "setup",
        "relative_errors": errors,
        "thresholds": thresholds,
    }


def compute_fetch_push_readiness_setup_command(
    *,
    robot_pose: dict[str, Any] | None,
    ball_pose: dict[str, Any] | None,
    fetch_pose_world: dict[str, Any] | None,
    delivery_radius_m: float,
    target_standoff_m: float = AI_PUSH_READINESS_SETUP_TARGET_STANDOFF_M,
    max_linear_x_mps: float = AI_PUSH_READINESS_SETUP_MAX_LINEAR_X_MPS,
    max_angular_z_rps: float = AI_PUSH_READINESS_SETUP_MAX_ANGULAR_Z_RPS,
    min_standoff_m: float = AI_PUSH_READINESS_MIN_STANDOFF_M,
    max_standoff_m: float = AI_PUSH_READINESS_MAX_STANDOFF_M,
    max_lateral_error_m: float = AI_PUSH_READINESS_MAX_LATERAL_ERROR_M,
    max_yaw_error_deg: float = AI_PUSH_READINESS_MAX_YAW_ERROR_DEG,
) -> PlaceControlCommand | None:
    gate = evaluate_fetch_push_readiness(
        robot_pose=robot_pose,
        ball_pose=ball_pose,
        fetch_pose_world=fetch_pose_world,
        delivery_radius_m=delivery_radius_m,
        min_standoff_m=min_standoff_m,
        max_standoff_m=max_standoff_m,
        max_lateral_error_m=max_lateral_error_m,
        max_yaw_error_deg=max_yaw_error_deg,
    )
    errors = gate.get("relative_errors", {}) if isinstance(gate.get("relative_errors"), dict) else {}
    thresholds = gate.get("thresholds", {}) if isinstance(gate.get("thresholds"), dict) else {}
    if not errors:
        return None
    if "ball_already_at_delivery_margin" in gate.get("flags", []):
        return None

    standoff_m = _finite_float(errors.get("robot_standoff_m"))
    lateral_signed_m = _finite_float(errors.get("robot_lateral_signed_m"))
    yaw_error_deg = _finite_float(errors.get("robot_yaw_error_deg"))
    if standoff_m is None or lateral_signed_m is None or yaw_error_deg is None:
        return None

    min_standoff_m = float(thresholds.get("min_standoff_m", AI_PUSH_READINESS_MIN_STANDOFF_M) or 0.0)
    max_standoff_m = float(thresholds.get("max_standoff_m", AI_PUSH_READINESS_MAX_STANDOFF_M) or 0.0)
    target_standoff = clamp(
        float(target_standoff_m),
        max(min_standoff_m + 0.04, min_standoff_m),
        max(max_standoff_m - 0.04, min_standoff_m + 0.04),
    )
    yaw_error_rad = math.radians(float(yaw_error_deg))
    lateral_signed = float(lateral_signed_m)
    angular = clamp(
        (-0.85 * yaw_error_rad) - (1.35 * lateral_signed),
        -float(max_angular_z_rps),
        float(max_angular_z_rps),
    )
    if abs(float(yaw_error_deg)) > 6.0 and abs(angular) < 0.14:
        angular = 0.14 if angular >= 0.0 else -0.14

    standoff_error_m = float(standoff_m) - float(target_standoff)
    needs_backoff = float(standoff_m) < target_standoff - 0.025
    yaw_only = abs(float(yaw_error_deg)) > AI_PUSH_READINESS_SETUP_YAW_ONLY_DEG and not needs_backoff
    if yaw_only:
        linear = 0.0
        mode = "push_readiness_yaw_align"
    else:
        linear = clamp(
            standoff_error_m * 0.45,
            -float(max_linear_x_mps),
            float(max_linear_x_mps),
        )
        if abs(linear) < AI_PUSH_READINESS_SETUP_MIN_CORRECTION_MPS and abs(standoff_error_m) > 0.025:
            linear = (
                AI_PUSH_READINESS_SETUP_MIN_CORRECTION_MPS
                if standoff_error_m > 0.0
                else -AI_PUSH_READINESS_SETUP_MIN_CORRECTION_MPS
            )
        if abs(standoff_error_m) <= 0.025 and abs(lateral_signed) > 0.04:
            linear = 0.0
        if float(standoff_m) < min_standoff_m:
            mode = (
                "push_readiness_backoff_yaw_align"
                if abs(float(yaw_error_deg)) > AI_PUSH_READINESS_SETUP_YAW_ONLY_DEG
                else "push_readiness_backoff"
            )
        elif float(standoff_m) > max_standoff_m:
            mode = "push_readiness_advance"
        elif abs(lateral_signed) > float(max_lateral_error_m):
            mode = "push_readiness_lateral_align"
        else:
            mode = "push_readiness_setup"

    if abs(linear) <= 1.0e-6 and abs(angular) <= 1.0e-6:
        return PlaceControlCommand(
            mode="push_readiness_setup_hold",
            linear_x=0.0,
            angular_z=0.0,
            target_speed_scale=0.0,
            rationale="Push-readiness setup command has no safe correction to apply.",
        )
    return PlaceControlCommand(
        mode=mode,
        linear_x=round(float(linear), 6),
        angular_z=round(float(angular), 6),
        target_speed_scale=0.0 if abs(linear) <= 1.0e-6 else 0.35,
        rationale="Correct measured standoff, lateral error, and yaw before Nav2 corridor push dispatch.",
    )


def _nav2_status(nav2_corridor_push: dict[str, Any] | None) -> dict[str, Any]:
    payload = nav2_corridor_push if isinstance(nav2_corridor_push, dict) else {}
    dispatch_status = str(payload.get("dispatch_status", "") or "")
    monitor = payload.get("monitor", {}) if isinstance(payload.get("monitor"), dict) else {}
    monitor_sample = (
        payload.get("monitor_sample", {})
        if isinstance(payload.get("monitor_sample"), dict)
        else monitor.get("last_sample", {}) if isinstance(monitor.get("last_sample"), dict) else {}
    )
    return {
        "dispatch_status": dispatch_status,
        "success": bool(payload.get("success", False)),
        "status_text": str(payload.get("status_text", "") or ""),
        "monitor_cancel_reason": str(payload.get("monitor_cancel_reason", "") or ""),
        "monitor_sample": dict(monitor_sample or {}),
        "first_contact_no_object_motion": bool(payload.get("first_contact_no_object_motion", False)),
        "first_contact_confirmed": bool(payload.get("first_contact_confirmed", False)),
    }


def classify_ai_push_coast_stage(
    *,
    approach_contact_metrics: dict[str, Any] | None = None,
    capture_geometry_gate: dict[str, Any] | None = None,
    shot_outcome: dict[str, Any] | None = None,
    relative_errors: dict[str, Any] | None = None,
    distance_to_fetch_pose_m: float | None = None,
    delivery_radius_m: float = 0.0,
    nav2_attempted: bool = False,
    terminal_correction_attempted: bool = False,
) -> dict[str, Any]:
    approach = approach_contact_metrics if isinstance(approach_contact_metrics, dict) else {}
    capture_gate = capture_geometry_gate if isinstance(capture_geometry_gate, dict) else {}
    shot = shot_outcome if isinstance(shot_outcome, dict) else {}
    flags = [str(flag) for flag in approach.get("flags", []) if str(flag)]
    for flag in capture_gate.get("flags", []):
        clean_flag = str(flag)
        if clean_flag and clean_flag not in flags:
            flags.append(clean_flag)
    if capture_gate and capture_gate.get("pass") is False and "capture_geometry_gate_failed" not in flags:
        flags.append("capture_geometry_gate_failed")
    labels: list[str] = []
    for flag in flags:
        stage = AI_PUSH_COAST_FLAG_STAGE_LABELS.get(flag)
        if stage and stage not in labels:
            labels.append(stage)
    errors = relative_errors if isinstance(relative_errors, dict) else {}
    lateral_error = _finite_float(errors.get("robot_lateral_error_m"))
    yaw_error_deg = _finite_float(errors.get("robot_yaw_error_deg"))
    if lateral_error is not None and lateral_error > AI_PUSH_COAST_MAX_LATERAL_ERROR_M:
        if "setup" not in labels:
            labels.append("setup")
    if yaw_error_deg is not None and abs(float(yaw_error_deg)) > AI_PUSH_COAST_MAX_SETUP_YAW_ERROR_DEG:
        if "setup" not in labels:
            labels.append("setup")
    reason = str(shot.get("reason", "") or "")
    if (
        "first_contact_no_object_motion" in reason
        or "missing_first_contact_motion" in reason
        or "no_object_motion" in reason
    ):
        if "first_contact" not in labels:
            labels.append("first_contact")
    if "capture_entry_timeout" in reason:
        if "setup" not in labels:
            labels.append("setup")
    distance = _finite_float(distance_to_fetch_pose_m)
    radius = max(float(delivery_radius_m), 0.0)
    if (
        "missed_delivery_radius" in reason
        or "stopped_short" in reason
        or (bool(nav2_attempted) and distance is not None and distance > radius)
    ):
        if "terminal_arrival" not in labels:
            labels.append("terminal_arrival")
    if bool(terminal_correction_attempted) and "terminal_correction" not in labels:
        labels.append("terminal_correction")
    capture_gate_pass = True
    if capture_gate:
        capture_gate_pass = bool(capture_gate.get("pass", False))
    stable_contact_pass = bool(approach.get("stable_contact_approach_pass", False)) and capture_gate_pass
    if not labels and stable_contact_pass:
        labels.append("clean_contact")
    primary = labels[0] if labels else "unknown"
    return {
        "primary_stage": primary,
        "stage_labels": labels,
        "contact_quality_flags": flags,
        "stable_contact_approach_pass": stable_contact_pass,
        "capture_geometry_gate": dict(capture_gate),
        "shot_reason": reason,
    }


def decide_ai_push_coast_handoff(
    *,
    robot_pose: dict[str, Any] | None,
    ball_pose: dict[str, Any] | None,
    fetch_pose_world: dict[str, Any],
    delivery_radius_m: float,
    nav2_corridor_push: dict[str, Any] | None = None,
    nav2_attempted: bool = False,
    terminal_correction_attempted: bool = False,
    distance_to_fetch_pose_m: float | None = None,
    closest_approach_distance_m: float | None = None,
    latest_still_s: float | None = None,
    terminal_settled_after_nav2: bool = False,
    ball_moved_since_fetch: bool = False,
    approach_contact_metrics: dict[str, Any] | None = None,
    capture_geometry_gate: dict[str, Any] | None = None,
    shot_outcome: dict[str, Any] | None = None,
    mode: str = AI_PUSH_COAST_MODE_SHADOW,
) -> dict[str, Any]:
    started = time.perf_counter()
    clean_mode = str(mode or AI_PUSH_COAST_MODE_SHADOW).strip().lower()
    if clean_mode not in ALLOWED_AI_PUSH_COAST_MODES:
        clean_mode = AI_PUSH_COAST_MODE_SHADOW
    distance = _finite_float(distance_to_fetch_pose_m)
    closest = _finite_float(closest_approach_distance_m)
    radius = max(float(delivery_radius_m), 0.0)
    errors = _relative_errors(robot_pose, ball_pose, fetch_pose_world)
    nav2 = _nav2_status(nav2_corridor_push)
    capture_gate = capture_geometry_gate if isinstance(capture_geometry_gate, dict) else {}
    stage_classification = classify_ai_push_coast_stage(
        approach_contact_metrics=approach_contact_metrics,
        capture_geometry_gate=capture_gate,
        shot_outcome=shot_outcome,
        relative_errors=errors,
        distance_to_fetch_pose_m=distance,
        delivery_radius_m=radius,
        nav2_attempted=nav2_attempted,
        terminal_correction_attempted=terminal_correction_attempted,
    )
    if bool(nav2.get("first_contact_no_object_motion", False)):
        labels = list(stage_classification.get("stage_labels", []) or [])
        if "first_contact" not in labels:
            labels.append("first_contact")
        stage_classification = {
            **stage_classification,
            "primary_stage": labels[0] if labels else "first_contact",
            "stage_labels": labels,
        }
    candidate_maneuvers = [
        "stay_with_nav2",
        "coast_accept",
        "continue_push",
        "terminal_repush",
        "recenter_left",
        "recenter_right",
        "abort_reaim",
    ]
    terminal_settled = bool(terminal_settled_after_nav2) or (
        latest_still_s is not None and float(latest_still_s) > 0.0
    )

    if distance is None or not robot_pose or not ball_pose:
        maneuver_class = "abort_reaim"
        abstain_reason = "missing_measured_state"
    elif distance <= radius:
        maneuver_class = "coast_accept"
        abstain_reason = ""
    elif not bool(nav2_attempted):
        maneuver_class = "stay_with_nav2"
        abstain_reason = ""
    elif bool(terminal_correction_attempted):
        maneuver_class = "abort_reaim"
        abstain_reason = "terminal_correction_budget_exhausted"
    elif float(errors.get("robot_lateral_error_m", 0.0) or 0.0) > AI_PUSH_COAST_MAX_LATERAL_ERROR_M:
        lateral_signed = float(errors.get("robot_lateral_signed_m", 0.0) or 0.0)
        maneuver_class = "recenter_left" if lateral_signed < 0.0 else "recenter_right"
        abstain_reason = ""
    elif bool(ball_moved_since_fetch) or terminal_settled:
        maneuver_class = "terminal_repush"
        abstain_reason = ""
    else:
        maneuver_class = "continue_push"
        abstain_reason = ""

    predicted_closest = None
    if distance is not None:
        if maneuver_class in {"terminal_repush", "continue_push", "recenter_left", "recenter_right"}:
            predicted_closest = max(0.0, float(distance) - AI_PUSH_COAST_PREDICTED_TERMINAL_GAIN_M)
        else:
            predicted_closest = float(distance)
    miss_vector = {}
    basis = _target_basis(ball_pose, fetch_pose_world)
    if basis is not None and distance is not None:
        push_ux, push_uy, normal_x, normal_y, _push_yaw, _ball_target_distance_m = basis
        ball_xyyaw = world_pose_xyyaw(ball_pose or {})
        fetch_xyyaw = world_pose_xyyaw(fetch_pose_world or {})
        if ball_xyyaw is not None and fetch_xyyaw is not None:
            dx = float(ball_xyyaw[0]) - float(fetch_xyyaw[0])
            dy = float(ball_xyyaw[1]) - float(fetch_xyyaw[1])
            miss_vector = {
                "longitudinal_m": round((dx * push_ux) + (dy * push_uy), 6),
                "lateral_m": round((dx * normal_x) + (dy * normal_y), 6),
            }

    guard_reasons: list[str] = []
    if clean_mode != AI_PUSH_COAST_MODE_GUARDED_LIVE:
        guard_reasons.append("shadow_mode")
    stage_labels = list(stage_classification.get("stage_labels", []) or [])
    setup_quality_flags = {
        str(flag)
        for flag in stage_classification.get("contact_quality_flags", []) or []
        if AI_PUSH_COAST_FLAG_STAGE_LABELS.get(str(flag)) == "setup"
    }
    capture_warning_flags = {
        "capture_geometry_gate_failed",
        "capture_yaw_watch",
        "capture_yaw_sign_crossing_watch",
    }
    robot_lateral_error_m = float(errors.get("robot_lateral_error_m", 0.0) or 0.0)
    robot_yaw_error_deg = abs(float(errors.get("robot_yaw_error_deg", 0.0) or 0.0))
    current_setup_geometry_bad = (
        robot_lateral_error_m > AI_PUSH_COAST_MAX_LATERAL_ERROR_M
        or robot_yaw_error_deg > AI_PUSH_COAST_MAX_SETUP_YAW_ERROR_DEG
    )
    terminal_contact_confirmed = bool(
        bool(nav2_attempted)
        and bool(ball_moved_since_fetch)
        and not bool(nav2.get("first_contact_no_object_motion", False))
        and ("terminal_arrival" in stage_labels or terminal_settled)
    )
    capture_warning_only = bool(
        capture_gate
        and capture_gate.get("pass") is False
        and terminal_contact_confirmed
        and not current_setup_geometry_bad
        and setup_quality_flags
        and setup_quality_flags.issubset(capture_warning_flags)
    )
    if capture_gate and capture_gate.get("pass") is False and not capture_warning_only:
        guard_reasons.append("capture_geometry_gate_failed")
    if maneuver_class != "terminal_repush":
        guard_reasons.append(f"maneuver_{maneuver_class}_not_terminal_live")
    if terminal_correction_attempted:
        guard_reasons.append("terminal_correction_budget_exhausted")
    if not bool(nav2_attempted):
        guard_reasons.append("nav2_not_attempted")
    if not bool(ball_moved_since_fetch):
        guard_reasons.append("object_motion_not_observed")
    if not terminal_settled:
        guard_reasons.append("ball_not_settled_for_terminal_correction")
    if "terminal_arrival" not in stage_labels:
        guard_reasons.append("not_terminal_arrival_stage")
    for blocked_stage in ("setup", "first_contact", "push_coast"):
        if blocked_stage == "setup" and capture_warning_only:
            continue
        if blocked_stage in stage_labels:
            guard_reasons.append(f"stage_{blocked_stage}_not_live")
    if distance is None:
        guard_reasons.append("missing_distance_to_fetch_pose")
    elif distance > radius + AI_PUSH_COAST_MAX_TERMINAL_MISS_M:
        guard_reasons.append("terminal_miss_too_large")
    if predicted_closest is None or predicted_closest > radius + AI_PUSH_COAST_PREDICTED_TERMINAL_TOLERANCE_M:
        guard_reasons.append("predicted_terminal_correction_not_sufficient")
    if robot_lateral_error_m > AI_PUSH_COAST_MAX_LATERAL_ERROR_M:
        guard_reasons.append("robot_lateral_error_too_large")
    if robot_yaw_error_deg > AI_PUSH_COAST_MAX_SETUP_YAW_ERROR_DEG:
        guard_reasons.append("robot_yaw_error_too_large")
    if nav2.get("monitor_cancel_reason") in {"ball_escape", "unsafe_drift", "stale_state"}:
        guard_reasons.append(f"nav2_monitor_{nav2.get('monitor_cancel_reason')}")

    accepted = not guard_reasons
    latency_ms = (time.perf_counter() - started) * 1000.0
    trajectory_summary = {
        "predicted_closest_approach_m": round(float(predicted_closest), 6) if predicted_closest is not None else None,
        "current_distance_to_fetch_pose_m": round(float(distance), 6) if distance is not None else None,
        "current_closest_approach_m": round(float(closest), 6) if closest is not None else None,
        "delivery_radius_m": round(float(radius), 6),
        "predicted_success": bool(predicted_closest is not None and predicted_closest <= radius),
    }
    proposal = {
        "family": AI_PUSH_COAST_SERVO_CONTROL_FAMILY,
        "mode": clean_mode,
        "stage_owner": "nav2_followpath_corridor_push" if not nav2_attempted else "hybrid_terminal_contact",
        "maneuver_class": maneuver_class,
        "candidate_maneuvers": candidate_maneuvers,
        "terminal_correction_attempted": bool(terminal_correction_attempted),
        "abstain_reason": abstain_reason,
        "miss_vector_m": miss_vector,
        "relative_errors": errors,
        "nav2_status": nav2,
        "capture_geometry_gate": dict(capture_gate),
        "stage_classification": stage_classification,
    }
    guard = {
        "accepted": bool(accepted),
        "reasons": guard_reasons,
        "deterministic_routine": "object_centric_fetch_to_pose" if accepted else "",
        "max_terminal_miss_m": round(float(AI_PUSH_COAST_MAX_TERMINAL_MISS_M), 6),
        "max_lateral_error_m": round(float(AI_PUSH_COAST_MAX_LATERAL_ERROR_M), 6),
        "predicted_terminal_tolerance_m": round(float(AI_PUSH_COAST_PREDICTED_TERMINAL_TOLERANCE_M), 6),
        "terminal_live_only": True,
    }
    shadow = {
        "model_id": "heuristic_hybrid_stage_supervisor_v0",
        "model_role": "shadow_handoff_maneuver_proposer",
        "input_digest": {
            "nav2_attempted": bool(nav2_attempted),
            "terminal_correction_attempted": bool(terminal_correction_attempted),
            "ball_moved_since_fetch": bool(ball_moved_since_fetch),
            "latest_still_s": round(float(latest_still_s), 6) if latest_still_s is not None else None,
            "terminal_settled_after_nav2": bool(terminal_settled_after_nav2),
            "stage_labels": list(stage_classification.get("stage_labels", []) or []),
            "primary_stage": stage_classification.get("primary_stage", "unknown"),
            "capture_geometry_gate_pass": (
                bool(capture_gate.get("pass", False)) if capture_gate else None
            ),
            "capture_geometry_flags": list(capture_gate.get("flags", [])) if capture_gate else [],
            **trajectory_summary,
        },
        "trajectory": trajectory_summary,
        "stage_classification": stage_classification,
        "latency_ms": round(float(latency_ms), 6),
    }
    return {
        "ai_push_coast_shadow": shadow,
        "ai_push_coast_proposal": proposal,
        "ai_push_coast_guard": guard,
        "ai_push_coast_latency_ms": round(float(latency_ms), 6),
    }
