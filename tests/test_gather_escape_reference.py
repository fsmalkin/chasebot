from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_escape_reference as reference  # noqa: E402
import gather_escape_sandbox as sandbox  # noqa: E402
from gather_mission_helpers import build_zone_spec  # noqa: E402


ZONE = build_zone_spec("corral_single_ball_place")
PLUS45_BALL_POSE = {"x": 4.555261, "y": 2.155261, "z": 0.05}
LIVE_POST_YAW_GATE_POSE = {"x": -0.097434, "y": 0.157671, "yaw": -2.01106}
LIVE_MID_STALLED_POSE = {"x": 0.308136, "y": 0.436242, "yaw": -2.688203}
REFERENCE_CORRIDOR_LOCAL = {"x": 0.31361758022929265, "y": 0.25607254243872984, "yaw": -2.3296093313272754}
REFERENCE_GOAL_SIDE_LOCAL = {"x": 0.3245497006069665, "y": 0.981579101726195, "yaw": -0.15782582158029346}
REFERENCE_PRIMARY_GATE_LOCAL = REFERENCE_CORRIDOR_LOCAL


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
                "generated_utc": f"2026-04-19T23:30:{index:02d}Z",
                "phase": "pre_stage",
                "attempt": 0,
                "robot_pose": dict(robot_pose),
                "ball_pose": dict(PLUS45_BALL_POSE),
                "pre_stage": {"yaw_error_deg": 30.0},
            }
        )
    state_history_path.write_text("\n".join(json.dumps(item) for item in rows), encoding="utf-8")
    return state_history_path


def test_reference_is_symmetric_for_mirrored_corridor_fixture():
    plus_world = sandbox.local_pose_to_world(REFERENCE_CORRIDOR_LOCAL, PLUS45_BALL_POSE, zone=ZONE)
    minus_ball = {"x": PLUS45_BALL_POSE["x"], "y": -PLUS45_BALL_POSE["y"], "z": PLUS45_BALL_POSE["z"]}
    minus_local = {
        "x": REFERENCE_CORRIDOR_LOCAL["x"],
        "y": -REFERENCE_CORRIDOR_LOCAL["y"],
        "yaw": -REFERENCE_CORRIDOR_LOCAL["yaw"],
    }
    minus_world = sandbox.local_pose_to_world(minus_local, minus_ball, zone=ZONE)

    plus_results = reference.search_reference_maneuvers(plus_world, PLUS45_BALL_POSE, zone=ZONE, top_k=1)
    minus_results = reference.search_reference_maneuvers(minus_world, minus_ball, zone=ZONE, top_k=1)

    assert plus_results
    assert minus_results
    assert plus_results[0].corridor_clearable is True
    assert minus_results[0].corridor_clearable is True
    assert plus_results[0].family_name == minus_results[0].family_name
    assert tuple(_mirror_macro_name(name) for name in plus_results[0].macro_sequence) == minus_results[0].macro_sequence
    assert abs(float(plus_results[0].projection_gain) - float(minus_results[0].projection_gain)) < 1.0e-6
    assert abs(float(plus_results[0].lateral_gain) - float(minus_results[0].lateral_gain)) < 1.0e-6


def test_reference_finds_corridor_clearable_fixture():
    world_pose = sandbox.local_pose_to_world(REFERENCE_CORRIDOR_LOCAL, PLUS45_BALL_POSE, zone=ZONE)

    results = reference.search_reference_maneuvers(world_pose, PLUS45_BALL_POSE, zone=ZONE, top_k=1)

    assert results
    assert results[0].corridor_clearable is True
    assert results[0].feasibility_class == "corridor_clearable"


def test_reference_can_classify_goal_side_clear_without_corridor():
    world_pose = sandbox.local_pose_to_world(REFERENCE_GOAL_SIDE_LOCAL, PLUS45_BALL_POSE, zone=ZONE)

    results = reference.search_reference_maneuvers(world_pose, PLUS45_BALL_POSE, zone=ZONE, top_k=1)

    assert results
    assert results[0].goal_side_clearable is True
    assert results[0].corridor_clearable is False
    assert results[0].feasibility_class == "goal_side_clearable"
    assert float(results[0].projected_snapshot["robot_lateral_error_m"]) > reference.DEFAULT_ESCAPE_REFERENCE_CORRIDOR_MAX_LATERAL_M


def test_live_plus45_stall_rows_remain_non_promoting_when_safe_side_is_not_reached():
    for robot_pose in [LIVE_POST_YAW_GATE_POSE, LIVE_MID_STALLED_POSE]:
        results = reference.search_reference_maneuvers(robot_pose, PLUS45_BALL_POSE, zone=ZONE, top_k=3)

        assert results
        assert all(item.corridor_clearable is False for item in results)
        assert all(item.goal_side_clearable is False for item in results)
        assert all(item.feasibility_class in {"near_clear", "not_clearable"} for item in results)


def test_build_reference_bundle_unlocks_distillation_when_primary_family_clears_corridor(tmp_path: Path):
    robot_pose = sandbox.local_pose_to_world(REFERENCE_PRIMARY_GATE_LOCAL, PLUS45_BALL_POSE, zone=ZONE)
    state_history_path = _write_state_history(tmp_path, robot_pose)

    summary, trajectories = reference.build_reference_bundle([("short_horizon_v2", state_history_path)], campaign_id="reference-pass")

    assert summary["selected_primary_family"] == "wide_loop"
    assert summary["primary_corridor_clear_count"] == 5
    assert summary["stable_goal_side_clear_count"] == 5
    assert summary["feasibility_class"] == "corridor_clearable"
    assert summary["decision_outcome"] == "unlock_sandbox_v2_distillation"
    assert set(trajectories.keys()) == {
        "first_post_yaw_gate",
        "early_stall",
        "mid_stall",
        "late_stall",
        "terminal_stall",
    }


def test_build_reference_bundle_reports_corridor_completion_lane_when_only_goal_side_clear_is_reached(tmp_path: Path):
    robot_pose = sandbox.local_pose_to_world(REFERENCE_GOAL_SIDE_LOCAL, PLUS45_BALL_POSE, zone=ZONE)
    state_history_path = _write_state_history(tmp_path, robot_pose)

    summary, _ = reference.build_reference_bundle([("short_horizon_v2", state_history_path)], campaign_id="reference-goal-side-only")

    assert summary["primary_corridor_clear_count"] == 0
    assert summary["stable_goal_side_clear_count"] == 5
    assert summary["feasibility_class"] == "goal_side_clearable"
    assert summary["decision_outcome"] == "sandbox_v2_corridor_completion"
