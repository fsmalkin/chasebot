#!/usr/bin/env python3
"""Audit the remaining physical/onboard proof gap for generalized fetch."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
ANALYZER_KIND = "fetch_physical_onboard_proof_gap"
DEFAULT_MILESTONE_READINESS = (
    "artifacts/session/generalized_fetch_to_pose_milestone_readiness_current_proof_cards_20260605/"
    "fetch_generalized_milestone_readiness/milestone_readiness_summary.json"
)
REQUIRED_FIELDS = (
    "runtime_target",
    "inference_backend",
    "execution_surface",
    "physical_robot_run",
    "onboard_tensorrt_execution",
    "physical_camera_evidence",
    "field_physics_notes",
)
REQUIRED_ARTIFACT_KEYS = (
    "control_preflight",
    "mission_verdict",
    "raw_camera",
    "topdown_telemetry",
    "world_stream",
    "keyframe_contact_sheet",
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


def dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "pass", "green"}
    return bool(value)


def issue_unless(issues: list[str], condition: bool, issue: str) -> None:
    if not condition:
        issues.append(issue)


def audit_artifact(path_text: str) -> dict[str, Any]:
    if not path_text:
        return {"path": "", "exists": False, "bytes": 0, "pass": False, "issues": ["artifact_path_missing"]}
    path = resolve_path(path_text)
    exists = path.is_file()
    size = path.stat().st_size if exists else 0
    issues: list[str] = []
    issue_unless(issues, exists, "artifact_missing")
    if exists:
        issue_unless(issues, size > 0, "artifact_empty")
    return {
        "path": artifact_display_path(path),
        "exists": exists,
        "bytes": size,
        "pass": not issues,
        "issues": issues,
    }


def summarize_claim(payload: dict[str, Any], source_path: str) -> dict[str, Any]:
    issues: list[str] = []
    if not payload:
        return {
            "provided": False,
            "path": artifact_display_path(source_path) if source_path else "",
            "pass": False,
            "issues": ["physical_claim_not_provided"],
            "fields": {},
            "artifacts": {},
        }
    fields = {field: payload.get(field) for field in REQUIRED_FIELDS}
    issue_unless(issues, str(payload.get("runtime_target", "")) == "robot_fidelity_orin", "runtime_target_not_robot_fidelity_orin")
    issue_unless(issues, str(payload.get("inference_backend", "")) == "tensorrt_int8", "inference_backend_not_tensorrt_int8")
    issue_unless(issues, str(payload.get("execution_surface", "")) == "physical_robot", "execution_surface_not_physical_robot")
    issue_unless(issues, bool_value(payload.get("physical_robot_run")), "physical_robot_run_not_true")
    issue_unless(issues, bool_value(payload.get("onboard_tensorrt_execution")), "onboard_tensorrt_execution_not_true")
    issue_unless(issues, bool_value(payload.get("physical_camera_evidence")), "physical_camera_evidence_not_true")
    issue_unless(issues, bool_value(payload.get("field_physics_notes")), "field_physics_notes_not_true")
    artifacts_payload = dict_value(payload.get("artifacts"))
    artifact_rows = {key: audit_artifact(str(artifacts_payload.get(key, "") or "")) for key in REQUIRED_ARTIFACT_KEYS}
    for key, row in artifact_rows.items():
        for issue in list_value(row.get("issues")):
            issues.append(f"{key}:{issue}")
    return {
        "provided": True,
        "path": artifact_display_path(source_path) if source_path else "",
        "pass": not issues,
        "issues": issues,
        "fields": fields,
        "artifacts": artifact_rows,
    }


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    milestone, milestone_issues = read_json(args.milestone_readiness_summary)
    claim_payload: dict[str, Any] = {}
    claim_issues: list[str] = []
    physical_claim_path = str(args.physical_claim_summary or "").strip()
    if physical_claim_path:
        claim_payload, claim_issues = read_json(physical_claim_path)
    physical_claim = summarize_claim(claim_payload, physical_claim_path)
    issues = list(milestone_issues)
    issues.extend(claim_issues)
    issue_unless(issues, bool(milestone.get("operator_uat_ready", False)), "milestone_operator_uat_not_ready")
    issue_unless(issues, bool(milestone.get("hardware_proven", True)) is False, "milestone_already_claims_hardware_proven")
    hardware_proven = bool(physical_claim.get("pass", False))
    open_gates = []
    if not physical_claim.get("provided", False):
        open_gates.extend(
            [
                "physical_robot_run_not_provided",
                "onboard_tensorrt_execution_not_provided",
                "physical_camera_evidence_not_provided",
                "field_physics_notes_not_provided",
            ]
        )
    else:
        open_gates.extend(str(issue) for issue in list_value(physical_claim.get("issues")))
    return {
        "generated_utc": utc_now(),
        "type": ANALYZER_KIND,
        "campaign_id": str(args.campaign_id or ""),
        "pass": bool(milestone.get("operator_uat_ready", False)),
        "promotion_evidence": False,
        "hardware_proven": hardware_proven,
        "physical_onboard_proof_ready": hardware_proven,
        "milestone_readiness_path": artifact_display_path(args.milestone_readiness_summary),
        "milestone_operator_uat_ready": bool(milestone.get("operator_uat_ready", False)),
        "milestone_complete_before_physical": bool(milestone.get("milestone_complete", False)),
        "milestone_interpretation": (
            "physical_onboard_proof_complete"
            if hardware_proven
            else "physical_onboard_proof_pending"
        ),
        "issues": issues,
        "open_gates": open_gates,
        "physical_claim": physical_claim,
        "required_claim_schema": {
            "fields": list(REQUIRED_FIELDS),
            "artifact_keys": list(REQUIRED_ARTIFACT_KEYS),
            "expected_values": {
                "runtime_target": "robot_fidelity_orin",
                "inference_backend": "tensorrt_int8",
                "execution_surface": "physical_robot",
            },
        },
        "next_actions": [
            "run_physical_robot_rehearsal_using_current_hardware_plan",
            "record_physical_raw_camera_topdown_world_stream_and_keyframe_review",
            "write_physical_claim_summary_json_using_required_schema",
            "rerun_this_gap_audit_before_setting_hardware_proven_true",
        ],
    }


def artifact_link(path_text: str) -> str:
    text = str(path_text or "").replace("\\", "/")
    return f"[artifact](/{text})" if text.startswith(("artifacts/", "runtime/", "docs/")) else text


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    claim = dict_value(summary.get("physical_claim"))
    lines = [
        "# Fetch Physical Onboard Proof Gap",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- hardware_proven: `{summary.get('hardware_proven', False)}`",
        f"- physical_onboard_proof_ready: `{summary.get('physical_onboard_proof_ready', False)}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        f"- milestone_operator_uat_ready: `{summary.get('milestone_operator_uat_ready', False)}`",
        f"- issues: `{summary.get('issues', [])}`",
        f"- milestone_readiness: {artifact_link(str(summary.get('milestone_readiness_path', '') or ''))}",
        "",
        "## Open Gates",
        "",
    ]
    for gate in list_value(summary.get("open_gates")):
        lines.append(f"- `{gate}`")
    lines.extend(
        [
            "",
            "## Physical Claim",
            "",
            f"- provided: `{claim.get('provided', False)}`",
            f"- pass: `{claim.get('pass', False)}`",
            f"- path: {artifact_link(str(claim.get('path', '') or ''))}",
            f"- issues: `{claim.get('issues', [])}`",
            "",
            "## Required Claim Schema",
            "",
        ]
    )
    schema = dict_value(summary.get("required_claim_schema"))
    lines.append(f"- fields: `{schema.get('fields', [])}`")
    lines.append(f"- artifact_keys: `{schema.get('artifact_keys', [])}`")
    lines.append(f"- expected_values: `{schema.get('expected_values', {})}`")
    lines.extend(["", "## Next Actions", ""])
    for action in list_value(summary.get("next_actions")):
        lines.append(f"- `{action}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit physical/onboard proof gap for generalized fetch.")
    parser.add_argument("--campaign-id", default=f"fetch_physical_onboard_proof_gap_{current_utc_stamp()}")
    parser.add_argument("--milestone-readiness-summary", default=DEFAULT_MILESTONE_READINESS)
    parser.add_argument("--physical-claim-summary", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / ANALYZER_KIND)
    summary = build_summary(args)
    summary_path = root / "physical_onboard_proof_gap_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["summary_path"] = artifact_display_path(summary_path)
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_PHYSICAL_ONBOARD_PROOF_GAP_SUMMARY={summary_path}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
