"""Helpers for comparing one-ball corral behavior across surface profiles."""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from typing import Any


DEFAULT_BASELINE_WORLD_FILE = "yolo_test_world_v6_clean_uat.world"
DEFAULT_SHORT_TURF_WORLD_FILE = "yolo_test_world_v6_clean_uat_short_turf.world"
DEFAULT_SHORT_GRASS_WORLD_FILE = "yolo_test_world_v6_clean_uat_short_grass.world"


@dataclass(frozen=True)
class SurfaceCalibrationLane:
    surface_profile: str
    world_file: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_surface_calibration_lanes() -> list[SurfaceCalibrationLane]:
    return [
        SurfaceCalibrationLane(surface_profile="baseline", world_file=DEFAULT_BASELINE_WORLD_FILE),
        SurfaceCalibrationLane(surface_profile="short_turf", world_file=DEFAULT_SHORT_TURF_WORLD_FILE),
        SurfaceCalibrationLane(surface_profile="short_grass", world_file=DEFAULT_SHORT_GRASS_WORLD_FILE),
    ]


def _round_average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 6)


def summarize_surface_lane(*, lane: SurfaceCalibrationLane, runs: list[dict[str, Any]]) -> dict[str, Any]:
    settled_runs = [item for item in runs if bool(item.get("settled_in_corral_pass", False))]
    settle_distances = [
        float(item.get("final_settle_distance_m", 0.0) or 0.0)
        for item in settled_runs
        if item.get("final_settle_distance_m") not in {None, ""}
    ]
    overshoot_distances = [
        float(item.get("max_overshoot_distance_m", 0.0) or 0.0)
        for item in runs
        if item.get("max_overshoot_distance_m") not in {None, ""}
    ]
    settle_times = [
        float(item.get("settle_time_s", 0.0) or 0.0)
        for item in settled_runs
        if item.get("settle_time_s") not in {None, ""}
    ]
    release_recontacts = [int(item.get("release_recontact_count", 0) or 0) for item in runs]
    mission_times = [
        float(item.get("mission_time_s", 0.0) or 0.0)
        for item in settled_runs
        if item.get("mission_time_s") not in {None, ""}
    ]
    settled_pass_count = sum(1 for item in runs if bool(item.get("settled_in_corral_pass", False)))
    return {
        "surface_profile": lane.surface_profile,
        "world_file": lane.world_file,
        "runs": len(runs),
        "settled_in_corral_pass_count": settled_pass_count,
        "avg_final_settle_distance_m": _round_average(settle_distances),
        "avg_max_overshoot_distance_m": _round_average(overshoot_distances),
        "avg_settle_time_s": _round_average(settle_times),
        "avg_release_recontact_count": _round_average([float(value) for value in release_recontacts]),
        "avg_mission_time_s": _round_average(mission_times),
        "all_runs_settled_pass": bool(runs) and settled_pass_count == len(runs),
    }


def compute_ordering_checks(lane_summaries: list[dict[str, Any]]) -> dict[str, bool]:
    by_profile = {str(item.get("surface_profile", "") or ""): item for item in lane_summaries}
    baseline = by_profile.get("baseline")
    short_turf = by_profile.get("short_turf")
    short_grass = by_profile.get("short_grass")
    required = [baseline, short_turf, short_grass]
    if any(item is None for item in required):
        return {
            "settle_distance_order_ok": False,
            "overshoot_order_ok": False,
            "settle_time_order_ok": False,
        }

    def _has_settled_stats(item: dict[str, Any]) -> bool:
        return int(item.get("settled_in_corral_pass_count", 0) or 0) > 0

    settle_distance_order_ok = all(_has_settled_stats(item) for item in required) and (
        float(short_grass.get("avg_final_settle_distance_m", 0.0) or 0.0)
        <= float(short_turf.get("avg_final_settle_distance_m", 0.0) or 0.0)
        <= float(baseline.get("avg_final_settle_distance_m", 0.0) or 0.0)
    )
    settle_time_order_ok = all(_has_settled_stats(item) for item in required) and (
        float(short_grass.get("avg_settle_time_s", 0.0) or 0.0)
        <= float(short_turf.get("avg_settle_time_s", 0.0) or 0.0)
        <= float(baseline.get("avg_settle_time_s", 0.0) or 0.0)
    )
    overshoot_order_ok = (
        float(short_grass.get("avg_max_overshoot_distance_m", 0.0) or 0.0)
        <= float(short_turf.get("avg_max_overshoot_distance_m", 0.0) or 0.0)
        <= float(baseline.get("avg_max_overshoot_distance_m", 0.0) or 0.0)
    )
    return {
        "settle_distance_order_ok": bool(settle_distance_order_ok),
        "overshoot_order_ok": bool(overshoot_order_ok),
        "settle_time_order_ok": bool(settle_time_order_ok),
    }


def choose_canonical_surface_profile(
    lane_summaries: list[dict[str, Any]],
    ordering_checks: dict[str, bool],
    *,
    preferred_surface_profile: str = "short_turf",
) -> str:
    by_profile = {str(item.get("surface_profile", "") or ""): item for item in lane_summaries}
    preferred = by_profile.get(preferred_surface_profile)
    if preferred and bool(preferred.get("all_runs_settled_pass", False)) and all(bool(ordering_checks.get(key, False)) for key in ordering_checks):
        return preferred_surface_profile
    fallback = by_profile.get("short_grass")
    if fallback and bool(fallback.get("all_runs_settled_pass", False)):
        return "short_grass"
    return ""


def summarize_surface_calibration(
    *,
    lane_summaries: list[dict[str, Any]],
    preferred_surface_profile: str = "short_turf",
) -> dict[str, Any]:
    ordering_checks = compute_ordering_checks(lane_summaries)
    canonical_surface_profile = choose_canonical_surface_profile(
        lane_summaries,
        ordering_checks,
        preferred_surface_profile=preferred_surface_profile,
    )
    return {
        "lane_summaries": lane_summaries,
        **ordering_checks,
        "canonical_surface_profile": canonical_surface_profile,
    }


def build_surface_calibration_scorecard_markdown(
    *,
    summary: dict[str, Any],
    lane_results: list[dict[str, Any]],
) -> str:
    lines = [
        "# Corral Surface Calibration Scorecard",
        "",
        f"- Canonical surface profile: `{str(summary.get('canonical_surface_profile', '') or 'unresolved')}`",
        f"- Settle distance ordering: `{bool(summary.get('settle_distance_order_ok', False))}`",
        f"- Overshoot ordering: `{bool(summary.get('overshoot_order_ok', False))}`",
        f"- Settle time ordering: `{bool(summary.get('settle_time_order_ok', False))}`",
        "",
        "## Lanes",
        "",
    ]
    for item in lane_results:
        lines.append(
            f"- `{str(item.get('surface_profile', '') or 'unspecified')}` "
            f"world=`{str(item.get('world_file', '') or 'unspecified')}` "
            f"settled_passes=`{int(item.get('settled_in_corral_pass_count', 0) or 0)}/{int(item.get('runs', 0) or 0)}` "
            f"avg_settle=`{float(item.get('avg_final_settle_distance_m', 0.0) or 0.0):.3f}m` "
            f"avg_overshoot=`{float(item.get('avg_max_overshoot_distance_m', 0.0) or 0.0):.3f}m` "
            f"avg_settle_time=`{float(item.get('avg_settle_time_s', 0.0) or 0.0):.3f}s` "
            f"avg_recontacts=`{float(item.get('avg_release_recontact_count', 0.0) or 0.0):.3f}` "
            f"avg_mission_time=`{float(item.get('avg_mission_time_s', 0.0) or 0.0):.3f}s` "
            f"repeatability=`{str(item.get('repeatability_summary_path', '') or 'n/a')}`"
        )
    lines.append("")
    return "\n".join(lines)
