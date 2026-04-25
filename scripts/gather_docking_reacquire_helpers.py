#!/usr/bin/env python3
"""Deterministic docking-style pre-stage reacquire helper."""

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


DOCKING_REACQUIRE_CONTROL_FAMILY = "docking_reacquire_v1"
DOCKING_REACQUIRE_OBJECTIVE = "docking_reacquire"

DEFAULT_DOCKING_REACQUIRE_ENTRY_LATERAL_M = 0.75
DEFAULT_DOCKING_REACQUIRE_ENTRY_BEHIND_BIAS_M = 0.20
DEFAULT_DOCKING_REACQUIRE_MIN_BALL_CLEARANCE_M = 0.45
DEFAULT_DOCKING_REACQUIRE_RELEASE_DISTANCE_M = 0.75
DEFAULT_DOCKING_REACQUIRE_RELEASE_LATERAL_M = 0.30
DEFAULT_DOCKING_REACQUIRE_RELEASE_PROJECTION_M = -0.35
DEFAULT_DOCKING_REACQUIRE_RELEASE_YAW_DEG = 45.0
DEFAULT_DOCKING_REACQUIRE_BALL_MOTION_TOLERANCE_M = 0.035
DEFAULT_DOCKING_REACQUIRE_STALL_ACTIVATION_S = 0.80
DEFAULT_DOCKING_REACQUIRE_HORIZON_S = 1.20
DEFAULT_DOCKING_REACQUIRE_STEP_S = 0.20


@dataclass(frozen=True)
class DockingReacquireDecision:
    active: bool
    strategy_name: str = ""
    objective_name: str = ""
    progress_score: float | None = None
    command: PlaceControlCommand | None = None
    projected_projection_gain: float | None = None
    projected_lateral_gain: float | None = None
    projected_distance_gain: float | None = None
    projected_snapshot: dict[str, Any] | None = None
    release_reason: str = ""
    dock_pose: dict[str, float] | None = None
    side_sign: float | None = None
    target_distance_m: float | None = None
    target_heading_error_rad: float | None = None
    segment_ball_clearance_m: float | None = None
    min_ball_clearance_m: float | None = None
    ball_motion_m: float | None = None
    release_blockers: tuple[str, ...] = ()

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
    normal_x = -push_uy
    normal_y = push_ux
    return push_ux, push_uy, normal_x, normal_y, math.atan2(push_uy, push_ux)


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
        return math.hypot(px - ax, py - ay)
    t = clamp(((px - ax) * dx + (py - ay) * dy) / denom, 0.0, 1.0)
    nearest_x = ax + (t * dx)
    nearest_y = ay + (t * dy)
    return round(math.hypot(px - nearest_x, py - nearest_y), 6)


def _rollout_samples(
    robot_pose: dict[str, Any],
    command: PlaceControlCommand,
    *,
    horizon_s: float = DEFAULT_DOCKING_REACQUIRE_HORIZON_S,
    step_s: float = DEFAULT_DOCKING_REACQUIRE_STEP_S,
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


def _strategy_side_order(
    *,
    robot_pose: dict[str, Any],
    snapshot: dict[str, Any],
    pre_stage_pose: dict[str, Any],
    basis: tuple[float, float, float, float, float],
    previous_strategy_name: str,
) -> list[float]:
    if previous_strategy_name.endswith("_left"):
        return [1.0, -1.0]
    if previous_strategy_name.endswith("_right"):
        return [-1.0, 1.0]
    lateral_signed_m = float(snapshot.get("robot_lateral_signed_m", 0.0) or 0.0)
    if abs(lateral_signed_m) > 0.05:
        preferred = 1.0 if lateral_signed_m > 0.0 else -1.0
        return [preferred, -preferred]
    robot_xyyaw = world_pose_xyyaw(robot_pose)
    if robot_xyyaw is None:
        return [1.0, -1.0]
    _push_ux, _push_uy, normal_x, normal_y, _push_yaw = basis
    robot_x, robot_y, robot_yaw = robot_xyyaw

    def heading_cost(side: float) -> float:
        target_x = float(pre_stage_pose.get("x", 0.0) or 0.0) + (side * DEFAULT_DOCKING_REACQUIRE_ENTRY_LATERAL_M * normal_x)
        target_y = float(pre_stage_pose.get("y", 0.0) or 0.0) + (side * DEFAULT_DOCKING_REACQUIRE_ENTRY_LATERAL_M * normal_y)
        return abs(normalize_angle(math.atan2(target_y - robot_y, target_x - robot_x) - robot_yaw))

    return sorted([1.0, -1.0], key=lambda side: (heading_cost(side), -side))


def _dock_target_pose(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    snapshot: dict[str, Any],
    previous_strategy_name: str,
) -> tuple[dict[str, float], str, float | None, float | None]:
    basis = _push_basis(ball_pose, zone)
    pre_stage_pose = (
        dict(snapshot.get("pre_stage_pose_world", {}))
        if isinstance(snapshot.get("pre_stage_pose_world"), dict)
        else {}
    )
    if basis is None or point_xy(pre_stage_pose) is None:
        return {}, "missing_dock_pose", None, None
    push_ux, push_uy, normal_x, normal_y, _push_yaw = basis
    projection_m = float(snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0)
    robot_on_goal_side = bool(snapshot.get("robot_on_goal_side", False))
    need_entry_pose = bool(robot_on_goal_side or projection_m > DEFAULT_DOCKING_REACQUIRE_RELEASE_PROJECTION_M)
    if not need_entry_pose:
        segment_clearance = _segment_ball_clearance(robot_pose, pre_stage_pose, ball_pose)
        return (
            {
                "x": round(float(pre_stage_pose.get("x", 0.0) or 0.0), 6),
                "y": round(float(pre_stage_pose.get("y", 0.0) or 0.0), 6),
            },
            "docking_port",
            None,
            segment_clearance,
        )

    best: tuple[float, dict[str, float], str, float] | None = None
    for lateral_m in (
        DEFAULT_DOCKING_REACQUIRE_ENTRY_LATERAL_M,
        DEFAULT_DOCKING_REACQUIRE_ENTRY_LATERAL_M + 0.30,
    ):
        for side in _strategy_side_order(
            robot_pose=robot_pose,
            snapshot=snapshot,
            pre_stage_pose=pre_stage_pose,
            basis=basis,
            previous_strategy_name=previous_strategy_name,
        ):
            target_pose = {
                "x": round(
                    float(pre_stage_pose.get("x", 0.0) or 0.0)
                    + (side * lateral_m * normal_x)
                    - (DEFAULT_DOCKING_REACQUIRE_ENTRY_BEHIND_BIAS_M * push_ux),
                    6,
                ),
                "y": round(
                    float(pre_stage_pose.get("y", 0.0) or 0.0)
                    + (side * lateral_m * normal_y)
                    - (DEFAULT_DOCKING_REACQUIRE_ENTRY_BEHIND_BIAS_M * push_uy),
                    6,
                ),
            }
            clearance = _segment_ball_clearance(robot_pose, target_pose, ball_pose)
            if clearance is None:
                continue
            score = clearance - (0.05 * lateral_m)
            if best is None or score > best[0]:
                best = (
                    score,
                    target_pose,
                    "docking_entry_left" if side > 0.0 else "docking_entry_right",
                    side,
                )
            if clearance >= DEFAULT_DOCKING_REACQUIRE_MIN_BALL_CLEARANCE_M:
                return target_pose, "docking_entry_left" if side > 0.0 else "docking_entry_right", side, clearance
    if best is None:
        return {}, "missing_dock_pose", None, None
    _score, target_pose, target_kind, side = best
    return target_pose, target_kind, side, _segment_ball_clearance(robot_pose, target_pose, ball_pose)


def docking_reacquire_release_reason(
    snapshot: dict[str, Any] | None,
    *,
    ball_motion_m: float | None = None,
) -> str:
    current_snapshot = _valid_snapshot(snapshot)
    if current_snapshot is None:
        return "missing_pre_stage_geometry"
    if bool(current_snapshot.get("pre_stage_pose_reached", False)):
        return "pre_stage_handoff_ready"
    if ball_motion_m is not None and float(ball_motion_m) > DEFAULT_DOCKING_REACQUIRE_BALL_MOTION_TOLERANCE_M:
        return "ball_motion_guard"
    if docking_reacquire_release_blockers(current_snapshot, ball_motion_m=ball_motion_m):
        return ""
    return "baseline_pre_stage_traversal_ready"


def docking_reacquire_release_blockers(
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
    if ball_motion_m is not None and float(ball_motion_m) > DEFAULT_DOCKING_REACQUIRE_BALL_MOTION_TOLERANCE_M:
        blockers.append("ball_motion_guard")
    robot_on_goal_side = bool(current_snapshot.get("robot_on_goal_side", False))
    projection_m = float(current_snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0)
    lateral_m = float(current_snapshot.get("robot_lateral_error_m", 0.0) or 0.0)
    distance_m = float(current_snapshot.get("pre_stage_pose_distance_m", 0.0) or 0.0)
    yaw_error_deg = float(current_snapshot.get("yaw_error_deg", 0.0) or 0.0)
    if robot_on_goal_side:
        blockers.append("robot_on_goal_side")
    if projection_m > DEFAULT_DOCKING_REACQUIRE_RELEASE_PROJECTION_M:
        blockers.append("projection_not_cleared")
    if lateral_m > DEFAULT_DOCKING_REACQUIRE_RELEASE_LATERAL_M:
        blockers.append("lateral_not_converged")
    if distance_m > DEFAULT_DOCKING_REACQUIRE_RELEASE_DISTANCE_M:
        blockers.append("distance_not_converged")
    if yaw_error_deg > DEFAULT_DOCKING_REACQUIRE_RELEASE_YAW_DEG:
        blockers.append("yaw_not_aligned")
    return tuple(blockers)


def docking_reacquire_pre_stage_active(
    snapshot: dict[str, Any] | None,
    *,
    stall_s: float = 0.0,
    ball_motion_m: float | None = None,
) -> bool:
    current_snapshot = _valid_snapshot(snapshot)
    if current_snapshot is None:
        return False
    if docking_reacquire_release_reason(current_snapshot, ball_motion_m=ball_motion_m):
        return False
    if docking_reacquire_release_blockers(current_snapshot, ball_motion_m=ball_motion_m):
        return True
    robot_on_goal_side = bool(current_snapshot.get("robot_on_goal_side", False))
    projection_m = float(current_snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0)
    distance_m = float(current_snapshot.get("pre_stage_pose_distance_m", 0.0) or 0.0)
    return bool(
        robot_on_goal_side
        or projection_m > DEFAULT_DOCKING_REACQUIRE_RELEASE_PROJECTION_M
        or (
            float(stall_s) >= DEFAULT_DOCKING_REACQUIRE_STALL_ACTIVATION_S
            and distance_m > DEFAULT_DOCKING_REACQUIRE_RELEASE_DISTANCE_M
        )
    )


def _command_toward_target(
    robot_pose: dict[str, Any],
    target_pose: dict[str, float],
    *,
    target_kind: str,
    push_yaw_rad: float,
) -> tuple[PlaceControlCommand, float, float]:
    target_rel = relative_point_robot_frame(robot_pose, target_pose)
    robot_xyyaw = world_pose_xyyaw(robot_pose)
    if target_rel is None or robot_xyyaw is None:
        return (
            PlaceControlCommand(
                mode="docking_reacquire_pre_stage",
                linear_x=0.0,
                angular_z=0.0,
                target_speed_scale=0.0,
                rationale="Docking reacquire is holding because target geometry is unavailable.",
            ),
            0.0,
            0.0,
        )
    target_x_m, target_y_m = target_rel
    _robot_x, _robot_y, robot_yaw = robot_xyyaw
    target_distance_m = math.hypot(target_x_m, target_y_m)
    heading_error = math.atan2(target_y_m, max(target_x_m, 1.0e-6))
    push_yaw_error = normalize_angle(push_yaw_rad - robot_yaw)
    if target_x_m < -0.05 or abs(heading_error) > 1.05:
        angular = clamp(heading_error * 1.4, -0.65, 0.65)
        if abs(angular) < 0.18 and abs(heading_error) > 0.18:
            angular = 0.18 if heading_error >= 0.0 else -0.18
        return (
            PlaceControlCommand(
                mode="docking_reacquire_pre_stage",
                linear_x=0.0,
                angular_z=round(angular, 6),
                target_speed_scale=0.0,
                rationale="Docking reacquire turns toward the safe behind-ball docking pocket.",
            ),
            target_distance_m,
            heading_error,
        )
    if target_kind == "docking_port" and target_distance_m <= 0.35 and abs(push_yaw_error) > 0.35:
        angular = clamp(push_yaw_error * 0.9, -0.50, 0.50)
        return (
            PlaceControlCommand(
                mode="docking_reacquire_pre_stage",
                linear_x=0.0,
                angular_z=round(angular, 6),
                target_speed_scale=0.0,
                rationale="Docking reacquire aligns with the push line before handing back to baseline.",
            ),
            target_distance_m,
            heading_error,
        )
    linear = clamp(target_distance_m * 0.20, 0.05, 0.16)
    if abs(heading_error) > 0.45:
        linear = min(linear, 0.10)
    angular = clamp((target_y_m * 1.15) + (heading_error * 0.35) + (push_yaw_error * 0.08), -0.65, 0.65)
    return (
        PlaceControlCommand(
            mode="docking_reacquire_pre_stage",
            linear_x=round(linear, 6),
            angular_z=round(angular, 6),
            target_speed_scale=0.70,
            rationale="Docking reacquire drives toward a safe behind-ball docking pocket.",
        ),
        target_distance_m,
        heading_error,
    )


def decide_docking_reacquire_pre_stage_command(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    snapshot: dict[str, Any] | None = None,
    previous_strategy_name: str = "",
    stall_s: float = 0.0,
    strategy_elapsed_s: float = 0.0,
    ball_motion_m: float | None = None,
) -> DockingReacquireDecision:
    _ = strategy_elapsed_s
    current_snapshot = (
        _valid_snapshot(snapshot)
        if snapshot is not None
        else _valid_snapshot(pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone))
    )
    release_reason = docking_reacquire_release_reason(current_snapshot, ball_motion_m=ball_motion_m)
    release_blockers = docking_reacquire_release_blockers(current_snapshot, ball_motion_m=ball_motion_m)
    if current_snapshot is None or release_reason:
        return DockingReacquireDecision(
            active=False,
            release_reason=release_reason,
            ball_motion_m=ball_motion_m,
            release_blockers=release_blockers,
        )
    if not docking_reacquire_pre_stage_active(
        current_snapshot,
        stall_s=stall_s,
        ball_motion_m=ball_motion_m,
    ):
        return DockingReacquireDecision(
            active=False,
            release_reason="baseline_control_preferred",
            ball_motion_m=ball_motion_m,
            release_blockers=release_blockers,
        )

    basis = _push_basis(ball_pose, zone)
    if basis is None:
        return DockingReacquireDecision(
            active=False,
            release_reason="missing_pre_stage_geometry",
            ball_motion_m=ball_motion_m,
            release_blockers=release_blockers,
        )
    _push_ux, _push_uy, _normal_x, _normal_y, push_yaw_rad = basis
    dock_pose, target_kind, side_sign, segment_clearance_m = _dock_target_pose(
        robot_pose,
        ball_pose,
        zone=zone,
        snapshot=current_snapshot,
        previous_strategy_name=previous_strategy_name,
    )
    if not dock_pose:
        return DockingReacquireDecision(
            active=False,
            release_reason="missing_dock_pose",
            ball_motion_m=ball_motion_m,
            release_blockers=release_blockers,
        )

    command, target_distance_m, heading_error = _command_toward_target(
        robot_pose,
        dock_pose,
        target_kind=target_kind,
        push_yaw_rad=push_yaw_rad,
    )
    strategy_name = target_kind
    if segment_clearance_m is not None and segment_clearance_m < DEFAULT_DOCKING_REACQUIRE_MIN_BALL_CLEARANCE_M:
        command = PlaceControlCommand(
            mode="docking_reacquire_pre_stage",
            linear_x=0.0,
            angular_z=0.0,
            target_speed_scale=0.0,
            rationale="Docking reacquire is holding because the docking segment is too close to the ball.",
        )
        strategy_name = "docking_clearance_hold"

    samples = _rollout_samples(robot_pose, command)
    min_ball_clearance_m = _min_ball_clearance(samples, ball_pose)
    projected_robot_pose = samples[-1] if samples else {}
    projected_snapshot = (
        pre_stage_arrival_snapshot(projected_robot_pose, ball_pose, zone=zone)
        if projected_robot_pose
        else None
    )
    projected_snapshot = _valid_snapshot(projected_snapshot) or {}

    current_projection_m = float(current_snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0)
    projected_projection_m = float(projected_snapshot.get("robot_longitudinal_projection_m", current_projection_m) or 0.0)
    current_lateral_m = float(current_snapshot.get("robot_lateral_error_m", 0.0) or 0.0)
    projected_lateral_m = float(projected_snapshot.get("robot_lateral_error_m", current_lateral_m) or 0.0)
    current_distance_m = float(current_snapshot.get("pre_stage_pose_distance_m", 0.0) or 0.0)
    projected_distance_m = float(projected_snapshot.get("pre_stage_pose_distance_m", current_distance_m) or 0.0)
    projection_gain = round(current_projection_m - projected_projection_m, 6)
    lateral_gain = round(current_lateral_m - projected_lateral_m, 6)
    distance_gain = round(current_distance_m - projected_distance_m, 6)
    if (
        min_ball_clearance_m is not None
        and min_ball_clearance_m < DEFAULT_DOCKING_REACQUIRE_MIN_BALL_CLEARANCE_M
    ) or projected_projection_m > current_projection_m + 0.06:
        command = PlaceControlCommand(
            mode="docking_reacquire_pre_stage",
            linear_x=0.0,
            angular_z=0.0,
            target_speed_scale=0.0,
            rationale="Docking reacquire is holding because the projected command violates safety bounds.",
        )
        strategy_name = "docking_projection_hold"
        samples = _rollout_samples(robot_pose, command)
        min_ball_clearance_m = _min_ball_clearance(samples, ball_pose)
        projected_robot_pose = samples[-1] if samples else {}
        projected_snapshot = (
            pre_stage_arrival_snapshot(projected_robot_pose, ball_pose, zone=zone)
            if projected_robot_pose
            else None
        )
        projected_snapshot = _valid_snapshot(projected_snapshot) or {}
        projected_projection_m = float(projected_snapshot.get("robot_longitudinal_projection_m", current_projection_m) or 0.0)
        projected_lateral_m = float(projected_snapshot.get("robot_lateral_error_m", current_lateral_m) or 0.0)
        projected_distance_m = float(projected_snapshot.get("pre_stage_pose_distance_m", current_distance_m) or 0.0)
        projection_gain = round(current_projection_m - projected_projection_m, 6)
        lateral_gain = round(current_lateral_m - projected_lateral_m, 6)
        distance_gain = round(current_distance_m - projected_distance_m, 6)

    progress_score = round(
        (projection_gain * 120.0)
        + (distance_gain * 40.0)
        + (lateral_gain * 25.0)
        + ((float(min_ball_clearance_m or 0.0) / 10.0))
        + (5.0 if target_kind.startswith("docking_entry") else 0.0),
        6,
    )
    return DockingReacquireDecision(
        active=True,
        strategy_name=strategy_name,
        objective_name=DOCKING_REACQUIRE_OBJECTIVE,
        progress_score=progress_score,
        command=command,
        projected_projection_gain=projection_gain,
        projected_lateral_gain=lateral_gain,
        projected_distance_gain=distance_gain,
        projected_snapshot=projected_snapshot,
        release_reason="",
        dock_pose=dock_pose,
        side_sign=side_sign,
        target_distance_m=round(target_distance_m, 6),
        target_heading_error_rad=round(heading_error, 6),
        segment_ball_clearance_m=segment_clearance_m,
        min_ball_clearance_m=min_ball_clearance_m,
        ball_motion_m=ball_motion_m,
        release_blockers=release_blockers,
    )
