#!/usr/bin/env python3
"""Pure helpers for offline/headless gather mission planning and scoring."""

from __future__ import annotations

import math
from dataclasses import asdict
from dataclasses import dataclass
from typing import Any


DEFAULT_ZONE_WORLD_X = 2.40
DEFAULT_ZONE_WORLD_Y = 0.00
DEFAULT_CONTROL_ZONE_RADIUS_M = 0.20
DEFAULT_RETRIEVAL_CORRAL_RADIUS_M = 0.762
DEFAULT_ZONE_DWELL_S = 1.0
DEFAULT_CAPTURE_LOSS_GRACE_S = 1.0
DEFAULT_TARGET_BALL_RADIUS_M = 0.05
DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M = 0.01
DEFAULT_RELEASE_SETTLE_STABLE_WINDOW_S = 1.0
DEFAULT_RELEASE_SETTLE_MAX_WAIT_S = 6.0
DEFAULT_RELEASE_ZONE_MARGIN_M = 0.07
DEFAULT_ZONE_EDGE_CORRECTION_MARGIN_M = 0.12
DEFAULT_MULTI_BALL_SPAWN_RADIUS_M = 3.048
DEFAULT_PRE_STAGE_BEHIND_BALL_DISTANCE_M = 0.90
DEFAULT_PRE_STAGE_READY_LONGITUDINAL_PROJECTION_M = -0.50
DEFAULT_PRE_STAGE_READY_LATERAL_ERROR_M = 0.30
DEFAULT_PRE_STAGE_READY_YAW_ERROR_DEG = 35.0
DEFAULT_PRE_STAGE_READY_DWELL_S = 0.25
DEFAULT_PRE_STAGE_ARRIVAL_RADIUS_M = 0.30
DEFAULT_PRE_STAGE_CLOSE_IN_READY_LONGITUDINAL_PROJECTION_M = -0.55
DEFAULT_PRE_STAGE_CLOSE_IN_READY_LATERAL_ERROR_M = 0.22
DEFAULT_PRE_STAGE_CLOSE_IN_READY_YAW_ERROR_DEG = 37.0
DEFAULT_PRE_STAGE_CLOSE_IN_READY_DISTANCE_M = 0.35
DEFAULT_PRE_STAGE_DEEP_CLOSE_HANDOFF_LONGITUDINAL_PROJECTION_M = -0.75
DEFAULT_PRE_STAGE_DEEP_CLOSE_HANDOFF_LATERAL_ERROR_M = 0.18
DEFAULT_PRE_STAGE_DEEP_CLOSE_HANDOFF_YAW_ERROR_DEG = 47.0
DEFAULT_PRE_STAGE_DEEP_CLOSE_HANDOFF_DISTANCE_M = 0.22
DEFAULT_PRE_STAGE_ORBIT_OFFSET_M = 1.00
DEFAULT_PRE_STAGE_ESCAPE_TRIGGER_PROJECTION_M = 0.15
DEFAULT_PRE_STAGE_ESCAPE_RELEASE_PROJECTION_M = -0.10
DEFAULT_PRE_STAGE_ESCAPE_RELEASE_LATERAL_ERROR_M = 0.75
DEFAULT_PRE_STAGE_ESCAPE_RELEASE_DISTANCE_M = 2.0
DEFAULT_PRE_STAGE_ESCAPE_LINEAR_X_MPS = -0.08
DEFAULT_PRE_STAGE_ESCAPE_EARLY_DIRECT_COMMIT_MIN_PROJECTION_M = 2.50
DEFAULT_PRE_STAGE_ESCAPE_EARLY_DIRECT_COMMIT_MIN_LATERAL_ERROR_M = 1.60
DEFAULT_PRE_STAGE_ESCAPE_EARLY_DIRECT_COMMIT_MAX_YAW_ERROR_DEG = 10.0
DEFAULT_PRE_STAGE_ESCAPE_EARLY_DIRECT_COMMIT_MAX_REVERSE_YAW_ERROR_DEG = 15.0
DEFAULT_PRE_STAGE_ESCAPE_DIRECT_COMMIT_PROJECTION_M = 1.30
DEFAULT_PRE_STAGE_ESCAPE_DIRECT_COMMIT_MAX_ORBIT_YAW_ERROR_DEG = 10.0
DEFAULT_PRE_STAGE_ESCAPE_DIRECT_REVERSE_MIN_FLOOR_ERROR_RAD = 0.08
DEFAULT_STAGE_BEHIND_BALL_DISTANCE_M = 0.45
DEFAULT_STAGE_READY_LONGITUDINAL_PROJECTION_M = -0.18
DEFAULT_STAGE_READY_LATERAL_ERROR_M = 0.18
DEFAULT_STAGE_READY_YAW_ERROR_DEG = 20.0
DEFAULT_STAGE_READY_DWELL_S = 0.4
DEFAULT_STAGE_ARRIVAL_RADIUS_M = 0.20
DEFAULT_STAGE_CLOSE_IN_ALIGN_LONGITUDINAL_PROJECTION_M = -0.65
DEFAULT_STAGE_CLOSE_IN_ALIGN_LATERAL_ERROR_M = 0.22
DEFAULT_STAGE_CLOSE_IN_ALIGN_DISTANCE_M = 0.33
DEFAULT_CAPTURE_ENTRY_READY_BALL_X_M = 0.45
DEFAULT_CAPTURE_ENTRY_READY_ABS_BALL_Y_M = 0.08
DEFAULT_CAPTURE_ENTRY_CENTERED_READY_BALL_X_M = 0.55
DEFAULT_CAPTURE_ENTRY_CENTERED_READY_ABS_BALL_Y_M = 0.05
DEFAULT_CAPTURE_ENTRY_PLUS45_FINISH_READY_BALL_X_M = 0.625
DEFAULT_CAPTURE_ENTRY_PLUS45_FINISH_READY_ABS_BALL_Y_M = 0.025
DEFAULT_CAPTURE_ENTRY_PLUS45_FINISH_READY_MAX_BEARING_RAD = 0.04
DEFAULT_CAPTURE_ENTRY_CENTERED_CLOSE_MIN_BALL_X_M = 0.50
DEFAULT_CAPTURE_ENTRY_CENTERED_CLOSE_MAX_ABS_BALL_Y_M = 0.03
DEFAULT_CAPTURE_ENTRY_CENTERED_CLOSE_MAX_BEARING_RAD = 0.06
DEFAULT_CAPTURE_ENTRY_READY_DWELL_S = 0.30
DEFAULT_CAPTURE_ENTRY_TIMEOUT_S = 4.0
DEFAULT_GOAL_SIDE_VIOLATION_PROJECTION_M = 0.0
DEFAULT_FIRST_CONTACT_ALIGNMENT_PASS_DEG = 25.0


@dataclass(frozen=True)
class GatherTargetSpec:
    id: str
    label: str
    start_visible: bool
    forward_m: float
    lateral_m: float
    z_m: float = 0.05
    visit_tolerance_m: float = 0.35
    min_dwell_s: float = 1.0


@dataclass(frozen=True)
class ZoneSpec:
    id: str
    label: str
    world_x: float
    world_y: float
    retrieval_radius_m: float = DEFAULT_RETRIEVAL_CORRAL_RADIUS_M
    control_radius_m: float = DEFAULT_CONTROL_ZONE_RADIUS_M
    dwell_s: float = DEFAULT_ZONE_DWELL_S
    z_m: float = 0.001

    @property
    def radius_m(self) -> float:
        return float(self.retrieval_radius_m)


@dataclass(frozen=True)
class CaptureEnvelope:
    min_x_m: float = 0.045
    max_x_m: float = 0.38
    max_abs_y_m: float = 0.070
    seated_max_x_m: float = 0.300
    seated_max_abs_y_m: float = 0.030
    recapture_max_x_m: float = 0.850
    recapture_max_abs_y_m: float = 0.200
    loss_grace_s: float = DEFAULT_CAPTURE_LOSS_GRACE_S


@dataclass(frozen=True)
class CaptureSnapshot:
    ball_x_m: float
    ball_y_m: float
    distance_m: float
    bearing_rad: float
    ball_ahead: bool
    within_recapture_window: bool
    within_capture_window: bool
    captured: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ZoneSnapshot:
    zone_distance_m: float
    retrieval_distance_m: float
    inside_zone: bool
    center_inside_zone: bool
    inside_retrieval_corral: bool
    center_inside_retrieval_corral: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlaceControlCommand:
    mode: str
    linear_x: float
    angular_z: float
    target_speed_scale: float
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReleaseSettleMetrics:
    surface_profile: str
    release_distance_to_zone_center_m: float
    max_overshoot_distance_m: float
    final_settle_distance_m: float
    settle_time_s: float
    release_recontact_count: int
    settled_inside_zone: bool
    final_inside_retrieval_corral: bool
    final_center_inside_zone: bool
    ball_stopped_in_corral: bool
    rolled_away_after_release: bool
    settled_in_corral_pass: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def marginal_capture(snapshot: CaptureSnapshot | None) -> bool:
    if snapshot is None or not snapshot.captured:
        return False
    return abs(float(snapshot.ball_y_m)) > 0.04 or float(snapshot.ball_x_m) < 0.08


def secure_capture(snapshot: CaptureSnapshot | None, envelope: CaptureEnvelope | None = None) -> bool:
    if snapshot is None or not snapshot.captured:
        return False
    active_envelope = envelope or CaptureEnvelope()
    return (
        float(snapshot.ball_x_m) <= float(active_envelope.seated_max_x_m)
        and abs(float(snapshot.ball_y_m)) <= float(active_envelope.seated_max_abs_y_m)
    )


def front_escape_risk(snapshot: CaptureSnapshot | None, envelope: CaptureEnvelope | None = None) -> bool:
    if snapshot is None or not snapshot.captured:
        return False
    active_envelope = envelope or CaptureEnvelope()
    return not secure_capture(snapshot, active_envelope)


def clean_retention_pass(run: dict[str, Any]) -> bool:
    if not isinstance(run, dict):
        return False
    mission_like_pass = bool(run.get("mission_completed_pass", run.get("pass", False)))
    return (
        mission_like_pass
        and int(run.get("capture_loss_count", 0) or 0) == 0
        and bool(run.get("stopped_with_ball_captured", False))
        and bool(run.get("release_started_with_capture", False))
    )


def zone_edge_correction_eligible(
    *,
    capture: CaptureSnapshot | None,
    zone_score: ZoneSnapshot | None,
    zone: ZoneSpec,
    margin_m: float = DEFAULT_ZONE_EDGE_CORRECTION_MARGIN_M,
) -> bool:
    if zone_score is None:
        return False
    if bool(zone_score.inside_zone):
        return True
    return bool(
        capture
        and capture.within_recapture_window
        and float(zone_score.zone_distance_m) <= (max(float(zone.control_radius_m), 0.0) + max(float(margin_m), 0.0))
    )


def settled_in_corral_pass(run: dict[str, Any]) -> bool:
    if not isinstance(run, dict):
        return False
    mission_like_pass = bool(run.get("mission_completed_pass", run.get("pass", False)))
    return (
        mission_like_pass
        and bool(run.get("final_inside_retrieval_corral", False))
        and bool(run.get("ball_stopped_in_corral", False))
        and not bool(run.get("rolled_away_after_release", False))
        and int(run.get("post_visit_revisit_count", 0) or 0) == 0
    )


def final_three_ball_corral_pass(run: dict[str, Any]) -> bool:
    if not isinstance(run, dict):
        return False
    mission_like_pass = bool(run.get("mission_completed_pass", run.get("pass", False)))
    return (
        mission_like_pass
        and bool(run.get("final_all_targets_inside_retrieval_corral", False))
        and bool(run.get("final_all_targets_stopped", False))
        and bool(run.get("final_three_ball_corral_pass", False))
        and int(run.get("post_visit_revisit_count", 0) or 0) == 0
    )


def gather_run_pass(run: dict[str, Any]) -> bool:
    if not isinstance(run, dict):
        return False
    scenario_id = str(run.get("scenario_id", "") or "").strip()
    if scenario_id == "gather_three_ball_zone" or "final_three_ball_corral_pass" in run:
        return final_three_ball_corral_pass(run)
    return settled_in_corral_pass(run)


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def normalize_angle(value: float) -> float:
    while value > math.pi:
        value -= 2.0 * math.pi
    while value < -math.pi:
        value += 2.0 * math.pi
    return value


def _number(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _spawn_on_corral_arc(*, angle_deg: float) -> tuple[float, float]:
    angle_rad = math.radians(angle_deg)
    return (
        DEFAULT_ZONE_WORLD_X + (DEFAULT_MULTI_BALL_SPAWN_RADIUS_M * math.cos(angle_rad)),
        DEFAULT_ZONE_WORLD_Y + (DEFAULT_MULTI_BALL_SPAWN_RADIUS_M * math.sin(angle_rad)),
    )


def build_gather_targets(scenario_id: str) -> list[GatherTargetSpec]:
    if scenario_id == "corral_single_ball_place":
        return [
            GatherTargetSpec(
                id="ball_1",
                label="Ball 1",
                start_visible=False,
                forward_m=1.10,
                lateral_m=0.00,
            )
        ]
    if scenario_id == "gather_three_ball_zone":
        left_forward_m, left_lateral_m = _spawn_on_corral_arc(angle_deg=45.0)
        center_forward_m, center_lateral_m = _spawn_on_corral_arc(angle_deg=0.0)
        right_forward_m, right_lateral_m = _spawn_on_corral_arc(angle_deg=-45.0)
        return [
            GatherTargetSpec(
                id="ball_a",
                label="Ball A (far left)",
                start_visible=False,
                forward_m=left_forward_m,
                lateral_m=left_lateral_m,
            ),
            GatherTargetSpec(
                id="ball_b",
                label="Ball B (near center)",
                start_visible=True,
                forward_m=center_forward_m,
                lateral_m=center_lateral_m,
            ),
            GatherTargetSpec(
                id="ball_c",
                label="Ball C (far right)",
                start_visible=False,
                forward_m=right_forward_m,
                lateral_m=right_lateral_m,
            ),
        ]
    raise ValueError(f"Unsupported gather mission scenario: {scenario_id}")


def build_zone_spec(scenario_id: str) -> ZoneSpec:
    if scenario_id not in {"corral_single_ball_place", "gather_three_ball_zone"}:
        raise ValueError(f"Unsupported gather mission scenario: {scenario_id}")
    return ZoneSpec(
        id="corral_zone",
        label="Corral Zone",
        world_x=DEFAULT_ZONE_WORLD_X,
        world_y=DEFAULT_ZONE_WORLD_Y,
    )


def route_target_specs_for_provider(targets: list[GatherTargetSpec], *, zone: ZoneSpec) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for target in targets:
        details.append(
            {
                "target_id": target.id,
                "label": target.label,
                "start_visible": bool(target.start_visible),
                "forward_m": round(target.forward_m, 6),
                "lateral_m": round(target.lateral_m, 6),
                "zone_world": {
                    "x": round(zone.world_x, 6),
                    "y": round(zone.world_y, 6),
                    "radius_m": round(zone.retrieval_radius_m, 6),
                    "control_radius_m": round(zone.control_radius_m, 6),
                },
            }
        )
    return details


def world_pose_xyyaw(pose: dict[str, Any]) -> tuple[float, float, float] | None:
    x = _number(pose.get("x"))
    y = _number(pose.get("y"))
    yaw = _number(pose.get("yaw"))
    if x is None or y is None:
        return None
    return float(x), float(y), float(yaw or 0.0)


def point_xy(point: dict[str, Any]) -> tuple[float, float] | None:
    x = _number(point.get("x"))
    y = _number(point.get("y"))
    if x is None or y is None:
        return None
    return float(x), float(y)


def relative_point_robot_frame(robot_pose: dict[str, Any], point: dict[str, Any]) -> tuple[float, float] | None:
    robot_xyyaw = world_pose_xyyaw(robot_pose)
    point_xy_value = point_xy(point)
    if robot_xyyaw is None or point_xy_value is None:
        return None
    robot_x, robot_y, robot_yaw = robot_xyyaw
    point_x, point_y = point_xy_value
    dx = point_x - robot_x
    dy = point_y - robot_y
    cos_yaw = math.cos(robot_yaw)
    sin_yaw = math.sin(robot_yaw)
    rel_x = (cos_yaw * dx) + (sin_yaw * dy)
    rel_y = (-sin_yaw * dx) + (cos_yaw * dy)
    return rel_x, rel_y


def capture_snapshot(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    envelope: CaptureEnvelope | None = None,
) -> CaptureSnapshot | None:
    active_envelope = envelope or CaptureEnvelope()
    rel = relative_point_robot_frame(robot_pose, ball_pose)
    if rel is None:
        return None
    ball_x_m, ball_y_m = rel
    distance_m = math.hypot(ball_x_m, ball_y_m)
    bearing_rad = math.atan2(ball_y_m, max(ball_x_m, 1.0e-6))
    ball_ahead = ball_x_m > 0.0
    within_capture = (
        active_envelope.min_x_m <= ball_x_m <= active_envelope.max_x_m
        and abs(ball_y_m) <= active_envelope.max_abs_y_m
    )
    within_recapture = (
        ball_ahead
        and ball_x_m <= active_envelope.recapture_max_x_m
        and abs(ball_y_m) <= active_envelope.recapture_max_abs_y_m
    )
    return CaptureSnapshot(
        ball_x_m=round(ball_x_m, 6),
        ball_y_m=round(ball_y_m, 6),
        distance_m=round(distance_m, 6),
        bearing_rad=round(bearing_rad, 6),
        ball_ahead=ball_ahead,
        within_recapture_window=within_recapture,
        within_capture_window=within_capture,
        captured=within_capture,
    )


def zone_snapshot(ball_pose: dict[str, Any], zone: ZoneSpec) -> ZoneSnapshot | None:
    ball_xy = point_xy(ball_pose)
    if ball_xy is None:
        return None
    dx = ball_xy[0] - float(zone.world_x)
    dy = ball_xy[1] - float(zone.world_y)
    distance_m = math.hypot(dx, dy)
    control_radius_m = max(float(zone.control_radius_m), 0.0)
    retrieval_radius_m = max(float(zone.retrieval_radius_m), 0.0)
    center_inside_zone = distance_m <= control_radius_m
    return ZoneSnapshot(
        zone_distance_m=round(distance_m, 6),
        retrieval_distance_m=round(distance_m, 6),
        inside_zone=distance_m <= control_radius_m + DEFAULT_TARGET_BALL_RADIUS_M,
        center_inside_zone=center_inside_zone,
        inside_retrieval_corral=distance_m <= retrieval_radius_m + DEFAULT_TARGET_BALL_RADIUS_M,
        center_inside_retrieval_corral=distance_m <= retrieval_radius_m,
    )


def zone_dwell_complete(
    *,
    inside_zone: bool,
    zone_entry_monotonic: float | None,
    now_monotonic: float,
    dwell_s: float,
) -> bool:
    if not inside_zone or zone_entry_monotonic is None:
        return False
    return (float(now_monotonic) - float(zone_entry_monotonic)) >= max(float(dwell_s), 0.0)


def release_ready(
    *,
    capture: CaptureSnapshot | None,
    zone_score: ZoneSnapshot | None,
    zone: ZoneSpec,
    release_margin_m: float = DEFAULT_RELEASE_ZONE_MARGIN_M,
) -> bool:
    if capture is None or zone_score is None:
        return False
    if zone_score.center_inside_zone:
        return True
    return (
        secure_capture(capture)
        and capture.ball_x_m >= 0.16
        and float(zone_score.zone_distance_m) <= max(float(zone.control_radius_m), 0.05) + max(float(release_margin_m), 0.0)
    )


def capture_loss_detected(
    *,
    captured_now: bool,
    last_captured_monotonic: float | None,
    now_monotonic: float,
    loss_grace_s: float,
) -> bool:
    if captured_now:
        return False
    if last_captured_monotonic is None:
        return False
    return (float(now_monotonic) - float(last_captured_monotonic)) >= max(float(loss_grace_s), 0.0)


def pose_delta_m(previous_pose: dict[str, Any] | None, current_pose: dict[str, Any] | None) -> float | None:
    previous_xy = point_xy(previous_pose or {})
    current_xy = point_xy(current_pose or {})
    if previous_xy is None or current_xy is None:
        return None
    return round(math.hypot(current_xy[0] - previous_xy[0], current_xy[1] - previous_xy[1]), 6)


def goal_side_approach_snapshot(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    stage_distance_m: float = DEFAULT_STAGE_BEHIND_BALL_DISTANCE_M,
    stage_arrival_radius_m: float = DEFAULT_STAGE_ARRIVAL_RADIUS_M,
    stage_ready_longitudinal_projection_m: float = DEFAULT_STAGE_READY_LONGITUDINAL_PROJECTION_M,
    stage_ready_lateral_error_m: float = DEFAULT_STAGE_READY_LATERAL_ERROR_M,
    stage_ready_yaw_error_deg: float = DEFAULT_STAGE_READY_YAW_ERROR_DEG,
    goal_side_violation_projection_m: float = DEFAULT_GOAL_SIDE_VIOLATION_PROJECTION_M,
) -> dict[str, Any] | None:
    robot_xyyaw = world_pose_xyyaw(robot_pose)
    ball_xy = point_xy(ball_pose)
    if robot_xyyaw is None or ball_xy is None:
        return None
    robot_x, robot_y, robot_yaw = robot_xyyaw
    ball_x, ball_y = ball_xy
    push_dx = float(zone.world_x) - ball_x
    push_dy = float(zone.world_y) - ball_y
    push_norm = math.hypot(push_dx, push_dy)
    if push_norm <= 1.0e-6:
        return {
            "push_direction_yaw_deg": 0.0,
            "staging_pose_world": {"x": round(ball_x, 6), "y": round(ball_y, 6)},
            "staging_pose_distance_m": 0.0,
            "robot_longitudinal_projection_m": 0.0,
            "robot_lateral_error_m": 0.0,
            "yaw_error_deg": 0.0,
            "robot_on_goal_side": False,
            "entered_goal_side_before_capture": False,
            "staging_pose_reached": True,
            "approach_failure_reason": "",
        }
    push_ux = push_dx / push_norm
    push_uy = push_dy / push_norm
    push_direction_yaw = math.atan2(push_uy, push_ux)
    staging_x = ball_x - (float(stage_distance_m) * push_ux)
    staging_y = ball_y - (float(stage_distance_m) * push_uy)
    robot_from_ball_x = robot_x - ball_x
    robot_from_ball_y = robot_y - ball_y
    robot_longitudinal_projection_m = (robot_from_ball_x * push_ux) + (robot_from_ball_y * push_uy)
    robot_lateral_signed_m = (robot_from_ball_x * -push_uy) + (robot_from_ball_y * push_ux)
    robot_lateral_error_m = abs(robot_lateral_signed_m)
    yaw_error_deg = abs(math.degrees(normalize_angle(robot_yaw - push_direction_yaw)))
    staging_pose_distance_m = math.hypot(staging_x - robot_x, staging_y - robot_y)
    robot_on_goal_side = robot_longitudinal_projection_m > float(goal_side_violation_projection_m)
    staging_pose_reached = bool(
        staging_pose_distance_m <= float(stage_arrival_radius_m)
        and robot_longitudinal_projection_m <= float(stage_ready_longitudinal_projection_m)
        and robot_lateral_error_m <= float(stage_ready_lateral_error_m)
        and yaw_error_deg <= float(stage_ready_yaw_error_deg)
    )
    return {
        "push_direction_yaw_deg": round(math.degrees(push_direction_yaw), 6),
        "staging_pose_world": {"x": round(staging_x, 6), "y": round(staging_y, 6)},
        "staging_pose_distance_m": round(staging_pose_distance_m, 6),
        "robot_longitudinal_projection_m": round(robot_longitudinal_projection_m, 6),
        "robot_lateral_error_m": round(robot_lateral_error_m, 6),
        "robot_lateral_signed_m": round(robot_lateral_signed_m, 6),
        "yaw_error_deg": round(yaw_error_deg, 6),
        "robot_on_goal_side": bool(robot_on_goal_side),
        "entered_goal_side_before_capture": bool(robot_on_goal_side),
        "staging_pose_reached": bool(staging_pose_reached),
        "approach_failure_reason": "entered_goal_side_before_capture" if robot_on_goal_side else "",
    }


def pre_stage_arrival_snapshot(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    pre_stage_distance_m: float = DEFAULT_PRE_STAGE_BEHIND_BALL_DISTANCE_M,
    pre_stage_arrival_radius_m: float = DEFAULT_PRE_STAGE_ARRIVAL_RADIUS_M,
    pre_stage_ready_longitudinal_projection_m: float = DEFAULT_PRE_STAGE_READY_LONGITUDINAL_PROJECTION_M,
    pre_stage_ready_lateral_error_m: float = DEFAULT_PRE_STAGE_READY_LATERAL_ERROR_M,
    pre_stage_ready_yaw_error_deg: float = DEFAULT_PRE_STAGE_READY_YAW_ERROR_DEG,
    goal_side_violation_projection_m: float = DEFAULT_GOAL_SIDE_VIOLATION_PROJECTION_M,
) -> dict[str, Any] | None:
    snapshot = goal_side_approach_snapshot(
        robot_pose,
        ball_pose,
        zone=zone,
        stage_distance_m=pre_stage_distance_m,
        stage_arrival_radius_m=pre_stage_arrival_radius_m,
        stage_ready_longitudinal_projection_m=pre_stage_ready_longitudinal_projection_m,
        stage_ready_lateral_error_m=pre_stage_ready_lateral_error_m,
        stage_ready_yaw_error_deg=pre_stage_ready_yaw_error_deg,
        goal_side_violation_projection_m=goal_side_violation_projection_m,
    )
    if not isinstance(snapshot, dict):
        return None
    pre_stage_pose_distance_m = float(_number(snapshot.get("staging_pose_distance_m")) or 0.0)
    robot_longitudinal_projection_m = float(_number(snapshot.get("robot_longitudinal_projection_m")) or 0.0)
    robot_lateral_error_m = float(_number(snapshot.get("robot_lateral_error_m")) or 0.0)
    yaw_error_deg = float(_number(snapshot.get("yaw_error_deg")) or 0.0)
    robot_on_goal_side = bool(snapshot.get("robot_on_goal_side", False))
    close_in_pre_stage_pose_reached = (
        not robot_on_goal_side
        and pre_stage_pose_distance_m <= DEFAULT_PRE_STAGE_CLOSE_IN_READY_DISTANCE_M
        and robot_longitudinal_projection_m <= DEFAULT_PRE_STAGE_CLOSE_IN_READY_LONGITUDINAL_PROJECTION_M
        and robot_lateral_error_m <= DEFAULT_PRE_STAGE_CLOSE_IN_READY_LATERAL_ERROR_M
        and yaw_error_deg <= DEFAULT_PRE_STAGE_CLOSE_IN_READY_YAW_ERROR_DEG
    )
    deep_close_pre_stage_handoff = (
        not robot_on_goal_side
        and pre_stage_pose_distance_m <= DEFAULT_PRE_STAGE_DEEP_CLOSE_HANDOFF_DISTANCE_M
        and robot_longitudinal_projection_m <= DEFAULT_PRE_STAGE_DEEP_CLOSE_HANDOFF_LONGITUDINAL_PROJECTION_M
        and robot_lateral_error_m <= DEFAULT_PRE_STAGE_DEEP_CLOSE_HANDOFF_LATERAL_ERROR_M
        and yaw_error_deg <= DEFAULT_PRE_STAGE_DEEP_CLOSE_HANDOFF_YAW_ERROR_DEG
    )
    return {
        "push_direction_yaw_deg": float(snapshot.get("push_direction_yaw_deg", 0.0) or 0.0),
        "pre_stage_pose_world": (
            dict(snapshot.get("staging_pose_world", {}))
            if isinstance(snapshot.get("staging_pose_world"), dict)
            else {}
        ),
        "pre_stage_pose_distance_m": pre_stage_pose_distance_m,
        "robot_longitudinal_projection_m": robot_longitudinal_projection_m,
        "robot_lateral_error_m": robot_lateral_error_m,
        "robot_lateral_signed_m": float(_number(snapshot.get("robot_lateral_signed_m")) or 0.0),
        "yaw_error_deg": yaw_error_deg,
        "robot_on_goal_side": robot_on_goal_side,
        "entered_goal_side_before_capture": bool(snapshot.get("entered_goal_side_before_capture", False)),
        "deep_close_pre_stage_handoff": bool(deep_close_pre_stage_handoff),
        "pre_stage_pose_reached": bool(
            snapshot.get("staging_pose_reached", False)
            or close_in_pre_stage_pose_reached
            or deep_close_pre_stage_handoff
        ),
        "approach_failure_reason": str(snapshot.get("approach_failure_reason", "") or ""),
    }


def first_contact_push_alignment_deg(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
) -> float | None:
    snapshot = goal_side_approach_snapshot(robot_pose, ball_pose, zone=zone)
    if not isinstance(snapshot, dict):
        return None
    return _number(snapshot.get("yaw_error_deg"))


def approach_side_verdict(
    *,
    entered_goal_side_before_capture: bool,
    staging_pose_reached: bool,
    first_contact_push_alignment_deg: float | None,
    first_contact_alignment_pass_deg: float = DEFAULT_FIRST_CONTACT_ALIGNMENT_PASS_DEG,
) -> dict[str, Any]:
    alignment = _number(first_contact_push_alignment_deg)
    if bool(entered_goal_side_before_capture):
        return {"pass": False, "reason": "entered_goal_side_before_capture"}
    if not bool(staging_pose_reached):
        return {"pass": False, "reason": "staging_pose_not_reached"}
    if alignment is None:
        return {"pass": False, "reason": "missing_first_contact_alignment"}
    if alignment > float(first_contact_alignment_pass_deg):
        return {"pass": False, "reason": "misaligned_first_contact"}
    return {"pass": True, "reason": ""}


def compute_stage_command(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
) -> PlaceControlCommand | None:
    snapshot = goal_side_approach_snapshot(robot_pose, ball_pose, zone=zone)
    if not isinstance(snapshot, dict):
        return None
    staging_pose = snapshot.get("staging_pose_world", {}) if isinstance(snapshot.get("staging_pose_world"), dict) else {}
    stage_rel = relative_point_robot_frame(robot_pose, staging_pose)
    if stage_rel is None:
        return None
    stage_x_m, stage_y_m = stage_rel
    yaw_error_deg = float(_number(snapshot.get("yaw_error_deg")) or 0.0)
    staging_pose_distance_m = float(_number(snapshot.get("staging_pose_distance_m")) or 0.0)
    robot_on_goal_side = bool(snapshot.get("robot_on_goal_side", False))
    robot_longitudinal_projection_m = float(_number(snapshot.get("robot_longitudinal_projection_m")) or 0.0)
    robot_lateral_error_m = float(_number(snapshot.get("robot_lateral_error_m")) or 0.0)
    push_direction_yaw_deg = float(_number(snapshot.get("push_direction_yaw_deg")) or 0.0)
    push_direction_yaw = math.radians(push_direction_yaw_deg)
    robot_xyyaw = world_pose_xyyaw(robot_pose)
    robot_yaw = float(robot_xyyaw[2]) if robot_xyyaw is not None else 0.0
    if robot_on_goal_side or robot_longitudinal_projection_m > -0.02:
        desired_escape_yaw = normalize_angle(push_direction_yaw + math.pi)
        escape_yaw_error = normalize_angle(desired_escape_yaw - robot_yaw)
        angular = clamp((escape_yaw_error * 1.6) + (stage_y_m * 1.2), -0.7, 0.7)
        return PlaceControlCommand(
            mode="stage_escape_goal_side",
            linear_x=-0.08,
            angular_z=round(angular, 6),
            target_speed_scale=0.0,
            rationale="Robot is on the goal side of the ball; back away and arc behind it before first contact.",
        )
    close_in_align_handoff = (
        staging_pose_distance_m <= DEFAULT_STAGE_CLOSE_IN_ALIGN_DISTANCE_M
        and robot_longitudinal_projection_m <= DEFAULT_STAGE_CLOSE_IN_ALIGN_LONGITUDINAL_PROJECTION_M
        and robot_lateral_error_m <= DEFAULT_STAGE_CLOSE_IN_ALIGN_LATERAL_ERROR_M
    )
    if staging_pose_distance_m > DEFAULT_STAGE_ARRIVAL_RADIUS_M and not close_in_align_handoff:
        angular = clamp((stage_y_m * 1.8), -0.7, 0.7)
        linear = 0.0 if stage_x_m < 0.05 else min(0.10, max(0.03, stage_x_m * 0.18))
        return PlaceControlCommand(
            mode="stage_traverse",
            linear_x=round(linear, 6),
            angular_z=round(angular, 6),
            target_speed_scale=1.0 if linear > 0.0 else 0.0,
            rationale="Drive to the zone-opposite staging pose behind the ball before pushing.",
        )
    if yaw_error_deg > DEFAULT_STAGE_READY_YAW_ERROR_DEG:
        desired_push_yaw_error = normalize_angle(push_direction_yaw - robot_yaw)
        angular = clamp((desired_push_yaw_error * 0.9) + (stage_y_m * 1.2), -0.6, 0.6)
        if abs(angular) < 0.18:
            if abs(desired_push_yaw_error) > 1.0e-6:
                angular = 0.18 if desired_push_yaw_error >= 0.0 else -0.18
            else:
                angular = 0.18 if stage_y_m >= 0.0 else -0.18
        return PlaceControlCommand(
            mode="stage_align",
            linear_x=0.0,
            angular_z=round(angular, 6),
            target_speed_scale=0.0,
            rationale="Rotate in place so the first push sends the ball toward the corral.",
        )
    return PlaceControlCommand(
        mode="stage_ready",
        linear_x=0.0,
        angular_z=0.0,
        target_speed_scale=0.0,
        rationale="Robot is staged behind the ball and aligned for the push.",
    )


def compute_pre_stage_command(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
) -> PlaceControlCommand | None:
    snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone)
    if not isinstance(snapshot, dict):
        return None
    pre_stage_pose = snapshot.get("pre_stage_pose_world", {}) if isinstance(snapshot.get("pre_stage_pose_world"), dict) else {}
    pre_stage_rel = relative_point_robot_frame(robot_pose, pre_stage_pose)
    if pre_stage_rel is None:
        return None
    pre_stage_x_m, pre_stage_y_m = pre_stage_rel
    yaw_error_deg = float(_number(snapshot.get("yaw_error_deg")) or 0.0)
    pre_stage_distance_m = float(_number(snapshot.get("pre_stage_pose_distance_m")) or 0.0)
    pre_stage_pose_reached = bool(snapshot.get("pre_stage_pose_reached", False))
    deep_close_pre_stage_handoff = bool(snapshot.get("deep_close_pre_stage_handoff", False))
    robot_on_goal_side = bool(snapshot.get("robot_on_goal_side", False))
    robot_longitudinal_projection_m = float(_number(snapshot.get("robot_longitudinal_projection_m")) or 0.0)
    robot_lateral_error_m = float(_number(snapshot.get("robot_lateral_error_m")) or 0.0)
    robot_lateral_signed_m = float(_number(snapshot.get("robot_lateral_signed_m")) or 0.0)
    push_direction_yaw_deg = float(_number(snapshot.get("push_direction_yaw_deg")) or 0.0)
    push_direction_yaw = math.radians(push_direction_yaw_deg)
    robot_xyyaw = world_pose_xyyaw(robot_pose)
    if robot_xyyaw is None:
        return None
    robot_x, robot_y, robot_yaw = robot_xyyaw

    def _orbit_candidate(
        *,
        flank_sign: float,
        orbit_offset_m: float,
        behind_bias_m: float,
    ) -> dict[str, Any] | None:
        orbit_pose = {
            "x": round(
                float(pre_stage_pose.get("x", 0.0))
                + (flank_sign * orbit_offset_m * -math.sin(push_direction_yaw))
                - (behind_bias_m * math.cos(push_direction_yaw)),
                6,
            ),
            "y": round(
                float(pre_stage_pose.get("y", 0.0))
                + (flank_sign * orbit_offset_m * math.cos(push_direction_yaw))
                - (behind_bias_m * math.sin(push_direction_yaw)),
                6,
            ),
        }
        orbit_rel = relative_point_robot_frame(robot_pose, orbit_pose)
        if orbit_rel is None:
            return None
        orbit_x_m, orbit_y_m = orbit_rel
        heading_error = math.atan2(orbit_y_m, orbit_x_m)
        desired_escape_yaw = normalize_angle(
            math.atan2(
                float(orbit_pose.get("y", 0.0)) - robot_y,
                float(orbit_pose.get("x", 0.0)) - robot_x,
            )
            + math.pi
        )
        escape_yaw_error = normalize_angle(desired_escape_yaw - robot_yaw)
        ball_xy = point_xy(ball_pose)
        orbit_xy = point_xy(orbit_pose)
        behind_progress_m = 0.0
        if ball_xy is not None and orbit_xy is not None:
            behind_progress_m = -(
                ((orbit_xy[0] - ball_xy[0]) * math.cos(push_direction_yaw))
                + ((orbit_xy[1] - ball_xy[1]) * math.sin(push_direction_yaw))
            )
        return {
            "flank_sign": flank_sign,
            "orbit_pose": orbit_pose,
            "orbit_x_m": orbit_x_m,
            "orbit_y_m": orbit_y_m,
            "heading_error": heading_error,
            "escape_yaw_error": escape_yaw_error,
            "behind_progress_m": behind_progress_m,
        }
    orbit_offset_m = DEFAULT_PRE_STAGE_ORBIT_OFFSET_M + min(
        0.35,
        max(0.0, robot_longitudinal_projection_m) * 0.06,
    )
    behind_bias_m = min(
        0.75,
        max(0.0, robot_longitudinal_projection_m + 0.05) * 0.15,
    )
    orbit_candidates = [
        candidate
        for candidate in (
            _orbit_candidate(flank_sign=1.0, orbit_offset_m=orbit_offset_m, behind_bias_m=behind_bias_m),
            _orbit_candidate(flank_sign=-1.0, orbit_offset_m=orbit_offset_m, behind_bias_m=behind_bias_m),
        )
        if isinstance(candidate, dict)
    ]
    if not orbit_candidates:
        return None
    orbit_candidate = min(
        orbit_candidates,
        key=lambda candidate: (
            abs(float(candidate["heading_error"])),
            -float(candidate["behind_progress_m"]),
            abs(float(candidate["flank_sign"] - (-1.0 if robot_lateral_signed_m < 0.0 else 1.0))),
        ),
    )
    escape_candidate = min(
        orbit_candidates,
        key=lambda candidate: (
            abs(float(candidate["escape_yaw_error"])),
            -float(candidate["behind_progress_m"]),
            abs(float(candidate["flank_sign"] - (-1.0 if robot_lateral_signed_m < 0.0 else 1.0))),
        ),
    )
    orbit_pose = orbit_candidate["orbit_pose"]
    orbit_x_m = float(orbit_candidate["orbit_x_m"])
    orbit_y_m = float(orbit_candidate["orbit_y_m"])
    heading_error = float(orbit_candidate["heading_error"])
    if robot_on_goal_side or robot_longitudinal_projection_m > DEFAULT_PRE_STAGE_ESCAPE_RELEASE_PROJECTION_M:
        direct_reverse_escape_yaw = normalize_angle(
            math.atan2(
                float(pre_stage_pose.get("y", 0.0)) - robot_y,
                float(pre_stage_pose.get("x", 0.0)) - robot_x,
            )
            + math.pi
        )
        direct_reverse_escape_yaw_error = normalize_angle(direct_reverse_escape_yaw - robot_yaw)
        early_direct_reverse_escape_commit = bool(
            robot_on_goal_side
            and robot_longitudinal_projection_m >= DEFAULT_PRE_STAGE_ESCAPE_EARLY_DIRECT_COMMIT_MIN_PROJECTION_M
            and robot_lateral_error_m >= DEFAULT_PRE_STAGE_ESCAPE_EARLY_DIRECT_COMMIT_MIN_LATERAL_ERROR_M
            and (
                yaw_error_deg <= DEFAULT_PRE_STAGE_ESCAPE_EARLY_DIRECT_COMMIT_MAX_YAW_ERROR_DEG
                or abs(direct_reverse_escape_yaw_error)
                <= math.radians(DEFAULT_PRE_STAGE_ESCAPE_EARLY_DIRECT_COMMIT_MAX_REVERSE_YAW_ERROR_DEG)
            )
        )
        late_direct_reverse_escape_commit = bool(
            robot_on_goal_side
            and robot_longitudinal_projection_m <= DEFAULT_PRE_STAGE_ESCAPE_DIRECT_COMMIT_PROJECTION_M
            and abs(float(escape_candidate["escape_yaw_error"]))
            <= math.radians(DEFAULT_PRE_STAGE_ESCAPE_DIRECT_COMMIT_MAX_ORBIT_YAW_ERROR_DEG)
        )
        direct_reverse_escape_commit = early_direct_reverse_escape_commit or late_direct_reverse_escape_commit
        deepen_escape_projection = (not robot_on_goal_side) or direct_reverse_escape_commit
        if deepen_escape_projection:
            escape_yaw_error = direct_reverse_escape_yaw_error
            angular = clamp(escape_yaw_error * 1.1, -0.8, 0.8)
            linear = -min(
                0.18,
                max(
                    0.12,
                    abs(pre_stage_x_m) * 0.18,
                    pre_stage_distance_m * 0.10,
                ),
            )
        else:
            escape_yaw_error = float(escape_candidate["escape_yaw_error"])
            escape_orbit_y_m = float(escape_candidate["orbit_y_m"])
            angular = clamp((escape_yaw_error * 1.35) + (escape_orbit_y_m * 0.04), -0.8, 0.8)
            linear = -0.12 if abs(escape_yaw_error) <= 0.45 else DEFAULT_PRE_STAGE_ESCAPE_LINEAR_X_MPS
        floor_error_threshold_rad = (
            DEFAULT_PRE_STAGE_ESCAPE_DIRECT_REVERSE_MIN_FLOOR_ERROR_RAD
            if direct_reverse_escape_commit
            else 0.20
        )
        if abs(angular) < 0.20 and abs(escape_yaw_error) > floor_error_threshold_rad:
            angular = 0.20 if escape_yaw_error >= 0.0 else -0.20
        return PlaceControlCommand(
            mode="pre_stage_escape_goal_side",
            linear_x=linear,
            angular_z=round(angular, 6),
            target_speed_scale=0.0,
            rationale=(
                "Keep backing into the behind-ball corridor until the release projection is satisfied."
                if deepen_escape_projection
                else "Reverse-arc toward the stronger flank waypoint until the robot is no longer trapped on the goal side."
            ),
        )
    if robot_longitudinal_projection_m > -0.05:
        if orbit_x_m < 0.0 or abs(heading_error) > 0.35:
            angular = clamp((heading_error * 1.6), -0.8, 0.8)
            if abs(angular) < 0.20:
                angular = 0.20 if heading_error >= 0.0 else -0.20
            return PlaceControlCommand(
                mode="pre_stage_orbit_turn",
                linear_x=0.0,
                angular_z=round(angular, 6),
                target_speed_scale=0.0,
                rationale="Turn toward the flank waypoint so the coarse arrival comes from behind the ball.",
            )
        angular = clamp((orbit_y_m * 1.1), -0.8, 0.8)
        linear = min(
            0.30,
            max(0.14 if robot_longitudinal_projection_m > 0.0 else 0.08, orbit_x_m * 0.24),
        )
        return PlaceControlCommand(
            mode="pre_stage_orbit",
            linear_x=round(linear, 6),
            angular_z=round(angular, 6),
            target_speed_scale=1.0,
            rationale="Orbit to a flank waypoint so the coarse arrival reaches the behind-ball side first.",
        )
    heading_error = math.atan2(pre_stage_y_m, max(pre_stage_x_m, 1.0e-6))
    recover_push_yaw = robot_longitudinal_projection_m <= -0.10 and yaw_error_deg > 90.0
    reverse_traverse_ready = (
        not pre_stage_pose_reached
        and
        pre_stage_distance_m > DEFAULT_PRE_STAGE_ARRIVAL_RADIUS_M
        and robot_longitudinal_projection_m <= DEFAULT_PRE_STAGE_ESCAPE_RELEASE_PROJECTION_M
        and not recover_push_yaw
        and pre_stage_x_m < 0.0
    )
    if reverse_traverse_ready:
        desired_reverse_yaw = normalize_angle(
            math.atan2(
                float(pre_stage_pose.get("y", 0.0)) - robot_y,
                float(pre_stage_pose.get("x", 0.0)) - robot_x,
            )
            + math.pi
        )
        reverse_yaw_error = normalize_angle(desired_reverse_yaw - robot_yaw)
        angular = clamp(reverse_yaw_error * 1.1, -0.8, 0.8)
        if abs(angular) < 0.20 and abs(reverse_yaw_error) > 0.20:
            angular = 0.20 if reverse_yaw_error >= 0.0 else -0.20
        if abs(reverse_yaw_error) > 0.65:
            linear = -0.12
        else:
            linear = -min(
                0.24,
                max(
                    0.18,
                    abs(pre_stage_x_m) * 0.30,
                    pre_stage_distance_m * 0.18,
                ),
            )
        return PlaceControlCommand(
            mode="pre_stage_traverse",
            linear_x=round(linear, 6),
            angular_z=round(angular, 6),
            target_speed_scale=1.0,
            rationale="Back into the coarse behind-ball pre-stage pose while holding the push line.",
        )
    if not pre_stage_pose_reached and pre_stage_distance_m > DEFAULT_PRE_STAGE_ARRIVAL_RADIUS_M and (
        pre_stage_x_m < 0.0
        or abs(heading_error) > 0.45
        or recover_push_yaw
    ):
        if recover_push_yaw:
            desired_push_yaw_error = normalize_angle(push_direction_yaw - robot_yaw)
            angular = clamp((desired_push_yaw_error * 1.1) + (pre_stage_y_m * 0.4), -0.8, 0.8)
        else:
            angular = clamp((heading_error * 1.6), -0.8, 0.8)
        if abs(angular) < 0.20:
            if recover_push_yaw:
                angular = 0.20 if desired_push_yaw_error >= 0.0 else -0.20
            else:
                angular = 0.20 if heading_error >= 0.0 else -0.20
        return PlaceControlCommand(
            mode="pre_stage_turn",
            linear_x=0.0,
            angular_z=round(angular, 6),
            target_speed_scale=0.0,
            rationale=(
                "Rotate back onto the push line now that the robot has crossed behind the ball."
                if recover_push_yaw
                else "Rotate first so the coarse arrival stays behind the ball."
            ),
        )
    if not pre_stage_pose_reached and pre_stage_distance_m > DEFAULT_PRE_STAGE_ARRIVAL_RADIUS_M:
        angular = clamp((pre_stage_y_m * 1.2), -0.8, 0.8)
        linear = min(0.30, max(0.06, pre_stage_x_m * 0.28))
        return PlaceControlCommand(
            mode="pre_stage_traverse",
            linear_x=round(linear, 6),
            angular_z=round(angular, 6),
            target_speed_scale=1.0,
            rationale="Drive to the coarse behind-ball pre-stage pose before handing off to fine staging.",
        )
    if deep_close_pre_stage_handoff:
        return PlaceControlCommand(
            mode="pre_stage_ready",
            linear_x=0.0,
            angular_z=0.0,
            target_speed_scale=0.0,
            rationale="Robot is deep behind the ball and close enough to hand off into fine staging.",
        )
    if yaw_error_deg > DEFAULT_PRE_STAGE_READY_YAW_ERROR_DEG:
        desired_push_yaw_error = normalize_angle(push_direction_yaw - robot_yaw)
        angular = clamp((desired_push_yaw_error * 0.9) + (pre_stage_y_m * 1.0), -0.6, 0.6)
        if abs(angular) < 0.18:
            if abs(desired_push_yaw_error) > 1.0e-6:
                angular = 0.18 if desired_push_yaw_error >= 0.0 else -0.18
            else:
                angular = 0.18 if pre_stage_y_m >= 0.0 else -0.18
        return PlaceControlCommand(
            mode="pre_stage_align",
            linear_x=0.0,
            angular_z=round(angular, 6),
            target_speed_scale=0.0,
            rationale="Rotate to face the push line before fine staging begins.",
        )
    return PlaceControlCommand(
        mode="pre_stage_ready",
        linear_x=0.0,
        angular_z=0.0,
        target_speed_scale=0.0,
        rationale="Robot reached the coarse behind-ball arrival pose.",
    )


def compute_capture_command(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    envelope: CaptureEnvelope | None = None,
) -> PlaceControlCommand | None:
    snapshot = capture_snapshot(robot_pose, ball_pose, envelope)
    if snapshot is None:
        return None
    if snapshot.captured:
        if secure_capture(snapshot, envelope):
            return PlaceControlCommand(
                mode="captured",
                linear_x=0.0,
                angular_z=0.0,
                target_speed_scale=0.0,
                rationale="Ball is securely seated inside the capture envelope.",
            )
        angular = clamp(snapshot.ball_y_m * 6.0, -0.20, 0.20)
        linear = 0.05 if abs(float(snapshot.ball_y_m)) <= 0.02 else 0.035
        if float(snapshot.ball_x_m) > float((envelope or CaptureEnvelope()).seated_max_x_m) + 0.01:
            linear = max(linear, 0.055)
        return PlaceControlCommand(
            mode="capture_seat",
            linear_x=round(linear, 6),
            angular_z=round(angular, 6),
            target_speed_scale=0.55,
            rationale="Ball is inside the spur but still too far forward; ease it deeper before place.",
        )

    if not snapshot.ball_ahead:
        angular = clamp(1.2 if snapshot.ball_y_m >= 0.0 else -1.2, -1.2, 1.2)
        return PlaceControlCommand(
            mode="reorient",
            linear_x=0.0,
            angular_z=angular,
            target_speed_scale=0.0,
            rationale="Ball fell behind the robot; rotate before recapture.",
        )

    angular = clamp((snapshot.ball_y_m * 7.5) + (snapshot.bearing_rad * 0.7), -1.0, 1.0)
    linear = 0.14
    if abs(snapshot.ball_y_m) > 0.06:
        linear = 0.075
    elif snapshot.ball_x_m > 0.22:
        linear = 0.16
    return PlaceControlCommand(
        mode="capture",
        linear_x=round(linear, 6),
        angular_z=round(angular, 6),
        target_speed_scale=1.0,
        rationale="Center the ball between the catcher rails and drive forward.",
    )


def capture_entry_snapshot(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    envelope: CaptureEnvelope | None = None,
    goal_side_violation_projection_m: float = DEFAULT_GOAL_SIDE_VIOLATION_PROJECTION_M,
    ready_ball_x_m: float = DEFAULT_CAPTURE_ENTRY_READY_BALL_X_M,
    ready_abs_ball_y_m: float = DEFAULT_CAPTURE_ENTRY_READY_ABS_BALL_Y_M,
) -> dict[str, Any] | None:
    capture = capture_snapshot(robot_pose, ball_pose, envelope)
    approach = goal_side_approach_snapshot(
        robot_pose,
        ball_pose,
        zone=zone,
        goal_side_violation_projection_m=goal_side_violation_projection_m,
    )
    if capture is None or not isinstance(approach, dict):
        return None
    return {
        "push_direction_yaw_deg": float(approach.get("push_direction_yaw_deg", 0.0) or 0.0),
        "robot_on_goal_side": bool(approach.get("robot_on_goal_side", False)),
        "entered_goal_side_before_capture": bool(approach.get("entered_goal_side_before_capture", False)),
        "robot_longitudinal_projection_m": float(_number(approach.get("robot_longitudinal_projection_m")) or 0.0),
        "robot_lateral_error_m": float(_number(approach.get("robot_lateral_error_m")) or 0.0),
        "ball_ahead": bool(capture.ball_ahead),
        "ball_x_m": float(capture.ball_x_m),
        "ball_y_m": float(capture.ball_y_m),
        "distance_m": float(capture.distance_m),
        "bearing_rad": float(capture.bearing_rad),
        "capture_entry_reached": bool(
            capture.ball_ahead
            and (
                (
                    float(capture.ball_x_m) <= float(ready_ball_x_m)
                    and abs(float(capture.ball_y_m)) <= float(ready_abs_ball_y_m)
                )
                or (
                    float(capture.ball_x_m) <= DEFAULT_CAPTURE_ENTRY_CENTERED_READY_BALL_X_M
                    and abs(float(capture.ball_y_m)) <= DEFAULT_CAPTURE_ENTRY_CENTERED_READY_ABS_BALL_Y_M
                )
                or (
                    float(capture.ball_x_m) <= DEFAULT_CAPTURE_ENTRY_PLUS45_FINISH_READY_BALL_X_M
                    and abs(float(capture.ball_y_m)) <= DEFAULT_CAPTURE_ENTRY_PLUS45_FINISH_READY_ABS_BALL_Y_M
                    and abs(float(capture.bearing_rad)) <= DEFAULT_CAPTURE_ENTRY_PLUS45_FINISH_READY_MAX_BEARING_RAD
                )
            )
        ),
    }


def compute_capture_entry_command(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    envelope: CaptureEnvelope | None = None,
) -> PlaceControlCommand | None:
    snapshot = capture_entry_snapshot(robot_pose, ball_pose, zone=zone, envelope=envelope)
    if not isinstance(snapshot, dict):
        return None
    if bool(snapshot.get("capture_entry_reached", False)):
        return PlaceControlCommand(
            mode="capture_entry_ready",
            linear_x=0.0,
            angular_z=0.0,
            target_speed_scale=0.0,
            rationale="Ball is centered in the short capture-entry corridor; hand off to generic capture.",
        )
    if not bool(snapshot.get("ball_ahead", False)):
        angular = clamp(0.45 if float(snapshot.get("ball_y_m", 0.0) or 0.0) >= 0.0 else -0.45, -0.45, 0.45)
        return PlaceControlCommand(
            mode="capture_entry_reorient",
            linear_x=0.0,
            angular_z=round(angular, 6),
            target_speed_scale=0.0,
            rationale="Rotate locally until the ball is back ahead before closing the final capture gap.",
        )

    ball_y_m = float(snapshot.get("ball_y_m", 0.0) or 0.0)
    bearing_rad = float(snapshot.get("bearing_rad", 0.0) or 0.0)
    ball_x_m = float(snapshot.get("ball_x_m", 0.0) or 0.0)
    if (
        ball_x_m > DEFAULT_CAPTURE_ENTRY_CENTERED_CLOSE_MIN_BALL_X_M
        and abs(ball_y_m) <= DEFAULT_CAPTURE_ENTRY_CENTERED_CLOSE_MAX_ABS_BALL_Y_M
        and abs(bearing_rad) <= DEFAULT_CAPTURE_ENTRY_CENTERED_CLOSE_MAX_BEARING_RAD
    ):
        angular = clamp((ball_y_m * 9.0) + (bearing_rad * 0.85), -0.25, 0.25)
        return PlaceControlCommand(
            mode="capture_entry",
            linear_x=0.07,
            angular_z=round(angular, 6),
            target_speed_scale=0.45,
            rationale="The ball is already centered; close the final capture gap before oscillation reopens it.",
        )
    angular = clamp((ball_y_m * 9.0) + (bearing_rad * 0.85), -0.45, 0.45)
    linear = 0.045
    if abs(ball_y_m) > 0.06:
        linear = 0.020
    elif ball_x_m > 0.55:
        linear = 0.055
    return PlaceControlCommand(
        mode="capture_entry",
        linear_x=round(linear, 6),
        angular_z=round(angular, 6),
        target_speed_scale=0.45,
        rationale="Close the final gap from staged pose into a capture-ready corridor without overdriving through the ball.",
    )


def compute_place_command(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    envelope: CaptureEnvelope | None = None,
) -> PlaceControlCommand | None:
    active_envelope = envelope or CaptureEnvelope()
    capture = capture_snapshot(robot_pose, ball_pose, active_envelope)
    zone_rel = relative_point_robot_frame(
        robot_pose,
        {"x": float(zone.world_x), "y": float(zone.world_y)},
    )
    if capture is None or zone_rel is None:
        return None
    zone_x_m, zone_y_m = zone_rel
    zone_heading_rad = math.atan2(zone_y_m, max(zone_x_m, 1.0e-6))
    zone_distance = math.hypot(zone_x_m, zone_y_m)
    zone_radius = max(zone.control_radius_m, 0.05)
    ball_zone_score = zone_snapshot(ball_pose, zone)
    ball_zone_distance = ball_zone_score.zone_distance_m if ball_zone_score else zone_distance
    inside_retrieval_corral = bool(ball_zone_score and ball_zone_score.center_inside_retrieval_corral)
    ball_to_zone_x_m = zone_x_m - capture.ball_x_m
    ball_to_zone_y_m = zone_y_m - capture.ball_y_m
    near_zone = ball_zone_distance < zone_radius + 0.35
    final_approach = ball_zone_distance < zone_radius + 0.25
    finish_push_corridor = (
        near_zone
        and ball_to_zone_x_m > 0.08
        and abs(ball_to_zone_y_m) <= 0.20
    )
    if not capture.captured:
        if inside_retrieval_corral:
            angular = clamp((ball_to_zone_y_m * 5.0) + (zone_heading_rad * 0.25), -0.25, 0.25)
            linear = 0.0
            if capture.within_recapture_window and abs(ball_to_zone_y_m) > 0.16:
                linear = 0.006
            return PlaceControlCommand(
                mode="retrieval_hold" if capture.within_recapture_window else "capture",
                linear_x=round(linear, 6),
                angular_z=round(angular, 6),
                target_speed_scale=0.25 if linear > 0.0 else 0.0,
                rationale="Ball is already inside the retrieval corral; stop injecting speed and let it settle.",
            )
        angular = clamp((capture.ball_y_m * 12.0) + (zone_heading_rad * 0.6), -1.0, 1.0)
        if finish_push_corridor and capture.within_recapture_window:
            angular = clamp(capture.ball_y_m * 6.0, -0.25, 0.25)
        elif near_zone:
            angular = clamp((ball_to_zone_y_m * 9.0) + (zone_heading_rad * 0.45), -0.65, 0.65)
        if final_approach and abs(ball_to_zone_y_m) <= 0.10:
            angular = clamp(angular, -0.45, 0.45)
        linear = 0.055 if capture.within_recapture_window else 0.025
        if finish_push_corridor and capture.within_recapture_window:
            linear = 0.03
        if (
            capture.within_recapture_window
            and ball_zone_distance > zone_radius + 0.40
            and abs(capture.ball_y_m) <= 0.02
        ):
            linear = 0.075
        elif (
            capture.within_recapture_window
            and ball_zone_distance > zone_radius + 0.30
            and abs(capture.ball_y_m) <= 0.04
        ):
            linear = max(linear, 0.065)
        if abs(capture.ball_y_m) > 0.05:
            linear = min(linear, 0.022)
        if near_zone:
            linear = min(linear, 0.016)
            if finish_push_corridor and capture.within_recapture_window:
                linear = max(linear, 0.018)
            if abs(ball_to_zone_y_m) <= 0.10 and ball_to_zone_x_m > -0.05:
                linear = max(linear, 0.014)
            elif abs(ball_to_zone_y_m) > 0.16:
                linear = min(linear, 0.006)
        if final_approach:
            linear = min(linear, 0.012)
            if finish_push_corridor and capture.within_recapture_window:
                linear = max(linear, 0.012)
            if abs(ball_to_zone_y_m) <= 0.08 and ball_to_zone_x_m > -0.04:
                linear = max(linear, 0.012)
        if final_approach and abs(ball_to_zone_y_m) > 0.18 and ball_to_zone_x_m < 0.05 and not capture.within_recapture_window:
            linear = 0.0
        turn_scale = max(0.25, 1.0 - min(abs(angular), 1.0) * 0.60)
        return PlaceControlCommand(
            mode="place_recapture" if capture.within_recapture_window else "capture",
            linear_x=round(linear * turn_scale, 6),
            angular_z=round(angular, 6),
            target_speed_scale=round(turn_scale, 6),
            rationale="Gently reel the ball back under the catcher while preserving the zone heading.",
        )

    if marginal_capture(capture):
        angular = clamp((capture.ball_y_m * 5.0) + (zone_heading_rad * 0.35), -0.18, 0.18)
        return PlaceControlCommand(
            mode="place_settle",
            linear_x=0.0,
            angular_z=round(angular, 6),
            target_speed_scale=0.0,
            rationale="Ball is marginally captured; hold and settle before the final push.",
        )

    if inside_retrieval_corral:
        angular = clamp((ball_to_zone_y_m * 5.0) + (zone_heading_rad * 0.25), -0.18, 0.18)
        linear = 0.0
        if abs(ball_to_zone_y_m) > 0.14 and capture.ball_x_m < 0.18:
            linear = 0.006
        return PlaceControlCommand(
            mode="retrieval_hold",
            linear_x=round(linear, 6),
            angular_z=round(angular, 6),
            target_speed_scale=0.25 if linear > 0.0 else 0.0,
            rationale="Ball is already practically retrieved; hold position and let turf friction finish the settle.",
        )

    if front_escape_risk(capture, active_envelope) and not release_ready(capture=capture, zone_score=ball_zone_score, zone=zone):
        angular = clamp((capture.ball_y_m * 4.0) + (zone_heading_rad * 0.30), -0.16, 0.16)
        linear = 0.018 if near_zone else 0.04
        if not near_zone and abs(float(capture.ball_y_m)) <= 0.02:
            linear = max(linear, 0.045)
        return PlaceControlCommand(
            mode="place_retention",
            linear_x=round(linear, 6),
            angular_z=round(angular, 6),
            target_speed_scale=0.45,
            rationale="Ball is riding the front of the spur; pull the catcher back under it before release.",
        )

    angular = clamp((capture.ball_y_m * 9.0) + (zone_heading_rad * 1.0), -1.0, 1.0)
    if finish_push_corridor:
        angular = clamp(capture.ball_y_m * 4.5, -0.22, 0.22)
    elif near_zone:
        angular = clamp((ball_to_zone_y_m * 8.0) + (zone_heading_rad * 0.55), -0.65, 0.65)
    linear = 0.05
    if finish_push_corridor:
        linear = 0.03
    if (
        ball_zone_distance > zone_radius + 0.40
        and capture.ball_x_m < 0.18
        and abs(capture.ball_y_m) <= 0.02
    ):
        linear = 0.06
    elif (
        ball_zone_distance > zone_radius + 0.30
        and capture.ball_x_m < 0.17
        and abs(capture.ball_y_m) <= 0.03
    ):
        linear = max(linear, 0.055)
    if capture.ball_x_m > 0.20:
        linear = min(linear, 0.025)
    if abs(capture.ball_y_m) > 0.05:
        linear = min(linear, 0.03)
    if near_zone:
        linear = 0.016
        if finish_push_corridor:
            linear = 0.018
        if abs(ball_to_zone_y_m) <= 0.04 and ball_to_zone_x_m > -0.03:
            linear = max(linear, 0.016)
    if final_approach:
        linear = min(linear, 0.014)
        if finish_push_corridor:
            linear = max(linear, 0.016)
    if ball_zone_distance < zone_radius + 0.12:
        linear = 0.004
    if ball_zone_distance < zone_radius + 0.10 and abs(ball_to_zone_y_m) > 0.06:
        linear = 0.0
    turn_scale = max(0.45, 1.0 - min(abs(angular), 1.0) * 0.35) if finish_push_corridor else max(0.30, 1.0 - min(abs(angular), 1.0) * 0.55)
    return PlaceControlCommand(
        mode="place",
        linear_x=round(linear * turn_scale, 6),
        angular_z=round(angular, 6),
        target_speed_scale=round(turn_scale, 6),
        rationale="Hold the ball in the catcher while steering toward the zone center.",
    )


def summarize_release_settle_trace(
    *,
    surface_profile: str,
    zone: ZoneSpec,
    release_samples: list[dict[str, Any]],
    release_recontact_count: int,
) -> ReleaseSettleMetrics:
    if not release_samples:
        return ReleaseSettleMetrics(
            surface_profile=str(surface_profile or ""),
            release_distance_to_zone_center_m=0.0,
            max_overshoot_distance_m=0.0,
            final_settle_distance_m=0.0,
            settle_time_s=0.0,
            release_recontact_count=int(release_recontact_count),
            settled_inside_zone=False,
            final_inside_retrieval_corral=False,
            final_center_inside_zone=False,
            ball_stopped_in_corral=False,
            rolled_away_after_release=False,
            settled_in_corral_pass=False,
        )

    first = release_samples[0]
    last = release_samples[-1]
    first_inside_index: int | None = None
    for index, sample in enumerate(release_samples):
        if bool(sample.get("inside_retrieval_corral")) or bool(sample.get("center_inside_retrieval_corral")):
            first_inside_index = index
            break
    overshoot_samples = release_samples[first_inside_index:] if first_inside_index is not None else release_samples
    max_overshoot_distance_m = 0.0
    for sample in overshoot_samples:
        distance = _number(sample.get("zone_distance_m"))
        if distance is None:
            continue
        max_overshoot_distance_m = max(
            max_overshoot_distance_m,
            max(0.0, float(distance) - max(float(zone.retrieval_radius_m), 0.0)),
        )
    retrieval_center_inside_seen = False
    rolled_away_after_release = False
    stable_start_elapsed_s: float | None = None
    ball_stopped_in_corral = False
    for sample in release_samples:
        retrieval_center_inside = bool(sample.get("center_inside_retrieval_corral", False))
        elapsed_s = _number(sample.get("elapsed_s")) or 0.0
        ball_motion_m = _number(sample.get("ball_motion_m"))
        if retrieval_center_inside:
            retrieval_center_inside_seen = True
            if ball_motion_m is not None and ball_motion_m <= DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M:
                stable_start_elapsed_s = elapsed_s if stable_start_elapsed_s is None else stable_start_elapsed_s
                if (elapsed_s - stable_start_elapsed_s) >= DEFAULT_RELEASE_SETTLE_STABLE_WINDOW_S:
                    ball_stopped_in_corral = True
            else:
                stable_start_elapsed_s = None
            continue
        if retrieval_center_inside_seen:
            rolled_away_after_release = True
        stable_start_elapsed_s = None
    settle_time_s = max(
        (_number(last.get("elapsed_s")) or 0.0) - (_number(first.get("elapsed_s")) or 0.0),
        0.0,
    )
    final_inside_retrieval_corral = bool(last.get("center_inside_retrieval_corral", False))
    final_center_inside_zone = bool(last.get("center_inside_zone", False))
    settled_inside_zone = bool(last.get("center_inside_retrieval_corral") or last.get("inside_retrieval_corral"))
    settled_pass = final_inside_retrieval_corral and ball_stopped_in_corral and not rolled_away_after_release
    return ReleaseSettleMetrics(
        surface_profile=str(surface_profile or ""),
        release_distance_to_zone_center_m=round(_number(first.get("zone_distance_m")) or 0.0, 6),
        max_overshoot_distance_m=round(max_overshoot_distance_m, 6),
        final_settle_distance_m=round(_number(last.get("zone_distance_m")) or 0.0, 6),
        settle_time_s=round(settle_time_s, 6),
        release_recontact_count=int(release_recontact_count),
        settled_inside_zone=settled_inside_zone,
        final_inside_retrieval_corral=final_inside_retrieval_corral,
        final_center_inside_zone=final_center_inside_zone,
        ball_stopped_in_corral=ball_stopped_in_corral,
        rolled_away_after_release=rolled_away_after_release,
        settled_in_corral_pass=settled_pass,
    )


def campaign_pass(runs: list[dict[str, Any]]) -> bool:
    if not runs:
        return False
    return all(gather_run_pass(item) for item in runs)


def summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    settled_flags = [settled_in_corral_pass(item) for item in runs]
    run_pass_flags = [gather_run_pass(item) for item in runs]
    clean_retention_flags = [clean_retention_pass(item) for item in runs]
    approach_side_flags = [
        bool((item.get("approach_side_verdict", {}) if isinstance(item.get("approach_side_verdict"), dict) else {}).get("pass", False))
        for item in runs
    ]
    mission_times = [
        float(item.get("mission_time_s", 0.0) or 0.0)
        for item, run_pass in zip(runs, run_pass_flags)
        if run_pass
    ]
    placed_counts = [int(item.get("placed_count", 0) or 0) for item in runs]
    retrieved_counts = [int(item.get("retrieved_count", 0) or 0) for item in runs]
    capture_losses = [int(item.get("capture_loss_count", 0) or 0) for item in runs]
    stopped_with_capture_flags = [bool(item.get("stopped_with_ball_captured", False)) for item in runs]
    release_started_with_capture_flags = [bool(item.get("release_started_with_capture", False)) for item in runs]
    final_inside_retrieval_flags = [bool(item.get("final_inside_retrieval_corral", False)) for item in runs]
    final_center_inside_flags = [bool(item.get("final_center_inside_zone", False)) for item in runs]
    ball_stopped_flags = [bool(item.get("ball_stopped_in_corral", False)) for item in runs]
    rolled_away_flags = [bool(item.get("rolled_away_after_release", False)) for item in runs]
    final_all_targets_inside_flags = [bool(item.get("final_all_targets_inside_retrieval_corral", False)) for item in runs]
    final_all_targets_stopped_flags = [bool(item.get("final_all_targets_stopped", False)) for item in runs]
    final_three_ball_flags = [bool(item.get("final_three_ball_corral_pass", False)) for item in runs]
    settle_distances = [
        float(item.get("final_settle_distance_m", 0.0) or 0.0)
        for item, run_pass in zip(runs, run_pass_flags)
        if run_pass and item.get("final_settle_distance_m") not in {None, ""}
    ]
    overshoot_distances = [
        float(item.get("max_overshoot_distance_m", 0.0) or 0.0)
        for item in runs
        if item.get("max_overshoot_distance_m") not in {None, ""}
    ]
    settle_times = [
        float(item.get("settle_time_s", 0.0) or 0.0)
        for item, run_pass in zip(runs, run_pass_flags)
        if run_pass and item.get("settle_time_s") not in {None, ""}
    ]
    release_recontacts = [int(item.get("release_recontact_count", 0) or 0) for item in runs]
    zone_edge_correction_counts = [int(item.get("zone_edge_correction_count", 0) or 0) for item in runs]
    place_controller_reentry_counts = [int(item.get("place_controller_reentry_count", 0) or 0) for item in runs]
    post_visit_revisit_counts = [int(item.get("post_visit_revisit_count", 0) or 0) for item in runs]
    settle_no_chase_flags = [bool(item.get("settle_no_chase_activated", False)) for item in runs]
    entered_goal_side_flags = [bool(item.get("entered_goal_side_before_capture", False)) for item in runs]
    pre_stage_pose_reached_flags = [bool(item.get("pre_stage_pose_reached", False)) for item in runs]
    pre_stage_handoff_flags = [bool(item.get("pre_stage_handoff_pass", False)) for item in runs]
    staging_pose_reached_flags = [bool(item.get("staging_pose_reached", False)) for item in runs]
    first_contact_alignment_values = [
        float(item.get("first_contact_push_alignment_deg", 0.0) or 0.0)
        for item in runs
        if item.get("first_contact_push_alignment_deg") not in {None, ""}
    ]
    stage_times = [
        float(item.get("stage_time_s", 0.0) or 0.0)
        for item in runs
        if item.get("stage_time_s") not in {None, ""}
    ]
    pre_stage_times = [
        float(item.get("pre_stage_time_s", 0.0) or 0.0)
        for item in runs
        if item.get("pre_stage_time_s") not in {None, ""}
    ]
    handoff_kinds = sorted({str(item.get("handoff_kind", "") or "") for item in runs if str(item.get("handoff_kind", "") or "").strip()})
    settle_exit_reasons = sorted(
        {
            str(item.get("settle_exit_reason", "") or "")
            for item in runs
            if str(item.get("settle_exit_reason", "") or "").strip()
        }
    )
    settle_no_chase_exit_reasons = sorted(
        {
            str(item.get("settle_no_chase_exit_reason", "") or "")
            for item in runs
            if str(item.get("settle_no_chase_exit_reason", "") or "").strip() and str(item.get("settle_no_chase_exit_reason", "") or "").strip() != "none"
        }
    )
    release_gate_blocked_reasons = sorted(
        {
            str(item.get("release_gate_blocked_reason", "") or "")
            for item in runs
            if str(item.get("release_gate_blocked_reason", "") or "").strip() and str(item.get("release_gate_blocked_reason", "") or "").strip() != "none"
        }
    )
    approach_failure_reasons = sorted(
        {
            str(item.get("approach_failure_reason", "") or "")
            for item in runs
            if str(item.get("approach_failure_reason", "") or "").strip()
        }
    )
    surface_profiles = sorted({str(item.get("surface_profile", "") or "") for item in runs if str(item.get("surface_profile", "") or "").strip()})
    summary = {
        "pass_count": sum(1 for flag in run_pass_flags if flag),
        "placed_count_max": max(placed_counts) if placed_counts else 0,
        "placed_count_min": min(placed_counts) if placed_counts else 0,
        "capture_loss_count_total": sum(capture_losses),
        "settled_in_corral_pass_count": sum(1 for flag in settled_flags if flag),
        "settled_in_corral_fail_count": sum(1 for flag in settled_flags if not flag),
        "final_inside_retrieval_corral_count": sum(1 for flag in final_inside_retrieval_flags if flag),
        "final_center_inside_zone_count": sum(1 for flag in final_center_inside_flags if flag),
        "ball_stopped_in_corral_count": sum(1 for flag in ball_stopped_flags if flag),
        "rolled_away_after_release_count": sum(1 for flag in rolled_away_flags if flag),
        "clean_retention_pass_count": sum(1 for flag in clean_retention_flags if flag),
        "clean_retention_fail_count": sum(1 for flag in clean_retention_flags if not flag),
        "stopped_with_ball_captured_count": sum(1 for flag in stopped_with_capture_flags if flag),
        "release_started_with_capture_count": sum(1 for flag in release_started_with_capture_flags if flag),
        "mission_time_avg_s": round(sum(mission_times) / len(mission_times), 6) if mission_times else 0.0,
        "mission_time_min_s": round(min(mission_times), 6) if mission_times else 0.0,
        "mission_time_max_s": round(max(mission_times), 6) if mission_times else 0.0,
        "surface_profiles": surface_profiles,
        "handoff_kinds": handoff_kinds,
        "approach_side_pass_count": sum(1 for flag in approach_side_flags if flag),
        "approach_side_fail_count": sum(1 for flag in approach_side_flags if not flag),
        "entered_goal_side_before_capture_count": sum(1 for flag in entered_goal_side_flags if flag),
        "pre_stage_pose_reached_count": sum(1 for flag in pre_stage_pose_reached_flags if flag),
        "pre_stage_handoff_pass_count": sum(1 for flag in pre_stage_handoff_flags if flag),
        "staging_pose_reached_count": sum(1 for flag in staging_pose_reached_flags if flag),
        "first_contact_push_alignment_avg_deg": round(sum(first_contact_alignment_values) / len(first_contact_alignment_values), 6)
        if first_contact_alignment_values
        else 0.0,
        "first_contact_push_alignment_max_deg": round(max(first_contact_alignment_values), 6) if first_contact_alignment_values else 0.0,
        "stage_time_avg_s": round(sum(stage_times) / len(stage_times), 6) if stage_times else 0.0,
        "stage_time_max_s": round(max(stage_times), 6) if stage_times else 0.0,
        "pre_stage_time_avg_s": round(sum(pre_stage_times) / len(pre_stage_times), 6) if pre_stage_times else 0.0,
        "pre_stage_time_max_s": round(max(pre_stage_times), 6) if pre_stage_times else 0.0,
        "final_settle_distance_avg_m": round(sum(settle_distances) / len(settle_distances), 6) if settle_distances else 0.0,
        "final_settle_distance_max_m": round(max(settle_distances), 6) if settle_distances else 0.0,
        "max_overshoot_distance_max_m": round(max(overshoot_distances), 6) if overshoot_distances else 0.0,
        "settle_time_avg_s": round(sum(settle_times) / len(settle_times), 6) if settle_times else 0.0,
        "settle_time_max_s": round(max(settle_times), 6) if settle_times else 0.0,
        "release_recontact_count_total": sum(release_recontacts),
        "zone_edge_correction_count_total": sum(zone_edge_correction_counts),
        "place_controller_reentry_count_total": sum(place_controller_reentry_counts),
        "post_visit_revisit_count_total": sum(post_visit_revisit_counts),
        "settle_no_chase_activated_count": sum(1 for flag in settle_no_chase_flags if flag),
        "settle_exit_reasons": settle_exit_reasons,
        "settle_no_chase_exit_reasons": settle_no_chase_exit_reasons,
        "release_gate_blocked_reasons": release_gate_blocked_reasons,
        "approach_failure_reasons": approach_failure_reasons,
    }
    if any("final_three_ball_corral_pass" in item for item in runs):
        summary.update(
            {
                "retrieved_count_avg": round(sum(retrieved_counts) / len(retrieved_counts), 6) if retrieved_counts else 0.0,
                "retrieved_count_max": max(retrieved_counts) if retrieved_counts else 0,
                "final_all_targets_inside_retrieval_corral_count": sum(1 for flag in final_all_targets_inside_flags if flag),
                "final_all_targets_stopped_count": sum(1 for flag in final_all_targets_stopped_flags if flag),
                "final_three_ball_corral_pass_count": sum(1 for flag in final_three_ball_flags if flag),
                "final_three_ball_corral_fail_count": sum(1 for flag in final_three_ball_flags if not flag),
            }
        )
    return summary


def build_scorecard_markdown(*, scenario_label: str, summary: dict[str, Any], runs: list[dict[str, Any]]) -> str:
    surface_profiles = list(summary.get("surface_profiles", [])) if isinstance(summary.get("surface_profiles"), list) else []
    multi_ball = bool(
        summary.get("final_three_ball_corral_pass_count")
        or summary.get("final_three_ball_corral_fail_count")
        or any("final_three_ball_corral_pass" in item for item in runs)
    )
    lines = [
        f"# {scenario_label} Scorecard",
        "",
        f"- Surface profiles: `{', '.join(surface_profiles) if surface_profiles else 'unspecified'}`",
        f"- Handoff kinds: `{', '.join(summary.get('handoff_kinds', [])) if summary.get('handoff_kinds') else 'unspecified'}`",
        f"- Approach-side pass/fail: `{summary.get('approach_side_pass_count', 0)}/{summary.get('approach_side_fail_count', 0)}`",
        f"- Goal-side entries before capture: `{summary.get('entered_goal_side_before_capture_count', 0)}`",
        f"- Pre-stage pose reached: `{summary.get('pre_stage_pose_reached_count', 0)}/{max(len(runs), 1)}`",
        f"- Pre-stage handoff pass: `{summary.get('pre_stage_handoff_pass_count', 0)}/{max(len(runs), 1)}`",
        f"- Pre-stage time avg/max: `{summary.get('pre_stage_time_avg_s', 0.0):.3f}s / {summary.get('pre_stage_time_max_s', 0.0):.3f}s`",
        f"- Staging pose reached: `{summary.get('staging_pose_reached_count', 0)}/{max(len(runs), 1)}`",
        f"- First-contact push alignment avg/max: `{summary.get('first_contact_push_alignment_avg_deg', 0.0):.2f}deg / {summary.get('first_contact_push_alignment_max_deg', 0.0):.2f}deg`",
        f"- Stage time avg/max: `{summary.get('stage_time_avg_s', 0.0):.3f}s / {summary.get('stage_time_max_s', 0.0):.3f}s`",
        f"- Approach failures: `{', '.join(summary.get('approach_failure_reasons', [])) if summary.get('approach_failure_reasons') else 'none'}`",
        f"- Settle exits: `{', '.join(summary.get('settle_exit_reasons', [])) if summary.get('settle_exit_reasons') else 'unspecified'}`",
        f"- Settle-no-chase activations: `{summary.get('settle_no_chase_activated_count', 0)}/{max(len(runs), 1)}`",
        f"- Settle-no-chase exits: `{', '.join(summary.get('settle_no_chase_exit_reasons', [])) if summary.get('settle_no_chase_exit_reasons') else 'none'}`",
        f"- Release gate blocks: `{', '.join(summary.get('release_gate_blocked_reasons', [])) if summary.get('release_gate_blocked_reasons') else 'none'}`",
        f"- Pass rate: `{summary.get('pass_count', 0)}/{max(len(runs), 1)}`",
        f"- Promotion gate: `{'PASS' if summary.get('promotion_gate_pass') else 'FAIL'}`",
        f"- Settled placement pass/fail: `{summary.get('settled_in_corral_pass_count', 0)}/{summary.get('settled_in_corral_fail_count', 0)}`",
        f"- Final inside retrieval corral: `{summary.get('final_inside_retrieval_corral_count', 0)}/{max(len(runs), 1)}`",
        f"- Final center inside zone: `{summary.get('final_center_inside_zone_count', 0)}/{max(len(runs), 1)}`",
        f"- Ball stopped in corral: `{summary.get('ball_stopped_in_corral_count', 0)}/{max(len(runs), 1)}`",
        f"- Rolled away after release: `{summary.get('rolled_away_after_release_count', 0)}`",
        f"- Clean retention pass/fail: `{summary.get('clean_retention_pass_count', 0)}/{summary.get('clean_retention_fail_count', 0)}`",
        f"- Mission time avg/min/max: `{summary.get('mission_time_avg_s', 0.0):.3f}s / {summary.get('mission_time_min_s', 0.0):.3f}s / {summary.get('mission_time_max_s', 0.0):.3f}s`",
        f"- Capture losses total: `{summary.get('capture_loss_count_total', 0)}`",
        f"- Stopped with ball captured: `{summary.get('stopped_with_ball_captured_count', 0)}/{max(len(runs), 1)}`",
        f"- Release started with capture: `{summary.get('release_started_with_capture_count', 0)}/{max(len(runs), 1)}`",
        f"- Final settle distance avg/max: `{summary.get('final_settle_distance_avg_m', 0.0):.3f}m / {summary.get('final_settle_distance_max_m', 0.0):.3f}m`",
        f"- Max overshoot distance: `{summary.get('max_overshoot_distance_max_m', 0.0):.3f}m`",
        f"- Settle time avg/max: `{summary.get('settle_time_avg_s', 0.0):.3f}s / {summary.get('settle_time_max_s', 0.0):.3f}s`",
        f"- Release recontacts total: `{summary.get('release_recontact_count_total', 0)}`",
        f"- Zone-edge corrections total: `{summary.get('zone_edge_correction_count_total', 0)}`",
        f"- Place controller reentries total: `{summary.get('place_controller_reentry_count_total', 0)}`",
        f"- Post-visit revisits total: `{summary.get('post_visit_revisit_count_total', 0)}`",
        "",
        "## Runs",
        "",
    ]
    if multi_ball:
        lines[10:10] = [
            f"- Retrieved count avg/max: `{summary.get('retrieved_count_avg', 0.0):.3f} / {summary.get('retrieved_count_max', 0)}`",
            f"- Final all targets inside retrieval corral: `{summary.get('final_all_targets_inside_retrieval_corral_count', 0)}/{max(len(runs), 1)}`",
            f"- Final all targets stopped: `{summary.get('final_all_targets_stopped_count', 0)}/{max(len(runs), 1)}`",
            f"- Final three-ball corral pass/fail: `{summary.get('final_three_ball_corral_pass_count', 0)}/{summary.get('final_three_ball_corral_fail_count', 0)}`",
        ]
    for item in runs:
        settled_ok = settled_in_corral_pass(item)
        run_pass = gather_run_pass(item)
        retention_ok = clean_retention_pass(item)
        approach_verdict = item.get("approach_side_verdict", {}) if isinstance(item.get("approach_side_verdict"), dict) else {}
        approach_reason = str(
            approach_verdict.get("reason", "")
            or ("pass" if approach_verdict.get("pass", False) else "unspecified")
        )
        lines.append(
            f"- Run {int(item.get('run_index', 0) or 0):02d}: "
            f"`{'PASS' if run_pass else 'FAIL'}` "
            f"handoff=`{str(item.get('handoff_kind', '') or 'unspecified')}` "
            f"approach=`{approach_reason}` "
            f"goal_side=`{bool(item.get('entered_goal_side_before_capture', False))}` "
            f"pre_stage=`{bool(item.get('pre_stage_pose_reached', False))}` "
            f"pre_stage_ok=`{bool(item.get('pre_stage_handoff_pass', False))}` "
            f"pre_stage_s=`{float(item.get('pre_stage_time_s', 0.0) or 0.0):.3f}` "
            f"staged=`{bool(item.get('staging_pose_reached', False))}` "
            f"align_deg=`{float(item.get('first_contact_push_alignment_deg', 0.0) or 0.0):.2f}` "
            f"stage_s=`{float(item.get('stage_time_s', 0.0) or 0.0):.3f}` "
            f"settle_exit=`{str(item.get('settle_exit_reason', '') or 'unspecified')}` "
            f"settle_no_chase=`{bool(item.get('settle_no_chase_activated', False))}` "
            f"release_gate=`{str(item.get('release_gate_blocked_reason', '') or 'none')}` "
            f"surface=`{str(item.get('surface_profile', '') or 'unspecified')}` "
            f"placed=`{int(item.get('placed_count', 0) or 0)}` "
            f"retrieved=`{bool(item.get('final_inside_retrieval_corral', False))}` "
            f"center_inside=`{bool(item.get('final_center_inside_zone', False))}` "
            f"stopped=`{bool(item.get('ball_stopped_in_corral', False))}` "
            f"rolled_away=`{bool(item.get('rolled_away_after_release', False))}` "
            f"settled=`{settled_ok}` "
            f"capture_losses=`{int(item.get('capture_loss_count', 0) or 0)}` "
            f"stopped_captured=`{bool(item.get('stopped_with_ball_captured', False))}` "
            f"release_captured=`{bool(item.get('release_started_with_capture', False))}` "
            f"clean_retention=`{retention_ok}` "
            f"mission_time=`{float(item.get('mission_time_s', 0.0) or 0.0):.3f}s` "
            f"settle=`{float(item.get('final_settle_distance_m', 0.0) or 0.0):.3f}m` "
            f"overshoot=`{float(item.get('max_overshoot_distance_m', 0.0) or 0.0):.3f}m` "
            f"settle_time=`{float(item.get('settle_time_s', 0.0) or 0.0):.3f}s` "
            f"recontacts=`{int(item.get('release_recontact_count', 0) or 0)}` "
            f"zone_edge_corrections=`{int(item.get('zone_edge_correction_count', 0) or 0)}` "
            f"place_reentries=`{int(item.get('place_controller_reentry_count', 0) or 0)}` "
            f"post_visit_revisits=`{int(item.get('post_visit_revisit_count', 0) or 0)}`"
        )
        if multi_ball:
            lines.append(
                "  "
                + f"retrieved_count=`{int(item.get('retrieved_count', 0) or 0)}` "
                + f"all_inside=`{bool(item.get('final_all_targets_inside_retrieval_corral', False))}` "
                + f"all_stopped=`{bool(item.get('final_all_targets_stopped', False))}` "
                + f"three_ball_pass=`{bool(item.get('final_three_ball_corral_pass', False))}`"
            )
    lines.append("")
    return "\n".join(lines)
