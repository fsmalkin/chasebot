#!/usr/bin/env python3
"""Diagnose capture-entry behavior from saved-anchor fetch artifacts."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from gather_mission_helpers import DEFAULT_CAPTURE_ENTRY_CENTERED_READY_ABS_BALL_Y_M
from gather_mission_helpers import DEFAULT_CAPTURE_ENTRY_CENTERED_READY_BALL_X_M
from gather_mission_helpers import DEFAULT_CAPTURE_ENTRY_PLUS45_FINISH_READY_ABS_BALL_Y_M
from gather_mission_helpers import DEFAULT_CAPTURE_ENTRY_PLUS45_FINISH_READY_BALL_X_M
from gather_mission_helpers import DEFAULT_CAPTURE_ENTRY_PLUS45_FINISH_READY_MAX_BEARING_RAD
from gather_mission_helpers import DEFAULT_CAPTURE_ENTRY_READY_ABS_BALL_Y_M
from gather_mission_helpers import DEFAULT_CAPTURE_ENTRY_READY_BALL_X_M
from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import read_json
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json


ANALYZER_KIND = "fetch_capture_entry_diagnostic_analyzer"
READY_BANDS = (
    ("standard", DEFAULT_CAPTURE_ENTRY_READY_BALL_X_M, DEFAULT_CAPTURE_ENTRY_READY_ABS_BALL_Y_M, None),
    ("centered", DEFAULT_CAPTURE_ENTRY_CENTERED_READY_BALL_X_M, DEFAULT_CAPTURE_ENTRY_CENTERED_READY_ABS_BALL_Y_M, None),
    (
        "plus45_finish",
        DEFAULT_CAPTURE_ENTRY_PLUS45_FINISH_READY_BALL_X_M,
        DEFAULT_CAPTURE_ENTRY_PLUS45_FINISH_READY_ABS_BALL_Y_M,
        DEFAULT_CAPTURE_ENTRY_PLUS45_FINISH_READY_MAX_BEARING_RAD,
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose capture-entry saved-anchor evidence.")
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--saved-anchor-summary", action="append", required=True)
    return parser.parse_args()


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _finite_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return float(numeric)


def _round_or_none(value: Any) -> float | None:
    numeric = _finite_float(value)
    return round(numeric, 6) if numeric is not None else None


def _resolve_path(raw_path: str) -> Path:
    path = Path(_clean_text(raw_path))
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


def _artifact_display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _run_state_history_path(run: dict[str, Any]) -> Path | None:
    mission_verdict = _dict(run.get("mission_verdict"))
    candidates = [
        run.get("state_history_path"),
        mission_verdict.get("state_history_path"),
    ]
    mission_root = _clean_text(run.get("mission_root") or mission_verdict.get("mission_root"))
    if mission_root:
        candidates.append(str(Path(mission_root) / "state_history.jsonl"))
    for raw in candidates:
        text = _clean_text(raw)
        if not text:
            continue
        path = _resolve_path(text)
        if path.is_file():
            return path
    return None


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


def _capture_entry_payload(run: dict[str, Any]) -> dict[str, Any]:
    for key in ("fresh_attempt_approach", "latest_approach_progress"):
        approach = _dict(run.get(key)) or _dict(_dict(run.get("mission_verdict")).get(key))
        capture_entry = _dict(approach.get("capture_entry"))
        if capture_entry:
            return capture_entry
    return {
        "reached": run.get("capture_entry_reached"),
        "time_s": run.get("capture_entry_time_s"),
        "failure_reason": run.get("approach_failure_reason"),
    }


def _failure_reason(run: dict[str, Any]) -> str:
    capture_entry = _capture_entry_payload(run)
    for value in (
        capture_entry.get("failure_reason"),
        run.get("approach_failure_reason"),
        run.get("fetch_to_pose_failure_reason"),
        _dict(run.get("mission_verdict")).get("approach_failure_reason"),
    ):
        text = _clean_text(value)
        if text:
            return text
    return ""


def _capture_entry_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if _clean_text(row.get("phase")) == "capture_entry"]


def _capture_sample(row: dict[str, Any]) -> dict[str, Any]:
    capture = _dict(row.get("capture"))
    diagnostics = _dict(row.get("capture_entry_diagnostics"))
    snapshot = _dict(diagnostics.get("capture_entry_snapshot")) or _dict(row.get("capture_entry"))
    return {
        "ball_x_m": _finite_float(capture.get("ball_x_m")) or _finite_float(snapshot.get("ball_x_m")),
        "ball_y_m": _finite_float(capture.get("ball_y_m")) or _finite_float(snapshot.get("ball_y_m")),
        "bearing_rad": _finite_float(capture.get("bearing_rad")) or _finite_float(snapshot.get("bearing_rad")),
        "robot_delta_from_handoff_m": _finite_float(diagnostics.get("robot_delta_from_handoff_m")),
        "ball_delta_from_handoff_m": _finite_float(diagnostics.get("ball_delta_from_handoff_m")),
        "timeout_cause": _clean_text(diagnostics.get("timeout_cause")),
        "ready_signal": bool(diagnostics.get("ready_signal", False)),
        "selected_command_mode": _clean_text(
            _dict(diagnostics.get("selected_command")).get("mode")
            or _dict(row.get("selected_command")).get("mode")
        ),
        "selected_linear_x": _finite_float(
            _dict(diagnostics.get("selected_command")).get("linear_x")
            if isinstance(diagnostics.get("selected_command"), dict)
            else _dict(row.get("selected_command")).get("linear_x")
        ),
        "selected_angular_z": _finite_float(
            _dict(diagnostics.get("selected_command")).get("angular_z")
            if isinstance(diagnostics.get("selected_command"), dict)
            else _dict(row.get("selected_command")).get("angular_z")
        ),
    }


def _ready_band_error(sample: dict[str, Any]) -> dict[str, Any]:
    ball_x = _finite_float(sample.get("ball_x_m"))
    ball_y = _finite_float(sample.get("ball_y_m"))
    bearing = _finite_float(sample.get("bearing_rad"))
    if ball_x is None or ball_y is None:
        return {"band": "", "total_excess": None}
    candidates: list[dict[str, Any]] = []
    for name, max_x, max_abs_y, max_abs_bearing in READY_BANDS:
        x_excess = max(0.0, ball_x - float(max_x))
        y_excess = max(0.0, abs(ball_y) - float(max_abs_y))
        bearing_excess = 0.0
        if max_abs_bearing is not None:
            if bearing is None:
                bearing_excess = 999.0
            else:
                bearing_excess = max(0.0, abs(bearing) - float(max_abs_bearing))
        candidates.append(
            {
                "band": name,
                "x_excess_m": round(x_excess, 6),
                "y_excess_m": round(y_excess, 6),
                "bearing_excess_rad": round(bearing_excess, 6),
                "total_excess": round(x_excess + y_excess + bearing_excess, 6),
            }
        )
    return min(candidates, key=lambda item: float(item.get("total_excess", 999.0)))


def _run_classification(
    *,
    capture_entry_pass: bool,
    failure_reason: str,
    samples: list[dict[str, Any]],
    best_ready_error: dict[str, Any],
) -> str:
    if capture_entry_pass:
        return "capture_entry_pass"
    if not samples:
        return "capture_entry_not_exercised"
    timeout = failure_reason == "capture_entry_timeout"
    command_modes = [_clean_text(sample.get("selected_command_mode")) for sample in samples]
    zero_recenter_count = sum(
        1
        for sample in samples
        if _clean_text(sample.get("selected_command_mode")) == "object_capture_entry_lateral_recenter"
        and abs(float(sample.get("selected_linear_x") or 0.0)) <= 1.0e-6
    )
    forward_count = sum(1 for sample in samples if abs(float(sample.get("selected_linear_x") or 0.0)) > 1.0e-6)
    max_robot_delta = max(
        [float(sample.get("robot_delta_from_handoff_m") or 0.0) for sample in samples],
        default=0.0,
    )
    final_ball_x = _finite_float(samples[-1].get("ball_x_m"))
    if (
        timeout
        and zero_recenter_count >= 2
        and zero_recenter_count >= forward_count
        and max_robot_delta <= 0.06
        and final_ball_x is not None
        and final_ball_x > DEFAULT_CAPTURE_ENTRY_CENTERED_READY_BALL_X_M
    ):
        return "recenter_without_forward_progress"
    if timeout and forward_count > 0 and final_ball_x is not None and final_ball_x > DEFAULT_CAPTURE_ENTRY_CENTERED_READY_BALL_X_M:
        return "insufficient_forward_closure"
    if timeout and _finite_float(best_ready_error.get("total_excess")) is not None and float(best_ready_error["total_excess"]) <= 0.06:
        return "ready_threshold_mismatch"
    if timeout:
        if "object_capture_entry_lateral_recenter" in command_modes:
            return "capture_entry_recenter_timeout"
        return "capture_entry_timeout_unknown"
    if failure_reason:
        return "capture_entry_failure_other"
    return "capture_entry_watchlist"


def analyze_run(summary: dict[str, Any], run: dict[str, Any], run_index: int) -> dict[str, Any]:
    capture_entry = _capture_entry_payload(run)
    capture_entry_pass = bool(capture_entry.get("pass", capture_entry.get("reached", False)))
    failure_reason = _failure_reason(run)
    state_history_path = _run_state_history_path(run)
    rows = _capture_entry_rows(_read_jsonl(state_history_path)) if state_history_path else []
    samples = [_capture_sample(row) for row in rows]
    ready_errors = [_ready_band_error(sample) for sample in samples]
    best_ready_error = min(
        [item for item in ready_errors if item.get("total_excess") is not None],
        key=lambda item: float(item.get("total_excess", 999.0)),
        default={"band": "", "total_excess": None},
    )
    command_counts = Counter(_clean_text(sample.get("selected_command_mode")) for sample in samples if _clean_text(sample.get("selected_command_mode")))
    classification = _run_classification(
        capture_entry_pass=capture_entry_pass,
        failure_reason=failure_reason,
        samples=samples,
        best_ready_error=best_ready_error,
    )
    final_sample = samples[-1] if samples else {}
    return {
        "layout": _layout_name(summary),
        "campaign_id": _clean_text(summary.get("campaign_id")),
        "run_index": run.get("run_index", run_index),
        "mission_root": _clean_text(run.get("mission_root") or _dict(run.get("mission_verdict")).get("mission_root")),
        "state_history_path": _artifact_display_path(state_history_path) if state_history_path else "",
        "delivery_pass": bool(run.get("fetch_to_pose_pass", False)),
        "capture_entry_pass": capture_entry_pass,
        "capture_entry_time_s": _round_or_none(capture_entry.get("time_s") or run.get("capture_entry_time_s")),
        "failure_reason": failure_reason,
        "classification": classification,
        "sample_count": len(samples),
        "command_counts": dict(sorted(command_counts.items())),
        "zero_linear_recenter_count": sum(
            1
            for sample in samples
            if _clean_text(sample.get("selected_command_mode")) == "object_capture_entry_lateral_recenter"
            and abs(float(sample.get("selected_linear_x") or 0.0)) <= 1.0e-6
        ),
        "forward_command_count": sum(1 for sample in samples if abs(float(sample.get("selected_linear_x") or 0.0)) > 1.0e-6),
        "max_robot_delta_from_handoff_m": _round_or_none(
            max([float(sample.get("robot_delta_from_handoff_m") or 0.0) for sample in samples], default=0.0)
        ),
        "max_ball_delta_from_handoff_m": _round_or_none(
            max([float(sample.get("ball_delta_from_handoff_m") or 0.0) for sample in samples], default=0.0)
        ),
        "best_ready_band": best_ready_error,
        "final_sample": {
            "ball_x_m": _round_or_none(final_sample.get("ball_x_m")),
            "ball_y_m": _round_or_none(final_sample.get("ball_y_m")),
            "bearing_rad": _round_or_none(final_sample.get("bearing_rad")),
            "selected_command_mode": _clean_text(final_sample.get("selected_command_mode")),
            "selected_linear_x": _round_or_none(final_sample.get("selected_linear_x")),
            "selected_angular_z": _round_or_none(final_sample.get("selected_angular_z")),
            "timeout_cause": _clean_text(final_sample.get("timeout_cause")),
        },
    }


def analyze(saved_anchor_summaries: list[str]) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    for raw_path in saved_anchor_summaries:
        path = _resolve_path(raw_path)
        summary = read_json(path)
        if not isinstance(summary, dict):
            raise SystemExit(f"saved anchor summary is not a JSON object: {path}")
        for index, run in enumerate(_list(summary.get("runs")), start=1):
            if isinstance(run, dict):
                runs.append(analyze_run(summary, run, index))
    counts = Counter(_clean_text(row.get("classification")) for row in runs)
    blocker_count = sum(
        count
        for classification, count in counts.items()
        if classification
        not in {
            "capture_entry_pass",
            "capture_entry_watchlist",
        }
    )
    if counts.get("recenter_without_forward_progress", 0):
        interpretation = "repair_recenter_forward_progress"
    elif blocker_count:
        interpretation = "repair_capture_entry_before_guarded_live"
    elif runs:
        interpretation = "capture_entry_requalified"
    else:
        interpretation = "no_capture_entry_runs"
    return {
        "type": ANALYZER_KIND,
        "analyzer": ANALYZER_KIND,
        "generated_utc": utc_now(),
        "run_count": len(runs),
        "capture_entry_pass_count": counts.get("capture_entry_pass", 0),
        "capture_entry_blocker_count": blocker_count,
        "classification_counts": dict(sorted(counts.items())),
        "overall_interpretation": interpretation,
        "runs": runs,
    }


def write_scorecard(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# Capture-Entry Diagnostic Analyzer",
        "",
        f"- Generated: `{summary.get('generated_utc')}`",
        f"- Overall interpretation: `{summary.get('overall_interpretation')}`",
        f"- Runs: `{summary.get('run_count')}`",
        f"- Capture-entry pass count: `{summary.get('capture_entry_pass_count')}`",
        f"- Capture-entry blocker count: `{summary.get('capture_entry_blocker_count')}`",
        "",
        "| layout | run | delivery | capture-entry | classification | time | commands | final x | final y | final bearing | best band | excess | timeout |",
        "|---|---:|---:|---:|---|---:|---|---:|---:|---:|---|---:|---|",
    ]
    for row in summary.get("runs", []) if isinstance(summary.get("runs"), list) else []:
        final_sample = _dict(row.get("final_sample"))
        best_band = _dict(row.get("best_ready_band"))
        commands = ", ".join(
            f"{key}:{value}"
            for key, value in (_dict(row.get("command_counts"))).items()
        )
        lines.append(
            "| "
            f"{row.get('layout', '')} | "
            f"`{row.get('run_index', '')}` | "
            f"`{bool(row.get('delivery_pass', False))}` | "
            f"`{bool(row.get('capture_entry_pass', False))}` | "
            f"{row.get('classification', '')} | "
            f"{row.get('capture_entry_time_s', '')} | "
            f"{commands} | "
            f"{final_sample.get('ball_x_m', '')} | "
            f"{final_sample.get('ball_y_m', '')} | "
            f"{final_sample.get('bearing_rad', '')} | "
            f"{best_band.get('band', '')} | "
            f"{best_band.get('total_excess', '')} | "
            f"{final_sample.get('timeout_cause', '')} |"
        )
    ensure_dir(path.parent)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    campaign_id = _clean_text(args.campaign_id) or f"fetch_capture_entry_diagnostic_{utc_now().replace(':', '').replace('.', '')}"
    out_dir = REPO_ROOT / "artifacts" / "session" / campaign_id / ANALYZER_KIND
    summary = analyze(args.saved_anchor_summary)
    summary["campaign_id"] = campaign_id
    summary_path = out_dir / "diagnostic_summary.json"
    scorecard_path = out_dir / "scorecard.md"
    write_json(summary_path, summary)
    write_scorecard(summary, scorecard_path)
    print(f"CAPTURE_ENTRY_DIAGNOSTIC_SUMMARY={summary_path}")
    print(f"CAPTURE_ENTRY_DIAGNOSTIC_SCORECARD={scorecard_path}")
    print(f"OVERALL_INTERPRETATION={summary.get('overall_interpretation', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
