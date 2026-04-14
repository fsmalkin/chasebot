#!/usr/bin/env python3
"""Pure helpers for offline/headless gather mission planning and scoring."""

from __future__ import annotations

import math
from dataclasses import asdict
from dataclasses import dataclass
from typing import Any


DEFAULT_ZONE_WORLD_X = 2.40
DEFAULT_ZONE_WORLD_Y = 0.00
DEFAULT_ZONE_RADIUS_M = 0.20
DEFAULT_ZONE_DWELL_S = 1.0
DEFAULT_CAPTURE_LOSS_GRACE_S = 1.0
DEFAULT_TARGET_BALL_RADIUS_M = 0.05
DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M = 0.01
DEFAULT_RELEASE_SETTLE_STABLE_WINDOW_S = 0.75
DEFAULT_RELEASE_ZONE_MARGIN_M = 0.035


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
    radius_m: float = DEFAULT_ZONE_RADIUS_M
    dwell_s: float = DEFAULT_ZONE_DWELL_S
    z_m: float = 0.001


@dataclass(frozen=True)
class CaptureEnvelope:
    min_x_m: float = 0.045
    max_x_m: float = 0.240
    max_abs_y_m: float = 0.070
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
    inside_zone: bool
    center_inside_zone: bool

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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
                    "radius_m": round(zone.radius_m, 6),
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
    center_inside_zone = distance_m <= max(float(zone.radius_m), 0.0)
    return ZoneSnapshot(
        zone_distance_m=round(distance_m, 6),
        inside_zone=distance_m <= max(float(zone.radius_m), 0.0) + DEFAULT_TARGET_BALL_RADIUS_M,
        center_inside_zone=center_inside_zone,
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
        capture.captured
        and capture.ball_x_m >= 0.16
        and abs(capture.ball_y_m) <= 0.03
        and float(zone_score.zone_distance_m) <= max(float(zone.radius_m), 0.05) + max(float(release_margin_m), 0.0)
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
        return PlaceControlCommand(
            mode="captured",
            linear_x=0.0,
            angular_z=0.0,
            target_speed_scale=0.0,
            rationale="Ball is already inside the capture envelope.",
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
    zone_radius = max(zone.radius_m, 0.05)
    ball_zone_score = zone_snapshot(ball_pose, zone)
    ball_zone_distance = ball_zone_score.zone_distance_m if ball_zone_score else zone_distance
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
            linear = min(linear, 0.02)
            if finish_push_corridor and capture.within_recapture_window:
                linear = max(linear, 0.026)
            if abs(ball_to_zone_y_m) <= 0.10 and ball_to_zone_x_m > -0.05:
                linear = max(linear, 0.018)
            elif abs(ball_to_zone_y_m) > 0.16:
                linear = min(linear, 0.006)
        if final_approach:
            linear = min(linear, 0.016)
            if finish_push_corridor and capture.within_recapture_window:
                linear = max(linear, 0.015)
            if abs(ball_to_zone_y_m) <= 0.08 and ball_to_zone_x_m > -0.04:
                linear = max(linear, 0.015)
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

    angular = clamp((capture.ball_y_m * 9.0) + (zone_heading_rad * 1.0), -1.0, 1.0)
    if finish_push_corridor:
        angular = clamp(capture.ball_y_m * 4.5, -0.22, 0.22)
    elif near_zone:
        angular = clamp((ball_to_zone_y_m * 8.0) + (zone_heading_rad * 0.55), -0.65, 0.65)
    linear = 0.055
    if finish_push_corridor:
        linear = 0.04
    if (
        ball_zone_distance > zone_radius + 0.40
        and capture.ball_x_m > 0.20
        and abs(capture.ball_y_m) <= 0.02
    ):
        linear = 0.07
    elif (
        ball_zone_distance > zone_radius + 0.30
        and capture.ball_x_m > 0.18
        and abs(capture.ball_y_m) <= 0.03
    ):
        linear = max(linear, 0.065)
    if abs(capture.ball_y_m) > 0.05:
        linear = min(linear, 0.03)
    if near_zone:
        linear = 0.028
        if finish_push_corridor:
            linear = 0.034
        if abs(ball_to_zone_y_m) <= 0.04 and ball_to_zone_x_m > -0.03:
            linear = max(linear, 0.032)
    if final_approach:
        linear = min(linear, 0.024)
        if finish_push_corridor:
            linear = max(linear, 0.03)
    if ball_zone_distance < zone_radius + 0.12:
        linear = 0.012
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
        )

    first = release_samples[0]
    last = release_samples[-1]
    first_inside_index: int | None = None
    for index, sample in enumerate(release_samples):
        if bool(sample.get("inside_zone")) or bool(sample.get("center_inside_zone")):
            first_inside_index = index
            break
    overshoot_samples = release_samples[first_inside_index:] if first_inside_index is not None else release_samples
    max_overshoot_distance_m = 0.0
    for sample in overshoot_samples:
        distance = _number(sample.get("zone_distance_m"))
        if distance is None:
            continue
        max_overshoot_distance_m = max(max_overshoot_distance_m, max(0.0, float(distance) - max(float(zone.radius_m), 0.0)))
    settle_time_s = max(
        (_number(last.get("elapsed_s")) or 0.0) - (_number(first.get("elapsed_s")) or 0.0),
        0.0,
    )
    return ReleaseSettleMetrics(
        surface_profile=str(surface_profile or ""),
        release_distance_to_zone_center_m=round(_number(first.get("zone_distance_m")) or 0.0, 6),
        max_overshoot_distance_m=round(max_overshoot_distance_m, 6),
        final_settle_distance_m=round(_number(last.get("zone_distance_m")) or 0.0, 6),
        settle_time_s=round(settle_time_s, 6),
        release_recontact_count=int(release_recontact_count),
        settled_inside_zone=bool(last.get("center_inside_zone") or last.get("inside_zone")),
    )


def campaign_pass(runs: list[dict[str, Any]]) -> bool:
    if not runs:
        return False
    return all(bool(item.get("pass")) for item in runs)


def summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    mission_times = [float(item.get("mission_time_s", 0.0) or 0.0) for item in runs if item.get("pass")]
    placed_counts = [int(item.get("placed_count", 0) or 0) for item in runs]
    capture_losses = [int(item.get("capture_loss_count", 0) or 0) for item in runs]
    settle_distances = [
        float(item.get("final_settle_distance_m", 0.0) or 0.0)
        for item in runs
        if item.get("pass") and item.get("final_settle_distance_m") not in {None, ""}
    ]
    overshoot_distances = [
        float(item.get("max_overshoot_distance_m", 0.0) or 0.0)
        for item in runs
        if item.get("max_overshoot_distance_m") not in {None, ""}
    ]
    settle_times = [
        float(item.get("settle_time_s", 0.0) or 0.0)
        for item in runs
        if item.get("pass") and item.get("settle_time_s") not in {None, ""}
    ]
    release_recontacts = [int(item.get("release_recontact_count", 0) or 0) for item in runs]
    surface_profiles = sorted({str(item.get("surface_profile", "") or "") for item in runs if str(item.get("surface_profile", "") or "").strip()})
    return {
        "pass_count": sum(1 for item in runs if bool(item.get("pass"))),
        "placed_count_max": max(placed_counts) if placed_counts else 0,
        "placed_count_min": min(placed_counts) if placed_counts else 0,
        "capture_loss_count_total": sum(capture_losses),
        "mission_time_avg_s": round(sum(mission_times) / len(mission_times), 6) if mission_times else 0.0,
        "mission_time_min_s": round(min(mission_times), 6) if mission_times else 0.0,
        "mission_time_max_s": round(max(mission_times), 6) if mission_times else 0.0,
        "surface_profiles": surface_profiles,
        "final_settle_distance_avg_m": round(sum(settle_distances) / len(settle_distances), 6) if settle_distances else 0.0,
        "final_settle_distance_max_m": round(max(settle_distances), 6) if settle_distances else 0.0,
        "max_overshoot_distance_max_m": round(max(overshoot_distances), 6) if overshoot_distances else 0.0,
        "settle_time_avg_s": round(sum(settle_times) / len(settle_times), 6) if settle_times else 0.0,
        "settle_time_max_s": round(max(settle_times), 6) if settle_times else 0.0,
        "release_recontact_count_total": sum(release_recontacts),
    }


def build_scorecard_markdown(*, scenario_label: str, summary: dict[str, Any], runs: list[dict[str, Any]]) -> str:
    surface_profiles = list(summary.get("surface_profiles", [])) if isinstance(summary.get("surface_profiles"), list) else []
    lines = [
        f"# {scenario_label} Scorecard",
        "",
        f"- Surface profiles: `{', '.join(surface_profiles) if surface_profiles else 'unspecified'}`",
        f"- Pass rate: `{summary.get('pass_count', 0)}/{max(len(runs), 1)}`",
        f"- Promotion gate: `{'PASS' if summary.get('promotion_gate_pass') else 'FAIL'}`",
        f"- Mission time avg/min/max: `{summary.get('mission_time_avg_s', 0.0):.3f}s / {summary.get('mission_time_min_s', 0.0):.3f}s / {summary.get('mission_time_max_s', 0.0):.3f}s`",
        f"- Capture losses total: `{summary.get('capture_loss_count_total', 0)}`",
        f"- Final settle distance avg/max: `{summary.get('final_settle_distance_avg_m', 0.0):.3f}m / {summary.get('final_settle_distance_max_m', 0.0):.3f}m`",
        f"- Max overshoot distance: `{summary.get('max_overshoot_distance_max_m', 0.0):.3f}m`",
        f"- Settle time avg/max: `{summary.get('settle_time_avg_s', 0.0):.3f}s / {summary.get('settle_time_max_s', 0.0):.3f}s`",
        f"- Release recontacts total: `{summary.get('release_recontact_count_total', 0)}`",
        "",
        "## Runs",
        "",
    ]
    for item in runs:
        lines.append(
            f"- Run {int(item.get('run_index', 0) or 0):02d}: "
            f"`{'PASS' if item.get('pass') else 'FAIL'}` "
            f"surface=`{str(item.get('surface_profile', '') or 'unspecified')}` "
            f"placed=`{int(item.get('placed_count', 0) or 0)}` "
            f"capture_losses=`{int(item.get('capture_loss_count', 0) or 0)}` "
            f"mission_time=`{float(item.get('mission_time_s', 0.0) or 0.0):.3f}s` "
            f"settle=`{float(item.get('final_settle_distance_m', 0.0) or 0.0):.3f}m` "
            f"overshoot=`{float(item.get('max_overshoot_distance_m', 0.0) or 0.0):.3f}m` "
            f"settle_time=`{float(item.get('settle_time_s', 0.0) or 0.0):.3f}s` "
            f"recontacts=`{int(item.get('release_recontact_count', 0) or 0)}`"
        )
    lines.append("")
    return "\n".join(lines)
