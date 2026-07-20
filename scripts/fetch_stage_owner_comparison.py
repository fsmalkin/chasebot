#!/usr/bin/env python3
"""Compare fetch evidence by lifecycle stage before targeted repairs."""

from __future__ import annotations

import argparse
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import read_json
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json


ANALYZER_KIND = "fetch_stage_owner_comparison"
STAGES = (
    "planner_handoff",
    "setup_pre_capture",
    "capture_entry",
    "first_contact",
    "push_coast",
    "terminal_delivery",
    "visual_clarity",
)
COLOR_RANK = {"stale": 0, "red": 1, "yellow": 2, "green": 3}
SOURCE_PRIORITY = {
    "current_staged_nav2_contact_buffer": 80,
    "object_centric_may27": 70,
    "corrected_direct_reference": 65,
    "nav2_corridor_push": 60,
    "prior_setup_acquisition": 40,
    "planner_handoff": 30,
}
VIDEO_NAMES = ("raw_camera.mp4", "yolo_debug.mp4", "topdown_telemetry.mp4", "world_stream.mp4")
DELIVERY_RADIUS_M = 0.300
TIGHT_DELIVERY_MARGIN_M = 0.270


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare fetch stage-owner evidence.")
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--dashboard-base-url", default=os.environ.get("DASHBOARD_TAILSCALE_URL", ""))
    parser.add_argument("--planner-gate-summary", default="")
    parser.add_argument("--current-saved-anchor-summary", action="append", default=[])
    parser.add_argument("--current-stage-audit", default="")
    parser.add_argument("--object-centric-gate-summary", default="")
    parser.add_argument("--nav2-corridor-summary", default="")
    parser.add_argument("--corrected-direct-summary", action="append", default=[])
    parser.add_argument("--prior-setup-summary", action="append", default=[])
    return parser.parse_args()


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _output_root(campaign_id: str) -> Path:
    return REPO_ROOT / "artifacts" / "session" / campaign_id / ANALYZER_KIND


def _resolve_path(raw_path: str | Path) -> Path:
    path = Path(str(raw_path or "").strip())
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


def _artifact_display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


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
    return round(numeric, 6) if numeric is not None else None


def _boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        clean = value.strip().lower()
        if clean in {"true", "1", "yes"}:
            return True
        if clean in {"false", "0", "no"}:
            return False
    return None


def _layout_id(*parts: Any) -> str:
    text = " ".join(_clean_text(part).replace("\\", "/").lower() for part in parts if _clean_text(part))
    for marker in ("right05", "left05", "zero", "centerline", "plus45", "minus45", "backside180"):
        if marker in text:
            return "zero" if marker == "centerline" else marker
    return ""


def _text_contains(values: list[Any], *needles: str) -> bool:
    text = " ".join(_clean_text(value).lower() for value in values if value is not None)
    return any(needle.lower() in text for needle in needles)


def _load_summary_path(raw_path: str) -> tuple[Path, dict[str, Any]] | None:
    if not _clean_text(raw_path):
        return None
    path = _resolve_path(raw_path)
    if not path.is_file():
        return None
    payload = read_json(path)
    if not isinstance(payload, dict):
        return None
    return path, payload


def _summary_paths_from_gate(path: Path, payload: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for result in _list(payload.get("results")):
        if isinstance(result, dict) and _clean_text(result.get("summary_path")):
            paths.append(_clean_text(result.get("summary_path")))
    return paths


def _summary_paths_from_nav2(path: Path, payload: dict[str, Any]) -> list[tuple[str, str]]:
    paths: list[tuple[str, str]] = []
    for candidate in _list(payload.get("candidate_families")):
        if not isinstance(candidate, dict):
            continue
        for evidence_type in ("one_run_results", "promotion_results"):
            for result in _list(candidate.get(evidence_type)):
                if isinstance(result, dict) and _clean_text(result.get("summary_path")):
                    paths.append((evidence_type, _clean_text(result.get("summary_path"))))
    return paths


def _run_payloads(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [run for run in _list(summary.get("runs")) if isinstance(run, dict)]


def _shot(run: dict[str, Any]) -> dict[str, Any]:
    return _dict(run.get("shot_outcome") or _dict(run.get("mission_verdict")).get("shot_outcome"))


def _failure_reasons(summary: dict[str, Any], runs: list[dict[str, Any]]) -> list[str]:
    reasons = [_clean_text(reason) for reason in _list(summary.get("fetch_to_pose_failure_reasons"))]
    for run in runs:
        reason = _clean_text(run.get("fetch_to_pose_failure_reason") or _shot(run).get("reason"))
        if reason and reason not in {"trajectory_intersects_delivery_radius", "none"}:
            reasons.append(reason)
    return sorted({reason for reason in reasons if reason})


def _closest_values(runs: list[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for run in runs:
        shot = _shot(run)
        for key in ("closest_approach_distance_m", "distance_to_fetch_pose_m"):
            value = _finite_float(shot.get(key))
            if value is not None:
                values.append(value)
                break
    return values


def _summary_metrics(path: Path, summary: dict[str, Any], *, source_id: str, evidence_type: str) -> dict[str, Any]:
    runs = _run_payloads(summary)
    run_count = len(runs)
    pass_count = _finite_float(summary.get("fetch_to_pose_pass_count"))
    if pass_count is None:
        pass_count = sum(1 for run in runs if bool(run.get("fetch_to_pose_pass", False)))
    fail_count = _finite_float(summary.get("fetch_to_pose_fail_count"))
    if fail_count is None and run_count:
        fail_count = max(0, run_count - int(pass_count or 0))
    reasons = _failure_reasons(summary, runs)
    closest = _closest_values(runs)
    campaign_id = _clean_text(summary.get("campaign_id"))
    layout = _layout_id(
        summary.get("requested_target_layout_json"),
        campaign_id,
        path,
        *[run.get("requested_target_layout_json") for run in runs],
    )
    model_valid = _boolish(summary.get("model_provenance_valid"))
    if model_valid is None:
        model_valid = all(_boolish(run.get("model_provenance_valid")) is not False for run in runs)
    capture_entry_pass = _finite_float(summary.get("fresh_attempt_capture_entry_pass_count"))
    if capture_entry_pass is None and run_count:
        capture_entry_pass = sum(1 for run in runs if bool(run.get("capture_entry_reached", False)))
    pre_stage_handoff = _finite_float(summary.get("fresh_attempt_pre_stage_handoff_pass_count"))
    if pre_stage_handoff is None and run_count:
        pre_stage_handoff = sum(1 for run in runs if bool(run.get("pre_stage_handoff_pass", False)))
    alignment_max = _finite_float(summary.get("fresh_attempt_first_contact_push_alignment_max_deg"))
    if alignment_max is None:
        alignment_values = [_finite_float(run.get("first_contact_push_alignment_deg")) for run in runs]
        alignment_values = [value for value in alignment_values if value is not None]
        alignment_max = max(alignment_values) if alignment_values else None
    goal_side_count = _finite_float(summary.get("entered_goal_side_before_capture_count")) or 0
    session_ids = []
    for run in runs:
        session_id = _clean_text(run.get("session_id") or _dict(run.get("mission_verdict")).get("session_id"))
        if session_id and session_id not in session_ids:
            session_ids.append(session_id)
    return {
        "source_id": source_id,
        "evidence_type": evidence_type,
        "campaign_id": campaign_id,
        "layout": layout,
        "summary_path": _artifact_display_path(path),
        "run_count": int(run_count),
        "pass_count": int(pass_count or 0),
        "fail_count": int(fail_count or 0),
        "delivery_pass": bool(run_count and int(pass_count or 0) == run_count and not reasons),
        "failure_reasons": reasons,
        "closest_approach_best_m": _round_or_none(min(closest) if closest else None),
        "closest_approach_worst_m": _round_or_none(max(closest) if closest else None),
        "model_provenance_valid": bool(model_valid),
        "capture_entry_pass_count": int(capture_entry_pass or 0),
        "pre_stage_handoff_pass_count": int(pre_stage_handoff or 0),
        "first_contact_alignment_max_deg": _round_or_none(alignment_max),
        "entered_goal_side_before_capture_count": int(goal_side_count),
        "session_ids": session_ids,
    }


def _video_links(session_ids: list[str], dashboard_base_url: str) -> list[dict[str, str]]:
    base = dashboard_base_url.rstrip("/")
    links: list[dict[str, str]] = []
    for session_id in session_ids:
        visual_dir = REPO_ROOT / "artifacts" / "session" / session_id / "visual"
        for name in VIDEO_NAMES:
            path = visual_dir / name
            if not path.is_file():
                continue
            rel = _artifact_display_path(path)
            href = f"{base}/{rel}" if base else f"/{rel}"
            links.append({"session_id": session_id, "name": name, "path": rel, "href": href})
    return links


def _color_row(
    *,
    source_id: str,
    source_label: str,
    evidence_type: str,
    layout: str,
    stage: str,
    color: str,
    rationale: str,
    summary_path: str,
    metrics: dict[str, Any],
    quality_flags: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "source_label": source_label,
        "evidence_type": evidence_type,
        "layout": layout,
        "stage": stage,
        "color": color,
        "rationale": rationale,
        "summary_path": summary_path,
        "closest_approach_worst_m": metrics.get("closest_approach_worst_m"),
        "pass_count": metrics.get("pass_count"),
        "run_count": metrics.get("run_count"),
        "failure_reasons": list(metrics.get("failure_reasons") or []),
        "quality_flags": list(quality_flags or []),
    }


def _mission_stage_rows(metrics: dict[str, Any], *, source_label: str, stale_reason: str = "") -> list[dict[str, Any]]:
    source_id = _clean_text(metrics.get("source_id"))
    evidence_type = _clean_text(metrics.get("evidence_type"))
    layout = _clean_text(metrics.get("layout"))
    path = _clean_text(metrics.get("summary_path"))
    reasons = list(metrics.get("failure_reasons") or [])
    run_count = int(metrics.get("run_count") or 0)
    pass_count = int(metrics.get("pass_count") or 0)
    worst = _finite_float(metrics.get("closest_approach_worst_m"))
    rows: list[dict[str, Any]] = []
    if stale_reason:
        for stage in ("setup_pre_capture", "capture_entry", "first_contact", "push_coast", "terminal_delivery", "visual_clarity"):
            rows.append(
                _color_row(
                    source_id=source_id,
                    source_label=source_label,
                    evidence_type=evidence_type,
                    layout=layout,
                    stage=stage,
                    color="stale",
                    rationale=stale_reason,
                    summary_path=path,
                    metrics=metrics,
                )
            )
        return rows

    setup_red = _text_contains(reasons, "capture_entry_timeout", "pre_stage", "handoff", "goal_side")
    capture_red = _text_contains(reasons, "capture_entry_timeout", "capture_entry")
    first_contact_red = _text_contains(reasons, "first_contact", "no_object_motion", "missing_first_contact")
    push_red = _text_contains(reasons, "ball_escape", "knock_away", "roll_away", "lateral")
    terminal_red = bool(reasons) and _text_contains(reasons, "missed_delivery_radius", "stopped_short", "timeout")

    setup_green = run_count > 0 and int(metrics.get("pre_stage_handoff_pass_count") or 0) >= run_count and not setup_red
    capture_green = run_count > 0 and int(metrics.get("capture_entry_pass_count") or 0) >= run_count and not capture_red
    delivery_green = run_count > 0 and pass_count == run_count and not reasons
    margin_yellow = worst is not None and DELIVERY_RADIUS_M >= worst > TIGHT_DELIVERY_MARGIN_M
    alignment = _finite_float(metrics.get("first_contact_alignment_max_deg"))
    contact_yellow = alignment is not None and alignment > 12.0

    def add(stage: str, color: str, rationale: str, flags: list[str] | None = None) -> None:
        rows.append(
            _color_row(
                source_id=source_id,
                source_label=source_label,
                evidence_type=evidence_type,
                layout=layout,
                stage=stage,
                color=color,
                rationale=rationale,
                summary_path=path,
                metrics=metrics,
                quality_flags=flags,
            )
        )

    if setup_red:
        add("setup_pre_capture", "red", "setup or pre-capture failure reason blocks this stage")
    elif setup_green:
        add("setup_pre_capture", "green", "pre-stage handoff is green in this summary")
    else:
        add("setup_pre_capture", "yellow", "setup evidence is partial or inferred from delivery")

    if capture_red:
        add("capture_entry", "red", "capture-entry failure reason blocks this stage")
    elif capture_green:
        add("capture_entry", "green", "capture entry is reached across the summary")
    else:
        add("capture_entry", "yellow", "capture-entry evidence is partial or inferred")

    if first_contact_red:
        add("first_contact", "red", "first-contact failure reason blocks this stage")
    elif delivery_green and not contact_yellow:
        add("first_contact", "green", "delivery passed without first-contact watch flags")
    elif delivery_green:
        add("first_contact", "yellow", "delivery passed with first-contact margin or alignment watch")
    else:
        add("first_contact", "yellow", "first-contact evidence is incomplete for this source")

    if push_red:
        add("push_coast", "red", "push/coast failure reason blocks this stage")
    elif delivery_green and not margin_yellow:
        add("push_coast", "green", "delivery passed with comfortable margin")
    elif delivery_green:
        add("push_coast", "yellow", "delivery passed close to the delivery-radius boundary")
    elif terminal_red and not push_red:
        add("push_coast", "yellow", "object moved but terminal delivery failed or timed out")
    else:
        add("push_coast", "yellow", "push/coast evidence is incomplete for this source")

    if delivery_green and not margin_yellow:
        add("terminal_delivery", "green", "delivery passed with comfortable margin")
    elif delivery_green:
        add("terminal_delivery", "yellow", "delivery passed near the contract boundary")
    else:
        add("terminal_delivery", "red", "delivery failed for this summary")

    visual_color = "green" if metrics.get("video_count", 0) else "yellow"
    visual_reason = "representative same-session videos were found" if visual_color == "green" else "video package is missing or incomplete"
    add("visual_clarity", visual_color, visual_reason)
    return rows


def _audit_rows(path: Path, payload: dict[str, Any], *, source_id: str, source_label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for anchor in _list(payload.get("saved_anchors")):
        if not isinstance(anchor, dict):
            continue
        metrics = {
            "source_id": source_id,
            "evidence_type": "stage_audit",
            "layout": _clean_text(anchor.get("layout")),
            "summary_path": _artifact_display_path(_resolve_path(anchor.get("summary_path") or path)),
            "run_count": len(_list(anchor.get("run_stage_quality"))) or 1,
            "pass_count": 1 if bool(anchor.get("delivery_pass", False)) else 0,
            "failure_reasons": list(anchor.get("failure_reasons") or []),
            "closest_approach_worst_m": _round_or_none(anchor.get("closest_approach_distance_m")),
        }
        flags = [_clean_text(flag) for flag in _list(anchor.get("quality_flags")) if _clean_text(flag)]
        classification = _clean_text(anchor.get("quality_classification"))
        reasons = list(metrics["failure_reasons"])
        stage_labels = [_clean_text(label) for label in _list(anchor.get("stage_labels"))]
        setup_blocked = classification == "setup_capture_blocker" or "setup" in stage_labels or _text_contains(reasons, "capture_entry_timeout")
        first_blocked = classification == "first_contact_blocker" or "first_contact" in stage_labels
        push_blocked = classification == "push_coast_blocker" or "push_coast" in stage_labels
        terminal_candidate = _clean_text(anchor.get("interpretation")) == "guarded_live_terminal_candidate"
        delivery_pass = bool(anchor.get("delivery_pass", False))
        pass_with_watch = classification.startswith("pass_with") or "watch" in classification or bool(flags)

        def add(stage: str, color: str, rationale: str) -> None:
            rows.append(
                _color_row(
                    source_id=source_id,
                    source_label=source_label,
                    evidence_type="stage_audit",
                    layout=_clean_text(anchor.get("layout")),
                    stage=stage,
                    color=color,
                    rationale=rationale,
                    summary_path=metrics["summary_path"],
                    metrics=metrics,
                    quality_flags=flags,
                )
            )

        add("setup_pre_capture", "red" if setup_blocked else "green", classification or "audit setup classification")
        add("capture_entry", "red" if setup_blocked else "green", classification or "audit capture classification")
        add("first_contact", "red" if first_blocked else "yellow" if pass_with_watch else "green", classification or "audit first-contact classification")
        add("push_coast", "red" if push_blocked else "yellow" if pass_with_watch else "green", classification or "audit push/coast classification")
        if delivery_pass and not pass_with_watch:
            add("terminal_delivery", "green", "audit delivery pass")
        elif delivery_pass:
            add("terminal_delivery", "yellow", classification or "audit delivery pass with watch")
        elif terminal_candidate:
            add("terminal_delivery", "yellow", "near-contract terminal correction candidate")
        else:
            add("terminal_delivery", "red", classification or "audit delivery failure")
    return rows


def _planner_rows(path: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = {
        "source_id": "planner_handoff",
        "evidence_type": "planner_gate",
        "layout": "mixed_fetch_planner_v1",
        "summary_path": _artifact_display_path(path),
        "run_count": int(payload.get("random_cases") or len(_list(payload.get("results"))) or 0),
        "pass_count": int(payload.get("pass_count") or 0),
        "failure_reasons": [] if bool(payload.get("pass", False)) else ["planner_handoff_gate_failed"],
        "closest_approach_worst_m": None,
    }
    color = "green" if bool(payload.get("pass", False)) and int(payload.get("wrong_fetch_dispatch_count") or 0) == 0 else "red"
    rationale = "planner gate routed mixed scenes without wrong local fetch dispatch" if color == "green" else "planner gate dispatched at least one wrong local fetch"
    return [
        _color_row(
            source_id="planner_handoff",
            source_label="Planner handoff gate",
            evidence_type="planner_gate",
            layout="mixed_fetch_planner_v1",
            stage="planner_handoff",
            color=color,
            rationale=rationale,
            summary_path=_artifact_display_path(path),
            metrics=metrics,
        )
    ]


def _add_mission_source(
    *,
    rows: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    raw_path: str,
    source_id: str,
    source_label: str,
    evidence_type: str,
    dashboard_base_url: str,
    stale_reason: str = "",
) -> None:
    loaded = _load_summary_path(raw_path)
    if not loaded:
        return
    path, payload = loaded
    metrics = _summary_metrics(path, payload, source_id=source_id, evidence_type=evidence_type)
    videos = _video_links(list(metrics.get("session_ids") or []), dashboard_base_url)
    metrics["video_count"] = len(videos)
    summaries.append({**metrics, "source_label": source_label, "videos": videos})
    rows.extend(_mission_stage_rows(metrics, source_label=source_label, stale_reason=stale_reason))


def _source_stage_rollups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        stage = _clean_text(row.get("stage"))
        source_id = _clean_text(row.get("source_id"))
        if stage in STAGES and source_id:
            grouped.setdefault((stage, source_id), []).append(row)
    rollups: list[dict[str, Any]] = []
    for (stage, source_id), source_rows in grouped.items():
        colors = [_clean_text(row.get("color")) for row in source_rows]
        if "red" in colors:
            color = "red"
        elif "yellow" in colors:
            color = "yellow"
        elif "green" in colors:
            color = "green"
        else:
            color = "stale"
        layouts = sorted({_clean_text(row.get("layout")) for row in source_rows if _clean_text(row.get("layout"))})
        red_layouts = sorted({_clean_text(row.get("layout")) for row in source_rows if row.get("color") == "red" and _clean_text(row.get("layout"))})
        yellow_layouts = sorted({_clean_text(row.get("layout")) for row in source_rows if row.get("color") == "yellow" and _clean_text(row.get("layout"))})
        representative = next((row for row in source_rows if row.get("color") == color), source_rows[0])
        if red_layouts:
            rationale = f"source has red evidence on {', '.join(red_layouts)}"
        elif yellow_layouts:
            rationale = f"source has watch/borderline evidence on {', '.join(yellow_layouts)}"
        else:
            rationale = _clean_text(representative.get("rationale"))
        if source_id == "corrected_direct_reference" and color == "green" and len(layouts) < 3:
            color = "yellow"
            rationale = "single-layout corrected direct reference; use as gap evidence, not broad owner proof"
        rollups.append(
            {
                "stage": stage,
                "source_id": source_id,
                "source_label": _clean_text(representative.get("source_label") or source_id),
                "color": color,
                "layouts": layouts,
                "red_layouts": red_layouts,
                "yellow_layouts": yellow_layouts,
                "rationale": rationale,
                "row_count": len(source_rows),
            }
        )
    return rollups


def _stage_verdicts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rollups = _source_stage_rollups(rows)
    verdicts: list[dict[str, Any]] = []
    for stage in STAGES:
        stage_rollups = [rollup for rollup in rollups if rollup.get("stage") == stage]
        if not stage_rollups:
            continue
        leader = max(
            stage_rollups,
            key=lambda rollup: (
                COLOR_RANK.get(_clean_text(rollup.get("color")), 0),
                SOURCE_PRIORITY.get(_clean_text(rollup.get("source_id")), 0),
            ),
        )
        stage_rows = [row for row in rows if row.get("stage") == stage]
        counts = {color: sum(1 for row in stage_rows if row.get("color") == color) for color in ("green", "yellow", "red", "stale")}
        verdicts.append(
            {
                "stage": stage,
                "recommended_owner": _clean_text(leader.get("source_label") or leader.get("source_id")),
                "color": _clean_text(leader.get("color")),
                "rationale": _clean_text(leader.get("rationale")),
                "source_id": _clean_text(leader.get("source_id")),
                "layouts": list(leader.get("layouts") or []),
                "evidence_counts": counts,
                "source_stage_rollups": stage_rollups,
            }
        )
    return verdicts


def _recommended_next_action(rows: list[dict[str, Any]], stage_verdicts: list[dict[str, Any]]) -> dict[str, Any]:
    current_red_setup = any(
        row.get("source_id") == "current_staged_nav2_contact_buffer"
        and row.get("color") == "red"
        and row.get("stage") in {"setup_pre_capture", "capture_entry"}
        for row in rows
    )
    prior_green_setup = any(
        row.get("source_id") in {"object_centric_may27", "corrected_direct_reference", "prior_setup_acquisition"}
        and row.get("color") == "green"
        and row.get("stage") in {"setup_pre_capture", "capture_entry"}
        for row in rows
    )
    terminal_red_only = any(row.get("stage") == "terminal_delivery" and row.get("color") == "red" for row in rows) and not current_red_setup
    if current_red_setup and prior_green_setup:
        return {
            "action": "run_setup_capture_gap_fill_or_port_prior_behavior",
            "rationale": "current staged baseline has setup/capture red evidence while prior/direct evidence has green setup or capture behavior",
        }
    if current_red_setup:
        return {
            "action": "collect_setup_capture_gap_fill_probe_before_fix",
            "rationale": "current staged baseline is blocked in setup/capture and comparison lacks a clean prior owner",
        }
    if terminal_red_only:
        return {
            "action": "prepare_guarded_terminal_correction_probe",
            "rationale": "comparison points to terminal delivery as the remaining blocker",
        }
    if stage_verdicts and all(verdict.get("color") in {"green", "yellow"} for verdict in stage_verdicts):
        return {
            "action": "rerun_saved_layout_repeatability",
            "rationale": "stage comparison has no red winner and can advance to repeatability evidence",
        }
    return {
        "action": "fill_missing_stage_evidence",
        "rationale": "comparison has stale or missing lifecycle-stage evidence",
    }


def summarize_comparison(
    *,
    campaign_id: str,
    dashboard_base_url: str,
    planner_gate_summary: str = "",
    current_saved_anchor_summaries: list[str] | None = None,
    current_stage_audit: str = "",
    object_centric_gate_summary: str = "",
    nav2_corridor_summary: str = "",
    corrected_direct_summaries: list[str] | None = None,
    prior_setup_summaries: list[str] | None = None,
) -> dict[str, Any]:
    clean_campaign_id = campaign_id.strip() or f"fetch_stage_owner_comparison_{current_utc_stamp()}"
    rows: list[dict[str, Any]] = []
    source_summaries: list[dict[str, Any]] = []

    loaded_planner = _load_summary_path(planner_gate_summary)
    if loaded_planner:
        rows.extend(_planner_rows(*loaded_planner))

    for raw_path in current_saved_anchor_summaries or []:
        _add_mission_source(
            rows=rows,
            summaries=source_summaries,
            raw_path=raw_path,
            source_id="current_staged_nav2_contact_buffer",
            source_label="Current staged Nav2/contact-buffer",
            evidence_type="saved_anchor_one_run",
            dashboard_base_url=dashboard_base_url,
        )

    loaded_audit = _load_summary_path(current_stage_audit)
    if loaded_audit:
        rows.extend(
            _audit_rows(
                loaded_audit[0],
                loaded_audit[1],
                source_id="current_staged_nav2_contact_buffer",
                source_label="Current staged Nav2/contact-buffer",
            )
        )

    loaded_object = _load_summary_path(object_centric_gate_summary)
    if loaded_object:
        gate_path, gate_payload = loaded_object
        for summary_path in _summary_paths_from_gate(gate_path, gate_payload):
            _add_mission_source(
                rows=rows,
                summaries=source_summaries,
                raw_path=summary_path,
                source_id="object_centric_may27",
                source_label="May 27 object-centric fetch",
                evidence_type="calibrated_gate_child",
                dashboard_base_url=dashboard_base_url,
            )

    loaded_nav2 = _load_summary_path(nav2_corridor_summary)
    if loaded_nav2:
        nav2_path, nav2_payload = loaded_nav2
        for evidence_type, summary_path in _summary_paths_from_nav2(nav2_path, nav2_payload):
            _add_mission_source(
                rows=rows,
                summaries=source_summaries,
                raw_path=summary_path,
                source_id="nav2_corridor_push",
                source_label="Nav2 corridor-push",
                evidence_type=f"nav2_corridor_{evidence_type}",
                dashboard_base_url=dashboard_base_url,
            )

    for raw_path in corrected_direct_summaries or []:
        _add_mission_source(
            rows=rows,
            summaries=source_summaries,
            raw_path=raw_path,
            source_id="corrected_direct_reference",
            source_label="Corrected direct reference",
            evidence_type="corrected_direct_one_run",
            dashboard_base_url=dashboard_base_url,
        )

    for raw_path in prior_setup_summaries or []:
        _add_mission_source(
            rows=rows,
            summaries=source_summaries,
            raw_path=raw_path,
            source_id="prior_setup_acquisition",
            source_label="Prior setup/acquisition evidence",
            evidence_type="historical_setup_reference",
            dashboard_base_url=dashboard_base_url,
            stale_reason="historical setup evidence; use for comparison only",
        )

    stage_verdicts = _stage_verdicts(rows)
    recommendation = _recommended_next_action(rows, stage_verdicts)
    representative_videos: list[dict[str, str]] = []
    seen_videos: set[str] = set()
    for source in source_summaries:
        for video in _list(source.get("videos")):
            if isinstance(video, dict) and video.get("href") not in seen_videos:
                seen_videos.add(str(video.get("href")))
                representative_videos.append(video)
    summary = {
        "type": ANALYZER_KIND,
        "campaign_id": clean_campaign_id,
        "generated_utc": utc_now(),
        "dashboard_base_url": dashboard_base_url,
        "recommended_next_action": recommendation,
        "stage_verdicts": stage_verdicts,
        "stage_rows": rows,
        "source_summaries": source_summaries,
        "representative_videos": representative_videos[:16],
    }
    output_root = _output_root(clean_campaign_id)
    ensure_dir(output_root)
    write_json(output_root / "stage_owner_summary.json", summary)
    write_scorecard(output_root / "scorecard.md", summary)
    return summary


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.3f}"
    return _clean_text(value)


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    recommendation = _dict(summary.get("recommended_next_action"))
    lines = [
        "# Fetch Stage-Owner Comparison",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- recommended_next_action: `{recommendation.get('action', '')}`",
        f"- rationale: {recommendation.get('rationale', '')}",
        "",
        "## Stage Verdicts",
        "",
        "| stage | recommended owner | color | evidence counts | rationale |",
        "| --- | --- | --- | --- | --- |",
    ]
    for verdict in _list(summary.get("stage_verdicts")):
        if not isinstance(verdict, dict):
            continue
        counts = ", ".join(f"{key}:{value}" for key, value in _dict(verdict.get("evidence_counts")).items())
        lines.append(
            f"| `{verdict.get('stage', '')}` | {verdict.get('recommended_owner', '')} | `{verdict.get('color', '')}` | "
            f"{counts} | {verdict.get('rationale', '')} |"
        )
    lines.extend(
        [
            "",
            "## Evidence Rows",
            "",
            "| source | layout | stage | color | closest | reasons | artifact |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in _list(summary.get("stage_rows")):
        if not isinstance(row, dict):
            continue
        reasons = ", ".join(str(reason) for reason in _list(row.get("failure_reasons"))) or ""
        artifact = _clean_text(row.get("summary_path"))
        lines.append(
            f"| {row.get('source_label', row.get('source_id', ''))} | `{row.get('layout', '')}` | "
            f"`{row.get('stage', '')}` | `{row.get('color', '')}` | `{_fmt(row.get('closest_approach_worst_m'))}` | "
            f"{reasons} | {artifact} |"
        )
    lines.extend(["", "## Representative Videos", ""])
    videos = _list(summary.get("representative_videos"))
    if not videos:
        lines.append("- No representative videos found from supplied summaries.")
    for video in videos:
        if not isinstance(video, dict):
            continue
        label = _clean_text(video.get("name"))
        href = _clean_text(video.get("href"))
        session_id = _clean_text(video.get("session_id"))
        lines.append(f"- [{label}]({href}) session `{session_id}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    summary = summarize_comparison(
        campaign_id=args.campaign_id,
        dashboard_base_url=args.dashboard_base_url,
        planner_gate_summary=args.planner_gate_summary,
        current_saved_anchor_summaries=list(args.current_saved_anchor_summary),
        current_stage_audit=args.current_stage_audit,
        object_centric_gate_summary=args.object_centric_gate_summary,
        nav2_corridor_summary=args.nav2_corridor_summary,
        corrected_direct_summaries=list(args.corrected_direct_summary),
        prior_setup_summaries=list(args.prior_setup_summary),
    )
    output_root = _output_root(str(summary.get("campaign_id", "")))
    print(f"FETCH_STAGE_OWNER_SUMMARY={output_root / 'stage_owner_summary.json'}")
    print(f"FETCH_STAGE_OWNER_SCORECARD={output_root / 'scorecard.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
