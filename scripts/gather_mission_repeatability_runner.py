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


def ensure_environment_ready(dashboard_url: str, timeout_s: float) -> None:
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
        payload={},
        timeout_s=15.0,
    )
    accepted = status in {200, 202} and bool(response.get("accepted", False))
    if not accepted and environment_state != "starting":
        raise RuntimeError(f"Dashboard environment start rejected: {response}")

    deadline = time.monotonic() + max(timeout_s, 30.0)
    last_state: dict[str, object] = state
    while time.monotonic() < deadline:
        status, current_state = http_json(f"{base_url}/api/state", timeout_s=10.0)
        if status == 200:
            last_state = current_state
            current_environment_state = str(current_state.get("environment_state", "") or "").strip().lower()
            if current_environment_state == "environment_ready":
                return
            if current_environment_state == "error":
                raise RuntimeError(f"Dashboard environment failed to start: {json.dumps(current_state, indent=2, sort_keys=True)}")
        time.sleep(1.0)
    raise RuntimeError(f"Dashboard environment did not become ready before gather repeatability run. Last state: {json.dumps(last_state, indent=2, sort_keys=True)}")


def promotion_gate_pass_for_runs(runs: list[dict[str, object]], *, mode: str) -> bool:
    if not runs:
        return False
    if mode == "pass_only":
        return all(settled_in_corral_pass(item) for item in runs)
    return campaign_pass(runs)


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
        "stopped_with_ball_captured": bool(verdict.get("stopped_with_ball_captured", summary.get("stopped_with_ball_captured", False))),
        "release_started_with_capture": bool(verdict.get("release_started_with_capture", summary.get("release_started_with_capture", False))),
        "stop_capture_state": verdict.get("stop_capture_state", summary.get("stop_capture_state", {})) if isinstance(verdict.get("stop_capture_state", summary.get("stop_capture_state", {})), dict) else {},
        "release_capture_state": verdict.get("release_capture_state", summary.get("release_capture_state", {})) if isinstance(verdict.get("release_capture_state", summary.get("release_capture_state", {})), dict) else {},
        "clean_retention_pass": bool(verdict.get("clean_retention_pass", summary.get("clean_retention_pass", False))),
        "final_center_inside_zone": bool(verdict.get("final_center_inside_zone", summary.get("final_center_inside_zone", False))),
        "ball_stopped_in_corral": bool(verdict.get("ball_stopped_in_corral", summary.get("ball_stopped_in_corral", False))),
        "rolled_away_after_release": bool(verdict.get("rolled_away_after_release", summary.get("rolled_away_after_release", False))),
        "settled_in_corral_pass": bool(verdict.get("settled_in_corral_pass", summary.get("settled_in_corral_pass", False))),
        "surface_profile": str(verdict.get("surface_profile", summary.get("surface_profile", "")) or ""),
        "final_settle_distance_m": float(verdict.get("final_settle_distance_m", summary.get("final_settle_distance_m", 0.0)) or 0.0),
        "max_overshoot_distance_m": float(verdict.get("max_overshoot_distance_m", summary.get("max_overshoot_distance_m", 0.0)) or 0.0),
        "settle_time_s": float(verdict.get("settle_time_s", summary.get("settle_time_s", 0.0)) or 0.0),
        "release_recontact_count": int(verdict.get("release_recontact_count", summary.get("release_recontact_count", 0)) or 0),
        "mission_time_s": float(verdict.get("mission_time_s", summary.get("mission_time_s", 0.0)) or 0.0),
        "route_order": list(verdict.get("route_order", summary.get("route_order", [])) or []),
        "target_results": target_results,
        "mission_verdict": verdict,
        "summary": summary,
    }


def run_dashboard_scenario_once(args: argparse.Namespace, *, run_index: int) -> tuple[dict[str, object], str]:
    status, before_state = http_json(f"{args.dashboard_url.rstrip('/')}/api/state", timeout_s=10.0)
    if status != 200:
        raise RuntimeError(f"Unable to fetch dashboard state before run {run_index}.")
    previous_session_id = str(before_state.get("session_id", "") or "")
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
        mission_verdict = current_state.get("mission_verdict", {}) if isinstance(current_state.get("mission_verdict"), dict) else {}
        if current_state.get("scenario_state") == "ready" and mission_verdict.get("scenario_id") == args.scenario_id:
            if previous_session_id and str(current_state.get("session_id", "") or "") == previous_session_id:
                time.sleep(1.0)
                continue
            artifacts = current_state.get("latest_artifacts", {}) if isinstance(current_state.get("latest_artifacts"), dict) else {}
            mission_verdict_path = str(artifacts.get("mission_verdict", "") or "")
            if mission_verdict_path:
                summary = summarize_gather_artifacts(run_index=run_index, mission_verdict_path=mission_verdict_path)
                return summary, json.dumps(current_state, indent=2, sort_keys=True)
        if current_state.get("scenario_state") == "error" and mission_verdict.get("scenario_id") == args.scenario_id:
            artifacts = current_state.get("latest_artifacts", {}) if isinstance(current_state.get("latest_artifacts"), dict) else {}
            mission_verdict_path = str(artifacts.get("mission_verdict", "") or "")
            if mission_verdict_path:
                summary = summarize_gather_artifacts(run_index=run_index, mission_verdict_path=mission_verdict_path)
                return summary, json.dumps(current_state, indent=2, sort_keys=True)
            raise RuntimeError(f"Dashboard scenario failed: {json.dumps(current_state, indent=2, sort_keys=True)}")
        time.sleep(1.0)
    raise RuntimeError(f"Dashboard scenario did not finish before timeout. Last state: {json.dumps(last_state, indent=2, sort_keys=True)}")


def main() -> int:
    args = parse_args()
    campaign_id = args.campaign_id.strip() or current_utc_stamp()
    campaign_root = ensure_dir(REPO_ROOT / "artifacts" / "session" / campaign_id / "gather_mission_repeatability")
    history_path = campaign_root / "history.jsonl"
    logs_root = ensure_dir(campaign_root / "logs")
    wait_for_dashboard(args.dashboard_url, timeout_s=90.0)
    ensure_environment_ready(args.dashboard_url, timeout_s=120.0)

    runs: list[dict[str, object]] = []
    for run_index in range(1, max(args.runs, 1) + 1):
        output_log_path = logs_root / f"run_{run_index:02d}.log"
        if args.execution_mode == "dashboard_scenario":
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
            proc = subprocess.run(
                command,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
            run_summary = summarize_gather_run(run_index=run_index, return_code=proc.returncode, output=output)
        output_log_path.write_text(output, encoding="utf-8")
        run_summary["generated_utc"] = utc_now()
        run_summary["output_log_path"] = str(output_log_path)
        append_jsonl(history_path, run_summary)
        runs.append(run_summary)

    rollup = summarize_runs(runs)
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
        "required_green_runs": max(args.runs, 1),
        "promotion_gate_mode": args.promotion_gate_mode,
        "promotion_gate_pass": promotion_gate_pass,
        "history_path": str(history_path),
        "runs": runs,
        **rollup,
    }
    write_json(campaign_root / "campaign_run_summary.json", summary)
    scorecard = build_scorecard_markdown(
        scenario_label=args.scenario_label,
        summary=summary,
        runs=runs,
    )
    (campaign_root / "scorecard.md").write_text(scorecard, encoding="utf-8")
    print(f"GATHER_MISSION_REPEATABILITY_SUMMARY={campaign_root / 'campaign_run_summary.json'}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["promotion_gate_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
