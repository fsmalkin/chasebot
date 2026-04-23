from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_region_funnel_helpers as region_funnel  # noqa: E402
from gather_mission_helpers import PlaceControlCommand  # noqa: E402
from gather_mission_helpers import build_zone_spec  # noqa: E402
from gather_mission_helpers import pre_stage_arrival_snapshot  # noqa: E402


ZONE = build_zone_spec("corral_single_ball_place")
PLUS45_BALL_POSE = {"x": 4.555261, "y": 2.155261, "z": 0.05}
POST_YAW_GATE_POSE = {"x": -0.097434, "y": 0.157671, "yaw": -2.01106}
MID_STALLED_POSE = {"x": 0.308136, "y": 0.436242, "yaw": -2.688203}
LATE_STALLED_POSE = {"x": 1.132622, "y": 0.786392, "yaw": -2.867772}


def _decision(
    robot_pose: dict[str, float],
    ball_pose: dict[str, float],
    *,
    previous_strategy_name: str = "",
    stall_s: float = 0.0,
    strategy_elapsed_s: float = 0.0,
):
    snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=ZONE)
    return region_funnel.decide_region_funnel_pre_stage_command(
        robot_pose,
        ball_pose,
        zone=ZONE,
        snapshot=snapshot,
        previous_strategy_name=previous_strategy_name,
        stall_s=stall_s,
        strategy_elapsed_s=strategy_elapsed_s,
    )


def _assert_bounded_command(command: PlaceControlCommand) -> None:
    assert command.mode == "pre_stage_escape_goal_side"
    assert -0.18 <= float(command.linear_x) <= 0.0
    assert -0.75 <= float(command.angular_z) <= 0.75
    assert float(command.target_speed_scale) == 0.0


def test_region_funnel_public_interface_exports_family_and_decision_fields():
    decision = region_funnel.RegionFunnelDecision(active=False)

    assert region_funnel.REGION_FUNNEL_CONTROL_FAMILY == "region_funnel_v1"
    assert decision.to_dict() == {
        "active": False,
        "strategy_name": "",
        "objective_name": "",
        "progress_score": None,
        "command": None,
        "projected_projection_gain": None,
        "projected_lateral_gain": None,
        "projected_distance_gain": None,
    }


def test_region_funnel_handles_plus45_shaped_stall_rows_with_scripted_fallbacks():
    for robot_pose in [POST_YAW_GATE_POSE, MID_STALLED_POSE, LATE_STALLED_POSE]:
        decision = _decision(robot_pose, PLUS45_BALL_POSE, stall_s=1.5)

        assert decision.active is True
        assert decision.objective_name == "scripted_maneuver_fallback"
        assert decision.strategy_name in {"scripted_reflank_left", "scripted_reflank_right"}
        assert decision.command is not None
        assert decision.progress_score is not None
        assert decision.projected_projection_gain is not None
        assert decision.projected_distance_gain is not None
        _assert_bounded_command(decision.command)


def test_region_funnel_uses_region_objective_before_scripted_stall_threshold():
    decision = _decision(POST_YAW_GATE_POSE, PLUS45_BALL_POSE, stall_s=0.0)

    assert decision.active is True
    assert decision.objective_name == "region_funnel"
    assert decision.strategy_name in {"funnel_reacquire", "funnel_reverse_clear"}
    assert decision.command is not None
    _assert_bounded_command(decision.command)


def test_region_funnel_scripted_fallback_is_symmetric_for_plus45_and_minus45():
    minus45_ball_pose = {"x": PLUS45_BALL_POSE["x"], "y": -PLUS45_BALL_POSE["y"], "z": PLUS45_BALL_POSE["z"]}
    mirrored_robot_pose = {
        "x": POST_YAW_GATE_POSE["x"],
        "y": -POST_YAW_GATE_POSE["y"],
        "yaw": -POST_YAW_GATE_POSE["yaw"],
    }

    plus_decision = _decision(POST_YAW_GATE_POSE, PLUS45_BALL_POSE, stall_s=1.5)
    minus_decision = _decision(mirrored_robot_pose, minus45_ball_pose, stall_s=1.5)

    assert plus_decision.active is True
    assert minus_decision.active is True
    assert plus_decision.command is not None
    assert minus_decision.command is not None
    assert plus_decision.strategy_name == "scripted_reflank_right"
    assert minus_decision.strategy_name == "scripted_reflank_left"
    assert abs(float(plus_decision.command.linear_x) - float(minus_decision.command.linear_x)) < 1.0e-6
    assert abs(float(plus_decision.command.angular_z) + float(minus_decision.command.angular_z)) < 1.0e-6
    assert plus_decision.progress_score == minus_decision.progress_score
    assert plus_decision.projected_projection_gain == minus_decision.projected_projection_gain
    assert plus_decision.projected_lateral_gain == minus_decision.projected_lateral_gain
    assert plus_decision.projected_distance_gain == minus_decision.projected_distance_gain


def test_region_funnel_stays_inactive_once_existing_pre_stage_handoff_owns_control():
    robot_pose = {"x": 0.41, "y": 0.0, "yaw": 0.0}
    ball_pose = {"x": 1.0, "y": 0.0, "z": 0.05}
    snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=ZONE)
    decision = region_funnel.decide_region_funnel_pre_stage_command(
        robot_pose,
        ball_pose,
        zone=ZONE,
        snapshot=snapshot,
    )

    assert snapshot is not None
    assert snapshot["pre_stage_pose_reached"] is True
    assert decision.active is False
    assert decision.command is None


def test_region_funnel_stays_inactive_for_invalid_snapshot():
    decision = region_funnel.decide_region_funnel_pre_stage_command(
        POST_YAW_GATE_POSE,
        PLUS45_BALL_POSE,
        zone=ZONE,
        snapshot={"pre_stage_pose_reached": False},
    )

    assert decision.active is False
    assert decision.command is None


def test_region_funnel_stays_inactive_until_large_start_of_run_yaw_is_recovered():
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    snapshot = pre_stage_arrival_snapshot(robot_pose, PLUS45_BALL_POSE, zone=ZONE)
    decision = region_funnel.decide_region_funnel_pre_stage_command(
        robot_pose,
        PLUS45_BALL_POSE,
        zone=ZONE,
        snapshot=snapshot,
    )

    assert snapshot is not None
    assert snapshot["yaw_error_deg"] > 45.0
    assert decision.active is False
    assert decision.command is None
