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
        "session_id": str(verdict.get("session_id", "") or summary.get("session_id", "")),
        "scenario_id": str(verdict.get("scenario_id", "") or summary.get("scenario_id", "")),
        "mission_root": str(mission_root) if mission_root else "",
        "summary_path": str(summary_path) if summary_path and summary_path.exists() else "",
        "mission_verdict_path": str(verdict_path) if verdict_path and verdict_path.exists() else "",
        "target_results_path": str(target_results_path) if target_results_path and target_results_path.exists() else "",
        "scorecard_path": str(scorecard_path) if scorecard_path and scorecard_path.exists() else "",
        "placed_count": int(verdict.get("placed_count", summary.get("placed_count", 0)) or 0),
        "capture_loss_count": int(verdict.get("capture_loss_count", summary.get("capture_loss_count", 0)) or 0),
        "mission_time_s": float(verdict.get("mission_time_s", summary.get("mission_time_s", 0.0)) or 0.0),
        "route_order": list(verdict.get("route_order", summary.get("route_order", [])) or []),
        "target_results": target_results,
        "mission_verdict": verdict,
        "summary": summary,
    }
