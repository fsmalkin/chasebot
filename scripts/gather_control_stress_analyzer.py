#!/usr/bin/env python3
"""Offline hard-case stress analyzer for gather-control branch summaries."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

from llm_supervisor_core import ensure_dir
from llm_supervisor_core import write_json


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_KIND = "gather_control_portfolio"
REQUIRED_FIXTURE_LABELS = ("early_stall", "mid_stall", "late_stall", "terminal_stall")
PASS_KEYS = ("pass", "passed", "fixture_pass", "stress_pass", "branch_pass")
STATUS_PASS_VALUES = ("pass", "passed", "passing", "success", "successful")
STATUS_FAIL_VALUES = ("fail", "failed", "failing", "failure", "unsuccessful")
STATUS_NOT_EVALUATED_VALUES = ("not_evaluated", "not evaluated", "missing", "no_evidence", "unknown")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_branch_name(name: str) -> str:
    """Return a safe artifact directory slug while keeping names recognizable."""
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name or "").strip())
    while ".." in cleaned:
        cleaned = cleaned.replace("..", "_")
    cleaned = re.sub(r"_+", "_", cleaned)
    cleaned = cleaned.strip("._-")
    if not cleaned:
        raise ValueError(f"Invalid empty branch name: {name!r}")
    if cleaned in {".", ".."} or "/" in cleaned or "\\" in cleaned:
        raise ValueError(f"Invalid branch name for artifact path: {name!r}")
    return cleaned


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Campaign summary does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Campaign summary must be a JSON object: {path}")
    return payload


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"} | set(STATUS_PASS_VALUES):
            return True
        if normalized in {"false", "0", "no", "n"} | set(STATUS_FAIL_VALUES):
            return False
    return None


def _status_text(payload: dict[str, Any]) -> str:
    for key in ("status", "result", "verdict", "outcome"):
        value = payload.get(key)
        if value is not None:
            text = str(value).strip().lower()
            if text:
                return text
    return ""


def _fixture_label(payload: dict[str, Any], fallback_label: str = "") -> str:
    for key in ("fixture_label", "label", "name"):
        value = payload.get(key)
        if value is not None:
            label = str(value).strip()
            if label:
                return label
    return fallback_label


def _explicit_fixture_pass(payload: dict[str, Any]) -> bool | None:
    for key in PASS_KEYS:
        if key in payload:
            parsed = _boolish(payload.get(key))
            if parsed is not None:
                return parsed
    status = _status_text(payload)
    if status in STATUS_PASS_VALUES:
        return True
    if status in STATUS_FAIL_VALUES:
        return False
    return None


def _evidence_source_candidates(source_summary: dict[str, Any]) -> list[tuple[str, Any]]:
    hard_case_stress = _dict_value(source_summary.get("hard_case_stress"))
    candidates: list[tuple[str, Any]] = [
        ("stress_fixtures", source_summary.get("stress_fixtures")),
        ("stress_fixture_evidence", source_summary.get("stress_fixture_evidence")),
        ("fixture_evidence", source_summary.get("fixture_evidence")),
        ("fixtures", source_summary.get("fixtures")),
        ("fixture_results", source_summary.get("fixture_results")),
        ("hard_case_stress.fixtures", hard_case_stress.get("fixtures")),
        ("hard_case_stress.fixture_results", hard_case_stress.get("fixture_results")),
        ("hard_case_stress.fixture_evidence", hard_case_stress.get("fixture_evidence")),
    ]
    for run in _list_value(source_summary.get("runs")):
        if isinstance(run, dict):
            candidates.append(("runs", run))
    return candidates


def _iter_fixture_payloads(source_summary: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    fixture_payloads: list[tuple[str, dict[str, Any]]] = []
    for source_key, candidate in _evidence_source_candidates(source_summary):
        if isinstance(candidate, dict):
            for label, payload in candidate.items():
                if isinstance(payload, dict):
                    fixture_payloads.append((source_key, {**payload, "fixture_label": _fixture_label(payload, str(label))}))
            if _fixture_label(candidate):
                fixture_payloads.append((source_key, candidate))
        elif isinstance(candidate, list):
            for payload in candidate:
                if isinstance(payload, dict):
                    fixture_payloads.append((source_key, payload))
    return fixture_payloads


def build_fixture_summary(
    *,
    branch_name: str,
    branch_slug: str,
    source_summary_path: Path,
    source_summary: dict[str, Any],
    fixture_label: str,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for source_key, payload in _iter_fixture_payloads(source_summary):
        if _fixture_label(payload) == fixture_label:
            payload_pass = _explicit_fixture_pass(payload)
            candidates.append(
                {
                    "source_key": source_key,
                    "pass": payload_pass,
                    "status": _status_text(payload),
                    "has_usable_pass_fail": payload_pass is not None,
                    "payload": payload,
                }
            )

    usable = [candidate for candidate in candidates if candidate["has_usable_pass_fail"]]
    if not candidates:
        status = "missing"
        fixture_pass: bool | None = None
        reason = "required_fixture_label_missing"
    elif not usable:
        status = "not_evaluated"
        fixture_pass = None
        reason = "fixture_label_present_without_explicit_pass_fail"
    else:
        fixture_pass = all(bool(candidate["pass"]) for candidate in usable)
        status = "passing" if fixture_pass else "failing"
        reason = "explicit_fixture_evidence_passed" if fixture_pass else "explicit_fixture_evidence_failed"

    return {
        "type": "gather_control_stress_fixture",
        "generated_utc": utc_now(),
        "branch_name": branch_name,
        "branch_slug": branch_slug,
        "source_summary_path": str(source_summary_path),
        "source_campaign_id": str(source_summary.get("campaign_id", "") or ""),
        "fixture_label": fixture_label,
        "status": status,
        "pass": fixture_pass,
        "reason": reason,
        "evidence_count": len(candidates),
        "usable_evidence_count": len(usable),
        "evidence": candidates,
    }


def _branch_status(fixture_summaries: list[dict[str, Any]]) -> str:
    usable_count = sum(1 for fixture in fixture_summaries if int(fixture.get("usable_evidence_count", 0) or 0) > 0)
    if usable_count == 0:
        return "not_evaluated"
    if all(fixture.get("status") == "passing" for fixture in fixture_summaries):
        return "passing"
    return "failing"


def build_branch_stress_summary(
    *,
    branch_name: str,
    source_summary_path: Path,
    source_summary: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    branch_slug = sanitize_branch_name(branch_name)
    fixture_summaries = [
        build_fixture_summary(
            branch_name=branch_name,
            branch_slug=branch_slug,
            source_summary_path=source_summary_path,
            source_summary=source_summary,
            fixture_label=fixture_label,
        )
        for fixture_label in REQUIRED_FIXTURE_LABELS
    ]
    evaluated = [fixture for fixture in fixture_summaries if int(fixture.get("usable_evidence_count", 0) or 0) > 0]
    missing = [fixture["fixture_label"] for fixture in fixture_summaries if fixture.get("status") == "missing"]
    not_evaluated = [fixture["fixture_label"] for fixture in fixture_summaries if fixture.get("status") == "not_evaluated"]
    failing = [fixture["fixture_label"] for fixture in fixture_summaries if fixture.get("status") == "failing"]
    status = _branch_status(fixture_summaries)
    blocking_reasons: list[str] = []
    if missing:
        blocking_reasons.append("missing_required_fixture_evidence")
    if not_evaluated:
        blocking_reasons.append("fixture_label_present_without_explicit_pass_fail")
    if failing:
        blocking_reasons.append("required_fixture_failed")
    if status == "not_evaluated":
        blocking_reasons = ["no_usable_fixture_evidence"]
    return (
        {
            "type": "gather_control_stress_branch",
            "generated_utc": utc_now(),
            "branch_name": branch_name,
            "branch_slug": branch_slug,
            "source_summary_path": str(source_summary_path),
            "source_summary_type": str(source_summary.get("type", "") or ""),
            "source_campaign_id": str(source_summary.get("campaign_id", "") or ""),
            "required_fixture_labels": list(REQUIRED_FIXTURE_LABELS),
            "status": status,
            "evaluated_fixture_labels": [fixture["fixture_label"] for fixture in evaluated],
            "missing_fixture_labels": missing,
            "not_evaluated_fixture_labels": not_evaluated,
            "failing_fixture_labels": failing,
            "passing_fixture_labels": [
                fixture["fixture_label"] for fixture in fixture_summaries if fixture.get("status") == "passing"
            ],
            "usable_fixture_count": len(evaluated),
            "required_fixture_count": len(REQUIRED_FIXTURE_LABELS),
            "blocking_reasons": blocking_reasons,
            "fixtures": {fixture["fixture_label"]: fixture for fixture in fixture_summaries},
        },
        fixture_summaries,
    )


def build_control_stress_summary(
    *,
    campaign_id: str,
    branch_specs: list[tuple[str, Path]],
) -> tuple[dict[str, Any], list[tuple[dict[str, Any], list[dict[str, Any]]]]]:
    seen_slugs: set[str] = set()
    branches: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for branch_name, source_path in branch_specs:
        branch_slug = sanitize_branch_name(branch_name)
        if branch_slug in seen_slugs:
            raise ValueError(f"Duplicate sanitized branch name: {branch_name!r} -> {branch_slug!r}")
        seen_slugs.add(branch_slug)
        source_summary = _load_json_object(source_path)
        branches.append(
            build_branch_stress_summary(
                branch_name=branch_name,
                source_summary_path=source_path,
                source_summary=source_summary,
            )
        )
    branch_summaries = [branch_summary for branch_summary, _ in branches]
    statuses = {str(branch.get("status", "")) for branch in branch_summaries}
    overall_status = "not_evaluated"
    if any(status == "failing" for status in statuses):
        overall_status = "failing"
    elif statuses and statuses == {"passing"}:
        overall_status = "passing"
    elif any(status == "passing" for status in statuses):
        overall_status = "failing"
    return (
        {
            "type": "gather_control_stress",
            "generated_utc": utc_now(),
            "campaign_id": campaign_id,
            "required_fixture_labels": list(REQUIRED_FIXTURE_LABELS),
            "branch_count": len(branch_summaries),
            "status": overall_status,
            "branches": branch_summaries,
        },
        branches,
    )


def build_scorecard_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Gather Control Stress",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- status: `{summary.get('status', '')}`",
        "",
        "| branch | status | evaluated | passing | failing | missing | blockers |",
        "|---|---|---:|---|---|---|---|",
    ]
    for branch in summary.get("branches", []):
        blockers = branch.get("blocking_reasons", [])
        if not isinstance(blockers, list):
            blockers = []
        lines.append(
            "| "
            f"`{branch.get('branch_name', '')}` | "
            f"`{branch.get('status', '')}` | "
            f"{int(branch.get('usable_fixture_count', 0) or 0)} / {int(branch.get('required_fixture_count', 0) or 0)} | "
            f"`{', '.join(str(item) for item in branch.get('passing_fixture_labels', [])) or 'none'}` | "
            f"`{', '.join(str(item) for item in branch.get('failing_fixture_labels', [])) or 'none'}` | "
            f"`{', '.join(str(item) for item in branch.get('missing_fixture_labels', [])) or 'none'}` | "
            f"`{', '.join(str(item) for item in blockers) if blockers else 'none'}` |"
        )
    lines.append("")
    return "\n".join(lines)


def write_control_stress_bundle(
    *,
    repo_root: Path,
    campaign_id: str,
    summary: dict[str, Any],
    branch_bundles: list[tuple[dict[str, Any], list[dict[str, Any]]]],
) -> dict[str, Path]:
    output_root = ensure_dir(repo_root / "artifacts" / "session" / campaign_id / OUTPUT_KIND)
    summary_path = output_root / "stress_summary.json"
    scorecard_path = output_root / "stress_scorecard.md"
    for branch_summary, fixture_summaries in branch_bundles:
        branch_slug = sanitize_branch_name(str(branch_summary.get("branch_slug") or branch_summary.get("branch_name") or "branch"))
        branch_root = ensure_dir(output_root / branch_slug)
        fixtures_root = ensure_dir(branch_root / "fixtures")
        write_json(branch_root / "stress_summary.json", branch_summary)
        for fixture_summary in fixture_summaries:
            fixture_label = str(fixture_summary.get("fixture_label", "") or "")
            if fixture_label not in REQUIRED_FIXTURE_LABELS:
                raise ValueError(f"Unexpected fixture label while writing bundle: {fixture_label!r}")
            write_json(fixtures_root / f"{fixture_label}.json", fixture_summary)
    write_json(summary_path, summary)
    scorecard_path.write_text(build_scorecard_markdown(summary), encoding="utf-8")
    return {"output_root": output_root, "summary_path": summary_path, "scorecard_path": scorecard_path}


def parse_branch_spec(spec: str) -> tuple[str, Path]:
    if "=" not in spec:
        raise argparse.ArgumentTypeError(f"--branch must be name=path, got {spec!r}")
    name, path_text = spec.split("=", 1)
    name = name.strip()
    path_text = path_text.strip()
    if not name or not path_text:
        raise argparse.ArgumentTypeError(f"--branch must be name=path, got {spec!r}")
    sanitize_branch_name(name)
    return name, Path(path_text)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True, help="Stress-analysis artifact campaign id.")
    parser.add_argument(
        "--branch",
        action="append",
        required=True,
        type=parse_branch_spec,
        help="Branch spec as name=path/to/gather_mission_repeatability/campaign_run_summary.json. Repeatable.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    campaign_id = str(args.campaign_id or "").strip()
    if not campaign_id:
        raise ValueError("--campaign-id must not be empty")
    branch_specs: list[tuple[str, Path]] = []
    for name, path in args.branch:
        source_path = path if path.is_absolute() else (REPO_ROOT / path)
        branch_specs.append((name, source_path))
    summary, branch_bundles = build_control_stress_summary(campaign_id=campaign_id, branch_specs=branch_specs)
    paths = write_control_stress_bundle(
        repo_root=REPO_ROOT,
        campaign_id=campaign_id,
        summary=summary,
        branch_bundles=branch_bundles,
    )
    print(f"GATHER_CONTROL_STRESS_SUMMARY={paths['summary_path']}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
