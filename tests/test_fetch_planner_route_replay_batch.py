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
        "allow_operator_view_degraded": False,
        "world_file": "yolo_test_world_v6_calibrated_golf_turf.world",
        "surface_profile": "calibrated_golf_turf",
        "robot_sdf_name": "jetbot_core_ignition_v1.7.0.sdf",
        "env_ready_timeout_s": 420.0,
        "env_stop_timeout_s": 90.0,
        "fetch_delivery_radius_m": 0.3,
        "route_only_sample_duration_s": 5.0,
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


def test_replay_batch_dry_run_can_materialize_planner_only_route_proofs(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(batch, "SESSION_ROOT", tmp_path / "artifacts" / "session")

    gate_root = tmp_path / "artifacts" / "session" / "gate" / gate.PLANNER_GATE_KIND
    scenes = gate.generate_random_scenes(seed=20260633, random_cases=30)
    results = []
    for scene in scenes:
        scene_path = gate_root / "scene_descriptors" / f"{scene['scene_id']}.json"
        _write_json(scene_path, scene)
        decision = gate.decide_scene(scene)
        results.append({**decision, "scene_path": str(scene_path)})
    gate_summary = gate_root / "gate_summary.json"
    _write_json(gate_summary, {"results": results})

    summary = batch.run_batch(
        _make_args(
            gate_summary=str(gate_summary),
            route=[gate.ROUTE_SCAN_OR_PERCEIVE, gate.ROUTE_NO_GO],
            max_per_route=1,
            dry_run=True,
        )
    )

    assert summary["pass"] is True
    assert summary["selected_count"] == 2
    assert summary["requested_route_count"] == {
        gate.ROUTE_SCAN_OR_PERCEIVE: 1,
        gate.ROUTE_NO_GO: 1,
    }
    assert all(row["planner_only_route"] is True for row in summary["rows"])
    for row in summary["rows"]:
        assert "--planner-route-only-proof" in row["command"]
        assert row["command"][row["command"].index("--drive-linear-x-mps") + 1] == "0.000000"
        assert row["command"][row["command"].index("--sample-duration-s") + 1] == "5.000000"


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


def test_replay_batch_live_mock_records_planner_only_route_package(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(batch, "SESSION_ROOT", tmp_path / "artifacts" / "session")

    gate_root = tmp_path / "artifacts" / "session" / "gate" / gate.PLANNER_GATE_KIND
    scene = next(
        item
        for item in gate.generate_random_scenes(seed=20260633, random_cases=30)
        if item["expected_route_label"] == gate.ROUTE_NO_GO
    )
    scene_path = gate_root / "scene_descriptors" / f"{scene['scene_id']}.json"
    _write_json(scene_path, scene)
    decision = gate.decide_scene(scene)
    gate_summary = gate_root / "gate_summary.json"
    _write_json(gate_summary, {"results": [{**decision, "scene_path": str(scene_path)}]})

    def fake_run(command, *, timeout_s):
        command_text = " ".join(command)
        if "golf_ball_circle_delivery_demo_runner.py" in command_text:
            assert "--planner-route-only-proof" in command
            mission = (
                tmp_path
                / "artifacts"
                / "session"
                / "session_route_only"
                / "golf_ball_circle_delivery"
                / "run"
                / "mission_verdict.json"
            )
            _write_json(
                mission,
                {
                    "type": "planner_route_only_proof",
                    "pass": True,
                    "fetch_to_pose_pass": False,
                    "planner_route_only_pass": True,
                    "local_fetch_dispatched": False,
                    "planner_route_executed": True,
                    "planner_route_label": gate.ROUTE_NO_GO,
                    "route_executor": gate.ROUTE_EXECUTOR_NO_GO,
                    "planner_route_execution": {
                        "route_label": gate.ROUTE_NO_GO,
                        "route_executor": gate.ROUTE_EXECUTOR_NO_GO,
                        "route_executed": True,
                        "outcome": "safe_no_go_selected",
                    },
                    "shot_outcome": {
                        "reason": "planner_route_only_local_fetch_withheld",
                        "closest_approach_distance_m": 0.733,
                    },
                },
            )
            return type("Completed", (), {"returncode": 0, "stdout": f"{batch.MISSION_SUMMARY_MARKER}{mission}\n", "stderr": ""})()
        assert "fetch_visual_uat_package.py" in command_text
        assert "--route-only-proof" in command
        package_summary = (
            tmp_path
            / "artifacts"
            / "session"
            / "route_only_package"
            / "fetch_visual_uat_package"
            / "package_summary.json"
        )
        _write_json(
            package_summary,
            {
                "campaign_id": "route_only_package",
                "pass": True,
                "route_only_proof": True,
                "scorecard_path": "artifacts/session/route_only_package/fetch_visual_uat_package/scorecard.md",
            },
        )
        return type("Completed", (), {"returncode": 0, "stdout": f"{batch.VISUAL_PACKAGE_MARKER}{package_summary}\n", "stderr": ""})()

    monkeypatch.setattr(batch, "_run_command", fake_run)

    summary = batch.run_batch(
        _make_args(
            gate_summary=str(gate_summary),
            route=[gate.ROUTE_NO_GO],
            max_per_route=1,
            dry_run=False,
        )
    )

    assert summary["pass"] is True
    assert summary["mission_pass_count"] == 0
    assert summary["route_only_pass_count"] == 1
    assert summary["route_success_count"] == 1
    assert summary["visual_package_pass_count"] == 1
    assert summary["rows"][0]["planner_only_route"] is True
    assert summary["rows"][0]["mission"]["planner_route_only_pass"] is True
    assert summary["rows"][0]["visual_package"]["route_only_proof"] is True


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
                "phase": "environment_ready",
                "sim_gate_ready": True,
                "world_stream_ready": True,
                "operator_view_ready": True,
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


def test_dashboard_environment_ready_accepts_operator_view_degraded_only_when_allowed():
    state = {
        "environment_state": "environment_ready",
        "phase": "environment_ready",
        "sim_gate_ready": True,
        "world_stream_ready": True,
        "operator_view_ready": False,
        "operator_view_required": False,
        "operator_view_status": "degraded",
    }

    assert batch.dashboard_environment_ready(state) is False
    assert batch.dashboard_environment_ready(state, allow_operator_view_degraded=True) is True

    state["operator_view_status"] = "error"
    assert batch.dashboard_environment_ready(state, allow_operator_view_degraded=True) is True

    state["operator_view_status"] = "degraded_optional"
    assert batch.dashboard_environment_ready(state, allow_operator_view_degraded=True) is True

    state["operator_view_required"] = True
    assert batch.dashboard_environment_ready(state, allow_operator_view_degraded=True) is False


def test_dashboard_environment_ready_trusts_dashboard_after_world_stream_goes_stale():
    state = {
        "environment_state": "environment_ready",
        "phase": "environment_ready",
        "sim_gate_ready": True,
        "world_stream_ready": False,
        "world_stream_renderable": False,
        "operator_view_ready": False,
        "operator_view_required": False,
        "operator_view_status": "degraded",
    }

    assert batch.dashboard_environment_ready(state, allow_operator_view_degraded=True) is True


def test_start_dashboard_environment_can_request_operator_view_degraded(monkeypatch):
    posted = {}

    def fake_post(dashboard_url, path, payload, *, timeout_s):
        posted.update(
            {
                "dashboard_url": dashboard_url,
                "path": path,
                "payload": payload,
                "timeout_s": timeout_s,
            }
        )
        return {"ok": True}

    def fake_wait(dashboard_url, *, timeout_s, poll_s, want_ready, allow_operator_view_degraded, **_kwargs):
        assert dashboard_url == "http://dash"
        assert want_ready is True
        assert allow_operator_view_degraded is True
        return {
            "environment_state": "environment_ready",
            "phase": "environment_ready",
            "sim_gate_ready": True,
            "world_stream_ready": True,
            "operator_view_ready": False,
            "operator_view_required": False,
            "visual_evidence_required": True,
            "operator_view_status": "degraded",
        }

    monkeypatch.setattr(batch, "post_dashboard_json", fake_post)
    monkeypatch.setattr(batch, "wait_for_dashboard_state", fake_wait)

    result = batch.start_dashboard_environment(
        _make_args(
            dashboard_url="http://dash",
            allow_operator_view_degraded=True,
        )
    )

    assert posted["path"] == "/api/env/start"
    assert posted["payload"]["operator_view_required"] is False
    assert posted["payload"]["visual_evidence_required"] is True
    assert result["state"]["operator_view_status"] == "degraded"


def test_start_dashboard_environment_skips_visual_evidence_when_no_package(monkeypatch):
    posted = {}

    def fake_post(dashboard_url, path, payload, *, timeout_s):
        posted.update({"payload": payload})
        return {"ok": True}

    monkeypatch.setattr(batch, "post_dashboard_json", fake_post)
    monkeypatch.setattr(
        batch,
        "wait_for_dashboard_state",
        lambda *_args, **_kwargs: {
            "environment_state": "environment_ready",
            "phase": "environment_ready",
            "sim_gate_ready": True,
            "operator_view_ready": False,
            "operator_view_required": False,
            "operator_view_status": "degraded_optional",
            "visual_evidence_required": False,
        },
    )

    batch.start_dashboard_environment(
        _make_args(
            dashboard_url="http://dash",
            allow_operator_view_degraded=True,
            no_visual_package=True,
        )
    )

    assert posted["payload"]["operator_view_required"] is False
    assert posted["payload"]["visual_evidence_required"] is False


def test_replay_batch_records_dashboard_start_failure_reason(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(batch, "SESSION_ROOT", tmp_path / "artifacts" / "session")

    gate_root = tmp_path / "artifacts" / "session" / "gate" / gate.PLANNER_GATE_KIND
    scene = next(
        item
        for item in gate.generate_random_scenes(seed=20260613, random_cases=10)
        if item["expected_route_label"] == gate.ROUTE_FETCH_READY
    )
    scene_path = gate_root / "scene_descriptors" / f"{scene['scene_id']}.json"
    _write_json(scene_path, scene)
    decision = gate.decide_scene(scene)
    gate_summary = gate_root / "gate_summary.json"
    _write_json(gate_summary, {"results": [{**decision, "scene_path": str(scene_path)}]})

    monkeypatch.setattr(batch, "stop_dashboard_environment", lambda *_args, **_kwargs: {"state": {"environment_state": "stopped"}})
    monkeypatch.setattr(
        batch,
        "start_dashboard_environment",
        lambda _args: {
            "request": {"ok": True},
            "state": {
                "environment_state": "error",
                "phase": "environment_starting",
                "last_error": "Truth probe did not report robot visibility.",
            },
        },
    )

    def fail_run(_command, *, timeout_s):
        raise AssertionError("dashboard start failure should not launch the live runner")

    monkeypatch.setattr(batch, "_run_command", fail_run)

    summary = batch.run_batch(
        _make_args(
            gate_summary=str(gate_summary),
            dashboard_url="http://dash",
            fresh_dashboard_session_per_run=True,
            max_per_route=1,
            dry_run=False,
            stop_on_fail=True,
        )
    )

    assert summary["pass"] is False
    assert summary["selected_count"] == 1
    assert summary["rows"][0]["returncode"] == -1
    assert "environment_state=error" in summary["rows"][0]["failure_reason"]
    assert "Truth probe did not report robot visibility." in summary["rows"][0]["failure_reason"]


def test_wait_for_dashboard_state_returns_start_error_without_full_timeout(monkeypatch):
    monkeypatch.setattr(
        batch,
        "dashboard_state",
        lambda *_args, **_kwargs: {
            "environment_state": "error",
            "phase": "environment_starting",
            "last_error": "Truth probe did not report robot visibility.",
        },
    )

    def fail_sleep(_duration):
        raise AssertionError("error state should return before sleeping")

    monkeypatch.setattr(batch.time, "sleep", fail_sleep)

    state = batch.wait_for_dashboard_state("http://dash", timeout_s=420.0, want_ready=True)

    assert state["environment_state"] == "error"
    assert "Truth probe" in state["last_error"]
