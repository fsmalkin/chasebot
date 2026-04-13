from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_mission_runner as gather_runner  # noqa: E402
from llm_supervisor_core import read_json  # noqa: E402


def _make_args(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        dashboard_url="http://127.0.0.1:8860",
        provider="local_stub",
        model="local-stub",
        reasoning_effort="low",
        scenario_id="corral_single_ball_place",
        scenario_label="Corral Single Ball Place",
        artifact_kind="gather_mission",
        poll_s=0.01,
        timeout_s=1.0,
        environment_timeout_s=1.0,
        visit_timeout_s=1.0,
        capture_timeout_s=1.0,
        place_timeout_s=1.0,
        pursuit_settle_timeout_s=0.01,
        max_retries_per_target=0,
        max_place_loss_revisits=1,
        target_model_name="visit_mission_target",
        target_model_sdf=str(tmp_path / "ball.sdf"),
        zone_model_name="corral_zone_marker",
        zone_model_sdf=str(tmp_path / "zone.sdf"),
        visit_runtime_json=str(tmp_path / "visit_mission_runtime.json"),
        gather_runtime_json=str(tmp_path / "gather_mission_runtime.json"),
        motion_loop_hz=10.0,
        keep_environment=True,
    )


def _make_runner(tmp_path: Path, monkeypatch) -> gather_runner.GatherMissionRunner:
    monkeypatch.setattr(gather_runner, "choose_docker_cli", lambda: "docker")
    return gather_runner.GatherMissionRunner(_make_args(tmp_path))


def test_resolve_gather_runtime_state_path_prefers_explicit_arg(tmp_path, monkeypatch):
    env_path = tmp_path / "env_runtime.json"
    monkeypatch.setenv("CHASECAR_GATHER_RUNTIME_PATH", str(env_path))
    explicit_path = tmp_path / "explicit_runtime.json"

    resolved = gather_runner.resolve_gather_runtime_state_path(str(explicit_path))

    assert resolved == explicit_path.resolve()


def test_resolve_gather_runtime_state_path_falls_back_to_env(tmp_path, monkeypatch):
    env_path = tmp_path / "env_runtime.json"
    monkeypatch.setenv("CHASECAR_GATHER_RUNTIME_PATH", str(env_path))

    resolved = gather_runner.resolve_gather_runtime_state_path("")

    assert resolved == env_path.resolve()


def test_init_runtime_state_seeds_dashboard_friendly_fields(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)

    runner._init_runtime_state(session_id="session-1", mission_root=mission_root)

    assert runner.visit_runtime_state["proof_state"] == "waiting"
    assert runner.visit_runtime_state["artifact_dir"] == str(mission_root)
    assert runner.gather_runtime_state["gather_phase"] == "setup"
    assert runner.gather_runtime_state["zone_pose"]["radius_m"] > 0.0
    assert runner.gather_runtime_state["artifact_dir"] == str(mission_root)


def test_run_normalizes_success_summary_and_marks_proof_completed(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    monkeypatch.setattr(gather_runner, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gather_runner, "current_utc_stamp", lambda: "20260412T000000Z")

    ready_state = {"session_id": "session-1", "compose_project": "proj", "world_name": "yolo_test_world"}
    monkeypatch.setattr(runner, "_ensure_environment_ready", lambda: (ready_state, False))
    monkeypatch.setattr(runner, "_wait_for_robot_pose", lambda timeout_s: ready_state)
    monkeypatch.setattr(runner, "_safe_stop", lambda: None)
    monkeypatch.setattr(runner, "_wait_for_pursuit_quiet", lambda timeout_s: None)
    monkeypatch.setattr(runner, "_spawn_mission_models", lambda ready_state, mission_root: None)
    monkeypatch.setattr(runner, "_wait_for_truth_models", lambda session_id, expected_truth_models, timeout_s: None)
    monkeypatch.setattr(runner, "_start_motion_bridge", lambda compose_project, mission_root: None)
    monkeypatch.setattr(runner, "_stop_motion_bridge", lambda compose_project: None)
    monkeypatch.setattr(runner, "_clear_mission_models", lambda state: None)
    monkeypatch.setattr(runner, "_plan_collection_route", lambda remaining_ids, state: list(remaining_ids))
    def _run_target_success(**kwargs):
        runner.gather_runtime_state["placed_targets"] = ["ball_1"]
        runner.gather_runtime_state["remaining_targets"] = []
        runner.visit_runtime_state["visited_targets"] = ["ball_1"]
        return {
            "target_id": "ball_1",
            "label": "Ball 1",
            "pass": True,
            "attempts": 1,
            "capture_loss_count": 0,
            "route_index": 1,
            "placed": True,
            "final_ball_pose": {"x": 2.4, "y": 0.0, "z": 0.05},
            "place_time_s": 7.5,
        }

    monkeypatch.setattr(runner, "_run_target", _run_target_success)
    monkeypatch.setattr(
        gather_runner,
        "fetch_dashboard_state",
        lambda dashboard_url, timeout_s=0: {"belief": {"latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0}}},
    )

    summary = runner.run()

    assert summary["pass"] is True
    assert summary["placed_count"] == 1
    verdict = read_json(Path(summary["mission_verdict_path"]))
    assert verdict["type"] == "gather_mission"
    assert verdict["route_order"] == ["ball_1"]
    assert Path(summary["scorecard_path"]).exists()
    assert runner.visit_runtime_state["proof_state"] == "completed"
    assert runner.gather_runtime_state["gather_phase"] == "completed"


def test_run_normalizes_failure_summary_and_marks_proof_failed(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    monkeypatch.setattr(gather_runner, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gather_runner, "current_utc_stamp", lambda: "20260412T000001Z")

    ready_state = {"session_id": "session-2", "compose_project": "proj", "world_name": "yolo_test_world"}
    monkeypatch.setattr(runner, "_ensure_environment_ready", lambda: (ready_state, False))
    monkeypatch.setattr(runner, "_wait_for_robot_pose", lambda timeout_s: ready_state)
    monkeypatch.setattr(runner, "_safe_stop", lambda: None)
    monkeypatch.setattr(runner, "_wait_for_pursuit_quiet", lambda timeout_s: None)
    monkeypatch.setattr(runner, "_spawn_mission_models", lambda ready_state, mission_root: None)
    monkeypatch.setattr(runner, "_wait_for_truth_models", lambda session_id, expected_truth_models, timeout_s: None)
    monkeypatch.setattr(runner, "_start_motion_bridge", lambda compose_project, mission_root: None)
    monkeypatch.setattr(runner, "_stop_motion_bridge", lambda compose_project: None)
    monkeypatch.setattr(runner, "_clear_mission_models", lambda state: None)
    monkeypatch.setattr(runner, "_plan_collection_route", lambda remaining_ids, state: list(remaining_ids))
    monkeypatch.setattr(
        runner,
        "_run_target",
        lambda **kwargs: {
            "target_id": "ball_1",
            "label": "Ball 1",
            "pass": False,
            "failure_reason": "capture_lost",
            "attempts": 1,
            "capture_loss_count": 1,
            "route_index": 1,
        },
    )
    monkeypatch.setattr(
        gather_runner,
        "fetch_dashboard_state",
        lambda dashboard_url, timeout_s=0: {"belief": {"latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0}}},
    )

    summary = runner.run()

    assert summary["pass"] is False
    verdict = read_json(Path(summary["mission_verdict_path"]))
    assert verdict["mission_error"] == "capture_lost"
    assert runner.visit_runtime_state["proof_state"] == "failed"
    assert runner.gather_runtime_state["gather_phase"] == "failed"


def test_run_target_uses_full_revisit_after_capture_timeout_on_place_loss_recapture(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.max_retries_per_target = 2
    runner.args.max_place_loss_revisits = 1

    visit_dispatches: list[str] = []
    capture_zone_recovery_flags: list[bool] = []
    monkeypatch.setattr(runner, "_wait_for_nav2_ready", lambda timeout_s: None)
    monkeypatch.setattr(
        gather_runner,
        "fetch_dashboard_state",
        lambda dashboard_url, timeout_s=0: {
            "brain": {"last_feedback_status": "", "last_feedback_text": ""},
            "belief": {"latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0}},
        },
    )
    monkeypatch.setattr(runner, "_dispatch_visit_target", lambda target_id: visit_dispatches.append(target_id))
    monkeypatch.setattr(runner, "_wait_for_visit_result", lambda **kwargs: (True, {}, "visit_target_reached"))
    monkeypatch.setattr(runner, "_wait_for_pursuit_quiet", lambda timeout_s: None)
    monkeypatch.setattr(runner, "_safe_stop", lambda: None)
    monkeypatch.setattr(runner, "_ball_truth_pose", lambda session_id, target: {"x": 1.0, "y": 0.0, "z": 0.05})
    monkeypatch.setattr(runner, "_update_prior_from_ball_pose", lambda target_id, ball_pose: None)

    capture_results = [
        (True, {"capture_state": {"captured": True}, "zone_score": {}}),
        (False, {"failure_reason": "capture_timeout", "failure_stage": "capture"}),
        (False, {"failure_reason": "capture_timeout", "failure_stage": "capture"}),
    ]
    place_results = [
        (False, {"failure_reason": "capture_lost", "failure_stage": "place", "local_recovery_attempted": True}),
    ]

    def _capture_target(**kwargs):
        capture_zone_recovery_flags.append(bool(kwargs.get("prefer_zone_recovery")))
        return capture_results.pop(0)

    monkeypatch.setattr(runner, "_capture_target", _capture_target)
    monkeypatch.setattr(runner, "_place_target", lambda **kwargs: place_results.pop(0))

    result = runner._run_target(
        session_id="session-1",
        target=runner.targets_by_id["ball_1"],
        route_index=1,
        gather_sequence_path=tmp_path / "gather_sequence.jsonl",
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=tmp_path / "mission",
    )

    assert result["pass"] is False
    assert result["failure_reason"] == "capture_timeout"
    assert result["failure_stage"] == "capture"
    assert result["attempt_kind"] == "place_loss_revisit"
    assert result["revisit_attempted"] is True
    assert visit_dispatches == ["ball_1", "ball_1"]
    assert capture_zone_recovery_flags == [False, True, False]


def test_place_target_bounds_local_recovery_and_keeps_zone_heading(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.place_timeout_s = 3.0
    runner.args.poll_s = 0.25
    mission_root = tmp_path / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    runner._init_runtime_state(session_id="session-1", mission_root=mission_root)

    clock = {"now": 0.0}

    def _fake_monotonic():
        return clock["now"]

    def _fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(gather_runner.time, "monotonic", _fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", _fake_sleep)

    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    captured_ball = {"x": 0.10, "y": 0.0, "z": 0.05}
    slipped_ball = {"x": 0.30, "y": 0.0, "z": 0.05}
    states = [
        ({}, robot_pose, captured_ball),
        ({}, robot_pose, slipped_ball),
        ({}, robot_pose, slipped_ball),
        ({}, robot_pose, slipped_ball),
        ({}, robot_pose, slipped_ball),
        ({}, robot_pose, slipped_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, robot_pose, slipped_ball

    command_log: list[dict[str, object]] = []
    monkeypatch.setattr(runner, "_control_loop_state", _control_loop_state)
    monkeypatch.setattr(runner, "_update_prior_from_ball_pose", lambda target_id, ball_pose: None)
    monkeypatch.setattr(
        runner,
        "_set_manual_drive",
        lambda enabled, linear_x=0.0, angular_z=0.0, mode="idle", rationale="": command_log.append(
            {
                "enabled": enabled,
                "linear_x": linear_x,
                "angular_z": angular_z,
                "mode": mode,
                "rationale": rationale,
            }
        ),
    )

    passed, payload = runner._place_target(
        session_id="session-1",
        target=runner.targets_by_id["ball_1"],
        state_history_path=tmp_path / "state_history.jsonl",
    )

    assert passed is False
    assert payload["failure_reason"] == "capture_lost"
    assert payload["failure_stage"] == "place"
    assert payload["local_recovery_attempted"] is True
    assert any(item["mode"] == "capture_recovery" for item in command_log)
    assert command_log[-1]["mode"] == "capture_lost"
    assert runner.gather_runtime_state["latest_control_command"]["mode"] == "capture_recovery"
    assert abs(float(runner.gather_runtime_state["latest_control_command"]["angular_z"])) <= 0.75


def test_place_target_switches_to_recovery_on_first_uncaptured_frame(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.place_timeout_s = 2.0
    runner.args.poll_s = 0.25
    mission_root = tmp_path / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    runner._init_runtime_state(session_id="session-1", mission_root=mission_root)

    clock = {"now": 0.0}

    def _fake_monotonic():
        return clock["now"]

    def _fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(gather_runner.time, "monotonic", _fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", _fake_sleep)

    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    states = [
        ({}, robot_pose, {"x": 0.10, "y": 0.0, "z": 0.05}),
        ({}, robot_pose, {"x": 0.26, "y": 0.0, "z": 0.05}),
        ({}, robot_pose, {"x": 2.40, "y": 0.0, "z": 0.05}),
        ({}, robot_pose, {"x": 2.40, "y": 0.0, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, robot_pose, {"x": 2.40, "y": 0.0, "z": 0.05}

    command_log: list[dict[str, object]] = []
    monkeypatch.setattr(runner, "_control_loop_state", _control_loop_state)
    monkeypatch.setattr(runner, "_update_prior_from_ball_pose", lambda target_id, ball_pose: None)
    monkeypatch.setattr(
        runner,
        "_set_manual_drive",
        lambda enabled, linear_x=0.0, angular_z=0.0, mode="idle", rationale="": command_log.append(
            {
                "enabled": enabled,
                "linear_x": linear_x,
                "angular_z": angular_z,
                "mode": mode,
                "rationale": rationale,
            }
        ),
    )

    passed, payload = runner._place_target(
        session_id="session-1",
        target=runner.targets_by_id["ball_1"],
        state_history_path=tmp_path / "state_history.jsonl",
    )

    assert passed is True
    assert "failure_reason" not in payload
    assert command_log[0]["mode"] == "place"
    assert any(item["mode"] == "capture_recovery" for item in command_log[1:])


def test_run_target_preserves_local_recovery_history_across_full_revisit_failure(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.max_retries_per_target = 2
    runner.args.max_place_loss_revisits = 1

    capture_zone_recovery_flags: list[bool] = []
    monkeypatch.setattr(runner, "_wait_for_nav2_ready", lambda timeout_s: None)
    monkeypatch.setattr(
        gather_runner,
        "fetch_dashboard_state",
        lambda dashboard_url, timeout_s=0: {
            "brain": {"last_feedback_status": "", "last_feedback_text": ""},
            "belief": {"latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0}},
        },
    )
    monkeypatch.setattr(runner, "_dispatch_visit_target", lambda target_id: None)
    monkeypatch.setattr(runner, "_wait_for_visit_result", lambda **kwargs: (True, {}, "visit_target_reached"))
    monkeypatch.setattr(runner, "_wait_for_pursuit_quiet", lambda timeout_s: None)
    monkeypatch.setattr(runner, "_safe_stop", lambda: None)
    monkeypatch.setattr(runner, "_ball_truth_pose", lambda session_id, target: {"x": 1.0, "y": 0.0, "z": 0.05})
    monkeypatch.setattr(runner, "_update_prior_from_ball_pose", lambda target_id, ball_pose: None)

    capture_results = [
        (True, {"capture_state": {"captured": True}, "zone_score": {}}),
        (False, {"failure_reason": "capture_timeout", "failure_stage": "capture"}),
        (False, {"failure_reason": "capture_timeout", "failure_stage": "capture"}),
    ]
    place_results = [
        (False, {"failure_reason": "capture_lost", "failure_stage": "place", "local_recovery_attempted": True}),
    ]

    def _capture_target(**kwargs):
        capture_zone_recovery_flags.append(bool(kwargs.get("prefer_zone_recovery")))
        return capture_results.pop(0)

    monkeypatch.setattr(runner, "_capture_target", _capture_target)
    monkeypatch.setattr(runner, "_place_target", lambda **kwargs: place_results.pop(0))

    result = runner._run_target(
        session_id="session-1",
        target=runner.targets_by_id["ball_1"],
        route_index=1,
        gather_sequence_path=tmp_path / "gather_sequence.jsonl",
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=tmp_path / "mission",
    )

    assert result["pass"] is False
    assert result["failure_reason"] == "capture_timeout"
    assert result["local_recovery_attempted"] is True
    assert result["revisit_attempted"] is True
    assert result["attempt_kind"] == "place_loss_revisit"
    assert capture_zone_recovery_flags == [False, True, False]


def test_capture_target_prefers_zone_recovery_command_on_place_loss_revisit(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.capture_timeout_s = 1.0
    runner.args.poll_s = 0.25
    mission_root = tmp_path / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    runner._init_runtime_state(session_id="session-1", mission_root=mission_root)

    clock = {"now": 0.0}

    def _fake_monotonic():
        return clock["now"]

    def _fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(gather_runner.time, "monotonic", _fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", _fake_sleep)

    robot_pose = {"x": 1.9, "y": 0.08, "yaw": 0.0}
    ball_states = [
        {"x": 2.16, "y": 0.10, "z": 0.05},
        {"x": 2.08, "y": 0.08, "z": 0.05},
    ]

    def _control_loop_state(**kwargs):
        if ball_states:
            return {}, robot_pose, ball_states.pop(0)
        return {}, robot_pose, {"x": 2.08, "y": 0.08, "z": 0.05}

    command_log: list[dict[str, object]] = []
    monkeypatch.setattr(runner, "_control_loop_state", _control_loop_state)
    monkeypatch.setattr(runner, "_update_prior_from_ball_pose", lambda target_id, ball_pose: None)
    monkeypatch.setattr(
        runner,
        "_set_manual_drive",
        lambda enabled, linear_x=0.0, angular_z=0.0, mode="idle", rationale="": command_log.append(
            {
                "enabled": enabled,
                "linear_x": linear_x,
                "angular_z": angular_z,
                "mode": mode,
                "rationale": rationale,
            }
        ),
    )

    passed, payload = runner._capture_target(
        session_id="session-1",
        target=runner.targets_by_id["ball_1"],
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
        prefer_zone_recovery=True,
    )

    assert passed is True
    assert payload["capture_state"]["captured"] is True
    assert command_log[0]["mode"] == "place_recapture"


def test_capture_target_holds_zone_dwell_during_zone_recovery(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.capture_timeout_s = 2.0
    runner.args.poll_s = 0.25
    mission_root = tmp_path / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    runner._init_runtime_state(session_id="session-1", mission_root=mission_root)

    clock = {"now": 0.0}

    def _fake_monotonic():
        return clock["now"]

    def _fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(gather_runner.time, "monotonic", _fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", _fake_sleep)

    robot_pose = {"x": 1.2, "y": 0.0, "yaw": 0.0}
    zone_ball = {"x": 2.39, "y": 0.0, "z": 0.05}

    def _control_loop_state(**kwargs):
        return {}, robot_pose, zone_ball

    command_log: list[dict[str, object]] = []
    monkeypatch.setattr(runner, "_control_loop_state", _control_loop_state)
    monkeypatch.setattr(runner, "_update_prior_from_ball_pose", lambda target_id, ball_pose: None)
    monkeypatch.setattr(
        runner,
        "_set_manual_drive",
        lambda enabled, linear_x=0.0, angular_z=0.0, mode="idle", rationale="": command_log.append(
            {
                "enabled": enabled,
                "linear_x": linear_x,
                "angular_z": angular_z,
                "mode": mode,
                "rationale": rationale,
            }
        ),
    )

    passed, payload = runner._capture_target(
        session_id="session-1",
        target=runner.targets_by_id["ball_1"],
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
        prefer_zone_recovery=True,
    )

    assert passed is True
    assert payload["zone_score"]["inside_zone"] is True
    assert any(item["mode"] == "zone_dwell" for item in command_log)
    assert command_log[-1]["mode"] == "placed"


def test_capture_target_falls_back_to_capture_command_when_zone_recovery_leaves_recapture_window(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.capture_timeout_s = 1.0
    runner.args.poll_s = 0.25
    mission_root = tmp_path / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    runner._init_runtime_state(session_id="session-1", mission_root=mission_root)

    clock = {"now": 0.0}

    def _fake_monotonic():
        return clock["now"]

    def _fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(gather_runner.time, "monotonic", _fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", _fake_sleep)

    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    ball_states = [
        {"x": 0.60, "y": 0.02, "z": 0.05},
        {"x": 0.70, "y": 0.24, "z": 0.05},
        {"x": 0.16, "y": 0.0, "z": 0.05},
    ]

    def _control_loop_state(**kwargs):
        if ball_states:
            return {}, robot_pose, ball_states.pop(0)
        return {}, robot_pose, {"x": 0.16, "y": 0.0, "z": 0.05}

    command_log: list[dict[str, object]] = []
    monkeypatch.setattr(runner, "_control_loop_state", _control_loop_state)
    monkeypatch.setattr(runner, "_update_prior_from_ball_pose", lambda target_id, ball_pose: None)
    monkeypatch.setattr(
        runner,
        "_set_manual_drive",
        lambda enabled, linear_x=0.0, angular_z=0.0, mode="idle", rationale="": command_log.append(
            {
                "enabled": enabled,
                "linear_x": linear_x,
                "angular_z": angular_z,
                "mode": mode,
                "rationale": rationale,
            }
        ),
    )

    passed, payload = runner._capture_target(
        session_id="session-1",
        target=runner.targets_by_id["ball_1"],
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
        prefer_zone_recovery=True,
    )

    assert passed is True
    assert payload["capture_state"]["captured"] is True
    assert command_log[0]["mode"] == "place_recapture"
    assert any(item["mode"] == "capture" for item in command_log[1:])
