from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from gather_mission_helpers import build_zone_spec  # noqa: E402
from gather_object_centric_policy_helpers import (  # noqa: E402
    OBJECT_CENTRIC_MAX_ABS_ANGULAR_Z_RADPS,
    OBJECT_CENTRIC_MAX_FORWARD_LINEAR_X_MPS,
    OBJECT_CENTRIC_MAX_LINEAR_DELTA_MPS,
    PlaceControlCommand,
    decide_object_centric_gather_command,
)


def test_policy_returns_pre_stage_ready_at_measured_handoff_pose():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 1.0, "y": 0.0}
    robot_pose = {"x": 0.1, "y": 0.0, "yaw": 0.0}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="pre_stage",
        zone=zone,
    )

    assert decision.active is True
    assert decision.command is not None
    assert decision.command.mode == "pre_stage_ready"
    assert decision.diagnostics["behind_ball"]["robot_longitudinal_projection_m"] == -0.9
    assert decision.diagnostics["guard_rejection_reason"] == ""


def test_policy_capture_command_is_object_centric_and_bounded():
    zone = build_zone_spec("corral_single_ball_place")
    ball_pose = {"x": 1.0, "y": 0.10}
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}

    decision = decide_object_centric_gather_command(
        robot_pose,
        ball_pose,
        phase="capture",
        zone=zone,
    )

    assert decision.command is not None
    assert decision.command.mode == "object_capture_push"
    assert abs(decision.command.linear_x) <= OBJECT_CENTRIC_MAX_FORWARD_LINEAR_X_MPS
    assert abs(decision.command.angular_z) <= OBJECT_CENTRIC_MAX_ABS_ANGULAR_Z_RADPS
    assert decision.diagnostics["push_line"]["ball_to_zone_distance_m"] > 0.0
    assert decision.diagnostics["ball_zone_progress"]["distance_m"] > 0.0


def test_policy_smooths_command_delta_from_previous_command():
    zone = build_zone_spec("corral_single_ball_place")
    previous = PlaceControlCommand(
        mode="object_capture_push",
        linear_x=0.0,
        angular_z=0.0,
        target_speed_scale=0.75,
        rationale="previous",
    )

    decision = decide_object_centric_gather_command(
        {"x": 0.0, "y": 0.0, "yaw": 0.0},
        {"x": 1.0, "y": 0.0},
        phase="capture",
        zone=zone,
        previous_command=previous,
    )

    assert decision.command is not None
    assert decision.command.linear_x == OBJECT_CENTRIC_MAX_LINEAR_DELTA_MPS
    assert decision.diagnostics["smoothing_applied"] is True


def test_policy_stops_on_pre_contact_ball_motion_guard():
    zone = build_zone_spec("corral_single_ball_place")

    decision = decide_object_centric_gather_command(
        {"x": 0.0, "y": 0.0, "yaw": 0.0},
        {"x": 1.0, "y": 0.08},
        phase="stage",
        zone=zone,
        previous_ball_pose={"x": 1.0, "y": 0.0},
    )

    assert decision.command is not None
    assert decision.command.mode == "object_policy_ball_motion_guard"
    assert decision.command.linear_x == 0.0
    assert decision.command.angular_z == 0.0
    assert decision.diagnostics["guard_rejection_reason"] == "ball_motion_guard"
