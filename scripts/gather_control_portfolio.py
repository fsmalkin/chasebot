#!/usr/bin/env python3
"""Compare bounded gather-control branches from existing repeatability summaries."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

from llm_supervisor_core import ensure_dir
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_KIND = "gather_control_portfolio"
STRESS_FIXTURE_LABELS = ("early_stall", "mid_stall", "late_stall", "terminal_stall")

RATE_FIELDS = (
    "pass",
    "mission_completed_pass",
    "pre_stage_pose_reached",
    "pre_stage_handoff_pass",
    "staging_pose_reached",
    "capture_entry_reached",
    "final_inside_retrieval_corral",
    "ball_stopped_in_corral",
    "rolled_away_after_release",
    "settled_in_corral_pass",
    "final_center_inside_zone",
    "final_all_targets_inside_retrieval_corral",
    "final_all_targets_stopped",
    "final_three_ball_corral_pass",
)
PHASE_REACH_FIELDS = (
    "pre_stage_pose_reached",
    "pre_stage_handoff_pass",
    "staging_pose_reached",
    "capture_entry_reached",
)
CORRAL_RATE_FIELDS = (
    "final_inside_retrieval_corral",
    "ball_stopped_in_corral",
    "rolled_away_after_release",
    "settled_in_corral_pass",
    "final_center_inside_zone",
    "final_all_targets_inside_retrieval_corral",
    "final_all_targets_stopped",
    "final_three_ball_corral_pass",
)
NUMERIC_FIELDS = (
    "mission_time_s",
    "final_settle_distance_m",
    "max_overshoot_distance_m",
    "settle_time_s",
    "placed_count",
    "retrieved_count",
    "capture_loss_count",
    "post_visit_revisit_count",
)
SCORE_WEIGHTS = {
    "pass_rate": 0.30,
    "practical_retrieval_pass_rate": 0.35,
    "mission_completed_pass_rate": 0.15,
    "pre_stage_handoff_pass_rate": 0.07,
    "staging_pose_reached_rate": 0.05,
    "capture_entry_reached_rate": 0.08,
}


def sanitize_branch_name(name: str) -> str:
    """Return a safe artifact directory slug while keeping names human-readable."""
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name or "").strip())
    while ".." in cleaned:
        cleaned = cleaned.replace("..", "_")
    cleaned = re.sub(r"_+", "_", cleaned)
    cleaned = cleaned.strip("._-")
    if not cleaned:
        raise ValueError(f"Invalid empty branch name: {name!r}")
    if cleaned in {".", ".."} or "/" in cleaned or "\\" in cleaned:
        raise ValueError(f"Invalid branch name for artifact path: {name!r}")
    return cleaned


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Campaign summary does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Campaign summary must be a JSON object: {path}")
    return payload


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _finite_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _maybe_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "pass", "passed"}:
            return True
        if normalized in {"false", "0", "no", "n", "fail", "failed"}:
            return False
    return None


def _first_present_bool(*values: Any) -> bool | None:
    for value in values:
        parsed = _maybe_bool(value)
        if parsed is not None:
            return parsed
    return None


def _nested_approach(run: dict[str, Any]) -> dict[str, Any]:
    latest = _dict_value(run.get("latest_approach_progress"))
    if latest:
        return latest
    return _dict_value(run.get("fresh_attempt_approach"))


def bool_metric_value(run: dict[str, Any], field: str) -> bool | None:
    approach = _nested_approach(run)
    pre_stage = _dict_value(approach.get("pre_stage"))
    stage = _dict_value(approach.get("stage"))
    capture_entry = _dict_value(approach.get("capture_entry"))
    if field == "pre_stage_pose_reached":
        return _first_present_bool(run.get(field), pre_stage.get("pose_reached"))
    if field == "pre_stage_handoff_pass":
        return _first_present_bool(run.get(field), pre_stage.get("handoff_pass"))
    if field == "staging_pose_reached":
        return _first_present_bool(run.get(field), stage.get("pose_reached"))
    if field == "capture_entry_reached":
        return _first_present_bool(
            run.get(field),
            capture_entry.get("reached"),
            capture_entry.get("pass"),
        )
    return _first_present_bool(run.get(field))


def _rate_metric(runs: list[dict[str, Any]], field: str) -> dict[str, Any]:
    values = [bool_metric_value(run, field) for run in runs]
    observed = [value for value in values if value is not None]
    true_count = sum(1 for value in observed if value)
    sample_count = len(observed)
    missing_count = len(values) - sample_count
    return {
        "field": field,
        "true_count": true_count,
        "sample_count": sample_count,
        "missing_count": missing_count,
        "rate": round(true_count / sample_count, 6) if sample_count else None,
    }


def practical_retrieval_pass(run: dict[str, Any]) -> bool | None:
    inside = bool_metric_value(run, "final_inside_retrieval_corral")
    stopped = bool_metric_value(run, "ball_stopped_in_corral")
    rolled_away = bool_metric_value(run, "rolled_away_after_release")
    if inside is None or stopped is None or rolled_away is None:
        return None
    return inside and stopped and not rolled_away


def _practical_retrieval_metric(runs: list[dict[str, Any]]) -> dict[str, Any]:
    values = [practical_retrieval_pass(run) for run in runs]
    observed = [value for value in values if value is not None]
    true_count = sum(1 for value in observed if value)
    sample_count = len(observed)
    missing_count = len(values) - sample_count
    return {
        "field": "practical_retrieval_pass",
        "true_count": true_count,
        "sample_count": sample_count,
        "missing_count": missing_count,
        "rate": round(true_count / sample_count, 6) if sample_count else None,
    }


def _numeric_metric(runs: list[dict[str, Any]], field: str) -> dict[str, Any]:
    values = [_finite_float(run.get(field)) for run in runs]
    observed = [value for value in values if value is not None]
    sample_count = len(observed)
    missing_count = len(values) - sample_count
    return {
        "field": field,
        "sample_count": sample_count,
        "missing_count": missing_count,
        "avg": round(sum(observed) / sample_count, 6) if sample_count else None,
        "min": round(min(observed), 6) if sample_count else None,
        "max": round(max(observed), 6) if sample_count else None,
    }


def _rate_value(metric: dict[str, Any]) -> float | None:
    value = metric.get("rate")
    return float(value) if isinstance(value, (int, float)) else None


def _score_value(metric: dict[str, Any]) -> float:
    value = _rate_value(metric)
    return value if value is not None else 0.0


def _blocking_reasons(
    *,
    run_count: int,
    rate_metrics: dict[str, dict[str, Any]],
    practical_metric: dict[str, Any],
    hard_case_stress_status: str,
) -> list[str]:
    reasons: list[str] = []
    if run_count <= 0:
        reasons.append("no_runs")
    for field in (
        "pass",
        "mission_completed_pass",
        "pre_stage_pose_reached",
        "pre_stage_handoff_pass",
        "staging_pose_reached",
        "capture_entry_reached",
        "final_inside_retrieval_corral",
        "ball_stopped_in_corral",
        "rolled_away_after_release",
    ):
        metric = rate_metrics.get(field, {})
        if int(metric.get("missing_count", 0) or 0) > 0:
            reasons.append(f"missing_{field}")
    if int(practical_metric.get("missing_count", 0) or 0) > 0:
        reasons.append("missing_practical_retrieval_fields")
    practical_rate = _rate_value(practical_metric)
    if practical_rate is None:
        reasons.append("practical_retrieval_not_observed")
    elif practical_rate <= 0.0:
        reasons.append("no_practical_retrieval_pass")
    if hard_case_stress_status != "passing":
        reasons.append(f"hard_case_stress_{hard_case_stress_status}")
    return sorted(set(reasons))


def build_branch_summary(
    *,
    branch_name: str,
    source_summary_path: Path,
    source_summary: dict[str, Any],
) -> dict[str, Any]:
    runs = source_summary.get("runs", [])
    if not isinstance(runs, list):
        raise ValueError(f"Campaign summary has non-list runs field: {source_summary_path}")
    normalized_runs = [run for run in runs if isinstance(run, dict)]
    branch_slug = sanitize_branch_name(branch_name)
    rate_metrics = {field: _rate_metric(normalized_runs, field) for field in RATE_FIELDS}
    practical_metric = _practical_retrieval_metric(normalized_runs)
    numeric_metrics = {field: _numeric_metric(normalized_runs, field) for field in NUMERIC_FIELDS}

    score_components = {
        "pass_rate": _score_value(rate_metrics["pass"]),
        "practical_retrieval_pass_rate": _score_value(practical_metric),
        "mission_completed_pass_rate": _score_value(rate_metrics["mission_completed_pass"]),
        "pre_stage_handoff_pass_rate": _score_value(rate_metrics["pre_stage_handoff_pass"]),
        "staging_pose_reached_rate": _score_value(rate_metrics["staging_pose_reached"]),
        "capture_entry_reached_rate": _score_value(rate_metrics["capture_entry_reached"]),
    }
    end_to_end_score = round(
        sum(score_components[key] * weight for key, weight in SCORE_WEIGHTS.items()),
        6,
    )
    hard_case_stress = {
        "status": "not_evaluated",
        "required_fixture_labels": list(STRESS_FIXTURE_LABELS),
        "evaluated_fixture_labels": [],
        "missing_fixture_labels": list(STRESS_FIXTURE_LABELS),
        "reason": "fixture_level_branch_evidence_not_supplied",
    }
    blocking_reasons = _blocking_reasons(
        run_count=len(normalized_runs),
        rate_metrics=rate_metrics,
        practical_metric=practical_metric,
        hard_case_stress_status=hard_case_stress["status"],
    )
    average_mission_time_s = numeric_metrics["mission_time_s"]["avg"]
    return {
        "type": "gather_control_portfolio_branch",
        "generated_utc": utc_now(),
        "branch_name": branch_name,
        "branch_slug": branch_slug,
        "source_summary_path": str(source_summary_path),
        "source_summary_type": str(source_summary.get("type", "") or ""),
        "source_campaign_id": str(source_summary.get("campaign_id", "") or ""),
        "source_scenario_id": str(source_summary.get("scenario_id", "") or ""),
        "run_count": len(normalized_runs),
        "pass_rate": _rate_value(rate_metrics["pass"]),
        "mission_completed_pass_rate": _rate_value(rate_metrics["mission_completed_pass"]),
        "practical_retrieval_pass_rate": _rate_value(practical_metric),
        "phase_reach_rates": {field: _rate_value(rate_metrics[field]) for field in PHASE_REACH_FIELDS},
        "average_mission_time_s": average_mission_time_s,
        "corral_placement_metrics": {
            "practical_retrieval_pass": practical_metric,
            **{field: rate_metrics[field] for field in CORRAL_RATE_FIELDS},
            "final_settle_distance_m": numeric_metrics["final_settle_distance_m"],
            "max_overshoot_distance_m": numeric_metrics["max_overshoot_distance_m"],
            "settle_time_s": numeric_metrics["settle_time_s"],
            "placed_count": numeric_metrics["placed_count"],
            "retrieved_count": numeric_metrics["retrieved_count"],
            "capture_loss_count": numeric_metrics["capture_loss_count"],
            "post_visit_revisit_count": numeric_metrics["post_visit_revisit_count"],
        },
        "rate_metrics": {**rate_metrics, "practical_retrieval_pass": practical_metric},
        "numeric_metrics": numeric_metrics,
        "end_to_end_score": end_to_end_score,
        "score_components": score_components,
        "hard_case_stress_status": hard_case_stress["status"],
        "hard_case_stress": hard_case_stress,
        "live_promotion_ready": len(blocking_reasons) == 0,
        "blocking_reasons": blocking_reasons,
    }


def _best_branch(branches: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not branches:
        return None
    return sorted(
        branches,
        key=lambda branch: (
            float(branch.get("end_to_end_score", 0.0) or 0.0),
            float(branch.get("practical_retrieval_pass_rate", 0.0) or 0.0),
            float(branch.get("pass_rate", 0.0) or 0.0),
            -float(branch.get("average_mission_time_s", 999999.0) or 999999.0),
            str(branch.get("branch_name", "")),
        ),
        reverse=True,
    )[0]


def _number_delta(value: Any, baseline_value: Any) -> float | None:
    if not isinstance(value, (int, float)) or not isinstance(baseline_value, (int, float)):
        return None
    return round(float(value) - float(baseline_value), 6)


def _attach_baseline_comparisons(branches: list[dict[str, Any]], baseline_branch: str | None) -> None:
    if not baseline_branch:
        return
    baseline = next((branch for branch in branches if branch.get("branch_name") == baseline_branch), None)
    if not baseline:
        return
    for branch in branches:
        branch["baseline_comparison"] = {
            "baseline_branch": baseline_branch,
            "is_baseline": branch.get("branch_name") == baseline_branch,
            "end_to_end_score_delta": _number_delta(branch.get("end_to_end_score"), baseline.get("end_to_end_score")),
            "pass_rate_delta": _number_delta(branch.get("pass_rate"), baseline.get("pass_rate")),
            "mission_completed_pass_rate_delta": _number_delta(
                branch.get("mission_completed_pass_rate"),
                baseline.get("mission_completed_pass_rate"),
            ),
            "practical_retrieval_pass_rate_delta": _number_delta(
                branch.get("practical_retrieval_pass_rate"),
                baseline.get("practical_retrieval_pass_rate"),
            ),
            "average_mission_time_delta_s": _number_delta(
                branch.get("average_mission_time_s"),
                baseline.get("average_mission_time_s"),
            ),
        }


def build_portfolio_summary(
    *,
    campaign_id: str,
    branch_specs: list[tuple[str, Path]],
    baseline_branch: str | None = None,
) -> dict[str, Any]:
    seen_slugs: set[str] = set()
    branches: list[dict[str, Any]] = []
    for branch_name, source_path in branch_specs:
        branch_slug = sanitize_branch_name(branch_name)
        if branch_slug in seen_slugs:
            raise ValueError(f"Duplicate sanitized branch name: {branch_name!r} -> {branch_slug!r}")
        seen_slugs.add(branch_slug)
        source_summary = _load_json_object(source_path)
        branches.append(
            build_branch_summary(
                branch_name=branch_name,
                source_summary_path=source_path,
                source_summary=source_summary,
            )
        )
    branch_names = {str(branch.get("branch_name", "")) for branch in branches}
    if baseline_branch and baseline_branch not in branch_names:
        raise ValueError(f"Baseline branch {baseline_branch!r} was not provided in --branch specs")
    _attach_baseline_comparisons(branches, baseline_branch)
    best = _best_branch(branches)
    ready_branches = [branch for branch in branches if bool(branch.get("live_promotion_ready", False))]
    stress_statuses = {str(branch.get("hard_case_stress_status", "")) for branch in branches}
    recommended_next_action = "collect_hard_case_stress_evidence"
    if ready_branches:
        recommended_next_action = "promote_best_ready_branch"
    elif stress_statuses and stress_statuses != {"not_evaluated"}:
        recommended_next_action = "inspect_branch_blocking_reasons"
    portfolio_blocking_reasons = sorted({reason for branch in branches for reason in branch.get("blocking_reasons", [])})
    return {
        "type": OUTPUT_KIND,
        "generated_utc": utc_now(),
        "campaign_id": campaign_id,
        "baseline_branch": baseline_branch or "",
        "branch_count": len(branches),
        "stress_fixture_labels": list(STRESS_FIXTURE_LABELS),
        "best_observed_branch": str(best.get("branch_name", "")) if best else "",
        "best_observed_score": float(best.get("end_to_end_score", 0.0) or 0.0) if best else None,
        "recommended_next_action": recommended_next_action,
        "live_promotion_ready": bool(ready_branches),
        "blocking_reasons": portfolio_blocking_reasons,
        "branches": branches,
    }


def _format_rate(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{float(value) * 100.0:.1f}%"
    return "missing"


def _format_seconds(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{float(value):.3f}s"
    return "missing"


def build_scorecard_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Gather Control Portfolio",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- baseline_branch: `{summary.get('baseline_branch', '') or 'none'}`",
        f"- best_observed_branch: `{summary.get('best_observed_branch', '') or 'none'}`",
        f"- best_observed_score: `{summary.get('best_observed_score', 'missing')}`",
        f"- recommended_next_action: `{summary.get('recommended_next_action', '')}`",
        "",
        "| branch | runs | pass | practical retrieval | pre-stage | handoff | staging | capture entry | avg mission time | stress | ready | blockers |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for branch in summary.get("branches", []):
        phase_rates = _dict_value(branch.get("phase_reach_rates"))
        blockers = branch.get("blocking_reasons", [])
        if not isinstance(blockers, list):
            blockers = []
        lines.append(
            "| "
            f"`{branch.get('branch_name', '')}` | "
            f"{int(branch.get('run_count', 0) or 0)} | "
            f"{_format_rate(branch.get('pass_rate'))} | "
            f"{_format_rate(branch.get('practical_retrieval_pass_rate'))} | "
            f"{_format_rate(phase_rates.get('pre_stage_pose_reached'))} | "
            f"{_format_rate(phase_rates.get('pre_stage_handoff_pass'))} | "
            f"{_format_rate(phase_rates.get('staging_pose_reached'))} | "
            f"{_format_rate(phase_rates.get('capture_entry_reached'))} | "
            f"{_format_seconds(branch.get('average_mission_time_s'))} | "
            f"`{branch.get('hard_case_stress_status', '')}` | "
            f"`{bool(branch.get('live_promotion_ready', False))}` | "
            f"`{', '.join(str(item) for item in blockers) if blockers else 'none'}` |"
        )
    lines.extend(
        [
            "",
            "Readiness rule: a branch may be the best observed end-to-end lane, but it is not live-promotion ready until hard-case stress evidence is evaluated and passing.",
            "",
        ]
    )
    return "\n".join(lines)


def write_portfolio_bundle(
    *,
    repo_root: Path,
    campaign_id: str,
    summary: dict[str, Any],
) -> dict[str, Path]:
    output_root = ensure_dir(repo_root / "artifacts" / "session" / campaign_id / OUTPUT_KIND)
    summary_path = output_root / "portfolio_summary.json"
    scorecard_path = output_root / "scorecard.md"
    for branch in summary.get("branches", []):
        branch_slug = sanitize_branch_name(str(branch.get("branch_slug") or branch.get("branch_name") or "branch"))
        branch_root = ensure_dir(output_root / branch_slug)
        branch_path = branch_root / "branch_summary.json"
        write_json(branch_path, branch)
    write_json(summary_path, summary)
    scorecard_path.write_text(build_scorecard_markdown(summary), encoding="utf-8")
    return {"output_root": output_root, "summary_path": summary_path, "scorecard_path": scorecard_path}


def parse_branch_spec(spec: str) -> tuple[str, Path]:
    if "=" not in spec:
        raise argparse.ArgumentTypeError(f"--branch must be name=path, got {spec!r}")
    name, path_text = spec.split("=", 1)
    name = name.strip()
    path_text = path_text.strip()
    if not name or not path_text:
        raise argparse.ArgumentTypeError(f"--branch must be name=path, got {spec!r}")
    sanitize_branch_name(name)
    return name, Path(path_text)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True, help="Portfolio artifact campaign id.")
    parser.add_argument(
        "--branch",
        action="append",
        required=True,
        type=parse_branch_spec,
        help="Branch spec as name=path/to/gather_mission_repeatability/campaign_run_summary.json. Repeatable.",
    )
    parser.add_argument("--baseline-branch", default="", help="Optional branch name to treat as the comparison baseline.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    campaign_id = str(args.campaign_id or "").strip()
    if not campaign_id:
        raise ValueError("--campaign-id must not be empty")
    branch_specs: list[tuple[str, Path]] = []
    for name, path in args.branch:
        source_path = path if path.is_absolute() else (REPO_ROOT / path)
        branch_specs.append((name, source_path))
    summary = build_portfolio_summary(
        campaign_id=campaign_id,
        branch_specs=branch_specs,
        baseline_branch=str(args.baseline_branch or "").strip() or None,
    )
    paths = write_portfolio_bundle(repo_root=REPO_ROOT, campaign_id=campaign_id, summary=summary)
    print(f"GATHER_CONTROL_PORTFOLIO_SUMMARY={paths['summary_path']}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
