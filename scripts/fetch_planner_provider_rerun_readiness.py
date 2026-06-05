#!/usr/bin/env python3
"""Check whether the planner-routed breadth floor is ready for provider rerun."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
ANALYZER_KIND = "fetch_planner_provider_rerun_readiness"
ROUTE_LABELS = (
    "fetch_ready_local",
    "nav2_reposition_first",
    "recovery_or_reaim",
    "scan_or_perceive_first",
    "ambiguous_or_unsafe_no_go",
)
DEFAULT_SEED = 20260650
DEFAULT_RANDOM_CASES = 100
DEFAULT_MAX_PER_ROUTE = 3
DEFAULT_MIN_ROLLUP_RANDOM_CASES = 300
DEFAULT_MIN_ROLLUP_EXECUTABLE_ROWS = 27
DEFAULT_DASHBOARD_URL = "http://127.0.0.1:8883"
DEFAULT_PLANNER_SUMMARY = (
    "artifacts/session/live_planner_seeded_generalization_gate_seed20260650_breadth_100x3_20260605_planner/"
    "fetch_planner_handoff_gate/gate_summary.json"
)
DEFAULT_BREADTH_ROLLUP = (
    "artifacts/session/analysis_fetch_planner_breadth_rollup_seeds20260648_20260650_20260605/"
    "fetch_planner_breadth_rollup/breadth_rollup_summary.json"
)
DEFAULT_DASHBOARD_PLAN = "runtime/dashboard/fetch_plan_data.json"


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
    path = resolve_path(path_text)
    try:
        return str(path.relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def read_json(path_text: str | Path) -> tuple[dict[str, Any], list[str]]:
    path = resolve_path(path_text)
    if not path.is_file():
        return {}, [f"missing_json:{artifact_display_path(path)}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive artifact parsing
        return {}, [f"invalid_json:{artifact_display_path(path)}:{exc}"]
    if not isinstance(payload, dict):
        return {}, [f"json_not_object:{artifact_display_path(path)}"]
    return payload, []


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def issue_unless(issues: list[str], condition: bool, issue: str) -> None:
    if not condition:
        issues.append(issue)


def summarize_fallback_seed(path_text: str, *, seed: int, random_cases: int) -> dict[str, Any]:
    payload, issues = read_json(path_text)
    route_counts = {str(key): int_value(value) for key, value in dict_value(payload.get("route_counts")).items()}
    provider_status_counts = {
        str(key): int_value(value) for key, value in dict_value(payload.get("provider_status_counts")).items()
    }
    effective_counts = {
        str(key): int_value(value) for key, value in dict_value(payload.get("planner_mode_effective_counts")).items()
    }
    total_count = int_value(payload.get("random_cases") or payload.get("pass_count"))
    issue_unless(issues, bool(payload.get("pass", False)), "latest_fallback_seed_not_green")
    issue_unless(issues, int_value(payload.get("seed")) == int(seed), f"latest_fallback_seed_not_{seed}")
    issue_unless(issues, total_count >= int(random_cases), f"latest_fallback_random_cases_below_{random_cases}")
    issue_unless(issues, int_value(payload.get("wrong_fetch_dispatch_count")) == 0, "wrong_fetch_dispatch_count_nonzero")
    issue_unless(issues, all(route_counts.get(route, 0) > 0 for route in ROUTE_LABELS), "route_family_coverage_incomplete")
    issue_unless(issues, provider_status_counts.get("skipped_missing_openai_api_key", 0) == total_count, "fallback_provider_status_unexpected")
    issue_unless(issues, effective_counts.get("deterministic_fallback", 0) == total_count, "fallback_effective_count_unexpected")
    return {
        "path": artifact_display_path(path_text),
        "pass": not issues,
        "issues": issues,
        "seed": int_value(payload.get("seed")),
        "random_cases": total_count,
        "route_counts": route_counts,
        "provider_status_counts": provider_status_counts,
        "planner_mode_effective_counts": effective_counts,
        "wrong_fetch_dispatch_count": int_value(payload.get("wrong_fetch_dispatch_count")),
    }


def summarize_breadth_rollup(
    path_text: str,
    *,
    min_random_cases: int,
    min_executable_rows: int,
) -> dict[str, Any]:
    payload, issues = read_json(path_text)
    route_counts = {str(key): int_value(value) for key, value in dict_value(payload.get("route_counts")).items()}
    provider_status_counts = {
        str(key): int_value(value) for key, value in dict_value(payload.get("provider_status_counts")).items()
    }
    rows = payload.get("rows", [])
    rows_list = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    seeds = [int_value(seed) for seed in payload.get("seeds", [])] if isinstance(payload.get("seeds"), list) else []
    total_random_cases = int_value(payload.get("total_random_cases"))
    total_planner_pass_count = int_value(payload.get("total_planner_pass_count"))
    total_selected_count = int_value(payload.get("total_selected_count"))
    total_visual_package_pass_count = int_value(payload.get("total_visual_package_pass_count"))
    issue_unless(issues, bool(payload.get("pass", False)), "breadth_rollup_not_green")
    issue_unless(
        issues,
        total_random_cases >= int(min_random_cases),
        f"breadth_rollup_random_cases_below_{int(min_random_cases)}",
    )
    issue_unless(issues, total_planner_pass_count == total_random_cases, "breadth_rollup_planner_pass_mismatch")
    issue_unless(
        issues,
        int_value(payload.get("total_wrong_fetch_dispatch_count")) == 0,
        "breadth_rollup_wrong_fetch_dispatch_count_nonzero",
    )
    issue_unless(
        issues,
        total_selected_count >= int(min_executable_rows),
        f"breadth_rollup_executable_rows_below_{int(min_executable_rows)}",
    )
    issue_unless(
        issues,
        int_value(payload.get("total_mission_fail_count")) == 0,
        "breadth_rollup_mission_fail_count_nonzero",
    )
    issue_unless(
        issues,
        total_visual_package_pass_count == total_selected_count,
        "breadth_rollup_visual_package_pass_mismatch",
    )
    issue_unless(
        issues,
        int_value(payload.get("total_contact_watch_count")) == 0,
        "breadth_rollup_contact_watch_count_nonzero",
    )
    issue_unless(
        issues,
        int_value(payload.get("total_first_contact_blocker_count")) == 0,
        "breadth_rollup_first_contact_blocker_count_nonzero",
    )
    issue_unless(issues, all(route_counts.get(route, 0) > 0 for route in ROUTE_LABELS), "route_family_coverage_incomplete")
    issue_unless(
        issues,
        provider_status_counts.get("skipped_missing_openai_api_key", 0) == total_random_cases,
        "breadth_rollup_provider_status_unexpected",
    )
    issue_unless(
        issues,
        bool(payload.get("provider_backed_authority_ready", True)) is False,
        "breadth_rollup_provider_authority_unexpected",
    )
    return {
        "path": artifact_display_path(path_text),
        "pass": not issues,
        "issues": issues,
        "seeds": seeds,
        "gate_count": int_value(payload.get("gate_count") or len(rows_list)),
        "total_random_cases": total_random_cases,
        "total_planner_pass_count": total_planner_pass_count,
        "total_wrong_fetch_dispatch_count": int_value(payload.get("total_wrong_fetch_dispatch_count")),
        "total_selected_count": total_selected_count,
        "total_mission_pass_count": int_value(payload.get("total_mission_pass_count")),
        "total_mission_fail_count": int_value(payload.get("total_mission_fail_count")),
        "total_visual_package_pass_count": total_visual_package_pass_count,
        "total_contact_watch_count": int_value(payload.get("total_contact_watch_count")),
        "total_first_contact_blocker_count": int_value(payload.get("total_first_contact_blocker_count")),
        "route_counts": route_counts,
        "provider_status_counts": provider_status_counts,
        "provider_backed_authority_ready": bool(payload.get("provider_backed_authority_ready", False)),
    }


def summarize_dashboard(path_text: str, *, seed: int, min_rollup_random_cases: int) -> dict[str, Any]:
    payload, issues = read_json(path_text)
    status_label = str(payload.get("status_label", ""))
    status_detail = str(payload.get("status_detail", ""))
    latest_evidence = payload.get("latest_evidence", [])
    evidence_rows = [row for row in latest_evidence if isinstance(row, dict)] if isinstance(latest_evidence, list) else []
    uat = dict_value(payload.get("uat_review_bundle"))
    route_samples = [row for row in uat.get("route_samples", []) if isinstance(row, dict)] if isinstance(uat.get("route_samples"), list) else []
    rollup_text = json.dumps(evidence_rows, sort_keys=True)
    issue_unless(
        issues,
        "Three-seed breadth rollup" in status_label or "Three-seed breadth rollup" in status_detail,
        "dashboard_status_missing_breadth_rollup",
    )
    issue_unless(issues, str(min_rollup_random_cases) in status_detail or str(min_rollup_random_cases) in rollup_text, f"dashboard_missing_rollup_{min_rollup_random_cases}_cases")
    issue_unless(issues, str(seed) in status_label or str(seed) in status_detail or str(seed) in rollup_text, f"dashboard_status_missing_seed_{seed}")
    issue_unless(issues, len(route_samples) >= 15, "dashboard_uat_samples_below_15")
    issue_unless(
        issues,
        all(str(row.get("video_url", "")).startswith("/artifacts/session/") for row in route_samples),
        "dashboard_video_links_not_browser_rooted",
    )
    return {
        "path": artifact_display_path(path_text),
        "pass": not issues,
        "issues": issues,
        "status_label": status_label,
        "status_detail": status_detail,
        "uat_sample_count": len(route_samples),
    }


def build_rerun_commands(args: argparse.Namespace) -> dict[str, str]:
    seed = int(args.seed)
    suffix = str(args.campaign_suffix)
    planner_campaign = f"provider_planner_seed{seed}_breadth_{int(args.random_cases)}x{int(args.max_per_route)}_{suffix}"
    replay_campaign = f"provider_planner_seed{seed}_mixed_all_routes_{int(args.max_per_route)}x_{suffix}"
    analysis_campaign = f"provider_planner_seed{seed}_mixed_all_routes_analysis_{suffix}"
    comparison_campaign = f"provider_planner_seed{seed}_provider_rerun_comparison_{suffix}"
    planner_summary = (
        f"artifacts\\session\\{planner_campaign}_planner\\fetch_planner_handoff_gate\\gate_summary.json"
    )
    replay_summary = f"artifacts\\session\\{replay_campaign}\\fetch_planner_route_replay_batch\\batch_summary.json"
    route_uat_summary = f"artifacts\\session\\{analysis_campaign}\\fetch_planner_route_uat_analyzer\\route_uat_summary.json"
    return {
        "planner_gate": (
            "python scripts\\fetch_planner_seeded_generalization_gate.py "
            f"--campaign-id {planner_campaign} "
            f"--seed {seed} --random-cases {int(args.random_cases)} "
            "--planner-mode llm_supervised_guarded --quality-order roughest "
            f"--max-per-route {int(args.max_per_route)} "
            f"--dashboard-url {args.dashboard_url} --fresh-dashboard-session-per-run "
            "--allow-operator-view-degraded --stop-on-fail"
        ),
        "explicit_all_routes_replay": (
            "python scripts\\fetch_planner_route_replay_batch.py "
            f"--campaign-id {replay_campaign} --gate-summary {planner_summary} "
            "--route fetch_ready_local --route nav2_reposition_first --route recovery_or_reaim "
            "--route scan_or_perceive_first --route ambiguous_or_unsafe_no_go "
            f"--quality-order roughest --max-per-route {int(args.max_per_route)} "
            f"--dashboard-url {args.dashboard_url} --fresh-dashboard-session-per-run "
            "--allow-operator-view-degraded --stop-on-fail"
        ),
        "analysis": (
            "python scripts\\fetch_planner_route_uat_analyzer.py "
            f"--campaign-id {analysis_campaign} --planner-summary {planner_summary} "
            "--mission-summary <each batch row mission_summary_path> "
            "--visual-package-summary <each batch row visual_package_summary_path>"
        ),
        "provider_rerun_comparison": (
            "python scripts\\fetch_planner_provider_rerun_comparison.py "
            f"--campaign-id {comparison_campaign} --seed {seed} "
            f"--provider-planner-summary {planner_summary} "
            f"--provider-replay-summary {replay_summary} "
            f"--provider-route-uat-summary {route_uat_summary}"
        ),
    }


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    openai_api_key_present = bool(str(args.openai_api_key or "").strip())
    breadth_rollup = summarize_breadth_rollup(
        str(args.breadth_rollup_summary),
        min_random_cases=int(args.min_rollup_random_cases),
        min_executable_rows=int(args.min_rollup_executable_rows),
    )
    fallback_seed = summarize_fallback_seed(
        str(args.latest_fallback_planner_summary),
        seed=int(args.seed),
        random_cases=int(args.random_cases),
    )
    dashboard = summarize_dashboard(
        str(args.dashboard_plan),
        seed=int(args.seed),
        min_rollup_random_cases=int(args.min_rollup_random_cases),
    )
    blockers: list[str] = []
    if not openai_api_key_present:
        blockers.append("missing_openai_api_key")
    for section_name, section in (
        ("breadth_rollup", breadth_rollup),
        ("latest_fallback_seed", fallback_seed),
        ("dashboard_plan", dashboard),
    ):
        for issue in section.get("issues", []):
            blockers.append(f"{section_name}:{issue}")
    rerun_ready = not blockers
    return {
        "generated_utc": utc_now(),
        "type": ANALYZER_KIND,
        "campaign_id": str(args.campaign_id or ""),
        "pass": rerun_ready,
        "promotion_evidence": False,
        "provider_rerun_ready": rerun_ready,
        "provider_backed_authority_proven": False,
        "openai_api_key_present": openai_api_key_present,
        "readiness_level": "ready_for_provider_rerun" if rerun_ready else "provider_rerun_blocked",
        "milestone_interpretation": (
            "provider_backed_planner_rerun_ready"
            if rerun_ready
            else "provider_backed_planner_rerun_waiting_on_prerequisites"
        ),
        "blockers": blockers,
        "breadth_rollup": breadth_rollup,
        "latest_fallback_seed": fallback_seed,
        "dashboard_plan": dashboard,
        "rerun_contract": {
            "seed": int(args.seed),
            "random_cases": int(args.random_cases),
            "max_per_route": int(args.max_per_route),
            "baseline_rollup_random_cases": int(args.min_rollup_random_cases),
            "baseline_rollup_executable_rows": int(args.min_rollup_executable_rows),
            "planner_mode": "llm_supervised_guarded",
            "required_provider_status": "ok_for_all_cases",
            "required_guard_result": "zero_wrong_fetch_dispatches_and_guard_agreement",
            "required_visual_replay": "three_rows_per_route_family_with_browser_watchable_packages",
        },
        "next_commands": build_rerun_commands(args),
    }


def artifact_link(path_text: str) -> str:
    return f"[artifact](/{path_text})" if str(path_text).startswith(("artifacts/", "runtime/")) else str(path_text)


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    rollup = dict_value(summary.get("breadth_rollup"))
    fallback = dict_value(summary.get("latest_fallback_seed"))
    dashboard = dict_value(summary.get("dashboard_plan"))
    commands = dict_value(summary.get("next_commands"))
    lines = [
        "# Fetch Planner Provider Rerun Readiness",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- provider_rerun_ready: `{summary.get('provider_rerun_ready', False)}`",
        f"- provider_backed_authority_proven: `{summary.get('provider_backed_authority_proven', False)}`",
        f"- openai_api_key_present: `{summary.get('openai_api_key_present', False)}`",
        f"- readiness_level: `{summary.get('readiness_level', '')}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        "",
        "## Breadth Rollup Baseline",
        "",
        f"- breadth_rollup pass=`{rollup.get('pass', False)}` issues=`{rollup.get('issues', [])}` {artifact_link(str(rollup.get('path', '') or ''))}",
        f"- seeds: `{rollup.get('seeds', [])}`",
        f"- total_random_cases: `{rollup.get('total_random_cases', '')}`",
        f"- total_selected_count: `{rollup.get('total_selected_count', '')}`",
        f"- total_wrong_fetch_dispatch_count: `{rollup.get('total_wrong_fetch_dispatch_count', '')}`",
        f"- total_contact_watch_count: `{rollup.get('total_contact_watch_count', '')}`",
        f"- total_first_contact_blocker_count: `{rollup.get('total_first_contact_blocker_count', '')}`",
        f"- route_counts: `{rollup.get('route_counts', {})}`",
        f"- provider_status_counts: `{rollup.get('provider_status_counts', {})}`",
        "",
        "## Current Fallback Evidence",
        "",
        f"- latest_fallback_seed pass=`{fallback.get('pass', False)}` issues=`{fallback.get('issues', [])}` {artifact_link(str(fallback.get('path', '') or ''))}",
        f"- seed: `{fallback.get('seed', '')}`",
        f"- random_cases: `{fallback.get('random_cases', '')}`",
        f"- route_counts: `{fallback.get('route_counts', {})}`",
        f"- provider_status_counts: `{fallback.get('provider_status_counts', {})}`",
        "",
        "## Dashboard Evidence",
        "",
        f"- dashboard pass=`{dashboard.get('pass', False)}` issues=`{dashboard.get('issues', [])}` {artifact_link(str(dashboard.get('path', '') or ''))}",
        f"- status_label: `{dashboard.get('status_label', '')}`",
        f"- uat_sample_count: `{dashboard.get('uat_sample_count', 0)}`",
        "",
        "## Blockers",
        "",
    ]
    blockers = summary.get("blockers", []) if isinstance(summary.get("blockers"), list) else []
    if blockers:
        lines.extend(f"- `{blocker}`" for blocker in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Rerun Commands", ""])
    for name, command in commands.items():
        lines.append(f"### {name}")
        lines.append("")
        lines.append("```powershell")
        lines.append(str(command))
        lines.append("```")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check provider-backed planner rerun readiness.")
    parser.add_argument("--campaign-id", default=f"fetch_planner_provider_rerun_readiness_{current_utc_stamp()}")
    parser.add_argument("--latest-fallback-planner-summary", default=DEFAULT_PLANNER_SUMMARY)
    parser.add_argument("--breadth-rollup-summary", default=DEFAULT_BREADTH_ROLLUP)
    parser.add_argument("--dashboard-plan", default=DEFAULT_DASHBOARD_PLAN)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--random-cases", type=int, default=DEFAULT_RANDOM_CASES)
    parser.add_argument("--max-per-route", type=int, default=DEFAULT_MAX_PER_ROUTE)
    parser.add_argument("--min-rollup-random-cases", type=int, default=DEFAULT_MIN_ROLLUP_RANDOM_CASES)
    parser.add_argument("--min-rollup-executable-rows", type=int, default=DEFAULT_MIN_ROLLUP_EXECUTABLE_ROWS)
    parser.add_argument("--dashboard-url", default=DEFAULT_DASHBOARD_URL)
    parser.add_argument("--campaign-suffix", default="20260605")
    parser.add_argument("--openai-api-key", default=os.environ.get("OPENAI_API_KEY", ""))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / ANALYZER_KIND)
    summary = build_summary(args)
    summary_path = root / "provider_rerun_readiness_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["summary_path"] = artifact_display_path(summary_path)
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_PLANNER_PROVIDER_RERUN_READINESS_SUMMARY={summary_path}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
