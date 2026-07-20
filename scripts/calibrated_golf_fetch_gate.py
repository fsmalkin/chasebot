#!/usr/bin/env python3
"""Run calibrated golf-ball fetch-to-pose gates."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import read_json
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json


DEFAULT_DASHBOARD_URL = "http://127.0.0.1:8860"
DEFAULT_WORLD_FILE = "yolo_test_world_v6_calibrated_golf_turf.world"
DEFAULT_SURFACE_PROFILE = "calibrated_golf_turf"
DEFAULT_BALL_SDF = "ros2_config/calibrated_golf_ball.sdf"
DEFAULT_ZONE_SDF = "ros2_config/golf_ball_delivery_zone_marker.sdf"
DEFAULT_FETCH_TARGET = {"x": 0.95, "y": 0.0, "z": 0.001, "radius_m": 0.30}
DEFAULT_CENTERLINE_LAYOUT = "ros2_config/target_layouts/golf_ball_circle_delivery_zero.json"
OFF_AXIS_LAYOUTS = {
    "left05": "ros2_config/target_layouts/golf_ball_circle_delivery_left05.json",
    "right05": "ros2_config/target_layouts/golf_ball_circle_delivery_right05.json",
}


@dataclass(frozen=True)
class GateSpec:
    gate_id: str
    label: str
    command: list[str]
    campaign_id: str
    summary_path: Path


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run calibrated golf-ball fetch gates.")
    parser.add_argument("--dashboard-url", default=DEFAULT_DASHBOARD_URL)
    parser.add_argument("--suite", choices=("centerline", "off_axis", "all"), default="centerline")
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--cta-runs", type=int, default=3)
    parser.add_argument("--policy-runs", type=int, default=3)
    parser.add_argument("--off-axis-runs", type=int, default=1)
    parser.add_argument("--provider", default="local_stub")
    parser.add_argument("--world-file", default=DEFAULT_WORLD_FILE)
    parser.add_argument("--surface-profile", default=DEFAULT_SURFACE_PROFILE)
    parser.add_argument("--fetch-target-x", type=float, default=DEFAULT_FETCH_TARGET["x"])
    parser.add_argument("--fetch-target-y", type=float, default=DEFAULT_FETCH_TARGET["y"])
    parser.add_argument("--fetch-target-z", type=float, default=DEFAULT_FETCH_TARGET["z"])
    parser.add_argument("--fetch-delivery-radius-m", type=float, default=DEFAULT_FETCH_TARGET["radius_m"])
    parser.add_argument("--scenario-timeout-s", type=float, default=240.0)
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stop-on-failure", action="store_true")
    return parser.parse_args()


def _summary_path(campaign_id: str) -> Path:
    return REPO_ROOT / "artifacts" / "session" / campaign_id / "gather_mission_repeatability" / "campaign_run_summary.json"


def _repeatability_command(
    args: argparse.Namespace,
    *,
    campaign_id: str,
    runs: int,
    label: str,
    execution_mode: str,
    target_layout_json: str = "",
    dashboard_scenario_id: str = "",
    artifact_kind: str = "",
) -> list[str]:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "gather_mission_repeatability_runner.py"),
        "--dashboard-url",
        args.dashboard_url,
        "--execution-mode",
        execution_mode,
        "--scenario-id",
        dashboard_scenario_id or "corral_single_ball_place",
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
        "object_centric_gather_policy_v1",
    ]
    if execution_mode == "direct":
        command.extend(["--target-model-sdf", DEFAULT_BALL_SDF])
        command.extend(["--zone-model-sdf", DEFAULT_ZONE_SDF])
        command.extend(["--artifact-kind", artifact_kind or "gather_mission_calibrated_golf_policy_probe"])
        if target_layout_json:
            command.extend(["--target-layout-json", target_layout_json])
    return command


def build_gate_specs(args: argparse.Namespace) -> list[GateSpec]:
    base_campaign_id = args.campaign_id.strip() or f"live_calibrated_golf_fetch_gate_{current_utc_stamp()}"
    specs: list[GateSpec] = []
    if args.suite in {"centerline", "all"}:
        cta_campaign = f"{base_campaign_id}_cta_centerline"
        specs.append(
            GateSpec(
                gate_id="cta_centerline",
                label="Golf Ball Circle Delivery CTA Repeatability",
                command=_repeatability_command(
                    args,
                    campaign_id=cta_campaign,
                    runs=args.cta_runs,
                    label="Golf Ball Circle Delivery CTA Repeatability",
                    execution_mode="dashboard_scenario",
                    dashboard_scenario_id="golf_ball_circle_delivery_uat",
                ),
                campaign_id=cta_campaign,
                summary_path=_summary_path(cta_campaign),
            )
        )
        policy_campaign = f"{base_campaign_id}_policy_centerline"
        specs.append(
            GateSpec(
                gate_id="policy_centerline",
                label="Calibrated Golf Object Policy Centerline Repeatability",
                command=_repeatability_command(
                    args,
                    campaign_id=policy_campaign,
                    runs=args.policy_runs,
                    label="Calibrated Golf Object Policy Centerline Repeatability",
                    execution_mode="direct",
                    target_layout_json=DEFAULT_CENTERLINE_LAYOUT,
                ),
                campaign_id=policy_campaign,
                summary_path=_summary_path(policy_campaign),
            )
        )
    if args.suite in {"off_axis", "all"}:
        for layout_id, layout_path in OFF_AXIS_LAYOUTS.items():
            campaign = f"{base_campaign_id}_policy_{layout_id}"
            label = f"Calibrated Golf Object Policy {layout_id} Off-Axis Smoke"
            specs.append(
                GateSpec(
                    gate_id=f"policy_{layout_id}",
                    label=label,
                    command=_repeatability_command(
                        args,
                        campaign_id=campaign,
                        runs=args.off_axis_runs,
                        label=label,
                        execution_mode="direct",
                        target_layout_json=layout_path,
                    ),
                    campaign_id=campaign,
                    summary_path=_summary_path(campaign),
                )
            )
    return specs


def _gate_pass(summary: dict[str, Any]) -> bool:
    if "promotion_gate_pass" in summary:
        return bool(summary.get("promotion_gate_pass", False))
    return bool(summary.get("pass", False))


def _read_gate_summary(spec: GateSpec) -> dict[str, Any]:
    summary = read_json(spec.summary_path)
    return summary if isinstance(summary, dict) else {}


def run_gate(spec: GateSpec, *, logs_root: Path, dry_run: bool) -> dict[str, Any]:
    ensure_dir(logs_root)
    log_path = logs_root / f"{spec.gate_id}.log"
    payload: dict[str, Any] = {
        "gate_id": spec.gate_id,
        "label": spec.label,
        "campaign_id": spec.campaign_id,
        "summary_path": str(spec.summary_path),
        "log_path": str(log_path),
        "command": spec.command,
        "dry_run": dry_run,
    }
    if dry_run:
        payload.update({"return_code": 0, "pass": True, "summary": {}})
        return payload
    proc = subprocess.run(
        spec.command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    log_path.write_text((proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else ""), encoding="utf-8")
    summary = _read_gate_summary(spec)
    payload.update(
        {
            "return_code": proc.returncode,
            "pass": proc.returncode == 0 and _gate_pass(summary),
            "promotion_gate_pass": bool(summary.get("promotion_gate_pass", False)),
            "fetch_to_pose_pass_count": int(summary.get("fetch_to_pose_pass_count", 0) or 0),
            "fetch_to_pose_fail_count": int(summary.get("fetch_to_pose_fail_count", 0) or 0),
            "required_green_runs": int(summary.get("required_green_runs", 0) or 0),
            "summary": summary,
        }
    )
    return payload


def main() -> int:
    args = parse_args()
    gate_campaign_id = args.campaign_id.strip() or f"live_calibrated_golf_fetch_gate_{current_utc_stamp()}"
    args.campaign_id = gate_campaign_id
    gate_root = ensure_dir(REPO_ROOT / "artifacts" / "session" / gate_campaign_id / "calibrated_golf_fetch_gate")
    logs_root = ensure_dir(gate_root / "logs")
    specs = build_gate_specs(args)
    results: list[dict[str, Any]] = []
    for spec in specs:
        result = run_gate(spec, logs_root=logs_root, dry_run=bool(args.dry_run))
        results.append(result)
        if args.stop_on_failure and not bool(result.get("pass", False)):
            break
    pass_count = sum(1 for item in results if bool(item.get("pass", False)))
    summary = {
        "generated_utc": utc_now(),
        "type": "calibrated_golf_fetch_gate",
        "campaign_id": gate_campaign_id,
        "suite": args.suite,
        "pass": bool(results) and pass_count == len(results),
        "pass_count": pass_count,
        "fail_count": max(len(results) - pass_count, 0),
        "dry_run": bool(args.dry_run),
        "world_file": args.world_file,
        "surface_profile": args.surface_profile,
        "fetch_pose_world": {
            "x": float(args.fetch_target_x),
            "y": float(args.fetch_target_y),
            "z": float(args.fetch_target_z),
            "radius_m": float(args.fetch_delivery_radius_m),
        },
        "results": results,
    }
    summary_path = gate_root / "gate_summary.json"
    write_json(summary_path, summary)
    print(f"CALIBRATED_GOLF_FETCH_GATE_SUMMARY={summary_path}")
    return 0 if summary["pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
