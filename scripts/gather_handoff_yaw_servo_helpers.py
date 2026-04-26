#!/usr/bin/env python3
"""Yaw-only pre-stage handoff servo for gather experiments."""

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
from gather_mission_helpers import world_pose_xyyaw


HANDOFF_YAW_SERVO_CONTROL_FAMILY = "handoff_yaw_servo_v1"
HANDOFF_YAW_SERVO_OBJECTIVE = "handoff_yaw_servo"

DEFAULT_HANDOFF_YAW_SERVO_RELEASE_PROJECTION_M = -0.35
DEFAULT_HANDOFF_YAW_SERVO_RELEASE_LATERAL_M = 0.30
DEFAULT_HANDOFF_YAW_SERVO_RELEASE_DISTANCE_M = 0.75
DEFAULT_HANDOFF_YAW_SERVO_MIN_YAW_ERROR_DEG = 20.0
DEFAULT_HANDOFF_YAW_SERVO_MAX_YAW_ERROR_DEG = 120.0
DEFAULT_HANDOFF_YAW_SERVO_BALL_MOTION_TOLERANCE_M = 0.035
DEFAULT_HANDOFF_YAW_SERVO_MAX_ANGULAR_Z = 0.45
DEFAULT_HANDOFF_YAW_SERVO_GAIN = 0.90
DEFAULT_HANDOFF_YAW_SERVO_PROJECTION_HORIZON_S = 1.0


@dataclass(frozen=True)
class HandoffYawServoDecision:
    active: bool
    strategy_name: str = ""
    objective_name: str = ""
    progress_score: float | None = None
    command: PlaceControlCommand | None = None
    release_reason: str = ""
    release_blockers: tuple[str, ...] = ()
    yaw_error_deg: float | None = None
    yaw_error_rad: float | None = None
    target_yaw_rad: float | None = None
    current_yaw_rad: float | None = None
    angular_z: float | None = None
    ball_motion_m: float | None = None
    projected_snapshot: dict[str, Any] | None = None
    handoff_ready_projected: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.command is not None:
            payload["command"] = self.command.to_dict()
        payload["release_blockers"] = list(self.release_blockers)
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
        "yaw_error_deg",
    ):
        if _finite_number(snapshot.get(key)) is None:
            return None
    return snapshot


def _target_yaw_rad(ball_pose: dict[str, Any], *, zone: ZoneSpec, snapshot: dict[str, Any]) -> float | None:
    snapshot_yaw_deg = _finite_number(snapshot.get("push_direction_yaw_deg"))
    if snapshot_yaw_deg is not None:
        return math.radians(snapshot_yaw_deg)
    ball_xy = point_xy(ball_pose)
    if ball_xy is None:
        return None
    push_dx = float(zone.world_x) - ball_xy[0]
    push_dy = float(zone.world_y) - ball_xy[1]
    if math.hypot(push_dx, push_dy) <= 1.0e-6:
        return None
    return math.atan2(push_dy, push_dx)


def handoff_yaw_servo_release_blockers(
    snapshot: dict[str, Any] | None,
    *,
    ball_motion_m: float | None = None,
) -> tuple[str, ...]:
    current_snapshot = _valid_snapshot(snapshot)
    if current_snapshot is None:
        return ("missing_pre_stage_geometry",)
    if bool(current_snapshot.get("pre_stage_pose_reached", False)):
        return ()
    blockers: list[str] = []
    if ball_motion_m is not None and float(ball_motion_m) > DEFAULT_HANDOFF_YAW_SERVO_BALL_MOTION_TOLERANCE_M:
        blockers.append("ball_motion_guard")
    if bool(current_snapshot.get("robot_on_goal_side", False)):
        blockers.append("robot_on_goal_side")
    projection_m = float(current_snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0)
    lateral_m = float(current_snapshot.get("robot_lateral_error_m", 0.0) or 0.0)
    distance_m = float(current_snapshot.get("pre_stage_pose_distance_m", 0.0) or 0.0)
    yaw_error_deg = float(current_snapshot.get("yaw_error_deg", 0.0) or 0.0)
    if projection_m > DEFAULT_HANDOFF_YAW_SERVO_RELEASE_PROJECTION_M:
        blockers.append("projection_not_cleared")
    if lateral_m > DEFAULT_HANDOFF_YAW_SERVO_RELEASE_LATERAL_M:
        blockers.append("lateral_not_converged")
    if distance_m > DEFAULT_HANDOFF_YAW_SERVO_RELEASE_DISTANCE_M:
        blockers.append("distance_not_converged")
    if yaw_error_deg > DEFAULT_HANDOFF_YAW_SERVO_MAX_YAW_ERROR_DEG:
        blockers.append("yaw_error_out_of_servo_range")
    return tuple(blockers)


def handoff_yaw_servo_release_reason(
    snapshot: dict[str, Any] | None,
    *,
    ball_motion_m: float | None = None,
) -> str:
    current_snapshot = _valid_snapshot(snapshot)
    if current_snapshot is None:
        return "missing_pre_stage_geometry"
    if bool(current_snapshot.get("pre_stage_pose_reached", False)):
        return "pre_stage_handoff_ready"
    if ball_motion_m is not None and float(ball_motion_m) > DEFAULT_HANDOFF_YAW_SERVO_BALL_MOTION_TOLERANCE_M:
        return "ball_motion_guard"
    yaw_error_deg = float(current_snapshot.get("yaw_error_deg", 0.0) or 0.0)
    blockers = tuple(
        blocker
        for blocker in handoff_yaw_servo_release_blockers(current_snapshot, ball_motion_m=ball_motion_m)
        if blocker != "ball_motion_guard"
    )
    if blockers:
        return "geometry_guard"
    if yaw_error_deg <= DEFAULT_HANDOFF_YAW_SERVO_MIN_YAW_ERROR_DEG:
        return "baseline_pre_stage_traversal_ready"
    return ""


def _project_yaw_only(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    angular_z: float,
) -> dict[str, Any] | None:
    robot_xyyaw = world_pose_xyyaw(robot_pose)
    if robot_xyyaw is None:
        return None
    x_m, y_m, yaw_rad = robot_xyyaw
    projected_pose = {
        "x": round(x_m, 6),
        "y": round(y_m, 6),
        "yaw": round(
            normalize_angle(yaw_rad + (float(angular_z) * DEFAULT_HANDOFF_YAW_SERVO_PROJECTION_HORIZON_S)),
            6,
        ),
    }
    return pre_stage_arrival_snapshot(projected_pose, ball_pose, zone=zone)


def decide_handoff_yaw_servo_pre_stage_command(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    snapshot: dict[str, Any] | None = None,
    ball_motion_m: float | None = None,
) -> HandoffYawServoDecision:
    current_snapshot = (
        _valid_snapshot(snapshot)
        if snapshot is not None
        else _valid_snapshot(pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone))
    )
    release_blockers = handoff_yaw_servo_release_blockers(current_snapshot, ball_motion_m=ball_motion_m)
    release_reason = handoff_yaw_servo_release_reason(current_snapshot, ball_motion_m=ball_motion_m)
    if current_snapshot is None or release_reason:
        return HandoffYawServoDecision(
            active=False,
            release_reason=release_reason,
            release_blockers=release_blockers,
            ball_motion_m=ball_motion_m,
        )

    robot_xyyaw = world_pose_xyyaw(robot_pose)
    target_yaw_rad = _target_yaw_rad(ball_pose, zone=zone, snapshot=current_snapshot)
    if robot_xyyaw is None or target_yaw_rad is None:
        return HandoffYawServoDecision(
            active=False,
            release_reason="missing_pre_stage_geometry",
            release_blockers=("missing_pre_stage_geometry",),
            ball_motion_m=ball_motion_m,
        )
    _robot_x, _robot_y, current_yaw_rad = robot_xyyaw
    yaw_error_rad = normalize_angle(target_yaw_rad - current_yaw_rad)
    yaw_error_deg = abs(math.degrees(yaw_error_rad))
    angular_z = round(
        clamp(
            yaw_error_rad * DEFAULT_HANDOFF_YAW_SERVO_GAIN,
            -DEFAULT_HANDOFF_YAW_SERVO_MAX_ANGULAR_Z,
            DEFAULT_HANDOFF_YAW_SERVO_MAX_ANGULAR_Z,
        ),
        6,
    )
    command = PlaceControlCommand(
        mode="handoff_yaw_servo_pre_stage",
        linear_x=0.0,
        angular_z=angular_z,
        target_speed_scale=0.0,
        rationale="Handoff yaw servo rotates in place because the pre-stage geometry is safe except yaw.",
    )
    projected_snapshot = _valid_snapshot(
        _project_yaw_only(robot_pose, ball_pose, zone=zone, angular_z=angular_z)
    )
    projected_yaw_error = (
        float(projected_snapshot.get("yaw_error_deg", yaw_error_deg) or 0.0)
        if projected_snapshot is not None
        else yaw_error_deg
    )
    progress_score = round(max(0.0, yaw_error_deg - projected_yaw_error), 6)
    return HandoffYawServoDecision(
        active=True,
        strategy_name="handoff_yaw_servo",
        objective_name=HANDOFF_YAW_SERVO_OBJECTIVE,
        progress_score=progress_score,
        command=command,
        release_reason="",
        release_blockers=release_blockers,
        yaw_error_deg=round(yaw_error_deg, 6),
        yaw_error_rad=round(yaw_error_rad, 6),
        target_yaw_rad=round(target_yaw_rad, 6),
        current_yaw_rad=round(current_yaw_rad, 6),
        angular_z=angular_z,
        ball_motion_m=ball_motion_m,
        projected_snapshot=projected_snapshot,
        handoff_ready_projected=(
            bool(projected_snapshot.get("pre_stage_pose_reached", False))
            if projected_snapshot is not None
            else False
        ),
    )
