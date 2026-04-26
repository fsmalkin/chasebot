#!/usr/bin/env python3
"""Measured-waypoint pre-stage path tracker for gather experiments."""

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


PRE_STAGE_PATH_TRACKER_CONTROL_FAMILY = "pre_stage_path_tracker_v1"
PRE_STAGE_PATH_TRACKER_OBJECTIVE = "pre_stage_path_tracker"

WAYPOINT_ESCAPE = "escape"
WAYPOINT_APPROACH = "approach"
WAYPOINT_PORT = "port"
WAYPOINT_YAW_ALIGN = "yaw_align"

DEFAULT_PATH_TRACKER_ESCAPE_LATERAL_M = 1.15
DEFAULT_PATH_TRACKER_APPROACH_LATERAL_M = 0.82
DEFAULT_PATH_TRACKER_ESCAPE_BEHIND_BIAS_M = 0.45
DEFAULT_PATH_TRACKER_APPROACH_BEHIND_BIAS_M = 0.22
DEFAULT_PATH_TRACKER_MIN_BALL_CLEARANCE_M = 0.48
DEFAULT_PATH_TRACKER_BALL_MOTION_TOLERANCE_M = 0.035
DEFAULT_PATH_TRACKER_RELEASE_PROJECTION_M = -0.45
DEFAULT_PATH_TRACKER_RELEASE_LATERAL_M = 0.24
DEFAULT_PATH_TRACKER_RELEASE_DISTANCE_M = 0.56
DEFAULT_PATH_TRACKER_RELEASE_YAW_DEG = 18.0
DEFAULT_PATH_TRACKER_MAX_LINEAR_X = 0.16
DEFAULT_PATH_TRACKER_MAX_ANGULAR_Z = 0.62
DEFAULT_PATH_TRACKER_YAW_MAX_ANGULAR_Z = 0.46
DEFAULT_PATH_TRACKER_HORIZON_S = 1.20
DEFAULT_PATH_TRACKER_STEP_S = 0.20
DEFAULT_PATH_TRACKER_STALL_TIMEOUT_S = 4.0

REJECTION_PREDICTED_BALL_CONTACT = "predicted_ball_contact"
REJECTION_SEGMENT_BALL_CLEARANCE = "segment_ball_clearance"
REJECTION_DEEPER_GOAL_SIDE = "deeper_goal_side"
REJECTION_WORSE_HANDOFF_PROGRESS = "worse_handoff_progress"
REJECTION_WAYPOINT_PROGRESS_STALL = "waypoint_progress_stall"


@dataclass(frozen=True)
class PreStagePathWaypoint:
    kind: str
    pose: dict[str, float]
    arrival_radius_m: float
    yaw_tolerance_deg: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PreStagePathTrackerDecision:
    active: bool
    waypoint_index: int = 0
    waypoint_kind: str = ""
    waypoint_count: int = 0
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
    waypoint_pose: dict[str, float] | None = None
    waypoint_distance_m: float | None = None
    waypoint_heading_error_rad: float | None = None
    waypoint_reached: bool = False
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
    segment_ball_clearance_m: float | None = None
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
    start_pose: dict[str, Any],
    target_pose: dict[str, Any],
    ball_pose: dict[str, Any],
) -> float | None:
    start_xyyaw = world_pose_xyyaw(start_pose)
    target_xy = point_xy(target_pose)
    ball_xy = point_xy(ball_pose)
    if start_xyyaw is None or target_xy is None or ball_xy is None:
        return None
    ax, ay, _yaw = start_xyyaw
    bx, by = target_xy
    px, py = ball_xy
    dx = bx - ax
    dy = by - ay
    denom = (dx * dx) + (dy * dy)
    if denom <= 1.0e-9:
        return round(math.hypot(px - ax, py - ay), 6)
    t = clamp(((px - ax) * dx + ((py - ay) * dy)) / denom, 0.0, 1.0)
    nearest_x = ax + (t * dx)
    nearest_y = ay + (t * dy)
    return round(math.hypot(px - nearest_x, py - nearest_y), 6)


def _rollout_samples(
    robot_pose: dict[str, Any],
    command: PlaceControlCommand,
    *,
    horizon_s: float = DEFAULT_PATH_TRACKER_HORIZON_S,
    step_s: float = DEFAULT_PATH_TRACKER_STEP_S,
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


def _choose_side(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    pre_stage_pose: dict[str, Any],
    *,
    basis: tuple[float, float, float, float, float],
    snapshot: dict[str, Any],
) -> float:
    _push_ux, _push_uy, normal_x, normal_y, _push_yaw = basis
    lateral_signed_m = float(snapshot.get("robot_lateral_signed_m", 0.0) or 0.0)
    preferred_sides = [1.0, -1.0]
    if abs(lateral_signed_m) > 0.05:
        preferred = 1.0 if lateral_signed_m > 0.0 else -1.0
        preferred_sides = [preferred, -preferred]

    robot_xyyaw = world_pose_xyyaw(robot_pose)
    best: tuple[float, float] | None = None
    for side in preferred_sides:
        target_pose = {
            "x": float(pre_stage_pose.get("x", 0.0) or 0.0)
            + (side * DEFAULT_PATH_TRACKER_ESCAPE_LATERAL_M * normal_x),
            "y": float(pre_stage_pose.get("y", 0.0) or 0.0)
            + (side * DEFAULT_PATH_TRACKER_ESCAPE_LATERAL_M * normal_y),
        }
        clearance = _segment_ball_clearance(robot_pose, target_pose, ball_pose) or 0.0
        heading_cost = 0.0
        if robot_xyyaw is not None:
            robot_x, robot_y, robot_yaw = robot_xyyaw
            heading_cost = abs(normalize_angle(math.atan2(target_pose["y"] - robot_y, target_pose["x"] - robot_x) - robot_yaw))
        score = clearance - (0.04 * heading_cost)
        if best is None or score > best[0]:
            best = (score, side)
    return float(best[1] if best is not None else 1.0)


def build_pre_stage_path_tracker_waypoints(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    snapshot: dict[str, Any] | None = None,
) -> list[PreStagePathWaypoint]:
    current_snapshot = (
        _valid_snapshot(snapshot)
        if snapshot is not None
        else _valid_snapshot(pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone))
    )
    basis = _push_basis(ball_pose, zone)
    pre_stage_pose = (
        dict(current_snapshot.get("pre_stage_pose_world", {}))
        if isinstance(current_snapshot, dict) and isinstance(current_snapshot.get("pre_stage_pose_world"), dict)
        else {}
    )
    if current_snapshot is None or basis is None or point_xy(pre_stage_pose) is None:
        return []
    push_ux, push_uy, normal_x, normal_y, push_yaw_rad = basis
    side = _choose_side(robot_pose, ball_pose, pre_stage_pose, basis=basis, snapshot=current_snapshot)
    pre_stage_x = float(pre_stage_pose.get("x", 0.0) or 0.0)
    pre_stage_y = float(pre_stage_pose.get("y", 0.0) or 0.0)

    def pose(lateral_m: float, behind_bias_m: float) -> dict[str, float]:
        return {
            "x": round(pre_stage_x + (side * lateral_m * normal_x) - (behind_bias_m * push_ux), 6),
            "y": round(pre_stage_y + (side * lateral_m * normal_y) - (behind_bias_m * push_uy), 6),
            "yaw": round(push_yaw_rad, 6),
        }

    return [
        PreStagePathWaypoint(
            kind=WAYPOINT_ESCAPE,
            pose=pose(DEFAULT_PATH_TRACKER_ESCAPE_LATERAL_M, DEFAULT_PATH_TRACKER_ESCAPE_BEHIND_BIAS_M),
            arrival_radius_m=0.32,
            yaw_tolerance_deg=90.0,
        ),
        PreStagePathWaypoint(
            kind=WAYPOINT_APPROACH,
            pose=pose(DEFAULT_PATH_TRACKER_APPROACH_LATERAL_M, DEFAULT_PATH_TRACKER_APPROACH_BEHIND_BIAS_M),
            arrival_radius_m=0.24,
            yaw_tolerance_deg=70.0,
        ),
        PreStagePathWaypoint(
            kind=WAYPOINT_PORT,
            pose={"x": round(pre_stage_x, 6), "y": round(pre_stage_y, 6), "yaw": round(push_yaw_rad, 6)},
            arrival_radius_m=0.22,
            yaw_tolerance_deg=45.0,
        ),
        PreStagePathWaypoint(
            kind=WAYPOINT_YAW_ALIGN,
            pose={"x": round(pre_stage_x, 6), "y": round(pre_stage_y, 6), "yaw": round(push_yaw_rad, 6)},
            arrival_radius_m=0.26,
            yaw_tolerance_deg=DEFAULT_PATH_TRACKER_RELEASE_YAW_DEG,
        ),
    ]


def pre_stage_path_tracker_release_blockers(
    snapshot: dict[str, Any] | None,
    *,
    ball_motion_m: float | None = None,
) -> tuple[str, ...]:
    current_snapshot = _valid_snapshot(snapshot)
    if current_snapshot is None:
        return ("missing_pre_stage_geometry",)
    if ball_motion_m is not None and float(ball_motion_m) > DEFAULT_PATH_TRACKER_BALL_MOTION_TOLERANCE_M:
        return ("ball_motion_guard",)
    if bool(current_snapshot.get("pre_stage_pose_reached", False)):
        return ()
    blockers: list[str] = []
    if bool(current_snapshot.get("robot_on_goal_side", False)):
        blockers.append("robot_on_goal_side")
    if float(current_snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0) > DEFAULT_PATH_TRACKER_RELEASE_PROJECTION_M:
        blockers.append("projection_not_cleared")
    if float(current_snapshot.get("robot_lateral_error_m", 0.0) or 0.0) > DEFAULT_PATH_TRACKER_RELEASE_LATERAL_M:
        blockers.append("lateral_not_converged")
    if float(current_snapshot.get("pre_stage_pose_distance_m", 0.0) or 0.0) > DEFAULT_PATH_TRACKER_RELEASE_DISTANCE_M:
        blockers.append("distance_not_converged")
    if float(current_snapshot.get("yaw_error_deg", 0.0) or 0.0) > DEFAULT_PATH_TRACKER_RELEASE_YAW_DEG:
        blockers.append("yaw_not_aligned")
    return tuple(blockers)


def pre_stage_path_tracker_release_reason(
    snapshot: dict[str, Any] | None,
    *,
    ball_motion_m: float | None = None,
) -> str:
    current_snapshot = _valid_snapshot(snapshot)
    if current_snapshot is None:
        return "missing_pre_stage_geometry"
    if ball_motion_m is not None and float(ball_motion_m) > DEFAULT_PATH_TRACKER_BALL_MOTION_TOLERANCE_M:
        return "ball_motion_guard"
    if bool(current_snapshot.get("pre_stage_pose_reached", False)):
        return "pre_stage_handoff_ready"
    if pre_stage_path_tracker_release_blockers(current_snapshot, ball_motion_m=ball_motion_m):
        return ""
    return "baseline_safe_release"


def _waypoint_distance_and_heading(
    robot_pose: dict[str, Any],
    waypoint: PreStagePathWaypoint,
) -> tuple[float | None, float | None]:
    rel = relative_point_robot_frame(robot_pose, waypoint.pose)
    if rel is None:
        return None, None
    rel_x, rel_y = rel
    return math.hypot(rel_x, rel_y), math.atan2(rel_y, max(rel_x, 1.0e-6))


def _waypoint_reached(robot_pose: dict[str, Any], waypoint: PreStagePathWaypoint) -> bool:
    distance_m, _heading_error = _waypoint_distance_and_heading(robot_pose, waypoint)
    if distance_m is None or distance_m > waypoint.arrival_radius_m:
        return False
    if waypoint.kind != WAYPOINT_YAW_ALIGN:
        return True
    robot_xyyaw = world_pose_xyyaw(robot_pose)
    if robot_xyyaw is None:
        return False
    _x, _y, yaw_rad = robot_xyyaw
    yaw_error_deg = abs(math.degrees(normalize_angle(float(waypoint.pose.get("yaw", 0.0)) - yaw_rad)))
    return yaw_error_deg <= waypoint.yaw_tolerance_deg


def _current_waypoint_index(robot_pose: dict[str, Any], waypoints: list[PreStagePathWaypoint], previous_index: int) -> tuple[int, bool]:
    if not waypoints:
        return 0, False
    index = int(clamp(previous_index, 0, len(waypoints) - 1))
    advanced = False
    while index < len(waypoints) - 1 and _waypoint_reached(robot_pose, waypoints[index]):
        index += 1
        advanced = True
    return index, advanced


def _command_toward_waypoint(
    robot_pose: dict[str, Any],
    waypoint: PreStagePathWaypoint,
) -> tuple[PlaceControlCommand, float | None, float | None]:
    distance_m, heading_error = _waypoint_distance_and_heading(robot_pose, waypoint)
    robot_xyyaw = world_pose_xyyaw(robot_pose)
    if distance_m is None or heading_error is None or robot_xyyaw is None:
        return (
            PlaceControlCommand(
                mode="pre_stage_path_tracker_hold",
                linear_x=0.0,
                angular_z=0.0,
                target_speed_scale=0.0,
                rationale="Pre-stage path tracker is holding because waypoint geometry is unavailable.",
            ),
            distance_m,
            heading_error,
        )
    _x, _y, robot_yaw = robot_xyyaw
    yaw_error = normalize_angle(float(waypoint.pose.get("yaw", robot_yaw)) - robot_yaw)
    if waypoint.kind == WAYPOINT_YAW_ALIGN:
        angular = clamp(yaw_error * 0.90, -DEFAULT_PATH_TRACKER_YAW_MAX_ANGULAR_Z, DEFAULT_PATH_TRACKER_YAW_MAX_ANGULAR_Z)
        if abs(angular) < 0.16 and abs(math.degrees(yaw_error)) > waypoint.yaw_tolerance_deg:
            angular = 0.16 if yaw_error >= 0.0 else -0.16
        return (
            PlaceControlCommand(
                mode="pre_stage_path_tracker_yaw_align",
                linear_x=0.0,
                angular_z=round(angular, 6),
                target_speed_scale=0.0,
                rationale="Pre-stage path tracker rotates in place at the final handoff waypoint.",
            ),
            distance_m,
            yaw_error,
        )
    if abs(heading_error) > 1.05:
        angular = clamp(heading_error * 1.25, -DEFAULT_PATH_TRACKER_MAX_ANGULAR_Z, DEFAULT_PATH_TRACKER_MAX_ANGULAR_Z)
        if abs(angular) < 0.16 and abs(heading_error) > 0.16:
            angular = 0.16 if heading_error >= 0.0 else -0.16
        return (
            PlaceControlCommand(
                mode="pre_stage_path_tracker",
                linear_x=0.0,
                angular_z=round(angular, 6),
                target_speed_scale=0.0,
                rationale="Pre-stage path tracker turns toward the next measured waypoint.",
            ),
            distance_m,
            heading_error,
        )
    linear = clamp(distance_m * 0.22, 0.04, DEFAULT_PATH_TRACKER_MAX_LINEAR_X)
    if waypoint.kind == WAYPOINT_ESCAPE:
        linear = min(linear, 0.14)
    if abs(heading_error) > 0.45:
        linear = min(linear, 0.10)
    angular = clamp(
        (heading_error * 0.72) + (yaw_error * 0.06),
        -DEFAULT_PATH_TRACKER_MAX_ANGULAR_Z,
        DEFAULT_PATH_TRACKER_MAX_ANGULAR_Z,
    )
    return (
        PlaceControlCommand(
            mode="pre_stage_path_tracker",
            linear_x=round(linear, 6),
            angular_z=round(angular, 6),
            target_speed_scale=0.70,
            rationale="Pre-stage path tracker follows the measured behind-ball waypoint path.",
        ),
        distance_m,
        heading_error,
    )


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


def _hold_command(rationale: str) -> PlaceControlCommand:
    return PlaceControlCommand(
        mode="pre_stage_path_tracker_hold",
        linear_x=0.0,
        angular_z=0.0,
        target_speed_scale=0.0,
        rationale=rationale,
    )


def decide_pre_stage_path_tracker_command(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    snapshot: dict[str, Any] | None = None,
    previous_waypoint_index: int = 0,
    stall_s: float = 0.0,
    ball_motion_m: float | None = None,
) -> PreStagePathTrackerDecision:
    current_snapshot = (
        _valid_snapshot(snapshot)
        if snapshot is not None
        else _valid_snapshot(pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone))
    )
    release_reason = pre_stage_path_tracker_release_reason(current_snapshot, ball_motion_m=ball_motion_m)
    release_blockers = pre_stage_path_tracker_release_blockers(current_snapshot, ball_motion_m=ball_motion_m)
    if current_snapshot is None or release_reason:
        return PreStagePathTrackerDecision(
            active=False,
            waypoint_index=int(max(previous_waypoint_index, 0)),
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

    waypoints = build_pre_stage_path_tracker_waypoints(robot_pose, ball_pose, zone=zone, snapshot=current_snapshot)
    if not waypoints:
        return PreStagePathTrackerDecision(
            active=False,
            release_reason="missing_pre_stage_geometry",
            release_blockers=("missing_pre_stage_geometry",),
            measured_snapshot=current_snapshot,
            measured_handoff_ready=False,
            ball_motion_m=ball_motion_m,
        )
    waypoint_index, advanced = _current_waypoint_index(robot_pose, waypoints, previous_waypoint_index)
    waypoint = waypoints[waypoint_index]
    command, waypoint_distance_m, waypoint_heading_error_rad = _command_toward_waypoint(robot_pose, waypoint)
    segment_ball_clearance_m = _segment_ball_clearance(robot_pose, waypoint.pose, ball_pose)
    projected_snapshot, min_ball_clearance_m = _project_command(
        robot_pose,
        ball_pose,
        zone=zone,
        command=command,
    )

    current_projection_m = float(current_snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0)
    current_lateral_m = float(current_snapshot.get("robot_lateral_error_m", 0.0) or 0.0)
    current_distance_m = float(current_snapshot.get("pre_stage_pose_distance_m", 0.0) or 0.0)
    current_yaw_deg = float(current_snapshot.get("yaw_error_deg", 0.0) or 0.0)
    projected_projection_m = float(projected_snapshot.get("robot_longitudinal_projection_m", current_projection_m) or 0.0)
    projected_lateral_m = float(projected_snapshot.get("robot_lateral_error_m", current_lateral_m) or 0.0)
    projected_distance_m = float(projected_snapshot.get("pre_stage_pose_distance_m", current_distance_m) or 0.0)
    projected_yaw_deg = float(projected_snapshot.get("yaw_error_deg", current_yaw_deg) or 0.0)
    projection_gain = round(current_projection_m - projected_projection_m, 6)
    lateral_gain = round(current_lateral_m - projected_lateral_m, 6)
    distance_gain = round(current_distance_m - projected_distance_m, 6)
    yaw_gain = round(current_yaw_deg - projected_yaw_deg, 6)

    rejection_reasons: list[str] = []
    if min_ball_clearance_m is not None and min_ball_clearance_m < DEFAULT_PATH_TRACKER_MIN_BALL_CLEARANCE_M:
        rejection_reasons.append(REJECTION_PREDICTED_BALL_CONTACT)
    if (
        segment_ball_clearance_m is not None
        and segment_ball_clearance_m < DEFAULT_PATH_TRACKER_MIN_BALL_CLEARANCE_M
        and waypoint.kind != WAYPOINT_YAW_ALIGN
    ):
        rejection_reasons.append(REJECTION_SEGMENT_BALL_CLEARANCE)
    if projected_projection_m > current_projection_m + 0.06:
        rejection_reasons.append(REJECTION_DEEPER_GOAL_SIDE)
    if projection_gain <= -0.02 and distance_gain <= -0.02 and lateral_gain <= -0.02:
        rejection_reasons.append(REJECTION_WORSE_HANDOFF_PROGRESS)
    if float(stall_s) >= DEFAULT_PATH_TRACKER_STALL_TIMEOUT_S and not advanced:
        rejection_reasons.append(REJECTION_WAYPOINT_PROGRESS_STALL)

    if rejection_reasons:
        command = _hold_command("Pre-stage path tracker is holding because the candidate command violated safety or progress bounds.")
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

    progress_score = round(
        (waypoint_index * 100.0)
        + (projection_gain * 80.0)
        + (distance_gain * 36.0)
        + (lateral_gain * 28.0)
        + (yaw_gain * 0.45)
        + (5.0 if advanced else 0.0),
        6,
    )
    return PreStagePathTrackerDecision(
        active=True,
        waypoint_index=waypoint_index,
        waypoint_kind=waypoint.kind,
        waypoint_count=len(waypoints),
        strategy_name=f"path_{waypoint.kind}",
        objective_name=PRE_STAGE_PATH_TRACKER_OBJECTIVE,
        progress_score=progress_score,
        command=command,
        release_reason="",
        release_blockers=release_blockers,
        measured_snapshot=current_snapshot,
        projected_snapshot=projected_snapshot,
        measured_handoff_ready=bool(current_snapshot.get("pre_stage_pose_reached", False)),
        projected_handoff_ready=bool(projected_snapshot.get("pre_stage_pose_reached", False)),
        waypoint_pose=waypoint.pose,
        waypoint_distance_m=round(float(waypoint_distance_m), 6) if waypoint_distance_m is not None else None,
        waypoint_heading_error_rad=round(float(waypoint_heading_error_rad), 6)
        if waypoint_heading_error_rad is not None
        else None,
        waypoint_reached=advanced,
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
        segment_ball_clearance_m=segment_ball_clearance_m,
        candidate_count=1,
        accepted_count=0 if rejection_reasons else 1,
        rejected_count=1 if rejection_reasons else 0,
        rejection_reasons=tuple(rejection_reasons),
    )
