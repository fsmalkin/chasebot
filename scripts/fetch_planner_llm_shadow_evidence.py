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
PLANNER_MODE_LLM_SHADOW = "llm_shadow"
PLANNER_MODE_LLM_SUPERVISED_GUARDED = "llm_supervised_guarded"
PLANNER_MODES = (PLANNER_MODE_LLM_SHADOW, PLANNER_MODE_LLM_SUPERVISED_GUARDED)
EVIDENCE_KIND_BY_MODE = {
    PLANNER_MODE_LLM_SHADOW: "fetch_planner_llm_shadow_evidence",
    PLANNER_MODE_LLM_SUPERVISED_GUARDED: "fetch_planner_llm_supervised_evidence",
}
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


def supervised_veto_reason_counts(payload: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in list(payload.get("results", []) if isinstance(payload.get("results"), list) else []):
        guard = result.get("llm_supervised_guard", {}) if isinstance(result.get("llm_supervised_guard"), dict) else {}
        if str(guard.get("decision", "") or "") != "vetoed":
            continue
        for reason in list(guard.get("veto_reasons", []) if isinstance(guard.get("veto_reasons"), list) else []):
            reason_text = str(reason or "").strip()
            if reason_text:
                counts[reason_text] = counts.get(reason_text, 0) + 1
    return counts


def evidence_kind_for_mode(expected_planner_mode: str) -> str:
    return EVIDENCE_KIND_BY_MODE.get(str(expected_planner_mode or ""), EVIDENCE_KIND_BY_MODE[PLANNER_MODE_LLM_SHADOW])


def readiness_field_for_mode(expected_planner_mode: str) -> str:
    if str(expected_planner_mode or "") == PLANNER_MODE_LLM_SUPERVISED_GUARDED:
        return "llm_supervised_ready"
    return "llm_shadow_ready"


def interpretation_for_mode(expected_planner_mode: str, *, green: bool) -> str:
    if str(expected_planner_mode or "") == PLANNER_MODE_LLM_SUPERVISED_GUARDED:
        return "llm_supervised_route_selection_green" if green else "llm_supervised_route_selection_incomplete"
    return "llm_shadow_route_selection_green" if green else "llm_shadow_route_selection_incomplete"


def summarize_gate(path: Path, *, expected_planner_mode: str = PLANNER_MODE_LLM_SHADOW) -> dict[str, Any]:
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
    readiness_field = readiness_field_for_mode(expected_planner_mode)
    ready = bool(payload.get(readiness_field, False))
    llm_supervised_accept_count = int(payload.get("llm_supervised_accept_count", 0) or 0)
    llm_supervised_veto_count = int(payload.get("llm_supervised_veto_count", 0) or 0)
    veto_reason_counts = supervised_veto_reason_counts(payload)
    blocking_reasons: list[str] = []
    watch_reasons: list[str] = []
    if str(payload.get("planner_mode", "") or "") != str(expected_planner_mode or ""):
        blocking_reasons.append(f"planner_mode_not_{expected_planner_mode}")
    if provider_ok_count != total_count:
        blocking_reasons.append("provider_not_ok_for_all_cases")
    if guard_agreement_count != total_count:
        blocking_reasons.append("guard_disagreement")
    if wrong_fetch_dispatch_count:
        blocking_reasons.append("wrong_fetch_dispatch")
    if pass_count != total_count:
        blocking_reasons.append("route_mismatch")
    if str(expected_planner_mode or "") == PLANNER_MODE_LLM_SUPERVISED_GUARDED:
        if llm_supervised_accept_count != total_count:
            watch_reasons.append("supervised_not_accepted_for_all_cases")
        if llm_supervised_veto_count:
            watch_reasons.append("supervised_veto_present")
        non_confidence_vetoes = sorted(
            reason for reason in veto_reason_counts if reason != "confidence_below_threshold"
        )
        if non_confidence_vetoes:
            blocking_reasons.extend(f"supervised_veto_{reason}" for reason in non_confidence_vetoes)
    if not ready:
        if str(expected_planner_mode or "") == PLANNER_MODE_LLM_SUPERVISED_GUARDED:
            watch_reasons.append(f"{readiness_field}_not_ready")
        else:
            blocking_reasons.append(f"{readiness_field}_not_ready")
    return {
        "campaign_id": str(payload.get("campaign_id", "") or ""),
        "path": artifact_display_path(path),
        "scorecard_path": artifact_display_path(path.with_name("scorecard.md")),
        "readable": True,
        "pass": bool(payload.get("pass", False)),
        "ready": ready,
        "llm_shadow_ready": bool(payload.get("llm_shadow_ready", False)),
        "llm_supervised_ready": bool(payload.get("llm_supervised_ready", False)),
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
        "llm_supervised_accept_count": llm_supervised_accept_count,
        "llm_supervised_veto_count": llm_supervised_veto_count,
        "llm_supervised_veto_reason_counts": veto_reason_counts,
        "route_counts": {str(key): int(value or 0) for key, value in route_counts.items()},
        "expected_route_counts": {str(key): int(value or 0) for key, value in expected_counts.items()},
        "scene_set": str(payload.get("scene_set", "") or ""),
        "seed": payload.get("seed"),
        "blocking_reasons": blocking_reasons,
        "watch_reasons": watch_reasons,
    }


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    expected_planner_mode = str(getattr(args, "expected_planner_mode", PLANNER_MODE_LLM_SHADOW) or PLANNER_MODE_LLM_SHADOW)
    gates = [
        summarize_gate(resolve_path(path), expected_planner_mode=expected_planner_mode)
        for path in list(args.planner_summary or [])
    ]
    total_cases = sum(int(gate.get("total_count", 0) or 0) for gate in gates)
    route_counts = {route: 0 for route in ROUTE_LABELS}
    expected_route_counts = {route: 0 for route in ROUTE_LABELS}
    provider_status_counts: dict[str, int] = {}
    planner_mode_effective_counts: dict[str, int] = {}
    llm_supervised_veto_reason_counts: dict[str, int] = {}
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
        add_counts(
            llm_supervised_veto_reason_counts,
            gate.get("llm_supervised_veto_reason_counts", {})
            if isinstance(gate.get("llm_supervised_veto_reason_counts"), dict)
            else {},
        )
    provider_ok_count = int(provider_status_counts.get("ok", 0))
    guard_agreement_count = sum(int(gate.get("guard_agreement_count", 0) or 0) for gate in gates)
    wrong_fetch_dispatch_count = sum(int(gate.get("wrong_fetch_dispatch_count", 0) or 0) for gate in gates)
    pass_count = sum(int(gate.get("pass_count", 0) or 0) for gate in gates)
    fail_count = sum(int(gate.get("fail_count", 0) or 0) for gate in gates)
    llm_supervised_accept_count = sum(int(gate.get("llm_supervised_accept_count", 0) or 0) for gate in gates)
    llm_supervised_veto_count = sum(int(gate.get("llm_supervised_veto_count", 0) or 0) for gate in gates)
    all_ready = bool(gates) and all(bool(gate.get("ready", False)) for gate in gates)
    aggregate_green = bool(
        all_ready
        and total_cases > 0
        and provider_ok_count == total_cases
        and guard_agreement_count == total_cases
        and wrong_fetch_dispatch_count == 0
        and pass_count == total_cases
        and fail_count == 0
        and (
            expected_planner_mode != PLANNER_MODE_LLM_SUPERVISED_GUARDED
            or (llm_supervised_accept_count == total_cases and llm_supervised_veto_count == 0)
        )
    )
    supervised_guarded_fallback_green = bool(
        expected_planner_mode == PLANNER_MODE_LLM_SUPERVISED_GUARDED
        and total_cases > 0
        and provider_ok_count == total_cases
        and guard_agreement_count == total_cases
        and wrong_fetch_dispatch_count == 0
        and pass_count == total_cases
        and fail_count == 0
        and set(llm_supervised_veto_reason_counts).issubset({"confidence_below_threshold"})
    )
    pass_green = aggregate_green or supervised_guarded_fallback_green
    blocking_reasons = sorted(
        {
            str(reason)
            for gate in gates
            for reason in list(gate.get("blocking_reasons", []) if isinstance(gate.get("blocking_reasons"), list) else [])
            if str(reason)
        }
    )
    watch_reasons = sorted(
        {
            str(reason)
            for gate in gates
            for reason in list(gate.get("watch_reasons", []) if isinstance(gate.get("watch_reasons"), list) else [])
            if str(reason)
        }
    )
    interpretation = interpretation_for_mode(expected_planner_mode, green=pass_green)
    if supervised_guarded_fallback_green and not aggregate_green:
        interpretation = "llm_supervised_guarded_fallback_green"
    summary = {
        "type": evidence_kind_for_mode(expected_planner_mode),
        "campaign_id": str(args.campaign_id or ""),
        "generated_utc": utc_now(),
        "expected_planner_mode": expected_planner_mode,
        "pass": pass_green,
        "promotion_evidence": False,
        "milestone_interpretation": interpretation,
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
        "llm_supervised_accept_count": llm_supervised_accept_count,
        "llm_supervised_veto_count": llm_supervised_veto_count,
        "llm_supervised_veto_reason_counts": llm_supervised_veto_reason_counts,
        "strict_supervised_acceptance_ready": aggregate_green
        if expected_planner_mode == PLANNER_MODE_LLM_SUPERVISED_GUARDED
        else False,
        "supervised_guarded_fallback_ready": supervised_guarded_fallback_green,
        "all_shadow_ready": all_ready if expected_planner_mode == PLANNER_MODE_LLM_SHADOW else False,
        "all_supervised_ready": all_ready if expected_planner_mode == PLANNER_MODE_LLM_SUPERVISED_GUARDED else False,
        "route_counts": route_counts,
        "expected_route_counts": expected_route_counts,
        "blocking_reasons": blocking_reasons,
        "watch_reasons": watch_reasons,
        "gates": gates,
    }
    return summary


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    expected_planner_mode = str(summary.get("expected_planner_mode", PLANNER_MODE_LLM_SHADOW) or PLANNER_MODE_LLM_SHADOW)
    is_supervised = expected_planner_mode == PLANNER_MODE_LLM_SUPERVISED_GUARDED
    title = "Fetch Planner LLM-Supervised Evidence" if is_supervised else "Fetch Planner LLM-Shadow Evidence"
    ready_label = "all_supervised_ready" if is_supervised else "all_shadow_ready"
    lines = [
        f"# {title}",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- expected_planner_mode: `{expected_planner_mode}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- gates: `{summary.get('gate_count', 0)}`",
        f"- total cases: `{summary.get('total_cases', 0)}`",
        f"- route pass/fail: `{summary.get('pass_count', 0)}/{summary.get('fail_count', 0)}`",
        f"- provider ok: `{summary.get('provider_ok_count', 0)}/{summary.get('total_cases', 0)}`",
        f"- guard agreement: `{summary.get('guard_agreement_count', 0)}/{summary.get('total_cases', 0)}`",
        f"- wrong fetch-ready dispatches: `{summary.get('wrong_fetch_dispatch_count', 0)}`",
        f"- {ready_label}: `{summary.get(ready_label, False)}`",
        f"- llm_supervised accepted/vetoed: `{summary.get('llm_supervised_accept_count', 0)}/{summary.get('llm_supervised_veto_count', 0)}`",
        f"- llm_supervised veto reasons: `{summary.get('llm_supervised_veto_reason_counts', {})}`",
        f"- strict_supervised_acceptance_ready: `{summary.get('strict_supervised_acceptance_ready', False)}`",
        f"- supervised_guarded_fallback_ready: `{summary.get('supervised_guarded_fallback_ready', False)}`",
        f"- provider status counts: `{summary.get('provider_status_counts', {})}`",
        f"- effective planner modes: `{summary.get('planner_mode_effective_counts', {})}`",
        f"- blocking reasons: `{summary.get('blocking_reasons', [])}`",
        f"- watch reasons: `{summary.get('watch_reasons', [])}`",
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
            f"seed=`{gate.get('seed', '')}` ready=`{gate.get('ready', False)}` "
            f"provider_ok=`{gate.get('provider_ok_count', 0)}/{gate.get('total_count', 0)}` "
            f"guard_agree=`{gate.get('guard_agreement_count', 0)}/{gate.get('total_count', 0)}` "
            f"accepted_vetoed=`{gate.get('llm_supervised_accept_count', 0)}/{gate.get('llm_supervised_veto_count', 0)}` "
            f"wrong_fetch=`{gate.get('wrong_fetch_dispatch_count', 0)}` "
            f"{artifact_link(str(gate.get('scorecard_path', '') or gate.get('path', '') or ''))}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate LLM fetch planner route evidence.")
    parser.add_argument("--campaign-id", default=f"fetch_planner_llm_shadow_evidence_{current_utc_stamp()}")
    parser.add_argument("--expected-planner-mode", choices=PLANNER_MODES, default=PLANNER_MODE_LLM_SHADOW)
    parser.add_argument("--planner-summary", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    evidence_kind = evidence_kind_for_mode(str(args.expected_planner_mode or PLANNER_MODE_LLM_SHADOW))
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / evidence_kind)
    summary = build_summary(args)
    summary_path = root / "evidence_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["summary_path"] = artifact_display_path(summary_path)
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_PLANNER_LLM_EVIDENCE_SUMMARY={summary_path}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
