#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Python 3.6-compatible deterministic fetch route policy for onboard use."""

from __future__ import print_function

import math


ROUTE_FETCH_READY = "fetch_ready_local"
ROUTE_NAV2_REPOSITION = "nav2_reposition_first"
ROUTE_SCAN_OR_PERCEIVE = "scan_or_perceive_first"
ROUTE_RECOVERY_OR_REAIM = "recovery_or_reaim"
ROUTE_LOCAL_SETUP_CAPTURE = "local_setup_capture"
ROUTE_NO_GO = "ambiguous_or_unsafe_no_go"
ROUTE_LABELS = (
    ROUTE_FETCH_READY,
    ROUTE_NAV2_REPOSITION,
    ROUTE_SCAN_OR_PERCEIVE,
    ROUTE_RECOVERY_OR_REAIM,
    ROUTE_LOCAL_SETUP_CAPTURE,
    ROUTE_NO_GO,
)

ROUTE_EXECUTOR_LOCAL_FETCH = "local_fetch_to_pose"
ROUTE_EXECUTOR_NAV2_REPOSITION_FETCH = "nav2_forward_reposition_then_fetch"
ROUTE_EXECUTOR_SCAN = "scan_or_perception_refresh"
ROUTE_EXECUTOR_RECOVERY = "bounded_recovery_reaim"
ROUTE_EXECUTOR_LOCAL_SETUP_CAPTURE = "measured_local_setup_capture"
ROUTE_EXECUTOR_NO_GO = "safe_no_go"
ROUTE_EXECUTORS = {
    ROUTE_FETCH_READY: ROUTE_EXECUTOR_LOCAL_FETCH,
    ROUTE_NAV2_REPOSITION: ROUTE_EXECUTOR_NAV2_REPOSITION_FETCH,
    ROUTE_SCAN_OR_PERCEIVE: ROUTE_EXECUTOR_SCAN,
    ROUTE_RECOVERY_OR_REAIM: ROUTE_EXECUTOR_RECOVERY,
    ROUTE_LOCAL_SETUP_CAPTURE: ROUTE_EXECUTOR_LOCAL_SETUP_CAPTURE,
    ROUTE_NO_GO: ROUTE_EXECUTOR_NO_GO,
}

MANEUVER_SCAN = "scan_perceive"
MANEUVER_NO_GO = "safe_no_go"
MANEUVER_NAV2_REPOSITION = "nav2_reposition"
MANEUVER_WRAPAROUND_SETUP = "wraparound_setup"
MANEUVER_RECOVERY_REAIM = "recovery_reaim"
MANEUVER_LOCAL_SETUP_CAPTURE = "local_setup_capture"
MANEUVER_VALIDATE_PUSH_READY = "validate_push_ready"
MANEUVER_LOCAL_FETCH = "local_fetch_to_pose"
MANEUVER_MONITOR_DELIVERY = "monitor_delivery"
MANEUVER_LABELS = (
    MANEUVER_SCAN,
    MANEUVER_NO_GO,
    MANEUVER_NAV2_REPOSITION,
    MANEUVER_WRAPAROUND_SETUP,
    MANEUVER_RECOVERY_REAIM,
    MANEUVER_LOCAL_SETUP_CAPTURE,
    MANEUVER_VALIDATE_PUSH_READY,
    MANEUVER_LOCAL_FETCH,
    MANEUVER_MONITOR_DELIVERY,
)

FETCH_READY_LATERAL_LIMIT_M = 0.050
FETCH_READY_YAW_LIMIT_DEG = 6.0
RECOVERY_LATERAL_LIMIT_M = 0.240
RECOVERY_YAW_LIMIT_DEG = 35.0
RECOVERY_ROBOT_BALL_DISTANCE_LIMIT_M = 0.900
EXTENDED_RECOVERY_LATERAL_LIMIT_M = 0.360
EXTENDED_RECOVERY_YAW_LIMIT_DEG = 85.0
EXTENDED_RECOVERY_ROBOT_BALL_DISTANCE_LIMIT_M = 0.950
LOCAL_SETUP_CAPTURE_ROBOT_BALL_DISTANCE_LIMIT_M = 2.600
LOCAL_SETUP_CAPTURE_LATERAL_LIMIT_M = 2.200
LOCAL_SETUP_CAPTURE_YAW_LIMIT_DEG = 180.0
NAV2_REPOSITION_MIN_ROBOT_BALL_DISTANCE_M = RECOVERY_ROBOT_BALL_DISTANCE_LIMIT_M
NAV2_REPOSITION_STANDOFF_LIMIT_M = 1.350


def _finite_float(value, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(number):
        return float(default)
    return number


def _recovery_admissible_from_geometry(geometry):
    ball_target_distance_m = _finite_float(geometry.get("ball_target_distance_m"), 999.0)
    robot_ball_distance_m = _finite_float(geometry.get("robot_ball_distance_m"), 999.0)
    lateral_error_m = _finite_float(geometry.get("robot_lateral_error_m"), 999.0)
    yaw_error_deg = abs(_finite_float(geometry.get("robot_yaw_error_deg"), 999.0))
    return bool(
        0.34 <= ball_target_distance_m <= 0.85
        and 0.24 <= robot_ball_distance_m <= RECOVERY_ROBOT_BALL_DISTANCE_LIMIT_M
        and lateral_error_m <= RECOVERY_LATERAL_LIMIT_M
        and yaw_error_deg <= RECOVERY_YAW_LIMIT_DEG
    )


def _extended_recovery_admissible_from_geometry(geometry):
    ball_target_distance_m = _finite_float(geometry.get("ball_target_distance_m"), 999.0)
    robot_ball_distance_m = _finite_float(geometry.get("robot_ball_distance_m"), 999.0)
    lateral_error_m = _finite_float(geometry.get("robot_lateral_error_m"), 999.0)
    yaw_error_deg = abs(_finite_float(geometry.get("robot_yaw_error_deg"), 999.0))
    return bool(
        0.34 <= ball_target_distance_m <= 0.85
        and 0.24 <= robot_ball_distance_m <= EXTENDED_RECOVERY_ROBOT_BALL_DISTANCE_LIMIT_M
        and lateral_error_m <= EXTENDED_RECOVERY_LATERAL_LIMIT_M
        and yaw_error_deg <= EXTENDED_RECOVERY_YAW_LIMIT_DEG
    )


def _local_setup_capture_admissible_from_geometry(geometry):
    ball_target_distance_m = _finite_float(geometry.get("ball_target_distance_m"), 999.0)
    robot_ball_distance_m = _finite_float(geometry.get("robot_ball_distance_m"), 999.0)
    lateral_error_m = _finite_float(geometry.get("robot_lateral_error_m"), 999.0)
    yaw_error_deg = abs(_finite_float(geometry.get("robot_yaw_error_deg"), 999.0))
    return bool(
        0.34 <= ball_target_distance_m <= 0.85
        and 0.24 <= robot_ball_distance_m <= LOCAL_SETUP_CAPTURE_ROBOT_BALL_DISTANCE_LIMIT_M
        and lateral_error_m <= LOCAL_SETUP_CAPTURE_LATERAL_LIMIT_M
        and yaw_error_deg <= LOCAL_SETUP_CAPTURE_YAW_LIMIT_DEG
    )


def _geometry_needs_ball_relative_setup_owner(geometry):
    robot_ball_relative_bearing_abs_deg = _finite_float(geometry.get("robot_ball_relative_bearing_abs_deg"), 0.0)
    opposite_side = bool(geometry.get("opposite_side_of_circle", False))
    lateral_error_m = _finite_float(geometry.get("robot_lateral_error_m"), 999.0)
    yaw_error_deg = abs(_finite_float(geometry.get("robot_yaw_error_deg"), 999.0))
    robot_ball_distance_m = _finite_float(geometry.get("robot_ball_distance_m"), 999.0)
    return bool(
        opposite_side
        or robot_ball_relative_bearing_abs_deg >= 90.0
        or lateral_error_m > RECOVERY_LATERAL_LIMIT_M
        or yaw_error_deg > RECOVERY_YAW_LIMIT_DEG
        or robot_ball_distance_m > NAV2_REPOSITION_STANDOFF_LIMIT_M
    )


def deterministic_route_label(scene):
    perception = scene.get("perception") if isinstance(scene.get("perception"), dict) else {}
    corridor = scene.get("corridor") if isinstance(scene.get("corridor"), dict) else {}
    geometry = scene.get("geometry") if isinstance(scene.get("geometry"), dict) else {}
    ball_conf = _finite_float(perception.get("ball_confidence"), 0.0)
    target_conf = _finite_float(perception.get("target_confidence"), 0.0)
    state_age_s = _finite_float(perception.get("state_age_s"), 999.0)
    blocked = bool(corridor.get("blocked", False))
    clearance_m = _finite_float(corridor.get("clearance_m"), 0.0)
    unsafe_drift_m = _finite_float(corridor.get("unsafe_drift_m"), 0.0)
    ball_target_distance_m = _finite_float(geometry.get("ball_target_distance_m"), 999.0)
    robot_ball_distance_m = _finite_float(geometry.get("robot_ball_distance_m"), 999.0)
    lateral_error_m = _finite_float(geometry.get("robot_lateral_error_m"), 999.0)
    yaw_error_deg = abs(_finite_float(geometry.get("robot_yaw_error_deg"), 999.0))
    needs_local_setup_capture = bool(_geometry_needs_ball_relative_setup_owner(geometry))

    if ball_conf < 0.65 or target_conf < 0.65 or state_age_s > 2.0:
        return ROUTE_SCAN_OR_PERCEIVE
    if blocked or clearance_m < 0.12 or unsafe_drift_m > 0.16 or ball_target_distance_m > 1.20:
        return ROUTE_NO_GO
    if not (0.34 <= ball_target_distance_m <= 0.85):
        return ROUTE_NO_GO
    if (
        0.24 <= robot_ball_distance_m <= 0.52
        and lateral_error_m <= FETCH_READY_LATERAL_LIMIT_M
        and yaw_error_deg <= FETCH_READY_YAW_LIMIT_DEG
    ):
        return ROUTE_FETCH_READY
    if (
        robot_ball_distance_m <= RECOVERY_ROBOT_BALL_DISTANCE_LIMIT_M
        and lateral_error_m <= RECOVERY_LATERAL_LIMIT_M
        and yaw_error_deg <= RECOVERY_YAW_LIMIT_DEG
    ):
        return ROUTE_RECOVERY_OR_REAIM
    if _extended_recovery_admissible_from_geometry(geometry):
        return ROUTE_RECOVERY_OR_REAIM
    if needs_local_setup_capture and _local_setup_capture_admissible_from_geometry(geometry):
        return ROUTE_LOCAL_SETUP_CAPTURE
    return ROUTE_NAV2_REPOSITION


def executor_for_route(route_label):
    return str(ROUTE_EXECUTORS.get(str(route_label or "").strip(), "unsupported_route"))


def default_maneuver_sequence_for_route(scene, route_label):
    route = str(route_label or "").strip()
    geometry = scene.get("geometry") if isinstance(scene.get("geometry"), dict) else {}
    opposite = bool(geometry.get("opposite_side_of_circle", False))
    behind = _finite_float(geometry.get("robot_ball_relative_bearing_abs_deg"), 0.0) >= 90.0
    if route == ROUTE_SCAN_OR_PERCEIVE:
        return [MANEUVER_SCAN]
    if route == ROUTE_NO_GO:
        return [MANEUVER_NO_GO]
    if route == ROUTE_FETCH_READY:
        return [MANEUVER_VALIDATE_PUSH_READY, MANEUVER_LOCAL_FETCH, MANEUVER_MONITOR_DELIVERY]
    if route == ROUTE_RECOVERY_OR_REAIM:
        return [
            MANEUVER_RECOVERY_REAIM,
            MANEUVER_VALIDATE_PUSH_READY,
            MANEUVER_LOCAL_FETCH,
            MANEUVER_MONITOR_DELIVERY,
        ]
    if route == ROUTE_LOCAL_SETUP_CAPTURE:
        sequence = [MANEUVER_LOCAL_SETUP_CAPTURE]
        if opposite or behind:
            sequence.append(MANEUVER_WRAPAROUND_SETUP)
        sequence.extend([MANEUVER_VALIDATE_PUSH_READY, MANEUVER_LOCAL_FETCH, MANEUVER_MONITOR_DELIVERY])
        return sequence
    if route == ROUTE_NAV2_REPOSITION:
        sequence = [MANEUVER_NAV2_REPOSITION]
        if opposite or behind:
            sequence.append(MANEUVER_WRAPAROUND_SETUP)
        sequence.extend([MANEUVER_VALIDATE_PUSH_READY, MANEUVER_LOCAL_FETCH, MANEUVER_MONITOR_DELIVERY])
        return sequence
    return [MANEUVER_NO_GO]


def compile_maneuver_plan(scene, route_label, proposed=None):
    route = str(route_label or "").strip()
    proposed = proposed if isinstance(proposed, dict) else {}
    raw_sequence = proposed.get("maneuver_sequence") if isinstance(proposed.get("maneuver_sequence"), list) else []
    sequence = [str(item).strip() for item in raw_sequence if str(item or "").strip() in MANEUVER_LABELS]
    source = "llm_proposed"
    if not sequence:
        sequence = default_maneuver_sequence_for_route(scene, route)
        source = "deterministic_compiled"

    executable_fetch_route = route in {
        ROUTE_FETCH_READY,
        ROUTE_NAV2_REPOSITION,
        ROUTE_RECOVERY_OR_REAIM,
        ROUTE_LOCAL_SETUP_CAPTURE,
    }
    veto_reasons = []
    if executable_fetch_route:
        if MANEUVER_LOCAL_FETCH not in sequence:
            veto_reasons.append("missing_local_fetch_maneuver")
        if MANEUVER_VALIDATE_PUSH_READY not in sequence:
            veto_reasons.append("missing_validate_push_ready_before_fetch")
        elif MANEUVER_LOCAL_FETCH in sequence and sequence.index(MANEUVER_VALIDATE_PUSH_READY) > sequence.index(
            MANEUVER_LOCAL_FETCH
        ):
            veto_reasons.append("validate_push_ready_after_fetch")
    else:
        if MANEUVER_LOCAL_FETCH in sequence:
            veto_reasons.append("planner_only_route_attempted_local_fetch")

    lower_sequence = {item.lower() for item in sequence}
    for blocked in ("cmd_vel", "direct_ball_impulse", "shoot_ball"):
        if blocked in lower_sequence:
            veto_reasons.append("forbidden_maneuver_%s" % blocked)

    if veto_reasons:
        sequence = default_maneuver_sequence_for_route(scene, route)
        source = "deterministic_compiled_after_veto"

    geometry = scene.get("geometry") if isinstance(scene.get("geometry"), dict) else {}
    inserted_maneuvers = []
    requires_wraparound_setup = bool(
        route in {ROUTE_LOCAL_SETUP_CAPTURE, ROUTE_NAV2_REPOSITION}
        and (
            bool(geometry.get("opposite_side_of_circle", False))
            or _finite_float(geometry.get("robot_ball_relative_bearing_abs_deg"), 0.0) >= 90.0
        )
    )
    if requires_wraparound_setup and MANEUVER_WRAPAROUND_SETUP not in sequence:
        if route == ROUTE_LOCAL_SETUP_CAPTURE and MANEUVER_LOCAL_SETUP_CAPTURE in sequence:
            insert_at = sequence.index(MANEUVER_LOCAL_SETUP_CAPTURE) + 1
        elif route == ROUTE_NAV2_REPOSITION and MANEUVER_NAV2_REPOSITION in sequence:
            insert_at = sequence.index(MANEUVER_NAV2_REPOSITION) + 1
        elif MANEUVER_VALIDATE_PUSH_READY in sequence:
            insert_at = sequence.index(MANEUVER_VALIDATE_PUSH_READY)
        else:
            insert_at = 0
        sequence.insert(insert_at, MANEUVER_WRAPAROUND_SETUP)
        inserted_maneuvers.append(MANEUVER_WRAPAROUND_SETUP)
        if source == "llm_proposed":
            source = "llm_proposed_with_deterministic_required_maneuvers"

    validation_gates = proposed.get("validation_gates") if isinstance(proposed.get("validation_gates"), list) else []
    if not validation_gates and executable_fetch_route:
        validation_gates = [
            "state_not_stale",
            "ball_motion_within_setup_limit",
            "robot_ball_distance_within_push_ready_window",
            "lateral_error_within_push_ready_limit",
            "yaw_error_within_push_ready_limit",
        ]
    elif not validation_gates:
        validation_gates = ["planner_only_route_local_fetch_withheld"]

    replan_triggers = proposed.get("replan_triggers") if isinstance(proposed.get("replan_triggers"), list) else []
    if not replan_triggers:
        replan_triggers = [
            "stale_state",
            "ball_escape",
            "setup_timeout",
            "push_ready_validation_failed",
            "nav2_abort",
        ]

    return {
        "objective": str(proposed.get("objective", "") or "deliver_ball_to_target_circle"),
        "route_label": route,
        "route_executor": executor_for_route(route),
        "source": source,
        "maneuver_sequence": sequence,
        "validation_gates": [str(item) for item in validation_gates],
        "replan_triggers": [str(item) for item in replan_triggers],
        "requires_measured_push_ready_before_fetch": bool(executable_fetch_route),
        "local_fetch_index": sequence.index(MANEUVER_LOCAL_FETCH) if MANEUVER_LOCAL_FETCH in sequence else None,
        "push_ready_index": sequence.index(MANEUVER_VALIDATE_PUSH_READY)
        if MANEUVER_VALIDATE_PUSH_READY in sequence
        else None,
        "opposite_side_of_circle": bool(geometry.get("opposite_side_of_circle", False)),
        "robot_ball_relative_bearing_abs_deg": round(
            _finite_float(geometry.get("robot_ball_relative_bearing_abs_deg"), 0.0),
            6,
        ),
        "inserted_maneuvers": inserted_maneuvers,
        "veto_reasons": veto_reasons,
        "valid": not bool(veto_reasons),
        "no_direct_cmd_vel": True,
        "no_direct_ball_impulse": True,
    }
