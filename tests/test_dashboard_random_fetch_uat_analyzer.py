from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import dashboard_random_fetch_uat_analyzer as analyzer  # noqa: E402
from llm_supervisor_core import read_json  # noqa: E402
from llm_supervisor_core import write_json  # noqa: E402


def _write_verdict(path: Path, *, flags: list[str], stable: bool = False, passed: bool = True) -> None:
    write_json(
        path,
        {
            "pass": passed,
            "random_profile": "local_visual_v1",
            "target_layout_json": str(path.parent / "layout.json"),
            "approach_contact_metrics": {
                "flags": flags,
                "stable_contact_approach_pass": stable,
            },
            "shot_outcome": {
                "reason": "trajectory_intersects_delivery_radius" if passed else "missed_delivery_radius",
                "closest_approach_distance_m": 0.12 if passed else 0.44,
                "distance_to_fetch_pose_m": 0.12 if passed else 0.44,
            },
            "random_draw": {
                "seed": 123,
                "random_profile": "local_visual_v1",
                "ball_target_distance_m": 0.55,
                "ball_target_angle_deg": 10.0,
                "robot_lateral_offset_m": 0.07,
                "robot_yaw_error_deg": -2.5,
                "robot_ball_separation_m": 0.32,
            },
        },
    )


def test_dashboard_random_fetch_uat_analyzer_flags_passes_as_stage_supervision_signal(tmp_path, monkeypatch):
    monkeypatch.setattr(analyzer, "REPO_ROOT", tmp_path)
    run_root = tmp_path / "artifacts" / "session" / "run1" / "golf_ball_circle_delivery_random" / "sample"
    run_root.mkdir(parents=True)
    verdict_path = run_root / "mission_verdict.json"
    _write_verdict(
        verdict_path,
        flags=["pre_contact_lateral_error", "ball_lateral_knock_away", "contact_trajectory_angle_error"],
    )

    summary = analyzer.summarize_runs(campaign_id="uat_summary", artifacts=[str(run_root)])

    assert summary["pass"] is True
    assert summary["promotion_evidence"] is False
    assert summary["flagged_contact_pass_count"] == 1
    assert summary["interpretation"] == "delivery_passed_with_contact_quality_flags_stage_supervision_needed"
    run = summary["runs"][0]
    assert run["stage_labels"] == ["setup", "first_contact", "push_coast"]
    assert run["seed"] == 123
    assert run["target_layout_json"].endswith("layout.json")
    summary_path = tmp_path / "artifacts" / "session" / "uat_summary" / analyzer.ANALYZER_KIND / "random_fetch_uat_summary.json"
    scorecard_path = summary_path.with_name("scorecard.md")
    assert read_json(summary_path)["interpretation"] == summary["interpretation"]
    assert "promotion_evidence: `False`" in scorecard_path.read_text(encoding="utf-8")


def test_dashboard_random_fetch_uat_analyzer_classifies_clean_and_failed_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(analyzer, "REPO_ROOT", tmp_path)
    clean_root = tmp_path / "clean"
    fail_root = tmp_path / "failed"
    clean_root.mkdir()
    fail_root.mkdir()
    _write_verdict(clean_root / "mission_verdict.json", flags=[], stable=True, passed=True)
    _write_verdict(fail_root / "mission_verdict.json", flags=[], stable=False, passed=False)

    clean_summary = analyzer.summarize_runs(campaign_id="clean", artifacts=[str(clean_root / "mission_verdict.json")])
    failed_summary = analyzer.summarize_runs(campaign_id="failed", artifacts=[str(fail_root / "mission_verdict.json")])

    assert clean_summary["interpretation"] == "clean_visual_delivery_no_new_stage_supervision_signal"
    assert clean_summary["runs"][0]["stage_labels"] == ["clean_contact"]
    assert failed_summary["pass"] is False
    assert failed_summary["interpretation"] == "visual_uat_failures_controller_stage_backlog_not_promotion_evidence"
    assert failed_summary["runs"][0]["stage_labels"] == ["terminal_arrival"]
