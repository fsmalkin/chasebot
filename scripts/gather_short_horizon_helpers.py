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
DEFAULT_SHORT_HORIZON_V2_HORIZON_S = 2.0
DEFAULT_SHORT_HORIZON_V2_STEP_S = 0.5
DEFAULT_SHORT_HORIZON_LINEAR_X_MPS = -0.18
DEFAULT_SHORT_HORIZON_SOFT_ARC_ANGULAR_Z = 0.25
DEFAULT_SHORT_HORIZON_HARD_ARC_ANGULAR_Z = 0.55
DEFAULT_SHORT_HORIZON_ANGULAR_LIMIT = 0.8
DEFAULT_SHORT_HORIZON_SWITCH_MARGIN = 0.08
DEFAULT_SHORT_HORIZON_SWITCH_PENALTY = 0.03
DEFAULT_SHORT_HORIZON_HOLD_PENALTY = 0.05
DEFAULT_SHORT_HORIZON_FREE_SWITCH_STALL_S = 1.5
DEFAULT_SHORT_HORIZON_MAX_ACTIVE_YAW_ERROR_DEG = 45.0
DEFAULT_SHORT_HORIZON_V2_ACTIVE_PROJECTION_M = 1.0
DEFAULT_SHORT_HORIZON_V2_FAR_GOAL_SIDE_PROJECTION_M = 2.5
DEFAULT_SHORT_HORIZON_V2_FAR_GOAL_SIDE_LATERAL_ERROR_M = 1.3
DEFAULT_SHORT_HORIZON_V2_REFLANK_COMMIT_S = 1.0

SHORT_HORIZON_BASELINE_OBJECTIVE = "pre_stage_pose"
SHORT_HORIZON_ESCAPE_REGION_OBJECTIVE = "escape_region"
SHORT_HORIZON_REFLANK_STRATEGIES = {"reset_reflank_left", "reset_reflank_right"}
SHORT_HORIZON_DIRECT_ESCAPE_STRATEGIES = {"hold", "reverse_straight", "reverse_direct_heading"}


@dataclass(frozen=True)
class ShortHorizonProjection:
    strategy_name: str
    command: PlaceControlCommand
    objective_name: str
    progress_score: float
    score_key: tuple[float, float, float, float, float]
    projected_projection_gain: float
    projected_lateral_gain: float
    projected_distance_gain: float
    projected_robot_pose: dict[str, float]
    projected_snapshot: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ShortHorizonDecision:
    active: bool
    strategy_name: str = ""
    objective_name: str = ""
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


def short_horizon_pre_stage_active(
    snapshot: dict[str, Any] | None,
    *,
    control_family: str = "short_horizon_v1",
) -> bool:
    if not isinstance(snapshot, dict):
        return False
    if bool(snapshot.get("pre_stage_pose_reached", False)):
        return False
    if float(snapshot.get("yaw_error_deg", 0.0) or 0.0) > DEFAULT_SHORT_HORIZON_MAX_ACTIVE_YAW_ERROR_DEG:
        return False
    robot_on_goal_side = bool(snapshot.get("robot_on_goal_side", False))
    robot_longitudinal_projection_m = float(snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0)
    if control_family == "short_horizon_v2":
        return robot_on_goal_side or robot_longitudinal_projection_m > DEFAULT_SHORT_HORIZON_V2_ACTIVE_PROJECTION_M
    return robot_on_goal_side or robot_longitudinal_projection_m > -0.05


def _apply_rollout_segment(
    *,
    x_m: float,
    y_m: float,
    yaw_rad: float,
    command: PlaceControlCommand,
    duration_s: float,
    step_s: float,
) -> tuple[float, float, float]:
    remaining_s = max(float(duration_s), 0.0)
    while remaining_s > 1.0e-9:
        dt_s = min(float(step_s), remaining_s)
        x_m += float(command.linear_x) * math.cos(yaw_rad) * dt_s
        y_m += float(command.linear_x) * math.sin(yaw_rad) * dt_s
        yaw_rad = normalize_angle(yaw_rad + (float(command.angular_z) * dt_s))
        remaining_s -= dt_s
    return x_m, y_m, yaw_rad


def _rollout_pose(
    robot_pose: dict[str, Any],
    command: PlaceControlCommand,
    *,
    horizon_s: float = DEFAULT_SHORT_HORIZON_HORIZON_S,
    step_s: float = DEFAULT_SHORT_HORIZON_STEP_S,
    segments: tuple[tuple[PlaceControlCommand, float], ...] | None = None,
) -> dict[str, float] | None:
    robot_xyyaw = world_pose_xyyaw(robot_pose)
    if robot_xyyaw is None:
        return None
    x_m, y_m, yaw_rad = robot_xyyaw
    rollout_segments = segments or ((command, float(horizon_s)),)
    for segment_command, duration_s in rollout_segments:
        x_m, y_m, yaw_rad = _apply_rollout_segment(
            x_m=x_m,
            y_m=y_m,
            yaw_rad=yaw_rad,
            command=segment_command,
            duration_s=float(duration_s),
            step_s=float(step_s),
        )
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
    *,
    control_family: str,
) -> list[tuple[str, PlaceControlCommand, str, tuple[tuple[PlaceControlCommand, float], ...] | None, float, float]]:
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
            SHORT_HORIZON_BASELINE_OBJECTIVE,
            None,
            DEFAULT_SHORT_HORIZON_HORIZON_S,
            DEFAULT_SHORT_HORIZON_STEP_S,
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
            SHORT_HORIZON_BASELINE_OBJECTIVE,
            None,
            DEFAULT_SHORT_HORIZON_HORIZON_S,
            DEFAULT_SHORT_HORIZON_STEP_S,
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
            SHORT_HORIZON_BASELINE_OBJECTIVE,
            None,
            DEFAULT_SHORT_HORIZON_HORIZON_S,
            DEFAULT_SHORT_HORIZON_STEP_S,
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
            SHORT_HORIZON_BASELINE_OBJECTIVE,
            None,
            DEFAULT_SHORT_HORIZON_HORIZON_S,
            DEFAULT_SHORT_HORIZON_STEP_S,
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
            SHORT_HORIZON_BASELINE_OBJECTIVE,
            None,
            DEFAULT_SHORT_HORIZON_HORIZON_S,
            DEFAULT_SHORT_HORIZON_STEP_S,
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
            SHORT_HORIZON_BASELINE_OBJECTIVE,
            None,
            DEFAULT_SHORT_HORIZON_HORIZON_S,
            DEFAULT_SHORT_HORIZON_STEP_S,
        ),
    ]
    pre_stage_pose_world = snapshot.get("pre_stage_pose_world", {}) if isinstance(snapshot.get("pre_stage_pose_world"), dict) else {}
    direct_command = _direct_reverse_heading_command(robot_pose, pre_stage_pose_world)
    if direct_command is not None:
        candidates.append(
            (
                "reverse_direct_heading",
                direct_command,
                SHORT_HORIZON_BASELINE_OBJECTIVE,
                None,
                DEFAULT_SHORT_HORIZON_HORIZON_S,
                DEFAULT_SHORT_HORIZON_STEP_S,
            )
        )
    if control_family == "short_horizon_v2":
        reflank_left_hard = PlaceControlCommand(
            mode="pre_stage_escape_goal_side",
            linear_x=DEFAULT_SHORT_HORIZON_LINEAR_X_MPS,
            angular_z=0.8,
            target_speed_scale=0.0,
            rationale="Short-horizon v2 chose a committed reverse-left reflank macro to clear the goal side.",
        )
        reflank_left_soft = PlaceControlCommand(
            mode="pre_stage_escape_goal_side",
            linear_x=DEFAULT_SHORT_HORIZON_LINEAR_X_MPS,
            angular_z=0.25,
            target_speed_scale=0.0,
            rationale="Short-horizon v2 is finishing the reverse-left reflank macro.",
        )
        reflank_right_hard = PlaceControlCommand(
            mode="pre_stage_escape_goal_side",
            linear_x=DEFAULT_SHORT_HORIZON_LINEAR_X_MPS,
            angular_z=-0.8,
            target_speed_scale=0.0,
            rationale="Short-horizon v2 chose a committed reverse-right reflank macro to clear the goal side.",
        )
        reflank_right_soft = PlaceControlCommand(
            mode="pre_stage_escape_goal_side",
            linear_x=DEFAULT_SHORT_HORIZON_LINEAR_X_MPS,
            angular_z=-0.25,
            target_speed_scale=0.0,
            rationale="Short-horizon v2 is finishing the reverse-right reflank macro.",
        )
        candidates.extend(
            [
                (
                    "reset_reflank_left",
                    reflank_left_hard,
                    SHORT_HORIZON_ESCAPE_REGION_OBJECTIVE,
                    ((reflank_left_hard, 1.0), (reflank_left_soft, 1.0)),
                    DEFAULT_SHORT_HORIZON_V2_HORIZON_S,
                    DEFAULT_SHORT_HORIZON_V2_STEP_S,
                ),
                (
                    "reset_reflank_right",
                    reflank_right_hard,
                    SHORT_HORIZON_ESCAPE_REGION_OBJECTIVE,
                    ((reflank_right_hard, 1.0), (reflank_right_soft, 1.0)),
                    DEFAULT_SHORT_HORIZON_V2_HORIZON_S,
                    DEFAULT_SHORT_HORIZON_V2_STEP_S,
                ),
            ]
        )
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
    objective_name: str = SHORT_HORIZON_BASELINE_OBJECTIVE,
    horizon_s: float = DEFAULT_SHORT_HORIZON_HORIZON_S,
    step_s: float = DEFAULT_SHORT_HORIZON_STEP_S,
    segments: tuple[tuple[PlaceControlCommand, float], ...] | None = None,
) -> ShortHorizonProjection | None:
    current_snapshot = snapshot if isinstance(snapshot, dict) else pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone)
    if not isinstance(current_snapshot, dict):
        return None
    projected_robot_pose = _rollout_pose(
        robot_pose,
        command,
        horizon_s=horizon_s,
        step_s=step_s,
        segments=segments,
    )
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
    # Keep the scalar debug score aligned with the lexicographic selector so
    # the reported "best" strategy reflects the same escape-region priorities.
    progress_score = (
        (score_key[0] * 1000.0)
        + (score_key[1] * 100.0)
        + (score_key[2] * 10.0)
        + score_key[3]
        + score_key[4]
    )
    return ShortHorizonProjection(
        strategy_name=strategy_name,
        command=command,
        objective_name=str(objective_name),
        progress_score=round(progress_score, 6),
        score_key=score_key,
        projected_projection_gain=round(projection_gain, 6),
        projected_lateral_gain=round(lateral_gain, 6),
        projected_distance_gain=round(distance_gain, 6),
        projected_robot_pose=projected_robot_pose,
        projected_snapshot=projected_snapshot,
    )


def decide_short_horizon_pre_stage_command(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    snapshot: dict[str, Any] | None = None,
    control_family: str = "short_horizon_v1",
    previous_strategy_name: str = "",
    stall_s: float = 0.0,
    strategy_elapsed_s: float = 0.0,
) -> ShortHorizonDecision:
    current_snapshot = snapshot if isinstance(snapshot, dict) else pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone)
    if not short_horizon_pre_stage_active(current_snapshot, control_family=control_family):
        return ShortHorizonDecision(active=False)
    family = str(control_family or "short_horizon_v1").strip().lower()
    robot_on_goal_side = bool(current_snapshot.get("robot_on_goal_side", False))
    robot_longitudinal_projection_m = float(current_snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0)
    robot_lateral_error_m = float(current_snapshot.get("robot_lateral_error_m", 0.0) or 0.0)
    far_goal_side_escape = bool(
        family == "short_horizon_v2"
        and robot_on_goal_side
        and robot_longitudinal_projection_m >= DEFAULT_SHORT_HORIZON_V2_FAR_GOAL_SIDE_PROJECTION_M
        and robot_lateral_error_m >= DEFAULT_SHORT_HORIZON_V2_FAR_GOAL_SIDE_LATERAL_ERROR_M
    )
    projections = [
        project_short_horizon_command(
            robot_pose,
            ball_pose,
            zone=zone,
            command=command,
            strategy_name=strategy_name,
            snapshot=current_snapshot,
            previous_strategy_name=previous_strategy_name,
            objective_name=objective_name,
            horizon_s=horizon_s,
            step_s=step_s,
            segments=segments,
        )
        for strategy_name, command, objective_name, segments, horizon_s, step_s in _candidate_commands(
            robot_pose,
            current_snapshot,
            control_family=family,
        )
    ]
    valid_projections = [item for item in projections if isinstance(item, ShortHorizonProjection)]
    if not valid_projections:
        return ShortHorizonDecision(active=False)
    if far_goal_side_escape:
        valid_projections = [
            item
            for item in valid_projections
            if item.strategy_name not in SHORT_HORIZON_DIRECT_ESCAPE_STRATEGIES
        ]
    if (
        family == "short_horizon_v2"
        and previous_strategy_name in SHORT_HORIZON_REFLANK_STRATEGIES
        and float(strategy_elapsed_s) < DEFAULT_SHORT_HORIZON_V2_REFLANK_COMMIT_S
        and robot_on_goal_side
    ):
        committed_projection = next(
            (item for item in valid_projections if item.strategy_name == previous_strategy_name),
            None,
        )
        if committed_projection is not None:
            return ShortHorizonDecision(
                active=True,
                strategy_name=committed_projection.strategy_name,
                objective_name=committed_projection.objective_name,
                progress_score=committed_projection.progress_score,
                command=committed_projection.command,
                projection=committed_projection,
            )
    best_projection = max(valid_projections, key=lambda item: (item.score_key, item.progress_score, item.strategy_name))
    current_projection = next(
        (item for item in valid_projections if item.strategy_name == previous_strategy_name),
        None,
    )
    if (
        family == "short_horizon_v2"
        and robot_on_goal_side
        and float(stall_s) >= DEFAULT_SHORT_HORIZON_FREE_SWITCH_STALL_S
    ):
        alternate_projections = [
            item for item in valid_projections if item.strategy_name != previous_strategy_name
        ]
        if previous_strategy_name in {"reverse_direct_heading", "reverse_straight"} and far_goal_side_escape:
            reflank_projection = max(
                (
                    item
                    for item in alternate_projections
                    if item.strategy_name in SHORT_HORIZON_REFLANK_STRATEGIES
                ),
                key=lambda item: (item.score_key, item.progress_score, item.strategy_name),
                default=None,
            )
            if reflank_projection is not None:
                best_projection = reflank_projection
        elif alternate_projections and best_projection.strategy_name == previous_strategy_name:
            best_projection = max(
                alternate_projections,
                key=lambda item: (item.score_key, item.progress_score, item.strategy_name),
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
        objective_name=best_projection.objective_name,
        progress_score=best_projection.progress_score,
        command=best_projection.command,
        projection=best_projection,
    )
