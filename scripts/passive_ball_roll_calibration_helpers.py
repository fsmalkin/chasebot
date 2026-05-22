"""Helpers for passive golf-ball roll calibration gates."""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


G_ACCEL_MPS2 = 9.80665
GOLF_BALL_MASS_MAX_KG = 0.04593
GOLF_BALL_DIAMETER_MIN_M = 0.042672
GOLF_BALL_RADIUS_MIN_M = GOLF_BALL_DIAMETER_MIN_M / 2.0
STIMPMETER_1X_EXIT_SPEED_MPS = 1.8288
STIMPMETER_TYPICAL_GREEN_ROLL_M = (2.1336, 3.6576)
STIMPMETER_MEDIUM_ROLL_M = 3.0480
FETCH_CAL_INITIAL_SPEED_MPS = 1.0
STOP_SPEED_THRESHOLD_MPS = 0.03
REST_DWELL_S = 0.5
MAX_LATERAL_DRIFT_RATIO = 0.15


@dataclass(frozen=True)
class BallPhysicalProfile:
    name: str
    model_sdf: str
    mass_kg: float
    radius_m: float
    inertia_kg_m2: float
    linear_velocity_decay: float = 0.0
    angular_velocity_decay: float = 0.0
    friction_mu: float = 0.0
    friction_mu2: float = 0.0
    torsional_coefficient: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RollReferenceBand:
    surface_profile: str
    reference_speed_mps: float
    stop_distance_min_m: float
    stop_distance_max_m: float
    max_lateral_drift_ratio: float = MAX_LATERAL_DRIFT_RATIO
    stop_speed_threshold_mps: float = STOP_SPEED_THRESHOLD_MPS
    rest_dwell_s: float = REST_DWELL_S

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "effective_decel_min_mps2": round(self.effective_decel_min_mps2, 6),
            "effective_decel_max_mps2": round(self.effective_decel_max_mps2, 6),
            "effective_mu_min": round(self.effective_mu_min, 6),
            "effective_mu_max": round(self.effective_mu_max, 6),
        }

    @property
    def effective_decel_min_mps2(self) -> float:
        return deceleration_from_stop(self.reference_speed_mps, self.stop_distance_max_m)

    @property
    def effective_decel_max_mps2(self) -> float:
        return deceleration_from_stop(self.reference_speed_mps, self.stop_distance_min_m)

    @property
    def effective_mu_min(self) -> float:
        return self.effective_decel_min_mps2 / G_ACCEL_MPS2

    @property
    def effective_mu_max(self) -> float:
        return self.effective_decel_max_mps2 / G_ACCEL_MPS2


GOLF_SHORT_TURF_ROLL_BAND = RollReferenceBand(
    surface_profile="calibrated_golf_turf",
    reference_speed_mps=FETCH_CAL_INITIAL_SPEED_MPS,
    stop_distance_min_m=0.45,
    stop_distance_max_m=0.90,
)

GOLF_SHORT_GRASS_ROLL_BAND = RollReferenceBand(
    surface_profile="calibrated_golf_grass",
    reference_speed_mps=FETCH_CAL_INITIAL_SPEED_MPS,
    stop_distance_min_m=0.30,
    stop_distance_max_m=0.65,
)

ROLL_BANDS_BY_SURFACE = {
    GOLF_SHORT_TURF_ROLL_BAND.surface_profile: GOLF_SHORT_TURF_ROLL_BAND,
    GOLF_SHORT_GRASS_ROLL_BAND.surface_profile: GOLF_SHORT_GRASS_ROLL_BAND,
}


def solid_sphere_inertia_kg_m2(*, mass_kg: float, radius_m: float) -> float:
    return (2.0 / 5.0) * float(mass_kg) * float(radius_m) ** 2


def ramp_exit_speed_mps(*, vertical_drop_m: float, inertia_factor: float = 2.0 / 5.0) -> float:
    drop = max(float(vertical_drop_m), 0.0)
    return math.sqrt((2.0 * G_ACCEL_MPS2 * drop) / (1.0 + float(inertia_factor)))


def deceleration_from_stop(initial_speed_mps: float, stop_distance_m: float) -> float:
    distance = float(stop_distance_m)
    if distance <= 0.0:
        raise ValueError("stop_distance_m must be positive")
    speed = max(float(initial_speed_mps), 0.0)
    return speed * speed / (2.0 * distance)


def stop_distance_m(*, initial_speed_mps: float, decel_mps2: float) -> float:
    decel = float(decel_mps2)
    if decel <= 0.0:
        raise ValueError("decel_mps2 must be positive")
    speed = max(float(initial_speed_mps), 0.0)
    return speed * speed / (2.0 * decel)


def stop_time_s(*, initial_speed_mps: float, decel_mps2: float) -> float:
    decel = float(decel_mps2)
    if decel <= 0.0:
        raise ValueError("decel_mps2 must be positive")
    return max(float(initial_speed_mps), 0.0) / decel


def _text_float(parent: ET.Element | None, path: str, default: float = 0.0) -> float:
    if parent is None:
        return default
    item = parent.find(path)
    if item is None or item.text is None:
        return default
    try:
        return float(item.text.strip())
    except ValueError:
        return default


def parse_ball_sdf_profile(path: Path | str) -> BallPhysicalProfile:
    sdf_path = Path(path)
    root = ET.parse(sdf_path).getroot()
    model = root.find("model")
    if model is None:
        raise ValueError(f"{sdf_path} does not contain an SDF model")
    model_name = str(model.get("name") or sdf_path.stem)
    link = model.find("link")
    if link is None:
        raise ValueError(f"{sdf_path} does not contain a model link")
    mass = _text_float(link, "inertial/mass")
    radius = _text_float(link, "collision/geometry/sphere/radius")
    if mass <= 0.0:
        raise ValueError(f"{sdf_path} is missing a positive mass")
    if radius <= 0.0:
        raise ValueError(f"{sdf_path} is missing a positive sphere radius")
    return BallPhysicalProfile(
        name=model_name,
        model_sdf=str(sdf_path),
        mass_kg=mass,
        radius_m=radius,
        inertia_kg_m2=_text_float(link, "inertial/inertia/ixx"),
        linear_velocity_decay=_text_float(link, "velocity_decay/linear"),
        angular_velocity_decay=_text_float(link, "velocity_decay/angular"),
        friction_mu=_text_float(link, "collision/surface/friction/ode/mu"),
        friction_mu2=_text_float(link, "collision/surface/friction/ode/mu2"),
        torsional_coefficient=_text_float(link, "collision/surface/friction/torsional/coefficient"),
    )


def _sample_xy(sample: dict[str, Any]) -> tuple[float, float] | None:
    position = sample.get("position") if isinstance(sample.get("position"), dict) else sample
    try:
        return float(position.get("x")), float(position.get("y"))  # type: ignore[union-attr]
    except (AttributeError, TypeError, ValueError):
        return None


def _sample_t(sample: dict[str, Any]) -> float | None:
    for key in ("t_s", "elapsed_s"):
        try:
            return float(sample.get(key))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
    return None


def _speed_between(previous: dict[str, Any], current: dict[str, Any]) -> float | None:
    previous_t = _sample_t(previous)
    current_t = _sample_t(current)
    previous_xy = _sample_xy(previous)
    current_xy = _sample_xy(current)
    if previous_t is None or current_t is None or previous_xy is None or current_xy is None:
        return None
    dt = current_t - previous_t
    if dt <= 0.0:
        return None
    return math.hypot(current_xy[0] - previous_xy[0], current_xy[1] - previous_xy[1]) / dt


def summarize_roll_samples(
    samples: list[dict[str, Any]],
    *,
    ground_start_x_m: float = 0.0,
    stop_speed_threshold_mps: float = STOP_SPEED_THRESHOLD_MPS,
    rest_dwell_s: float = REST_DWELL_S,
) -> dict[str, Any]:
    ordered = sorted(
        [sample for sample in samples if _sample_t(sample) is not None and _sample_xy(sample) is not None],
        key=lambda item: float(_sample_t(item) or 0.0),
    )
    if len(ordered) < 2:
        return {
            "observed": bool(ordered),
            "sample_count": len(ordered),
            "stopped": False,
            "peak_speed_mps": 0.0,
            "roll_distance_m": 0.0,
            "stop_time_s": 0.0,
            "lateral_drift_m": 0.0,
            "lateral_drift_ratio": 0.0,
            "effective_decel_mps2": 0.0,
        }

    speed_rows: list[dict[str, Any]] = []
    for previous, current in zip(ordered, ordered[1:]):
        speed = _speed_between(previous, current)
        current_xy = _sample_xy(current)
        current_t = _sample_t(current)
        if speed is None or current_xy is None or current_t is None:
            continue
        if current_xy[0] < ground_start_x_m:
            continue
        speed_rows.append({"sample": current, "speed_mps": speed})

    if not speed_rows:
        return {
            "observed": True,
            "sample_count": len(ordered),
            "stopped": False,
            "peak_speed_mps": 0.0,
            "roll_distance_m": 0.0,
            "stop_time_s": 0.0,
            "lateral_drift_m": 0.0,
            "lateral_drift_ratio": 0.0,
            "effective_decel_mps2": 0.0,
        }

    peak_row = max(speed_rows, key=lambda item: float(item["speed_mps"]))
    start_sample = peak_row["sample"]
    start_xy = _sample_xy(start_sample) or (0.0, 0.0)
    start_t = float(_sample_t(start_sample) or 0.0)
    candidate_samples = [
        sample
        for sample in ordered
        if (_sample_t(sample) is not None and float(_sample_t(sample) or 0.0) >= start_t)
    ]
    end_sample = candidate_samples[-1]
    end_xy = _sample_xy(end_sample) or start_xy
    end_t = float(_sample_t(end_sample) or start_t)
    roll_distance = math.hypot(end_xy[0] - start_xy[0], end_xy[1] - start_xy[1])
    lateral_drift = abs(end_xy[1] - start_xy[1])
    lateral_ratio = lateral_drift / max(abs(end_xy[0] - start_xy[0]), 1e-6)
    peak_speed = float(peak_row["speed_mps"])

    stopped_since: float | None = None
    stopped = False
    for row in speed_rows:
        row_sample = row["sample"]
        row_t = float(_sample_t(row_sample) or 0.0)
        if row_t < start_t:
            continue
        if float(row["speed_mps"]) <= stop_speed_threshold_mps:
            if stopped_since is None:
                stopped_since = row_t
            if row_t - stopped_since >= rest_dwell_s:
                stopped = True
        else:
            stopped_since = None
    if stopped_since is not None and end_t - stopped_since >= rest_dwell_s:
        stopped = True

    effective_decel = deceleration_from_stop(peak_speed, roll_distance) if roll_distance > 0.0 else 0.0
    return {
        "observed": True,
        "sample_count": len(ordered),
        "stopped": bool(stopped),
        "start_pose": {
            "x": round(start_xy[0], 6),
            "y": round(start_xy[1], 6),
            "t_s": round(start_t, 6),
        },
        "end_pose": {
            "x": round(end_xy[0], 6),
            "y": round(end_xy[1], 6),
            "t_s": round(end_t, 6),
        },
        "peak_speed_mps": round(peak_speed, 6),
        "roll_distance_m": round(roll_distance, 6),
        "stop_time_s": round(max(0.0, end_t - start_t), 6),
        "lateral_drift_m": round(lateral_drift, 6),
        "lateral_drift_ratio": round(lateral_ratio, 6),
        "effective_decel_mps2": round(effective_decel, 6),
        "effective_mu": round(effective_decel / G_ACCEL_MPS2, 6) if effective_decel > 0.0 else 0.0,
    }


def expected_stop_distance_band_m(*, initial_speed_mps: float, reference_band: RollReferenceBand) -> tuple[float, float]:
    speed = max(float(initial_speed_mps), 0.0)
    min_distance = stop_distance_m(initial_speed_mps=speed, decel_mps2=reference_band.effective_decel_max_mps2)
    max_distance = stop_distance_m(initial_speed_mps=speed, decel_mps2=reference_band.effective_decel_min_mps2)
    return min_distance, max_distance


def classify_roll_result(
    metrics: dict[str, Any],
    *,
    reference_band: RollReferenceBand = GOLF_SHORT_TURF_ROLL_BAND,
    min_peak_speed_mps: float = 0.35,
) -> dict[str, Any]:
    if not bool(metrics.get("observed", False)):
        return {"pass": False, "reason": "no_roll_observed"}
    peak_speed = float(metrics.get("peak_speed_mps", 0.0) or 0.0)
    roll_distance = float(metrics.get("roll_distance_m", 0.0) or 0.0)
    if peak_speed < min_peak_speed_mps:
        return {
            "pass": False,
            "reason": "insufficient_initial_speed",
            "expected_stop_distance_min_m": 0.0,
            "expected_stop_distance_max_m": 0.0,
        }
    min_distance, max_distance = expected_stop_distance_band_m(
        initial_speed_mps=peak_speed,
        reference_band=reference_band,
    )
    if not bool(metrics.get("stopped", False)):
        return {
            "pass": False,
            "reason": "ball_did_not_stop",
            "expected_stop_distance_min_m": round(min_distance, 6),
            "expected_stop_distance_max_m": round(max_distance, 6),
        }
    if float(metrics.get("lateral_drift_ratio", 0.0) or 0.0) > reference_band.max_lateral_drift_ratio:
        return {
            "pass": False,
            "reason": "excessive_lateral_drift",
            "expected_stop_distance_min_m": round(min_distance, 6),
            "expected_stop_distance_max_m": round(max_distance, 6),
        }
    if roll_distance < min_distance:
        reason = "under_roll"
        pass_flag = False
    elif roll_distance > max_distance:
        reason = "over_roll"
        pass_flag = False
    else:
        reason = "within_reference_band"
        pass_flag = True
    return {
        "pass": bool(pass_flag),
        "reason": reason,
        "expected_stop_distance_min_m": round(min_distance, 6),
        "expected_stop_distance_max_m": round(max_distance, 6),
    }


def summarize_campaign(
    *,
    campaign_id: str,
    surface_profile: str,
    world_file: str,
    ball_profile: BallPhysicalProfile,
    reference_band: RollReferenceBand,
    run_results: list[dict[str, Any]],
) -> dict[str, Any]:
    pass_count = sum(1 for item in run_results if bool(item.get("pass", False)))
    observed = [item for item in run_results if bool(item.get("observed", False))]

    def avg(key: str) -> float:
        values = [float(item.get(key, 0.0) or 0.0) for item in observed if item.get(key) not in {None, ""}]
        return round(sum(values) / len(values), 6) if values else 0.0

    return {
        "campaign_id": campaign_id,
        "surface_profile": surface_profile,
        "world_file": world_file,
        "ball_profile": ball_profile.to_dict(),
        "reference_band": reference_band.to_dict(),
        "runs": len(run_results),
        "pass_count": pass_count,
        "fail_count": max(0, len(run_results) - pass_count),
        "pass": bool(run_results) and pass_count == len(run_results),
        "avg_peak_speed_mps": avg("peak_speed_mps"),
        "avg_roll_distance_m": avg("roll_distance_m"),
        "avg_stop_time_s": avg("stop_time_s"),
        "avg_effective_decel_mps2": avg("effective_decel_mps2"),
        "run_results": run_results,
    }


def build_scorecard_markdown(summary: dict[str, Any]) -> str:
    profile = summary.get("ball_profile", {}) if isinstance(summary.get("ball_profile"), dict) else {}
    band = summary.get("reference_band", {}) if isinstance(summary.get("reference_band"), dict) else {}
    lines = [
        "# Passive Ball Roll Calibration Scorecard",
        "",
        f"- Campaign: `{summary.get('campaign_id', '')}`",
        f"- Pass: `{bool(summary.get('pass', False))}`",
        f"- Surface: `{summary.get('surface_profile', '')}` world=`{summary.get('world_file', '')}`",
        f"- Ball: `{profile.get('name', '')}` mass=`{float(profile.get('mass_kg', 0.0) or 0.0):.5f}kg` radius=`{float(profile.get('radius_m', 0.0) or 0.0):.5f}m`",
        f"- Reference: `{band.get('surface_profile', '')}` at `{float(band.get('reference_speed_mps', 0.0) or 0.0):.2f}m/s` distance=`{float(band.get('stop_distance_min_m', 0.0) or 0.0):.2f}-{float(band.get('stop_distance_max_m', 0.0) or 0.0):.2f}m`",
        f"- Runs: `{int(summary.get('pass_count', 0) or 0)}/{int(summary.get('runs', 0) or 0)}`",
        f"- Averages: speed=`{float(summary.get('avg_peak_speed_mps', 0.0) or 0.0):.3f}m/s` distance=`{float(summary.get('avg_roll_distance_m', 0.0) or 0.0):.3f}m` stop=`{float(summary.get('avg_stop_time_s', 0.0) or 0.0):.3f}s` decel=`{float(summary.get('avg_effective_decel_mps2', 0.0) or 0.0):.3f}m/s^2`",
        "",
        "## Runs",
        "",
    ]
    for item in summary.get("run_results", []):
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- run `{int(item.get('run_index', 0) or 0)}` pass=`{bool(item.get('pass', False))}` "
            f"reason=`{item.get('reason', '')}` speed=`{float(item.get('peak_speed_mps', 0.0) or 0.0):.3f}m/s` "
            f"distance=`{float(item.get('roll_distance_m', 0.0) or 0.0):.3f}m` "
            f"expected=`{float(item.get('expected_stop_distance_min_m', 0.0) or 0.0):.3f}-{float(item.get('expected_stop_distance_max_m', 0.0) or 0.0):.3f}m`"
        )
    lines.append("")
    return "\n".join(lines)
