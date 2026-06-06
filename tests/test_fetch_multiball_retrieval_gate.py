from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_multiball_retrieval_gate as multiball_gate  # noqa: E402
import fetch_planner_handoff_gate as planner_gate  # noqa: E402
import fetch_planner_route_replay_batch as replay_batch  # noqa: E402


def _args(**overrides):
    payload = {
        "campaign_id": "multiball_gate",
        "dry_run": True,
        "random_cases": 2,
        "balls_per_scene": 3,
        "seed": 20260606,
        "profile": multiball_gate.DEFAULT_PROFILE,
        "scene_descriptor_json": [],
        "planner_mode": planner_gate.PLANNER_MODE_DETERMINISTIC,
        "openai_model": planner_gate.DEFAULT_OPENAI_MODEL,
        "openai_api_key": "",
        "openai_base_url": planner_gate.DEFAULT_OPENAI_BASE_URL,
        "openai_org_id": "",
        "openai_project_id": "",
        "reasoning_effort": planner_gate.DEFAULT_REASONING_EFFORT,
        "planner_timeout_s": 45.0,
        "dashboard_url": "",
        "compose_project": "",
        "fetch_delivery_radius_m": 0.3,
        "python_exe": sys.executable,
        "timeout_s": 180.0,
        "stop_on_fail": False,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _patch_roots(tmp_path, monkeypatch):
    session_root = tmp_path / "artifacts" / "session"
    monkeypatch.setattr(multiball_gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(multiball_gate, "SESSION_ROOT", session_root)
    monkeypatch.setattr(replay_batch, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(replay_batch, "SESSION_ROOT", session_root)
    monkeypatch.setattr(planner_gate, "REPO_ROOT", tmp_path)


def _pose_distance(a, b):
    return math.hypot(float(a["x"]) - float(b["x"]), float(a["y"]) - float(b["y"]))


def test_generate_multiball_scenes_is_deterministic_and_bounded():
    scenes_a = multiball_gate.generate_multiball_scenes(seed=20260606, random_cases=3, balls_per_scene=3)
    scenes_b = multiball_gate.generate_multiball_scenes(seed=20260606, random_cases=3, balls_per_scene=3)

    comparable_a = [
        {
            "scene_id": scene["scene_id"],
            "robot_pose": scene["robot_pose"],
            "balls": [(ball["id"], ball["pose"]) for ball in scene["balls"]],
            "randomization": scene["randomization"],
        }
        for scene in scenes_a
    ]
    comparable_b = [
        {
            "scene_id": scene["scene_id"],
            "robot_pose": scene["robot_pose"],
            "balls": [(ball["id"], ball["pose"]) for ball in scene["balls"]],
            "randomization": scene["randomization"],
        }
        for scene in scenes_b
    ]
    assert comparable_a == comparable_b
    assert len(scenes_a) == 3
    for scene in scenes_a:
        assert scene["profile"] == multiball_gate.DEFAULT_PROFILE
        assert len(scene["balls"]) == 3
        robot_pose = scene["robot_pose"]
        target_pose = scene["target_pose"]
        for index, ball in enumerate(scene["balls"]):
            pose = ball["pose"]
            assert multiball_gate.in_field_bounds(pose["x"], pose["y"])
            assert _pose_distance(pose, target_pose) > target_pose["radius_m"] + 0.12
            assert _pose_distance(pose, robot_pose) >= multiball_gate.MIN_ROBOT_BALL_SEPARATION_M
            for other in scene["balls"][index + 1 :]:
                assert _pose_distance(pose, other["pose"]) >= multiball_gate.MIN_BALL_SEPARATION_M


def test_multiball_planner_orders_nearest_feasible_setup_first():
    target = multiball_gate.target_pose()
    scene = {
        "generated_utc": "2026-06-06T00:00:00Z",
        "type": "fetch_multiball_scene_descriptor",
        "profile": multiball_gate.DEFAULT_PROFILE,
        "scene_id": "manual_multiball",
        "seed": 1,
        "target_pose": target,
        "robot_pose": {"x": -0.35, "y": -0.72, "z": 0.0, "yaw": 0.0},
        "balls": [
            {"id": "ball_1", "pose": {"x": 0.35, "y": 0.52, "z": 0.021336, "yaw": 0.0}},
            {"id": "ball_2", "pose": {"x": 0.36, "y": -0.45, "z": 0.021336, "yaw": 0.0}},
            {"id": "ball_3", "pose": {"x": 1.55, "y": 0.40, "z": 0.021336, "yaw": 0.0}},
        ],
    }

    plan = multiball_gate.plan_multiball_scene(scene, args=_args())

    assert plan["planner_ready"] is True
    assert plan["retrieval_order"][0] == "ball_2"
    assert sorted(plan["retrieval_order"]) == ["ball_1", "ball_2", "ball_3"]
    assert plan["executable_step_count"] == 3


def test_multiball_gate_dry_run_materializes_layouts_and_replay_commands(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)

    summary = multiball_gate.run_gate(_args(campaign_id="dry_multiball", dry_run=True, random_cases=2, balls_per_scene=3))

    assert summary["pass"] is True
    assert summary["promotion_evidence"] is False
    assert summary["scene_count"] == 2
    assert summary["planned_step_count"] == 6
    assert summary["planner_ready_scene_count"] == 2
    assert (tmp_path / summary["summary_path"]).is_file()
    assert (tmp_path / summary["scorecard_path"]).is_file()
    seen_model_names = set()
    for row in summary["step_rows"]:
        layout_path = tmp_path / row["layout_path"]
        assert layout_path.is_file()
        layout = json.loads(layout_path.read_text(encoding="utf-8"))
        assert layout["multiball_scene_id"] == row["scene_id"]
        assert layout["multiball_ball_id"] == row["ball_id"]
        assert "--target-layout-json" in row["command"]
        assert row["command"][row["command"].index("--target-layout-json") + 1] == str(layout_path)
        assert "--target-model-name" in row["command"]
        model_name = row["command"][row["command"].index("--target-model-name") + 1]
        assert model_name not in seen_model_names
        seen_model_names.add(model_name)


def test_multiball_gate_live_mock_records_per_ball_missions(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    calls = []

    def fake_run_command(command, *, timeout_s):
        calls.append(command)
        mission_path = (
            tmp_path
            / "artifacts"
            / "session"
            / f"live_multiball_step_{len(calls)}"
            / "golf_ball_circle_delivery"
            / "run"
            / "mission_verdict.json"
        )
        mission_path.parent.mkdir(parents=True, exist_ok=True)
        mission_path.write_text(
            json.dumps(
                {
                    "pass": True,
                    "fetch_to_pose_pass": True,
                    "planner_route_label": planner_gate.ROUTE_FETCH_READY,
                    "route_executor": planner_gate.ROUTE_EXECUTOR_LOCAL_FETCH,
                    "measured_push_ready_handoff": {"pass": True, "source": "mock"},
                    "shot_outcome": {
                        "closest_approach_distance_m": 0.18,
                        "reason": "trajectory_intersects_delivery_radius",
                    },
                    "approach_contact_metrics": {
                        "flags": [],
                        "first_contact_quality_flags": [],
                        "stable_contact_approach_pass": True,
                        "first_contact_quality_pass": True,
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return type(
            "Completed",
            (),
            {
                "returncode": 0,
                "stdout": f"{multiball_gate.MISSION_SUMMARY_MARKER}{mission_path}\n",
                "stderr": "",
            },
        )()

    monkeypatch.setattr(multiball_gate, "run_command", fake_run_command)

    summary = multiball_gate.run_gate(_args(campaign_id="live_multiball", dry_run=False, random_cases=1, balls_per_scene=3))

    assert summary["pass"] is True
    assert len(calls) == 3
    assert summary["live_fetch_to_pose_pass_count"] == 3
    assert summary["live_fetch_to_pose_fail_count"] == 0
    assert all(row["mission"]["fetch_to_pose_pass"] for row in summary["step_rows"])
