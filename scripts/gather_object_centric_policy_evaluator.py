#!/usr/bin/env python3
"""Evaluate object-centric gather policy evidence from existing artifacts."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from llm_supervisor_core import ensure_dir
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_KIND = "gather_object_centric_policy_evaluator"
PRE_CONTACT_PHASES = {"pre_stage", "stage", "capture_entry"}
PREMATURE_BALL_MOTION_THRESHOLD_M = 0.05


def parse_artifact_spec(spec: str) -> tuple[str, Path]:
    if "=" not in spec:
        raise argparse.ArgumentTypeError(f"--artifact must be label=path, got {spec!r}")
    label, path_text = spec.split("=", 1)
    label = label.strip()
    path_text = path_text.strip()
    if not label or not path_text:
        raise argparse.ArgumentTypeError(f"--artifact must be label=path, got {spec!r}")
    return label, Path(path_text)


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return payload


def _load_jsonl(path: Path) -> tuple[str, list[dict[str, Any]]]:
    if not path.exists():
        return "missing", []
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return "invalid_jsonl", rows
        if isinstance(payload, dict):
            rows.append(payload)
    return "ok", rows


def _finite_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _round_number(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "pass", "passed"}:
            return True
        if normalized in {"false", "0", "no", "fail", "failed"}:
            return False
    return None


def _resolve_path(raw_path: Any, *, source_summary_path: Path) -> Path | None:
    text = str(raw_path or "").strip()
    if not text:
        return None
    path = Path(text)
    if path.is_absolute():
        if not path.exists():
            fallback = _repo_artifact_fallback(path)
            if fallback is not None and fallback.exists():
                return fallback
        return path
    repo_path = REPO_ROOT / path
    if repo_path.exists():
        return repo_path
    return source_summary_path.parent / path


def _repo_artifact_fallback(path: Path) -> Path | None:
    parts = path.parts
    for index, part in enumerate(parts):
        if part == "artifacts" and index + 1 < len(parts):
            return REPO_ROOT / Path(*parts[index:])
    return None


def _mission_root_path(run: dict[str, Any], *, source_summary_path: Path) -> Path | None:
    mission_root = _resolve_path(run.get("mission_root"), source_summary_path=source_summary_path)
    if mission_root is not None:
        return mission_root
    summary_path = _resolve_path(run.get("summary_path"), source_summary_path=source_summary_path)
    if summary_path is not None:
        return summary_path.parent
    verdict_path = _resolve_path(run.get("mission_verdict_path"), source_summary_path=source_summary_path)
    if verdict_path is not None:
        return verdict_path.parent
    return None


def _state_history_path(run: dict[str, Any], mission_root: Path | None, *, source_summary_path: Path) -> Path | None:
    explicit = _resolve_path(run.get("state_history_path"), source_summary_path=source_summary_path)
    if explicit is not None:
        return explicit
    if mission_root is not None:
        return mission_root / "state_history.jsonl"
    return None


def _mission_verdict(run: dict[str, Any], mission_root: Path | None, *, source_summary_path: Path) -> dict[str, Any]:
    inline = _dict_value(run.get("mission_verdict") or run.get("summary"))
    if inline:
        return inline
    explicit = _resolve_path(run.get("mission_verdict_path"), source_summary_path=source_summary_path)
    candidates = [explicit] if explicit is not None else []
    if mission_root is not None:
        candidates.append(mission_root / "mission_verdict.json")
    for path in candidates:
        if path is not None and path.exists():
            return _load_json_object(path)
    return {}


def _case_id_from_label(label: str) -> str:
    text = str(label or "").lower()
    for case_id in ("backside180", "plus45", "minus45", "zero"):
        if case_id in text:
            return case_id
    return "unknown_case"


def _iter_runs(source_label: str, source_summary_path: Path, summary: dict[str, Any]) -> list[dict[str, Any]]:
    extracted: list[dict[str, Any]] = []
    cases = _list_value(summary.get("cases"))
    if cases:
        for case in cases:
            case_payload = _dict_value(case)
            case_id = str(case_payload.get("case_id", "") or "unknown_case")
            for index, raw_run in enumerate(_list_value(case_payload.get("runs")), start=1):
                run = _dict_value(raw_run)
                extracted.append(
                    {
                        "source_label": source_label,
                        "source_kind": "gather_goal_side_matrix",
                        "case_id": case_id,
                        "run_label": f"{source_label}:{case_id}:run_{index}",
                        "run_index": int(run.get("run_index") or index),
                        "run": run,
                    }
                )
        return extracted
    for index, raw_run in enumerate(_list_value(summary.get("runs")), start=1):
        run = _dict_value(raw_run)
        nested_runs = _list_value(run.get("runs"))
        if nested_runs:
            parent_label = str(run.get("label", "") or f"entry_{index}")
            for nested_index, raw_nested in enumerate(nested_runs, start=1):
                nested = _dict_value(raw_nested)
                extracted.append(
                    {
                        "source_label": source_label,
                        "source_kind": "nested_repeatability",
                        "case_id": str(nested.get("case_id", "") or _case_id_from_label(parent_label)),
                        "run_label": f"{source_label}:{parent_label}:run_{nested_index}",
                        "run_index": int(nested.get("run_index") or nested_index),
                        "run": nested,
                    }
                )
        else:
            extracted.append(
                {
                    "source_label": source_label,
                    "source_kind": "gather_mission_repeatability",
                    "case_id": str(run.get("case_id", "") or _case_id_from_label(source_label)),
                    "run_label": f"{source_label}:run_{int(run.get('run_index') or index)}",
                    "run_index": int(run.get("run_index") or index),
                    "run": run,
                }
            )
    if not extracted and {"pass", "mission_completed_pass", "failure_reason"} & set(summary.keys()):
        extracted.append(
            {
                "source_label": source_label,
                "source_kind": "mission_verdict",
                "case_id": _case_id_from_label(source_label),
                "run_label": f"{source_label}:mission_verdict",
                "run_index": 1,
                "run": {"mission_verdict": summary},
            }
        )
    return extracted


def _command_from_row(row: dict[str, Any]) -> dict[str, Any]:
    command = _dict_value(row.get("selected_command"))
    if command:
        return command
    capture_debug = _dict_value(row.get("capture_diagnostics"))
    command = _dict_value(capture_debug.get("selected_command"))
    if command:
        return command
    entry_debug = _dict_value(row.get("capture_entry_diagnostics"))
    command = _dict_value(entry_debug.get("selected_command"))
    if command:
        return command
    policy = _dict_value(row.get("object_centric_policy"))
    return _dict_value(policy.get("selected_command"))


def _object_policy_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_dict_value(row.get("object_centric_policy")) for row in rows if _dict_value(row.get("object_centric_policy"))]


def _command_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    for row in rows:
        command = _command_from_row(row)
        if command:
            samples.append(
                {
                    "phase": str(row.get("phase", "") or ""),
                    "mode": str(command.get("mode", "") or ""),
                    "linear_x": _round_number(_finite_float(command.get("linear_x"))),
                    "angular_z": _round_number(_finite_float(command.get("angular_z"))),
                    "target_speed_scale": _round_number(_finite_float(command.get("target_speed_scale"))),
                }
            )
    modes = [sample["mode"] for sample in samples if sample.get("mode")]
    mode_counts = Counter(modes)
    deltas_linear: list[float] = []
    deltas_angular: list[float] = []
    mode_churn = 0
    previous: dict[str, Any] | None = None
    for sample in samples:
        if previous is not None:
            linear = _finite_float(sample.get("linear_x"))
            prev_linear = _finite_float(previous.get("linear_x"))
            angular = _finite_float(sample.get("angular_z"))
            prev_angular = _finite_float(previous.get("angular_z"))
            if linear is not None and prev_linear is not None:
                deltas_linear.append(abs(linear - prev_linear))
            if angular is not None and prev_angular is not None:
                deltas_angular.append(abs(angular - prev_angular))
            if sample.get("mode") != previous.get("mode"):
                mode_churn += 1
        previous = sample
    linear_values = [_finite_float(sample.get("linear_x")) for sample in samples]
    angular_values = [_finite_float(sample.get("angular_z")) for sample in samples]
    return {
        "sample_count": len(samples),
        "mode_counts": dict(mode_counts),
        "mode_churn_count": mode_churn,
        "max_abs_linear_x": _round_number(max((abs(value) for value in linear_values if value is not None), default=None)),
        "max_abs_angular_z": _round_number(max((abs(value) for value in angular_values if value is not None), default=None)),
        "max_linear_delta_mps": _round_number(max(deltas_linear, default=None)),
        "max_angular_delta_radps": _round_number(max(deltas_angular, default=None)),
        "tail": samples[-8:],
    }


def _first_contact_alignment(rows: list[dict[str, Any]], run: dict[str, Any], verdict: dict[str, Any]) -> float | None:
    for source in (
        _dict_value(run.get("capture_entry")),
        _dict_value(verdict.get("capture_entry")),
        _dict_value(verdict.get("progress", {})).get("capture_entry"),
    ):
        source_dict = _dict_value(source)
        value = _finite_float(source_dict.get("first_contact_push_alignment_deg"))
        if value is not None:
            return value
    for row in rows:
        for payload in (
            _dict_value(row.get("capture_diagnostics")),
            _dict_value(row.get("capture_entry_diagnostics")),
        ):
            value = _finite_float(payload.get("first_contact_push_alignment_deg"))
            if value is not None:
                return value
    return None


def _phase_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("phase", "") or "") for row in rows if str(row.get("phase", "") or ""))
    return dict(counts)


def _premature_ball_motion(rows: list[dict[str, Any]]) -> dict[str, Any]:
    samples: list[float] = []
    for row in rows:
        if str(row.get("phase", "") or "") not in PRE_CONTACT_PHASES:
            continue
        motion = _finite_float(row.get("ball_motion_m"))
        if motion is None:
            diagnostics = _dict_value(row.get("capture_entry_diagnostics") or row.get("object_centric_policy"))
            motion = _finite_float(diagnostics.get("ball_delta_from_handoff_m") or diagnostics.get("ball_motion_m"))
        if motion is not None:
            samples.append(float(motion))
    max_motion = max(samples, default=0.0)
    return {
        "sample_count": len(samples),
        "max_m": round(max_motion, 6),
        "observed": bool(max_motion > PREMATURE_BALL_MOTION_THRESHOLD_M),
        "threshold_m": PREMATURE_BALL_MOTION_THRESHOLD_M,
    }


def _capture_metrics(rows: list[dict[str, Any]], run: dict[str, Any], verdict: dict[str, Any]) -> dict[str, Any]:
    capture_rows = [row for row in rows if str(row.get("phase", "") or "") == "capture"]
    capture_entry_rows = [row for row in rows if str(row.get("phase", "") or "") == "capture_entry"]
    capture_entry_payload = _dict_value(run.get("capture_entry") or verdict.get("capture_entry"))
    capture_entry_reached = bool(
        capture_entry_payload.get("reached", capture_entry_payload.get("pass", False))
        or _finite_float(capture_entry_payload.get("time_s"))
        or any(_dict_value(row.get("capture_entry")).get("capture_entry_reached") for row in capture_entry_rows + capture_rows)
        or any(_dict_value(row.get("capture_entry_diagnostics")).get("ready_reached_once") for row in capture_entry_rows + capture_rows)
    )
    captured_rows = [
        row
        for row in capture_rows
        if bool(_dict_value(row.get("capture")).get("captured", False))
        or bool(_dict_value(row.get("capture_diagnostics")).get("captured_now", False))
    ]
    secure_rows = [
        row for row in capture_rows if bool(_dict_value(row.get("capture_diagnostics")).get("secure_capture_ready", False))
    ]
    soft_rows = [
        row for row in capture_rows if bool(_dict_value(row.get("capture_diagnostics")).get("soft_capture_handoff_ready", False))
    ]
    zone_rows = [
        row
        for row in rows
        if bool(_dict_value(row.get("zone_score")).get("center_inside_zone", False))
        or bool(_dict_value(row.get("capture_diagnostics")).get("zone_entry_handoff_ready", False))
    ]
    return {
        "capture_entry_reached": bool(capture_entry_reached),
        "capture_entry_row_count": len(capture_entry_rows),
        "capture_row_count": len(capture_rows),
        "capture_observed": bool(captured_rows),
        "capture_count": len(captured_rows),
        "secure_capture_observed": bool(secure_rows),
        "secure_capture_count": len(secure_rows),
        "soft_capture_observed": bool(soft_rows),
        "soft_capture_count": len(soft_rows),
        "zone_entry_observed": bool(zone_rows),
        "zone_entry_count": len(zone_rows),
    }


def _terminal_cause(rows: list[dict[str, Any]], run: dict[str, Any], verdict: dict[str, Any]) -> str:
    for row in reversed(rows):
        for payload in (
            _dict_value(row.get("object_centric_policy")),
            _dict_value(row.get("capture_diagnostics")),
            _dict_value(row.get("capture_entry_diagnostics")),
        ):
            cause = str(payload.get("terminal_cause", "") or "")
            if cause:
                return cause
    return str(
        run.get("failure_reason")
        or run.get("status")
        or verdict.get("failure_reason")
        or verdict.get("mission_error")
        or ""
    )


def _safety_stop_count(rows: list[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        command = _command_from_row(row)
        mode = str(command.get("mode", "") or row.get("mode", "") or "")
        policy = _dict_value(row.get("object_centric_policy"))
        guard = str(policy.get("guard_rejection_reason", "") or "")
        if guard or any(token in mode for token in ("guard", "abort", "timeout", "safe_stop")):
            count += 1
    return count


def _extract_run_evidence(run_spec: dict[str, Any], *, source_summary_path: Path) -> dict[str, Any]:
    run = _dict_value(run_spec.get("run"))
    mission_root = _mission_root_path(run, source_summary_path=source_summary_path)
    state_history_path = _state_history_path(run, mission_root, source_summary_path=source_summary_path)
    state_history_status = "missing"
    rows: list[dict[str, Any]] = []
    if state_history_path is not None:
        state_history_status, rows = _load_jsonl(state_history_path)
    verdict = _mission_verdict(run, mission_root, source_summary_path=source_summary_path)
    pass_value = _boolish(run.get("pass", verdict.get("pass", verdict.get("mission_completed_pass"))))
    pre_stage_pass = _boolish(
        run.get(
            "pre_stage_handoff_pass",
            verdict.get("pre_stage_handoff_pass", _dict_value(verdict.get("pre_stage")).get("pass")),
        )
    )
    capture = _capture_metrics(rows, run, verdict)
    premature_motion = _premature_ball_motion(rows)
    object_rows = _object_policy_rows(rows)
    return {
        "source_label": str(run_spec.get("source_label", "")),
        "source_kind": str(run_spec.get("source_kind", "")),
        "case_id": str(run_spec.get("case_id", "") or "unknown_case"),
        "run_label": str(run_spec.get("run_label", "")),
        "run_index": int(run_spec.get("run_index") or 0),
        "mission_root": str(mission_root or ""),
        "state_history_path": str(state_history_path or ""),
        "state_history_status": state_history_status,
        "pass": bool(pass_value) if pass_value is not None else False,
        "pre_stage_handoff_pass": bool(pre_stage_pass) if pre_stage_pass is not None else False,
        "failure_stage": str(run.get("failure_stage") or verdict.get("failure_stage") or ""),
        "failure_reason": str(run.get("failure_reason") or verdict.get("failure_reason") or verdict.get("mission_error") or ""),
        "terminal_cause": _terminal_cause(rows, run, verdict),
        "phase_counts": _phase_counts(rows),
        "object_centric_policy_row_count": len(object_rows),
        "pre_stage_handoff": {
            "pass": bool(pre_stage_pass) if pre_stage_pass is not None else False,
        },
        "capture": capture,
        "first_contact_alignment_deg": _round_number(_first_contact_alignment(rows, run, verdict)),
        "premature_ball_motion": premature_motion,
        "safety_stop_count": _safety_stop_count(rows),
        "command_summary": _command_summary(rows),
        "object_centric_policy_tail": object_rows[-5:],
    }


def analyze_artifacts(campaign_id: str, artifacts: list[tuple[str, Path]]) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    artifact_summaries: list[dict[str, Any]] = []
    for label, raw_path in artifacts:
        summary_path = raw_path if raw_path.is_absolute() else (REPO_ROOT / raw_path)
        summary = _load_json_object(summary_path)
        run_specs = _iter_runs(label, summary_path, summary)
        artifact_summaries.append(
            {
                "label": label,
                "summary_path": str(summary_path),
                "source_run_count": len(run_specs),
            }
        )
        for run_spec in run_specs:
            runs.append(_extract_run_evidence(run_spec, source_summary_path=summary_path))

    return {
        "campaign_id": str(campaign_id),
        "generated_utc": utc_now(),
        "analyzer": OUTPUT_KIND,
        "portfolio_stress_status": "blocked_no_ingestion",
        "artifact_count": len(artifacts),
        "run_count": len(runs),
        "pass_count": sum(1 for run in runs if bool(run.get("pass", False))),
        "pre_stage_handoff_pass_count": sum(1 for run in runs if bool(run.get("pre_stage_handoff_pass", False))),
        "capture_entry_reached_count": sum(1 for run in runs if bool(_dict_value(run.get("capture")).get("capture_entry_reached", False))),
        "capture_observed_count": sum(1 for run in runs if bool(_dict_value(run.get("capture")).get("capture_observed", False))),
        "zone_entry_observed_count": sum(1 for run in runs if bool(_dict_value(run.get("capture")).get("zone_entry_observed", False))),
        "premature_ball_motion_count": sum(1 for run in runs if bool(_dict_value(run.get("premature_ball_motion")).get("observed", False))),
        "safety_stop_count": sum(int(run.get("safety_stop_count", 0) or 0) for run in runs),
        "artifact_summaries": artifact_summaries,
        "runs": runs,
    }


def _markdown_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("|", "\\|")


def render_scorecard(summary: dict[str, Any]) -> str:
    lines = [
        "# Gather Object-Centric Policy Evaluator",
        "",
        f"- Campaign: `{summary.get('campaign_id', '')}`",
        f"- Runs summarized: `{summary.get('run_count', 0)}`",
        f"- Passes: `{summary.get('pass_count', 0)}`",
        f"- Pre-stage handoff passes: `{summary.get('pre_stage_handoff_pass_count', 0)}`",
        f"- Capture-entry reached: `{summary.get('capture_entry_reached_count', 0)}`",
        f"- Capture observed: `{summary.get('capture_observed_count', 0)}`",
        f"- Zone entry observed: `{summary.get('zone_entry_observed_count', 0)}`",
        f"- Premature ball motion runs: `{summary.get('premature_ball_motion_count', 0)}`",
        "- Portfolio/stress status: `blocked_no_ingestion`",
        "",
        "| Source | Case | Run | Pass | Pre-stage | Capture-entry | Capture | Zone | Premature ball m | First contact deg | Safety stops | Mode churn | Terminal |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for raw_run in _list_value(summary.get("runs")):
        run = _dict_value(raw_run)
        capture = _dict_value(run.get("capture"))
        premature = _dict_value(run.get("premature_ball_motion"))
        command = _dict_value(run.get("command_summary"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_value(run.get("source_label")),
                    _markdown_value(run.get("case_id")),
                    _markdown_value(run.get("run_index")),
                    _markdown_value(run.get("pass")),
                    _markdown_value(run.get("pre_stage_handoff_pass")),
                    _markdown_value(capture.get("capture_entry_reached")),
                    _markdown_value(capture.get("capture_observed")),
                    _markdown_value(capture.get("zone_entry_observed")),
                    _markdown_value(premature.get("max_m")),
                    _markdown_value(run.get("first_contact_alignment_deg")),
                    _markdown_value(run.get("safety_stop_count")),
                    _markdown_value(command.get("mode_churn_count")),
                    _markdown_value(run.get("terminal_cause") or run.get("failure_reason")),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def write_outputs(summary: dict[str, Any], *, repo_root: Path = REPO_ROOT) -> Path:
    output_root = ensure_dir(repo_root / "artifacts" / "session" / str(summary["campaign_id"]) / OUTPUT_KIND)
    summary_path = output_root / "object_centric_policy_summary.json"
    write_json(summary_path, summary)
    (output_root / "scorecard.md").write_text(render_scorecard(summary), encoding="utf-8")
    return summary_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        type=parse_artifact_spec,
        help="Existing summary artifact as label=path. Supports matrix, repeatability, and mission verdict summaries.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if not args.artifact:
        parser.error("at least one --artifact label=path is required")
    summary = analyze_artifacts(args.campaign_id, args.artifact)
    summary_path = write_outputs(summary)
    print(f"OBJECT_CENTRIC_POLICY_SUMMARY={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
