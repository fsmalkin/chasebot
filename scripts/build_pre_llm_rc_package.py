#!/usr/bin/env python3
"""Build a single pre-LLM release-candidate package from campaign + soak artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Build pre-LLM RC package.")
    parser.add_argument("--campaign", required=True, help="Path to pre_llm_campaign_trend.json")
    parser.add_argument("--soak", required=True, help="Path to fidelity pre_llm_headless_summary.json")
    parser.add_argument(
        "--output-dir",
        default=str(repo_root / "artifacts" / "session" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")),
        help="Output directory for RC manifest/readiness files.",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as fp:
        return json.load(fp)


def normalize(raw: str, repo_root: Path) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    return (repo_root / p).resolve()


def stage_lookup(readiness: dict[str, Any], stage_id: str) -> dict[str, Any] | None:
    for step in readiness.get("steps", []):
        if str(step.get("id")) == stage_id:
            return step
    return None


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    campaign_path = normalize(args.campaign, repo_root)
    soak_path = normalize(args.soak, repo_root)
    out_dir = normalize(args.output_dir, repo_root)
    out_dir.mkdir(parents=True, exist_ok=True)

    campaign = read_json(campaign_path)
    soak = read_json(soak_path)

    unresolved: list[dict[str, Any]] = []

    campaign_green = bool((campaign.get("campaign") or {}).get("all_green", False))
    if not campaign_green:
        unresolved.append({"gate": "campaign", "issue": "campaign_all_green_false"})

    soak_green = bool(soak.get("pre_llm_ready", False))
    if not soak_green:
        unresolved.append({"gate": "soak", "issue": "soak_pre_llm_ready_false"})

    soak_lane = None
    for lane in soak.get("lane_results", []):
        if str(lane.get("lane")) == "fidelity":
            soak_lane = lane
            break
    if soak_lane is None and soak.get("lane_results"):
        soak_lane = soak.get("lane_results")[0]
    if soak_lane is None:
        unresolved.append({"gate": "soak", "issue": "missing_fidelity_lane_result"})
        soak_lane = {}

    nav2_duration = int(soak_lane.get("nav2_duration_s") or 0)
    if nav2_duration < 1200:
        unresolved.append({"gate": "soak", "issue": f"nav2_duration_lt_1200 ({nav2_duration})"})

    soak_readiness_path_raw = str(((soak_lane.get("artifacts") or {}).get("readiness_report") or ""))
    soak_readiness_path = normalize(soak_readiness_path_raw, repo_root) if soak_readiness_path_raw else None
    soak_readiness = read_json(soak_readiness_path) if (soak_readiness_path and soak_readiness_path.exists()) else {}

    multi_step = stage_lookup(soak_readiness, "multi_target")
    multi_goal_count = 0
    if multi_step and multi_step.get("artifact_dir"):
        mt_summary_path = normalize(str(multi_step.get("artifact_dir")) + "/multi_target_summary.json", repo_root)
        if mt_summary_path.exists():
            mt_summary = read_json(mt_summary_path)
            multi_goal_count = int(mt_summary.get("goal_count") or 0)
    if multi_goal_count < 10:
        unresolved.append({"gate": "soak", "issue": f"multi_target_goal_count_lt_10 ({multi_goal_count})"})

    rc_pass = len(unresolved) == 0
    generated_utc = datetime.now(timezone.utc).isoformat()

    manifest = {
        "generated_utc": generated_utc,
        "type": "pre_llm_rc_package",
        "campaign_report": str(campaign_path),
        "soak_summary": str(soak_path),
        "soak_readiness_report": str(soak_readiness_path) if soak_readiness_path else None,
        "artifacts": {
            "campaign_report": str(campaign_path),
            "soak_summary": str(soak_path),
            "soak_readiness_report": str(soak_readiness_path) if soak_readiness_path else None,
        },
    }

    readiness = {
        "generated_utc": generated_utc,
        "type": "pre_llm_rc_readiness",
        "pass": rc_pass,
        "status": "pass" if rc_pass else "fail",
        "campaign_all_green": campaign_green,
        "soak_pre_llm_ready": soak_green,
        "soak_nav2_duration_s": nav2_duration,
        "soak_multi_target_goal_count": multi_goal_count,
        "unresolved_issues": unresolved,
    }

    manifest_path = out_dir / "manifest.json"
    readiness_path = out_dir / "readiness_report.json"
    with manifest_path.open("w", encoding="utf-8") as fp:
        json.dump(manifest, fp, indent=2, sort_keys=True)
        fp.write("\n")
    with readiness_path.open("w", encoding="utf-8") as fp:
        json.dump(readiness, fp, indent=2, sort_keys=True)
        fp.write("\n")

    print(f"Wrote {manifest_path}")
    print(f"Wrote {readiness_path}")
    print(f"RC pass={rc_pass}")
    return 0 if rc_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
