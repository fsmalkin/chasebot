#!/usr/bin/env python3
"""Audit fetch artifacts for calibrated ball and delivery-marker provenance."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
AUDIT_KIND = "fetch_model_provenance_audit"
DEFAULT_BOUNDARY_COMMIT = "680e393"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def artifact_display_path(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def resolve_path(raw_path: str) -> Path:
    path = Path(str(raw_path or "").strip())
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def _first_dict(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict) and value:
            return dict(value)
    return {}


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _fetch_runs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    runs = payload.get("runs", [])
    if not isinstance(runs, list):
        return []
    return [
        dict(run)
        for run in runs
        if isinstance(run, dict)
        and str(run.get("mission_objective", payload.get("mission_objective", "")) or "") == "fetch_to_pose"
    ]


def _model_payload_from_source(source: dict[str, Any]) -> dict[str, Any]:
    existing = source.get("model_provenance") if isinstance(source.get("model_provenance"), dict) else {}
    if existing:
        return dict(existing)
    payload: dict[str, Any] = {}
    for key in (
        "target_model_sdf",
        "zone_model_sdf",
        "target_model_radius_m",
        "target_model_classification",
        "zone_model_radius_m",
        "zone_model_classification",
        "model_provenance_valid",
        "model_provenance_reason",
        "model_provenance_required",
    ):
        if key in source:
            payload[key] = source.get(key)
    return payload


def _infer_model_payload(source: dict[str, Any], *, mission_objective: str) -> dict[str, Any]:
    payload = _model_payload_from_source(source)
    if payload and (
        "model_provenance_valid" in payload
        or str(payload.get("target_model_classification", "") or "").strip()
    ):
        return payload
    target_model_sdf = _first_text(
        payload.get("target_model_sdf") if payload else "",
        source.get("target_model_sdf"),
        source.get("requested_target_model_sdf"),
    )
    zone_model_sdf = _first_text(
        payload.get("zone_model_sdf") if payload else "",
        source.get("zone_model_sdf"),
        source.get("requested_zone_model_sdf"),
    )
    if not target_model_sdf and not zone_model_sdf:
        return {}
    try:
        from gather_mission_runner import fetch_model_provenance
    except Exception:
        return {
            "target_model_sdf": target_model_sdf,
            "zone_model_sdf": zone_model_sdf,
            "model_provenance_valid": False,
            "model_provenance_reason": "unable_to_import_model_classifier",
        }
    return fetch_model_provenance(
        mission_objective=mission_objective,
        target_model_sdf=target_model_sdf,
        zone_model_sdf=zone_model_sdf,
    )


def _artifact_candidates(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    candidates: set[Path] = set()
    for pattern in (
        "*/gather_mission_repeatability/campaign_run_summary.json",
        "*/*/campaign_run_summary.json",
        "**/mission_verdict.json",
    ):
        for path in root.glob(pattern):
            if path.is_file():
                candidates.add(path.resolve())
    return sorted(candidates, key=lambda item: str(item))


def classify_artifact(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    runs = _fetch_runs(payload)
    representative_run = runs[0] if runs else {}
    mission_objective = _first_text(
        payload.get("mission_objective"),
        representative_run.get("mission_objective"),
        "gather_here",
    )
    fetch_artifact = mission_objective == "fetch_to_pose" or bool(runs)
    source = dict(payload)
    if representative_run:
        source = {**representative_run, **source}
    model_payload = _infer_model_payload(source, mission_objective="fetch_to_pose" if fetch_artifact else mission_objective)
    if not fetch_artifact:
        status = "not_applicable"
        interpretation = "non_fetch_artifact"
    elif not model_payload:
        status = "needs_recheck_missing_model_provenance"
        interpretation = "diagnostic_only_until_rerun"
    elif bool(model_payload.get("model_provenance_valid", False)):
        status = "valid_model_provenance"
        interpretation = "eligible_for_metric_review"
    else:
        status = "quarantine_invalid_model_provenance"
        interpretation = "diagnostic_only_until_rerun"
    return {
        "path": artifact_display_path(path),
        "generated_utc": str(payload.get("generated_utc", "") or ""),
        "campaign_id": str(payload.get("campaign_id", "") or ""),
        "session_id": str(payload.get("session_id", "") or representative_run.get("session_id", "") or ""),
        "type": str(payload.get("type", path.parent.name) or path.parent.name),
        "mission_objective": mission_objective,
        "fetch_artifact": fetch_artifact,
        "fetch_to_pose_pass_count": int(payload.get("fetch_to_pose_pass_count", 0) or 0),
        "fetch_to_pose_fail_count": int(payload.get("fetch_to_pose_fail_count", 0) or 0),
        "model_provenance_status": status,
        "interpretation": interpretation,
        "model_provenance": model_payload,
        "model_provenance_valid": bool(model_payload.get("model_provenance_valid", False)),
        "model_provenance_reason": str(model_payload.get("model_provenance_reason", "") or ""),
        "target_model_sdf": str(model_payload.get("target_model_sdf", "") or ""),
        "zone_model_sdf": str(model_payload.get("zone_model_sdf", "") or ""),
        "target_model_radius_m": model_payload.get("target_model_radius_m"),
        "target_model_classification": str(model_payload.get("target_model_classification", "") or ""),
        "zone_model_classification": str(model_payload.get("zone_model_classification", "") or ""),
    }


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve_path(args.root)
    rows = [
        classify_artifact(path, read_json(path))
        for path in _artifact_candidates(root)
    ]
    if not args.include_non_fetch:
        rows = [row for row in rows if bool(row.get("fetch_artifact", False))]
    valid_rows = [row for row in rows if row.get("model_provenance_status") == "valid_model_provenance"]
    quarantine_rows = [row for row in rows if row.get("model_provenance_status") == "quarantine_invalid_model_provenance"]
    needs_recheck_rows = [row for row in rows if row.get("model_provenance_status") == "needs_recheck_missing_model_provenance"]
    rows_by_status: dict[str, int] = {}
    for row in rows:
        status = str(row.get("model_provenance_status", "") or "")
        rows_by_status[status] = rows_by_status.get(status, 0) + 1
    return {
        "type": AUDIT_KIND,
        "campaign_id": str(args.campaign_id or ""),
        "generated_utc": utc_now(),
        "artifact_root": artifact_display_path(root),
        "provenance_boundary_commit": str(args.provenance_boundary_commit or DEFAULT_BOUNDARY_COMMIT),
        "pass": bool(rows and not quarantine_rows and not needs_recheck_rows),
        "valid_model_provenance_count": len(valid_rows),
        "quarantine_invalid_model_provenance_count": len(quarantine_rows),
        "needs_recheck_missing_model_provenance_count": len(needs_recheck_rows),
        "audited_fetch_artifact_count": len(rows),
        "rows_by_status": rows_by_status,
        "rows": rows[: max(int(args.max_rows), 0)] if int(args.max_rows) else rows,
        "truncated": bool(int(args.max_rows) and len(rows) > int(args.max_rows)),
        "scorecard_path": "",
    }


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Fetch Model Provenance Audit",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- provenance_boundary_commit: `{summary.get('provenance_boundary_commit', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- valid_model_provenance_count: `{summary.get('valid_model_provenance_count', 0)}`",
        f"- quarantine_invalid_model_provenance_count: `{summary.get('quarantine_invalid_model_provenance_count', 0)}`",
        f"- needs_recheck_missing_model_provenance_count: `{summary.get('needs_recheck_missing_model_provenance_count', 0)}`",
        f"- audited_fetch_artifact_count: `{summary.get('audited_fetch_artifact_count', 0)}`",
        "",
        "## Interpretation",
        "",
        "Artifacts with calibrated golf-ball and delivery-marker provenance remain eligible for metric review. Artifacts with legacy or missing provenance stay diagnostic until rerun.",
        "",
        "## Rows",
    ]
    rows = summary.get("rows", []) if isinstance(summary.get("rows"), list) else []
    if rows:
        for row in rows:
            lines.append(
                f"- `{row.get('model_provenance_status', '')}` "
                f"`{row.get('path', '')}` "
                f"target=`{row.get('target_model_classification', '')}` "
                f"radius=`{row.get('target_model_radius_m', '')}` "
                f"reason=`{row.get('model_provenance_reason', '')}`"
            )
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit fetch artifacts for calibrated model provenance.")
    parser.add_argument("--campaign-id", default=f"fetch_model_provenance_audit_{current_utc_stamp()}")
    parser.add_argument("--root", default=str(SESSION_ROOT))
    parser.add_argument("--provenance-boundary-commit", default=DEFAULT_BOUNDARY_COMMIT)
    parser.add_argument("--max-rows", type=int, default=500)
    parser.add_argument("--include-non-fetch", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / AUDIT_KIND)
    summary = build_summary(args)
    summary_path = root / "model_provenance_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_MODEL_PROVENANCE_AUDIT_SUMMARY={summary_path}")
    return 0 if summary.get("pass") else 2


if __name__ == "__main__":
    raise SystemExit(main())
