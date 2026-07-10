#!/usr/bin/env python3
"""Score real-robot onboard acquisition traces against the hardware goal."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


REQUIRED_CASES = ("center", "mid-left", "mid-right", "far-left", "far-right")
CENTER_DEADBAND = 0.12
TURN_GATE = 0.55
FAR_CASE_MIN = 0.60
RANGE_MIN_M = 0.70
RANGE_MAX_M = 1.20
TURN_STALL_MIN_ROWS = 10
FORWARD_STALL_MIN_ROWS = 10
CENTER_PROGRESS_MIN = 0.10
RANGE_PROGRESS_MIN_M = 0.05
MEANINGFUL_ANGULAR_Z = 0.15
LIMIT_CYCLE_REVERSALS = 4
LIMIT_CYCLE_DEADBAND_ENTRIES = 2


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def classify_initial_case(center_error: float) -> str:
    error = float(center_error)
    if abs(error) <= CENTER_DEADBAND:
        return "center"
    if error < -FAR_CASE_MIN:
        return "far-left"
    if error > FAR_CASE_MIN:
        return "far-right"
    if error < -CENTER_DEADBAND and error >= -TURN_GATE:
        return "mid-left"
    if error > CENTER_DEADBAND and error <= TURN_GATE:
        return "mid-right"
    return "transition-left" if error < 0.0 else "transition-right"


def _row_center_error(row: dict[str, Any]) -> float | None:
    for container_name in ("policy_obs", "obs"):
        container = row.get(container_name)
        if isinstance(container, dict):
            value = _number(container.get("center_error"))
            if value is not None:
                return value
    decision = row.get("decision")
    if isinstance(decision, dict):
        return _number(decision.get("center_error"))
    return None


def _row_source(row: dict[str, Any]) -> str | None:
    for container_name in ("obs", "policy_obs"):
        container = row.get(container_name)
        if isinstance(container, dict) and container.get("detected"):
            source = container.get("source")
            return str(source) if source else None
    return None


def _row_regime(row: dict[str, Any]) -> str | None:
    decision = row.get("decision")
    if not isinstance(decision, dict) or decision.get("action") != "forward":
        return None
    regime = decision.get("arc_regime")
    if regime in ("turn", "forward"):
        return str(regime)
    linear_x = _number(decision.get("linear_x"))
    return "turn" if linear_x is not None and abs(linear_x) < 1e-6 else "forward"


def _count_deadband_entries(errors: list[float]) -> int:
    entries = 0
    was_inside = abs(errors[0]) <= CENTER_DEADBAND
    for error in errors[1:]:
        inside = abs(error) <= CENTER_DEADBAND
        if inside and not was_inside:
            entries += 1
        was_inside = inside
    return entries


def _count_direction_reversals(rows: Iterable[dict[str, Any]]) -> int:
    signs: list[int] = []
    for row in rows:
        decision = row.get("decision")
        if not isinstance(decision, dict):
            continue
        angular_z = _number(decision.get("angular_z"))
        if angular_z is None or abs(angular_z) < MEANINGFUL_ANGULAR_Z:
            continue
        sign = 1 if angular_z > 0.0 else -1
        if not signs or signs[-1] != sign:
            signs.append(sign)
    return max(0, len(signs) - 1)


def _trace_stop_reason(rows: list[dict[str, Any]]) -> str:
    for row in reversed(rows):
        decision = row.get("decision")
        if isinstance(decision, dict) and decision.get("reason"):
            return str(decision["reason"])
    return "missing_stop_reason"


def analyze_run(
    entry: dict[str, Any],
    rows: list[dict[str, Any]],
    summary: dict[str, Any] | None,
) -> dict[str, Any]:
    summary = summary or {}
    samples: list[dict[str, Any]] = []
    sources: list[str] = []
    for index, row in enumerate(rows):
        error = _row_center_error(row)
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        z_m = _number(decision.get("z_m"))
        source = _row_source(row)
        if source:
            sources.append(source)
        if error is not None:
            samples.append(
                {
                    "index": index,
                    "error": error,
                    "z_m": z_m,
                    "regime": _row_regime(row),
                }
            )

    errors = [sample["error"] for sample in samples]
    ranges = [sample["z_m"] for sample in samples if sample["z_m"] is not None]
    observed_case = classify_initial_case(errors[0]) if errors else "unavailable"
    initial_z = ranges[0] if ranges else None
    minimum_z = min(ranges) if ranges else None
    final_z = ranges[-1] if ranges else None
    range_progress = (
        max(0.0, float(initial_z) - float(minimum_z))
        if initial_z is not None and minimum_z is not None
        else 0.0
    )
    center_progress = (
        max(0.0, abs(errors[0]) - min(abs(error) for error in errors))
        if errors
        else 0.0
    )
    turn_rows = sum(1 for sample in samples if sample["regime"] == "turn")
    forward_rows = sum(1 for sample in samples if sample["regime"] == "forward")
    regimes = [sample["regime"] for sample in samples if sample["regime"]]
    turn_to_forward = any(
        regimes[i] == "turn" and "forward" in regimes[i + 1 :]
        for i in range(len(regimes))
    )
    deadband_entries = _count_deadband_entries(errors) if errors else 0
    direction_reversals = _count_direction_reversals(rows)
    limit_cycle = (
        direction_reversals >= LIMIT_CYCLE_REVERSALS
        and deadband_entries >= LIMIT_CYCLE_DEADBAND_ENTRIES
    )
    trace_stop_reason = _trace_stop_reason(rows)
    episode_stop_reason = str(summary.get("stop_reason") or trace_stop_reason)
    reached_standoff = trace_stop_reason == "standoff_reached" or episode_stop_reason in (
        "standoff_reached",
        "standoff_then_pushed",
    )
    turn_stalled = turn_rows >= TURN_STALL_MIN_ROWS and center_progress < CENTER_PROGRESS_MIN
    forward_stalled = (
        forward_rows >= FORWARD_STALL_MIN_ROWS and range_progress < RANGE_PROGRESS_MIN_M
    )
    onboard_perception = bool(sources) and all(source == "onboard_trt" for source in sources)
    initial_range_in_scope = (
        initial_z is not None and RANGE_MIN_M <= float(initial_z) <= RANGE_MAX_M
    )
    expected_case = str(entry.get("expected_case") or "")
    expected_case_match = bool(expected_case) and expected_case == observed_case
    final_safe = summary.get("final_safe") if isinstance(summary.get("final_safe"), bool) else None
    preflight_safe = entry.get("preflight_safe") is True
    operator_started = entry.get("operator_started") is True
    surface = str(entry.get("surface") or "unknown")

    smooth_approach = (
        reached_standoff
        and range_progress >= RANGE_PROGRESS_MIN_M
        and not turn_stalled
        and not forward_stalled
        and not limit_cycle
    )
    if not rows:
        diagnosis = "missing_trace_rows"
    elif not errors:
        diagnosis = "target_not_detected"
    elif trace_stop_reason == "lost_target" or episode_stop_reason == "lost_target":
        diagnosis = "target_lost"
    elif turn_stalled:
        diagnosis = "turn_response_stalled"
    elif forward_stalled:
        diagnosis = "forward_response_stalled"
    elif limit_cycle:
        diagnosis = "center_limit_cycle"
    elif smooth_approach:
        diagnosis = "smooth_acquisition_pass"
    else:
        diagnosis = trace_stop_reason

    qualifying_pass = all(
        (
            surface == "hard_floor",
            expected_case_match,
            initial_range_in_scope,
            onboard_perception,
            preflight_safe,
            operator_started,
            final_safe is True,
            smooth_approach,
        )
    )
    issues: list[str] = []
    checks = {
        "hard_floor": surface == "hard_floor",
        "expected_case_match": expected_case_match,
        "initial_range_in_scope": initial_range_in_scope,
        "onboard_perception": onboard_perception,
        "preflight_safe": preflight_safe,
        "operator_started": operator_started,
        "final_safe": final_safe is True,
        "smooth_approach": smooth_approach,
    }
    issues.extend(name for name, passed in checks.items() if not passed)

    return {
        "run_id": str(entry.get("run_id") or "unnamed"),
        "phase": str(entry.get("phase") or "unclassified"),
        "surface": surface,
        "expected_case": expected_case or None,
        "observed_case": observed_case,
        "expected_case_match": expected_case_match,
        "trace_row_count": len(rows),
        "detected_sample_count": len(errors),
        "detected_sources": sorted(set(sources)),
        "onboard_perception_pass": onboard_perception,
        "initial_center_error": round(errors[0], 6) if errors else None,
        "final_center_error": round(errors[-1], 6) if errors else None,
        "center_error_progress": round(center_progress, 6),
        "initial_z_m": round(initial_z, 4) if initial_z is not None else None,
        "minimum_z_m": round(minimum_z, 4) if minimum_z is not None else None,
        "final_z_m": round(final_z, 4) if final_z is not None else None,
        "range_progress_m": round(range_progress, 4),
        "initial_range_in_scope": initial_range_in_scope,
        "turn_regime_rows": turn_rows,
        "forward_regime_rows": forward_rows,
        "turn_to_forward_transition": turn_to_forward,
        "deadband_entry_count": deadband_entries,
        "direction_reversal_count": direction_reversals,
        "limit_cycle_detected": limit_cycle,
        "trace_stop_reason": trace_stop_reason,
        "episode_stop_reason": episode_stop_reason,
        "reached_standoff": reached_standoff,
        "smooth_approach_pass": smooth_approach,
        "preflight_safe": preflight_safe,
        "operator_started": operator_started,
        "final_safe": final_safe,
        "diagnosis": diagnosis,
        "qualifying_pass": qualifying_pass,
        "failed_checks": issues,
    }


def summarize_campaign(runs: list[dict[str, Any]]) -> dict[str, Any]:
    covered = {
        case
        for case in REQUIRED_CASES
        if any(
            run.get("phase") == "diagnostic"
            and run.get("observed_case") == case
            and run.get("qualifying_pass") is True
            for run in runs
        )
    }
    missing = [case for case in REQUIRED_CASES if case not in covered]
    mixed_runs = [run for run in runs if run.get("phase") == "mixed"]
    consecutive = 0
    for run in reversed(mixed_runs):
        if run.get("qualifying_pass") is True:
            consecutive += 1
        else:
            break
    diagnosis_counts = Counter(str(run.get("diagnosis") or "unknown") for run in runs)
    coverage_pass = not missing
    goal_ready = coverage_pass and consecutive >= 5
    return {
        "run_count": len(runs),
        "qualifying_pass_count": sum(run.get("qualifying_pass") is True for run in runs),
        "diagnostic_case_coverage": [case for case in REQUIRED_CASES if case in covered],
        "missing_diagnostic_cases": missing,
        "diagnostic_case_coverage_pass": coverage_pass,
        "mixed_run_count": len(mixed_runs),
        "mixed_consecutive_passes": consecutive,
        "diagnosis_counts": dict(sorted(diagnosis_counts.items())),
        "goal_ready": goal_ready,
    }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError("%s:%d: invalid JSON: %s" % (path, line_number, exc)) from exc
        if not isinstance(payload, dict):
            raise ValueError("%s:%d: trace row must be an object" % (path, line_number))
        rows.append(payload)
    return rows


def load_summary(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        pass
    for line in reversed(text.splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError("%s: no JSON object found" % path)


def _resolve(repo_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def analyze_manifest(manifest: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    raw_runs = manifest.get("runs")
    if not isinstance(raw_runs, list) or not raw_runs:
        raise ValueError("manifest.runs must be a non-empty list")
    run_results: list[dict[str, Any]] = []
    for raw_entry in raw_runs:
        if not isinstance(raw_entry, dict):
            raise ValueError("each manifest run must be an object")
        trace_value = raw_entry.get("trace_path")
        if not trace_value:
            raise ValueError("run %s is missing trace_path" % raw_entry.get("run_id"))
        trace_path = _resolve(repo_root, str(trace_value))
        summary_value = raw_entry.get("summary_path")
        summary_path = _resolve(repo_root, str(summary_value)) if summary_value else None
        result = analyze_run(
            raw_entry,
            load_jsonl(trace_path),
            load_summary(summary_path) if summary_path else None,
        )
        result["trace_path"] = str(trace_path)
        result["summary_path"] = str(summary_path) if summary_path else None
        run_results.append(result)
    return {
        "type": "onboard_acquisition_trace_scorecard",
        "campaign_id": str(manifest.get("campaign_id") or "unnamed"),
        "runs": run_results,
        "campaign": summarize_campaign(run_results),
        "thresholds": {
            "center_deadband": CENTER_DEADBAND,
            "turn_gate": TURN_GATE,
            "far_case_min": FAR_CASE_MIN,
            "range_min_m": RANGE_MIN_M,
            "range_max_m": RANGE_MAX_M,
            "center_progress_min": CENTER_PROGRESS_MIN,
            "range_progress_min_m": RANGE_PROGRESS_MIN_M,
            "limit_cycle_reversals": LIMIT_CYCLE_REVERSALS,
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    campaign = payload["campaign"]
    lines = [
        "# Onboard Acquisition Trace Scorecard",
        "",
        "Campaign: `%s`" % payload["campaign_id"],
        "",
        "| Run | Phase | Expected | Observed | Start z | Progress | Reversals | Diagnosis | Qualifying |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for run in payload["runs"]:
        lines.append(
            "| {run_id} | {phase} | {expected_case} | {observed_case} | {initial_z_m} | "
            "{range_progress_m} | {direction_reversal_count} | {diagnosis} | {qualifying_pass} |".format(
                **run
            )
        )
    lines.extend(
        [
            "",
            "## Campaign Gate",
            "",
            "- Diagnostic coverage: `%s`" % campaign["diagnostic_case_coverage_pass"],
            "- Missing diagnostic cases: `%s`" % ", ".join(campaign["missing_diagnostic_cases"]),
            "- Consecutive mixed passes: `%d`" % campaign["mixed_consecutive_passes"],
            "- Acquisition goal ready: `%s`" % campaign["goal_ready"],
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--require-goal-ready", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
    payload = analyze_manifest(manifest, args.repo_root.resolve())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.output_dir / "summary.json"
    scorecard_path = args.output_dir / "scorecard.md"
    summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    scorecard_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"summary_path": str(summary_path), "scorecard_path": str(scorecard_path),
                      "goal_ready": payload["campaign"]["goal_ready"]}, sort_keys=True))
    if args.require_goal_ready and not payload["campaign"]["goal_ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
