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
import gather_turn_realization_audit as audit  # noqa: E402
import gather_escape_sandbox as sandbox  # noqa: E402
from gather_mission_helpers import build_zone_spec  # noqa: E402


ZONE = build_zone_spec("corral_single_ball_place")
BALL_POSE = {"x": 4.555261, "y": 2.155261, "z": 0.05}
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
    angular_z: float = 0.45,
    linear_x: float = -0.18,
    mode: str = "pre_stage_escape_goal_side",
    controller_family: str = "short_horizon_v2",
) -> dict[str, object]:
    robot_world = _world_pose_from_local(local_pose, BALL_POSE)
    return {
        "generated_utc": f"2026-04-19T22:00:{index:02d}+00:00",
        "phase": "pre_stage",
        "attempt": 0,
        "fixture_index": index,
        "robot_pose": robot_world,
        "ball_pose": dict(BALL_POSE),
        "robot_pose_local": dict(local_pose),
        "pre_stage": {
            "yaw_error_deg": 30.0,
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
        "controller_family": controller_family,
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


def test_decide_dominant_gap_prefers_strategy_authority():
    payloads = [
        {"classifier_flags": {"strategy_authority_limited": True, "sign_parity_limited": False, "plant_realization_limited": False}}
        for _ in range(5)
    ]
    decision = audit.decide_dominant_gap(payloads)
    assert decision["dominant_gap"] == "strategy_authority_limited"
    assert decision["dominant_coverage_count"] == 5


def test_decide_dominant_gap_prefers_sign_parity_after_strategy():
    payloads = [
        {"classifier_flags": {"strategy_authority_limited": False, "sign_parity_limited": True, "plant_realization_limited": False}}
        for _ in range(3)
    ] + [
        {"classifier_flags": {"strategy_authority_limited": False, "sign_parity_limited": False, "plant_realization_limited": False}}
        for _ in range(2)
    ]
    decision = audit.decide_dominant_gap(payloads)
    assert decision["dominant_gap"] == "sign_parity_limited"
    assert decision["dominant_coverage_count"] == 3


def test_decide_dominant_gap_prefers_plant_realization_after_sign():
    payloads = [
        {"classifier_flags": {"strategy_authority_limited": False, "sign_parity_limited": False, "plant_realization_limited": True}}
        for _ in range(4)
    ] + [
        {"classifier_flags": {"strategy_authority_limited": False, "sign_parity_limited": False, "plant_realization_limited": False}}
    ]
    decision = audit.decide_dominant_gap(payloads)
    assert decision["dominant_gap"] == "plant_realization_limited"
    assert decision["confidence"] == "high"


def test_decide_dominant_gap_falls_back_to_mixed():
    payloads = [
        {"classifier_flags": {"strategy_authority_limited": True, "sign_parity_limited": False, "plant_realization_limited": False}},
        {"classifier_flags": {"strategy_authority_limited": False, "sign_parity_limited": True, "plant_realization_limited": False}},
        {"classifier_flags": {"strategy_authority_limited": False, "sign_parity_limited": False, "plant_realization_limited": True}},
        {"classifier_flags": {"strategy_authority_limited": False, "sign_parity_limited": False, "plant_realization_limited": False}},
        {"classifier_flags": {"strategy_authority_limited": False, "sign_parity_limited": False, "plant_realization_limited": False}},
    ]
    decision = audit.decide_dominant_gap(payloads)
    assert decision["dominant_gap"] == "mixed_turn_contract_limited"
    assert decision["dominant_coverage_count"] == 1


def test_build_turn_realization_bundle_from_temp_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(divergence, "REPO_ROOT", tmp_path)

    session_id = "session_turn_realization_temp"
    mission_root = tmp_path / "artifacts" / "session" / session_id / "gather_mission" / "20260419T220438Z"
    visual_root = tmp_path / "artifacts" / "session" / session_id / "visual"
    mission_root.mkdir(parents=True, exist_ok=True)
    visual_root.mkdir(parents=True, exist_ok=True)

    state_rows = [
        _state_row(index, GOAL_SIDE_ONLY_LOCAL, angular_z=0.45, mode=f"mode_{index}")
        for index in range(5)
    ]
    _write_state_history(mission_root / "state_history.jsonl", state_rows)

    truth_samples = [
        _truth_sample(1.0, GOAL_SIDE_ONLY_LOCAL),
        _truth_sample(2.0, {"x": GOAL_SIDE_ONLY_LOCAL["x"] - 0.01, "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.01, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.15}),
        _truth_sample(3.0, {"x": GOAL_SIDE_ONLY_LOCAL["x"] - 0.02, "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.02, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.30}),
        _truth_sample(4.0, {"x": GOAL_SIDE_ONLY_LOCAL["x"] - 0.03, "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.03, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.45}),
        _truth_sample(5.0, {"x": GOAL_SIDE_ONLY_LOCAL["x"] - 0.04, "y": GOAL_SIDE_ONLY_LOCAL["y"] - 0.04, "yaw": GOAL_SIDE_ONLY_LOCAL["yaw"] + 0.60}),
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
        "campaign_id": "temp_turn_realization_source",
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

    summary, fixture_payloads = audit.build_turn_realization_audit_bundle(
        campaign_id="temp_turn_realization_audit",
        campaign_summary_path=campaign_summary_path,
        run_index=0,
    )

    assert summary["type"] == "gather_turn_realization_audit"
    assert summary["source_campaign_id"] == "temp_turn_realization_source"
    assert summary["representative_fixture_count"] == 5
    assert summary["dominant_gap"] == "strategy_authority_limited"
    assert summary["dominant_gap_fixture_count"] == 5
    assert set(fixture_payloads.keys()) == {
        "first_post_yaw_gate",
        "early_stall",
        "mid_stall",
        "late_stall",
        "terminal_stall",
    }
    first_fixture = fixture_payloads["first_post_yaw_gate"]
    assert first_fixture["turn_limit_surfaces"]["active_helper_surface"] == "short_horizon_helper_abs_angular_cap_radps"
    assert first_fixture["command_metrics"]["peak_requested_angular_z_radps"] == pytest.approx(0.45, abs=1.0e-6)
    assert first_fixture["offline_turn_baseline"]["family_name"] != ""
