#!/usr/bin/env python3
"""Compare a provider-backed planner rerun against the deterministic baseline."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
ANALYZER_KIND = "fetch_planner_provider_rerun_comparison"
PLANNER_MODE = "llm_supervised_guarded"
ROUTE_LABELS = (
    "fetch_ready_local",
    "nav2_reposition_first",
    "recovery_or_reaim",
    "local_setup_capture",
    "scan_or_perceive_first",
    "ambiguous_or_unsafe_no_go",
)
DEFAULT_BASELINE_ROLLUP = (
    "artifacts/session/analysis_fetch_planner_breadth_rollup_seeds20260648_20260650_20260605/"
    "fetch_planner_breadth_rollup/breadth_rollup_summary.json"
)


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
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # pragma: no cover - defensive artifact parsing
        return {}, [f"invalid_json:{artifact_display_path(path)}:{exc}"]
    if not isinstance(payload, dict):
        return {}, [f"json_not_object:{artifact_display_path(path)}"]
    return payload, []


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def issue_unless(issues: list[str], condition: bool, issue: str) -> None:
    if not condition:
        issues.append(issue)


def summarize_baseline_rollup(path_text: str, *, seed: int, min_random_cases: int) -> dict[str, Any]:
    payload, issues = read_json(path_text)
    rows = [row for row in list_value(payload.get("rows")) if isinstance(row, dict)]
    seed_rows = [row for row in rows if int_value(row.get("seed")) == int(seed)]
    seed_row = seed_rows[0] if seed_rows else {}
    issue_unless(issues, bool(payload.get("pass", False)), "baseline_rollup_not_green")
    issue_unless(
        issues,
        int_value(payload.get("total_random_cases")) >= int(min_random_cases),
        f"baseline_rollup_random_cases_below_{int(min_random_cases)}",
    )
    issue_unless(issues, bool(seed_row), f"baseline_seed_{int(seed)}_missing")
    if seed_row:
        issue_unless(issues, bool(seed_row.get("pass", False)), f"baseline_seed_{int(seed)}_not_green")
        issue_unless(issues, int_value(seed_row.get("wrong_fetch_dispatch_count")) == 0, "baseline_seed_wrong_fetch_nonzero")
    return {
        "path": artifact_display_path(path_text),
        "pass": not issues,
        "issues": issues,
        "seeds": [int_value(row.get("seed")) for row in rows],
        "total_random_cases": int_value(payload.get("total_random_cases")),
        "seed": int(seed),
        "seed_random_cases": int_value(seed_row.get("random_cases")),
        "seed_route_counts": {
            str(key): int_value(value) for key, value in dict_value(seed_row.get("route_counts")).items()
        },
        "seed_scorecard_path": str(seed_row.get("scorecard_path", "") or ""),
    }


def supervised_veto_reason_counts(payload: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in list_value(payload.get("results")):
        if not isinstance(result, dict):
            continue
        guard = dict_value(result.get("llm_supervised_guard"))
        if str(guard.get("decision", "") or "") != "vetoed":
            continue
        for reason in list_value(guard.get("veto_reasons")):
            reason_text = str(reason or "").strip()
            if reason_text:
                counts[reason_text] = counts.get(reason_text, 0) + 1
    return counts


def summarize_provider_planner(path_text: str, *, baseline_routes: dict[str, Any]) -> dict[str, Any]:
    payload, issues = read_json(path_text)
    route_counts = {str(key): int_value(value) for key, value in dict_value(payload.get("route_counts")).items()}
    provider_counts = {
        str(key): int_value(value) for key, value in dict_value(payload.get("provider_status_counts")).items()
    }
    effective_counts = {
        str(key): int_value(value) for key, value in dict_value(payload.get("planner_mode_effective_counts")).items()
    }
    total = int_value(payload.get("random_cases") or payload.get("pass_count"))
    provider_ok = int_value(provider_counts.get("ok"))
    guard_agreement = int_value(payload.get("guard_agreement_count"))
    wrong_fetch = int_value(payload.get("wrong_fetch_dispatch_count"))
    accept_count = int_value(payload.get("llm_supervised_accept_count"))
    veto_count = int_value(payload.get("llm_supervised_veto_count"))
    veto_reasons = supervised_veto_reason_counts(payload)
    non_confidence_veto_reasons = sorted(
        reason for reason in veto_reasons if reason != "confidence_below_threshold"
    )
    issue_unless(issues, str(payload.get("planner_mode", "") or "") == PLANNER_MODE, f"planner_mode_not_{PLANNER_MODE}")
    issue_unless(issues, bool(payload.get("pass", False)), "provider_planner_not_green")
    issue_unless(issues, provider_ok == total and total > 0, "provider_not_ok_for_all_cases")
    issue_unless(issues, guard_agreement == total and total > 0, "guard_agreement_not_all_cases")
    issue_unless(issues, wrong_fetch == 0, "wrong_fetch_dispatch_count_nonzero")
    issue_unless(issues, all(route_counts.get(route, 0) > 0 for route in ROUTE_LABELS), "route_family_coverage_incomplete")
    for reason in non_confidence_veto_reasons:
        issues.append(f"non_confidence_veto:{reason}")
    baseline_int_routes = {str(key): int_value(value) for key, value in baseline_routes.items()}
    route_deltas = {
        route: route_counts.get(route, 0) - baseline_int_routes.get(route, 0)
        for route in ROUTE_LABELS
    }
    return {
        "path": artifact_display_path(path_text),
        "pass": not issues,
        "issues": issues,
        "seed": int_value(payload.get("seed")),
        "random_cases": total,
        "provider_status_counts": provider_counts,
        "planner_mode_effective_counts": effective_counts,
        "provider_ok_count": provider_ok,
        "guard_agreement_count": guard_agreement,
        "wrong_fetch_dispatch_count": wrong_fetch,
        "llm_supervised_accept_count": accept_count,
        "llm_supervised_veto_count": veto_count,
        "llm_supervised_veto_reason_counts": veto_reasons,
        "strict_provider_authority_ready": accept_count == total and veto_count == 0 and provider_ok == total and total > 0,
        "guarded_provider_rerun_ready": not issues,
        "route_counts": route_counts,
        "baseline_route_counts": baseline_int_routes,
        "route_deltas_from_baseline_seed": route_deltas,
    }


def summarize_replay(path_text: str) -> dict[str, Any]:
    if not str(path_text or "").strip():
        return {"provided": False, "pass": False, "issues": ["replay_summary_missing"]}
    payload, issues = read_json(path_text)
    selected = int_value(payload.get("selected_count"))
    mission_fail = int_value(payload.get("mission_fail_count"))
    visual_pass = int_value(payload.get("visual_package_pass_count"))
    issue_unless(issues, bool(payload.get("pass", False)), "replay_not_green")
    issue_unless(issues, selected > 0, "replay_selected_count_zero")
    issue_unless(issues, mission_fail == 0, "replay_mission_fail_nonzero")
    issue_unless(issues, visual_pass == selected, "replay_visual_package_mismatch")
    return {
        "provided": True,
        "path": artifact_display_path(path_text),
        "pass": not issues,
        "issues": issues,
        "selected_count": selected,
        "mission_pass_count": int_value(payload.get("mission_pass_count")),
        "mission_fail_count": mission_fail,
        "visual_package_pass_count": visual_pass,
        "route_only_pass_count": int_value(payload.get("route_only_pass_count")),
        "requested_route_count": {
            str(key): int_value(value) for key, value in dict_value(payload.get("requested_route_count")).items()
        },
    }


def summarize_route_uat(path_text: str) -> dict[str, Any]:
    if not str(path_text or "").strip():
        return {"provided": False, "pass": False, "issues": ["route_uat_summary_missing"]}
    payload, issues = read_json(path_text)
    issue_unless(issues, bool(payload.get("pass", False)), "route_uat_not_green")
    issue_unless(issues, str(payload.get("execution_quality_status", "") or "") == "clean", "execution_quality_not_clean")
    issue_unless(issues, str(payload.get("setup_quality_status", "") or "") == "clean", "setup_quality_not_clean")
    issue_unless(issues, str(payload.get("contact_quality_status", "") or "") == "clean", "contact_quality_not_clean")
    issue_unless(issues, int_value(payload.get("contact_watch_count")) == 0, "contact_watch_nonzero")
    issue_unless(issues, int_value(payload.get("first_contact_blocker_count")) == 0, "first_contact_blocker_nonzero")
    return {
        "provided": True,
        "path": artifact_display_path(path_text),
        "pass": not issues,
        "issues": issues,
        "milestone_interpretation": str(payload.get("milestone_interpretation", "") or ""),
        "execution_quality_status": str(payload.get("execution_quality_status", "") or ""),
        "setup_quality_status": str(payload.get("setup_quality_status", "") or ""),
        "contact_quality_status": str(payload.get("contact_quality_status", "") or ""),
        "contact_watch_count": int_value(payload.get("contact_watch_count")),
        "first_contact_blocker_count": int_value(payload.get("first_contact_blocker_count")),
    }


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    seed = int(args.seed)
    baseline = summarize_baseline_rollup(
        str(args.baseline_rollup_summary),
        seed=seed,
        min_random_cases=int(args.min_baseline_random_cases),
    )
    provider = summarize_provider_planner(
        str(args.provider_planner_summary),
        baseline_routes=dict_value(baseline.get("seed_route_counts")),
    )
    replay = summarize_replay(str(args.provider_replay_summary or ""))
    route_uat = summarize_route_uat(str(args.provider_route_uat_summary or ""))
    blockers: list[str] = []
    for section_name, section in (
        ("baseline_rollup", baseline),
        ("provider_planner", provider),
        ("provider_replay", replay),
        ("provider_route_uat", route_uat),
    ):
        for issue in list_value(section.get("issues")):
            blockers.append(f"{section_name}:{issue}")
    planner_green = bool(baseline.get("pass") and provider.get("pass"))
    replay_green = bool(replay.get("pass") and route_uat.get("pass"))
    green = planner_green and replay_green
    if green and bool(provider.get("strict_provider_authority_ready")):
        interpretation = "provider_rerun_strict_visual_uat_green"
    elif green:
        interpretation = "provider_rerun_guarded_visual_uat_green"
    elif planner_green:
        interpretation = "provider_rerun_planner_green_visual_incomplete"
    else:
        interpretation = "provider_rerun_incomplete"
    return {
        "generated_utc": utc_now(),
        "type": ANALYZER_KIND,
        "campaign_id": str(args.campaign_id or ""),
        "pass": green,
        "promotion_evidence": False,
        "hardware_proven": False,
        "provider_rerun_comparison_ready": green,
        "strict_provider_authority_ready": bool(provider.get("strict_provider_authority_ready", False)),
        "guarded_provider_rerun_ready": bool(provider.get("guarded_provider_rerun_ready", False)),
        "milestone_interpretation": interpretation,
        "blockers": blockers,
        "seed": seed,
        "baseline_rollup": baseline,
        "provider_planner": provider,
        "provider_replay": replay,
        "provider_route_uat": route_uat,
        "claim_boundaries": [
            "provider_comparison_only_until_live_provider_artifacts_exist",
            "promotion_evidence_false_until_canonical_saved_layout_and_seeded_gate_rules_apply",
            "hardware_proven_false_until_physical_onboard_evidence",
        ],
    }


def artifact_link(path_text: str) -> str:
    text = str(path_text or "").replace("\\", "/")
    return f"[artifact](/{text})" if text.startswith(("artifacts/", "runtime/")) else text


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    baseline = dict_value(summary.get("baseline_rollup"))
    provider = dict_value(summary.get("provider_planner"))
    replay = dict_value(summary.get("provider_replay"))
    route_uat = dict_value(summary.get("provider_route_uat"))
    lines = [
        "# Fetch Planner Provider Rerun Comparison",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- seed: `{summary.get('seed', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        f"- provider_rerun_comparison_ready: `{summary.get('provider_rerun_comparison_ready', False)}`",
        f"- strict_provider_authority_ready: `{summary.get('strict_provider_authority_ready', False)}`",
        f"- guarded_provider_rerun_ready: `{summary.get('guarded_provider_rerun_ready', False)}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- hardware_proven: `{summary.get('hardware_proven', False)}`",
        f"- blockers: `{summary.get('blockers', [])}`",
        "",
        "## Baseline",
        "",
        f"- baseline pass=`{baseline.get('pass', False)}` issues=`{baseline.get('issues', [])}` {artifact_link(str(baseline.get('path', '') or ''))}",
        f"- baseline seeds: `{baseline.get('seeds', [])}`",
        f"- baseline seed route counts: `{baseline.get('seed_route_counts', {})}`",
        "",
        "## Provider Planner",
        "",
        f"- provider pass=`{provider.get('pass', False)}` issues=`{provider.get('issues', [])}` {artifact_link(str(provider.get('path', '') or ''))}",
        f"- provider status counts: `{provider.get('provider_status_counts', {})}`",
        f"- effective planner modes: `{provider.get('planner_mode_effective_counts', {})}`",
        f"- guard agreement: `{provider.get('guard_agreement_count', 0)}/{provider.get('random_cases', 0)}`",
        f"- wrong fetch dispatches: `{provider.get('wrong_fetch_dispatch_count', 0)}`",
        f"- accepted/vetoed: `{provider.get('llm_supervised_accept_count', 0)}/{provider.get('llm_supervised_veto_count', 0)}`",
        f"- veto reasons: `{provider.get('llm_supervised_veto_reason_counts', {})}`",
        f"- route counts: `{provider.get('route_counts', {})}`",
        f"- route deltas from baseline seed: `{provider.get('route_deltas_from_baseline_seed', {})}`",
        "",
        "## Visual Replay",
        "",
        f"- replay pass=`{replay.get('pass', False)}` issues=`{replay.get('issues', [])}` {artifact_link(str(replay.get('path', '') or ''))}",
        f"- selected/visual_pass/mission_fail: `{replay.get('selected_count', 0)}/{replay.get('visual_package_pass_count', 0)}/{replay.get('mission_fail_count', 0)}`",
        f"- route_uat pass=`{route_uat.get('pass', False)}` issues=`{route_uat.get('issues', [])}` {artifact_link(str(route_uat.get('path', '') or ''))}",
        f"- route_uat quality: execution=`{route_uat.get('execution_quality_status', '')}` setup=`{route_uat.get('setup_quality_status', '')}` contact=`{route_uat.get('contact_quality_status', '')}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    for boundary in list_value(summary.get("claim_boundaries")):
        lines.append(f"- `{boundary}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare provider rerun evidence with deterministic baseline.")
    parser.add_argument("--campaign-id", default=f"fetch_planner_provider_rerun_comparison_{current_utc_stamp()}")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--baseline-rollup-summary", default=DEFAULT_BASELINE_ROLLUP)
    parser.add_argument("--provider-planner-summary", required=True)
    parser.add_argument("--provider-replay-summary", default="")
    parser.add_argument("--provider-route-uat-summary", default="")
    parser.add_argument("--min-baseline-random-cases", type=int, default=300)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / ANALYZER_KIND)
    summary = build_summary(args)
    summary_path = root / "provider_rerun_comparison_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["summary_path"] = artifact_display_path(summary_path)
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_PLANNER_PROVIDER_RERUN_COMPARISON_SUMMARY={summary_path}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
