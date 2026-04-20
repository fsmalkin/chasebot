from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_escape_divergence_audit as divergence  # noqa: E402
import gather_escape_feasibility_audit as feasibility  # noqa: E402
import gather_escape_oracle as oracle  # noqa: E402
import gather_escape_sandbox as sandbox  # noqa: E402
from gather_mission_helpers import build_zone_spec  # noqa: E402


ZONE = build_zone_spec("corral_single_ball_place")
BALL_POSE = {"x": 4.555261, "y": 2.155261, "z": 0.05}
CONTROLLER_SHAPE_LOCAL = {"x": 0.31361758022929265, "y": 0.25607254243872984, "yaw": -2.3296093313272754}
GOAL_SIDE_ONLY_LOCAL = {"x": 0.023141687334822705, "y": 1.3629109105513886, "yaw": -0.8439014238462192}


def _quat_from_yaw(yaw_rad: float) -> dict[str, float]:
    half = yaw_rad / 2.0
    return {"x": 0.0, "y": 0.0, "z": math.sin(half), "w": math.cos(half)}


def _world_pose_from_local(local_pose: dict[str, float], ball_pose: dict[str, float] | None = None) -> dict[str, float]:
    world_pose = sandbox.local_pose_to_world(local_pose, ball_pose or BALL_POSE, zone=ZONE)
    assert world_pose is not None
    return world_pose


def _truth_sample(t_s: float, local_pose: dict[str, float], *, ball_pose: dict[str, float] | None = None) -> dict[str, object]:
    resolved_ball_pose = ball_pose or BALL_POSE
    robot_world = _world_pose_from_local(local_pose, resolved_ball_pose)
    return {
        "t_s": t_s,
        "robot_truth_pose": {
            "name": "jetbot",
            "position": {"x": robot_world["x"], "y": robot_world["y"], "z": 0.0},
            "orientation": _quat_from_yaw(robot_world["yaw"]),
        },
        "true_target_pose": {
            "name": "ball_1",
            "position": {"x": resolved_ball_pose["x"], "y": resolved_ball_pose["y"], "z": resolved_ball_pose.get("z", 0.05)},
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        },
    }


def _state_row(
    index: int,
    local_pose: dict[str, float],
    *,
    angular_z: float = 0.0,
    linear_x: float = -0.18,
    mode: str = "pre_stage_escape_goal_side",
    yaw_error_deg: float = 30.0,
    ball_pose: dict[str, float] | None = None,
) -> dict[str, object]:
    resolved_ball_pose = ball_pose or BALL_POSE
    robot_world = _world_pose_from_local(local_pose, resolved_ball_pose)
    return {
        "generated_utc": f"2026-04-19T22:00:{index:02d}+00:00",
        "phase": "pre_stage",
        "attempt": 0,
        "fixture_index": index,
        "robot_pose": robot_world,
        "ball_pose": dict(resolved_ball_pose),
        "robot_pose_local": dict(local_pose),
        "pre_stage": {
            "yaw_error_deg": yaw_error_deg,
            "robot_longitudinal_projection_m": local_pose["x"],
            "robot_lateral_signed_m": local_pose["y"],
            "robot_lateral_error_m": abs(local_pose["y"]),
        },
        "selected_command": {
            "angular_z": angular_z,
            "linear_x": linear_x,
            "mode": mode,
        },
        "manager_directive": "recover_goal_side",
        "controller_family": "short_horizon_v2",
        "strategy_name": "synthetic",
        "objective_name": "synthetic",
        "progress_score": 0.0,
        "stall_s": 0.0,
        "projected_projection_gain": 0.0,
        "projected_lateral_gain": 0.0,
        "projected_distance_gain": 0.0,
    }


def _write_state_history(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def test_representative_fixture_extraction_matches_oracle_path(tmp_path: Path):
    rows = []
    for index in range(8):
        rows.append(
            _state_row(
                index,
                GOAL_SIDE_ONLY_LOCAL,
                angular_z=-0.4,
                yaw_error_deg=90.0 - (index * 12.0),
            )
        )
    state_history_path = tmp_path / "state_history.jsonl"
    _write_state_history(state_history_path, rows)

    oracle_rows = oracle.load_pre_stage_attempt_rows(state_history_path, attempt=0)
    expected = oracle.select_representative_fixture_rows(oracle_rows)
    actual = divergence.extract_representative_fixtures(state_history_path)

    assert [(item["fixture_label"], item["fixture_index"]) for item in actual] == [
        (item["fixture_label"], item["fixture_index"]) for item in expected
    ]
    assert all("robot_pose_local" in item for item in actual)


def test_alignment_uses_utc_anchor_when_available():
    fixture_row = _state_row(2, GOAL_SIDE_ONLY_LOCAL, angular_z=0.4)
    truth_samples = [
        _truth_sample(1.0, GOAL_SIDE_ONLY_LOCAL),
        _truth_sample(2.0, GOAL_SIDE_ONLY_LOCAL),
        _truth_sample(3.0, GOAL_SIDE_ONLY_LOCAL),
    ]
    timeline_payload = {
        "events": [
            {
                "event_type": "feedback_observed",
                "timestamp_utc": "2026-04-19T22:00:00+00:00",
                "t_s": 1.0,
            }
        ]
    }

    anchor = divergence.extract_timeline_utc_anchor(timeline_payload, [])
    assert anchor is not None

    alignment = divergence.align_fixture_to_truth_sample(fixture_row, truth_samples, timeline_anchor=anchor)
    assert alignment["source"] == "timeline_json_event"
    assert alignment["matched_truth_t_s"] == pytest.approx(3.0, abs=1.0e-6)
    assert alignment["quality"] == "good"


def test_alignment_falls_back_to_pose_when_utc_anchor_is_missing():
    fixture_row = _state_row(4, GOAL_SIDE_ONLY_LOCAL, angular_z=0.4)
    truth_samples = [
        _truth_sample(5.0, GOAL_SIDE_ONLY_LOCAL),
        _truth_sample(6.0, {"x": GOAL_SIDE_ONLY_LOCAL["x"] + 0.1, "y": GOAL_SIDE_ONLY_LOCAL["y"], "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"]}),
    ]

    alignment = divergence.align_fixture_to_truth_sample(fixture_row, truth_samples, timeline_anchor=None)
    assert alignment["source"] == "pose_fallback"
    assert alignment["matched_truth_t_s"] == pytest.approx(5.0, abs=1.0e-6)
    assert alignment["quality"] == "good"


def test_compute_metrics_flags_turn_realization_limited():
    state_rows = [
        _state_row(index, GOAL_SIDE_ONLY_LOCAL, angular_z=1.0, mode="turn_commit")
        for index in range(5)
    ]
    fixture = dict(state_rows[0])
    fixture["fixture_label"] = "first_post_yaw_gate"
    fixture["fixture_index"] = 0
    truth_samples = [
        _truth_sample(1.0, GOAL_SIDE_ONLY_LOCAL),
        _truth_sample(2.0, {"x": GOAL_SIDE_ONLY_LOCAL["x"] - 0.02, "y": GOAL_SIDE_ONLY_LOCAL["y"], "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.05}),
        _truth_sample(3.0, {"x": GOAL_SIDE_ONLY_LOCAL["x"] - 0.03, "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.01, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.10}),
        _truth_sample(4.0, {"x": GOAL_SIDE_ONLY_LOCAL["x"] - 0.05, "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.02, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.15}),
        _truth_sample(5.0, {"x": GOAL_SIDE_ONLY_LOCAL["x"] - 0.06, "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.03, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.20}),
    ]
    timeline_anchor = {"source": "timeline_json_event", "timestamp_utc": "2026-04-19T22:00:00+00:00", "t_s": 1.0}

    payload = divergence.compute_fixture_metrics(
        fixture,
        state_rows=state_rows,
        truth_samples=truth_samples,
        timeline_anchor=timeline_anchor,
    )

    assert payload["fixture_blocker"] == "turn_realization_limited"
    assert payload["classifier_flags"]["turn_realization_limited"] is True
    assert payload["classifier_flags"]["contact_geometry_limited"] is False
    assert payload["derived_metrics"]["yaw_realization_ratio"] is not None
    assert payload["derived_metrics"]["yaw_realization_ratio"] < 0.70


def test_compute_metrics_flags_contact_geometry_limited():
    shifted_ball_1 = {"x": BALL_POSE["x"] + 0.04, "y": BALL_POSE["y"], "z": BALL_POSE["z"]}
    shifted_ball_2 = {"x": BALL_POSE["x"] + 0.06, "y": BALL_POSE["y"] + 0.01, "z": BALL_POSE["z"]}
    state_rows = [
        _state_row(index, CONTROLLER_SHAPE_LOCAL, angular_z=0.25, mode="arc_hold")
        for index in range(4)
    ]
    fixture = dict(state_rows[0])
    fixture["fixture_label"] = "early_stall"
    fixture["fixture_index"] = 0
    truth_samples = [
        _truth_sample(1.0, CONTROLLER_SHAPE_LOCAL),
        _truth_sample(2.0, {"x": CONTROLLER_SHAPE_LOCAL["x"] - 0.01, "y": CONTROLLER_SHAPE_LOCAL["y"] - 0.01, "yaw": CONTROLLER_SHAPE_LOCAL["yaw"] + 0.40}, ball_pose=shifted_ball_1),
        _truth_sample(3.0, {"x": CONTROLLER_SHAPE_LOCAL["x"] - 0.02, "y": CONTROLLER_SHAPE_LOCAL["y"] - 0.01, "yaw": CONTROLLER_SHAPE_LOCAL["yaw"] + 0.80}, ball_pose=shifted_ball_2),
        _truth_sample(4.0, {"x": CONTROLLER_SHAPE_LOCAL["x"] - 0.02, "y": CONTROLLER_SHAPE_LOCAL["y"] - 0.02, "yaw": CONTROLLER_SHAPE_LOCAL["yaw"] + 1.00}, ball_pose=shifted_ball_2),
    ]
    timeline_anchor = {"source": "timeline_json_event", "timestamp_utc": "2026-04-19T22:00:00+00:00", "t_s": 1.0}

    payload = divergence.compute_fixture_metrics(
        fixture,
        state_rows=state_rows,
        truth_samples=truth_samples,
        timeline_anchor=timeline_anchor,
    )

    assert payload["fixture_blocker"] == "contact_geometry_limited"
    assert payload["classifier_flags"]["turn_realization_limited"] is False
    assert payload["classifier_flags"]["contact_geometry_limited"] is True
    assert payload["classifier_flags"]["early_interference"] is True
    assert payload["realized_metrics"]["ball_motion_magnitude_m"] > 0.03


def test_compute_metrics_flags_control_timing_limited():
    commands = [
        (0.5, "mode_a"),
        (-0.5, "mode_b"),
        (0.5, "mode_c"),
        (-0.5, "mode_d"),
        (0.5, "mode_e"),
    ]
    state_rows = [
        _state_row(index, GOAL_SIDE_ONLY_LOCAL, angular_z=angular_z, mode=mode)
        for index, (angular_z, mode) in enumerate(commands)
    ]
    fixture = dict(state_rows[0])
    fixture["fixture_label"] = "mid_stall"
    fixture["fixture_index"] = 0
    truth_samples = [
        _truth_sample(1.0, GOAL_SIDE_ONLY_LOCAL),
        _truth_sample(2.0, {"x": GOAL_SIDE_ONLY_LOCAL["x"] - 0.02, "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.01, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.35}),
        _truth_sample(3.0, {"x": GOAL_SIDE_ONLY_LOCAL["x"] - 0.03, "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.02, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.70}),
        _truth_sample(4.0, {"x": GOAL_SIDE_ONLY_LOCAL["x"] - 0.04, "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.03, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 1.05}),
        _truth_sample(5.0, {"x": GOAL_SIDE_ONLY_LOCAL["x"] - 0.05, "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.04, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 1.40}),
    ]
    timeline_anchor = {"source": "timeline_json_event", "timestamp_utc": "2026-04-19T22:00:00+00:00", "t_s": 1.0}

    payload = divergence.compute_fixture_metrics(
        fixture,
        state_rows=state_rows,
        truth_samples=truth_samples,
        timeline_anchor=timeline_anchor,
    )

    assert payload["fixture_blocker"] == "control_timing_limited"
    assert payload["classifier_flags"]["turn_realization_limited"] is False
    assert payload["classifier_flags"]["control_timing_limited"] is True
    assert payload["derived_metrics"]["combined_flip_count_before_projection_gain"] > 2
    assert payload["classifier_flags"]["ball_effectively_static"] is True


def test_world_model_mismatch_is_used_when_no_blocker_dominates():
    fixture_payloads = [
        {"classifier_flags": {"poor_alignment": False, "turn_realization_limited": True, "turn_realization_ratio_below_threshold": True, "wrong_sign_yaw": False, "contact_geometry_limited": False, "control_timing_limited": False}},
        {"classifier_flags": {"poor_alignment": False, "turn_realization_limited": True, "turn_realization_ratio_below_threshold": False, "wrong_sign_yaw": True, "contact_geometry_limited": False, "control_timing_limited": False}},
        {"classifier_flags": {"poor_alignment": False, "turn_realization_limited": False, "turn_realization_ratio_below_threshold": False, "wrong_sign_yaw": False, "contact_geometry_limited": True, "control_timing_limited": False}},
        {"classifier_flags": {"poor_alignment": False, "turn_realization_limited": False, "turn_realization_ratio_below_threshold": False, "wrong_sign_yaw": False, "contact_geometry_limited": False, "control_timing_limited": True}},
        {"classifier_flags": {"poor_alignment": False, "turn_realization_limited": False, "turn_realization_ratio_below_threshold": False, "wrong_sign_yaw": False, "contact_geometry_limited": False, "control_timing_limited": False}},
    ]

    decision = divergence.decide_dominant_blocker(fixture_payloads)

    assert decision["dominant_blocker"] == "world_model_mismatch_unresolved"
    assert decision["live_probe_required"] is True
    assert decision["dominant_coverage_count"] == 2


def test_build_divergence_bundle_from_temp_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(divergence, "REPO_ROOT", tmp_path)

    session_id = "session_divergence_temp"
    mission_root = tmp_path / "artifacts" / "session" / session_id / "gather_mission" / "20260419T220438Z"
    visual_root = tmp_path / "artifacts" / "session" / session_id / "visual"
    mission_root.mkdir(parents=True, exist_ok=True)
    visual_root.mkdir(parents=True, exist_ok=True)

    state_rows = [
        _state_row(index, GOAL_SIDE_ONLY_LOCAL, angular_z=0.5 if index < 3 else -0.5, mode=f"mode_{index}")
        for index in range(5)
    ]
    _write_state_history(mission_root / "state_history.jsonl", state_rows)

    truth_samples = [
        _truth_sample(1.0, GOAL_SIDE_ONLY_LOCAL),
        _truth_sample(2.0, {"x": GOAL_SIDE_ONLY_LOCAL["x"] - 0.02, "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.01, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.40}),
        _truth_sample(3.0, {"x": GOAL_SIDE_ONLY_LOCAL["x"] - 0.03, "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.02, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.75}),
        _truth_sample(4.0, {"x": GOAL_SIDE_ONLY_LOCAL["x"] - 0.04, "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.03, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 1.10}),
        _truth_sample(5.0, {"x": GOAL_SIDE_ONLY_LOCAL["x"] - 0.05, "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.04, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 1.45}),
    ]
    (visual_root / "truth_timeline.json").write_text(json.dumps(truth_samples, indent=2), encoding="utf-8")
    timeline_payload = {
        "samples": [{"t_s": item["t_s"]} for item in truth_samples],
        "events": [
            {
                "event_type": "feedback_observed",
                "timestamp_utc": "2026-04-19T22:00:00+00:00",
                "t_s": 1.0,
            }
        ],
    }
    (visual_root / "timeline.json").write_text(json.dumps(timeline_payload, indent=2), encoding="utf-8")
    (visual_root / "timeline_events.jsonl").write_text("", encoding="utf-8")
    (mission_root / "mission_verdict.json").write_text(
        json.dumps({"pre_stage_handoff_pass": False, "approach_failure_reason": "pre_stage_timeout"}, indent=2),
        encoding="utf-8",
    )
    (mission_root / "gather_sequence.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"event_type": "route_planned", "timestamp_utc": "2026-04-19T22:00:00+00:00"}),
                json.dumps({"event_type": "pre_stage_result", "timestamp_utc": "2026-04-19T22:00:05+00:00", "status": "pre_stage_timeout"}),
            ]
        ),
        encoding="utf-8",
    )

    campaign_summary = {
        "campaign_id": "temp_source_campaign",
        "runs": [
            {
                "run_index": 0,
                "session_id": session_id,
                "mission_root": str(mission_root),
            }
        ],
    }
    campaign_summary_path = tmp_path / "campaign_run_summary.json"
    campaign_summary_path.write_text(json.dumps(campaign_summary, indent=2), encoding="utf-8")

    summary, fixture_payloads = divergence.build_divergence_audit_bundle(
        campaign_id="temp_divergence_audit",
        campaign_summary_path=campaign_summary_path,
        run_index=0,
    )

    assert summary["type"] == "gather_escape_divergence_audit"
    assert summary["source_campaign_id"] == "temp_source_campaign"
    assert summary["representative_fixture_count"] == 5
    assert set(fixture_payloads.keys()) == {
        "first_post_yaw_gate",
        "early_stall",
        "mid_stall",
        "late_stall",
        "terminal_stall",
    }
    assert summary["run_context"]["mission_verdict"]["approach_failure_reason"] == "pre_stage_timeout"
    assert summary["alignment_source"] == "timeline_json_event"
    assert "nominal_current" in summary["offline_vs_live_delta_metrics"]
    assert "combined_relaxed" in summary["offline_vs_live_delta_metrics"]
