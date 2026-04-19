#!/usr/bin/env python3
"""Deterministic short-horizon helpers for pre-stage gather repositioning."""

from __future__ import annotations

import math
from dataclasses import asdict
from dataclasses import dataclass
from typing import Any

from gather_mission_helpers import PlaceControlCommand
from gather_mission_helpers import ZoneSpec
from gather_mission_helpers import clamp
from gather_mission_helpers import normalize_angle
from gather_mission_helpers import pre_stage_arrival_snapshot
from gather_mission_helpers import world_pose_xyyaw


DEFAULT_SHORT_HORIZON_HORIZON_S = 1.5
DEFAULT_SHORT_HORIZON_STEP_S = 0.5
DEFAULT_SHORT_HORIZON_LINEAR_X_MPS = -0.18
DEFAULT_SHORT_HORIZON_SOFT_ARC_ANGULAR_Z = 0.25
DEFAULT_SHORT_HORIZON_HARD_ARC_ANGULAR_Z = 0.55
DEFAULT_SHORT_HORIZON_ANGULAR_LIMIT = 0.8
DEFAULT_SHORT_HORIZON_SWITCH_MARGIN = 0.08
DEFAULT_SHORT_HORIZON_SWITCH_PENALTY = 0.03
DEFAULT_SHORT_HORIZON_HOLD_PENALTY = 0.05
DEFAULT_SHORT_HORIZON_FREE_SWITCH_STALL_S = 1.5
DEFAULT_SHORT_HORIZON_MAX_ACTIVE_YAW_ERROR_DEG = 45.0


@dataclass(frozen=True)
class ShortHorizonProjection:
    strategy_name: str
    command: PlaceControlCommand
    progress_score: float
    score_key: tuple[float, float, float, float, float]
    projected_robot_pose: dict[str, float]
    projected_snapshot: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ShortHorizonDecision:
    active: bool
    strategy_name: str = ""
    progress_score: float | None = None
    command: PlaceControlCommand | None = None
    projection: ShortHorizonProjection | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        projection = payload.get("projection")
        if isinstance(self.projection, ShortHorizonProjection):
            payload["projection"] = self.projection.to_dict()
        elif projection is None:
            payload["projection"] = None
        return payload


def short_horizon_pre_stage_active(snapshot: dict[str, Any] | None) -> bool:
    if not isinstance(snapshot, dict):
        return False
    if bool(snapshot.get("pre_stage_pose_reached", False)):
        return False
    if float(snapshot.get("yaw_error_deg", 0.0) or 0.0) > DEFAULT_SHORT_HORIZON_MAX_ACTIVE_YAW_ERROR_DEG:
        return False
    robot_on_goal_side = bool(snapshot.get("robot_on_goal_side", False))
    robot_longitudinal_projection_m = float(snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0)
    return robot_on_goal_side or robot_longitudinal_projection_m > -0.05


def _rollout_pose(
    robot_pose: dict[str, Any],
    command: PlaceControlCommand,
    *,
    horizon_s: float = DEFAULT_SHORT_HORIZON_HORIZON_S,
    step_s: float = DEFAULT_SHORT_HORIZON_STEP_S,
) -> dict[str, float] | None:
    robot_xyyaw = world_pose_xyyaw(robot_pose)
    if robot_xyyaw is None:
        return None
    x_m, y_m, yaw_rad = robot_xyyaw
    remaining_s = max(float(horizon_s), 0.0)
    if remaining_s <= 0.0:
        return {"x": round(x_m, 6), "y": round(y_m, 6), "yaw": round(yaw_rad, 6)}
    while remaining_s > 1.0e-9:
        dt_s = min(float(step_s), remaining_s)
        x_m += float(command.linear_x) * math.cos(yaw_rad) * dt_s
        y_m += float(command.linear_x) * math.sin(yaw_rad) * dt_s
        yaw_rad = normalize_angle(yaw_rad + (float(command.angular_z) * dt_s))
        remaining_s -= dt_s
    return {"x": round(x_m, 6), "y": round(y_m, 6), "yaw": round(yaw_rad, 6)}


def _direct_reverse_heading_command(
    robot_pose: dict[str, Any],
    pre_stage_pose_world: dict[str, Any],
) -> PlaceControlCommand | None:
    robot_xyyaw = world_pose_xyyaw(robot_pose)
    if robot_xyyaw is None:
        return None
    robot_x_m, robot_y_m, robot_yaw_rad = robot_xyyaw
    desired_reverse_yaw = normalize_angle(
        math.atan2(
            float(pre_stage_pose_world.get("y", 0.0)) - robot_y_m,
            float(pre_stage_pose_world.get("x", 0.0)) - robot_x_m,
        )
        + math.pi
    )
    reverse_yaw_error = normalize_angle(desired_reverse_yaw - robot_yaw_rad)
    angular_z = clamp(reverse_yaw_error * 1.1, -DEFAULT_SHORT_HORIZON_ANGULAR_LIMIT, DEFAULT_SHORT_HORIZON_ANGULAR_LIMIT)
    if abs(angular_z) < 0.20 and abs(reverse_yaw_error) > 0.10:
        angular_z = 0.20 if reverse_yaw_error >= 0.0 else -0.20
    return PlaceControlCommand(
        mode="pre_stage_escape_goal_side",
        linear_x=DEFAULT_SHORT_HORIZON_LINEAR_X_MPS,
        angular_z=round(angular_z, 6),
        target_speed_scale=0.0,
        rationale="Short-horizon scorer chose a direct reverse heading toward the behind-ball corridor.",
    )


def _candidate_commands(
    robot_pose: dict[str, Any],
    snapshot: dict[str, Any],
) -> list[tuple[str, PlaceControlCommand]]:
    candidates = [
        (
            "hold",
            PlaceControlCommand(
                mode="pre_stage_escape_goal_side",
                linear_x=0.0,
                angular_z=0.0,
                target_speed_scale=0.0,
                rationale="Short-horizon scorer chose to hold the current pre-stage pose.",
            ),
        ),
        (
            "reverse_straight",
            PlaceControlCommand(
                mode="pre_stage_escape_goal_side",
                linear_x=DEFAULT_SHORT_HORIZON_LINEAR_X_MPS,
                angular_z=0.0,
                target_speed_scale=0.0,
                rationale="Short-horizon scorer chose a straight reverse to reduce goal-side projection.",
            ),
        ),
        (
            "reverse_arc_left_soft",
            PlaceControlCommand(
                mode="pre_stage_escape_goal_side",
                linear_x=DEFAULT_SHORT_HORIZON_LINEAR_X_MPS,
                angular_z=DEFAULT_SHORT_HORIZON_SOFT_ARC_ANGULAR_Z,
                target_speed_scale=0.0,
                rationale="Short-horizon scorer chose a soft reverse-left arc to leave the goal side.",
            ),
        ),
        (
            "reverse_arc_right_soft",
            PlaceControlCommand(
                mode="pre_stage_escape_goal_side",
                linear_x=DEFAULT_SHORT_HORIZON_LINEAR_X_MPS,
                angular_z=-DEFAULT_SHORT_HORIZON_SOFT_ARC_ANGULAR_Z,
                target_speed_scale=0.0,
                rationale="Short-horizon scorer chose a soft reverse-right arc to leave the goal side.",
            ),
        ),
        (
            "reverse_arc_left_hard",
            PlaceControlCommand(
                mode="pre_stage_escape_goal_side",
                linear_x=DEFAULT_SHORT_HORIZON_LINEAR_X_MPS,
                angular_z=DEFAULT_SHORT_HORIZON_HARD_ARC_ANGULAR_Z,
                target_speed_scale=0.0,
                rationale="Short-horizon scorer chose a hard reverse-left arc to accelerate behind-ball progress.",
            ),
        ),
        (
            "reverse_arc_right_hard",
            PlaceControlCommand(
                mode="pre_stage_escape_goal_side",
                linear_x=DEFAULT_SHORT_HORIZON_LINEAR_X_MPS,
                angular_z=-DEFAULT_SHORT_HORIZON_HARD_ARC_ANGULAR_Z,
                target_speed_scale=0.0,
                rationale="Short-horizon scorer chose a hard reverse-right arc to accelerate behind-ball progress.",
            ),
        ),
    ]
    pre_stage_pose_world = snapshot.get("pre_stage_pose_world", {}) if isinstance(snapshot.get("pre_stage_pose_world"), dict) else {}
    direct_command = _direct_reverse_heading_command(robot_pose, pre_stage_pose_world)
    if direct_command is not None:
        candidates.append(("reverse_direct_heading", direct_command))
    return candidates


def project_short_horizon_command(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    command: PlaceControlCommand,
    strategy_name: str,
    snapshot: dict[str, Any] | None = None,
    previous_strategy_name: str = "",
    horizon_s: float = DEFAULT_SHORT_HORIZON_HORIZON_S,
    step_s: float = DEFAULT_SHORT_HORIZON_STEP_S,
) -> ShortHorizonProjection | None:
    current_snapshot = snapshot if isinstance(snapshot, dict) else pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone)
    if not isinstance(current_snapshot, dict):
        return None
    projected_robot_pose = _rollout_pose(robot_pose, command, horizon_s=horizon_s, step_s=step_s)
    if projected_robot_pose is None:
        return None
    projected_snapshot = pre_stage_arrival_snapshot(projected_robot_pose, ball_pose, zone=zone)
    if not isinstance(projected_snapshot, dict):
        return None
    initial_projection_m = float(current_snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0)
    final_projection_m = float(projected_snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0)
    initial_lateral_error_m = float(current_snapshot.get("robot_lateral_error_m", 0.0) or 0.0)
    final_lateral_error_m = float(projected_snapshot.get("robot_lateral_error_m", 0.0) or 0.0)
    initial_distance_m = float(current_snapshot.get("pre_stage_pose_distance_m", 0.0) or 0.0)
    final_distance_m = float(projected_snapshot.get("pre_stage_pose_distance_m", 0.0) or 0.0)
    projection_gain = initial_projection_m - final_projection_m
    lateral_gain = initial_lateral_error_m - final_lateral_error_m
    distance_gain = initial_distance_m - final_distance_m
    projection_gain_bucket = round(projection_gain / 0.05) * 0.05
    switch_penalty = (
        DEFAULT_SHORT_HORIZON_SWITCH_PENALTY
        if previous_strategy_name and previous_strategy_name != strategy_name
        else 0.0
    )
    hold_penalty = DEFAULT_SHORT_HORIZON_HOLD_PENALTY if strategy_name == "hold" else 0.0
    score_key = (
        1.0 if not bool(projected_snapshot.get("robot_on_goal_side", False)) else 0.0,
        round(projection_gain_bucket, 6),
        round(lateral_gain, 6),
        round(distance_gain, 6),
        round(-(switch_penalty + hold_penalty), 6),
    )
    progress_score = (
        (score_key[0] * 100.0)
        + (projection_gain * 10.0)
        + (lateral_gain * 5.0)
        + (distance_gain * 2.0)
        - switch_penalty
        - hold_penalty
    )
    return ShortHorizonProjection(
        strategy_name=strategy_name,
        command=command,
        progress_score=round(progress_score, 6),
        score_key=score_key,
        projected_robot_pose=projected_robot_pose,
        projected_snapshot=projected_snapshot,
    )


def decide_short_horizon_pre_stage_command(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    snapshot: dict[str, Any] | None = None,
    previous_strategy_name: str = "",
    stall_s: float = 0.0,
) -> ShortHorizonDecision:
    current_snapshot = snapshot if isinstance(snapshot, dict) else pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone)
    if not short_horizon_pre_stage_active(current_snapshot):
        return ShortHorizonDecision(active=False)
    projections = [
        project_short_horizon_command(
            robot_pose,
            ball_pose,
            zone=zone,
            command=command,
            strategy_name=strategy_name,
            snapshot=current_snapshot,
            previous_strategy_name=previous_strategy_name,
        )
        for strategy_name, command in _candidate_commands(robot_pose, current_snapshot)
    ]
    valid_projections = [item for item in projections if isinstance(item, ShortHorizonProjection)]
    if not valid_projections:
        return ShortHorizonDecision(active=False)
    best_projection = max(valid_projections, key=lambda item: (item.score_key, item.progress_score, item.strategy_name))
    current_projection = next(
        (item for item in valid_projections if item.strategy_name == previous_strategy_name),
        None,
    )
    if (
        current_projection is not None
        and current_projection.strategy_name != best_projection.strategy_name
        and float(stall_s) < DEFAULT_SHORT_HORIZON_FREE_SWITCH_STALL_S
        and float(best_projection.progress_score) < float(current_projection.progress_score) + DEFAULT_SHORT_HORIZON_SWITCH_MARGIN
    ):
        best_projection = current_projection
    return ShortHorizonDecision(
        active=True,
        strategy_name=best_projection.strategy_name,
        progress_score=best_projection.progress_score,
        command=best_projection.command,
        projection=best_projection,
    )
