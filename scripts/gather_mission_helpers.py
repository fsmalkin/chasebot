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
        return [
            GatherTargetSpec(
                id="ball_a",
                label="Ball A (far left)",
                start_visible=False,
                forward_m=1.75,
                lateral_m=0.60,
            ),
            GatherTargetSpec(
                id="ball_b",
                label="Ball B (near center)",
                start_visible=True,
                forward_m=1.10,
                lateral_m=0.00,
            ),
            GatherTargetSpec(
                id="ball_c",
                label="Ball C (far right)",
                start_visible=False,
                forward_m=1.75,
                lateral_m=-0.60,
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
    handoff_kinds = sorted({str(item.get("handoff_kind", "") or "") for item in runs if str(item.get("handoff_kind", "") or "").strip()})
    settle_exit_reasons = sorted(
        {
            str(item.get("settle_exit_reason", "") or "")
            for item in runs
            if str(item.get("settle_exit_reason", "") or "").strip()
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
        "final_settle_distance_avg_m": round(sum(settle_distances) / len(settle_distances), 6) if settle_distances else 0.0,
        "final_settle_distance_max_m": round(max(settle_distances), 6) if settle_distances else 0.0,
        "max_overshoot_distance_max_m": round(max(overshoot_distances), 6) if overshoot_distances else 0.0,
        "settle_time_avg_s": round(sum(settle_times) / len(settle_times), 6) if settle_times else 0.0,
        "settle_time_max_s": round(max(settle_times), 6) if settle_times else 0.0,
        "release_recontact_count_total": sum(release_recontacts),
        "zone_edge_correction_count_total": sum(zone_edge_correction_counts),
        "place_controller_reentry_count_total": sum(place_controller_reentry_counts),
        "post_visit_revisit_count_total": sum(post_visit_revisit_counts),
        "settle_exit_reasons": settle_exit_reasons,
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
        f"- Settle exits: `{', '.join(summary.get('settle_exit_reasons', [])) if summary.get('settle_exit_reasons') else 'unspecified'}`",
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
        lines.append(
            f"- Run {int(item.get('run_index', 0) or 0):02d}: "
            f"`{'PASS' if run_pass else 'FAIL'}` "
            f"handoff=`{str(item.get('handoff_kind', '') or 'unspecified')}` "
            f"settle_exit=`{str(item.get('settle_exit_reason', '') or 'unspecified')}` "
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
