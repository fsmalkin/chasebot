#!/usr/bin/env python3
"""Object-centric gather policy helpers.

The v1 policy is deliberately structured and inspectable. It treats the task as
robot-ball-zone geometry, emits a bounded short-horizon command, and leaves all
mission phase gates in the gather runner unchanged.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from dataclasses import dataclass
from typing import Any

from gather_mission_helpers import CaptureEnvelope
from gather_mission_helpers import PlaceControlCommand
from gather_mission_helpers import ZoneSpec
from gather_mission_helpers import capture_entry_snapshot
from gather_mission_helpers import capture_snapshot
from gather_mission_helpers import clamp
from gather_mission_helpers import goal_side_approach_snapshot
from gather_mission_helpers import normalize_angle
from gather_mission_helpers import point_xy
from gather_mission_helpers import pose_delta_m
from gather_mission_helpers import pre_stage_arrival_snapshot
from gather_mission_helpers import relative_point_robot_frame
from gather_mission_helpers import secure_capture
from gather_mission_helpers import world_pose_xyyaw
from gather_mission_helpers import zone_snapshot


OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY = "object_centric_gather_policy_v1"
OBJECT_CENTRIC_MAX_FORWARD_LINEAR_X_MPS = 0.16
OBJECT_CENTRIC_MAX_REVERSE_LINEAR_X_MPS = -0.14
OBJECT_CENTRIC_MAX_ABS_ANGULAR_Z_RADPS = 0.80
OBJECT_CENTRIC_MAX_TARGET_SPEED_SCALE = 0.75
OBJECT_CENTRIC_MAX_LINEAR_DELTA_MPS = 0.04
OBJECT_CENTRIC_MAX_ANGULAR_DELTA_RADPS = 0.20
OBJECT_CENTRIC_PRE_CONTACT_BALL_MOTION_GUARD_M = 0.05
OBJECT_CENTRIC_PRE_CONTACT_MIN_BALL_DISTANCE_M = 0.16
OBJECT_CENTRIC_GOAL_SIDE_ORBIT_CLEARANCE_M = 0.78
OBJECT_CENTRIC_GOAL_SIDE_ORBIT_MIN_BALL_DISTANCE_M = 1.05
OBJECT_CENTRIC_GOAL_SIDE_ORBIT_NEAR_BALL_MIN_DISTANCE_M = 0.90
OBJECT_CENTRIC_GOAL_SIDE_ORBIT_NEAR_BALL_MIN_LATERAL_M = 0.42
OBJECT_CENTRIC_GOAL_SIDE_ORBIT_CLOSE_BALL_MIN_DISTANCE_M = 0.78
OBJECT_CENTRIC_GOAL_SIDE_ORBIT_CLOSE_BALL_MIN_LATERAL_M = 0.52
OBJECT_CENTRIC_GOAL_SIDE_ORBIT_VERY_CLOSE_BALL_MIN_DISTANCE_M = 0.62
OBJECT_CENTRIC_GOAL_SIDE_ORBIT_VERY_CLOSE_BALL_MIN_LATERAL_M = 0.60
OBJECT_CENTRIC_PRE_STAGE_CLOSE_YAW_SETTLE_LONGITUDINAL_M = -0.55
OBJECT_CENTRIC_PRE_STAGE_CLOSE_YAW_SETTLE_LATERAL_M = 0.22
OBJECT_CENTRIC_PRE_STAGE_CLOSE_YAW_SETTLE_TARGET_DISTANCE_M = 0.43
OBJECT_CENTRIC_PRE_STAGE_CLOSE_YAW_SETTLE_YAW_ERROR_RAD = math.radians(35.0)


@dataclass(frozen=True)
class ObjectCentricPolicyDecision:
    active: bool
    phase: str
    command: PlaceControlCommand | None
    raw_command: PlaceControlCommand | None
    diagnostics: dict[str, Any]
    strategy_name: str = "object_centric_gather_policy"
    objective_name: str = ""
    progress_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["command"] = self.command.to_dict() if self.command else {}
        payload["raw_command"] = self.raw_command.to_dict() if self.raw_command else {}
        return payload


def _number(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _command_payload(command: PlaceControlCommand | dict[str, Any] | None) -> dict[str, Any]:
    if command is None:
        return {}
    if isinstance(command, PlaceControlCommand):
        return command.to_dict()
    if isinstance(command, dict):
        return dict(command)
    to_dict = getattr(command, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
        return dict(payload) if isinstance(payload, dict) else {}
    return {}


def _previous_command_values(command: PlaceControlCommand | dict[str, Any] | None) -> tuple[float | None, float | None]:
    payload = _command_payload(command)
    return _number(payload.get("linear_x")), _number(payload.get("angular_z"))


def _clamp_command(command: PlaceControlCommand) -> tuple[PlaceControlCommand, bool]:
    linear = clamp(
        float(command.linear_x),
        OBJECT_CENTRIC_MAX_REVERSE_LINEAR_X_MPS,
        OBJECT_CENTRIC_MAX_FORWARD_LINEAR_X_MPS,
    )
    angular = clamp(
        float(command.angular_z),
        -OBJECT_CENTRIC_MAX_ABS_ANGULAR_Z_RADPS,
        OBJECT_CENTRIC_MAX_ABS_ANGULAR_Z_RADPS,
    )
    speed_scale = clamp(float(command.target_speed_scale), 0.0, OBJECT_CENTRIC_MAX_TARGET_SPEED_SCALE)
    limited = (
        abs(linear - float(command.linear_x)) > 1.0e-9
        or abs(angular - float(command.angular_z)) > 1.0e-9
        or abs(speed_scale - float(command.target_speed_scale)) > 1.0e-9
    )
    return (
        PlaceControlCommand(
            mode=command.mode,
            linear_x=round(linear, 6),
            angular_z=round(angular, 6),
            target_speed_scale=round(speed_scale, 6),
            rationale=command.rationale,
        ),
        limited,
    )


def _smooth_command(
    command: PlaceControlCommand,
    previous_command: PlaceControlCommand | dict[str, Any] | None,
    *,
    smooth: bool = True,
) -> tuple[PlaceControlCommand, dict[str, Any]]:
    clamped, command_limited = _clamp_command(command)
    previous_linear, previous_angular = _previous_command_values(previous_command)
    smoothing_applied = False
    linear = float(clamped.linear_x)
    angular = float(clamped.angular_z)
    if smooth and previous_linear is not None:
        smoothed_linear = clamp(
            linear,
            previous_linear - OBJECT_CENTRIC_MAX_LINEAR_DELTA_MPS,
            previous_linear + OBJECT_CENTRIC_MAX_LINEAR_DELTA_MPS,
        )
        smoothing_applied = smoothing_applied or abs(smoothed_linear - linear) > 1.0e-9
        linear = smoothed_linear
    if smooth and previous_angular is not None:
        smoothed_angular = clamp(
            angular,
            previous_angular - OBJECT_CENTRIC_MAX_ANGULAR_DELTA_RADPS,
            previous_angular + OBJECT_CENTRIC_MAX_ANGULAR_DELTA_RADPS,
        )
        smoothing_applied = smoothing_applied or abs(smoothed_angular - angular) > 1.0e-9
        angular = smoothed_angular
    selected = PlaceControlCommand(
        mode=clamped.mode,
        linear_x=round(linear, 6),
        angular_z=round(angular, 6),
        target_speed_scale=clamped.target_speed_scale,
        rationale=clamped.rationale,
    )
    return selected, {
        "command_limited": bool(command_limited),
        "smoothing_applied": bool(smoothing_applied),
        "limits": {
            "linear_x_min_mps": OBJECT_CENTRIC_MAX_REVERSE_LINEAR_X_MPS,
            "linear_x_max_mps": OBJECT_CENTRIC_MAX_FORWARD_LINEAR_X_MPS,
            "angular_z_abs_max_radps": OBJECT_CENTRIC_MAX_ABS_ANGULAR_Z_RADPS,
            "target_speed_scale_max": OBJECT_CENTRIC_MAX_TARGET_SPEED_SCALE,
            "linear_delta_max_mps": OBJECT_CENTRIC_MAX_LINEAR_DELTA_MPS,
            "angular_delta_max_radps": OBJECT_CENTRIC_MAX_ANGULAR_DELTA_RADPS,
        },
    }


def _phase_behind_distance_m(phase: str) -> float:
    if phase == "pre_stage":
        return 0.90
    if phase == "stage":
        return 0.45
    if phase == "capture_entry":
        return 0.26
    return 0.12


def _geometry(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    phase: str,
    envelope: CaptureEnvelope | None,
    previous_ball_pose: dict[str, Any] | None,
) -> dict[str, Any] | None:
    robot_xyyaw = world_pose_xyyaw(robot_pose)
    ball_xy = point_xy(ball_pose)
    if robot_xyyaw is None or ball_xy is None:
        return None
    robot_x, robot_y, robot_yaw = robot_xyyaw
    ball_x, ball_y = ball_xy
    zone_dx = float(zone.world_x) - ball_x
    zone_dy = float(zone.world_y) - ball_y
    zone_distance = math.hypot(zone_dx, zone_dy)
    if zone_distance <= 1.0e-6:
        push_ux = math.cos(robot_yaw)
        push_uy = math.sin(robot_yaw)
    else:
        push_ux = zone_dx / zone_distance
        push_uy = zone_dy / zone_distance
    push_yaw = math.atan2(push_uy, push_ux)
    lateral_ux = -push_uy
    lateral_uy = push_ux
    robot_from_ball_x = robot_x - ball_x
    robot_from_ball_y = robot_y - ball_y
    longitudinal = (robot_from_ball_x * push_ux) + (robot_from_ball_y * push_uy)
    lateral_signed = (robot_from_ball_x * lateral_ux) + (robot_from_ball_y * lateral_uy)
    desired_behind = _phase_behind_distance_m(phase)
    target_world = {
        "x": ball_x - (desired_behind * push_ux),
        "y": ball_y - (desired_behind * push_uy),
    }
    target_rel = relative_point_robot_frame(robot_pose, target_world)
    target_x_m = target_rel[0] if target_rel is not None else 0.0
    target_y_m = target_rel[1] if target_rel is not None else 0.0
    target_distance = math.hypot(target_x_m, target_y_m)
    yaw_error_signed = normalize_angle(push_yaw - robot_yaw)
    yaw_error_deg = abs(math.degrees(yaw_error_signed))
    capture = capture_snapshot(robot_pose, ball_pose, envelope)
    zone_score = zone_snapshot(ball_pose, zone)
    return {
        "phase": str(phase),
        "push_yaw": push_yaw,
        "push_yaw_error_signed": yaw_error_signed,
        "push_line": {
            "yaw_deg": round(math.degrees(push_yaw), 6),
            "unit_x": round(push_ux, 6),
            "unit_y": round(push_uy, 6),
            "ball_to_zone_distance_m": round(zone_distance, 6),
        },
        "behind_ball": {
            "desired_distance_m": round(desired_behind, 6),
            "robot_longitudinal_projection_m": round(longitudinal, 6),
            "robot_lateral_signed_m": round(lateral_signed, 6),
            "robot_lateral_error_m": round(abs(lateral_signed), 6),
            "target_world": {"x": round(target_world["x"], 6), "y": round(target_world["y"], 6)},
            "target_x_m": round(target_x_m, 6),
            "target_y_m": round(target_y_m, 6),
            "target_distance_m": round(target_distance, 6),
            "yaw_error_deg": round(yaw_error_deg, 6),
        },
        "capture": capture.to_dict() if capture else {},
        "zone": zone_score.to_dict() if zone_score else {},
        "ball_motion_m": pose_delta_m(previous_ball_pose, ball_pose) if previous_ball_pose is not None else None,
    }


def _ready_command(phase: str) -> PlaceControlCommand:
    if phase == "pre_stage":
        return PlaceControlCommand(
            mode="pre_stage_ready",
            linear_x=0.0,
            angular_z=0.0,
            target_speed_scale=0.0,
            rationale="Object-centric policy reached the coarse behind-ball pre-stage pose.",
        )
    if phase == "stage":
        return PlaceControlCommand(
            mode="stage_ready",
            linear_x=0.0,
            angular_z=0.0,
            target_speed_scale=0.0,
            rationale="Object-centric policy is staged behind the ball and aligned for first contact.",
        )
    return PlaceControlCommand(
        mode="capture_entry_ready",
        linear_x=0.0,
        angular_z=0.0,
        target_speed_scale=0.0,
        rationale="Object-centric policy reached the capture-entry corridor.",
    )


def _guard_command(mode: str, rationale: str) -> PlaceControlCommand:
    return PlaceControlCommand(mode=mode, linear_x=0.0, angular_z=0.0, target_speed_scale=0.0, rationale=rationale)


def _goal_side_orbit_target_robot_frame(
    geometry: dict[str, Any],
    *,
    target_x_m: float,
    target_y_m: float,
    lateral_signed: float,
) -> tuple[float, float]:
    push_yaw = float(geometry["push_yaw"])
    yaw_error = float(geometry["push_yaw_error_signed"])
    robot_yaw = normalize_angle(push_yaw - yaw_error)
    lateral_ux = -math.sin(push_yaw)
    lateral_uy = math.cos(push_yaw)
    if abs(lateral_signed) > 0.05:
        side = 1.0 if lateral_signed >= 0.0 else -1.0
    else:
        side = 1.0
    offset_world_x = side * OBJECT_CENTRIC_GOAL_SIDE_ORBIT_CLEARANCE_M * lateral_ux
    offset_world_y = side * OBJECT_CENTRIC_GOAL_SIDE_ORBIT_CLEARANCE_M * lateral_uy
    cos_yaw = math.cos(robot_yaw)
    sin_yaw = math.sin(robot_yaw)
    offset_robot_x = (cos_yaw * offset_world_x) + (sin_yaw * offset_world_y)
    offset_robot_y = (-sin_yaw * offset_world_x) + (cos_yaw * offset_world_y)
    return target_x_m + offset_robot_x, target_y_m + offset_robot_y


def _approach_command(phase: str, geometry: dict[str, Any]) -> PlaceControlCommand:
    behind = geometry["behind_ball"]
    target_x_m = float(behind["target_x_m"])
    target_y_m = float(behind["target_y_m"])
    target_distance_m = float(behind["target_distance_m"])
    longitudinal = float(behind["robot_longitudinal_projection_m"])
    lateral_signed = float(behind["robot_lateral_signed_m"])
    yaw_error = float(geometry["push_yaw_error_signed"])
    heading_error = math.atan2(target_y_m, target_x_m if abs(target_x_m) > 1.0e-6 else 1.0e-6)
    phase_prefix = "object_pre_stage" if phase == "pre_stage" else "object_stage"
    desired_behind = float(behind["desired_distance_m"])
    if longitudinal > 0.0:
        capture = geometry.get("capture", {})
        ball_distance_m = float(capture.get("distance_m", 999.0) or 999.0)
        orbit_has_clearance = (
            ball_distance_m > OBJECT_CENTRIC_GOAL_SIDE_ORBIT_MIN_BALL_DISTANCE_M
            or (
                ball_distance_m > OBJECT_CENTRIC_GOAL_SIDE_ORBIT_NEAR_BALL_MIN_DISTANCE_M
                and abs(lateral_signed) >= OBJECT_CENTRIC_GOAL_SIDE_ORBIT_NEAR_BALL_MIN_LATERAL_M
            )
            or (
                ball_distance_m > OBJECT_CENTRIC_GOAL_SIDE_ORBIT_CLOSE_BALL_MIN_DISTANCE_M
                and abs(lateral_signed) >= OBJECT_CENTRIC_GOAL_SIDE_ORBIT_CLOSE_BALL_MIN_LATERAL_M
            )
            or (
                ball_distance_m > OBJECT_CENTRIC_GOAL_SIDE_ORBIT_VERY_CLOSE_BALL_MIN_DISTANCE_M
                and abs(lateral_signed) >= OBJECT_CENTRIC_GOAL_SIDE_ORBIT_VERY_CLOSE_BALL_MIN_LATERAL_M
            )
        )
        if orbit_has_clearance and target_distance_m > 0.55:
            orbit_x_m, orbit_y_m = _goal_side_orbit_target_robot_frame(
                geometry,
                target_x_m=target_x_m,
                target_y_m=target_y_m,
                lateral_signed=lateral_signed,
            )
            orbit_heading_error = math.atan2(orbit_y_m, orbit_x_m if abs(orbit_x_m) > 1.0e-6 else 1.0e-6)
            if orbit_x_m < -0.05 or abs(orbit_heading_error) > 0.95:
                linear = 0.0
            else:
                linear = clamp(orbit_x_m * 0.18, 0.055, 0.14)
            angular = clamp(orbit_heading_error * 1.25, -0.8, 0.8)
            if abs(angular) < 0.12 and abs(orbit_heading_error) > 0.05:
                angular = 0.12 if orbit_heading_error >= 0.0 else -0.12
            return PlaceControlCommand(
                mode=f"{phase_prefix}_goal_side_orbit",
                linear_x=round(linear, 6),
                angular_z=round(angular, 6),
                target_speed_scale=0.65,
                rationale="Traverse toward a lateral behind-ball port before converging onto the push line.",
            )
        escape_yaw = normalize_angle(float(geometry["push_yaw"]) + math.pi)
        angular = clamp((escape_yaw * 0.0) + (yaw_error * -0.85) + (lateral_signed * 0.30), -0.8, 0.8)
        if abs(angular) < 0.18 and abs(yaw_error) > 0.12:
            angular = 0.18 if yaw_error < 0.0 else -0.18
        return PlaceControlCommand(
            mode=f"{phase_prefix}_escape_goal_side",
            linear_x=-0.10,
            angular_z=round(angular, 6),
            target_speed_scale=0.0,
            rationale="Back away from the goal side and rotate around the ball before contact.",
        )
    if (
        phase == "pre_stage"
        and longitudinal <= OBJECT_CENTRIC_PRE_STAGE_CLOSE_YAW_SETTLE_LONGITUDINAL_M
        and abs(lateral_signed) <= OBJECT_CENTRIC_PRE_STAGE_CLOSE_YAW_SETTLE_LATERAL_M
        and target_distance_m <= OBJECT_CENTRIC_PRE_STAGE_CLOSE_YAW_SETTLE_TARGET_DISTANCE_M
        and abs(yaw_error) > OBJECT_CENTRIC_PRE_STAGE_CLOSE_YAW_SETTLE_YAW_ERROR_RAD
    ):
        angular = clamp(yaw_error * 1.10, -0.8, 0.8)
        if abs(angular) < 0.20 and abs(yaw_error) > 0.12:
            angular = 0.20 if yaw_error >= 0.0 else -0.20
        return PlaceControlCommand(
            mode="object_pre_stage_close_yaw_settle",
            linear_x=0.0,
            angular_z=round(angular, 6),
            target_speed_scale=0.0,
            rationale="Hold the close behind-ball pose while settling push-line yaw before handoff.",
        )
    if target_distance_m > 0.18 and (target_x_m < -0.05 or abs(heading_error) > 0.55):
        angular = clamp(heading_error * 1.25, -0.8, 0.8)
        if abs(angular) < 0.18:
            angular = 0.18 if heading_error >= 0.0 else -0.18
        return PlaceControlCommand(
            mode=f"{phase_prefix}_turn_to_behind",
            linear_x=0.0,
            angular_z=round(angular, 6),
            target_speed_scale=0.0,
            rationale="Turn toward the object-centric behind-ball target before translating.",
        )
    longitudinal_error = longitudinal + desired_behind
    linear = (target_x_m * 0.28) - max(0.0, longitudinal_error) * 0.05
    angular = (target_y_m * 1.15) + (yaw_error * 0.22)
    return PlaceControlCommand(
        mode=f"{phase_prefix}_traverse",
        linear_x=round(linear, 6),
        angular_z=round(angular, 6),
        target_speed_scale=0.75,
        rationale="Regulate behind-ball offset, lateral error, and push-line yaw as one object-centric state.",
    )


def _capture_entry_command(geometry: dict[str, Any]) -> PlaceControlCommand:
    capture = geometry.get("capture", {})
    if not bool(capture.get("ball_ahead", False)):
        ball_y = float(capture.get("ball_y_m", 0.0) or 0.0)
        return PlaceControlCommand(
            mode="object_capture_entry_reorient",
            linear_x=0.0,
            angular_z=0.45 if ball_y >= 0.0 else -0.45,
            target_speed_scale=0.0,
            rationale="Rotate locally until the ball is ahead before closing the capture-entry corridor.",
        )
    ball_x = float(capture.get("ball_x_m", 0.0) or 0.0)
    ball_y = float(capture.get("ball_y_m", 0.0) or 0.0)
    bearing = float(capture.get("bearing_rad", 0.0) or 0.0)
    yaw_error = float(geometry["push_yaw_error_signed"])
    linear = 0.050 if ball_x > 0.40 else 0.035
    if abs(ball_y) > 0.065:
        linear = min(linear, 0.025)
    angular = (ball_y * 8.0) + (bearing * 0.60) + (yaw_error * 0.12)
    return PlaceControlCommand(
        mode="object_capture_entry_close",
        linear_x=round(linear, 6),
        angular_z=round(angular, 6),
        target_speed_scale=0.55,
        rationale="Close the robot-ball gap while keeping the ball centered on the push line.",
    )


def _capture_command(geometry: dict[str, Any], envelope: CaptureEnvelope | None) -> PlaceControlCommand:
    capture = geometry.get("capture", {})
    if bool(capture.get("captured", False)):
        active_envelope = envelope or CaptureEnvelope()
        if secure_capture_snapshot_payload(capture, active_envelope):
            return PlaceControlCommand(
                mode="captured",
                linear_x=0.0,
                angular_z=0.0,
                target_speed_scale=0.0,
                rationale="Ball is securely seated inside the capture envelope.",
            )
        ball_x = float(capture.get("ball_x_m", 0.0) or 0.0)
        ball_y = float(capture.get("ball_y_m", 0.0) or 0.0)
        return PlaceControlCommand(
            mode="object_capture_seat",
            linear_x=0.055 if ball_x > float(active_envelope.seated_max_x_m) else 0.040,
            angular_z=round(ball_y * 5.0, 6),
            target_speed_scale=0.55,
            rationale="Keep the ball seated while nudging it deeper before place control.",
        )
    if not bool(capture.get("ball_ahead", False)):
        ball_y = float(capture.get("ball_y_m", 0.0) or 0.0)
        return PlaceControlCommand(
            mode="object_capture_reorient",
            linear_x=0.0,
            angular_z=0.75 if ball_y >= 0.0 else -0.75,
            target_speed_scale=0.0,
            rationale="Ball slipped behind the capture spur; rotate before pushing.",
        )
    ball_x = float(capture.get("ball_x_m", 0.0) or 0.0)
    ball_y = float(capture.get("ball_y_m", 0.0) or 0.0)
    bearing = float(capture.get("bearing_rad", 0.0) or 0.0)
    yaw_error = float(geometry["push_yaw_error_signed"])
    linear = 0.12
    if abs(ball_y) > 0.07:
        linear = 0.065
    elif ball_x > 0.35:
        linear = 0.14
    angular = (ball_y * 6.5) + (bearing * 0.55) + (yaw_error * 0.20)
    return PlaceControlCommand(
        mode="object_capture_push",
        linear_x=round(linear, 6),
        angular_z=round(angular, 6),
        target_speed_scale=0.75,
        rationale="Push the centered ball along the ball-to-zone line with bounded object-centric feedback.",
    )


def secure_capture_snapshot_payload(payload: dict[str, Any], envelope: CaptureEnvelope) -> bool:
    return bool(
        payload
        and bool(payload.get("captured", False))
        and float(payload.get("ball_x_m", 0.0) or 0.0) <= float(envelope.seated_max_x_m)
        and abs(float(payload.get("ball_y_m", 0.0) or 0.0)) <= float(envelope.seated_max_abs_y_m)
    )


def _raw_command_for_phase(
    phase: str,
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    zone: ZoneSpec,
    envelope: CaptureEnvelope | None,
    geometry: dict[str, Any],
) -> tuple[PlaceControlCommand, str, str]:
    ball_motion_m = _number(geometry.get("ball_motion_m"))
    if phase in {"pre_stage", "stage", "capture_entry"} and ball_motion_m is not None:
        if ball_motion_m > OBJECT_CENTRIC_PRE_CONTACT_BALL_MOTION_GUARD_M:
            return (
                _guard_command(
                    "object_policy_ball_motion_guard",
                    "Ball moved before intentional capture contact; stop the object-centric policy.",
                ),
                "ball_motion_guard",
                "ball_motion_guard",
            )
    capture = geometry.get("capture", {})
    if phase in {"pre_stage", "stage"} and float(capture.get("distance_m", 999.0) or 999.0) < OBJECT_CENTRIC_PRE_CONTACT_MIN_BALL_DISTANCE_M:
        return (
            _guard_command(
                "object_policy_pre_contact_clearance_guard",
                "Robot is too close to the ball before the capture phase; stop before accidental contact.",
            ),
            "pre_contact_clearance_guard",
            "clearance_guard",
        )
    if phase == "pre_stage":
        snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone)
        if isinstance(snapshot, dict) and bool(snapshot.get("pre_stage_pose_reached", False)):
            return _ready_command(phase), "", "pre_stage_ready"
        return _approach_command(phase, geometry), "", ""
    if phase == "stage":
        snapshot = goal_side_approach_snapshot(robot_pose, ball_pose, zone=zone)
        if isinstance(snapshot, dict) and bool(snapshot.get("staging_pose_reached", False)):
            return _ready_command(phase), "", "stage_ready"
        return _approach_command(phase, geometry), "", ""
    if phase == "capture_entry":
        snapshot = capture_entry_snapshot(robot_pose, ball_pose, zone=zone, envelope=envelope)
        if isinstance(snapshot, dict) and bool(snapshot.get("capture_entry_reached", False)):
            return _ready_command(phase), "", "capture_entry_ready"
        return _capture_entry_command(geometry), "", ""
    if phase == "capture":
        return _capture_command(geometry, envelope), "", ""
    return (
        _guard_command("object_policy_unknown_phase", f"Unsupported object-centric phase: {phase}."),
        "unknown_phase",
        "unknown_phase",
    )


def decide_object_centric_gather_command(
    robot_pose: dict[str, Any],
    ball_pose: dict[str, Any],
    *,
    phase: str,
    zone: ZoneSpec,
    envelope: CaptureEnvelope | None = None,
    previous_command: PlaceControlCommand | dict[str, Any] | None = None,
    previous_ball_pose: dict[str, Any] | None = None,
) -> ObjectCentricPolicyDecision:
    normalized_phase = str(phase or "").strip().lower()
    geometry = _geometry(
        robot_pose,
        ball_pose,
        zone=zone,
        phase=normalized_phase,
        envelope=envelope,
        previous_ball_pose=previous_ball_pose,
    )
    if geometry is None:
        diagnostics = {
            "family": OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY,
            "phase": normalized_phase,
            "active": False,
            "guard_rejection_reason": "missing_pose_or_ball",
            "terminal_cause": "missing_pose_or_ball",
            "selected_command": {},
            "raw_command": {},
        }
        return ObjectCentricPolicyDecision(
            active=False,
            phase=normalized_phase,
            command=None,
            raw_command=None,
            diagnostics=diagnostics,
            objective_name=f"{normalized_phase}_object_state",
            progress_score=None,
        )

    raw_command, guard_reason, terminal_cause = _raw_command_for_phase(
        normalized_phase,
        robot_pose,
        ball_pose,
        zone=zone,
        envelope=envelope,
        geometry=geometry,
    )
    smooth = raw_command.mode not in {
        "pre_stage_ready",
        "stage_ready",
        "capture_entry_ready",
        "captured",
        "object_policy_ball_motion_guard",
        "object_policy_pre_contact_clearance_guard",
        "object_policy_unknown_phase",
    }
    selected_command, limit_diagnostics = _smooth_command(raw_command, previous_command, smooth=smooth)
    behind = geometry.get("behind_ball", {})
    progress_score = -(
        abs(float(behind.get("robot_lateral_error_m", 0.0) or 0.0))
        + abs(float(behind.get("robot_longitudinal_projection_m", 0.0) or 0.0) + float(behind.get("desired_distance_m", 0.0) or 0.0))
        + (float(behind.get("yaw_error_deg", 0.0) or 0.0) / 180.0)
    )
    diagnostics = {
        "family": OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY,
        "phase": normalized_phase,
        "active": True,
        "mode": selected_command.mode,
        "objective_name": f"{normalized_phase}_object_state",
        "push_line": geometry.get("push_line", {}),
        "behind_ball": geometry.get("behind_ball", {}),
        "ball_zone_progress": {
            "distance_m": _round(_number(geometry.get("push_line", {}).get("ball_to_zone_distance_m"))),
        },
        "capture_snapshot": geometry.get("capture", {}),
        "zone_snapshot": geometry.get("zone", {}),
        "ball_motion_m": _round(_number(geometry.get("ball_motion_m"))),
        "guard_rejection_reason": guard_reason,
        "terminal_cause": terminal_cause,
        "raw_command": raw_command.to_dict(),
        "selected_command": selected_command.to_dict(),
        **limit_diagnostics,
    }
    return ObjectCentricPolicyDecision(
        active=True,
        phase=normalized_phase,
        command=selected_command,
        raw_command=raw_command,
        diagnostics=diagnostics,
        objective_name=f"{normalized_phase}_object_state",
        progress_score=round(progress_score, 6),
    )
