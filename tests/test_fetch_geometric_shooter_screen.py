import json
import math
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_geometric_shooter_screen as screen  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def test_geometric_shot_model_scores_delivery_speed_window():
    model = screen.build_geometric_shot_model(
        ball_start_pose={"x": 0.38, "y": 0.0, "z": 0.021336},
        fetch_pose_world={"x": 0.95, "y": 0.0, "z": 0.001, "radius_m": 0.3},
        decel_mps2=0.72,
        max_shot_speed_mps=1.0,
    )

    assert model["offline_pass"] is True
    assert model["ball_to_target_distance_m"] == pytest.approx(0.57)
    assert model["entry_distance_m"] == pytest.approx(0.27)
    assert model["required_entry_speed_mps"] == pytest.approx(math.sqrt(2.0 * 0.72 * 0.27))
    assert model["required_target_center_speed_mps"] == pytest.approx(math.sqrt(2.0 * 0.72 * 0.57))
    assert model["center_stop_possible_with_cap"] is True
    assert model["full_cap_stops_before_far_edge"] is True


def test_analyzer_reads_state_history_fetch_traces_and_stays_offline_only(tmp_path: Path):
    mission_root = tmp_path / "session" / "run1"
    verdict_path = mission_root / "mission_verdict.json"
    state_history_path = mission_root / "state_history.jsonl"
    repeatability_path = tmp_path / "repeatability" / "campaign_run_summary.json"
    gate_path = tmp_path / "gate" / "gate_summary.json"
    shot_outcome = {
        "pass": True,
        "reason": "trajectory_intersects_delivery_radius",
        "closest_approach_distance_m": 0.18,
        "delivery_radius_m": 0.3,
        "fetch_ball_displacement_m": 0.39,
        "fetch_max_commanded_linear_x_mps": 0.08,
        "fetch_pose_world": {"x": 0.95, "y": 0.0, "z": 0.001, "radius_m": 0.3},
        "ball_start_pose": {"x": 0.38, "y": 0.0, "z": 0.021336},
        "ball_end_pose": {"x": 0.77, "y": 0.0, "z": 0.021336},
    }
    _write_json(
        verdict_path,
        {
            "pass": True,
            "mission_completed_pass": True,
            "fetch_to_pose_pass": True,
            "shot_outcome": shot_outcome,
        },
    )
    _write_jsonl(
        state_history_path,
        [
            {
                "phase": "fetch_to_pose",
                "event_type": "fetch_to_pose_tick",
                "fetch_to_pose": {"elapsed_s": 0.0},
                "ball_pose": {"x": 0.38, "y": 0.0, "z": 0.021336},
            },
            {
                "phase": "fetch_to_pose",
                "event_type": "fetch_to_pose_tick",
                "fetch_to_pose": {"elapsed_s": 1.0},
                "ball_pose": {"x": 0.77, "y": 0.0, "z": 0.021336},
            },
        ],
    )
    _write_json(
        repeatability_path,
        {
            "runs": [
                {
                    "run_index": 1,
                    "pass": True,
                    "mission_completed_pass": True,
                    "fetch_to_pose_pass": True,
                    "mission_verdict_path": str(verdict_path),
                    "shot_outcome": shot_outcome,
                    "latest_approach_progress": {
                        "capture_entry": {
                            "pass": True,
                            "first_contact_push_alignment_deg": 2.5,
                        }
                    },
                }
            ]
        },
    )
    _write_json(
        gate_path,
        {
            "pass": True,
            "surface_profile": "calibrated_golf_turf",
            "world_file": "yolo_test_world_v6_calibrated_golf_turf.world",
            "fetch_pose_world": {"x": 0.95, "y": 0.0, "z": 0.001, "radius_m": 0.3},
            "results": [
                {
                    "gate_id": "policy_centerline",
                    "label": "Policy centerline",
                    "summary_path": str(repeatability_path),
                }
            ],
        },
    )

    summary = screen.analyze_gate_summary(campaign_id="test-screen", baseline_gate_summary_path=gate_path)

    assert summary["promotion_allowed"] is False
    assert summary["promotion_status"] == "offline_only_not_uat"
    assert summary["recommendation"] == "run_canonical_zero_one_run_probe"
    assert summary["run_count"] == 1
    assert summary["offline_model_pass_count"] == 1
    run = summary["runs"][0]
    assert run["trace_source"] == "state_history_fetch_to_pose"
    assert run["trace_status"] == "ok"
    assert run["baseline"]["observed_peak_ball_speed_mps"] == pytest.approx(0.39)
    assert run["approach_evidence"]["evidence_source"] == "summary_only"


def test_analyzer_blocks_recommendation_when_speed_cap_cannot_reach_delivery(tmp_path: Path):
    mission_root = tmp_path / "session" / "run1"
    verdict_path = mission_root / "mission_verdict.json"
    repeatability_path = tmp_path / "repeatability" / "campaign_run_summary.json"
    gate_path = tmp_path / "gate" / "gate_summary.json"
    shot_outcome = {
        "pass": False,
        "closest_approach_distance_m": 0.6,
        "delivery_radius_m": 0.3,
        "fetch_pose_world": {"x": 0.95, "y": 0.0, "z": 0.001, "radius_m": 0.3},
        "ball_start_pose": {"x": 0.38, "y": 0.0, "z": 0.021336},
    }
    _write_json(verdict_path, {"pass": False, "mission_completed_pass": False, "shot_outcome": shot_outcome})
    _write_json(
        repeatability_path,
        {
            "runs": [
                {
                    "run_index": 1,
                    "pass": False,
                    "mission_verdict_path": str(verdict_path),
                    "shot_outcome": shot_outcome,
                }
            ]
        },
    )
    _write_json(
        gate_path,
        {
            "pass": False,
            "fetch_pose_world": {"x": 0.95, "y": 0.0, "z": 0.001, "radius_m": 0.3},
            "results": [{"gate_id": "policy_centerline", "summary_path": str(repeatability_path)}],
        },
    )

    summary = screen.analyze_gate_summary(
        campaign_id="test-screen",
        baseline_gate_summary_path=gate_path,
        max_shot_speed_mps=0.2,
    )

    assert summary["offline_model_pass_count"] == 0
    assert summary["recommendation"] == "keep_as_offline_hypothesis"
    assert summary["runs"][0]["geometric_shooter"]["reason"] == "speed_or_aim_window_blocked"
