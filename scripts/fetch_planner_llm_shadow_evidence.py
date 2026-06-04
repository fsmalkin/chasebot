#!/usr/bin/env python3
"""Aggregate LLM-shadow planner route evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
EVIDENCE_KIND = "fetch_planner_llm_shadow_evidence"
ROUTE_LABELS = (
    "fetch_ready_local",
    "nav2_reposition_first",
    "scan_or_perceive_first",
    "recovery_or_reaim",
    "ambiguous_or_unsafe_no_go",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


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


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add_counts(target: dict[str, int], source: dict[str, Any]) -> None:
    for key, value in source.items():
        try:
            count = int(value or 0)
        except (TypeError, ValueError):
            count = 0
        target[str(key)] = target.get(str(key), 0) + count


def summarize_gate(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    if not payload:
        return {
            "path": artifact_display_path(path),
            "readable": False,
            "pass": False,
            "blocking_reason": "missing_or_invalid_summary",
        }
    route_counts = payload.get("route_counts", {}) if isinstance(payload.get("route_counts"), dict) else {}
    expected_counts = (
        payload.get("expected_route_counts", {}) if isinstance(payload.get("expected_route_counts"), dict) else {}
    )
    provider_status_counts = (
        payload.get("provider_status_counts", {}) if isinstance(payload.get("provider_status_counts"), dict) else {}
    )
    planner_mode_effective_counts = (
        payload.get("planner_mode_effective_counts", {})
        if isinstance(payload.get("planner_mode_effective_counts"), dict)
        else {}
    )
    total_count = int(payload.get("random_cases", 0) or payload.get("pass_count", 0) or 0)
    provider_ok_count = int(payload.get("llm_shadow_provider_ok_count", provider_status_counts.get("ok", 0)) or 0)
    guard_agreement_count = int(payload.get("guard_agreement_count", 0) or 0)
    wrong_fetch_dispatch_count = int(payload.get("wrong_fetch_dispatch_count", 0) or 0)
    pass_count = int(payload.get("pass_count", 0) or 0)
    llm_shadow_ready = bool(payload.get("llm_shadow_ready", False))
    blocking_reasons: list[str] = []
    if str(payload.get("planner_mode", "") or "") != "llm_shadow":
        blocking_reasons.append("planner_mode_not_llm_shadow")
    if provider_ok_count != total_count:
        blocking_reasons.append("provider_not_ok_for_all_cases")
    if guard_agreement_count != total_count:
        blocking_reasons.append("guard_disagreement")
    if wrong_fetch_dispatch_count:
        blocking_reasons.append("wrong_fetch_dispatch")
    if pass_count != total_count:
        blocking_reasons.append("route_mismatch")
    if not llm_shadow_ready:
        blocking_reasons.append("llm_shadow_not_ready")
    return {
        "campaign_id": str(payload.get("campaign_id", "") or ""),
        "path": artifact_display_path(path),
        "scorecard_path": artifact_display_path(path.with_name("scorecard.md")),
        "readable": True,
        "pass": bool(payload.get("pass", False)),
        "llm_shadow_ready": llm_shadow_ready,
        "total_count": total_count,
        "pass_count": pass_count,
        "fail_count": int(payload.get("fail_count", 0) or 0),
        "provider_ok_count": provider_ok_count,
        "provider_status_counts": {str(key): int(value or 0) for key, value in provider_status_counts.items()},
        "planner_mode_effective_counts": {
            str(key): int(value or 0) for key, value in planner_mode_effective_counts.items()
        },
        "guard_agreement_count": guard_agreement_count,
        "guard_disagreement_count": int(payload.get("guard_disagreement_count", 0) or 0),
        "wrong_fetch_dispatch_count": wrong_fetch_dispatch_count,
        "route_counts": {str(key): int(value or 0) for key, value in route_counts.items()},
        "expected_route_counts": {str(key): int(value or 0) for key, value in expected_counts.items()},
        "scene_set": str(payload.get("scene_set", "") or ""),
        "seed": payload.get("seed"),
        "blocking_reasons": blocking_reasons,
    }


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    gates = [summarize_gate(resolve_path(path)) for path in list(args.planner_summary or [])]
    total_cases = sum(int(gate.get("total_count", 0) or 0) for gate in gates)
    route_counts = {route: 0 for route in ROUTE_LABELS}
    expected_route_counts = {route: 0 for route in ROUTE_LABELS}
    provider_status_counts: dict[str, int] = {}
    planner_mode_effective_counts: dict[str, int] = {}
    for gate in gates:
        add_counts(route_counts, gate.get("route_counts", {}) if isinstance(gate.get("route_counts"), dict) else {})
        add_counts(
            expected_route_counts,
            gate.get("expected_route_counts", {}) if isinstance(gate.get("expected_route_counts"), dict) else {},
        )
        add_counts(
            provider_status_counts,
            gate.get("provider_status_counts", {}) if isinstance(gate.get("provider_status_counts"), dict) else {},
        )
        add_counts(
            planner_mode_effective_counts,
            gate.get("planner_mode_effective_counts", {})
            if isinstance(gate.get("planner_mode_effective_counts"), dict)
            else {},
        )
    provider_ok_count = int(provider_status_counts.get("ok", 0))
    guard_agreement_count = sum(int(gate.get("guard_agreement_count", 0) or 0) for gate in gates)
    wrong_fetch_dispatch_count = sum(int(gate.get("wrong_fetch_dispatch_count", 0) or 0) for gate in gates)
    pass_count = sum(int(gate.get("pass_count", 0) or 0) for gate in gates)
    fail_count = sum(int(gate.get("fail_count", 0) or 0) for gate in gates)
    all_shadow_ready = bool(gates) and all(bool(gate.get("llm_shadow_ready", False)) for gate in gates)
    aggregate_green = bool(
        all_shadow_ready
        and total_cases > 0
        and provider_ok_count == total_cases
        and guard_agreement_count == total_cases
        and wrong_fetch_dispatch_count == 0
        and pass_count == total_cases
        and fail_count == 0
    )
    blocking_reasons = sorted(
        {
            str(reason)
            for gate in gates
            for reason in list(gate.get("blocking_reasons", []) if isinstance(gate.get("blocking_reasons"), list) else [])
            if str(reason)
        }
    )
    summary = {
        "type": EVIDENCE_KIND,
        "campaign_id": str(args.campaign_id or ""),
        "generated_utc": utc_now(),
        "pass": aggregate_green,
        "promotion_evidence": False,
        "milestone_interpretation": (
            "llm_shadow_route_selection_green"
            if aggregate_green
            else "llm_shadow_route_selection_incomplete"
        ),
        "gate_count": len(gates),
        "total_cases": total_cases,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "provider_ok_count": provider_ok_count,
        "provider_status_counts": provider_status_counts,
        "planner_mode_effective_counts": planner_mode_effective_counts,
        "guard_agreement_count": guard_agreement_count,
        "guard_disagreement_count": sum(int(gate.get("guard_disagreement_count", 0) or 0) for gate in gates),
        "wrong_fetch_dispatch_count": wrong_fetch_dispatch_count,
        "all_shadow_ready": all_shadow_ready,
        "route_counts": route_counts,
        "expected_route_counts": expected_route_counts,
        "blocking_reasons": blocking_reasons,
        "gates": gates,
    }
    return summary


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Fetch Planner LLM-Shadow Evidence",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- gates: `{summary.get('gate_count', 0)}`",
        f"- total cases: `{summary.get('total_cases', 0)}`",
        f"- route pass/fail: `{summary.get('pass_count', 0)}/{summary.get('fail_count', 0)}`",
        f"- provider ok: `{summary.get('provider_ok_count', 0)}/{summary.get('total_cases', 0)}`",
        f"- guard agreement: `{summary.get('guard_agreement_count', 0)}/{summary.get('total_cases', 0)}`",
        f"- wrong fetch-ready dispatches: `{summary.get('wrong_fetch_dispatch_count', 0)}`",
        f"- all_shadow_ready: `{summary.get('all_shadow_ready', False)}`",
        f"- provider status counts: `{summary.get('provider_status_counts', {})}`",
        f"- effective planner modes: `{summary.get('planner_mode_effective_counts', {})}`",
        f"- blocking reasons: `{summary.get('blocking_reasons', [])}`",
        "",
        "## Route Totals",
        "",
    ]
    route_counts = summary.get("route_counts", {}) if isinstance(summary.get("route_counts"), dict) else {}
    expected_counts = (
        summary.get("expected_route_counts", {})
        if isinstance(summary.get("expected_route_counts"), dict)
        else {}
    )
    for route in ROUTE_LABELS:
        lines.append(f"- `{route}` expected=`{expected_counts.get(route, 0)}` chosen=`{route_counts.get(route, 0)}`")
    lines.extend(["", "## Gates", ""])
    for gate in list(summary.get("gates", []) if isinstance(summary.get("gates"), list) else []):
        lines.append(
            f"- `{gate.get('campaign_id', '')}` scene_set=`{gate.get('scene_set', '')}` "
            f"seed=`{gate.get('seed', '')}` ready=`{gate.get('llm_shadow_ready', False)}` "
            f"provider_ok=`{gate.get('provider_ok_count', 0)}/{gate.get('total_count', 0)}` "
            f"guard_agree=`{gate.get('guard_agreement_count', 0)}/{gate.get('total_count', 0)}` "
            f"wrong_fetch=`{gate.get('wrong_fetch_dispatch_count', 0)}` "
            f"{artifact_link(str(gate.get('scorecard_path', '') or gate.get('path', '') or ''))}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate LLM-shadow fetch planner route evidence.")
    parser.add_argument("--campaign-id", default=f"fetch_planner_llm_shadow_evidence_{current_utc_stamp()}")
    parser.add_argument("--planner-summary", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / EVIDENCE_KIND)
    summary = build_summary(args)
    summary_path = root / "shadow_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["summary_path"] = artifact_display_path(summary_path)
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_PLANNER_LLM_SHADOW_EVIDENCE_SUMMARY={summary_path}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
