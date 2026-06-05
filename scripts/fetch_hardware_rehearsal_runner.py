#!/usr/bin/env python3
"""Preflight or execute one step from the fetch hardware rehearsal plan."""

from __future__ import annotations

import argparse
import json
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
    "artifacts/session/analysis_fetch_hardware_rehearsal_plan_20260605/"
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
        payload = json.loads(path.read_text(encoding="utf-8"))
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
            "timed_out": True,
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
    if bool(args.execute):
        if len(selected_steps) != 1:
            issues.append("execute_requires_exactly_one_step")
        if preflight_pass and len(selected_steps) == 1:
            execution = run_step(selected_steps[0], timeout_s=int(args.timeout_s))
            if not bool(execution.get("pass", False)):
                issues.append("executed_step_failed")
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
