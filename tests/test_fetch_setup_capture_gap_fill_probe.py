from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_setup_capture_gap_fill_probe as probe  # noqa: E402
from llm_supervisor_core import read_json  # noqa: E402
from llm_supervisor_core import write_json  # noqa: E402


def _args(**overrides):
    values = {
        "campaign_id": "gap",
        "dashboard_url": "http://127.0.0.1:8860",
        "dashboard_base_url": "",
        "dry_run": True,
        "family": [],
        "runs": 1,
        "layout_json": "ros2_config/target_layouts/golf_ball_circle_delivery_right05.json",
        "fetch_delivery_radius_m": 0.3,
        "world_file": "yolo_test_world_v6_calibrated_golf_turf.world",
        "surface_profile": "calibrated_golf_turf",
        "timeout_s": 90.0,
        "scenario_timeout_s": 300.0,
        "provider": "openai",
        "planner_gate_summary": "",
        "object_centric_gate_summary": "",
        "nav2_corridor_summary": "",
        "corrected_direct_summary": [],
        "skip_visual_package": True,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _summary(*, campaign_id: str, passed: bool, reason: str = "") -> dict:
    return {
        "campaign_id": campaign_id,
        "requested_target_layout_json": "ros2_config/target_layouts/golf_ball_circle_delivery_right05.json",
        "model_provenance_valid": True,
        "fetch_to_pose_pass_count": 1 if passed else 0,
        "fetch_to_pose_fail_count": 0 if passed else 1,
        "fetch_to_pose_failure_reasons": [] if passed else [reason],
        "runs": [
            {
                "session_id": f"{campaign_id}_session",
                "fetch_to_pose_pass": passed,
                "fetch_to_pose_failure_reason": reason,
                "capture_entry_reached": passed,
                "capture_entry_time_s": 2.0 if passed else 6.5,
                "pre_stage_handoff_pass": True,
                "model_provenance_valid": True,
                "shot_outcome": {
                    "reason": reason or "trajectory_intersects_delivery_radius",
                    "closest_approach_distance_m": 0.16 if passed else None,
                    "distance_to_fetch_pose_m": 0.16 if passed else None,
                },
            }
        ],
    }


def test_build_probe_specs_uses_fixed_right05_gate_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "REPO_ROOT", tmp_path)
    args = _args(campaign_id="gap", family=["ai_push_coast_servo_v1"])

    specs = probe.build_probe_specs(args, "gap")

    assert len(specs) == 1
    command = specs[0].command
    assert "--execution-mode" in command
    assert command[command.index("--execution-mode") + 1] == "direct"
    assert command[command.index("--mission-objective") + 1] == "fetch_to_pose"
    assert command[command.index("--fetch-delivery-radius-m") + 1] == "0.300000"
    assert command[command.index("--max-retries-per-target") + 1] == "0"
    assert command[command.index("--target-layout-json") + 1].endswith("golf_ball_circle_delivery_right05.json")
    assert command[command.index("--gather-control-family") + 1] == "ai_push_coast_servo_v1"


def test_dry_run_writes_command_scorecard_without_live_execution(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "REPO_ROOT", tmp_path)
    args = _args(campaign_id="gap", dry_run=True)

    summary = probe.run_probe(args)

    assert summary["decision"]["action"] == "dry_run_ready"
    assert len(summary["children"]) == 3
    assert all(child["dry_run"] for child in summary["children"])
    scorecard = tmp_path / "artifacts" / "session" / "gap" / probe.ANALYZER_KIND / "scorecard.md"
    assert scorecard.is_file()
    assert "ai_push_coast_servo_v1" in scorecard.read_text(encoding="utf-8")


def test_live_probe_summary_recommends_port_when_candidate_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(probe.stage_compare, "REPO_ROOT", tmp_path)

    def fake_run(command: list[str], log_path: Path) -> int:
        family = command[command.index("--gather-control-family") + 1]
        campaign_id = command[command.index("--campaign-id") + 1]
        passed = family == "nav2_followpath_corridor_push_v1"
        reason = "" if passed else "capture_entry_timeout"
        write_json(probe._summary_path_for_campaign(campaign_id), _summary(campaign_id=campaign_id, passed=passed, reason=reason))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("fake run\n", encoding="utf-8")
        return 0 if passed else 2

    monkeypatch.setattr(probe, "_run_command", fake_run)
    args = _args(
        campaign_id="gap_live",
        dry_run=False,
        family=["ai_push_coast_servo_v1", "nav2_followpath_corridor_push_v1"],
    )

    summary = probe.run_probe(args)

    assert summary["decision"]["action"] == "port_setup_capture_behavior_from_nav2_followpath_corridor_push_v1"
    assert summary["capture_entry_diagnostic"]["run_count"] == 2
    assert summary["setup_contact_audit"]["saved_anchor_count"] == 2
    written = read_json(tmp_path / "artifacts" / "session" / "gap_live" / probe.ANALYZER_KIND / "gap_fill_summary.json")
    assert written["campaign_id"] == "gap_live"


def test_live_probe_without_child_summaries_is_infrastructure_blocker(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(probe.stage_compare, "REPO_ROOT", tmp_path)

    def fake_run(command: list[str], log_path: Path) -> int:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("failed before summary\n", encoding="utf-8")
        return 1

    monkeypatch.setattr(probe, "_run_command", fake_run)
    args = _args(
        campaign_id="gap_infra",
        dry_run=False,
        family=["ai_push_coast_servo_v1", "nav2_followpath_corridor_push_v1"],
    )

    summary = probe.run_probe(args)

    assert summary["decision"]["action"] == "live_probe_infrastructure_blocker"
    assert all(not child["summary_exists"] for child in summary["children"])
