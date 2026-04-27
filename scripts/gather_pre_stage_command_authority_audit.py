#!/usr/bin/env python3
"""Audit pre-stage command authority from blocked gather-control artifacts."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

from llm_supervisor_core import ensure_dir
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_KIND = "gather_pre_stage_command_authority_audit"
PRIMARY_CASE_IDS = ("zero", "plus45")
SECONDARY_CASE_IDS = ("minus45", "backside180")
AUDIT_LABELS = (
    "command_realization_limited",
    "geometry_progress_limited",
    "timeout_despite_progress",
    "handoff_threshold_mismatch",
    "ball_safety_blocked",
    "missing_motion_evidence",
)
RECOMMEND_MOTION_PROBE = "run_minimal_motion_realization_probe"
RECOMMEND_ARCHITECTURE_REVIEW = "architecture_review_before_next_branch"
RECOMMEND_HANDOFF_GATE_AUDIT = "handoff_gate_contract_audit"
BALL_MOTION_THRESHOLD_M = 0.05
BALL_CLEARANCE_CONTACT_THRESHOLD_M = 0.20
NONZERO_LINEAR_EPS = 0.01
NONZERO_ANGULAR_EPS = 0.02
REALIZED_DISPLACEMENT_MIN_M = 0.05
REALIZED_YAW_MIN_RAD = 0.05
OBJECTIVE_PROGRESS_MIN_M = 0.10
OBJECTIVE_YAW_PROGRESS_MIN_DEG = 5.0


def sanitize_branch_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name or "").strip())
    while ".." in cleaned:
        cleaned = cleaned.replace("..", "_")
    cleaned = re.sub(r"_+", "_", cleaned)
    cleaned = cleaned.strip("._-")
    if not cleaned:
        raise ValueError(f"Invalid empty branch name: {name!r}")
    if cleaned in {".", ".."} or "/" in cleaned or "\\" in cleaned:
        raise ValueError(f"Invalid branch name for artifact path: {name!r}")
    return cleaned


def parse_branch_spec(spec: str) -> tuple[str, Path]:
    if "=" not in spec:
        raise argparse.ArgumentTypeError(f"--branch must be name=path, got {spec!r}")
    name, path_text = spec.split("=", 1)
    name = name.strip()
    path_text = path_text.strip()
    if not name or not path_text:
        raise argparse.ArgumentTypeError(f"--branch must be name=path, got {spec!r}")
    sanitize_branch_name(name)
    return name, Path(path_text)


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Summary does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Summary must be a JSON object: {path}")
    return payload


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


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


def _boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "pass", "passed"}:
            return True
        if normalized in {"false", "0", "no", "n", "fail", "failed"}:
            return False
    return None


def _int_value(value: Any) -> int:
    number = _finite_float(value)
    if number is None:
        return 0
    return int(number)


def _round_number(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _normalize_angle(value: float) -> float:
    while value > math.pi:
        value -= 2.0 * math.pi
    while value < -math.pi:
        value += 2.0 * math.pi
    return value


def _ordered_unique(values: list[str]) -> list[str]:
    ordered: list[str] = []
    for value in values:
        if value and value not in ordered:
            ordered.append(value)
    return ordered


def _ordered_case_ids(cases: list[dict[str, Any]]) -> list[str]:
    by_id = {str(case.get("case_id", "") or ""): case for case in cases}
    ordered = [case_id for case_id in (*PRIMARY_CASE_IDS, *SECONDARY_CASE_IDS) if case_id in by_id]
    ordered.extend(case_id for case_id in by_id if case_id and case_id not in ordered)
    return ordered


def _resolve_optional_path(raw_path: Any, *, source_summary_path: Path) -> Path | None:
    text = str(raw_path or "").strip()
    if not text:
        return None
    path = Path(text)
    if path.is_absolute():
        return path
    repo_path = REPO_ROOT / path
    if repo_path.exists():
        return repo_path
    return source_summary_path.parent / path


def _first_run(case: dict[str, Any]) -> dict[str, Any]:
    for run in _list_value(case.get("runs")):
        if isinstance(run, dict):
            return run
    return {}


def _mission_verdict_path(run: dict[str, Any], *, source_summary_path: Path) -> Path | None:
    path = _resolve_optional_path(run.get("mission_verdict_path"), source_summary_path=source_summary_path)
    if path is not None:
        return path
    summary_path = _resolve_optional_path(run.get("summary_path"), source_summary_path=source_summary_path)
    if summary_path is not None:
        return summary_path.parent / "mission_verdict.json"
    return None


def _mission_root_path(
    run: dict[str, Any],
    mission_verdict_path: Path | None,
    *,
    source_summary_path: Path,
) -> Path | None:
    mission_root = _resolve_optional_path(run.get("mission_root"), source_summary_path=source_summary_path)
    if mission_root is not None:
        return mission_root
    if mission_verdict_path is not None:
        return mission_verdict_path.parent
    return None


def _state_history_path(run: dict[str, Any], mission_root: Path | None, *, source_summary_path: Path) -> Path | None:
    explicit = _resolve_optional_path(run.get("state_history_path"), source_summary_path=source_summary_path)
    if explicit is not None:
        return explicit
    if mission_root is not None:
        return mission_root / "state_history.jsonl"
    return None


def _mission_verdict_status(path: Path | None, fallback_payload: Any = None) -> tuple[str, dict[str, Any]]:
    if path is None:
        if isinstance(fallback_payload, dict):
            return "embedded", fallback_payload
        return "not_referenced", {}
    if not path.exists():
        if isinstance(fallback_payload, dict):
            return "embedded_path_missing", fallback_payload
        return "missing", {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        if isinstance(fallback_payload, dict):
            return "embedded_path_unreadable", fallback_payload
        return "unreadable", {}
    return ("available", payload if isinstance(payload, dict) else {})


def _load_jsonl(path: Path | None) -> tuple[str, list[dict[str, Any]]]:
    if path is None:
        return "not_referenced", []
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
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return "available", rows


def _fresh_pre_stage(case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    fresh = _dict_value(case.get("fresh_attempt_approach"))
    pre_stage = _dict_value(fresh.get("pre_stage"))
    capture_entry = _dict_value(fresh.get("capture_entry"))
    return fresh, pre_stage, capture_entry


def _fresh_pre_stage_handoff(case: dict[str, Any]) -> bool | None:
    _fresh, pre_stage, _capture_entry = _fresh_pre_stage(case)
    parsed = _boolish(pre_stage.get("handoff_pass"))
    if parsed is not None:
        return parsed
    return _boolish(case.get("pre_stage_handoff_pass"))


def _fresh_pre_stage_pose_reached(case: dict[str, Any]) -> bool | None:
    _fresh, pre_stage, _capture_entry = _fresh_pre_stage(case)
    parsed = _boolish(pre_stage.get("pose_reached"))
    if parsed is not None:
        return parsed
    return _boolish(case.get("pre_stage_pose_reached"))


def _pose_xy(value: Any) -> tuple[float, float] | None:
    pose = _dict_value(value)
    if "position" in pose and isinstance(pose.get("position"), dict):
        pose = _dict_value(pose.get("position"))
    x = _finite_float(pose.get("x"))
    y = _finite_float(pose.get("y"))
    if x is None or y is None:
        return None
    return float(x), float(y)


def _pose_yaw(value: Any) -> float | None:
    return _finite_float(_dict_value(value).get("yaw"))


def _first_number(values: list[float | None]) -> float | None:
    for value in values:
        if value is not None:
            return float(value)
    return None


def _last_number(values: list[float | None]) -> float | None:
    for value in reversed(values):
        if value is not None:
            return float(value)
    return None


def _max_number(values: list[float | None]) -> float | None:
    finite = [float(value) for value in values if value is not None]
    if not finite:
        return None
    return round(max(finite), 6)


def _min_number(values: list[float | None]) -> float | None:
    finite = [float(value) for value in values if value is not None]
    if not finite:
        return None
    return round(min(finite), 6)


def _observed_reduction(values: list[float | None]) -> float | None:
    first = _first_number(values)
    last = _last_number(values)
    if first is None or last is None:
        return None
    return round(first - last, 6)


def _fresh_pre_stage_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pre_stage_rows = [row for row in rows if str(row.get("phase", "") or "") == "pre_stage"]
    if not pre_stage_rows:
        return []
    attempt_one = [row for row in pre_stage_rows if _int_value(row.get("attempt")) == 1]
    if attempt_one:
        return attempt_one
    attempt_zero = [row for row in pre_stage_rows if _int_value(row.get("attempt")) == 0]
    if attempt_zero:
        return attempt_zero
    initial = [row for row in pre_stage_rows if str(row.get("attempt_kind", "") or "") == "initial_visit"]
    return initial or pre_stage_rows


def _command_from_row(row: dict[str, Any]) -> dict[str, Any]:
    command = _dict_value(row.get("selected_command"))
    if command:
        return command
    return _dict_value(row.get("latest_control_command"))


def _snapshot_from_row(row: dict[str, Any]) -> dict[str, Any]:
    snapshot = _dict_value(row.get("pre_stage"))
    if snapshot:
        return snapshot
    for key in (
        "pre_stage_path_tracker_measured_pre_stage",
        "pre_stage_reacquire_fsm_measured_pre_stage",
        "local_planner_measured_pre_stage",
        "docking_reacquire_measured_pre_stage",
        "handoff_yaw_servo_measured_pre_stage",
    ):
        snapshot = _dict_value(row.get(key))
        if snapshot:
            return snapshot
    return {}


def _bool_from_row_or_snapshot(row: dict[str, Any], snapshot: dict[str, Any], keys: tuple[str, ...]) -> bool | None:
    for key in keys:
        parsed = _boolish(row.get(key))
        if parsed is not None:
            return parsed
    for key in keys:
        parsed = _boolish(snapshot.get(key))
        if parsed is not None:
            return parsed
    return None


def _metric_series(rows: list[dict[str, Any]], key: str) -> list[float | None]:
    return [_finite_float(_snapshot_from_row(row).get(key)) for row in rows]


def _waypoint_distance_series(rows: list[dict[str, Any]]) -> list[float | None]:
    values: list[float | None] = []
    for row in rows:
        value = None
        for key in (
            "pre_stage_path_tracker_waypoint_distance_m",
            "pre_stage_reacquire_fsm_target_distance_m",
            "docking_reacquire_target_distance_m",
            "local_planner_target_distance_m",
        ):
            value = _finite_float(row.get(key))
            if value is not None:
                break
        values.append(value)
    return values


def _progress_flags(metrics: dict[str, Any]) -> tuple[bool, bool]:
    motion_realized = (
        float(metrics.get("robot_displacement_m") or 0.0) >= REALIZED_DISPLACEMENT_MIN_M
        or float(metrics.get("robot_cumulative_yaw_change_rad") or 0.0) >= REALIZED_YAW_MIN_RAD
    )
    progress_values = (
        float(metrics.get("projection_reduction_m") or 0.0),
        float(metrics.get("distance_reduction_m") or 0.0),
        float(metrics.get("lateral_reduction_m") or 0.0),
        float(metrics.get("waypoint_distance_reduction_m") or 0.0),
    )
    objective_progress = any(value >= OBJECTIVE_PROGRESS_MIN_M for value in progress_values)
    objective_progress = objective_progress or float(metrics.get("yaw_error_reduction_deg") or 0.0) >= OBJECTIVE_YAW_PROGRESS_MIN_DEG
    return motion_realized, objective_progress


def _motion_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    commands = [_command_from_row(row) for row in rows]
    linear_values = [_finite_float(command.get("linear_x")) for command in commands]
    angular_values = [_finite_float(command.get("angular_z")) for command in commands]
    command_row_count = sum(linear is not None or angular is not None for linear, angular in zip(linear_values, angular_values))
    nonzero_command_count = sum(
        abs(float(linear or 0.0)) > NONZERO_LINEAR_EPS or abs(float(angular or 0.0)) > NONZERO_ANGULAR_EPS
        for linear, angular in zip(linear_values, angular_values)
    )

    robot_poses = [_dict_value(row.get("robot_pose")) for row in rows if _dict_value(row.get("robot_pose"))]
    robot_xy = [_pose_xy(pose) for pose in robot_poses]
    robot_xy = [xy for xy in robot_xy if xy is not None]
    robot_yaws = [_pose_yaw(pose) for pose in robot_poses]
    robot_yaws = [yaw for yaw in robot_yaws if yaw is not None]

    displacement = None
    if len(robot_xy) >= 2:
        first_xy = robot_xy[0]
        last_xy = robot_xy[-1]
        displacement = math.hypot(last_xy[0] - first_xy[0], last_xy[1] - first_xy[1])

    net_yaw = None
    cumulative_yaw = None
    if len(robot_yaws) >= 2:
        net_yaw = abs(_normalize_angle(robot_yaws[-1] - robot_yaws[0]))
        cumulative = 0.0
        for previous, current in zip(robot_yaws, robot_yaws[1:]):
            cumulative += abs(_normalize_angle(current - previous))
        cumulative_yaw = cumulative

    projection_values = _metric_series(rows, "robot_longitudinal_projection_m")
    lateral_values = _metric_series(rows, "robot_lateral_error_m")
    distance_values = _metric_series(rows, "pre_stage_pose_distance_m")
    yaw_error_values = _metric_series(rows, "yaw_error_deg")
    waypoint_distance_values = _waypoint_distance_series(rows)
    projected_projection_gains = [_finite_float(row.get("projected_projection_gain")) for row in rows]
    projected_distance_gains = [_finite_float(row.get("projected_distance_gain")) for row in rows]
    projected_lateral_gains = [_finite_float(row.get("projected_lateral_gain")) for row in rows]
    projected_yaw_gains = [_finite_float(row.get("pre_stage_path_tracker_projected_yaw_gain_deg")) for row in rows]
    ball_motion_values = [
        _finite_float(
            row.get(
                "pre_stage_path_tracker_ball_motion_m",
                row.get(
                    "pre_stage_reacquire_fsm_ball_motion_m",
                    row.get(
                        "local_planner_ball_motion_m",
                        row.get(
                            "docking_reacquire_ball_motion_m",
                            row.get("handoff_yaw_servo_ball_motion_m", row.get("ball_motion_m")),
                        ),
                    ),
                ),
            )
        )
        for row in rows
    ]
    clearance_values = [
        _finite_float(
            row.get(
                "pre_stage_path_tracker_min_ball_clearance_m",
                row.get(
                    "pre_stage_reacquire_fsm_min_ball_clearance_m",
                    row.get(
                        "local_planner_min_ball_clearance_m",
                        row.get("docking_reacquire_min_ball_clearance_m", row.get("min_ball_clearance_m")),
                    ),
                ),
            )
        )
        for row in rows
    ]
    measured_ready_values = [
        _bool_from_row_or_snapshot(
            row,
            _snapshot_from_row(row),
            (
                "pre_stage_path_tracker_measured_handoff_ready",
                "pre_stage_reacquire_fsm_measured_handoff_ready",
                "docking_reacquire_handoff_ready_measured",
                "handoff_yaw_servo_handoff_ready_measured",
                "measured_handoff_ready",
                "pre_stage_pose_reached",
                "handoff_pass",
            ),
        )
        for row in rows
    ]
    projected_ready_values = [
        _bool_from_row_or_snapshot(
            row,
            _dict_value(row.get("pre_stage_path_tracker_projected_pre_stage"))
            or _dict_value(row.get("pre_stage_reacquire_fsm_projected_pre_stage"))
            or _dict_value(row.get("local_planner_projected_pre_stage"))
            or _dict_value(row.get("docking_reacquire_projected_pre_stage")),
            (
                "pre_stage_path_tracker_projected_handoff_ready",
                "pre_stage_reacquire_fsm_projected_handoff_ready",
                "docking_reacquire_handoff_ready_projected",
                "projected_handoff_ready",
                "pre_stage_pose_reached",
                "handoff_pass",
            ),
        )
        for row in rows
    ]

    metrics = {
        "row_count": len(rows),
        "command_row_count": command_row_count,
        "nonzero_command_count": nonzero_command_count,
        "max_abs_linear_x": _max_number([abs(float(value)) if value is not None else None for value in linear_values]),
        "max_abs_angular_z": _max_number([abs(float(value)) if value is not None else None for value in angular_values]),
        "robot_pose_row_count": len(robot_xy),
        "robot_displacement_m": _round_number(displacement),
        "robot_net_yaw_change_rad": _round_number(net_yaw),
        "robot_cumulative_yaw_change_rad": _round_number(cumulative_yaw),
        "projection_start_m": _round_number(_first_number(projection_values)),
        "projection_end_m": _round_number(_last_number(projection_values)),
        "projection_reduction_m": _observed_reduction(projection_values),
        "lateral_start_m": _round_number(_first_number(lateral_values)),
        "lateral_end_m": _round_number(_last_number(lateral_values)),
        "lateral_reduction_m": _observed_reduction(lateral_values),
        "distance_start_m": _round_number(_first_number(distance_values)),
        "distance_end_m": _round_number(_last_number(distance_values)),
        "distance_reduction_m": _observed_reduction(distance_values),
        "yaw_error_start_deg": _round_number(_first_number(yaw_error_values)),
        "yaw_error_end_deg": _round_number(_last_number(yaw_error_values)),
        "yaw_error_reduction_deg": _observed_reduction(yaw_error_values),
        "waypoint_distance_start_m": _round_number(_first_number(waypoint_distance_values)),
        "waypoint_distance_end_m": _round_number(_last_number(waypoint_distance_values)),
        "waypoint_distance_reduction_m": _observed_reduction(waypoint_distance_values),
        "projected_projection_gain_max_m": _max_number(projected_projection_gains),
        "projected_distance_gain_max_m": _max_number(projected_distance_gains),
        "projected_lateral_gain_max_m": _max_number(projected_lateral_gains),
        "projected_abs_yaw_gain_max_deg": _max_number(
            [abs(float(value)) if value is not None else None for value in projected_yaw_gains]
        ),
        "max_ball_motion_m": _max_number(ball_motion_values),
        "min_ball_clearance_m": _min_number(clearance_values),
        "measured_handoff_ready_count": sum(value is True for value in measured_ready_values),
        "projected_handoff_ready_count": sum(value is True for value in projected_ready_values),
    }
    motion_realized, objective_progress = _progress_flags(metrics)
    metrics["motion_realized"] = motion_realized
    metrics["objective_progress_observed"] = objective_progress
    projected_progress_values = (
        float(metrics.get("projected_projection_gain_max_m") or 0.0),
        float(metrics.get("projected_distance_gain_max_m") or 0.0),
        float(metrics.get("projected_lateral_gain_max_m") or 0.0),
    )
    metrics["projected_progress_expected"] = (
        any(value >= OBJECTIVE_PROGRESS_MIN_M for value in projected_progress_values)
        or float(metrics.get("projected_abs_yaw_gain_max_deg") or 0.0) >= OBJECTIVE_YAW_PROGRESS_MIN_DEG
        or int(metrics.get("projected_handoff_ready_count") or 0) > 0
    )
    return metrics


def classify_case(case: dict[str, Any], rows: list[dict[str, Any]], metrics: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    fresh_handoff = _fresh_pre_stage_handoff(case)
    fresh_pose = _fresh_pre_stage_pose_reached(case)
    missing_motion = (
        not rows
        or int(metrics.get("command_row_count") or 0) == 0
        or int(metrics.get("robot_pose_row_count") or 0) < 2
    )
    if missing_motion:
        labels.append("missing_motion_evidence")

    max_ball_motion = _finite_float(metrics.get("max_ball_motion_m"))
    min_clearance = _finite_float(metrics.get("min_ball_clearance_m"))
    if (max_ball_motion is not None and max_ball_motion >= BALL_MOTION_THRESHOLD_M) or (
        min_clearance is not None and min_clearance < BALL_CLEARANCE_CONTACT_THRESHOLD_M
    ):
        labels.append("ball_safety_blocked")

    if fresh_handoff is False and int(metrics.get("measured_handoff_ready_count") or 0) > 0:
        labels.append("handoff_threshold_mismatch")

    nonzero_commands = int(metrics.get("nonzero_command_count") or 0) > 0
    motion_realized = bool(metrics.get("motion_realized"))
    objective_progress = bool(metrics.get("objective_progress_observed"))
    if nonzero_commands and not missing_motion and not motion_realized:
        labels.append("command_realization_limited")
    if nonzero_commands and motion_realized and not objective_progress and fresh_handoff is False:
        labels.append("geometry_progress_limited")
    if nonzero_commands and motion_realized and objective_progress and fresh_handoff is False:
        labels.append("timeout_despite_progress")
    if fresh_pose is False and not any(label in labels for label in ("command_realization_limited", "timeout_despite_progress")):
        if nonzero_commands and motion_realized:
            labels.append("geometry_progress_limited")
    return [label for label in AUDIT_LABELS if label in labels]


def build_case_authority_summary(
    case: dict[str, Any],
    *,
    source_summary_path: Path,
) -> dict[str, Any]:
    run = _first_run(case)
    mission_verdict_path = _mission_verdict_path(run, source_summary_path=source_summary_path)
    mission_verdict_status, mission_verdict = _mission_verdict_status(
        mission_verdict_path,
        fallback_payload=run.get("mission_verdict"),
    )
    mission_root = _mission_root_path(run, mission_verdict_path, source_summary_path=source_summary_path)
    state_history_path = _state_history_path(run, mission_root, source_summary_path=source_summary_path)
    state_history_status, all_rows = _load_jsonl(state_history_path)
    rows = _fresh_pre_stage_rows(all_rows)
    metrics = _motion_metrics(rows)
    labels = classify_case(case, rows, metrics)
    fresh, _pre_stage, _capture_entry = _fresh_pre_stage(case)
    missing_evidence: list[str] = []
    if state_history_status != "available":
        missing_evidence.append("state_history")
    if not rows:
        missing_evidence.append("fresh_pre_stage_rows")
    if int(metrics.get("command_row_count") or 0) == 0:
        missing_evidence.append("selected_command")
    if int(metrics.get("robot_pose_row_count") or 0) < 2:
        missing_evidence.append("robot_pose_delta")
    return {
        "case_id": str(case.get("case_id", "") or ""),
        "case_role": "primary" if str(case.get("case_id", "") or "") in PRIMARY_CASE_IDS else "secondary",
        "mission_verdict_status": mission_verdict_status,
        "mission_verdict_path": str(mission_verdict_path) if mission_verdict_path is not None else "",
        "mission_error": str(mission_verdict.get("mission_error", "") or ""),
        "failure_stage": str(mission_verdict.get("failure_stage", "") or ""),
        "failure_reason": str(mission_verdict.get("failure_reason", "") or ""),
        "fresh_attempt_reason": str(fresh.get("reason", "") or ""),
        "fresh_pre_stage_handoff_pass": _fresh_pre_stage_handoff(case),
        "fresh_pre_stage_pose_reached": _fresh_pre_stage_pose_reached(case),
        "state_history_status": state_history_status,
        "state_history_path": str(state_history_path) if state_history_path is not None else "",
        "state_history_row_count": len(all_rows),
        "fresh_pre_stage_row_count": len(rows),
        "missing_evidence": missing_evidence,
        "labels": labels,
        "metrics": metrics,
    }


def build_branch_authority_summary(
    *,
    branch_name: str,
    source_summary_path: Path,
    source_summary: dict[str, Any],
) -> dict[str, Any]:
    cases = [case for case in _list_value(source_summary.get("cases")) if isinstance(case, dict)]
    by_id = {str(case.get("case_id", "") or ""): case for case in cases}
    ordered_ids = _ordered_case_ids(cases)
    case_summaries = [
        build_case_authority_summary(by_id[case_id], source_summary_path=source_summary_path)
        for case_id in ordered_ids
        if case_id in by_id
    ]
    labels = _ordered_unique(
        [label for case_summary in case_summaries for label in _list_value(case_summary.get("labels"))]
    )
    primary_cases = [
        case_summary
        for case_summary in case_summaries
        if str(case_summary.get("case_id", "") or "") in PRIMARY_CASE_IDS
    ]
    return {
        "branch_name": branch_name,
        "source_summary_path": str(source_summary_path),
        "source_campaign_id": str(source_summary.get("campaign_id", "") or ""),
        "source_gather_control_family": str(source_summary.get("gather_control_family", "") or ""),
        "case_order": ordered_ids,
        "labels": [label for label in AUDIT_LABELS if label in labels],
        "primary_labels": _ordered_unique(
            [label for case_summary in primary_cases for label in _list_value(case_summary.get("labels"))]
        ),
        "primary_motion_evidence_missing": any(
            "missing_motion_evidence" in _list_value(case_summary.get("labels")) for case_summary in primary_cases
        ),
        "cases": case_summaries,
    }


def _recommend_next_action(branches: list[dict[str, Any]]) -> tuple[str, list[str]]:
    primary_labels = _ordered_unique(
        [
            str(label)
            for branch in branches
            for label in _list_value(branch.get("primary_labels"))
            if str(label)
        ]
    )
    if "handoff_threshold_mismatch" in primary_labels:
        return RECOMMEND_HANDOFF_GATE_AUDIT, ["handoff_threshold_mismatch"]
    if "command_realization_limited" in primary_labels:
        return RECOMMEND_MOTION_PROBE, ["command_realization_limited"]
    if "geometry_progress_limited" in primary_labels or "timeout_despite_progress" in primary_labels:
        return RECOMMEND_ARCHITECTURE_REVIEW, [
            label
            for label in ("geometry_progress_limited", "timeout_despite_progress")
            if label in primary_labels
        ]
    if "ball_safety_blocked" in primary_labels:
        return RECOMMEND_ARCHITECTURE_REVIEW, ["ball_safety_blocked"]
    if "missing_motion_evidence" in primary_labels:
        return RECOMMEND_MOTION_PROBE, ["missing_motion_evidence"]
    return RECOMMEND_MOTION_PROBE, ["primary_case_motion_blocker_unclassified"]


def build_command_authority_summary(
    *,
    campaign_id: str,
    branch_specs: list[tuple[str, Path]],
) -> dict[str, Any]:
    seen_slugs: set[str] = set()
    branches: list[dict[str, Any]] = []
    for branch_name, source_path in branch_specs:
        branch_slug = sanitize_branch_name(branch_name)
        if branch_slug in seen_slugs:
            raise ValueError(f"Duplicate sanitized branch name: {branch_name!r} -> {branch_slug!r}")
        seen_slugs.add(branch_slug)
        source_summary = _load_json_object(source_path)
        branches.append(
            build_branch_authority_summary(
                branch_name=branch_name,
                source_summary_path=source_path,
                source_summary=source_summary,
            )
        )
    labels = [label for label in AUDIT_LABELS if any(label in branch.get("labels", []) for branch in branches)]
    recommendation, reasons = _recommend_next_action(branches)
    status = "needs_live_probe" if recommendation == RECOMMEND_MOTION_PROBE else "needs_architecture_review"
    if recommendation == RECOMMEND_HANDOFF_GATE_AUDIT:
        status = "needs_gate_contract_audit"
    return {
        "type": OUTPUT_KIND,
        "generated_utc": utc_now(),
        "campaign_id": campaign_id,
        "status": status,
        "branch_count": len(branches),
        "primary_case_ids": list(PRIMARY_CASE_IDS),
        "secondary_case_ids": list(SECONDARY_CASE_IDS),
        "audit_labels": labels,
        "recommended_next_action": recommendation,
        "recommendation_reasons": reasons,
        "thresholds": {
            "ball_motion_threshold_m": BALL_MOTION_THRESHOLD_M,
            "ball_clearance_contact_threshold_m": BALL_CLEARANCE_CONTACT_THRESHOLD_M,
            "realized_displacement_min_m": REALIZED_DISPLACEMENT_MIN_M,
            "realized_yaw_min_rad": REALIZED_YAW_MIN_RAD,
            "objective_progress_min_m": OBJECTIVE_PROGRESS_MIN_M,
            "objective_yaw_progress_min_deg": OBJECTIVE_YAW_PROGRESS_MIN_DEG,
        },
        "branches": branches,
    }


def build_scorecard_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Gather Pre-Stage Command Authority Audit",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- status: `{summary.get('status', '')}`",
        f"- recommended_next_action: `{summary.get('recommended_next_action', '')}`",
        "",
        "| branch | case | labels | nonzero cmds | motion realized | objective progress | displacement m | yaw rad | projection gain m | state history |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for branch in _list_value(summary.get("branches")):
        if not isinstance(branch, dict):
            continue
        for case in _list_value(branch.get("cases")):
            if not isinstance(case, dict):
                continue
            if str(case.get("case_role", "") or "") != "primary":
                continue
            metrics = _dict_value(case.get("metrics"))
            lines.append(
                "| "
                f"`{branch.get('branch_name', '')}` | "
                f"`{case.get('case_id', '')}` | "
                f"`{', '.join(str(label) for label in case.get('labels', [])) or 'none'}` | "
                f"{int(metrics.get('nonzero_command_count') or 0)} | "
                f"`{bool(metrics.get('motion_realized', False))}` | "
                f"`{bool(metrics.get('objective_progress_observed', False))}` | "
                f"`{metrics.get('robot_displacement_m', '')}` | "
                f"`{metrics.get('robot_cumulative_yaw_change_rad', '')}` | "
                f"`{metrics.get('projection_reduction_m', '')}` | "
                f"`{case.get('state_history_status', '')}` |"
            )
    lines.append("")
    return "\n".join(lines)


def write_command_authority_bundle(
    *,
    repo_root: Path,
    campaign_id: str,
    summary: dict[str, Any],
) -> dict[str, Path]:
    output_root = ensure_dir(repo_root / "artifacts" / "session" / campaign_id / OUTPUT_KIND)
    summary_path = output_root / "command_authority_summary.json"
    scorecard_path = output_root / "scorecard.md"
    write_json(summary_path, summary)
    scorecard_path.write_text(build_scorecard_markdown(summary), encoding="utf-8")
    return {"output_root": output_root, "summary_path": summary_path, "scorecard_path": scorecard_path}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True, help="Command-authority audit artifact campaign id.")
    parser.add_argument(
        "--branch",
        action="append",
        required=True,
        type=parse_branch_spec,
        help="Branch spec as name=path/to/gather_goal_side_matrix/campaign_summary.json. Repeatable.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    campaign_id = str(args.campaign_id or "").strip()
    if not campaign_id:
        raise ValueError("--campaign-id must not be empty")
    branch_specs: list[tuple[str, Path]] = []
    for name, path in args.branch:
        source_path = path if path.is_absolute() else (REPO_ROOT / path)
        branch_specs.append((name, source_path))
    summary = build_command_authority_summary(campaign_id=campaign_id, branch_specs=branch_specs)
    paths = write_command_authority_bundle(repo_root=REPO_ROOT, campaign_id=campaign_id, summary=summary)
    print(f"GATHER_PRE_STAGE_COMMAND_AUTHORITY_AUDIT_SUMMARY={paths['summary_path']}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
