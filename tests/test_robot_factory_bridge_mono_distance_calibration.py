from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_TOOLS_DIR = REPO_ROOT / "tools" / "robot_factory_bridge"
if str(BRIDGE_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_TOOLS_DIR))

import chasecar_bridge_mono_distance_calibration as calib  # noqa: E402


def _sample(d, size, *, detected=True, key="bbox_height_px"):
    return {"label": "d%03d" % int(round(d * 100)), "known_distance_m": d, key: size, "detected": detected}


def test_perfect_fit_recovers_constant_and_focal():
    k_true = 12.0  # px * m
    samples = [_sample(d, k_true / d) for d in (0.25, 0.5, 1.0)]

    fit = calib.fit_apparent_size(samples, size_key="bbox_height_px", object_size_m=0.0427)

    assert fit["pass"] is True
    assert fit["n_used"] == 3
    assert abs(fit["K_px_m"] - k_true) < 1e-6
    assert fit["sigma_s_px"] == 0.0
    # implied focal = K / object_size = 12 / 0.0427
    assert abs(fit["implied_focal_px"] - (k_true / 0.0427)) < 0.5
    assert fit["max_calibrated_range_m"] == 1.0
    for row in fit["per_sample"]:
        assert row["abs_err_m"] < 1e-6
        assert row["sigma_d_m"] == 0.0


def test_requires_at_least_two_detected_samples():
    fit = calib.fit_apparent_size([_sample(0.5, 24.0)], size_key="bbox_height_px", object_size_m=0.0427)

    assert fit["pass"] is False
    assert "need_at_least_two_detected_samples" in fit["issues"]
    assert fit["n_used"] == 1


def test_excludes_undetected_and_zero_size_samples():
    k_true = 10.0
    samples = [
        _sample(0.3, k_true / 0.3),
        _sample(0.6, k_true / 0.6),
        _sample(0.9, 0.0),  # zero size -> excluded
        _sample(1.2, k_true / 1.2, detected=False),  # undetected -> excluded
    ]

    fit = calib.fit_apparent_size(samples, size_key="bbox_height_px", object_size_m=0.0427)

    assert fit["pass"] is True
    assert fit["n_used"] == 2
    assert abs(fit["K_px_m"] - k_true) < 1e-6


def test_sigma_d_grows_with_distance_squared():
    # Inject a fixed-magnitude residual so sigma_s > 0, then confirm the
    # reported per-distance uncertainty is monotone increasing in d.
    k_true = 12.0
    perturb = {0.25: +0.5, 0.5: -0.5, 1.0: +0.5, 1.5: -0.5}
    samples = [_sample(d, k_true / d + perturb[d]) for d in (0.25, 0.5, 1.0, 1.5)]

    fit = calib.fit_apparent_size(samples, size_key="bbox_height_px", object_size_m=0.0427)

    assert fit["pass"] is True
    assert fit["sigma_s_px"] > 0.0
    rows = sorted(fit["per_sample"], key=lambda r: r["known_distance_m"])
    sigmas = [r["sigma_d_m"] for r in rows]
    assert sigmas == sorted(sigmas)
    assert sigmas[-1] > sigmas[0]


def test_load_dataset_roundtrip(tmp_path):
    dataset = tmp_path / "calibration_dataset.jsonl"
    rows = [
        {"label": "d030", "known_distance_m": 0.3, "bbox_height_px": 40.0, "detected": True},
        {"label": "d060", "known_distance_m": 0.6, "bbox_height_px": 20.0, "detected": True},
    ]
    dataset.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    loaded = calib.load_dataset(dataset)

    assert loaded == rows
    assert calib.load_dataset(tmp_path / "missing.jsonl") == []
