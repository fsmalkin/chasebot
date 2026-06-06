#!/usr/bin/env python3
"""Roll up generalized fetch-to-pose milestone readiness."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
ANALYZER_KIND = "fetch_generalized_milestone_readiness"
DEFAULT_PROVIDER_READINESS = (
    "artifacts/session/provider_rerun_readiness_rollup_seed20260650_20260605/"
    "fetch_planner_provider_rerun_readiness/provider_rerun_readiness_summary.json"
)
DEFAULT_PROVIDER_COMPARISON = (
    "artifacts/session/provider_planner_seed20260650_provider_rerun_comparison_20260605/"
    "fetch_planner_provider_rerun_comparison/provider_rerun_comparison_summary.json"
)
DEFAULT_DASHBOARD_AUDIT = (
    "artifacts/session/dashboard_visual_evidence_audit_current_proof_cards_20260605/"
    "fetch_dashboard_visual_evidence_audit/dashboard_visual_evidence_summary.json"
)
DEFAULT_HARDWARE_READINESS = (
    "artifacts/session/hardware_transfer_readiness_seed20260648_dashboard_20260605/"
    "fetch_hardware_transfer_readiness/hardware_transfer_readiness_summary.json"
)
DEFAULT_GEOMETRY_BREADTH = (
    "artifacts/session/planner_geometry_breadth_audit_seeds20260648_20260650_20260605/"
    "fetch_planner_geometry_breadth_audit/geometry_breadth_summary.json"
)
DEFAULT_UAT_WATCHLIST = (
    "artifacts/session/dashboard_uat_watchlist_seed20260648_20260605/"
    "fetch_dashboard_uat_watchlist/uat_watchlist_summary.json"
)
REQUIRED_ROUTES = {
    "ambiguous_or_unsafe_no_go",
    "fetch_ready_local",
    "nav2_reposition_first",
    "recovery_or_reaim",
    "scan_or_perceive_first",
}
REQUIRED_SETUP_FLAGS = {
    "bounded_recovery_required",
    "corridor_unusable",
    "initial_lateral_setup_debt",
    "initial_yaw_setup_debt",
    "nav2_reposition_required",
    "perception_refresh_required",
    "target_distance_outside_local_fetch_window",
}
MIN_GEOMETRY_SPANS = {
    "ball_target_angle_abs_deg": 30.0,
    "ball_target_distance_m": 1.0,
    "lateral_m": 0.15,
    "robot_ball_distance_m": 0.8,
    "yaw_deg": 20.0,
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


def int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def float_value(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def issue_unless(issues: list[str], condition: bool, issue: str) -> None:
    if not condition:
        issues.append(issue)


def summarize_provider_readiness(path_text: str) -> dict[str, Any]:
    payload, issues = read_json(path_text)
    blockers = [str(item) for item in list_value(payload.get("blockers"))]
    expected_only_key_blocker = blockers == ["missing_openai_api_key"]
    provider_preflight_ready = bool(payload.get("provider_rerun_ready", False)) and not blockers
    breadth = dict_value(payload.get("breadth_rollup"))
    issue_unless(issues, bool(breadth.get("pass", False)), "breadth_rollup_not_green")
    issue_unless(issues, int_value(breadth.get("total_random_cases")) >= 300, "breadth_rollup_below_300_cases")
    issue_unless(issues, int_value(breadth.get("total_selected_count")) >= 27, "executable_visual_rows_below_27")
    issue_unless(issues, int_value(breadth.get("total_wrong_fetch_dispatch_count")) == 0, "wrong_fetch_dispatch_nonzero")
    issue_unless(issues, int_value(breadth.get("total_contact_watch_count")) == 0, "contact_watch_nonzero")
    issue_unless(issues, int_value(breadth.get("total_first_contact_blocker_count")) == 0, "first_contact_blocker_nonzero")
    issue_unless(issues, expected_only_key_blocker or provider_preflight_ready, "provider_readiness_has_unexpected_blockers")
    return {
        "path": artifact_display_path(path_text),
        "pass": not issues,
        "issues": issues,
        "blockers": blockers,
        "provider_rerun_ready": bool(payload.get("provider_rerun_ready", False)),
        "provider_backed_authority_proven": bool(payload.get("provider_backed_authority_proven", False)),
        "expected_pending_only": expected_only_key_blocker,
        "provider_preflight_ready": provider_preflight_ready,
        "breadth_random_cases": int_value(breadth.get("total_random_cases")),
        "executable_visual_rows": int_value(breadth.get("total_selected_count")),
        "wrong_fetch_dispatch_count": int_value(breadth.get("total_wrong_fetch_dispatch_count")),
    }


def summarize_provider_comparison(path_text: str) -> dict[str, Any]:
    payload, issues = read_json(path_text)
    blockers = [str(item) for item in list_value(payload.get("blockers"))]
    expected_provider_missing = blockers and all(
        blocker.startswith("provider_planner:") for blocker in blockers
    )
    provider_authority_ready = (
        bool(payload.get("guarded_provider_rerun_ready", False))
        and bool(payload.get("strict_provider_authority_ready", False))
        and not blockers
    )
    replay = dict_value(payload.get("provider_replay"))
    route_uat = dict_value(payload.get("provider_route_uat"))
    issue_unless(issues, bool(replay.get("pass", False)), "provider_replay_baseline_not_green")
    issue_unless(issues, bool(route_uat.get("pass", False)), "provider_route_uat_baseline_not_green")
    issue_unless(issues, expected_provider_missing or provider_authority_ready, "provider_comparison_has_unexpected_blockers")
    return {
        "path": artifact_display_path(path_text),
        "pass": not issues,
        "issues": issues,
        "blockers": blockers,
        "guarded_provider_rerun_ready": bool(payload.get("guarded_provider_rerun_ready", False)),
        "strict_provider_authority_ready": bool(payload.get("strict_provider_authority_ready", False)),
        "provider_authority_ready": provider_authority_ready,
        "expected_pending_only": expected_provider_missing,
        "replay_pass_count": int_value(replay.get("mission_pass_count")),
        "route_uat_interpretation": str(route_uat.get("milestone_interpretation", "") or ""),
    }


def summarize_dashboard_audit(path_text: str) -> dict[str, Any]:
    payload, issues = read_json(path_text)
    issue_unless(issues, bool(payload.get("pass", False)), "dashboard_visual_audit_not_green")
    issue_unless(issues, int_value(payload.get("uat_sample_count")) >= 15, "uat_sample_count_below_15")
    issue_unless(
        issues,
        int_value(payload.get("uat_sample_pass_count")) == int_value(payload.get("uat_sample_count")),
        "uat_sample_pass_count_mismatch",
    )
    issue_unless(issues, int_value(payload.get("evidence_card_count")) >= 10, "evidence_card_count_below_10")
    issue_unless(
        issues,
        int_value(payload.get("evidence_card_pass_count")) == int_value(payload.get("evidence_card_count")),
        "evidence_card_pass_count_mismatch",
    )
    return {
        "path": artifact_display_path(path_text),
        "pass": not issues,
        "issues": issues,
        "uat_sample_count": int_value(payload.get("uat_sample_count")),
        "uat_sample_pass_count": int_value(payload.get("uat_sample_pass_count")),
        "evidence_card_count": int_value(payload.get("evidence_card_count")),
        "evidence_card_pass_count": int_value(payload.get("evidence_card_pass_count")),
        "route_counts": dict_value(payload.get("route_counts")),
    }


def summarize_hardware_readiness(path_text: str) -> dict[str, Any]:
    payload, issues = read_json(path_text)
    open_hardware_gates = [str(item) for item in list_value(payload.get("open_hardware_gates"))]
    issue_unless(issues, bool(payload.get("pass", False)), "hardware_transfer_readiness_not_green")
    issue_unless(issues, bool(payload.get("hardware_transfer_ready", False)), "hardware_transfer_not_ready")
    issue_unless(issues, bool(payload.get("hardware_proven", True)) is False, "hardware_proven_unexpected")
    issue_unless(issues, bool(open_hardware_gates), "open_hardware_gates_missing")
    return {
        "path": artifact_display_path(path_text),
        "pass": not issues,
        "issues": issues,
        "hardware_transfer_ready": bool(payload.get("hardware_transfer_ready", False)),
        "hardware_proven": bool(payload.get("hardware_proven", False)),
        "readiness_level": str(payload.get("readiness_level", "") or ""),
        "open_hardware_gates": open_hardware_gates,
    }


def summarize_geometry_breadth(path_text: str) -> dict[str, Any]:
    payload, issues = read_json(path_text)
    route_counts = dict_value(payload.get("route_counts"))
    flag_counts = dict_value(payload.get("flag_counts"))
    ranges = dict_value(payload.get("ranges"))
    missing_routes = sorted(route for route in REQUIRED_ROUTES if int_value(route_counts.get(route)) <= 0)
    missing_flags = sorted(flag for flag in REQUIRED_SETUP_FLAGS if int_value(flag_counts.get(flag)) <= 0)
    span_failures: list[str] = []
    for key, minimum in MIN_GEOMETRY_SPANS.items():
        span = float_value(dict_value(ranges.get(key)).get("span"))
        if span < minimum:
            span_failures.append(f"{key}:{span:.3f}<{minimum:.3f}")
    issue_unless(issues, bool(payload.get("pass", False)), "geometry_breadth_not_green")
    issue_unless(issues, int_value(payload.get("scene_count")) >= 300, "geometry_scene_count_below_300")
    issue_unless(issues, not missing_routes, f"geometry_missing_routes:{','.join(missing_routes)}")
    issue_unless(issues, not missing_flags, f"geometry_missing_setup_flags:{','.join(missing_flags)}")
    issue_unless(issues, not span_failures, f"geometry_span_failures:{','.join(span_failures)}")
    return {
        "path": artifact_display_path(path_text),
        "pass": not issues,
        "issues": issues,
        "scene_count": int_value(payload.get("scene_count")),
        "seeds": list_value(payload.get("seeds")),
        "route_counts": route_counts,
        "flag_counts": flag_counts,
        "minimum_spans": dict_value(payload.get("minimum_spans")),
        "spans": {key: float_value(dict_value(ranges.get(key)).get("span")) for key in MIN_GEOMETRY_SPANS},
    }


def summarize_uat_watchlist(path_text: str) -> dict[str, Any]:
    payload, issues = read_json(path_text)
    route_counts = dict_value(payload.get("route_counts"))
    missing_routes = sorted(route for route in REQUIRED_ROUTES if int_value(route_counts.get(route)) < 3)
    guidance = [str(item) for item in list_value(payload.get("review_guidance"))]
    issue_unless(issues, bool(payload.get("pass", False)), "uat_watchlist_not_green")
    issue_unless(issues, int_value(payload.get("sample_count")) >= 15, "uat_watchlist_sample_count_below_15")
    issue_unless(issues, not missing_routes, f"uat_watchlist_route_counts_below_3:{','.join(missing_routes)}")
    issue_unless(
        issues,
        str(payload.get("milestone_interpretation", "") or "") == "dashboard_uat_watchlist_ready",
        "uat_watchlist_interpretation_unexpected",
    )
    issue_unless(
        issues,
        any("onboard" in item and "first" in item for item in guidance),
        "uat_watchlist_onboard_first_guidance_missing",
    )
    return {
        "path": artifact_display_path(path_text),
        "pass": not issues,
        "issues": issues,
        "sample_count": int_value(payload.get("sample_count")),
        "route_counts": route_counts,
        "review_guidance": guidance,
    }


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    provider_readiness = summarize_provider_readiness(str(args.provider_readiness_summary))
    provider_comparison = summarize_provider_comparison(str(args.provider_comparison_summary))
    dashboard_audit = summarize_dashboard_audit(str(args.dashboard_visual_evidence_summary))
    hardware_readiness = summarize_hardware_readiness(str(args.hardware_transfer_readiness_summary))
    geometry_breadth = summarize_geometry_breadth(str(args.geometry_breadth_summary))
    uat_watchlist = summarize_uat_watchlist(str(args.uat_watchlist_summary))
    sim_uat_green = all(
        bool(section.get("pass", False))
        for section in (
            provider_readiness,
            provider_comparison,
            dashboard_audit,
            hardware_readiness,
            geometry_breadth,
            uat_watchlist,
        )
    )
    provider_authority_proven = bool(provider_comparison.get("provider_authority_ready", False))
    hardware_proven = bool(hardware_readiness.get("hardware_proven", False))
    open_gates: list[str] = []
    if not provider_authority_proven:
        open_gates.append("provider_backed_llm_routing_not_proven")
    for gate in list_value(hardware_readiness.get("open_hardware_gates")):
        open_gates.append(str(gate))
    issues: list[str] = []
    for name, section in (
        ("provider_readiness", provider_readiness),
        ("provider_comparison", provider_comparison),
        ("dashboard_visual_evidence", dashboard_audit),
        ("hardware_transfer_readiness", hardware_readiness),
        ("planner_geometry_breadth", geometry_breadth),
        ("operator_uat_watchlist", uat_watchlist),
    ):
        for issue in list_value(section.get("issues")):
            issues.append(f"{name}:{issue}")
    milestone_complete = sim_uat_green and provider_authority_proven and hardware_proven
    return {
        "generated_utc": utc_now(),
        "type": ANALYZER_KIND,
        "campaign_id": str(args.campaign_id or ""),
        "pass": sim_uat_green,
        "promotion_evidence": False,
        "hardware_proven": hardware_proven,
        "provider_backed_authority_proven": provider_authority_proven,
        "milestone_complete": milestone_complete,
        "operator_uat_ready": sim_uat_green,
        "readiness_level": (
            "milestone_complete"
            if milestone_complete
            else "operator_uat_ready_provider_and_physical_pending"
            if sim_uat_green
            else "milestone_readiness_incomplete"
        ),
        "milestone_interpretation": (
            "sim_uat_green_provider_and_physical_pending"
            if sim_uat_green and not milestone_complete
            else "generalized_fetch_to_pose_v1_complete"
            if milestone_complete
            else "generalized_fetch_to_pose_v1_incomplete"
        ),
        "issues": issues,
        "open_gates": open_gates,
        "green_evidence": [
            "three_seed_deterministic_breadth_rollup_green",
            "provider_backed_route_owner_seed20260650_green"
            if provider_authority_proven
            else "provider_backed_route_owner_seed20260650_pending",
            "planner_geometry_breadth_green",
            "current_dashboard_visual_evidence_links_green",
            "operator_uat_watchlist_ready",
            "seed20260648_robot_fidelity_sim_gate_hardware_rehearsal_green",
        ]
        if sim_uat_green
        else [],
        "next_actions": [
            "run_physical_onboard_tensor_rt_rehearsal_with_physical_camera_evidence",
            "keep_hardware_proven_false_until_field_physics_and_onboard_artifacts_are_recorded",
        ],
        "provider_readiness": provider_readiness,
        "provider_comparison": provider_comparison,
        "dashboard_visual_evidence": dashboard_audit,
        "hardware_transfer_readiness": hardware_readiness,
        "planner_geometry_breadth": geometry_breadth,
        "operator_uat_watchlist": uat_watchlist,
    }


def artifact_link(path_text: str) -> str:
    text = str(path_text or "").replace("\\", "/")
    return f"[artifact](/{text})" if text.startswith(("artifacts/", "runtime/")) else text


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Generalized Fetch-To-Pose Milestone Readiness",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- operator_uat_ready: `{summary.get('operator_uat_ready', False)}`",
        f"- milestone_complete: `{summary.get('milestone_complete', False)}`",
        f"- provider_backed_authority_proven: `{summary.get('provider_backed_authority_proven', False)}`",
        f"- hardware_proven: `{summary.get('hardware_proven', False)}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- readiness_level: `{summary.get('readiness_level', '')}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        f"- issues: `{summary.get('issues', [])}`",
        "",
        "## Green Evidence",
        "",
    ]
    for item in list_value(summary.get("green_evidence")):
        lines.append(f"- `{item}`")
    lines.extend(["", "## Open Gates", ""])
    for gate in list_value(summary.get("open_gates")):
        lines.append(f"- `{gate}`")
    lines.extend(["", "## Evidence Sources", ""])
    for key in (
        "provider_readiness",
        "provider_comparison",
        "planner_geometry_breadth",
        "dashboard_visual_evidence",
        "operator_uat_watchlist",
        "hardware_transfer_readiness",
    ):
        section = dict_value(summary.get(key))
        lines.append(
            f"- `{key}` pass=`{section.get('pass', False)}` issues=`{section.get('issues', [])}` "
            f"{artifact_link(str(section.get('path', '') or ''))}"
        )
    lines.extend(["", "## Next Actions", ""])
    for action in list_value(summary.get("next_actions")):
        lines.append(f"- `{action}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Roll up generalized fetch-to-pose milestone readiness.")
    parser.add_argument("--campaign-id", default=f"fetch_generalized_milestone_readiness_{current_utc_stamp()}")
    parser.add_argument("--provider-readiness-summary", default=DEFAULT_PROVIDER_READINESS)
    parser.add_argument("--provider-comparison-summary", default=DEFAULT_PROVIDER_COMPARISON)
    parser.add_argument("--dashboard-visual-evidence-summary", default=DEFAULT_DASHBOARD_AUDIT)
    parser.add_argument("--hardware-transfer-readiness-summary", default=DEFAULT_HARDWARE_READINESS)
    parser.add_argument("--geometry-breadth-summary", default=DEFAULT_GEOMETRY_BREADTH)
    parser.add_argument("--uat-watchlist-summary", default=DEFAULT_UAT_WATCHLIST)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / ANALYZER_KIND)
    summary = build_summary(args)
    summary_path = root / "milestone_readiness_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["summary_path"] = artifact_display_path(summary_path)
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_GENERALIZED_MILESTONE_READINESS_SUMMARY={summary_path}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
