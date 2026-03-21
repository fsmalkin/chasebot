#!/usr/bin/env python3
"""Repeatability gate for the bounded turn-then-go LLM proof."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from llm_demo_campaign_helpers import campaign_pass
from llm_demo_campaign_helpers import summarize_demo_run
from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import append_jsonl
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import http_json
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the bounded turn-then-go proof repeatedly.")
    parser.add_argument("--dashboard-url", default=os.environ.get("CHASECAR_DASHBOARD_URL", "http://127.0.0.1:8860"))
    parser.add_argument("--provider", default=os.environ.get("CHASECAR_LLM_PROVIDER", "openai"))
    parser.add_argument("--model", default=os.environ.get("OPENAI_SUPERVISOR_MODEL") or "gpt-5-nano")
    parser.add_argument("--reasoning-effort", default=os.environ.get("OPENAI_SUPERVISOR_REASONING_EFFORT") or os.environ.get("OPENAI_REASONING_EFFORT") or "medium")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--timeout-s", type=float, default=45.0)
    parser.add_argument("--max-runtime-s", type=float, default=180.0)
    parser.add_argument("--campaign-id", default="")
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
    raise RuntimeError("Dashboard API did not become ready before repeatability run.")


def main() -> int:
    args = parse_args()
    campaign_id = args.campaign_id.strip() or current_utc_stamp()
    campaign_root = ensure_dir(REPO_ROOT / "artifacts" / "session" / campaign_id / "llm_turn_then_go_repeatability")
    history_path = campaign_root / "history.jsonl"
    logs_root = ensure_dir(campaign_root / "logs")
    wait_for_dashboard(args.dashboard_url, timeout_s=90.0)

    runs: list[dict[str, object]] = []
    for run_index in range(1, max(args.runs, 1) + 1):
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
        ]
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
        run_summary = summarize_demo_run(
            run_index=run_index,
            return_code=proc.returncode,
            output=output,
            summary_marker="LLM_TURN_THEN_GO_PROOF_SUMMARY=",
        )
        run_summary["generated_utc"] = utc_now()
        run_summary["output_log_path"] = str(output_log_path)
        append_jsonl(history_path, run_summary)
        runs.append(run_summary)

    summary = {
        "generated_utc": utc_now(),
        "type": "llm_turn_then_go_repeatability",
        "campaign_id": campaign_id,
        "required_green_runs": max(args.runs, 1),
        "provider": args.provider,
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "pass_count": sum(1 for item in runs if bool(item.get("pass"))),
        "blocked_only_count": sum(1 for item in runs if bool(item.get("blocked_only"))),
        "invalid_provider_output_count": sum(int(item.get("invalid_provider_output_count", 0)) for item in runs),
        "promotion_gate_pass": campaign_pass(runs),
        "history_path": str(history_path),
        "runs": runs,
    }
    write_json(campaign_root / "campaign_run_summary.json", summary)
    print(f"LLM_TURN_THEN_GO_REPEATABILITY_SUMMARY={campaign_root / 'campaign_run_summary.json'}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["promotion_gate_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
