import json
import math
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_geometric_shooter_probe as probe  # noqa: E402


def test_load_first_layout_target_reads_golf_layout(tmp_path: Path):
    layout = tmp_path / "layout.json"
    layout.write_text(
        json.dumps(
            {
                "targets": [
                    {
                        "id": "ball_1",
                        "forward_m": 0.38,
                        "lateral_m": -0.05,
                        "z_m": 0.021336,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert probe.load_first_layout_target(layout) == {"x": 0.38, "y": -0.05, "z": 0.021336}


def test_shot_heading_points_from_ball_to_target():
    assert probe.shot_heading_deg(ball_x=0.38, ball_y=0.0, target_x=0.95, target_y=0.0) == pytest.approx(0.0)
    assert probe.shot_heading_deg(ball_x=0.38, ball_y=0.05, target_x=0.95, target_y=0.0) == pytest.approx(
        math.degrees(math.atan2(-0.05, 0.57))
    )


def test_select_shot_speed_uses_center_speed_by_default():
    model = {
        "required_entry_speed_mps": 0.62,
        "required_target_center_speed_mps": 0.91,
        "required_far_edge_speed_mps": 1.12,
    }

    assert probe.select_shot_speed_mps(model, mode="entry") == pytest.approx(0.62)
    assert probe.select_shot_speed_mps(model, mode="center") == pytest.approx(0.91)
    assert probe.select_shot_speed_mps(model, mode="far_edge") == pytest.approx(1.12)
