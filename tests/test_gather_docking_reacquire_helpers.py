from __future__ import annotations

import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_docking_reacquire_helpers as docking  # noqa: E402
from gather_mission_helpers import build_zone_spec  # noqa: E402
from gather_mission_helpers import pre_stage_arrival_snapshot  # noqa: E402


def _zone():
    return build_zone_spec("corral_single_ball_place")


def _decision(robot_pose, ball_pose, *, snapshot=None, **kwargs):
    zone = _zone()
    return docking.decide_docking_reacquire_pre_stage_command(
        robot_pose,
        ball_pose,
        zone=zone,
        snapshot=snapshot if snapshot is not None else pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone),
        **kwargs,
    )


def test_docking_reacquire_public_interface_exports_family_and_decision_fields():
    decision = docking.DockingReacquireDecision(active=False)

    assert docking.DOCKING_REACQUIRE_CONTROL_FAMILY == "docking_reacquire_v1"
    assert decision.to_dict()["active"] is False
    assert decision.to_dict()["release_blockers"] == []


def test_docking_reacquire_stays_inactive_when_handoff_ready():
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}
    robot_pose = {"x": 6.348, "y": 0.0, "yaw": math.pi}

    decision = _decision(robot_pose, ball_pose)

    assert decision.active is False
    assert decision.release_reason == "pre_stage_handoff_ready"


def test_zero_goal_side_start_selects_safe_docking_entry_without_ball_contact():
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}

    decision = _decision(robot_pose, ball_pose)

    assert decision.active is True
    assert decision.command is not None
    assert decision.command.mode == "docking_reacquire_pre_stage"
    assert decision.strategy_name.startswith("docking_entry_")
    assert decision.segment_ball_clearance_m is not None
    assert decision.segment_ball_clearance_m >= docking.DEFAULT_DOCKING_REACQUIRE_MIN_BALL_CLEARANCE_M
    assert decision.min_ball_clearance_m is not None
    assert decision.min_ball_clearance_m >= docking.DEFAULT_DOCKING_REACQUIRE_MIN_BALL_CLEARANCE_M
    assert abs(float(decision.dock_pose["y"])) >= 0.5


def test_plus45_goal_side_start_improves_goal_side_clearance():
    ball_pose = {"x": 4.555261, "y": 2.155261, "z": 0.05}
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=_zone())

    decision = _decision(robot_pose, ball_pose, snapshot=snapshot)

    assert decision.active is True
    assert decision.command is not None
    assert decision.projected_projection_gain is not None
    assert decision.projected_projection_gain > 0.0
    assert decision.projected_distance_gain is not None
    assert decision.projected_distance_gain > 0.0
    assert decision.projected_lateral_gain is not None
    assert decision.projected_lateral_gain > 0.0
    assert decision.projected_snapshot["robot_longitudinal_projection_m"] < snapshot["robot_longitudinal_projection_m"]


def test_plus45_and_minus45_choose_symmetric_docking_sides():
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    plus_decision = _decision(robot_pose, {"x": 4.555261, "y": 2.155261, "z": 0.05})
    minus_decision = _decision(robot_pose, {"x": 4.555261, "y": -2.155261, "z": 0.05})

    assert plus_decision.active is True
    assert minus_decision.active is True
    assert plus_decision.side_sign == -minus_decision.side_sign
    assert plus_decision.command is not None
    assert minus_decision.command is not None
    assert plus_decision.command.angular_z == -minus_decision.command.angular_z
    assert plus_decision.dock_pose["x"] == minus_decision.dock_pose["x"]
    assert plus_decision.dock_pose["y"] == -minus_decision.dock_pose["y"]


def test_docking_reacquire_releases_to_baseline_only_inside_safe_envelope():
    snapshot = {
        "pre_stage_pose_distance_m": 0.70,
        "robot_longitudinal_projection_m": -0.40,
        "robot_lateral_error_m": 0.25,
        "robot_lateral_signed_m": 0.25,
        "yaw_error_deg": 30.0,
        "robot_on_goal_side": False,
        "pre_stage_pose_reached": False,
    }

    reason = docking.docking_reacquire_release_reason(snapshot, ball_motion_m=0.0)

    assert reason == "baseline_pre_stage_traversal_ready"
    assert docking.docking_reacquire_release_blockers(snapshot, ball_motion_m=0.0) == ()


def test_docking_reacquire_stays_active_when_release_blockers_remain():
    snapshot = {
        "pre_stage_pose_distance_m": 0.66,
        "robot_longitudinal_projection_m": -0.58,
        "robot_lateral_error_m": 0.57,
        "robot_lateral_signed_m": 0.57,
        "yaw_error_deg": 84.0,
        "robot_on_goal_side": False,
        "pre_stage_pose_reached": False,
    }

    assert docking.docking_reacquire_release_reason(snapshot, ball_motion_m=0.0) == ""
    assert docking.docking_reacquire_pre_stage_active(snapshot, ball_motion_m=0.0) is True
    assert docking.docking_reacquire_release_blockers(snapshot, ball_motion_m=0.0) == (
        "lateral_not_converged",
        "yaw_not_aligned",
    )


def test_docking_reacquire_reports_ball_motion_guard():
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}

    decision = _decision(robot_pose, ball_pose, ball_motion_m=0.051)

    assert decision.active is False
    assert decision.release_reason == "ball_motion_guard"
    assert "ball_motion_guard" in decision.release_blockers


def test_docking_reacquire_rejects_invalid_snapshot():
    decision = _decision(
        {"x": 0.0, "y": 0.0, "yaw": 0.0},
        {"x": 5.448, "y": 0.0, "z": 0.05},
        snapshot={"pre_stage_pose_distance_m": "missing"},
    )

    assert decision.active is False
    assert decision.release_reason == "missing_pre_stage_geometry"
