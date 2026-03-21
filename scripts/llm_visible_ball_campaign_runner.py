#!/usr/bin/env python3
"""Run the bounded supervisor across the visible-ball M3 demo set."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

from llm_demo_campaign_helpers import campaign_pass
from llm_demo_campaign_helpers import summarize_demo_run
from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import append_jsonl
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import http_json
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json


VISIBLE_BALL_SCENARIOS = {
    "m3_single_target": {"label": "M3 Single Target", "target_x": 1.10, "target_y": 0.00},
    "m3_center": {"label": "M3 Center", "target_x": 1.10, "target_y": 0.00},
    "m3_left": {"label": "M3 Left", "target_x": 1.10, "target_y": 0.12},
    "m3_right": {"label": "M3 Right", "target_x": 1.10, "target_y": -0.12},
}

VISIBLE_BALL_TASK = (
    "Use the bounded frozen robot controls to approach the visible ball. "
    "If the ball is visible but not locked, choose acquire_target(ball). "
    "Once the ball is locked, choose plan_to_target(0.25) or track_target() as appropriate. "
    "Prefer safe_stop() if the state becomes unsafe or uncertain."
)


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run bounded supervisor visible-ball demos.")
    parser.add_argument("--dashboard-url", default=os.environ.get("CHASECAR_DASHBOARD_URL", "http://127.0.0.1:8860"))
    parser.add_argument("--provider", default=os.environ.get("CHASECAR_LLM_PROVIDER", "openai"))
    parser.add_argument("--model", default=os.environ.get("OPENAI_SUPERVISOR_MODEL") or "gpt-5-nano")
    parser.add_argument("--reasoning-effort", default=os.environ.get("OPENAI_SUPERVISOR_REASONING_EFFORT") or os.environ.get("OPENAI_REASONING_EFFORT") or "medium")
    parser.add_argument("--timeout-s", type=float, default=45.0)
    parser.add_argument("--max-runtime-s", type=float, default=180.0)
    parser.add_argument("--campaign-id", default="")
    parser.add_argument(
        "--scenarios",
        default="m3_single_target,m3_center,m3_left,m3_right",
        help="Comma-separated visible-ball scenario ids.",
    )
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
    raise RuntimeError("Dashboard API did not become ready before visible-ball campaign.")


def main() -> int:
    args = parse_args()
    requested = [item.strip() for item in str(args.scenarios).split(",") if item.strip()]
    scenario_ids = [item for item in requested if item in VISIBLE_BALL_SCENARIOS]
    if not scenario_ids:
        raise SystemExit("No supported visible-ball scenarios were requested.")

    campaign_id = args.campaign_id.strip() or current_utc_stamp()
    campaign_root = ensure_dir(REPO_ROOT / "artifacts" / "session" / campaign_id / "llm_visible_ball_campaign")
    history_path = campaign_root / "history.jsonl"
    logs_root = ensure_dir(campaign_root / "logs")
    wait_for_dashboard(args.dashboard_url, timeout_s=90.0)

    runs: list[dict[str, object]] = []
    for run_index, scenario_id in enumerate(scenario_ids, start=1):
        scenario = VISIBLE_BALL_SCENARIOS[scenario_id]
        command = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "llm_turn_then_go_proof_runner.py"),
            "--dashboard-url",
            args.dashboard_url,
            "--provider",
            args.provider,
            "--model",
            args.model,
            "--reasoning-effort",
            args.reasoning_effort,
            "--timeout-s",
            str(args.timeout_s),
            "--max-runtime-s",
            str(args.max_runtime_s),
            "--scenario-id",
            scenario_id,
            "--scenario-label",
            str(scenario["label"]),
            "--artifact-kind",
            "llm_visible_ball_demo",
            "--start-visible",
            "--skip-search-requirement",
            "--task",
            VISIBLE_BALL_TASK,
            "--target-behind-m",
            str(scenario["target_x"]),
            "--target-lateral-m",
            str(scenario["target_y"]),
        ]
        proc = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        output_log_path = logs_root / f"{scenario_id}.log"
        output_log_path.write_text(output, encoding="utf-8")
        run_summary = summarize_demo_run(
            run_index=run_index,
            return_code=proc.returncode,
            output=output,
            summary_marker="LLM_BOUNDED_DEMO_SUMMARY=",
        )
        run_summary["generated_utc"] = utc_now()
        run_summary["scenario_id"] = scenario_id
        run_summary["label"] = scenario["label"]
        run_summary["output_log_path"] = str(output_log_path)
        append_jsonl(history_path, run_summary)
        runs.append(run_summary)

    summary = {
        "generated_utc": utc_now(),
        "type": "llm_visible_ball_campaign",
        "campaign_id": campaign_id,
        "provider": args.provider,
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "scenario_ids": scenario_ids,
        "pass_count": sum(1 for item in runs if bool(item.get("pass"))),
        "invalid_provider_output_count": sum(int(item.get("invalid_provider_output_count", 0)) for item in runs),
        "promotion_gate_pass": campaign_pass(runs),
        "history_path": str(history_path),
        "runs": runs,
    }
    write_json(campaign_root / "campaign_run_summary.json", summary)
    print(f"LLM_VISIBLE_BALL_CAMPAIGN_SUMMARY={campaign_root / 'campaign_run_summary.json'}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["promotion_gate_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
