#!/usr/bin/env python3
"""Single-pass pre-stage reacquire FSM for gather experiments."""

from __future__ import annotations

import math
from dataclasses import asdict
from dataclasses import dataclass
from typing import Any

from gather_mission_helpers import PlaceControlCommand
from gather_mission_helpers import ZoneSpec
from gather_mission_helpers import clamp
from gather_mission_helpers import normalize_angle
from gather_mission_helpers import point_xy
from gather_mission_helpers import pre_stage_arrival_snapshot
from gather_mission_helpers import relative_point_robot_frame
from gather_mission_helpers import world_pose_xyyaw


PRE_STAGE_REACQUIRE_FSM_CONTROL_FAMILY = "pre_stage_reacquire_fsm_v1"
PRE_STAGE_REACQUIRE_FSM_OBJECTIVE = "pre_stage_reacquire_fsm"

PHASE_GOAL_SIDE_ESCAPE = "goal_side_escape"
PHASE_DOCK_ENTRY = "dock_entry"
PHASE_DOCK_PORT = "dock_port"
PHASE_YAW_ALIGN = "yaw_align"
PHASE_BASELINE_RELEASE = "baseline_release"

DEFAULT_FSM_ENTRY_LATERAL_M = 0.85
DEFAULT_FSM_ENTRY_WIDE_LATERAL_M = 1.15
DEFAULT_FSM_ENTRY_BEHIND_BIAS_M = 0.20
DEFAULT_FSM_MIN_BALL_CLEARANCE_M = 0.42
DEFAULT_FSM_BALL_MOTION_TOLERANCE_M = 0.035
DEFAULT_FSM_GOAL_SIDE_ESCAPE_RELEASE_PROJECTION_M = -0.10
DEFAULT_FSM_BASELINE_SAFE_PROJECTION_M = -0.35
DEFAULT_FSM_BASELINE_SAFE_LATERAL_M = 0.30
DEFAULT_FSM_BASELINE_SAFE_DISTANCE_M = 0.75
DEFAULT_FSM_DOCK_ENTRY_DISTANCE_M = 1.05
DEFAULT_FSM_DOCK_ENTRY_LATERAL_M = 0.58
DEFAULT_FSM_DOCK_PORT_DISTANCE_M = 0.35
DEFAULT_FSM_DOCK_PORT_LATERAL_M = 0.22
DEFAULT_FSM_DOCK_PORT_PROJECTION_M = -0.50
DEFAULT_FSM_YAW_ALIGN_DONE_DEG = 20.0
DEFAULT_FSM_BASELINE_SAFE_YAW_DEG = DEFAULT_FSM_YAW_ALIGN_DONE_DEG
DEFAULT_FSM_MAX_LINEAR_X = 0.14
DEFAULT_FSM_MAX_ANGULAR_Z = 0.55
DEFAULT_FSM_YAW_MAX_ANGULAR_Z = 0.45
DEFAULT_FSM_HORIZON_S = 1.20
DEFAULT_FSM_STEP_S = 0.20

REJECTION_PREDICTED_BALL_CONTACT = "predicted_ball_contact"
REJECTION_DEEPER_GOAL_SIDE_PERSISTENCE = "deeper_goal_side_persistence"
REJECTION_WORSE_HANDOFF_READINESS = "worse_handoff_readiness"


@dataclass(frozen=True)
class PreStageReacquireFsmDecision:
    active: bool
    phase: str = ""
    strategy_name: str = ""
    objective_name: str = ""
    progress_score: float | None = None
    command: PlaceControlCommand | None = None
    release_reason: str = ""
    release_blockers: tuple[str, ...] = ()
    measured_snapshot: dict[str, Any] | None = None
    projected_snapshot: dict[str, Any] | None = None
    measured_handoff_ready: bool | None = None
    projected_handoff_ready: bool | None = None
    projection_m: float | None = None
    lateral_error_m: float | None = None
    distance_m: float | None = None
    yaw_error_deg: float | None = None
    projected_projection_gain: float | None = None
    projected_lateral_gain: float | None = None
    projected_distance_gain: float | None = None
    projected_yaw_gain_deg: float | None = None
    ball_motion_m: float | None = None
    min_ball_clearance_m: float | None = None
    target_pose: dict[str, float] | None = None
    target_distance_m: float | None = None
    target_heading_error_rad: float | None = None
    candidate_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    rejection_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.command is not None:
            payload["command"] = self.command.to_dict()
        payload["release_blockers"] = list(self.release_blockers)
        payload["rejection_reasons"] = list(self.rejection_reasons)
        return payload


def _finite_number(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _valid_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(snapshot, dict):
        return None
    for key in (
        "pre_stage_pose_distance_m",
        "robot_longitudinal_projection_m",
        "robot_lateral_error_m",
        "robot_lateral_signed_m",
        "yaw_error_deg",
    ):
        if _finite_number(snapshot.get(key)) is None:
            return None
    return snapshot


def _push_basis(ball_pose: dict[str, Any], zone: ZoneSpec) -> tuple[float, float, float, float, float] | None:
    ball_xy = point_xy(ball_pose)
    if ball_xy is None:
        return None
    push_dx = float(zone.world_x) - ball_xy[0]
    push_dy = float(zone.world_y) - ball_xy[1]
    push_norm = math.hypot(push_dx, push_dy)
    if push_norm <= 1.0e-6:
        return None
    push_ux = push_dx / push_norm
    push_uy = push_dy / push_norm
    return push_ux, push_uy, -push_uy, push_ux, math.atan2(push_uy, push_ux)


def _segment_ball_clearance(
    robot_pose: dict[str, Any],
    target_pose: dict[str, Any],
    ball_pose: dict[str, Any],
) -> float | None:
    robot_xyyaw = world_pose_xyyaw(robot_pose)
    target_xy = point_xy(target_pose)
    ball_xy = point_xy(ball_pose)
    if robot_xyyaw is None or target_xy is None or ball_xy is None:
        return None
    ax, ay, _yaw = robot_xyyaw
    bx, by = target_xy
    px, py = ball_xy
    dx = bx - ax
    dy = by - ay
    denom = (dx * dx) + (dy * dy)
    if denom <= 1.0e-9:
        return round(math.hypot(px - ax, py - ay), 6)
    t = clamp(((px - ax) * dx + (py - ay) * dy) / denom, 0.0, 1.0)
    nearest_x = ax + (t * dx)
    nearest_y = ay + (t * dy)
    return round(math.hypot(px - nearest_x, py - nearest_y), 6)


def _rollout_samples(
    robot_pose: dict[str, Any],
    command: PlaceControlCommand,
    *,
    horizon_s: float = DEFAULT_FSM_HORIZON_S,
    step_s: float = DEFAULT_FSM_STEP_S,
) -> list[dict[str, float]]:
    robot_xyyaw = world_pose_xyyaw(robot_pose)
    if robot_xyyaw is None:
        return []
    x_m, y_m, yaw_rad = robot_xyyaw
    samples = [{"x": round(x_m, 6), "y": round(y_m, 6), "yaw": round(yaw_rad, 6)}]
    remaining_s = max(float(horizon_s), 0.0)
    while remaining_s > 1.0e-9:
        dt_s = min(float(step_s), remaining_s)
        x_m += float(command.linear_x) * math.cos(yaw_rad) * dt_s
        y_m += float(command.linear_x) * math.sin(yaw_rad) * dt_s
        yaw_rad = normalize_angle(yaw_rad + (float(command.angular_z) * dt_s))
        samples.append({"x": round(x_m, 6), "y": round(y_m, 6), "yaw": round(yaw_rad, 6)})
        remaining_s -= dt_s
    return samples


def _min_ball_clearance(samples: list[dict[str, float]], ball_pose: dict[str, Any]) -> float | None:
    ball_xy = point_xy(ball_pose)
    if ball_xy is None or not samples:
        return None
    ball_x, ball_y = ball_xy
    return round(
        min(math.hypot(float(sample["x"]) - ball_x, float(sample["y"]) - ball_y) for sample in samples),
        6,
    )


def _entry_target_pose(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    snapshot: dict[str, Any],
    previous_phase: str = "",
) -> tuple[dict[str, float], float | None, float | None]:
    basis = _push_basis(ball_pose, zone)
    pre_stage_pose = (
        dict(snapshot.get("pre_stage_pose_world", {}))
        if isinstance(snapshot.get("pre_stage_pose_world"), dict)
        else {}
    )
    if basis is None or point_xy(pre_stage_pose) is None:
        return {}, None, None
    push_ux, push_uy, normal_x, normal_y, _push_yaw = basis
    side_order = [1.0, -1.0]
    if str(previous_phase).endswith("_right"):
        side_order = [-1.0, 1.0]
    elif str(previous_phase).endswith("_left"):
        side_order = [1.0, -1.0]
    else:
        lateral_signed_m = float(snapshot.get("robot_lateral_signed_m", 0.0) or 0.0)
        if abs(lateral_signed_m) > 0.05:
            preferred = 1.0 if lateral_signed_m > 0.0 else -1.0
            side_order = [preferred, -preferred]

    robot_xyyaw = world_pose_xyyaw(robot_pose)
    best: tuple[float, float, dict[str, float], float, float | None] | None = None
    for lateral_m in (DEFAULT_FSM_ENTRY_LATERAL_M, DEFAULT_FSM_ENTRY_WIDE_LATERAL_M):
        for side in side_order:
            target_pose = {
                "x": round(
                    float(pre_stage_pose.get("x", 0.0) or 0.0)
                    + (side * lateral_m * normal_x)
                    - (DEFAULT_FSM_ENTRY_BEHIND_BIAS_M * push_ux),
                    6,
                ),
                "y": round(
                    float(pre_stage_pose.get("y", 0.0) or 0.0)
                    + (side * lateral_m * normal_y)
                    - (DEFAULT_FSM_ENTRY_BEHIND_BIAS_M * push_uy),
                    6,
                ),
            }
            clearance = _segment_ball_clearance(robot_pose, target_pose, ball_pose)
            heading_cost = 0.0
            if robot_xyyaw is not None:
                robot_x, robot_y, robot_yaw = robot_xyyaw
                heading_cost = abs(normalize_angle(math.atan2(target_pose["y"] - robot_y, target_pose["x"] - robot_x) - robot_yaw))
            score = float(clearance if clearance is not None else 0.0) - (0.05 * heading_cost) - (0.02 * lateral_m)
            if best is None or score > best[0]:
                best = (score, side, target_pose, lateral_m, clearance)
    if best is None:
        return {}, None, None
    _score, side, target_pose, _lateral_m, clearance = best
    return target_pose, side, clearance


def _command_toward_target(
    robot_pose: dict[str, Any],
    target_pose: dict[str, float],
    *,
    phase: str,
    push_yaw_rad: float,
) -> tuple[PlaceControlCommand, float | None, float | None]:
    target_rel = relative_point_robot_frame(robot_pose, target_pose)
    robot_xyyaw = world_pose_xyyaw(robot_pose)
    if target_rel is None or robot_xyyaw is None:
        return (
            PlaceControlCommand(
                mode="pre_stage_reacquire_fsm_hold",
                linear_x=0.0,
                angular_z=0.0,
                target_speed_scale=0.0,
                rationale="Pre-stage reacquire FSM is holding because target geometry is unavailable.",
            ),
            None,
            None,
        )
    target_x_m, target_y_m = target_rel
    _robot_x, _robot_y, robot_yaw = robot_xyyaw
    target_distance_m = math.hypot(target_x_m, target_y_m)
    target_bearing = math.atan2(target_y_m, target_x_m)
    heading_error = target_bearing if target_x_m < 0.0 else math.atan2(target_y_m, max(target_x_m, 1.0e-6))
    push_yaw_error = normalize_angle(push_yaw_rad - robot_yaw)
    if target_x_m < -0.05 or abs(heading_error) > 1.05:
        angular = clamp(heading_error * 1.35, -DEFAULT_FSM_MAX_ANGULAR_Z, DEFAULT_FSM_MAX_ANGULAR_Z)
        if abs(angular) < 0.18 and abs(heading_error) > 0.18:
            angular = 0.18 if heading_error >= 0.0 else -0.18
        return (
            PlaceControlCommand(
                mode="pre_stage_reacquire_fsm",
                linear_x=0.0,
                angular_z=round(angular, 6),
                target_speed_scale=0.0,
                rationale="Pre-stage reacquire FSM turns toward the next safe measured-state target.",
            ),
            target_distance_m,
            heading_error,
        )
    linear = clamp(target_distance_m * 0.18, 0.04, DEFAULT_FSM_MAX_LINEAR_X)
    if phase == PHASE_GOAL_SIDE_ESCAPE:
        linear = min(linear, 0.12)
    if abs(heading_error) > 0.45:
        linear = min(linear, 0.09)
    angular = clamp(
        (target_y_m * 0.90) + (heading_error * 0.40) + (push_yaw_error * 0.05),
        -DEFAULT_FSM_MAX_ANGULAR_Z,
        DEFAULT_FSM_MAX_ANGULAR_Z,
    )
    return (
        PlaceControlCommand(
            mode="pre_stage_reacquire_fsm",
            linear_x=round(linear, 6),
            angular_z=round(angular, 6),
            target_speed_scale=0.70,
            rationale="Pre-stage reacquire FSM drives toward the next safe behind-ball measured-state target.",
        ),
        target_distance_m,
        heading_error,
    )


def _yaw_align_command(
    robot_pose: dict[str, Any],
    *,
    push_yaw_rad: float,
) -> tuple[PlaceControlCommand, float | None]:
    robot_xyyaw = world_pose_xyyaw(robot_pose)
    if robot_xyyaw is None:
        return (
            PlaceControlCommand(
                mode="pre_stage_reacquire_fsm_hold",
                linear_x=0.0,
                angular_z=0.0,
                target_speed_scale=0.0,
                rationale="Pre-stage reacquire FSM is holding because yaw geometry is unavailable.",
            ),
            None,
        )
    _robot_x, _robot_y, robot_yaw = robot_xyyaw
    yaw_error_rad = normalize_angle(push_yaw_rad - robot_yaw)
    angular = clamp(yaw_error_rad * 0.85, -DEFAULT_FSM_YAW_MAX_ANGULAR_Z, DEFAULT_FSM_YAW_MAX_ANGULAR_Z)
    if abs(angular) < 0.18 and abs(yaw_error_rad) > math.radians(DEFAULT_FSM_YAW_ALIGN_DONE_DEG):
        angular = 0.18 if yaw_error_rad >= 0.0 else -0.18
    return (
        PlaceControlCommand(
            mode="pre_stage_reacquire_fsm_yaw_align",
            linear_x=0.0,
            angular_z=round(angular, 6),
            target_speed_scale=0.0,
            rationale="Pre-stage reacquire FSM rotates in place for the final push-line handoff yaw.",
        ),
        yaw_error_rad,
    )


def _handoff_score(snapshot: dict[str, Any]) -> float:
    projection_m = float(snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0)
    lateral_m = float(snapshot.get("robot_lateral_error_m", 0.0) or 0.0)
    distance_m = float(snapshot.get("pre_stage_pose_distance_m", 0.0) or 0.0)
    yaw_error_deg = float(snapshot.get("yaw_error_deg", 0.0) or 0.0)
    projection_penalty = max(0.0, projection_m - DEFAULT_FSM_BASELINE_SAFE_PROJECTION_M)
    return (projection_penalty * 2.0) + lateral_m + distance_m + (yaw_error_deg / 180.0)


def _project_command(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    command: PlaceControlCommand,
) -> tuple[dict[str, Any], float | None]:
    samples = _rollout_samples(robot_pose, command)
    min_clearance_m = _min_ball_clearance(samples, ball_pose)
    projected_pose = samples[-1] if samples else {}
    projected_snapshot = (
        pre_stage_arrival_snapshot(projected_pose, ball_pose, zone=zone)
        if projected_pose
        else None
    )
    return _valid_snapshot(projected_snapshot) or {}, min_clearance_m


def pre_stage_reacquire_fsm_release_blockers(
    snapshot: dict[str, Any] | None,
    *,
    ball_motion_m: float | None = None,
) -> tuple[str, ...]:
    current_snapshot = _valid_snapshot(snapshot)
    if current_snapshot is None:
        return ("missing_pre_stage_geometry",)
    if ball_motion_m is not None and float(ball_motion_m) > DEFAULT_FSM_BALL_MOTION_TOLERANCE_M:
        return ("ball_motion_guard",)
    if bool(current_snapshot.get("pre_stage_pose_reached", False)):
        return ()
    blockers: list[str] = []
    if bool(current_snapshot.get("robot_on_goal_side", False)):
        blockers.append("robot_on_goal_side")
    if float(current_snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0) > DEFAULT_FSM_BASELINE_SAFE_PROJECTION_M:
        blockers.append("projection_not_cleared")
    if float(current_snapshot.get("robot_lateral_error_m", 0.0) or 0.0) > DEFAULT_FSM_BASELINE_SAFE_LATERAL_M:
        blockers.append("lateral_not_converged")
    if float(current_snapshot.get("pre_stage_pose_distance_m", 0.0) or 0.0) > DEFAULT_FSM_BASELINE_SAFE_DISTANCE_M:
        blockers.append("distance_not_converged")
    if float(current_snapshot.get("yaw_error_deg", 0.0) or 0.0) > DEFAULT_FSM_BASELINE_SAFE_YAW_DEG:
        blockers.append("yaw_not_aligned")
    return tuple(blockers)


def pre_stage_reacquire_fsm_release_reason(
    snapshot: dict[str, Any] | None,
    *,
    ball_motion_m: float | None = None,
) -> str:
    current_snapshot = _valid_snapshot(snapshot)
    if current_snapshot is None:
        return "missing_pre_stage_geometry"
    if ball_motion_m is not None and float(ball_motion_m) > DEFAULT_FSM_BALL_MOTION_TOLERANCE_M:
        return "ball_motion_guard"
    if bool(current_snapshot.get("pre_stage_pose_reached", False)):
        return "pre_stage_handoff_ready"
    if pre_stage_reacquire_fsm_release_blockers(current_snapshot, ball_motion_m=ball_motion_m):
        return ""
    return "baseline_safe_release"


def pre_stage_reacquire_fsm_phase(
    snapshot: dict[str, Any] | None,
    *,
    ball_motion_m: float | None = None,
) -> str:
    current_snapshot = _valid_snapshot(snapshot)
    if current_snapshot is None or pre_stage_reacquire_fsm_release_reason(
        current_snapshot,
        ball_motion_m=ball_motion_m,
    ):
        return PHASE_BASELINE_RELEASE
    projection_m = float(current_snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0)
    lateral_m = float(current_snapshot.get("robot_lateral_error_m", 0.0) or 0.0)
    distance_m = float(current_snapshot.get("pre_stage_pose_distance_m", 0.0) or 0.0)
    yaw_error_deg = float(current_snapshot.get("yaw_error_deg", 0.0) or 0.0)
    if bool(current_snapshot.get("robot_on_goal_side", False)) or projection_m > DEFAULT_FSM_GOAL_SIDE_ESCAPE_RELEASE_PROJECTION_M:
        return PHASE_GOAL_SIDE_ESCAPE
    if (
        projection_m <= DEFAULT_FSM_BASELINE_SAFE_PROJECTION_M
        and lateral_m <= DEFAULT_FSM_BASELINE_SAFE_LATERAL_M
        and distance_m <= DEFAULT_FSM_BASELINE_SAFE_DISTANCE_M
        and yaw_error_deg > DEFAULT_FSM_YAW_ALIGN_DONE_DEG
    ):
        return PHASE_YAW_ALIGN
    if distance_m > DEFAULT_FSM_DOCK_ENTRY_DISTANCE_M or lateral_m > DEFAULT_FSM_DOCK_ENTRY_LATERAL_M:
        return PHASE_DOCK_ENTRY
    if (
        distance_m > DEFAULT_FSM_DOCK_PORT_DISTANCE_M
        or lateral_m > DEFAULT_FSM_DOCK_PORT_LATERAL_M
        or projection_m > DEFAULT_FSM_DOCK_PORT_PROJECTION_M
    ):
        return PHASE_DOCK_PORT
    if yaw_error_deg > DEFAULT_FSM_YAW_ALIGN_DONE_DEG:
        return PHASE_YAW_ALIGN
    return PHASE_BASELINE_RELEASE


def decide_pre_stage_reacquire_fsm_command(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    snapshot: dict[str, Any] | None = None,
    previous_phase: str = "",
    ball_motion_m: float | None = None,
) -> PreStageReacquireFsmDecision:
    current_snapshot = (
        _valid_snapshot(snapshot)
        if snapshot is not None
        else _valid_snapshot(pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone))
    )
    release_reason = pre_stage_reacquire_fsm_release_reason(current_snapshot, ball_motion_m=ball_motion_m)
    release_blockers = pre_stage_reacquire_fsm_release_blockers(current_snapshot, ball_motion_m=ball_motion_m)
    phase = pre_stage_reacquire_fsm_phase(current_snapshot, ball_motion_m=ball_motion_m)
    if current_snapshot is None or release_reason:
        return PreStageReacquireFsmDecision(
            active=False,
            phase=phase,
            release_reason=release_reason,
            release_blockers=release_blockers,
            measured_snapshot=current_snapshot,
            measured_handoff_ready=(
                bool(current_snapshot.get("pre_stage_pose_reached", False))
                if isinstance(current_snapshot, dict)
                else None
            ),
            ball_motion_m=ball_motion_m,
        )

    basis = _push_basis(ball_pose, zone)
    if basis is None:
        return PreStageReacquireFsmDecision(
            active=False,
            phase=PHASE_BASELINE_RELEASE,
            release_reason="missing_pre_stage_geometry",
            release_blockers=("missing_pre_stage_geometry",),
            measured_snapshot=current_snapshot,
            measured_handoff_ready=False,
            ball_motion_m=ball_motion_m,
        )
    _push_ux, _push_uy, _normal_x, _normal_y, push_yaw_rad = basis
    target_pose: dict[str, float] = {}
    side_sign: float | None = None
    segment_clearance_m: float | None = None
    yaw_error_rad: float | None = None
    if phase in {PHASE_GOAL_SIDE_ESCAPE, PHASE_DOCK_ENTRY}:
        target_pose, side_sign, segment_clearance_m = _entry_target_pose(
            robot_pose,
            ball_pose,
            zone=zone,
            snapshot=current_snapshot,
            previous_phase=previous_phase,
        )
        command, target_distance_m, target_heading_error_rad = _command_toward_target(
            robot_pose,
            target_pose,
            phase=phase,
            push_yaw_rad=push_yaw_rad,
        )
        strategy_name = f"{phase}_{'left' if side_sign is None or side_sign > 0.0 else 'right'}"
    elif phase == PHASE_DOCK_PORT:
        target_pose = (
            dict(current_snapshot.get("pre_stage_pose_world", {}))
            if isinstance(current_snapshot.get("pre_stage_pose_world"), dict)
            else {}
        )
        segment_clearance_m = _segment_ball_clearance(robot_pose, target_pose, ball_pose)
        command, target_distance_m, target_heading_error_rad = _command_toward_target(
            robot_pose,
            target_pose,
            phase=phase,
            push_yaw_rad=push_yaw_rad,
        )
        strategy_name = PHASE_DOCK_PORT
    elif phase == PHASE_YAW_ALIGN:
        command, yaw_error_rad = _yaw_align_command(robot_pose, push_yaw_rad=push_yaw_rad)
        target_distance_m = 0.0
        target_heading_error_rad = yaw_error_rad
        strategy_name = PHASE_YAW_ALIGN
    else:
        return PreStageReacquireFsmDecision(
            active=False,
            phase=PHASE_BASELINE_RELEASE,
            release_reason="baseline_safe_release",
            release_blockers=release_blockers,
            measured_snapshot=current_snapshot,
            measured_handoff_ready=False,
            ball_motion_m=ball_motion_m,
        )

    projected_snapshot, min_ball_clearance_m = _project_command(
        robot_pose,
        ball_pose,
        zone=zone,
        command=command,
    )
    current_projection_m = float(current_snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0)
    projected_projection_m = float(projected_snapshot.get("robot_longitudinal_projection_m", current_projection_m) or 0.0)
    current_lateral_m = float(current_snapshot.get("robot_lateral_error_m", 0.0) or 0.0)
    projected_lateral_m = float(projected_snapshot.get("robot_lateral_error_m", current_lateral_m) or 0.0)
    current_distance_m = float(current_snapshot.get("pre_stage_pose_distance_m", 0.0) or 0.0)
    projected_distance_m = float(projected_snapshot.get("pre_stage_pose_distance_m", current_distance_m) or 0.0)
    current_yaw_deg = float(current_snapshot.get("yaw_error_deg", 0.0) or 0.0)
    projected_yaw_deg = float(projected_snapshot.get("yaw_error_deg", current_yaw_deg) or 0.0)
    projection_gain = round(current_projection_m - projected_projection_m, 6)
    lateral_gain = round(current_lateral_m - projected_lateral_m, 6)
    distance_gain = round(current_distance_m - projected_distance_m, 6)
    yaw_gain = round(current_yaw_deg - projected_yaw_deg, 6)
    rejection_reasons: list[str] = []
    if min_ball_clearance_m is not None and min_ball_clearance_m < DEFAULT_FSM_MIN_BALL_CLEARANCE_M:
        rejection_reasons.append(REJECTION_PREDICTED_BALL_CONTACT)
    if projected_projection_m > current_projection_m + 0.06:
        rejection_reasons.append(REJECTION_DEEPER_GOAL_SIDE_PERSISTENCE)
    if (
        not bool(projected_snapshot.get("pre_stage_pose_reached", False))
        and _handoff_score(projected_snapshot or current_snapshot) > _handoff_score(current_snapshot) + 0.10
        and projection_gain <= 0.02
    ):
        rejection_reasons.append(REJECTION_WORSE_HANDOFF_READINESS)

    if rejection_reasons:
        command = PlaceControlCommand(
            mode="pre_stage_reacquire_fsm_hold",
            linear_x=0.0,
            angular_z=0.0,
            target_speed_scale=0.0,
            rationale="Pre-stage reacquire FSM is holding because the candidate command violated safety bounds.",
        )
        projected_snapshot, min_ball_clearance_m = _project_command(
            robot_pose,
            ball_pose,
            zone=zone,
            command=command,
        )
        projected_projection_m = float(projected_snapshot.get("robot_longitudinal_projection_m", current_projection_m) or 0.0)
        projected_lateral_m = float(projected_snapshot.get("robot_lateral_error_m", current_lateral_m) or 0.0)
        projected_distance_m = float(projected_snapshot.get("pre_stage_pose_distance_m", current_distance_m) or 0.0)
        projected_yaw_deg = float(projected_snapshot.get("yaw_error_deg", current_yaw_deg) or 0.0)
        projection_gain = round(current_projection_m - projected_projection_m, 6)
        lateral_gain = round(current_lateral_m - projected_lateral_m, 6)
        distance_gain = round(current_distance_m - projected_distance_m, 6)
        yaw_gain = round(current_yaw_deg - projected_yaw_deg, 6)
        strategy_name = f"{strategy_name}_hold"

    progress_score = round(
        (projection_gain * 120.0)
        + (distance_gain * 40.0)
        + (lateral_gain * 25.0)
        + (yaw_gain * 0.5)
        + ((float(min_ball_clearance_m or segment_clearance_m or 0.0) / 10.0))
        + (8.0 if phase == PHASE_GOAL_SIDE_ESCAPE else 0.0)
        + (4.0 if phase == PHASE_DOCK_ENTRY else 0.0),
        6,
    )
    return PreStageReacquireFsmDecision(
        active=True,
        phase=phase,
        strategy_name=strategy_name,
        objective_name=PRE_STAGE_REACQUIRE_FSM_OBJECTIVE,
        progress_score=progress_score,
        command=command,
        release_reason="",
        release_blockers=release_blockers,
        measured_snapshot=current_snapshot,
        projected_snapshot=projected_snapshot,
        measured_handoff_ready=bool(current_snapshot.get("pre_stage_pose_reached", False)),
        projected_handoff_ready=bool(projected_snapshot.get("pre_stage_pose_reached", False)),
        projection_m=round(current_projection_m, 6),
        lateral_error_m=round(current_lateral_m, 6),
        distance_m=round(current_distance_m, 6),
        yaw_error_deg=round(current_yaw_deg, 6),
        projected_projection_gain=projection_gain,
        projected_lateral_gain=lateral_gain,
        projected_distance_gain=distance_gain,
        projected_yaw_gain_deg=yaw_gain,
        ball_motion_m=ball_motion_m,
        min_ball_clearance_m=min_ball_clearance_m,
        target_pose=target_pose,
        target_distance_m=round(float(target_distance_m), 6) if target_distance_m is not None else None,
        target_heading_error_rad=round(float(target_heading_error_rad), 6)
        if target_heading_error_rad is not None
        else None,
        candidate_count=1,
        accepted_count=0 if rejection_reasons else 1,
        rejected_count=1 if rejection_reasons else 0,
        rejection_reasons=tuple(rejection_reasons),
    )
