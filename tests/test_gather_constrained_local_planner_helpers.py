from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_constrained_local_planner_helpers as constrained_planner  # noqa: E402
from gather_mission_helpers import build_zone_spec  # noqa: E402
from gather_mission_helpers import pre_stage_arrival_snapshot  # noqa: E402


ZONE = build_zone_spec("corral_single_ball_place")
ZERO_BALL_POSE = {"x": 5.448, "y": 0.0, "z": 0.05}
PLUS45_BALL_POSE = {"x": 4.555261, "y": 2.155261, "z": 0.05}


def _decision(
    robot_pose: dict[str, float],
    ball_pose: dict[str, float],
    *,
    previous_strategy_name: str = "",
    stall_s: float = 0.0,
    ball_motion_m: float | None = None,
):
    snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=ZONE)
    return constrained_planner.decide_constrained_local_pre_stage_command(
        robot_pose,
        ball_pose,
        zone=ZONE,
        snapshot=snapshot,
        previous_strategy_name=previous_strategy_name,
        stall_s=stall_s,
        ball_motion_m=ball_motion_m,
    )


def test_constrained_local_planner_public_interface_exports_family_and_decision_fields():
    decision = constrained_planner.ConstrainedLocalPlannerDecision(active=False)

    assert constrained_planner.CONSTRAINED_LOCAL_PLANNER_CONTROL_FAMILY == "constrained_local_planner_v1"
    assert decision.to_dict()["active"] is False
    assert decision.to_dict()["rejection_reasons"] == []


def test_constrained_local_planner_stays_inactive_when_handoff_ready():
    robot_pose = {"x": 0.1, "y": 0.0, "yaw": 0.0}
    ball_pose = {"x": 1.0, "y": 0.0, "z": 0.05}

    decision = _decision(robot_pose, ball_pose)

    assert decision.active is False
    assert decision.command is None
    assert decision.release_reason == "pre_stage_handoff_ready"


def test_zero_start_selects_safe_local_arc_without_ball_contact():
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    snapshot = pre_stage_arrival_snapshot(robot_pose, ZERO_BALL_POSE, zone=ZONE)

    decision = _decision(robot_pose, ZERO_BALL_POSE)

    assert snapshot is not None
    assert snapshot["entered_goal_side_before_capture"] is True
    assert decision.active is True
    assert decision.command is not None
    assert decision.command.mode == "constrained_local_pre_stage"
    assert decision.command.linear_x >= 0.0
    assert decision.min_ball_clearance_m is not None
    assert decision.min_ball_clearance_m >= constrained_planner.DEFAULT_CONSTRAINED_LOCAL_MIN_BALL_CLEARANCE_M
    assert "predicted_ball_contact" not in decision.rejection_reasons


def test_plus45_goal_side_start_improves_goal_side_clearance_without_scripted_reflank():
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    snapshot = pre_stage_arrival_snapshot(robot_pose, PLUS45_BALL_POSE, zone=ZONE)

    decision = _decision(robot_pose, PLUS45_BALL_POSE)

    assert snapshot is not None
    assert snapshot["entered_goal_side_before_capture"] is True
    assert decision.active is True
    assert decision.command is not None
    assert decision.objective_name == "constrained_local_planner"
    assert not decision.strategy_name.startswith("scripted")
    assert decision.projected_snapshot is not None
    assert (
        float(decision.projected_snapshot["robot_longitudinal_projection_m"])
        < float(snapshot["robot_longitudinal_projection_m"])
    )


def test_near_ball_candidate_rejections_are_reported_with_fixed_reasons():
    robot_pose = {"x": 5.20, "y": 0.0, "yaw": 0.0}
    snapshot = pre_stage_arrival_snapshot(robot_pose, ZERO_BALL_POSE, zone=ZONE)

    decision = constrained_planner.decide_constrained_local_pre_stage_command(
        robot_pose,
        ZERO_BALL_POSE,
        zone=ZONE,
        snapshot=snapshot,
        stall_s=1.2,
    )

    assert decision.candidate_count > 0
    assert decision.rejected_count > 0
    assert "predicted_ball_contact" in decision.rejection_reasons


def test_release_condition_hands_control_back_to_baseline():
    robot_pose = {"x": 6.02, "y": 0.48, "yaw": 3.0}
    snapshot = pre_stage_arrival_snapshot(robot_pose, ZERO_BALL_POSE, zone=ZONE)

    decision = constrained_planner.decide_constrained_local_pre_stage_command(
        robot_pose,
        ZERO_BALL_POSE,
        zone=ZONE,
        snapshot=snapshot,
        previous_strategy_name="advance_left",
        stall_s=2.0,
        ball_motion_m=0.0,
    )

    assert snapshot is not None
    assert snapshot["robot_on_goal_side"] is False
    assert decision.active is False
    assert decision.command is None
    assert decision.release_reason == "baseline_pre_stage_traversal_ready"
