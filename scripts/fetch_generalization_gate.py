#!/usr/bin/env python3
"""Seeded random fetch-to-pose generalization gate."""

from __future__ import annotations

import argparse
import random
import shutil
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


DEFAULT_ARCHITECTURE = "ai_push_coast_servo_v1"
DEFAULT_ARTIFACT_KIND = "gather_mission_fetch_generalization_gate"
DEFAULT_RANDOM_CASES = 6
DEFAULT_SEED = 20260529


@dataclass(frozen=True)
class RandomFetchCase:
    case_id: str
    layout_path: Path
    forward_m: float
    lateral_m: float


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run seeded random fetch-to-pose generalization gates.")
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--random-cases", type=int, default=DEFAULT_RANDOM_CASES)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--architecture", action="append", default=[])
    parser.add_argument("--world-file", default=fetch_gate.DEFAULT_WORLD_FILE)
    parser.add_argument("--surface-profile", default=fetch_gate.DEFAULT_SURFACE_PROFILE)
    parser.add_argument("--fetch-delivery-radius-m", type=float, default=fetch_gate.DEFAULT_FETCH_TARGET["radius_m"])
    parser.add_argument("--ai-push-coast-mode", choices=("shadow", "guarded_live"), default="shadow")
    parser.add_argument("--dashboard-url", default=fetch_gate.DEFAULT_DASHBOARD_URL)
    parser.add_argument("--provider", default="local_stub")
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--scenario-timeout-s", type=float, default=240.0)
    return parser.parse_args()


def _campaign_root(campaign_id: str) -> Path:
    return REPO_ROOT / "artifacts" / "session" / campaign_id / "fetch_generalization_gate"


def _repeatability_summary_path(campaign_id: str) -> Path:
    return (
        REPO_ROOT
        / "artifacts"
        / "session"
        / campaign_id
        / "gather_mission_repeatability"
        / "campaign_run_summary.json"
    )


def _write_layout(path: Path, *, case_id: str, forward_m: float, lateral_m: float) -> None:
    ensure_dir(path.parent)
    write_json(
        path,
        {
            "generated_utc": utc_now(),
            "case_id": case_id,
            "layout_family": "seeded_fetch_generalization",
            "targets": [
                {
                    "id": "ball_1",
                    "label": case_id,
                    "start_visible": True,
                    "forward_m": round(float(forward_m), 6),
                    "lateral_m": round(float(lateral_m), 6),
                    "z_m": 0.021336,
                    "visit_tolerance_m": 0.22,
                    "min_dwell_s": 0.5,
                }
            ],
        },
    )


def generate_random_cases(*, layouts_root: Path, seed: int, random_cases: int) -> list[RandomFetchCase]:
    rng = random.Random(int(seed))
    cases: list[RandomFetchCase] = []
    for index in range(1, max(int(random_cases), 1) + 1):
        forward_m = rng.uniform(0.30, 0.66)
        lateral_m = rng.uniform(-0.18, 0.18)
        case_id = f"seed{int(seed)}_case{index:02d}_f{forward_m:.3f}_l{lateral_m:+.3f}".replace("+", "p").replace("-", "m")
        layout_path = layouts_root / f"{case_id}.json"
        _write_layout(layout_path, case_id=case_id, forward_m=forward_m, lateral_m=lateral_m)
        cases.append(
            RandomFetchCase(
                case_id=case_id,
                layout_path=layout_path,
                forward_m=round(float(forward_m), 6),
                lateral_m=round(float(lateral_m), 6),
            )
        )
    return cases


def _repeatability_command(
    args: argparse.Namespace,
    *,
    campaign_id: str,
    architecture: str,
    case: RandomFetchCase,
    runs: int,
) -> list[str]:
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
        f"Fetch Generalization {architecture} {case.case_id}",
        "--mission-objective",
        "fetch_to_pose",
        "--fetch-gate-mode",
        "full_mission",
        "--fetch-target-x",
        f"{float(fetch_gate.DEFAULT_FETCH_TARGET['x']):.6f}",
        "--fetch-target-y",
        f"{float(fetch_gate.DEFAULT_FETCH_TARGET['y']):.6f}",
        "--fetch-target-z",
        f"{float(fetch_gate.DEFAULT_FETCH_TARGET['z']):.6f}",
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
        architecture,
        "--ai-push-coast-mode",
        args.ai_push_coast_mode,
        "--target-model-sdf",
        fetch_gate.DEFAULT_BALL_SDF,
        "--zone-model-sdf",
        fetch_gate.DEFAULT_ZONE_SDF,
        "--artifact-kind",
        DEFAULT_ARTIFACT_KIND,
        "--target-layout-json",
        str(case.layout_path),
    ]


def _summary_pass(summary: dict[str, Any]) -> bool:
    return bool(summary.get("promotion_gate_pass", summary.get("pass", False)))


def _read_summary(path: Path) -> dict[str, Any]:
    payload = read_json(path) if path.exists() else {}
    return payload if isinstance(payload, dict) else {}


def _run_command(command: list[str], *, log_path: Path, dry_run: bool) -> tuple[int, dict[str, Any]]:
    ensure_dir(log_path.parent)
    if dry_run:
        return 0, {}
    proc = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    log_path.write_text((proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else ""), encoding="utf-8")
    return int(proc.returncode), {}


def _freeze_failure(case: RandomFetchCase, *, frozen_root: Path, architecture: str) -> Path:
    ensure_dir(frozen_root)
    frozen_path = frozen_root / f"{case.case_id}_{architecture}.json"
    shutil.copyfile(case.layout_path, frozen_path)
    return frozen_path


def run_gate(args: argparse.Namespace) -> dict[str, Any]:
    campaign_id = args.campaign_id.strip() or f"live_fetch_generalization_gate_{current_utc_stamp()}"
    gate_root = _campaign_root(campaign_id)
    layouts_root = gate_root / "generated_layouts"
    logs_root = gate_root / "logs"
    frozen_root = gate_root / "frozen_failure_layouts"
    ensure_dir(gate_root)
    architectures = [str(item).strip() for item in args.architecture if str(item).strip()] or [DEFAULT_ARCHITECTURE]
    cases = generate_random_cases(
        layouts_root=layouts_root,
        seed=int(args.seed),
        random_cases=max(int(args.random_cases), 1),
    )
    results: list[dict[str, Any]] = []
    for architecture in architectures:
        architecture_slug = architecture.replace("_", "-")
        for case in cases:
            run_campaign_id = f"{campaign_id}_{architecture_slug}_{case.case_id}"
            summary_path = _repeatability_summary_path(run_campaign_id)
            command = _repeatability_command(
                args,
                campaign_id=run_campaign_id,
                architecture=architecture,
                case=case,
                runs=max(int(args.runs), 1),
            )
            log_path = logs_root / f"{architecture_slug}_{case.case_id}.log"
            return_code, _ = _run_command(command, log_path=log_path, dry_run=bool(args.dry_run))
            summary = _read_summary(summary_path)
            passed = bool(args.dry_run) or (return_code == 0 and _summary_pass(summary))
            reproduced_failure = False
            frozen_failure_layout = ""
            repro: dict[str, Any] = {}
            if not passed and not args.dry_run:
                repro_campaign_id = f"{run_campaign_id}_repro"
                repro_summary_path = _repeatability_summary_path(repro_campaign_id)
                repro_command = _repeatability_command(
                    args,
                    campaign_id=repro_campaign_id,
                    architecture=architecture,
                    case=case,
                    runs=1,
                )
                repro_return_code, _ = _run_command(
                    repro_command,
                    log_path=logs_root / f"{architecture_slug}_{case.case_id}_repro.log",
                    dry_run=False,
                )
                repro_summary = _read_summary(repro_summary_path)
                reproduced_failure = bool(repro_return_code != 0 or not _summary_pass(repro_summary))
                if reproduced_failure:
                    frozen_failure_layout = str(_freeze_failure(case, frozen_root=frozen_root, architecture=architecture))
                repro = {
                    "campaign_id": repro_campaign_id,
                    "return_code": repro_return_code,
                    "summary_path": str(repro_summary_path),
                    "pass": not reproduced_failure,
                    "command": repro_command,
                }
            results.append(
                {
                    "architecture": architecture,
                    "case_id": case.case_id,
                    "forward_m": case.forward_m,
                    "lateral_m": case.lateral_m,
                    "layout_path": str(case.layout_path),
                    "campaign_id": run_campaign_id,
                    "summary_path": str(summary_path),
                    "log_path": str(log_path),
                    "command": command,
                    "return_code": return_code,
                    "pass": bool(passed),
                    "summary": summary,
                    "reproduced_failure": bool(reproduced_failure),
                    "frozen_failure_layout": frozen_failure_layout,
                    "repro": repro,
                }
            )
    pass_count = sum(1 for item in results if bool(item.get("pass", False)))
    summary = {
        "generated_utc": utc_now(),
        "type": "fetch_generalization_gate",
        "campaign_id": campaign_id,
        "dry_run": bool(args.dry_run),
        "seed": int(args.seed),
        "random_cases": len(cases),
        "runs_per_case": max(int(args.runs), 1),
        "architectures": architectures,
        "world_file": args.world_file,
        "surface_profile": args.surface_profile,
        "fetch_delivery_radius_m": round(float(args.fetch_delivery_radius_m), 6),
        "ai_push_coast_mode": args.ai_push_coast_mode,
        "pass": bool(pass_count == len(results)),
        "pass_count": pass_count,
        "fail_count": len(results) - pass_count,
        "generated_layouts_dir": str(layouts_root),
        "frozen_failure_layouts_dir": str(frozen_root),
        "results": results,
    }
    write_json(gate_root / "gate_summary.json", summary)
    write_scorecard(gate_root / "scorecard.md", summary)
    return summary


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    lines = [
        "# Fetch Generalization Gate",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- dry_run: `{bool(summary.get('dry_run', False))}`",
        f"- seed: `{summary.get('seed', '')}`",
        f"- pass: `{bool(summary.get('pass', False))}`",
        f"- pass/fail: `{summary.get('pass_count', 0)}/{summary.get('fail_count', 0)}`",
        f"- mode: `{summary.get('ai_push_coast_mode', 'shadow')}`",
        "",
        "## Cases",
        "",
    ]
    for result in summary.get("results", []) or []:
        if not isinstance(result, dict):
            continue
        lines.append(
            f"- `{result.get('architecture', '')}` `{result.get('case_id', '')}` "
            f"pass=`{bool(result.get('pass', False))}` "
            f"f=`{float(result.get('forward_m', 0.0) or 0.0):.3f}` "
            f"l=`{float(result.get('lateral_m', 0.0) or 0.0):.3f}` "
            f"summary=`{result.get('summary_path', '')}`"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    summary = run_gate(args)
    summary_path = _campaign_root(str(summary.get("campaign_id", ""))) / "gate_summary.json"
    print(f"FETCH_GENERALIZATION_GATE_SUMMARY={summary_path}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    sys.exit(main())
