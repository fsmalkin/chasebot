#!/usr/bin/env python3
"""Audit saved-anchor fetch runs for setup/contact versus terminal failures."""

from __future__ import annotations

import argparse
import json
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
PRE_CONTACT_BALL_MOTION_LIMIT_M = 0.030
PRE_STAGE_YAW_WATCH_DEG = 270.0
PRE_STAGE_TIME_WATCH_S = 18.0
CAPTURE_ENTRY_TIME_WATCH_S = 4.0
FIRST_CONTACT_ALIGNMENT_WATCH_DEG = 12.0
FIRST_CONTACT_ALIGNMENT_LIMIT_DEG = 30.0
PRE_CONTACT_PHASES = {"pre_stage", "stage", "capture_entry"}
BLOCKING_QUALITY_CLASSIFICATIONS = {
    "invalid_geometry",
    "invalid_model_provenance",
    "setup_capture_blocker",
    "first_contact_blocker",
    "push_coast_blocker",
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


def _parse_utc(value: Any) -> datetime | None:
    text = _clean_text(value)
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _angle_delta_rad(current: float, previous: float) -> float:
    delta = current - previous
    while delta > math.pi:
        delta -= 2.0 * math.pi
    while delta < -math.pi:
        delta += 2.0 * math.pi
    return delta


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if not clean:
            continue
        try:
            payload = json.loads(clean)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _run_state_history_path(run: dict[str, Any]) -> Path | None:
    candidates = [
        run.get("state_history_path"),
        _dict(run.get("mission_verdict")).get("state_history_path"),
    ]
    mission_root = _clean_text(run.get("mission_root") or _dict(run.get("mission_verdict")).get("mission_root"))
    if mission_root:
        candidates.append(str(Path(mission_root) / "state_history.jsonl"))
    for raw_path in candidates:
        text = _clean_text(raw_path)
        if not text:
            continue
        path = _resolve_path(text)
        if path.is_file():
            return path
    return None


def _xy_pose(value: Any) -> tuple[float, float] | None:
    payload = _dict(value)
    x_value = _finite_float(payload.get("x"))
    y_value = _finite_float(payload.get("y"))
    if x_value is None or y_value is None:
        return None
    return float(x_value), float(y_value)


def _metric_max(values: list[float | None]) -> float | None:
    finite = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return max(finite) if finite else None


def _metric_min_abs(values: list[float | None]) -> float | None:
    finite = [abs(float(value)) for value in values if value is not None and math.isfinite(float(value))]
    return min(finite) if finite else None


def _state_history_stage_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pre_stage_rows = [row for row in rows if _clean_text(row.get("phase")) == "pre_stage"]
    pre_contact_rows = [row for row in rows if _clean_text(row.get("phase")) in PRE_CONTACT_PHASES]
    capture_entry_rows = [row for row in rows if _clean_text(row.get("phase")) == "capture_entry"]

    yaw_values: list[float] = []
    for row in pre_stage_rows:
        yaw = _finite_float(_dict(row.get("robot_pose")).get("yaw"))
        if yaw is not None:
            yaw_values.append(float(yaw))
    yaw_delta = 0.0
    for index in range(1, len(yaw_values)):
        yaw_delta += abs(_angle_delta_rad(yaw_values[index], yaw_values[index - 1]))

    modes: list[str] = []
    for row in pre_stage_rows:
        mode = _clean_text(_dict(row.get("selected_command")).get("mode"))
        if mode:
            modes.append(mode)
    mode_transition_count = 0
    for index in range(1, len(modes)):
        if modes[index] != modes[index - 1]:
            mode_transition_count += 1

    ball_start = None
    ball_motion_max = 0.0
    for row in pre_contact_rows:
        ball_xy = _xy_pose(row.get("ball_pose"))
        if ball_xy is None:
            continue
        if ball_start is None:
            ball_start = ball_xy
        ball_motion_max = max(ball_motion_max, math.hypot(ball_xy[0] - ball_start[0], ball_xy[1] - ball_start[1]))

    capture_snapshots = [
        _dict(row.get("capture"))
        for row in capture_entry_rows
        if isinstance(row.get("capture"), dict)
    ]
    capture_diagnostics = [
        _dict(row.get("capture_entry_diagnostics"))
        for row in capture_entry_rows
        if isinstance(row.get("capture_entry_diagnostics"), dict)
    ]
    ready_observed = any(
        bool(_dict(row.get("capture_entry")).get("capture_entry_reached", False))
        or bool(_dict(row.get("capture_entry_diagnostics")).get("ready_reached_once", False))
        for row in capture_entry_rows
    )
    final_capture = capture_snapshots[-1] if capture_snapshots else {}
    if not final_capture and capture_diagnostics:
        final_capture = _dict(capture_diagnostics[-1].get("capture_entry_snapshot"))

    return {
        "state_history_rows": len(rows),
        "pre_stage_row_count": len(pre_stage_rows),
        "capture_entry_row_count": len(capture_entry_rows),
        "pre_stage_yaw_travel_deg": round(math.degrees(yaw_delta), 6),
        "pre_stage_mode_count": len(set(modes)),
        "pre_stage_mode_transition_count": mode_transition_count,
        "pre_stage_command_modes": sorted(set(modes)),
        "ball_pre_contact_motion_m": round(ball_motion_max, 6) if ball_start is not None else None,
        "capture_entry_ready_observed": bool(ready_observed),
        "capture_entry_final_ball_x_m": _round_or_none(final_capture.get("ball_x_m")),
        "capture_entry_final_ball_y_m": _round_or_none(final_capture.get("ball_y_m")),
        "capture_entry_final_bearing_rad": _round_or_none(final_capture.get("bearing_rad")),
        "capture_entry_min_abs_ball_y_m": _round_or_none(
            _metric_min_abs([_finite_float(item.get("ball_y_m")) for item in capture_snapshots])
        ),
        "capture_entry_min_abs_bearing_rad": _round_or_none(
            _metric_min_abs([_finite_float(item.get("bearing_rad")) for item in capture_snapshots])
        ),
    }


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


def _geometry_consistency(run: dict[str, Any]) -> dict[str, Any]:
    for payload in _payload_candidates(run):
        geometry = _dict(payload.get("geometry_consistency"))
        if geometry:
            return geometry
    return {}


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


def _model_provenance(summary: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    candidates = [summary]
    candidates.extend(_payload_candidates(run))
    for payload in candidates:
        provenance = _model_provenance_from_payload(payload)
        if provenance:
            return provenance
    return {
        "model_provenance_valid": False,
        "model_provenance_reason": "missing_model_provenance",
        "model_provenance_required": True,
    }


def _run_approach(run: dict[str, Any]) -> dict[str, Any]:
    for key in ("fresh_attempt_approach", "latest_approach_progress"):
        payload = _dict(run.get(key)) or _dict(_dict(run.get("mission_verdict")).get(key))
        if payload:
            return payload
    return {}


def _capture_entry_payload(run: dict[str, Any]) -> dict[str, Any]:
    approach = _run_approach(run)
    capture_entry = _dict(approach.get("capture_entry"))
    if capture_entry:
        return capture_entry
    mission_verdict = _dict(run.get("mission_verdict"))
    return _dict(mission_verdict.get("capture_entry")) or {
        "reached": mission_verdict.get("capture_entry_reached"),
        "time_s": mission_verdict.get("capture_entry_time_s"),
        "failure_reason": mission_verdict.get("approach_failure_reason"),
    }


def _pre_stage_payload(run: dict[str, Any]) -> dict[str, Any]:
    approach = _run_approach(run)
    pre_stage = _dict(approach.get("pre_stage"))
    if pre_stage:
        return pre_stage
    mission_verdict = _dict(run.get("mission_verdict"))
    return {
        "handoff_pass": mission_verdict.get("pre_stage_handoff_pass"),
        "pose_reached": mission_verdict.get("pre_stage_pose_reached"),
        "time_s": mission_verdict.get("pre_stage_time_s"),
    }


def _run_stage_metrics(run: dict[str, Any]) -> dict[str, Any]:
    state_history_path = _run_state_history_path(run)
    rows = _read_jsonl(state_history_path) if state_history_path else []
    state_metrics = _state_history_stage_metrics(rows)
    pre_stage = _pre_stage_payload(run)
    capture_entry = _capture_entry_payload(run)
    geometry = _geometry_consistency(run)
    pre_stage_time_s = (
        _finite_float(pre_stage.get("time_s"))
        or _finite_float(run.get("pre_stage_time_s"))
        or _finite_float(_dict(run.get("mission_verdict")).get("pre_stage_time_s"))
    )
    capture_entry_time_s = (
        _finite_float(capture_entry.get("time_s"))
        or _finite_float(run.get("capture_entry_time_s"))
        or _finite_float(_dict(run.get("mission_verdict")).get("capture_entry_time_s"))
    )
    capture_entry_reached = _boolish(capture_entry.get("reached"))
    if capture_entry_reached is None:
        capture_entry_reached = _boolish(run.get("capture_entry_reached"))
    if capture_entry_reached is None:
        capture_entry_reached = _boolish(_dict(run.get("mission_verdict")).get("capture_entry_reached"))
    first_contact_alignment = _finite_float(run.get("first_contact_push_alignment_deg"))
    if first_contact_alignment is None:
        first_contact_alignment = _finite_float(capture_entry.get("first_contact_push_alignment_deg"))
    return {
        "state_history_path": str(state_history_path) if state_history_path else "",
        "pre_stage_time_s": _round_or_none(pre_stage_time_s),
        "capture_entry_time_s": _round_or_none(capture_entry_time_s),
        "capture_entry_reached": bool(capture_entry_reached),
        "capture_entry_failure_reason": _clean_text(capture_entry.get("failure_reason"))
        or _clean_text(run.get("approach_failure_reason"))
        or _clean_text(_dict(run.get("mission_verdict")).get("approach_failure_reason")),
        "pre_stage_handoff_pass": bool(pre_stage.get("handoff_pass", run.get("pre_stage_handoff_pass", False))),
        "pre_stage_pose_reached": bool(pre_stage.get("pose_reached", run.get("pre_stage_pose_reached", False))),
        "first_contact_push_alignment_deg": _round_or_none(first_contact_alignment),
        "geometry_consistency_pass": bool(geometry.get("pass", True)) if geometry else True,
        "geometry_consistency_reason": _clean_text(geometry.get("reason")),
        **state_metrics,
    }


def _quality_flags(metrics: dict[str, Any], failure_reasons: list[str]) -> list[str]:
    flags: list[str] = []

    def add(flag: str) -> None:
        if flag not in flags:
            flags.append(flag)

    if not bool(metrics.get("geometry_consistency_pass", True)):
        add("invalid_geometry")
    if metrics.get("model_provenance_valid") is False:
        add("invalid_model_provenance")
    failure_text = " ".join(reason.lower() for reason in failure_reasons)
    if "capture_entry_timeout" in failure_text or "pre_stage" in failure_text or "handoff" in failure_text:
        add("setup_capture_blocker")
    if metrics.get("capture_entry_reached") is False and (
        _clean_text(metrics.get("capture_entry_failure_reason")) or "capture_entry_timeout" in failure_text
    ):
        add("setup_capture_blocker")
    ball_motion = _finite_float(metrics.get("ball_pre_contact_motion_m"))
    if ball_motion is not None and ball_motion > PRE_CONTACT_BALL_MOTION_LIMIT_M:
        add("pre_contact_ball_motion_blocker")
    first_contact_alignment = _finite_float(metrics.get("first_contact_push_alignment_deg"))
    if first_contact_alignment is not None and abs(first_contact_alignment) > FIRST_CONTACT_ALIGNMENT_LIMIT_DEG:
        add("first_contact_blocker")
    pre_stage_yaw = _finite_float(metrics.get("pre_stage_yaw_travel_deg"))
    if pre_stage_yaw is not None and pre_stage_yaw > PRE_STAGE_YAW_WATCH_DEG:
        add("pre_stage_yaw_watch")
    pre_stage_time = _finite_float(metrics.get("pre_stage_time_s"))
    if pre_stage_time is not None and pre_stage_time > PRE_STAGE_TIME_WATCH_S:
        add("pre_stage_time_watch")
    capture_entry_time = _finite_float(metrics.get("capture_entry_time_s"))
    if capture_entry_time is not None and capture_entry_time > CAPTURE_ENTRY_TIME_WATCH_S:
        add("capture_entry_time_watch")
    if first_contact_alignment is not None and abs(first_contact_alignment) > FIRST_CONTACT_ALIGNMENT_WATCH_DEG:
        add("first_contact_alignment_watch")
    return flags


def _quality_classification(
    *,
    delivery_pass: bool,
    flags: list[str],
    stage_labels: list[str],
    closest_approach_m: float | None,
    delivery_radius_m: float,
) -> str:
    if "invalid_geometry" in flags:
        return "invalid_geometry"
    if "invalid_model_provenance" in flags:
        return "invalid_model_provenance"
    if "setup_capture_blocker" in flags or "pre_contact_ball_motion_blocker" in flags:
        return "setup_capture_blocker"
    if "first_contact_blocker" in flags:
        return "first_contact_blocker"
    if not delivery_pass and "first_contact" in stage_labels:
        return "first_contact_blocker"
    if not delivery_pass and "setup" in stage_labels and "terminal_arrival" not in stage_labels:
        return "setup_capture_blocker"
    if not delivery_pass and "push_coast" in stage_labels:
        return "push_coast_blocker"
    near_contract = (
        closest_approach_m is not None
        and closest_approach_m <= delivery_radius_m + TERMINAL_LIVE_MAX_EXTRA_M
    )
    if not delivery_pass and "terminal_arrival" in stage_labels and near_contract:
        return "terminal_arrival_candidate"
    if delivery_pass and any(flag.endswith("_watch") for flag in flags):
        return "pass_with_capture_quality_watch"
    if delivery_pass:
        return "clean_pass"
    return "setup_capture_blocker"


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
    quality_classification: str,
    stage_labels: list[str],
    closest_approach_m: float | None,
    delivery_radius_m: float,
    failure_reasons: list[str],
) -> tuple[str, str]:
    if quality_classification == "invalid_geometry":
        return "invalid_geometry", "repair_geometry_evidence_before_gate"
    if quality_classification == "invalid_model_provenance":
        return "invalid_model_provenance", "rerun_with_calibrated_model_provenance"
    if quality_classification in {"setup_capture_blocker", "first_contact_blocker"}:
        return "setup_contact_blocker", "repair_setup_contact_before_guarded_live"
    if quality_classification == "push_coast_blocker":
        return "setup_contact_blocker", "repair_push_coast_before_guarded_live"
    if quality_classification == "pass_with_capture_quality_watch":
        return "saved_anchor_pass_with_contact_watch", "run_repeatability_ladder_with_contact_watch"
    if quality_classification == "terminal_arrival_candidate":
        return "guarded_live_terminal_candidate", "run_narrow_terminal_correction_probe"
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
    model_provenance = _model_provenance(summary, run)
    model_valid = bool(model_provenance.get("model_provenance_valid", False))
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
    run_quality_rows: list[dict[str, Any]] = []
    for candidate_run in _summary_runs(summary) or [run]:
        for label in _stage_labels(summary, candidate_run, _ai_payload(candidate_run)):
            if label not in labels:
                labels.append(label)
        candidate_failure_reasons = _failure_reasons({}, candidate_run)
        candidate_metrics = _run_stage_metrics(candidate_run)
        candidate_provenance = _model_provenance(summary, candidate_run)
        candidate_metrics["model_provenance_valid"] = bool(candidate_provenance.get("model_provenance_valid", False))
        candidate_metrics["model_provenance_reason"] = _clean_text(candidate_provenance.get("model_provenance_reason"))
        candidate_delivery_pass = bool(candidate_run.get("fetch_to_pose_pass", False))
        for flag in _quality_flags(candidate_metrics, candidate_failure_reasons):
            if flag in {"setup_capture_blocker", "pre_contact_ball_motion_blocker"} and "setup" not in labels:
                labels.append("setup")
            if flag == "first_contact_blocker" and "first_contact" not in labels:
                labels.append("first_contact")
        run_quality_rows.append(
            {
                "run_index": candidate_run.get("run_index"),
                "mission_root": _clean_text(candidate_run.get("mission_root") or _dict(candidate_run.get("mission_verdict")).get("mission_root")),
                "delivery_pass": candidate_delivery_pass,
                "failure_reasons": candidate_failure_reasons,
                "metrics": candidate_metrics,
            }
        )
    required_green_runs = int(_finite_float(summary.get("required_green_runs")) or max(len(_summary_runs(summary)), 1))
    pass_count = int(_finite_float(summary.get("fetch_to_pose_pass_count")) or _finite_float(summary.get("pass_count")) or 0)
    failure_count = int(_finite_float(summary.get("fetch_to_pose_fail_count")) or 0)
    delivery_passed = bool(summary.get("promotion_gate_pass", False)) or (
        pass_count >= required_green_runs and failure_count == 0
    )
    representative_metrics = _run_stage_metrics(run)
    all_flags: list[str] = []
    for row in run_quality_rows:
        for flag in _quality_flags(_dict(row.get("metrics")), _list(row.get("failure_reasons"))):
            if flag not in all_flags:
                all_flags.append(flag)
    if not model_valid and "invalid_model_provenance" not in all_flags:
        all_flags.append("invalid_model_provenance")
    quality_classification = _quality_classification(
        delivery_pass=delivery_passed,
        flags=all_flags,
        stage_labels=labels,
        closest_approach_m=closest_approach_m,
        delivery_radius_m=delivery_radius_m,
    )
    stage_quality_pass = delivery_passed and quality_classification not in BLOCKING_QUALITY_CLASSIFICATIONS
    interpretation, next_action = _interpretation(
        passed=stage_quality_pass,
        quality_classification=quality_classification,
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
        "pass": stage_quality_pass,
        "delivery_pass": delivery_passed,
        "stage_quality_pass": stage_quality_pass,
        "quality_classification": quality_classification,
        "quality_flags": all_flags,
        "run_stage_quality": run_quality_rows,
        "failure_reasons": failure_reasons,
        "stage_labels": labels,
        "interpretation": interpretation,
        "recommended_next_action": next_action,
        "closest_approach_distance_m": _round_or_none(closest_approach_m),
        "distance_to_fetch_pose_m": _round_or_none(distance_to_fetch_pose_m),
        "delivery_radius_m": round(float(delivery_radius_m), 6),
        "approach_failure_reason": _clean_text(run.get("approach_failure_reason")),
        "first_contact_push_alignment_deg": _round_or_none(run.get("first_contact_push_alignment_deg")),
        "first_contact_push_alignment_max_deg": _round_or_none(
            _metric_max([
                _finite_float(_dict(row.get("metrics")).get("first_contact_push_alignment_deg"))
                for row in run_quality_rows
            ])
        ),
        "pre_stage_yaw_travel_max_deg": _round_or_none(
            _metric_max([
                _finite_float(_dict(row.get("metrics")).get("pre_stage_yaw_travel_deg"))
                for row in run_quality_rows
            ])
        ),
        "pre_stage_mode_transition_max": int(
            _metric_max([
                _finite_float(_dict(row.get("metrics")).get("pre_stage_mode_transition_count"))
                for row in run_quality_rows
            ])
            or 0
        ),
        "pre_stage_time_max_s": _round_or_none(
            _metric_max([
                _finite_float(_dict(row.get("metrics")).get("pre_stage_time_s"))
                for row in run_quality_rows
            ])
        ),
        "capture_entry_time_max_s": _round_or_none(
            _metric_max([
                _finite_float(_dict(row.get("metrics")).get("capture_entry_time_s"))
                for row in run_quality_rows
            ])
        ),
        "ball_pre_contact_motion_max_m": _round_or_none(
            _metric_max([
                _finite_float(_dict(row.get("metrics")).get("ball_pre_contact_motion_m"))
                for row in run_quality_rows
            ])
        ),
        "capture_entry_final_bearing_rad": representative_metrics.get("capture_entry_final_bearing_rad"),
        "capture_entry_final_ball_y_m": representative_metrics.get("capture_entry_final_ball_y_m"),
        "geometry_consistency_pass": bool(representative_metrics.get("geometry_consistency_pass", True)),
        "geometry_consistency_reason": _clean_text(representative_metrics.get("geometry_consistency_reason")),
        "model_provenance": model_provenance,
        "model_provenance_valid": model_valid,
        "model_provenance_reason": _clean_text(model_provenance.get("model_provenance_reason")),
        "target_model_sdf": _clean_text(model_provenance.get("target_model_sdf")),
        "zone_model_sdf": _clean_text(model_provenance.get("zone_model_sdf")),
        "target_model_radius_m": model_provenance.get("target_model_radius_m"),
        "target_model_classification": _clean_text(model_provenance.get("target_model_classification")),
        "zone_model_classification": _clean_text(model_provenance.get("zone_model_classification")),
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
    blocker_count = sum(
        1
        for row in rows
        if row.get("interpretation") in {"setup_contact_blocker", "invalid_geometry", "invalid_model_provenance"}
    )
    setup_capture_blocker_count = sum(1 for row in rows if row.get("quality_classification") == "setup_capture_blocker")
    first_contact_blocker_count = sum(1 for row in rows if row.get("quality_classification") == "first_contact_blocker")
    push_coast_blocker_count = sum(1 for row in rows if row.get("quality_classification") == "push_coast_blocker")
    invalid_geometry_count = sum(1 for row in rows if row.get("quality_classification") == "invalid_geometry")
    invalid_model_provenance_count = sum(1 for row in rows if row.get("quality_classification") == "invalid_model_provenance")
    terminal_candidate_count = sum(1 for row in rows if row.get("interpretation") == "guarded_live_terminal_candidate")
    contact_watch_count = sum(1 for row in rows if row.get("interpretation") == "saved_anchor_pass_with_contact_watch")
    pass_count = sum(1 for row in rows if bool(row.get("pass", False)))
    if invalid_model_provenance_count:
        overall = "rebuild_model_provenance_before_gate"
    elif blocker_count:
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
        "type": ANALYZER_KIND,
        "generated_utc": utc_now(),
        "analyzer": ANALYZER_KIND,
        "saved_anchor_count": len(rows),
        "pass_count": pass_count,
        "stage_quality_pass_count": pass_count,
        "setup_contact_blocker_count": blocker_count,
        "setup_capture_blocker_count": setup_capture_blocker_count,
        "first_contact_blocker_count": first_contact_blocker_count,
        "push_coast_blocker_count": push_coast_blocker_count,
        "invalid_geometry_count": invalid_geometry_count,
        "invalid_model_provenance_count": invalid_model_provenance_count,
        "saved_anchor_pass_with_contact_watch_count": contact_watch_count,
        "guarded_live_terminal_candidate_count": terminal_candidate_count,
        "stage_quality_green": bool(rows and pass_count == len(rows) and blocker_count == 0 and invalid_model_provenance_count == 0),
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
        f"- Stage-quality pass count: `{summary.get('stage_quality_pass_count', summary.get('pass_count'))}`",
        f"- Pass-with-contact-watch count: `{summary.get('saved_anchor_pass_with_contact_watch_count')}`",
        f"- Setup/contact blockers: `{summary.get('setup_contact_blocker_count')}`",
        f"- Setup/capture blockers: `{summary.get('setup_capture_blocker_count', 0)}`",
        f"- First-contact blockers: `{summary.get('first_contact_blocker_count', 0)}`",
        f"- Push/coast blockers: `{summary.get('push_coast_blocker_count', 0)}`",
        f"- Invalid geometry: `{summary.get('invalid_geometry_count', 0)}`",
        f"- Invalid model provenance: `{summary.get('invalid_model_provenance_count', 0)}`",
        f"- Guarded-live terminal candidates: `{summary.get('guarded_live_terminal_candidate_count')}`",
        "",
        "| layout | stage pass | delivery | model | quality | flags | closest | yaw travel | capture-entry | interpretation | next action |",
        "|---|---:|---:|---:|---|---|---:|---:|---:|---|---|",
    ]
    for row in _list(summary.get("saved_anchors")):
        lines.append(
            "| "
            + " | ".join(
                [
                    _clean_text(row.get("layout")),
                    "`true`" if row.get("pass") else "`false`",
                    "`true`" if row.get("delivery_pass") else "`false`",
                    "`true`" if row.get("model_provenance_valid") else "`false`",
                    _clean_text(row.get("quality_classification")) or "-",
                    ", ".join(_list(row.get("quality_flags"))) or "-",
                    str(row.get("closest_approach_distance_m")),
                    str(row.get("pre_stage_yaw_travel_max_deg")),
                    str(row.get("capture_entry_time_max_s")),
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
