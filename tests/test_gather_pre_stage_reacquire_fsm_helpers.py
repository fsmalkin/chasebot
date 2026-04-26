from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_pre_stage_reacquire_fsm_helpers as fsm  # noqa: E402
from gather_mission_helpers import build_zone_spec  # noqa: E402
from gather_mission_helpers import pre_stage_arrival_snapshot  # noqa: E402


ZONE = build_zone_spec("corral_single_ball_place")
ZERO_BALL = {"x": 5.448, "y": 0.0, "z": 0.05}
PLUS45_BALL = {"x": 4.555261, "y": 2.155261, "z": 0.05}


def _decision(robot_pose, ball_pose=ZERO_BALL, *, snapshot=None, ball_motion_m=None, previous_phase=""):
    return fsm.decide_pre_stage_reacquire_fsm_command(
        robot_pose,
        ball_pose,
        zone=ZONE,
        snapshot=snapshot if snapshot is not None else pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=ZONE),
        previous_phase=previous_phase,
        ball_motion_m=ball_motion_m,
    )


def test_pre_stage_reacquire_fsm_public_interface_exports_family_and_payload_fields():
    decision = fsm.PreStageReacquireFsmDecision(
        active=False,
        phase="baseline_release",
        release_blockers=("robot_on_goal_side",),
        rejection_reasons=("predicted_ball_contact",),
    )

    payload = decision.to_dict()

    assert fsm.PRE_STAGE_REACQUIRE_FSM_CONTROL_FAMILY == "pre_stage_reacquire_fsm_v1"
    assert payload["active"] is False
    assert payload["phase"] == "baseline_release"
    assert payload["release_blockers"] == ["robot_on_goal_side"]
    assert payload["rejection_reasons"] == ["predicted_ball_contact"]


def test_pre_stage_reacquire_fsm_stays_inactive_when_handoff_ready():
    decision = _decision({"x": 6.348, "y": 0.0, "yaw": math.pi})

    assert decision.active is False
    assert decision.command is None
    assert decision.phase == fsm.PHASE_BASELINE_RELEASE
    assert decision.release_reason == "pre_stage_handoff_ready"
    assert decision.release_blockers == ()


def test_zero_goal_side_start_selects_safe_escape_without_ball_contact():
    decision = _decision({"x": 0.0, "y": 0.0, "yaw": 0.0})

    assert decision.active is True
    assert decision.phase == fsm.PHASE_GOAL_SIDE_ESCAPE
    assert decision.command is not None
    assert decision.command.mode == "pre_stage_reacquire_fsm"
    assert decision.command.linear_x > 0.0
    assert decision.min_ball_clearance_m is not None
    assert decision.min_ball_clearance_m >= fsm.DEFAULT_FSM_MIN_BALL_CLEARANCE_M
    assert decision.rejection_reasons == ()
    assert decision.projected_projection_gain is not None
    assert decision.projected_projection_gain > 0.0


def test_plus45_goal_side_start_improves_goal_side_clearance_without_scripted_oscillation():
    snapshot = pre_stage_arrival_snapshot({"x": 0.0, "y": 0.0, "yaw": 0.0}, PLUS45_BALL, zone=ZONE)
    decision = _decision({"x": 0.0, "y": 0.0, "yaw": 0.0}, PLUS45_BALL, snapshot=snapshot)

    assert snapshot is not None
    assert decision.active is True
    assert decision.phase == fsm.PHASE_GOAL_SIDE_ESCAPE
    assert decision.command is not None
    assert decision.projected_snapshot is not None
    assert decision.projected_snapshot["robot_longitudinal_projection_m"] < snapshot["robot_longitudinal_projection_m"]
    assert decision.projected_projection_gain is not None
    assert decision.projected_projection_gain > 0.0
    assert decision.rejection_reasons == ()


def test_dock_port_rejects_candidate_that_predicts_ball_contact():
    robot_pose = {"x": 5.7, "y": 0.0, "yaw": 0.0}
    snapshot = pre_stage_arrival_snapshot(robot_pose, ZERO_BALL, zone=ZONE)
    decision = _decision(robot_pose, snapshot=snapshot)

    assert snapshot is not None
    assert decision.active is True
    assert decision.phase == fsm.PHASE_DOCK_PORT
    assert decision.command is not None
    assert decision.command.mode == "pre_stage_reacquire_fsm_hold"
    assert decision.candidate_count == 1
    assert decision.accepted_count == 0
    assert decision.rejected_count == 1
    assert fsm.REJECTION_PREDICTED_BALL_CONTACT in decision.rejection_reasons


def test_exact_behind_target_turns_instead_of_zero_motion():
    command, target_distance_m, heading_error_rad = fsm._command_toward_target(
        {"x": 0.0, "y": 0.0, "yaw": 0.0},
        {"x": -1.0, "y": 0.0},
        phase=fsm.PHASE_DOCK_PORT,
        push_yaw_rad=math.pi,
    )

    assert target_distance_m == pytest.approx(1.0)
    assert abs(heading_error_rad) == pytest.approx(math.pi)
    assert command.linear_x == 0.0
    assert abs(command.angular_z) >= 0.18


def test_yaw_align_phase_is_yaw_only_and_reduces_yaw_error():
    decision = _decision({"x": 6.0, "y": 0.0, "yaw": math.radians(140.0)})

    assert decision.active is True
    assert decision.phase == fsm.PHASE_YAW_ALIGN
    assert decision.command is not None
    assert decision.command.mode == "pre_stage_reacquire_fsm_yaw_align"
    assert decision.command.linear_x == 0.0
    assert 0.0 < decision.command.angular_z <= fsm.DEFAULT_FSM_YAW_MAX_ANGULAR_Z
    assert decision.yaw_error_deg == pytest.approx(40.0)
    assert decision.projected_yaw_gain_deg is not None
    assert decision.projected_yaw_gain_deg > 0.0
    assert decision.projected_snapshot is not None
    assert decision.projected_snapshot["yaw_error_deg"] < decision.yaw_error_deg


def test_release_condition_hands_back_to_baseline_inside_safe_envelope():
    snapshot = {
        "push_direction_yaw_deg": 180.0,
        "pre_stage_pose_distance_m": 0.42,
        "robot_longitudinal_projection_m": -0.55,
        "robot_lateral_error_m": 0.16,
        "robot_lateral_signed_m": 0.16,
        "yaw_error_deg": 18.0,
        "robot_on_goal_side": False,
        "pre_stage_pose_reached": False,
    }

    decision = _decision({"x": 6.0, "y": 0.16, "yaw": math.radians(162.0)}, snapshot=snapshot)

    assert decision.active is False
    assert decision.command is None
    assert decision.phase == fsm.PHASE_BASELINE_RELEASE
    assert decision.release_reason == "baseline_safe_release"
    assert decision.release_blockers == ()


def test_yaw_boundary_stays_in_yaw_align_until_done_threshold():
    snapshot = {
        "push_direction_yaw_deg": 180.0,
        "pre_stage_pose_distance_m": 0.42,
        "robot_longitudinal_projection_m": -0.55,
        "robot_lateral_error_m": 0.16,
        "robot_lateral_signed_m": 0.16,
        "yaw_error_deg": 22.0,
        "robot_on_goal_side": False,
        "pre_stage_pose_reached": False,
    }

    decision = _decision({"x": 6.0, "y": 0.16, "yaw": math.radians(158.0)}, snapshot=snapshot)

    assert decision.active is True
    assert decision.phase == fsm.PHASE_YAW_ALIGN
    assert decision.command is not None
    assert decision.command.linear_x == 0.0


def test_ball_motion_guard_aborts_before_override():
    decision = _decision({"x": 0.0, "y": 0.0, "yaw": 0.0}, ball_motion_m=0.051)

    assert decision.active is False
    assert decision.command is None
    assert decision.phase == fsm.PHASE_BASELINE_RELEASE
    assert decision.release_reason == "ball_motion_guard"
    assert "ball_motion_guard" in decision.release_blockers
    assert decision.ball_motion_m == pytest.approx(0.051)


def test_ball_motion_guard_wins_over_handoff_ready():
    decision = _decision({"x": 6.348, "y": 0.0, "yaw": math.pi}, ball_motion_m=0.051)

    assert decision.active is False
    assert decision.command is None
    assert decision.phase == fsm.PHASE_BASELINE_RELEASE
    assert decision.release_reason == "ball_motion_guard"
    assert decision.release_blockers == ("ball_motion_guard",)
