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
NAV2_MPPI_FOLLOW_PATH_REACQUIRE_CONTROL_FAMILY = "nav2_mppi_follow_path_reacquire_v1"
NAV2_FOLLOW_PATH_CORRIDOR_PUSH_CONTROL_FAMILY = "nav2_followpath_corridor_push_v1"
NAV2_FOLLOW_PATH_REACQUIRE_OBJECTIVE = "nav2_follow_path_reacquire"
NAV2_MPPI_FOLLOW_PATH_REACQUIRE_OBJECTIVE = "nav2_mppi_follow_path_reacquire"
NAV2_FOLLOW_PATH_CORRIDOR_PUSH_OBJECTIVE = "nav2_followpath_corridor_push"
NAV2_FOLLOW_PATH_RESULT_MARKER = "NAV2_FOLLOW_PATH_RESULT="

FOLLOW_PATH_START = "start"
FOLLOW_PATH_ESCAPE_CLEAR = "escape_clear"
FOLLOW_PATH_CORRIDOR_APPROACH = "corridor_approach"
FOLLOW_PATH_PORT = "port"
FOLLOW_PATH_HANDOFF_ALIGN = "handoff_align"
FOLLOW_PATH_HANDOFF_YAW = "handoff_yaw"
FOLLOW_PATH_CORRIDOR_CONTACT_READY = "corridor_contact_ready"
FOLLOW_PATH_CORRIDOR_CONTACT = "corridor_contact"
FOLLOW_PATH_CORRIDOR_CONTACT_CONFIRM = "corridor_contact_confirm"
FOLLOW_PATH_CORRIDOR_DELIVERY_INTERSECTION = "corridor_delivery_intersection"
FOLLOW_PATH_CORRIDOR_PUSH_THROUGH = "corridor_push_through"

DEFAULT_NAV2_FOLLOW_PATH_FRAME_ID = "odom"
DEFAULT_NAV2_FOLLOW_PATH_CONTROLLER_ID = "FollowPath"
DEFAULT_NAV2_MPPI_FOLLOW_PATH_CONTROLLER_ID = "MppiFollowPath"
DEFAULT_NAV2_FOLLOW_PATH_GOAL_CHECKER_ID = "general_goal_checker"
DEFAULT_NAV2_FOLLOW_PATH_SERVER_WAIT_S = 5.0
DEFAULT_NAV2_FOLLOW_PATH_GOAL_TIMEOUT_S = 22.0
DEFAULT_NAV2_MPPI_FOLLOW_PATH_GOAL_TIMEOUT_S = 105.0
DEFAULT_NAV2_MPPI_FOLLOW_PATH_PRE_STAGE_TIMEOUT_S = 110.0
DEFAULT_NAV2_FOLLOW_PATH_CORRIDOR_PUSH_GOAL_TIMEOUT_S = 32.0
DEFAULT_NAV2_FOLLOW_PATH_BALL_MOTION_TOLERANCE_M = 0.035
DEFAULT_NAV2_FOLLOW_PATH_MIN_BALL_CLEARANCE_M = 0.50
DEFAULT_NAV2_MPPI_FOLLOW_PATH_MAX_SPACING_M = 0.25
DEFAULT_NAV2_FOLLOW_PATH_CORRIDOR_PUSH_MAX_SPACING_M = 0.12
DEFAULT_NAV2_FOLLOW_PATH_CORRIDOR_PUSH_CONTACT_STANDOFF_M = 0.35
DEFAULT_NAV2_FOLLOW_PATH_CORRIDOR_CONTACT_CONFIRM_M = 0.08
DEFAULT_NAV2_FOLLOW_PATH_CORRIDOR_PUSH_THROUGH_M = 0.45

DEFAULT_FOLLOW_PATH_ESCAPE_LATERAL_M = 1.45
DEFAULT_FOLLOW_PATH_CORRIDOR_LATERAL_M = 0.92
DEFAULT_FOLLOW_PATH_PORT_LATERAL_M = 0.28
DEFAULT_FOLLOW_PATH_ESCAPE_BEHIND_BIAS_M = 0.65
DEFAULT_FOLLOW_PATH_CORRIDOR_BEHIND_BIAS_M = 0.34
DEFAULT_FOLLOW_PATH_PORT_BEHIND_BIAS_M = 0.08
DEFAULT_FOLLOW_PATH_HANDOFF_ALIGN_BEHIND_BIAS_M = 0.55


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


def _target_basis(start_pose: dict[str, Any], target_pose: dict[str, Any]) -> tuple[float, float, float, float, float] | None:
    start_xy = point_xy(start_pose)
    target_xy = point_xy(target_pose)
    if start_xy is None or target_xy is None:
        return None
    push_dx = target_xy[0] - start_xy[0]
    push_dy = target_xy[1] - start_xy[1]
    push_norm = math.hypot(push_dx, push_dy)
    if push_norm <= 1.0e-6:
        return None
    push_ux = push_dx / push_norm
    push_uy = push_dy / push_norm
    return push_ux, push_uy, -push_uy, push_ux, math.atan2(push_uy, push_ux)


def _push_basis(ball_pose: dict[str, Any], zone: ZoneSpec) -> tuple[float, float, float, float, float] | None:
    return _target_basis(ball_pose, {"x": float(zone.world_x), "y": float(zone.world_y), "z": float(zone.z_m)})


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
    include_handoff_align_pose: bool = False,
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

    path = [
        offset_pose(FOLLOW_PATH_ESCAPE_CLEAR, DEFAULT_FOLLOW_PATH_ESCAPE_LATERAL_M, DEFAULT_FOLLOW_PATH_ESCAPE_BEHIND_BIAS_M),
        offset_pose(
            FOLLOW_PATH_CORRIDOR_APPROACH,
            DEFAULT_FOLLOW_PATH_CORRIDOR_LATERAL_M,
            DEFAULT_FOLLOW_PATH_CORRIDOR_BEHIND_BIAS_M,
        ),
        offset_pose(FOLLOW_PATH_PORT, DEFAULT_FOLLOW_PATH_PORT_LATERAL_M, DEFAULT_FOLLOW_PATH_PORT_BEHIND_BIAS_M),
    ]
    if include_handoff_align_pose:
        path.append(
            offset_pose(
                FOLLOW_PATH_HANDOFF_ALIGN,
                0.0,
                DEFAULT_FOLLOW_PATH_HANDOFF_ALIGN_BEHIND_BIAS_M,
            )
        )
    path.append(_pose(FOLLOW_PATH_HANDOFF_YAW, frame_id, pre_stage_x, pre_stage_y, push_yaw_rad))
    return tuple(path)


def _interpolate_yaw(start_yaw: float, target_yaw: float, t: float) -> float:
    return normalize_angle(float(start_yaw) + (normalize_angle(float(target_yaw) - float(start_yaw)) * float(t)))


def _densify_path(
    robot_pose: dict[str, Any],
    path_poses: tuple[Nav2FollowPathPose, ...],
    *,
    frame_id: str,
    max_spacing_m: float | None,
    include_start_pose: bool,
    yaw_mode: str = "interpolate",
) -> tuple[Nav2FollowPathPose, ...]:
    spacing = _finite_number(max_spacing_m)
    if not include_start_pose and (spacing is None or spacing <= 0.0):
        return path_poses

    robot_xyyaw = world_pose_xyyaw(robot_pose)
    if robot_xyyaw is None:
        return path_poses

    densified: list[Nav2FollowPathPose] = []
    previous_x, previous_y, previous_yaw = robot_xyyaw
    if include_start_pose:
        densified.append(_pose(FOLLOW_PATH_START, frame_id, previous_x, previous_y, previous_yaw))

    if spacing is None or spacing <= 0.0:
        densified.extend(path_poses)
        return tuple(densified)

    for target in path_poses:
        dx = float(target.x) - previous_x
        dy = float(target.y) - previous_y
        distance_m = math.hypot(dx, dy)
        step_count = max(1, int(math.ceil(distance_m / float(spacing))))
        segment_yaw = math.atan2(dy, dx) if distance_m > 1.0e-6 else previous_yaw
        for index in range(1, step_count + 1):
            ratio = float(index) / float(step_count)
            kind = target.kind if index == step_count else f"{target.kind}_approach_{index}"
            path_yaw = _interpolate_yaw(previous_yaw, target.yaw, ratio)
            if yaw_mode == "tangent":
                if target.kind in {FOLLOW_PATH_HANDOFF_ALIGN, FOLLOW_PATH_HANDOFF_YAW}:
                    path_yaw = target.yaw
                else:
                    path_yaw = segment_yaw
            elif yaw_mode == "corridor_push":
                if target.kind == FOLLOW_PATH_CORRIDOR_CONTACT_READY:
                    path_yaw = _interpolate_yaw(previous_yaw, target.yaw, ratio)
                else:
                    path_yaw = target.yaw
            densified.append(
                _pose(
                    kind,
                    frame_id,
                    previous_x + (dx * ratio),
                    previous_y + (dy * ratio),
                    path_yaw,
                )
            )
        previous_x = float(target.x)
        previous_y = float(target.y)
        previous_yaw = float(target.yaw)

    return tuple(densified)


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
    include_handoff_align_pose: bool = False,
) -> tuple[float, tuple[Nav2FollowPathPose, ...], tuple[float, ...]]:
    lateral_signed_m = float(snapshot.get("robot_lateral_signed_m", 0.0) or 0.0)
    preferred_sides = [1.0, -1.0]
    if abs(lateral_signed_m) > 0.05:
        preferred = 1.0 if lateral_signed_m > 0.0 else -1.0
        preferred_sides = [preferred, -preferred]

    robot_xyyaw = world_pose_xyyaw(robot_pose)
    best: tuple[float, float, tuple[Nav2FollowPathPose, ...], tuple[float, ...]] | None = None
    for side in preferred_sides:
        candidate = _candidate_path(
            pre_stage_pose,
            basis=basis,
            side_sign=side,
            frame_id=frame_id,
            include_handoff_align_pose=include_handoff_align_pose,
        )
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
        candidate = _candidate_path(
            pre_stage_pose,
            basis=basis,
            side_sign=1.0,
            frame_id=frame_id,
            include_handoff_align_pose=include_handoff_align_pose,
        )
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
    max_path_spacing_m: float | None = None,
    include_start_pose: bool = False,
    path_yaw_mode: str = "interpolate",
    include_handoff_align_pose: bool = False,
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
        include_handoff_align_pose=include_handoff_align_pose,
    )
    path_poses = _densify_path(
        robot_pose,
        path_poses,
        frame_id=frame_id,
        max_spacing_m=max_path_spacing_m,
        include_start_pose=include_start_pose,
        yaw_mode=path_yaw_mode,
    )
    clearances = _path_segment_clearances(robot_pose, path_poses, ball_pose)
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


def build_nav2_mppi_follow_path_reacquire_plan(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    snapshot: dict[str, Any] | None = None,
    frame_id: str = DEFAULT_NAV2_FOLLOW_PATH_FRAME_ID,
    controller_id: str = DEFAULT_NAV2_MPPI_FOLLOW_PATH_CONTROLLER_ID,
    goal_checker_id: str = DEFAULT_NAV2_FOLLOW_PATH_GOAL_CHECKER_ID,
    min_ball_clearance_m: float = DEFAULT_NAV2_FOLLOW_PATH_MIN_BALL_CLEARANCE_M,
    max_path_spacing_m: float = DEFAULT_NAV2_MPPI_FOLLOW_PATH_MAX_SPACING_M,
) -> Nav2FollowPathReacquirePlan:
    return build_nav2_follow_path_reacquire_plan(
        robot_pose,
        ball_pose,
        zone=zone,
        snapshot=snapshot,
        frame_id=frame_id,
        controller_id=controller_id,
        goal_checker_id=goal_checker_id,
        min_ball_clearance_m=min_ball_clearance_m,
        max_path_spacing_m=max_path_spacing_m,
        include_start_pose=True,
        path_yaw_mode="tangent",
        include_handoff_align_pose=False,
    )


def build_nav2_follow_path_corridor_push_plan(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    delivery_pose: dict[str, Any],
    *,
    frame_id: str = DEFAULT_NAV2_FOLLOW_PATH_FRAME_ID,
    controller_id: str = DEFAULT_NAV2_FOLLOW_PATH_CONTROLLER_ID,
    goal_checker_id: str = DEFAULT_NAV2_FOLLOW_PATH_GOAL_CHECKER_ID,
    contact_standoff_m: float = DEFAULT_NAV2_FOLLOW_PATH_CORRIDOR_PUSH_CONTACT_STANDOFF_M,
    push_through_m: float = DEFAULT_NAV2_FOLLOW_PATH_CORRIDOR_PUSH_THROUGH_M,
    max_path_spacing_m: float = DEFAULT_NAV2_FOLLOW_PATH_CORRIDOR_PUSH_MAX_SPACING_M,
    include_start_pose: bool = True,
) -> Nav2FollowPathReacquirePlan:
    basis = _target_basis(ball_pose, delivery_pose)
    robot_xyyaw = world_pose_xyyaw(robot_pose)
    ball_xy = point_xy(ball_pose)
    delivery_xy = point_xy(delivery_pose)
    trigger: dict[str, Any] = {}
    if basis is not None and robot_xyyaw is not None and ball_xy is not None and delivery_xy is not None:
        push_ux, push_uy, normal_x, normal_y, push_yaw_rad = basis
        robot_x, robot_y, robot_yaw = robot_xyyaw
        robot_from_ball_x = robot_x - ball_xy[0]
        robot_from_ball_y = robot_y - ball_xy[1]
        trigger = {
            "robot_longitudinal_projection_m": round((robot_from_ball_x * push_ux) + (robot_from_ball_y * push_uy), 6),
            "robot_lateral_signed_m": round((robot_from_ball_x * normal_x) + (robot_from_ball_y * normal_y), 6),
            "yaw_error_deg": round(math.degrees(normalize_angle(robot_yaw - push_yaw_rad)), 6),
            "ball_target_distance_m": round(math.hypot(delivery_xy[0] - ball_xy[0], delivery_xy[1] - ball_xy[1]), 6),
            "contact_standoff_m": round(max(float(contact_standoff_m), 0.0), 6),
            "push_through_m": round(max(float(push_through_m), 0.0), 6),
        }
    if basis is None or ball_xy is None or delivery_xy is None:
        return Nav2FollowPathReacquirePlan(
            active=False,
            reason="missing_corridor_push_geometry",
            controller_id=controller_id,
            goal_checker_id=goal_checker_id,
            frame_id=frame_id,
            trigger=trigger,
        )

    push_ux, push_uy, _normal_x, _normal_y, push_yaw_rad = basis
    contact_standoff = max(float(contact_standoff_m), 0.0)
    push_through = max(float(push_through_m), 0.0)
    path_poses = (
        _pose(
            FOLLOW_PATH_CORRIDOR_CONTACT_READY,
            frame_id,
            ball_xy[0] - (contact_standoff * push_ux),
            ball_xy[1] - (contact_standoff * push_uy),
            push_yaw_rad,
        ),
        _pose(FOLLOW_PATH_CORRIDOR_CONTACT, frame_id, ball_xy[0], ball_xy[1], push_yaw_rad),
        _pose(
            FOLLOW_PATH_CORRIDOR_DELIVERY_INTERSECTION,
            frame_id,
            delivery_xy[0],
            delivery_xy[1],
            push_yaw_rad,
        ),
        _pose(
            FOLLOW_PATH_CORRIDOR_PUSH_THROUGH,
            frame_id,
            delivery_xy[0] + (push_through * push_ux),
            delivery_xy[1] + (push_through * push_uy),
            push_yaw_rad,
        ),
    )
    path_poses = _densify_path(
        robot_pose,
        path_poses,
        frame_id=frame_id,
        max_spacing_m=max_path_spacing_m,
        include_start_pose=include_start_pose,
        yaw_mode="corridor_push",
    )
    clearances = _path_segment_clearances(robot_pose, path_poses, ball_pose)
    min_clearance = min(clearances) if clearances else None
    return Nav2FollowPathReacquirePlan(
        active=True,
        reason="follow_path_corridor_push",
        path_poses=path_poses,
        controller_id=controller_id,
        goal_checker_id=goal_checker_id,
        frame_id=frame_id,
        trigger=trigger,
        pre_stage_at_plan={},
        side_sign=None,
        min_path_ball_clearance_m=round(float(min_clearance), 6) if min_clearance is not None else None,
        segment_ball_clearances_m=tuple(round(float(value), 6) for value in clearances),
    )


def build_nav2_follow_path_corridor_contact_probe_plan(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    delivery_pose: dict[str, Any],
    *,
    frame_id: str = DEFAULT_NAV2_FOLLOW_PATH_FRAME_ID,
    controller_id: str = DEFAULT_NAV2_FOLLOW_PATH_CONTROLLER_ID,
    goal_checker_id: str = DEFAULT_NAV2_FOLLOW_PATH_GOAL_CHECKER_ID,
    contact_standoff_m: float = DEFAULT_NAV2_FOLLOW_PATH_CORRIDOR_PUSH_CONTACT_STANDOFF_M,
    contact_confirm_m: float = DEFAULT_NAV2_FOLLOW_PATH_CORRIDOR_CONTACT_CONFIRM_M,
    max_path_spacing_m: float = DEFAULT_NAV2_FOLLOW_PATH_CORRIDOR_PUSH_MAX_SPACING_M,
    include_start_pose: bool = True,
) -> Nav2FollowPathReacquirePlan:
    basis = _target_basis(ball_pose, delivery_pose)
    robot_xyyaw = world_pose_xyyaw(robot_pose)
    ball_xy = point_xy(ball_pose)
    delivery_xy = point_xy(delivery_pose)
    trigger: dict[str, Any] = {}
    if basis is not None and robot_xyyaw is not None and ball_xy is not None and delivery_xy is not None:
        push_ux, push_uy, normal_x, normal_y, push_yaw_rad = basis
        robot_x, robot_y, robot_yaw = robot_xyyaw
        robot_from_ball_x = robot_x - ball_xy[0]
        robot_from_ball_y = robot_y - ball_xy[1]
        trigger = {
            "robot_longitudinal_projection_m": round((robot_from_ball_x * push_ux) + (robot_from_ball_y * push_uy), 6),
            "robot_lateral_signed_m": round((robot_from_ball_x * normal_x) + (robot_from_ball_y * normal_y), 6),
            "yaw_error_deg": round(math.degrees(normalize_angle(robot_yaw - push_yaw_rad)), 6),
            "ball_target_distance_m": round(math.hypot(delivery_xy[0] - ball_xy[0], delivery_xy[1] - ball_xy[1]), 6),
            "contact_standoff_m": round(max(float(contact_standoff_m), 0.0), 6),
            "contact_confirm_m": round(max(float(contact_confirm_m), 0.0), 6),
        }
    if basis is None or ball_xy is None or delivery_xy is None:
        return Nav2FollowPathReacquirePlan(
            active=False,
            reason="missing_corridor_contact_probe_geometry",
            controller_id=controller_id,
            goal_checker_id=goal_checker_id,
            frame_id=frame_id,
            trigger=trigger,
        )

    push_ux, push_uy, _normal_x, _normal_y, push_yaw_rad = basis
    contact_standoff = max(float(contact_standoff_m), 0.0)
    contact_confirm = max(float(contact_confirm_m), 0.0)
    path_poses = (
        _pose(
            FOLLOW_PATH_CORRIDOR_CONTACT_READY,
            frame_id,
            ball_xy[0] - (contact_standoff * push_ux),
            ball_xy[1] - (contact_standoff * push_uy),
            push_yaw_rad,
        ),
        _pose(FOLLOW_PATH_CORRIDOR_CONTACT, frame_id, ball_xy[0], ball_xy[1], push_yaw_rad),
        _pose(
            FOLLOW_PATH_CORRIDOR_CONTACT_CONFIRM,
            frame_id,
            ball_xy[0] + (contact_confirm * push_ux),
            ball_xy[1] + (contact_confirm * push_uy),
            push_yaw_rad,
        ),
    )
    path_poses = _densify_path(
        robot_pose,
        path_poses,
        frame_id=frame_id,
        max_spacing_m=max_path_spacing_m,
        include_start_pose=include_start_pose,
        yaw_mode="corridor_push",
    )
    clearances = _path_segment_clearances(robot_pose, path_poses, ball_pose)
    min_clearance = min(clearances) if clearances else None
    return Nav2FollowPathReacquirePlan(
        active=True,
        reason="follow_path_corridor_contact_probe",
        path_poses=path_poses,
        controller_id=controller_id,
        goal_checker_id=goal_checker_id,
        frame_id=frame_id,
        trigger=trigger,
        pre_stage_at_plan={},
        side_sign=None,
        min_path_ball_clearance_m=round(float(min_clearance), 6) if min_clearance is not None else None,
        segment_ball_clearances_m=tuple(round(float(value), 6) for value in clearances),
    )
