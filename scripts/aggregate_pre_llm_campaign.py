#!/usr/bin/env python3
"""Aggregate pre-LLM headless campaign runs into one trend report."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Aggregate pre-LLM campaign outputs.")
    parser.add_argument(
        "--runs",
        nargs="+",
        required=True,
        help="Paths to pre_llm_headless_summary.json files.",
    )
    parser.add_argument(
        "--output",
        default=str(repo_root / "artifacts" / "session" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") / "pre_llm_campaign_trend.json"),
        help="Path to write aggregated trend report.",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as fp:
        return json.load(fp)


def normalize_path(raw: str, repo_root: Path) -> Path:
    raw = (raw or "").strip()
    if not raw:
        return Path()
    p = Path(raw)
    if p.is_absolute():
        return p
    return (repo_root / raw).resolve()


def stat(values: list[float]) -> dict[str, float | int] | None:
    if not values:
        return None
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    p95_idx = max(0, min(n - 1, math.ceil(0.95 * n) - 1))
    return {
        "count": n,
        "min": float(sorted_vals[0]),
        "max": float(sorted_vals[-1]),
        "mean": float(sum(sorted_vals) / n),
        "p95": float(sorted_vals[p95_idx]),
    }


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]

    stage_outcomes: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    stage_elapsed: dict[str, list[float]] = defaultdict(list)
    failure_class_counts: dict[str, int] = defaultdict(int)

    nav2_goal_success_rates: list[float] = []
    nav2_goal_accept_rates: list[float] = []
    multi_goal_success_rates: list[float] = []
    multi_goal_accept_rates: list[float] = []
    multi_median_final_distance: list[float] = []
    snapshot_mean_abs_diff: list[float] = []

    run_rows: list[dict[str, Any]] = []
    pass_count = 0

    for run_raw in args.runs:
        run_path = normalize_path(run_raw, repo_root)
        run_data = read_json(run_path)
        run_status = str(run_data.get("overall_status", "fail"))
        if run_status == "pass":
            pass_count += 1

        lane_rows: list[dict[str, Any]] = []
        for lane in run_data.get("lane_results", []):
            lane_name = str(lane.get("lane", "unknown"))
            readiness_raw = str(((lane.get("artifacts") or {}).get("readiness_report") or ""))
            readiness_path = normalize_path(readiness_raw, repo_root)

            if readiness_path and readiness_path.exists():
                readiness = read_json(readiness_path)
                for fc, count in (readiness.get("failure_class_counts") or {}).items():
                    failure_class_counts[str(fc)] += int(count)

                for step in readiness.get("steps", []):
                    stage = str(step.get("id", "unknown"))
                    status = str(step.get("status", "unknown"))
                    stage_outcomes[stage][status] += 1
                    elapsed = step.get("elapsed_s")
                    if isinstance(elapsed, (int, float)):
                        stage_elapsed[f"{lane_name}:{stage}"].append(float(elapsed))

                    artifact_dir = step.get("artifact_dir") or ""
                    if artifact_dir:
                        artifact_path = normalize_path(str(artifact_dir), repo_root)
                        if stage == "snapshot":
                            summary_path = artifact_path / "snapshot_summary.json"
                            if summary_path.exists():
                                snap = read_json(summary_path)
                                image_diff = snap.get("image_diff") or {}
                                mad = image_diff.get("mean_abs_diff")
                                if isinstance(mad, (int, float)):
                                    snapshot_mean_abs_diff.append(float(mad))
                        elif stage == "nav2":
                            summary_path = artifact_path / "nav_summary.json"
                            if summary_path.exists():
                                nav = read_json(summary_path)
                                gsr = nav.get("goal_success_rate")
                                gar = nav.get("goal_accept_rate")
                                if isinstance(gsr, (int, float)):
                                    nav2_goal_success_rates.append(float(gsr))
                                if isinstance(gar, (int, float)):
                                    nav2_goal_accept_rates.append(float(gar))
                        elif stage == "multi_target":
                            summary_path = artifact_path / "multi_target_summary.json"
                            if summary_path.exists():
                                mt = read_json(summary_path)
                                gsr = mt.get("goal_success_rate")
                                gar = mt.get("goal_accept_rate")
                                mfd = mt.get("median_final_distance_m")
                                if isinstance(gsr, (int, float)):
                                    multi_goal_success_rates.append(float(gsr))
                                if isinstance(gar, (int, float)):
                                    multi_goal_accept_rates.append(float(gar))
                                if isinstance(mfd, (int, float)):
                                    multi_median_final_distance.append(float(mfd))

                lane_rows.append(
                    {
                        "lane": lane_name,
                        "status": lane.get("status"),
                        "readiness_report": str(readiness_path),
                        "stage_timing_s": readiness.get("stage_timing_s"),
                        "stage_retry_counts": readiness.get("stage_retry_counts"),
                        "failure_class": readiness.get("failure_class"),
                    }
                )
            else:
                lane_rows.append(
                    {
                        "lane": lane_name,
                        "status": lane.get("status"),
                        "readiness_report": readiness_raw,
                        "error": "missing_readiness_report",
                    }
                )

        run_rows.append(
            {
                "summary_path": str(run_path),
                "run_id": run_data.get("run_id"),
                "status": run_status,
                "pre_llm_ready": bool(run_data.get("pre_llm_ready", False)),
                "lanes": lane_rows,
            }
        )

    total_runs = len(args.runs)
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "campaign": {
            "run_count": total_runs,
            "pass_count": pass_count,
            "all_green": (pass_count == total_runs and total_runs > 0),
            "run_summaries": run_rows,
        },
        "stage_outcomes": {k: dict(v) for k, v in stage_outcomes.items()},
        "stage_elapsed_s_stats": {k: stat(v) for k, v in stage_elapsed.items()},
        "failure_class_counts": dict(failure_class_counts),
        "metrics": {
            "nav2_goal_success_rate": stat(nav2_goal_success_rates),
            "nav2_goal_accept_rate": stat(nav2_goal_accept_rates),
            "multi_target_goal_success_rate": stat(multi_goal_success_rates),
            "multi_target_goal_accept_rate": stat(multi_goal_accept_rates),
            "multi_target_median_final_distance_m": stat(multi_median_final_distance),
            "snapshot_mean_abs_diff": stat(snapshot_mean_abs_diff),
        },
    }

    output_path = normalize_path(args.output, repo_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fp:
        json.dump(report, fp, indent=2, sort_keys=True)
        fp.write("\n")

    print(f"Wrote {output_path}")
    print(f"Campaign all_green={report['campaign']['all_green']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
