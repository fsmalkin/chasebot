#!/usr/bin/env python3
"""Create a robot-side fetch rehearsal preflight/runbook artifact."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
PREFLIGHT_KIND = "fetch_robot_side_rehearsal_preflight"
DEFAULT_READINESS_SUMMARY = (
    "artifacts/session/hardware_transfer_readiness_seed20260648_dashboard_20260605/"
    "fetch_hardware_transfer_readiness/hardware_transfer_readiness_summary.json"
)
DEFAULT_REHEARSAL_PLAN = (
    "artifacts/session/analysis_fetch_hardware_rehearsal_plan_seed20260648_20260605/"
    "fetch_hardware_rehearsal_plan/hardware_rehearsal_plan_summary.json"
)
DEFAULT_PHYSICAL_GAP_SUMMARY = (
    "artifacts/session/physical_onboard_proof_gap_current_proof_cards_20260605/"
    "fetch_physical_onboard_proof_gap/physical_onboard_proof_gap_summary.json"
)
DEFAULT_DASHBOARD_URL = "http://127.0.0.1:8883"
CURRENT_REHEARSAL_SEED = "20260648"


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


def bool_issue(issues: list[str], condition: bool, issue: str) -> None:
    if not condition:
        issues.append(issue)


def command_check(command: str) -> dict[str, Any]:
    resolved = shutil.which(command)
    return {
        "command": command,
        "pass": bool(resolved),
        "path": resolved or "",
        "issues": [] if resolved else [f"command_not_found:{command}"],
    }


def file_check(path_text: str) -> dict[str, Any]:
    path = resolve_path(path_text)
    exists = path.is_file()
    return {
        "path": artifact_display_path(path),
        "pass": exists,
        "issues": [] if exists else [f"file_missing:{artifact_display_path(path)}"],
    }


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    issues: list[str] = []
    readiness, readiness_issues = read_json(args.readiness_summary)
    plan, plan_issues = read_json(args.rehearsal_plan)
    physical_gap, physical_gap_issues = read_json(args.physical_gap_summary)
    issues.extend(readiness_issues)
    issues.extend(plan_issues)
    issues.extend(physical_gap_issues)
    bool_issue(issues, bool(readiness.get("pass", False)), "readiness_summary_not_pass")
    bool_issue(issues, bool(readiness.get("hardware_transfer_ready", False)), "hardware_transfer_ready_false")
    bool_issue(issues, readiness.get("hardware_proven") is False, "readiness_should_not_claim_hardware_proven")
    bool_issue(issues, bool(plan.get("pass", False)), "rehearsal_plan_not_pass")
    bool_issue(issues, bool(plan.get("hardware_rehearsal_plan_ready", False)), "rehearsal_plan_not_ready")
    bool_issue(issues, plan.get("hardware_proven") is False, "plan_should_not_claim_hardware_proven")
    bool_issue(issues, bool(physical_gap.get("pass", False)), "physical_gap_summary_not_pass")
    bool_issue(
        issues,
        bool(physical_gap.get("physical_onboard_proof_ready", True)) is False,
        "physical_gap_should_not_claim_proof_ready",
    )

    command_checks = [command_check(command) for command in ("python", "powershell", "git")]
    script_checks = [
        file_check(path)
        for path in (
            "scripts/run_dashboard_service.ps1",
            "scripts/sync_runtime_workspace.ps1",
            "scripts/run_first_uat.ps1",
            "scripts/fetch_hardware_rehearsal_runner.py",
            "scripts/fetch_planner_route_replay_batch.py",
            "scripts/fetch_planner_seeded_generalization_gate.py",
            "scripts/fetch_physical_onboard_proof_gap.py",
            "scripts/fetch_physical_claim_from_run.py",
        )
    ]
    issues.extend(issue for check in command_checks for issue in check["issues"])
    issues.extend(issue for check in script_checks for issue in check["issues"])

    openai_api_key_present = bool(os.environ.get("OPENAI_API_KEY"))
    local_preflight_ready = not issues
    return {
        "generated_utc": utc_now(),
        "type": PREFLIGHT_KIND,
        "campaign_id": str(args.campaign_id),
        "pass": local_preflight_ready,
        "local_preflight_ready": local_preflight_ready,
        "hardware_connected": False,
        "hardware_proven": False,
        "promotion_evidence": False,
        "milestone_interpretation": (
            "robot_side_fetch_rehearsal_preflight_ready"
            if local_preflight_ready
            else "robot_side_fetch_rehearsal_preflight_incomplete"
        ),
        "issues": issues,
        "readiness_summary_path": artifact_display_path(args.readiness_summary),
        "rehearsal_plan_path": artifact_display_path(args.rehearsal_plan),
        "physical_gap_summary_path": artifact_display_path(args.physical_gap_summary),
        "dashboard_url": str(args.dashboard_url),
        "command_checks": command_checks,
        "script_checks": script_checks,
        "planner_provider": {
            "openai_api_key_present": openai_api_key_present,
            "execution_policy": "deterministic_fallback_allowed_when_provider_unavailable",
            "provider_absence_blocks_hardware_proof": False,
        },
        "required_robot_side_artifacts": [
            "control_preflight.json with /controller_manager/list_controllers evidence",
            "mission_verdict.json",
            "visual/raw_camera_browser.mp4",
            "visual/topdown_telemetry_browser.mp4",
            "visual/world_stream.mp4",
            "visual/keyframe_review_contact_sheet.png",
            "physical_claim_summary.json with robot_fidelity_orin, tensorrt_int8, execution_surface=physical_robot",
            "physical claim artifacts keyed as control_preflight, mission_verdict, raw_camera, topdown_telemetry, world_stream, keyframe_contact_sheet",
            "operator visual review notes for start/setup, pre-contact, first contact, mid-push, terminal arrival, final rest",
        ],
        "physical_claim_template": {
            "runtime_target": "robot_fidelity_orin",
            "inference_backend": "tensorrt_int8",
            "execution_surface": "physical_robot",
            "physical_robot_run": True,
            "onboard_tensorrt_execution": True,
            "physical_camera_evidence": True,
            "field_physics_notes": True,
            "artifacts": {
                "control_preflight": "<path-to-control_preflight.json>",
                "mission_verdict": "<path-to-mission_verdict.json>",
                "raw_camera": "<path-to-raw_camera_browser.mp4>",
                "topdown_telemetry": "<path-to-topdown_telemetry_browser.mp4>",
                "world_stream": "<path-to-world_stream.mp4>",
                "keyframe_contact_sheet": "<path-to-keyframe_review_contact_sheet.png>",
            },
        },
        "next_commands": [
            "powershell -ExecutionPolicy Bypass -File scripts/run_dashboard_service.ps1 -BindHost 0.0.0.0 -Port 8883",
            "powershell -ExecutionPolicy Bypass -File scripts/sync_runtime_workspace.ps1 -Distro Ubuntu-24.04 -WorkspacePath '~/ros2_ws' -SkipBuild -RosDistro kilted",
            f"python scripts/fetch_hardware_rehearsal_runner.py --campaign-id robot_side_fetch_rehearsal_seed{CURRENT_REHEARSAL_SEED}_runtime_stack_smoke_20260605 --step-id runtime_stack_smoke --execute --timeout-s 1800",
            f"python scripts/fetch_hardware_rehearsal_runner.py --campaign-id robot_side_fetch_rehearsal_seed{CURRENT_REHEARSAL_SEED}_saved_anchors_20260605 --step-id saved_anchor_one_run_fetch_rehearsal --execute --timeout-s 2400",
            f"python scripts/fetch_hardware_rehearsal_runner.py --campaign-id robot_side_fetch_rehearsal_seed{CURRENT_REHEARSAL_SEED}_mixed_all_routes_20260605 --step-id seed{CURRENT_REHEARSAL_SEED}_mixed_all_routes_rehearsal --execute --timeout-s 3600",
            "python scripts/fetch_physical_claim_from_run.py --campaign-id physical_claim_from_robot_side_rehearsal_20260605 --batch-summary <path-to-physical-batch-summary.json> --confirm-physical-robot --confirm-onboard-tensorrt --confirm-physical-camera --confirm-field-physics",
            "python scripts/fetch_physical_onboard_proof_gap.py --campaign-id physical_onboard_proof_gap_after_robot_side_rehearsal_20260605 --physical-claim-summary artifacts/session/physical_claim_from_robot_side_rehearsal_20260605/fetch_physical_claim_from_run/physical_claim_summary.json",
        ],
        "claim_boundary": (
            "This preflight proves the local run package is ready to attempt robot-side rehearsal. "
            "It does not prove onboard TensorRT execution, physical camera behavior, field physics, or hardware delivery."
        ),
    }


def artifact_link(path_text: str) -> str:
    return f"[artifact](/{path_text})" if str(path_text).startswith(("artifacts/", "runtime/", "docs/")) else str(path_text)


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Fetch Robot-Side Rehearsal Preflight",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- local_preflight_ready: `{summary.get('local_preflight_ready', False)}`",
        f"- hardware_connected: `{summary.get('hardware_connected', False)}`",
        f"- hardware_proven: `{summary.get('hardware_proven', False)}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        f"- issues: `{summary.get('issues', [])}`",
        f"- readiness_summary: {artifact_link(str(summary.get('readiness_summary_path', '')))}",
        f"- rehearsal_plan: {artifact_link(str(summary.get('rehearsal_plan_path', '')))}",
        f"- physical_gap_summary: {artifact_link(str(summary.get('physical_gap_summary_path', '')))}",
        f"- dashboard_url: {summary.get('dashboard_url', '')}",
        "",
        "## Command Checks",
        "",
    ]
    for row in summary.get("command_checks", []):
        if isinstance(row, dict):
            lines.append(f"- `{row.get('command', '')}` pass=`{row.get('pass', False)}` path=`{row.get('path', '')}`")
    lines.extend(["", "## Script Checks", ""])
    for row in summary.get("script_checks", []):
        if isinstance(row, dict):
            lines.append(f"- {artifact_link(str(row.get('path', '')))} pass=`{row.get('pass', False)}`")
    lines.extend(["", "## Required Robot-Side Artifacts", ""])
    for item in summary.get("required_robot_side_artifacts", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Physical Claim Template", ""])
    lines.append("```json")
    lines.append(json.dumps(summary.get("physical_claim_template", {}), indent=2, sort_keys=True))
    lines.append("```")
    lines.extend(["", "## Next Commands", ""])
    for command in summary.get("next_commands", []):
        lines.append(f"- `{command}`")
    lines.extend(["", "## Claim Boundary", "", str(summary.get("claim_boundary", ""))])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a robot-side fetch rehearsal preflight/runbook artifact.")
    parser.add_argument("--campaign-id", default=f"fetch_robot_side_rehearsal_preflight_{current_utc_stamp()}")
    parser.add_argument("--readiness-summary", default=DEFAULT_READINESS_SUMMARY)
    parser.add_argument("--rehearsal-plan", default=DEFAULT_REHEARSAL_PLAN)
    parser.add_argument("--physical-gap-summary", default=DEFAULT_PHYSICAL_GAP_SUMMARY)
    parser.add_argument("--dashboard-url", default=DEFAULT_DASHBOARD_URL)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / PREFLIGHT_KIND)
    summary = build_summary(args)
    summary_path = root / "robot_side_rehearsal_preflight_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["summary_path"] = artifact_display_path(summary_path)
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_ROBOT_SIDE_REHEARSAL_PREFLIGHT_SUMMARY={summary_path}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
