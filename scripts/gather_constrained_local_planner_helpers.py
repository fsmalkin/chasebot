#!/usr/bin/env python3
"""Constrained local pre-stage planner for gather reacquisition."""

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


CONSTRAINED_LOCAL_PLANNER_CONTROL_FAMILY = "constrained_local_planner_v1"
CONSTRAINED_LOCAL_PLANNER_OBJECTIVE = "constrained_local_planner"

REJECTION_PREDICTED_BALL_CONTACT = "predicted_ball_contact"
REJECTION_DEEPER_GOAL_SIDE = "deeper_goal_side"
REJECTION_WORSE_HANDOFF_READINESS = "worse_handoff_readiness"
REJECTION_INVALID_ROLLOUT = "invalid_rollout"

DEFAULT_CONSTRAINED_LOCAL_HORIZON_S = 1.4
DEFAULT_CONSTRAINED_LOCAL_STEP_S = 0.20
DEFAULT_CONSTRAINED_LOCAL_MIN_BALL_CLEARANCE_M = 0.58
DEFAULT_CONSTRAINED_LOCAL_RELEASE_DISTANCE_M = 1.25
DEFAULT_CONSTRAINED_LOCAL_RELEASE_LATERAL_M = 0.75
DEFAULT_CONSTRAINED_LOCAL_RELEASE_PROJECTION_M = 0.10
DEFAULT_CONSTRAINED_LOCAL_BALL_MOTION_TOLERANCE_M = 0.035
DEFAULT_CONSTRAINED_LOCAL_STALL_ACTIVATION_S = 1.0


@dataclass(frozen=True)
class ConstrainedLocalPlannerDecision:
    active: bool
    strategy_name: str = ""
    objective_name: str = ""
    progress_score: float | None = None
    command: PlaceControlCommand | None = None
    projected_projection_gain: float | None = None
    projected_lateral_gain: float | None = None
    projected_distance_gain: float | None = None
    candidate_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    rejection_reasons: tuple[str, ...] = ()
    projected_snapshot: dict[str, Any] | None = None
    release_reason: str = ""
    min_ball_clearance_m: float | None = None
    ball_motion_m: float | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.command is not None:
            payload["command"] = self.command.to_dict()
        payload["rejection_reasons"] = list(self.rejection_reasons)
        return payload


@dataclass(frozen=True)
class _CandidateProjection:
    strategy_name: str
    command: PlaceControlCommand
    progress_score: float
    score_key: tuple[float, float, float, float, float, float, float]
    projected_robot_pose: dict[str, float]
    projected_snapshot: dict[str, Any]
    projected_projection_gain: float
    projected_lateral_gain: float
    projected_distance_gain: float
    projected_yaw_gain: float
    min_ball_clearance_m: float
    rejection_reasons: tuple[str, ...]


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


def constrained_local_planner_release_reason(
    snapshot: dict[str, Any] | None,
    *,
    ball_motion_m: float | None = None,
) -> str:
    current_snapshot = _valid_snapshot(snapshot)
    if current_snapshot is None:
        return "missing_pre_stage_geometry"
    if bool(current_snapshot.get("pre_stage_pose_reached", False)):
        return "pre_stage_handoff_ready"
    if ball_motion_m is not None and float(ball_motion_m) > DEFAULT_CONSTRAINED_LOCAL_BALL_MOTION_TOLERANCE_M:
        return ""
    robot_on_goal_side = bool(current_snapshot.get("robot_on_goal_side", False))
    projection_m = float(current_snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0)
    lateral_m = float(current_snapshot.get("robot_lateral_error_m", 0.0) or 0.0)
    distance_m = float(current_snapshot.get("pre_stage_pose_distance_m", 0.0) or 0.0)
    if (
        not robot_on_goal_side
        and projection_m <= DEFAULT_CONSTRAINED_LOCAL_RELEASE_PROJECTION_M
        and lateral_m <= DEFAULT_CONSTRAINED_LOCAL_RELEASE_LATERAL_M
        and distance_m <= DEFAULT_CONSTRAINED_LOCAL_RELEASE_DISTANCE_M
    ):
        return "baseline_pre_stage_traversal_ready"
    return ""


def constrained_local_planner_pre_stage_active(
    snapshot: dict[str, Any] | None,
    *,
    stall_s: float = 0.0,
    ball_motion_m: float | None = None,
) -> bool:
    current_snapshot = _valid_snapshot(snapshot)
    if current_snapshot is None:
        return False
    if constrained_local_planner_release_reason(current_snapshot, ball_motion_m=ball_motion_m):
        return False
    robot_on_goal_side = bool(current_snapshot.get("robot_on_goal_side", False))
    distance_m = float(current_snapshot.get("pre_stage_pose_distance_m", 0.0) or 0.0)
    return bool(
        robot_on_goal_side
        or distance_m > DEFAULT_CONSTRAINED_LOCAL_RELEASE_DISTANCE_M
        or float(stall_s) >= DEFAULT_CONSTRAINED_LOCAL_STALL_ACTIVATION_S
    )


def _bounded_command(
    *,
    strategy_name: str,
    linear_x: float,
    angular_z: float,
    target_speed_scale: float,
    rationale: str,
) -> PlaceControlCommand:
    return PlaceControlCommand(
        mode="constrained_local_pre_stage",
        linear_x=round(clamp(linear_x, -0.14, 0.22), 6),
        angular_z=round(clamp(angular_z, -0.75, 0.75), 6),
        target_speed_scale=round(clamp(target_speed_scale, 0.0, 1.0), 6),
        rationale=f"Constrained local planner {strategy_name}: {rationale}",
    )


def _candidate_commands(
    snapshot: dict[str, Any],
    *,
    previous_strategy_name: str = "",
) -> list[tuple[str, PlaceControlCommand]]:
    lateral_signed_m = float(snapshot.get("robot_lateral_signed_m", 0.0) or 0.0)
    preferred_turn_sign = -1.0 if lateral_signed_m > 0.0 else 1.0
    if previous_strategy_name.endswith("_right"):
        preferred_turn_sign = -1.0
    elif previous_strategy_name.endswith("_left"):
        preferred_turn_sign = 1.0

    side_order = (preferred_turn_sign, -preferred_turn_sign)
    candidates: list[tuple[str, PlaceControlCommand]] = []
    for side in side_order:
        suffix = "left" if side > 0.0 else "right"
        candidates.extend(
            [
                (
                    f"advance_{suffix}",
                    _bounded_command(
                        strategy_name=f"advance_{suffix}",
                        linear_x=0.18,
                        angular_z=0.42 * side,
                        target_speed_scale=0.75,
                        rationale="advance on a shallow arc only while predicted ball clearance stays safe.",
                    ),
                ),
                (
                    f"wide_{suffix}",
                    _bounded_command(
                        strategy_name=f"wide_{suffix}",
                        linear_x=0.14,
                        angular_z=0.68 * side,
                        target_speed_scale=0.65,
                        rationale="open lateral clearance before approaching the behind-ball corridor.",
                    ),
                ),
                (
                    f"turn_{suffix}",
                    _bounded_command(
                        strategy_name=f"turn_{suffix}",
                        linear_x=0.0,
                        angular_z=0.62 * side,
                        target_speed_scale=0.0,
                        rationale="rotate in place when translation would violate ball-clearance constraints.",
                    ),
                ),
                (
                    f"reverse_{suffix}",
                    _bounded_command(
                        strategy_name=f"reverse_{suffix}",
                        linear_x=-0.10,
                        angular_z=0.46 * side,
                        target_speed_scale=0.0,
                        rationale="back out of a near-ball or wrong-side posture without pushing the ball.",
                    ),
                ),
            ]
        )
    return candidates


def _rollout_samples(
    robot_pose: dict[str, Any],
    command: PlaceControlCommand,
    *,
    horizon_s: float = DEFAULT_CONSTRAINED_LOCAL_HORIZON_S,
    step_s: float = DEFAULT_CONSTRAINED_LOCAL_STEP_S,
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
    return min(math.hypot(float(sample["x"]) - ball_x, float(sample["y"]) - ball_y) for sample in samples)


def _projection_for_candidate(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    snapshot: dict[str, Any],
    strategy_name: str,
    command: PlaceControlCommand,
    previous_strategy_name: str,
) -> _CandidateProjection:
    samples = _rollout_samples(robot_pose, command)
    if not samples:
        return _CandidateProjection(
            strategy_name=strategy_name,
            command=command,
            progress_score=-1.0e9,
            score_key=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            projected_robot_pose={},
            projected_snapshot={},
            projected_projection_gain=0.0,
            projected_lateral_gain=0.0,
            projected_distance_gain=0.0,
            projected_yaw_gain=0.0,
            min_ball_clearance_m=0.0,
            rejection_reasons=(REJECTION_INVALID_ROLLOUT,),
        )
    projected_robot_pose = samples[-1]
    projected_snapshot = pre_stage_arrival_snapshot(projected_robot_pose, ball_pose, zone=zone)
    projected_snapshot = _valid_snapshot(projected_snapshot)
    if projected_snapshot is None:
        return _CandidateProjection(
            strategy_name=strategy_name,
            command=command,
            progress_score=-1.0e9,
            score_key=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            projected_robot_pose=projected_robot_pose,
            projected_snapshot={},
            projected_projection_gain=0.0,
            projected_lateral_gain=0.0,
            projected_distance_gain=0.0,
            projected_yaw_gain=0.0,
            min_ball_clearance_m=0.0,
            rejection_reasons=(REJECTION_INVALID_ROLLOUT,),
        )

    current_projection_m = float(snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0)
    projected_projection_m = float(projected_snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0)
    current_lateral_m = float(snapshot.get("robot_lateral_error_m", 0.0) or 0.0)
    projected_lateral_m = float(projected_snapshot.get("robot_lateral_error_m", 0.0) or 0.0)
    current_distance_m = float(snapshot.get("pre_stage_pose_distance_m", 0.0) or 0.0)
    projected_distance_m = float(projected_snapshot.get("pre_stage_pose_distance_m", 0.0) or 0.0)
    current_yaw_error_deg = float(snapshot.get("yaw_error_deg", 0.0) or 0.0)
    projected_yaw_error_deg = float(projected_snapshot.get("yaw_error_deg", 0.0) or 0.0)

    projection_gain = current_projection_m - projected_projection_m
    lateral_gain = current_lateral_m - projected_lateral_m
    distance_gain = current_distance_m - projected_distance_m
    yaw_gain = current_yaw_error_deg - projected_yaw_error_deg
    min_clearance = _min_ball_clearance(samples, ball_pose)
    min_clearance_m = round(float(min_clearance), 6) if min_clearance is not None else 0.0

    rejection_reasons: list[str] = []
    if min_clearance is None or min_clearance < DEFAULT_CONSTRAINED_LOCAL_MIN_BALL_CLEARANCE_M:
        rejection_reasons.append(REJECTION_PREDICTED_BALL_CONTACT)
    if projected_projection_m > current_projection_m + 0.04:
        rejection_reasons.append(REJECTION_DEEPER_GOAL_SIDE)
    if (
        distance_gain < -0.08
        and lateral_gain < -0.04
        and yaw_gain < -3.0
        and not bool(projected_snapshot.get("pre_stage_pose_reached", False))
    ):
        rejection_reasons.append(REJECTION_WORSE_HANDOFF_READINESS)

    leaves_goal_side = not bool(projected_snapshot.get("robot_on_goal_side", False))
    stays_with_previous = 1.0 if previous_strategy_name and previous_strategy_name == strategy_name else 0.0
    translation_bias = 1.0 if abs(float(command.linear_x)) > 1.0e-6 else 0.0
    score_key = (
        1.0 if leaves_goal_side else 0.0,
        round(projection_gain, 6),
        round(distance_gain, 6),
        round(lateral_gain, 6),
        round(yaw_gain / 180.0, 6),
        round(min_clearance_m / 10.0, 6),
        round((stays_with_previous * 0.05) + (translation_bias * 0.01), 6),
    )
    progress_score = (
        (score_key[0] * 1000.0)
        + (score_key[1] * 120.0)
        + (score_key[2] * 40.0)
        + (score_key[3] * 25.0)
        + (score_key[4] * 10.0)
        + score_key[5]
        + score_key[6]
    )
    return _CandidateProjection(
        strategy_name=strategy_name,
        command=command,
        progress_score=round(progress_score, 6),
        score_key=score_key,
        projected_robot_pose=projected_robot_pose,
        projected_snapshot=projected_snapshot,
        projected_projection_gain=round(projection_gain, 6),
        projected_lateral_gain=round(lateral_gain, 6),
        projected_distance_gain=round(distance_gain, 6),
        projected_yaw_gain=round(yaw_gain, 6),
        min_ball_clearance_m=min_clearance_m,
        rejection_reasons=tuple(rejection_reasons),
    )


def _ordered_unique(values: list[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    for value in values:
        if value and value not in ordered:
            ordered.append(value)
    return tuple(ordered)


def decide_constrained_local_pre_stage_command(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    snapshot: dict[str, Any] | None = None,
    previous_strategy_name: str = "",
    stall_s: float = 0.0,
    strategy_elapsed_s: float = 0.0,
    ball_motion_m: float | None = None,
) -> ConstrainedLocalPlannerDecision:
    _ = strategy_elapsed_s
    current_snapshot = (
        _valid_snapshot(snapshot)
        if snapshot is not None
        else _valid_snapshot(pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone))
    )
    release_reason = constrained_local_planner_release_reason(current_snapshot, ball_motion_m=ball_motion_m)
    if current_snapshot is None or release_reason:
        return ConstrainedLocalPlannerDecision(
            active=False,
            release_reason=release_reason,
            ball_motion_m=ball_motion_m,
        )
    if not constrained_local_planner_pre_stage_active(
        current_snapshot,
        stall_s=stall_s,
        ball_motion_m=ball_motion_m,
    ):
        return ConstrainedLocalPlannerDecision(
            active=False,
            release_reason="baseline_control_preferred",
            ball_motion_m=ball_motion_m,
        )

    candidate_payloads = _candidate_commands(current_snapshot, previous_strategy_name=previous_strategy_name)
    projections = [
        _projection_for_candidate(
            robot_pose,
            ball_pose,
            zone=zone,
            snapshot=current_snapshot,
            strategy_name=strategy_name,
            command=command,
            previous_strategy_name=previous_strategy_name,
        )
        for strategy_name, command in candidate_payloads
    ]
    accepted = [projection for projection in projections if not projection.rejection_reasons]
    rejection_reasons = _ordered_unique(
        [reason for projection in projections for reason in projection.rejection_reasons]
    )
    if not accepted:
        return ConstrainedLocalPlannerDecision(
            active=False,
            candidate_count=len(projections),
            accepted_count=0,
            rejected_count=len(projections),
            rejection_reasons=rejection_reasons,
            release_reason="no_safe_local_candidate",
            ball_motion_m=ball_motion_m,
        )

    best_projection = max(
        accepted,
        key=lambda projection: (projection.score_key, projection.progress_score),
    )
    return ConstrainedLocalPlannerDecision(
        active=True,
        strategy_name=best_projection.strategy_name,
        objective_name=CONSTRAINED_LOCAL_PLANNER_OBJECTIVE,
        progress_score=best_projection.progress_score,
        command=best_projection.command,
        projected_projection_gain=best_projection.projected_projection_gain,
        projected_lateral_gain=best_projection.projected_lateral_gain,
        projected_distance_gain=best_projection.projected_distance_gain,
        candidate_count=len(projections),
        accepted_count=len(accepted),
        rejected_count=len(projections) - len(accepted),
        rejection_reasons=rejection_reasons,
        projected_snapshot=best_projection.projected_snapshot,
        release_reason="",
        min_ball_clearance_m=best_projection.min_ball_clearance_m,
        ball_motion_m=ball_motion_m,
    )
