#!/usr/bin/env python3
"""Summarize FollowPath controller evidence from existing gather artifacts."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from llm_supervisor_core import ensure_dir
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_KIND = "gather_follow_path_research_analyzer"
FOLLOW_PATH_EVENTS = {
    "nav2_follow_path_reacquire_dispatch",
    "nav2_follow_path_reacquire_complete",
    "nav2_follow_path_reacquire_plan_blocked",
}
SEMANTIC_KINDS = (
    "start",
    "escape_clear",
    "corridor_approach",
    "port",
    "handoff_align",
    "handoff_yaw",
)


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


def _first_finite(*values: Any) -> float | None:
    for value in values:
        number = _finite_float(value)
        if number is not None:
            return number
    return None


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


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


def _iter_runs(
    source_label: str,
    source_summary_path: Path,
    summary: dict[str, Any],
) -> list[dict[str, Any]]:
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
                        "context": {},
                    }
                )
        return extracted

    for index, raw_entry in enumerate(_list_value(summary.get("runs")), start=1):
        entry = _dict_value(raw_entry)
        nested_runs = _list_value(entry.get("runs"))
        if nested_runs:
            entry_label = str(entry.get("label", "") or f"entry_{index}")
            for nested_index, raw_run in enumerate(nested_runs, start=1):
                run = _dict_value(raw_run)
                extracted.append(
                    {
                        "source_label": source_label,
                        "source_kind": "research_reset",
                        "case_id": str(run.get("case_id", "") or _case_id_from_label(entry_label)),
                        "run_label": f"{source_label}:{entry_label}:run_{nested_index}",
                        "run_index": int(run.get("run_index") or nested_index),
                        "run": run,
                        "context": entry,
                    }
                )
        else:
            extracted.append(
                {
                    "source_label": source_label,
                    "source_kind": "gather_mission_repeatability",
                    "case_id": str(entry.get("case_id", "") or _case_id_from_label(source_label)),
                    "run_label": f"{source_label}:run_{int(entry.get('run_index') or index)}",
                    "run_index": int(entry.get("run_index") or index),
                    "run": entry,
                    "context": {},
                }
            )
    return extracted


def _case_id_from_label(label: str) -> str:
    text = str(label or "").lower()
    for case_id in ("backside180", "plus45", "minus45", "zero"):
        if case_id in text:
            return case_id
    return "unknown_case"


def _first_matching_row(rows: list[dict[str, Any]], event_type: str) -> dict[str, Any]:
    for row in rows:
        if row.get("event_type") == event_type:
            return row
    return {}


def _last_matching_row(rows: list[dict[str, Any]], event_type: str) -> dict[str, Any]:
    for row in reversed(rows):
        if row.get("event_type") == event_type:
            return row
    return {}


def _pose_xy(pose: Any) -> tuple[float, float] | None:
    payload = _dict_value(pose)
    x = _finite_float(payload.get("x"))
    y = _finite_float(payload.get("y"))
    if x is None or y is None:
        return None
    return float(x), float(y)


def _pose_yaw(pose: Any) -> float | None:
    return _finite_float(_dict_value(pose).get("yaw"))


def _angle_delta_deg(a: float, b: float) -> float:
    return math.degrees(math.atan2(math.sin(float(b) - float(a)), math.cos(float(b) - float(a))))


def _segment_clearance(start: Any, end: Any, point: Any) -> float | None:
    start_xy = _pose_xy(start)
    end_xy = _pose_xy(end)
    point_xy = _pose_xy(point)
    if start_xy is None or end_xy is None or point_xy is None:
        return None
    ax, ay = start_xy
    bx, by = end_xy
    px, py = point_xy
    dx = bx - ax
    dy = by - ay
    denom = (dx * dx) + (dy * dy)
    if denom <= 1.0e-9:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, (((px - ax) * dx) + ((py - ay) * dy)) / denom))
    nearest_x = ax + (t * dx)
    nearest_y = ay + (t * dy)
    return math.hypot(px - nearest_x, py - nearest_y)


def _semantic_path_kinds(path_poses: list[Any]) -> list[str]:
    kinds: list[str] = []
    for pose in path_poses:
        kind = str(_dict_value(pose).get("kind", "") or "")
        if kind in SEMANTIC_KINDS and kind not in kinds:
            kinds.append(kind)
    return kinds


def _path_geometry(path_poses: list[Any], ball_pose: dict[str, Any]) -> dict[str, Any]:
    segments: list[dict[str, Any]] = []
    for index in range(1, len(path_poses)):
        start = _dict_value(path_poses[index - 1])
        end = _dict_value(path_poses[index])
        start_xy = _pose_xy(start)
        end_xy = _pose_xy(end)
        if start_xy is None or end_xy is None:
            continue
        start_yaw = _pose_yaw(start)
        end_yaw = _pose_yaw(end)
        heading_delta = _angle_delta_deg(start_yaw, end_yaw) if start_yaw is not None and end_yaw is not None else None
        segments.append(
            {
                "from_kind": str(start.get("kind", "") or ""),
                "to_kind": str(end.get("kind", "") or ""),
                "length_m": _round_number(math.hypot(end_xy[0] - start_xy[0], end_xy[1] - start_xy[1])),
                "yaw_delta_deg": _round_number(heading_delta),
                "ball_clearance_m": _round_number(_segment_clearance(start, end, ball_pose)),
            }
        )

    lengths = [_finite_float(segment.get("length_m")) for segment in segments]
    yaw_deltas = [_finite_float(segment.get("yaw_delta_deg")) for segment in segments]
    clearances = [_finite_float(segment.get("ball_clearance_m")) for segment in segments]
    path_kinds = [str(_dict_value(pose).get("kind", "") or "") for pose in path_poses]
    return {
        "path_pose_count": len(path_poses),
        "semantic_path_kinds": _semantic_path_kinds(path_poses),
        "handoff_align_present": any(kind.startswith("handoff_align") for kind in path_kinds),
        "handoff_yaw_present": any(kind.startswith("handoff_yaw") for kind in path_kinds),
        "terminal_kind": path_kinds[-1] if path_kinds else "",
        "max_segment_length_m": _round_number(max((value for value in lengths if value is not None), default=None)),
        "max_abs_yaw_delta_deg": _round_number(max((abs(value) for value in yaw_deltas if value is not None), default=None)),
        "min_segment_ball_clearance_m": _round_number(min((value for value in clearances if value is not None), default=None)),
        "terminal_segments_tail": segments[-8:],
    }


def _progress_samples(diagnostics: dict[str, Any]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    seen: set[tuple[float | None, int | None, str]] = set()

    def append_progress(raw_sample: Any) -> None:
        sample = _dict_value(raw_sample)
        progress = _dict_value(sample.get("path_progress")) if "path_progress" in sample else sample
        if not progress:
            return
        elapsed = _finite_float(sample.get("elapsed_s", progress.get("elapsed_s")))
        index_value = _finite_float(progress.get("nearest_path_index"))
        key = (
            round(elapsed, 6) if elapsed is not None else None,
            int(index_value) if index_value is not None else None,
            str(progress.get("nearest_path_kind", "") or ""),
        )
        if key in seen:
            return
        seen.add(key)
        samples.append(
            {
                "elapsed_s": _round_number(elapsed),
                "nearest_path_index": int(index_value) if index_value is not None else None,
                "nearest_path_kind": str(progress.get("nearest_path_kind", "") or ""),
                "nearest_path_distance_m": _round_number(_finite_float(progress.get("nearest_path_distance_m"))),
                "remaining_path_pose_count": (
                    int(_finite_float(progress.get("remaining_path_pose_count")))
                    if _finite_float(progress.get("remaining_path_pose_count")) is not None
                    else None
                ),
                "terminal_path_distance_m": _round_number(_finite_float(progress.get("terminal_path_distance_m"))),
                "terminal_yaw_error_deg": _round_number(_finite_float(progress.get("terminal_yaw_error_deg"))),
            }
        )

    for sample in _list_value(diagnostics.get("path_progress_samples")):
        append_progress(sample)
    append_progress(diagnostics.get("path_progress_last"))
    for sample in _list_value(diagnostics.get("odom_samples")):
        append_progress(sample)
    append_progress(_dict_value(diagnostics.get("odom_last")).get("path_progress"))

    samples.sort(key=lambda sample: _finite_float(sample.get("elapsed_s")) if _finite_float(sample.get("elapsed_s")) is not None else -1.0)
    return samples


def _progress_summary(diagnostics: dict[str, Any]) -> dict[str, Any]:
    samples = _progress_samples(diagnostics)
    terminal_distances = [_finite_float(sample.get("terminal_path_distance_m")) for sample in samples]
    yaw_errors = [_finite_float(sample.get("terminal_yaw_error_deg")) for sample in samples]
    last_meter = [sample for sample in samples if (_finite_float(sample.get("terminal_path_distance_m")) or math.inf) <= 1.0]
    transitions: list[dict[str, Any]] = []
    last_key: tuple[str, int | None] | None = None
    for sample in samples:
        key = (str(sample.get("nearest_path_kind", "") or ""), sample.get("nearest_path_index"))
        if key != last_key:
            transitions.append(sample)
            last_key = key
    return {
        "sample_count": len(samples),
        "best_terminal_path_distance_m": _round_number(min((value for value in terminal_distances if value is not None), default=None)),
        "best_abs_terminal_yaw_error_deg": _round_number(min((abs(value) for value in yaw_errors if value is not None), default=None)),
        "last_sample": samples[-1] if samples else {},
        "last_meter_sample_count": len(last_meter),
        "last_meter_trace_tail": last_meter[-8:],
        "kind_transitions": transitions[-12:],
    }


def _cmd_summary(diagnostics: dict[str, Any]) -> dict[str, Any]:
    samples = [_dict_value(sample) for sample in _list_value(diagnostics.get("cmd_vel_samples")) if isinstance(sample, dict)]
    last = _dict_value(diagnostics.get("cmd_vel_last"))
    linear_values = [_finite_float(sample.get("linear_x")) for sample in samples + ([last] if last else [])]
    angular_values = [_finite_float(sample.get("angular_z")) for sample in samples + ([last] if last else [])]
    return {
        "topic_counts": _dict_value(diagnostics.get("cmd_vel_counts")),
        "sample_count": len(samples),
        "first_sample": samples[0] if samples else {},
        "last_sample": last or (samples[-1] if samples else {}),
        "max_abs_linear_x": _round_number(max((abs(value) for value in linear_values if value is not None), default=None)),
        "max_abs_angular_z": _round_number(max((abs(value) for value in angular_values if value is not None), default=None)),
        "tail": samples[-8:],
    }


def _feedback_summary(diagnostics: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    samples = [_dict_value(sample) for sample in _list_value(diagnostics.get("feedback_samples") or result.get("feedback_samples"))]
    last = _dict_value(diagnostics.get("feedback_last") or result.get("feedback_last"))
    distances: list[float] = []
    for sample in samples + ([last] if last else []):
        feedback = _dict_value(sample.get("feedback"))
        value = _finite_float(feedback.get("distance_to_goal"))
        if value is not None:
            distances.append(value)
    return {
        "feedback_count": int(_finite_float(diagnostics.get("feedback_count") or result.get("feedback_count")) or 0),
        "sample_count": len(samples),
        "first_distance_to_goal": _round_number(distances[0] if distances else None),
        "last_distance_to_goal": _round_number(distances[-1] if distances else None),
        "min_sampled_distance_to_goal": _round_number(min(distances) if distances else None),
        "tail": samples[-6:],
    }


def _param_summary(source_summary_path: Path, context: dict[str, Any]) -> dict[str, Any]:
    loaded = _dict_value(context.get("loaded_param_summary"))
    matches = _dict_value(context.get("param_matches"))
    path_text = str(context.get("params_path", "") or "")
    if loaded or matches:
        return {
            "source_path": path_text,
            "loaded": loaded,
            "matches": matches,
        }

    for parent in [source_summary_path.parent, *source_summary_path.parents]:
        params_root = parent / "controller_params"
        comparison_path = params_root / "mppi_param_comparison.json"
        if comparison_path.exists():
            payload = _load_json_object(comparison_path)
            return {
                "source_path": str(comparison_path),
                "loaded": _dict_value(payload.get("loaded")),
                "matches": _dict_value(payload.get("matches")),
            }
        loaded_path = params_root / "mppi_param_loaded_summary.json"
        if loaded_path.exists():
            payload = _load_json_object(loaded_path)
            return {
                "source_path": str(loaded_path),
                "loaded": payload,
                "matches": {},
            }
    return {"source_path": "", "loaded": {}, "matches": {}}


def _extract_run_evidence(
    *,
    run_spec: dict[str, Any],
    source_summary_path: Path,
) -> dict[str, Any]:
    run = _dict_value(run_spec.get("run"))
    context = _dict_value(run_spec.get("context"))
    mission_root = _mission_root_path(run, source_summary_path=source_summary_path)
    state_history_path = _state_history_path(run, mission_root, source_summary_path=source_summary_path)
    state_history_status = "missing"
    rows: list[dict[str, Any]] = []
    if state_history_path is not None:
        state_history_status, rows = _load_jsonl(state_history_path)
    dispatch_row = _first_matching_row(rows, "nav2_follow_path_reacquire_dispatch")
    complete_row = _last_matching_row(rows, "nav2_follow_path_reacquire_complete")
    blocked_row = _last_matching_row(rows, "nav2_follow_path_reacquire_plan_blocked")
    follow_path_row = complete_row or blocked_row or dispatch_row
    plan = _dict_value(dispatch_row.get("nav2_follow_path_plan") or follow_path_row.get("nav2_follow_path_plan"))
    result = _dict_value(follow_path_row.get("nav2_follow_path_result"))
    diagnostics = _dict_value(follow_path_row.get("nav2_follow_path_diagnostics"))
    path_poses = _list_value(dispatch_row.get("nav2_follow_path_path_poses") or plan.get("path_poses"))
    ball_pose = _dict_value(dispatch_row.get("ball_pose") or follow_path_row.get("ball_pose"))
    verdict = _dict_value(run.get("mission_verdict") or run.get("summary"))
    follow_path_compact = _dict_value(run.get("follow_path"))
    params = _param_summary(source_summary_path, context)

    dispatch_status = str(
        follow_path_row.get("nav2_follow_path_dispatch_status")
        or result.get("dispatch_status")
        or follow_path_compact.get("dispatch_status")
        or ""
    )
    status_text = str(diagnostics.get("status_text") or result.get("status_text") or follow_path_compact.get("status_text") or "")
    terminal_path_distance = _first_finite(
        follow_path_row.get("nav2_follow_path_terminal_path_distance_m"),
        diagnostics.get("completion_terminal_path_distance_m"),
        follow_path_compact.get("terminal_path_distance_m"),
    )
    terminal_yaw_error = _first_finite(
        follow_path_row.get("nav2_follow_path_terminal_yaw_error_deg"),
        diagnostics.get("completion_terminal_yaw_error_deg"),
        follow_path_compact.get("terminal_yaw_error_deg"),
    )
    ball_motion = _first_finite(
        follow_path_row.get("nav2_follow_path_ball_motion_m"),
        diagnostics.get("ball_motion_m"),
        follow_path_compact.get("ball_motion_m"),
    )
    robot_motion = _first_finite(
        follow_path_row.get("nav2_follow_path_robot_motion_m"),
        diagnostics.get("robot_motion_m"),
        follow_path_compact.get("robot_motion_m"),
    )

    return {
        "source_label": str(run_spec.get("source_label", "")),
        "source_kind": str(run_spec.get("source_kind", "")),
        "case_id": str(run_spec.get("case_id", "") or "unknown_case"),
        "run_label": str(run_spec.get("run_label", "")),
        "run_index": int(run_spec.get("run_index") or 0),
        "mission_root": str(mission_root or ""),
        "state_history_path": str(state_history_path or ""),
        "state_history_status": state_history_status,
        "state_history_follow_path_event_count": sum(1 for row in rows if row.get("event_type") in FOLLOW_PATH_EVENTS),
        "pass": bool(run.get("pass", verdict.get("pass", False))),
        "pre_stage_handoff_pass": bool(run.get("pre_stage_handoff_pass", verdict.get("pre_stage_handoff_pass", False))),
        "failure_stage": str(run.get("failure_stage") or verdict.get("failure_stage") or ""),
        "failure_reason": str(run.get("failure_reason") or verdict.get("failure_reason") or verdict.get("mission_error") or ""),
        "dispatch_status": dispatch_status,
        "status_text": status_text,
        "error": str(result.get("error") or diagnostics.get("error") or follow_path_compact.get("error") or ""),
        "timed_out": bool(result.get("timed_out", diagnostics.get("timed_out", dispatch_status == "goal_result_timeout"))),
        "controller_id": str(plan.get("controller_id") or dispatch_row.get("nav2_follow_path_controller_id") or diagnostics.get("controller_id") or ""),
        "goal_checker_id": str(plan.get("goal_checker_id") or dispatch_row.get("nav2_follow_path_goal_checker_id") or diagnostics.get("goal_checker_id") or ""),
        "ball_motion_m": _round_number(ball_motion),
        "robot_motion_m": _round_number(robot_motion),
        "terminal_path_distance_m": _round_number(terminal_path_distance),
        "terminal_yaw_error_deg": _round_number(terminal_yaw_error),
        "nearest_path_kind": str(
            _dict_value(diagnostics.get("path_progress_last")).get("nearest_path_kind")
            or follow_path_compact.get("nearest_path_kind")
            or ""
        ),
        "remaining_path_pose_count": int(
            _finite_float(_dict_value(diagnostics.get("path_progress_last")).get("remaining_path_pose_count"))
            or _finite_float(follow_path_compact.get("remaining_path_pose_count"))
            or 0
        ),
        "path_geometry": _path_geometry(path_poses, ball_pose),
        "path_progress": _progress_summary(diagnostics),
        "cmd_vel": _cmd_summary(diagnostics),
        "feedback": _feedback_summary(diagnostics, result),
        "loaded_controller_params": params,
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
            runs.append(_extract_run_evidence(run_spec=run_spec, source_summary_path=summary_path))

    pre_stage_passes = sum(1 for run in runs if run.get("pre_stage_handoff_pass"))
    handoff_align_runs = sum(1 for run in runs if _dict_value(run.get("path_geometry")).get("handoff_align_present"))
    return {
        "campaign_id": str(campaign_id),
        "generated_utc": utc_now(),
        "analyzer": OUTPUT_KIND,
        "portfolio_stress_status": "blocked_no_ingestion",
        "artifact_count": len(artifacts),
        "run_count": len(runs),
        "pre_stage_handoff_pass_count": pre_stage_passes,
        "pre_stage_handoff_fail_count": len(runs) - pre_stage_passes,
        "handoff_align_path_run_count": handoff_align_runs,
        "artifact_summaries": artifact_summaries,
        "runs": runs,
    }


def _markdown_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    return text.replace("\n", " ").replace("|", "\\|")


def render_scorecard(summary: dict[str, Any]) -> str:
    lines = [
        "# Gather FollowPath Research Analyzer",
        "",
        f"- Campaign: `{summary.get('campaign_id', '')}`",
        f"- Runs summarized: `{summary.get('run_count', 0)}`",
        f"- Pre-stage handoff passes: `{summary.get('pre_stage_handoff_pass_count', 0)}`",
        f"- Handoff-align path runs: `{summary.get('handoff_align_path_run_count', 0)}`",
        "- Portfolio/stress status: `blocked_no_ingestion`",
        "",
        "| Source | Case | Run | Pre-stage | Status | Nearest | Terminal m | Yaw deg | Ball m | Robot m | Progress samples | Handoff align | Param match |",
        "|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for run in _list_value(summary.get("runs")):
        row = _dict_value(run)
        progress = _dict_value(row.get("path_progress"))
        geometry = _dict_value(row.get("path_geometry"))
        params = _dict_value(row.get("loaded_controller_params"))
        matches = _dict_value(params.get("matches"))
        true_matches = [name for name, value in matches.items() if bool(value)]
        param_match = ",".join(true_matches) if true_matches else ("none" if matches else "")
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_value(row.get("source_label")),
                    _markdown_value(row.get("case_id")),
                    _markdown_value(row.get("run_index")),
                    _markdown_value(row.get("pre_stage_handoff_pass")),
                    _markdown_value(row.get("dispatch_status") or row.get("status_text")),
                    _markdown_value(row.get("nearest_path_kind")),
                    _markdown_value(row.get("terminal_path_distance_m")),
                    _markdown_value(row.get("terminal_yaw_error_deg")),
                    _markdown_value(row.get("ball_motion_m")),
                    _markdown_value(row.get("robot_motion_m")),
                    _markdown_value(progress.get("sample_count")),
                    _markdown_value(geometry.get("handoff_align_present")),
                    _markdown_value(param_match),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def write_outputs(summary: dict[str, Any], *, repo_root: Path = REPO_ROOT) -> Path:
    output_root = ensure_dir(repo_root / "artifacts" / "session" / str(summary["campaign_id"]) / OUTPUT_KIND)
    summary_path = output_root / "follow_path_research_summary.json"
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
        help="Existing summary artifact as label=path. Supports goal-side matrix, repeatability, and research reset summaries.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if not args.artifact:
        parser.error("at least one --artifact label=path is required")
    summary = analyze_artifacts(args.campaign_id, args.artifact)
    summary_path = write_outputs(summary)
    print(f"FOLLOW_PATH_RESEARCH_SUMMARY={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
