import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_planner_handoff_gate as gate  # noqa: E402
import fetch_planner_route_replay_batch as batch  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _make_args(**overrides):
    payload = {
        "campaign_id": "batch",
        "gate_summary": "",
        "route": [],
        "scene_id": [],
        "skip_scene_id": [],
        "max_per_route": 1,
        "quality_order": "source",
        "dry_run": True,
        "dashboard_url": "",
        "compose_project": "",
        "fresh_dashboard_session_per_run": False,
        "world_file": "yolo_test_world_v6_calibrated_golf_turf.world",
        "surface_profile": "calibrated_golf_turf",
        "robot_sdf_name": "jetbot_core_ignition_v1.7.0.sdf",
        "env_ready_timeout_s": 420.0,
        "env_stop_timeout_s": 90.0,
        "fetch_delivery_radius_m": 0.3,
        "python_exe": sys.executable,
        "timeout_s": 180.0,
        "package_timeout_s": 120.0,
        "no_visual_package": False,
        "resume_skip_existing": False,
        "stop_on_fail": False,
    }
    payload.update(overrides)
    return type("Args", (), payload)()


def test_replay_batch_dry_run_materializes_one_layout_per_route(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(batch, "SESSION_ROOT", tmp_path / "artifacts" / "session")

    gate_root = tmp_path / "artifacts" / "session" / "gate" / gate.PLANNER_GATE_KIND
    scenes = gate.generate_random_scenes(seed=20260609, random_cases=20)
    results = []
    for scene in scenes:
        scene_path = gate_root / "scene_descriptors" / f"{scene['scene_id']}.json"
        _write_json(scene_path, scene)
        decision = gate.decide_scene(scene)
        results.append({**decision, "scene_path": str(scene_path)})
    gate_summary = gate_root / "gate_summary.json"
    _write_json(gate_summary, {"results": results})

    summary = batch.run_batch(_make_args(gate_summary=str(gate_summary), max_per_route=1, dry_run=True))

    assert summary["pass"] is True
    assert summary["dry_run"] is True
    assert summary["selected_count"] == 3
    assert summary["requested_route_count"] == {
        gate.ROUTE_FETCH_READY: 1,
        gate.ROUTE_NAV2_REPOSITION: 1,
        gate.ROUTE_RECOVERY_OR_REAIM: 1,
    }
    for row in summary["rows"]:
        layout_path = tmp_path / row["layout_path"]
        assert layout_path.is_file()
        layout = json.loads(layout_path.read_text(encoding="utf-8"))
        assert layout["planner_route_label"] == row["route_label"]
        assert "--target-layout-json" in row["command"]
        assert row["command"][row["command"].index("--target-layout-json") + 1] == str(layout_path)


def test_replay_batch_quality_order_selects_roughest_per_route():
    rows = [
        {
            "scene_id": "fetch_clean",
            "route_label": gate.ROUTE_FETCH_READY,
            "correct": True,
            "route_quality": {"quality_score": 95.0},
        },
        {
            "scene_id": "fetch_rough",
            "route_label": gate.ROUTE_FETCH_READY,
            "correct": True,
            "route_quality": {"quality_score": 52.0},
        },
        {
            "scene_id": "recovery_cleaner",
            "route_label": gate.ROUTE_RECOVERY_OR_REAIM,
            "correct": True,
            "route_quality": {"quality_score": 70.0},
        },
        {
            "scene_id": "recovery_rough",
            "route_label": gate.ROUTE_RECOVERY_OR_REAIM,
            "correct": True,
            "route_quality": {"quality_score": 40.0},
        },
    ]

    selected = batch.select_executable_results(
        rows,
        routes={gate.ROUTE_FETCH_READY, gate.ROUTE_RECOVERY_OR_REAIM},
        max_per_route=1,
        scene_ids=set(),
        skip_scene_ids=set(),
        quality_order="roughest",
    )

    assert {row["scene_id"] for row in selected} == {"fetch_rough", "recovery_rough"}


def test_replay_batch_live_mock_records_mission_and_visual_package(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(batch, "SESSION_ROOT", tmp_path / "artifacts" / "session")

    gate_root = tmp_path / "artifacts" / "session" / "gate" / gate.PLANNER_GATE_KIND
    scene = next(
        item
        for item in gate.generate_random_scenes(seed=20260610, random_cases=10)
        if item["expected_route_label"] == gate.ROUTE_FETCH_READY
    )
    scene_path = gate_root / "scene_descriptors" / f"{scene['scene_id']}.json"
    _write_json(scene_path, scene)
    decision = gate.decide_scene(scene)
    gate_summary = gate_root / "gate_summary.json"
    _write_json(gate_summary, {"results": [{**decision, "scene_path": str(scene_path)}]})

    def fake_run(command, *, timeout_s):
        command_text = " ".join(command)
        if "golf_ball_circle_delivery_demo_runner.py" in command_text:
            mission = tmp_path / "artifacts" / "session" / "session_a" / "golf_ball_circle_delivery" / "run" / "mission_verdict.json"
            _write_json(
                mission,
                {
                    "pass": True,
                    "fetch_to_pose_pass": True,
                    "planner_route_label": gate.ROUTE_FETCH_READY,
                    "route_executor": gate.ROUTE_EXECUTOR_LOCAL_FETCH,
                    "forward_only_pre_contact": True,
                    "shot_outcome": {
                        "reason": "trajectory_intersects_delivery_radius",
                        "closest_approach_distance_m": 0.196,
                    },
                    "approach_contact_metrics": {
                        "flags": [],
                        "first_contact_quality_flags": [],
                        "stable_contact_approach_pass": True,
                        "first_contact_quality_pass": True,
                    },
                },
            )
            return type("Completed", (), {"returncode": 0, "stdout": f"{batch.MISSION_SUMMARY_MARKER}{mission}\n", "stderr": ""})()
        package_summary = tmp_path / "artifacts" / "session" / "package" / "fetch_visual_uat_package" / "package_summary.json"
        _write_json(
            package_summary,
            {
                "campaign_id": "package",
                "pass": True,
                "scorecard_path": "artifacts/session/package/fetch_visual_uat_package/scorecard.md",
            },
        )
        return type("Completed", (), {"returncode": 0, "stdout": f"{batch.VISUAL_PACKAGE_MARKER}{package_summary}\n", "stderr": ""})()

    monkeypatch.setattr(batch, "_run_command", fake_run)

    summary = batch.run_batch(_make_args(gate_summary=str(gate_summary), max_per_route=1, dry_run=False))

    assert summary["pass"] is True
    assert summary["mission_pass_count"] == 1
    assert summary["visual_package_pass_count"] == 1
    assert summary["rows"][0]["mission"]["closest_approach_distance_m"] == 0.196
    assert summary["rows"][0]["visual_package"]["pass"] is True


def test_replay_batch_resume_skip_existing_visual_package(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(batch, "SESSION_ROOT", tmp_path / "artifacts" / "session")

    gate_root = tmp_path / "artifacts" / "session" / "gate" / gate.PLANNER_GATE_KIND
    scene = next(
        item
        for item in gate.generate_random_scenes(seed=20260612, random_cases=10)
        if item["expected_route_label"] == gate.ROUTE_FETCH_READY
    )
    scene_path = gate_root / "scene_descriptors" / f"{scene['scene_id']}.json"
    _write_json(scene_path, scene)
    decision = gate.decide_scene(scene)
    gate_summary = gate_root / "gate_summary.json"
    _write_json(gate_summary, {"results": [{**decision, "scene_path": str(scene_path)}]})

    campaign_id = "resume_campaign"
    mission = tmp_path / "artifacts" / "session" / "session_resume" / "golf_ball_circle_delivery" / "run" / "mission_verdict.json"
    _write_json(
        mission,
        {
            "pass": True,
            "fetch_to_pose_pass": True,
            "planner_route_label": gate.ROUTE_FETCH_READY,
            "route_executor": gate.ROUTE_EXECUTOR_LOCAL_FETCH,
            "shot_outcome": {
                "reason": "trajectory_intersects_delivery_radius",
                "closest_approach_distance_m": 0.192,
            },
            "approach_contact_metrics": {
                "flags": [],
                "first_contact_quality_flags": [],
                "stable_contact_approach_pass": True,
                "first_contact_quality_pass": True,
            },
        },
    )
    package_summary = (
        tmp_path
        / "artifacts"
        / "session"
        / f"{campaign_id}_{decision['scene_id']}"
        / "fetch_visual_uat_package"
        / "package_summary.json"
    )
    _write_json(
        package_summary,
        {
            "campaign_id": f"{campaign_id}_{decision['scene_id']}",
            "pass": True,
            "scorecard_path": f"artifacts/session/{campaign_id}_{decision['scene_id']}/fetch_visual_uat_package/scorecard.md",
            "missions": [{"path": str(mission)}],
        },
    )

    def fail_run(_command, *, timeout_s):
        raise AssertionError("resume should not launch live runner or package command")

    monkeypatch.setattr(batch, "_run_command", fail_run)

    summary = batch.run_batch(
        _make_args(
            campaign_id=campaign_id,
            gate_summary=str(gate_summary),
            max_per_route=1,
            dry_run=False,
            resume_skip_existing=True,
        )
    )

    assert summary["pass"] is True
    assert summary["selected_count"] == 1
    assert summary["skipped_existing_count"] == 1
    assert summary["mission_pass_count"] == 1
    assert summary["visual_package_pass_count"] == 1
    assert summary["rows"][0]["resume_skip_existing"] is True
    assert summary["rows"][0]["mission"]["closest_approach_distance_m"] == 0.192
    assert summary["rows"][0]["visual_package"]["pass"] is True


def test_replay_batch_fresh_dashboard_session_binds_visual_session(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(batch, "SESSION_ROOT", tmp_path / "artifacts" / "session")

    gate_root = tmp_path / "artifacts" / "session" / "gate" / gate.PLANNER_GATE_KIND
    scene = next(
        item
        for item in gate.generate_random_scenes(seed=20260611, random_cases=10)
        if item["expected_route_label"] == gate.ROUTE_FETCH_READY
    )
    scene_path = gate_root / "scene_descriptors" / f"{scene['scene_id']}.json"
    _write_json(scene_path, scene)
    decision = gate.decide_scene(scene)
    gate_summary = gate_root / "gate_summary.json"
    _write_json(gate_summary, {"results": [{**decision, "scene_path": str(scene_path)}]})

    stops = []

    def fake_stop(dashboard_url, *, timeout_s):
        stops.append((dashboard_url, timeout_s))
        return {"state": {"environment_state": "stopped"}}

    def fake_start(args):
        return {
            "state": {
                "session_id": "session_fresh",
                "compose_project": "project_fresh",
                "environment_state": "environment_ready",
            }
        }

    def fake_run(command, *, timeout_s):
        command_text = " ".join(command)
        if "golf_ball_circle_delivery_demo_runner.py" in command_text:
            assert "--expected-session-id" in command
            assert command[command.index("--expected-session-id") + 1] == "session_fresh"
            mission = tmp_path / "artifacts" / "session" / "session_fresh" / "golf_ball_circle_delivery" / "run" / "mission_verdict.json"
            _write_json(
                mission,
                {
                    "pass": True,
                    "fetch_to_pose_pass": True,
                    "session_id": "session_fresh",
                    "planner_route_label": gate.ROUTE_FETCH_READY,
                    "route_executor": gate.ROUTE_EXECUTOR_LOCAL_FETCH,
                    "shot_outcome": {
                        "reason": "trajectory_intersects_delivery_radius",
                        "closest_approach_distance_m": 0.19,
                    },
                    "approach_contact_metrics": {},
                },
            )
            return type("Completed", (), {"returncode": 0, "stdout": f"{batch.MISSION_SUMMARY_MARKER}{mission}\n", "stderr": ""})()
        package_summary = tmp_path / "artifacts" / "session" / "package" / "fetch_visual_uat_package" / "package_summary.json"
        _write_json(package_summary, {"campaign_id": "package", "pass": True})
        return type("Completed", (), {"returncode": 0, "stdout": f"{batch.VISUAL_PACKAGE_MARKER}{package_summary}\n", "stderr": ""})()

    monkeypatch.setattr(batch, "stop_dashboard_environment", fake_stop)
    monkeypatch.setattr(batch, "start_dashboard_environment", fake_start)
    monkeypatch.setattr(batch, "_run_command", fake_run)

    summary = batch.run_batch(
        _make_args(
            gate_summary=str(gate_summary),
            dashboard_url="http://dash",
            fresh_dashboard_session_per_run=True,
            max_per_route=1,
            dry_run=False,
        )
    )

    assert summary["pass"] is True
    assert stops
    assert summary["rows"][0]["expected_session_id"] == "session_fresh"
    assert summary["rows"][0]["compose_project"] == "project_fresh"
    assert summary["rows"][0]["mission"]["session_id"] == "session_fresh"
