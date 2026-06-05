#!/usr/bin/env python3
"""Build a physical proof claim from a completed fetch run artifact bundle."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
CLAIM_KIND = "fetch_physical_claim_from_run"
VIDEO_BY_KEY = {
    "raw_camera": "raw_camera_browser.mp4",
    "topdown_telemetry": "topdown_telemetry_browser.mp4",
    "world_stream": "world_stream.mp4",
}


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


def issue_unless(issues: list[str], condition: bool, issue: str) -> None:
    if not condition:
        issues.append(issue)


def choose_batch_row(batch: dict[str, Any], scene_id: str) -> tuple[dict[str, Any], list[str]]:
    rows = [dict_value(row) for row in list_value(batch.get("rows")) if isinstance(row, dict)]
    issues: list[str] = []
    if scene_id:
        matches = [row for row in rows if str(row.get("scene_id", "")) == scene_id]
        issue_unless(issues, bool(matches), f"scene_id_not_found:{scene_id}")
        return (matches[0] if matches else {}, issues)
    executable = []
    for row in rows:
        mission, mission_issues = read_json(str(row.get("mission_summary_path", "") or ""))
        if mission_issues:
            continue
        if is_executable_delivery(mission):
            executable.append(row)
    issue_unless(issues, bool(executable), "no_passing_executable_batch_row")
    return (executable[0] if executable else {}, issues)


def is_executable_delivery(mission: dict[str, Any]) -> bool:
    local_fetch_dispatched = bool(mission.get("local_fetch_dispatched", False)) or (
        str(mission.get("route_executor", "")) == "local_fetch_to_pose"
    )
    delivery_pass = bool(mission.get("pass", False)) and (
        bool(mission.get("fetch_to_pose_pass", False))
        or bool(mission.get("mission_completed_pass", False))
        or bool(mission.get("local_fetch_dispatched", False))
    )
    return local_fetch_dispatched and delivery_pass


def video_path(package: dict[str, Any], video_name: str) -> str:
    for video in list_value(package.get("videos")):
        row = dict_value(video)
        if str(row.get("name", "")) == video_name and bool(row.get("browser_playable", False)):
            return str(row.get("path", "") or "")
    return ""


def keyframe_path(package: dict[str, Any]) -> str:
    for review in list_value(package.get("keyframe_reviews")):
        row = dict_value(review)
        if bool(row.get("ok", False)):
            return str(row.get("path", "") or "")
    return ""


def assert_file(issues: list[str], path_text: str, issue: str) -> None:
    issue_unless(issues, bool(path_text), f"{issue}:path_missing")
    if path_text:
        issue_unless(issues, resolve_path(path_text).is_file(), f"{issue}:file_missing")


def build_claim(args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    issues: list[str] = []
    mission_path = str(args.mission_summary or "").strip()
    package_path = str(args.visual_package_summary or "").strip()
    if args.batch_summary:
        batch, batch_issues = read_json(args.batch_summary)
        issues.extend(batch_issues)
        row, row_issues = choose_batch_row(batch, str(args.scene_id or ""))
        issues.extend(row_issues)
        mission_path = mission_path or str(row.get("mission_summary_path", "") or "")
        package_path = package_path or str(row.get("visual_package_summary_path", "") or "")

    mission, mission_issues = read_json(mission_path)
    package, package_issues = read_json(package_path)
    issues.extend(mission_issues)
    issues.extend(package_issues)
    issue_unless(issues, bool(mission.get("pass", False)), "mission_not_pass")
    issue_unless(issues, bool(package.get("pass", False)), "visual_package_not_pass")
    issue_unless(issues, is_executable_delivery(mission), "mission_not_executable_local_fetch")

    control_path = str(args.control_preflight or "").strip()
    if not control_path and isinstance(mission.get("control_preflight"), dict):
        control_path = str(output_dir / "control_preflight.json")
        write_json(resolve_path(control_path), dict_value(mission.get("control_preflight")))

    artifacts = {
        "control_preflight": artifact_display_path(control_path) if control_path else "",
        "mission_verdict": artifact_display_path(mission_path) if mission_path else "",
        "keyframe_contact_sheet": artifact_display_path(keyframe_path(package)),
    }
    for key, name in VIDEO_BY_KEY.items():
        artifacts[key] = artifact_display_path(video_path(package, name))

    for key, path_text in artifacts.items():
        assert_file(issues, path_text, key)

    claim = {
        "generated_utc": utc_now(),
        "type": "physical_claim_summary",
        "source": CLAIM_KIND,
        "runtime_target": "robot_fidelity_orin",
        "inference_backend": "tensorrt_int8",
        "execution_surface": "physical_robot" if bool(args.confirm_physical_robot) else "unconfirmed",
        "physical_robot_run": bool(args.confirm_physical_robot),
        "onboard_tensorrt_execution": bool(args.confirm_onboard_tensorrt),
        "physical_camera_evidence": bool(args.confirm_physical_camera),
        "field_physics_notes": bool(args.confirm_field_physics),
        "claim_ready_for_gap_audit": not issues,
        "issues": issues,
        "source_artifacts": {
            "batch_summary": artifact_display_path(args.batch_summary) if args.batch_summary else "",
            "mission_summary": artifact_display_path(mission_path) if mission_path else "",
            "visual_package_summary": artifact_display_path(package_path) if package_path else "",
        },
        "selected_scene_id": str(args.scene_id or ""),
        "artifacts": artifacts,
    }
    return claim


def artifact_link(path_text: str) -> str:
    text = str(path_text or "").replace("\\", "/")
    return f"[artifact](/{text})" if text.startswith(("artifacts/", "runtime/", "docs/")) else text


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    claim = dict_value(summary.get("claim"))
    lines = [
        "# Fetch Physical Claim From Run",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- claim_ready_for_gap_audit: `{claim.get('claim_ready_for_gap_audit', False)}`",
        f"- physical_robot_run: `{claim.get('physical_robot_run', False)}`",
        f"- onboard_tensorrt_execution: `{claim.get('onboard_tensorrt_execution', False)}`",
        f"- physical_camera_evidence: `{claim.get('physical_camera_evidence', False)}`",
        f"- field_physics_notes: `{claim.get('field_physics_notes', False)}`",
        f"- issues: `{summary.get('issues', [])}`",
        f"- claim_summary: {artifact_link(str(summary.get('claim_summary_path', '') or ''))}",
        "",
        "## Artifacts",
        "",
    ]
    for key, value in dict_value(claim.get("artifacts")).items():
        lines.append(f"- `{key}`: {artifact_link(str(value))}")
    lines.extend(["", "## Next Command", ""])
    lines.append(f"- `python scripts/fetch_physical_onboard_proof_gap.py --physical-claim-summary {summary.get('claim_summary_path', '')}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build physical claim JSON from fetch run artifacts.")
    parser.add_argument("--campaign-id", default=f"fetch_physical_claim_from_run_{current_utc_stamp()}")
    parser.add_argument("--batch-summary", default="")
    parser.add_argument("--scene-id", default="")
    parser.add_argument("--mission-summary", default="")
    parser.add_argument("--visual-package-summary", default="")
    parser.add_argument("--control-preflight", default="")
    parser.add_argument("--confirm-physical-robot", action="store_true")
    parser.add_argument("--confirm-onboard-tensorrt", action="store_true")
    parser.add_argument("--confirm-physical-camera", action="store_true")
    parser.add_argument("--confirm-field-physics", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / CLAIM_KIND)
    claim = build_claim(args, root)
    claim_path = root / "physical_claim_summary.json"
    scorecard_path = root / "scorecard.md"
    summary = {
        "generated_utc": utc_now(),
        "type": CLAIM_KIND,
        "campaign_id": str(args.campaign_id),
        "pass": bool(claim.get("claim_ready_for_gap_audit", False)),
        "promotion_evidence": False,
        "hardware_proven": False,
        "issues": list_value(claim.get("issues")),
        "claim_summary_path": artifact_display_path(claim_path),
        "scorecard_path": artifact_display_path(scorecard_path),
        "claim": claim,
    }
    write_json(claim_path, claim)
    write_json(root / "claim_generator_summary.json", summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_PHYSICAL_CLAIM_SUMMARY={claim_path}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
