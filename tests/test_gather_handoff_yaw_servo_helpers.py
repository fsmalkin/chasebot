from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_handoff_yaw_servo_helpers as yaw_servo  # noqa: E402
from gather_mission_helpers import build_zone_spec  # noqa: E402
from gather_mission_helpers import pre_stage_arrival_snapshot  # noqa: E402


ZONE = build_zone_spec("corral_single_ball_place")
BALL_POSE = {"x": 5.448, "y": 0.0, "z": 0.05}


def _decision(robot_pose, *, snapshot=None, ball_motion_m=None):
    return yaw_servo.decide_handoff_yaw_servo_pre_stage_command(
        robot_pose,
        BALL_POSE,
        zone=ZONE,
        snapshot=snapshot if snapshot is not None else pre_stage_arrival_snapshot(robot_pose, BALL_POSE, zone=ZONE),
        ball_motion_m=ball_motion_m,
    )


def test_handoff_yaw_servo_public_interface_exports_family_and_decision_fields():
    decision = yaw_servo.HandoffYawServoDecision(
        active=False,
        release_blockers=("robot_on_goal_side",),
    )

    payload = decision.to_dict()

    assert yaw_servo.HANDOFF_YAW_SERVO_CONTROL_FAMILY == "handoff_yaw_servo_v1"
    assert payload["active"] is False
    assert payload["release_blockers"] == ["robot_on_goal_side"]


def test_handoff_yaw_servo_stays_inactive_when_handoff_ready():
    decision = _decision({"x": 6.348, "y": 0.0, "yaw": math.pi})

    assert decision.active is False
    assert decision.command is None
    assert decision.release_reason == "pre_stage_handoff_ready"
    assert decision.release_blockers == ()


def test_handoff_yaw_servo_emits_yaw_only_command_inside_safe_geometry():
    decision = _decision({"x": 6.0, "y": 0.0, "yaw": math.radians(140.0)})

    assert decision.active is True
    assert decision.strategy_name == "handoff_yaw_servo"
    assert decision.objective_name == "handoff_yaw_servo"
    assert decision.command is not None
    assert decision.command.mode == "handoff_yaw_servo_pre_stage"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == pytest.approx(decision.angular_z)
    assert 0.0 < decision.command.angular_z <= yaw_servo.DEFAULT_HANDOFF_YAW_SERVO_MAX_ANGULAR_Z
    assert decision.yaw_error_deg == pytest.approx(40.0)
    assert decision.current_yaw_rad == pytest.approx(math.radians(140.0))
    assert decision.target_yaw_rad == pytest.approx(math.pi)
    assert decision.projected_snapshot is not None
    assert decision.projected_snapshot["yaw_error_deg"] < decision.yaw_error_deg


def test_handoff_yaw_servo_signed_angular_command_is_symmetric():
    plus_decision = _decision({"x": 6.0, "y": 0.0, "yaw": math.radians(140.0)})
    minus_decision = _decision({"x": 6.0, "y": 0.0, "yaw": math.radians(-140.0)})

    assert plus_decision.active is True
    assert minus_decision.active is True
    assert plus_decision.command is not None
    assert minus_decision.command is not None
    assert plus_decision.command.angular_z == pytest.approx(-minus_decision.command.angular_z)
    assert plus_decision.yaw_error_rad == pytest.approx(-minus_decision.yaw_error_rad)
    assert plus_decision.yaw_error_deg == pytest.approx(minus_decision.yaw_error_deg)


def test_handoff_yaw_servo_does_not_activate_with_geometry_blockers():
    decision = _decision({"x": 4.9, "y": 0.0, "yaw": 0.0})

    assert decision.active is False
    assert decision.command is None
    assert decision.release_reason == "geometry_guard"
    assert "robot_on_goal_side" in decision.release_blockers
    assert "projection_not_cleared" in decision.release_blockers
    assert "distance_not_converged" in decision.release_blockers


def test_handoff_yaw_servo_reports_ball_motion_guard():
    decision = _decision({"x": 6.0, "y": 0.0, "yaw": math.radians(140.0)}, ball_motion_m=0.051)

    assert decision.active is False
    assert decision.release_reason == "ball_motion_guard"
    assert "ball_motion_guard" in decision.release_blockers
    assert decision.ball_motion_m == pytest.approx(0.051)


def test_handoff_yaw_servo_rejects_invalid_snapshot():
    decision = _decision(
        {"x": 6.0, "y": 0.0, "yaw": math.radians(140.0)},
        snapshot={"pre_stage_pose_distance_m": "missing"},
    )

    assert decision.active is False
    assert decision.command is None
    assert decision.release_reason == "missing_pre_stage_geometry"
    assert decision.release_blockers == ("missing_pre_stage_geometry",)


def test_handoff_yaw_servo_below_yaw_threshold_releases_to_baseline():
    snapshot = {
        "push_direction_yaw_deg": 180.0,
        "pre_stage_pose_distance_m": 0.36,
        "robot_longitudinal_projection_m": -0.55,
        "robot_lateral_error_m": 0.24,
        "robot_lateral_signed_m": 0.24,
        "yaw_error_deg": 18.0,
        "robot_on_goal_side": False,
        "pre_stage_pose_reached": False,
    }

    decision = _decision({"x": 6.0, "y": 0.24, "yaw": math.radians(162.0)}, snapshot=snapshot)

    assert decision.active is False
    assert decision.command is None
    assert decision.release_reason == "baseline_pre_stage_traversal_ready"
    assert decision.release_blockers == ()
