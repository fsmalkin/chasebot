from __future__ import annotations

import json
import math
import subprocess
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
        "expected_session_id": "",
        "fresh_dashboard_session": False,
        "fresh_session_per_scene": False,
        "allow_operator_view_degraded": False,
        "world_file": "yolo_test_world_v6_calibrated_golf_turf.world",
        "surface_profile": "calibrated_golf_turf",
        "robot_sdf_name": "jetbot_core_ignition_v1.7.0.sdf",
        "nav2_goal_frame_mode": multiball_gate.DEFAULT_NAV2_GOAL_FRAME_MODE,
        "env_ready_timeout_s": replay_batch.DEFAULT_ENV_READY_TIMEOUT_S,
        "env_start_attempts": 2,
        "env_stop_timeout_s": 90.0,
        "fetch_delivery_radius_m": 0.3,
        "python_exe": sys.executable,
        "timeout_s": 180.0,
        "package_timeout_s": 180.0,
        "no_visual_package": False,
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


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def test_multiball_planner_prefers_lower_setup_debt_local_setup_capture_candidate():
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
    assert plan["sequence"][0]["route_label"] == planner_gate.ROUTE_LOCAL_SETUP_CAPTURE


def test_multiball_planner_prioritizes_target_aligned_candidate_over_nearer_high_angle_nav2_setup():
    target = multiball_gate.target_pose()
    scene = {
        "generated_utc": "2026-06-06T00:00:00Z",
        "type": "fetch_multiball_scene_descriptor",
        "profile": multiball_gate.DEFAULT_PROFILE,
        "scene_id": "manual_multiball_setup_debt",
        "seed": 20260606,
        "target_pose": target,
        "robot_pose": {"x": 0.65962, "y": -1.35, "z": 0.0, "yaw": 1.082342},
        "balls": [
            {"id": "aligned_far", "pose": {"x": 0.12877, "y": -0.011075, "z": 0.021336, "yaw": 0.0}},
            {"id": "moderate_angle", "pose": {"x": 0.461078, "y": 0.204072, "z": 0.021336, "yaw": 0.0}},
            {"id": "near_high_angle", "pose": {"x": 1.312656, "y": -0.519675, "z": 0.021336, "yaw": 0.0}},
        ],
    }

    plan = multiball_gate.plan_multiball_scene(scene, args=_args())
    first_step = plan["sequence"][0]
    first_candidates = plan["candidate_audit"][0]["candidates"]
    high_angle = next(row for row in first_candidates if row["ball_id"] == "near_high_angle")

    assert plan["retrieval_order"][0] == "aligned_far"
    assert first_step["route_label"] == planner_gate.ROUTE_LOCAL_SETUP_CAPTURE
    assert high_angle["cost"]["direction_alignment_penalty"] > 1.0
    assert high_angle["route_quality"]["setup_debt"]["ball_target_angle_abs_deg"] > 90.0


def test_multiball_planner_deprioritizes_recently_failed_ball_when_other_targets_remain():
    scenes = multiball_gate.generate_multiball_scenes(seed=20260606, random_cases=2, balls_per_scene=3)
    scene = scenes[1]
    scene["balls"][0]["last_attempt_failed"] = True
    scene["balls"][0]["attempt_count"] = 1

    plan = multiball_gate.plan_multiball_scene(scene, args=_args())
    first_candidates = plan["candidate_audit"][0]["candidates"]
    failed_candidate = next(row for row in first_candidates if row["ball_id"] == "ball_1")

    assert plan["retrieval_order"][0] != "ball_1"
    assert failed_candidate["cost"]["failed_attempt_penalty"] > 0.0


def test_multiball_gate_dry_run_materializes_layouts_and_replay_commands(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)

    summary = multiball_gate.run_gate(_args(campaign_id="dry_multiball", dry_run=True, random_cases=2, balls_per_scene=3))

    assert summary["pass"] is True
    assert summary["promotion_evidence"] is False
    assert summary["scene_count"] == 2
    assert summary["planned_step_count"] == 6
    assert summary["planner_ready_scene_count"] == 2
    assert sum(summary["route_counts"].values()) == 6
    assert summary["route_counts"][planner_gate.ROUTE_LOCAL_SETUP_CAPTURE] >= 1
    assert summary["scene_rows"][0]["retrieval_order"] == ["ball_3", "ball_1", "ball_2"]
    assert (tmp_path / summary["summary_path"]).is_file()
    assert (tmp_path / summary["scorecard_path"]).is_file()
    first_plan_path = tmp_path / summary["scene_rows"][0]["sequence_plan_path"]
    first_plan = json.loads(first_plan_path.read_text(encoding="utf-8"))
    first_candidate = first_plan["candidate_audit"][0]["candidates"][0]
    assert "route_quality" in first_candidate
    assert "direction_alignment_penalty" in first_candidate["cost"]
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
        assert model_name.startswith(multiball_gate.TARGET_MODEL_NAME_PREFIX)
        seen_model_names.add(model_name)
        robot_pose = layout["multiball_estimated_start_robot_pose"]
        assert "--robot-x" in row["command"]
        assert "--robot-y" in row["command"]
        assert "--robot-yaw" in row["command"]
        assert float(row["command"][row["command"].index("--robot-x") + 1]) == robot_pose["x"]
        assert float(row["command"][row["command"].index("--robot-y") + 1]) == robot_pose["y"]
        assert float(row["command"][row["command"].index("--robot-yaw") + 1]) == robot_pose["yaw"]
        if row["route_label"] == planner_gate.ROUTE_NAV2_REPOSITION:
            assert "--nav2-reposition-before-fetch" in row["command"]
            assert "--nav2-reposition-goal-frame-mode" in row["command"]
            assert row["command"][row["command"].index("--nav2-reposition-goal-frame-mode") + 1] == "world_direct"
            assert "--nav2-reposition-timeout-s" in row["command"]
            assert float(row["command"][row["command"].index("--nav2-reposition-timeout-s") + 1]) == 48.0
            assert "--nav2-reposition-refine-attempts" in row["command"]
            assert int(row["command"][row["command"].index("--nav2-reposition-refine-attempts") + 1]) == 1
            assert "--nav2-reposition-continue-on-failure" not in row["command"]
        else:
            assert "--nav2-reposition-before-fetch" not in row["command"]
        assert "--ai-push-coast-mode" in row["command"]
        assert row["command"][row["command"].index("--ai-push-coast-mode") + 1] == "guarded_live"


def test_persistent_field_mode_preserves_target_and_robot_in_step_commands(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)

    summary = multiball_gate.run_gate(
        _args(campaign_id="dry_persistent_multiball", dry_run=True, random_cases=1, balls_per_scene=3, persistent_field=True)
    )

    for row in summary["step_rows"]:
        assert "--use-existing-target-model" in row["command"]
        assert "--preserve-robot-pose" in row["command"]
        assert "--pre-fetch-setup-correction-s" in row["command"]
        assert float(row["command"][row["command"].index("--pre-fetch-setup-correction-s") + 1]) == 14.0
        if row["route_label"] == planner_gate.ROUTE_NAV2_REPOSITION:
            assert "--nav2-pre-setup-standoff-m" in row["command"]
            assert float(row["command"][row["command"].index("--nav2-pre-setup-standoff-m") + 1]) == 0.9
        else:
            assert "--nav2-pre-setup-standoff-m" not in row["command"]


def test_nav2_goal_frame_mode_is_configurable_for_step_commands(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    layout_path = tmp_path / "layout.json"
    _write_json(layout_path, {"planner_route_label": planner_gate.ROUTE_NAV2_REPOSITION})

    command = multiball_gate.build_step_command(
        args=_args(nav2_goal_frame_mode="nav2_relative"),
        layout_path=layout_path,
        scene_id="manual_nav2_scene",
        step={
            "step_index": 1,
            "ball_id": "ball_1",
            "route_label": planner_gate.ROUTE_NAV2_REPOSITION,
            "estimated_start_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
        },
    )

    assert command[command.index("--nav2-reposition-goal-frame-mode") + 1] == "nav2_relative"


def test_recovery_route_step_command_does_not_force_nav2_reposition(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    layout_path = tmp_path / "layout.json"
    _write_json(layout_path, {"planner_route_label": planner_gate.ROUTE_RECOVERY_OR_REAIM})

    command = multiball_gate.build_step_command(
        args=_args(dry_run=True, persistent_field=True),
        layout_path=layout_path,
        scene_id="manual_scene",
        step={
            "ball_id": "ball_1",
            "route_label": planner_gate.ROUTE_RECOVERY_OR_REAIM,
            "estimated_start_robot_pose": {"x": 0.1, "y": 0.2, "z": 0.0, "yaw": 0.3},
        },
    )

    assert "--nav2-reposition-before-fetch" not in command
    assert "--nav2-pre-setup-standoff-m" not in command
    assert "--use-existing-target-model" in command
    assert "--preserve-robot-pose" in command


def test_prepare_persistent_field_scene_spawns_all_balls_and_sets_robot(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    calls = {"removed": [], "spawned": [], "robot": []}

    def fake_remove_model(*, compose_project, world_name, model_name):
        calls["removed"].append((compose_project, world_name, model_name))

    def fake_spawn_model(**kwargs):
        calls["spawned"].append(kwargs)
        return {"pass": True, "model_name": kwargs["model_name"], "pose": {"x": kwargs["x"], "y": kwargs["y"], "z": kwargs["z"]}}

    def fake_set_model_pose(**kwargs):
        calls["robot"].append(kwargs)
        return {"pass": True, "pose": {"x": kwargs["x"], "y": kwargs["y"], "z": kwargs["z"], "yaw": kwargs["yaw"]}}

    monkeypatch.setattr(multiball_gate, "remove_model", fake_remove_model)
    monkeypatch.setattr(multiball_gate, "spawn_model", fake_spawn_model)
    monkeypatch.setattr(multiball_gate, "set_model_pose", fake_set_model_pose)

    scene = multiball_gate.generate_multiball_scenes(seed=20260606, random_cases=1, balls_per_scene=3)[0]

    result = multiball_gate.prepare_persistent_field_scene(
        scene=scene,
        compose_project="persistent_project",
        world_name="yolo_test_world",
    )

    assert result["pass"] is True
    assert result["ball_count"] == 3
    assert len(calls["removed"]) == 3
    assert len(calls["spawned"]) == 3
    assert len(calls["robot"]) == 1
    assert calls["spawned"][0]["model_name"].startswith(multiball_gate.TARGET_MODEL_NAME_PREFIX)


def test_latest_measured_state_from_mission_reads_contact_trace(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    artifact_dir = tmp_path / "artifacts" / "session" / "session_a" / "golf_ball_circle_delivery" / "run_a"
    artifact_dir.mkdir(parents=True)
    mission = artifact_dir / "mission_verdict.json"
    contact_trace = artifact_dir / "contact_trace.jsonl"
    contact_trace.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "robot_pose": {"position": {"x": 0.1, "y": 0.2, "z": 0.0}, "yaw": 0.3},
                        "ball_pose": {"position": {"x": 0.4, "y": 0.5, "z": 0.021336}, "yaw": 0.0},
                    }
                ),
                json.dumps(
                    {
                        "robot_pose": {"position": {"x": 0.6, "y": 0.7, "z": 0.0}, "yaw": 0.8},
                        "ball_pose": {"position": {"x": 0.9, "y": 1.0, "z": 0.021336}, "yaw": 0.0},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        mission,
        {
            "artifact_dir": str(artifact_dir),
            "fetch_to_pose_pass": True,
            "shot_outcome": {"closest_approach_distance_m": 0.2},
        },
    )

    state = multiball_gate.latest_measured_state_from_mission(mission)

    assert state["available"] is True
    assert state["fetch_to_pose_pass"] is True
    assert state["contact_sample_count"] == 2
    assert state["robot_pose"] == {"x": 0.6, "y": 0.7, "z": 0.0, "yaw": 0.8}
    assert state["ball_pose"] == {"x": 0.9, "y": 1.0, "z": 0.021336, "yaw": 0.0}


def test_latest_measured_state_from_mission_falls_back_to_post_nav2_reposition_pose(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    artifact_dir = tmp_path / "artifacts" / "session" / "session_nav2" / "golf_ball_circle_delivery" / "run_nav2"
    artifact_dir.mkdir(parents=True)
    mission = artifact_dir / "mission_verdict.json"
    _write_json(
        mission,
        {
            "artifact_dir": str(artifact_dir),
            "fetch_to_pose_pass": False,
            "pre_fetch_reposition": {
                "post_reposition_robot_pose": {
                    "position": {"x": 0.36, "y": -1.70, "z": 0.0},
                    "yaw": 0.87,
                },
                "post_reposition_ball_pose": {
                    "position": {"x": 0.13, "y": -0.01, "z": 0.021336},
                    "yaw": 0.0,
                },
            },
            "shot_outcome": {"reason": "fetch_skipped_after_reposition"},
        },
    )

    state = multiball_gate.latest_measured_state_from_mission(mission)

    assert state["available"] is True
    assert state["fetch_to_pose_pass"] is False
    assert state["robot_pose"] == {"x": 0.36, "y": -1.7, "z": 0.0, "yaw": 0.87}
    assert state["ball_pose"] == {"x": 0.13, "y": -0.01, "z": 0.021336, "yaw": 0.0}


def test_latest_measured_state_ignores_empty_shot_pose_before_nav2_fallback(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    artifact_dir = tmp_path / "artifacts" / "session" / "session_nav2_empty" / "golf_ball_circle_delivery" / "run_nav2"
    artifact_dir.mkdir(parents=True)
    mission = artifact_dir / "mission_verdict.json"
    _write_json(
        mission,
        {
            "artifact_dir": str(artifact_dir),
            "fetch_to_pose_pass": False,
            "pre_fetch_reposition": {
                "post_reposition_robot_pose": {
                    "position": {"x": 1.9, "y": 0.31, "z": 0.0},
                    "yaw": -2.56,
                },
                "post_reposition_ball_pose": {
                    "position": {"x": 0.12877, "y": -0.011075, "z": 0.021336},
                    "yaw": 0.0,
                },
            },
            "shot_outcome": {"ball_end_pose": {}, "reason": "nav2_reposition_failed_before_fetch"},
        },
    )

    state = multiball_gate.latest_measured_state_from_mission(mission)

    assert state["ball_pose"] == {"x": 0.12877, "y": -0.011075, "z": 0.021336, "yaw": 0.0}


def test_update_remaining_removes_passed_ball_and_keeps_failed_ball_with_measured_pose():
    remaining = [
        {"id": "ball_1", "pose": {"x": 0.1, "y": 0.0, "z": 0.021336, "yaw": 0.0}},
        {"id": "ball_2", "pose": {"x": 0.5, "y": 0.2, "z": 0.021336, "yaw": 0.0}},
    ]

    after_pass = multiball_gate.update_remaining_after_attempt(
        remaining,
        attempted_ball_id="ball_1",
        measured_state={"fetch_to_pose_pass": True, "ball_pose": {"x": 0.9, "y": 0.0, "z": 0.021336, "yaw": 0.0}},
    )
    after_fail = multiball_gate.update_remaining_after_attempt(
        remaining,
        attempted_ball_id="ball_1",
        measured_state={"fetch_to_pose_pass": False, "ball_pose": {"x": 0.25, "y": -0.1, "z": 0.021336, "yaw": 0.0}},
    )

    assert [ball["id"] for ball in after_pass] == ["ball_2"]
    assert [ball["id"] for ball in after_fail] == ["ball_1", "ball_2"]
    assert after_fail[0]["pose"]["x"] == 0.25
    assert after_fail[0]["last_attempt_failed"] is True
    assert after_fail[0]["attempt_count"] == 1


def test_replanning_rows_use_measured_robot_pose_for_next_step(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    root = tmp_path / "artifacts" / "session" / "replan" / multiball_gate.GATE_KIND
    scene = multiball_gate.generate_multiball_scenes(seed=20260606, random_cases=1, balls_per_scene=3)[0]
    calls = []

    def fake_run_command(command, *, timeout_s):
        calls.append(command)
        run_index = len(calls)
        artifact_dir = (
            tmp_path
            / "artifacts"
            / "session"
            / "session_replan"
            / "golf_ball_circle_delivery"
            / f"run_{run_index}"
        )
        artifact_dir.mkdir(parents=True)
        mission = artifact_dir / "mission_verdict.json"
        contact_trace = artifact_dir / "contact_trace.jsonl"
        robot_x = 0.10 * run_index
        contact_trace.write_text(
            json.dumps(
                {
                    "robot_pose": {"position": {"x": robot_x, "y": 0.25, "z": 0.0}, "yaw": 0.5},
                    "ball_pose": {"position": {"x": 0.8, "y": 0.0, "z": 0.021336}, "yaw": 0.0},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        _write_json(
            mission,
            {
                "artifact_dir": str(artifact_dir),
                "scenario_id": "fetch_multiball_retrieval_v1",
                "scenario_label": "Multi-Ball Retrieval v1",
                "fetch_to_pose_pass": True,
                "pass": True,
                "shot_outcome": {
                    "closest_approach_distance_m": 0.2,
                    "reason": "trajectory_intersects_delivery_radius",
                    "ball_end_pose": {"x": 0.8, "y": 0.0, "z": 0.021336},
                },
            },
        )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=f"{multiball_gate.MISSION_SUMMARY_MARKER}{mission}\n",
            stderr="",
        )

    monkeypatch.setattr(multiball_gate, "run_command", fake_run_command)

    rows, replan = multiball_gate.materialize_replanning_rows(
        root,
        scene,
        args=_args(dry_run=False, persistent_field=True),
        execute_live=True,
        compose_project="persistent_project",
        expected_session_id="session_replan",
    )

    assert len(rows) == 3
    assert replan["enabled"] is True
    assert len(replan["iterations"]) == 3
    assert all(row["measured_post_step_state"]["available"] for row in rows)
    second_layout = json.loads((tmp_path / rows[1]["layout_path"]).read_text(encoding="utf-8"))
    assert second_layout["multiball_estimated_start_robot_pose"]["x"] == 0.1
    assert "--use-existing-target-model" in rows[0]["command"]
    assert "--preserve-robot-pose" in rows[0]["command"]
    assert "--pre-fetch-setup-correction-s" in rows[0]["command"]


def test_replanning_rows_can_use_bounded_extra_attempt_to_deliver_failed_ball(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    root = tmp_path / "artifacts" / "session" / "replan_retry" / multiball_gate.GATE_KIND
    scene = multiball_gate.generate_multiball_scenes(seed=20260606, random_cases=1, balls_per_scene=2)[0]
    calls = []

    def fake_run_command(command, *, timeout_s):
        calls.append(command)
        run_index = len(calls)
        layout_path = Path(command[command.index("--target-layout-json") + 1])
        layout = json.loads(layout_path.read_text(encoding="utf-8"))
        ball_id = layout["multiball_ball_id"]
        pass_attempt = run_index > 1
        artifact_dir = (
            tmp_path
            / "artifacts"
            / "session"
            / "session_retry"
            / "golf_ball_circle_delivery"
            / f"run_{run_index}"
        )
        artifact_dir.mkdir(parents=True)
        mission = artifact_dir / "mission_verdict.json"
        contact_trace = artifact_dir / "contact_trace.jsonl"
        contact_trace.write_text(
            json.dumps(
                {
                    "robot_pose": {"position": {"x": 0.2 * run_index, "y": 0.1, "z": 0.0}, "yaw": 0.0},
                    "ball_pose": {"position": {"x": 0.4 + 0.1 * run_index, "y": 0.0, "z": 0.021336}, "yaw": 0.0},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        _write_json(
            mission,
            {
                "artifact_dir": str(artifact_dir),
                "scenario_id": "fetch_multiball_retrieval_v1",
                "scenario_label": "Multi-Ball Retrieval v1",
                "fetch_to_pose_pass": pass_attempt,
                "pass": pass_attempt,
                "shot_outcome": {
                    "closest_approach_distance_m": 0.2 if pass_attempt else 0.5,
                    "reason": "trajectory_intersects_delivery_radius" if pass_attempt else "missed_delivery_radius",
                    "ball_end_pose": {"x": 0.5 + 0.1 * run_index, "y": 0.0, "z": 0.021336},
                },
                "debug_ball_id": ball_id,
            },
        )
        return subprocess.CompletedProcess(
            command,
            0 if pass_attempt else 2,
            stdout=f"{multiball_gate.MISSION_SUMMARY_MARKER}{mission}\n",
            stderr="",
        )

    monkeypatch.setattr(multiball_gate, "run_command", fake_run_command)

    rows, replan = multiball_gate.materialize_replanning_rows(
        root,
        scene,
        args=_args(dry_run=False, persistent_field=True, max_extra_attempts_per_scene=1),
        execute_live=True,
        compose_project="persistent_project",
        expected_session_id="session_retry",
    )

    assert len(rows) == 3
    assert [bool(row["mission"]["fetch_to_pose_pass"]) for row in rows] == [False, True, True]
    assert all(row["selected_ball_id"] == row["ball_id"] for row in rows)
    assert all(isinstance(row["route_quality"], dict) for row in rows)
    assert all(isinstance(row["route_cost"], dict) for row in rows)
    assert replan["max_iterations"] == 3
    assert replan["all_balls_delivered"] is True
    assert replan["remaining_ball_ids"] == []


def test_replanning_rows_keep_ball_remaining_when_runner_omits_mission_marker(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    root = tmp_path / "artifacts" / "session" / "replan_missing_marker" / multiball_gate.GATE_KIND
    scene = multiball_gate.generate_multiball_scenes(seed=20260606, random_cases=1, balls_per_scene=1)[0]

    def fake_run_command(command, *, timeout_s):
        return subprocess.CompletedProcess(command, 2, stdout="", stderr="runner failed before summary")

    monkeypatch.setattr(multiball_gate, "run_command", fake_run_command)

    rows, replan = multiball_gate.materialize_replanning_rows(
        root,
        scene,
        args=_args(dry_run=False, persistent_field=True, max_extra_attempts_per_scene=0),
        execute_live=True,
        compose_project="persistent_project",
        expected_session_id="session_missing_marker",
    )

    assert len(rows) == len(scene["balls"])
    assert rows[0]["failure_reason"] == "runner_returned_nonzero"
    assert replan["all_balls_delivered"] is False
    assert scene["balls"][0]["id"] in replan["remaining_ball_ids"]


def test_multiball_gate_live_mock_records_per_ball_missions(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    calls = []
    stops = []

    def fake_stop_dashboard_environment(dashboard_url, *, timeout_s):
        stops.append((dashboard_url, timeout_s))
        return {"request": {"ok": True}, "state": {"environment_state": "stopped"}}

    def fake_start_dashboard_environment(args):
        return {
            "request": {"ok": True},
            "state": {
                "environment_state": "environment_ready",
                "phase": "environment_ready",
                "sim_gate_ready": True,
                "operator_view_ready": True,
                "compose_project": "fresh_multiball_project",
                "session_id": "fresh_multiball_session",
            },
        }

    monkeypatch.setattr(replay_batch, "stop_dashboard_environment", fake_stop_dashboard_environment)
    monkeypatch.setattr(replay_batch, "start_dashboard_environment", fake_start_dashboard_environment)

    def fake_run_command(command, *, timeout_s):
        calls.append(command)
        if "fetch_visual_uat_package.py" in " ".join(command):
            package_path = (
                tmp_path
                / "artifacts"
                / "session"
                / "live_multiball_visual_package"
                / "fetch_visual_uat_package"
                / "package_summary.json"
            )
            package_path.parent.mkdir(parents=True, exist_ok=True)
            package_path.write_text(
                json.dumps(
                    {
                        "campaign_id": "live_multiball_visual_package",
                        "pass": True,
                        "mobile_watchable": True,
                        "onboard_camera_watchable": True,
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
                    "stdout": f"{multiball_gate.VISUAL_PACKAGE_MARKER}{package_path}\n",
                    "stderr": "",
                },
            )()
        mission_path = (
            tmp_path
            / "artifacts"
            / "session"
            / "fresh_multiball_session"
            / "golf_ball_circle_delivery"
            / f"run_{len(calls)}"
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

    summary = multiball_gate.run_gate(
        _args(
            campaign_id="live_multiball",
            dry_run=False,
            random_cases=1,
            balls_per_scene=3,
            fresh_dashboard_session=True,
            dashboard_url="http://127.0.0.1:8894",
        )
    )

    assert summary["pass"] is True
    assert len(calls) == 4
    assert len(stops) == 2
    assert summary["fresh_dashboard_session"] is True
    assert summary["live_execution_ready"] is True
    assert summary["compose_project"] == "fresh_multiball_project"
    assert summary["expected_session_id"] == "fresh_multiball_session"
    assert summary["live_fetch_to_pose_pass_count"] == 3
    assert summary["live_fetch_to_pose_fail_count"] == 0
    assert summary["visual_package_required"] is True
    assert summary["visual_package_pass"] is True
    assert summary["visual_package_summary_path"].endswith("fetch_visual_uat_package/package_summary.json")
    for step_command in calls[:3]:
        assert "--expected-session-id" in step_command
        assert step_command[step_command.index("--expected-session-id") + 1] == "fresh_multiball_session"
        assert "--compose-project" in step_command
        assert step_command[step_command.index("--compose-project") + 1] == "fresh_multiball_project"
    package_command = calls[-1]
    assert package_command.count("--mission-summary") == 3
    assert package_command.count("--visual-dir") == 1
    assert str(tmp_path / "artifacts" / "session" / "fresh_multiball_session" / "visual") in package_command
    assert all(row["mission"]["fetch_to_pose_pass"] for row in summary["step_rows"])
    assert all(row["fetch_to_pose_pass"] for row in summary["step_rows"])
    assert all(row["closest_approach_m"] == 0.18 for row in summary["step_rows"])
    assert all(row["shot_reason"] == "trajectory_intersects_delivery_radius" for row in summary["step_rows"])
    assert summary["scene_rows"][0]["delivered_ball_count"] == 3
    assert summary["scene_rows"][0]["remaining_ball_count"] == 0
    assert summary["scene_rows"][0]["fetch_to_pose_pass_count"] == 3
    assert summary["scene_rows"][0]["fetch_to_pose_fail_count"] == 0
    assert set(summary["scene_rows"][0]["delivered_ball_ids"]) == {"ball_1", "ball_2", "ball_3"}


def test_multiball_gate_persistent_scene_rows_preserve_live_replanning_counts(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)

    monkeypatch.setattr(
        replay_batch,
        "stop_dashboard_environment",
        lambda dashboard_url, *, timeout_s: {"request": {"ok": True}, "state": {"environment_state": "stopped"}},
    )
    monkeypatch.setattr(
        replay_batch,
        "start_dashboard_environment",
        lambda args: {
            "request": {"ok": True},
            "state": {
                "environment_state": "environment_ready",
                "phase": "environment_ready",
                "sim_gate_ready": True,
                "operator_view_ready": True,
                "compose_project": "persistent_project",
                "session_id": "persistent_session",
            },
        },
    )
    monkeypatch.setattr(
        multiball_gate,
        "prepare_persistent_field_scene",
        lambda **kwargs: {"pass": True, "reason": "persistent_field_ready", "balls": [], "robot_pose": {}},
    )

    def fake_materialize_replanning_rows(*args, **kwargs):
        rows = [
            {
                "scene_id": "seed20260606_multiball_scene01",
                "step_index": 1,
                "ball_id": "ball_2",
                "mission": {"fetch_to_pose_pass": True},
                "fetch_to_pose_pass": True,
                "returncode": 0,
            },
            {
                "scene_id": "seed20260606_multiball_scene01",
                "step_index": 2,
                "ball_id": "ball_1",
                "mission": {"fetch_to_pose_pass": False},
                "fetch_to_pose_pass": False,
                "returncode": 2,
            },
        ]
        return rows, {
            "enabled": True,
            "initial_ball_count": 3,
            "max_iterations": 3,
            "delivered_ball_ids": ["ball_2"],
            "remaining_ball_ids": ["ball_1", "ball_3"],
            "all_balls_delivered": False,
            "iterations": [],
        }

    monkeypatch.setattr(multiball_gate, "materialize_replanning_rows", fake_materialize_replanning_rows)

    summary = multiball_gate.run_gate(
        _args(
            campaign_id="persistent_counts",
            dry_run=False,
            random_cases=1,
            balls_per_scene=3,
            persistent_field=True,
            fresh_dashboard_session=True,
            no_visual_package=True,
            dashboard_url="http://127.0.0.1:8894",
        )
    )

    scene_row = summary["scene_rows"][0]
    assert summary["pass"] is False
    assert scene_row["pass"] is False
    assert scene_row["live_all_balls_delivered"] is False
    assert scene_row["delivered_ball_count"] == 1
    assert scene_row["remaining_ball_count"] == 2
    assert scene_row["delivered_ball_ids"] == ["ball_2"]
    assert scene_row["remaining_ball_ids"] == ["ball_1", "ball_3"]
    assert scene_row["fetch_to_pose_pass_count"] == 1
    assert scene_row["fetch_to_pose_fail_count"] == 1


def test_multiball_gate_accepts_watchable_retried_scene_visual_evidence(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)

    monkeypatch.setattr(
        replay_batch,
        "stop_dashboard_environment",
        lambda dashboard_url, *, timeout_s: {"request": {"ok": True}, "state": {"environment_state": "stopped"}},
    )
    monkeypatch.setattr(
        replay_batch,
        "start_dashboard_environment",
        lambda args: {
            "request": {"ok": True},
            "state": {
                "environment_state": "environment_ready",
                "phase": "environment_ready",
                "sim_gate_ready": True,
                "operator_view_ready": True,
                "compose_project": "persistent_project",
                "session_id": "persistent_session",
            },
        },
    )
    monkeypatch.setattr(
        multiball_gate,
        "prepare_persistent_field_scene",
        lambda **kwargs: {"pass": True, "reason": "persistent_field_ready", "balls": [], "robot_pose": {}},
    )

    def fake_materialize_replanning_rows(*args, **kwargs):
        rows = [
            {
                "scene_id": "seed20260606_multiball_scene01",
                "step_index": 1,
                "ball_id": "ball_1",
                "mission_summary_path": "artifacts/session/persistent_session/golf_ball_circle_delivery/run_1/mission_verdict.json",
                "mission": {"fetch_to_pose_pass": False},
                "fetch_to_pose_pass": False,
                "returncode": 2,
            },
            {
                "scene_id": "seed20260606_multiball_scene01",
                "step_index": 2,
                "ball_id": "ball_1",
                "mission_summary_path": "artifacts/session/persistent_session/golf_ball_circle_delivery/run_2/mission_verdict.json",
                "mission": {"fetch_to_pose_pass": True},
                "fetch_to_pose_pass": True,
                "returncode": 0,
            },
            {
                "scene_id": "seed20260606_multiball_scene01",
                "step_index": 3,
                "ball_id": "ball_2",
                "mission_summary_path": "artifacts/session/persistent_session/golf_ball_circle_delivery/run_3/mission_verdict.json",
                "mission": {"fetch_to_pose_pass": True},
                "fetch_to_pose_pass": True,
                "returncode": 0,
            },
        ]
        return rows, {
            "enabled": True,
            "initial_ball_count": 2,
            "max_iterations": 3,
            "delivered_ball_ids": ["ball_1", "ball_2"],
            "remaining_ball_ids": [],
            "all_balls_delivered": True,
            "iterations": [],
        }

    def fake_run_command(command, *, timeout_s):
        package_path = (
            tmp_path
            / "artifacts"
            / "session"
            / "retried_multiball_visual_package"
            / "fetch_visual_uat_package"
            / "package_summary.json"
        )
        package_path.parent.mkdir(parents=True, exist_ok=True)
        package_path.write_text(
            json.dumps(
                {
                    "pass": False,
                    "mobile_watchable": True,
                    "onboard_camera_watchable": True,
                    "local_fetch_visual_confirmed": True,
                    "keyframe_reviews": [{"ok": True, "session_id": "persistent_session"}],
                    "warnings": ["planner_gate_not_green"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=f"{multiball_gate.VISUAL_PACKAGE_MARKER}{package_path}\n",
            stderr="",
        )

    monkeypatch.setattr(multiball_gate, "materialize_replanning_rows", fake_materialize_replanning_rows)
    monkeypatch.setattr(multiball_gate, "run_command", fake_run_command)

    summary = multiball_gate.run_gate(
        _args(
            campaign_id="retried_visual",
            dry_run=False,
            random_cases=1,
            balls_per_scene=2,
            persistent_field=True,
            fresh_dashboard_session=True,
            dashboard_url="http://127.0.0.1:8894",
        )
    )

    assert summary["visual_package_pass"] is False
    assert summary["multiball_visual_evidence_pass"] is True
    assert summary["visual_package_effective_pass"] is True
    assert summary["live_fetch_to_pose_pass_count"] == 2
    assert summary["live_fetch_to_pose_fail_count"] == 1
    assert summary["scene_rows"][0]["pass"] is True
    assert summary["pass"] is True


def test_multiball_gate_can_package_before_blocking_dashboard_stop(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    calls = []
    stops = []

    def fake_stop_dashboard_environment(dashboard_url, *, timeout_s):
        stops.append((dashboard_url, timeout_s))
        return {"request": {"ok": True}, "state": {"environment_state": "stopped"}}

    def fake_start_dashboard_environment(args):
        return {
            "request": {"ok": True},
            "state": {
                "environment_state": "environment_ready",
                "phase": "environment_ready",
                "sim_gate_ready": True,
                "operator_view_ready": True,
                "compose_project": "fresh_multiball_project",
                "session_id": "fresh_multiball_session",
            },
        }

    def fake_run_command(command, *, timeout_s):
        calls.append(command)
        if "fetch_visual_uat_package.py" in " ".join(command):
            package_path = (
                tmp_path
                / "artifacts"
                / "session"
                / "live_multiball_visual_package"
                / "fetch_visual_uat_package"
                / "package_summary.json"
            )
            _write_json(package_path, {"pass": True, "mobile_watchable": True, "onboard_camera_watchable": True})
            return subprocess.CompletedProcess(command, 0, stdout=f"{multiball_gate.VISUAL_PACKAGE_MARKER}{package_path}\n", stderr="")
        mission_path = (
            tmp_path
            / "artifacts"
            / "session"
            / "fresh_multiball_session"
            / "golf_ball_circle_delivery"
            / f"run_{len(calls)}"
            / "mission_verdict.json"
        )
        _write_json(
            mission_path,
            {
                "pass": True,
                "fetch_to_pose_pass": True,
                "scenario_id": "fetch_multiball_retrieval_v1",
                "scenario_label": "Multi-Ball Retrieval v1",
                "shot_outcome": {"closest_approach_distance_m": 0.18},
            },
        )
        return subprocess.CompletedProcess(command, 0, stdout=f"{multiball_gate.MISSION_SUMMARY_MARKER}{mission_path}\n", stderr="")

    monkeypatch.setattr(replay_batch, "stop_dashboard_environment", fake_stop_dashboard_environment)
    monkeypatch.setattr(replay_batch, "start_dashboard_environment", fake_start_dashboard_environment)
    monkeypatch.setattr(multiball_gate, "run_command", fake_run_command)

    summary = multiball_gate.run_gate(
        _args(
            campaign_id="live_multiball_skip_stop_before_package",
            dry_run=False,
            random_cases=1,
            balls_per_scene=3,
            fresh_dashboard_session=True,
            skip_dashboard_stop_before_package=True,
            dashboard_url="http://127.0.0.1:8894",
        )
    )

    assert summary["pass"] is True
    assert summary["skip_dashboard_stop_before_package"] is True
    assert len(stops) == 1
    assert len(calls) == 4
    assert summary["dashboard_stop_before_package"] == {}
    assert summary["visual_package_pass"] is True


def test_multiball_gate_fresh_session_per_scene_isolates_random_scenes(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    starts = []
    stops = []
    calls = []

    def fake_stop_dashboard_environment(dashboard_url, *, timeout_s):
        stops.append((dashboard_url, timeout_s))
        return {"request": {"ok": True}, "state": {"environment_state": "stopped"}}

    def fake_start_dashboard_environment(args):
        starts.append(dict(index=len(starts) + 1))
        index = len(starts)
        return {
            "request": {"ok": True},
            "state": {
                "environment_state": "environment_ready",
                "phase": "environment_ready",
                "sim_gate_ready": True,
                "operator_view_ready": True,
                "compose_project": f"fresh_scene_project_{index}",
                "session_id": f"fresh_scene_session_{index}",
            },
        }

    def fake_run_command(command, *, timeout_s):
        calls.append(command)
        session_id = command[command.index("--expected-session-id") + 1]
        mission_path = (
            tmp_path
            / "artifacts"
            / "session"
            / session_id
            / "golf_ball_circle_delivery"
            / f"run_{len(calls)}"
            / "mission_verdict.json"
        )
        _write_json(
            mission_path,
            {
                "pass": True,
                "fetch_to_pose_pass": True,
                "scenario_id": "fetch_multiball_retrieval_v1",
                "scenario_label": "Multi-Ball Retrieval v1",
                "shot_outcome": {"closest_approach_distance_m": 0.2},
                "approach_contact_metrics": {"flags": [], "first_contact_quality_flags": []},
            },
        )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=f"{multiball_gate.MISSION_SUMMARY_MARKER}{mission_path}\n",
            stderr="",
        )

    monkeypatch.setattr(replay_batch, "stop_dashboard_environment", fake_stop_dashboard_environment)
    monkeypatch.setattr(replay_batch, "start_dashboard_environment", fake_start_dashboard_environment)
    monkeypatch.setattr(multiball_gate, "run_command", fake_run_command)

    summary = multiball_gate.run_gate(
        _args(
            campaign_id="fresh_session_per_scene",
            dry_run=False,
            random_cases=2,
            balls_per_scene=1,
            fresh_dashboard_session=True,
            fresh_session_per_scene=True,
            no_visual_package=True,
            dashboard_url="http://127.0.0.1:8894",
        )
    )

    assert summary["pass"] is True
    assert summary["fresh_session_per_scene"] is True
    assert len(starts) == 2
    assert len(stops) == 4
    assert [row["expected_session_id"] for row in summary["scene_rows"]] == [
        "fresh_scene_session_1",
        "fresh_scene_session_2",
    ]
    assert {row["expected_session_id"] for row in summary["step_rows"]} == {
        "fresh_scene_session_1",
        "fresh_scene_session_2",
    }
    assert {row["compose_project"] for row in summary["step_rows"]} == {
        "fresh_scene_project_1",
        "fresh_scene_project_2",
    }
