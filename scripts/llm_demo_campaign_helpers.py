#!/usr/bin/env python3
"""Helpers for bounded LLM proof and demo campaign summaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable

from llm_supervisor_core import read_json, read_jsonl


def parse_marker(output: str, prefix: str) -> str:
    for line in str(output or "").splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return ""


def first_decision_seen(decision_history: Iterable[Dict[str, Any]]) -> str:
    for entry in decision_history:
        decision = entry.get("decision") if isinstance(entry, dict) else {}
        if not isinstance(decision, dict):
            continue
        intent = str(decision.get("intent", "") or "").strip()
        status = str(decision.get("status", "") or "").strip()
        if intent:
            return intent
        if status:
            return status
    return ""


def invalid_provider_output_count(decision_history: Iterable[Dict[str, Any]]) -> int:
    count = 0
    for entry in decision_history:
        decision = entry.get("decision") if isinstance(entry, dict) else {}
        if not isinstance(decision, dict):
            continue
        missing = [str(item) for item in list(decision.get("missing_prerequisites", []))]
        if "provider_output_invalid" in missing:
            count += 1
    return count


def blocked_only(decision_history: Iterable[Dict[str, Any]]) -> bool:
    seen = False
    for entry in decision_history:
        decision = entry.get("decision") if isinstance(entry, dict) else {}
        if not isinstance(decision, dict):
            continue
        status = str(decision.get("status", "") or "").strip()
        if not status:
            continue
        seen = True
        if status != "blocked":
            return False
    return seen


def summarize_demo_run(
    *,
    run_index: int,
    return_code: int,
    output: str,
    summary_marker: str,
) -> Dict[str, Any]:
    summary_marker_value = parse_marker(output, summary_marker)
    proof_verdict_path = Path(summary_marker_value) if summary_marker_value else None
    proof_verdict = read_json(proof_verdict_path) if proof_verdict_path and proof_verdict_path.exists() else {}
    proof_root = proof_verdict_path.parent if proof_verdict_path and proof_verdict_path.exists() else None
    summary_path = proof_root / "summary.json" if proof_root else None
    summary_payload = read_json(summary_path) if summary_path and summary_path.exists() else {}
    decision_history_path = proof_root / "decision_history.jsonl" if proof_root else None
    decision_history = read_jsonl(decision_history_path) if decision_history_path and decision_history_path.exists() else []

    return {
        "run_index": run_index,
        "return_code": return_code,
        "pass": bool(proof_verdict.get("pass")) if proof_verdict else bool(summary_payload.get("pass")),
        "session_id": str(proof_verdict.get("session_id", "") or summary_payload.get("session_id", "")),
        "proof_root": str(proof_root) if proof_root else "",
        "summary_path": str(summary_path) if summary_path and summary_path.exists() else "",
        "proof_verdict_path": str(proof_verdict_path) if proof_verdict_path and proof_verdict_path.exists() else "",
        "first_decision_seen": first_decision_seen(decision_history),
        "invalid_provider_output_count": invalid_provider_output_count(decision_history),
        "blocked_only": blocked_only(decision_history),
        "proof_verdict": proof_verdict,
        "summary": summary_payload,
    }


def campaign_pass(runs: Iterable[Dict[str, Any]]) -> bool:
    run_items = list(runs)
    if not run_items:
        return False
    return all(
        bool(item.get("pass"))
        and int(item.get("invalid_provider_output_count", 0)) == 0
        and not bool(item.get("blocked_only", False))
        for item in run_items
    )
