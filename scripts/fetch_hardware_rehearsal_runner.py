#!/usr/bin/env python3
"""Preflight or execute one step from the fetch hardware rehearsal plan."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
RUNNER_KIND = "fetch_hardware_rehearsal_runner"
DEFAULT_PLAN_SUMMARY = (
    "artifacts/session/analysis_fetch_hardware_rehearsal_plan_seed20260648_20260605/"
    "fetch_hardware_rehearsal_plan/hardware_rehearsal_plan_summary.json"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_path(path_text: str | Path) -> Path:
    path = Path(str(path_text or "").strip())
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def artifact_display_path(path_text: str | Path) -> str:
    resolved = resolve_path(path_text)
    try:
        return str(resolved.relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(resolved)


def read_json(path_text: str | Path) -> tuple[dict[str, Any], list[str]]:
    path = resolve_path(path_text)
    if not path.is_file():
        return {}, [f"missing_json:{artifact_display_path(path)}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # pragma: no cover - defensive artifact parsing
        return {}, [f"invalid_json:{artifact_display_path(path)}:{exc}"]
    if not isinstance(payload, dict):
        return {}, [f"json_not_object:{artifact_display_path(path)}"]
    return payload, []


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def bool_issue(issues: list[str], condition: bool, issue: str) -> None:
    if not condition:
        issues.append(issue)


def command_tokens(command: str) -> list[str]:
    return [part for part in command.split(" ") if part]


def referenced_script(tokens: list[str]) -> str:
    if not tokens:
        return ""
    if tokens[0].lower().startswith("python") and len(tokens) > 1:
        return tokens[1]
    if tokens[0].lower().startswith("powershell") and "-File" in tokens:
        index = tokens.index("-File")
        if index + 1 < len(tokens):
            return tokens[index + 1]
    return ""


def evaluate_step_preflight(step: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    command = str(step.get("command", "") or "")
    tokens = command_tokens(command)
    executable = tokens[0] if tokens else ""
    script_path = referenced_script(tokens)
    bool_issue(issues, bool(command), "step_command_missing")
    bool_issue(issues, bool(executable), "step_executable_missing")
    if executable:
        bool_issue(issues, shutil.which(executable) is not None, f"step_executable_not_found:{executable}")
    if script_path:
        bool_issue(issues, resolve_path(script_path).is_file(), f"step_script_missing:{script_path}")
    required_artifacts = [str(item) for item in list_value(step.get("required_artifacts"))]
    bool_issue(issues, bool(required_artifacts), "step_required_artifacts_missing")
    return {
        "id": str(step.get("id", "")),
        "pass": not issues,
        "issues": issues,
        "command": command,
        "executable": executable,
        "script_path": script_path,
        "required_artifacts": required_artifacts,
        "post_run_analyzer": dict_value(step.get("post_run_analyzer")),
    }


def run_step(step: dict[str, Any], *, timeout_s: int) -> dict[str, Any]:
    command = str(step.get("command", "") or "")
    started_utc = utc_now()
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            shell=True,
            capture_output=True,
            text=True,
            timeout=max(timeout_s, 1),
        )
        return {
            "id": str(step.get("id", "")),
            "started_utc": started_utc,
            "ended_utc": utc_now(),
            "pass": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
            "session_dir": extract_session_dir(completed.stdout),
            "batch_summary_path": extract_marker_path(completed.stdout, "FETCH_PLANNER_ROUTE_REPLAY_BATCH_SUMMARY"),
            "seeded_gate_summary_path": extract_marker_path(completed.stdout, "FETCH_PLANNER_SEEDED_GENERALIZATION_GATE_SUMMARY"),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "id": str(step.get("id", "")),
            "started_utc": started_utc,
            "ended_utc": utc_now(),
            "pass": False,
            "returncode": 124,
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
            "session_dir": extract_session_dir(exc.stdout or "") if isinstance(exc.stdout, str) else "",
            "batch_summary_path": extract_marker_path(exc.stdout or "", "FETCH_PLANNER_ROUTE_REPLAY_BATCH_SUMMARY")
            if isinstance(exc.stdout, str)
            else "",
            "seeded_gate_summary_path": extract_marker_path(exc.stdout or "", "FETCH_PLANNER_SEEDED_GENERALIZATION_GATE_SUMMARY")
            if isinstance(exc.stdout, str)
            else "",
            "timed_out": True,
        }


def extract_session_dir(output: str) -> str:
    match = re.search(r"Session directory:\s*(.+)", output or "")
    if not match:
        return ""
    return match.group(1).strip()


def extract_marker_path(output: str, marker: str) -> str:
    match = re.search(rf"{re.escape(marker)}=(.+)", output or "")
    if not match:
        return ""
    return match.group(1).strip()


def analyzer_campaign_id(step: dict[str, Any], batch_summary_path: str) -> str:
    analyzer = dict_value(step.get("post_run_analyzer"))
    configured = str(analyzer.get("campaign_id", "") or "").strip()
    if configured:
        return configured
    batch_path = resolve_path(batch_summary_path)
    campaign = batch_path.parent.parent.name if batch_path.name else ""
    return f"{campaign}_analysis" if campaign else f"fetch_hardware_rehearsal_analysis_{current_utc_stamp()}"


def run_post_run_analyzer(step: dict[str, Any], execution: dict[str, Any], *, timeout_s: int) -> dict[str, Any]:
    analyzer = dict_value(step.get("post_run_analyzer"))
    if str(analyzer.get("type", "") or "") != "fetch_planner_route_uat_analyzer":
        return {}
    batch_summary_path = str(execution.get("batch_summary_path", "") or "")
    planner_summary_path = str(analyzer.get("planner_summary_path", "") or "")
    if not batch_summary_path or not planner_summary_path:
        return {
            "type": "fetch_planner_route_uat_analyzer",
            "pass": False,
            "issues": [issue for issue in [
                "post_run_analyzer_batch_summary_missing" if not batch_summary_path else "",
                "post_run_analyzer_planner_summary_missing" if not planner_summary_path else "",
            ] if issue],
        }

    batch, batch_issues = read_json(batch_summary_path)
    rows = [dict_value(row) for row in list_value(batch.get("rows")) if isinstance(row, dict)]
    command = [
        "python",
        "scripts/fetch_planner_route_uat_analyzer.py",
        "--campaign-id",
        analyzer_campaign_id(step, batch_summary_path),
        "--planner-summary",
        artifact_display_path(planner_summary_path),
    ]
    for row in rows:
        mission_summary_path = str(row.get("mission_summary_path", "") or "")
        visual_package_summary_path = str(row.get("visual_package_summary_path", "") or "")
        if mission_summary_path:
            command.extend(["--mission-summary", artifact_display_path(mission_summary_path)])
        if visual_package_summary_path:
            command.extend(["--visual-package-summary", artifact_display_path(visual_package_summary_path)])

    issues = [issue for issue in batch_issues if issue]
    bool_issue(issues, bool(rows), "post_run_analyzer_batch_rows_missing")
    bool_issue(issues, resolve_path(planner_summary_path).is_file(), "post_run_analyzer_planner_summary_missing")
    if issues:
        return {
            "type": "fetch_planner_route_uat_analyzer",
            "pass": False,
            "issues": issues,
            "command": command,
            "batch_summary_path": artifact_display_path(batch_summary_path),
            "planner_summary_path": artifact_display_path(planner_summary_path),
        }

    started_utc = utc_now()
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=max(timeout_s, 1),
        )
        summary_path = extract_marker_path(completed.stdout, "FETCH_PLANNER_ROUTE_UAT_ANALYZER_SUMMARY")
        summary, summary_issues = read_json(summary_path) if summary_path else ({}, ["post_run_analyzer_summary_missing"])
        run_issues = list(summary_issues)
        bool_issue(run_issues, completed.returncode == 0, "post_run_analyzer_command_failed")
        bool_issue(run_issues, bool(summary.get("pass", False)), "post_run_analyzer_summary_not_pass")
        return {
            "type": "fetch_planner_route_uat_analyzer",
            "started_utc": started_utc,
            "ended_utc": utc_now(),
            "pass": not run_issues,
            "issues": run_issues,
            "returncode": completed.returncode,
            "command": command,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
            "summary_path": artifact_display_path(summary_path) if summary_path else "",
            "scorecard_path": artifact_display_path(summary.get("scorecard_path", "")) if summary else "",
            "batch_summary_path": artifact_display_path(batch_summary_path),
            "planner_summary_path": artifact_display_path(planner_summary_path),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "type": "fetch_planner_route_uat_analyzer",
            "started_utc": started_utc,
            "ended_utc": utc_now(),
            "pass": False,
            "issues": ["post_run_analyzer_timed_out"],
            "returncode": 124,
            "command": command,
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
            "batch_summary_path": artifact_display_path(batch_summary_path),
            "planner_summary_path": artifact_display_path(planner_summary_path),
        }


def nested_value(payload: dict[str, Any], path_text: str) -> Any:
    value: Any = payload
    for part in path_text.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def validate_artifact_spec(spec: str, *, session_dir: str, readiness: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    resolved = ""
    if spec.startswith("session:"):
        rel_path = spec.split(":", 1)[1]
        if not session_dir:
            issues.append("missing_session_dir")
        else:
            resolved = str((Path(session_dir) / rel_path).resolve())
    elif spec.startswith("readiness_path:"):
        _, tail = spec.split(":", 1)
        json_path, suffix = (tail.split(":", 1) + [""])[:2] if ":" in tail else (tail, "")
        base = nested_value(readiness, json_path)
        if not base:
            issues.append(f"missing_readiness_path:{json_path}")
        else:
            resolved = str((Path(str(base)) / suffix).resolve()) if suffix else str(Path(str(base)).resolve())
    else:
        if not session_dir:
            issues.append("missing_session_dir")
        else:
            resolved = str((Path(session_dir) / spec).resolve())
    if resolved:
        issues.extend([] if Path(resolved).is_file() else [f"missing_artifact:{artifact_display_path(resolved)}"])
    return {
        "spec": spec,
        "path": artifact_display_path(resolved) if resolved else "",
        "pass": not issues,
        "issues": issues,
    }


def validate_execution_artifacts(step: dict[str, Any], execution: dict[str, Any]) -> dict[str, Any]:
    seeded_gate_summary_path = str(execution.get("seeded_gate_summary_path", "") or "")
    if seeded_gate_summary_path:
        return validate_seeded_gate_artifacts(seeded_gate_summary_path)
    batch_summary_path = str(execution.get("batch_summary_path", "") or "")
    if batch_summary_path:
        return validate_replay_batch_artifacts(batch_summary_path)
    session_dir = str(execution.get("session_dir", "") or "")
    readiness_path = Path(session_dir) / "readiness_report.json" if session_dir else Path()
    readiness, readiness_issues = read_json(readiness_path) if session_dir else ({}, ["missing_session_dir"])
    rows = [
        validate_artifact_spec(str(spec), session_dir=session_dir, readiness=readiness)
        for spec in list_value(step.get("required_artifacts"))
    ]
    issues = list(readiness_issues)
    issues.extend(issue for row in rows for issue in list_value(row.get("issues")))
    return {
        "pass": not issues,
        "issues": issues,
        "session_dir": artifact_display_path(session_dir) if session_dir else "",
        "readiness_report": artifact_display_path(readiness_path) if session_dir else "",
        "artifacts": rows,
    }


def validate_seeded_gate_artifacts(gate_summary_path: str) -> dict[str, Any]:
    gate, issues = read_json(gate_summary_path)
    bool_issue(issues, bool(gate.get("pass", False)), "seeded_gate_not_pass")
    bool_issue(issues, bool(gate.get("planner_gate_pass", False)), "seeded_gate_planner_not_pass")
    bool_issue(issues, bool(gate.get("replay_pass", False)), "seeded_gate_replay_not_pass")
    bool_issue(issues, bool(gate.get("analyzer_pass", False)), "seeded_gate_analyzer_not_pass")
    expected_executable_count = int(gate.get("expected_executable_count") or 0)
    bool_issue(issues, expected_executable_count > 0, "seeded_gate_expected_executable_count_zero")

    artifact_rows: list[dict[str, Any]] = [
        {
            "spec": "seeded_gate_summary",
            "path": artifact_display_path(gate_summary_path),
            "pass": not issues,
            "issues": list(issues),
        }
    ]
    child_specs = {
        "planner_summary": str(gate.get("planner_summary_path", "") or ""),
        "replay_summary": str(gate.get("replay_summary_path", "") or ""),
        "analyzer_summary": str(gate.get("analyzer_summary_path", "") or ""),
    }
    for spec, path in child_specs.items():
        _, child_issues = read_json(path)
        artifact_rows.append(
            {
                "spec": spec,
                "path": artifact_display_path(path) if path else "",
                "pass": not child_issues,
                "issues": child_issues,
            }
        )
        issues.extend(child_issues)

    replay_summary_path = child_specs["replay_summary"]
    if replay_summary_path:
        replay_validation = validate_replay_batch_artifacts(replay_summary_path)
        issues.extend(list_value(replay_validation.get("issues")))
        artifact_rows.append(
            {
                "spec": "seeded_gate_replay_batch_validation",
                "path": artifact_display_path(replay_summary_path),
                "pass": bool(replay_validation.get("pass", False)),
                "issues": list_value(replay_validation.get("issues")),
            }
        )
        artifact_rows.extend(list_value(replay_validation.get("artifacts")))

    return {
        "pass": not issues,
        "issues": issues,
        "seeded_gate_summary": artifact_display_path(gate_summary_path),
        "batch_summary": artifact_display_path(replay_summary_path) if replay_summary_path else "",
        "session_dir": "",
        "readiness_report": "",
        "artifacts": artifact_rows,
    }


def validate_replay_batch_artifacts(batch_summary_path: str) -> dict[str, Any]:
    batch, issues = read_json(batch_summary_path)
    bool_issue(issues, bool(batch.get("pass", False)), "batch_summary_not_pass")
    rows = [dict_value(row) for row in list_value(batch.get("rows")) if isinstance(row, dict)]
    selected_count = int(batch.get("selected_count") or 0)
    visual_package_pass_count = int(batch.get("visual_package_pass_count") or 0)
    mission_fail_count = int(batch.get("mission_fail_count") or 0)
    bool_issue(issues, selected_count > 0, "batch_selected_count_zero")
    bool_issue(issues, mission_fail_count == 0, "batch_mission_fail_count_nonzero")
    bool_issue(issues, visual_package_pass_count == selected_count, "batch_visual_package_count_mismatch")
    artifact_rows: list[dict[str, Any]] = [
        {
            "spec": "batch_summary",
            "path": artifact_display_path(batch_summary_path),
            "pass": not issues,
            "issues": list(issues),
        }
    ]
    for row in rows:
        row_id = str(row.get("scene_id", "") or row.get("label", "") or "row")
        mission_path = str(row.get("mission_summary_path", "") or "")
        package_path = str(row.get("visual_package_summary_path", "") or "")
        mission, mission_issues = read_json(mission_path)
        package, package_issues = read_json(package_path)
        planner_route_only_pass = bool(mission.get("planner_route_only_pass", False)) and not bool(
            mission.get("local_fetch_dispatched", True)
        )
        bool_issue(mission_issues, bool(mission.get("pass", False)), f"{row_id}:mission_not_pass")
        if planner_route_only_pass:
            bool_issue(mission_issues, planner_route_only_pass, f"{row_id}:planner_route_only_not_pass")
        else:
            bool_issue(
                mission_issues,
                bool(dict_value(mission.get("control_preflight")).get("pass", False)),
                f"{row_id}:control_preflight_not_pass",
            )
        bool_issue(package_issues, bool(package.get("pass", False)), f"{row_id}:visual_package_not_pass")
        keyframe_reviews = [dict_value(item) for item in list_value(package.get("keyframe_reviews"))]
        bool_issue(
            package_issues,
            any(bool(item.get("ok", False)) and resolve_path(str(item.get("path", ""))).is_file() for item in keyframe_reviews),
            f"{row_id}:keyframe_review_missing",
        )
        videos = [dict_value(item) for item in list_value(package.get("videos"))]
        for video_name in ("raw_camera_browser.mp4", "topdown_telemetry_browser.mp4", "world_stream.mp4"):
            bool_issue(
                package_issues,
                any(
                    str(video.get("name", "")) == video_name
                    and bool(video.get("browser_playable", False))
                    and resolve_path(str(video.get("path", ""))).is_file()
                    for video in videos
                ),
                f"{row_id}:{video_name}_missing_or_unplayable",
            )
        artifact_rows.append(
            {
                "spec": f"{row_id}:mission_summary",
                "path": artifact_display_path(mission_path) if mission_path else "",
                "pass": not mission_issues,
                "issues": mission_issues,
            }
        )
        artifact_rows.append(
            {
                "spec": f"{row_id}:visual_package",
                "path": artifact_display_path(package_path) if package_path else "",
                "pass": not package_issues,
                "issues": package_issues,
            }
        )
        issues.extend(mission_issues)
        issues.extend(package_issues)
    return {
        "pass": not issues,
        "issues": issues,
        "batch_summary": artifact_display_path(batch_summary_path),
        "session_dir": "",
        "readiness_report": "",
        "artifacts": artifact_rows,
    }


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    plan, issues = read_json(args.plan_summary)
    bool_issue(issues, bool(plan.get("pass", False)), "plan_summary_not_pass")
    bool_issue(issues, bool(plan.get("hardware_rehearsal_plan_ready", False)), "plan_not_rehearsal_ready")
    bool_issue(issues, plan.get("hardware_proven") is False, "plan_should_not_claim_hardware_proven")
    steps = [dict_value(step) for step in list_value(plan.get("planned_steps")) if isinstance(step, dict)]
    bool_issue(issues, bool(steps), "plan_steps_missing")
    selected_steps = steps
    if args.step_id:
        selected_steps = [step for step in steps if str(step.get("id", "")) == str(args.step_id)]
        bool_issue(issues, bool(selected_steps), f"step_id_not_found:{args.step_id}")
    preflights = [evaluate_step_preflight(step) for step in selected_steps]
    preflight_pass = not issues and all(bool(row.get("pass", False)) for row in preflights)
    execution = {}
    execution_artifacts = {}
    post_run_analyzer = {}
    if bool(args.execute):
        if len(selected_steps) != 1:
            issues.append("execute_requires_exactly_one_step")
        if preflight_pass and len(selected_steps) == 1:
            execution = run_step(selected_steps[0], timeout_s=int(args.timeout_s))
            if not bool(execution.get("pass", False)):
                issues.append("executed_step_failed")
            execution_artifacts = validate_execution_artifacts(selected_steps[0], execution)
            if not bool(execution_artifacts.get("pass", False)):
                issues.append("execution_artifact_contract_failed")
            if bool(execution.get("pass", False)) and dict_value(selected_steps[0].get("post_run_analyzer")):
                post_run_analyzer = run_post_run_analyzer(
                    selected_steps[0],
                    execution,
                    timeout_s=int(args.timeout_s),
                )
                if not bool(post_run_analyzer.get("pass", False)):
                    issues.append("post_run_analyzer_failed")
    mode = "execute" if bool(args.execute) else "preflight"
    pass_value = not issues and preflight_pass and (not args.execute or bool(execution.get("pass", False)))
    return {
        "generated_utc": utc_now(),
        "type": RUNNER_KIND,
        "campaign_id": str(args.campaign_id),
        "mode": mode,
        "pass": pass_value,
        "promotion_evidence": False,
        "hardware_proven": False,
        "plan_summary_path": artifact_display_path(args.plan_summary),
        "milestone_interpretation": (
            "planner_routed_fetch_hardware_rehearsal_preflight_ready"
            if pass_value and mode == "preflight"
            else "planner_routed_fetch_hardware_rehearsal_step_executed"
            if pass_value
            else "planner_routed_fetch_hardware_rehearsal_runner_incomplete"
        ),
        "issues": issues,
        "step_preflights": preflights,
        "execution": execution,
        "execution_artifacts": execution_artifacts,
        "post_run_analyzer": post_run_analyzer,
        "next_action": (
            "execute_runtime_stack_smoke"
            if pass_value and mode == "preflight"
            else "review_execution_artifacts"
            if pass_value
            else "repair_runner_or_plan_preflight"
        ),
    }


def artifact_link(path_text: str) -> str:
    return f"[artifact](/{path_text})" if str(path_text).startswith(("artifacts/", "runtime/", "docs/")) else str(path_text)


def artifact_link_or_empty(path_text: str) -> str:
    link = artifact_link(path_text)
    return link if link else "` `"


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Fetch Hardware Rehearsal Runner",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- mode: `{summary.get('mode', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- hardware_proven: `{summary.get('hardware_proven', False)}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        f"- next_action: `{summary.get('next_action', '')}`",
        f"- issues: `{summary.get('issues', [])}`",
        f"- plan_summary: {artifact_link(str(summary.get('plan_summary_path', '')))}",
        "",
        "## Step Preflights",
        "",
    ]
    for row in list_value(summary.get("step_preflights")):
        if not isinstance(row, dict):
            continue
        lines.extend(
            [
                f"- `{row.get('id', '')}` pass=`{row.get('pass', False)}` issues=`{row.get('issues', [])}`",
                f"  - command: `{row.get('command', '')}`",
                f"  - required_artifacts: `{row.get('required_artifacts', [])}`",
                f"  - post_run_analyzer: `{row.get('post_run_analyzer', {})}`",
            ]
        )
    execution = dict_value(summary.get("execution"))
    if execution:
        lines.extend(
            [
                "",
                "## Execution",
                "",
                f"- step_id: `{execution.get('id', '')}`",
                f"- pass: `{execution.get('pass', False)}`",
                f"- returncode: `{execution.get('returncode', '')}`",
                f"- timed_out: `{execution.get('timed_out', False)}`",
                f"- session_dir: `{execution.get('session_dir', '')}`",
                f"- batch_summary_path: `{execution.get('batch_summary_path', '')}`",
                f"- seeded_gate_summary_path: `{execution.get('seeded_gate_summary_path', '')}`",
            ]
        )
    execution_artifacts = dict_value(summary.get("execution_artifacts"))
    if execution_artifacts:
        lines.extend(
            [
                "",
                "## Execution Artifacts",
                "",
                f"- pass: `{execution_artifacts.get('pass', False)}`",
                f"- issues: `{execution_artifacts.get('issues', [])}`",
                f"- session_dir: {artifact_link_or_empty(str(execution_artifacts.get('session_dir', '')))}",
                f"- readiness_report: {artifact_link_or_empty(str(execution_artifacts.get('readiness_report', '')))}",
                f"- seeded_gate_summary: {artifact_link_or_empty(str(execution_artifacts.get('seeded_gate_summary', '')))}",
                f"- batch_summary: {artifact_link_or_empty(str(execution_artifacts.get('batch_summary', '')))}",
            ]
        )
        for row in list_value(execution_artifacts.get("artifacts")):
            if not isinstance(row, dict):
                continue
            lines.append(
                f"- `{row.get('spec', '')}` pass=`{row.get('pass', False)}` "
                f"issues=`{row.get('issues', [])}` {artifact_link(str(row.get('path', '')))}"
            )
    post_run_analyzer = dict_value(summary.get("post_run_analyzer"))
    if post_run_analyzer:
        lines.extend(
            [
                "",
                "## Post-Run Analyzer",
                "",
                f"- type: `{post_run_analyzer.get('type', '')}`",
                f"- pass: `{post_run_analyzer.get('pass', False)}`",
                f"- issues: `{post_run_analyzer.get('issues', [])}`",
                f"- returncode: `{post_run_analyzer.get('returncode', '')}`",
                f"- summary: {artifact_link_or_empty(str(post_run_analyzer.get('summary_path', '')))}",
                f"- scorecard: {artifact_link_or_empty(str(post_run_analyzer.get('scorecard_path', '')))}",
                f"- batch_summary: {artifact_link_or_empty(str(post_run_analyzer.get('batch_summary_path', '')))}",
                f"- planner_summary: {artifact_link_or_empty(str(post_run_analyzer.get('planner_summary_path', '')))}",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight or execute a fetch hardware rehearsal plan step.")
    parser.add_argument("--campaign-id", default=f"fetch_hardware_rehearsal_runner_{current_utc_stamp()}")
    parser.add_argument("--plan-summary", default=DEFAULT_PLAN_SUMMARY)
    parser.add_argument("--step-id", default="")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--timeout-s", type=int, default=600)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / RUNNER_KIND)
    summary = build_summary(args)
    summary_path = root / "rehearsal_runner_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["summary_path"] = artifact_display_path(summary_path)
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_HARDWARE_REHEARSAL_RUNNER_SUMMARY={summary_path}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
