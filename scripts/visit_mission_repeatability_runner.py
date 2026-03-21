#!/usr/bin/env python3
"""Repeatability gate for deterministic visit-mission scenarios."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import append_jsonl
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import http_json
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json
from visit_mission_campaign_helpers import campaign_pass
from visit_mission_campaign_helpers import summarize_visit_run


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic visit missions repeatedly.")
    parser.add_argument("--dashboard-url", default=os.environ.get("CHASECAR_DASHBOARD_URL", "http://127.0.0.1:8860"))
    parser.add_argument("--scenario-id", default="visit_single_ball_proof")
    parser.add_argument("--scenario-label", default="Visit Single Ball")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--hidden-start-settle-s", type=float, default=3.0)
    parser.add_argument("--keep-visited-targets", action="store_true")
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
    raise RuntimeError("Dashboard API did not become ready before visit repeatability run.")


def main() -> int:
    args = parse_args()
    campaign_id = args.campaign_id.strip() or current_utc_stamp()
    campaign_root = ensure_dir(REPO_ROOT / "artifacts" / "session" / campaign_id / "visit_mission_repeatability")
    history_path = campaign_root / "history.jsonl"
    logs_root = ensure_dir(campaign_root / "logs")
    wait_for_dashboard(args.dashboard_url, timeout_s=90.0)

    runs: list[dict[str, object]] = []
    for run_index in range(1, max(args.runs, 1) + 1):
        command = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "visit_mission_runner.py"),
            "--dashboard-url",
            args.dashboard_url,
            "--scenario-id",
            args.scenario_id,
            "--scenario-label",
            args.scenario_label,
            "--hidden-start-settle-s",
            str(args.hidden_start_settle_s),
        ]
        if args.keep_visited_targets:
            command.append("--keep-visited-targets")
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
        run_summary = summarize_visit_run(run_index=run_index, return_code=proc.returncode, output=output)
        run_summary["generated_utc"] = utc_now()
        run_summary["output_log_path"] = str(output_log_path)
        append_jsonl(history_path, run_summary)
        runs.append(run_summary)

    summary = {
        "generated_utc": utc_now(),
        "type": "visit_mission_repeatability",
        "campaign_id": campaign_id,
        "scenario_id": args.scenario_id,
        "scenario_label": args.scenario_label,
        "required_green_runs": max(args.runs, 1),
        "pass_count": sum(1 for item in runs if bool(item.get("pass"))),
        "hidden_start_search_first_count": sum(1 for item in runs if bool(item.get("hidden_start_search_first"))),
        "retry_count_total": sum(int(item.get("retry_count", 0)) for item in runs),
        "promotion_gate_pass": campaign_pass(runs),
        "history_path": str(history_path),
        "runs": runs,
    }
    write_json(campaign_root / "campaign_run_summary.json", summary)
    print(f"VISIT_MISSION_REPEATABILITY_SUMMARY={campaign_root / 'campaign_run_summary.json'}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["promotion_gate_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
