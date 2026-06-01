from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_seeded_gate_evidence_analyzer as analyzer  # noqa: E402
from llm_supervisor_core import read_json  # noqa: E402
from llm_supervisor_core import write_json  # noqa: E402


def _summary_with_ai(*, passed: bool, reason: str = "", stage_labels: list[str] | None = None) -> dict:
    return {
        "promotion_gate_pass": passed,
        "model_provenance_valid": True,
        "model_provenance_reason": "calibrated_fetch_models",
        "target_model_classification": "calibrated_golf_ball",
        "zone_model_classification": "golf_ball_delivery_zone_marker",
        "target_model_radius_m": 0.021336,
        "fetch_to_pose_failure_reasons": [reason] if reason else [],
        "runs": [
            {
                "fetch_to_pose_failure_reason": reason,
                "shot_outcome": {
                    "reason": reason or "trajectory_intersects_delivery_radius",
                    "closest_approach_distance_m": 0.42 if reason else 0.12,
                    "distance_to_fetch_pose_m": 0.42 if reason else 0.12,
                    "ai_push_coast_mode": "shadow",
                    "ai_push_coast_shadow": {
                        "stage_classification": {
                            "primary_stage": (stage_labels or ["terminal_arrival"])[0],
                            "stage_labels": stage_labels or ["terminal_arrival"],
                        }
                    },
                    "ai_push_coast_proposal": {
                        "maneuver_class": "terminal_repush" if reason else "coast_accept",
                    },
                    "ai_push_coast_guard": {
                        "accepted": False,
                        "reasons": ["shadow_mode"],
                    },
                },
            }
        ],
    }


def test_seeded_gate_analyzer_classifies_pass_non_repro_and_reproduced_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(analyzer, "REPO_ROOT", tmp_path)
    gate_path = tmp_path / "gate_summary.json"
    frozen_layout = tmp_path / "frozen_case.json"
    gate_summary = {
        "campaign_id": "seeded_gate",
        "seed": 20260529,
        "ai_push_coast_mode": "shadow",
        "fetch_delivery_radius_m": 0.3,
        "pass": False,
        "pass_count": 1,
        "fail_count": 2,
        "results": [
            {
                "architecture": "ai_push_coast_servo_v1",
                "case_id": "case01",
                "layout_path": "layout01.json",
                "summary_path": "summary01.json",
                "pass": True,
                "return_code": 0,
                "summary": _summary_with_ai(passed=True),
            },
            {
                "architecture": "ai_push_coast_servo_v1",
                "case_id": "case02",
                "layout_path": "layout02.json",
                "summary_path": "summary02.json",
                "pass": False,
                "return_code": 2,
                "reproduced_failure": False,
                "repro": {"pass": True},
                "summary": _summary_with_ai(
                    passed=False,
                    reason="capture_entry_timeout",
                    stage_labels=["setup"],
                ),
            },
            {
                "architecture": "ai_push_coast_servo_v1",
                "case_id": "case03",
                "layout_path": "layout03.json",
                "summary_path": "summary03.json",
                "pass": False,
                "return_code": 2,
                "reproduced_failure": True,
                "frozen_failure_layout": str(frozen_layout),
                "repro": {"pass": False},
                "summary": _summary_with_ai(
                    passed=False,
                    reason="missed_delivery_radius_after_fetch_to_pose_ball_stopped_short",
                    stage_labels=["terminal_arrival"],
                ),
            },
        ],
    }
    write_json(gate_path, gate_summary)

    summary = analyzer.summarize_evidence(campaign_id="evidence", gate_summary_path=str(gate_path))

    assert summary["seeded_gate"]["pass_count"] == 1
    assert summary["seeded_gate"]["fail_count"] == 2
    assert summary["seeded_gate"]["non_repro_failure_count"] == 1
    assert summary["seeded_gate"]["reproduced_failure_count"] == 1
    assert summary["recommended_next_action"] == "freeze_reproduced_failures_before_tuning"
    cases = {case["case_id"]: case for case in summary["seeded_gate"]["cases"]}
    assert cases["case01"]["interpretation"] == "shadow_pass"
    assert cases["case02"]["interpretation"] == "non_repro_setup_capture_watchlist"
    assert cases["case02"]["repro_pass"] is True
    assert cases["case03"]["interpretation"] == "promotion_blocker_reproduced_failure"
    assert cases["case03"]["frozen_failure_layout"] == str(frozen_layout)
    assert cases["case03"]["ai_push_coast_proposal"]["maneuver_class"] == "terminal_repush"
    output_path = tmp_path / "artifacts" / "session" / "evidence" / analyzer.ANALYZER_KIND / "evidence_summary.json"
    assert read_json(output_path)["seeded_gate"]["cases"][1]["stage_labels"] == ["setup"]
    assert output_path.with_name("scorecard.md").exists()


def test_seeded_gate_analyzer_blocks_missing_model_provenance(tmp_path, monkeypatch):
    monkeypatch.setattr(analyzer, "REPO_ROOT", tmp_path)
    gate_path = tmp_path / "gate_summary.json"
    gate_summary = {
        "campaign_id": "seeded_gate",
        "seed": 20260529,
        "ai_push_coast_mode": "shadow",
        "fetch_delivery_radius_m": 0.3,
        "pass": True,
        "pass_count": 1,
        "fail_count": 0,
        "results": [
            {
                "architecture": "ai_push_coast_servo_v1",
                "case_id": "case01",
                "layout_path": "layout01.json",
                "summary_path": "summary01.json",
                "pass": True,
                "return_code": 0,
                "summary": {"promotion_gate_pass": True, "runs": [{"fetch_to_pose_pass": True}]},
            }
        ],
    }
    write_json(gate_path, gate_summary)

    summary = analyzer.summarize_evidence(campaign_id="evidence", gate_summary_path=str(gate_path))

    assert summary["seeded_gate"]["model_provenance_valid"] is False
    assert summary["seeded_gate"]["model_provenance_invalid_count"] == 1
    assert summary["seeded_gate"]["cases"][0]["interpretation"] == "rebuild_required_model_provenance"
    assert summary["recommended_next_action"] == "rerun_seeded_gate_with_calibrated_model_provenance"


def test_seeded_gate_analyzer_builds_milestone_context(tmp_path, monkeypatch):
    monkeypatch.setattr(analyzer, "REPO_ROOT", tmp_path)
    gate_path = tmp_path / "gate_summary.json"
    visual_path = tmp_path / "visual.json"
    saved_path = tmp_path / "saved.json"
    write_json(
        gate_path,
        {
            "campaign_id": "seeded_gate",
            "seed": 20260529,
            "ai_push_coast_mode": "shadow",
            "fetch_delivery_radius_m": 0.3,
            "pass": True,
            "pass_count": 1,
            "fail_count": 0,
            "results": [
                {
                    "architecture": "ai_push_coast_servo_v1",
                    "case_id": "case01",
                    "layout_path": "layout01.json",
                    "summary_path": "summary01.json",
                    "pass": True,
                    "return_code": 0,
                    "summary": _summary_with_ai(passed=True),
                }
            ],
        },
    )
    write_json(
        visual_path,
        {
            "campaign_id": "local_visual",
            "pass_count": 3,
            "fail_count": 0,
            "clean_contact_pass_count": 0,
            "flagged_contact_pass_count": 3,
            "interpretation": "delivery_passed_with_contact_quality_flags_stage_supervision_needed",
            "promotion_evidence": False,
        },
    )
    write_json(
        saved_path,
        {
            "campaign_id": "saved_anchor",
            "baseline_by_layout": {"zero": {}, "left05": {}, "right05": {}},
            "candidate_families": [
                {
                    "family": "nav2_followpath_corridor_push_v1",
                    "promotion_results": [
                        {
                            "family": "nav2_followpath_corridor_push_v1",
                            "layout_id": "right05",
                            "stage": "promotion",
                            "pass": False,
                            "summary_path": "right05_summary.json",
                            "metrics": {
                                "worst_closest_approach_distance_m": 0.451645,
                                "fetch_to_pose_failure_reasons": [
                                    "missed_delivery_radius_after_fetch_to_pose_ball_stopped_short"
                                ],
                            },
                        }
                    ],
                }
            ],
        },
    )

    summary = analyzer.summarize_evidence(
        campaign_id="milestone",
        gate_summary_path=str(gate_path),
        local_visual_summary_path=str(visual_path),
        saved_anchor_summary_path=str(saved_path),
    )

    assert summary["local_visual_uat"]["flagged_contact_pass_count"] == 3
    assert summary["saved_anchor_context"]["baseline_layouts"] == ["left05", "right05", "zero"]
    assert len(summary["saved_anchor_context"]["watchlist_rows"]) == 1
    assert len(summary["saved_anchor_context"]["stop_short_rows"]) == 1
    assert summary["recommended_next_action"] == "run_guarded_live_terminal_probe"
