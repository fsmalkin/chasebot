#!/usr/bin/env python3
"""Build the planner-routed fetch moonshot regression manifest."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
MANIFEST_KIND = "fetch_moonshot_regression_manifest"
DEFAULT_REGRESSION_SET_ID = "planner_routed_generalized_fetch_v1_20260604"
DEFAULT_DELIVERY_RADIUS_M = 0.300

DEFAULT_SAVED_ANCHOR_SUMMARY = (
    "artifacts/session/analysis_planner_saved_anchor_repeat3x_20260604/"
    "fetch_planner_route_uat_analyzer/route_uat_summary.json"
)
DEFAULT_SETUP_CONTACT_AUDIT = (
    "artifacts/session/audit_fetch_setup_contact_repair_saved_anchor_3x_20260602/"
    "fetch_saved_anchor_setup_contact_audit/audit_summary.json"
)
DEFAULT_SEEDED_GATES = (
    (
        "seed20260627",
        "artifacts/session/live_planner_seeded_generalization_gate_full_visual_fix_20260604/"
        "fetch_planner_seeded_generalization_gate/gate_summary.json",
    ),
    (
        "seed20260628",
        "artifacts/session/live_planner_seeded_generalization_gate_seed20260628_full_visual_rerun_20260604/"
        "fetch_planner_seeded_generalization_gate/gate_summary.json",
    ),
    (
        "seed20260629",
        "artifacts/session/live_planner_seeded_generalization_gate_seed20260629_boundary_repair_full_visual_20260604/"
        "fetch_planner_seeded_generalization_gate/gate_summary.json",
    ),
    (
        "seed20260630",
        "artifacts/session/live_planner_seeded_generalization_gate_seed20260630_recovery_crawl_full_20260604/"
        "fetch_planner_seeded_generalization_gate/gate_summary.json",
    ),
    (
        "seed20260631",
        "artifacts/session/live_planner_seeded_generalization_gate_seed20260631_breadth_20260604/"
        "fetch_planner_seeded_generalization_gate/gate_summary.json",
    ),
    (
        "seed20260632",
        "artifacts/session/live_planner_seeded_generalization_gate_seed20260632_breadth_20260604/"
        "fetch_planner_seeded_generalization_gate/gate_summary.json",
    ),
    (
        "seed20260633",
        "artifacts/session/live_planner_seeded_generalization_gate_seed20260633_breadth_20260604/"
        "fetch_planner_seeded_generalization_gate/gate_summary.json",
    ),
)
DEFAULT_BOUNDARY_REPLAY_SUMMARY = (
    "artifacts/session/live_planner_seeded_generalization_gate_seed20260629_boundary_repair_full_visual_20260604_replay/"
    "fetch_planner_route_replay_batch/batch_summary.json"
)
DEFAULT_BOUNDARY_ROWS = (
    (
        "seed20260629_scene01_nav2_reposition_first",
        "nav2_reposition_first",
        "clean_pre_contact_nav2_abort_fallback",
    ),
    (
        "seed20260629_scene05_recovery_or_reaim",
        "recovery_or_reaim",
        "high_debt_recovery_duration_window",
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_path(raw_path: str | Path) -> Path:
    path = Path(str(raw_path or "").strip())
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def artifact_display_path(path: Path | str) -> str:
    path = resolve_path(path)
    try:
        return str(path.relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def read_json(path: Path) -> tuple[dict[str, Any], list[str]]:
    if not path.is_file():
        return {}, [f"missing_json:{artifact_display_path(path)}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive failure label
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


def int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def float_value(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def bool_issue(issues: list[str], condition: bool, issue: str) -> None:
    if not condition:
        issues.append(issue)


def parse_label_path(spec: str) -> tuple[str, str]:
    text = str(spec or "").strip()
    if "=" in text:
        label, path = text.split("=", 1)
        return label.strip() or Path(path).stem, path.strip()
    return Path(text).stem, text


def parse_boundary_spec(spec: str) -> tuple[str, str, str]:
    text = str(spec or "").strip()
    if "=" in text:
        scene_id, rest = text.split("=", 1)
        parts = [part.strip() for part in rest.split(":")]
        route = parts[0] if parts else ""
        note = parts[1] if len(parts) > 1 else ""
        return scene_id.strip(), route, note
    parts = [part.strip() for part in text.split(":")]
    scene_id = parts[0] if parts else ""
    route = parts[1] if len(parts) > 1 else ""
    note = parts[2] if len(parts) > 2 else ""
    return scene_id, route, note


def seeded_gate_specs(raw_specs: list[str]) -> list[tuple[str, str]]:
    if not raw_specs:
        return list(DEFAULT_SEEDED_GATES)
    return [parse_label_path(spec) for spec in raw_specs]


def boundary_specs(raw_specs: list[str]) -> list[tuple[str, str, str]]:
    if not raw_specs:
        return list(DEFAULT_BOUNDARY_ROWS)
    return [parse_boundary_spec(spec) for spec in raw_specs]


def child_payload(parent: dict[str, Any], key: str) -> tuple[dict[str, Any], str, list[str]]:
    raw_path = str(parent.get(key, "") or "").strip()
    if not raw_path:
        return {}, "", [f"missing_child_path:{key}"]
    path = resolve_path(raw_path)
    payload, issues = read_json(path)
    return payload, artifact_display_path(path), issues


def evaluate_saved_anchor_summary(path_text: str) -> dict[str, Any]:
    path = resolve_path(path_text)
    payload, issues = read_json(path)
    counts = dict_value(payload.get("saved_anchor_scene_counts"))
    required = {
        "saved_anchor_zero": 3,
        "saved_anchor_left05": 3,
        "saved_anchor_right05": 3,
    }
    for anchor, minimum in required.items():
        bool_issue(issues, int_value(counts.get(anchor)) >= minimum, f"saved_anchor_count_below_{minimum}:{anchor}")
    bool_issue(issues, bool(payload.get("pass", False)), "saved_anchor_summary_not_pass")
    bool_issue(issues, bool(payload.get("saved_anchor_repeatability_green", False)), "saved_anchor_repeatability_not_green")
    bool_issue(issues, str(payload.get("evidence_scope", "")) == "saved_anchor_repeatability", "saved_anchor_scope_mismatch")
    bool_issue(issues, bool(payload.get("mission_green", False)), "saved_anchor_missions_not_green")
    bool_issue(issues, bool(payload.get("visual_package_green", False)), "saved_anchor_visual_packages_not_green")
    bool_issue(issues, str(payload.get("execution_quality_status", "")) == "clean", "saved_anchor_execution_not_clean")
    bool_issue(issues, str(payload.get("setup_quality_status", "")) == "clean", "saved_anchor_setup_not_clean")
    bool_issue(issues, str(payload.get("contact_quality_status", "")) == "clean", "saved_anchor_contact_not_clean")
    bool_issue(issues, int_value(payload.get("first_contact_blocker_count")) == 0, "saved_anchor_first_contact_blockers")
    return {
        "path": artifact_display_path(path),
        "pass": not issues,
        "issues": issues,
        "saved_anchor_scene_counts": counts,
        "mission_count": len(list_value(payload.get("missions"))),
        "visual_package_count": len(list_value(payload.get("visual_packages"))),
        "closest_approach_range_m": closest_range(list_value(payload.get("missions"))),
        "milestone_interpretation": str(payload.get("milestone_interpretation", "")),
    }


def evaluate_setup_contact_audit(path_text: str) -> dict[str, Any]:
    path = resolve_path(path_text)
    payload, issues = read_json(path)
    for key in (
        "setup_contact_blocker_count",
        "setup_capture_blocker_count",
        "push_coast_blocker_count",
        "first_contact_blocker_count",
        "invalid_geometry_count",
        "invalid_model_provenance_count",
    ):
        bool_issue(issues, int_value(payload.get(key)) == 0, f"audit_nonzero:{key}")
    bool_issue(issues, bool(payload.get("stage_quality_green", False)), "audit_stage_quality_not_green")
    bool_issue(issues, int_value(payload.get("pass_count")) >= 3, "audit_pass_count_below_3")
    return {
        "path": artifact_display_path(path),
        "pass": not issues,
        "issues": issues,
        "stage_quality_green": bool(payload.get("stage_quality_green", False)),
        "pass_count": int_value(payload.get("pass_count")),
        "overall_interpretation": str(payload.get("overall_interpretation", "")),
    }


def closest_range(missions: list[Any]) -> dict[str, float] | dict[str, None]:
    values: list[float] = []
    for mission in missions:
        if not isinstance(mission, dict):
            continue
        closest = float_value(mission.get("closest_approach_distance_m"))
        if closest is not None:
            values.append(closest)
    if not values:
        return {"min": None, "max": None}
    return {"min": min(values), "max": max(values)}


def evaluate_seeded_gate(label: str, path_text: str, *, min_random_cases: int) -> dict[str, Any]:
    path = resolve_path(path_text)
    payload, issues = read_json(path)
    planner_summary = dict_value(payload.get("planner_summary"))
    replay_summary = dict_value(payload.get("replay_summary"))
    analyzer_summary = dict_value(payload.get("analyzer_summary"))
    expected_count = int_value(payload.get("expected_executable_count")) or 6
    selected_count = int_value(replay_summary.get("selected_count"))
    random_cases = int_value(payload.get("random_cases"))

    planner_child, planner_child_path, planner_child_issues = child_payload(payload, "planner_summary_path")
    replay_child, replay_child_path, replay_child_issues = child_payload(payload, "replay_summary_path")
    analyzer_child, analyzer_child_path, analyzer_child_issues = child_payload(payload, "analyzer_summary_path")
    issues.extend(planner_child_issues)
    issues.extend(replay_child_issues)
    issues.extend(analyzer_child_issues)

    bool_issue(issues, bool(payload.get("pass", False)), "seeded_gate_not_pass")
    bool_issue(issues, bool(payload.get("promotion_evidence", False)), "seeded_gate_not_promotion_evidence")
    bool_issue(issues, not bool(payload.get("dry_run", False)), "seeded_gate_is_dry_run")
    bool_issue(issues, bool(payload.get("fresh_dashboard_session_per_run", False)), "seeded_gate_not_fresh_session")
    bool_issue(issues, bool(payload.get("planner_gate_pass", False)), "seeded_gate_planner_child_not_pass")
    bool_issue(issues, bool(payload.get("replay_pass", False)), "seeded_gate_replay_child_not_pass")
    bool_issue(issues, bool(payload.get("analyzer_pass", False)), "seeded_gate_analyzer_child_not_pass")
    bool_issue(issues, random_cases >= min_random_cases, f"seeded_gate_random_cases_below_{min_random_cases}")
    bool_issue(issues, int_value(planner_summary.get("pass_count")) >= random_cases, "seeded_gate_planner_pass_count_below_random_cases")
    bool_issue(issues, int_value(planner_summary.get("wrong_fetch_dispatch_count")) == 0, "seeded_gate_wrong_fetch_dispatch")
    bool_issue(issues, selected_count >= expected_count, "seeded_gate_selected_below_expected")
    bool_issue(issues, int_value(replay_summary.get("mission_pass_count")) == selected_count, "seeded_gate_mission_pass_count_mismatch")
    bool_issue(issues, int_value(replay_summary.get("mission_fail_count")) == 0, "seeded_gate_mission_fail_count")
    bool_issue(issues, int_value(replay_summary.get("visual_package_pass_count")) == selected_count, "seeded_gate_visual_package_mismatch")
    bool_issue(issues, str(analyzer_summary.get("execution_quality_status", "")) == "clean", "seeded_gate_execution_not_clean")
    bool_issue(issues, str(analyzer_summary.get("setup_quality_status", "")) == "clean", "seeded_gate_setup_not_clean")
    bool_issue(issues, str(analyzer_summary.get("contact_quality_status", "")) == "clean", "seeded_gate_contact_not_clean")
    bool_issue(issues, int_value(analyzer_summary.get("first_contact_blocker_count")) == 0, "seeded_gate_first_contact_blockers")

    if replay_child:
        bool_issue(issues, bool(replay_child.get("pass", False)), "seeded_gate_replay_summary_not_pass")
        bool_issue(issues, len(list_value(replay_child.get("rows"))) >= expected_count, "seeded_gate_replay_rows_below_expected")
    if analyzer_child:
        bool_issue(issues, bool(analyzer_child.get("pass", False)), "seeded_gate_analyzer_summary_not_pass")

    return {
        "label": label,
        "path": artifact_display_path(path),
        "pass": not issues,
        "issues": issues,
        "seed": payload.get("seed"),
        "random_cases": random_cases,
        "expected_executable_count": expected_count,
        "planner_pass_count": int_value(planner_summary.get("pass_count")),
        "wrong_fetch_dispatch_count": int_value(planner_summary.get("wrong_fetch_dispatch_count")),
        "route_counts": dict_value(planner_summary.get("route_counts")),
        "selected_count": selected_count,
        "mission_pass_count": int_value(replay_summary.get("mission_pass_count")),
        "visual_package_pass_count": int_value(replay_summary.get("visual_package_pass_count")),
        "execution_quality_status": str(analyzer_summary.get("execution_quality_status", "")),
        "setup_quality_status": str(analyzer_summary.get("setup_quality_status", "")),
        "contact_quality_status": str(analyzer_summary.get("contact_quality_status", "")),
        "first_contact_blocker_count": int_value(analyzer_summary.get("first_contact_blocker_count")),
        "planner_summary_path": planner_child_path,
        "replay_summary_path": replay_child_path,
        "analyzer_summary_path": analyzer_child_path,
        "milestone_interpretation": str(payload.get("milestone_interpretation", "")),
    }


def first_video_url(visual_package: dict[str, Any], role: str) -> str:
    for video in list_value(visual_package.get("videos")):
        if not isinstance(video, dict):
            continue
        if str(video.get("role", "")) == role and bool(video.get("browser_playable", False)):
            return str(video.get("url") or video.get("path") or "")
    return ""


def first_keyframe_url(visual_package: dict[str, Any]) -> str:
    for review in list_value(visual_package.get("keyframe_reviews")):
        if not isinstance(review, dict):
            continue
        if bool(review.get("ok", False)):
            return str(review.get("url") or review.get("path") or "")
    return ""


def evaluate_boundary_rows(
    replay_path_text: str,
    specs: list[tuple[str, str, str]],
    *,
    delivery_radius_m: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    replay_path = resolve_path(replay_path_text)
    replay_payload, replay_issues = read_json(replay_path)
    rows_by_scene = {
        str(row.get("scene_id", "") or ""): row
        for row in list_value(replay_payload.get("rows"))
        if isinstance(row, dict)
    }
    results: list[dict[str, Any]] = []
    for scene_id, expected_route, note in specs:
        issues = list(replay_issues)
        row = rows_by_scene.get(scene_id)
        if not row:
            results.append(
                {
                    "scene_id": scene_id,
                    "expected_route_label": expected_route,
                    "note": note,
                    "pass": False,
                    "issues": issues + [f"missing_boundary_row:{scene_id}"],
                }
            )
            continue
        mission = dict_value(row.get("mission"))
        visual_package = dict_value(row.get("visual_package"))
        closest = float_value(mission.get("closest_approach_distance_m"))
        route_label = str(row.get("route_label", "") or "")
        bool_issue(issues, not str(row.get("failure_reason", "") or "").strip(), "boundary_row_failure_reason")
        bool_issue(issues, row.get("returncode") in {0, None}, "boundary_row_returncode")
        bool_issue(issues, not expected_route or route_label == expected_route, "boundary_row_route_mismatch")
        bool_issue(issues, bool(mission.get("pass", False)), "boundary_row_mission_not_pass")
        bool_issue(issues, closest is not None and closest <= delivery_radius_m, "boundary_row_outside_delivery_radius")
        bool_issue(issues, bool(visual_package.get("pass", False)), "boundary_row_visual_package_not_pass")
        bool_issue(issues, bool(visual_package.get("mobile_watchable", False)), "boundary_row_mobile_video_not_watchable")
        bool_issue(issues, bool(visual_package.get("onboard_camera_watchable", False)), "boundary_row_onboard_not_watchable")
        mission_path = str(row.get("mission_summary_path", "") or "")
        package_path = str(row.get("visual_package_summary_path", "") or "")
        if mission_path:
            bool_issue(issues, resolve_path(mission_path).is_file(), "boundary_row_missing_mission_summary")
        else:
            issues.append("boundary_row_missing_mission_summary_path")
        if package_path:
            bool_issue(issues, resolve_path(package_path).is_file(), "boundary_row_missing_visual_package_summary")
        else:
            issues.append("boundary_row_missing_visual_package_summary_path")
        results.append(
            {
                "scene_id": scene_id,
                "route_label": route_label,
                "expected_route_label": expected_route,
                "note": note,
                "pass": not issues,
                "issues": issues,
                "closest_approach_distance_m": closest,
                "mission_summary_path": mission_path,
                "visual_package_summary_path": package_path,
                "onboard_video_url": first_video_url(visual_package, "onboard_camera"),
                "topdown_video_url": first_video_url(visual_package, "external_context"),
                "keyframe_review_url": first_keyframe_url(visual_package),
            }
        )
    replay_result = {
        "path": artifact_display_path(replay_path),
        "pass": bool(replay_payload.get("pass", False)) and not replay_issues,
        "issues": replay_issues,
        "selected_count": int_value(replay_payload.get("selected_count")),
        "mission_pass_count": int_value(replay_payload.get("mission_pass_count")),
        "visual_package_pass_count": int_value(replay_payload.get("visual_package_pass_count")),
    }
    return replay_result, results


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    saved_anchor = evaluate_saved_anchor_summary(str(args.saved_anchor_summary))
    setup_contact_audit = (
        evaluate_setup_contact_audit(str(args.setup_contact_audit))
        if str(args.setup_contact_audit or "").strip()
        else {"pass": True, "issues": [], "path": ""}
    )
    seeded = [
        evaluate_seeded_gate(label, path, min_random_cases=int(args.min_random_cases))
        for label, path in seeded_gate_specs(list(args.seeded_gate or []))
    ]
    boundary_replay, boundaries = evaluate_boundary_rows(
        str(args.boundary_replay_summary),
        boundary_specs(list(args.boundary_row or [])),
        delivery_radius_m=float(args.fetch_delivery_radius_m),
    )
    issue_count = (
        len(saved_anchor.get("issues", []))
        + len(setup_contact_audit.get("issues", []))
        + sum(len(row.get("issues", [])) for row in seeded)
        + len(boundary_replay.get("issues", []))
        + sum(len(row.get("issues", [])) for row in boundaries)
    )
    seeded_gate_green_count = sum(1 for row in seeded if bool(row.get("pass", False)))
    boundary_green_count = sum(1 for row in boundaries if bool(row.get("pass", False)))
    pass_manifest = bool(
        saved_anchor.get("pass", False)
        and setup_contact_audit.get("pass", False)
        and seeded
        and seeded_gate_green_count == len(seeded)
        and boundaries
        and boundary_green_count == len(boundaries)
    )
    return {
        "generated_utc": utc_now(),
        "type": MANIFEST_KIND,
        "campaign_id": str(args.campaign_id or ""),
        "regression_set_id": str(args.regression_set_id or DEFAULT_REGRESSION_SET_ID),
        "pass": pass_manifest,
        "promotion_evidence": False,
        "milestone_interpretation": (
            "planner_routed_moonshot_regression_set_green"
            if pass_manifest
            else "planner_routed_moonshot_regression_set_incomplete"
        ),
        "delivery_radius_m": float(args.fetch_delivery_radius_m),
        "saved_anchor_repeatability": saved_anchor,
        "setup_contact_audit": setup_contact_audit,
        "seeded_gates": seeded,
        "boundary_replay": boundary_replay,
        "boundary_rows": boundaries,
        "totals": {
            "issue_count": issue_count,
            "seeded_gate_count": len(seeded),
            "seeded_gate_green_count": seeded_gate_green_count,
            "boundary_row_count": len(boundaries),
            "boundary_row_green_count": boundary_green_count,
            "seeded_live_mission_pass_count": sum(int_value(row.get("mission_pass_count")) for row in seeded),
            "seeded_visual_package_pass_count": sum(int_value(row.get("visual_package_pass_count")) for row in seeded),
        },
    }


def artifact_link(path: str) -> str:
    return f"[artifact](/{path})" if str(path).startswith("artifacts/session/") else str(path)


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Fetch Moonshot Regression Manifest",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- regression_set_id: `{summary.get('regression_set_id', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        f"- delivery_radius_m: `{summary.get('delivery_radius_m', '')}`",
        f"- totals: `{summary.get('totals', {})}`",
        "",
        "## Saved Anchors",
        "",
    ]
    saved = dict_value(summary.get("saved_anchor_repeatability"))
    lines.extend(
        [
            f"- repeatability pass=`{saved.get('pass', False)}` counts=`{saved.get('saved_anchor_scene_counts', {})}` closest_range=`{saved.get('closest_approach_range_m', {})}` {artifact_link(str(saved.get('path', '') or ''))}",
            f"- repeatability issues=`{saved.get('issues', [])}`",
        ]
    )
    audit = dict_value(summary.get("setup_contact_audit"))
    if audit.get("path"):
        lines.extend(
            [
                f"- setup/contact audit pass=`{audit.get('pass', False)}` stage_quality_green=`{audit.get('stage_quality_green', False)}` pass_count=`{audit.get('pass_count', 0)}` {artifact_link(str(audit.get('path', '') or ''))}",
                f"- setup/contact audit issues=`{audit.get('issues', [])}`",
            ]
        )
    lines.extend(["", "## Seeded Promotion Gates", ""])
    for row in list_value(summary.get("seeded_gates")):
        lines.append(
            f"- `{row.get('label', '')}` seed=`{row.get('seed', '')}` pass=`{row.get('pass', False)}` "
            f"planner=`{row.get('planner_pass_count', 0)}/{row.get('random_cases', 0)}` "
            f"wrong_fetch=`{row.get('wrong_fetch_dispatch_count', 0)}` "
            f"live=`{row.get('mission_pass_count', 0)}/{row.get('selected_count', 0)}` "
            f"visual=`{row.get('visual_package_pass_count', 0)}/{row.get('selected_count', 0)}` "
            f"quality=`{row.get('execution_quality_status', '')}/{row.get('setup_quality_status', '')}/{row.get('contact_quality_status', '')}` "
            f"issues=`{row.get('issues', [])}` {artifact_link(str(row.get('path', '') or ''))}"
        )
    lines.extend(["", "## Boundary Rows", ""])
    for row in list_value(summary.get("boundary_rows")):
        closest = row.get("closest_approach_distance_m")
        closest_text = f"{float(closest):.3f}m" if isinstance(closest, (int, float)) else ""
        links = " ".join(
            artifact_link(str(path))
            for path in (
                row.get("mission_summary_path", ""),
                row.get("visual_package_summary_path", ""),
            )
            if str(path).startswith("artifacts/session/")
        )
        lines.append(
            f"- `{row.get('scene_id', '')}` route=`{row.get('route_label', '')}` "
            f"pass=`{row.get('pass', False)}` closest=`{closest_text}` "
            f"note=`{row.get('note', '')}` issues=`{row.get('issues', [])}` {links}"
        )
        if row.get("onboard_video_url"):
            lines.append(f"  - onboard: `{row.get('onboard_video_url', '')}`")
        if row.get("keyframe_review_url"):
            lines.append(f"  - keyframes: `{row.get('keyframe_review_url', '')}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the planner-routed moonshot regression manifest.")
    parser.add_argument("--campaign-id", default=f"fetch_moonshot_regression_manifest_{current_utc_stamp()}")
    parser.add_argument("--regression-set-id", default=DEFAULT_REGRESSION_SET_ID)
    parser.add_argument("--saved-anchor-summary", default=DEFAULT_SAVED_ANCHOR_SUMMARY)
    parser.add_argument("--setup-contact-audit", default=DEFAULT_SETUP_CONTACT_AUDIT)
    parser.add_argument("--seeded-gate", action="append", default=[], help="label=path to a parent seeded gate summary.")
    parser.add_argument("--boundary-replay-summary", default=DEFAULT_BOUNDARY_REPLAY_SUMMARY)
    parser.add_argument("--boundary-row", action="append", default=[], help="scene_id=route_label:note boundary row requirement.")
    parser.add_argument("--fetch-delivery-radius-m", type=float, default=DEFAULT_DELIVERY_RADIUS_M)
    parser.add_argument("--min-random-cases", type=int, default=30)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / MANIFEST_KIND)
    summary = build_summary(args)
    summary_path = root / "regression_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["summary_path"] = artifact_display_path(summary_path)
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_MOONSHOT_REGRESSION_MANIFEST_SUMMARY={summary_path}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
