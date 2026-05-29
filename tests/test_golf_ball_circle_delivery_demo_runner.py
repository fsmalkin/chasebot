import sys
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from golf_ball_circle_delivery_demo_runner import build_shot_outcome  # noqa: E402
from golf_ball_circle_delivery_demo_runner import ball_samples_from_contact_samples  # noqa: E402
from golf_ball_circle_delivery_demo_runner import build_approach_contact_metrics  # noqa: E402
from golf_ball_circle_delivery_demo_runner import parse_args  # noqa: E402
from golf_ball_circle_delivery_demo_runner import apply_target_layout  # noqa: E402


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


def test_apply_target_layout_sets_ball_pose_from_layout(tmp_path):
    layout_path = tmp_path / "layout.json"
    layout_path.write_text(
        json.dumps(
            {
                "layout_family": "bounded_random_golf_ball_circle_delivery",
                "random_profile": "local_visual_v1",
                "random_draw": {"seed": 123},
                "targets": [
                    {
                        "id": "ball_1",
                        "forward_m": 0.52,
                        "lateral_m": -0.11,
                        "z_m": 0.021336,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    args = SimpleNamespace(
        target_layout_json=str(layout_path),
        ball_x=0.38,
        ball_y=0.0,
        ball_z=0.021336,
    )

    layout = apply_target_layout(args)

    assert args.ball_x == pytest.approx(0.52)
    assert args.ball_y == pytest.approx(-0.11)
    assert args.ball_z == pytest.approx(0.021336)
    assert layout["random_profile"] == "local_visual_v1"
    assert layout["random_draw"]["seed"] == 123


def test_contact_trace_metrics_accept_stable_axial_approach():
    samples = [
        {
            "sample_index": 0,
            "t_s": 0.0,
            "robot_pose": {"position": {"x": 0.06, "y": 0.0, "z": 0.0}, "yaw": 0.0},
            "ball_pose": {"position": {"x": 0.38, "y": 0.0, "z": 0.021336}, "yaw": 0.0},
        },
        {
            "sample_index": 1,
            "t_s": 0.5,
            "robot_pose": {"position": {"x": 0.32, "y": 0.001, "z": 0.0}, "yaw": 0.01},
            "ball_pose": {"position": {"x": 0.38, "y": 0.0, "z": 0.021336}, "yaw": 0.0},
        },
        {
            "sample_index": 2,
            "t_s": 0.8,
            "robot_pose": {"position": {"x": 0.40, "y": 0.001, "z": 0.0}, "yaw": 0.01},
            "ball_pose": {"position": {"x": 0.40, "y": 0.0, "z": 0.021336}, "yaw": 0.0},
        },
        {
            "sample_index": 3,
            "t_s": 1.2,
            "robot_pose": {"position": {"x": 0.52, "y": 0.001, "z": 0.0}, "yaw": 0.0},
            "ball_pose": {"position": {"x": 0.55, "y": 0.002, "z": 0.021336}, "yaw": 0.0},
        },
    ]

    metrics = build_approach_contact_metrics(
        samples,
        ball_start_x=0.38,
        ball_start_y=0.0,
        target_x=0.95,
        target_y=0.0,
    )

    assert metrics["stable_contact_approach_pass"] is True
    assert metrics["flags"] == []
    assert metrics["first_contact_index"] == 2
    assert metrics["max_abs_robot_lateral_error_pre_contact_m"] == pytest.approx(0.001)
    assert metrics["robot_yaw_error_sign_changes_pre_contact"] == 0


def test_contact_trace_metrics_flag_lateral_knock_away_and_yaw_oscillation():
    samples = [
        {
            "sample_index": 0,
            "t_s": 0.0,
            "robot_pose": {"position": {"x": 0.06, "y": 0.0, "z": 0.0}, "yaw": 0.02},
            "ball_pose": {"position": {"x": 0.38, "y": 0.0, "z": 0.021336}, "yaw": 0.0},
        },
        {
            "sample_index": 1,
            "t_s": 0.2,
            "robot_pose": {"position": {"x": 0.18, "y": 0.04, "z": 0.0}, "yaw": -0.02},
            "ball_pose": {"position": {"x": 0.38, "y": 0.0, "z": 0.021336}, "yaw": 0.0},
        },
        {
            "sample_index": 2,
            "t_s": 0.4,
            "robot_pose": {"position": {"x": 0.30, "y": -0.04, "z": 0.0}, "yaw": 0.02},
            "ball_pose": {"position": {"x": 0.39, "y": 0.04, "z": 0.021336}, "yaw": 0.0},
        },
    ]

    metrics = build_approach_contact_metrics(
        samples,
        ball_start_x=0.38,
        ball_start_y=0.0,
        target_x=0.95,
        target_y=0.0,
        yaw_threshold_deg=5.0,
    )

    assert metrics["stable_contact_approach_pass"] is False
    assert "pre_contact_lateral_error" in metrics["flags"]
    assert "pre_contact_yaw_oscillation" in metrics["flags"]
    assert "ball_lateral_knock_away" in metrics["flags"]


def test_ball_samples_from_contact_samples_preserves_legacy_ball_trace_shape():
    contact_samples = [
        {
            "sample_index": 7,
            "t_s": 1.25,
            "topic_ok": True,
            "ball_model_name": "ball",
            "ball_pose": {
                "position": {"x": 0.4, "y": 0.1, "z": 0.021336},
                "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
            },
        }
    ]

    rows = ball_samples_from_contact_samples(contact_samples)

    assert rows == [
        {
            "sample_index": 7,
            "t_s": 1.25,
            "topic_ok": True,
            "model_name": "ball",
            "position": {"x": 0.4, "y": 0.1, "z": 0.021336},
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        }
    ]
