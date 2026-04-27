#!/usr/bin/env python3
"""Nav2 FollowPath pre-stage reacquire planning helpers."""

from __future__ import annotations

import math
from dataclasses import asdict
from dataclasses import dataclass
from typing import Any

from gather_mission_helpers import ZoneSpec
from gather_mission_helpers import clamp
from gather_mission_helpers import normalize_angle
from gather_mission_helpers import point_xy
from gather_mission_helpers import pre_stage_arrival_snapshot
from gather_mission_helpers import world_pose_xyyaw


NAV2_FOLLOW_PATH_REACQUIRE_CONTROL_FAMILY = "nav2_follow_path_reacquire_v1"
NAV2_FOLLOW_PATH_REACQUIRE_OBJECTIVE = "nav2_follow_path_reacquire"
NAV2_FOLLOW_PATH_RESULT_MARKER = "NAV2_FOLLOW_PATH_RESULT="

FOLLOW_PATH_ESCAPE_CLEAR = "escape_clear"
FOLLOW_PATH_CORRIDOR_APPROACH = "corridor_approach"
FOLLOW_PATH_PORT = "port"
FOLLOW_PATH_HANDOFF_YAW = "handoff_yaw"

DEFAULT_NAV2_FOLLOW_PATH_FRAME_ID = "odom"
DEFAULT_NAV2_FOLLOW_PATH_CONTROLLER_ID = "FollowPath"
DEFAULT_NAV2_FOLLOW_PATH_GOAL_CHECKER_ID = "general_goal_checker"
DEFAULT_NAV2_FOLLOW_PATH_SERVER_WAIT_S = 5.0
DEFAULT_NAV2_FOLLOW_PATH_GOAL_TIMEOUT_S = 22.0
DEFAULT_NAV2_FOLLOW_PATH_BALL_MOTION_TOLERANCE_M = 0.035
DEFAULT_NAV2_FOLLOW_PATH_MIN_BALL_CLEARANCE_M = 0.50

DEFAULT_FOLLOW_PATH_ESCAPE_LATERAL_M = 1.45
DEFAULT_FOLLOW_PATH_CORRIDOR_LATERAL_M = 0.92
DEFAULT_FOLLOW_PATH_PORT_LATERAL_M = 0.28
DEFAULT_FOLLOW_PATH_ESCAPE_BEHIND_BIAS_M = 0.65
DEFAULT_FOLLOW_PATH_CORRIDOR_BEHIND_BIAS_M = 0.34
DEFAULT_FOLLOW_PATH_PORT_BEHIND_BIAS_M = 0.08


@dataclass(frozen=True)
class Nav2FollowPathPose:
    kind: str
    frame_id: str
    x: float
    y: float
    yaw: float
    yaw_deg: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Nav2FollowPathReacquirePlan:
    active: bool
    reason: str
    path_poses: tuple[Nav2FollowPathPose, ...] = ()
    controller_id: str = DEFAULT_NAV2_FOLLOW_PATH_CONTROLLER_ID
    goal_checker_id: str = DEFAULT_NAV2_FOLLOW_PATH_GOAL_CHECKER_ID
    frame_id: str = DEFAULT_NAV2_FOLLOW_PATH_FRAME_ID
    trigger: dict[str, Any] | None = None
    pre_stage_at_plan: dict[str, Any] | None = None
    side_sign: float | None = None
    min_path_ball_clearance_m: float | None = None
    segment_ball_clearances_m: tuple[float, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "active": bool(self.active),
            "reason": str(self.reason),
            "path_poses": [pose.to_dict() for pose in self.path_poses],
            "path_kinds": [pose.kind for pose in self.path_poses],
            "controller_id": str(self.controller_id),
            "goal_checker_id": str(self.goal_checker_id),
            "frame_id": str(self.frame_id),
            "trigger": dict(self.trigger or {}),
            "pre_stage_at_plan": dict(self.pre_stage_at_plan or {}),
            "side_sign": self.side_sign,
            "min_path_ball_clearance_m": self.min_path_ball_clearance_m,
            "segment_ball_clearances_m": list(self.segment_ball_clearances_m),
        }


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


def _pose(kind: str, frame_id: str, x: float, y: float, yaw: float) -> Nav2FollowPathPose:
    return Nav2FollowPathPose(
        kind=str(kind),
        frame_id=str(frame_id),
        x=round(float(x), 6),
        y=round(float(y), 6),
        yaw=round(normalize_angle(float(yaw)), 6),
        yaw_deg=round(math.degrees(normalize_angle(float(yaw))), 6),
    )


def _candidate_path(
    pre_stage_pose: dict[str, Any],
    *,
    basis: tuple[float, float, float, float, float],
    side_sign: float,
    frame_id: str,
) -> tuple[Nav2FollowPathPose, ...]:
    push_ux, push_uy, normal_x, normal_y, push_yaw_rad = basis
    pre_stage_x = float(pre_stage_pose.get("x", 0.0) or 0.0)
    pre_stage_y = float(pre_stage_pose.get("y", 0.0) or 0.0)

    def offset_pose(kind: str, lateral_m: float, behind_bias_m: float) -> Nav2FollowPathPose:
        return _pose(
            kind,
            frame_id,
            pre_stage_x + (float(side_sign) * lateral_m * normal_x) - (behind_bias_m * push_ux),
            pre_stage_y + (float(side_sign) * lateral_m * normal_y) - (behind_bias_m * push_uy),
            push_yaw_rad,
        )

    return (
        offset_pose(FOLLOW_PATH_ESCAPE_CLEAR, DEFAULT_FOLLOW_PATH_ESCAPE_LATERAL_M, DEFAULT_FOLLOW_PATH_ESCAPE_BEHIND_BIAS_M),
        offset_pose(
            FOLLOW_PATH_CORRIDOR_APPROACH,
            DEFAULT_FOLLOW_PATH_CORRIDOR_LATERAL_M,
            DEFAULT_FOLLOW_PATH_CORRIDOR_BEHIND_BIAS_M,
        ),
        offset_pose(FOLLOW_PATH_PORT, DEFAULT_FOLLOW_PATH_PORT_LATERAL_M, DEFAULT_FOLLOW_PATH_PORT_BEHIND_BIAS_M),
        _pose(FOLLOW_PATH_HANDOFF_YAW, frame_id, pre_stage_x, pre_stage_y, push_yaw_rad),
    )


def _path_segment_clearances(
    robot_pose: dict[str, Any],
    path_poses: tuple[Nav2FollowPathPose, ...],
    ball_pose: dict[str, Any],
) -> tuple[float, ...]:
    clearances: list[float] = []
    start_pose: dict[str, Any] = robot_pose
    for path_pose in path_poses:
        target_pose = path_pose.to_dict()
        clearance = _segment_ball_clearance(start_pose, target_pose, ball_pose)
        if clearance is not None:
            clearances.append(float(clearance))
        start_pose = target_pose
    return tuple(clearances)


def _choose_side(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    pre_stage_pose: dict[str, Any],
    *,
    basis: tuple[float, float, float, float, float],
    snapshot: dict[str, Any],
    frame_id: str,
) -> tuple[float, tuple[Nav2FollowPathPose, ...], tuple[float, ...]]:
    lateral_signed_m = float(snapshot.get("robot_lateral_signed_m", 0.0) or 0.0)
    preferred_sides = [1.0, -1.0]
    if abs(lateral_signed_m) > 0.05:
        preferred = 1.0 if lateral_signed_m > 0.0 else -1.0
        preferred_sides = [preferred, -preferred]

    robot_xyyaw = world_pose_xyyaw(robot_pose)
    best: tuple[float, float, tuple[Nav2FollowPathPose, ...], tuple[float, ...]] | None = None
    for side in preferred_sides:
        candidate = _candidate_path(pre_stage_pose, basis=basis, side_sign=side, frame_id=frame_id)
        clearances = _path_segment_clearances(robot_pose, candidate, ball_pose)
        min_clearance = min(clearances) if clearances else 0.0
        heading_cost = 0.0
        if robot_xyyaw is not None and candidate:
            robot_x, robot_y, robot_yaw = robot_xyyaw
            first = candidate[0]
            heading_cost = abs(normalize_angle(math.atan2(first.y - robot_y, first.x - robot_x) - robot_yaw))
        score = float(min_clearance) - (0.04 * heading_cost)
        if best is None or score > best[0]:
            best = (score, side, candidate, clearances)
    if best is None:
        candidate = _candidate_path(pre_stage_pose, basis=basis, side_sign=1.0, frame_id=frame_id)
        return 1.0, candidate, _path_segment_clearances(robot_pose, candidate, ball_pose)
    _score, side, candidate, clearances = best
    return float(side), candidate, clearances


def build_nav2_follow_path_reacquire_plan(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    snapshot: dict[str, Any] | None = None,
    frame_id: str = DEFAULT_NAV2_FOLLOW_PATH_FRAME_ID,
    controller_id: str = DEFAULT_NAV2_FOLLOW_PATH_CONTROLLER_ID,
    goal_checker_id: str = DEFAULT_NAV2_FOLLOW_PATH_GOAL_CHECKER_ID,
    min_ball_clearance_m: float = DEFAULT_NAV2_FOLLOW_PATH_MIN_BALL_CLEARANCE_M,
) -> Nav2FollowPathReacquirePlan:
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
    trigger = {
        "robot_on_goal_side": bool(current_snapshot.get("robot_on_goal_side", False)) if current_snapshot else False,
        "pre_stage_pose_distance_m": (
            round(float(current_snapshot.get("pre_stage_pose_distance_m", 0.0) or 0.0), 6)
            if current_snapshot
            else None
        ),
        "robot_longitudinal_projection_m": (
            round(float(current_snapshot.get("robot_longitudinal_projection_m", 0.0) or 0.0), 6)
            if current_snapshot
            else None
        ),
        "robot_lateral_error_m": (
            round(float(current_snapshot.get("robot_lateral_error_m", 0.0) or 0.0), 6)
            if current_snapshot
            else None
        ),
        "yaw_error_deg": (
            round(float(current_snapshot.get("yaw_error_deg", 0.0) or 0.0), 6)
            if current_snapshot
            else None
        ),
    }
    if current_snapshot is None or basis is None or point_xy(pre_stage_pose) is None:
        return Nav2FollowPathReacquirePlan(
            active=False,
            reason="missing_follow_path_geometry",
            controller_id=controller_id,
            goal_checker_id=goal_checker_id,
            frame_id=frame_id,
            trigger=trigger,
            pre_stage_at_plan=current_snapshot or {},
        )
    if bool(current_snapshot.get("pre_stage_pose_reached", False)):
        return Nav2FollowPathReacquirePlan(
            active=False,
            reason="pre_stage_handoff_already_ready",
            controller_id=controller_id,
            goal_checker_id=goal_checker_id,
            frame_id=frame_id,
            trigger=trigger,
            pre_stage_at_plan=current_snapshot,
        )

    side_sign, path_poses, clearances = _choose_side(
        robot_pose,
        ball_pose,
        pre_stage_pose,
        basis=basis,
        snapshot=current_snapshot,
        frame_id=frame_id,
    )
    min_clearance = min(clearances) if clearances else None
    if min_clearance is None or float(min_clearance) < float(min_ball_clearance_m):
        return Nav2FollowPathReacquirePlan(
            active=False,
            reason="follow_path_clearance_guard",
            path_poses=path_poses,
            controller_id=controller_id,
            goal_checker_id=goal_checker_id,
            frame_id=frame_id,
            trigger=trigger,
            pre_stage_at_plan=current_snapshot,
            side_sign=side_sign,
            min_path_ball_clearance_m=round(float(min_clearance or 0.0), 6),
            segment_ball_clearances_m=tuple(round(float(value), 6) for value in clearances),
        )

    return Nav2FollowPathReacquirePlan(
        active=True,
        reason="follow_path_reacquire",
        path_poses=path_poses,
        controller_id=controller_id,
        goal_checker_id=goal_checker_id,
        frame_id=frame_id,
        trigger=trigger,
        pre_stage_at_plan=current_snapshot,
        side_sign=side_sign,
        min_path_ball_clearance_m=round(float(min_clearance), 6),
        segment_ball_clearances_m=tuple(round(float(value), 6) for value in clearances),
    )
