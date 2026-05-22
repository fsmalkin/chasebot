import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from golf_ball_circle_delivery_demo_runner import build_shot_outcome  # noqa: E402
from golf_ball_circle_delivery_demo_runner import parse_args  # noqa: E402


def test_shot_outcome_uses_segment_intersection_for_delivery_circle():
    samples = [
        {"t_s": 0.0, "position": {"x": 0.20, "y": 0.0, "z": 0.021336}},
        {"t_s": 0.5, "position": {"x": 1.20, "y": 0.0, "z": 0.021336}},
    ]

    outcome = build_shot_outcome(samples, target_x=0.95, target_y=0.0, target_z=0.001, radius_m=0.30)

    assert outcome["pass"] is True
    assert outcome["closest_approach_distance_m"] == pytest.approx(0.0)
    assert outcome["fetch_pose_world"] == {"x": 0.95, "y": 0.0, "z": 0.001, "radius_m": 0.3}


def test_parse_args_accepts_dashboard_fetch_target_aliases(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "golf_ball_circle_delivery_demo_runner.py",
            "--fetch-target-x",
            "1.25",
            "--fetch-target-y",
            "0.10",
            "--fetch-target-z",
            "0.002",
        ],
    )

    args = parse_args()

    assert args.fetch_target_x == pytest.approx(1.25)
    assert args.fetch_target_y == pytest.approx(0.10)
    assert args.fetch_target_z == pytest.approx(0.002)
