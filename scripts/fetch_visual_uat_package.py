#!/usr/bin/env python3
"""Build a mobile-watchable fetch UAT evidence package."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
PACKAGE_KIND = "fetch_visual_uat_package"
VIDEO_MIN_BYTES = 1024
VIDEO_NAMES = (
    "world_stream.mp4",
    "topdown_telemetry.mp4",
    "raw_camera.mp4",
    "yolo_debug.mp4",
)


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


def resolve_path(raw_path: str) -> Path:
    path = Path(str(raw_path or "").strip())
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def artifact_display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def artifact_url(path: Path) -> str:
    resolved = path.resolve()
    try:
        rel = resolved.relative_to(SESSION_ROOT.resolve())
    except ValueError:
        return ""
    return "/artifacts/session/" + rel.as_posix()


def summarize_planner_gate(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    if not payload:
        return {}
    return {
        "campaign_id": str(payload.get("campaign_id", "") or ""),
        "path": artifact_display_path(path),
        "pass": bool(payload.get("pass", False)),
        "planner_mode": str(payload.get("planner_mode", "") or ""),
        "scene_set": str(payload.get("scene_set", "") or ""),
        "scene_source": str(payload.get("scene_source", "") or ""),
        "pass_count": int(payload.get("pass_count", 0) or 0),
        "fail_count": int(payload.get("fail_count", 0) or 0),
        "total_count": int(payload.get("random_cases", 0) or 0),
        "fetch_dispatch_count": int(payload.get("fetch_dispatch_count", 0) or 0),
        "wrong_fetch_dispatch_count": int(payload.get("wrong_fetch_dispatch_count", 0) or 0),
        "route_counts": payload.get("route_counts", {}) if isinstance(payload.get("route_counts"), dict) else {},
    }


def summarize_seeded_evidence(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    seeded = payload.get("seeded_gate", payload.get("seeded_shadow_gate", {}))
    seeded = seeded if isinstance(seeded, dict) else {}
    return {
        "campaign_id": str(payload.get("campaign_id", "") or ""),
        "path": artifact_display_path(path),
        "promotion_evidence": bool(payload.get("promotion_evidence", False)),
        "milestone_interpretation": str(payload.get("milestone_interpretation", "") or ""),
        "recommended_next_action": str(payload.get("recommended_next_action", "") or ""),
        "seeded_pass": bool(seeded.get("pass", False)),
        "seeded_pass_count": int(seeded.get("pass_count", 0) or 0),
        "seeded_fail_count": int(seeded.get("fail_count", 0) or 0),
        "guarded_live_candidate_count": int(seeded.get("guarded_live_candidate_count", 0) or 0),
        "non_repro_failure_count": int(seeded.get("non_repro_failure_count", 0) or 0),
        "reproduced_failure_count": int(seeded.get("reproduced_failure_count", 0) or 0),
    }


def summarize_mission(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    runs = payload.get("runs", []) if isinstance(payload.get("runs"), list) else []
    first_run = runs[0] if runs and isinstance(runs[0], dict) else {}
    mission_verdict = payload.get("mission_verdict", {}) if isinstance(payload.get("mission_verdict"), dict) else {}
    if not mission_verdict and isinstance(first_run.get("mission_verdict"), dict):
        mission_verdict = first_run.get("mission_verdict", {})
    pass_flag = bool(
        payload.get("pass", payload.get("promotion_gate_pass", mission_verdict.get("pass", first_run.get("mission_completed_pass", False))))
    )
    fetch_pass = bool(
        payload.get("fetch_to_pose_pass_count", 0)
        or payload.get("fetch_to_pose_pass", False)
        or mission_verdict.get("fetch_to_pose_pass", False)
        or first_run.get("fetch_to_pose_pass", False)
    )
    return {
        "campaign_id": str(payload.get("campaign_id", "") or ""),
        "path": artifact_display_path(path),
        "pass": pass_flag,
        "fetch_to_pose_pass": fetch_pass,
        "fetch_to_pose_pass_count": int(payload.get("fetch_to_pose_pass_count", 1 if fetch_pass else 0) or 0),
        "fetch_to_pose_fail_count": int(payload.get("fetch_to_pose_fail_count", 0 if fetch_pass else 1) or 0),
        "ai_push_coast_mode": str(payload.get("ai_push_coast_mode", mission_verdict.get("ai_push_coast_mode", "")) or ""),
        "mission_objective": str(payload.get("mission_objective", mission_verdict.get("mission_objective", "")) or ""),
        "scenario_label": str(payload.get("scenario_label", mission_verdict.get("scenario_label", "")) or ""),
        "target_layout_json": str(payload.get("requested_target_layout_json", mission_verdict.get("target_layout_json", "")) or ""),
        "closest_approach_distance_m": payload.get("closest_approach_distance_m", mission_verdict.get("closest_approach_distance_m")),
        "failure_reasons": payload.get("fetch_to_pose_failure_reasons", mission_verdict.get("failure_reasons", [])),
    }


def discover_videos(visual_dirs: list[Path]) -> list[dict[str, Any]]:
    videos: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for visual_dir in visual_dirs:
        if not visual_dir.is_dir():
            continue
        for name in VIDEO_NAMES:
            path = (visual_dir / name).resolve()
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            videos.append(
                {
                    "name": name,
                    "path": artifact_display_path(path),
                    "url": artifact_url(path),
                    "size_bytes": int(path.stat().st_size),
                    "playable_candidate": int(path.stat().st_size) >= VIDEO_MIN_BYTES,
                }
            )
    return videos


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    planner_gates = [summarize_planner_gate(resolve_path(path)) for path in args.planner_summary]
    planner_gates = [item for item in planner_gates if item]
    seeded_evidence = [summarize_seeded_evidence(resolve_path(path)) for path in args.seeded_evidence_summary]
    seeded_evidence = [item for item in seeded_evidence if item]
    missions = [summarize_mission(resolve_path(path)) for path in args.mission_summary]
    missions = [item for item in missions if item]
    visual_dirs = [resolve_path(path) for path in args.visual_dir]
    videos = discover_videos(visual_dirs)

    planner_ok = bool(planner_gates) and all(
        gate.get("pass") and int(gate.get("wrong_fetch_dispatch_count", 0) or 0) == 0 for gate in planner_gates
    )
    local_fetch_seen = any(mission.get("fetch_to_pose_pass") for mission in missions)
    playable_core = {video["name"] for video in videos if video.get("url") and video.get("playable_candidate")}
    video_ok = {"world_stream.mp4", "topdown_telemetry.mp4"}.issubset(playable_core)
    pass_flag = bool(planner_ok and local_fetch_seen and video_ok)
    warnings: list[str] = []
    if not planner_ok:
        warnings.append("planner_gate_not_green")
    if not local_fetch_seen:
        warnings.append("no_local_fetch_pass_seen")
    if not video_ok:
        warnings.append("missing_or_tiny_world_or_topdown_video")

    return {
        "type": PACKAGE_KIND,
        "campaign_id": str(args.campaign_id or ""),
        "generated_utc": utc_now(),
        "pass": pass_flag,
        "mobile_watchable": video_ok,
        "planner_gate_green": planner_ok,
        "local_fetch_pass_seen": local_fetch_seen,
        "promotion_evidence": False,
        "milestone_interpretation": (
            "mobile_visual_uat_ready_not_promotion" if pass_flag else "mobile_visual_uat_incomplete"
        ),
        "warnings": warnings,
        "planner_gates": planner_gates,
        "seeded_evidence": seeded_evidence,
        "missions": missions,
        "videos": videos,
        "scorecard_path": "",
    }


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Fetch Visual UAT Package",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- mobile_watchable: `{summary.get('mobile_watchable', False)}`",
        f"- planner_gate_green: `{summary.get('planner_gate_green', False)}`",
        f"- local_fetch_pass_seen: `{summary.get('local_fetch_pass_seen', False)}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        "",
        "## Videos",
    ]
    videos = summary.get("videos", []) if isinstance(summary.get("videos"), list) else []
    if videos:
        for video in videos:
            lines.append(f"- `{video.get('name', '')}`: `{video.get('url', '')}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Planner Gates"])
    for gate in summary.get("planner_gates", []) if isinstance(summary.get("planner_gates"), list) else []:
        lines.append(
            f"- `{gate.get('campaign_id', '')}` pass=`{gate.get('pass', False)}` "
            f"routes=`{gate.get('pass_count', 0)}/{gate.get('total_count', 0)}` "
            f"wrong_fetch=`{gate.get('wrong_fetch_dispatch_count', 0)}`"
        )
    lines.extend(["", "## Missions"])
    for mission in summary.get("missions", []) if isinstance(summary.get("missions"), list) else []:
        lines.append(
            f"- `{mission.get('campaign_id', '') or mission.get('scenario_label', '')}` "
            f"fetch_to_pose=`{mission.get('fetch_to_pose_pass', False)}` "
            f"ai_mode=`{mission.get('ai_push_coast_mode', '')}`"
        )
    warnings = summary.get("warnings", []) if isinstance(summary.get("warnings"), list) else []
    lines.extend(["", "## Warnings"])
    lines.extend([f"- `{item}`" for item in warnings] or ["- none"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a mobile fetch visual UAT package.")
    parser.add_argument("--campaign-id", default=f"live_fetch_visual_uat_package_{current_utc_stamp()}")
    parser.add_argument("--planner-summary", action="append", default=[])
    parser.add_argument("--seeded-evidence-summary", action="append", default=[])
    parser.add_argument("--mission-summary", action="append", default=[])
    parser.add_argument("--visual-dir", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / PACKAGE_KIND)
    summary = build_summary(args)
    summary_path = root / "package_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_VISUAL_UAT_PACKAGE_SUMMARY={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
