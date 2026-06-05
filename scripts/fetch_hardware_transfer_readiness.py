#!/usr/bin/env python3
"""Score planner-routed fetch readiness for hardware-transfer rehearsal."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
ANALYZER_KIND = "fetch_hardware_transfer_readiness"
DEFAULT_REGRESSION_MANIFEST = (
    "artifacts/session/analysis_planner_moonshot_regression_set_seed20260635_preflight_20260605/"
    "fetch_moonshot_regression_manifest/regression_summary.json"
)
DEFAULT_DASHBOARD_PLAN = "runtime/dashboard/fetch_plan_data.json"
DEFAULT_HARDWARE_CONTRACT = "docs/ROBOT_HARDWARE_CONTRACT_ORIN_NANO.md"
DEFAULT_HARDWARE_CONSTRAINTS = "docs/ROBOT_HARDWARE_CONSTRAINTS.md"
DEFAULT_TENSORRT_README = "runtime/tensorrt/README.md"


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


def artifact_display_path(path: str | Path) -> str:
    resolved = resolve_path(path)
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


def read_text(path_text: str | Path) -> tuple[str, list[str]]:
    path = resolve_path(path_text)
    if not path.is_file():
        return "", [f"missing_text:{artifact_display_path(path)}"]
    return path.read_text(encoding="utf-8", errors="replace"), []


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def bool_issue(issues: list[str], condition: bool, issue: str) -> None:
    if not condition:
        issues.append(issue)


def evaluate_regression_manifest(path_text: str, *, min_seeded_gates: int, min_live_missions: int) -> dict[str, Any]:
    payload, issues = read_json(path_text)
    totals = dict_value(payload.get("totals"))
    bool_issue(issues, bool(payload.get("pass", False)), "regression_manifest_not_pass")
    bool_issue(
        issues,
        str(payload.get("milestone_interpretation", "")) == "planner_routed_moonshot_regression_set_green",
        "regression_manifest_interpretation_mismatch",
    )
    bool_issue(issues, int_value(totals.get("issue_count")) == 0, "regression_manifest_issue_count_nonzero")
    bool_issue(issues, int_value(totals.get("seeded_gate_green_count")) >= min_seeded_gates, f"seeded_gate_green_count_below_{min_seeded_gates}")
    bool_issue(issues, int_value(totals.get("seeded_live_mission_pass_count")) >= min_live_missions, f"seeded_live_missions_below_{min_live_missions}")
    bool_issue(issues, int_value(totals.get("seeded_visual_package_pass_count")) >= min_live_missions, f"seeded_visual_packages_below_{min_live_missions}")
    bool_issue(issues, int_value(totals.get("control_preflight_green_count")) >= 1, "control_preflight_green_count_below_1")
    return {
        "path": artifact_display_path(path_text),
        "pass": not issues,
        "issues": issues,
        "totals": totals,
        "seeded_gate_count": int_value(totals.get("seeded_gate_count")),
        "seeded_live_mission_pass_count": int_value(totals.get("seeded_live_mission_pass_count")),
        "seeded_visual_package_pass_count": int_value(totals.get("seeded_visual_package_pass_count")),
        "control_preflight_green_count": int_value(totals.get("control_preflight_green_count")),
    }


def evaluate_dashboard_plan(path_text: str) -> dict[str, Any]:
    payload, issues = read_json(path_text)
    uat = dict_value(payload.get("uat_review_bundle"))
    samples = [row for row in list_value(uat.get("route_samples")) if isinstance(row, dict)]
    status_label = str(payload.get("status_label", ""))
    status_ready = (
        status_label.startswith("Promotion green")
        or status_label.startswith("Hardware rehearsal green")
        or status_label.startswith("Mixed all-routes seed 20260643")
        or status_label.startswith("Robot-side seed 20260643")
    )
    bool_issue(issues, status_ready, "dashboard_status_not_hardware_ready")
    status_detail = str(payload.get("status_detail", ""))
    bool_issue(
        issues,
        "20260643" in status_detail or "20260635" in status_detail,
        "dashboard_missing_current_seed_status",
    )
    bool_issue(issues, len(samples) >= 6, "dashboard_uat_samples_below_6")
    for index, sample in enumerate(samples):
        label = str(sample.get("label") or f"sample{index}")
        for key in ("video_url", "topdown_url", "world_url", "contact_sheet_url"):
            bool_issue(issues, str(sample.get(key, "")).startswith("/artifacts/session/"), f"dashboard_{label}_{key}_missing")
    return {
        "path": artifact_display_path(path_text),
        "pass": not issues,
        "issues": issues,
        "status_label": status_label,
        "uat_sample_count": len(samples),
        "first_video_url": str(samples[0].get("video_url", "")) if samples else "",
    }


def evaluate_text_contract(path_text: str, required_terms: list[str]) -> dict[str, Any]:
    text, issues = read_text(path_text)
    lower_text = text.lower()
    for term in required_terms:
        bool_issue(issues, term.lower() in lower_text, f"missing_required_term:{term}")
    return {
        "path": artifact_display_path(path_text),
        "pass": not issues,
        "issues": issues,
        "required_terms": required_terms,
    }


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    regression = evaluate_regression_manifest(
        str(args.regression_manifest),
        min_seeded_gates=int(args.min_seeded_gates),
        min_live_missions=int(args.min_live_missions),
    )
    dashboard = evaluate_dashboard_plan(str(args.dashboard_plan))
    hardware_contract = evaluate_text_contract(
        str(args.hardware_contract),
        ["Jetson Orin Nano 8GB", "runtime_target=robot_fidelity_orin", "inference_backend=tensorrt_int8"],
    )
    hardware_constraints = evaluate_text_contract(
        str(args.hardware_constraints),
        ["Jetson Orin Nano 8GB", "cmd_vel", "Controller update rate", "100 Hz"],
    )
    tensorrt = evaluate_text_contract(
        str(args.tensorrt_readme),
        ["tensorrt_int8", "build INT8 engine", "RuntimeTarget robot_fidelity_orin"],
    )
    sections = {
        "regression_manifest": regression,
        "dashboard_plan": dashboard,
        "hardware_contract": hardware_contract,
        "hardware_constraints": hardware_constraints,
        "tensorrt_runtime": tensorrt,
    }
    issue_count = sum(len(dict_value(section).get("issues", [])) for section in sections.values())
    ready = all(bool(dict_value(section).get("pass", False)) for section in sections.values())
    return {
        "generated_utc": utc_now(),
        "type": ANALYZER_KIND,
        "campaign_id": str(args.campaign_id or ""),
        "pass": ready,
        "promotion_evidence": False,
        "hardware_proven": False,
        "hardware_transfer_ready": ready,
        "readiness_level": "ready_for_hardware_rehearsal" if ready else "hardware_rehearsal_blocked",
        "milestone_interpretation": (
            "planner_routed_fetch_hardware_rehearsal_ready"
            if ready
            else "planner_routed_fetch_hardware_rehearsal_incomplete"
        ),
        "issue_count": issue_count,
        **sections,
        "open_hardware_gates": [
            "robot_side_live_rehearsal_not_run",
            "onboard_tensorrt_execution_not_proven",
            "physical_camera_visual_package_not_recorded",
            "field_physics_not_proven",
        ],
        "required_next_rehearsal": {
            "runtime_target": "robot_fidelity_orin",
            "inference_backend": "tensorrt_int8",
            "required_artifacts": [
                "control_preflight.json",
                "mission_verdict.json",
                "raw_camera_browser.mp4",
                "topdown_telemetry_browser.mp4",
                "world_stream.mp4",
                "keyframe_review_contact_sheet.png",
            ],
            "minimum_live_contract": "saved anchors one-run plus one seed20260643 mixed all-routes sample before hardware promotion discussion",
        },
    }


def artifact_link(path_text: str) -> str:
    return f"[artifact](/{path_text})" if str(path_text).startswith(("artifacts/", "runtime/", "docs/")) else str(path_text)


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Fetch Hardware Transfer Readiness",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- hardware_transfer_ready: `{summary.get('hardware_transfer_ready', False)}`",
        f"- hardware_proven: `{summary.get('hardware_proven', False)}`",
        f"- readiness_level: `{summary.get('readiness_level', '')}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        f"- issue_count: `{summary.get('issue_count', 0)}`",
        "",
        "## Evidence Checks",
        "",
    ]
    for key in ("regression_manifest", "dashboard_plan", "hardware_contract", "hardware_constraints", "tensorrt_runtime"):
        section = dict_value(summary.get(key))
        lines.append(
            f"- `{key}` pass=`{section.get('pass', False)}` issues=`{section.get('issues', [])}` "
            f"{artifact_link(str(section.get('path', '') or ''))}"
        )
    rehearsal = dict_value(summary.get("required_next_rehearsal"))
    lines.extend(
        [
            "",
            "## Open Hardware Gates",
            "",
        ]
    )
    for gate in list_value(summary.get("open_hardware_gates")):
        lines.append(f"- `{gate}`")
    lines.extend(
        [
            "",
            "## Required Next Rehearsal",
            "",
            f"- runtime_target: `{rehearsal.get('runtime_target', '')}`",
            f"- inference_backend: `{rehearsal.get('inference_backend', '')}`",
            f"- minimum_live_contract: `{rehearsal.get('minimum_live_contract', '')}`",
            f"- required_artifacts: `{rehearsal.get('required_artifacts', [])}`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score planner-routed fetch hardware-transfer readiness.")
    parser.add_argument("--campaign-id", default=f"fetch_hardware_transfer_readiness_{current_utc_stamp()}")
    parser.add_argument("--regression-manifest", default=DEFAULT_REGRESSION_MANIFEST)
    parser.add_argument("--dashboard-plan", default=DEFAULT_DASHBOARD_PLAN)
    parser.add_argument("--hardware-contract", default=DEFAULT_HARDWARE_CONTRACT)
    parser.add_argument("--hardware-constraints", default=DEFAULT_HARDWARE_CONSTRAINTS)
    parser.add_argument("--tensorrt-readme", default=DEFAULT_TENSORRT_README)
    parser.add_argument("--min-seeded-gates", type=int, default=8)
    parser.add_argument("--min-live-missions", type=int, default=48)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / ANALYZER_KIND)
    summary = build_summary(args)
    summary_path = root / "hardware_transfer_readiness_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["summary_path"] = artifact_display_path(summary_path)
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_HARDWARE_TRANSFER_READINESS_SUMMARY={summary_path}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
