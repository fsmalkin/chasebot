#!/usr/bin/env python3
"""Build the launch checklist for the provider-backed planner rerun."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

from chasecar_env import load_repo_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
load_repo_dotenv(REPO_ROOT)
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
ANALYZER_KIND = "fetch_provider_launch_checklist"
DEFAULT_PROVIDER_READINESS = (
    "artifacts/session/provider_rerun_readiness_rollup_seed20260650_20260605/"
    "fetch_planner_provider_rerun_readiness/provider_rerun_readiness_summary.json"
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
    path = resolve_path(path_text)
    try:
        return str(path.relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


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


def dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def command_arg(command: str, flag: str) -> str:
    parts = str(command or "").split()
    try:
        index = parts.index(flag)
    except ValueError:
        return ""
    if index + 1 >= len(parts):
        return ""
    return parts[index + 1].strip()


def summary_to_scorecard(path_text: str) -> str:
    text = str(path_text or "").replace("\\", "/")
    if not text:
        return ""
    name = Path(text).name
    if name.endswith(".json"):
        return str(Path(text).with_name("scorecard.md")).replace("\\", "/")
    return text


def build_expected_artifacts(commands: dict[str, Any]) -> dict[str, str]:
    comparison_command = str(commands.get("provider_rerun_comparison", "") or "")
    planner_summary = command_arg(comparison_command, "--provider-planner-summary")
    replay_summary = command_arg(comparison_command, "--provider-replay-summary")
    route_uat_summary = command_arg(comparison_command, "--provider-route-uat-summary")
    comparison_campaign = command_arg(comparison_command, "--campaign-id")
    comparison_summary = (
        f"artifacts/session/{comparison_campaign}/fetch_planner_provider_rerun_comparison/"
        "provider_rerun_comparison_summary.json"
        if comparison_campaign
        else ""
    )
    return {
        "provider_planner_summary": planner_summary.replace("\\", "/"),
        "provider_planner_scorecard": summary_to_scorecard(planner_summary),
        "provider_replay_summary": replay_summary.replace("\\", "/"),
        "provider_replay_scorecard": summary_to_scorecard(replay_summary),
        "provider_route_uat_summary": route_uat_summary.replace("\\", "/"),
        "provider_route_uat_scorecard": summary_to_scorecard(route_uat_summary),
        "provider_comparison_summary": comparison_summary,
        "provider_comparison_scorecard": summary_to_scorecard(comparison_summary),
    }


def build_steps(commands: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": "provider_preflight",
            "owner": "operator_or_agent",
            "command": "python scripts\\fetch_planner_provider_rerun_readiness.py --campaign-id provider_rerun_readiness_rollup_seed20260650_20260605",
            "success_condition": "provider_rerun_ready=true and blockers=[]",
        },
        {
            "id": "provider_planner_gate",
            "owner": "agent",
            "command": str(commands.get("planner_gate", "") or ""),
            "success_condition": "provider_status_counts.ok equals random_cases and wrong_fetch_dispatch_count=0",
        },
        {
            "id": "provider_visual_replay",
            "owner": "agent",
            "command": str(commands.get("explicit_all_routes_replay", "") or ""),
            "success_condition": "three browser-watchable rows per route family pass or planner-only abstain correctly",
        },
        {
            "id": "provider_route_uat_analysis",
            "owner": "agent",
            "command": str(commands.get("analysis", "") or ""),
            "success_condition": "execution/setup/contact quality are clean and first_contact_blocker_count=0",
        },
        {
            "id": "provider_rerun_comparison",
            "owner": "agent",
            "command": str(commands.get("provider_rerun_comparison", "") or ""),
            "success_condition": "guarded_provider_rerun_ready=true with provider-vs-baseline deltas recorded",
        },
        {
            "id": "refresh_dashboard_proofs",
            "owner": "agent",
            "command": (
                "python scripts\\fetch_generalized_milestone_readiness.py --campaign-id "
                "generalized_fetch_to_pose_milestone_readiness_provider_rerun_20260605; "
                "python scripts\\fetch_dashboard_visual_evidence_audit.py --campaign-id "
                "dashboard_visual_evidence_audit_provider_rerun_20260605"
            ),
            "success_condition": "dashboard links resolve and milestone_complete remains evidence-bound",
        },
    ]


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    readiness, issues = read_json(str(args.provider_readiness_summary))
    commands = dict_value(readiness.get("next_commands"))
    blockers = [str(item) for item in list_value(readiness.get("blockers"))]
    openai_api_key_present = bool(str(args.openai_api_key or "").strip())
    if openai_api_key_present and "missing_openai_api_key" in blockers:
        blockers = [blocker for blocker in blockers if blocker != "missing_openai_api_key"]
    provider_rerun_ready = bool(readiness.get("provider_rerun_ready", False)) or (
        openai_api_key_present and not blockers and bool(commands)
    )
    launch_plan_ready = bool(commands) and not issues
    expected_artifacts = build_expected_artifacts(commands)
    missing_commands = [step["id"] for step in build_steps(commands) if not str(step.get("command", "") or "")]
    if missing_commands:
        issues.append(f"missing_launch_commands:{','.join(missing_commands)}")
    contract = dict_value(readiness.get("rerun_contract"))
    return {
        "generated_utc": utc_now(),
        "type": ANALYZER_KIND,
        "campaign_id": str(args.campaign_id or ""),
        "pass": launch_plan_ready and not issues,
        "promotion_evidence": False,
        "hardware_proven": False,
        "provider_backed_authority_proven": False,
        "provider_launch_ready": provider_rerun_ready and not issues,
        "launch_plan_ready": launch_plan_ready,
        "openai_api_key_present": openai_api_key_present,
        "readiness_level": "ready_for_provider_launch" if provider_rerun_ready and not issues else "provider_launch_waiting",
        "milestone_interpretation": (
            "provider_launch_ready"
            if provider_rerun_ready and not issues
            else "provider_launch_plan_ready_waiting_on_credentials"
        ),
        "issues": issues,
        "blockers": blockers,
        "provider_readiness_summary": artifact_display_path(str(args.provider_readiness_summary)),
        "rerun_contract": {
            "seed": int_value(contract.get("seed")),
            "random_cases": int_value(contract.get("random_cases")),
            "max_per_route": int_value(contract.get("max_per_route")),
            "planner_mode": str(contract.get("planner_mode", "") or ""),
            "required_provider_status": str(contract.get("required_provider_status", "") or ""),
            "required_guard_result": str(contract.get("required_guard_result", "") or ""),
            "required_visual_replay": str(contract.get("required_visual_replay", "") or ""),
        },
        "expected_artifacts": expected_artifacts,
        "launch_steps": build_steps(commands),
        "claim_boundaries": [
            "provider_backed_authority_proven_false_until_provider_artifacts_pass",
            "promotion_evidence_false_until_canonical_promotion_gate",
            "hardware_proven_false_until_physical_onboard_run",
        ],
    }


def artifact_link(path_text: str) -> str:
    text = str(path_text or "").replace("\\", "/")
    return f"[artifact](/{text})" if text.startswith(("artifacts/", "runtime/")) else text


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Fetch Provider Launch Checklist",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- launch_plan_ready: `{summary.get('launch_plan_ready', False)}`",
        f"- provider_launch_ready: `{summary.get('provider_launch_ready', False)}`",
        f"- provider_backed_authority_proven: `{summary.get('provider_backed_authority_proven', False)}`",
        f"- openai_api_key_present: `{summary.get('openai_api_key_present', False)}`",
        f"- readiness_level: `{summary.get('readiness_level', '')}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        f"- issues: `{summary.get('issues', [])}`",
        f"- blockers: `{summary.get('blockers', [])}`",
        f"- provider_readiness_summary: {artifact_link(str(summary.get('provider_readiness_summary', '') or ''))}",
        "",
        "## Rerun Contract",
        "",
    ]
    for key, value in dict_value(summary.get("rerun_contract")).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Expected Artifacts", ""])
    for key, value in dict_value(summary.get("expected_artifacts")).items():
        lines.append(f"- `{key}`: {artifact_link(str(value or ''))}")
    lines.extend(["", "## Launch Steps", ""])
    for step in list_value(summary.get("launch_steps")):
        lines.append(f"### {step.get('id', '')}")
        lines.append("")
        lines.append(f"- owner: `{step.get('owner', '')}`")
        lines.append(f"- success_condition: `{step.get('success_condition', '')}`")
        lines.append("")
        lines.append("```powershell")
        lines.append(str(step.get("command", "") or ""))
        lines.append("```")
        lines.append("")
    lines.extend(["## Claim Boundaries", ""])
    for boundary in list_value(summary.get("claim_boundaries")):
        lines.append(f"- `{boundary}`")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build provider-backed planner launch checklist.")
    parser.add_argument("--campaign-id", default=f"fetch_provider_launch_checklist_{current_utc_stamp()}")
    parser.add_argument("--provider-readiness-summary", default=DEFAULT_PROVIDER_READINESS)
    parser.add_argument("--openai-api-key", default=os.environ.get("OPENAI_API_KEY", ""))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / ANALYZER_KIND)
    summary = build_summary(args)
    summary_path = root / "provider_launch_checklist_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["summary_path"] = artifact_display_path(summary_path)
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_PROVIDER_LAUNCH_CHECKLIST_SUMMARY={summary_path}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
