#!/usr/bin/env python3
"""Summarize planner-routed fetch UAT evidence."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
ANALYZER_KIND = "fetch_planner_route_uat_analyzer"
ROUTE_FETCH_READY = "fetch_ready_local"
ROUTE_NAV2_REPOSITION = "nav2_reposition_first"
ROUTE_SCAN_OR_PERCEIVE = "scan_or_perceive_first"
ROUTE_RECOVERY_OR_REAIM = "recovery_or_reaim"
ROUTE_NO_GO = "ambiguous_or_unsafe_no_go"
ROUTE_LABELS = (
    ROUTE_FETCH_READY,
    ROUTE_NAV2_REPOSITION,
    ROUTE_SCAN_OR_PERCEIVE,
    ROUTE_RECOVERY_OR_REAIM,
    ROUTE_NO_GO,
)
EXECUTABLE_FETCH_ROUTES = (ROUTE_FETCH_READY, ROUTE_NAV2_REPOSITION, ROUTE_RECOVERY_OR_REAIM)
PLANNER_ONLY_ROUTES = (ROUTE_SCAN_OR_PERCEIVE, ROUTE_NO_GO)


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
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def artifact_link(path: str) -> str:
    text = str(path or "").replace("\\", "/")
    if text.startswith("artifacts/session/"):
        return f"[summary](/{text})"
    return text


def finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def pick_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def list_value(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def summarize_planner_gate(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    if not payload:
        return {}
    route_counts = payload.get("route_counts", {}) if isinstance(payload.get("route_counts"), dict) else {}
    expected_counts = (
        payload.get("expected_route_counts", {}) if isinstance(payload.get("expected_route_counts"), dict) else {}
    )
    total_count = int(payload.get("random_cases", 0) or payload.get("pass_count", 0) or 0)
    return {
        "campaign_id": str(payload.get("campaign_id", "") or ""),
        "path": artifact_display_path(path),
        "pass": bool(payload.get("pass", False)),
        "pass_count": int(payload.get("pass_count", 0) or 0),
        "fail_count": int(payload.get("fail_count", 0) or 0),
        "total_count": total_count,
        "wrong_fetch_dispatch_count": int(payload.get("wrong_fetch_dispatch_count", 0) or 0),
        "fetch_dispatch_count": int(payload.get("fetch_dispatch_count", 0) or 0),
        "scene_source": str(payload.get("scene_source", "") or ""),
        "scene_set": str(payload.get("scene_set", "") or ""),
        "seed": payload.get("seed"),
        "route_counts": {str(key): int(value or 0) for key, value in route_counts.items()},
        "expected_route_counts": {str(key): int(value or 0) for key, value in expected_counts.items()},
    }


def summarize_mission(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    if not payload:
        return {}
    runs = list_value(payload.get("runs"))
    first_run = runs[0] if runs and isinstance(runs[0], dict) else {}
    verdict = payload.get("mission_verdict", {}) if isinstance(payload.get("mission_verdict"), dict) else {}
    if not verdict and isinstance(first_run.get("mission_verdict"), dict):
        verdict = first_run["mission_verdict"]
    route = payload.get("planner_route", {}) if isinstance(payload.get("planner_route"), dict) else {}
    if isinstance(verdict.get("planner_route"), dict):
        route = {**route, **verdict["planner_route"]}
    shot = payload.get("shot_outcome", {}) if isinstance(payload.get("shot_outcome"), dict) else {}
    if isinstance(verdict.get("shot_outcome"), dict):
        shot = {**shot, **verdict["shot_outcome"]}
    metrics = (
        payload.get("approach_contact_metrics", {})
        if isinstance(payload.get("approach_contact_metrics"), dict)
        else {}
    )
    if isinstance(verdict.get("approach_contact_metrics"), dict):
        metrics = {**metrics, **verdict["approach_contact_metrics"]}
    route_label = pick_text(
        payload.get("planner_route_label"),
        verdict.get("planner_route_label"),
        first_run.get("planner_route_label"),
        route.get("planner_route_label"),
        route.get("route_label"),
    )
    route_executor = pick_text(
        payload.get("route_executor"),
        verdict.get("route_executor"),
        first_run.get("route_executor"),
        route.get("route_executor"),
        route.get("executor"),
    )
    closest = finite_float(
        payload.get(
            "closest_approach_distance_m",
            verdict.get("closest_approach_distance_m", shot.get("closest_approach_distance_m")),
        )
    )
    session_id = pick_text(verdict.get("session_id"), first_run.get("session_id"), payload.get("session_id"))
    if not session_id:
        parts = path.parts
        if "artifacts" in parts and "session" in parts:
            session_index = parts.index("session")
            if len(parts) > session_index + 1:
                session_id = parts[session_index + 1]
    flags = [str(item) for item in list_value(metrics.get("flags"))]
    first_flags = [str(item) for item in list_value(metrics.get("first_contact_quality_flags"))]
    delivery_pass = bool(
        payload.get("fetch_to_pose_pass", verdict.get("fetch_to_pose_pass", first_run.get("fetch_to_pose_pass", False)))
    )
    first_contact_blocker_flags = {
        "missing_first_contact",
        "first_contact_ball_lateral_error",
        "first_contact_trajectory_angle_error",
    }
    severe_first_flags = [flag for flag in first_flags if flag in first_contact_blocker_flags]
    if severe_first_flags or not delivery_pass:
        contact_quality = "blocker"
    elif first_flags or flags:
        contact_quality = "watch"
    else:
        contact_quality = "clean"
    return {
        "session_id": session_id,
        "path": artifact_display_path(path),
        "route_label": route_label,
        "route_executor": route_executor,
        "fetch_to_pose_pass": delivery_pass,
        "mission_completed_pass": bool(
            payload.get("mission_completed_pass", verdict.get("mission_completed_pass", delivery_pass))
        ),
        "closest_approach_distance_m": round(closest, 6) if closest is not None else None,
        "outcome_reason": pick_text(payload.get("reason"), verdict.get("reason"), shot.get("reason")),
        "contact_quality": contact_quality,
        "contact_flags": flags,
        "first_contact_quality_flags": first_flags,
        "first_contact_blocker_flags": severe_first_flags,
        "first_contact_t_s": metrics.get("first_contact_t_s"),
        "first_contact_quality_pass": metrics.get("first_contact_quality_pass"),
        "stable_contact_approach_pass": metrics.get("stable_contact_approach_pass"),
        "model_provenance_valid": bool(
            payload.get("model_provenance_valid", verdict.get("model_provenance_valid", False))
            or (
                isinstance(payload.get("model_provenance"), dict)
                and bool(payload["model_provenance"].get("model_provenance_valid", False))
            )
            or (
                isinstance(verdict.get("model_provenance"), dict)
                and bool(verdict["model_provenance"].get("model_provenance_valid", False))
            )
        ),
        "visual_review_required": True,
    }


def summarize_visual_package(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    if not payload:
        return {}
    recoveries = list_value(payload.get("video_recovery"))
    recovery_attempt_count = sum(1 for item in recoveries if isinstance(item, dict) and item.get("attempted"))
    recovery_ok_count = sum(1 for item in recoveries if isinstance(item, dict) and item.get("ok"))
    return {
        "campaign_id": str(payload.get("campaign_id", "") or ""),
        "path": artifact_display_path(path),
        "scorecard_path": str(payload.get("scorecard_path", "") or ""),
        "pass": bool(payload.get("pass", False)),
        "mobile_watchable": bool(payload.get("mobile_watchable", False)),
        "onboard_camera_watchable": bool(payload.get("onboard_camera_watchable", False)),
        "visual_confirmation_seen": bool(payload.get("visual_confirmation_seen", False)),
        "local_fetch_visual_confirmed": bool(payload.get("local_fetch_visual_confirmed", False)),
        "milestone_interpretation": str(payload.get("milestone_interpretation", "") or ""),
        "promotion_evidence": bool(payload.get("promotion_evidence", False)),
        "warnings": [str(item) for item in list_value(payload.get("warnings"))],
        "video_recovery_count": len(recoveries),
        "video_recovery_attempt_count": recovery_attempt_count,
        "video_recovery_ok_count": recovery_ok_count,
        "video_count": len(list_value(payload.get("videos"))),
    }


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    planner_gates = [summarize_planner_gate(resolve_path(path)) for path in args.planner_summary]
    planner_gates = [item for item in planner_gates if item]
    missions = [summarize_mission(resolve_path(path)) for path in args.mission_summary]
    missions = [item for item in missions if item]
    visual_packages = [summarize_visual_package(resolve_path(path)) for path in args.visual_package_summary]
    visual_packages = [item for item in visual_packages if item]

    gate_green = bool(planner_gates) and all(
        gate.get("pass") and int(gate.get("wrong_fetch_dispatch_count", 0) or 0) == 0 for gate in planner_gates
    )
    route_counts: dict[str, int] = {route: 0 for route in ROUTE_LABELS}
    for gate in planner_gates:
        for route, count in (gate.get("route_counts", {}) or {}).items():
            route_counts[str(route)] = route_counts.get(str(route), 0) + int(count or 0)
    live_by_route = {
        route: [mission for mission in missions if mission.get("route_label") == route]
        for route in ROUTE_LABELS
    }
    route_rows = []
    for route in ROUTE_LABELS:
        live_rows = live_by_route.get(route, [])
        pass_count = sum(1 for item in live_rows if item.get("fetch_to_pose_pass"))
        clean_count = sum(1 for item in live_rows if item.get("contact_quality") == "clean")
        watch_count = sum(1 for item in live_rows if item.get("contact_quality") == "watch")
        blocker_count = sum(1 for item in live_rows if item.get("contact_quality") == "blocker")
        route_rows.append(
            {
                "route_label": route,
                "planner_count": int(route_counts.get(route, 0) or 0),
                "live_count": len(live_rows),
                "live_pass_count": pass_count,
                "live_clean_count": clean_count,
                "live_watch_count": watch_count,
                "live_blocker_count": blocker_count,
                "coverage_status": (
                    "live_executable_passed"
                    if route in EXECUTABLE_FETCH_ROUTES and pass_count > 0
                    else "planner_only_classified"
                    if route in PLANNER_ONLY_ROUTES and int(route_counts.get(route, 0) or 0) > 0
                    else "missing_live_executable"
                    if route in EXECUTABLE_FETCH_ROUTES
                    else "missing_planner_coverage"
                ),
            }
        )
    executable_green = all(
        any(item.get("fetch_to_pose_pass") for item in live_by_route.get(route, []))
        for route in EXECUTABLE_FETCH_ROUTES
    )
    planner_only_green = all(int(route_counts.get(route, 0) or 0) > 0 for route in PLANNER_ONLY_ROUTES)
    visual_green = bool(visual_packages) and all(
        item.get("pass") and item.get("mobile_watchable") and item.get("onboard_camera_watchable")
        for item in visual_packages
    )
    first_contact_blockers = sum(1 for mission in missions if mission.get("contact_quality") == "blocker")
    contact_watch_count = sum(1 for mission in missions if mission.get("contact_quality") == "watch")
    contact_quality_status = "blocker" if first_contact_blockers else "watch" if contact_watch_count else "clean"
    green = bool(gate_green and executable_green and planner_only_green and visual_green and first_contact_blockers == 0)
    return {
        "type": ANALYZER_KIND,
        "campaign_id": str(args.campaign_id or ""),
        "generated_utc": utc_now(),
        "pass": green,
        "promotion_evidence": False,
        "milestone_interpretation": (
            "randomized_route_owner_visual_uat_green" if green else "randomized_route_owner_visual_uat_incomplete"
        ),
        "planner_gate_green": gate_green,
        "executable_route_green": executable_green,
        "planner_only_route_green": planner_only_green,
        "visual_package_green": visual_green,
        "contact_quality_status": contact_quality_status,
        "contact_watch_count": contact_watch_count,
        "first_contact_blocker_count": first_contact_blockers,
        "route_rows": route_rows,
        "planner_gates": planner_gates,
        "missions": missions,
        "visual_packages": visual_packages,
    }


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Fetch Planner Route UAT Scorecard",
        "",
        f"- Campaign: `{summary.get('campaign_id', '')}`",
        f"- Pass: `{summary.get('pass', False)}`",
        f"- Interpretation: `{summary.get('milestone_interpretation', '')}`",
        f"- Promotion evidence: `{summary.get('promotion_evidence', False)}`",
        f"- Contact quality: `{summary.get('contact_quality_status', '')}`",
        f"- Contact watches: `{summary.get('contact_watch_count', 0)}`",
        f"- First-contact blockers: `{summary.get('first_contact_blocker_count', 0)}`",
        "",
        "## Route Coverage",
    ]
    for row in list_value(summary.get("route_rows")):
        lines.append(
            f"- route=`{row.get('route_label', '')}` planner=`{row.get('planner_count', 0)}` "
            f"live=`{row.get('live_count', 0)}` pass=`{row.get('live_pass_count', 0)}` "
            f"clean=`{row.get('live_clean_count', 0)}` watch=`{row.get('live_watch_count', 0)}` "
            f"blocker=`{row.get('live_blocker_count', 0)}` status=`{row.get('coverage_status', '')}`"
        )
    lines.extend(["", "## Planner Gates"])
    for gate in list_value(summary.get("planner_gates")):
        lines.append(
            f"- `{gate.get('campaign_id', '')}` pass=`{gate.get('pass', False)}` "
            f"routes=`{gate.get('pass_count', 0)}/{gate.get('total_count', 0)}` "
            f"wrong_fetch=`{gate.get('wrong_fetch_dispatch_count', 0)}` "
            f"source=`{gate.get('scene_source', '')}` seed=`{gate.get('seed', '')}` "
            f"{artifact_link(str(gate.get('path', '') or ''))}"
        )
    lines.extend(["", "## Live Missions"])
    for mission in list_value(summary.get("missions")):
        closest = mission.get("closest_approach_distance_m")
        closest_text = f"{float(closest):.3f}m" if isinstance(closest, (int, float)) else ""
        flags = ",".join(mission.get("contact_flags", []) or [])
        first_flags = ",".join(mission.get("first_contact_quality_flags", []) or [])
        lines.append(
            f"- route=`{mission.get('route_label', '')}` session=`{mission.get('session_id', '')}` "
            f"pass=`{mission.get('fetch_to_pose_pass', False)}` closest=`{closest_text}` "
            f"quality=`{mission.get('contact_quality', '')}` flags=`{flags}` "
            f"first_flags=`{first_flags}` {artifact_link(str(mission.get('path', '') or ''))}"
        )
    lines.extend(["", "## Visual Packages"])
    for package in list_value(summary.get("visual_packages")):
        scorecard = str(package.get("scorecard_path", "") or package.get("path", "") or "")
        lines.append(
            f"- `{package.get('campaign_id', '')}` pass=`{package.get('pass', False)}` "
            f"mobile=`{package.get('mobile_watchable', False)}` "
            f"onboard=`{package.get('onboard_camera_watchable', False)}` "
            f"recoveries=`{package.get('video_recovery_ok_count', 0)}/{package.get('video_recovery_count', 0)}` "
            f"warnings=`{','.join(package.get('warnings', []) or [])}` {artifact_link(scorecard)}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze planner-routed fetch UAT evidence.")
    parser.add_argument("--campaign-id", default=f"live_fetch_planner_route_uat_analyzer_{current_utc_stamp()}")
    parser.add_argument("--planner-summary", action="append", default=[])
    parser.add_argument("--mission-summary", action="append", default=[])
    parser.add_argument("--visual-package-summary", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / ANALYZER_KIND)
    summary = build_summary(args)
    summary_path = root / "route_uat_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["summary_path"] = artifact_display_path(summary_path)
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_PLANNER_ROUTE_UAT_ANALYZER_SUMMARY={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
