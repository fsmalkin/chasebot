#!/usr/bin/env python3
"""Helpers for deterministic gather-mission repeatability summaries."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llm_supervisor_core import read_json
from visit_mission_campaign_helpers import parse_marker


def summarize_gather_run(
    *,
    run_index: int,
    return_code: int,
    output: str,
    summary_marker: str = "GATHER_MISSION_SUMMARY=",
) -> dict[str, Any]:
    verdict_marker = parse_marker(output, summary_marker)
    verdict_path = Path(verdict_marker) if verdict_marker else None
    mission_root = verdict_path.parent if verdict_path and verdict_path.exists() else None
    summary_path = mission_root / "summary.json" if mission_root else None
    target_results_path = mission_root / "target_results.json" if mission_root else None
    scorecard_path = mission_root / "scorecard.md" if mission_root else None

    verdict = read_json(verdict_path) if verdict_path and verdict_path.exists() else {}
    summary = read_json(summary_path) if summary_path and summary_path.exists() else {}
    target_results_payload = read_json(target_results_path) if target_results_path and target_results_path.exists() else {}
    target_results = list(target_results_payload.get("targets", [])) if isinstance(target_results_payload.get("targets"), list) else []

    return {
        "run_index": run_index,
        "return_code": return_code,
        "pass": bool(verdict.get("pass")) if verdict else bool(summary.get("pass")),
        "mission_completed_pass": bool(verdict.get("mission_completed_pass", summary.get("mission_completed_pass", verdict.get("pass", summary.get("pass", False))))),
        "session_id": str(verdict.get("session_id", "") or summary.get("session_id", "")),
        "scenario_id": str(verdict.get("scenario_id", "") or summary.get("scenario_id", "")),
        "mission_root": str(mission_root) if mission_root else "",
        "summary_path": str(summary_path) if summary_path and summary_path.exists() else "",
        "mission_verdict_path": str(verdict_path) if verdict_path and verdict_path.exists() else "",
        "target_results_path": str(target_results_path) if target_results_path and target_results_path.exists() else "",
        "scorecard_path": str(scorecard_path) if scorecard_path and scorecard_path.exists() else "",
        "placed_count": int(verdict.get("placed_count", summary.get("placed_count", 0)) or 0),
        "capture_loss_count": int(verdict.get("capture_loss_count", summary.get("capture_loss_count", 0)) or 0),
        "surface_profile": str(verdict.get("surface_profile", summary.get("surface_profile", "")) or ""),
        "handoff_kind": str(verdict.get("handoff_kind", summary.get("handoff_kind", "")) or ""),
        "zone_edge_correction_count": int(verdict.get("zone_edge_correction_count", summary.get("zone_edge_correction_count", 0)) or 0),
        "place_controller_reentry_count": int(verdict.get("place_controller_reentry_count", summary.get("place_controller_reentry_count", 0)) or 0),
        "post_visit_revisit_count": int(verdict.get("post_visit_revisit_count", summary.get("post_visit_revisit_count", 0)) or 0),
        "stopped_with_ball_captured": bool(verdict.get("stopped_with_ball_captured", summary.get("stopped_with_ball_captured", False))),
        "release_started_with_capture": bool(verdict.get("release_started_with_capture", summary.get("release_started_with_capture", False))),
        "clean_retention_pass": bool(verdict.get("clean_retention_pass", summary.get("clean_retention_pass", False))),
        "final_inside_retrieval_corral": bool(verdict.get("final_inside_retrieval_corral", summary.get("final_inside_retrieval_corral", False))),
        "final_center_inside_zone": bool(verdict.get("final_center_inside_zone", summary.get("final_center_inside_zone", False))),
        "ball_stopped_in_corral": bool(verdict.get("ball_stopped_in_corral", summary.get("ball_stopped_in_corral", False))),
        "rolled_away_after_release": bool(verdict.get("rolled_away_after_release", summary.get("rolled_away_after_release", False))),
        "settled_in_corral_pass": bool(verdict.get("settled_in_corral_pass", summary.get("settled_in_corral_pass", False))),
        "final_corral_audit": verdict.get("final_corral_audit", summary.get("final_corral_audit", {}))
        if isinstance(verdict.get("final_corral_audit", summary.get("final_corral_audit", {})), dict)
        else {},
        "final_all_targets_inside_retrieval_corral": bool(
            verdict.get(
                "final_all_targets_inside_retrieval_corral",
                summary.get("final_all_targets_inside_retrieval_corral", False),
            )
        ),
        "final_all_targets_stopped": bool(
            verdict.get(
                "final_all_targets_stopped",
                summary.get("final_all_targets_stopped", False),
            )
        ),
        "final_three_ball_corral_pass": bool(
            verdict.get(
                "final_three_ball_corral_pass",
                summary.get("final_three_ball_corral_pass", False),
            )
        ),
        "retrieved_count": int(verdict.get("retrieved_count", summary.get("retrieved_count", 0)) or 0),
        "final_settle_distance_m": float(verdict.get("final_settle_distance_m", summary.get("final_settle_distance_m", 0.0)) or 0.0),
        "max_overshoot_distance_m": float(verdict.get("max_overshoot_distance_m", summary.get("max_overshoot_distance_m", 0.0)) or 0.0),
        "settle_time_s": float(verdict.get("settle_time_s", summary.get("settle_time_s", 0.0)) or 0.0),
        "release_recontact_count": int(verdict.get("release_recontact_count", summary.get("release_recontact_count", 0)) or 0),
        "mission_time_s": float(verdict.get("mission_time_s", summary.get("mission_time_s", 0.0)) or 0.0),
        "route_order": list(verdict.get("route_order", summary.get("route_order", [])) or []),
        "target_results": target_results,
        "mission_verdict": verdict,
        "summary": summary,
    }
