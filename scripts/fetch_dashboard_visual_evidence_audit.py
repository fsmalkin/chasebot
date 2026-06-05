#!/usr/bin/env python3
"""Audit dashboard browser-watchable fetch evidence links."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
AUDIT_KIND = "fetch_dashboard_visual_evidence_audit"
DEFAULT_DASHBOARD_PLAN = "runtime/dashboard/fetch_plan_data.json"
DEFAULT_MIN_UAT_SAMPLES = 15
DEFAULT_MIN_FILE_BYTES = 1000
REQUIRED_SAMPLE_LINK_KEYS = (
    "video_url",
    "topdown_url",
    "world_url",
    "contact_sheet_url",
    "scorecard_url",
)
REQUIRED_EVIDENCE_TITLES = (
    "Three-seed breadth rollup is green",
    "Seed 20260648 hardware rehearsal is green",
    "Provider rerun preflight is waiting on OPENAI_API_KEY",
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


def url_to_path(url: str) -> Path | None:
    text = str(url or "").strip()
    if not text.startswith("/"):
        return None
    if not text.startswith(("/artifacts/", "/runtime/")):
        return None
    return resolve_path(text.lstrip("/"))


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


def issue_unless(issues: list[str], condition: bool, issue: str) -> None:
    if not condition:
        issues.append(issue)


def audit_url(url: str, *, min_file_bytes: int) -> dict[str, Any]:
    path = url_to_path(url)
    if path is None:
        return {
            "url": str(url or ""),
            "path": "",
            "exists": False,
            "bytes": 0,
            "pass": False,
            "issues": ["url_not_local_artifact"],
        }
    exists = path.is_file()
    size = path.stat().st_size if exists else 0
    issues: list[str] = []
    issue_unless(issues, exists, "linked_file_missing")
    if exists:
        issue_unless(issues, size >= int(min_file_bytes), f"linked_file_below_{int(min_file_bytes)}_bytes")
    return {
        "url": str(url or ""),
        "path": artifact_display_path(path),
        "exists": exists,
        "bytes": size,
        "pass": not issues,
        "issues": issues,
    }


def audit_route_sample(sample: dict[str, Any], *, min_file_bytes: int) -> dict[str, Any]:
    label = str(sample.get("label", "") or "")
    route = str(sample.get("route", "") or "")
    issues: list[str] = []
    link_results: dict[str, Any] = {}
    for key in REQUIRED_SAMPLE_LINK_KEYS:
        url = str(sample.get(key, "") or "")
        if not url:
            issues.append(f"missing_{key}")
            link_results[key] = {"pass": False, "issues": [f"missing_{key}"], "url": ""}
            continue
        result = audit_url(url, min_file_bytes=min_file_bytes)
        link_results[key] = result
        for issue in list_value(result.get("issues")):
            issues.append(f"{key}:{issue}")
    return {
        "label": label,
        "route": route,
        "session_id": str(sample.get("session_id", "") or ""),
        "interpretation": str(sample.get("interpretation", "") or ""),
        "pass": not issues,
        "issues": issues,
        "links": link_results,
    }


def audit_evidence_links(
    cards: list[dict[str, Any]],
    *,
    min_file_bytes: int,
    audit_all_cards: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    cards_by_title = {str(card.get("title", "") or ""): card for card in cards}
    for title in REQUIRED_EVIDENCE_TITLES:
        if title not in cards_by_title:
            issues.append(f"missing_evidence_card:{title}")
    cards_to_audit = cards if audit_all_cards else [cards_by_title[title] for title in REQUIRED_EVIDENCE_TITLES if title in cards_by_title]
    for card in cards_to_audit:
        title = str(card.get("title", "") or "")
        link_rows = []
        card_issues: list[str] = []
        for link in list_value(card.get("links")):
            if not isinstance(link, dict):
                continue
            url = str(link.get("url", "") or "")
            if not url.startswith(("/artifacts/", "/runtime/")):
                continue
            result = audit_url(url, min_file_bytes=min_file_bytes)
            result["label"] = str(link.get("label", "") or "")
            link_rows.append(result)
            for issue in list_value(result.get("issues")):
                card_issues.append(f"{result.get('label', '')}:{issue}")
        rows.append(
            {
                "title": title,
                "tone": str(card.get("tone", "") or ""),
                "link_count": len(link_rows),
                "pass": not card_issues,
                "issues": card_issues,
                "links": link_rows,
            }
        )
        issues.extend(f"evidence_card:{title}:{issue}" for issue in card_issues)
    return rows, issues


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    payload, issues = read_json(str(args.dashboard_plan))
    min_samples = int(args.min_uat_samples)
    min_file_bytes = int(args.min_file_bytes)
    uat = dict_value(payload.get("uat_review_bundle"))
    samples = [row for row in list_value(uat.get("route_samples")) if isinstance(row, dict)]
    sample_rows = [audit_route_sample(sample, min_file_bytes=min_file_bytes) for sample in samples]
    issue_unless(issues, len(samples) >= min_samples, f"uat_sample_count_below_{min_samples}")
    for row in sample_rows:
        for issue in list_value(row.get("issues")):
            issues.append(f"uat_sample:{row.get('label', '')}:{issue}")
    evidence_cards = [row for row in list_value(payload.get("latest_evidence")) if isinstance(row, dict)]
    evidence_rows, evidence_issues = audit_evidence_links(
        evidence_cards,
        min_file_bytes=min_file_bytes,
        audit_all_cards=bool(args.audit_all_evidence_cards),
    )
    issues.extend(evidence_issues)
    route_counts: dict[str, int] = {}
    for row in sample_rows:
        route = str(row.get("route", "") or "")
        route_counts[route] = route_counts.get(route, 0) + 1
    visual_pass = not issues
    return {
        "generated_utc": utc_now(),
        "type": AUDIT_KIND,
        "campaign_id": str(args.campaign_id or ""),
        "pass": visual_pass,
        "promotion_evidence": False,
        "hardware_proven": False,
        "dashboard_plan_path": artifact_display_path(str(args.dashboard_plan)),
        "status_label": str(payload.get("status_label", "") or ""),
        "milestone_interpretation": (
            "dashboard_visual_evidence_links_green"
            if visual_pass
            else "dashboard_visual_evidence_links_incomplete"
        ),
        "issues": issues,
        "min_uat_samples": min_samples,
        "min_file_bytes": min_file_bytes,
        "uat_review_bundle_title": str(uat.get("title", "") or ""),
        "uat_sample_count": len(samples),
        "uat_sample_pass_count": sum(1 for row in sample_rows if bool(row.get("pass", False))),
        "route_counts": route_counts,
        "evidence_card_count": len(evidence_rows),
        "all_evidence_cards_audited": bool(args.audit_all_evidence_cards),
        "evidence_card_pass_count": sum(1 for row in evidence_rows if bool(row.get("pass", False))),
        "uat_samples": sample_rows,
        "evidence_cards": evidence_rows,
    }


def artifact_link(path_text: str) -> str:
    text = str(path_text or "").replace("\\", "/")
    return f"[artifact](/{text})" if text.startswith(("artifacts/", "runtime/")) else text


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Fetch Dashboard Visual Evidence Audit",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- hardware_proven: `{summary.get('hardware_proven', False)}`",
        f"- dashboard_plan: `{summary.get('dashboard_plan_path', '')}`",
        f"- status_label: `{summary.get('status_label', '')}`",
        f"- issues: `{summary.get('issues', [])}`",
        f"- uat_sample_count: `{summary.get('uat_sample_count', 0)}`",
        f"- uat_sample_pass_count: `{summary.get('uat_sample_pass_count', 0)}`",
        f"- evidence_card_count: `{summary.get('evidence_card_count', 0)}`",
        f"- all_evidence_cards_audited: `{summary.get('all_evidence_cards_audited', False)}`",
        f"- evidence_card_pass_count: `{summary.get('evidence_card_pass_count', 0)}`",
        f"- route_counts: `{summary.get('route_counts', {})}`",
        "",
        "## UAT Bundle Samples",
        "",
    ]
    for row in list_value(summary.get("uat_samples")):
        links = dict_value(row.get("links"))
        lines.append(
            f"- `{row.get('label', '')}` route=`{row.get('route', '')}` pass=`{row.get('pass', False)}` "
            f"session=`{row.get('session_id', '')}` issues=`{row.get('issues', [])}`"
        )
        video = dict_value(links.get("video_url"))
        sheet = dict_value(links.get("contact_sheet_url"))
        if video.get("path"):
            lines.append(f"  - onboard: {artifact_link(str(video.get('path', '') or ''))}")
        if sheet.get("path"):
            lines.append(f"  - keyframes: {artifact_link(str(sheet.get('path', '') or ''))}")
    lines.extend(["", "## Evidence Cards", ""])
    for card in list_value(summary.get("evidence_cards")):
        lines.append(
            f"- `{card.get('title', '')}` tone=`{card.get('tone', '')}` pass=`{card.get('pass', False)}` "
            f"links=`{card.get('link_count', 0)}` issues=`{card.get('issues', [])}`"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit dashboard fetch visual evidence links.")
    parser.add_argument("--campaign-id", default=f"fetch_dashboard_visual_evidence_audit_{current_utc_stamp()}")
    parser.add_argument("--dashboard-plan", default=DEFAULT_DASHBOARD_PLAN)
    parser.add_argument("--min-uat-samples", type=int, default=DEFAULT_MIN_UAT_SAMPLES)
    parser.add_argument("--min-file-bytes", type=int, default=DEFAULT_MIN_FILE_BYTES)
    parser.add_argument("--audit-all-evidence-cards", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / AUDIT_KIND)
    summary = build_summary(args)
    summary_path = root / "dashboard_visual_evidence_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["summary_path"] = artifact_display_path(summary_path)
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_DASHBOARD_VISUAL_EVIDENCE_AUDIT_SUMMARY={summary_path}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
