#!/usr/bin/env python3
"""Run and classify targeted calibrated fetch architecture revisits."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import calibrated_golf_fetch_gate as fetch_gate
from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import read_json
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json


DEFAULT_BASELINE_SUMMARY = (
    "artifacts/session/live_calibrated_golf_fetch_uat_readiness_rerun_20260527/"
    "calibrated_golf_fetch_gate/gate_summary.json"
)
DEFAULT_CANDIDATE_FAMILY = "nav2_followpath_corridor_push_v1"
NAV2_MPPI_REVISIT_FAMILY = "nav2_mppi_follow_path_reacquire_v1"
DEFAULT_ARTIFACT_KIND = "gather_mission_calibrated_golf_architecture_revisit"
FAST_SCREEN_WORLD_FILE = "yolo_test_world_v6_calibrated_golf_turf_fast.world"
DEFAULT_SCREEN_SCOPE = "runnable_control_family_screen"

LAYOUTS = {
    "zero": fetch_gate.DEFAULT_CENTERLINE_LAYOUT,
    "left05": fetch_gate.OFF_AXIS_LAYOUTS["left05"],
    "right05": fetch_gate.OFF_AXIS_LAYOUTS["right05"],
}


@dataclass(frozen=True)
class CandidateSpec:
    family: str
    layout_id: str
    campaign_id: str
    runs: int
    command: list[str]
    summary_path: Path
    stage: str


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run calibrated fetch architecture revisit gates.")
    parser.add_argument("--dashboard-url", default=fetch_gate.DEFAULT_DASHBOARD_URL)
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--baseline-summary", default=DEFAULT_BASELINE_SUMMARY)
    parser.add_argument("--screen-scope", default=DEFAULT_SCREEN_SCOPE)
    parser.add_argument("--candidate-family", action="append", default=[])
    parser.add_argument("--layout", action="append", choices=tuple(LAYOUTS.keys()), default=[])
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--promote-runs", type=int, default=3)
    parser.add_argument("--promote-on-green", action="store_true")
    parser.add_argument("--short-circuit-on-failure", action="store_true")
    parser.add_argument("--provider", default="local_stub")
    parser.add_argument("--world-file", default=fetch_gate.DEFAULT_WORLD_FILE)
    parser.add_argument("--fast-screen", action="store_true")
    parser.add_argument("--fast-world-file", default=FAST_SCREEN_WORLD_FILE)
    parser.add_argument("--surface-profile", default=fetch_gate.DEFAULT_SURFACE_PROFILE)
    parser.add_argument("--fetch-target-x", type=float, default=fetch_gate.DEFAULT_FETCH_TARGET["x"])
    parser.add_argument("--fetch-target-y", type=float, default=fetch_gate.DEFAULT_FETCH_TARGET["y"])
    parser.add_argument("--fetch-target-z", type=float, default=fetch_gate.DEFAULT_FETCH_TARGET["z"])
    parser.add_argument("--fetch-delivery-radius-m", type=float, default=fetch_gate.DEFAULT_FETCH_TARGET["radius_m"])
    parser.add_argument("--scenario-timeout-s", type=float, default=240.0)
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reuse-existing", action="store_true")
    return parser.parse_args()


def _campaign_summary_path(campaign_id: str) -> Path:
    return (
        REPO_ROOT
        / "artifacts"
        / "session"
        / campaign_id
        / "gather_mission_repeatability"
        / "campaign_run_summary.json"
    )


def _comparison_scope(family: str) -> str:
    if family == "object_centric_gather_policy_v1":
        return "full_fetch_policy_baseline"
    if family == DEFAULT_CANDIDATE_FAMILY:
        return "nav2_corridor_push_contact_candidate"
    if family == NAV2_MPPI_REVISIT_FAMILY:
        return "setup_prestage_candidate_with_fetch_fallback"
    return "legacy_setup_candidate_with_fetch_fallback"


def _build_command(
    args: argparse.Namespace,
    *,
    campaign_id: str,
    family: str,
    layout_id: str,
    layout_path: str,
    runs: int,
) -> list[str]:
    label = f"Calibrated Fetch Architecture Revisit {family} {layout_id}"
    return [
        sys.executable,
        str(REPO_ROOT / "scripts" / "gather_mission_repeatability_runner.py"),
        "--dashboard-url",
        args.dashboard_url,
        "--execution-mode",
        "direct",
        "--scenario-id",
        "corral_single_ball_place",
        "--scenario-label",
        label,
        "--mission-objective",
        "fetch_to_pose",
        "--fetch-target-x",
        f"{float(args.fetch_target_x):.6f}",
        "--fetch-target-y",
        f"{float(args.fetch_target_y):.6f}",
        "--fetch-target-z",
        f"{float(args.fetch_target_z):.6f}",
        "--fetch-delivery-radius-m",
        f"{float(args.fetch_delivery_radius_m):.6f}",
        "--runs",
        str(max(int(runs), 1)),
        "--campaign-id",
        campaign_id,
        "--timeout-s",
        f"{float(args.timeout_s):.3f}",
        "--scenario-timeout-s",
        f"{float(args.scenario_timeout_s):.3f}",
        "--provider",
        args.provider,
        "--world-file",
        args.world_file,
        "--surface-profile",
        args.surface_profile,
        "--promotion-gate-mode",
        "pass_only",
        "--max-retries-per-target",
        "0",
        "--gather-control-family",
        family,
        "--target-model-sdf",
        fetch_gate.DEFAULT_BALL_SDF,
        "--zone-model-sdf",
        fetch_gate.DEFAULT_ZONE_SDF,
        "--artifact-kind",
        DEFAULT_ARTIFACT_KIND,
        "--target-layout-json",
        layout_path,
    ]


def build_candidate_specs(
    args: argparse.Namespace,
    *,
    stage: str,
    families: list[str],
    runs: int,
) -> list[CandidateSpec]:
    base_campaign_id = str(args.campaign_id).strip() or f"live_calibrated_fetch_architecture_revisit_{current_utc_stamp()}"
    specs: list[CandidateSpec] = []
    selected_layout_ids = [layout_id for layout_id in LAYOUTS if not args.layout or layout_id in set(args.layout)]
    for family in families:
        family_slug = family.replace("_v1", "").replace("_", "-")
        for layout_id in selected_layout_ids:
            layout_path = LAYOUTS[layout_id]
            campaign_id = f"{base_campaign_id}_{family_slug}_{layout_id}_{stage}"
            specs.append(
                CandidateSpec(
                    family=family,
                    layout_id=layout_id,
                    campaign_id=campaign_id,
                    runs=max(int(runs), 1),
                    command=_build_command(
                        args,
                        campaign_id=campaign_id,
                        family=family,
                        layout_id=layout_id,
                        layout_path=layout_path,
                        runs=runs,
                    ),
                    summary_path=_campaign_summary_path(campaign_id),
                    stage=stage,
                )
            )
    return specs


def _coerce_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _run_closest_distance(run: dict[str, Any]) -> float | None:
    for container in (
        run.get("shot_outcome"),
        run.get("mission_verdict", {}).get("shot_outcome") if isinstance(run.get("mission_verdict"), dict) else {},
        run.get("summary", {}).get("shot_outcome") if isinstance(run.get("summary"), dict) else {},
    ):
        if isinstance(container, dict):
            value = _coerce_float(container.get("closest_approach_distance_m"))
            if value is not None:
                return value
    return None


def _read_summary(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    return payload if isinstance(payload, dict) else {}


def _summarize_repeatability(summary: dict[str, Any]) -> dict[str, Any]:
    runs = summary.get("runs", [])
    run_list = runs if isinstance(runs, list) else []
    closest_values = [value for value in (_run_closest_distance(run) for run in run_list if isinstance(run, dict)) if value is not None]
    mission_completed = sum(1 for run in run_list if isinstance(run, dict) and bool(run.get("mission_completed_pass", False)))
    fetch_passes = sum(1 for run in run_list if isinstance(run, dict) and bool(run.get("fetch_to_pose_pass", False)))
    pre_stage_passes = sum(1 for run in run_list if isinstance(run, dict) and bool(run.get("pre_stage_handoff_pass", False)))
    return {
        "pass": bool(summary.get("promotion_gate_pass", summary.get("pass", False))),
        "run_count": len(run_list),
        "mission_completed_pass_count": mission_completed,
        "fetch_to_pose_pass_count": int(summary.get("fetch_to_pose_pass_count", fetch_passes) or 0),
        "fetch_to_pose_fail_count": int(summary.get("fetch_to_pose_fail_count", 0) or 0),
        "required_green_runs": int(summary.get("required_green_runs", len(run_list)) or len(run_list)),
        "pre_stage_handoff_pass_count": int(summary.get("pre_stage_handoff_pass_count", pre_stage_passes) or 0),
        "fresh_attempt_approach_pass_count": int(summary.get("fresh_attempt_approach_pass_count", 0) or 0),
        "approach_side_pass_count": int(summary.get("approach_side_pass_count", 0) or 0),
        "approach_failure_reasons": list(summary.get("approach_failure_reasons", []) or []),
        "fetch_to_pose_failure_reasons": list(summary.get("fetch_to_pose_failure_reasons", []) or []),
        "first_contact_push_alignment_max_deg": _coerce_float(summary.get("first_contact_push_alignment_max_deg")),
        "closest_approach_distances_m": [round(float(value), 6) for value in closest_values],
        "worst_closest_approach_distance_m": round(max(closest_values), 6) if closest_values else None,
    }


def _baseline_by_layout(baseline_summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_layout: dict[str, dict[str, Any]] = {}
    for result in baseline_summary.get("results", []) or []:
        if not isinstance(result, dict):
            continue
        gate_id = str(result.get("gate_id", ""))
        if gate_id == "policy_centerline":
            layout_id = "zero"
        elif gate_id.startswith("policy_"):
            layout_id = gate_id.removeprefix("policy_")
        else:
            continue
        by_layout[layout_id] = _summarize_repeatability(result.get("summary", {}) if isinstance(result.get("summary"), dict) else {})
        by_layout[layout_id]["summary_path"] = str(result.get("summary_path", ""))
    return by_layout


def _summary_return_code(summary: dict[str, Any]) -> int:
    runs = summary.get("runs", [])
    codes = []
    if isinstance(runs, list):
        for run in runs:
            if isinstance(run, dict):
                value = run.get("return_code")
                try:
                    if value is not None and value != "":
                        codes.append(int(value))
                except (TypeError, ValueError):
                    pass
    return max(codes, default=0)


def run_candidate(spec: CandidateSpec, *, logs_root: Path, dry_run: bool, reuse_existing: bool = False) -> dict[str, Any]:
    ensure_dir(logs_root)
    family_slug = spec.family.replace("_v1", "").replace("_", "-")
    log_path = logs_root / f"{family_slug}_{spec.layout_id}_{spec.stage}.log"
    payload: dict[str, Any] = {
        "family": spec.family,
        "layout_id": spec.layout_id,
        "campaign_id": spec.campaign_id,
        "stage": spec.stage,
        "runs": spec.runs,
        "summary_path": str(spec.summary_path),
        "log_path": str(log_path),
        "command": spec.command,
        "comparison_scope": _comparison_scope(spec.family),
        "dry_run": bool(dry_run),
    }
    if dry_run:
        payload.update({"return_code": 0, "summary": {}, "metrics": {}, "pass": True})
        return payload
    if reuse_existing and spec.summary_path.exists():
        summary = _read_summary(spec.summary_path)
        metrics = _summarize_repeatability(summary)
        payload.update(
            {
                "return_code": _summary_return_code(summary),
                "summary": summary,
                "metrics": metrics,
                "pass": bool(metrics.get("pass", False)),
                "reused_existing_summary": True,
            }
        )
        return payload
    proc = subprocess.run(
        spec.command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    log_path.write_text((proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else ""), encoding="utf-8")
    summary = _read_summary(spec.summary_path)
    metrics = _summarize_repeatability(summary)
    payload.update(
        {
            "return_code": int(proc.returncode),
            "summary": summary,
            "metrics": metrics,
            "pass": bool(proc.returncode == 0 and metrics.get("pass", False)),
        }
    )
    return payload


def _classify_layout_result(result: dict[str, Any], *, delivery_radius_m: float) -> str:
    metrics = result.get("metrics", {}) if isinstance(result.get("metrics"), dict) else {}
    if not metrics:
        if int(result.get("return_code", 0) or 0) != 0:
            return "runner_failure"
        return "missing_summary"
    if not bool(result.get("pass", False)):
        reasons = metrics.get("fetch_to_pose_failure_reasons") or metrics.get("approach_failure_reasons") or []
        reason_set = {str(reason) for reason in reasons}
        if "nav2_follow_path_path_clearance_guard" in reason_set:
            return "pre_stage_path_clearance_guard"
        if "pre_stage_pose_not_reached" in reason_set:
            return "pre_stage_pose_not_reached"
        if reasons:
            return "failed_with_reasons"
        worst = _coerce_float(metrics.get("worst_closest_approach_distance_m"))
        if worst is not None and worst > float(delivery_radius_m):
            return "delivery_radius_miss"
        if int(metrics.get("pre_stage_handoff_pass_count", 0) or 0) < int(metrics.get("required_green_runs", 1) or 1):
            return "pre_stage_handoff_not_requalified"
        return "fetch_to_pose_not_requalified"
    worst = _coerce_float(metrics.get("worst_closest_approach_distance_m"))
    if worst is not None and worst <= float(delivery_radius_m):
        return "green_within_delivery_radius"
    return "green_missing_closest_distance"


def _family_decision(
    *,
    family: str,
    one_run_results: list[dict[str, Any]],
    promotion_results: list[dict[str, Any]],
    baseline_by_layout: dict[str, dict[str, Any]],
    delivery_radius_m: float,
) -> dict[str, Any]:
    classifications = {
        str(result.get("layout_id")): _classify_layout_result(result, delivery_radius_m=delivery_radius_m)
        for result in one_run_results
    }
    one_run_green = bool(one_run_results) and all(bool(result.get("pass", False)) for result in one_run_results)
    promotion_green = bool(promotion_results) and all(bool(result.get("pass", False)) for result in promotion_results)
    scope = _comparison_scope(family)
    margins: dict[str, float | None] = {}
    for result in promotion_results or one_run_results:
        layout_id = str(result.get("layout_id", ""))
        metrics = result.get("metrics", {}) if isinstance(result.get("metrics"), dict) else {}
        candidate_worst = _coerce_float(metrics.get("worst_closest_approach_distance_m"))
        baseline_worst = _coerce_float(baseline_by_layout.get(layout_id, {}).get("worst_closest_approach_distance_m"))
        margins[layout_id] = (
            round(float(baseline_worst) - float(candidate_worst), 6)
            if baseline_worst is not None and candidate_worst is not None
            else None
        )
    if not one_run_green:
        next_action = "do_not_develop_alternative"
        rationale = "At least one one-run calibrated layout failed; classify artifacts before any policy work."
    elif scope == "nav2_corridor_push_contact_candidate":
        if promotion_results and not promotion_green:
            next_action = "do_not_promote_corridor_push"
            rationale = "Nav2 corridor-push cleared the first screen but failed the three-run promotion gate."
        elif promotion_green:
            next_action = "run_seeded_generalization_gate"
            rationale = "Nav2 corridor-push cleared saved layouts; test seeded random layouts before promotion."
        else:
            next_action = "run_live_nav2_corridor_push_gate"
            rationale = "Nav2 corridor-push is the fresh contact hypothesis; run the live saved-layout gate next."
    elif scope != "full_fetch_policy_baseline":
        next_action = "preserve_as_setup_baseline_evidence"
        rationale = "The candidate requalified setup/fetch-fallback behavior only; it is not a full fetch-contact architecture."
    elif promotion_results and not promotion_green:
        next_action = "do_not_promote_alternative"
        rationale = "One-run evidence was green but three-run promotion failed."
    else:
        best_margin = min((value for value in margins.values() if value is not None), default=None)
        if best_margin is not None and best_margin >= 0.015:
            next_action = "consider_targeted_development"
            rationale = "Candidate cleared the calibrated gate with a meaningful closest-approach margin."
        else:
            next_action = "keep_object_centric_fetch_baseline"
            rationale = "Candidate did not clearly beat the current calibrated baseline."
    return {
        "family": family,
        "comparison_scope": scope,
        "one_run_green": one_run_green,
        "promotion_green": promotion_green,
        "layout_classifications": classifications,
        "closest_approach_margin_vs_baseline_m": margins,
        "recommended_next_action": next_action,
        "rationale": rationale,
    }


def _scorecard(summary: dict[str, Any]) -> str:
    lines = [
        "# Calibrated Fetch Architecture Revisit",
        "",
        f"- Campaign: `{summary['campaign_id']}`",
        f"- Screen scope: `{summary.get('screen_scope', '')}`",
        f"- Baseline: `{summary['baseline_summary_path']}`",
        f"- Fast screen: `{bool(summary.get('fast_screen', False))}`",
        f"- Short circuit: `{bool(summary.get('short_circuit_on_failure', False))}`",
        f"- Layouts: `{', '.join(summary.get('requested_layouts', []))}`",
        f"- World: `{summary.get('world_file', '')}`",
        f"- Delivery radius: `{summary['fetch_pose_world']['radius_m']:.3f}m`",
        f"- Overall recommendation: `{summary['recommended_next_action']}`",
        "",
        "## Candidates",
        "",
    ]
    for family in summary.get("candidate_families", []):
        decision = family.get("decision", {})
        lines.extend(
            [
                f"### `{family.get('family')}`",
                "",
                f"- Scope: `{family.get('comparison_scope')}`",
                f"- One-run green: `{decision.get('one_run_green')}`",
                f"- Promotion green: `{decision.get('promotion_green')}`",
                f"- Recommendation: `{decision.get('recommended_next_action')}`",
                f"- Rationale: {decision.get('rationale')}",
                "",
                "| Layout | Stage | Pass | Classification | Worst closest (m) | Summary |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for result in family.get("one_run_results", []) + family.get("promotion_results", []):
            metrics = result.get("metrics", {}) if isinstance(result.get("metrics"), dict) else {}
            classification = _classify_layout_result(result, delivery_radius_m=float(summary["fetch_pose_world"]["radius_m"]))
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{result.get('layout_id')}`",
                        f"`{result.get('stage')}`",
                        str(bool(result.get("pass", False))).lower(),
                        f"`{classification}`",
                        str(metrics.get("worst_closest_approach_distance_m", "")),
                        f"`{result.get('summary_path')}`",
                    ]
                )
                + " |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    if bool(args.fast_screen) and str(args.world_file) == str(fetch_gate.DEFAULT_WORLD_FILE):
        args.world_file = str(args.fast_world_file)
    campaign_id = str(args.campaign_id).strip() or f"live_calibrated_fetch_architecture_revisit_{current_utc_stamp()}"
    args.campaign_id = campaign_id
    root = ensure_dir(REPO_ROOT / "artifacts" / "session" / campaign_id / "calibrated_fetch_architecture_revisit")
    logs_root = ensure_dir(root / "logs")
    families = args.candidate_family or [DEFAULT_CANDIDATE_FAMILY]
    baseline_summary_path = REPO_ROOT / str(args.baseline_summary)
    baseline_summary = _read_summary(baseline_summary_path)
    baseline_layouts = _baseline_by_layout(baseline_summary)

    candidate_payloads: list[dict[str, Any]] = []
    overall_actions: list[str] = []
    for family in families:
        one_run_specs = build_candidate_specs(args, stage="one_run", families=[family], runs=args.runs)
        one_run_results: list[dict[str, Any]] = []
        for spec in one_run_specs:
            result = run_candidate(
                spec,
                logs_root=logs_root,
                dry_run=bool(args.dry_run),
                reuse_existing=bool(args.reuse_existing),
            )
            one_run_results.append(result)
            if bool(args.short_circuit_on_failure) and not bool(result.get("pass", False)):
                break
        promotion_results: list[dict[str, Any]] = []
        if args.promote_on_green and all(bool(result.get("pass", False)) for result in one_run_results):
            promotion_specs = build_candidate_specs(args, stage="promotion", families=[family], runs=args.promote_runs)
            promotion_results = [
                run_candidate(
                    spec,
                    logs_root=logs_root,
                    dry_run=bool(args.dry_run),
                    reuse_existing=bool(args.reuse_existing),
                )
                for spec in promotion_specs
            ]
        decision = _family_decision(
            family=family,
            one_run_results=one_run_results,
            promotion_results=promotion_results,
            baseline_by_layout=baseline_layouts,
            delivery_radius_m=float(args.fetch_delivery_radius_m),
        )
        overall_actions.append(str(decision.get("recommended_next_action", "")))
        candidate_payloads.append(
            {
                "family": family,
                "comparison_scope": _comparison_scope(family),
                "one_run_results": one_run_results,
                "promotion_results": promotion_results,
                "decision": decision,
            }
        )

    if any(action == "consider_targeted_development" for action in overall_actions):
        recommended_next_action = "consider_targeted_development"
    elif any(action == "preserve_as_setup_baseline_evidence" for action in overall_actions):
        recommended_next_action = "preserve_as_setup_baseline_evidence"
    elif any(action == "do_not_develop_alternative" for action in overall_actions):
        recommended_next_action = "do_not_develop_alternative"
    else:
        recommended_next_action = "keep_object_centric_fetch_baseline"

    summary = {
        "generated_utc": utc_now(),
        "type": "calibrated_fetch_architecture_revisit",
        "campaign_id": campaign_id,
        "dry_run": bool(args.dry_run),
        "screen_scope": str(args.screen_scope or DEFAULT_SCREEN_SCOPE),
        "baseline_summary_path": str(baseline_summary_path.relative_to(REPO_ROOT) if baseline_summary_path.is_relative_to(REPO_ROOT) else baseline_summary_path),
        "baseline_by_layout": baseline_layouts,
        "fast_screen": bool(args.fast_screen),
        "short_circuit_on_failure": bool(args.short_circuit_on_failure),
        "requested_layouts": list(args.layout or LAYOUTS.keys()),
        "world_file": args.world_file,
        "surface_profile": args.surface_profile,
        "fetch_pose_world": {
            "x": float(args.fetch_target_x),
            "y": float(args.fetch_target_y),
            "z": float(args.fetch_target_z),
            "radius_m": float(args.fetch_delivery_radius_m),
        },
        "candidate_families": candidate_payloads,
        "recommended_next_action": recommended_next_action,
    }
    write_json(root / "architecture_revisit_summary.json", summary)
    (root / "scorecard.md").write_text(_scorecard(summary), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
