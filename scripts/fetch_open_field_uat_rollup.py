#!/usr/bin/env python3
"""Roll up open-field planner-routed fetch UAT evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
ROLLUP_KIND = "fetch_open_field_uat_rollup"
PINNED_OPPOSITE_FAILURE_SCENE_ID = "opbehind_nav2_opposite_circle_left_07"


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
    path = resolve_path(path_text)
    try:
        return str(path.relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def read_json(path_text: str | Path) -> dict[str, Any]:
    path = resolve_path(path_text)
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def strict_row_success(row: dict[str, Any]) -> bool:
    mission = dict_value(row.get("mission"))
    visual = dict_value(row.get("visual_package"))
    if bool(row.get("planner_only_route", False)):
        return False
    if not bool(mission.get("fetch_to_pose_pass", False)):
        return False
    if bool(mission.get("measured_push_ready_handoff_required", False)) and not bool(
        mission.get("measured_push_ready_handoff_pass", False)
    ):
        return False
    return bool(visual.get("pass", False))


def layout_for_row(row: dict[str, Any]) -> dict[str, Any]:
    layout_path = str(row.get("layout_path", "") or "")
    return read_json(layout_path) if layout_path else {}


def row_geometry(row: dict[str, Any], layout: dict[str, Any]) -> dict[str, Any]:
    random_draw = dict_value(layout.get("random_draw"))
    planner_scene = dict_value(layout.get("planner_scene"))
    scene_geometry = dict_value(planner_scene.get("geometry"))
    geometry = dict(random_draw)
    geometry.update({k: v for k, v in scene_geometry.items() if k not in geometry})
    return {
        "opposite_side_of_circle": bool(geometry.get("opposite_side_of_circle", False)),
        "ball_target_angle_deg": geometry.get("ball_target_angle_deg"),
        "ball_target_distance_m": geometry.get("ball_target_distance_m"),
        "robot_ball_distance_m": geometry.get("robot_ball_distance_m"),
        "robot_ball_relative_bearing_abs_deg": geometry.get("robot_ball_relative_bearing_abs_deg"),
        "robot_lateral_error_m": geometry.get("robot_lateral_error_m"),
        "robot_yaw_error_deg": geometry.get("robot_yaw_error_deg"),
    }


def classify_scene(scene_id: str, route_label: str, geometry: dict[str, Any]) -> str:
    if bool(geometry.get("opposite_side_of_circle", False)):
        return "opposite_side"
    text = f"{scene_id} {route_label}".lower()
    if "fetch_ready" in text:
        return "fetch_ready"
    if "recovery" in text:
        return "recovery_reaim"
    if "behind" in text:
        return "behind_ball"
    if "wraparound" in text:
        return "wraparound"
    if "wide" in text:
        return "wide_angle"
    return route_label or "unknown"


def best_rows_by_scene(batch_summaries: list[Path]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    best: dict[str, dict[str, Any]] = {}
    attempts: list[dict[str, Any]] = []
    for batch_path in batch_summaries:
        batch = read_json(batch_path)
        for row in list_value(batch.get("rows")):
            if not isinstance(row, dict):
                continue
            scene_id = str(row.get("scene_id", "") or "")
            if not scene_id:
                continue
            enriched = dict(row)
            enriched["batch_summary_path"] = artifact_display_path(batch_path)
            enriched["strict_success"] = strict_row_success(row)
            layout = layout_for_row(row)
            geometry = row_geometry(row, layout)
            enriched["geometry"] = geometry
            enriched["scene_class"] = classify_scene(scene_id, str(row.get("route_label", "") or ""), geometry)
            attempts.append(enriched)
            previous = best.get(scene_id)
            if previous is None:
                best[scene_id] = enriched
                continue
            if bool(enriched.get("strict_success", False)) and not bool(previous.get("strict_success", False)):
                best[scene_id] = enriched
            elif bool(enriched.get("strict_success", False)) == bool(previous.get("strict_success", False)):
                best[scene_id] = enriched
    return best, attempts


def summarize_rollup(args: argparse.Namespace) -> dict[str, Any]:
    batch_paths = [resolve_path(path) for path in args.batch_summary]
    best, attempts = best_rows_by_scene(batch_paths)
    successes = [row for row in best.values() if bool(row.get("strict_success", False))]
    failures = [row for row in best.values() if not bool(row.get("strict_success", False))]
    opposite_successes = [row for row in successes if bool(dict_value(row.get("geometry")).get("opposite_side_of_circle", False))]
    pinned_success = any(row.get("scene_id") == PINNED_OPPOSITE_FAILURE_SCENE_ID for row in successes)
    route_counts: dict[str, int] = {}
    class_counts: dict[str, int] = {}
    recovery_count = 0
    for row in successes:
        route = str(row.get("route_label", "") or "")
        scene_class = str(row.get("scene_class", "") or "")
        route_counts[route] = route_counts.get(route, 0) + 1
        class_counts[scene_class] = class_counts.get(scene_class, 0) + 1
        if bool(dict_value(row.get("mission")).get("pre_fetch_local_recovery_applied", False)):
            recovery_count += 1
    issues: list[str] = []
    if len(successes) < int(args.min_successes):
        issues.append("strict_success_count_below_minimum")
    if len(opposite_successes) < int(args.min_opposite_successes):
        issues.append("opposite_success_count_below_minimum")
    if not pinned_success:
        issues.append("pinned_opposite_failure_shape_not_successful")
    if failures:
        issues.append("best_scene_failures_remain")
    summary = {
        "generated_utc": utc_now(),
        "type": ROLLUP_KIND,
        "campaign_id": str(args.campaign_id),
        "batch_summary_paths": [artifact_display_path(path) for path in batch_paths],
        "attempt_count": len(attempts),
        "distinct_scene_count": len(best),
        "strict_success_count": len(successes),
        "strict_failure_count": len(failures),
        "opposite_success_count": len(opposite_successes),
        "pinned_previous_opposite_failure_success": pinned_success,
        "pre_fetch_local_recovery_applied_success_count": recovery_count,
        "route_success_counts": route_counts,
        "scene_class_success_counts": class_counts,
        "min_successes": int(args.min_successes),
        "min_opposite_successes": int(args.min_opposite_successes),
        "pass": not issues,
        "issues": issues,
        "promotion_evidence": False,
        "milestone_interpretation": (
            "open_field_planner_routed_visual_uat_green"
            if not issues
            else "open_field_planner_routed_visual_uat_has_gaps"
        ),
        "successes": [
            {
                "scene_id": row.get("scene_id", ""),
                "scene_class": row.get("scene_class", ""),
                "route_label": row.get("route_label", ""),
                "mission_summary_path": row.get("mission_summary_path", ""),
                "visual_package_summary_path": row.get("visual_package_summary_path", ""),
                "batch_summary_path": row.get("batch_summary_path", ""),
                "closest_approach_distance_m": dict_value(row.get("mission")).get("closest_approach_distance_m"),
                "measured_push_ready_handoff_pass": dict_value(row.get("mission")).get(
                    "measured_push_ready_handoff_pass"
                ),
                "pre_fetch_local_recovery_applied": dict_value(row.get("mission")).get(
                    "pre_fetch_local_recovery_applied"
                ),
                "pre_fetch_local_recovery_reason": dict_value(row.get("mission")).get(
                    "pre_fetch_local_recovery_reason"
                ),
                "geometry": row.get("geometry", {}),
            }
            for row in sorted(successes, key=lambda item: str(item.get("scene_id", "")))
        ],
        "failures": [
            {
                "scene_id": row.get("scene_id", ""),
                "route_label": row.get("route_label", ""),
                "failure_reason": row.get("failure_reason", ""),
                "mission": row.get("mission", {}),
                "batch_summary_path": row.get("batch_summary_path", ""),
            }
            for row in sorted(failures, key=lambda item: str(item.get("scene_id", "")))
        ],
    }
    return summary


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Open-Field Fetch UAT Rollup",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- strict_success_count: `{summary.get('strict_success_count', 0)}`",
        f"- strict_failure_count: `{summary.get('strict_failure_count', 0)}`",
        f"- opposite_success_count: `{summary.get('opposite_success_count', 0)}`",
        f"- pinned_previous_opposite_failure_success: `{summary.get('pinned_previous_opposite_failure_success', False)}`",
        f"- pre_fetch_local_recovery_applied_success_count: `{summary.get('pre_fetch_local_recovery_applied_success_count', 0)}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        f"- issues: `{summary.get('issues', [])}`",
        "",
        "## Successes",
    ]
    for row in list_value(summary.get("successes")):
        mission_path = str(row.get("mission_summary_path", "") or "")
        visual_path = str(row.get("visual_package_summary_path", "") or "")
        mission_link = f" [mission](/" + mission_path + ")" if mission_path.startswith("artifacts/session/") else ""
        visual_link = f" [visual](/" + visual_path + ")" if visual_path.startswith("artifacts/session/") else ""
        lines.append(
            f"- `{row.get('scene_id', '')}` class=`{row.get('scene_class', '')}` route=`{row.get('route_label', '')}` "
            f"closest=`{row.get('closest_approach_distance_m', '')}` "
            f"push_ready=`{row.get('measured_push_ready_handoff_pass', False)}` "
            f"local_recovery=`{row.get('pre_fetch_local_recovery_applied', False)}`"
            f"{mission_link}{visual_link}"
        )
    lines.extend(["", "## Failures"])
    for row in list_value(summary.get("failures")):
        lines.append(
            f"- `{row.get('scene_id', '')}` route=`{row.get('route_label', '')}` failure=`{row.get('failure_reason', '')}`"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Roll up open-field route replay visual UAT evidence.")
    parser.add_argument("--campaign-id", default=f"open_field_fetch_uat_rollup_{current_utc_stamp()}")
    parser.add_argument("--batch-summary", action="append", required=True)
    parser.add_argument("--min-successes", type=int, default=6)
    parser.add_argument("--min-opposite-successes", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / ROLLUP_KIND)
    summary = summarize_rollup(args)
    summary["summary_path"] = artifact_display_path(root / "open_field_uat_summary.json")
    summary["scorecard_path"] = artifact_display_path(root / "scorecard.md")
    write_json(root / "open_field_uat_summary.json", summary)
    write_scorecard(root / "scorecard.md", summary)
    print(f"FETCH_OPEN_FIELD_UAT_ROLLUP_SUMMARY={root / 'open_field_uat_summary.json'}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
