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
SCOPE_ROUTE_OWNER_VISUAL_UAT = "route_owner_visual_uat"
SCOPE_SAVED_ANCHOR_REPEATABILITY = "saved_anchor_repeatability"
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
SETUP_WATCH_FLAGS = {
    "pre_contact_lateral_error",
    "pre_contact_yaw_error",
    "pre_contact_yaw_oscillation",
}
CONTACT_WATCH_FLAGS = {
    "missing_contact_trace",
    "missing_first_contact_motion",
    "ball_lateral_knock_away",
    "contact_trajectory_angle_error",
}
FIRST_CONTACT_BLOCKER_FLAGS = {
    "missing_first_contact",
    "first_contact_ball_lateral_error",
}


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
    results = payload.get("results", []) if isinstance(payload.get("results"), list) else []
    scene_ids = [
        str(row.get("scene_id", "") or "").strip()
        for row in results
        if isinstance(row, dict) and str(row.get("scene_id", "") or "").strip()
    ]
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
        "guard_agreement_count": int(payload.get("guard_agreement_count", 0) or 0),
        "guard_disagreement_count": int(payload.get("guard_disagreement_count", 0) or 0),
        "provider_status_counts": (
            {str(key): int(value or 0) for key, value in payload.get("provider_status_counts", {}).items()}
            if isinstance(payload.get("provider_status_counts"), dict)
            else {}
        ),
        "planner_mode_effective_counts": (
            {str(key): int(value or 0) for key, value in payload.get("planner_mode_effective_counts", {}).items()}
            if isinstance(payload.get("planner_mode_effective_counts"), dict)
            else {}
        ),
        "llm_shadow_provider_ok_count": int(payload.get("llm_shadow_provider_ok_count", 0) or 0),
        "llm_shadow_ready": bool(payload.get("llm_shadow_ready", False)),
        "scene_source": str(payload.get("scene_source", "") or ""),
        "scene_set": str(payload.get("scene_set", "") or ""),
        "seed": payload.get("seed"),
        "route_counts": {str(key): int(value or 0) for key, value in route_counts.items()},
        "expected_route_counts": {str(key): int(value or 0) for key, value in expected_counts.items()},
        "scene_ids": scene_ids,
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
    random_draw = payload.get("random_draw", {}) if isinstance(payload.get("random_draw"), dict) else {}
    if isinstance(verdict.get("random_draw"), dict):
        random_draw = {**random_draw, **verdict["random_draw"]}
    route_quality = {}
    if isinstance(route.get("route_quality"), dict):
        route_quality = route["route_quality"]
    elif isinstance(random_draw.get("route_quality"), dict):
        route_quality = random_draw["route_quality"]
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
    local_fetch_dispatched = bool(
        payload.get(
            "local_fetch_dispatched",
            verdict.get("local_fetch_dispatched", first_run.get("local_fetch_dispatched", True)),
        )
    )
    planner_route_only_pass = bool(
        payload.get(
            "planner_route_only_pass",
            verdict.get("planner_route_only_pass", first_run.get("planner_route_only_pass", False)),
        )
    )
    planner_route_executed = bool(
        payload.get(
            "planner_route_executed",
            verdict.get("planner_route_executed", first_run.get("planner_route_executed", False)),
        )
    )
    route_execution = (
        payload.get("planner_route_execution", {})
        if isinstance(payload.get("planner_route_execution"), dict)
        else {}
    )
    if isinstance(verdict.get("planner_route_execution"), dict):
        route_execution = {**route_execution, **verdict["planner_route_execution"]}
    planner_route_outcome = pick_text(route_execution.get("outcome"), payload.get("planner_route_outcome"))
    planner_only_route = route_label in PLANNER_ONLY_ROUTES
    planner_only_contract_pass = bool(
        planner_only_route and planner_route_only_pass and not local_fetch_dispatched
    )
    route_contract_pass = bool(planner_only_contract_pass if planner_only_route else delivery_pass)
    setup_watch_flags = [flag for flag in flags if flag in SETUP_WATCH_FLAGS]
    contact_watch_flags = [flag for flag in flags if flag in CONTACT_WATCH_FLAGS]
    contact_watch_flags.extend(
        flag for flag in flags if flag not in SETUP_WATCH_FLAGS and flag not in CONTACT_WATCH_FLAGS
    )
    severe_first_flags = [flag for flag in first_flags if flag in FIRST_CONTACT_BLOCKER_FLAGS]
    if planner_only_contract_pass:
        contact_quality = "clean"
    elif severe_first_flags or not delivery_pass:
        contact_quality = "blocker"
    elif first_flags or contact_watch_flags:
        contact_quality = "watch"
    else:
        contact_quality = "clean"
    setup_quality = "clean" if planner_only_contract_pass else "watch" if setup_watch_flags else "clean"
    execution_quality = (
        "blocker"
        if contact_quality == "blocker"
        else "watch"
        if setup_quality == "watch" or contact_quality == "watch"
        else "clean"
    )
    return {
        "session_id": session_id,
        "path": artifact_display_path(path),
        "route_label": route_label,
        "route_executor": route_executor,
        "route_quality": route_quality,
        "predicted_contact_quality": str(route_quality.get("predicted_contact_quality", "") or ""),
        "predicted_first_contact_risk": str(route_quality.get("predicted_first_contact_risk", "") or ""),
        "route_quality_score": (
            round(float(route_quality.get("quality_score")), 6)
            if finite_float(route_quality.get("quality_score")) is not None
            else None
        ),
        "route_quality_flags": [str(item) for item in list_value(route_quality.get("flags"))],
        "fetch_to_pose_pass": delivery_pass,
        "route_contract_pass": route_contract_pass,
        "planner_only_route": planner_only_route,
        "local_fetch_dispatched": local_fetch_dispatched,
        "planner_route_only_pass": planner_route_only_pass,
        "planner_route_executed": planner_route_executed,
        "planner_route_outcome": planner_route_outcome,
        "mission_completed_pass": bool(
            payload.get("mission_completed_pass", verdict.get("mission_completed_pass", route_contract_pass))
        ),
        "closest_approach_distance_m": round(closest, 6) if closest is not None else None,
        "outcome_reason": pick_text(payload.get("reason"), verdict.get("reason"), shot.get("reason")),
        "execution_quality": execution_quality,
        "setup_quality": setup_quality,
        "contact_quality": contact_quality,
        "contact_flags": flags,
        "setup_watch_flags": setup_watch_flags,
        "contact_watch_flags": contact_watch_flags,
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


def saved_anchor_scene_counts(planner_gates: list[dict[str, Any]], visual_packages: list[dict[str, Any]]) -> dict[str, int]:
    scene_ids: list[str] = []
    for gate in planner_gates:
        for scene_id in list_value(gate.get("scene_ids")):
            text = str(scene_id or "").strip()
            if text and text not in scene_ids:
                scene_ids.append(text)
    counts = {scene_id: 0 for scene_id in scene_ids}
    for package in visual_packages:
        haystack = " ".join(
            [
                str(package.get("campaign_id", "") or ""),
                str(package.get("path", "") or ""),
                str(package.get("scorecard_path", "") or ""),
            ]
        )
        for scene_id in scene_ids:
            if haystack.endswith(scene_id) or f"_{scene_id}" in haystack or f"/{scene_id}" in haystack:
                counts[scene_id] += 1
                break
    return counts


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    evidence_scope = str(getattr(args, "evidence_scope", SCOPE_ROUTE_OWNER_VISUAL_UAT) or SCOPE_ROUTE_OWNER_VISUAL_UAT)
    repeatability_runs_per_anchor = int(getattr(args, "repeatability_runs_per_anchor", 3) or 3)
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
    quality_prediction_counts: dict[str, int] = {}
    first_contact_risk_counts: dict[str, int] = {}
    for mission in missions:
        predicted = str(mission.get("predicted_contact_quality", "") or "missing")
        risk = str(mission.get("predicted_first_contact_risk", "") or "missing")
        quality_prediction_counts[predicted] = quality_prediction_counts.get(predicted, 0) + 1
        first_contact_risk_counts[risk] = first_contact_risk_counts.get(risk, 0) + 1
    route_rows = []
    for route in ROUTE_LABELS:
        live_rows = live_by_route.get(route, [])
        pass_count = sum(1 for item in live_rows if item.get("route_contract_pass"))
        fetch_pass_count = sum(1 for item in live_rows if item.get("fetch_to_pose_pass"))
        route_only_pass_count = sum(1 for item in live_rows if item.get("planner_route_only_pass"))
        clean_count = sum(1 for item in live_rows if item.get("contact_quality") == "clean")
        watch_count = sum(1 for item in live_rows if item.get("contact_quality") == "watch")
        blocker_count = sum(1 for item in live_rows if item.get("contact_quality") == "blocker")
        setup_watch_count = sum(1 for item in live_rows if item.get("setup_quality") == "watch")
        execution_watch_count = sum(1 for item in live_rows if item.get("execution_quality") == "watch")
        predicted_watch_count = sum(1 for item in live_rows if item.get("predicted_contact_quality") == "watch")
        predicted_blocker_count = sum(1 for item in live_rows if item.get("predicted_contact_quality") == "blocker")
        route_rows.append(
            {
                "route_label": route,
                "planner_count": int(route_counts.get(route, 0) or 0),
                "live_count": len(live_rows),
                "live_pass_count": pass_count,
                "live_fetch_pass_count": fetch_pass_count,
                "live_route_only_pass_count": route_only_pass_count,
                "live_clean_count": clean_count,
                "live_watch_count": watch_count,
                "live_blocker_count": blocker_count,
                "live_setup_watch_count": setup_watch_count,
                "live_execution_watch_count": execution_watch_count,
                "predicted_watch_count": predicted_watch_count,
                "predicted_blocker_count": predicted_blocker_count,
                "coverage_status": (
                    "live_executable_passed"
                    if route in EXECUTABLE_FETCH_ROUTES and fetch_pass_count > 0
                    else "planner_only_live_passed"
                    if route in PLANNER_ONLY_ROUTES and live_rows and pass_count == len(live_rows)
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
    planner_only_green = all(
        int(route_counts.get(route, 0) or 0) > 0
        and (
            not live_by_route.get(route)
            or all(item.get("route_contract_pass") for item in live_by_route.get(route, []))
        )
        for route in PLANNER_ONLY_ROUTES
    )
    visual_green = bool(visual_packages) and all(
        item.get("pass") and item.get("mobile_watchable") and item.get("onboard_camera_watchable")
        for item in visual_packages
    )
    mission_green = bool(missions) and all(mission.get("route_contract_pass") for mission in missions)
    first_contact_blockers = sum(1 for mission in missions if mission.get("contact_quality") == "blocker")
    contact_watch_count = sum(1 for mission in missions if mission.get("contact_quality") == "watch")
    setup_watch_count = sum(1 for mission in missions if mission.get("setup_quality") == "watch")
    execution_watch_count = sum(1 for mission in missions if mission.get("execution_quality") == "watch")
    contact_quality_status = "blocker" if first_contact_blockers else "watch" if contact_watch_count else "clean"
    setup_quality_status = "watch" if setup_watch_count else "clean"
    execution_quality_status = (
        "blocker" if first_contact_blockers else "watch" if execution_watch_count else "clean"
    )
    anchor_counts = (
        saved_anchor_scene_counts(planner_gates, visual_packages)
        if evidence_scope == SCOPE_SAVED_ANCHOR_REPEATABILITY
        else {}
    )
    saved_anchor_repeatability_green = bool(
        evidence_scope == SCOPE_SAVED_ANCHOR_REPEATABILITY
        and gate_green
        and mission_green
        and visual_green
        and first_contact_blockers == 0
        and anchor_counts
        and all(count >= repeatability_runs_per_anchor for count in anchor_counts.values())
    )
    route_owner_green = bool(
        evidence_scope == SCOPE_ROUTE_OWNER_VISUAL_UAT
        and gate_green
        and executable_green
        and planner_only_green
        and visual_green
        and first_contact_blockers == 0
    )
    green = bool(saved_anchor_repeatability_green or route_owner_green)
    milestone_interpretation = (
        "saved_anchor_repeatability_green"
        if saved_anchor_repeatability_green
        else "saved_anchor_repeatability_incomplete"
        if evidence_scope == SCOPE_SAVED_ANCHOR_REPEATABILITY
        else "randomized_route_owner_visual_uat_green"
        if green
        else "randomized_route_owner_visual_uat_incomplete"
    )
    return {
        "type": ANALYZER_KIND,
        "campaign_id": str(args.campaign_id or ""),
        "generated_utc": utc_now(),
        "evidence_scope": evidence_scope,
        "repeatability_runs_per_anchor": repeatability_runs_per_anchor,
        "pass": green,
        "promotion_evidence": False,
        "milestone_interpretation": milestone_interpretation,
        "planner_gate_green": gate_green,
        "executable_route_green": executable_green,
        "planner_only_route_green": planner_only_green,
        "mission_green": mission_green,
        "visual_package_green": visual_green,
        "saved_anchor_repeatability_green": saved_anchor_repeatability_green,
        "saved_anchor_scene_counts": anchor_counts,
        "execution_quality_status": execution_quality_status,
        "execution_watch_count": execution_watch_count,
        "setup_quality_status": setup_quality_status,
        "setup_watch_count": setup_watch_count,
        "contact_quality_status": contact_quality_status,
        "contact_watch_count": contact_watch_count,
        "first_contact_blocker_count": first_contact_blockers,
        "quality_prediction_counts": quality_prediction_counts,
        "first_contact_risk_counts": first_contact_risk_counts,
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
        f"- Evidence scope: `{summary.get('evidence_scope', '')}`",
        f"- Pass: `{summary.get('pass', False)}`",
        f"- Interpretation: `{summary.get('milestone_interpretation', '')}`",
        f"- Promotion evidence: `{summary.get('promotion_evidence', False)}`",
        f"- Mission green: `{summary.get('mission_green', False)}`",
        f"- Visual package green: `{summary.get('visual_package_green', False)}`",
        f"- Execution quality: `{summary.get('execution_quality_status', '')}`",
        f"- Execution watches: `{summary.get('execution_watch_count', 0)}`",
        f"- Setup quality: `{summary.get('setup_quality_status', '')}`",
        f"- Setup watches: `{summary.get('setup_watch_count', 0)}`",
        f"- Contact quality: `{summary.get('contact_quality_status', '')}`",
        f"- Contact watches: `{summary.get('contact_watch_count', 0)}`",
        f"- First-contact blockers: `{summary.get('first_contact_blocker_count', 0)}`",
        f"- Predicted contact quality: `{summary.get('quality_prediction_counts', {})}`",
        f"- Predicted first-contact risk: `{summary.get('first_contact_risk_counts', {})}`",
        "",
        "## Route Coverage",
    ]
    if summary.get("evidence_scope") == SCOPE_SAVED_ANCHOR_REPEATABILITY:
        lines[9:9] = [
            f"- Saved-anchor repeatability green: `{summary.get('saved_anchor_repeatability_green', False)}`",
            f"- Repeatability runs per anchor: `{summary.get('repeatability_runs_per_anchor', 0)}`",
            f"- Saved-anchor scene counts: `{summary.get('saved_anchor_scene_counts', {})}`",
        ]
    for row in list_value(summary.get("route_rows")):
        lines.append(
            f"- route=`{row.get('route_label', '')}` planner=`{row.get('planner_count', 0)}` "
            f"live=`{row.get('live_count', 0)}` pass=`{row.get('live_pass_count', 0)}` "
            f"fetch_pass=`{row.get('live_fetch_pass_count', 0)}` "
            f"route_only_pass=`{row.get('live_route_only_pass_count', 0)}` "
            f"clean=`{row.get('live_clean_count', 0)}` watch=`{row.get('live_watch_count', 0)}` "
            f"setup_watch=`{row.get('live_setup_watch_count', 0)}` "
            f"exec_watch=`{row.get('live_execution_watch_count', 0)}` "
            f"pred_watch=`{row.get('predicted_watch_count', 0)}` "
            f"pred_blocker=`{row.get('predicted_blocker_count', 0)}` "
            f"blocker=`{row.get('live_blocker_count', 0)}` status=`{row.get('coverage_status', '')}`"
        )
    lines.extend(["", "## Planner Gates"])
    for gate in list_value(summary.get("planner_gates")):
        lines.append(
            f"- `{gate.get('campaign_id', '')}` pass=`{gate.get('pass', False)}` "
            f"routes=`{gate.get('pass_count', 0)}/{gate.get('total_count', 0)}` "
            f"wrong_fetch=`{gate.get('wrong_fetch_dispatch_count', 0)}` "
            f"guard_agree=`{gate.get('guard_agreement_count', 0)}/{gate.get('total_count', 0)}` "
            f"provider=`{gate.get('provider_status_counts', {})}` "
            f"llm_shadow_ready=`{gate.get('llm_shadow_ready', False)}` "
            f"source=`{gate.get('scene_source', '')}` seed=`{gate.get('seed', '')}` "
            f"{artifact_link(str(gate.get('path', '') or ''))}"
        )
    lines.extend(["", "## Live Missions"])
    for mission in list_value(summary.get("missions")):
        closest = mission.get("closest_approach_distance_m")
        closest_text = f"{float(closest):.3f}m" if isinstance(closest, (int, float)) else ""
        flags = ",".join(mission.get("contact_flags", []) or [])
        setup_flags = ",".join(mission.get("setup_watch_flags", []) or [])
        contact_flags = ",".join(mission.get("contact_watch_flags", []) or [])
        first_flags = ",".join(mission.get("first_contact_quality_flags", []) or [])
        lines.append(
            f"- route=`{mission.get('route_label', '')}` session=`{mission.get('session_id', '')}` "
            f"contract_pass=`{mission.get('route_contract_pass', False)}` "
            f"fetch_pass=`{mission.get('fetch_to_pose_pass', False)}` "
            f"route_only_pass=`{mission.get('planner_route_only_pass', False)}` "
            f"local_fetch=`{mission.get('local_fetch_dispatched', True)}` closest=`{closest_text}` "
            f"predicted=`{mission.get('predicted_contact_quality', '')}` "
            f"risk=`{mission.get('predicted_first_contact_risk', '')}` "
            f"score=`{mission.get('route_quality_score', '')}` "
            f"exec=`{mission.get('execution_quality', '')}` setup=`{mission.get('setup_quality', '')}` "
            f"contact=`{mission.get('contact_quality', '')}` flags=`{flags}` "
            f"setup_flags=`{setup_flags}` contact_flags=`{contact_flags}` "
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
    parser.add_argument(
        "--evidence-scope",
        choices=(SCOPE_ROUTE_OWNER_VISUAL_UAT, SCOPE_SAVED_ANCHOR_REPEATABILITY),
        default=SCOPE_ROUTE_OWNER_VISUAL_UAT,
    )
    parser.add_argument("--repeatability-runs-per-anchor", type=int, default=3)
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
