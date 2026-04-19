from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_short_horizon_helpers as short_horizon  # noqa: E402
from gather_mission_helpers import build_zone_spec  # noqa: E402
from gather_mission_helpers import compute_pre_stage_command  # noqa: E402
from gather_mission_helpers import pre_stage_arrival_snapshot  # noqa: E402


ZONE = build_zone_spec("corral_single_ball_place")
PLUS45_BALL_POSE = {"x": 4.555261, "y": 2.155261, "z": 0.05}
EARLY_STALLED_POSE = {"x": -0.056707, "y": 0.197428, "yaw": -2.426363}
MID_STALLED_POSE = {"x": 0.225021, "y": 0.355253, "yaw": -2.694619}
LATE_STALLED_POSE = {"x": 1.445098, "y": 0.838023, "yaw": -2.854658}


def _baseline_projection(robot_pose: dict[str, float], ball_pose: dict[str, float]):
    snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=ZONE)
    baseline_command = compute_pre_stage_command(robot_pose, ball_pose, zone=ZONE)
    assert snapshot is not None
    assert baseline_command is not None
    return short_horizon.project_short_horizon_command(
        robot_pose,
        ball_pose,
        zone=ZONE,
        command=baseline_command,
        strategy_name="baseline_command",
        snapshot=snapshot,
    )


def test_short_horizon_beats_baseline_on_live_shaped_plus45_stall_rows():
    fixtures = [EARLY_STALLED_POSE, MID_STALLED_POSE, LATE_STALLED_POSE]
    for robot_pose in fixtures:
        snapshot = pre_stage_arrival_snapshot(robot_pose, PLUS45_BALL_POSE, zone=ZONE)
        decision = short_horizon.decide_short_horizon_pre_stage_command(
            robot_pose,
            PLUS45_BALL_POSE,
            zone=ZONE,
            snapshot=snapshot,
        )
        baseline_projection = _baseline_projection(robot_pose, PLUS45_BALL_POSE)

        assert snapshot is not None
        assert decision.active is True
        assert decision.command is not None
        assert decision.command.mode == "pre_stage_escape_goal_side"
        assert baseline_projection is not None
        assert decision.progress_score is not None
        assert decision.progress_score > baseline_projection.progress_score


def test_short_horizon_is_symmetric_for_mirrored_plus45_and_minus45():
    minus45_ball_pose = {"x": PLUS45_BALL_POSE["x"], "y": -PLUS45_BALL_POSE["y"], "z": PLUS45_BALL_POSE["z"]}
    mirrored_robot_pose = {
        "x": EARLY_STALLED_POSE["x"],
        "y": -EARLY_STALLED_POSE["y"],
        "yaw": -EARLY_STALLED_POSE["yaw"],
    }

    plus_decision = short_horizon.decide_short_horizon_pre_stage_command(
        EARLY_STALLED_POSE,
        PLUS45_BALL_POSE,
        zone=ZONE,
    )
    minus_decision = short_horizon.decide_short_horizon_pre_stage_command(
        mirrored_robot_pose,
        minus45_ball_pose,
        zone=ZONE,
    )

    assert plus_decision.active is True
    assert minus_decision.active is True
    assert plus_decision.command is not None
    assert minus_decision.command is not None
    assert plus_decision.progress_score is not None
    assert minus_decision.progress_score is not None
    assert abs(float(plus_decision.progress_score) - float(minus_decision.progress_score)) < 1.0e-6
    assert abs(float(plus_decision.command.linear_x) - float(minus_decision.command.linear_x)) < 1.0e-6
    assert abs(float(plus_decision.command.angular_z) + float(minus_decision.command.angular_z)) < 1.0e-6


def test_short_horizon_stays_inactive_once_existing_behind_ball_handoff_owns_control():
    robot_pose = {"x": 0.41, "y": 0.0, "yaw": 0.0}
    ball_pose = {"x": 1.0, "y": 0.0, "z": 0.05}
    snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=ZONE)

    decision = short_horizon.decide_short_horizon_pre_stage_command(
        robot_pose,
        ball_pose,
        zone=ZONE,
        snapshot=snapshot,
    )

    assert snapshot is not None
    assert snapshot["pre_stage_pose_reached"] is True
    assert decision.active is False


def test_short_horizon_stays_inactive_until_large_start_of_run_yaw_is_recovered():
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    snapshot = pre_stage_arrival_snapshot(robot_pose, PLUS45_BALL_POSE, zone=ZONE)

    decision = short_horizon.decide_short_horizon_pre_stage_command(
        robot_pose,
        PLUS45_BALL_POSE,
        zone=ZONE,
        snapshot=snapshot,
    )

    assert snapshot is not None
    assert snapshot["yaw_error_deg"] > 45.0
    assert decision.active is False
