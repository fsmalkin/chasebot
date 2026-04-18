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
        cleanup_mission_models=False,
    )


def _make_runner(tmp_path: Path, monkeypatch) -> gather_runner.GatherMissionRunner:
    monkeypatch.setattr(gather_runner, "choose_docker_cli", lambda: "docker")
    return gather_runner.GatherMissionRunner(_make_args(tmp_path))


def _make_three_ball_runner(tmp_path: Path, monkeypatch) -> gather_runner.GatherMissionRunner:
    args = _make_args(tmp_path)
    args.scenario_id = "gather_three_ball_zone"
    args.scenario_label = "Gather Three Ball Zone"
    monkeypatch.setattr(gather_runner, "choose_docker_cli", lambda: "docker")
    return gather_runner.GatherMissionRunner(args)


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


def test_inter_target_quiet_timeout_is_shorter_for_three_ball(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    three_ball_runner = _make_three_ball_runner(tmp_path, monkeypatch)
    runner.args.pursuit_settle_timeout_s = 8.0
    three_ball_runner.args.pursuit_settle_timeout_s = 8.0

    assert runner._inter_target_quiet_timeout_s() == runner.args.pursuit_settle_timeout_s
    assert three_ball_runner._inter_target_quiet_timeout_s() == 1.0


def test_reuse_prior_route_order_is_enabled_for_three_ball(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    three_ball_runner = _make_three_ball_runner(tmp_path, monkeypatch)
    prior = [{"step": 1, "ordered_ids": ["ball_b", "ball_a", "ball_c"], "selected_id": "ball_b"}]

    assert runner._reuse_prior_route_order(["ball_a", "ball_c"], prior) == []
    assert three_ball_runner._reuse_prior_route_order(["ball_a", "ball_c"], prior) == ["ball_a", "ball_c"]


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
            "settle_exit_reason": "settled",
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
    assert verdict["settle_exit_reason"] == "settled"
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
            "settle_exit_reason": "rolled_out",
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
    assert verdict["settle_exit_reason"] == "rolled_out"
    assert verdict["settled_in_corral_pass"] is False
    assert verdict["clean_retention_pass"] is False
    assert runner.visit_runtime_state["proof_state"] == "failed"
    assert runner.gather_runtime_state["gather_phase"] == "failed"


def test_run_preserves_mission_models_by_default(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    monkeypatch.setattr(gather_runner, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gather_runner, "current_utc_stamp", lambda: "20260416T000002Z")

    ready_state = {"session_id": "session-keep", "compose_project": "proj", "world_name": "yolo_test_world"}
    monkeypatch.setattr(runner, "_ensure_environment_ready", lambda: (ready_state, False))
    monkeypatch.setattr(runner, "_wait_for_robot_pose", lambda timeout_s: ready_state)
    monkeypatch.setattr(runner, "_safe_stop", lambda: None)
    monkeypatch.setattr(runner, "_wait_for_pursuit_quiet", lambda timeout_s: None)
    monkeypatch.setattr(runner, "_spawn_mission_models", lambda ready_state, mission_root: None)
    monkeypatch.setattr(runner, "_wait_for_truth_models", lambda session_id, expected_truth_models, timeout_s: None)
    monkeypatch.setattr(runner, "_start_motion_bridge", lambda compose_project, mission_root: None)
    monkeypatch.setattr(runner, "_stop_motion_bridge", lambda compose_project: None)
    cleanup_calls: list[dict[str, object]] = []
    monkeypatch.setattr(runner, "_clear_mission_models", lambda state: cleanup_calls.append(dict(state)))
    monkeypatch.setattr(runner, "_plan_collection_route", lambda remaining_ids, state: list(remaining_ids))
    monkeypatch.setattr(
        runner,
        "_run_target",
        lambda **kwargs: {
            "target_id": "ball_1",
            "label": "Ball 1",
            "pass": False,
            "failure_reason": "release_roll_away",
            "attempts": 1,
            "capture_loss_count": 0,
            "route_index": 1,
            "settle_exit_reason": "rolled_out",
        },
    )
    monkeypatch.setattr(gather_runner, "fetch_dashboard_state", lambda dashboard_url, timeout_s=0: ready_state)

    runner.run()

    assert cleanup_calls == []


def test_run_can_cleanup_mission_models_when_requested(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.cleanup_mission_models = True
    monkeypatch.setattr(gather_runner, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gather_runner, "current_utc_stamp", lambda: "20260416T000003Z")

    ready_state = {"session_id": "session-clean", "compose_project": "proj", "world_name": "yolo_test_world"}
    monkeypatch.setattr(runner, "_ensure_environment_ready", lambda: (ready_state, False))
    monkeypatch.setattr(runner, "_wait_for_robot_pose", lambda timeout_s: ready_state)
    monkeypatch.setattr(runner, "_safe_stop", lambda: None)
    monkeypatch.setattr(runner, "_wait_for_pursuit_quiet", lambda timeout_s: None)
    monkeypatch.setattr(runner, "_spawn_mission_models", lambda ready_state, mission_root: None)
    monkeypatch.setattr(runner, "_wait_for_truth_models", lambda session_id, expected_truth_models, timeout_s: None)
    monkeypatch.setattr(runner, "_start_motion_bridge", lambda compose_project, mission_root: None)
    monkeypatch.setattr(runner, "_stop_motion_bridge", lambda compose_project: None)
    cleanup_calls: list[dict[str, object]] = []
    monkeypatch.setattr(runner, "_clear_mission_models", lambda state: cleanup_calls.append(dict(state)))
    monkeypatch.setattr(runner, "_plan_collection_route", lambda remaining_ids, state: list(remaining_ids))
    monkeypatch.setattr(
        runner,
        "_run_target",
        lambda **kwargs: {
            "target_id": "ball_1",
            "label": "Ball 1",
            "pass": False,
            "failure_reason": "release_roll_away",
            "attempts": 1,
            "capture_loss_count": 0,
            "route_index": 1,
            "settle_exit_reason": "rolled_out",
        },
    )
    monkeypatch.setattr(gather_runner, "fetch_dashboard_state", lambda dashboard_url, timeout_s=0: ready_state)

    runner.run()

    assert len(cleanup_calls) == 1
    assert cleanup_calls[0]["compose_project"] == "proj"


def test_run_target_uses_goal_side_stage_for_initial_visit_and_skips_it_on_local_recapture(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.max_retries_per_target = 1
    runner.gather_runtime_state.update({"remaining_targets": [runner.targets[0].id], "placed_targets": []})
    runner.visit_runtime_state.update({"remaining_targets": [runner.targets[0].id], "visited_targets": []})
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    call_flags: list[tuple[bool, bool]] = []
    pre_stage_calls: list[str] = []

    monkeypatch.setattr(gather_runner, "fetch_dashboard_state", lambda dashboard_url, timeout_s=0: {"brain": {}, "last_feedback": ""})
    monkeypatch.setattr(runner, "_wait_for_pursuit_quiet", lambda timeout_s: {})
    monkeypatch.setattr(runner, "_safe_stop", lambda: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_append_runtime_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_update_prior_from_ball_pose", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_record_target_position", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_ball_truth_pose", lambda session_id, target: {"x": 0.73, "y": 0.0, "z": 0.05})
    monkeypatch.setattr(
        runner,
        "_pre_stage_target",
        lambda **kwargs: (
            pre_stage_calls.append(str(kwargs["target"].id)),
            True,
            {
                "pre_stage_pose_world": {"x": 0.10, "y": 0.0},
                "pre_stage_pose_reached": True,
                "pre_stage_time_s": 1.2,
                "pre_stage_handoff_pass": True,
                "push_direction_yaw_deg": 0.0,
            },
        )[1:],
    )

    def fake_capture_target(*, prefer_zone_recovery: bool, enable_goal_side_stage: bool, **kwargs):
        call_flags.append((prefer_zone_recovery, enable_goal_side_stage))
        if len(call_flags) == 1:
            return False, {
                "pass": False,
                "failure_reason": "capture_timeout",
                "failure_stage": "capture",
                "capture_state": {},
                "zone_score": {},
                "approach_side_verdict": {"pass": True, "reason": ""},
                "staging_pose_reached": True,
                "entered_goal_side_before_capture": False,
                "first_contact_push_alignment_deg": 5.0,
                "push_direction_yaw_deg": 0.0,
                "stage_time_s": 0.5,
                "capture_entry_reached": True,
                "capture_entry_time_s": 0.4,
                "approach_failure_reason": "",
            }
        return True, {
            "pass": True,
            "capture_state": {"captured": True, "ball_x_m": 0.18, "ball_y_m": 0.0},
            "zone_score": {"center_inside_zone": True, "center_inside_retrieval_corral": True},
            "final_ball_pose": {"x": 2.45, "y": 0.0, "z": 0.05},
            "handoff_kind": "secure_capture",
            "stopped_with_ball_captured": True,
            "release_started_with_capture": True,
            "stop_capture_state": {"captured": True},
            "release_capture_state": {"captured": True},
            "clean_retention_pass": True,
            "final_inside_retrieval_corral": True,
            "final_center_inside_zone": True,
            "ball_stopped_in_corral": True,
            "rolled_away_after_release": False,
            "settled_in_corral_pass": True,
            "settle_metrics": {
                "final_inside_retrieval_corral": True,
                "final_center_inside_zone": True,
                "ball_stopped_in_corral": True,
                "rolled_away_after_release": False,
                "settled_in_corral_pass": True,
                "settle_exit_reason": "settled",
                "release_recontact_count": 0,
            },
            "approach_side_verdict": {"pass": True, "reason": ""},
            "staging_pose_reached": True,
            "entered_goal_side_before_capture": False,
            "first_contact_push_alignment_deg": 5.0,
            "push_direction_yaw_deg": 0.0,
            "stage_time_s": 0.5,
            "capture_entry_reached": False,
            "capture_entry_time_s": 0.0,
            "approach_failure_reason": "",
        }

    monkeypatch.setattr(runner, "_capture_target", fake_capture_target)

    result = runner._run_target(
        session_id="session-1",
        target=target,
        route_index=1,
        gather_sequence_path=tmp_path / "gather_sequence.jsonl",
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert call_flags == [(False, True), (True, False)]
    assert pre_stage_calls == [target.id]
    assert result["pass"] is True
    assert result["attempts"] == 2
    assert result["settled_in_corral_pass"] is True
    assert result["approach_side_verdict"] == {"pass": True, "reason": ""}
    assert result["pre_stage_pose_reached"] is True
    assert result["pre_stage_handoff_pass"] is True
    assert result["fresh_attempt_approach"]["pass"] is True
    assert result["fresh_attempt_approach"]["capture_entry"]["pass"] is True
    assert result["fresh_attempt_approach"]["capture_entry"]["entered_goal_side_before_capture"] is False


def test_pre_stage_target_returns_handoff_payload_on_success(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    manual_drive_calls: list[dict[str, object]] = []

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: manual_drive_calls.append({"args": args, **kwargs}))
    monkeypatch.setattr(
        runner,
        "_control_loop_state",
        lambda **kwargs: (
            {},
            {"x": 0.10, "y": 0.0, "yaw": 0.0},
            {"x": 1.0, "y": 0.0, "z": 0.05},
        ),
    )

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert pre_stage_pass is True
    assert payload["pre_stage_pose_world"]["x"] == 0.1
    assert payload["pre_stage_pose_reached"] is True
    assert payload["pre_stage_handoff_pass"] is True
    assert payload["pre_stage_time_s"] >= 0.25
    assert any(call["mode"] == "pre_stage_ready" for call in manual_drive_calls)


def test_run_target_retries_fresh_approach_after_capture_entry_failure(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.max_retries_per_target = 1
    runner.visit_runtime_state.update({"remaining_targets": [runner.targets[0].id], "visited_targets": []})
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    call_flags: list[tuple[bool, bool]] = []
    pre_stage_calls: list[str] = []

    monkeypatch.setattr(gather_runner, "fetch_dashboard_state", lambda dashboard_url, timeout_s=0: {"brain": {}, "last_feedback": ""})
    monkeypatch.setattr(runner, "_wait_for_pursuit_quiet", lambda timeout_s: None)
    monkeypatch.setattr(runner, "_safe_stop", lambda: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_append_runtime_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_update_prior_from_ball_pose", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_record_target_position", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_ball_truth_pose", lambda session_id, target: {"x": 0.73, "y": 0.0, "z": 0.05})
    monkeypatch.setattr(
        runner,
        "_pre_stage_target",
        lambda **kwargs: (
            pre_stage_calls.append(str(kwargs["target"].id)),
            True,
            {
                "pre_stage_pose_world": {"x": 0.10, "y": 0.0},
                "pre_stage_pose_reached": True,
                "pre_stage_time_s": 1.0,
                "pre_stage_handoff_pass": True,
            },
        )[1:],
    )

    def fake_capture_target(*, prefer_zone_recovery: bool, enable_goal_side_stage: bool, **kwargs):
        call_flags.append((prefer_zone_recovery, enable_goal_side_stage))
        if len(call_flags) == 1:
            return False, {
                "failure_reason": "capture_entry_timeout",
                "failure_stage": "capture_entry",
                "capture_state": {},
                "zone_score": {},
                "staging_pose_reached": True,
                "entered_goal_side_before_capture": False,
                "capture_entry_reached": False,
                "capture_entry_time_s": 4.0,
                "approach_failure_reason": "capture_entry_timeout",
            }
        return True, {
            "capture_state": {"captured": True, "ball_x_m": 0.18, "ball_y_m": 0.0},
            "zone_score": {"center_inside_zone": True, "center_inside_retrieval_corral": True},
            "final_ball_pose": {"x": 2.45, "y": 0.0, "z": 0.05},
            "handoff_kind": "secure_capture",
            "settle_metrics": {
                "final_inside_retrieval_corral": True,
                "final_center_inside_zone": True,
                "ball_stopped_in_corral": True,
                "rolled_away_after_release": False,
                "settled_in_corral_pass": True,
            },
            "staging_pose_reached": True,
            "entered_goal_side_before_capture": False,
            "capture_entry_reached": True,
            "capture_entry_time_s": 0.4,
        }

    monkeypatch.setattr(runner, "_capture_target", fake_capture_target)

    result = runner._run_target(
        session_id="session-fresh-retry",
        target=target,
        route_index=1,
        gather_sequence_path=tmp_path / "gather_sequence.jsonl",
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert result["pass"] is True
    assert call_flags == [(False, True), (False, True)]
    assert pre_stage_calls == [target.id, target.id]
    assert result["fresh_attempt_approach"]["pass"] is False
    assert result["fresh_attempt_approach"]["reason"] == "capture_entry_timeout"
    assert result["fresh_attempt_approach"]["capture_entry"]["pass"] is False


def test_run_final_corral_audit_requires_stable_window_for_all_three_targets(tmp_path, monkeypatch):
    runner = _make_three_ball_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.25
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    runner._init_runtime_state(session_id="session-3ball", mission_root=mission_root)

    clock = {"now": 0.0}

    def _fake_monotonic():
        return clock["now"]

    def _fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(gather_runner.time, "monotonic", _fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", _fake_sleep)
    monkeypatch.setattr(runner, "_safe_stop", lambda: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)

    poses = {
        "ball_a": {"x": 2.22, "y": 0.12, "z": 0.05},
        "ball_b": {"x": 2.46, "y": -0.03, "z": 0.05},
        "ball_c": {"x": 2.58, "y": 0.06, "z": 0.05},
    }
    monkeypatch.setattr(runner, "_ball_truth_pose", lambda session_id, target: poses[target.id])

    audit = runner._run_final_corral_audit(
        session_id="session-3ball",
        state_history_path=tmp_path / "final_corral_audit.jsonl",
    )

    assert audit["retrieved_count"] == 3
    assert audit["final_all_targets_inside_retrieval_corral"] is True
    assert audit["final_all_targets_stopped"] is True
    assert audit["final_three_ball_corral_pass"] is True
    assert set(audit["final_corral_audit"].keys()) == {"ball_a", "ball_b", "ball_c"}
    assert all(entry["inside_retrieval_corral"] for entry in audit["final_corral_audit"].values())


def test_capture_target_goal_side_stage_timeout_returns_stage_failure(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.capture_timeout_s = 10.0
    runner.args.poll_s = 0.5
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    manual_drive_calls: list[dict[str, object]] = []

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: manual_drive_calls.append({"args": args, **kwargs}))
    monkeypatch.setattr(
        runner,
        "_control_loop_state",
        lambda **kwargs: (
            {},
            {"x": 0.0, "y": 0.0, "yaw": 0.0},
            {"x": 1.0, "y": 0.0, "z": 0.05},
        ),
    )

    capture_pass, payload = runner._capture_target(
        session_id="session-timeout",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
        enable_goal_side_stage=True,
    )

    timeout_path = mission_root / f"{target.id}_stage_timeout.json"
    timeout_payload = read_json(timeout_path)

    assert capture_pass is False
    assert payload["failure_stage"] == "stage"
    assert payload["failure_reason"] == "goal_side_stage_timeout"
    assert payload["approach_failure_reason"] == "staging_pose_not_reached"
    assert timeout_payload["failure_stage"] == "stage"
    assert timeout_payload["failure_reason"] == "goal_side_stage_timeout"
    assert any(call["mode"].startswith("stage_") for call in manual_drive_calls)


def test_capture_target_capture_entry_timeout_returns_capture_entry_failure(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.capture_timeout_s = 10.0
    runner.args.poll_s = 0.5
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    phase_entries: list[str] = []

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(
        gather_runner,
        "append_jsonl",
        lambda _path, payload: phase_entries.append(str(payload.get("phase", ""))) if isinstance(payload, dict) else None,
    )
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_control_loop_state",
        lambda **kwargs: (
            {},
            {"x": 0.55, "y": -0.10, "yaw": 0.0},
            {"x": 1.0, "y": 0.0, "z": 0.05},
        ),
    )

    capture_pass, payload = runner._capture_target(
        session_id="session-capture-entry-timeout",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
        enable_goal_side_stage=True,
    )

    timeout_path = mission_root / f"{target.id}_capture_entry_timeout.json"
    timeout_payload = read_json(timeout_path)

    assert capture_pass is False
    assert payload["failure_stage"] == "capture_entry"
    assert payload["failure_reason"] == "capture_entry_timeout"
    assert payload["staging_pose_reached"] is True
    assert payload["capture_entry_reached"] is False
    assert payload["capture_entry_time_s"] >= 4.0
    assert timeout_payload["failure_stage"] == "capture_entry"
    assert phase_entries.count("capture_entry") > 0
    assert "capture" not in phase_entries


def test_capture_target_records_capture_entry_before_generic_capture_timeout(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.capture_timeout_s = 1.2
    runner.args.poll_s = 0.1
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    phase_entries: list[str] = []

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(
        gather_runner,
        "append_jsonl",
        lambda _path, payload: phase_entries.append(str(payload.get("phase", ""))) if isinstance(payload, dict) else None,
    )
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_control_loop_state",
        lambda **kwargs: (
            {},
            {"x": 0.55, "y": 0.0, "yaw": 0.0},
            {"x": 1.0, "y": 0.0, "z": 0.05},
        ),
    )

    capture_pass, payload = runner._capture_target(
        session_id="session-capture-entry-pass",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
        enable_goal_side_stage=True,
    )

    assert capture_pass is False
    assert payload["failure_stage"] == "capture"
    assert payload["capture_entry_reached"] is True
    assert payload["capture_entry_time_s"] >= 0.3
    assert "capture_entry" in phase_entries
    assert "capture" in phase_entries
    assert phase_entries.index("capture_entry") < phase_entries.index("capture")


def test_run_for_three_ball_zone_uses_final_corral_audit_not_last_target_only(tmp_path, monkeypatch):
    runner = _make_three_ball_runner(tmp_path, monkeypatch)
    monkeypatch.setattr(gather_runner, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gather_runner, "current_utc_stamp", lambda: "20260416T000100Z")

    ready_state = {"session_id": "session-4", "compose_project": "proj", "world_name": "yolo_test_world"}
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

    target_results = iter(
        [
            {
                "target_id": "ball_a",
                "label": "Ball A (far left)",
                "pass": True,
                "attempts": 1,
                "capture_loss_count": 0,
                "route_index": 1,
                "handoff_kind": "soft_capture",
                "settle_exit_reason": "settled",
                "zone_edge_correction_count": 0,
                "place_controller_reentry_count": 0,
                "post_visit_revisit_count": 0,
                "placed": True,
                "stopped_with_ball_captured": True,
                "release_started_with_capture": True,
                "clean_retention_pass": True,
                "final_inside_retrieval_corral": True,
                "final_center_inside_zone": True,
                "ball_stopped_in_corral": True,
                "rolled_away_after_release": False,
                "settled_in_corral_pass": True,
                "final_ball_pose": {"x": 2.4, "y": 0.10, "z": 0.05},
                "place_time_s": 6.0,
                "final_settle_distance_m": 0.16,
                "max_overshoot_distance_m": 0.01,
                "settle_time_s": 1.0,
                "release_recontact_count": 0,
            },
            {
                "target_id": "ball_b",
                "label": "Ball B (near center)",
                "pass": True,
                "attempts": 1,
                "capture_loss_count": 0,
                "route_index": 2,
                "handoff_kind": "zone_entry",
                "settle_exit_reason": "corrected",
                "zone_edge_correction_count": 1,
                "place_controller_reentry_count": 0,
                "post_visit_revisit_count": 0,
                "placed": True,
                "stopped_with_ball_captured": True,
                "release_started_with_capture": True,
                "clean_retention_pass": True,
                "final_inside_retrieval_corral": True,
                "final_center_inside_zone": True,
                "ball_stopped_in_corral": True,
                "rolled_away_after_release": False,
                "settled_in_corral_pass": True,
                "final_ball_pose": {"x": 2.4, "y": 0.00, "z": 0.05},
                "place_time_s": 7.0,
                "final_settle_distance_m": 0.10,
                "max_overshoot_distance_m": 0.02,
                "settle_time_s": 1.1,
                "release_recontact_count": 0,
            },
            {
                "target_id": "ball_c",
                "label": "Ball C (far right)",
                "pass": True,
                "attempts": 1,
                "capture_loss_count": 0,
                "route_index": 3,
                "handoff_kind": "soft_capture",
                "settle_exit_reason": "settled",
                "zone_edge_correction_count": 0,
                "place_controller_reentry_count": 0,
                "post_visit_revisit_count": 0,
                "placed": True,
                "stopped_with_ball_captured": True,
                "release_started_with_capture": True,
                "clean_retention_pass": True,
                "final_inside_retrieval_corral": True,
                "final_center_inside_zone": True,
                "ball_stopped_in_corral": True,
                "rolled_away_after_release": False,
                "settled_in_corral_pass": True,
                "final_ball_pose": {"x": 2.45, "y": -0.04, "z": 0.05},
                "place_time_s": 8.0,
                "final_settle_distance_m": 0.12,
                "max_overshoot_distance_m": 0.03,
                "settle_time_s": 1.2,
                "release_recontact_count": 0,
            },
        ]
    )

    def _run_target_success(**kwargs):
        result = next(target_results)
        placed = list(runner.gather_runtime_state.get("placed_targets", []))
        if result["target_id"] not in placed:
            placed.append(result["target_id"])
        remaining = [item.id for item in runner.targets if item.id not in placed]
        runner.gather_runtime_state["placed_targets"] = placed
        runner.gather_runtime_state["remaining_targets"] = remaining
        runner.visit_runtime_state["visited_targets"] = placed
        return result

    monkeypatch.setattr(runner, "_run_target", _run_target_success)
    monkeypatch.setattr(
        runner,
        "_run_final_corral_audit",
        lambda **kwargs: {
            "final_corral_audit": {
                "ball_a": {"distance_to_zone_center_m": 0.18, "inside_retrieval_corral": True, "stopped_in_corral": True},
                "ball_b": {"distance_to_zone_center_m": 0.92, "inside_retrieval_corral": False, "stopped_in_corral": False},
                "ball_c": {"distance_to_zone_center_m": 0.16, "inside_retrieval_corral": True, "stopped_in_corral": True},
            },
            "retrieved_count": 2,
            "final_all_targets_inside_retrieval_corral": False,
            "final_all_targets_stopped": False,
            "final_three_ball_corral_pass": False,
        },
    )
    monkeypatch.setattr(
        gather_runner,
        "fetch_dashboard_state",
        lambda dashboard_url, timeout_s=0: {"belief": {"latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0}}},
    )

    summary = runner.run()

    verdict = read_json(Path(summary["mission_verdict_path"]))
    assert summary["pass"] is False
    assert verdict["mission_completed_pass"] is True
    assert verdict["final_three_ball_corral_pass"] is False
    assert verdict["retrieved_count"] == 2
    assert verdict["final_all_targets_inside_retrieval_corral"] is False
    assert verdict["mission_error"] == "final_corral_audit_failed"


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
                "settle_exit_reason": "corrected",
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
    assert verdict["settle_exit_reason"] == "corrected"
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

    pre_stage_calls: list[str] = []
    capture_calls: list[bool] = []
    monkeypatch.setattr(
        gather_runner,
        "fetch_dashboard_state",
        lambda dashboard_url, timeout_s=0: {
            "brain": {"last_feedback_status": "", "last_feedback_text": ""},
            "belief": {"latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0}},
        },
    )
    monkeypatch.setattr(runner, "_wait_for_pursuit_quiet", lambda timeout_s: None)
    monkeypatch.setattr(runner, "_safe_stop", lambda: None)
    monkeypatch.setattr(runner, "_ball_truth_pose", lambda session_id, target: {"x": 1.0, "y": 0.0, "z": 0.05})
    monkeypatch.setattr(runner, "_update_prior_from_ball_pose", lambda target_id, ball_pose: None)
    monkeypatch.setattr(runner, "_record_target_position", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_pre_stage_target",
        lambda **kwargs: (
            pre_stage_calls.append(str(kwargs["target"].id)),
            True,
            {"pre_stage_pose_world": {"x": 0.1, "y": 0.0}, "pre_stage_pose_reached": True, "pre_stage_time_s": 1.0, "pre_stage_handoff_pass": True},
        )[1:],
    )

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
    assert pre_stage_calls == ["ball_1"]
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
    runner.args.place_timeout_s = 4.0
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


def test_place_target_prefers_no_chase_or_turn_recovery_when_ball_slips_behind_inside_corral(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.place_timeout_s = 1.5
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

    robot_pose = {"x": 1.02517, "y": -0.023582, "yaw": 1.98}
    states = [
        ({}, robot_pose, {"x": 1.20, "y": -0.03, "z": 0.05}),
        ({}, robot_pose, {"x": 2.82, "y": -0.16, "z": 0.05}),
        ({}, robot_pose, {"x": 2.84, "y": -0.17, "z": 0.05}),
        ({}, robot_pose, {"x": 2.86, "y": -0.17, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, robot_pose, {"x": 2.88, "y": -0.17, "z": 0.05}

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
    assert payload["failure_reason"] in {"place_timeout", "release_roll_away"}
    assert any(item["mode"] in {"capture_recovery_turn", "settle_no_chase"} for item in command_log)
    turn_commands = [item for item in command_log if item["mode"] == "capture_recovery_turn"]
    if turn_commands:
        assert all(item["linear_x"] == 0.0 for item in turn_commands)
        assert all(abs(float(item["angular_z"])) >= 0.8 for item in turn_commands)


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
    assert any(item["mode"] in {"release_settle", "settle_no_chase"} for item in command_log)


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
    assert payload["settle_no_chase_activated"] is True
    assert payload["settle_no_chase_exit_reason"] in {"settled", "corrected"}
    assert payload["release_gate_blocked_reason"] == "none"
    assert any(item["mode"] == "settle_no_chase" for item in command_log)


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
    assert any(item["mode"] in {"release_settle", "settle_no_chase"} for item in command_log)


def test_place_target_avoids_normal_release_settle_at_outer_edge_with_captured_ball(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.place_timeout_s = 1.25
    runner.args.poll_s = 0.25
    mission_root = tmp_path / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    runner._init_runtime_state(session_id="session-1", mission_root=mission_root)

    clock = {"now": 0.0}
    sample_index = {"value": 0}

    def _fake_monotonic():
        return clock["now"]

    def _fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(gather_runner.time, "monotonic", _fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", _fake_sleep)

    robot_pose = {"x": 1.324551, "y": -0.063129, "yaw": -0.073522}

    def _control_loop_state(**kwargs):
        offset_x = 0.00 + (0.01 * sample_index["value"])
        offset_y = -0.103485 - (0.001 * sample_index["value"])
        sample_index["value"] += 1
        return {}, robot_pose, {"x": 1.66878 + offset_x, "y": offset_y, "z": 0.05}

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
    assert payload["settle_no_chase_activated"] is True
    assert all(item["mode"] != "release_settle" for item in command_log[:-1])


def test_place_target_can_latch_practical_retrieval_when_robot_is_still_far_back(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.place_timeout_s = 1.25
    runner.args.poll_s = 0.25
    mission_root = tmp_path / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    runner._init_runtime_state(session_id="session-1", mission_root=mission_root)

    clock = {"now": 0.0}
    sample_index = {"value": 0}

    def _fake_monotonic():
        return clock["now"]

    def _fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(gather_runner.time, "monotonic", _fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", _fake_sleep)

    robot_pose = {"x": 1.05, "y": -0.01, "yaw": 0.49}

    def _control_loop_state(**kwargs):
        offset_x = 0.00 + (0.02 * sample_index["value"])
        offset_y = -0.12 - (0.001 * sample_index["value"])
        sample_index["value"] += 1
        return {}, robot_pose, {"x": 2.26 + offset_x, "y": offset_y, "z": 0.05}

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
    assert payload["settle_no_chase_activated"] is True
    assert any(item["mode"] in {"capture_recovery", "capture_recovery_hold", "retrieval_shepherd", "settle_no_chase"} for item in command_log)
    assert all(item["mode"] != "release_settle" for item in command_log[:-1])


def test_place_target_three_ball_advances_after_practical_retrieval_without_full_stop(tmp_path, monkeypatch):
    runner = _make_three_ball_runner(tmp_path, monkeypatch)
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

    robot_pose = {"x": 1.48, "y": 0.0, "yaw": 0.0}
    states = [
        ({}, robot_pose, {"x": 2.38, "y": 0.0, "z": 0.05}),
        ({}, robot_pose, {"x": 2.40, "y": 0.0, "z": 0.05}),
        ({}, robot_pose, {"x": 2.42, "y": 0.0, "z": 0.05}),
        ({}, robot_pose, {"x": 2.435, "y": 0.0, "z": 0.05}),
        ({}, robot_pose, {"x": 2.447, "y": 0.0, "z": 0.05}),
        ({}, robot_pose, {"x": 2.456, "y": 0.0, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, robot_pose, {"x": 2.462, "y": 0.0, "z": 0.05}

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
        target=runner.targets_by_id["ball_b"],
        state_history_path=tmp_path / "state_history.jsonl",
    )

    assert passed is True
    assert payload["final_inside_retrieval_corral"] is True
    assert payload["settled_in_corral_pass"] is False
    assert payload["settle_no_chase_activated"] is True
    assert any(item["mode"] == "settle_no_chase" for item in command_log)


def test_run_target_fails_settled_placement_loss_when_ball_leaves_local_correction_range(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.max_retries_per_target = 2

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
    ]
    place_results = [
        (
            False,
            {
                "failure_reason": "capture_lost",
                "failure_stage": "place",
                "local_recovery_attempted": True,
                "allow_full_revisit": False,
            },
        ),
        (
            False,
            {
                "failure_reason": "release_roll_away",
                "failure_stage": "release",
                "local_recovery_attempted": True,
                "allow_full_revisit": False,
                "rolled_away_after_release": True,
                "settle_exit_reason": "rolled_out",
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
    assert result["failure_reason"] == "release_roll_away"
    assert result["local_recovery_attempted"] is True
    assert result["revisit_attempted"] is False
    assert result["attempt_kind"] == "place_controller_reentry"
    assert result["handoff_kind"] == "secure_capture"
    assert result["post_visit_revisit_count"] == 0
    assert result["rolled_away_after_release"] is True
    assert result["settle_exit_reason"] == "rolled_out"
    assert capture_zone_recovery_flags == [False]


def test_run_target_three_ball_accepts_practical_retrieval_before_final_audit(tmp_path, monkeypatch):
    runner = _make_three_ball_runner(tmp_path, monkeypatch)
    runner.args.max_retries_per_target = 1

    pre_stage_calls: list[str] = []
    monkeypatch.setattr(
        gather_runner,
        "fetch_dashboard_state",
        lambda dashboard_url, timeout_s=0: {
            "brain": {"last_feedback_status": "", "last_feedback_text": ""},
            "belief": {"latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0}},
        },
    )
    monkeypatch.setattr(runner, "_wait_for_pursuit_quiet", lambda timeout_s: None)
    monkeypatch.setattr(runner, "_safe_stop", lambda: None)
    monkeypatch.setattr(runner, "_ball_truth_pose", lambda session_id, target: {"x": 2.45, "y": 0.0, "z": 0.05})
    monkeypatch.setattr(runner, "_update_prior_from_ball_pose", lambda target_id, ball_pose: None)
    monkeypatch.setattr(runner, "_record_target_position", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_pre_stage_target",
        lambda **kwargs: (
            pre_stage_calls.append(str(kwargs["target"].id)),
            True,
            {"pre_stage_pose_world": {"x": 1.55, "y": 0.0}, "pre_stage_pose_reached": True, "pre_stage_time_s": 2.0, "pre_stage_handoff_pass": True},
        )[1:],
    )
    monkeypatch.setattr(
        runner,
        "_capture_target",
        lambda **kwargs: (True, {"capture_state": {"captured": False}, "zone_score": {}, "handoff_kind": "zone_entry"}),
    )
    monkeypatch.setattr(
        runner,
        "_place_target",
        lambda **kwargs: (
            True,
            {
                "final_ball_pose": {"x": 2.45, "y": 0.0, "z": 0.05},
                "settle_no_chase_activated": True,
                "settle_exit_reason": "settled",
                "settle_metrics": {
                    "surface_profile": "short_turf",
                    "release_distance_to_zone_center_m": 0.18,
                    "max_overshoot_distance_m": 0.0,
                    "final_settle_distance_m": 0.05,
                    "settle_time_s": 0.5,
                    "release_recontact_count": 0,
                    "settled_inside_zone": False,
                    "final_inside_retrieval_corral": True,
                    "final_center_inside_zone": False,
                    "ball_stopped_in_corral": False,
                    "rolled_away_after_release": False,
                    "settled_in_corral_pass": False,
                },
            },
        ),
    )

    result = runner._run_target(
        session_id="session-1",
        target=runner.targets_by_id["ball_b"],
        route_index=1,
        gather_sequence_path=tmp_path / "gather_sequence.jsonl",
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=tmp_path / "mission",
    )

    assert result["pass"] is True
    assert result["placed"] is True
    assert result["practical_retrieval_pass"] is True
    assert result["settled_in_corral_pass"] is False
    assert result["final_inside_retrieval_corral"] is True
    assert result["post_visit_revisit_count"] == 0
    assert pre_stage_calls == ["ball_b"]


def test_run_target_uses_local_gather_recapture_after_post_visit_capture_timeout(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.max_retries_per_target = 2

    pre_stage_calls: list[str] = []
    capture_zone_recovery_flags: list[bool] = []
    monkeypatch.setattr(
        gather_runner,
        "fetch_dashboard_state",
        lambda dashboard_url, timeout_s=0: {
            "brain": {"last_feedback_status": "", "last_feedback_text": ""},
            "belief": {"latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0}},
        },
    )
    monkeypatch.setattr(runner, "_wait_for_pursuit_quiet", lambda timeout_s: None)
    monkeypatch.setattr(runner, "_safe_stop", lambda: None)
    monkeypatch.setattr(runner, "_ball_truth_pose", lambda session_id, target: {"x": 1.0, "y": 0.0, "z": 0.05})
    monkeypatch.setattr(runner, "_update_prior_from_ball_pose", lambda target_id, ball_pose: None)
    monkeypatch.setattr(runner, "_record_target_position", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_pre_stage_target",
        lambda **kwargs: (
            pre_stage_calls.append(str(kwargs["target"].id)),
            True,
            {"pre_stage_pose_world": {"x": 0.1, "y": 0.0}, "pre_stage_pose_reached": True, "pre_stage_time_s": 1.0, "pre_stage_handoff_pass": True},
        )[1:],
    )

    capture_results = [
        (False, {"failure_reason": "capture_timeout", "failure_stage": "capture", "allow_full_revisit": False}),
        (True, {"capture_state": {"captured": True}, "zone_score": {}, "handoff_kind": "soft_capture"}),
    ]
    place_results = [
        (
            True,
            {
                "final_ball_pose": {"x": 2.36, "y": 0.0, "z": 0.05},
                "settle_exit_reason": "corrected",
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
    assert result["settle_exit_reason"] == "corrected"
    assert pre_stage_calls == ["ball_1"]
    assert capture_zone_recovery_flags == [False, True]


def test_run_target_uses_place_controller_reentry_after_release_unsettled(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.max_retries_per_target = 2
    runner.args.max_place_loss_revisits = 1

    pre_stage_calls: list[str] = []
    capture_zone_recovery_flags: list[bool] = []
    monkeypatch.setattr(
        gather_runner,
        "fetch_dashboard_state",
        lambda dashboard_url, timeout_s=0: {
            "brain": {"last_feedback_status": "", "last_feedback_text": ""},
            "belief": {"latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0}},
        },
    )
    monkeypatch.setattr(runner, "_wait_for_pursuit_quiet", lambda timeout_s: None)
    monkeypatch.setattr(runner, "_safe_stop", lambda: None)
    monkeypatch.setattr(runner, "_ball_truth_pose", lambda session_id, target: {"x": 2.15, "y": -0.05, "z": 0.05})
    monkeypatch.setattr(runner, "_update_prior_from_ball_pose", lambda target_id, ball_pose: None)
    monkeypatch.setattr(runner, "_record_target_position", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_pre_stage_target",
        lambda **kwargs: (
            pre_stage_calls.append(str(kwargs["target"].id)),
            True,
            {"pre_stage_pose_world": {"x": 0.1, "y": 0.0}, "pre_stage_pose_reached": True, "pre_stage_time_s": 1.0, "pre_stage_handoff_pass": True},
        )[1:],
    )

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
    assert pre_stage_calls == ["ball_1"]
    assert capture_zone_recovery_flags == [False]


def test_run_target_stops_after_visit_before_capture_handoff(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.max_retries_per_target = 1

    safe_stop_calls: list[str] = []
    monkeypatch.setattr(
        gather_runner,
        "fetch_dashboard_state",
        lambda dashboard_url, timeout_s=0: {
            "brain": {"last_feedback_status": "", "last_feedback_text": ""},
            "belief": {"latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0}},
        },
    )
    monkeypatch.setattr(runner, "_wait_for_pursuit_quiet", lambda timeout_s: None)
    monkeypatch.setattr(runner, "_safe_stop", lambda: safe_stop_calls.append("safe_stop"))
    monkeypatch.setattr(runner, "_ball_truth_pose", lambda session_id, target: {"x": 1.0, "y": 0.0, "z": 0.05})
    monkeypatch.setattr(runner, "_update_prior_from_ball_pose", lambda target_id, ball_pose: None)
    monkeypatch.setattr(
        runner,
        "_pre_stage_target",
        lambda **kwargs: (
            True,
            {"pre_stage_pose_world": {"x": 0.1, "y": 0.0}, "pre_stage_pose_reached": True, "pre_stage_time_s": 1.0, "pre_stage_handoff_pass": True},
        ),
    )
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


def test_capture_target_does_not_handoff_on_overlap_only_zone_entry(tmp_path, monkeypatch):
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

    robot_pose = {"x": 1.043484, "y": -0.053114, "yaw": 0.402599}
    overlap_only_zone_ball = {"x": 2.197246, "y": -0.133356, "z": 0.05}

    def _control_loop_state(**kwargs):
        return {}, robot_pose, overlap_only_zone_ball

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

    assert passed is False
    assert payload["failure_reason"] == "capture_timeout"
    assert payload["zone_score"]["inside_zone"] is True
    assert payload["zone_score"]["center_inside_zone"] is False
    assert payload["allow_full_revisit"] is False
    assert all(item["mode"] != "capture_handoff" for item in command_log)


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
