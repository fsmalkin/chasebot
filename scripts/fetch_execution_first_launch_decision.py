#!/usr/bin/env python3
"""Choose the next execution-first generalized fetch launch lane."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
ANALYZER_KIND = "fetch_execution_first_launch_decision"
DEFAULT_PROVIDER_CHECKLIST = (
    "artifacts/session/provider_launch_checklist_seed20260650_20260605/"
    "fetch_provider_launch_checklist/provider_launch_checklist_summary.json"
)
DEFAULT_ROBOT_PREFLIGHT = (
    "artifacts/session/robot_side_rehearsal_preflight_seed20260648_current_physical_gap_20260605/"
    "fetch_robot_side_rehearsal_preflight/robot_side_rehearsal_preflight_summary.json"
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


def first_commands(steps: list[Any], count: int = 3) -> list[str]:
    commands: list[str] = []
    for step in steps:
        if isinstance(step, dict):
            command = str(step.get("command", "") or "").strip()
        else:
            command = str(step or "").strip()
        if command:
            commands.append(command)
        if len(commands) >= count:
            break
    return commands


def provider_status(provider: dict[str, Any], *, openai_api_key: str) -> dict[str, Any]:
    blockers = [str(item) for item in list_value(provider.get("blockers"))]
    api_key_present = bool(str(openai_api_key or "").strip())
    effective_blockers = [blocker for blocker in blockers if blocker != "missing_openai_api_key" or not api_key_present]
    plan_ready = bool(provider.get("launch_plan_ready", False))
    ready = plan_ready and api_key_present and not effective_blockers
    return {
        "path": "",
        "ready": ready,
        "plan_ready": plan_ready,
        "openai_api_key_present": api_key_present,
        "blockers": effective_blockers,
        "next_commands": first_commands(list_value(provider.get("launch_steps")), count=3),
    }


def physical_status(robot: dict[str, Any], *, allow_physical_launch: bool) -> dict[str, Any]:
    issues = [str(item) for item in list_value(robot.get("issues"))]
    local_ready = bool(robot.get("local_preflight_ready", False))
    hardware_connected = bool(robot.get("hardware_connected", False)) or bool(allow_physical_launch)
    blockers = list(issues)
    if not local_ready:
        blockers.append("robot_side_local_preflight_not_ready")
    if not hardware_connected:
        blockers.append("hardware_connected_false")
    ready = local_ready and hardware_connected and not issues
    return {
        "path": "",
        "ready": ready,
        "local_preflight_ready": local_ready,
        "hardware_connected": hardware_connected,
        "allow_physical_launch": bool(allow_physical_launch),
        "blockers": blockers,
        "next_commands": first_commands(list_value(robot.get("next_commands")), count=3),
    }


def choose_lane(provider: dict[str, Any], physical: dict[str, Any], preference: str) -> str:
    if preference == "provider":
        return "provider_launch" if provider.get("ready") else "waiting_on_external_gate"
    if preference == "physical":
        return "physical_onboard_launch" if physical.get("ready") else "waiting_on_external_gate"
    if provider.get("ready"):
        return "provider_launch"
    if physical.get("ready"):
        return "physical_onboard_launch"
    return "waiting_on_external_gate"


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    provider_payload, provider_issues = read_json(args.provider_checklist_summary)
    robot_payload, robot_issues = read_json(args.robot_side_preflight_summary)
    provider = provider_status(provider_payload, openai_api_key=str(args.openai_api_key or ""))
    physical = physical_status(robot_payload, allow_physical_launch=bool(args.allow_physical_launch))
    provider["path"] = artifact_display_path(str(args.provider_checklist_summary))
    physical["path"] = artifact_display_path(str(args.robot_side_preflight_summary))
    issues = [f"provider:{issue}" for issue in provider_issues]
    issues.extend(f"physical:{issue}" for issue in robot_issues)
    selected = choose_lane(provider, physical, str(args.prefer or "auto"))
    if selected == "provider_launch":
        launch_ready = True
        selected_commands = provider["next_commands"]
        blockers: list[str] = []
    elif selected == "physical_onboard_launch":
        launch_ready = True
        selected_commands = physical["next_commands"]
        blockers = []
    else:
        launch_ready = False
        selected_commands = []
        blockers = [f"provider:{blocker}" for blocker in list_value(provider.get("blockers"))]
        blockers.extend(f"physical:{blocker}" for blocker in list_value(physical.get("blockers")))
    return {
        "generated_utc": utc_now(),
        "type": ANALYZER_KIND,
        "campaign_id": str(args.campaign_id or ""),
        "pass": not issues,
        "promotion_evidence": False,
        "hardware_proven": False,
        "provider_backed_authority_proven": False,
        "launch_ready": launch_ready,
        "selected_lane": selected,
        "preference": str(args.prefer or "auto"),
        "issues": issues,
        "blockers": blockers,
        "provider": provider,
        "physical": physical,
        "selected_next_commands": selected_commands,
        "milestone_interpretation": (
            "execution_first_provider_launch_ready"
            if selected == "provider_launch"
            else "execution_first_physical_launch_ready"
            if selected == "physical_onboard_launch"
            else "execution_first_waiting_on_external_gate"
        ),
    }


def artifact_link(path_text: str) -> str:
    text = str(path_text or "").replace("\\", "/")
    return f"[artifact](/{text})" if text.startswith(("artifacts/", "runtime/", "docs/")) else text


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Fetch Execution-First Launch Decision",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- launch_ready: `{summary.get('launch_ready', False)}`",
        f"- selected_lane: `{summary.get('selected_lane', '')}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- provider_backed_authority_proven: `{summary.get('provider_backed_authority_proven', False)}`",
        f"- hardware_proven: `{summary.get('hardware_proven', False)}`",
        f"- issues: `{summary.get('issues', [])}`",
        f"- blockers: `{summary.get('blockers', [])}`",
        "",
        "## Provider Lane",
        "",
    ]
    provider = dict_value(summary.get("provider"))
    lines.append(f"- ready: `{provider.get('ready', False)}`")
    lines.append(f"- plan_ready: `{provider.get('plan_ready', False)}`")
    lines.append(f"- openai_api_key_present: `{provider.get('openai_api_key_present', False)}`")
    lines.append(f"- blockers: `{provider.get('blockers', [])}`")
    lines.append(f"- source: {artifact_link(str(provider.get('path', '') or ''))}")
    lines.extend(["", "## Physical Lane", ""])
    physical = dict_value(summary.get("physical"))
    lines.append(f"- ready: `{physical.get('ready', False)}`")
    lines.append(f"- local_preflight_ready: `{physical.get('local_preflight_ready', False)}`")
    lines.append(f"- hardware_connected: `{physical.get('hardware_connected', False)}`")
    lines.append(f"- blockers: `{physical.get('blockers', [])}`")
    lines.append(f"- source: {artifact_link(str(physical.get('path', '') or ''))}")
    lines.extend(["", "## Selected Next Commands", ""])
    commands = [str(command) for command in list_value(summary.get("selected_next_commands"))]
    if commands:
        for command in commands:
            lines.append("```powershell")
            lines.append(command)
            lines.append("```")
    else:
        lines.append("- none until an external launch gate opens")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Choose the first available execution-first launch lane.")
    parser.add_argument("--campaign-id", default=f"fetch_execution_first_launch_decision_{current_utc_stamp()}")
    parser.add_argument("--provider-checklist-summary", default=DEFAULT_PROVIDER_CHECKLIST)
    parser.add_argument("--robot-side-preflight-summary", default=DEFAULT_ROBOT_PREFLIGHT)
    parser.add_argument("--openai-api-key", default=os.environ.get("OPENAI_API_KEY", ""))
    parser.add_argument("--prefer", choices=("auto", "provider", "physical"), default="auto")
    parser.add_argument("--allow-physical-launch", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / ANALYZER_KIND)
    summary = build_summary(args)
    summary_path = root / "execution_first_launch_decision_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["summary_path"] = artifact_display_path(summary_path)
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_EXECUTION_FIRST_LAUNCH_DECISION_SUMMARY={summary_path}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
