#!/usr/bin/env python3
"""Audit blocked gather-control live-smoke evidence without rerunning sim."""

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
OUTPUT_KIND = "gather_control_failure_audit"
PRIMARY_CASE_IDS = ("zero", "plus45")
SECONDARY_CASE_IDS = ("minus45", "backside180")
FAILURE_LABELS = (
    "pre_stage_handoff_blocked",
    "goal_side_persistent",
    "nav2_goal_timeout",
    "ball_contact_during_reacquire",
    "post_reacquire_not_handoff_ready",
    "path_clearance_guard",
    "no_controller_progress",
    "slow_controller_convergence",
    "handoff_gate_mismatch",
    "ball_motion_guard",
    "action_error",
    "stage_timeout_after_prestage",
    "local_planner_progress_insufficient",
    "local_planner_release_not_reached",
    "local_planner_goal_side_persistent",
    "docking_release_not_reached",
    "docking_handoff_yaw_not_aligned",
    "docking_progress_insufficient",
    "handoff_yaw_servo_zero_plus45_pre_stage_handoff_blocked",
    "fresh_latest_handoff_divergence",
    "late_retry_handoff_not_promotion_ready",
    "pre_stage_fsm_zero_plus45_pre_stage_handoff_blocked",
    "pre_stage_fsm_escape_not_converged",
    "pre_stage_fsm_dock_entry_not_converged",
    "pre_stage_fsm_timeout_without_ball_contact",
    "pre_stage_path_tracker_zero_plus45_pre_stage_handoff_blocked",
    "pre_stage_path_tracker_escape_not_converged",
    "pre_stage_path_tracker_progress_stalled",
    "pre_stage_path_tracker_timeout_without_ball_contact",
    "pre_stage_trajectory_owner_zero_plus45_pre_stage_handoff_blocked",
    "pre_stage_trajectory_owner_progress_stalled",
    "pre_stage_trajectory_owner_clearance_guard",
    "pre_stage_trajectory_owner_escape_not_converged",
    "pre_stage_trajectory_owner_timeout_without_ball_contact",
)
BLOCKED_CANDIDATE_BRANCHES = {"region_funnel_v1", "nav2_reacquire_v1"}
NAV2_FOLLOW_PATH_BRANCH = "nav2_follow_path_reacquire_v1"
NAV2_MPPI_FOLLOW_PATH_BRANCH = "nav2_mppi_follow_path_reacquire_v1"
NAV2_FOLLOW_PATH_BRANCHES = {NAV2_FOLLOW_PATH_BRANCH, NAV2_MPPI_FOLLOW_PATH_BRANCH}
CONSTRAINED_LOCAL_PLANNER_BRANCH = "constrained_local_planner_v1"
DOCKING_REACQUIRE_BRANCH = "docking_reacquire_v1"
HANDOFF_YAW_SERVO_BRANCH = "handoff_yaw_servo_v1"
PRE_STAGE_REACQUIRE_FSM_BRANCH = "pre_stage_reacquire_fsm_v1"
PRE_STAGE_PATH_TRACKER_BRANCH = "pre_stage_path_tracker_v1"
PRE_STAGE_TRAJECTORY_OWNER_BRANCH = "pre_stage_trajectory_owner_v1"
BLOCKED_CURRENT_CANDIDATE_BRANCHES = BLOCKED_CANDIDATE_BRANCHES | {
    CONSTRAINED_LOCAL_PLANNER_BRANCH,
    DOCKING_REACQUIRE_BRANCH,
    HANDOFF_YAW_SERVO_BRANCH,
    PRE_STAGE_REACQUIRE_FSM_BRANCH,
    PRE_STAGE_PATH_TRACKER_BRANCH,
    PRE_STAGE_TRAJECTORY_OWNER_BRANCH,
}
RECOMMENDED_RETIRE_AND_DESIGN = "retire_current_candidates_and_design_constrained_local_planner_branch"
RECOMMENDED_RETIRE_BLOCKED_AND_DEFINE_REQUIREMENTS = (
    "retire_blocked_candidates_and_define_next_reacquire_architecture_requirements"
)
RECOMMENDED_RETIRE_BLOCKED_AND_DESIGN_NAV2_FOLLOW_PATH = (
    "retire_blocked_candidates_and_design_nav2_follow_path_pre_stage_branch"
)
BALL_DRIFT_CONTACT_THRESHOLD_M = 0.05


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


def _int_value(value: Any) -> int:
    number = _finite_float(value)
    if number is None:
        return 0
    return int(number)


def _round_number(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _pose_xy(value: Any) -> tuple[float, float] | None:
    pose = _dict_value(value)
    if "position" in pose and isinstance(pose.get("position"), dict):
        pose = _dict_value(pose.get("position"))
    x = _finite_float(pose.get("x"))
    y = _finite_float(pose.get("y"))
    if x is None or y is None:
        return None
    return float(x), float(y)


def _pose_delta_m(first: Any, second: Any) -> float | None:
    first_xy = _pose_xy(first)
    second_xy = _pose_xy(second)
    if first_xy is None or second_xy is None:
        return None
    return math.hypot(second_xy[0] - first_xy[0], second_xy[1] - first_xy[1])


def _ordered_case_ids(cases: list[dict[str, Any]]) -> list[str]:
    by_id = {str(case.get("case_id", "") or ""): case for case in cases}
    ordered = [case_id for case_id in (*PRIMARY_CASE_IDS, *SECONDARY_CASE_IDS) if case_id in by_id]
    ordered.extend(case_id for case_id in by_id if case_id and case_id not in ordered)
    return ordered


def _ordered_unique(values: list[str]) -> list[str]:
    ordered: list[str] = []
    for value in values:
        if value and value not in ordered:
            ordered.append(value)
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
    runs = _list_value(case.get("runs"))
    for run in runs:
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


def _mission_root_path(run: dict[str, Any], mission_verdict_path: Path | None, *, source_summary_path: Path) -> Path | None:
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
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return "available", rows


def _fresh_pre_stage(case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    fresh = _dict_value(case.get("fresh_attempt_approach"))
    pre_stage = _dict_value(fresh.get("pre_stage"))
    capture_entry = _dict_value(fresh.get("capture_entry"))
    return fresh, pre_stage, capture_entry


def _pre_stage_handoff_pass(case: dict[str, Any]) -> bool | None:
    _fresh, pre_stage, _capture_entry = _fresh_pre_stage(case)
    parsed = _boolish(pre_stage.get("handoff_pass"))
    if parsed is not None:
        return parsed
    return _boolish(case.get("pre_stage_handoff_pass"))


def _pre_stage_pose_reached(case: dict[str, Any]) -> bool | None:
    _fresh, pre_stage, _capture_entry = _fresh_pre_stage(case)
    parsed = _boolish(pre_stage.get("pose_reached"))
    if parsed is not None:
        return parsed
    return _boolish(case.get("pre_stage_pose_reached"))


def _goal_side_count(case: dict[str, Any], fresh: dict[str, Any], capture_entry: dict[str, Any]) -> int:
    count = _int_value(case.get("entered_goal_side_before_capture_count"))
    if count:
        return count
    if str(fresh.get("reason", "") or "") == "entered_goal_side_before_capture":
        return 1
    if _boolish(capture_entry.get("entered_goal_side_before_capture")) is True:
        return 1
    return 0


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


def _nav2_debug_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    dispatch_rows = [row for row in rows if row.get("event_type") == "nav2_reacquire_dispatch"]
    complete_rows = [row for row in rows if row.get("event_type") == "nav2_reacquire_complete"]
    dispatch_by_attempt: dict[int, dict[str, Any]] = {}
    for row in dispatch_rows:
        dispatch_by_attempt[_int_value(row.get("attempt"))] = row

    drift_samples: list[dict[str, Any]] = []
    timeout_count = 0
    post_reacquire_not_ready_count = 0
    for row in complete_rows:
        dispatch_status = str(row.get("nav2_dispatch_status", "") or "")
        nav2_result = _dict_value(row.get("nav2_result"))
        result_status = str(nav2_result.get("dispatch_status", "") or dispatch_status)
        if result_status == "goal_result_timeout":
            timeout_count += 1
        completion_snapshot = _dict_value(row.get("pre_stage_at_completion")) or _dict_value(row.get("pre_stage"))
        if _boolish(completion_snapshot.get("pre_stage_pose_reached")) is False:
            post_reacquire_not_ready_count += 1
        attempt = _int_value(row.get("attempt"))
        dispatch_row = dispatch_by_attempt.get(attempt, {})
        drift_m = _pose_delta_m(dispatch_row.get("ball_pose"), row.get("ball_pose"))
        if drift_m is not None:
            drift_samples.append(
                {
                    "attempt": attempt,
                    "drift_m": round(drift_m, 6),
                    "dispatch_ball_pose": dispatch_row.get("ball_pose", {}),
                    "completion_ball_pose": row.get("ball_pose", {}),
                }
            )

    max_drift_m = max((float(sample["drift_m"]) for sample in drift_samples), default=0.0)
    return {
        "nav2_dispatch_count": len(dispatch_rows),
        "nav2_complete_count": len(complete_rows),
        "state_history_row_count": len(rows),
        "nav2_goal_timeout_count": timeout_count,
        "post_reacquire_not_handoff_ready_count": post_reacquire_not_ready_count,
        "ball_drift_contact_threshold_m": BALL_DRIFT_CONTACT_THRESHOLD_M,
        "ball_drift_sample_count": len(drift_samples),
        "ball_drift_max_m": round(max_drift_m, 6),
        "ball_drift_samples": drift_samples,
    }


def _nav2_follow_path_debug_summary(rows: list[dict[str, Any]], mission_verdict: dict[str, Any]) -> dict[str, Any]:
    dispatch_rows = [row for row in rows if row.get("event_type") == "nav2_follow_path_reacquire_dispatch"]
    complete_rows = [row for row in rows if row.get("event_type") == "nav2_follow_path_reacquire_complete"]
    blocked_rows = [row for row in rows if row.get("event_type") == "nav2_follow_path_reacquire_plan_blocked"]
    statuses: list[str] = []
    errors: list[str] = []
    robot_motion_values: list[float | None] = []
    ball_motion_values: list[float | None] = []
    terminal_distance_values: list[float | None] = []
    terminal_yaw_values: list[float | None] = []
    handoff_ready_values: list[bool | None] = []
    feedback_counts: list[int] = []
    timeout_count = 0
    action_error_count = 0
    cancel_requested_count = 0
    feedback_sample_count = 0

    for row in complete_rows:
        result = _dict_value(row.get("nav2_follow_path_result"))
        diagnostics = _dict_value(row.get("nav2_follow_path_diagnostics"))
        dispatch_status = str(
            diagnostics.get("dispatch_status")
            or row.get("nav2_follow_path_dispatch_status")
            or result.get("dispatch_status")
            or ""
        )
        if dispatch_status:
            statuses.append(dispatch_status)
        error = str(diagnostics.get("error") or result.get("error") or "")
        if error:
            errors.append(error)
        if dispatch_status == "goal_result_timeout" or _boolish(result.get("timed_out")) is True:
            timeout_count += 1
        if dispatch_status and dispatch_status not in {"goal_succeeded", "goal_result_timeout"}:
            action_error_count += 1
        if _boolish(result.get("cancel_requested")) is True or _boolish(diagnostics.get("cancel_requested")) is True:
            cancel_requested_count += 1
        feedback_count = _int_value(diagnostics.get("feedback_count", result.get("feedback_count")))
        feedback_counts.append(feedback_count)
        feedback_sample_count += len(_list_value(result.get("feedback_samples")))
        robot_motion_values.append(
            _finite_float(diagnostics.get("robot_motion_m", row.get("nav2_follow_path_robot_motion_m")))
        )
        ball_motion_values.append(
            _finite_float(diagnostics.get("ball_motion_m", row.get("nav2_follow_path_ball_motion_m")))
        )
        terminal_distance_values.append(
            _finite_float(
                diagnostics.get(
                    "completion_terminal_path_distance_m",
                    row.get("nav2_follow_path_terminal_path_distance_m"),
                )
            )
        )
        terminal_yaw_values.append(
            _finite_float(
                diagnostics.get(
                    "completion_terminal_yaw_error_deg",
                    row.get("nav2_follow_path_terminal_yaw_error_deg"),
                )
            )
        )
        parsed_handoff = _boolish(
            diagnostics.get("measured_handoff_ready", row.get("nav2_follow_path_measured_handoff_ready"))
        )
        if parsed_handoff is not None:
            handoff_ready_values.append(parsed_handoff)

    mission_failure_reason = str(mission_verdict.get("failure_reason", "") or "")
    path_clearance_guard_count = sum(
        1
        for row in blocked_rows
        if str(row.get("nav2_follow_path_dispatch_status", "") or "") == "follow_path_clearance_guard"
        or str(_dict_value(row.get("nav2_follow_path_plan")).get("reason", "") or "") == "follow_path_clearance_guard"
    )
    if mission_failure_reason == "nav2_follow_path_path_clearance_guard":
        path_clearance_guard_count += 1
    max_robot_motion_m = _max_number(robot_motion_values) or 0.0
    max_ball_motion_m = _max_number(ball_motion_values) or 0.0
    min_terminal_path_distance_m = _min_number(terminal_distance_values)
    min_abs_terminal_yaw_error_deg = _min_number([abs(value) if value is not None else None for value in terminal_yaw_values])
    return {
        "nav2_follow_path_dispatch_count": len(dispatch_rows),
        "nav2_follow_path_complete_count": len(complete_rows),
        "nav2_follow_path_plan_blocked_count": len(blocked_rows),
        "nav2_follow_path_statuses": _ordered_unique(statuses),
        "nav2_follow_path_errors": _ordered_unique(errors),
        "nav2_follow_path_timeout_count": timeout_count,
        "nav2_follow_path_action_error_count": action_error_count,
        "nav2_follow_path_path_clearance_guard_count": path_clearance_guard_count,
        "nav2_follow_path_cancel_requested_count": cancel_requested_count,
        "nav2_follow_path_feedback_count_max": max(feedback_counts, default=0),
        "nav2_follow_path_feedback_sample_count": feedback_sample_count,
        "nav2_follow_path_robot_motion_max_m": round(float(max_robot_motion_m), 6),
        "nav2_follow_path_ball_motion_max_m": round(float(max_ball_motion_m), 6),
        "nav2_follow_path_min_terminal_path_distance_m": min_terminal_path_distance_m,
        "nav2_follow_path_min_abs_terminal_yaw_error_deg": min_abs_terminal_yaw_error_deg,
        "nav2_follow_path_handoff_ready_count": sum(value is True for value in handoff_ready_values),
        "nav2_follow_path_handoff_not_ready_count": sum(value is False for value in handoff_ready_values),
    }


def _snapshot_number(snapshot: dict[str, Any], key: str) -> float | None:
    return _finite_float(_dict_value(snapshot).get(key))


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


def _observed_reduction(values: list[float | None]) -> float | None:
    first = _first_number(values)
    last = _last_number(values)
    if first is None or last is None:
        return None
    return round(first - last, 6)


def _max_number(values: list[float | None]) -> float | None:
    finite_values = [float(value) for value in values if value is not None]
    if not finite_values:
        return None
    return round(max(finite_values), 6)


def _min_number(values: list[float | None]) -> float | None:
    finite_values = [float(value) for value in values if value is not None]
    if not finite_values:
        return None
    return round(min(finite_values), 6)


def _local_planner_debug_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    local_rows = [
        row
        for row in rows
        if row.get("controller_family") == CONSTRAINED_LOCAL_PLANNER_BRANCH
        or any(str(key).startswith("local_planner_") for key in row)
    ]
    active_rows = [
        row
        for row in local_rows
        if str(row.get("objective_name", "") or "") == "constrained_local_planner"
        or str(_dict_value(row.get("selected_command")).get("mode", "") or "") == "constrained_local_pre_stage"
        or bool(str(row.get("strategy_name", "") or ""))
    ]
    release_reasons = _ordered_unique(
        [
            str(row.get("local_planner_release_reason", "") or "")
            for row in local_rows
            if str(row.get("local_planner_release_reason", "") or "")
        ]
    )
    rejection_reasons = _ordered_unique(
        [
            str(reason)
            for row in local_rows
            for reason in _list_value(row.get("local_planner_rejection_reasons"))
            if str(reason)
        ]
    )
    strategy_counts: dict[str, int] = {}
    for row in active_rows:
        strategy_name = str(row.get("strategy_name", "") or "")
        if strategy_name:
            strategy_counts[strategy_name] = strategy_counts.get(strategy_name, 0) + 1

    current_snapshots = [_dict_value(row.get("pre_stage")) for row in local_rows]
    projected_snapshots = [_dict_value(row.get("local_planner_projected_pre_stage")) for row in local_rows]
    current_goal_side_values = [_boolish(snapshot.get("robot_on_goal_side")) for snapshot in current_snapshots]
    projected_goal_side_values = [_boolish(snapshot.get("robot_on_goal_side")) for snapshot in projected_snapshots]
    current_projection_values = [
        _snapshot_number(snapshot, "robot_longitudinal_projection_m") for snapshot in current_snapshots
    ]
    projected_projection_values = [
        _snapshot_number(snapshot, "robot_longitudinal_projection_m") for snapshot in projected_snapshots
    ]
    current_distance_values = [
        _snapshot_number(snapshot, "pre_stage_pose_distance_m") for snapshot in current_snapshots
    ]
    current_lateral_values = [
        _snapshot_number(snapshot, "robot_lateral_error_m") for snapshot in current_snapshots
    ]
    ball_motion_values = [_finite_float(row.get("local_planner_ball_motion_m")) for row in local_rows]
    clearance_values = [_finite_float(row.get("local_planner_min_ball_clearance_m")) for row in local_rows]
    return {
        "local_planner_row_count": len(local_rows),
        "local_planner_active_row_count": len(active_rows),
        "local_planner_release_reason_count": len(release_reasons),
        "local_planner_release_reasons": release_reasons,
        "local_planner_rejection_reasons": rejection_reasons,
        "local_planner_strategy_counts": strategy_counts,
        "local_planner_current_goal_side_row_count": sum(value is True for value in current_goal_side_values),
        "local_planner_projected_goal_side_row_count": sum(value is True for value in projected_goal_side_values),
        "local_planner_current_goal_side_last": next(
            (value for value in reversed(current_goal_side_values) if value is not None),
            None,
        ),
        "local_planner_projected_goal_side_last": next(
            (value for value in reversed(projected_goal_side_values) if value is not None),
            None,
        ),
        "local_planner_observed_projection_reduction_m": _observed_reduction(current_projection_values),
        "local_planner_observed_distance_reduction_m": _observed_reduction(current_distance_values),
        "local_planner_observed_lateral_reduction_m": _observed_reduction(current_lateral_values),
        "local_planner_projected_projection_min_m": _min_number(projected_projection_values),
        "local_planner_projected_projection_last_m": _last_number(projected_projection_values),
        "local_planner_max_projected_projection_gain_m": _max_number(
            [_finite_float(row.get("projected_projection_gain")) for row in local_rows]
        ),
        "local_planner_max_projected_distance_gain_m": _max_number(
            [_finite_float(row.get("projected_distance_gain")) for row in local_rows]
        ),
        "local_planner_max_projected_lateral_gain_m": _max_number(
            [_finite_float(row.get("projected_lateral_gain")) for row in local_rows]
        ),
        "local_planner_max_ball_motion_m": _max_number(ball_motion_values),
        "local_planner_min_ball_clearance_m": _min_number(clearance_values),
    }


def _truthy_blocker_count(value: Any) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value) if math.isfinite(float(value)) and value > 0 else 0
    if isinstance(value, str):
        return 1 if value.strip() else 0
    if isinstance(value, list):
        return len([item for item in value if str(item or "").strip()])
    if isinstance(value, dict):
        return len([key for key, item in value.items() if _boolish(item) is not False and str(key or "").strip()])
    return 0


def _handoff_ready_values(
    rows: list[dict[str, Any]],
    keys: tuple[str, ...],
    snapshot_keys: tuple[str, ...],
) -> list[bool | None]:
    values: list[bool | None] = []
    for row in rows:
        row_value: bool | None = None
        for key in keys:
            if key not in row:
                continue
            parsed = _boolish(row.get(key))
            if parsed is not None:
                row_value = parsed
                break
        if row_value is not None:
            values.append(row_value)
            continue
        for snapshot_key in snapshot_keys:
            snapshot = _dict_value(row.get(snapshot_key))
            for key in keys:
                if key not in snapshot:
                    continue
                parsed = _boolish(snapshot.get(key))
                if parsed is not None:
                    row_value = parsed
                    break
            if row_value is not None:
                break
        if row_value is not None:
            values.append(row_value)
    return values


def _docking_debug_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    docking_rows = [
        row
        for row in rows
        if row.get("controller_family") == DOCKING_REACQUIRE_BRANCH
        or str(row.get("objective_name", "") or "") == "docking_reacquire"
        or any(str(key).startswith("docking_") for key in row)
    ]
    active_rows = [
        row
        for row in docking_rows
        if str(row.get("objective_name", "") or "") == "docking_reacquire"
        or str(_dict_value(row.get("selected_command")).get("mode", "") or "").startswith("docking")
        or bool(
            str(
                row.get("strategy_name", "")
                or row.get("docking_reacquire_strategy_name", "")
                or row.get("docking_strategy_name", "")
                or ""
            )
        )
    ]
    release_reasons = _ordered_unique(
        [
            str(row.get("docking_reacquire_release_reason", "") or row.get("docking_release_reason", "") or "")
            for row in docking_rows
            if str(row.get("docking_reacquire_release_reason", "") or row.get("docking_release_reason", "") or "")
        ]
    )
    release_blockers = _ordered_unique(
        [
            str(blocker)
            for row in docking_rows
            for blocker in (
                _list_value(row.get("docking_reacquire_release_blockers"))
                or _list_value(row.get("docking_release_blockers"))
                or _list_value(row.get("release_blockers"))
                or _list_value(row.get("docking_blockers"))
            )
            if str(blocker)
        ]
    )
    strategy_counts: dict[str, int] = {}
    for row in active_rows:
        strategy_name = str(
            row.get("docking_reacquire_strategy_name", "")
            or row.get("docking_strategy_name", "")
            or row.get("strategy_name", "")
            or ""
        )
        if strategy_name:
            strategy_counts[strategy_name] = strategy_counts.get(strategy_name, 0) + 1

    measured_ready_values = _handoff_ready_values(
        docking_rows,
        (
            "docking_reacquire_handoff_ready_measured",
            "docking_measured_handoff_ready",
            "measured_handoff_ready",
            "handoff_ready",
            "handoff_pass",
            "pre_stage_pose_reached",
        ),
        ("pre_stage", "docking_measured_handoff"),
    )
    projected_ready_values = _handoff_ready_values(
        docking_rows,
        (
            "docking_reacquire_handoff_ready_projected",
            "docking_projected_handoff_ready",
            "projected_handoff_ready",
            "handoff_ready",
            "handoff_pass",
            "pre_stage_pose_reached",
        ),
        ("docking_reacquire_projected_pre_stage", "docking_projected_handoff"),
    )
    ball_motion_values = [
        _finite_float(
            row.get("docking_reacquire_ball_motion_m", row.get("docking_ball_motion_m", row.get("ball_motion_m")))
        )
        for row in docking_rows
    ]
    yaw_blocker_count = sum(
        _truthy_blocker_count(row.get(key))
        for row in docking_rows
        for key in (
            "docking_handoff_yaw_blocker",
            "docking_handoff_yaw_blocked",
            "docking_yaw_blocker",
            "handoff_yaw_blocker",
            "yaw_blocker",
            "yaw_not_aligned",
        )
    )
    yaw_blocker_count += sum(
        1
        for row in docking_rows
        for blocker in (
            _list_value(row.get("docking_reacquire_release_blockers"))
            or _list_value(row.get("docking_release_blockers"))
            or _list_value(row.get("release_blockers"))
            or _list_value(row.get("docking_blockers"))
        )
        if "yaw" in str(blocker).lower()
    )
    current_distance_values = [
        _snapshot_number(_dict_value(row.get("pre_stage")), "pre_stage_pose_distance_m") for row in docking_rows
    ]
    projected_distance_values = [
        _snapshot_number(
            _dict_value(row.get("docking_reacquire_projected_pre_stage") or row.get("docking_projected_handoff")),
            "pre_stage_pose_distance_m",
        )
        for row in docking_rows
    ]
    return {
        "docking_row_count": len(docking_rows),
        "docking_active_row_count": len(active_rows),
        "docking_release_reason_count": len(release_reasons),
        "docking_release_reasons": release_reasons,
        "docking_release_blockers": release_blockers,
        "docking_strategy_counts": strategy_counts,
        "docking_measured_handoff_ready_count": sum(value is True for value in measured_ready_values),
        "docking_measured_handoff_not_ready_count": sum(value is False for value in measured_ready_values),
        "docking_projected_handoff_ready_count": sum(value is True for value in projected_ready_values),
        "docking_projected_handoff_not_ready_count": sum(value is False for value in projected_ready_values),
        "docking_handoff_yaw_blocker_count": yaw_blocker_count,
        "docking_observed_distance_reduction_m": _observed_reduction(current_distance_values),
        "docking_projected_distance_min_m": _min_number(projected_distance_values),
        "docking_max_ball_motion_m": _max_number(ball_motion_values),
    }


def _handoff_yaw_servo_debug_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    servo_rows = [
        row
        for row in rows
        if row.get("controller_family") == HANDOFF_YAW_SERVO_BRANCH
        or str(row.get("objective_name", "") or "") == "handoff_yaw_servo"
        or any(str(key).startswith("handoff_yaw_servo_") for key in row)
    ]
    active_rows = [
        row
        for row in servo_rows
        if bool(row.get("handoff_yaw_servo_active", False))
        or str(_dict_value(row.get("selected_command")).get("mode", "") or "") == "handoff_yaw_servo_pre_stage"
        or str(row.get("objective_name", "") or "") == "handoff_yaw_servo"
    ]
    release_reasons = _ordered_unique(
        [
            str(row.get("handoff_yaw_servo_release_reason", "") or "")
            for row in servo_rows
            if str(row.get("handoff_yaw_servo_release_reason", "") or "")
        ]
    )
    release_blockers = _ordered_unique(
        [
            str(blocker)
            for row in servo_rows
            for blocker in _list_value(row.get("handoff_yaw_servo_release_blockers"))
            if str(blocker)
        ]
    )
    strategy_counts: dict[str, int] = {}
    for row in active_rows:
        strategy_name = str(row.get("handoff_yaw_servo_strategy_name", "") or row.get("strategy_name", "") or "")
        if strategy_name:
            strategy_counts[strategy_name] = strategy_counts.get(strategy_name, 0) + 1

    measured_ready_values = _handoff_ready_values(
        servo_rows,
        (
            "handoff_yaw_servo_handoff_ready_measured",
            "handoff_ready",
            "handoff_pass",
            "pre_stage_pose_reached",
        ),
        ("pre_stage",),
    )
    projected_ready_values = _handoff_ready_values(
        servo_rows,
        (
            "handoff_yaw_servo_handoff_ready_projected",
            "handoff_ready",
            "handoff_pass",
            "pre_stage_pose_reached",
        ),
        ("handoff_yaw_servo_projected_pre_stage",),
    )
    yaw_error_values = [_finite_float(row.get("handoff_yaw_servo_yaw_error_deg")) for row in servo_rows]
    angular_values = [_finite_float(row.get("handoff_yaw_servo_angular_z")) for row in servo_rows]
    ball_motion_values = [_finite_float(row.get("handoff_yaw_servo_ball_motion_m")) for row in servo_rows]
    return {
        "handoff_yaw_servo_row_count": len(servo_rows),
        "handoff_yaw_servo_active_row_count": len(active_rows),
        "handoff_yaw_servo_release_reason_count": len(release_reasons),
        "handoff_yaw_servo_release_reasons": release_reasons,
        "handoff_yaw_servo_release_blockers": release_blockers,
        "handoff_yaw_servo_strategy_counts": strategy_counts,
        "handoff_yaw_servo_measured_handoff_ready_count": sum(value is True for value in measured_ready_values),
        "handoff_yaw_servo_measured_handoff_not_ready_count": sum(value is False for value in measured_ready_values),
        "handoff_yaw_servo_projected_handoff_ready_count": sum(value is True for value in projected_ready_values),
        "handoff_yaw_servo_projected_handoff_not_ready_count": sum(value is False for value in projected_ready_values),
        "handoff_yaw_servo_yaw_error_max_deg": _max_number(yaw_error_values),
        "handoff_yaw_servo_yaw_error_min_deg": _min_number(yaw_error_values),
        "handoff_yaw_servo_max_abs_angular_z": _max_number(
            [abs(float(value)) if value is not None else None for value in angular_values]
        ),
        "handoff_yaw_servo_max_ball_motion_m": _max_number(ball_motion_values),
    }


def _pre_stage_fsm_debug_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fsm_rows = [
        row
        for row in rows
        if row.get("controller_family") == PRE_STAGE_REACQUIRE_FSM_BRANCH
        or str(row.get("objective_name", "") or "") == "pre_stage_reacquire_fsm"
        or any(str(key).startswith("pre_stage_reacquire_fsm_") for key in row)
    ]
    active_rows = [
        row
        for row in fsm_rows
        if bool(row.get("pre_stage_reacquire_fsm_active", False))
        or str(_dict_value(row.get("selected_command")).get("mode", "") or "").startswith(
            "pre_stage_reacquire_fsm"
        )
        or str(row.get("objective_name", "") or "") == "pre_stage_reacquire_fsm"
    ]
    release_reasons = _ordered_unique(
        [
            str(row.get("pre_stage_reacquire_fsm_release_reason", "") or "")
            for row in fsm_rows
            if str(row.get("pre_stage_reacquire_fsm_release_reason", "") or "")
        ]
    )
    release_blockers = _ordered_unique(
        [
            str(blocker)
            for row in fsm_rows
            for blocker in _list_value(row.get("pre_stage_reacquire_fsm_release_blockers"))
            if str(blocker)
        ]
    )
    rejection_reasons = _ordered_unique(
        [
            str(reason)
            for row in fsm_rows
            for reason in _list_value(row.get("pre_stage_reacquire_fsm_rejection_reasons"))
            if str(reason)
        ]
    )
    phase_counts: dict[str, int] = {}
    phases: list[str] = []
    for row in active_rows:
        phase = str(row.get("pre_stage_reacquire_fsm_phase", "") or "")
        if not phase:
            continue
        phases.append(phase)
        phase_counts[phase] = phase_counts.get(phase, 0) + 1

    measured_ready_values = _handoff_ready_values(
        fsm_rows,
        (
            "pre_stage_reacquire_fsm_measured_handoff_ready",
            "handoff_ready",
            "handoff_pass",
            "pre_stage_pose_reached",
        ),
        ("pre_stage_reacquire_fsm_measured_pre_stage", "pre_stage"),
    )
    projected_ready_values = _handoff_ready_values(
        fsm_rows,
        (
            "pre_stage_reacquire_fsm_projected_handoff_ready",
            "handoff_ready",
            "handoff_pass",
            "pre_stage_pose_reached",
        ),
        ("pre_stage_reacquire_fsm_projected_pre_stage",),
    )
    projection_values = [_finite_float(row.get("pre_stage_reacquire_fsm_projection_m")) for row in fsm_rows]
    lateral_values = [_finite_float(row.get("pre_stage_reacquire_fsm_lateral_error_m")) for row in fsm_rows]
    distance_values = [_finite_float(row.get("pre_stage_reacquire_fsm_distance_m")) for row in fsm_rows]
    yaw_values = [_finite_float(row.get("pre_stage_reacquire_fsm_yaw_error_deg")) for row in fsm_rows]
    ball_motion_values = [_finite_float(row.get("pre_stage_reacquire_fsm_ball_motion_m")) for row in fsm_rows]
    clearance_values = [_finite_float(row.get("pre_stage_reacquire_fsm_min_ball_clearance_m")) for row in fsm_rows]
    return {
        "pre_stage_fsm_row_count": len(fsm_rows),
        "pre_stage_fsm_active_row_count": len(active_rows),
        "pre_stage_fsm_phase_counts": phase_counts,
        "pre_stage_fsm_final_phase": phases[-1] if phases else "",
        "pre_stage_fsm_release_reason_count": len(release_reasons),
        "pre_stage_fsm_release_reasons": release_reasons,
        "pre_stage_fsm_release_blockers": release_blockers,
        "pre_stage_fsm_rejection_reasons": rejection_reasons,
        "pre_stage_fsm_measured_handoff_ready_count": sum(value is True for value in measured_ready_values),
        "pre_stage_fsm_measured_handoff_not_ready_count": sum(value is False for value in measured_ready_values),
        "pre_stage_fsm_projected_handoff_ready_count": sum(value is True for value in projected_ready_values),
        "pre_stage_fsm_projected_handoff_not_ready_count": sum(value is False for value in projected_ready_values),
        "pre_stage_fsm_projection_min_m": _min_number(projection_values),
        "pre_stage_fsm_projection_max_m": _max_number(projection_values),
        "pre_stage_fsm_lateral_error_min_m": _min_number(lateral_values),
        "pre_stage_fsm_lateral_error_max_m": _max_number(lateral_values),
        "pre_stage_fsm_distance_min_m": _min_number(distance_values),
        "pre_stage_fsm_distance_max_m": _max_number(distance_values),
        "pre_stage_fsm_yaw_error_min_deg": _min_number(yaw_values),
        "pre_stage_fsm_yaw_error_max_deg": _max_number(yaw_values),
        "pre_stage_fsm_accepted_count": sum(_int_value(row.get("pre_stage_reacquire_fsm_accepted_count")) for row in fsm_rows),
        "pre_stage_fsm_rejected_count": sum(_int_value(row.get("pre_stage_reacquire_fsm_rejected_count")) for row in fsm_rows),
        "pre_stage_fsm_max_ball_motion_m": _max_number(ball_motion_values),
        "pre_stage_fsm_min_ball_clearance_m": _min_number(clearance_values),
    }


def _pre_stage_path_tracker_debug_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    path_rows = [
        row
        for row in rows
        if row.get("controller_family") == PRE_STAGE_PATH_TRACKER_BRANCH
        or str(row.get("objective_name", "") or "") == "pre_stage_path_tracker"
        or any(str(key).startswith("pre_stage_path_tracker_") for key in row)
    ]
    active_rows = [
        row
        for row in path_rows
        if bool(row.get("pre_stage_path_tracker_active", False))
        or str(_dict_value(row.get("selected_command")).get("mode", "") or "").startswith(
            "pre_stage_path_tracker"
        )
        or str(row.get("objective_name", "") or "") == "pre_stage_path_tracker"
    ]
    release_reasons = _ordered_unique(
        [
            str(row.get("pre_stage_path_tracker_release_reason", "") or "")
            for row in path_rows
            if str(row.get("pre_stage_path_tracker_release_reason", "") or "")
        ]
    )
    release_blockers = _ordered_unique(
        [
            str(blocker)
            for row in path_rows
            for blocker in _list_value(row.get("pre_stage_path_tracker_release_blockers"))
            if str(blocker)
        ]
    )
    rejection_reasons = _ordered_unique(
        [
            str(reason)
            for row in path_rows
            for reason in _list_value(row.get("pre_stage_path_tracker_rejection_reasons"))
            if str(reason)
        ]
    )
    waypoint_counts: dict[str, int] = {}
    waypoint_kinds: list[str] = []
    command_counts: dict[str, int] = {}
    for row in active_rows:
        waypoint_kind = str(row.get("pre_stage_path_tracker_waypoint_kind", "") or "")
        if waypoint_kind:
            waypoint_kinds.append(waypoint_kind)
            waypoint_counts[waypoint_kind] = waypoint_counts.get(waypoint_kind, 0) + 1
        command_mode = str(_dict_value(row.get("selected_command")).get("mode", "") or "")
        if command_mode:
            command_counts[command_mode] = command_counts.get(command_mode, 0) + 1

    measured_ready_values = _handoff_ready_values(
        path_rows,
        (
            "pre_stage_path_tracker_measured_handoff_ready",
            "handoff_ready",
            "handoff_pass",
            "pre_stage_pose_reached",
        ),
        ("pre_stage_path_tracker_measured_pre_stage", "pre_stage"),
    )
    projected_ready_values = _handoff_ready_values(
        path_rows,
        (
            "pre_stage_path_tracker_projected_handoff_ready",
            "handoff_ready",
            "handoff_pass",
            "pre_stage_pose_reached",
        ),
        ("pre_stage_path_tracker_projected_pre_stage",),
    )
    projection_values = [_finite_float(row.get("pre_stage_path_tracker_projection_m")) for row in path_rows]
    lateral_values = [_finite_float(row.get("pre_stage_path_tracker_lateral_error_m")) for row in path_rows]
    distance_values = [_finite_float(row.get("pre_stage_path_tracker_distance_m")) for row in path_rows]
    yaw_values = [_finite_float(row.get("pre_stage_path_tracker_yaw_error_deg")) for row in path_rows]
    ball_motion_values = [_finite_float(row.get("pre_stage_path_tracker_ball_motion_m")) for row in path_rows]
    clearance_values = [_finite_float(row.get("pre_stage_path_tracker_min_ball_clearance_m")) for row in path_rows]
    return {
        "pre_stage_path_tracker_row_count": len(path_rows),
        "pre_stage_path_tracker_active_row_count": len(active_rows),
        "pre_stage_path_tracker_waypoint_counts": waypoint_counts,
        "pre_stage_path_tracker_final_waypoint": waypoint_kinds[-1] if waypoint_kinds else "",
        "pre_stage_path_tracker_command_counts": command_counts,
        "pre_stage_path_tracker_release_reason_count": len(release_reasons),
        "pre_stage_path_tracker_release_reasons": release_reasons,
        "pre_stage_path_tracker_release_blockers": release_blockers,
        "pre_stage_path_tracker_rejection_reasons": rejection_reasons,
        "pre_stage_path_tracker_measured_handoff_ready_count": sum(value is True for value in measured_ready_values),
        "pre_stage_path_tracker_measured_handoff_not_ready_count": sum(value is False for value in measured_ready_values),
        "pre_stage_path_tracker_projected_handoff_ready_count": sum(value is True for value in projected_ready_values),
        "pre_stage_path_tracker_projected_handoff_not_ready_count": sum(value is False for value in projected_ready_values),
        "pre_stage_path_tracker_projection_start_m": _first_number(projection_values),
        "pre_stage_path_tracker_projection_end_m": _last_number(projection_values),
        "pre_stage_path_tracker_projection_min_m": _min_number(projection_values),
        "pre_stage_path_tracker_projection_max_m": _max_number(projection_values),
        "pre_stage_path_tracker_lateral_error_start_m": _first_number(lateral_values),
        "pre_stage_path_tracker_lateral_error_end_m": _last_number(lateral_values),
        "pre_stage_path_tracker_lateral_error_min_m": _min_number(lateral_values),
        "pre_stage_path_tracker_lateral_error_max_m": _max_number(lateral_values),
        "pre_stage_path_tracker_distance_start_m": _first_number(distance_values),
        "pre_stage_path_tracker_distance_end_m": _last_number(distance_values),
        "pre_stage_path_tracker_distance_min_m": _min_number(distance_values),
        "pre_stage_path_tracker_distance_max_m": _max_number(distance_values),
        "pre_stage_path_tracker_yaw_error_start_deg": _first_number(yaw_values),
        "pre_stage_path_tracker_yaw_error_end_deg": _last_number(yaw_values),
        "pre_stage_path_tracker_yaw_error_min_deg": _min_number(yaw_values),
        "pre_stage_path_tracker_yaw_error_max_deg": _max_number(yaw_values),
        "pre_stage_path_tracker_accepted_count": sum(
            _int_value(row.get("pre_stage_path_tracker_accepted_count")) for row in path_rows
        ),
        "pre_stage_path_tracker_rejected_count": sum(
            _int_value(row.get("pre_stage_path_tracker_rejected_count")) for row in path_rows
        ),
        "pre_stage_path_tracker_max_ball_motion_m": _max_number(ball_motion_values),
        "pre_stage_path_tracker_min_ball_clearance_m": _min_number(clearance_values),
    }


def _pre_stage_trajectory_owner_debug_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    owner_rows = [
        row
        for row in rows
        if row.get("controller_family") == PRE_STAGE_TRAJECTORY_OWNER_BRANCH
        or str(row.get("objective_name", "") or "") == "pre_stage_trajectory_owner"
        or any(str(key).startswith("pre_stage_trajectory_owner_") for key in row)
    ]
    active_rows = [
        row
        for row in owner_rows
        if bool(row.get("pre_stage_trajectory_owner_active", False))
        or str(_dict_value(row.get("selected_command")).get("mode", "") or "").startswith(
            "pre_stage_trajectory_owner"
        )
        or str(row.get("objective_name", "") or "") == "pre_stage_trajectory_owner"
    ]
    release_reasons = _ordered_unique(
        [
            str(row.get("pre_stage_trajectory_owner_release_reason", "") or "")
            for row in owner_rows
            if str(row.get("pre_stage_trajectory_owner_release_reason", "") or "")
        ]
    )
    release_blockers = _ordered_unique(
        [
            str(blocker)
            for row in owner_rows
            for blocker in _list_value(row.get("pre_stage_trajectory_owner_release_blockers"))
            if str(blocker)
        ]
    )
    rejection_reasons = _ordered_unique(
        [
            str(reason)
            for row in owner_rows
            for reason in _list_value(row.get("pre_stage_trajectory_owner_rejection_reasons"))
            if str(reason)
        ]
    )
    replan_reasons = _ordered_unique(
        [
            str(row.get("pre_stage_trajectory_owner_replan_reason", "") or "")
            for row in owner_rows
            if str(row.get("pre_stage_trajectory_owner_replan_reason", "") or "")
        ]
    )
    milestone_counts: dict[str, int] = {}
    milestone_kinds: list[str] = []
    command_counts: dict[str, int] = {}
    for row in active_rows:
        milestone_kind = str(row.get("pre_stage_trajectory_owner_milestone_kind", "") or "")
        if milestone_kind:
            milestone_kinds.append(milestone_kind)
            milestone_counts[milestone_kind] = milestone_counts.get(milestone_kind, 0) + 1
        command_mode = str(_dict_value(row.get("selected_command")).get("mode", "") or "")
        if command_mode:
            command_counts[command_mode] = command_counts.get(command_mode, 0) + 1

    measured_ready_values = _handoff_ready_values(
        owner_rows,
        (
            "pre_stage_trajectory_owner_measured_handoff_ready",
            "handoff_ready",
            "handoff_pass",
            "pre_stage_pose_reached",
        ),
        ("pre_stage_trajectory_owner_measured_pre_stage", "pre_stage"),
    )
    projected_ready_values = _handoff_ready_values(
        owner_rows,
        (
            "pre_stage_trajectory_owner_projected_handoff_ready",
            "handoff_ready",
            "handoff_pass",
            "pre_stage_pose_reached",
        ),
        ("pre_stage_trajectory_owner_projected_pre_stage",),
    )
    projection_values = [_finite_float(row.get("pre_stage_trajectory_owner_projection_m")) for row in owner_rows]
    lateral_values = [_finite_float(row.get("pre_stage_trajectory_owner_lateral_error_m")) for row in owner_rows]
    distance_values = [_finite_float(row.get("pre_stage_trajectory_owner_distance_m")) for row in owner_rows]
    yaw_values = [_finite_float(row.get("pre_stage_trajectory_owner_yaw_error_deg")) for row in owner_rows]
    ball_motion_values = [_finite_float(row.get("pre_stage_trajectory_owner_ball_motion_m")) for row in owner_rows]
    clearance_values = [
        _finite_float(row.get("pre_stage_trajectory_owner_min_ball_clearance_m"))
        for row in owner_rows
    ]
    replan_count_values = [_finite_float(row.get("pre_stage_trajectory_owner_replan_count")) for row in owner_rows]
    next_replan_count_values = [
        _finite_float(row.get("pre_stage_trajectory_owner_next_replan_count"))
        for row in owner_rows
    ]
    return {
        "pre_stage_trajectory_owner_row_count": len(owner_rows),
        "pre_stage_trajectory_owner_active_row_count": len(active_rows),
        "pre_stage_trajectory_owner_milestone_counts": milestone_counts,
        "pre_stage_trajectory_owner_final_milestone": milestone_kinds[-1] if milestone_kinds else "",
        "pre_stage_trajectory_owner_command_counts": command_counts,
        "pre_stage_trajectory_owner_release_reason_count": len(release_reasons),
        "pre_stage_trajectory_owner_release_reasons": release_reasons,
        "pre_stage_trajectory_owner_release_blockers": release_blockers,
        "pre_stage_trajectory_owner_rejection_reasons": rejection_reasons,
        "pre_stage_trajectory_owner_replan_reasons": replan_reasons,
        "pre_stage_trajectory_owner_replan_count_max": _max_number(replan_count_values),
        "pre_stage_trajectory_owner_next_replan_count_max": _max_number(next_replan_count_values),
        "pre_stage_trajectory_owner_measured_handoff_ready_count": sum(value is True for value in measured_ready_values),
        "pre_stage_trajectory_owner_measured_handoff_not_ready_count": sum(value is False for value in measured_ready_values),
        "pre_stage_trajectory_owner_projected_handoff_ready_count": sum(value is True for value in projected_ready_values),
        "pre_stage_trajectory_owner_projected_handoff_not_ready_count": sum(value is False for value in projected_ready_values),
        "pre_stage_trajectory_owner_projection_start_m": _first_number(projection_values),
        "pre_stage_trajectory_owner_projection_end_m": _last_number(projection_values),
        "pre_stage_trajectory_owner_projection_min_m": _min_number(projection_values),
        "pre_stage_trajectory_owner_projection_max_m": _max_number(projection_values),
        "pre_stage_trajectory_owner_lateral_error_start_m": _first_number(lateral_values),
        "pre_stage_trajectory_owner_lateral_error_end_m": _last_number(lateral_values),
        "pre_stage_trajectory_owner_lateral_error_min_m": _min_number(lateral_values),
        "pre_stage_trajectory_owner_lateral_error_max_m": _max_number(lateral_values),
        "pre_stage_trajectory_owner_distance_start_m": _first_number(distance_values),
        "pre_stage_trajectory_owner_distance_end_m": _last_number(distance_values),
        "pre_stage_trajectory_owner_distance_min_m": _min_number(distance_values),
        "pre_stage_trajectory_owner_distance_max_m": _max_number(distance_values),
        "pre_stage_trajectory_owner_yaw_error_start_deg": _first_number(yaw_values),
        "pre_stage_trajectory_owner_yaw_error_end_deg": _last_number(yaw_values),
        "pre_stage_trajectory_owner_yaw_error_min_deg": _min_number(yaw_values),
        "pre_stage_trajectory_owner_yaw_error_max_deg": _max_number(yaw_values),
        "pre_stage_trajectory_owner_accepted_count": sum(
            _int_value(row.get("pre_stage_trajectory_owner_accepted_count")) for row in owner_rows
        ),
        "pre_stage_trajectory_owner_rejected_count": sum(
            _int_value(row.get("pre_stage_trajectory_owner_rejected_count")) for row in owner_rows
        ),
        "pre_stage_trajectory_owner_max_ball_motion_m": _max_number(ball_motion_values),
        "pre_stage_trajectory_owner_min_ball_clearance_m": _min_number(clearance_values),
    }


def _case_labels(
    *,
    branch_name: str,
    case: dict[str, Any],
    fresh: dict[str, Any],
    capture_entry: dict[str, Any],
    mission_verdict: dict[str, Any],
    nav2_debug: dict[str, Any],
    nav2_follow_path_debug: dict[str, Any],
    local_planner_debug: dict[str, Any],
    docking_debug: dict[str, Any],
    handoff_yaw_servo_debug: dict[str, Any],
    pre_stage_fsm_debug: dict[str, Any],
    pre_stage_path_tracker_debug: dict[str, Any],
    pre_stage_trajectory_owner_debug: dict[str, Any],
) -> list[str]:
    labels: list[str] = []
    handoff_pass = _pre_stage_handoff_pass(case)
    if handoff_pass is False:
        labels.append("pre_stage_handoff_blocked")
    if _goal_side_count(case, fresh, capture_entry) > 0:
        labels.append("goal_side_persistent")
    if int(nav2_debug.get("nav2_goal_timeout_count", 0) or 0) > 0:
        labels.append("nav2_goal_timeout")
    if float(nav2_debug.get("ball_drift_max_m", 0.0) or 0.0) >= BALL_DRIFT_CONTACT_THRESHOLD_M:
        labels.append("ball_contact_during_reacquire")
    if (
        float(nav2_follow_path_debug.get("nav2_follow_path_ball_motion_max_m", 0.0) or 0.0)
        >= BALL_DRIFT_CONTACT_THRESHOLD_M
    ):
        labels.append("ball_contact_during_reacquire")
    if float(local_planner_debug.get("local_planner_max_ball_motion_m", 0.0) or 0.0) >= BALL_DRIFT_CONTACT_THRESHOLD_M:
        labels.append("ball_contact_during_reacquire")
    if float(docking_debug.get("docking_max_ball_motion_m", 0.0) or 0.0) >= BALL_DRIFT_CONTACT_THRESHOLD_M:
        labels.append("ball_contact_during_reacquire")
    if (
        float(handoff_yaw_servo_debug.get("handoff_yaw_servo_max_ball_motion_m", 0.0) or 0.0)
        >= BALL_DRIFT_CONTACT_THRESHOLD_M
    ):
        labels.append("ball_contact_during_reacquire")
    if float(pre_stage_fsm_debug.get("pre_stage_fsm_max_ball_motion_m", 0.0) or 0.0) >= BALL_DRIFT_CONTACT_THRESHOLD_M:
        labels.append("ball_contact_during_reacquire")
    if (
        float(pre_stage_path_tracker_debug.get("pre_stage_path_tracker_max_ball_motion_m", 0.0) or 0.0)
        >= BALL_DRIFT_CONTACT_THRESHOLD_M
    ):
        labels.append("ball_contact_during_reacquire")
    if (
        float(pre_stage_trajectory_owner_debug.get("pre_stage_trajectory_owner_max_ball_motion_m", 0.0) or 0.0)
        >= BALL_DRIFT_CONTACT_THRESHOLD_M
    ):
        labels.append("ball_contact_during_reacquire")
    if int(nav2_debug.get("post_reacquire_not_handoff_ready_count", 0) or 0) > 0:
        labels.append("post_reacquire_not_handoff_ready")
    if str(branch_name or "") in NAV2_FOLLOW_PATH_BRANCHES:
        follow_path_failure_reason = str(mission_verdict.get("failure_reason", "") or "")
        follow_path_timeout_count = int(nav2_follow_path_debug.get("nav2_follow_path_timeout_count", 0) or 0)
        follow_path_action_error_count = int(
            nav2_follow_path_debug.get("nav2_follow_path_action_error_count", 0) or 0
        )
        follow_path_motion_m = float(
            nav2_follow_path_debug.get("nav2_follow_path_robot_motion_max_m", 0.0) or 0.0
        )
        follow_path_ball_motion_m = float(
            nav2_follow_path_debug.get("nav2_follow_path_ball_motion_max_m", 0.0) or 0.0
        )
        follow_path_handoff_not_ready_count = int(
            nav2_follow_path_debug.get("nav2_follow_path_handoff_not_ready_count", 0) or 0
        )
        follow_path_terminal_distance = _finite_float(
            nav2_follow_path_debug.get("nav2_follow_path_min_terminal_path_distance_m")
        )
        if follow_path_timeout_count > 0:
            labels.append("nav2_goal_timeout")
        if int(nav2_follow_path_debug.get("nav2_follow_path_path_clearance_guard_count", 0) or 0) > 0:
            labels.append("path_clearance_guard")
        if follow_path_ball_motion_m >= BALL_DRIFT_CONTACT_THRESHOLD_M:
            labels.append("ball_motion_guard")
        if follow_path_timeout_count > 0 and follow_path_motion_m < 0.05:
            labels.append("no_controller_progress")
        if (
            follow_path_timeout_count > 0
            and follow_path_motion_m >= 0.05
            and follow_path_ball_motion_m < BALL_DRIFT_CONTACT_THRESHOLD_M
        ):
            labels.append("slow_controller_convergence")
        if (
            follow_path_handoff_not_ready_count > 0
            and (follow_path_terminal_distance is not None and follow_path_terminal_distance <= 0.25)
        ) or follow_path_failure_reason == "nav2_follow_path_post_action_not_handoff_ready":
            labels.append("handoff_gate_mismatch")
        if follow_path_action_error_count > 0 or follow_path_failure_reason == "nav2_follow_path_failed":
            labels.append("action_error")
    if str(branch_name or "") == CONSTRAINED_LOCAL_PLANNER_BRANCH:
        local_active_count = int(local_planner_debug.get("local_planner_active_row_count", 0) or 0)
        local_release_count = int(local_planner_debug.get("local_planner_release_reason_count", 0) or 0)
        if local_active_count > 0 and local_release_count == 0:
            labels.append("local_planner_release_not_reached")
        if local_active_count > 0 and _pre_stage_handoff_pass(case) is False:
            labels.append("local_planner_progress_insufficient")
        if (
            local_active_count > 0
            and _goal_side_count(case, fresh, capture_entry) > 0
            and int(local_planner_debug.get("local_planner_current_goal_side_row_count", 0) or 0) > 0
        ):
            labels.append("local_planner_goal_side_persistent")
    if str(branch_name or "") == DOCKING_REACQUIRE_BRANCH:
        docking_active_count = int(docking_debug.get("docking_active_row_count", 0) or 0)
        docking_release_count = int(docking_debug.get("docking_release_reason_count", 0) or 0)
        if docking_active_count > 0 and docking_release_count == 0:
            labels.append("docking_release_not_reached")
        if int(docking_debug.get("docking_handoff_yaw_blocker_count", 0) or 0) > 0:
            labels.append("docking_handoff_yaw_not_aligned")
        if docking_active_count > 0 and _pre_stage_handoff_pass(case) is False:
            labels.append("docking_progress_insufficient")
    if str(branch_name or "") == PRE_STAGE_REACQUIRE_FSM_BRANCH:
        fsm_active_count = int(pre_stage_fsm_debug.get("pre_stage_fsm_active_row_count", 0) or 0)
        fsm_release_count = int(pre_stage_fsm_debug.get("pre_stage_fsm_release_reason_count", 0) or 0)
        fsm_final_phase = str(pre_stage_fsm_debug.get("pre_stage_fsm_final_phase", "") or "")
        fsm_phase_counts = _dict_value(pre_stage_fsm_debug.get("pre_stage_fsm_phase_counts"))
        if handoff_pass is False and fsm_active_count > 0:
            if fsm_final_phase == "goal_side_escape" or int(fsm_phase_counts.get("goal_side_escape", 0) or 0) > 0:
                labels.append("pre_stage_fsm_escape_not_converged")
            if fsm_final_phase == "dock_entry" or int(fsm_phase_counts.get("dock_entry", 0) or 0) > 0:
                labels.append("pre_stage_fsm_dock_entry_not_converged")
            max_ball_motion = float(pre_stage_fsm_debug.get("pre_stage_fsm_max_ball_motion_m", 0.0) or 0.0)
            if max_ball_motion < BALL_DRIFT_CONTACT_THRESHOLD_M and fsm_release_count == 0:
                labels.append("pre_stage_fsm_timeout_without_ball_contact")
    if str(branch_name or "") == PRE_STAGE_PATH_TRACKER_BRANCH:
        path_active_count = int(
            pre_stage_path_tracker_debug.get("pre_stage_path_tracker_active_row_count", 0) or 0
        )
        path_release_count = int(
            pre_stage_path_tracker_debug.get("pre_stage_path_tracker_release_reason_count", 0) or 0
        )
        path_final_waypoint = str(
            pre_stage_path_tracker_debug.get("pre_stage_path_tracker_final_waypoint", "") or ""
        )
        path_rejection_reasons = set(
            str(reason)
            for reason in _list_value(pre_stage_path_tracker_debug.get("pre_stage_path_tracker_rejection_reasons"))
            if str(reason)
        )
        if handoff_pass is False and path_active_count > 0:
            if path_final_waypoint == "escape":
                labels.append("pre_stage_path_tracker_escape_not_converged")
            if "waypoint_progress_stall" in path_rejection_reasons:
                labels.append("pre_stage_path_tracker_progress_stalled")
            max_ball_motion = float(
                pre_stage_path_tracker_debug.get("pre_stage_path_tracker_max_ball_motion_m", 0.0) or 0.0
            )
            if max_ball_motion < BALL_DRIFT_CONTACT_THRESHOLD_M and path_release_count == 0:
                labels.append("pre_stage_path_tracker_timeout_without_ball_contact")
    if str(branch_name or "") == PRE_STAGE_TRAJECTORY_OWNER_BRANCH:
        owner_active_count = int(
            pre_stage_trajectory_owner_debug.get("pre_stage_trajectory_owner_active_row_count", 0) or 0
        )
        owner_release_count = int(
            pre_stage_trajectory_owner_debug.get("pre_stage_trajectory_owner_release_reason_count", 0) or 0
        )
        owner_final_milestone = str(
            pre_stage_trajectory_owner_debug.get("pre_stage_trajectory_owner_final_milestone", "") or ""
        )
        owner_rejection_reasons = set(
            str(reason)
            for reason in _list_value(pre_stage_trajectory_owner_debug.get("pre_stage_trajectory_owner_rejection_reasons"))
            if str(reason)
        )
        owner_release_reasons = set(
            str(reason)
            for reason in _list_value(pre_stage_trajectory_owner_debug.get("pre_stage_trajectory_owner_release_reasons"))
            if str(reason)
        )
        if handoff_pass is False and owner_active_count > 0:
            if owner_final_milestone == "escape_clear":
                labels.append("pre_stage_trajectory_owner_escape_not_converged")
            if "trajectory_progress_stalled" in owner_rejection_reasons or "trajectory_progress_stalled" in owner_release_reasons:
                labels.append("pre_stage_trajectory_owner_progress_stalled")
            clearance_tokens = {
                "trajectory_clearance_guard",
                "predicted_clearance_violation",
                "segment_clearance_violation",
                "measured_clearance_violation",
            }
            if owner_release_reasons.intersection(clearance_tokens) or owner_rejection_reasons.intersection(clearance_tokens):
                labels.append("pre_stage_trajectory_owner_clearance_guard")
            max_ball_motion = float(
                pre_stage_trajectory_owner_debug.get("pre_stage_trajectory_owner_max_ball_motion_m", 0.0) or 0.0
            )
            if max_ball_motion < BALL_DRIFT_CONTACT_THRESHOLD_M and (
                owner_release_count == 0
                or "trajectory_progress_stalled" in owner_rejection_reasons
                or "trajectory_progress_stalled" in owner_release_reasons
            ):
                labels.append("pre_stage_trajectory_owner_timeout_without_ball_contact")

    latest = _dict_value(_first_run(case).get("latest_approach_progress"))
    latest_pre_stage = _dict_value(latest.get("pre_stage"))
    latest_reason = str(latest.get("reason", "") or "")
    if (
        str(branch_name or "") == HANDOFF_YAW_SERVO_BRANCH
        and handoff_pass is False
        and _boolish(latest_pre_stage.get("handoff_pass")) is True
    ):
        labels.append("fresh_latest_handoff_divergence")
        labels.append("late_retry_handoff_not_promotion_ready")
    mission_failure_stage = str(mission_verdict.get("failure_stage", "") or "")
    mission_failure_reason = str(mission_verdict.get("failure_reason", "") or "")
    if (
        _boolish(latest_pre_stage.get("handoff_pass")) is True
        and latest_reason == "staging_pose_not_reached"
    ) or mission_failure_stage == "stage" or mission_failure_reason == "goal_side_stage_timeout":
        labels.append("stage_timeout_after_prestage")
    return [label for label in FAILURE_LABELS if label in set(labels)]


def build_case_failure_summary(
    *,
    branch_name: str,
    case: dict[str, Any],
    source_summary_path: Path,
) -> dict[str, Any]:
    case_id = str(case.get("case_id", "") or "")
    fresh, pre_stage, capture_entry = _fresh_pre_stage(case)
    run = _first_run(case)
    mission_verdict_path = _mission_verdict_path(run, source_summary_path=source_summary_path)
    mission_root = _mission_root_path(run, mission_verdict_path, source_summary_path=source_summary_path)
    state_history_path = _state_history_path(run, mission_root, source_summary_path=source_summary_path)
    mission_verdict_status, mission_verdict = _mission_verdict_status(
        mission_verdict_path,
        run.get("mission_verdict"),
    )
    state_history_status = "not_referenced"
    state_rows: list[dict[str, Any]] = []
    if state_history_path is not None:
        state_history_status, state_rows = _load_jsonl(state_history_path)
    nav2_debug = _nav2_debug_summary(state_rows)
    nav2_follow_path_debug = _nav2_follow_path_debug_summary(state_rows, mission_verdict)
    local_planner_debug = _local_planner_debug_summary(state_rows)
    docking_debug = _docking_debug_summary(state_rows)
    handoff_yaw_servo_debug = _handoff_yaw_servo_debug_summary(state_rows)
    pre_stage_fsm_debug = _pre_stage_fsm_debug_summary(state_rows)
    pre_stage_path_tracker_debug = _pre_stage_path_tracker_debug_summary(state_rows)
    pre_stage_trajectory_owner_debug = _pre_stage_trajectory_owner_debug_summary(state_rows)

    missing_evidence: list[str] = []
    if mission_verdict_status in {"not_referenced", "missing", "unreadable"}:
        missing_evidence.append(f"mission_verdict_{mission_verdict_status}")
    if state_history_status in {"not_referenced", "missing"}:
        missing_evidence.append(f"state_history_{state_history_status}")

    labels = _case_labels(
        branch_name=branch_name,
        case=case,
        fresh=fresh,
        capture_entry=capture_entry,
        mission_verdict=mission_verdict,
        nav2_debug=nav2_debug,
        nav2_follow_path_debug=nav2_follow_path_debug,
        local_planner_debug=local_planner_debug,
        docking_debug=docking_debug,
        handoff_yaw_servo_debug=handoff_yaw_servo_debug,
        pre_stage_fsm_debug=pre_stage_fsm_debug,
        pre_stage_path_tracker_debug=pre_stage_path_tracker_debug,
        pre_stage_trajectory_owner_debug=pre_stage_trajectory_owner_debug,
    )
    handoff_pass = _pre_stage_handoff_pass(case)
    pose_reached = _pre_stage_pose_reached(case)
    return {
        "branch_name": branch_name,
        "case_id": case_id,
        "case_role": "primary" if case_id in PRIMARY_CASE_IDS else "secondary",
        "labels": labels,
        "failure_labels": labels,
        "pass_count": _int_value(case.get("pass_count")),
        "run_count": _int_value(case.get("run_count")),
        "promotion_gate_pass": bool(case.get("promotion_gate_pass", False)),
        "fresh_attempt_reason": str(fresh.get("reason", "") or ""),
        "fresh_pre_stage_pose_reached": pose_reached,
        "fresh_pre_stage_handoff_pass": handoff_pass,
        "fresh_pre_stage_time_s": _round_number(_finite_float(pre_stage.get("time_s"))),
        "entered_goal_side_before_capture_count": _goal_side_count(case, fresh, capture_entry),
        "latest_approach_reason": str(_dict_value(run.get("latest_approach_progress")).get("reason", "") or ""),
        "mission_verdict_path": str(mission_verdict_path) if mission_verdict_path is not None else "",
        "mission_verdict_status": mission_verdict_status,
        "mission_failure_reason": str(mission_verdict.get("failure_reason", "") or ""),
        "mission_failure_stage": str(mission_verdict.get("failure_stage", "") or ""),
        "state_history_path": str(state_history_path) if state_history_path is not None else "",
        "state_history_status": state_history_status,
        "missing_evidence": missing_evidence,
        "nav2_debug": nav2_debug,
        "nav2_follow_path_debug": nav2_follow_path_debug,
        "local_planner_debug": local_planner_debug,
        "docking_debug": docking_debug,
        "handoff_yaw_servo_debug": handoff_yaw_servo_debug,
        "pre_stage_fsm_debug": pre_stage_fsm_debug,
        "pre_stage_path_tracker_debug": pre_stage_path_tracker_debug,
        "pre_stage_trajectory_owner_debug": pre_stage_trajectory_owner_debug,
    }


def build_branch_failure_summary(
    *,
    branch_name: str,
    source_summary_path: Path,
    source_summary: dict[str, Any],
) -> dict[str, Any]:
    branch_slug = sanitize_branch_name(branch_name)
    raw_cases = [case for case in _list_value(source_summary.get("cases")) if isinstance(case, dict)]
    cases_by_id = {str(case.get("case_id", "") or ""): case for case in raw_cases}
    case_order = _ordered_case_ids(raw_cases)
    case_summaries = [
        build_case_failure_summary(
            branch_name=branch_name,
            case=cases_by_id[case_id],
            source_summary_path=source_summary_path,
        )
        for case_id in case_order
    ]
    primary = [case for case in case_summaries if case.get("case_id") in PRIMARY_CASE_IDS]
    primary_handoff_blocked = all(
        case.get("fresh_pre_stage_handoff_pass") is False
        for case in primary
        if case.get("case_id") in PRIMARY_CASE_IDS
    ) and {case.get("case_id") for case in primary} == set(PRIMARY_CASE_IDS)
    labels = [label for label in FAILURE_LABELS if any(label in case.get("labels", []) for case in case_summaries)]
    if str(branch_name or "") == HANDOFF_YAW_SERVO_BRANCH and primary_handoff_blocked:
        labels.append("handoff_yaw_servo_zero_plus45_pre_stage_handoff_blocked")
        labels = [label for label in FAILURE_LABELS if label in set(labels)]
    if str(branch_name or "") == PRE_STAGE_REACQUIRE_FSM_BRANCH and primary_handoff_blocked:
        labels.append("pre_stage_fsm_zero_plus45_pre_stage_handoff_blocked")
        labels = [label for label in FAILURE_LABELS if label in set(labels)]
    if str(branch_name or "") == PRE_STAGE_PATH_TRACKER_BRANCH and primary_handoff_blocked:
        labels.append("pre_stage_path_tracker_zero_plus45_pre_stage_handoff_blocked")
        labels = [label for label in FAILURE_LABELS if label in set(labels)]
    if str(branch_name or "") == PRE_STAGE_TRAJECTORY_OWNER_BRANCH and primary_handoff_blocked:
        labels.append("pre_stage_trajectory_owner_zero_plus45_pre_stage_handoff_blocked")
        labels = [label for label in FAILURE_LABELS if label in set(labels)]
    return {
        "type": "gather_control_failure_audit_branch",
        "generated_utc": utc_now(),
        "branch_name": branch_name,
        "branch_slug": branch_slug,
        "source_summary_path": str(source_summary_path),
        "source_campaign_id": str(source_summary.get("campaign_id", "") or ""),
        "source_gather_control_family": str(source_summary.get("gather_control_family", "") or ""),
        "case_count": len(case_summaries),
        "case_order": case_order,
        "primary_case_ids": list(PRIMARY_CASE_IDS),
        "primary_pre_stage_handoff_pass": {
            case_id: next(
                (
                    case.get("fresh_pre_stage_handoff_pass")
                    for case in case_summaries
                    if case.get("case_id") == case_id
                ),
                None,
            )
            for case_id in PRIMARY_CASE_IDS
        },
        "primary_cases_pre_stage_handoff_blocked": bool(primary_handoff_blocked),
        "labels": labels,
        "failure_labels": labels,
        "cases": case_summaries,
    }


def _recommend_next_action(branches: list[dict[str, Any]]) -> tuple[str, list[str]]:
    branch_names = {str(branch.get("branch_name", "") or "") for branch in branches}
    blocked_branches = {
        str(branch.get("branch_name", "") or "")
        for branch in branches
        if bool(branch.get("primary_cases_pre_stage_handoff_blocked", False))
    }
    if (
        BLOCKED_CURRENT_CANDIDATE_BRANCHES.issubset(branch_names)
        and BLOCKED_CURRENT_CANDIDATE_BRANCHES.issubset(blocked_branches)
    ):
        return (
            RECOMMENDED_RETIRE_BLOCKED_AND_DESIGN_NAV2_FOLLOW_PATH,
            [
                "region_funnel_v1_zero_plus45_pre_stage_handoff_blocked",
                "nav2_reacquire_v1_zero_plus45_pre_stage_handoff_blocked",
                "constrained_local_planner_v1_zero_plus45_pre_stage_handoff_blocked",
                "docking_reacquire_v1_zero_plus45_pre_stage_handoff_blocked",
                "handoff_yaw_servo_v1_zero_plus45_pre_stage_handoff_blocked",
                "pre_stage_reacquire_fsm_v1_zero_plus45_pre_stage_handoff_blocked",
                "pre_stage_path_tracker_v1_zero_plus45_pre_stage_handoff_blocked",
                "pre_stage_trajectory_owner_v1_zero_plus45_pre_stage_handoff_blocked",
            ],
        )
    if BLOCKED_CANDIDATE_BRANCHES.issubset(branch_names) and BLOCKED_CANDIDATE_BRANCHES.issubset(blocked_branches):
        return (
            RECOMMENDED_RETIRE_AND_DESIGN,
            [
                "region_funnel_v1_zero_plus45_pre_stage_handoff_blocked",
                "nav2_reacquire_v1_zero_plus45_pre_stage_handoff_blocked",
            ],
        )
    if any(branch.get("primary_cases_pre_stage_handoff_blocked", False) for branch in branches):
        return "inspect_blocked_primary_case_evidence", ["primary_case_pre_stage_handoff_blocked"]
    return "collect_missing_failure_evidence", ["primary_case_blocker_not_confirmed"]


def build_failure_audit_summary(
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
            build_branch_failure_summary(
                branch_name=branch_name,
                source_summary_path=source_path,
                source_summary=source_summary,
            )
        )
    labels = [label for label in FAILURE_LABELS if any(label in branch.get("labels", []) for branch in branches)]
    recommended_next_action, blocking_reasons = _recommend_next_action(branches)
    status = (
        "blocked"
        if recommended_next_action
        in {
            RECOMMENDED_RETIRE_AND_DESIGN,
            RECOMMENDED_RETIRE_BLOCKED_AND_DEFINE_REQUIREMENTS,
            RECOMMENDED_RETIRE_BLOCKED_AND_DESIGN_NAV2_FOLLOW_PATH,
        }
        else "needs_review"
    )
    return {
        "type": "gather_control_failure_audit",
        "generated_utc": utc_now(),
        "campaign_id": campaign_id,
        "status": status,
        "branch_count": len(branches),
        "primary_case_ids": list(PRIMARY_CASE_IDS),
        "secondary_case_ids": list(SECONDARY_CASE_IDS),
        "failure_labels": labels,
        "recommended_next_action": recommended_next_action,
        "blocking_reasons": blocking_reasons,
        "branches": branches,
    }


def build_scorecard_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Gather Control Failure Audit",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- status: `{summary.get('status', '')}`",
        f"- recommended_next_action: `{summary.get('recommended_next_action', '')}`",
        "",
        "| branch | primary handoff blocked | zero handoff | plus45 handoff | labels | missing evidence | zero reason | plus45 reason |",
        "|---|---:|---:|---:|---|---:|---|---|",
    ]
    for branch in _list_value(summary.get("branches")):
        if not isinstance(branch, dict):
            continue
        cases = {
            str(case.get("case_id", "") or ""): case
            for case in _list_value(branch.get("cases"))
            if isinstance(case, dict)
        }
        zero = cases.get("zero", {})
        plus45 = cases.get("plus45", {})
        missing_evidence_count = sum(
            len(case.get("missing_evidence", []))
            for case in _list_value(branch.get("cases"))
            if isinstance(case, dict)
        )
        lines.append(
            "| "
            f"`{branch.get('branch_name', '')}` | "
            f"`{bool(branch.get('primary_cases_pre_stage_handoff_blocked', False))}` | "
            f"`{zero.get('fresh_pre_stage_handoff_pass', '')}` | "
            f"`{plus45.get('fresh_pre_stage_handoff_pass', '')}` | "
            f"`{', '.join(str(label) for label in branch.get('labels', [])) or 'none'}` | "
            f"{missing_evidence_count} | "
            f"`{zero.get('fresh_attempt_reason', '') or 'none'}` | "
            f"`{plus45.get('fresh_attempt_reason', '') or 'none'}` |"
        )
    lines.append("")
    return "\n".join(lines)


def write_failure_audit_bundle(
    *,
    repo_root: Path,
    campaign_id: str,
    summary: dict[str, Any],
) -> dict[str, Path]:
    output_root = ensure_dir(repo_root / "artifacts" / "session" / campaign_id / OUTPUT_KIND)
    summary_path = output_root / "failure_audit_summary.json"
    scorecard_path = output_root / "scorecard.md"
    write_json(summary_path, summary)
    scorecard_path.write_text(build_scorecard_markdown(summary), encoding="utf-8")
    return {"output_root": output_root, "summary_path": summary_path, "scorecard_path": scorecard_path}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True, help="Failure-audit artifact campaign id.")
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
    summary = build_failure_audit_summary(campaign_id=campaign_id, branch_specs=branch_specs)
    paths = write_failure_audit_bundle(repo_root=REPO_ROOT, campaign_id=campaign_id, summary=summary)
    print(f"GATHER_CONTROL_FAILURE_AUDIT_SUMMARY={paths['summary_path']}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
