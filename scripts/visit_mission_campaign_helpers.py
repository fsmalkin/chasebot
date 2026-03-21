#!/usr/bin/env python3
"""Helpers for deterministic visit-mission repeatability summaries."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable

from llm_supervisor_core import read_json
from llm_supervisor_core import read_jsonl


def parse_marker(output: str, prefix: str) -> str:
    for line in str(output or "").splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def first_dispatched_intents_by_target(sequence: Iterable[Dict[str, Any]]) -> Dict[str, str]:
    firsts: Dict[str, str] = {}
    for entry in sequence:
        if not isinstance(entry, dict) or entry.get("event_type") != "decision_dispatched":
            continue
        target_id = str(entry.get("target_id", "") or "").strip()
        if not target_id or target_id in firsts:
            continue
        decision = entry.get("decision") if isinstance(entry.get("decision"), dict) else {}
        intent = str(decision.get("intent", "") or "").strip()
        if intent:
            firsts[target_id] = intent
    return firsts


def hidden_start_search_first(target_results: Iterable[Dict[str, Any]]) -> bool:
    checked = False
    for item in target_results:
        if not isinstance(item, dict):
            continue
        if bool(item.get("started_visible", True)):
            continue
        checked = True
        if str(item.get("first_dispatched_intent", "") or "").strip() != "search_for_target":
            return False
    return checked


def summarize_visit_run(
    *,
    run_index: int,
    return_code: int,
    output: str,
    summary_marker: str = "VISIT_MISSION_SUMMARY=",
) -> Dict[str, Any]:
    verdict_marker = parse_marker(output, summary_marker)
    verdict_path = Path(verdict_marker) if verdict_marker else None
    mission_root = verdict_path.parent if verdict_path and verdict_path.exists() else None
    summary_path = mission_root / "summary.json" if mission_root else None
    target_results_path = mission_root / "target_results.json" if mission_root else None
    visit_sequence_path = mission_root / "visit_sequence.jsonl" if mission_root else None

    verdict = read_json(verdict_path) if verdict_path and verdict_path.exists() else {}
    summary = read_json(summary_path) if summary_path and summary_path.exists() else {}
    target_results_payload = read_json(target_results_path) if target_results_path and target_results_path.exists() else {}
    target_results = list(target_results_payload.get("targets", [])) if isinstance(target_results_payload.get("targets"), list) else []
    visit_sequence = read_jsonl(visit_sequence_path) if visit_sequence_path and visit_sequence_path.exists() else []

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
        "visit_sequence_path": str(visit_sequence_path) if visit_sequence_path and visit_sequence_path.exists() else "",
        "retry_count": int(verdict.get("retry_count", 0) or 0),
        "target_results": target_results,
        "first_dispatched_intents_by_target": first_dispatched_intents_by_target(visit_sequence),
        "hidden_start_search_first": hidden_start_search_first(target_results),
        "mission_verdict": verdict,
        "summary": summary,
    }


def campaign_pass(runs: Iterable[Dict[str, Any]]) -> bool:
    items = list(runs)
    if not items:
        return False
    return all(bool(item.get("pass")) and bool(item.get("hidden_start_search_first")) for item in items)
