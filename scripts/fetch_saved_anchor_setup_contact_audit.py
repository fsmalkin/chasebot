#!/usr/bin/env python3
"""Audit saved-anchor fetch runs for setup/contact versus terminal failures."""

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


ANALYZER_KIND = "fetch_saved_anchor_setup_contact_audit"
TERMINAL_LIVE_MAX_EXTRA_M = 0.55
SETUP_LATERAL_LIMIT_M = 0.22
SETUP_YAW_LIMIT_DEG = 18.0
FIRST_CONTACT_ALIGNMENT_LIMIT_DEG = 30.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit saved-anchor setup/contact fetch evidence.")
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--saved-anchor-summary", action="append", required=True)
    return parser.parse_args()


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


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


def _round_or_none(value: Any) -> float | None:
    numeric = _finite_float(value)
    return round(float(numeric), 6) if numeric is not None else None


def _payload_candidates(run: dict[str, Any]) -> list[dict[str, Any]]:
    mission_verdict = _dict(run.get("mission_verdict"))
    shot_outcome = _dict(run.get("shot_outcome"))
    verdict_shot = _dict(mission_verdict.get("shot_outcome"))
    return [shot_outcome, verdict_shot, mission_verdict, run]


def _first_payload_value(run: dict[str, Any], key: str) -> Any:
    for payload in _payload_candidates(run):
        if key in payload and payload.get(key) not in (None, ""):
            return payload.get(key)
    return None


def _summary_runs(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in _list(summary.get("runs")) if isinstance(item, dict)]


def _representative_run(summary: dict[str, Any]) -> dict[str, Any]:
    runs = [item for item in _list(summary.get("runs")) if isinstance(item, dict)]
    for run in runs:
        if not bool(run.get("fetch_to_pose_pass", False)):
            return run
    return runs[-1] if runs else {}


def _layout_name(summary: dict[str, Any]) -> str:
    layout_path = _clean_text(summary.get("requested_target_layout_json"))
    if layout_path:
        stem = Path(layout_path).stem
        for prefix in ("golf_ball_circle_delivery_", "fetch_"):
            if stem.startswith(prefix):
                return stem[len(prefix) :]
        return stem
    campaign_id = _clean_text(summary.get("campaign_id"))
    for candidate in ("zero", "left05", "right05"):
        if candidate in campaign_id:
            return candidate
    return campaign_id or "unknown"


def _failure_reasons(summary: dict[str, Any], run: dict[str, Any]) -> list[str]:
    reasons: list[str] = []

    def add(value: Any) -> None:
        text = _clean_text(value)
        if not text or text in {"trajectory_intersects_delivery_radius", "none"}:
            return
        if text not in reasons:
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
    for key in ("fetch_to_pose_failure_reason", "approach_failure_reason", "approach_side_reason"):
        add(run.get(key))
    for approach_key in ("fresh_attempt_approach", "latest_approach_progress"):
        approach = _dict(run.get(approach_key))
        add(approach.get("reason"))
        add(_dict(approach.get("capture_entry")).get("failure_reason"))
    for payload in _payload_candidates(run):
        add(payload.get("reason"))
    return reasons


def _ai_payload(run: dict[str, Any]) -> dict[str, Any]:
    for payload in _payload_candidates(run):
        if payload.get("ai_push_coast_shadow") or payload.get("ai_push_coast_proposal") or payload.get("ai_push_coast_guard"):
            return {
                "ai_push_coast_mode": _clean_text(payload.get("ai_push_coast_mode")),
                "ai_push_coast_shadow": _dict(payload.get("ai_push_coast_shadow")),
                "ai_push_coast_proposal": _dict(payload.get("ai_push_coast_proposal")),
                "ai_push_coast_guard": _dict(payload.get("ai_push_coast_guard")),
                "ai_push_coast_latency_ms": payload.get("ai_push_coast_latency_ms"),
            }
    return {}


def _stage_labels(summary: dict[str, Any], run: dict[str, Any], ai_fields: dict[str, Any]) -> list[str]:
    labels: list[str] = []

    def add(label: str) -> None:
        clean = _clean_text(label)
        if clean and clean != "clean_contact" and clean not in labels:
            labels.append(clean)

    shadow = _dict(ai_fields.get("ai_push_coast_shadow"))
    proposal = _dict(ai_fields.get("ai_push_coast_proposal"))
    for classification in (
        _dict(shadow.get("stage_classification")),
        _dict(proposal.get("stage_classification")),
    ):
        for label in _list(classification.get("stage_labels")):
            add(str(label))

    relative = _dict(proposal.get("relative_errors"))
    lateral_error = _finite_float(relative.get("robot_lateral_error_m"))
    yaw_error = _finite_float(relative.get("robot_yaw_error_deg"))
    if lateral_error is not None and lateral_error > SETUP_LATERAL_LIMIT_M:
        add("setup")
    if yaw_error is not None and abs(float(yaw_error)) > SETUP_YAW_LIMIT_DEG:
        add("setup")

    first_contact_alignment = _finite_float(run.get("first_contact_push_alignment_deg"))
    if first_contact_alignment is None:
        first_contact_alignment = _finite_float(summary.get("first_contact_push_alignment_max_deg"))
    if first_contact_alignment is not None and abs(float(first_contact_alignment)) > FIRST_CONTACT_ALIGNMENT_LIMIT_DEG:
        add("first_contact")

    nav2 = _dict(_first_payload_value(run, "nav2_follow_path_corridor_push"))
    monitor_sample = _dict(nav2.get("monitor_sample")) or _dict(_dict(nav2.get("monitor")).get("last_sample"))
    lateral_escape = _finite_float(monitor_sample.get("lateral_error_m"))
    if lateral_escape is not None and abs(float(lateral_escape)) > 0.45:
        add("push_coast")
    guard_reasons = [
        _clean_text(reason)
        for reason in _list(_dict(ai_fields.get("ai_push_coast_guard")).get("reasons"))
    ]
    if "object_motion_not_observed" in guard_reasons:
        add("first_contact")
    if (
        _first_payload_value(run, "fetch_ball_moved_since_fetch") is False
        and _clean_text(nav2.get("dispatch_status")) == "goal_succeeded"
    ):
        add("first_contact")

    for reason in _failure_reasons(summary, run):
        text = reason.lower()
        if "capture_entry_timeout" in text or "pre_stage" in text or "handoff" in text:
            add("setup")
        if "misaligned_first_contact" in text or "first_contact" in text or "knock_away" in text:
            add("first_contact")
        if "ball_escape" in text or "trajectory_angle" in text or "roll_away" in text:
            add("push_coast")
        if "missed_delivery_radius" in text or "stopped_short" in text:
            add("terminal_arrival")

    if bool(run.get("fetch_to_pose_pass", False)):
        add("terminal_arrival")
    return labels


def _interpretation(
    *,
    passed: bool,
    stage_labels: list[str],
    closest_approach_m: float | None,
    delivery_radius_m: float,
    failure_reasons: list[str],
) -> tuple[str, str]:
    if passed and not any(label in stage_labels for label in ("setup", "first_contact", "push_coast")):
        return "saved_anchor_pass", "continue_saved_anchor_ladder"
    if passed:
        return "saved_anchor_pass_with_contact_watch", "run_repeatability_ladder_with_contact_watch"
    if any(label in stage_labels for label in ("setup", "first_contact", "push_coast")):
        return "setup_contact_blocker", "repair_setup_contact_before_guarded_live"
    near_contract = (
        closest_approach_m is not None
        and closest_approach_m <= delivery_radius_m + TERMINAL_LIVE_MAX_EXTRA_M
    )
    if "terminal_arrival" in stage_labels and near_contract:
        return "guarded_live_terminal_candidate", "run_narrow_terminal_correction_probe"
    if any("ball_escape" in reason for reason in failure_reasons):
        return "setup_contact_blocker", "repair_setup_contact_before_guarded_live"
    return "saved_anchor_watchlist", "collect_repro_before_tuning"


def analyze_summary(path: Path, summary: dict[str, Any]) -> dict[str, Any]:
    run = _representative_run(summary)
    ai_fields = _ai_payload(run)
    failure_reasons = _failure_reasons(summary, run)
    delivery_radius_m = float(
        _finite_float(_first_payload_value(run, "delivery_radius_m"))
        or _finite_float(_first_payload_value(run, "fetch_delivery_radius_m"))
        or _finite_float(_dict(summary.get("requested_fetch_pose_world")).get("radius_m"))
        or 0.3
    )
    closest_values = [
        _finite_float(_first_payload_value(item, "closest_approach_distance_m"))
        for item in _summary_runs(summary)
    ]
    closest_values = [value for value in closest_values if value is not None]
    distance_values = [
        _finite_float(_first_payload_value(item, "distance_to_fetch_pose_m"))
        for item in _summary_runs(summary)
    ]
    distance_values = [value for value in distance_values if value is not None]
    closest_approach_m = max(closest_values) if closest_values else _finite_float(_first_payload_value(run, "closest_approach_distance_m"))
    distance_to_fetch_pose_m = max(distance_values) if distance_values else _finite_float(_first_payload_value(run, "distance_to_fetch_pose_m"))
    nav2 = _dict(_first_payload_value(run, "nav2_follow_path_corridor_push"))
    monitor_sample = _dict(nav2.get("monitor_sample")) or _dict(_dict(nav2.get("monitor")).get("last_sample"))
    labels: list[str] = []
    for candidate_run in _summary_runs(summary) or [run]:
        for label in _stage_labels(summary, candidate_run, _ai_payload(candidate_run)):
            if label not in labels:
                labels.append(label)
    required_green_runs = int(_finite_float(summary.get("required_green_runs")) or max(len(_summary_runs(summary)), 1))
    pass_count = int(_finite_float(summary.get("fetch_to_pose_pass_count")) or _finite_float(summary.get("pass_count")) or 0)
    failure_count = int(_finite_float(summary.get("fetch_to_pose_fail_count")) or 0)
    passed = bool(summary.get("promotion_gate_pass", False)) or (
        pass_count >= required_green_runs and failure_count == 0
    )
    interpretation, next_action = _interpretation(
        passed=passed,
        stage_labels=labels,
        closest_approach_m=closest_approach_m,
        delivery_radius_m=delivery_radius_m,
        failure_reasons=failure_reasons,
    )
    proposal = _dict(ai_fields.get("ai_push_coast_proposal"))
    guard = _dict(ai_fields.get("ai_push_coast_guard"))
    return {
        "layout": _layout_name(summary),
        "campaign_id": _clean_text(summary.get("campaign_id")),
        "summary_path": str(path),
        "history_path": _clean_text(summary.get("history_path")),
        "pass": passed,
        "failure_reasons": failure_reasons,
        "stage_labels": labels,
        "interpretation": interpretation,
        "recommended_next_action": next_action,
        "closest_approach_distance_m": _round_or_none(closest_approach_m),
        "distance_to_fetch_pose_m": _round_or_none(distance_to_fetch_pose_m),
        "delivery_radius_m": round(float(delivery_radius_m), 6),
        "approach_failure_reason": _clean_text(run.get("approach_failure_reason")),
        "first_contact_push_alignment_deg": _round_or_none(run.get("first_contact_push_alignment_deg")),
        "push_direction_yaw_deg": _round_or_none(summary.get("push_direction_yaw_avg_deg")),
        "nav2_dispatch_status": _clean_text(nav2.get("dispatch_status")),
        "nav2_monitor_cancel_reason": _clean_text(nav2.get("monitor_cancel_reason")),
        "monitor_lateral_error_m": _round_or_none(monitor_sample.get("lateral_error_m")),
        "monitor_delivery_distance_m": _round_or_none(monitor_sample.get("delivery_distance_m")),
        "monitor_robot_ball_distance_m": _round_or_none(monitor_sample.get("robot_ball_distance_m")),
        "path_terminal_yaw_error_deg": _round_or_none(_dict(nav2.get("path_progress_last")).get("terminal_yaw_error_deg")),
        "ai_maneuver_class": _clean_text(proposal.get("maneuver_class")),
        "ai_relative_errors": _dict(proposal.get("relative_errors")),
        "ai_guard_accepted": bool(guard.get("accepted", False)),
        "ai_guard_reasons": _list(guard.get("reasons")),
    }


def analyze(saved_anchor_summaries: list[str]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for raw_path in saved_anchor_summaries:
        path = _resolve_path(raw_path)
        payload = read_json(path)
        if not isinstance(payload, dict):
            raise SystemExit(f"saved anchor summary is not a JSON object: {path}")
        rows.append(analyze_summary(path, payload))
    blocker_count = sum(1 for row in rows if row.get("interpretation") == "setup_contact_blocker")
    terminal_candidate_count = sum(1 for row in rows if row.get("interpretation") == "guarded_live_terminal_candidate")
    contact_watch_count = sum(1 for row in rows if row.get("interpretation") == "saved_anchor_pass_with_contact_watch")
    pass_count = sum(1 for row in rows if bool(row.get("pass", False)))
    if blocker_count:
        overall = "repair_setup_contact_before_guarded_live"
    elif terminal_candidate_count:
        overall = "guarded_live_terminal_probe_ready"
    elif pass_count == len(rows) and contact_watch_count:
        overall = "saved_anchor_repeatability_ready_with_contact_watch"
    elif pass_count == len(rows):
        overall = "saved_anchor_ladder_ready"
    else:
        overall = "saved_anchor_watchlist"
    return {
        "generated_utc": utc_now(),
        "analyzer": ANALYZER_KIND,
        "saved_anchor_count": len(rows),
        "pass_count": pass_count,
        "setup_contact_blocker_count": blocker_count,
        "saved_anchor_pass_with_contact_watch_count": contact_watch_count,
        "guarded_live_terminal_candidate_count": terminal_candidate_count,
        "overall_interpretation": overall,
        "saved_anchors": rows,
    }


def write_scorecard(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# Saved Anchor Setup/Contact Audit",
        "",
        f"- Generated: `{summary.get('generated_utc')}`",
        f"- Overall interpretation: `{summary.get('overall_interpretation')}`",
        f"- Saved anchors: `{summary.get('saved_anchor_count')}`",
        f"- Pass count: `{summary.get('pass_count')}`",
        f"- Pass-with-contact-watch count: `{summary.get('saved_anchor_pass_with_contact_watch_count')}`",
        f"- Setup/contact blockers: `{summary.get('setup_contact_blocker_count')}`",
        f"- Guarded-live terminal candidates: `{summary.get('guarded_live_terminal_candidate_count')}`",
        "",
        "| layout | pass | stage labels | closest | monitor | AI maneuver | interpretation | next action |",
        "|---|---:|---|---:|---|---|---|---|",
    ]
    for row in _list(summary.get("saved_anchors")):
        monitor = row.get("nav2_monitor_cancel_reason") or row.get("nav2_dispatch_status") or ""
        lines.append(
            "| "
            + " | ".join(
                [
                    _clean_text(row.get("layout")),
                    "`true`" if row.get("pass") else "`false`",
                    ", ".join(_list(row.get("stage_labels"))) or "-",
                    str(row.get("closest_approach_distance_m")),
                    _clean_text(monitor),
                    _clean_text(row.get("ai_maneuver_class")) or "-",
                    _clean_text(row.get("interpretation")),
                    _clean_text(row.get("recommended_next_action")),
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    campaign_id = _clean_text(args.campaign_id) or f"fetch_saved_anchor_setup_contact_audit_{current_utc_stamp()}"
    output_root = ensure_dir(_output_root(campaign_id))
    summary = analyze(list(args.saved_anchor_summary or []))
    summary["campaign_id"] = campaign_id
    summary_path = output_root / "audit_summary.json"
    scorecard_path = output_root / "scorecard.md"
    write_json(summary_path, summary)
    write_scorecard(summary, scorecard_path)
    print(f"AUDIT_SUMMARY={summary_path}")
    print(f"AUDIT_SCORECARD={scorecard_path}")
    print(f"OVERALL_INTERPRETATION={summary['overall_interpretation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
