#!/usr/bin/env python3
"""Audit geometric breadth across planner-routed seeded fetch scenes."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
AUDIT_KIND = "fetch_planner_geometry_breadth_audit"
ROUTE_LABELS = (
    "fetch_ready_local",
    "nav2_reposition_first",
    "recovery_or_reaim",
    "local_setup_capture",
    "scan_or_perceive_first",
    "ambiguous_or_unsafe_no_go",
)
SETUP_DEBT_FIELDS = (
    "ball_target_distance_m",
    "ball_target_angle_abs_deg",
    "lateral_m",
    "robot_ball_distance_m",
    "yaw_deg",
)
REQUIRED_FLAGS = (
    "bounded_recovery_required",
    "corridor_unusable",
    "initial_lateral_setup_debt",
    "initial_yaw_setup_debt",
    "nav2_reposition_required",
    "perception_refresh_required",
    "target_distance_outside_local_fetch_window",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_path(path_text: str | Path) -> Path:
    path = Path(str(path_text or "").strip())
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def artifact_display_path(path_text: str | Path) -> str:
    resolved = resolve_path(path_text)
    try:
        return str(resolved.relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(resolved)


def read_json(path_text: str | Path) -> tuple[dict[str, Any], list[str]]:
    path = resolve_path(path_text)
    if not path.is_file():
        return {}, [f"missing_json:{artifact_display_path(path)}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # pragma: no cover - defensive artifact parsing
        return {}, [f"invalid_json:{artifact_display_path(path)}:{exc}"]
    if not isinstance(payload, dict):
        return {}, [f"json_not_object:{artifact_display_path(path)}"]
    return payload, []


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def float_value(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def issue_unless(issues: list[str], condition: bool, issue: str) -> None:
    if not condition:
        issues.append(issue)


def add_count(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


def range_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "min": None, "max": None, "span": None, "mean": None}
    return {
        "count": len(values),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "span": round(max(values) - min(values), 6),
        "mean": round(sum(values) / len(values), 6),
    }


def combine_range_summaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ranges = [dict_value(row) for row in rows if int_value(dict_value(row).get("count"))]
    if not ranges:
        return {"count": 0, "min": None, "max": None, "span": None, "mean": None}
    total_count = sum(int_value(row.get("count")) for row in ranges)
    min_value = min(float(row.get("min")) for row in ranges)
    max_value = max(float(row.get("max")) for row in ranges)
    weighted_mean = sum(float(row.get("mean")) * int_value(row.get("count")) for row in ranges) / total_count
    return {
        "count": total_count,
        "min": round(min_value, 6),
        "max": round(max_value, 6),
        "span": round(max_value - min_value, 6),
        "mean": round(weighted_mean, 6),
    }


def extract_planner_path(path_text: str) -> str:
    payload, _ = read_json(path_text)
    if payload.get("type") == "fetch_planner_seeded_generalization_gate" and payload.get("planner_summary_path"):
        return str(payload.get("planner_summary_path"))
    return path_text


def summarize_gate(path_text: str) -> dict[str, Any]:
    planner_path = extract_planner_path(path_text)
    gate, issues = read_json(planner_path)
    rows = [dict_value(row) for row in list_value(gate.get("results")) if isinstance(row, dict)]
    route_counts: dict[str, int] = {}
    flag_counts: dict[str, int] = {}
    field_values: dict[str, list[float]] = {field: [] for field in SETUP_DEBT_FIELDS}
    for row in rows:
        add_count(route_counts, str(row.get("route_label", "") or ""))
        route_quality = dict_value(row.get("route_quality"))
        setup_debt = dict_value(route_quality.get("setup_debt"))
        for field in SETUP_DEBT_FIELDS:
            value = float_value(setup_debt.get(field))
            if value is not None:
                field_values[field].append(value)
        for flag in list_value(route_quality.get("flags")):
            add_count(flag_counts, str(flag))
    return {
        "path": artifact_display_path(planner_path),
        "seed": gate.get("seed"),
        "pass": bool(gate.get("pass", False)) and not issues,
        "issues": issues if bool(gate.get("pass", False)) else [*issues, "planner_gate_not_pass"],
        "scene_count": len(rows),
        "route_counts": route_counts,
        "flag_counts": flag_counts,
        "ranges": {field: range_summary(values) for field, values in field_values.items()},
        "provider_status_counts": dict_value(gate.get("provider_status_counts")),
        "planner_mode_effective_counts": dict_value(gate.get("planner_mode_effective_counts")),
        "scorecard_path": str(gate.get("scorecard_path", "") or ""),
    }


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    gate_rows = [summarize_gate(path) for path in list_value(args.gate_summary)]
    issues: list[str] = []
    if not gate_rows:
        issues.append("gate_summaries_missing")
    route_counts: dict[str, int] = {}
    flag_counts: dict[str, int] = {}
    range_rows: dict[str, list[dict[str, Any]]] = {field: [] for field in SETUP_DEBT_FIELDS}
    provider_counts: dict[str, int] = {}
    mode_counts: dict[str, int] = {}
    for row in gate_rows:
        for issue in list_value(row.get("issues")):
            issues.append(f"seed{row.get('seed')}:{issue}")
        for key, count in dict_value(row.get("route_counts")).items():
            route_counts[key] = route_counts.get(key, 0) + int_value(count)
        for key, count in dict_value(row.get("flag_counts")).items():
            flag_counts[key] = flag_counts.get(key, 0) + int_value(count)
        for key, count in dict_value(row.get("provider_status_counts")).items():
            provider_counts[key] = provider_counts.get(key, 0) + int_value(count)
        for key, count in dict_value(row.get("planner_mode_effective_counts")).items():
            mode_counts[key] = mode_counts.get(key, 0) + int_value(count)
        for field, range_row in dict_value(row.get("ranges")).items():
            range_rows.setdefault(field, []).append(dict_value(range_row))
    total_scenes = sum(int_value(row.get("scene_count")) for row in gate_rows)
    ranges = {field: combine_range_summaries(rows) for field, rows in range_rows.items()}
    issue_unless(issues, total_scenes >= int(args.min_scenes), f"scene_count_below_{int(args.min_scenes)}")
    for route in ROUTE_LABELS:
        issue_unless(issues, route_counts.get(route, 0) > 0, f"missing_route_family:{route}")
    for flag in REQUIRED_FLAGS:
        issue_unless(issues, flag_counts.get(flag, 0) > 0, f"missing_setup_flag:{flag}")
    min_spans = {
        "ball_target_distance_m": float(args.min_ball_target_distance_span_m),
        "ball_target_angle_abs_deg": float(args.min_ball_target_angle_span_deg),
        "lateral_m": float(args.min_lateral_span_m),
        "robot_ball_distance_m": float(args.min_robot_ball_distance_span_m),
        "yaw_deg": float(args.min_yaw_span_deg),
    }
    for field, min_span in min_spans.items():
        span = dict_value(ranges.get(field)).get("span")
        issue_unless(issues, span is not None and float(span) >= min_span, f"{field}_span_below_{min_span}")
    return {
        "generated_utc": utc_now(),
        "type": AUDIT_KIND,
        "campaign_id": str(args.campaign_id),
        "pass": not issues,
        "promotion_evidence": False,
        "hardware_proven": False,
        "provider_backed_authority_ready": provider_counts.get("ok", 0) == total_scenes and total_scenes > 0,
        "milestone_interpretation": (
            "planner_geometry_breadth_green" if not issues else "planner_geometry_breadth_incomplete"
        ),
        "issues": issues,
        "gate_count": len(gate_rows),
        "seeds": [row.get("seed") for row in gate_rows],
        "scene_count": total_scenes,
        "route_counts": route_counts,
        "flag_counts": flag_counts,
        "ranges": ranges,
        "provider_status_counts": provider_counts,
        "planner_mode_effective_counts": mode_counts,
        "minimum_spans": min_spans,
        "claim_boundaries": [
            "geometry_breadth_not_promotion_evidence",
            "provider_backed_authority_false_until_provider_ok_rerun",
            "hardware_proven_false_until_physical_onboard_evidence",
        ],
        "gates": gate_rows,
    }


def artifact_link(path_text: str) -> str:
    text = str(path_text or "").replace("\\", "/")
    return f"[artifact](/{text})" if text.startswith("artifacts/") else text


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Fetch Planner Geometry Breadth Audit",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        f"- scene_count: `{summary.get('scene_count', 0)}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- provider_backed_authority_ready: `{summary.get('provider_backed_authority_ready', False)}`",
        f"- hardware_proven: `{summary.get('hardware_proven', False)}`",
        f"- issues: `{summary.get('issues', [])}`",
        "",
        "## Geometry Ranges",
        "",
    ]
    for field, row in dict_value(summary.get("ranges")).items():
        lines.append(f"- `{field}`: `{row}`")
    lines.extend(["", "## Route And Flag Coverage", ""])
    lines.append(f"- route_counts: `{summary.get('route_counts', {})}`")
    lines.append(f"- flag_counts: `{summary.get('flag_counts', {})}`")
    lines.extend(["", "## Claim Boundaries", ""])
    for boundary in list_value(summary.get("claim_boundaries")):
        lines.append(f"- `{boundary}`")
    lines.extend(["", "## Gates", ""])
    for row in list_value(summary.get("gates")):
        lines.append(
            f"- seed `{row.get('seed', '')}` scenes=`{row.get('scene_count', 0)}` "
            f"pass=`{row.get('pass', False)}` {artifact_link(str(row.get('scorecard_path', '') or row.get('path', '')))}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit geometry breadth across seeded planner gates.")
    parser.add_argument("--campaign-id", default=f"fetch_planner_geometry_breadth_audit_{current_utc_stamp()}")
    parser.add_argument("--gate-summary", action="append", default=[])
    parser.add_argument("--min-scenes", type=int, default=300)
    parser.add_argument("--min-ball-target-distance-span-m", type=float, default=1.0)
    parser.add_argument("--min-ball-target-angle-span-deg", type=float, default=30.0)
    parser.add_argument("--min-lateral-span-m", type=float, default=0.15)
    parser.add_argument("--min-robot-ball-distance-span-m", type=float, default=0.8)
    parser.add_argument("--min-yaw-span-deg", type=float, default=20.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / AUDIT_KIND)
    summary = build_summary(args)
    summary_path = root / "geometry_breadth_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["summary_path"] = artifact_display_path(summary_path)
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_PLANNER_GEOMETRY_BREADTH_AUDIT_SUMMARY={summary_path}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
