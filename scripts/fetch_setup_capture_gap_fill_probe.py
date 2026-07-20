#!/usr/bin/env python3
"""Run or plan a right05 setup/capture gap-fill comparison probe."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import calibrated_golf_fetch_gate as fetch_gate
import fetch_capture_entry_diagnostic_analyzer as capture_diag
import fetch_saved_anchor_setup_contact_audit as setup_audit
import fetch_stage_owner_comparison as stage_compare
import fetch_visual_uat_package as visual_package
from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import read_json
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json


ANALYZER_KIND = "fetch_setup_capture_gap_fill_probe"
DEFAULT_FAMILIES = (
    "ai_push_coast_servo_v1",
    "nav2_followpath_corridor_push_v1",
    "object_centric_gather_policy_v1",
)
DEFAULT_LAYOUT_JSON = fetch_gate.OFF_AXIS_LAYOUTS["right05"]
DEFAULT_PLANNER_GATE_SUMMARY = (
    "artifacts/session/live_planner_handoff_mixed_fetch_20260601/"
    "fetch_planner_handoff_gate/gate_summary.json"
)
DEFAULT_OBJECT_CENTRIC_GATE_SUMMARY = (
    "artifacts/session/live_calibrated_golf_fetch_uat_readiness_rerun_20260527/"
    "calibrated_golf_fetch_gate/gate_summary.json"
)
DEFAULT_NAV2_CORRIDOR_SUMMARY = (
    "artifacts/session/live_nav2_corridor_push_full_saved_layout_20260529/"
    "calibrated_fetch_architecture_revisit/architecture_revisit_summary.json"
)
DEFAULT_CORRECTED_DIRECT_RIGHT05 = (
    "artifacts/session/live_calibrated_ball_right05_one_run_20260601/"
    "gather_mission_repeatability/campaign_run_summary.json"
)


@dataclass(frozen=True)
class ProbeSpec:
    family: str
    campaign_id: str
    command: list[str]


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare setup/capture behavior on the right05 saved layout.")
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--dashboard-url", default=fetch_gate.DEFAULT_DASHBOARD_URL)
    parser.add_argument("--dashboard-base-url", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--family", action="append", choices=DEFAULT_FAMILIES, default=[])
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--layout-json", default=DEFAULT_LAYOUT_JSON)
    parser.add_argument("--fetch-delivery-radius-m", type=float, default=fetch_gate.DEFAULT_FETCH_TARGET["radius_m"])
    parser.add_argument("--world-file", default=fetch_gate.DEFAULT_WORLD_FILE)
    parser.add_argument("--surface-profile", default=fetch_gate.DEFAULT_SURFACE_PROFILE)
    parser.add_argument("--timeout-s", type=float, default=90.0)
    parser.add_argument("--scenario-timeout-s", type=float, default=300.0)
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--planner-gate-summary", default=DEFAULT_PLANNER_GATE_SUMMARY)
    parser.add_argument("--object-centric-gate-summary", default=DEFAULT_OBJECT_CENTRIC_GATE_SUMMARY)
    parser.add_argument("--nav2-corridor-summary", default=DEFAULT_NAV2_CORRIDOR_SUMMARY)
    parser.add_argument("--corrected-direct-summary", action="append", default=[DEFAULT_CORRECTED_DIRECT_RIGHT05])
    parser.add_argument("--skip-visual-package", action="store_true")
    return parser.parse_args()


def _output_root(campaign_id: str) -> Path:
    return REPO_ROOT / "artifacts" / "session" / campaign_id / ANALYZER_KIND


def _resolve_path(raw_path: str | Path) -> Path:
    path = Path(str(raw_path or "").strip())
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


def _artifact_display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _family_slug(family: str) -> str:
    return family.replace("_v1", "").replace("_", "-")


def selected_families(args: argparse.Namespace) -> list[str]:
    families = list(args.family or DEFAULT_FAMILIES)
    seen: set[str] = set()
    unique: list[str] = []
    for family in families:
        if family not in seen:
            seen.add(family)
            unique.append(family)
    return unique


def build_probe_specs(args: argparse.Namespace, campaign_id: str) -> list[ProbeSpec]:
    specs: list[ProbeSpec] = []
    for family in selected_families(args):
        child_campaign_id = f"{campaign_id}_{_family_slug(family)}_right05"
        command = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "gather_mission_repeatability_runner.py"),
            "--dashboard-url",
            args.dashboard_url,
            "--execution-mode",
            "direct",
            "--scenario-id",
            "corral_single_ball_place",
            "--scenario-label",
            f"Setup/Capture Gap Fill {family}",
            "--mission-objective",
            "fetch_to_pose",
            "--fetch-gate-mode",
            "full_mission",
            "--fetch-target-x",
            f"{float(fetch_gate.DEFAULT_FETCH_TARGET['x']):.6f}",
            "--fetch-target-y",
            f"{float(fetch_gate.DEFAULT_FETCH_TARGET['y']):.6f}",
            "--fetch-target-z",
            f"{float(fetch_gate.DEFAULT_FETCH_TARGET['z']):.6f}",
            "--fetch-delivery-radius-m",
            f"{float(args.fetch_delivery_radius_m):.6f}",
            "--runs",
            str(max(int(args.runs), 1)),
            "--campaign-id",
            child_campaign_id,
            "--timeout-s",
            f"{float(args.timeout_s):.3f}",
            "--scenario-timeout-s",
            f"{float(args.scenario_timeout_s):.3f}",
            "--provider",
            args.provider,
            "--world-file",
            args.world_file,
            "--surface-profile",
            args.surface_profile,
            "--promotion-gate-mode",
            "pass_only",
            "--max-retries-per-target",
            "0",
            "--target-model-sdf",
            fetch_gate.DEFAULT_BALL_SDF,
            "--zone-model-sdf",
            fetch_gate.DEFAULT_ZONE_SDF,
            "--artifact-kind",
            "gather_mission_setup_capture_gap_fill",
            "--target-layout-json",
            args.layout_json,
            "--gather-control-family",
            family,
            "--ai-push-coast-mode",
            "shadow",
        ]
        specs.append(ProbeSpec(family=family, campaign_id=child_campaign_id, command=command))
    return specs


def _summary_path_for_campaign(child_campaign_id: str) -> Path:
    return REPO_ROOT / "artifacts" / "session" / child_campaign_id / "gather_mission_repeatability" / "campaign_run_summary.json"


def _run_command(command: list[str], log_path: Path) -> int:
    ensure_dir(log_path.parent)
    proc = subprocess.run(command, cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    log_path.write_text(output, encoding="utf-8")
    return int(proc.returncode)


def _capture_diagnostic(campaign_id: str, summary_paths: list[Path]) -> dict[str, Any]:
    if not summary_paths:
        return {}
    summary = capture_diag.analyze([str(path) for path in summary_paths])
    summary["campaign_id"] = campaign_id
    root = _output_root(campaign_id) / "capture_entry_diagnostic"
    ensure_dir(root)
    summary_path = root / "diagnostic_summary.json"
    scorecard_path = root / "scorecard.md"
    write_json(summary_path, summary)
    capture_diag.write_scorecard(summary, scorecard_path)
    summary["summary_path"] = _artifact_display_path(summary_path)
    summary["scorecard_path"] = _artifact_display_path(scorecard_path)
    return summary


def _setup_audit(campaign_id: str, summary_paths: list[Path]) -> dict[str, Any]:
    if not summary_paths:
        return {}
    summary = setup_audit.analyze([str(path) for path in summary_paths])
    summary["campaign_id"] = campaign_id
    root = _output_root(campaign_id) / "saved_anchor_setup_contact_audit"
    ensure_dir(root)
    summary_path = root / "audit_summary.json"
    scorecard_path = root / "scorecard.md"
    write_json(summary_path, summary)
    setup_audit.write_scorecard(summary, scorecard_path)
    summary["summary_path"] = _artifact_display_path(summary_path)
    summary["scorecard_path"] = _artifact_display_path(scorecard_path)
    return summary


def _stage_comparison(args: argparse.Namespace, campaign_id: str, summary_paths: list[Path], audit_summary_path: str) -> dict[str, Any]:
    if not summary_paths:
        return {}
    summary = stage_compare.summarize_comparison(
        campaign_id=f"{campaign_id}_stage_owner_refresh",
        dashboard_base_url=_clean_text(args.dashboard_base_url),
        planner_gate_summary=_clean_text(args.planner_gate_summary),
        current_saved_anchor_summaries=[str(path) for path in summary_paths],
        current_stage_audit=audit_summary_path,
        object_centric_gate_summary=_clean_text(args.object_centric_gate_summary),
        nav2_corridor_summary=_clean_text(args.nav2_corridor_summary),
        corrected_direct_summaries=list(args.corrected_direct_summary or []),
    )
    return {
        "campaign_id": summary.get("campaign_id", ""),
        "recommended_next_action": summary.get("recommended_next_action", {}),
        "scorecard_path": _artifact_display_path(
            REPO_ROOT
            / "artifacts"
            / "session"
            / str(summary.get("campaign_id", ""))
            / stage_compare.ANALYZER_KIND
            / "scorecard.md"
        ),
        "summary_path": _artifact_display_path(
            REPO_ROOT
            / "artifacts"
            / "session"
            / str(summary.get("campaign_id", ""))
            / stage_compare.ANALYZER_KIND
            / "stage_owner_summary.json"
        ),
    }


def _visual_dirs_for_summaries(summary_paths: list[Path]) -> list[str]:
    visual_dirs: list[str] = []
    for summary_path in summary_paths:
        payload = read_json(summary_path)
        for run in _list(payload.get("runs")):
            if not isinstance(run, dict):
                continue
            session_id = _clean_text(run.get("session_id") or _dict(run.get("mission_verdict")).get("session_id"))
            if session_id:
                visual_dir = REPO_ROOT / "artifacts" / "session" / session_id / "visual"
                if visual_dir.is_dir():
                    visual_dirs.append(str(visual_dir))
    return visual_dirs


def _build_visual_package(args: argparse.Namespace, campaign_id: str, summary_paths: list[Path], audit_summary_path: str) -> dict[str, Any]:
    if args.skip_visual_package or not summary_paths:
        return {}
    visual_dirs = _visual_dirs_for_summaries(summary_paths)
    if not visual_dirs:
        return {}
    package_args = argparse.Namespace(
        campaign_id=f"{campaign_id}_visual_uat",
        planner_summary=[_clean_text(args.planner_gate_summary)] if _clean_text(args.planner_gate_summary) else [],
        seeded_evidence_summary=[],
        stage_quality_summary=[audit_summary_path] if audit_summary_path else [],
        mission_summary=[str(path) for path in summary_paths],
        visual_dir=visual_dirs,
    )
    summary = visual_package.build_summary(package_args)
    root = REPO_ROOT / "artifacts" / "session" / str(package_args.campaign_id) / visual_package.PACKAGE_KIND
    ensure_dir(root)
    summary_path = root / "visual_uat_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["scorecard_path"] = _artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    visual_package.write_scorecard(scorecard_path, summary)
    return {
        "campaign_id": package_args.campaign_id,
        "pass": bool(summary.get("pass", False)),
        "warnings": list(summary.get("warnings") or []),
        "scorecard_path": _artifact_display_path(scorecard_path),
        "summary_path": _artifact_display_path(summary_path),
    }


def _child_summary(summary_path: Path, family: str, return_code: int, dry_run: bool) -> dict[str, Any]:
    payload = read_json(summary_path) if summary_path.is_file() else {}
    runs = _list(payload.get("runs"))
    first_run = _dict(runs[0]) if runs else {}
    return {
        "family": family,
        "dry_run": dry_run,
        "return_code": return_code,
        "summary_path": _artifact_display_path(summary_path) if summary_path.is_file() else "",
        "summary_exists": summary_path.is_file(),
        "pass": bool(payload.get("promotion_gate_pass", False) or payload.get("fetch_to_pose_pass_count", 0)),
        "fetch_to_pose_pass_count": int(payload.get("fetch_to_pose_pass_count", 0) or 0),
        "fetch_to_pose_fail_count": int(payload.get("fetch_to_pose_fail_count", 0) or 0),
        "failure_reasons": list(payload.get("fetch_to_pose_failure_reasons") or []),
        "first_run_capture_entry_reached": bool(first_run.get("capture_entry_reached", False)),
        "first_run_failure_reason": _clean_text(first_run.get("fetch_to_pose_failure_reason") or first_run.get("approach_failure_reason")),
        "first_run_closest_approach_m": _dict(first_run.get("shot_outcome")).get("closest_approach_distance_m"),
    }


def _decision(children: list[dict[str, Any]], capture_summary: dict[str, Any]) -> dict[str, str]:
    if not children or all(child.get("dry_run") for child in children):
        return {"action": "dry_run_ready", "rationale": "commands were built without running live evidence"}
    if not any(child.get("summary_exists", False) for child in children):
        return {
            "action": "live_probe_infrastructure_blocker",
            "rationale": "live commands returned without readable repeatability summaries",
        }
    by_family = {str(child.get("family")): child for child in children}
    current = by_family.get("ai_push_coast_servo_v1", {})
    current_pass = bool(current.get("pass", False))
    candidate_passes = [
        family
        for family in ("nav2_followpath_corridor_push_v1", "object_centric_gather_policy_v1")
        if bool(by_family.get(family, {}).get("pass", False))
    ]
    capture_pass_count = int(capture_summary.get("capture_entry_pass_count", 0) or 0)
    blocker_count = int(capture_summary.get("capture_entry_blocker_count", 0) or 0)
    if current_pass:
        return {
            "action": "rerun_saved_anchor_one_run_matrix",
            "rationale": "current staged right05 passed; treat prior failure as watchlist until repeatability says otherwise",
        }
    if candidate_passes:
        return {
            "action": f"port_setup_capture_behavior_from_{candidate_passes[0]}",
            "rationale": "current staged right05 failed while a comparison family passed",
        }
    if capture_pass_count > 0 and blocker_count == 0:
        return {
            "action": "route_next_work_to_first_contact_or_push_coast",
            "rationale": "capture-entry is no longer the primary blocker",
        }
    return {
        "action": "repair_capture_entry_geometry_before_contact",
        "rationale": "all live comparison families are blocked or missing before clean capture-entry proof",
    }


def _write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    decision = _dict(summary.get("decision"))
    lines = [
        "# Setup/Capture Gap-Fill Probe",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- dry_run: `{bool(summary.get('dry_run', False))}`",
        f"- decision: `{decision.get('action', '')}`",
        f"- rationale: {decision.get('rationale', '')}",
        "",
        "## Families",
        "",
        "| family | return | pass | capture-entry | closest | reasons | summary |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for child in _list(summary.get("children")):
        if not isinstance(child, dict):
            continue
        lines.append(
            "| "
            f"`{child.get('family', '')}` | "
            f"`{child.get('return_code', '')}` | "
            f"`{bool(child.get('pass', False))}` | "
            f"`{bool(child.get('first_run_capture_entry_reached', False))}` | "
            f"`{child.get('first_run_closest_approach_m', '')}` | "
            f"{', '.join(str(reason) for reason in _list(child.get('failure_reasons'))) or child.get('first_run_failure_reason', '')} | "
            f"{child.get('summary_path', '')} |"
        )
    lines.extend(["", "## Commands", ""])
    for spec in _list(summary.get("specs")):
        if not isinstance(spec, dict):
            continue
        lines.append(f"- `{spec.get('family', '')}`:")
        lines.append("")
        lines.append("```powershell")
        lines.append(" ".join(str(part) for part in _list(spec.get("command"))))
        lines.append("```")
        lines.append("")
    for section in ("capture_entry_diagnostic", "setup_contact_audit", "stage_owner_refresh", "visual_uat_package"):
        payload = _dict(summary.get(section))
        if payload:
            lines.extend([f"## {section.replace('_', ' ').title()}", ""])
            for key in ("summary_path", "scorecard_path"):
                if payload.get(key):
                    lines.append(f"- {key}: `{payload.get(key)}`")
            if payload.get("recommended_next_action"):
                lines.append(f"- recommended_next_action: `{payload.get('recommended_next_action')}`")
            if payload.get("warnings"):
                lines.append(f"- warnings: `{', '.join(str(item) for item in _list(payload.get('warnings')))}`")
            lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    campaign_id = _clean_text(args.campaign_id) or f"live_fetch_setup_capture_gap_fill_{current_utc_stamp()}"
    root = _output_root(campaign_id)
    logs_root = ensure_dir(root / "logs")
    specs = build_probe_specs(args, campaign_id)
    children: list[dict[str, Any]] = []
    summary_paths: list[Path] = []
    for spec in specs:
        return_code = 0
        if not args.dry_run:
            return_code = _run_command(spec.command, logs_root / f"{_family_slug(spec.family)}.log")
        summary_path = _summary_path_for_campaign(spec.campaign_id)
        child = _child_summary(summary_path, spec.family, return_code, bool(args.dry_run))
        children.append(child)
        if summary_path.is_file():
            summary_paths.append(summary_path)
    capture_summary = {} if args.dry_run else _capture_diagnostic(campaign_id, summary_paths)
    audit_summary = {} if args.dry_run else _setup_audit(campaign_id, summary_paths)
    audit_summary_path = _clean_text(audit_summary.get("summary_path"))
    stage_refresh = {} if args.dry_run else _stage_comparison(args, campaign_id, summary_paths, audit_summary_path)
    visual_summary = {} if args.dry_run else _build_visual_package(args, campaign_id, summary_paths, audit_summary_path)
    summary = {
        "type": ANALYZER_KIND,
        "campaign_id": campaign_id,
        "generated_utc": utc_now(),
        "dry_run": bool(args.dry_run),
        "layout_json": _clean_text(args.layout_json),
        "families": selected_families(args),
        "specs": [
            {"family": spec.family, "campaign_id": spec.campaign_id, "command": spec.command}
            for spec in specs
        ],
        "children": children,
        "capture_entry_diagnostic": capture_summary,
        "setup_contact_audit": audit_summary,
        "stage_owner_refresh": stage_refresh,
        "visual_uat_package": visual_summary,
    }
    summary["decision"] = _decision(children, capture_summary)
    ensure_dir(root)
    summary_path = root / "gap_fill_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["summary_path"] = _artifact_display_path(summary_path)
    summary["scorecard_path"] = _artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    _write_scorecard(scorecard_path, summary)
    return summary


def main() -> int:
    args = parse_args()
    summary = run_probe(args)
    print(f"SETUP_CAPTURE_GAP_FILL_SUMMARY={REPO_ROOT / summary['summary_path']}")
    print(f"SETUP_CAPTURE_GAP_FILL_SCORECARD={REPO_ROOT / summary['scorecard_path']}")
    print(f"DECISION={_dict(summary.get('decision')).get('action', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
