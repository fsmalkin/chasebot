#!/usr/bin/env python3
"""Analyze seeded fetch generalization evidence and milestone context."""

from __future__ import annotations

import argparse
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import read_json
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json


ANALYZER_KIND = "fetch_seeded_gate_evidence_analyzer"
TERMINAL_LIVE_MAX_EXTRA_M = 0.55
NON_FAILURE_REASONS = {
    "trajectory_intersects_delivery_radius",
    "none",
}
MODEL_PROVENANCE_FIELDS = (
    "target_model_sdf",
    "zone_model_sdf",
    "target_model_radius_m",
    "target_model_classification",
    "zone_model_radius_m",
    "zone_model_classification",
    "model_provenance_valid",
    "model_provenance_reason",
    "model_provenance_required",
)


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze seeded random fetch evidence.")
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--gate-summary", required=True)
    parser.add_argument("--local-visual-summary", default="")
    parser.add_argument("--saved-anchor-summary", action="append", default=[])
    return parser.parse_args()


def _output_root(campaign_id: str) -> Path:
    return REPO_ROOT / "artifacts" / "session" / campaign_id / ANALYZER_KIND


def _resolve_path(raw_path: str) -> Path:
    path = Path(str(raw_path or "").strip())
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _finite_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _summary_for_result(result: dict[str, Any]) -> dict[str, Any]:
    embedded = _dict(result.get("summary"))
    summary_path = _clean_text(result.get("summary_path"))
    if summary_path:
        path = _resolve_path(summary_path)
        if path.exists():
            loaded = read_json(path)
            if isinstance(loaded, dict):
                return loaded
    return embedded


def _payload_candidates(run: dict[str, Any]) -> list[dict[str, Any]]:
    mission_verdict = _dict(run.get("mission_verdict"))
    shot_outcome = _dict(run.get("shot_outcome"))
    mission_shot = _dict(mission_verdict.get("shot_outcome"))
    return [run, mission_verdict, shot_outcome, mission_shot]


def _model_provenance_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    nested = _dict(payload.get("model_provenance"))
    if nested:
        result.update(nested)
    for key in MODEL_PROVENANCE_FIELDS:
        if key in payload:
            result[key] = payload.get(key)
    if not result:
        return {}
    if "model_provenance_valid" not in result:
        result["model_provenance_valid"] = bool(
            str(result.get("target_model_classification", "") or "") == "calibrated_golf_ball"
            and str(result.get("zone_model_classification", "") or "") == "golf_ball_delivery_zone_marker"
        )
    if not str(result.get("model_provenance_reason", "") or ""):
        result["model_provenance_reason"] = (
            "calibrated_fetch_models"
            if bool(result.get("model_provenance_valid", False))
            else "invalid_or_missing_model_provenance"
        )
    return result


def _model_provenance(summary: dict[str, Any]) -> dict[str, Any]:
    for candidate in [summary]:
        provenance = _model_provenance_from_payload(candidate)
        if provenance:
            return provenance
    for run in _list(summary.get("runs")):
        if not isinstance(run, dict):
            continue
        for payload in _payload_candidates(run):
            provenance = _model_provenance_from_payload(payload)
            if provenance:
                return provenance
    return {
        "model_provenance_valid": False,
        "model_provenance_reason": "missing_model_provenance",
        "model_provenance_required": True,
    }


def _latest_ai_fields(summary: dict[str, Any]) -> dict[str, Any]:
    for run in reversed(_list(summary.get("runs"))):
        if not isinstance(run, dict):
            continue
        for payload in reversed(_payload_candidates(run)):
            if payload.get("ai_push_coast_shadow") or payload.get("ai_push_coast_proposal") or payload.get("ai_push_coast_guard"):
                return {
                    "ai_push_coast_mode": _clean_text(payload.get("ai_push_coast_mode")),
                    "ai_push_coast_shadow": _dict(payload.get("ai_push_coast_shadow")),
                    "ai_push_coast_proposal": _dict(payload.get("ai_push_coast_proposal")),
                    "ai_push_coast_guard": _dict(payload.get("ai_push_coast_guard")),
                    "ai_push_coast_latency_ms": payload.get("ai_push_coast_latency_ms"),
                }
    return {}


def _failure_reasons(summary: dict[str, Any]) -> list[str]:
    reasons: list[str] = []

    def add(value: Any) -> None:
        text = _clean_text(value)
        if text in NON_FAILURE_REASONS:
            return
        if text and text not in reasons:
            reasons.append(text)

    for key in (
        "fetch_to_pose_failure_reasons",
        "approach_failure_reasons",
        "approach_side_reasons",
        "fresh_attempt_capture_entry_failure_reasons",
        "latest_approach_capture_entry_failure_reasons",
    ):
        for reason in _list(summary.get(key)):
            add(reason)
    for run in _list(summary.get("runs")):
        if not isinstance(run, dict):
            continue
        for key in ("fetch_to_pose_failure_reason", "approach_failure_reason", "approach_side_reason"):
            add(run.get(key))
        for approach_key in ("fresh_attempt_approach", "latest_approach_progress"):
            approach = _dict(run.get(approach_key))
            add(approach.get("reason"))
            add(_dict(approach.get("capture_entry")).get("failure_reason"))
        for payload in _payload_candidates(run):
            add(payload.get("reason"))
    return reasons


def _numeric_candidates(summary: dict[str, Any], keys: tuple[str, ...]) -> list[float]:
    values: list[float] = []
    for key in keys:
        numeric = _finite_float(summary.get(key))
        if numeric is not None:
            values.append(numeric)
    for key in ("closest_approach_distances_m",):
        for item in _list(summary.get(key)):
            numeric = _finite_float(item)
            if numeric is not None:
                values.append(numeric)
    for run in _list(summary.get("runs")):
        if not isinstance(run, dict):
            continue
        for payload in _payload_candidates(run):
            for key in keys:
                numeric = _finite_float(payload.get(key))
                if numeric is not None:
                    values.append(numeric)
    return values


def _stage_labels(*, summary: dict[str, Any], ai_fields: dict[str, Any], passed: bool) -> list[str]:
    labels: list[str] = []

    def add(label: str) -> None:
        clean = _clean_text(label)
        if clean and clean != "clean_contact" and clean not in labels:
            labels.append(clean)

    shadow = _dict(ai_fields.get("ai_push_coast_shadow"))
    classification = _dict(shadow.get("stage_classification"))
    proposal = _dict(ai_fields.get("ai_push_coast_proposal"))
    proposal_classification = _dict(proposal.get("stage_classification"))
    for label in _list(classification.get("stage_labels")) + _list(proposal_classification.get("stage_labels")):
        add(str(label))
    for reason in _failure_reasons(summary):
        text = reason.lower()
        if "capture_entry_timeout" in text or "pre_stage" in text or "handoff" in text:
            add("setup")
        if "first_contact" in text or "knock_away" in text or "alignment" in text:
            add("first_contact")
        if "trajectory_angle" in text or "push" in text or "roll_away" in text:
            add("push_coast")
        if "missed_delivery_radius" in text or "stopped_short" in text or "fetch_to_pose_ball_stopped_short" in text:
            add("terminal_arrival")
    if passed:
        add("terminal_arrival")
    return labels


def _case_interpretation(
    *,
    mode: str,
    model_provenance_valid: bool,
    passed: bool,
    reproduced_failure: bool,
    stage_labels: list[str],
    failure_reasons: list[str],
    closest_approach_m: float | None,
    delivery_radius_m: float,
) -> str:
    if not model_provenance_valid:
        return "rebuild_required_model_provenance"
    if passed:
        return "guarded_live_pass" if mode == "guarded_live" else "shadow_pass"
    if reproduced_failure:
        return "promotion_blocker_reproduced_failure"
    if "setup" in stage_labels or any("capture_entry_timeout" in reason for reason in failure_reasons):
        return "non_repro_setup_capture_watchlist"
    near_contract = closest_approach_m is not None and closest_approach_m <= delivery_radius_m + TERMINAL_LIVE_MAX_EXTRA_M
    if "terminal_arrival" in stage_labels and near_contract:
        return "guarded_live_terminal_candidate"
    return "non_repro_watchlist"


def analyze_gate(gate_summary: dict[str, Any]) -> dict[str, Any]:
    delivery_radius_m = float(_finite_float(gate_summary.get("fetch_delivery_radius_m")) or 0.3)
    mode = _clean_text(gate_summary.get("ai_push_coast_mode"))
    cases: list[dict[str, Any]] = []
    for result in _list(gate_summary.get("results")):
        if not isinstance(result, dict):
            continue
        summary = _summary_for_result(result)
        ai_fields = _latest_ai_fields(summary)
        model_provenance = _model_provenance(summary)
        model_valid = bool(model_provenance.get("model_provenance_valid", False))
        passed = bool(result.get("pass", False))
        reproduced_failure = bool(result.get("reproduced_failure", False))
        failure_reasons = _failure_reasons(summary)
        closest_values = _numeric_candidates(
            summary,
            ("closest_approach_distance_m", "fetch_closest_approach_distance_m", "worst_closest_approach_distance_m"),
        )
        delivery_values = _numeric_candidates(summary, ("distance_to_fetch_pose_m",))
        closest_approach_m = max(closest_values) if closest_values else None
        distance_to_fetch_pose_m = max(delivery_values) if delivery_values else closest_approach_m
        labels = _stage_labels(summary=summary, ai_fields=ai_fields, passed=passed)
        cases.append(
            {
                "architecture": _clean_text(result.get("architecture")),
                "case_id": _clean_text(result.get("case_id")),
                "seed": gate_summary.get("seed"),
                "layout_path": _clean_text(result.get("layout_path")),
                "summary_path": _clean_text(result.get("summary_path")),
                "pass": passed,
                "return_code": result.get("return_code"),
                "repro_pass": bool(_dict(result.get("repro")).get("pass", False)) if result.get("repro") else None,
                "reproduced_failure": reproduced_failure,
                "frozen_failure_layout": _clean_text(result.get("frozen_failure_layout")),
                "failure_reasons": failure_reasons,
                "stage_labels": labels,
                "closest_approach_distance_m": round(float(closest_approach_m), 6) if closest_approach_m is not None else None,
                "distance_to_fetch_pose_m": round(float(distance_to_fetch_pose_m), 6) if distance_to_fetch_pose_m is not None else None,
                "ai_push_coast_proposal": _dict(ai_fields.get("ai_push_coast_proposal")),
                "ai_push_coast_guard": _dict(ai_fields.get("ai_push_coast_guard")),
                "model_provenance": model_provenance,
                "model_provenance_valid": model_valid,
                "model_provenance_reason": _clean_text(model_provenance.get("model_provenance_reason")),
                "target_model_classification": _clean_text(model_provenance.get("target_model_classification")),
                "zone_model_classification": _clean_text(model_provenance.get("zone_model_classification")),
                "interpretation": _case_interpretation(
                    mode=mode,
                    model_provenance_valid=model_valid,
                    passed=passed,
                    reproduced_failure=reproduced_failure,
                    stage_labels=labels,
                    failure_reasons=failure_reasons,
                    closest_approach_m=closest_approach_m,
                    delivery_radius_m=delivery_radius_m,
                ),
            }
        )
    invalid_model_count = sum(1 for case in cases if not bool(case.get("model_provenance_valid", False)))
    reproduced_count = sum(
        1
        for case in cases
        if bool(case.get("model_provenance_valid", False)) and bool(case.get("reproduced_failure", False))
    )
    non_repro_count = sum(
        1
        for case in cases
        if bool(case.get("model_provenance_valid", False)) and not case.get("pass") and not case.get("reproduced_failure")
    )
    guarded_candidate_count = sum(
        1
        for case in cases
        if bool(case.get("model_provenance_valid", False)) and case.get("interpretation") == "guarded_live_terminal_candidate"
    )
    if invalid_model_count:
        interpretation = "rebuild_required_model_provenance"
    elif reproduced_count:
        interpretation = "promotion_blocker_freeze_reproduced_failures"
    elif non_repro_count:
        interpretation = "non_repro_watchlist_before_promotion"
    elif guarded_candidate_count:
        interpretation = "guarded_live_terminal_probe_candidates_present"
    else:
        interpretation = "guarded_live_seeded_gate_clean" if mode == "guarded_live" else "shadow_gate_clean"
    return {
        "campaign_id": _clean_text(gate_summary.get("campaign_id")),
        "seed": gate_summary.get("seed"),
        "mode": mode,
        "pass": bool(gate_summary.get("pass", False)),
        "pass_count": int(gate_summary.get("pass_count", 0) or 0),
        "fail_count": int(gate_summary.get("fail_count", 0) or 0),
        "reproduced_failure_count": reproduced_count,
        "non_repro_failure_count": non_repro_count,
        "guarded_live_candidate_count": guarded_candidate_count,
        "model_provenance_valid": bool(cases and invalid_model_count == 0),
        "model_provenance_invalid_count": invalid_model_count,
        "interpretation": interpretation,
        "cases": cases,
    }


def _local_visual_summary(path: str) -> dict[str, Any]:
    if not path:
        return {}
    payload = read_json(_resolve_path(path))
    if not isinstance(payload, dict):
        return {}
    return {
        "campaign_id": _clean_text(payload.get("campaign_id")),
        "pass_count": int(payload.get("pass_count", 0) or 0),
        "fail_count": int(payload.get("fail_count", 0) or 0),
        "clean_contact_pass_count": int(payload.get("clean_contact_pass_count", 0) or 0),
        "flagged_contact_pass_count": int(payload.get("flagged_contact_pass_count", 0) or 0),
        "interpretation": _clean_text(payload.get("interpretation")),
        "promotion_evidence": bool(payload.get("promotion_evidence", False)),
        "summary_path": str(_resolve_path(path)),
    }


def _saved_anchor_summary(path: str) -> dict[str, Any]:
    if not path:
        return {}
    payload = read_json(_resolve_path(path))
    if not isinstance(payload, dict):
        return {}
    watchlist_rows: list[dict[str, Any]] = []
    stop_short_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for candidate in _list(payload.get("candidate_families")):
        if not isinstance(candidate, dict):
            continue
        for stage_key in ("one_run_results", "promotion_results"):
            for row in _list(candidate.get(stage_key)):
                if not isinstance(row, dict):
                    continue
                metrics = _dict(row.get("metrics"))
                row_payload: dict[str, Any] = {}
                row_summary_path = _clean_text(row.get("summary_path"))
                if row_summary_path:
                    resolved_row_path = _resolve_path(row_summary_path)
                    if resolved_row_path.exists():
                        loaded_row = read_json(resolved_row_path)
                        if isinstance(loaded_row, dict):
                            row_payload = loaded_row
                row_provenance = _model_provenance(row_payload) if row_payload else {
                    "model_provenance_valid": False,
                    "model_provenance_reason": "missing_model_provenance",
                }
                row_summary = {
                    "family": _clean_text(row.get("family")),
                    "layout_id": _clean_text(row.get("layout_id")),
                    "stage": _clean_text(row.get("stage")),
                    "pass": bool(row.get("pass", False)),
                    "worst_closest_approach_distance_m": metrics.get("worst_closest_approach_distance_m"),
                    "failure_reasons": _list(metrics.get("fetch_to_pose_failure_reasons")),
                    "summary_path": row_summary_path,
                    "model_provenance_valid": bool(row_provenance.get("model_provenance_valid", False)),
                    "model_provenance_reason": _clean_text(row_provenance.get("model_provenance_reason")),
                    "target_model_classification": _clean_text(row_provenance.get("target_model_classification")),
                }
                candidate_rows.append(row_summary)
                reasons_text = " ".join(str(reason) for reason in row_summary["failure_reasons"])
                if not row_summary["pass"]:
                    watchlist_rows.append(row_summary)
                if "stopped_short" in reasons_text:
                    stop_short_rows.append(row_summary)
    return {
        "campaign_id": _clean_text(payload.get("campaign_id")),
        "overall_recommended_next_action": _clean_text(payload.get("overall_recommended_next_action")),
        "baseline_layouts": sorted(_dict(payload.get("baseline_by_layout")).keys()),
        "candidate_rows": candidate_rows,
        "watchlist_rows": watchlist_rows,
        "stop_short_rows": stop_short_rows,
        "summary_path": str(_resolve_path(path)),
    }


def _saved_anchor_summaries(paths: str | list[str]) -> dict[str, Any]:
    raw_paths = [paths] if isinstance(paths, str) else list(paths or [])
    summaries = [_saved_anchor_summary(path) for path in raw_paths if _clean_text(path)]
    summaries = [summary for summary in summaries if summary]
    baseline_layouts: set[str] = set()
    candidate_rows: list[dict[str, Any]] = []
    watchlist_rows: list[dict[str, Any]] = []
    stop_short_rows: list[dict[str, Any]] = []
    for summary in summaries:
        baseline_layouts.update(str(item) for item in _list(summary.get("baseline_layouts")))
        candidate_rows.extend(row for row in _list(summary.get("candidate_rows")) if isinstance(row, dict))
        watchlist_rows.extend(row for row in _list(summary.get("watchlist_rows")) if isinstance(row, dict))
        stop_short_rows.extend(row for row in _list(summary.get("stop_short_rows")) if isinstance(row, dict))
    return {
        "campaign_id": ",".join(_clean_text(summary.get("campaign_id")) for summary in summaries if summary.get("campaign_id")),
        "baseline_layouts": sorted(baseline_layouts),
        "candidate_rows": candidate_rows,
        "watchlist_rows": watchlist_rows,
        "stop_short_rows": stop_short_rows,
        "summary_paths": [_clean_text(summary.get("summary_path")) for summary in summaries if summary.get("summary_path")],
        "summaries": summaries,
    }


def _saved_anchor_promotion_green(saved_anchor_context: dict[str, Any]) -> bool:
    required_layouts = {"zero", "left05", "right05"}
    promotion_rows = [
        row
        for row in _list(saved_anchor_context.get("candidate_rows"))
        if isinstance(row, dict) and _clean_text(row.get("stage")) == "promotion"
    ]
    passing_layouts = {
        _clean_text(row.get("layout_id"))
        for row in promotion_rows
        if bool(row.get("pass", False)) and bool(row.get("model_provenance_valid", False))
    }
    return required_layouts.issubset(passing_layouts)


def _recommended_next_action(gate_analysis: dict[str, Any], saved_anchor_context: dict[str, Any]) -> str:
    if gate_analysis["model_provenance_invalid_count"]:
        return "rerun_seeded_gate_with_calibrated_model_provenance"
    if gate_analysis["reproduced_failure_count"]:
        return "freeze_reproduced_failures_before_tuning"
    if gate_analysis["non_repro_failure_count"]:
        return "rerun_watchlist_before_guarded_live"
    if gate_analysis["interpretation"] == "guarded_live_seeded_gate_clean":
        return "package_mobile_visual_uat" if _saved_anchor_promotion_green(saved_anchor_context) else "run_saved_layout_ai_push_coast_gate"
    return "run_guarded_live_terminal_probe"


def summarize_evidence(
    *,
    campaign_id: str,
    gate_summary_path: str,
    local_visual_summary_path: str = "",
    saved_anchor_summary_path: str | list[str] = "",
) -> dict[str, Any]:
    clean_campaign_id = campaign_id.strip() or f"live_fetch_seeded_gate_evidence_{current_utc_stamp()}"
    gate_payload = read_json(_resolve_path(gate_summary_path))
    if not isinstance(gate_payload, dict):
        raise ValueError(f"gate summary is not a JSON object: {gate_summary_path}")
    gate_analysis = analyze_gate(gate_payload)
    saved_anchor_context = _saved_anchor_summaries(saved_anchor_summary_path)
    promotion_evidence = (
        gate_analysis["interpretation"] == "guarded_live_seeded_gate_clean"
        and bool(gate_analysis["pass"])
        and bool(gate_analysis["model_provenance_valid"])
        and _saved_anchor_promotion_green(saved_anchor_context)
    )
    summary = {
        "generated_utc": utc_now(),
        "type": ANALYZER_KIND,
        "campaign_id": clean_campaign_id,
        "gate_summary_path": str(_resolve_path(gate_summary_path)),
        "seeded_gate": gate_analysis,
        "local_visual_uat": _local_visual_summary(local_visual_summary_path),
        "saved_anchor_context": saved_anchor_context,
        "milestone_interpretation": "guarded_live_seeded_gate_promotion_ready"
        if promotion_evidence
        else gate_analysis["interpretation"],
        "promotion_evidence": promotion_evidence,
        "recommended_next_action": _recommended_next_action(gate_analysis, saved_anchor_context),
    }
    output_root = _output_root(clean_campaign_id)
    ensure_dir(output_root)
    write_json(output_root / "evidence_summary.json", summary)
    write_scorecard(output_root / "scorecard.md", summary)
    return summary


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    seeded = _dict(summary.get("seeded_gate"))
    local = _dict(summary.get("local_visual_uat"))
    saved = _dict(summary.get("saved_anchor_context"))
    lines = [
        "# Fetch Seeded Gate Evidence",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- recommended_next_action: `{summary.get('recommended_next_action', '')}`",
        f"- milestone_interpretation: `{summary.get('milestone_interpretation', '')}`",
        f"- promotion_evidence: `{bool(summary.get('promotion_evidence', False))}`",
        "",
        "## Local Visual UAT",
        "",
        f"- pass/fail: `{local.get('pass_count', 0)}/{local.get('fail_count', 0)}`",
        f"- clean/flagged contact passes: `{local.get('clean_contact_pass_count', 0)}/{local.get('flagged_contact_pass_count', 0)}`",
        f"- interpretation: `{local.get('interpretation', '')}`",
        "",
        "## Seeded Shadow Gate",
        "",
        f"- campaign_id: `{seeded.get('campaign_id', '')}`",
        f"- mode: `{seeded.get('mode', '')}`",
        f"- pass/fail: `{seeded.get('pass_count', 0)}/{seeded.get('fail_count', 0)}`",
        f"- non-repro/reproduced failures: `{seeded.get('non_repro_failure_count', 0)}/{seeded.get('reproduced_failure_count', 0)}`",
        f"- guarded-live candidates: `{seeded.get('guarded_live_candidate_count', 0)}`",
        f"- model_provenance_valid: `{seeded.get('model_provenance_valid', False)}`",
        f"- model_provenance_invalid_count: `{seeded.get('model_provenance_invalid_count', 0)}`",
        "",
        "## Cases",
        "",
    ]
    for case in _list(seeded.get("cases")):
        if not isinstance(case, dict):
            continue
        labels = ",".join(str(label) for label in _list(case.get("stage_labels"))) or "none"
        reasons = ",".join(str(reason) for reason in _list(case.get("failure_reasons"))) or "none"
        proposal = _dict(case.get("ai_push_coast_proposal"))
        guard = _dict(case.get("ai_push_coast_guard"))
        lines.append(
            f"- `{case.get('case_id', '')}` pass=`{bool(case.get('pass', False))}` "
            f"repro_pass=`{case.get('repro_pass', None)}` reproduced=`{bool(case.get('reproduced_failure', False))}` "
            f"stage=`{labels}` closest=`{case.get('closest_approach_distance_m', None)}` "
            f"model=`{case.get('model_provenance_valid', False)}` "
            f"proposal=`{proposal.get('maneuver_class', '')}` guard=`{bool(guard.get('accepted', False))}` "
            f"interpretation=`{case.get('interpretation', '')}` reasons=`{reasons}`"
        )
    lines.extend(["", "## Saved Anchor Context", ""])
    lines.append(f"- campaign_id: `{saved.get('campaign_id', '')}`")
    lines.append(f"- baseline_layouts: `{','.join(str(item) for item in _list(saved.get('baseline_layouts')))}`")
    lines.append(f"- watchlist_rows: `{len(_list(saved.get('watchlist_rows')))}`")
    lines.append(f"- terminal_stop_short_rows: `{len(_list(saved.get('stop_short_rows')))}`")
    for row in _list(saved.get("watchlist_rows")):
        if not isinstance(row, dict):
            continue
        lines.append(
            f"- `{row.get('family', '')}` `{row.get('layout_id', '')}` `{row.get('stage', '')}` "
            f"closest=`{row.get('worst_closest_approach_distance_m', '')}` "
            f"model=`{row.get('model_provenance_valid', False)}` "
            f"reasons=`{','.join(str(reason) for reason in _list(row.get('failure_reasons')))}` "
            f"summary=`{row.get('summary_path', '')}`"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    summary = summarize_evidence(
        campaign_id=args.campaign_id,
        gate_summary_path=args.gate_summary,
        local_visual_summary_path=args.local_visual_summary,
        saved_anchor_summary_path=args.saved_anchor_summary,
    )
    summary_path = _output_root(str(summary.get("campaign_id", ""))) / "evidence_summary.json"
    print(f"FETCH_SEEDED_GATE_EVIDENCE_SUMMARY={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
