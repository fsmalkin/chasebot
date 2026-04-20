from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_escape_oracle as oracle  # noqa: E402
import gather_escape_sandbox as sandbox  # noqa: E402
from gather_mission_helpers import build_zone_spec  # noqa: E402


ZONE = build_zone_spec("corral_single_ball_place")
PLUS45_BALL_POSE = {"x": 4.555261, "y": 2.155261, "z": 0.05}
LIVE_POST_YAW_GATE_POSE = {"x": -0.097434, "y": 0.157671, "yaw": -2.01106}
LIVE_MID_STALLED_POSE = {"x": 0.308136, "y": 0.436242, "yaw": -2.688203}
SANDBOX_ONLY_CORRIDOR_LOCAL = {"x": 1.0744275463932906, "y": 0.443135200677364, "yaw": -1.654040212523118}
GOAL_SIDE_ONLY_LOCAL = {"x": 0.683356291326266, "y": 1.988069459481704, "yaw": -0.4201604136141306}
PRIMARY_GATE_GREEN_LOCAL = {"x": 0.6855575525102697, "y": 0.5898063027663567, "yaw": -1.8600896669038416}


def _mirror_macro_name(name: str) -> str:
    if "_left" in name:
        return name.replace("_left", "_right")
    if "_right" in name:
        return name.replace("_right", "_left")
    return name


def _write_state_history(tmp_path: Path, robot_pose: dict[str, float], *, row_count: int = 5) -> Path:
    state_history_path = tmp_path / "state_history.jsonl"
    rows = []
    for index in range(row_count):
        rows.append(
            {
                "generated_utc": f"2026-04-19T23:00:{index:02d}Z",
                "phase": "pre_stage",
                "attempt": 0,
                "robot_pose": dict(robot_pose),
                "ball_pose": dict(PLUS45_BALL_POSE),
                "pre_stage": {"yaw_error_deg": 30.0},
            }
        )
    state_history_path.write_text("\n".join(json.dumps(item) for item in rows), encoding="utf-8")
    return state_history_path


def test_sandbox_is_symmetric_for_mirrored_corridor_fixture():
    plus_world = sandbox.local_pose_to_world(SANDBOX_ONLY_CORRIDOR_LOCAL, PLUS45_BALL_POSE, zone=ZONE)
    minus_ball = {"x": PLUS45_BALL_POSE["x"], "y": -PLUS45_BALL_POSE["y"], "z": PLUS45_BALL_POSE["z"]}
    minus_local = {
        "x": SANDBOX_ONLY_CORRIDOR_LOCAL["x"],
        "y": -SANDBOX_ONLY_CORRIDOR_LOCAL["y"],
        "yaw": -SANDBOX_ONLY_CORRIDOR_LOCAL["yaw"],
    }
    minus_world = sandbox.local_pose_to_world(minus_local, minus_ball, zone=ZONE)

    plus_results = sandbox.search_sandbox_sequences(plus_world, PLUS45_BALL_POSE, zone=ZONE, top_k=1)
    minus_results = sandbox.search_sandbox_sequences(minus_world, minus_ball, zone=ZONE, top_k=1)

    assert plus_results
    assert minus_results
    assert plus_results[0].corridor_clearable is True
    assert minus_results[0].corridor_clearable is True
    assert plus_results[0].family_name == minus_results[0].family_name
    assert tuple(_mirror_macro_name(name) for name in plus_results[0].macro_sequence) == minus_results[0].macro_sequence
    assert abs(float(plus_results[0].projection_gain) - float(minus_results[0].projection_gain)) < 1.0e-6
    assert abs(float(plus_results[0].lateral_gain) - float(minus_results[0].lateral_gain)) < 1.0e-6


def test_sandbox_finds_corridor_clear_fixture_that_oracle_does_not_clear():
    world_pose = sandbox.local_pose_to_world(SANDBOX_ONLY_CORRIDOR_LOCAL, PLUS45_BALL_POSE, zone=ZONE)

    sandbox_results = sandbox.search_sandbox_sequences(world_pose, PLUS45_BALL_POSE, zone=ZONE, top_k=1)
    oracle_results = oracle.search_escape_sequences(world_pose, PLUS45_BALL_POSE, zone=ZONE, search_profile="deep_escape_v1")

    assert sandbox_results
    assert oracle_results
    assert sandbox_results[0].corridor_clearable is True
    assert sandbox_results[0].feasibility_class == "corridor_clearable"
    assert oracle_results[0].stable_goal_side_cleared is False
    assert oracle_results[0].feasibility_class in {"near_clear", "not_clearable"}


def test_sandbox_can_classify_goal_side_clear_without_corridor():
    world_pose = sandbox.local_pose_to_world(GOAL_SIDE_ONLY_LOCAL, PLUS45_BALL_POSE, zone=ZONE)

    results = sandbox.search_sandbox_sequences(world_pose, PLUS45_BALL_POSE, zone=ZONE, top_k=1)

    assert results
    assert results[0].goal_side_clearable is True
    assert results[0].corridor_clearable is False
    assert results[0].feasibility_class == "goal_side_clearable"
    assert float(results[0].projected_snapshot["robot_lateral_error_m"]) > sandbox.DEFAULT_ESCAPE_SANDBOX_CORRIDOR_MAX_LATERAL_M


def test_live_plus45_stall_rows_remain_non_promoting_when_safe_side_is_not_reached():
    for robot_pose in [LIVE_POST_YAW_GATE_POSE, LIVE_MID_STALLED_POSE]:
        results = sandbox.search_sandbox_sequences(robot_pose, PLUS45_BALL_POSE, zone=ZONE, top_k=3)

        assert results
        assert all(item.corridor_clearable is False for item in results)
        assert all(item.goal_side_clearable is False for item in results)
        assert all(item.feasibility_class in {"near_clear", "not_clearable"} for item in results)


def test_build_sandbox_bundle_unlocks_controller_distillation_when_primary_family_clears_corridor(tmp_path: Path):
    robot_pose = sandbox.local_pose_to_world(PRIMARY_GATE_GREEN_LOCAL, PLUS45_BALL_POSE, zone=ZONE)
    state_history_path = _write_state_history(tmp_path, robot_pose)

    summary, trajectories = sandbox.build_sandbox_bundle([("short_horizon_v2", state_history_path)], campaign_id="sandbox-pass")

    assert summary["selected_primary_family"] == "clear_then_realign"
    assert summary["primary_corridor_clear_count"] == 5
    assert summary["stable_goal_side_clear_count"] == 5
    assert summary["feasibility_class"] == "corridor_clearable"
    assert summary["decision_outcome"] == "unlock_controller_distillation"
    assert set(trajectories.keys()) == {
        "first_post_yaw_gate",
        "early_stall",
        "mid_stall",
        "late_stall",
        "terminal_stall",
    }


def test_build_sandbox_bundle_reports_escape_only_lane_when_corridor_is_not_reached(tmp_path: Path):
    robot_pose = sandbox.local_pose_to_world(GOAL_SIDE_ONLY_LOCAL, PLUS45_BALL_POSE, zone=ZONE)
    state_history_path = _write_state_history(tmp_path, robot_pose)

    summary, _ = sandbox.build_sandbox_bundle([("short_horizon_v2", state_history_path)], campaign_id="sandbox-goal-side-only")

    assert summary["primary_corridor_clear_count"] == 0
    assert summary["stable_goal_side_clear_count"] == 5
    assert summary["feasibility_class"] == "goal_side_clearable"
    assert summary["decision_outcome"] == "escape_only_live_lane"
