#!/usr/bin/env python3
"""Create the planner-routed fetch hardware rehearsal plan artifact."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
PLAN_KIND = "fetch_hardware_rehearsal_plan"
DEFAULT_READINESS_SUMMARY = (
    "artifacts/session/hardware_transfer_readiness_seed20260648_dashboard_20260605/"
    "fetch_hardware_transfer_readiness/hardware_transfer_readiness_summary.json"
)
DEFAULT_SAVED_ANCHOR_GATE = (
    "artifacts/session/dev_planner_saved_anchor_handoff_gate_zero_numeric_fix_20260604/"
    "fetch_planner_handoff_gate/gate_summary.json"
)
DEFAULT_SEEDED_GATE = (
    "artifacts/session/live_planner_seeded_generalization_gate_seed20260648_breadth_100x3_20260605_planner/"
    "fetch_planner_handoff_gate/gate_summary.json"
)
CURRENT_REHEARSAL_SEED = "20260648"
DEFAULT_DASHBOARD_URL = "http://127.0.0.1:8883"


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


def bool_issue(issues: list[str], condition: bool, issue: str) -> None:
    if not condition:
        issues.append(issue)


def command_text(parts: list[str]) -> str:
    return " ".join(parts)


def build_rehearsal_steps(args: argparse.Namespace) -> list[dict[str, Any]]:
    dashboard_url = str(args.dashboard_url)
    return [
        {
            "id": "runtime_stack_smoke",
            "purpose": "Confirm the robot_fidelity_orin/tensorrt_int8 stack and visual capture path before fetch scoring.",
            "owner": "operator",
            "promotion_evidence": False,
            "command": command_text(
                [
                    "powershell",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "scripts/run_first_uat.ps1",
                    "-ExecutionLane",
                    "container_kilted",
                    "-Distro",
                    "Ubuntu-24.04",
                    "-RuntimeTarget",
                    "robot_fidelity_orin",
                    "-InferenceBackend",
                    "tensorrt_int8",
                    "-IncludeVisual",
                    "true",
                ]
            ),
            "required_artifacts": [
                "session:readiness_report.json",
                "session:visual/operator_status.json",
                "readiness_path:artifacts.coordinate_summary",
                "readiness_path:artifacts.milestone_1_evidence_dir:screenshots/d415_color.png",
                "readiness_path:artifacts.milestone_1_evidence_dir:screenshots/yolo_debug.png",
            ],
        },
        {
            "id": "saved_anchor_one_run_fetch_rehearsal",
            "purpose": "Run zero, left05, and right05 through the planner-routed fetch stack on the hardware rehearsal surface.",
            "owner": "operator",
            "promotion_evidence": False,
            "command": command_text(
                [
                    "python",
                    "scripts/fetch_planner_route_replay_batch.py",
                    "--campaign-id",
                    str(args.saved_anchor_campaign_id),
                    "--gate-summary",
                    artifact_display_path(args.saved_anchor_gate),
                    "--max-per-route",
                    "3",
                    "--dashboard-url",
                    dashboard_url,
                    "--fresh-dashboard-session-per-run",
                    "--allow-operator-view-degraded",
                    "--stop-on-fail",
                ]
            ),
            "required_artifacts": [
                "control_preflight.json",
                "mission_verdict.json",
                "visual/raw_camera_browser.mp4",
                "visual/topdown_telemetry_browser.mp4",
                "visual/world_stream.mp4",
                "visual/keyframe_review_contact_sheet.png",
            ],
        },
        {
            "id": f"seed{CURRENT_REHEARSAL_SEED}_mixed_all_routes_rehearsal",
            "purpose": (
                "Repeat the current broad mixed all-routes seed across fetch-ready, Nav2-first, "
                "recovery/re-aim, scan/perceive, and no-go route owners."
            ),
            "owner": "operator",
            "promotion_evidence": False,
            "command": command_text(
                [
                    "python",
                    "scripts/fetch_planner_route_replay_batch.py",
                    "--campaign-id",
                    str(args.seeded_campaign_id),
                    "--gate-summary",
                    artifact_display_path(args.seeded_gate),
                    "--route",
                    "fetch_ready_local",
                    "--route",
                    "nav2_reposition_first",
                    "--route",
                    "recovery_or_reaim",
                    "--route",
                    "scan_or_perceive_first",
                    "--route",
                    "ambiguous_or_unsafe_no_go",
                    "--quality-order",
                    "roughest",
                    "--max-per-route",
                    "3",
                    "--dashboard-url",
                    dashboard_url,
                    "--fresh-dashboard-session-per-run",
                    "--allow-operator-view-degraded",
                    "--stop-on-fail",
                ]
            ),
            "required_artifacts": [
                "fetch_planner_handoff_gate/gate_summary.json",
                "fetch_planner_route_replay_batch/batch_summary.json",
                "fetch_planner_route_uat_analyzer/route_uat_summary.json",
                "visual/raw_camera_browser.mp4",
                "visual/topdown_telemetry_browser.mp4",
                "visual/keyframe_review_contact_sheet.png",
            ],
        },
    ]


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    readiness, issues = read_json(args.readiness_summary)
    bool_issue(issues, bool(readiness.get("pass", False)), "readiness_summary_not_pass")
    bool_issue(issues, bool(readiness.get("hardware_transfer_ready", False)), "hardware_transfer_ready_false")
    bool_issue(issues, readiness.get("hardware_proven") is False, "readiness_should_not_claim_hardware_proven")
    bool_issue(
        issues,
        str(readiness.get("milestone_interpretation", "")) == "planner_routed_fetch_hardware_rehearsal_ready",
        "readiness_interpretation_mismatch",
    )
    for path_text, label in (
        (args.saved_anchor_gate, "saved_anchor_gate_missing"),
        (args.seeded_gate, "seeded_gate_missing"),
    ):
        bool_issue(issues, resolve_path(path_text).is_file(), label)
    steps = build_rehearsal_steps(args)
    return {
        "generated_utc": utc_now(),
        "type": PLAN_KIND,
        "campaign_id": str(args.campaign_id),
        "pass": not issues,
        "promotion_evidence": False,
        "hardware_proven": False,
        "hardware_rehearsal_plan_ready": not issues,
        "milestone_interpretation": (
            "planner_routed_fetch_hardware_rehearsal_plan_ready"
            if not issues
            else "planner_routed_fetch_hardware_rehearsal_plan_incomplete"
        ),
        "issues": issues,
        "readiness_summary_path": artifact_display_path(args.readiness_summary),
        "runtime_contract": {
            "runtime_target": "robot_fidelity_orin",
            "inference_backend": "tensorrt_int8",
            "dashboard_url": str(args.dashboard_url),
            "visual_review_required": True,
            "visual_review_phases": [
                "start_setup",
                "pre_contact",
                "first_contact",
                "mid_push_or_coast",
                "terminal_arrival",
                "final_rest",
            ],
        },
        "planned_steps": steps,
        "rehearsal_pass_contract": {
            "saved_anchors": "zero/left05/right05 one-run pass with browser-watchable onboard/context video",
            "seeded_mixed_route": (
                f"seed{CURRENT_REHEARSAL_SEED} mixed all-routes sample pass across fetch_ready_local, "
                "nav2_reposition_first, recovery_or_reaim, scan_or_perceive_first, "
                "and ambiguous_or_unsafe_no_go"
            ),
            "blocked_claims_until_recorded": [
                "robot_side_live_rehearsal",
                "onboard_tensorrt_execution",
                "physical_camera_visual_package",
                "field_physics",
            ],
        },
        "source_artifacts": {
            "readiness_summary": artifact_display_path(args.readiness_summary),
            "saved_anchor_gate": artifact_display_path(args.saved_anchor_gate),
            "seeded_gate": artifact_display_path(args.seeded_gate),
        },
    }


def artifact_link(path_text: str) -> str:
    return f"[artifact](/{path_text})" if str(path_text).startswith(("artifacts/", "runtime/", "docs/")) else str(path_text)


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Fetch Hardware Rehearsal Plan",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- hardware_rehearsal_plan_ready: `{summary.get('hardware_rehearsal_plan_ready', False)}`",
        f"- hardware_proven: `{summary.get('hardware_proven', False)}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        f"- issues: `{summary.get('issues', [])}`",
        f"- readiness_summary: {artifact_link(str(summary.get('readiness_summary_path', '')))}",
        "",
        "## Runtime Contract",
        "",
    ]
    runtime = summary.get("runtime_contract", {})
    if isinstance(runtime, dict):
        for key in ("runtime_target", "inference_backend", "dashboard_url", "visual_review_required"):
            lines.append(f"- {key}: `{runtime.get(key, '')}`")
        lines.append(f"- visual_review_phases: `{runtime.get('visual_review_phases', [])}`")
    lines.extend(["", "## Planned Steps", ""])
    for step in summary.get("planned_steps", []):
        if not isinstance(step, dict):
            continue
        lines.extend(
            [
                f"### {step.get('id', '')}",
                "",
                f"- purpose: {step.get('purpose', '')}",
                f"- promotion_evidence: `{step.get('promotion_evidence', False)}`",
                f"- command: `{step.get('command', '')}`",
                f"- required_artifacts: `{step.get('required_artifacts', [])}`",
                "",
            ]
        )
    contract = summary.get("rehearsal_pass_contract", {})
    if isinstance(contract, dict):
        lines.extend(["## Pass Contract", ""])
        lines.append(f"- saved_anchors: `{contract.get('saved_anchors', '')}`")
        lines.append(f"- seeded_mixed_route: `{contract.get('seeded_mixed_route', '')}`")
        lines.append(f"- blocked_claims_until_recorded: `{contract.get('blocked_claims_until_recorded', [])}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a planner-routed fetch hardware rehearsal plan artifact.")
    parser.add_argument("--campaign-id", default=f"fetch_hardware_rehearsal_plan_{current_utc_stamp()}")
    parser.add_argument("--readiness-summary", default=DEFAULT_READINESS_SUMMARY)
    parser.add_argument("--saved-anchor-gate", default=DEFAULT_SAVED_ANCHOR_GATE)
    parser.add_argument("--seeded-gate", default=DEFAULT_SEEDED_GATE)
    parser.add_argument("--dashboard-url", default=DEFAULT_DASHBOARD_URL)
    parser.add_argument("--saved-anchor-campaign-id", default="hardware_rehearsal_saved_anchors_20260605")
    parser.add_argument("--seeded-campaign-id", default=f"hardware_rehearsal_seed{CURRENT_REHEARSAL_SEED}_mixed_all_routes_20260605")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / PLAN_KIND)
    summary = build_summary(args)
    summary_path = root / "hardware_rehearsal_plan_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["summary_path"] = artifact_display_path(summary_path)
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_HARDWARE_REHEARSAL_PLAN_SUMMARY={summary_path}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
