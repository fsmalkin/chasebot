#!/usr/bin/env python3
"""Build an operator watchlist from the current fetch dashboard UAT bundle."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
WATCHLIST_KIND = "fetch_dashboard_uat_watchlist"
DEFAULT_DASHBOARD_PLAN = "runtime/dashboard/fetch_plan_data.json"
ROUTE_ORDER = (
    "ambiguous_or_unsafe_no_go",
    "scan_or_perceive_first",
    "recovery_or_reaim",
    "nav2_reposition_first",
    "fetch_ready_local",
)
PLANNER_ONLY_ROUTES = {"ambiguous_or_unsafe_no_go", "scan_or_perceive_first"}


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


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def issue_unless(issues: list[str], condition: bool, issue: str) -> None:
    if not condition:
        issues.append(issue)


def link_path_exists(url: str) -> bool:
    text = str(url or "")
    if not text.startswith("/artifacts/"):
        return False
    return resolve_path(text.lstrip("/")).is_file()


def row_contract(route: str) -> str:
    return "planner_only_abstention" if route in PLANNER_ONLY_ROUTES else "delivery_pass"


def summarize_sample(sample: dict[str, Any]) -> dict[str, Any]:
    route = str(sample.get("route", "") or "")
    interpretation = str(sample.get("interpretation", "") or "")
    contract = row_contract(route)
    issues: list[str] = []
    issue_unless(issues, route in ROUTE_ORDER, f"unknown_route:{route}")
    if contract == "planner_only_abstention":
        issue_unless(issues, "abstention" in interpretation, "planner_only_interpretation_missing")
    else:
        issue_unless(issues, "delivery pass" in interpretation, "delivery_interpretation_missing")
    for key in ("video_url", "topdown_url", "world_url", "contact_sheet_url", "scorecard_url"):
        issue_unless(issues, link_path_exists(str(sample.get(key, "") or "")), f"{key}_missing")
    return {
        "label": str(sample.get("label", "") or ""),
        "route": route,
        "session_id": str(sample.get("session_id", "") or ""),
        "contract": contract,
        "interpretation": interpretation,
        "pass": not issues,
        "issues": issues,
        "watch_order": [
            {"label": "onboard", "url": str(sample.get("video_url", "") or "")},
            {"label": "keyframes", "url": str(sample.get("contact_sheet_url", "") or "")},
            {"label": "topdown", "url": str(sample.get("topdown_url", "") or "")},
            {"label": "world", "url": str(sample.get("world_url", "") or "")},
            {"label": "scorecard", "url": str(sample.get("scorecard_url", "") or "")},
        ],
    }


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    payload, issues = read_json(args.dashboard_plan)
    uat = dict_value(payload.get("uat_review_bundle"))
    samples = [dict_value(row) for row in list_value(uat.get("route_samples")) if isinstance(row, dict)]
    rows = [summarize_sample(sample) for sample in samples]
    route_counts: dict[str, int] = {}
    for row in rows:
        route_counts[row["route"]] = route_counts.get(row["route"], 0) + 1
        issues.extend(f"{row['label']}:{issue}" for issue in list_value(row.get("issues")))
    for route in ROUTE_ORDER:
        issue_unless(issues, route_counts.get(route, 0) >= int(args.min_per_route), f"{route}_below_{int(args.min_per_route)}")
    recommended = []
    for route in ROUTE_ORDER:
        recommended.extend(row for row in rows if row["route"] == route)
    return {
        "generated_utc": utc_now(),
        "type": WATCHLIST_KIND,
        "campaign_id": str(args.campaign_id),
        "pass": not issues,
        "promotion_evidence": False,
        "hardware_proven": False,
        "dashboard_plan_path": artifact_display_path(args.dashboard_plan),
        "uat_review_bundle_title": str(uat.get("title", "") or ""),
        "sample_count": len(rows),
        "route_counts": route_counts,
        "issues": issues,
        "milestone_interpretation": "dashboard_uat_watchlist_ready" if not issues else "dashboard_uat_watchlist_incomplete",
        "review_guidance": [
            "watch onboard raw_camera_browser first",
            "cross-check keyframe sheet across start/setup, first contact or abstention, mid-push/coast, terminal arrival, and final rest",
            "use topdown/world streams only after onboard sanity check",
            "planner-only routes should visibly withhold local fetch",
            "delivery routes should visibly reach the delivery circle without relying on telemetry alone",
        ],
        "recommended_watchlist": recommended,
    }


def artifact_link(path_text: str) -> str:
    text = str(path_text or "")
    return f"[artifact]({text})" if text.startswith("/artifacts/") else text


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Fetch Dashboard UAT Watchlist",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        f"- sample_count: `{summary.get('sample_count', 0)}`",
        f"- route_counts: `{summary.get('route_counts', {})}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- hardware_proven: `{summary.get('hardware_proven', False)}`",
        f"- issues: `{summary.get('issues', [])}`",
        "",
        "## Review Guidance",
        "",
    ]
    for item in list_value(summary.get("review_guidance")):
        lines.append(f"- {item}")
    lines.extend(["", "## Recommended Watchlist", ""])
    for row in list_value(summary.get("recommended_watchlist")):
        links = {item["label"]: item["url"] for item in list_value(dict_value(row).get("watch_order")) if isinstance(item, dict)}
        lines.append(
            f"- `{dict_value(row).get('label', '')}` route=`{dict_value(row).get('route', '')}` "
            f"contract=`{dict_value(row).get('contract', '')}` onboard={artifact_link(links.get('onboard', ''))} "
            f"keyframes={artifact_link(links.get('keyframes', ''))}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a dashboard UAT watchlist from route samples.")
    parser.add_argument("--campaign-id", default=f"fetch_dashboard_uat_watchlist_{current_utc_stamp()}")
    parser.add_argument("--dashboard-plan", default=DEFAULT_DASHBOARD_PLAN)
    parser.add_argument("--min-per-route", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / WATCHLIST_KIND)
    summary = build_summary(args)
    summary_path = root / "uat_watchlist_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["summary_path"] = artifact_display_path(summary_path)
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_DASHBOARD_UAT_WATCHLIST_SUMMARY={summary_path}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
