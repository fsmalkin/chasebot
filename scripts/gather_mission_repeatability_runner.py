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

from gather_mission_campaign_helpers import summarize_gather_run
from gather_mission_helpers import build_scorecard_markdown
from gather_mission_helpers import campaign_pass
from gather_mission_helpers import summarize_runs
from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import append_jsonl
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import http_json
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
    parser.add_argument("--provider", default=os.environ.get("CHASECAR_LLM_PROVIDER", "openai"))
    parser.add_argument("--visit-runtime-json", default=os.environ.get("CHASECAR_VISIT_RUNTIME_PATH", ""))
    parser.add_argument("--gather-runtime-json", default=os.environ.get("CHASECAR_GATHER_RUNTIME_PATH", ""))
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


def promotion_gate_pass_for_runs(runs: list[dict[str, object]], *, mode: str) -> bool:
    if not runs:
        return False
    if mode == "pass_only":
        return all(bool(item.get("pass")) for item in runs)
    return campaign_pass(runs)


def main() -> int:
    args = parse_args()
    campaign_id = args.campaign_id.strip() or current_utc_stamp()
    campaign_root = ensure_dir(REPO_ROOT / "artifacts" / "session" / campaign_id / "gather_mission_repeatability")
    history_path = campaign_root / "history.jsonl"
    logs_root = ensure_dir(campaign_root / "logs")
    wait_for_dashboard(args.dashboard_url, timeout_s=90.0)

    runs: list[dict[str, object]] = []
    for run_index in range(1, max(args.runs, 1) + 1):
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
        output_log_path = logs_root / f"run_{run_index:02d}.log"
        output_log_path.write_text(output, encoding="utf-8")
        run_summary = summarize_gather_run(run_index=run_index, return_code=proc.returncode, output=output)
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
