from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_pre_stage_trajectory_owner_helpers as owner  # noqa: E402
from gather_mission_helpers import build_zone_spec  # noqa: E402
from gather_mission_helpers import pre_stage_arrival_snapshot  # noqa: E402


ZONE = build_zone_spec("corral_single_ball_place")
ZERO_BALL = {"x": 5.448, "y": 0.0, "z": 0.05}
PLUS45_BALL = {"x": 4.555261, "y": 2.155261, "z": 0.05}


def _snapshot(robot_pose, ball_pose=ZERO_BALL):
    return pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=ZONE)


def _decision(
    robot_pose,
    ball_pose=ZERO_BALL,
    *,
    snapshot=None,
    previous_milestone_index=0,
    ball_motion_m=None,
    stall_s=0.0,
    side_sign=None,
    replan_count=0,
):
    return owner.decide_pre_stage_trajectory_owner_command(
        robot_pose,
        ball_pose,
        zone=ZONE,
        snapshot=snapshot if snapshot is not None else _snapshot(robot_pose, ball_pose),
        previous_milestone_index=previous_milestone_index,
        stall_s=stall_s,
        ball_motion_m=ball_motion_m,
        side_sign=side_sign,
        replan_count=replan_count,
    )


def _assert_trajectory_clear(robot_pose, ball_pose):
    snapshot = _snapshot(robot_pose, ball_pose)
    milestones = owner.build_pre_stage_trajectory_owner_milestones(
        robot_pose,
        ball_pose,
        zone=ZONE,
        snapshot=snapshot,
    )

    assert [milestone.kind for milestone in milestones] == [
        owner.MILESTONE_ESCAPE_CLEAR,
        owner.MILESTONE_CORRIDOR_APPROACH,
        owner.MILESTONE_PORT,
        owner.MILESTONE_HANDOFF_YAW,
    ]
    starts = [robot_pose, *[milestone.pose for milestone in milestones[:-1]]]
    for start_pose, milestone in zip(starts, milestones):
        clearance_m = owner._segment_ball_clearance(start_pose, milestone.pose, ball_pose)
        assert clearance_m is not None
        assert clearance_m >= owner.DEFAULT_TRAJECTORY_OWNER_MIN_BALL_CLEARANCE_M


def test_pre_stage_trajectory_owner_public_payload_fields():
    decision = owner.PreStageTrajectoryOwnerDecision(
        active=False,
        milestone_index=2,
        milestone_kind="port",
        release_blockers=("yaw_not_aligned",),
        rejection_reasons=("predicted_clearance_violation",),
    )

    payload = decision.to_dict()

    assert owner.PRE_STAGE_TRAJECTORY_OWNER_CONTROL_FAMILY == "pre_stage_trajectory_owner_v1"
    assert payload["active"] is False
    assert payload["milestone_index"] == 2
    assert payload["milestone_kind"] == "port"
    assert payload["release_blockers"] == ["yaw_not_aligned"]
    assert payload["rejection_reasons"] == ["predicted_clearance_violation"]


def test_trajectory_owner_stays_inactive_when_handoff_ready():
    decision = _decision({"x": 6.348, "y": 0.0, "yaw": math.pi})

    assert decision.active is False
    assert decision.command is None
    assert decision.release_reason == "pre_stage_handoff_ready"
    assert decision.release_blockers == ()


def test_zero_and_plus45_generate_safe_trajectory_milestones():
    _assert_trajectory_clear({"x": 0.0, "y": 0.0, "yaw": 0.0}, ZERO_BALL)
    _assert_trajectory_clear({"x": 0.0, "y": 0.0, "yaw": 0.0}, PLUS45_BALL)


def test_zero_start_selects_non_contacting_trajectory_command():
    decision = _decision({"x": 0.0, "y": 0.0, "yaw": 0.0})

    assert decision.active is True
    assert decision.milestone_index == 0
    assert decision.milestone_kind == owner.MILESTONE_ESCAPE_CLEAR
    assert decision.command is not None
    assert decision.command.mode == "pre_stage_trajectory_owner"
    assert decision.command.linear_x > 0.0
    assert decision.min_ball_clearance_m is not None
    assert decision.min_ball_clearance_m >= owner.DEFAULT_TRAJECTORY_OWNER_MIN_BALL_CLEARANCE_M
    assert decision.rejection_reasons == ()


def test_plus45_start_keeps_clearance_and_improves_objective_progress():
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    snapshot = _snapshot(robot_pose, PLUS45_BALL)
    decision = _decision(robot_pose, PLUS45_BALL, snapshot=snapshot)

    assert snapshot is not None
    assert decision.active is True
    assert decision.milestone_kind == owner.MILESTONE_ESCAPE_CLEAR
    assert decision.projected_snapshot is not None
    assert decision.min_ball_clearance_m is not None
    assert decision.min_ball_clearance_m >= owner.DEFAULT_TRAJECTORY_OWNER_MIN_BALL_CLEARANCE_M
    assert decision.projected_snapshot["robot_longitudinal_projection_m"] < snapshot["robot_longitudinal_projection_m"]
    assert decision.projected_snapshot["robot_lateral_error_m"] < snapshot["robot_lateral_error_m"]


def test_milestones_advance_only_from_measured_progress():
    start_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    start_snapshot = _snapshot(start_pose, ZERO_BALL)
    milestones = owner.build_pre_stage_trajectory_owner_milestones(
        start_pose,
        ZERO_BALL,
        zone=ZONE,
        snapshot=start_snapshot,
        side_sign=1.0,
    )
    not_reached = _decision(start_pose, ZERO_BALL, snapshot=start_snapshot, previous_milestone_index=0, side_sign=1.0)
    reached_pose = {**milestones[0].pose, "yaw": 0.0}
    reached_snapshot = _snapshot(reached_pose, ZERO_BALL)
    reached = _decision(
        reached_pose,
        ZERO_BALL,
        snapshot=reached_snapshot,
        previous_milestone_index=0,
        side_sign=1.0,
    )

    assert not_reached.milestone_index == 0
    assert not_reached.milestone_reached is False
    assert reached.milestone_reached is True
    assert reached.milestone_index == 1
    assert reached.milestone_kind == owner.MILESTONE_CORRIDOR_APPROACH


def test_owner_replans_once_to_alternate_side_on_progress_stall():
    decision = _decision(
        {"x": 0.0, "y": 0.0, "yaw": 0.0},
        stall_s=owner.DEFAULT_TRAJECTORY_OWNER_STALL_TIMEOUT_S + 0.1,
        side_sign=1.0,
        replan_count=0,
    )

    assert decision.active is True
    assert decision.command is not None
    assert decision.replan_reason == "trajectory_progress_stalled"
    assert decision.next_replan_count == 1
    assert decision.side_sign == -1.0
    assert decision.next_side_sign == -1.0
    assert decision.milestone_index == 0


def test_owner_does_not_replan_when_measured_progress_advanced():
    start_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    milestones = owner.build_pre_stage_trajectory_owner_milestones(
        start_pose,
        ZERO_BALL,
        zone=ZONE,
        snapshot=_snapshot(start_pose, ZERO_BALL),
        side_sign=1.0,
    )
    reached_pose = {**milestones[0].pose, "yaw": 0.0}
    decision = _decision(
        reached_pose,
        ZERO_BALL,
        snapshot=_snapshot(reached_pose, ZERO_BALL),
        previous_milestone_index=0,
        stall_s=owner.DEFAULT_TRAJECTORY_OWNER_STALL_TIMEOUT_S + 0.1,
        side_sign=1.0,
        replan_count=0,
    )

    assert decision.milestone_reached is True
    assert decision.milestone_index == 1
    assert decision.replan_reason == ""
    assert decision.next_replan_count == 0
    assert decision.side_sign == 1.0


def test_owner_aborts_after_second_progress_stall():
    decision = _decision(
        {"x": 0.0, "y": 0.0, "yaw": 0.0},
        stall_s=owner.DEFAULT_TRAJECTORY_OWNER_STALL_TIMEOUT_S + 0.1,
        side_sign=-1.0,
        replan_count=1,
    )

    assert decision.active is False
    assert decision.command is None
    assert decision.release_reason == "trajectory_progress_stalled"
    assert decision.release_blockers == ("trajectory_progress_stalled",)
    assert owner.REJECTION_REPEATED_STALL in decision.rejection_reasons


def test_owner_aborts_on_ball_motion_guard():
    decision = _decision({"x": 0.0, "y": 0.0, "yaw": 0.0}, ball_motion_m=0.051)

    assert decision.active is False
    assert decision.command is None
    assert decision.release_reason == "ball_motion_guard"
    assert decision.release_blockers == ("ball_motion_guard",)
    assert decision.ball_motion_m == pytest.approx(0.051)


def test_owner_aborts_on_measured_clearance_violation():
    robot_pose = {"x": 5.45, "y": 0.0, "yaw": 0.0}
    decision = _decision(robot_pose, ZERO_BALL, snapshot=_snapshot(robot_pose, ZERO_BALL))

    assert decision.active is False
    assert decision.command is None
    assert decision.release_reason == "trajectory_clearance_guard"
    assert owner.REJECTION_MEASURED_CLEARANCE in decision.rejection_reasons
    assert decision.measured_ball_clearance_m is not None
    assert decision.measured_ball_clearance_m < owner.DEFAULT_TRAJECTORY_OWNER_MIN_BALL_CLEARANCE_M


def test_final_yaw_alignment_is_yaw_only():
    robot_pose = {"x": 6.348, "y": 0.0, "yaw": math.radians(100.0)}
    decision = _decision(
        robot_pose,
        ZERO_BALL,
        snapshot=_snapshot(robot_pose, ZERO_BALL),
        previous_milestone_index=3,
    )

    assert decision.active is True
    assert decision.milestone_index == 3
    assert decision.milestone_kind == owner.MILESTONE_HANDOFF_YAW
    assert decision.command is not None
    assert decision.command.mode == "pre_stage_trajectory_owner_yaw"
    assert decision.command.linear_x == 0.0
    assert 0.0 < decision.command.angular_z <= owner.DEFAULT_TRAJECTORY_OWNER_YAW_MAX_ANGULAR_Z


def test_release_is_strictly_measured_handoff_ready():
    almost_ready_snapshot = {
        "push_direction_yaw_deg": 180.0,
        "pre_stage_pose_world": {"x": 6.348, "y": 0.0},
        "pre_stage_pose_distance_m": 0.22,
        "robot_longitudinal_projection_m": -0.70,
        "robot_lateral_error_m": 0.12,
        "robot_lateral_signed_m": 0.12,
        "yaw_error_deg": 45.0,
        "robot_on_goal_side": False,
        "pre_stage_pose_reached": False,
    }
    active = _decision(
        {"x": 6.20, "y": 0.12, "yaw": math.radians(135.0)},
        snapshot=almost_ready_snapshot,
        previous_milestone_index=3,
    )
    ready = _decision({"x": 6.348, "y": 0.0, "yaw": math.pi})

    assert active.active is True
    assert active.release_reason == ""
    assert ready.active is False
    assert ready.release_reason == "pre_stage_handoff_ready"
