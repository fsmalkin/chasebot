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
LARGE_YAW_START_POSE = {"x": 0.0, "y": 0.0, "yaw": 0.0}
POST_YAW_GATE_POSE = {"x": -0.097434, "y": 0.157671, "yaw": -2.01106}
MID_STALLED_POSE = {"x": 0.308136, "y": 0.436242, "yaw": -2.688203}
LATE_STALLED_POSE = {"x": 1.132622, "y": 0.786392, "yaw": -2.867772}


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


def _short_horizon_decision(
    robot_pose: dict[str, float],
    ball_pose: dict[str, float],
    *,
    control_family: str,
    previous_strategy_name: str = "",
    stall_s: float = 0.0,
    strategy_elapsed_s: float = 0.0,
):
    snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=ZONE)
    decision = short_horizon.decide_short_horizon_pre_stage_command(
        robot_pose,
        ball_pose,
        zone=ZONE,
        snapshot=snapshot,
        control_family=control_family,
        previous_strategy_name=previous_strategy_name,
        stall_s=stall_s,
        strategy_elapsed_s=strategy_elapsed_s,
    )
    return snapshot, decision


def test_short_horizon_v1_beats_baseline_on_live_shaped_plus45_stall_rows():
    fixtures = [POST_YAW_GATE_POSE, MID_STALLED_POSE, LATE_STALLED_POSE]
    for robot_pose in fixtures:
        snapshot, decision = _short_horizon_decision(
            robot_pose,
            PLUS45_BALL_POSE,
            control_family="short_horizon_v1",
        )
        baseline_projection = _baseline_projection(robot_pose, PLUS45_BALL_POSE)

        assert snapshot is not None
        assert decision.active is True
        assert decision.command is not None
        assert decision.command.mode == "pre_stage_escape_goal_side"
        assert baseline_projection is not None
        assert decision.progress_score is not None
        assert decision.progress_score > baseline_projection.progress_score


def test_short_horizon_v2_chooses_reflank_after_yaw_gate():
    snapshot, decision = _short_horizon_decision(
        POST_YAW_GATE_POSE,
        PLUS45_BALL_POSE,
        control_family="short_horizon_v2",
    )

    assert snapshot is not None
    assert decision.active is True
    assert decision.projection is not None
    assert decision.objective_name == short_horizon.SHORT_HORIZON_ESCAPE_REGION_OBJECTIVE
    assert decision.strategy_name in short_horizon.SHORT_HORIZON_REFLANK_STRATEGIES
    assert decision.strategy_name not in {"hold", "reverse_straight", "reverse_direct_heading"}
    assert abs(float(decision.command.angular_z)) == 0.8


def test_short_horizon_v2_reflank_commit_holds_strategy_for_one_second():
    snapshot, decision = _short_horizon_decision(
        POST_YAW_GATE_POSE,
        PLUS45_BALL_POSE,
        control_family="short_horizon_v2",
    )
    assert snapshot is not None
    assert decision.strategy_name in short_horizon.SHORT_HORIZON_REFLANK_STRATEGIES

    _, committed = _short_horizon_decision(
        POST_YAW_GATE_POSE,
        PLUS45_BALL_POSE,
        control_family="short_horizon_v2",
        previous_strategy_name=decision.strategy_name,
        stall_s=0.8,
        strategy_elapsed_s=0.5,
    )

    assert committed.active is True
    assert committed.strategy_name == decision.strategy_name


def test_short_horizon_v2_forces_reflank_after_direct_heading_stall():
    snapshot, decision = _short_horizon_decision(
        MID_STALLED_POSE,
        PLUS45_BALL_POSE,
        control_family="short_horizon_v2",
        previous_strategy_name="reverse_direct_heading",
        stall_s=1.6,
        strategy_elapsed_s=1.6,
    )

    assert snapshot is not None
    assert decision.active is True
    assert decision.strategy_name in short_horizon.SHORT_HORIZON_REFLANK_STRATEGIES


def test_short_horizon_v2_is_symmetric_for_mirrored_plus45_and_minus45():
    minus45_ball_pose = {"x": PLUS45_BALL_POSE["x"], "y": -PLUS45_BALL_POSE["y"], "z": PLUS45_BALL_POSE["z"]}
    mirrored_robot_pose = {
        "x": POST_YAW_GATE_POSE["x"],
        "y": -POST_YAW_GATE_POSE["y"],
        "yaw": -POST_YAW_GATE_POSE["yaw"],
    }

    _, plus_decision = _short_horizon_decision(
        POST_YAW_GATE_POSE,
        PLUS45_BALL_POSE,
        control_family="short_horizon_v2",
    )
    _, minus_decision = _short_horizon_decision(
        mirrored_robot_pose,
        minus45_ball_pose,
        control_family="short_horizon_v2",
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
    assert plus_decision.strategy_name in short_horizon.SHORT_HORIZON_REFLANK_STRATEGIES
    assert minus_decision.strategy_name in short_horizon.SHORT_HORIZON_REFLANK_STRATEGIES


def test_short_horizon_v2_beats_baseline_and_v1_on_mid_and_late_stalled_rows():
    for robot_pose in [MID_STALLED_POSE, LATE_STALLED_POSE]:
        baseline_projection = _baseline_projection(robot_pose, PLUS45_BALL_POSE)
        _, v1_decision = _short_horizon_decision(
            robot_pose,
            PLUS45_BALL_POSE,
            control_family="short_horizon_v1",
        )
        _, v2_decision = _short_horizon_decision(
            robot_pose,
            PLUS45_BALL_POSE,
            control_family="short_horizon_v2",
        )

        assert baseline_projection is not None
        assert v1_decision.progress_score is not None
        assert v2_decision.progress_score is not None
        assert v2_decision.progress_score > baseline_projection.progress_score
        assert v2_decision.progress_score > v1_decision.progress_score
        assert v2_decision.strategy_name in short_horizon.SHORT_HORIZON_REFLANK_STRATEGIES


def test_short_horizon_v2_stays_inactive_once_existing_behind_ball_handoff_owns_control():
    robot_pose = {"x": 0.41, "y": 0.0, "yaw": 0.0}
    ball_pose = {"x": 1.0, "y": 0.0, "z": 0.05}
    snapshot, decision = _short_horizon_decision(
        robot_pose,
        ball_pose,
        control_family="short_horizon_v2",
    )

    assert snapshot is not None
    assert snapshot["pre_stage_pose_reached"] is True
    assert decision.active is False


def test_short_horizon_v2_stays_inactive_until_large_start_of_run_yaw_is_recovered():
    snapshot, decision = _short_horizon_decision(
        LARGE_YAW_START_POSE,
        PLUS45_BALL_POSE,
        control_family="short_horizon_v2",
    )

    assert snapshot is not None
    assert snapshot["yaw_error_deg"] > 45.0
    assert decision.active is False
