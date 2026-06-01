from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_stage_owner_comparison as comparison  # noqa: E402
from llm_supervisor_core import read_json  # noqa: E402
from llm_supervisor_core import write_json  # noqa: E402


def _mission_summary(
    *,
    campaign_id: str,
    layout: str,
    passed: bool,
    closest: float | None = 0.18,
    reason: str = "",
    run_count: int = 1,
    session_id: str = "session01",
) -> dict:
    runs = []
    for _ in range(run_count):
        runs.append(
            {
                "session_id": session_id,
                "fetch_to_pose_pass": passed,
                "fetch_to_pose_failure_reason": reason,
                "capture_entry_reached": passed,
                "pre_stage_handoff_pass": True,
                "model_provenance_valid": True,
                "shot_outcome": {
                    "reason": reason or "trajectory_intersects_delivery_radius",
                    "closest_approach_distance_m": closest,
                    "distance_to_fetch_pose_m": closest,
                    "fetch_ball_moved_since_fetch": True,
                },
            }
        )
    return {
        "campaign_id": campaign_id,
        "requested_target_layout_json": f"ros2_config/target_layouts/golf_ball_circle_delivery_{layout}.json",
        "model_provenance_valid": True,
        "fetch_to_pose_pass_count": run_count if passed else 0,
        "fetch_to_pose_fail_count": 0 if passed else run_count,
        "fetch_to_pose_failure_reasons": [] if passed else [reason],
        "fresh_attempt_capture_entry_pass_count": run_count if passed else 0,
        "fresh_attempt_pre_stage_handoff_pass_count": run_count,
        "fresh_attempt_first_contact_push_alignment_max_deg": 4.0,
        "runs": runs,
    }


def test_stage_owner_comparison_recommends_gap_fill_when_current_setup_red_but_prior_green(tmp_path, monkeypatch):
    monkeypatch.setattr(comparison, "REPO_ROOT", tmp_path)
    planner = tmp_path / "planner.json"
    current = tmp_path / "current_right05.json"
    object_child = tmp_path / "object_right05.json"
    object_gate = tmp_path / "object_gate.json"
    direct = tmp_path / "direct_right05.json"
    audit = tmp_path / "audit.json"

    write_json(
        planner,
        {
            "type": "fetch_planner_handoff_gate",
            "pass": True,
            "pass_count": 5,
            "random_cases": 5,
            "wrong_fetch_dispatch_count": 0,
            "results": [],
        },
    )
    write_json(
        current,
        _mission_summary(
            campaign_id="live_current_right05",
            layout="right05",
            passed=False,
            closest=None,
            reason="capture_entry_timeout",
        ),
    )
    write_json(object_child, _mission_summary(campaign_id="may27_right05", layout="right05", passed=True, closest=0.22))
    write_json(object_gate, {"results": [{"summary_path": str(object_child)}]})
    write_json(direct, _mission_summary(campaign_id="direct_right05", layout="right05", passed=True, closest=0.136))
    write_json(
        audit,
        {
            "saved_anchors": [
                {
                    "layout": "right05",
                    "summary_path": str(current),
                    "delivery_pass": False,
                    "failure_reasons": ["capture_entry_timeout"],
                    "quality_classification": "setup_capture_blocker",
                    "quality_flags": ["setup_capture_blocker", "capture_entry_time_watch"],
                    "stage_labels": ["setup"],
                    "run_stage_quality": [{}],
                }
            ]
        },
    )
    (tmp_path / "artifacts" / "session" / "session01" / "visual").mkdir(parents=True)
    (tmp_path / "artifacts" / "session" / "session01" / "visual" / "raw_camera.mp4").write_bytes(b"video")

    summary = comparison.summarize_comparison(
        campaign_id="cmp",
        dashboard_base_url="",
        planner_gate_summary=str(planner),
        current_saved_anchor_summaries=[str(current)],
        current_stage_audit=str(audit),
        object_centric_gate_summary=str(object_gate),
        corrected_direct_summaries=[str(direct)],
    )

    assert summary["recommended_next_action"]["action"] == "run_setup_capture_gap_fill_or_port_prior_behavior"
    verdicts = {verdict["stage"]: verdict for verdict in summary["stage_verdicts"]}
    assert verdicts["planner_handoff"]["color"] == "green"
    assert verdicts["capture_entry"]["color"] == "green"
    current_capture_rows = [
        row
        for row in summary["stage_rows"]
        if row["source_id"] == "current_staged_nav2_contact_buffer" and row["stage"] == "capture_entry"
    ]
    assert any(row["color"] == "red" for row in current_capture_rows)
    assert summary["representative_videos"][0]["href"] == "/artifacts/session/session01/visual/raw_camera.mp4"
    assert (tmp_path / "artifacts" / "session" / "cmp" / comparison.ANALYZER_KIND / "stage_owner_summary.json").is_file()
    assert (tmp_path / "artifacts" / "session" / "cmp" / comparison.ANALYZER_KIND / "scorecard.md").is_file()


def test_nav2_stop_short_scores_push_coast_yellow_and_terminal_red(tmp_path, monkeypatch):
    monkeypatch.setattr(comparison, "REPO_ROOT", tmp_path)
    stop_short = tmp_path / "nav2_right05_promotion.json"
    nav2_summary = tmp_path / "nav2_architecture.json"
    write_json(
        stop_short,
        _mission_summary(
            campaign_id="nav2_right05_promotion",
            layout="right05",
            passed=False,
            closest=0.451645,
            reason="missed_delivery_radius_after_fetch_to_pose_ball_stopped_short",
            run_count=3,
        ),
    )
    write_json(
        nav2_summary,
        {
            "candidate_families": [
                {
                    "family": "nav2_followpath_corridor_push_v1",
                    "promotion_results": [{"summary_path": str(stop_short)}],
                }
            ]
        },
    )

    summary = comparison.summarize_comparison(
        campaign_id="cmp_nav2",
        dashboard_base_url="",
        nav2_corridor_summary=str(nav2_summary),
    )

    rows = {(row["source_id"], row["stage"]): row for row in summary["stage_rows"]}
    assert rows[("nav2_corridor_push", "push_coast")]["color"] == "yellow"
    assert rows[("nav2_corridor_push", "terminal_delivery")]["color"] == "red"


def test_current_red_without_prior_green_collects_gap_fill_probe(tmp_path, monkeypatch):
    monkeypatch.setattr(comparison, "REPO_ROOT", tmp_path)
    current = tmp_path / "current_right05.json"
    write_json(
        current,
        _mission_summary(
            campaign_id="live_current_right05",
            layout="right05",
            passed=False,
            closest=None,
            reason="capture_entry_timeout",
        ),
    )

    summary = comparison.summarize_comparison(
        campaign_id="cmp_current_only",
        dashboard_base_url="",
        current_saved_anchor_summaries=[str(current)],
    )

    assert summary["recommended_next_action"]["action"] == "collect_setup_capture_gap_fill_probe_before_fix"
    written = read_json(tmp_path / "artifacts" / "session" / "cmp_current_only" / comparison.ANALYZER_KIND / "stage_owner_summary.json")
    assert written["campaign_id"] == "cmp_current_only"
