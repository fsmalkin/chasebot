from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_escape_oracle as oracle  # noqa: E402
from gather_mission_helpers import build_zone_spec  # noqa: E402
from gather_mission_helpers import pre_stage_arrival_snapshot  # noqa: E402


ZONE = build_zone_spec("corral_single_ball_place")
PLUS45_BALL_POSE = {"x": 4.555261, "y": 2.155261, "z": 0.05}
LIVE_POST_YAW_GATE_POSE = {"x": -0.097434, "y": 0.157671, "yaw": -2.01106}
LIVE_MID_STALLED_POSE = {"x": 0.308136, "y": 0.436242, "yaw": -2.688203}
CONTROL_CLEAR_POSE = {"x": 4.542845, "y": 2.458262, "yaw": -2.330346}
DEEP_ONLY_CLEAR_POSE = {"x": 3.687587, "y": 1.694548, "yaw": -1.139115}
UNSTABLE_CLEAR_POSE = {"x": 3.874382, "y": 1.372011, "yaw": -1.118099}


def _mirror_macro_name(name: str) -> str:
    if "_left" in name:
        return name.replace("_left", "_right")
    if "_right" in name:
        return name.replace("_right", "_left")
    return name


def test_search_escape_sequences_finds_goal_side_clear_on_synthetic_fixture():
    results = oracle.search_escape_sequences(
        CONTROL_CLEAR_POSE,
        PLUS45_BALL_POSE,
        zone=ZONE,
        search_profile="control_v1",
    )

    assert results
    assert any(item.goal_side_cleared for item in results)
    assert results[0].goal_side_cleared is True
    assert results[0].stable_goal_side_cleared is True
    assert results[0].feasibility_class == "clearable"
    assert results[0].promoting is True


def test_deep_profile_is_symmetric_for_mirrored_fixture():
    mirrored_ball_pose = {"x": PLUS45_BALL_POSE["x"], "y": -PLUS45_BALL_POSE["y"], "z": PLUS45_BALL_POSE["z"]}
    mirrored_robot_pose = {
        "x": DEEP_ONLY_CLEAR_POSE["x"],
        "y": -DEEP_ONLY_CLEAR_POSE["y"],
        "yaw": -DEEP_ONLY_CLEAR_POSE["yaw"],
    }

    plus_results = oracle.search_escape_sequences(
        DEEP_ONLY_CLEAR_POSE,
        PLUS45_BALL_POSE,
        zone=ZONE,
        search_profile="deep_escape_v1",
    )
    minus_results = oracle.search_escape_sequences(
        mirrored_robot_pose,
        mirrored_ball_pose,
        zone=ZONE,
        search_profile="deep_escape_v1",
    )

    assert plus_results
    assert minus_results
    assert plus_results[0].stable_goal_side_cleared is True
    assert minus_results[0].stable_goal_side_cleared is True
    assert plus_results[0].family_name == minus_results[0].family_name
    assert tuple(_mirror_macro_name(name) for name in plus_results[0].macro_sequence) == minus_results[0].macro_sequence
    assert abs(float(plus_results[0].projection_gain) - float(minus_results[0].projection_gain)) < 1.0e-6
    assert abs(float(plus_results[0].lateral_gain) - float(minus_results[0].lateral_gain)) < 1.0e-6


def test_live_stall_rows_are_non_promoting_when_goal_side_persists():
    for robot_pose in [LIVE_POST_YAW_GATE_POSE, LIVE_MID_STALLED_POSE]:
        results = oracle.search_escape_sequences(
            robot_pose,
            PLUS45_BALL_POSE,
            zone=ZONE,
            search_profile="deep_escape_v1",
        )

        assert results
        assert all(item.promoting is False for item in results)
        assert all(item.stable_goal_side_cleared is False for item in results)
        assert all(item.goal_side_cleared is False for item in results)


def test_deep_profile_unlocks_multi_segment_clear_that_control_profile_misses():
    control_results = oracle.search_escape_sequences(
        DEEP_ONLY_CLEAR_POSE,
        PLUS45_BALL_POSE,
        zone=ZONE,
        search_profile="control_v1",
    )
    deep_results = oracle.search_escape_sequences(
        DEEP_ONLY_CLEAR_POSE,
        PLUS45_BALL_POSE,
        zone=ZONE,
        search_profile="deep_escape_v1",
    )

    assert control_results
    assert deep_results
    assert control_results[0].stable_goal_side_cleared is False
    assert deep_results[0].stable_goal_side_cleared is True
    assert deep_results[0].feasibility_class == "clearable"
    assert deep_results[0].family_name == "clear_then_realign"
    assert deep_results[0].macro_sequence == (
        "clear_then_realign_right",
        "reverse_arc_left_soft",
        "reverse_straight",
    )


def test_stable_clear_requires_final_window_not_just_final_pose():
    macro_library = oracle.build_escape_macro_library("deep_escape_v1")
    macro_sequence = tuple(
        macro_library[name]
        for name in ("clear_then_realign_right", "reverse_arc_left_hard", "reverse_arc_left_soft")
    )

    result = oracle.evaluate_escape_sequence(
        UNSTABLE_CLEAR_POSE,
        PLUS45_BALL_POSE,
        macro_sequence,
        zone=ZONE,
        search_profile="deep_escape_v1",
    )

    assert result is not None
    assert result.goal_side_cleared is True
    assert result.stable_goal_side_cleared is False
    assert result.promoting is False
    assert result.feasibility_class == "not_clearable"


def test_select_representative_fixture_rows_returns_five_labeled_rows():
    rows = []
    for index in range(12):
        yaw_error_deg = 90.0 if index < 2 else max(5.0, 45.0 - (index * 2.0))
        rows.append(
            {
                "generated_utc": f"2026-04-19T22:00:{index:02d}Z",
                "robot_pose": {"x": float(index), "y": 0.0, "yaw": 0.0},
                "ball_pose": dict(PLUS45_BALL_POSE),
                "pre_stage": {"yaw_error_deg": yaw_error_deg},
            }
        )

    fixtures = oracle.select_representative_fixture_rows(rows)

    assert [item["fixture_label"] for item in fixtures] == [
        "first_post_yaw_gate",
        "early_stall",
        "mid_stall",
        "late_stall",
        "terminal_stall",
    ]
    assert len({int(item["fixture_index"]) for item in fixtures}) == 5
    assert fixtures[0]["fixture_index"] >= 2
    assert fixtures[-1]["fixture_index"] == len(rows) - 1


def test_load_pre_stage_attempt_rows_falls_back_to_earliest_attempt_for_fresh_traces(tmp_path: Path):
    state_history_path = tmp_path / "state_history.jsonl"
    rows = [
        {
            "generated_utc": "2026-04-19T22:00:01Z",
            "phase": "pre_stage",
            "attempt": 1,
            "robot_pose": dict(LIVE_POST_YAW_GATE_POSE),
            "ball_pose": dict(PLUS45_BALL_POSE),
            "pre_stage": pre_stage_arrival_snapshot(LIVE_POST_YAW_GATE_POSE, PLUS45_BALL_POSE, zone=ZONE),
        },
        {
            "generated_utc": "2026-04-19T22:00:02Z",
            "phase": "pre_stage",
            "attempt": 1,
            "robot_pose": dict(LIVE_MID_STALLED_POSE),
            "ball_pose": dict(PLUS45_BALL_POSE),
            "pre_stage": pre_stage_arrival_snapshot(LIVE_MID_STALLED_POSE, PLUS45_BALL_POSE, zone=ZONE),
        },
    ]
    state_history_path.write_text("\n".join(json.dumps(item) for item in rows), encoding="utf-8")

    loaded = oracle.load_pre_stage_attempt_rows(state_history_path, attempt=0)

    assert len(loaded) == 2
    assert all(int(item["attempt"]) == 1 for item in loaded)


def test_build_oracle_summary_uses_campaign_summary_trace_and_reports_gate(tmp_path: Path):
    mission_root = tmp_path / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    state_history_path = mission_root / "state_history.jsonl"
    representative_poses = [
        {"x": -0.097434, "y": 0.157671, "yaw": -2.01106},
        {"x": 0.022297, "y": 0.284275, "yaw": -2.540351},
        {"x": 0.308136, "y": 0.436242, "yaw": -2.688203},
        {"x": 0.76033, "y": 0.654703, "yaw": -2.69224},
        {"x": 1.132622, "y": 0.786392, "yaw": -2.867772},
    ]
    rows = []
    for index, robot_pose in enumerate(representative_poses, start=1):
        snapshot = pre_stage_arrival_snapshot(robot_pose, PLUS45_BALL_POSE, zone=ZONE)
        rows.append(
            {
                "generated_utc": f"2026-04-19T22:00:{index:02d}Z",
                "phase": "pre_stage",
                "attempt": 0,
                "robot_pose": robot_pose,
                "ball_pose": dict(PLUS45_BALL_POSE),
                "pre_stage": snapshot,
            }
        )
    state_history_path.write_text("\n".join(json.dumps(item) for item in rows), encoding="utf-8")

    campaign_summary_path = tmp_path / "campaign_summary.json"
    campaign_summary_path.write_text(
        json.dumps({"runs": [{"mission_root": str(mission_root)}]}),
        encoding="utf-8",
    )

    trace_specs = [("short_horizon_v2", oracle._state_history_path_from_campaign_summary(campaign_summary_path))]
    summary = oracle.build_oracle_summary(trace_specs, campaign_id="oracle-test")

    assert summary["primary_trace_family"] == "short_horizon_v2"
    assert summary["search_profile"] == "deep_escape_v1"
    assert summary["representative_fixture_count"] == 5
    assert summary["primary_goal_side_clear_count"] == 0
    assert summary["stable_goal_side_clear_count"] == 0
    assert summary["near_clear_count"] == 1
    assert summary["feasibility_class"] == "near_clear"
    assert summary["wave_2_gate_pass"] is False
    assert summary["trace_summaries"][0]["selected_v3_family"] == "clear_then_realign"
    assert summary["trace_summaries"][0]["stable_goal_side_clear_count"] == 0
    assert summary["trace_summaries"][0]["near_clear_count"] == 1
    assert summary["trace_summaries"][0]["feasibility_class"] == "near_clear"
