#!/usr/bin/env python3
"""Analyze dashboard random golf-fetch UAT artifacts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import read_json
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json


ANALYZER_KIND = "dashboard_random_fetch_uat_analyzer"
FLAG_STAGE_LABELS = {
    "pre_contact_lateral_error": "setup",
    "pre_contact_yaw_error": "setup",
    "ball_lateral_knock_away": "first_contact",
    "contact_trajectory_angle_error": "push_coast",
    "stop_short": "terminal_arrival",
    "missed_delivery_radius": "terminal_arrival",
    "missed_delivery_radius_after_fetch_to_pose_ball_stopped_short": "terminal_arrival",
}


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze dashboard random golf-fetch UAT runs.")
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--artifact", action="append", default=[], help="Mission root, mission_verdict.json, or session dir.")
    return parser.parse_args()


def _output_root(campaign_id: str) -> Path:
    return REPO_ROOT / "artifacts" / "session" / campaign_id / ANALYZER_KIND


def _resolve_path(raw_path: str) -> Path:
    path = Path(str(raw_path or "").strip())
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


def _mission_verdict_paths(raw_paths: list[str]) -> list[Path]:
    verdicts: list[Path] = []
    seen: set[str] = set()
    for raw_path in raw_paths:
        path = _resolve_path(raw_path)
        candidates: list[Path] = []
        if path.is_file():
            candidates = [path]
        elif (path / "mission_verdict.json").is_file():
            candidates = [path / "mission_verdict.json"]
        elif path.is_dir():
            candidates = sorted(path.glob("**/golf_ball_circle_delivery_random/*/mission_verdict.json"))
        for candidate in candidates:
            key = str(candidate.resolve())
            if key not in seen:
                seen.add(key)
                verdicts.append(candidate)
    return verdicts


def _stage_labels(*, flags: list[str], reason: str, pass_flag: bool, stable_contact: bool) -> list[str]:
    labels: list[str] = []
    for flag in flags:
        stage = FLAG_STAGE_LABELS.get(flag)
        if stage and stage not in labels:
            labels.append(stage)
    reason_text = str(reason or "")
    for marker, stage in FLAG_STAGE_LABELS.items():
        if marker in reason_text and stage not in labels:
            labels.append(stage)
    if not pass_flag and not labels:
        labels.append("terminal_arrival")
    if pass_flag and stable_contact and not flags:
        labels.append("clean_contact")
    return labels


def analyze_verdict(path: Path) -> dict[str, Any]:
    verdict = read_json(path)
    approach = verdict.get("approach_contact_metrics", {}) if isinstance(verdict.get("approach_contact_metrics"), dict) else {}
    shot = verdict.get("shot_outcome", {}) if isinstance(verdict.get("shot_outcome"), dict) else {}
    draw = verdict.get("random_draw", {}) if isinstance(verdict.get("random_draw"), dict) else {}
    if not draw:
        layout = verdict.get("target_layout", {}) if isinstance(verdict.get("target_layout"), dict) else {}
        draw = layout.get("random_draw", {}) if isinstance(layout.get("random_draw"), dict) else {}
    flags = [str(flag) for flag in approach.get("flags", []) if str(flag)]
    pass_flag = bool(verdict.get("pass", False))
    stable_contact = bool(approach.get("stable_contact_approach_pass", False))
    reason = str(shot.get("reason", verdict.get("fetch_to_pose_failure_reason", "")) or "")
    labels = _stage_labels(flags=flags, reason=reason, pass_flag=pass_flag, stable_contact=stable_contact)
    contact_quality = "clean" if pass_flag and stable_contact and not flags else "flagged" if pass_flag else "failed"
    return {
        "artifact_dir": str(path.parent),
        "mission_verdict_path": str(path),
        "pass": pass_flag,
        "contact_quality": contact_quality,
        "stage_labels": labels,
        "flags": flags,
        "stable_contact_approach_pass": stable_contact,
        "reason": reason,
        "closest_approach_distance_m": shot.get("closest_approach_distance_m"),
        "distance_to_fetch_pose_m": shot.get("distance_to_fetch_pose_m"),
        "random_profile": str(verdict.get("random_profile", "") or draw.get("random_profile", "")),
        "seed": draw.get("seed"),
        "ball_target_distance_m": draw.get("ball_target_distance_m"),
        "ball_target_angle_deg": draw.get("ball_target_angle_deg"),
        "robot_lateral_offset_m": draw.get("robot_lateral_offset_m"),
        "robot_yaw_error_deg": draw.get("robot_yaw_error_deg"),
        "robot_ball_separation_m": draw.get("robot_ball_separation_m"),
        "target_layout_json": str(verdict.get("target_layout_json", "")),
    }


def summarize_runs(*, campaign_id: str, artifacts: list[str]) -> dict[str, Any]:
    clean_campaign_id = campaign_id.strip() or f"live_dashboard_random_fetch_uat_{current_utc_stamp()}"
    verdict_paths = _mission_verdict_paths(artifacts)
    runs = [analyze_verdict(path) for path in verdict_paths]
    pass_count = sum(1 for run in runs if bool(run.get("pass", False)))
    clean_count = sum(1 for run in runs if run.get("contact_quality") == "clean")
    flagged_count = sum(1 for run in runs if run.get("contact_quality") == "flagged")
    fail_count = len(runs) - pass_count
    if fail_count:
        interpretation = "visual_uat_failures_controller_stage_backlog_not_promotion_evidence"
    elif flagged_count:
        interpretation = "delivery_passed_with_contact_quality_flags_stage_supervision_needed"
    else:
        interpretation = "clean_visual_delivery_no_new_stage_supervision_signal"
    summary = {
        "generated_utc": utc_now(),
        "type": ANALYZER_KIND,
        "campaign_id": clean_campaign_id,
        "artifact_count": len(runs),
        "pass": bool(runs and fail_count == 0),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "clean_contact_pass_count": clean_count,
        "flagged_contact_pass_count": flagged_count,
        "interpretation": interpretation,
        "promotion_evidence": False,
        "runs": runs,
    }
    output_root = _output_root(clean_campaign_id)
    ensure_dir(output_root)
    write_json(output_root / "random_fetch_uat_summary.json", summary)
    write_scorecard(output_root / "scorecard.md", summary)
    return summary


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    lines = [
        "# Dashboard Random Fetch UAT Analyzer",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- artifact_count: `{summary.get('artifact_count', 0)}`",
        f"- pass/fail: `{summary.get('pass_count', 0)}/{summary.get('fail_count', 0)}`",
        f"- clean/flagged contact passes: `{summary.get('clean_contact_pass_count', 0)}/{summary.get('flagged_contact_pass_count', 0)}`",
        f"- interpretation: `{summary.get('interpretation', '')}`",
        f"- promotion_evidence: `{bool(summary.get('promotion_evidence', False))}`",
        "",
        "## Runs",
        "",
    ]
    for index, run in enumerate(summary.get("runs", []) or [], start=1):
        if not isinstance(run, dict):
            continue
        flags = ",".join(run.get("flags", []) or []) or "none"
        labels = ",".join(run.get("stage_labels", []) or []) or "none"
        lines.append(
            f"- run `{index}` seed=`{run.get('seed', '')}` profile=`{run.get('random_profile', '')}` "
            f"pass=`{bool(run.get('pass', False))}` quality=`{run.get('contact_quality', '')}` "
            f"closest=`{float(run.get('closest_approach_distance_m', 0.0) or 0.0):.3f}` "
            f"distance=`{float(run.get('ball_target_distance_m', 0.0) or 0.0):.3f}` "
            f"angle=`{float(run.get('ball_target_angle_deg', 0.0) or 0.0):.2f}` "
            f"lat=`{float(run.get('robot_lateral_offset_m', 0.0) or 0.0):.3f}` "
            f"yaw_error=`{float(run.get('robot_yaw_error_deg', 0.0) or 0.0):.2f}` "
            f"stages=`{labels}` flags=`{flags}` "
            f"artifact=`{run.get('artifact_dir', '')}`"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    if not args.artifact:
        raise SystemExit("At least one --artifact path is required.")
    summary = summarize_runs(campaign_id=args.campaign_id, artifacts=list(args.artifact))
    summary_path = _output_root(str(summary.get("campaign_id", ""))) / "random_fetch_uat_summary.json"
    print(f"DASHBOARD_RANDOM_FETCH_UAT_SUMMARY={summary_path}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
