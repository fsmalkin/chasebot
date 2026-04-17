#!/usr/bin/env python3
"""Repeatability gate for deterministic gather-mission scenarios."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from gather_mission_campaign_helpers import summarize_gather_run
from gather_mission_helpers import build_scorecard_markdown
from gather_mission_helpers import campaign_pass
from gather_mission_helpers import gather_run_pass
from gather_mission_helpers import settled_in_corral_pass
from gather_mission_helpers import summarize_runs
from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import append_jsonl
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import http_json
from llm_supervisor_core import read_json
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic gather missions repeatedly.")
    parser.add_argument("--dashboard-url", default=os.environ.get("CHASECAR_DASHBOARD_URL", "http://127.0.0.1:8860"))
    parser.add_argument("--scenario-id", default="corral_single_ball_place")
    parser.add_argument("--scenario-label", default="Corral Single Ball Place")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--scenario-timeout-s", type=float, default=240.0)
    parser.add_argument("--provider", default=os.environ.get("CHASECAR_LLM_PROVIDER", "openai"))
    parser.add_argument("--visit-runtime-json", default=os.environ.get("CHASECAR_VISIT_RUNTIME_PATH", ""))
    parser.add_argument("--gather-runtime-json", default=os.environ.get("CHASECAR_GATHER_RUNTIME_PATH", ""))
    parser.add_argument("--world-file", default=os.environ.get("WORLD_FILE", ""))
    parser.add_argument("--surface-profile", default=os.environ.get("CHASECAR_SURFACE_PROFILE", ""))
    parser.add_argument("--target-layout-json", default="", help="Test-only target layout override for direct-mode gather runs.")
    parser.add_argument("--execution-mode", choices=("dashboard_scenario", "direct"), default="dashboard_scenario")
    parser.add_argument("--promotion-gate-mode", choices=("strict", "pass_only"), default="pass_only")
    return parser.parse_args()


def wait_for_dashboard(dashboard_url: str, timeout_s: float) -> None:
    deadline = time.monotonic() + max(timeout_s, 5.0)
    while time.monotonic() < deadline:
        try:
            status, _ = http_json(f"{dashboard_url.rstrip('/')}/api/state", timeout_s=5.0)
            if status == 200:
                return
        except Exception:
            pass
        time.sleep(1.0)
    raise RuntimeError("Dashboard API did not become ready before gather repeatability run.")


def _environment_request_payload(args: argparse.Namespace) -> dict[str, object]:
    payload: dict[str, object] = {"scenario_id": args.scenario_id}
    if str(args.world_file or "").strip():
        payload["world_file"] = str(args.world_file).strip()
    if str(args.surface_profile or "").strip():
        payload["surface_profile"] = str(args.surface_profile).strip()
    return payload


def wait_for_environment_ready(
    dashboard_url: str,
    *,
    timeout_s: float,
    previous_session_id: str = "",
) -> dict[str, object]:
    deadline = time.monotonic() + max(timeout_s, 30.0)
    last_state: dict[str, object] = {}
    while time.monotonic() < deadline:
        status, current_state = http_json(f"{dashboard_url.rstrip('/')}/api/state", timeout_s=10.0)
        if status == 200:
            last_state = current_state
            current_environment_state = str(current_state.get("environment_state", "") or "").strip().lower()
            current_session_id = str(current_state.get("session_id", "") or "")
            if current_environment_state == "environment_ready" and (not previous_session_id or current_session_id != previous_session_id):
                return current_state
            if current_environment_state == "error":
                raise RuntimeError(f"Dashboard environment failed to start: {json.dumps(current_state, indent=2, sort_keys=True)}")
        time.sleep(1.0)
    raise RuntimeError(
        "Dashboard environment did not become ready before gather repeatability run. "
        f"Last state: {json.dumps(last_state, indent=2, sort_keys=True)}"
    )


def ensure_environment_ready(dashboard_url: str, timeout_s: float, *, startup_payload: dict[str, object] | None = None) -> None:
    base_url = dashboard_url.rstrip("/")
    status, state = http_json(f"{base_url}/api/state", timeout_s=10.0)
    if status != 200:
        raise RuntimeError("Unable to fetch dashboard state before gather repeatability run.")
    environment_state = str(state.get("environment_state", "") or "").strip().lower()
    if environment_state == "environment_ready":
        return

    status, response = http_json(
        f"{base_url}/api/env/start",
        method="POST",
        payload=dict(startup_payload or {}),
        timeout_s=15.0,
    )
    accepted = status in {200, 202} and bool(response.get("accepted", False))
    if not accepted and environment_state != "starting":
        raise RuntimeError(f"Dashboard environment start rejected: {response}")
    wait_for_environment_ready(dashboard_url, timeout_s=timeout_s)


def wait_for_dashboard_slot(dashboard_url: str, timeout_s: float) -> None:
    deadline = time.monotonic() + max(timeout_s, 30.0)
    last_state: dict[str, object] = {}
    while time.monotonic() < deadline:
        ensure_environment_ready(dashboard_url, timeout_s=min(max(timeout_s, 5.0), 30.0))
        status, current_state = http_json(f"{dashboard_url.rstrip('/')}/api/state", timeout_s=10.0)
        if status == 200:
            last_state = current_state
            environment_state = str(current_state.get("environment_state", "") or "").strip().lower()
            scenario_state = str(current_state.get("scenario_state", "") or "").strip().lower()
            if environment_state == "environment_ready" and scenario_state != "running":
                return
        time.sleep(1.0)
    raise RuntimeError(f"Dashboard scenario slot did not become ready before gather repeatability run. Last state: {json.dumps(last_state, indent=2, sort_keys=True)}")


def promotion_gate_pass_for_runs(runs: list[dict[str, object]], *, mode: str) -> bool:
    if not runs:
        return False
    settled_without_revisit = all(gather_run_pass(item) for item in runs)
    if mode == "pass_only":
        return settled_without_revisit
    return campaign_pass(runs) and settled_without_revisit


def _float_list_from_runs(runs: list[dict[str, object]], key: str) -> list[float]:
    values: list[float] = []
    for item in runs:
        raw_value = item.get(key)
        if raw_value in {None, ""}:
            continue
        try:
            values.append(float(raw_value))
        except (TypeError, ValueError):
            continue
    return values


def _approach_side_rollup(runs: list[dict[str, object]]) -> dict[str, object]:
    approach_side_pass_flags = [bool(item.get("approach_side_pass", False)) for item in runs]
    staging_pose_reached_flags = [bool(item.get("staging_pose_reached", False)) for item in runs]
    entered_goal_side_flags = [bool(item.get("entered_goal_side_before_capture", False)) for item in runs]
    approach_reasons = sorted(
        {
            str(item.get("approach_side_reason", "") or "")
            for item in runs
            if str(item.get("approach_side_reason", "") or "").strip()
        }
    )
    approach_failure_reasons = sorted(
        {
            str(item.get("approach_failure_reason", "") or "")
            for item in runs
            if str(item.get("approach_failure_reason", "") or "").strip()
        }
    )
    first_contact_alignments = _float_list_from_runs(runs, "first_contact_push_alignment_deg")
    push_direction_yaws = _float_list_from_runs(runs, "push_direction_yaw_deg")
    stage_times = _float_list_from_runs(runs, "stage_time_s")
    return {
        "approach_side_pass_count": sum(1 for flag in approach_side_pass_flags if flag),
        "approach_side_fail_count": sum(1 for flag in approach_side_pass_flags if not flag),
        "staging_pose_reached_count": sum(1 for flag in staging_pose_reached_flags if flag),
        "entered_goal_side_before_capture_count": sum(1 for flag in entered_goal_side_flags if flag),
        "first_contact_push_alignment_avg_deg": round(sum(first_contact_alignments) / len(first_contact_alignments), 6) if first_contact_alignments else 0.0,
        "first_contact_push_alignment_min_deg": round(min(first_contact_alignments), 6) if first_contact_alignments else 0.0,
        "first_contact_push_alignment_max_deg": round(max(first_contact_alignments), 6) if first_contact_alignments else 0.0,
        "push_direction_yaw_avg_deg": round(sum(push_direction_yaws) / len(push_direction_yaws), 6) if push_direction_yaws else 0.0,
        "push_direction_yaw_min_deg": round(min(push_direction_yaws), 6) if push_direction_yaws else 0.0,
        "push_direction_yaw_max_deg": round(max(push_direction_yaws), 6) if push_direction_yaws else 0.0,
        "stage_time_avg_s": round(sum(stage_times) / len(stage_times), 6) if stage_times else 0.0,
        "stage_time_min_s": round(min(stage_times), 6) if stage_times else 0.0,
        "stage_time_max_s": round(max(stage_times), 6) if stage_times else 0.0,
        "approach_side_reasons": approach_reasons,
        "approach_failure_reasons": approach_failure_reasons,
    }


def _enrich_run_with_approach_side_fields(run_summary: dict[str, object]) -> dict[str, object]:
    mission_verdict_path = str(run_summary.get("mission_verdict_path", "") or "")
    if not mission_verdict_path:
        return run_summary
    verdict_path = Path(mission_verdict_path)
    if not verdict_path.exists():
        return run_summary
    verdict = read_json(verdict_path)
    summary_path = str(run_summary.get("summary_path", "") or "")
    summary = read_json(Path(summary_path)) if summary_path and Path(summary_path).exists() else {}
    merged = verdict if isinstance(verdict, dict) and verdict else summary if isinstance(summary, dict) else {}
    approach_side_verdict = merged.get("approach_side_verdict", {}) if isinstance(merged.get("approach_side_verdict"), dict) else {}
    run_summary.update(
        {
            "approach_side_verdict": approach_side_verdict,
            "approach_side_pass": bool(approach_side_verdict.get("pass", False)),
            "approach_side_reason": str(approach_side_verdict.get("reason", "") or ""),
            "staging_pose_reached": bool(merged.get("staging_pose_reached", run_summary.get("staging_pose_reached", False))),
            "entered_goal_side_before_capture": bool(
                merged.get("entered_goal_side_before_capture", run_summary.get("entered_goal_side_before_capture", False))
            ),
            "first_contact_push_alignment_deg": float(
                merged.get("first_contact_push_alignment_deg", run_summary.get("first_contact_push_alignment_deg", 0.0)) or 0.0
            ),
            "push_direction_yaw_deg": float(merged.get("push_direction_yaw_deg", run_summary.get("push_direction_yaw_deg", 0.0)) or 0.0),
            "stage_time_s": float(merged.get("stage_time_s", run_summary.get("stage_time_s", 0.0)) or 0.0),
            "approach_failure_reason": str(merged.get("approach_failure_reason", run_summary.get("approach_failure_reason", "")) or ""),
        }
    )
    return run_summary


def summarize_gather_artifacts(*, run_index: int, mission_verdict_path: str) -> dict[str, object]:
    verdict_path = Path(mission_verdict_path)
    mission_root = verdict_path.parent if verdict_path.exists() else None
    summary_path = mission_root / "summary.json" if mission_root else None
    target_results_path = mission_root / "target_results.json" if mission_root else None
    scorecard_path = mission_root / "scorecard.md" if mission_root else None

    verdict = read_json(verdict_path) if verdict_path.exists() else {}
    summary = read_json(summary_path) if summary_path and summary_path.exists() else {}
    target_results_payload = read_json(target_results_path) if target_results_path and target_results_path.exists() else {}
    target_results = list(target_results_payload.get("targets", [])) if isinstance(target_results_payload.get("targets"), list) else []
    merged = verdict if verdict else summary
    approach_side_verdict = merged.get("approach_side_verdict", {}) if isinstance(merged.get("approach_side_verdict"), dict) else {}

    return {
        "run_index": run_index,
        "return_code": 0 if bool(verdict.get("pass")) else 2,
        "pass": bool(verdict.get("pass")) if verdict else bool(summary.get("pass")),
        "mission_completed_pass": bool(verdict.get("mission_completed_pass", summary.get("mission_completed_pass", verdict.get("pass", summary.get("pass", False))))),
        "session_id": str(verdict.get("session_id", "") or summary.get("session_id", "")),
        "scenario_id": str(verdict.get("scenario_id", "") or summary.get("scenario_id", "")),
        "mission_root": str(mission_root) if mission_root else "",
        "summary_path": str(summary_path) if summary_path and summary_path.exists() else "",
        "mission_verdict_path": str(verdict_path) if verdict_path.exists() else "",
        "target_results_path": str(target_results_path) if target_results_path and target_results_path.exists() else "",
        "scorecard_path": str(scorecard_path) if scorecard_path and scorecard_path.exists() else "",
        "placed_count": int(verdict.get("placed_count", summary.get("placed_count", 0)) or 0),
        "capture_loss_count": int(verdict.get("capture_loss_count", summary.get("capture_loss_count", 0)) or 0),
        "handoff_kind": str(verdict.get("handoff_kind", summary.get("handoff_kind", "")) or ""),
        "settle_exit_reason": str(verdict.get("settle_exit_reason", summary.get("settle_exit_reason", "")) or ""),
        "zone_edge_correction_count": int(verdict.get("zone_edge_correction_count", summary.get("zone_edge_correction_count", 0)) or 0),
        "place_controller_reentry_count": int(verdict.get("place_controller_reentry_count", summary.get("place_controller_reentry_count", 0)) or 0),
        "post_visit_revisit_count": int(verdict.get("post_visit_revisit_count", summary.get("post_visit_revisit_count", 0)) or 0),
        "settle_no_chase_activated": bool(verdict.get("settle_no_chase_activated", summary.get("settle_no_chase_activated", False))),
        "settle_no_chase_exit_reason": str(verdict.get("settle_no_chase_exit_reason", summary.get("settle_no_chase_exit_reason", "none")) or "none"),
        "release_gate_blocked_reason": str(verdict.get("release_gate_blocked_reason", summary.get("release_gate_blocked_reason", "none")) or "none"),
        "stopped_with_ball_captured": bool(verdict.get("stopped_with_ball_captured", summary.get("stopped_with_ball_captured", False))),
        "release_started_with_capture": bool(verdict.get("release_started_with_capture", summary.get("release_started_with_capture", False))),
        "stop_capture_state": verdict.get("stop_capture_state", summary.get("stop_capture_state", {})) if isinstance(verdict.get("stop_capture_state", summary.get("stop_capture_state", {})), dict) else {},
        "release_capture_state": verdict.get("release_capture_state", summary.get("release_capture_state", {})) if isinstance(verdict.get("release_capture_state", summary.get("release_capture_state", {})), dict) else {},
        "clean_retention_pass": bool(verdict.get("clean_retention_pass", summary.get("clean_retention_pass", False))),
        "final_inside_retrieval_corral": bool(verdict.get("final_inside_retrieval_corral", summary.get("final_inside_retrieval_corral", False))),
        "final_center_inside_zone": bool(verdict.get("final_center_inside_zone", summary.get("final_center_inside_zone", False))),
        "ball_stopped_in_corral": bool(verdict.get("ball_stopped_in_corral", summary.get("ball_stopped_in_corral", False))),
        "rolled_away_after_release": bool(verdict.get("rolled_away_after_release", summary.get("rolled_away_after_release", False))),
        "settled_in_corral_pass": bool(verdict.get("settled_in_corral_pass", summary.get("settled_in_corral_pass", False))),
        "final_corral_audit": verdict.get("final_corral_audit", summary.get("final_corral_audit", {}))
        if isinstance(verdict.get("final_corral_audit", summary.get("final_corral_audit", {})), dict)
        else {},
        "final_all_targets_inside_retrieval_corral": bool(
            verdict.get(
                "final_all_targets_inside_retrieval_corral",
                summary.get("final_all_targets_inside_retrieval_corral", False),
            )
        ),
        "final_all_targets_stopped": bool(
            verdict.get(
                "final_all_targets_stopped",
                summary.get("final_all_targets_stopped", False),
            )
        ),
        "final_three_ball_corral_pass": bool(
            verdict.get(
                "final_three_ball_corral_pass",
                summary.get("final_three_ball_corral_pass", False),
            )
        ),
        "retrieved_count": int(verdict.get("retrieved_count", summary.get("retrieved_count", 0)) or 0),
        "surface_profile": str(verdict.get("surface_profile", summary.get("surface_profile", "")) or ""),
        "final_settle_distance_m": float(verdict.get("final_settle_distance_m", summary.get("final_settle_distance_m", 0.0)) or 0.0),
        "max_overshoot_distance_m": float(verdict.get("max_overshoot_distance_m", summary.get("max_overshoot_distance_m", 0.0)) or 0.0),
        "settle_time_s": float(verdict.get("settle_time_s", summary.get("settle_time_s", 0.0)) or 0.0),
        "release_recontact_count": int(verdict.get("release_recontact_count", summary.get("release_recontact_count", 0)) or 0),
        "mission_time_s": float(verdict.get("mission_time_s", summary.get("mission_time_s", 0.0)) or 0.0),
        "route_order": list(verdict.get("route_order", summary.get("route_order", [])) or []),
        "approach_side_verdict": approach_side_verdict,
        "approach_side_pass": bool(approach_side_verdict.get("pass", False)),
        "approach_side_reason": str(approach_side_verdict.get("reason", "") or ""),
        "staging_pose_reached": bool(merged.get("staging_pose_reached", False)),
        "entered_goal_side_before_capture": bool(merged.get("entered_goal_side_before_capture", False)),
        "first_contact_push_alignment_deg": float(merged.get("first_contact_push_alignment_deg", 0.0) or 0.0),
        "push_direction_yaw_deg": float(merged.get("push_direction_yaw_deg", 0.0) or 0.0),
        "stage_time_s": float(merged.get("stage_time_s", 0.0) or 0.0),
        "approach_failure_reason": str(merged.get("approach_failure_reason", "") or ""),
        "target_results": target_results,
        "mission_verdict": verdict,
        "summary": summary,
    }


def _latest_mission_verdict_path(state: dict[str, object]) -> str:
    artifacts = state.get("latest_artifacts", {}) if isinstance(state.get("latest_artifacts"), dict) else {}
    return str(artifacts.get("mission_verdict", "") or "")


def _fresh_dashboard_result_available(
    state: dict[str, object],
    *,
    scenario_id: str,
    previous_session_id: str,
    previous_mission_verdict_path: str,
) -> bool:
    mission_verdict = state.get("mission_verdict", {}) if isinstance(state.get("mission_verdict"), dict) else {}
    if str(mission_verdict.get("scenario_id", "") or "") != scenario_id:
        return False
    current_mission_verdict_path = _latest_mission_verdict_path(state)
    if not current_mission_verdict_path:
        return False
    current_session_id = str(state.get("session_id", "") or "")
    if previous_session_id and current_session_id == previous_session_id and current_mission_verdict_path == previous_mission_verdict_path:
        return False
    if previous_mission_verdict_path and current_mission_verdict_path == previous_mission_verdict_path:
        return False
    return True


def run_dashboard_scenario_once(args: argparse.Namespace, *, run_index: int) -> tuple[dict[str, object], str]:
    status, before_state = http_json(f"{args.dashboard_url.rstrip('/')}/api/state", timeout_s=10.0)
    if status != 200:
        raise RuntimeError(f"Unable to fetch dashboard state before run {run_index}.")
    previous_session_id = str(before_state.get("session_id", "") or "")
    previous_mission_verdict_path = _latest_mission_verdict_path(before_state)
    payload = {"scenario_id": args.scenario_id}
    if args.world_file.strip():
        payload["world_file"] = args.world_file.strip()
    if args.surface_profile.strip():
        payload["surface_profile"] = args.surface_profile.strip()
    status, response = http_json(
        f"{args.dashboard_url.rstrip('/')}/api/scenario/run",
        method="POST",
        payload=payload,
        timeout_s=15.0,
    )
    if status not in {200, 202} or not bool(response.get("accepted", False)):
        raise RuntimeError(f"Dashboard scenario run rejected: {response}")

    deadline = time.monotonic() + max(args.scenario_timeout_s, 30.0)
    last_state: dict[str, object] = {}
    while time.monotonic() < deadline:
        status, current_state = http_json(f"{args.dashboard_url.rstrip('/')}/api/state", timeout_s=10.0)
        if status != 200:
            time.sleep(1.0)
            continue
        last_state = current_state
        current_scenario_state = str(current_state.get("scenario_state", "") or "").strip().lower()
        if current_scenario_state == "ready" and _fresh_dashboard_result_available(
            current_state,
            scenario_id=args.scenario_id,
            previous_session_id=previous_session_id,
            previous_mission_verdict_path=previous_mission_verdict_path,
        ):
            mission_verdict_path = _latest_mission_verdict_path(current_state)
            if mission_verdict_path:
                summary = summarize_gather_artifacts(run_index=run_index, mission_verdict_path=mission_verdict_path)
                return summary, json.dumps(current_state, indent=2, sort_keys=True)
        if current_scenario_state == "error" and _fresh_dashboard_result_available(
            current_state,
            scenario_id=args.scenario_id,
            previous_session_id=previous_session_id,
            previous_mission_verdict_path=previous_mission_verdict_path,
        ):
            mission_verdict_path = _latest_mission_verdict_path(current_state)
            if mission_verdict_path:
                summary = summarize_gather_artifacts(run_index=run_index, mission_verdict_path=mission_verdict_path)
                return summary, json.dumps(current_state, indent=2, sort_keys=True)
            raise RuntimeError(f"Dashboard scenario failed: {json.dumps(current_state, indent=2, sort_keys=True)}")
        time.sleep(1.0)
    raise RuntimeError(f"Dashboard scenario did not finish before timeout. Last state: {json.dumps(last_state, indent=2, sort_keys=True)}")


def prepare_direct_environment(args: argparse.Namespace) -> dict[str, object]:
    base_url = args.dashboard_url.rstrip("/")
    payload = _environment_request_payload(args)
    status, state = http_json(f"{base_url}/api/state", timeout_s=10.0)
    if status != 200:
        raise RuntimeError("Unable to fetch dashboard state before direct gather run.")
    environment_state = str(state.get("environment_state", "") or "").strip().lower()
    previous_session_id = str(state.get("session_id", "") or "")
    if environment_state == "environment_ready":
        status, response = http_json(
            f"{base_url}/api/sim/reset",
            method="POST",
            payload=payload,
            timeout_s=15.0,
        )
        if status not in {200, 202} or not bool(response.get("accepted", False)):
            raise RuntimeError(f"Dashboard sim reset rejected before direct gather run: {response}")
        return wait_for_environment_ready(
            args.dashboard_url,
            timeout_s=max(args.timeout_s, 120.0),
            previous_session_id=previous_session_id,
        )
    if environment_state == "stopped":
        ensure_environment_ready(
            args.dashboard_url,
            timeout_s=max(args.timeout_s, 120.0),
            startup_payload=payload,
        )
        status, ready_state = http_json(f"{base_url}/api/state", timeout_s=10.0)
        if status != 200:
            raise RuntimeError("Unable to fetch dashboard state after direct gather environment start.")
        return ready_state
    status, stop_response = http_json(
        f"{base_url}/api/env/stop",
        method="POST",
        payload={},
        timeout_s=15.0,
    )
    if status not in {200, 202}:
        raise RuntimeError(f"Dashboard environment stop rejected before direct gather run: {stop_response}")
    deadline = time.monotonic() + 180.0
    while time.monotonic() < deadline:
        status, current_state = http_json(f"{base_url}/api/state", timeout_s=10.0)
        if status == 200 and str(current_state.get("environment_state", "") or "").strip().lower() == "stopped":
            ensure_environment_ready(
                args.dashboard_url,
                timeout_s=max(args.timeout_s, 120.0),
                startup_payload=payload,
            )
            status, ready_state = http_json(f"{base_url}/api/state", timeout_s=10.0)
            if status != 200:
                raise RuntimeError("Unable to fetch dashboard state after restarting direct gather environment.")
            return ready_state
        time.sleep(1.0)
    raise RuntimeError("Dashboard environment did not stop before restarting direct gather run.")


def main() -> int:
    args = parse_args()
    campaign_id = args.campaign_id.strip() or current_utc_stamp()
    campaign_root = ensure_dir(REPO_ROOT / "artifacts" / "session" / campaign_id / "gather_mission_repeatability")
    history_path = campaign_root / "history.jsonl"
    logs_root = ensure_dir(campaign_root / "logs")
    wait_for_dashboard(args.dashboard_url, timeout_s=90.0)

    runs: list[dict[str, object]] = []
    for run_index in range(1, max(args.runs, 1) + 1):
        output_log_path = logs_root / f"run_{run_index:02d}.log"
        if args.execution_mode == "dashboard_scenario":
            wait_for_dashboard_slot(args.dashboard_url, timeout_s=120.0)
            try:
                run_summary, output = run_dashboard_scenario_once(args, run_index=run_index)
            except Exception as exc:
                output = str(exc)
                run_summary = {
                    "run_index": run_index,
                    "return_code": 2,
                    "pass": False,
                    "session_id": "",
                    "scenario_id": args.scenario_id,
                    "mission_root": "",
                    "summary_path": "",
                    "mission_verdict_path": "",
                    "target_results_path": "",
                    "scorecard_path": "",
                    "placed_count": 0,
                    "capture_loss_count": 0,
                    "surface_profile": args.surface_profile.strip(),
                    "final_settle_distance_m": 0.0,
                    "max_overshoot_distance_m": 0.0,
                    "settle_time_s": 0.0,
                    "release_recontact_count": 0,
                    "mission_time_s": 0.0,
                    "route_order": [],
                    "target_results": [],
                    "mission_verdict": {},
                    "summary": {},
                    "failure_reason": str(exc),
                }
        else:
            prepare_direct_environment(args)
            command = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "gather_mission_runner.py"),
                "--dashboard-url",
                args.dashboard_url,
                "--provider",
                args.provider,
                "--scenario-id",
                args.scenario_id,
                "--scenario-label",
                args.scenario_label,
            ]
            if args.world_file.strip():
                command.extend(["--world-file", args.world_file.strip()])
            if args.surface_profile.strip():
                command.extend(["--surface-profile", args.surface_profile.strip()])
            if args.visit_runtime_json.strip():
                command.extend(["--visit-runtime-json", args.visit_runtime_json.strip()])
            if args.gather_runtime_json.strip():
                command.extend(["--gather-runtime-json", args.gather_runtime_json.strip()])
            if args.target_layout_json.strip():
                command.extend(["--target-layout-json", args.target_layout_json.strip()])
            proc = subprocess.run(
                command,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
            run_summary = summarize_gather_run(run_index=run_index, return_code=proc.returncode, output=output)
            run_summary = _enrich_run_with_approach_side_fields(run_summary)
        output_log_path.write_text(output, encoding="utf-8")
        run_summary["generated_utc"] = utc_now()
        run_summary["output_log_path"] = str(output_log_path)
        append_jsonl(history_path, run_summary)
        runs.append(run_summary)

    rollup = summarize_runs(runs)
    approach_side_rollup = _approach_side_rollup(runs)
    promotion_gate_pass = promotion_gate_pass_for_runs(runs, mode=args.promotion_gate_mode)
    summary = {
        "generated_utc": utc_now(),
        "type": "gather_mission_repeatability",
        "campaign_id": campaign_id,
        "scenario_id": args.scenario_id,
        "scenario_label": args.scenario_label,
        "execution_mode": args.execution_mode,
        "requested_world_file": args.world_file.strip(),
        "requested_surface_profile": args.surface_profile.strip(),
        "requested_target_layout_json": args.target_layout_json.strip(),
        "required_green_runs": max(args.runs, 1),
        "promotion_gate_mode": args.promotion_gate_mode,
        "promotion_gate_pass": promotion_gate_pass,
        "history_path": str(history_path),
        "runs": runs,
        **approach_side_rollup,
        **rollup,
    }
    write_json(campaign_root / "campaign_run_summary.json", summary)
    scorecard = build_scorecard_markdown(
        scenario_label=args.scenario_label,
        summary=summary,
        runs=runs,
    )
    approach_side_lines = [
        "",
        "## Approach Side Rollup",
        "",
        f"- Approach side pass/fail: `{summary.get('approach_side_pass_count', 0)}/{summary.get('approach_side_fail_count', 0)}`",
        f"- Staging pose reached: `{summary.get('staging_pose_reached_count', 0)}/{max(len(runs), 1)}`",
        f"- Entered goal side before capture: `{summary.get('entered_goal_side_before_capture_count', 0)}/{max(len(runs), 1)}`",
        f"- First contact push alignment avg/min/max: `{summary.get('first_contact_push_alignment_avg_deg', 0.0):.3f}deg / {summary.get('first_contact_push_alignment_min_deg', 0.0):.3f}deg / {summary.get('first_contact_push_alignment_max_deg', 0.0):.3f}deg`",
        f"- Push direction yaw avg/min/max: `{summary.get('push_direction_yaw_avg_deg', 0.0):.3f}deg / {summary.get('push_direction_yaw_min_deg', 0.0):.3f}deg / {summary.get('push_direction_yaw_max_deg', 0.0):.3f}deg`",
        f"- Stage time avg/min/max: `{summary.get('stage_time_avg_s', 0.0):.3f}s / {summary.get('stage_time_min_s', 0.0):.3f}s / {summary.get('stage_time_max_s', 0.0):.3f}s`",
        f"- Approach-side reasons: `{', '.join(summary.get('approach_side_reasons', [])) if summary.get('approach_side_reasons') else 'none'}`",
        f"- Approach failure reasons: `{', '.join(summary.get('approach_failure_reasons', [])) if summary.get('approach_failure_reasons') else 'none'}`",
    ]
    scorecard = scorecard.rstrip() + "\n".join(approach_side_lines) + "\n"
    (campaign_root / "scorecard.md").write_text(scorecard, encoding="utf-8")
    print(f"GATHER_MISSION_REPEATABILITY_SUMMARY={campaign_root / 'campaign_run_summary.json'}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["promotion_gate_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
