#!/usr/bin/env python3
"""Offline screen for a contact-aware geometric shooter fetch architecture."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

from llm_supervisor_core import ensure_dir
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
OUTPUT_KIND = "fetch_geometric_shooter_screen"
DEFAULT_BASELINE_GATE_SUMMARY = (
    REPO_ROOT
    / "artifacts"
    / "session"
    / "live_calibrated_golf_fetch_uat_readiness_rerun_20260527"
    / "calibrated_golf_fetch_gate"
    / "gate_summary.json"
)
DEFAULT_DECEL_MPS2 = 0.72
DEFAULT_MAX_SHOT_SPEED_MPS = 1.0
DEFAULT_MIN_AIM_HALF_ANGLE_DEG = 5.0


def make_session_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


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


def _round_number(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "pass", "passed"}:
            return True
        if normalized in {"false", "0", "no", "fail", "failed"}:
            return False
    return None


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return payload


def _load_jsonl(path: Path) -> tuple[str, list[dict[str, Any]]]:
    if not path.exists():
        return "missing", []
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return "invalid_jsonl", rows
        if isinstance(payload, dict):
            rows.append(payload)
    return "ok", rows


def _repo_artifact_fallback(path: Path) -> Path | None:
    parts = path.parts
    for index, part in enumerate(parts):
        if part == "artifacts" and index + 1 < len(parts):
            return REPO_ROOT / Path(*parts[index:])
    return None


def _resolve_path(raw_path: Any, *, source_summary_path: Path) -> Path | None:
    text = str(raw_path or "").strip()
    if not text:
        return None
    path = Path(text)
    if path.is_absolute():
        if not path.exists():
            fallback = _repo_artifact_fallback(path)
            if fallback is not None and fallback.exists():
                return fallback
        return path
    repo_path = REPO_ROOT / path
    if repo_path.exists():
        return repo_path
    return source_summary_path.parent / path


def _pose_xy(value: Any) -> dict[str, float] | None:
    payload = _dict_value(value)
    position = _dict_value(payload.get("position")) or payload
    x = _finite_float(position.get("x"))
    y = _finite_float(position.get("y"))
    if x is None or y is None:
        return None
    z = _finite_float(position.get("z"))
    return {"x": x, "y": y, "z": z if z is not None else 0.0}


def _distance_xy(a: dict[str, Any], b: dict[str, Any]) -> float | None:
    ax = _finite_float(a.get("x"))
    ay = _finite_float(a.get("y"))
    bx = _finite_float(b.get("x"))
    by = _finite_float(b.get("y"))
    if ax is None or ay is None or bx is None or by is None:
        return None
    return math.hypot(bx - ax, by - ay)


def required_speed_for_roll_distance(distance_m: float, decel_mps2: float) -> float:
    distance = max(0.0, float(distance_m))
    decel = float(decel_mps2)
    if decel <= 0.0:
        raise ValueError("decel_mps2 must be positive")
    return math.sqrt(2.0 * decel * distance)


def stop_distance_for_speed(speed_mps: float, decel_mps2: float) -> float:
    speed = max(0.0, float(speed_mps))
    decel = float(decel_mps2)
    if decel <= 0.0:
        raise ValueError("decel_mps2 must be positive")
    return speed * speed / (2.0 * decel)


def build_geometric_shot_model(
    *,
    ball_start_pose: dict[str, Any],
    fetch_pose_world: dict[str, Any],
    decel_mps2: float,
    max_shot_speed_mps: float,
    min_aim_half_angle_deg: float = DEFAULT_MIN_AIM_HALF_ANGLE_DEG,
) -> dict[str, Any]:
    radius = max(0.0, _finite_float(fetch_pose_world.get("radius_m")) or 0.0)
    distance = _distance_xy(ball_start_pose, fetch_pose_world)
    if distance is None:
        return {
            "observed": False,
            "offline_pass": False,
            "reason": "missing_ball_or_target_pose",
        }
    entry_distance = max(0.0, distance - radius)
    exit_distance = distance + radius
    entry_speed = required_speed_for_roll_distance(entry_distance, decel_mps2)
    center_speed = required_speed_for_roll_distance(distance, decel_mps2)
    far_edge_speed = required_speed_for_roll_distance(exit_distance, decel_mps2)
    max_stop_distance = stop_distance_for_speed(max_shot_speed_mps, decel_mps2)
    if distance <= radius:
        aim_half_angle = 180.0
    else:
        aim_half_angle = math.degrees(math.asin(min(1.0, radius / max(distance, 1e-9))))
    entry_speed_margin = float(max_shot_speed_mps) - entry_speed
    center_speed_margin = float(max_shot_speed_mps) - center_speed
    speed_window_width = far_edge_speed - entry_speed
    offline_pass = bool(entry_speed_margin >= 0.0 and aim_half_angle >= float(min_aim_half_angle_deg))
    return {
        "observed": True,
        "offline_pass": offline_pass,
        "reason": "speed_and_aim_window_available" if offline_pass else "speed_or_aim_window_blocked",
        "ball_to_target_distance_m": round(distance, 6),
        "delivery_radius_m": round(radius, 6),
        "entry_distance_m": round(entry_distance, 6),
        "target_center_distance_m": round(distance, 6),
        "far_edge_distance_m": round(exit_distance, 6),
        "required_entry_speed_mps": round(entry_speed, 6),
        "required_target_center_speed_mps": round(center_speed, 6),
        "required_far_edge_speed_mps": round(far_edge_speed, 6),
        "max_shot_speed_mps": round(float(max_shot_speed_mps), 6),
        "max_shot_stop_distance_m": round(max_stop_distance, 6),
        "entry_speed_margin_mps": round(entry_speed_margin, 6),
        "target_center_speed_margin_mps": round(center_speed_margin, 6),
        "speed_window_width_mps": round(speed_window_width, 6),
        "aim_half_angle_deg": round(aim_half_angle, 6),
        "center_stop_possible_with_cap": bool(center_speed_margin >= 0.0),
        "full_cap_stops_before_far_edge": bool(max_stop_distance <= exit_distance + 1e-9),
        "decel_mps2": round(float(decel_mps2), 6),
        "min_aim_half_angle_deg": round(float(min_aim_half_angle_deg), 6),
    }


def _case_id_from_gate(gate_id: str, label: str = "") -> str:
    text = f"{gate_id} {label}".lower()
    if "left05" in text:
        return "left05"
    if "right05" in text:
        return "right05"
    if "zero" in text or "centerline" in text:
        return "centerline"
    return "unknown_layout"


def _mission_root_path(run: dict[str, Any], *, source_summary_path: Path) -> Path | None:
    explicit = _resolve_path(run.get("mission_root"), source_summary_path=source_summary_path)
    if explicit is not None:
        return explicit
    verdict_path = _resolve_path(run.get("mission_verdict_path"), source_summary_path=source_summary_path)
    if verdict_path is not None:
        return verdict_path.parent
    target_results_path = _resolve_path(run.get("target_results_path"), source_summary_path=source_summary_path)
    if target_results_path is not None:
        return target_results_path.parent
    return None


def _mission_verdict(run: dict[str, Any], mission_root: Path | None, *, source_summary_path: Path) -> dict[str, Any]:
    inline = _dict_value(run.get("mission_verdict") or run.get("summary"))
    if inline:
        return inline
    explicit = _resolve_path(run.get("mission_verdict_path"), source_summary_path=source_summary_path)
    candidates = [explicit] if explicit is not None else []
    if mission_root is not None:
        candidates.append(mission_root / "mission_verdict.json")
    for path in candidates:
        if path is not None and path.exists():
            return _load_json_object(path)
    return {}


def _shot_outcome(run: dict[str, Any], verdict: dict[str, Any]) -> dict[str, Any]:
    shot = _dict_value(run.get("shot_outcome"))
    if shot:
        return shot
    return _dict_value(verdict.get("shot_outcome"))


def _path_status(path: Path | None) -> tuple[str, str]:
    if path is None:
        return "", "not_referenced"
    return str(path), "ok" if path.exists() else "missing"


def _trace_sample_from_ball_row(row: dict[str, Any], fallback_t: float) -> dict[str, Any] | None:
    pose = _pose_xy(row.get("position"))
    if pose is None:
        return None
    t_s = _finite_float(row.get("t_s"))
    return {"t_s": t_s if t_s is not None else fallback_t, "position": pose}


def _trace_sample_from_state_row(row: dict[str, Any], fallback_t: float) -> dict[str, Any] | None:
    pose = _pose_xy(row.get("ball_pose"))
    if pose is None:
        return None
    fetch = _dict_value(row.get("fetch_to_pose"))
    t_s = _finite_float(fetch.get("elapsed_s"))
    if t_s is None:
        t_s = _finite_float(row.get("t_s"))
    return {"t_s": t_s if t_s is not None else fallback_t, "position": pose}


def _load_ball_trajectory(mission_root: Path | None) -> dict[str, Any]:
    if mission_root is None:
        return {
            "trace_source": "missing",
            "trace_status": "not_referenced",
            "trace_path": "",
            "samples": [],
        }
    ball_trace_path = mission_root / "ball_trace.jsonl"
    ball_status, ball_rows = _load_jsonl(ball_trace_path)
    if ball_status == "ok":
        samples = [
            sample
            for index, row in enumerate(ball_rows)
            if (sample := _trace_sample_from_ball_row(row, float(index))) is not None
        ]
        return {
            "trace_source": "ball_trace",
            "trace_status": "ok",
            "trace_path": str(ball_trace_path),
            "samples": samples,
        }
    state_history_path = mission_root / "state_history.jsonl"
    state_status, state_rows = _load_jsonl(state_history_path)
    if state_status == "ok":
        fetch_rows = [
            row
            for row in state_rows
            if str(row.get("phase", "") or "") == "fetch_to_pose"
            or str(row.get("event_type", "") or "").startswith("fetch_to_pose")
        ]
        samples = [
            sample
            for index, row in enumerate(fetch_rows)
            if (sample := _trace_sample_from_state_row(row, float(index))) is not None
        ]
        return {
            "trace_source": "state_history_fetch_to_pose",
            "trace_status": "ok" if samples else "missing_fetch_samples",
            "trace_path": str(state_history_path),
            "samples": samples,
        }
    return {
        "trace_source": "missing",
        "trace_status": ball_status if ball_status != "missing" else state_status,
        "trace_path": str(ball_trace_path if ball_status != "missing" else state_history_path),
        "samples": [],
    }


def _peak_planar_speed(samples: list[dict[str, Any]]) -> float | None:
    peak = 0.0
    observed = False
    previous: dict[str, Any] | None = None
    for sample in samples:
        if previous is None:
            previous = sample
            continue
        prev_pose = _dict_value(previous.get("position"))
        pose = _dict_value(sample.get("position"))
        dt = (_finite_float(sample.get("t_s")) or 0.0) - (_finite_float(previous.get("t_s")) or 0.0)
        if dt <= 0.0:
            previous = sample
            continue
        distance = _distance_xy(prev_pose, pose)
        if distance is not None:
            observed = True
            peak = max(peak, distance / dt)
        previous = sample
    return peak if observed else None


def _trajectory_displacement(samples: list[dict[str, Any]]) -> float | None:
    if len(samples) < 2:
        return None
    start = _dict_value(samples[0].get("position"))
    end = _dict_value(samples[-1].get("position"))
    return _distance_xy(start, end)


def _approach_evidence(run: dict[str, Any], mission_root: Path | None) -> dict[str, Any]:
    metrics_path = mission_root / "approach_metrics.json" if mission_root is not None else None
    path_text, status = _path_status(metrics_path)
    if metrics_path is not None and metrics_path.exists():
        metrics = _load_json_object(metrics_path)
        flags = [str(item) for item in _list_value(metrics.get("flags"))]
        return {
            "evidence_source": "approach_metrics",
            "approach_metrics_path": path_text,
            "approach_metrics_status": status,
            "stable_contact_approach_pass": bool(metrics.get("stable_contact_approach_pass", False)),
            "flags": flags,
            "first_contact_robot_yaw_error_deg": _round_number(
                _finite_float(metrics.get("first_contact_robot_yaw_error_deg"))
            ),
            "max_abs_robot_lateral_error_pre_contact_m": _round_number(
                _finite_float(metrics.get("max_abs_robot_lateral_error_pre_contact_m"))
            ),
            "robot_yaw_error_sign_changes_pre_contact": int(
                _finite_float(metrics.get("robot_yaw_error_sign_changes_pre_contact")) or 0
            ),
            "max_abs_ball_lateral_error_m": _round_number(_finite_float(metrics.get("max_abs_ball_lateral_error_m"))),
        }
    latest = _dict_value(run.get("latest_approach_progress"))
    capture_entry = _dict_value(latest.get("capture_entry"))
    alignment = _finite_float(
        run.get("first_contact_push_alignment_deg") or capture_entry.get("first_contact_push_alignment_deg")
    )
    pass_value = _boolish(capture_entry.get("pass"))
    if pass_value is None:
        pass_value = _boolish(run.get("pre_stage_handoff_pass"))
    flags: list[str] = []
    if alignment is not None and abs(alignment) > 15.0:
        flags.append("summary_first_contact_alignment_high")
    return {
        "evidence_source": "summary_only",
        "approach_metrics_path": path_text,
        "approach_metrics_status": status,
        "stable_contact_approach_pass": bool(pass_value) and not flags,
        "flags": flags,
        "first_contact_robot_yaw_error_deg": _round_number(alignment),
        "max_abs_robot_lateral_error_pre_contact_m": None,
        "robot_yaw_error_sign_changes_pre_contact": None,
        "max_abs_ball_lateral_error_m": None,
    }


def _fetch_pose_world(shot_outcome: dict[str, Any], gate_summary: dict[str, Any]) -> dict[str, Any]:
    shot_pose = _dict_value(shot_outcome.get("fetch_pose_world"))
    if shot_pose:
        return shot_pose
    return _dict_value(gate_summary.get("fetch_pose_world"))


def _extract_run_evidence(
    *,
    gate_id: str,
    gate_label: str,
    run_index: int,
    run: dict[str, Any],
    source_summary_path: Path,
    gate_summary: dict[str, Any],
    decel_mps2: float,
    max_shot_speed_mps: float,
    min_aim_half_angle_deg: float,
) -> dict[str, Any]:
    mission_root = _mission_root_path(run, source_summary_path=source_summary_path)
    verdict = _mission_verdict(run, mission_root, source_summary_path=source_summary_path)
    shot = _shot_outcome(run, verdict)
    fetch_pose = _fetch_pose_world(shot, gate_summary)
    ball_start = _pose_xy(shot.get("ball_start_pose"))
    trace = _load_ball_trajectory(mission_root)
    samples = _list_value(trace.get("samples"))
    if ball_start is None and samples:
        ball_start = _pose_xy(_dict_value(samples[0]).get("position"))
    geometric_model = build_geometric_shot_model(
        ball_start_pose=ball_start or {},
        fetch_pose_world=fetch_pose,
        decel_mps2=decel_mps2,
        max_shot_speed_mps=max_shot_speed_mps,
        min_aim_half_angle_deg=min_aim_half_angle_deg,
    )
    mission_completed_pass = _boolish(run.get("mission_completed_pass", verdict.get("mission_completed_pass")))
    fetch_to_pose_pass = _boolish(run.get("fetch_to_pose_pass", verdict.get("fetch_to_pose_pass")))
    pass_value = _boolish(run.get("pass", verdict.get("pass")))
    closest = _finite_float(shot.get("closest_approach_distance_m"))
    delivery_radius = _finite_float(shot.get("delivery_radius_m") or fetch_pose.get("radius_m"))
    baseline_delivery_margin = delivery_radius - closest if delivery_radius is not None and closest is not None else None
    peak_speed = _peak_planar_speed(samples)
    displacement = _trajectory_displacement(samples)
    approach = _approach_evidence(run, mission_root)
    verdict_path = _resolve_path(run.get("mission_verdict_path"), source_summary_path=source_summary_path)
    target_results_path = _resolve_path(run.get("target_results_path"), source_summary_path=source_summary_path)
    return {
        "source_gate_id": gate_id,
        "source_label": gate_label,
        "case_id": _case_id_from_gate(gate_id, gate_label),
        "run_index": run_index,
        "mission_root": str(mission_root or ""),
        "mission_verdict_path": str(verdict_path or ""),
        "target_results_path": str(target_results_path or ""),
        "trace_source": str(trace.get("trace_source", "")),
        "trace_status": str(trace.get("trace_status", "")),
        "trace_path": str(trace.get("trace_path", "")),
        "trace_sample_count": len(samples),
        "baseline": {
            "pass": bool(pass_value) if pass_value is not None else False,
            "mission_completed_pass": bool(mission_completed_pass) if mission_completed_pass is not None else False,
            "fetch_to_pose_pass": bool(fetch_to_pose_pass) if fetch_to_pose_pass is not None else False,
            "closest_approach_distance_m": _round_number(closest),
            "delivery_radius_m": _round_number(delivery_radius),
            "delivery_margin_m": _round_number(baseline_delivery_margin),
            "shot_reason": str(shot.get("reason", "") or ""),
            "observed_fetch_ball_displacement_m": _round_number(
                _finite_float(shot.get("fetch_ball_displacement_m")) or displacement
            ),
            "observed_peak_ball_speed_mps": _round_number(peak_speed),
            "fetch_max_commanded_linear_x_mps": _round_number(_finite_float(shot.get("fetch_max_commanded_linear_x_mps"))),
            "fetch_max_target_speed_scale": _round_number(_finite_float(shot.get("fetch_max_target_speed_scale"))),
        },
        "ball_start_pose": ball_start or {},
        "fetch_pose_world": fetch_pose,
        "approach_evidence": approach,
        "geometric_shooter": geometric_model,
    }


def _iter_gate_runs(
    gate_summary: dict[str, Any],
    *,
    gate_summary_path: Path,
    gate_filter: set[str],
    decel_mps2: float,
    max_shot_speed_mps: float,
    min_aim_half_angle_deg: float,
) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for result in _list_value(gate_summary.get("results")):
        gate = _dict_value(result)
        gate_id = str(gate.get("gate_id", "") or "")
        if gate_filter and gate_id not in gate_filter:
            continue
        summary_path = _resolve_path(gate.get("summary_path"), source_summary_path=gate_summary_path)
        if summary_path is None or not summary_path.exists():
            continue
        repeatability = _load_json_object(summary_path)
        gate_label = str(gate.get("label", "") or repeatability.get("scenario_label", "") or gate_id)
        for index, raw_run in enumerate(_list_value(repeatability.get("runs")), start=1):
            run = _dict_value(raw_run)
            runs.append(
                _extract_run_evidence(
                    gate_id=gate_id,
                    gate_label=gate_label,
                    run_index=int(run.get("run_index") or index),
                    run=run,
                    source_summary_path=summary_path,
                    gate_summary=gate_summary,
                    decel_mps2=decel_mps2,
                    max_shot_speed_mps=max_shot_speed_mps,
                    min_aim_half_angle_deg=min_aim_half_angle_deg,
                )
            )
    return runs


def analyze_gate_summary(
    *,
    campaign_id: str,
    baseline_gate_summary_path: Path,
    gate_filter: set[str] | None = None,
    decel_mps2: float = DEFAULT_DECEL_MPS2,
    max_shot_speed_mps: float = DEFAULT_MAX_SHOT_SPEED_MPS,
    min_aim_half_angle_deg: float = DEFAULT_MIN_AIM_HALF_ANGLE_DEG,
) -> dict[str, Any]:
    summary_path = baseline_gate_summary_path if baseline_gate_summary_path.is_absolute() else REPO_ROOT / baseline_gate_summary_path
    gate_summary = _load_json_object(summary_path)
    runs = _iter_gate_runs(
        gate_summary,
        gate_summary_path=summary_path,
        gate_filter=gate_filter or set(),
        decel_mps2=decel_mps2,
        max_shot_speed_mps=max_shot_speed_mps,
        min_aim_half_angle_deg=min_aim_half_angle_deg,
    )
    layout_counts = Counter(str(run.get("case_id", "")) for run in runs)
    pass_count = sum(1 for run in runs if bool(_dict_value(run.get("geometric_shooter")).get("offline_pass", False)))
    baseline_pass_count = sum(
        1
        for run in runs
        if bool(_dict_value(run.get("baseline")).get("mission_completed_pass", False))
        and bool(_dict_value(run.get("baseline")).get("fetch_to_pose_pass", False))
    )
    stable_approach_count = sum(
        1 for run in runs if bool(_dict_value(run.get("approach_evidence")).get("stable_contact_approach_pass", False))
    )
    missing_trace_count = sum(1 for run in runs if str(run.get("trace_status", "")) != "ok")
    required_entry_speeds = [
        float(_dict_value(run.get("geometric_shooter")).get("required_entry_speed_mps"))
        for run in runs
        if _finite_float(_dict_value(run.get("geometric_shooter")).get("required_entry_speed_mps")) is not None
    ]
    target_center_speeds = [
        float(_dict_value(run.get("geometric_shooter")).get("required_target_center_speed_mps"))
        for run in runs
        if _finite_float(_dict_value(run.get("geometric_shooter")).get("required_target_center_speed_mps")) is not None
    ]
    entry_speed_margins = [
        float(_dict_value(run.get("geometric_shooter")).get("entry_speed_margin_mps"))
        for run in runs
        if _finite_float(_dict_value(run.get("geometric_shooter")).get("entry_speed_margin_mps")) is not None
    ]
    aim_half_angles = [
        float(_dict_value(run.get("geometric_shooter")).get("aim_half_angle_deg"))
        for run in runs
        if _finite_float(_dict_value(run.get("geometric_shooter")).get("aim_half_angle_deg")) is not None
    ]
    all_model_passed = bool(runs) and pass_count == len(runs)
    recommendation = "run_canonical_zero_one_run_probe" if all_model_passed else "keep_as_offline_hypothesis"
    return {
        "campaign_id": str(campaign_id),
        "generated_utc": utc_now(),
        "type": OUTPUT_KIND,
        "architecture_family": "contact_aware_geometric_shooter",
        "screen_scope": "offline_shot_model_replay",
        "promotion_status": "offline_only_not_uat",
        "promotion_allowed": False,
        "baseline_gate_summary_path": str(summary_path),
        "baseline_gate_pass": bool(gate_summary.get("pass", False)),
        "surface_profile": str(gate_summary.get("surface_profile", "") or ""),
        "world_file": str(gate_summary.get("world_file", "") or ""),
        "model_assumptions": {
            "linear_decel_mps2": round(float(decel_mps2), 6),
            "max_shot_speed_mps": round(float(max_shot_speed_mps), 6),
            "min_aim_half_angle_deg": round(float(min_aim_half_angle_deg), 6),
            "delivery_intersection_counts_as_success": True,
            "artifact_only": True,
        },
        "run_count": len(runs),
        "baseline_pass_count": baseline_pass_count,
        "stable_approach_count": stable_approach_count,
        "offline_model_pass_count": pass_count,
        "offline_model_fail_count": len(runs) - pass_count,
        "missing_trace_count": missing_trace_count,
        "layout_counts": dict(sorted(layout_counts.items())),
        "max_required_entry_speed_mps": _round_number(max(required_entry_speeds) if required_entry_speeds else None),
        "max_required_target_center_speed_mps": _round_number(max(target_center_speeds) if target_center_speeds else None),
        "min_entry_speed_margin_mps": _round_number(min(entry_speed_margins) if entry_speed_margins else None),
        "min_aim_half_angle_deg": _round_number(min(aim_half_angles) if aim_half_angles else None),
        "recommendation": recommendation,
        "recommended_next_gate": (
            "canonical_zero_one_run_no_retry_probe" if all_model_passed else "fix_or_retire_offline_hypothesis"
        ),
        "runs": runs,
    }


def _markdown_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("|", "\\|")


def render_scorecard(summary: dict[str, Any]) -> str:
    lines = [
        "# Fetch Geometric Shooter Offline Screen",
        "",
        f"- Campaign: `{summary.get('campaign_id', '')}`",
        f"- Architecture family: `{summary.get('architecture_family', '')}`",
        f"- Scope: `{summary.get('screen_scope', '')}`",
        f"- Promotion status: `{summary.get('promotion_status', '')}`",
        f"- Runs summarized: `{summary.get('run_count', 0)}`",
        f"- Offline model passes: `{summary.get('offline_model_pass_count', 0)}`",
        f"- Recommendation: `{summary.get('recommendation', '')}`",
        "",
        "| Gate | Layout | Run | Trace | Base pass | Closest m | Entry speed | Center speed | Aim half deg | Model pass | Approach |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for raw_run in _list_value(summary.get("runs")):
        run = _dict_value(raw_run)
        baseline = _dict_value(run.get("baseline"))
        model = _dict_value(run.get("geometric_shooter"))
        approach = _dict_value(run.get("approach_evidence"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_value(run.get("source_gate_id")),
                    _markdown_value(run.get("case_id")),
                    _markdown_value(run.get("run_index")),
                    _markdown_value(run.get("trace_source")),
                    _markdown_value(baseline.get("mission_completed_pass") and baseline.get("fetch_to_pose_pass")),
                    _markdown_value(baseline.get("closest_approach_distance_m")),
                    _markdown_value(model.get("required_entry_speed_mps")),
                    _markdown_value(model.get("required_target_center_speed_mps")),
                    _markdown_value(model.get("aim_half_angle_deg")),
                    _markdown_value(model.get("offline_pass")),
                    _markdown_value(
                        approach.get("evidence_source")
                        + ":"
                        + str(approach.get("stable_contact_approach_pass", False))
                    ),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "This is an offline/shadow screen. A green result can justify the next canonical probe, but it is not UAT evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Screen a geometric-shooter fetch architecture from saved traces.")
    parser.add_argument(
        "--baseline-gate-summary",
        type=Path,
        default=DEFAULT_BASELINE_GATE_SUMMARY,
        help="May 27 calibrated fetch gate summary or a compatible gate summary.",
    )
    parser.add_argument("--campaign-id", default=f"live_fetch_geometric_shooter_screen_{make_session_id()}")
    parser.add_argument("--gate-id", action="append", default=[], help="Restrict analysis to one gate_id; repeatable.")
    parser.add_argument("--decel-mps2", type=float, default=DEFAULT_DECEL_MPS2)
    parser.add_argument("--max-shot-speed-mps", type=float, default=DEFAULT_MAX_SHOT_SPEED_MPS)
    parser.add_argument("--min-aim-half-angle-deg", type=float, default=DEFAULT_MIN_AIM_HALF_ANGLE_DEG)
    parser.add_argument("--output-root", type=Path, default=SESSION_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = analyze_gate_summary(
        campaign_id=args.campaign_id,
        baseline_gate_summary_path=args.baseline_gate_summary,
        gate_filter=set(args.gate_id or []),
        decel_mps2=args.decel_mps2,
        max_shot_speed_mps=args.max_shot_speed_mps,
        min_aim_half_angle_deg=args.min_aim_half_angle_deg,
    )
    output_root = args.output_root if args.output_root.is_absolute() else REPO_ROOT / args.output_root
    output_dir = ensure_dir(output_root / args.campaign_id / OUTPUT_KIND)
    summary_path = output_dir / "geometric_shooter_summary.json"
    scorecard_path = output_dir / "scorecard.md"
    write_json(summary_path, summary)
    scorecard_path.write_text(render_scorecard(summary), encoding="utf-8")
    print(f"FETCH_GEOMETRIC_SHOOTER_SCREEN_SUMMARY={summary_path}")
    print(f"FETCH_GEOMETRIC_SHOOTER_SCREEN_SCORECARD={scorecard_path}")
    print(f"FETCH_GEOMETRIC_SHOOTER_SCREEN_RECOMMENDATION={summary['recommendation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
