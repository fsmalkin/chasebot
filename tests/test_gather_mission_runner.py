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
        world_file="yolo_test_world_v6_clean_uat_short_turf.world",
        surface_profile="short_turf",
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
    assert runner.gather_runtime_state["zone_pose"]["radius_m"] == 0.762
    assert runner.gather_runtime_state["zone_pose"]["control_radius_m"] == 0.2
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
            "handoff_kind": "soft_capture",
            "zone_edge_correction_count": 1,
            "place_controller_reentry_count": 0,
            "post_visit_revisit_count": 0,
            "placed": True,
            "stopped_with_ball_captured": True,
            "release_started_with_capture": True,
            "stop_capture_state": {"captured": True, "ball_x_m": 0.16, "ball_y_m": 0.0},
            "release_capture_state": {"captured": True, "ball_x_m": 0.16, "ball_y_m": 0.0},
            "clean_retention_pass": True,
            "final_inside_retrieval_corral": True,
            "final_center_inside_zone": True,
            "ball_stopped_in_corral": True,
            "rolled_away_after_release": False,
            "settled_in_corral_pass": True,
            "final_ball_pose": {"x": 2.4, "y": 0.0, "z": 0.05},
            "place_time_s": 7.5,
            "final_settle_distance_m": 0.14,
            "max_overshoot_distance_m": 0.01,
            "settle_time_s": 1.2,
            "release_recontact_count": 0,
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
    assert summary["surface_profile"] == "short_turf"
    verdict = read_json(Path(summary["mission_verdict_path"]))
    assert verdict["type"] == "gather_mission"
    assert verdict["surface_profile"] == "short_turf"
    assert verdict["route_order"] == ["ball_1"]
    assert verdict["handoff_kind"] == "soft_capture"
    assert verdict["zone_edge_correction_count"] == 1
    assert verdict["place_controller_reentry_count"] == 0
    assert verdict["post_visit_revisit_count"] == 0
    assert verdict["settled_in_corral_pass"] is True
    assert verdict["final_inside_retrieval_corral"] is True
    assert verdict["final_center_inside_zone"] is True
    assert verdict["ball_stopped_in_corral"] is True
    assert verdict["rolled_away_after_release"] is False
    assert verdict["clean_retention_pass"] is True
    assert verdict["stopped_with_ball_captured"] is True
    assert verdict["release_started_with_capture"] is True
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
    assert verdict["surface_profile"] == "short_turf"
    assert verdict["settled_in_corral_pass"] is False
    assert verdict["clean_retention_pass"] is False
    assert runner.visit_runtime_state["proof_state"] == "failed"
    assert runner.gather_runtime_state["gather_phase"] == "failed"


def test_run_passes_when_target_settles_in_corral_even_with_capture_loss_diagnostic(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    monkeypatch.setattr(gather_runner, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gather_runner, "current_utc_stamp", lambda: "20260412T000002Z")

    ready_state = {"session_id": "session-3", "compose_project": "proj", "world_name": "yolo_test_world"}
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
        lambda **kwargs: (
            runner.gather_runtime_state.__setitem__("placed_targets", ["ball_1"]),
            runner.gather_runtime_state.__setitem__("remaining_targets", []),
            runner.gather_runtime_state.__setitem__("capture_loss_count", 1),
            runner.visit_runtime_state.__setitem__("visited_targets", ["ball_1"]),
            {
                "target_id": "ball_1",
                "label": "Ball 1",
                "pass": True,
            "attempts": 1,
            "capture_loss_count": 1,
            "route_index": 1,
            "handoff_kind": "zone_entry",
            "zone_edge_correction_count": 2,
            "place_controller_reentry_count": 1,
            "post_visit_revisit_count": 0,
            "placed": True,
            "stopped_with_ball_captured": True,
                "release_started_with_capture": True,
                "stop_capture_state": {"captured": True},
                "release_capture_state": {"captured": True},
                "clean_retention_pass": False,
                "final_inside_retrieval_corral": True,
                "final_center_inside_zone": True,
                "ball_stopped_in_corral": True,
                "rolled_away_after_release": False,
                "settled_in_corral_pass": True,
                "final_ball_pose": {"x": 2.4, "y": 0.0, "z": 0.05},
                "place_time_s": 9.2,
                "final_settle_distance_m": 0.11,
                "max_overshoot_distance_m": 0.02,
                "settle_time_s": 0.8,
                "release_recontact_count": 0,
            },
        )[-1],
    )
    monkeypatch.setattr(
        gather_runner,
        "fetch_dashboard_state",
        lambda dashboard_url, timeout_s=0: {"belief": {"latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0}}},
    )

    summary = runner.run()

    verdict = read_json(Path(summary["mission_verdict_path"]))
    assert summary["pass"] is True
    assert verdict["mission_completed_pass"] is True
    assert verdict["handoff_kind"] == "zone_entry"
    assert verdict["zone_edge_correction_count"] == 2
    assert verdict["place_controller_reentry_count"] == 1
    assert verdict["post_visit_revisit_count"] == 0
    assert verdict["settled_in_corral_pass"] is True
    assert verdict["final_inside_retrieval_corral"] is True
    assert verdict["final_center_inside_zone"] is True
    assert verdict["ball_stopped_in_corral"] is True
    assert verdict["rolled_away_after_release"] is False
    assert verdict["clean_retention_pass"] is False
    assert verdict["mission_error"] == ""
    assert runner.visit_runtime_state["proof_state"] == "completed"


def test_run_target_keeps_place_control_after_near_zone_place_failure(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.max_retries_per_target = 2
    runner.args.max_place_loss_revisits = 1

    visit_dispatches: list[str] = []
    capture_calls: list[bool] = []
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
    monkeypatch.setattr(runner, "_record_target_position", lambda *args, **kwargs: None)

    capture_results = [
        (True, {"capture_state": {"captured": True}, "zone_score": {}, "handoff_kind": "soft_capture"}),
    ]
    place_results = [
        (
            False,
            {
                "failure_reason": "release_unsettled",
                "failure_stage": "release",
                "local_recovery_attempted": True,
                "allow_full_revisit": False,
                "zone_edge_correction_count": 1,
                "settle_metrics": {
                    "final_inside_retrieval_corral": True,
                    "final_center_inside_zone": True,
                    "ball_stopped_in_corral": False,
                    "rolled_away_after_release": False,
                    "settled_in_corral_pass": False,
                },
            },
        ),
        (
            True,
            {
                "final_ball_pose": {"x": 2.35, "y": 0.01, "z": 0.05},
                "zone_edge_correction_count": 1,
                "settle_metrics": {
                    "surface_profile": "short_turf",
                    "release_distance_to_zone_center_m": 0.18,
                    "max_overshoot_distance_m": 0.0,
                    "final_settle_distance_m": 0.06,
                    "settle_time_s": 1.4,
                    "release_recontact_count": 0,
                    "settled_inside_zone": True,
                    "final_inside_retrieval_corral": True,
                    "final_center_inside_zone": True,
                    "ball_stopped_in_corral": True,
                    "rolled_away_after_release": False,
                    "settled_in_corral_pass": True,
                },
            },
        ),
    ]

    def _capture_target(**kwargs):
        capture_calls.append(bool(kwargs.get("prefer_zone_recovery")))
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

    assert result["pass"] is True
    assert result["attempt_kind"] == "place_controller_reentry"
    assert result["handoff_kind"] == "soft_capture"
    assert result["zone_edge_correction_count"] == 2
    assert result["place_controller_reentry_count"] == 1
    assert result["post_visit_revisit_count"] == 0
    assert visit_dispatches == ["ball_1"]
    assert capture_calls == [False]


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
    slipped_ball = {"x": 0.41, "y": 0.0, "z": 0.05}
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
    assert payload["failure_reason"] == "place_timeout"
    assert payload["failure_stage"] == "place"
    assert payload["local_recovery_attempted"] is True
    assert any(item["mode"] in {"capture_recovery", "capture_recovery_hold"} for item in command_log)
    assert command_log[-1]["mode"] == "place_timeout"
    assert runner.gather_runtime_state["latest_control_command"]["mode"] in {"capture_recovery", "capture_recovery_hold"}
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
        ({}, robot_pose, {"x": 0.41, "y": 0.0, "z": 0.05}),
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
    assert any(item["mode"] in {"capture_recovery", "capture_recovery_hold"} for item in command_log[1:])


def test_place_target_allows_small_zone_edge_drift_to_settle_without_failure(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.place_timeout_s = 5.0
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

    robot_pose = {"x": 1.48, "y": 0.0, "yaw": 0.0}
    centered_ball = {"x": 2.39, "y": 0.0, "z": 0.05}
    edge_drift_ball = {"x": 2.605, "y": 0.0, "z": 0.05}
    states = [
        ({}, robot_pose, centered_ball),
        ({}, robot_pose, edge_drift_ball),
        ({}, robot_pose, centered_ball),
        ({}, robot_pose, centered_ball),
        ({}, robot_pose, centered_ball),
        ({}, robot_pose, centered_ball),
        ({}, robot_pose, centered_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, robot_pose, centered_ball

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
    assert payload["settled_in_corral_pass"] is True
    assert payload["release_recontact_count"] <= 1
    assert payload["rolled_away_after_release"] is False
    assert any(item["mode"] == "release_settle" for item in command_log)


def test_place_target_starts_release_monitor_when_ball_enters_outer_retrieval_corral(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.place_timeout_s = 6.0
    runner.args.poll_s = 0.5
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

    robot_pose = {"x": 1.60, "y": 0.0, "yaw": 0.0}
    states = [
        ({}, robot_pose, {"x": 2.55, "y": 0.00, "z": 0.05}),
        ({}, robot_pose, {"x": 2.56, "y": 0.00, "z": 0.05}),
        ({}, robot_pose, {"x": 2.565, "y": 0.00, "z": 0.05}),
        ({}, robot_pose, {"x": 2.565, "y": 0.00, "z": 0.05}),
        ({}, robot_pose, {"x": 2.565, "y": 0.00, "z": 0.05}),
        ({}, robot_pose, {"x": 2.565, "y": 0.00, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, robot_pose, {"x": 2.565, "y": 0.00, "z": 0.05}

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
    assert payload["settled_in_corral_pass"] is True
    assert payload["final_inside_retrieval_corral"] is True
    assert payload["ball_stopped_in_corral"] is True
    assert any(item["mode"] == "release_settle" for item in command_log)


def test_place_target_keeps_waiting_while_ball_stays_inside_overlap_and_is_still_moving(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.place_timeout_s = 15.0
    runner.args.poll_s = 1.0
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

    robot_pose = {"x": 1.48, "y": 0.0, "yaw": 0.0}
    states = [
        ({}, robot_pose, {"x": 2.39, "y": 0.0, "z": 0.05}),
        ({}, robot_pose, {"x": 2.405, "y": 0.0, "z": 0.05}),
        ({}, robot_pose, {"x": 2.42, "y": 0.0, "z": 0.05}),
        ({}, robot_pose, {"x": 2.435, "y": 0.0, "z": 0.05}),
        ({}, robot_pose, {"x": 2.45, "y": 0.0, "z": 0.05}),
        ({}, robot_pose, {"x": 2.465, "y": 0.0, "z": 0.05}),
        ({}, robot_pose, {"x": 2.48, "y": 0.0, "z": 0.05}),
        ({}, robot_pose, {"x": 2.48, "y": 0.0, "z": 0.05}),
        ({}, robot_pose, {"x": 2.48, "y": 0.0, "z": 0.05}),
        ({}, robot_pose, {"x": 2.48, "y": 0.0, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, robot_pose, {"x": 2.48, "y": 0.0, "z": 0.05}

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
    assert payload["settled_in_corral_pass"] is True
    assert payload["release_recontact_count"] == 0
    assert any(item["mode"] == "release_settle" for item in command_log)


def test_run_target_counts_post_visit_revisit_when_ball_leaves_local_correction_range(tmp_path, monkeypatch):
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
        (True, {"capture_state": {"captured": True}, "zone_score": {}, "handoff_kind": "secure_capture"}),
        (False, {"failure_reason": "capture_timeout", "failure_stage": "capture", "allow_full_revisit": True}),
        (False, {"failure_reason": "capture_timeout", "failure_stage": "capture", "allow_full_revisit": True}),
    ]
    place_results = [
        (
            False,
            {
                "failure_reason": "capture_lost",
                "failure_stage": "place",
                "local_recovery_attempted": True,
                "allow_full_revisit": True,
            },
        ),
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
    assert result["handoff_kind"] == "secure_capture"
    assert result["post_visit_revisit_count"] == 1
    assert capture_zone_recovery_flags == [False, True, False]


def test_run_target_prefers_local_recapture_over_retry_visit_after_post_visit_capture_timeout(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.max_retries_per_target = 2

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
    monkeypatch.setattr(runner, "_record_target_position", lambda *args, **kwargs: None)

    capture_results = [
        (False, {"failure_reason": "capture_timeout", "failure_stage": "capture", "allow_full_revisit": True}),
        (True, {"capture_state": {"captured": True}, "zone_score": {}, "handoff_kind": "soft_capture"}),
    ]
    place_results = [
        (
            True,
            {
                "final_ball_pose": {"x": 2.36, "y": 0.0, "z": 0.05},
                "settle_metrics": {
                    "surface_profile": "short_turf",
                    "release_distance_to_zone_center_m": 0.18,
                    "max_overshoot_distance_m": 0.0,
                    "final_settle_distance_m": 0.04,
                    "settle_time_s": 1.5,
                    "release_recontact_count": 0,
                    "settled_inside_zone": True,
                    "final_inside_retrieval_corral": True,
                    "final_center_inside_zone": True,
                    "ball_stopped_in_corral": True,
                    "rolled_away_after_release": False,
                    "settled_in_corral_pass": True,
                },
            },
        ),
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

    assert result["pass"] is True
    assert result["attempt_kind"] == "place_loss_recapture"
    assert result["post_visit_revisit_count"] == 0
    assert visit_dispatches == ["ball_1"]
    assert capture_zone_recovery_flags == [False, True]


def test_run_target_uses_place_controller_reentry_after_release_unsettled(tmp_path, monkeypatch):
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
    monkeypatch.setattr(runner, "_ball_truth_pose", lambda session_id, target: {"x": 2.15, "y": -0.05, "z": 0.05})
    monkeypatch.setattr(runner, "_update_prior_from_ball_pose", lambda target_id, ball_pose: None)
    monkeypatch.setattr(runner, "_record_target_position", lambda *args, **kwargs: None)

    capture_results = [
        (True, {"capture_state": {"captured": True}, "zone_score": {}, "handoff_kind": "soft_capture"}),
    ]
    place_results = [
        (
            False,
            {
                "failure_reason": "release_unsettled",
                "failure_stage": "release",
                "local_recovery_attempted": True,
                "allow_full_revisit": False,
                "zone_edge_correction_count": 1,
                "settle_metrics": {
                    "final_inside_retrieval_corral": True,
                    "final_center_inside_zone": True,
                    "ball_stopped_in_corral": False,
                    "rolled_away_after_release": False,
                    "settled_in_corral_pass": False,
                },
            },
        ),
        (
            True,
            {
                "final_ball_pose": {"x": 2.35, "y": 0.01, "z": 0.05},
                "zone_edge_correction_count": 1,
                "settle_metrics": {
                    "surface_profile": "short_turf",
                    "release_distance_to_zone_center_m": 0.18,
                    "max_overshoot_distance_m": 0.0,
                    "final_settle_distance_m": 0.06,
                    "settle_time_s": 1.6,
                    "release_recontact_count": 1,
                    "settled_inside_zone": True,
                    "final_inside_retrieval_corral": True,
                    "final_center_inside_zone": True,
                    "ball_stopped_in_corral": True,
                    "rolled_away_after_release": False,
                    "settled_in_corral_pass": True,
                },
                "release_recontact_count": 1,
            },
        ),
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

    assert result["pass"] is True
    assert result["attempt_kind"] == "place_controller_reentry"
    assert result["handoff_kind"] == "soft_capture"
    assert result["local_recovery_attempted"] is True
    assert result["settled_in_corral_pass"] is True
    assert result["place_controller_reentry_count"] == 1
    assert result["post_visit_revisit_count"] == 0
    assert visit_dispatches == ["ball_1"]
    assert capture_zone_recovery_flags == [False]


def test_run_target_stops_after_visit_before_capture_handoff(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.max_retries_per_target = 1

    safe_stop_calls: list[str] = []
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
    monkeypatch.setattr(runner, "_safe_stop", lambda: safe_stop_calls.append("safe_stop"))
    monkeypatch.setattr(runner, "_ball_truth_pose", lambda session_id, target: {"x": 1.0, "y": 0.0, "z": 0.05})
    monkeypatch.setattr(runner, "_update_prior_from_ball_pose", lambda target_id, ball_pose: None)
    monkeypatch.setattr(
        runner,
        "_capture_target",
        lambda **kwargs: (True, {"capture_state": {"captured": True}, "zone_score": {}, "handoff_kind": "secure_capture"}),
    )
    monkeypatch.setattr(
        runner,
        "_place_target",
        lambda **kwargs: (
            True,
            {
                "final_ball_pose": {"x": 2.38, "y": 0.01, "z": 0.05},
                "settle_metrics": {
                    "surface_profile": "short_turf",
                    "release_distance_to_zone_center_m": 0.15,
                    "max_overshoot_distance_m": 0.0,
                    "final_settle_distance_m": 0.04,
                    "settle_time_s": 1.2,
                    "release_recontact_count": 0,
                    "settled_inside_zone": True,
                    "final_inside_retrieval_corral": True,
                    "final_center_inside_zone": True,
                    "ball_stopped_in_corral": True,
                    "rolled_away_after_release": False,
                    "settled_in_corral_pass": True,
                },
            },
        ),
    )

    result = runner._run_target(
        session_id="session-1",
        target=runner.targets_by_id["ball_1"],
        route_index=1,
        gather_sequence_path=tmp_path / "gather_sequence.jsonl",
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=tmp_path / "mission",
    )

    assert result["pass"] is True
    assert result["handoff_kind"] == "secure_capture"
    assert safe_stop_calls == ["safe_stop"]


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
    assert command_log[0]["mode"] in {"place_recapture", "place_recapture_hold", "place_retention", "captured"}


def test_capture_target_turns_more_aggressively_when_zone_recovery_ball_slips_behind(tmp_path, monkeypatch):
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

    robot_pose = {"x": 2.2, "y": 0.0, "yaw": 0.0}
    ball_states = [
        {"x": 2.05, "y": 0.05, "z": 0.05},
        {"x": 2.08, "y": 0.02, "z": 0.05},
    ]

    def _control_loop_state(**kwargs):
        if ball_states:
            return {}, robot_pose, ball_states.pop(0)
        return {}, robot_pose, {"x": 2.08, "y": 0.02, "z": 0.05}

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

    assert passed is False
    assert payload["failure_reason"] == "capture_timeout"
    assert command_log[0]["linear_x"] == 0.0
    assert abs(float(command_log[0]["angular_z"])) >= 0.8


def test_capture_target_hands_off_to_place_verification_when_ball_reaches_zone(tmp_path, monkeypatch):
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
    assert payload["entered_zone_during_capture"] is True
    assert payload["handoff_kind"] == "zone_entry"
    assert command_log[-1]["mode"] == "capture_handoff"


def test_capture_target_hands_off_after_stable_soft_capture(tmp_path, monkeypatch):
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

    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    softly_captured_ball = {"x": 0.33, "y": 0.0, "z": 0.05}

    def _control_loop_state(**kwargs):
        return {}, robot_pose, softly_captured_ball

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
    )

    assert passed is True
    assert payload["soft_capture_handoff"] is True
    assert payload["handoff_kind"] == "soft_capture"
    assert payload["capture_state"]["captured"] is True
    assert command_log[-1]["mode"] == "capture_handoff"


def test_capture_target_uses_gentle_handoff_control_near_zone_before_zone_entry(tmp_path, monkeypatch):
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

    robot_pose = {"x": 1.75, "y": 0.0, "yaw": 0.0}
    near_zone_states = [
        {"x": 2.15, "y": 0.02, "z": 0.05},
        {"x": 2.39, "y": 0.0, "z": 0.05},
    ]

    def _control_loop_state(**kwargs):
        if near_zone_states:
            return {}, robot_pose, near_zone_states.pop(0)
        return {}, robot_pose, {"x": 2.39, "y": 0.0, "z": 0.05}

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
    )

    assert passed is True
    assert payload["handoff_kind"] == "zone_entry"
    assert command_log[0]["mode"] == "capture_handoff_hold"
    assert command_log[0]["linear_x"] <= 0.03
    assert command_log[-1]["mode"] == "capture_handoff"


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
    assert command_log[0]["mode"] in {"place_recapture", "place_recapture_hold"}
    assert any(item["mode"] == "capture" for item in command_log[1:])
