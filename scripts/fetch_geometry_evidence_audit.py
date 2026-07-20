#!/usr/bin/env python3
"""Audit fetch-to-pose artifacts for visible-marker geometry mismatches."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

from fetch_visual_uat_package import artifact_display_path
from fetch_visual_uat_package import current_utc_stamp
from fetch_visual_uat_package import ensure_dir
from fetch_visual_uat_package import infer_geometry_consistency
from fetch_visual_uat_package import read_json
from fetch_visual_uat_package import write_json


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
AUDIT_KIND = "fetch_geometry_evidence_audit"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_path(raw_path: str) -> Path:
    path = Path(str(raw_path or "").strip())
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def iter_verdict_paths(artifact_root: Path, explicit_paths: list[str]) -> list[Path]:
    if explicit_paths:
        return [resolve_path(item) for item in explicit_paths]
    if not artifact_root.exists():
        return []
    return sorted(path for path in artifact_root.rglob("mission_verdict.json") if path.is_file())


def audit_verdict(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    if not payload:
        return {}
    mission_objective = str(payload.get("mission_objective", "") or "")
    fetch_pose = payload.get("fetch_pose_world") if isinstance(payload.get("fetch_pose_world"), dict) else {}
    if mission_objective != "fetch_to_pose" and not fetch_pose:
        return {}
    geometry = infer_geometry_consistency(payload)
    raw_fetch_pass = bool(payload.get("fetch_to_pose_pass", payload.get("pass", False)))
    geometry_present = bool(geometry)
    geometry_pass = bool(geometry.get("pass", False)) if geometry_present else False
    return {
        "path": artifact_display_path(path),
        "session_id": str(payload.get("session_id", "") or ""),
        "scenario_label": str(payload.get("scenario_label", "") or ""),
        "mission_objective": mission_objective,
        "raw_pass": bool(payload.get("pass", False)),
        "raw_fetch_to_pose_pass": raw_fetch_pass,
        "geometry_present": geometry_present,
        "geometry_consistent": geometry_pass,
        "evidence_valid": bool(raw_fetch_pass and geometry_pass),
        "invalid_reason": "" if geometry_pass else "missing_geometry" if not geometry_present else "fetch_marker_geometry_mismatch",
        "fetch_pose_world": fetch_pose,
        "visible_delivery_marker_pose": (
            payload.get("visible_delivery_marker_pose", {})
            if isinstance(payload.get("visible_delivery_marker_pose"), dict)
            else payload.get("zone_pose", {})
            if isinstance(payload.get("zone_pose"), dict)
            else {}
        ),
        "geometry_consistency": geometry,
    }


def build_scorecard(summary: dict[str, Any]) -> str:
    rows = summary.get("runs", []) if isinstance(summary.get("runs"), list) else []
    lines = [
        "# Fetch Geometry Evidence Audit",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- total_fetch_runs: `{summary.get('total_fetch_runs', 0)}`",
        f"- valid_fetch_evidence: `{summary.get('valid_fetch_evidence_count', 0)}`",
        f"- invalid_fetch_evidence: `{summary.get('invalid_fetch_evidence_count', 0)}`",
        f"- geometry_mismatch_count: `{summary.get('geometry_mismatch_count', 0)}`",
        f"- missing_geometry_count: `{summary.get('missing_geometry_count', 0)}`",
        "",
        "## Runs",
    ]
    if not rows:
        lines.append("- none")
    for row in rows:
        lines.append(
            f"- `{row.get('path', '')}` raw_fetch=`{row.get('raw_fetch_to_pose_pass', False)}` "
            f"geometry=`{row.get('geometry_consistent', False)}` "
            f"valid=`{row.get('evidence_valid', False)}` "
            f"reason=`{row.get('invalid_reason', '')}`"
        )
    return "\n".join(lines) + "\n"


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    artifact_root = resolve_path(args.artifact_root)
    verdicts = [audit_verdict(path) for path in iter_verdict_paths(artifact_root, args.mission_verdict)]
    runs = [item for item in verdicts if item]
    valid_count = sum(1 for item in runs if item.get("evidence_valid"))
    mismatch_count = sum(1 for item in runs if item.get("invalid_reason") == "fetch_marker_geometry_mismatch")
    missing_count = sum(1 for item in runs if item.get("invalid_reason") == "missing_geometry")
    return {
        "type": AUDIT_KIND,
        "campaign_id": str(args.campaign_id or ""),
        "generated_utc": utc_now(),
        "artifact_root": artifact_display_path(artifact_root),
        "total_fetch_runs": len(runs),
        "valid_fetch_evidence_count": valid_count,
        "invalid_fetch_evidence_count": len(runs) - valid_count,
        "geometry_mismatch_count": mismatch_count,
        "missing_geometry_count": missing_count,
        "runs": runs,
        "scorecard_path": "",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit fetch-to-pose evidence geometry.")
    parser.add_argument("--campaign-id", default=f"fetch_geometry_evidence_audit_{current_utc_stamp()}")
    parser.add_argument("--artifact-root", default=str(SESSION_ROOT))
    parser.add_argument("--mission-verdict", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / AUDIT_KIND)
    summary = build_summary(args)
    summary_path = root / "audit_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    scorecard_path.write_text(build_scorecard(summary), encoding="utf-8")
    print(f"FETCH_GEOMETRY_EVIDENCE_AUDIT_SUMMARY={summary_path}")
    return 0 if int(summary["geometry_mismatch_count"]) == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
