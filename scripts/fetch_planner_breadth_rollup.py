#!/usr/bin/env python3
"""Roll up planner-routed fetch breadth evidence across seeded gates."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
ROLLUP_KIND = "fetch_planner_breadth_rollup"


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


def add_counts(target: dict[str, int], source: dict[str, Any]) -> None:
    for key, value in source.items():
        target[str(key)] = target.get(str(key), 0) + int_value(value)


def summarize_gate(path_text: str | Path) -> dict[str, Any]:
    gate, issues = read_json(path_text)
    planner = dict_value(gate.get("planner_summary"))
    replay = dict_value(gate.get("replay_summary"))
    analyzer = dict_value(gate.get("analyzer_summary"))
    seed = gate.get("seed")
    gate_pass = bool(gate.get("pass", False))
    wrong_fetch = int_value(planner.get("wrong_fetch_dispatch_count"))
    selected = int_value(replay.get("selected_count"))
    mission_pass = int_value(replay.get("mission_pass_count"))
    mission_fail = int_value(replay.get("mission_fail_count"))
    visual_pass = int_value(replay.get("visual_package_pass_count"))
    contact_watch = int_value(analyzer.get("contact_watch_count"))
    first_contact_blockers = int_value(analyzer.get("first_contact_blocker_count"))
    provider_counts = dict_value(planner.get("provider_status_counts"))
    deterministic_count = int_value(dict_value(planner.get("planner_mode_effective_counts")).get("deterministic_fallback"))
    provider_ok_count = int_value(provider_counts.get("ok"))
    row_issues = list(issues)
    if not gate_pass:
        row_issues.append("gate_not_pass")
    if wrong_fetch:
        row_issues.append("wrong_fetch_dispatch_nonzero")
    if mission_fail:
        row_issues.append("mission_fail_nonzero")
    if selected and visual_pass != selected:
        row_issues.append("visual_package_count_mismatch")
    if contact_watch:
        row_issues.append("contact_watch_nonzero")
    if first_contact_blockers:
        row_issues.append("first_contact_blocker_nonzero")
    return {
        "path": artifact_display_path(path_text),
        "seed": seed,
        "pass": not row_issues,
        "issues": row_issues,
        "random_cases": int_value(gate.get("random_cases")),
        "planner_pass_count": int_value(planner.get("pass_count")),
        "planner_fail_count": int_value(planner.get("fail_count")),
        "wrong_fetch_dispatch_count": wrong_fetch,
        "route_counts": {str(key): int_value(value) for key, value in dict_value(planner.get("route_counts")).items()},
        "provider_status_counts": {str(key): int_value(value) for key, value in provider_counts.items()},
        "deterministic_fallback_count": deterministic_count,
        "provider_ok_count": provider_ok_count,
        "selected_count": selected,
        "mission_pass_count": mission_pass,
        "mission_fail_count": mission_fail,
        "visual_package_pass_count": visual_pass,
        "contact_watch_count": contact_watch,
        "first_contact_blocker_count": first_contact_blockers,
        "execution_quality_status": str(analyzer.get("execution_quality_status", "") or ""),
        "setup_quality_status": str(analyzer.get("setup_quality_status", "") or ""),
        "contact_quality_status": str(analyzer.get("contact_quality_status", "") or ""),
        "scorecard_path": str(gate.get("scorecard_path", "") or ""),
        "planner_summary_path": str(gate.get("planner_summary_path", "") or ""),
        "replay_summary_path": str(gate.get("replay_summary_path", "") or ""),
        "analyzer_summary_path": str(gate.get("analyzer_summary_path", "") or ""),
    }


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    rows = [summarize_gate(path) for path in list_value(args.gate_summary)]
    issues: list[str] = []
    if not rows:
        issues.append("gate_summaries_missing")
    for row in rows:
        issues.extend(f"seed{row.get('seed')}:{issue}" for issue in list_value(row.get("issues")))
    route_counts: dict[str, int] = {}
    provider_counts: dict[str, int] = {}
    for row in rows:
        add_counts(route_counts, dict_value(row.get("route_counts")))
        add_counts(provider_counts, dict_value(row.get("provider_status_counts")))
    total_random_cases = sum(int_value(row.get("random_cases")) for row in rows)
    total_planner_pass = sum(int_value(row.get("planner_pass_count")) for row in rows)
    total_wrong_fetch = sum(int_value(row.get("wrong_fetch_dispatch_count")) for row in rows)
    total_selected = sum(int_value(row.get("selected_count")) for row in rows)
    total_mission_pass = sum(int_value(row.get("mission_pass_count")) for row in rows)
    total_mission_fail = sum(int_value(row.get("mission_fail_count")) for row in rows)
    total_visual_pass = sum(int_value(row.get("visual_package_pass_count")) for row in rows)
    total_contact_watch = sum(int_value(row.get("contact_watch_count")) for row in rows)
    total_first_contact_blockers = sum(int_value(row.get("first_contact_blocker_count")) for row in rows)
    provider_ok_count = int_value(provider_counts.get("ok"))
    deterministic_count = sum(int_value(row.get("deterministic_fallback_count")) for row in rows)
    provider_backed_authority_ready = provider_ok_count == total_random_cases and total_random_cases > 0
    broad_deterministic_green = (
        not issues
        and total_random_cases > 0
        and total_planner_pass == total_random_cases
        and total_wrong_fetch == 0
        and total_mission_fail == 0
        and total_selected == total_visual_pass
        and total_contact_watch == 0
        and total_first_contact_blockers == 0
    )
    return {
        "generated_utc": utc_now(),
        "type": ROLLUP_KIND,
        "campaign_id": str(args.campaign_id),
        "pass": broad_deterministic_green,
        "promotion_evidence": False,
        "provider_backed_authority_ready": provider_backed_authority_ready,
        "hardware_proven": False,
        "milestone_interpretation": (
            "planner_routed_multi_seed_breadth_green"
            if broad_deterministic_green
            else "planner_routed_multi_seed_breadth_incomplete"
        ),
        "issues": issues,
        "gate_count": len(rows),
        "seeds": [row.get("seed") for row in rows],
        "total_random_cases": total_random_cases,
        "total_planner_pass_count": total_planner_pass,
        "total_wrong_fetch_dispatch_count": total_wrong_fetch,
        "route_counts": route_counts,
        "provider_status_counts": provider_counts,
        "deterministic_fallback_count": deterministic_count,
        "provider_ok_count": provider_ok_count,
        "total_selected_count": total_selected,
        "total_mission_pass_count": total_mission_pass,
        "total_mission_fail_count": total_mission_fail,
        "total_visual_package_pass_count": total_visual_pass,
        "total_contact_watch_count": total_contact_watch,
        "total_first_contact_blocker_count": total_first_contact_blockers,
        "claim_boundaries": [
            "deterministic_fallback_evidence_only_until_provider_ok_rerun",
            "hardware_proven_false_until_physical_onboard_evidence",
            "promotion_evidence_false_for_visual_uat_rollup",
        ],
        "rows": rows,
    }


def artifact_link(path_text: str) -> str:
    text = str(path_text or "").replace("\\", "/")
    return f"[artifact](/{text})" if text.startswith("artifacts/") else text


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Fetch Planner Breadth Rollup",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- provider_backed_authority_ready: `{summary.get('provider_backed_authority_ready', False)}`",
        f"- hardware_proven: `{summary.get('hardware_proven', False)}`",
        f"- issues: `{summary.get('issues', [])}`",
        "",
        "## Totals",
        "",
        f"- seeds: `{summary.get('seeds', [])}`",
        f"- random_cases: `{summary.get('total_random_cases', 0)}`",
        f"- planner_pass: `{summary.get('total_planner_pass_count', 0)}`",
        f"- wrong_fetch_dispatches: `{summary.get('total_wrong_fetch_dispatch_count', 0)}`",
        f"- selected_executable_rows: `{summary.get('total_selected_count', 0)}`",
        f"- mission_pass: `{summary.get('total_mission_pass_count', 0)}`",
        f"- mission_fail: `{summary.get('total_mission_fail_count', 0)}`",
        f"- visual_package_pass: `{summary.get('total_visual_package_pass_count', 0)}`",
        f"- contact_watches: `{summary.get('total_contact_watch_count', 0)}`",
        f"- first_contact_blockers: `{summary.get('total_first_contact_blocker_count', 0)}`",
        f"- provider_status_counts: `{summary.get('provider_status_counts', {})}`",
        f"- route_counts: `{summary.get('route_counts', {})}`",
        "",
        "## Claim Boundaries",
        "",
    ]
    for boundary in list_value(summary.get("claim_boundaries")):
        lines.append(f"- `{boundary}`")
    lines.extend(["", "## Gates", ""])
    for row in list_value(summary.get("rows")):
        if not isinstance(row, dict):
            continue
        lines.append(
            f"- seed `{row.get('seed', '')}` pass=`{row.get('pass', False)}` "
            f"random_cases=`{row.get('random_cases', 0)}` selected=`{row.get('selected_count', 0)}` "
            f"mission_pass=`{row.get('mission_pass_count', 0)}` visual_pass=`{row.get('visual_package_pass_count', 0)}` "
            f"contact_watches=`{row.get('contact_watch_count', 0)}` "
            f"first_contact_blockers=`{row.get('first_contact_blocker_count', 0)}` "
            f"{artifact_link(str(row.get('scorecard_path', '') or row.get('path', '')))}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Roll up planner-routed fetch seeded breadth evidence.")
    parser.add_argument("--campaign-id", default=f"fetch_planner_breadth_rollup_{current_utc_stamp()}")
    parser.add_argument("--gate-summary", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / ROLLUP_KIND)
    summary = build_summary(args)
    summary_path = root / "breadth_rollup_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["summary_path"] = artifact_display_path(summary_path)
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_PLANNER_BREADTH_ROLLUP_SUMMARY={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
