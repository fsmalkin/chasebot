#!/usr/bin/env python3
"""Deterministic region-funnel helpers for pre-stage gather recovery."""

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


REGION_FUNNEL_CONTROL_FAMILY = "region_funnel_v1"

REGION_FUNNEL_OBJECTIVE = "region_funnel"
SCRIPTED_MANEUVER_FALLBACK_OBJECTIVE = "scripted_maneuver_fallback"

DEFAULT_REGION_FUNNEL_HORIZON_S = 1.4
DEFAULT_REGION_FUNNEL_STEP_S = 0.35
DEFAULT_REGION_FUNNEL_LINEAR_X_MPS = -0.16
DEFAULT_REGION_FUNNEL_RECOVER_LINEAR_X_MPS = -0.12
DEFAULT_REGION_FUNNEL_MAX_ANGULAR_Z = 0.75
DEFAULT_REGION_FUNNEL_SOFT_ANGULAR_Z = 0.28
DEFAULT_REGION_FUNNEL_HARD_ANGULAR_Z = 0.62
DEFAULT_REGION_FUNNEL_STALL_FALLBACK_S = 1.25
DEFAULT_REGION_FUNNEL_FAR_PROJECTION_M = 1.75
DEFAULT_REGION_FUNNEL_WIDE_LATERAL_M = 0.75
DEFAULT_REGION_FUNNEL_COMMIT_S = 0.8
DEFAULT_REGION_FUNNEL_MAX_ACTIVE_YAW_ERROR_DEG = 45.0

REGION_FUNNEL_STRATEGIES = {"funnel_reacquire", "funnel_reverse_clear"}
SCRIPTED_REGION_FUNNEL_FALLBACK_STRATEGIES = {"scripted_reflank_left", "scripted_reflank_right"}


@dataclass(frozen=True)
class RegionFunnelDecision:
    active: bool
    strategy_name: str = ""
    objective_name: str = ""
    progress_score: float | None = None
    command: PlaceControlCommand | None = None
    projected_projection_gain: float | None = None
    projected_lateral_gain: float | None = None
    projected_distance_gain: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class _RegionFunnelProjection:
    strategy_name: str
    objective_name: str
    command: PlaceControlCommand
    progress_score: float
    score_key: tuple[float, float, float, float, float]
    projected_projection_gain: float
    projected_lateral_gain: float
    projected_distance_gain: float


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


def _active_snapshot(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    snapshot: dict[str, Any] | None,
) -> dict[str, Any] | None:
    current_snapshot = (
        _valid_snapshot(snapshot)
        if snapshot is not None
        else _valid_snapshot(pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone))
    )
    if current_snapshot is None:
        return None
    if bool(current_snapshot.get("pre_stage_pose_reached", False)):
        return None
    if float(current_snapshot.get("yaw_error_deg", 0.0) or 0.0) > DEFAULT_REGION_FUNNEL_MAX_ACTIVE_YAW_ERROR_DEG:
        return None
    return current_snapshot


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
    horizon_s: float = DEFAULT_REGION_FUNNEL_HORIZON_S,
    step_s: float = DEFAULT_REGION_FUNNEL_STEP_S,
    segments: tuple[tuple[PlaceControlCommand, float], ...] | None = None,
) -> dict[str, float] | None:
    robot_xyyaw = world_pose_xyyaw(robot_pose)
    if robot_xyyaw is None:
        return None
    x_m, y_m, yaw_rad = robot_xyyaw
    for segment_command, duration_s in segments or ((command, horizon_s),):
        x_m, y_m, yaw_rad = _apply_rollout_segment(
            x_m=x_m,
            y_m=y_m,
            yaw_rad=yaw_rad,
            command=segment_command,
            duration_s=duration_s,
            step_s=step_s,
        )
    return {"x": round(x_m, 6), "y": round(y_m, 6), "yaw": round(yaw_rad, 6)}


def _bounded_command(
    *,
    strategy_name: str,
    linear_x: float,
    angular_z: float,
    rationale: str,
) -> PlaceControlCommand:
    return PlaceControlCommand(
        mode="pre_stage_escape_goal_side",
        linear_x=round(clamp(linear_x, -0.18, 0.0), 6),
        angular_z=round(clamp(angular_z, -DEFAULT_REGION_FUNNEL_MAX_ANGULAR_Z, DEFAULT_REGION_FUNNEL_MAX_ANGULAR_Z), 6),
        target_speed_scale=0.0,
        rationale=f"Region-funnel {strategy_name}: {rationale}",
    )


def _candidate_commands(
    snapshot: dict[str, Any],
    *,
    stall_s: float,
) -> list[tuple[str, str, PlaceControlCommand, tuple[tuple[PlaceControlCommand, float], ...] | None]]:
    lateral_signed_m = float(snapshot.get("robot_lateral_signed_m", 0.0) or 0.0)
    projection_m = float(snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0)
    yaw_error_deg = float(snapshot.get("yaw_error_deg", 0.0) or 0.0)
    turn_sign = -1.0 if lateral_signed_m > 0.0 else 1.0
    if abs(lateral_signed_m) < 1.0e-6:
        turn_sign = -1.0 if projection_m >= 0.0 else 1.0

    reacquire_angular_z = turn_sign * clamp(
        0.22 + (abs(lateral_signed_m) * 0.25) + (abs(yaw_error_deg) * 0.003),
        DEFAULT_REGION_FUNNEL_SOFT_ANGULAR_Z,
        DEFAULT_REGION_FUNNEL_HARD_ANGULAR_Z,
    )
    reacquire = _bounded_command(
        strategy_name="funnel_reacquire",
        linear_x=DEFAULT_REGION_FUNNEL_RECOVER_LINEAR_X_MPS,
        angular_z=reacquire_angular_z,
        rationale="arc backward toward the behind-ball funnel while trimming lateral error.",
    )
    reverse_clear = _bounded_command(
        strategy_name="funnel_reverse_clear",
        linear_x=DEFAULT_REGION_FUNNEL_LINEAR_X_MPS,
        angular_z=0.0,
        rationale="reverse straight to clear excess goal-side projection.",
    )
    candidates: list[tuple[str, str, PlaceControlCommand, tuple[tuple[PlaceControlCommand, float], ...] | None]] = [
        ("funnel_reacquire", REGION_FUNNEL_OBJECTIVE, reacquire, None),
        ("funnel_reverse_clear", REGION_FUNNEL_OBJECTIVE, reverse_clear, None),
    ]

    fallback_needed = (
        float(stall_s) >= DEFAULT_REGION_FUNNEL_STALL_FALLBACK_S
        or projection_m >= DEFAULT_REGION_FUNNEL_FAR_PROJECTION_M
        or abs(lateral_signed_m) >= DEFAULT_REGION_FUNNEL_WIDE_LATERAL_M
    )
    if fallback_needed:
        left_hard = _bounded_command(
            strategy_name="scripted_reflank_left",
            linear_x=DEFAULT_REGION_FUNNEL_LINEAR_X_MPS,
            angular_z=DEFAULT_REGION_FUNNEL_MAX_ANGULAR_Z,
            rationale="scripted fallback reflanks left before re-entering the funnel.",
        )
        left_soft = _bounded_command(
            strategy_name="scripted_reflank_left",
            linear_x=DEFAULT_REGION_FUNNEL_RECOVER_LINEAR_X_MPS,
            angular_z=DEFAULT_REGION_FUNNEL_SOFT_ANGULAR_Z,
            rationale="scripted fallback settles the left reflank.",
        )
        right_hard = _bounded_command(
            strategy_name="scripted_reflank_right",
            linear_x=DEFAULT_REGION_FUNNEL_LINEAR_X_MPS,
            angular_z=-DEFAULT_REGION_FUNNEL_MAX_ANGULAR_Z,
            rationale="scripted fallback reflanks right before re-entering the funnel.",
        )
        right_soft = _bounded_command(
            strategy_name="scripted_reflank_right",
            linear_x=DEFAULT_REGION_FUNNEL_RECOVER_LINEAR_X_MPS,
            angular_z=-DEFAULT_REGION_FUNNEL_SOFT_ANGULAR_Z,
            rationale="scripted fallback settles the right reflank.",
        )
        candidates.extend(
            [
                (
                    "scripted_reflank_left",
                    SCRIPTED_MANEUVER_FALLBACK_OBJECTIVE,
                    left_hard,
                    ((left_hard, 0.8), (left_soft, 0.6)),
                ),
                (
                    "scripted_reflank_right",
                    SCRIPTED_MANEUVER_FALLBACK_OBJECTIVE,
                    right_hard,
                    ((right_hard, 0.8), (right_soft, 0.6)),
                ),
            ]
        )
    return candidates


def _project_command(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    snapshot: dict[str, Any],
    strategy_name: str,
    objective_name: str,
    command: PlaceControlCommand,
    previous_strategy_name: str,
    segments: tuple[tuple[PlaceControlCommand, float], ...] | None,
) -> _RegionFunnelProjection | None:
    projected_robot_pose = _rollout_pose(robot_pose, command, segments=segments)
    if projected_robot_pose is None:
        return None
    projected_snapshot = pre_stage_arrival_snapshot(projected_robot_pose, ball_pose, zone=zone)
    projected_snapshot = _valid_snapshot(projected_snapshot)
    if projected_snapshot is None:
        return None

    initial_projection_m = float(snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0)
    final_projection_m = float(projected_snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0)
    initial_lateral_error_m = float(snapshot.get("robot_lateral_error_m", 0.0) or 0.0)
    final_lateral_error_m = float(projected_snapshot.get("robot_lateral_error_m", 0.0) or 0.0)
    initial_distance_m = float(snapshot.get("pre_stage_pose_distance_m", 0.0) or 0.0)
    final_distance_m = float(projected_snapshot.get("pre_stage_pose_distance_m", 0.0) or 0.0)

    projection_gain = initial_projection_m - final_projection_m
    lateral_gain = initial_lateral_error_m - final_lateral_error_m
    distance_gain = initial_distance_m - final_distance_m
    leaves_goal_side = not bool(projected_snapshot.get("robot_on_goal_side", False))
    switch_bias = 0.02 if previous_strategy_name and previous_strategy_name == strategy_name else 0.0
    objective_bias = 0.01 if objective_name == REGION_FUNNEL_OBJECTIVE else 0.0
    score_key = (
        1.0 if leaves_goal_side else 0.0,
        round(projection_gain, 6),
        round(lateral_gain, 6),
        round(distance_gain, 6),
        round(switch_bias + objective_bias, 6),
    )
    progress_score = (
        (score_key[0] * 1000.0)
        + (score_key[1] * 100.0)
        + (score_key[2] * 20.0)
        + (score_key[3] * 5.0)
        + score_key[4]
    )
    return _RegionFunnelProjection(
        strategy_name=strategy_name,
        objective_name=objective_name,
        command=command,
        progress_score=round(progress_score, 6),
        score_key=score_key,
        projected_projection_gain=round(projection_gain, 6),
        projected_lateral_gain=round(lateral_gain, 6),
        projected_distance_gain=round(distance_gain, 6),
    )


def decide_region_funnel_pre_stage_command(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    snapshot: dict[str, Any] | None = None,
    previous_strategy_name: str = "",
    stall_s: float = 0.0,
    strategy_elapsed_s: float = 0.0,
) -> RegionFunnelDecision:
    current_snapshot = _active_snapshot(robot_pose, ball_pose, zone=zone, snapshot=snapshot)
    if current_snapshot is None:
        return RegionFunnelDecision(active=False)

    candidates = _candidate_commands(current_snapshot, stall_s=float(stall_s))
    projections = [
        _project_command(
            robot_pose,
            ball_pose,
            zone=zone,
            snapshot=current_snapshot,
            strategy_name=strategy_name,
            objective_name=objective_name,
            command=command,
            previous_strategy_name=previous_strategy_name,
            segments=segments,
        )
        for strategy_name, objective_name, command, segments in candidates
    ]
    valid_projections = [projection for projection in projections if projection is not None]
    if not valid_projections:
        return RegionFunnelDecision(active=False)

    if (
        previous_strategy_name in SCRIPTED_REGION_FUNNEL_FALLBACK_STRATEGIES
        and float(strategy_elapsed_s) < DEFAULT_REGION_FUNNEL_COMMIT_S
    ):
        committed_projection = next(
            (projection for projection in valid_projections if projection.strategy_name == previous_strategy_name),
            None,
        )
        if committed_projection is not None:
            return _decision_from_projection(committed_projection)

    if float(stall_s) >= DEFAULT_REGION_FUNNEL_STALL_FALLBACK_S:
        fallback_projections = [
            projection
            for projection in valid_projections
            if projection.strategy_name in SCRIPTED_REGION_FUNNEL_FALLBACK_STRATEGIES
        ]
        if fallback_projections:
            valid_projections = fallback_projections

    best_projection = max(
        valid_projections,
        key=lambda projection: (projection.score_key, projection.progress_score),
    )
    return _decision_from_projection(best_projection)


def _decision_from_projection(projection: _RegionFunnelProjection) -> RegionFunnelDecision:
    return RegionFunnelDecision(
        active=True,
        strategy_name=projection.strategy_name,
        objective_name=projection.objective_name,
        progress_score=projection.progress_score,
        command=projection.command,
        projected_projection_gain=projection.projected_projection_gain,
        projected_lateral_gain=projection.projected_lateral_gain,
        projected_distance_gain=projection.projected_distance_gain,
    )
