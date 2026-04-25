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
    "stage_timeout_after_prestage",
)
BLOCKED_CANDIDATE_BRANCHES = {"region_funnel_v1", "nav2_reacquire_v1"}
RECOMMENDED_RETIRE_AND_DESIGN = "retire_current_candidates_and_design_constrained_local_planner_branch"
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


def _case_labels(
    *,
    case: dict[str, Any],
    fresh: dict[str, Any],
    capture_entry: dict[str, Any],
    mission_verdict: dict[str, Any],
    nav2_debug: dict[str, Any],
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
    if int(nav2_debug.get("post_reacquire_not_handoff_ready_count", 0) or 0) > 0:
        labels.append("post_reacquire_not_handoff_ready")

    latest = _dict_value(_first_run(case).get("latest_approach_progress"))
    latest_pre_stage = _dict_value(latest.get("pre_stage"))
    latest_reason = str(latest.get("reason", "") or "")
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

    missing_evidence: list[str] = []
    if mission_verdict_status in {"not_referenced", "missing", "unreadable"}:
        missing_evidence.append(f"mission_verdict_{mission_verdict_status}")
    if state_history_status in {"not_referenced", "missing"}:
        missing_evidence.append(f"state_history_{state_history_status}")

    labels = _case_labels(
        case=case,
        fresh=fresh,
        capture_entry=capture_entry,
        mission_verdict=mission_verdict,
        nav2_debug=nav2_debug,
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
    status = "blocked" if recommended_next_action == RECOMMENDED_RETIRE_AND_DESIGN else "needs_review"
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
