"""Run one-ball corral repeatability across surface profiles and compare outcomes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from corral_surface_calibration_helpers import build_surface_calibration_lanes
from corral_surface_calibration_helpers import build_surface_calibration_scorecard_markdown
from corral_surface_calibration_helpers import summarize_surface_calibration
from corral_surface_calibration_helpers import summarize_surface_lane
from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import http_json
from llm_supervisor_core import read_json
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json
from visit_mission_campaign_helpers import parse_marker


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare one-ball corral behavior across surface profiles.")
    parser.add_argument("--dashboard-url", default="http://127.0.0.1:8860")
    parser.add_argument("--scenario-id", default="corral_single_ball_place")
    parser.add_argument("--scenario-label", default="Corral Single Ball Place")
    parser.add_argument("--runs-per-lane", type=int, default=3)
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--execution-mode", choices=("dashboard_scenario", "direct"), default="dashboard_scenario")
    parser.add_argument("--promotion-gate-mode", choices=("strict", "pass_only"), default="pass_only")
    parser.add_argument("--visit-runtime-json", default="")
    parser.add_argument("--gather-runtime-json", default="")
    parser.add_argument("--preferred-surface-profile", default="short_turf")
    return parser.parse_args()


def wait_for_dashboard(dashboard_url: str, timeout_s: float) -> None:
    import time

    deadline = time.monotonic() + max(timeout_s, 5.0)
    while time.monotonic() < deadline:
        try:
            status, _ = http_json(f"{dashboard_url.rstrip('/')}/api/state", timeout_s=5.0)
            if status == 200:
                return
        except Exception:
            pass
        time.sleep(1.0)
    raise RuntimeError("Dashboard API did not become ready before surface calibration run.")


def _build_lane_command(
    args: argparse.Namespace,
    *,
    lane_surface_profile: str,
    lane_world_file: str,
    lane_campaign_id: str,
) -> list[str]:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "gather_mission_repeatability_runner.py"),
        "--dashboard-url",
        args.dashboard_url,
        "--scenario-id",
        args.scenario_id,
        "--scenario-label",
        args.scenario_label,
        "--runs",
        str(max(args.runs_per_lane, 1)),
        "--campaign-id",
        lane_campaign_id,
        "--provider",
        args.provider,
        "--execution-mode",
        args.execution_mode,
        "--promotion-gate-mode",
        args.promotion_gate_mode,
        "--world-file",
        lane_world_file,
        "--surface-profile",
        lane_surface_profile,
    ]
    if args.visit_runtime_json.strip():
        command.extend(["--visit-runtime-json", args.visit_runtime_json.strip()])
    if args.gather_runtime_json.strip():
        command.extend(["--gather-runtime-json", args.gather_runtime_json.strip()])
    return command


def _read_lane_repeatability_summary(output: str) -> Path:
    marker = parse_marker(output, "GATHER_MISSION_REPEATABILITY_SUMMARY=")
    if not marker:
        raise RuntimeError("Lane repeatability run did not emit GATHER_MISSION_REPEATABILITY_SUMMARY.")
    summary_path = Path(marker)
    if not summary_path.exists():
        raise RuntimeError(f"Lane repeatability summary not found: {summary_path}")
    return summary_path


def main() -> int:
    args = parse_args()
    campaign_id = args.campaign_id.strip() or current_utc_stamp()
    campaign_root = ensure_dir(REPO_ROOT / "artifacts" / "session" / campaign_id / "corral_surface_calibration")
    logs_root = ensure_dir(campaign_root / "logs")
    wait_for_dashboard(args.dashboard_url, timeout_s=90.0)

    lane_results: list[dict[str, object]] = []
    for lane in build_surface_calibration_lanes():
        lane_campaign_id = f"{campaign_id}_{lane.surface_profile}"
        lane_log_path = logs_root / f"{lane.surface_profile}.log"
        command = _build_lane_command(
            args,
            lane_surface_profile=lane.surface_profile,
            lane_world_file=lane.world_file,
            lane_campaign_id=lane_campaign_id,
        )
        proc = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        lane_log_path.write_text(output, encoding="utf-8")
        summary_path = _read_lane_repeatability_summary(output)
        repeatability_summary = read_json(summary_path)
        runs = list(repeatability_summary.get("runs", [])) if isinstance(repeatability_summary.get("runs"), list) else []
        lane_summary = summarize_surface_lane(lane=lane, runs=runs)
        lane_summary.update(
            {
                "generated_utc": utc_now(),
                "repeatability_campaign_id": lane_campaign_id,
                "repeatability_return_code": proc.returncode,
                "repeatability_summary_path": str(summary_path),
                "repeatability_scorecard_path": str(summary_path.parent / "scorecard.md"),
                "output_log_path": str(lane_log_path),
            }
        )
        lane_results.append(lane_summary)

    rollup = summarize_surface_calibration(
        lane_summaries=lane_results,
        preferred_surface_profile=str(args.preferred_surface_profile or "short_turf"),
    )
    summary = {
        "generated_utc": utc_now(),
        "type": "corral_surface_calibration",
        "campaign_id": campaign_id,
        "scenario_id": args.scenario_id,
        "scenario_label": args.scenario_label,
        "runs_per_lane": max(args.runs_per_lane, 1),
        "preferred_surface_profile": str(args.preferred_surface_profile or "short_turf"),
        **rollup,
    }
    write_json(campaign_root / "campaign_summary.json", summary)
    scorecard = build_surface_calibration_scorecard_markdown(summary=summary, lane_results=lane_results)
    (campaign_root / "scorecard.md").write_text(scorecard, encoding="utf-8")
    print(f"CORRAL_SURFACE_CALIBRATION_SUMMARY={campaign_root / 'campaign_summary.json'}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if str(summary.get("canonical_surface_profile", "") or "").strip() else 2


if __name__ == "__main__":
    raise SystemExit(main())
