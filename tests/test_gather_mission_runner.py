from __future__ import annotations

import json
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
        gather_control_family="baseline",
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


def test_gather_control_family_allows_region_funnel_v1(tmp_path, monkeypatch):
    args = _make_args(tmp_path)
    args.gather_control_family = "region_funnel_v1"
    monkeypatch.setattr(gather_runner, "choose_docker_cli", lambda: "docker")

    runner = gather_runner.GatherMissionRunner(args)

    assert runner.gather_control_family == "region_funnel_v1"


def test_gather_control_family_allows_nav2_reacquire_v1(tmp_path, monkeypatch):
    args = _make_args(tmp_path)
    args.gather_control_family = "nav2_reacquire_v1"
    monkeypatch.setattr(gather_runner, "choose_docker_cli", lambda: "docker")

    runner = gather_runner.GatherMissionRunner(args)

    assert runner.gather_control_family == "nav2_reacquire_v1"


def test_gather_control_family_allows_constrained_local_planner_v1(tmp_path, monkeypatch):
    args = _make_args(tmp_path)
    args.gather_control_family = "constrained_local_planner_v1"
    monkeypatch.setattr(gather_runner, "choose_docker_cli", lambda: "docker")

    runner = gather_runner.GatherMissionRunner(args)

    assert runner.gather_control_family == "constrained_local_planner_v1"


def test_gather_control_family_allows_docking_reacquire_v1(tmp_path, monkeypatch):
    args = _make_args(tmp_path)
    args.gather_control_family = "docking_reacquire_v1"
    monkeypatch.setattr(gather_runner, "choose_docker_cli", lambda: "docker")

    runner = gather_runner.GatherMissionRunner(args)

    assert runner.gather_control_family == "docking_reacquire_v1"


def test_gather_control_family_allows_handoff_yaw_servo_v1(tmp_path, monkeypatch):
    args = _make_args(tmp_path)
    args.gather_control_family = "handoff_yaw_servo_v1"
    monkeypatch.setattr(gather_runner, "choose_docker_cli", lambda: "docker")

    runner = gather_runner.GatherMissionRunner(args)

    assert runner.gather_control_family == "handoff_yaw_servo_v1"


def test_gather_control_family_allows_pre_stage_reacquire_fsm_v1(tmp_path, monkeypatch):
    args = _make_args(tmp_path)
    args.gather_control_family = "pre_stage_reacquire_fsm_v1"
    monkeypatch.setattr(gather_runner, "choose_docker_cli", lambda: "docker")

    runner = gather_runner.GatherMissionRunner(args)

    assert runner.gather_control_family == "pre_stage_reacquire_fsm_v1"


def test_gather_control_family_allows_pre_stage_path_tracker_v1(tmp_path, monkeypatch):
    args = _make_args(tmp_path)
    args.gather_control_family = "pre_stage_path_tracker_v1"
    monkeypatch.setattr(gather_runner, "choose_docker_cli", lambda: "docker")

    runner = gather_runner.GatherMissionRunner(args)

    assert runner.gather_control_family == "pre_stage_path_tracker_v1"


def test_gather_control_family_allows_pre_stage_trajectory_owner_v1(tmp_path, monkeypatch):
    args = _make_args(tmp_path)
    args.gather_control_family = "pre_stage_trajectory_owner_v1"
    monkeypatch.setattr(gather_runner, "choose_docker_cli", lambda: "docker")

    runner = gather_runner.GatherMissionRunner(args)

    assert runner.gather_control_family == "pre_stage_trajectory_owner_v1"


def test_gather_control_family_allows_nav2_follow_path_reacquire_v1(tmp_path, monkeypatch):
    args = _make_args(tmp_path)
    args.gather_control_family = "nav2_follow_path_reacquire_v1"
    monkeypatch.setattr(gather_runner, "choose_docker_cli", lambda: "docker")

    runner = gather_runner.GatherMissionRunner(args)

    assert runner.gather_control_family == "nav2_follow_path_reacquire_v1"


def test_gather_control_family_allows_nav2_mppi_follow_path_reacquire_v1(tmp_path, monkeypatch):
    args = _make_args(tmp_path)
    args.gather_control_family = "nav2_mppi_follow_path_reacquire_v1"
    monkeypatch.setattr(gather_runner, "choose_docker_cli", lambda: "docker")

    runner = gather_runner.GatherMissionRunner(args)

    assert runner.gather_control_family == "nav2_mppi_follow_path_reacquire_v1"


def test_gather_control_family_allows_nav2_followpath_corridor_push_v1(tmp_path, monkeypatch):
    args = _make_args(tmp_path)
    args.gather_control_family = "nav2_followpath_corridor_push_v1"
    monkeypatch.setattr(gather_runner, "choose_docker_cli", lambda: "docker")

    runner = gather_runner.GatherMissionRunner(args)

    assert runner.gather_control_family == "nav2_followpath_corridor_push_v1"


def test_gather_control_family_allows_object_centric_gather_policy_v1(tmp_path, monkeypatch):
    args = _make_args(tmp_path)
    args.gather_control_family = "object_centric_gather_policy_v1"
    monkeypatch.setattr(gather_runner, "choose_docker_cli", lambda: "docker")

    runner = gather_runner.GatherMissionRunner(args)

    assert runner.gather_control_family == "object_centric_gather_policy_v1"


def test_gather_control_family_allows_ai_push_coast_servo_v1(tmp_path, monkeypatch):
    args = _make_args(tmp_path)
    args.gather_control_family = "ai_push_coast_servo_v1"
    args.ai_push_coast_mode = "guarded_live"
    monkeypatch.setattr(gather_runner, "choose_docker_cli", lambda: "docker")

    runner = gather_runner.GatherMissionRunner(args)

    assert runner.gather_control_family == "ai_push_coast_servo_v1"
    assert runner.ai_push_coast_mode == "guarded_live"


def test_parse_args_allows_region_funnel_v1(monkeypatch):
    monkeypatch.setattr(
        gather_runner.sys,
        "argv",
        ["gather_mission_runner.py", "--gather-control-family", "region_funnel_v1"],
    )

    args = gather_runner.parse_args()

    assert args.gather_control_family == "region_funnel_v1"


def test_parse_args_allows_nav2_reacquire_v1(monkeypatch):
    monkeypatch.setattr(
        gather_runner.sys,
        "argv",
        ["gather_mission_runner.py", "--gather-control-family", "nav2_reacquire_v1"],
    )

    args = gather_runner.parse_args()

    assert args.gather_control_family == "nav2_reacquire_v1"


def test_parse_args_allows_constrained_local_planner_v1(monkeypatch):
    monkeypatch.setattr(
        gather_runner.sys,
        "argv",
        ["gather_mission_runner.py", "--gather-control-family", "constrained_local_planner_v1"],
    )

    args = gather_runner.parse_args()

    assert args.gather_control_family == "constrained_local_planner_v1"


def test_parse_args_allows_docking_reacquire_v1(monkeypatch):
    monkeypatch.setattr(
        gather_runner.sys,
        "argv",
        ["gather_mission_runner.py", "--gather-control-family", "docking_reacquire_v1"],
    )

    args = gather_runner.parse_args()

    assert args.gather_control_family == "docking_reacquire_v1"


def test_parse_args_allows_handoff_yaw_servo_v1(monkeypatch):
    monkeypatch.setattr(
        gather_runner.sys,
        "argv",
        ["gather_mission_runner.py", "--gather-control-family", "handoff_yaw_servo_v1"],
    )

    args = gather_runner.parse_args()

    assert args.gather_control_family == "handoff_yaw_servo_v1"


def test_parse_args_allows_pre_stage_reacquire_fsm_v1(monkeypatch):
    monkeypatch.setattr(
        gather_runner.sys,
        "argv",
        ["gather_mission_runner.py", "--gather-control-family", "pre_stage_reacquire_fsm_v1"],
    )

    args = gather_runner.parse_args()

    assert args.gather_control_family == "pre_stage_reacquire_fsm_v1"


def test_parse_args_allows_pre_stage_path_tracker_v1(monkeypatch):
    monkeypatch.setattr(
        gather_runner.sys,
        "argv",
        ["gather_mission_runner.py", "--gather-control-family", "pre_stage_path_tracker_v1"],
    )

    args = gather_runner.parse_args()

    assert args.gather_control_family == "pre_stage_path_tracker_v1"


def test_parse_args_allows_pre_stage_trajectory_owner_v1(monkeypatch):
    monkeypatch.setattr(
        gather_runner.sys,
        "argv",
        ["gather_mission_runner.py", "--gather-control-family", "pre_stage_trajectory_owner_v1"],
    )

    args = gather_runner.parse_args()

    assert args.gather_control_family == "pre_stage_trajectory_owner_v1"


def test_parse_args_allows_nav2_follow_path_reacquire_v1(monkeypatch):
    monkeypatch.setattr(
        gather_runner.sys,
        "argv",
        ["gather_mission_runner.py", "--gather-control-family", "nav2_follow_path_reacquire_v1"],
    )

    args = gather_runner.parse_args()

    assert args.gather_control_family == "nav2_follow_path_reacquire_v1"


def test_parse_args_allows_nav2_mppi_follow_path_reacquire_v1(monkeypatch):
    monkeypatch.setattr(
        gather_runner.sys,
        "argv",
        ["gather_mission_runner.py", "--gather-control-family", "nav2_mppi_follow_path_reacquire_v1"],
    )

    args = gather_runner.parse_args()

    assert args.gather_control_family == "nav2_mppi_follow_path_reacquire_v1"


def test_parse_args_allows_nav2_followpath_corridor_push_v1(monkeypatch):
    monkeypatch.setattr(
        gather_runner.sys,
        "argv",
        ["gather_mission_runner.py", "--gather-control-family", "nav2_followpath_corridor_push_v1"],
    )

    args = gather_runner.parse_args()

    assert args.gather_control_family == "nav2_followpath_corridor_push_v1"


def test_parse_args_allows_object_centric_gather_policy_v1(monkeypatch):
    monkeypatch.setattr(
        gather_runner.sys,
        "argv",
        ["gather_mission_runner.py", "--gather-control-family", "object_centric_gather_policy_v1"],
    )

    args = gather_runner.parse_args()

    assert args.gather_control_family == "object_centric_gather_policy_v1"


def test_parse_args_allows_ai_push_coast_servo_v1_guarded_live(monkeypatch):
    monkeypatch.setattr(
        gather_runner.sys,
        "argv",
        [
            "gather_mission_runner.py",
            "--gather-control-family",
            "ai_push_coast_servo_v1",
            "--ai-push-coast-mode",
            "guarded_live",
        ],
    )

    args = gather_runner.parse_args()

    assert args.gather_control_family == "ai_push_coast_servo_v1"
    assert args.ai_push_coast_mode == "guarded_live"


def test_parse_args_allows_fetch_to_pose_objective(monkeypatch):
    monkeypatch.setattr(
        gather_runner.sys,
        "argv",
        [
            "gather_mission_runner.py",
            "--mission-objective",
            "fetch_to_pose",
            "--fetch-target-x",
            "2.8",
            "--fetch-target-y",
            "-0.2",
            "--fetch-delivery-radius-m",
            "0.5",
        ],
    )

    args = gather_runner.parse_args()

    assert args.mission_objective == "fetch_to_pose"
    assert args.fetch_target_x == 2.8
    assert args.fetch_target_y == -0.2
    assert args.fetch_delivery_radius_m == 0.5


def test_parse_args_allows_contact_ready_fetch_gate_mode(monkeypatch):
    monkeypatch.setattr(
        gather_runner.sys,
        "argv",
        [
            "gather_mission_runner.py",
            "--mission-objective",
            "fetch_to_pose",
            "--fetch-gate-mode",
            "contact_ready",
        ],
    )

    args = gather_runner.parse_args()

    assert args.fetch_gate_mode == "contact_ready"


def test_nav2_reacquire_goal_generation_covers_zero_plus_minus_and_ready_states():
    zone = gather_runner.build_zone_spec("corral_single_ball_place")
    zero_ball = {"x": 5.448, "y": 0.0, "z": 0.05}
    zero_robot = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    zero_snapshot = gather_runner.pre_stage_arrival_snapshot(zero_robot, zero_ball, zone=zone)

    zero_goal = gather_runner.compute_nav2_reacquire_pre_stage_goal(zero_robot, zero_ball, zero_snapshot)

    assert zero_snapshot is not None
    assert zero_goal["active"] is True
    assert zero_goal["reason"] == "goal_side_reacquire"
    assert zero_goal["goal_pose"]["kind"] == "fallback_flank"
    assert abs(float(zero_goal["goal_pose"]["y"])) >= 0.50
    assert zero_goal["trigger"]["fallback_selected"] is True

    plus_ball = {"x": 4.555261, "y": 2.155261, "z": 0.05}
    minus_ball = {"x": 4.555261, "y": -2.155261, "z": 0.05}
    plus_snapshot = gather_runner.pre_stage_arrival_snapshot(zero_robot, plus_ball, zone=zone)
    minus_snapshot = gather_runner.pre_stage_arrival_snapshot(zero_robot, minus_ball, zone=zone)
    plus_goal = gather_runner.compute_nav2_reacquire_pre_stage_goal(zero_robot, plus_ball, plus_snapshot)
    minus_goal = gather_runner.compute_nav2_reacquire_pre_stage_goal(zero_robot, minus_ball, minus_snapshot)

    assert plus_snapshot is not None
    assert minus_snapshot is not None
    assert plus_goal["active"] is True
    assert minus_goal["active"] is True
    assert float(plus_goal["goal_pose"]["yaw_deg"]) < -90.0
    assert float(minus_goal["goal_pose"]["yaw_deg"]) > 90.0
    assert abs(float(plus_goal["goal_pose"]["x"]) - float(minus_goal["goal_pose"]["x"])) < 1.0e-6
    assert abs(float(plus_goal["goal_pose"]["y"]) + float(minus_goal["goal_pose"]["y"])) < 1.0e-6

    ready_ball = {"x": 1.0, "y": 0.0, "z": 0.05}
    ready_robot = {"x": 0.1, "y": 0.0, "yaw": 0.0}
    ready_snapshot = gather_runner.pre_stage_arrival_snapshot(ready_robot, ready_ball, zone=zone)
    ready_goal = gather_runner.compute_nav2_reacquire_pre_stage_goal(ready_robot, ready_ball, ready_snapshot)

    assert ready_snapshot is not None
    assert ready_snapshot["pre_stage_pose_reached"] is True
    assert ready_goal["active"] is False
    assert ready_goal["reason"] == "pre_stage_handoff_already_ready"


def test_nav2_follow_path_result_parser_handles_success_timeout_and_malformed_output(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)

    success = runner._parse_nav2_follow_path_result(
        'noise\nNAV2_FOLLOW_PATH_RESULT={"dispatch_status":"goal_succeeded","accepted":true,"success":true}',
        rc=0,
    )
    timeout = runner._parse_nav2_follow_path_result(
        'NAV2_FOLLOW_PATH_RESULT={"dispatch_status":"goal_result_timeout","accepted":true,"success":false}',
        rc=0,
    )
    missing = runner._parse_nav2_follow_path_result("plain failure output", rc=3)
    malformed = runner._parse_nav2_follow_path_result("NAV2_FOLLOW_PATH_RESULT={not-json", rc=4)

    assert success["success"] is True
    assert success["dispatch_status"] == "goal_succeeded"
    assert success["process_returncode"] == 0
    assert timeout["dispatch_status"] == "goal_result_timeout"
    assert timeout["success"] is False
    assert missing["dispatch_status"] == "client_error"
    assert missing["process_returncode"] == 3
    assert malformed["dispatch_status"] == "client_error"
    assert malformed["process_returncode"] == 4


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


def test_pre_stage_target_accepts_close_in_ready_band_beyond_legacy_arrival_radius(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    manual_drive_calls: list[dict[str, object]] = []
    robot_pose = {"x": 0.41, "y": 0.0, "yaw": 0.0}
    ball_pose = {"x": 1.0, "y": 0.0, "z": 0.05}

    pre_stage_snapshot = gather_runner.pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=runner.zone)

    assert pre_stage_snapshot is not None
    assert pre_stage_snapshot["pre_stage_pose_distance_m"] > 0.30
    assert pre_stage_snapshot["pre_stage_pose_reached"] is True

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_set_manual_drive",
        lambda *args, **kwargs: manual_drive_calls.append({"args": args, **kwargs}),
    )
    monkeypatch.setattr(
        runner,
        "_control_loop_state",
        lambda **kwargs: ({}, robot_pose, ball_pose),
    )

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-close-in",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert pre_stage_pass is True
    assert payload["pre_stage_pose_world"] == pre_stage_snapshot["pre_stage_pose_world"]
    assert payload["pre_stage_pose_reached"] is True
    assert payload["pre_stage_handoff_pass"] is True
    assert payload["pre_stage_time_s"] >= 0.25
    assert any(call["mode"] == "pre_stage_ready" for call in manual_drive_calls)


def test_pre_stage_target_accepts_deep_close_handoff_band_with_moderate_yaw_error(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    manual_drive_calls: list[dict[str, object]] = []
    robot_pose = {"x": 6.226953, "y": -0.165494, "yaw": -2.351599}
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}

    pre_stage_snapshot = gather_runner.pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=runner.zone)

    assert pre_stage_snapshot is not None
    assert pre_stage_snapshot["deep_close_pre_stage_handoff"] is True
    assert pre_stage_snapshot["pre_stage_pose_reached"] is True

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_set_manual_drive",
        lambda *args, **kwargs: manual_drive_calls.append({"args": args, **kwargs}),
    )
    monkeypatch.setattr(
        runner,
        "_control_loop_state",
        lambda **kwargs: ({}, robot_pose, ball_pose),
    )

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-deep-close",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert pre_stage_pass is True
    assert payload["pre_stage_pose_world"] == pre_stage_snapshot["pre_stage_pose_world"]
    assert payload["pre_stage_pose_reached"] is True
    assert payload["pre_stage_handoff_pass"] is True
    assert payload["pre_stage_time_s"] >= 0.25
    assert any(call["mode"] == "pre_stage_ready" for call in manual_drive_calls)
    assert not any(call["mode"] == "pre_stage_align" for call in manual_drive_calls)


def test_pre_stage_target_leaves_repeated_plus45_escape_stall_and_hands_off(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    manual_drive_calls: list[dict[str, object]] = []
    ball_pose = {"x": 4.555261, "y": 2.155261, "z": 0.05}
    stalled_escape_pose = {"x": 2.687926, "y": 2.345621, "yaw": -2.520141}
    reverse_release_pose = {"x": 4.306274, "y": 2.596228, "yaw": -2.374841}
    close_ready_pose = {"x": 4.852057, "y": 2.736506, "yaw": -2.97762}
    sequence = [
        stalled_escape_pose,
        reverse_release_pose,
        close_ready_pose,
        close_ready_pose,
        close_ready_pose,
        close_ready_pose,
    ]
    index = {"value": 0}

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def fake_control_loop_state(**kwargs):
        current = sequence[min(index["value"], len(sequence) - 1)]
        index["value"] += 1
        return {}, current, ball_pose

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_set_manual_drive",
        lambda *args, **kwargs: manual_drive_calls.append({"args": args, **kwargs}),
    )
    monkeypatch.setattr(runner, "_control_loop_state", fake_control_loop_state)

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-plus45-stall",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    modes = [str(call["mode"]) for call in manual_drive_calls]

    assert pre_stage_pass is True
    assert payload["pre_stage_pose_reached"] is True
    assert payload["pre_stage_handoff_pass"] is True
    assert "pre_stage_escape_goal_side" in modes
    assert "pre_stage_traverse" in modes
    assert modes.index("pre_stage_escape_goal_side") < modes.index("pre_stage_traverse")


def test_pre_stage_target_records_short_horizon_v2_debug_fields(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    runner.gather_control_family = "short_horizon_v2"
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    state_rows: list[dict[str, object]] = []
    ball_pose = {"x": 4.555261, "y": 2.155261, "z": 0.05}
    early_escape_pose = {"x": -0.056707, "y": 0.197428, "yaw": -2.426363}
    close_ready_pose = {"x": 4.852057, "y": 2.736506, "yaw": -2.97762}
    sequence = [
        early_escape_pose,
        close_ready_pose,
        close_ready_pose,
        close_ready_pose,
        close_ready_pose,
    ]
    index = {"value": 0}

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def fake_control_loop_state(**kwargs):
        current = sequence[min(index["value"], len(sequence) - 1)]
        index["value"] += 1
        return {}, current, ball_pose

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda path, payload: state_rows.append(dict(payload)))
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_control_loop_state", fake_control_loop_state)

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-short-horizon",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert pre_stage_pass is True
    assert payload["pre_stage_pose_reached"] is True
    assert state_rows
    first_row = state_rows[0]
    assert first_row["controller_family"] == "short_horizon_v2"
    assert str(first_row["strategy_name"])
    assert str(first_row["objective_name"])
    assert isinstance(first_row["progress_score"], float)
    assert isinstance(first_row["stall_s"], float)
    assert isinstance(first_row["projected_projection_gain"], float)
    assert isinstance(first_row["projected_lateral_gain"], float)
    assert isinstance(first_row["projected_distance_gain"], float)


def test_pre_stage_target_records_object_centric_policy_diagnostics(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    runner.gather_control_family = "object_centric_gather_policy_v1"
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    state_rows: list[dict[str, object]] = []
    ball_pose = {"x": 1.0, "y": 0.0, "z": 0.05}
    ready_pose = {"x": 0.1, "y": 0.0, "yaw": 0.0}
    sequence = [ready_pose, ready_pose, ready_pose, ready_pose]
    index = {"value": 0}

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def fake_control_loop_state(**kwargs):
        current = sequence[min(index["value"], len(sequence) - 1)]
        index["value"] += 1
        return {}, current, ball_pose

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda path, payload: state_rows.append(dict(payload)))
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_control_loop_state", fake_control_loop_state)

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-object-centric",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert pre_stage_pass is True
    assert payload["pre_stage_handoff_pass"] is True
    assert payload["object_centric_policy"]["phase"] == "pre_stage"
    assert state_rows
    first_row = state_rows[0]
    assert first_row["controller_family"] == "object_centric_gather_policy_v1"
    assert first_row["strategy_name"] == "object_centric_gather_policy"
    assert first_row["objective_name"] == "pre_stage_object_state"
    assert first_row["selected_command"]["mode"] == "pre_stage_ready"
    assert first_row["object_centric_policy"]["selected_command"]["mode"] == "pre_stage_ready"
    assert first_row["object_centric_policy"]["guard_rejection_reason"] == ""


def test_pre_stage_target_object_centric_uses_extended_timeout_budget(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.5
    runner.gather_control_family = "object_centric_gather_policy_v1"
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(gather_runner, "DEFAULT_PRE_STAGE_TIMEOUT_S", 1.0)
    monkeypatch.setattr(gather_runner, "DEFAULT_OBJECT_CENTRIC_PRE_STAGE_TIMEOUT_S", 3.0)
    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda path, payload: None)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_control_loop_state", lambda **kwargs: ({}, robot_pose, ball_pose))

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-object-centric-timeout",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    timeout_payload = read_json(mission_root / f"{target.id}_pre_stage_timeout.json")
    assert pre_stage_pass is False
    assert payload["failure_reason"] == "pre_stage_timeout"
    assert payload["pre_stage_time_s"] >= 3.0
    assert payload["pre_stage_timeout_budget_s"] == 3.0
    assert timeout_payload["pre_stage_timeout_budget_s"] == 3.0


def test_pre_stage_target_records_region_funnel_v1_debug_fields(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    runner.gather_control_family = "region_funnel_v1"
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    state_rows: list[dict[str, object]] = []
    ball_pose = {"x": 4.555261, "y": 2.155261, "z": 0.05}
    ready_pose = {"x": 4.852057, "y": 2.736506, "yaw": -2.97762}
    sequence = [ready_pose, ready_pose, ready_pose]
    index = {"value": 0}

    command = gather_runner.PlaceControlCommand(
        mode="region_funnel_pre_stage",
        linear_x=-0.12,
        angular_z=0.34,
        target_speed_scale=1.0,
        rationale="Region funnel override.",
    )
    decision = SimpleNamespace(
        active=True,
        strategy_name="region_funnel_align",
        objective_name="region_funnel_entry",
        progress_score=0.42,
        command=command,
        projected_projection_gain=0.11,
        projected_lateral_gain=0.22,
        projected_distance_gain=0.33,
    )

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def fake_control_loop_state(**kwargs):
        current = sequence[min(index["value"], len(sequence) - 1)]
        index["value"] += 1
        return {}, current, ball_pose

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda path, payload: state_rows.append(dict(payload)))
    monkeypatch.setattr(gather_runner, "decide_region_funnel_pre_stage_command", lambda *args, **kwargs: decision)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_control_loop_state", fake_control_loop_state)

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-region-funnel",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert pre_stage_pass is True
    assert payload["pre_stage_pose_reached"] is True
    assert state_rows
    first_row = state_rows[0]
    assert first_row["controller_family"] == "region_funnel_v1"
    assert first_row["strategy_name"] == "region_funnel_align"
    assert first_row["objective_name"] == "region_funnel_entry"
    assert first_row["progress_score"] == 0.42
    assert first_row["projected_projection_gain"] == 0.11
    assert first_row["projected_lateral_gain"] == 0.22
    assert first_row["projected_distance_gain"] == 0.33
    assert first_row["selected_command"] == command.to_dict()


def test_pre_stage_target_records_constrained_local_planner_debug_fields(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    runner.gather_control_family = "constrained_local_planner_v1"
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    state_rows: list[dict[str, object]] = []
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}
    nonready_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    ready_pose = {"x": 6.348, "y": 0.0, "yaw": gather_runner.math.pi}
    sequence = [nonready_pose, ready_pose, ready_pose, ready_pose, ready_pose]
    index = {"value": 0}

    command = gather_runner.PlaceControlCommand(
        mode="constrained_local_pre_stage",
        linear_x=0.14,
        angular_z=0.42,
        target_speed_scale=0.75,
        rationale="Constrained local planner override.",
    )
    decision = SimpleNamespace(
        active=True,
        strategy_name="advance_left",
        objective_name="constrained_local_planner",
        progress_score=0.52,
        command=command,
        projected_projection_gain=0.12,
        projected_lateral_gain=0.23,
        projected_distance_gain=0.34,
        candidate_count=8,
        accepted_count=5,
        rejected_count=3,
        rejection_reasons=("predicted_ball_contact",),
        projected_snapshot={"pre_stage_pose_reached": False, "robot_on_goal_side": True},
        release_reason="",
        min_ball_clearance_m=0.61,
        ball_motion_m=0.0,
    )

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def fake_control_loop_state(**kwargs):
        current = sequence[min(index["value"], len(sequence) - 1)]
        index["value"] += 1
        return {}, current, ball_pose

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda path, payload: state_rows.append(dict(payload)))
    monkeypatch.setattr(gather_runner, "decide_constrained_local_pre_stage_command", lambda *args, **kwargs: decision)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_control_loop_state", fake_control_loop_state)

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-constrained-local",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert pre_stage_pass is True
    assert payload["pre_stage_pose_reached"] is True
    assert state_rows
    first_row = state_rows[0]
    assert first_row["controller_family"] == "constrained_local_planner_v1"
    assert first_row["strategy_name"] == "advance_left"
    assert first_row["objective_name"] == "constrained_local_planner"
    assert first_row["selected_command"] == command.to_dict()
    assert first_row["local_planner_candidate_count"] == 8
    assert first_row["local_planner_accepted_count"] == 5
    assert first_row["local_planner_rejected_count"] == 3
    assert first_row["local_planner_rejection_reasons"] == ["predicted_ball_contact"]
    assert first_row["local_planner_projected_pre_stage"]["robot_on_goal_side"] is True
    assert first_row["local_planner_release_reason"] == ""
    assert first_row["local_planner_min_ball_clearance_m"] == 0.61


def test_pre_stage_target_records_docking_reacquire_debug_fields(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    runner.gather_control_family = "docking_reacquire_v1"
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    state_rows: list[dict[str, object]] = []
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}
    ready_pose = {"x": 6.348, "y": 0.0, "yaw": gather_runner.math.pi}
    sequence = [ready_pose, ready_pose, ready_pose]
    index = {"value": 0}

    command = gather_runner.PlaceControlCommand(
        mode="docking_reacquire_pre_stage",
        linear_x=0.10,
        angular_z=0.24,
        target_speed_scale=0.70,
        rationale="Docking reacquire override.",
    )
    decision = SimpleNamespace(
        active=True,
        strategy_name="docking_entry_left",
        objective_name="docking_reacquire",
        progress_score=0.62,
        command=command,
        projected_projection_gain=0.13,
        projected_lateral_gain=0.24,
        projected_distance_gain=0.35,
        projected_snapshot={"pre_stage_pose_reached": False, "robot_on_goal_side": True},
        release_reason="",
        release_blockers=("robot_on_goal_side",),
        dock_pose={"x": 6.548, "y": 0.75},
        side_sign=1.0,
        target_distance_m=6.59,
        target_heading_error_rad=0.11,
        segment_ball_clearance_m=0.62,
        min_ball_clearance_m=0.71,
        ball_motion_m=0.0,
    )

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def fake_control_loop_state(**kwargs):
        current = sequence[min(index["value"], len(sequence) - 1)]
        index["value"] += 1
        return {}, current, ball_pose

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda path, payload: state_rows.append(dict(payload)))
    monkeypatch.setattr(gather_runner, "decide_docking_reacquire_pre_stage_command", lambda *args, **kwargs: decision)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_control_loop_state", fake_control_loop_state)

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-docking-reacquire",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert pre_stage_pass is True
    assert payload["pre_stage_pose_reached"] is True
    assert state_rows
    first_row = state_rows[0]
    assert first_row["controller_family"] == "docking_reacquire_v1"
    assert first_row["strategy_name"] == "docking_entry_left"
    assert first_row["objective_name"] == "docking_reacquire"
    assert first_row["selected_command"] == command.to_dict()
    assert first_row["docking_reacquire_active"] is True
    assert first_row["docking_reacquire_release_reason"] == ""
    assert first_row["docking_reacquire_release_blockers"] == ["robot_on_goal_side"]
    assert first_row["docking_reacquire_dock_pose"] == {"x": 6.548, "y": 0.75}
    assert first_row["docking_reacquire_side_sign"] == 1.0
    assert first_row["docking_reacquire_target_distance_m"] == 6.59
    assert first_row["docking_reacquire_segment_ball_clearance_m"] == 0.62
    assert first_row["docking_reacquire_min_ball_clearance_m"] == 0.71
    assert first_row["docking_reacquire_handoff_ready_measured"] is True
    assert first_row["docking_reacquire_handoff_ready_projected"] is False
    assert first_row["docking_reacquire_release_allowed"] is False


def test_pre_stage_target_records_handoff_yaw_servo_debug_fields(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    runner.gather_control_family = "handoff_yaw_servo_v1"
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    state_rows: list[dict[str, object]] = []
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}
    ready_pose = {"x": 6.348, "y": 0.0, "yaw": gather_runner.math.pi}
    sequence = [ready_pose, ready_pose, ready_pose]
    index = {"value": 0}

    command = gather_runner.PlaceControlCommand(
        mode="handoff_yaw_servo_pre_stage",
        linear_x=0.0,
        angular_z=0.32,
        target_speed_scale=0.0,
        rationale="Handoff yaw servo override.",
    )
    decision = SimpleNamespace(
        active=True,
        strategy_name="handoff_yaw_servo",
        objective_name="handoff_yaw_servo",
        progress_score=12.5,
        command=command,
        release_reason="",
        release_blockers=(),
        yaw_error_deg=63.0,
        yaw_error_rad=1.099557,
        current_yaw_rad=2.042035,
        target_yaw_rad=3.141593,
        angular_z=0.32,
        ball_motion_m=0.0,
        projected_snapshot={"pre_stage_pose_reached": False, "yaw_error_deg": 50.5},
        handoff_ready_projected=False,
    )

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def fake_control_loop_state(**kwargs):
        current = sequence[min(index["value"], len(sequence) - 1)]
        index["value"] += 1
        return {}, current, ball_pose

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda path, payload: state_rows.append(dict(payload)))
    monkeypatch.setattr(gather_runner, "decide_handoff_yaw_servo_pre_stage_command", lambda *args, **kwargs: decision)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_control_loop_state", fake_control_loop_state)

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-handoff-yaw-servo",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert pre_stage_pass is True
    assert payload["pre_stage_pose_reached"] is True
    assert state_rows
    first_row = state_rows[0]
    assert first_row["controller_family"] == "handoff_yaw_servo_v1"
    assert first_row["strategy_name"] == "handoff_yaw_servo"
    assert first_row["objective_name"] == "handoff_yaw_servo"
    assert first_row["selected_command"] == command.to_dict()
    assert first_row["handoff_yaw_servo_active"] is True
    assert first_row["handoff_yaw_servo_release_reason"] == ""
    assert first_row["handoff_yaw_servo_release_blockers"] == []
    assert first_row["handoff_yaw_servo_yaw_error_deg"] == 63.0
    assert first_row["handoff_yaw_servo_yaw_error_rad"] == 1.099557
    assert first_row["handoff_yaw_servo_current_yaw_rad"] == 2.042035
    assert first_row["handoff_yaw_servo_target_yaw_rad"] == 3.141593
    assert first_row["handoff_yaw_servo_angular_z"] == 0.32
    assert first_row["handoff_yaw_servo_ball_motion_m"] == 0.0
    assert first_row["handoff_yaw_servo_projected_pre_stage"]["yaw_error_deg"] == 50.5
    assert first_row["handoff_yaw_servo_handoff_ready_measured"] is True
    assert first_row["handoff_yaw_servo_handoff_ready_projected"] is False


def test_pre_stage_target_records_pre_stage_reacquire_fsm_debug_fields(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    runner.gather_control_family = "pre_stage_reacquire_fsm_v1"
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    state_rows: list[dict[str, object]] = []
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}
    ready_pose = {"x": 6.348, "y": 0.0, "yaw": gather_runner.math.pi}
    sequence = [ready_pose, ready_pose, ready_pose]
    index = {"value": 0}

    command = gather_runner.PlaceControlCommand(
        mode="pre_stage_reacquire_fsm",
        linear_x=0.12,
        angular_z=0.28,
        target_speed_scale=0.70,
        rationale="Pre-stage reacquire FSM override.",
    )
    decision = SimpleNamespace(
        active=True,
        phase="goal_side_escape",
        strategy_name="goal_side_escape_left",
        objective_name="pre_stage_reacquire_fsm",
        progress_score=0.72,
        command=command,
        release_reason="",
        release_blockers=("robot_on_goal_side",),
        measured_snapshot={"pre_stage_pose_reached": False, "robot_on_goal_side": True},
        projected_snapshot={"pre_stage_pose_reached": False, "robot_on_goal_side": False},
        measured_handoff_ready=False,
        projected_handoff_ready=False,
        projection_m=5.44,
        lateral_error_m=0.15,
        distance_m=6.34,
        yaw_error_deg=180.0,
        projected_projection_gain=0.14,
        projected_lateral_gain=0.03,
        projected_distance_gain=0.09,
        projected_yaw_gain_deg=8.0,
        ball_motion_m=0.0,
        min_ball_clearance_m=0.69,
        target_pose={"x": 6.548, "y": 0.85},
        target_distance_m=6.60,
        target_heading_error_rad=0.13,
        candidate_count=1,
        accepted_count=1,
        rejected_count=0,
        rejection_reasons=(),
    )

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def fake_control_loop_state(**kwargs):
        current = sequence[min(index["value"], len(sequence) - 1)]
        index["value"] += 1
        return {}, current, ball_pose

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda path, payload: state_rows.append(dict(payload)))
    monkeypatch.setattr(gather_runner, "decide_pre_stage_reacquire_fsm_command", lambda *args, **kwargs: decision)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_control_loop_state", fake_control_loop_state)

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-reacquire-fsm",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert pre_stage_pass is True
    assert payload["pre_stage_pose_reached"] is True
    assert state_rows
    first_row = state_rows[0]
    assert first_row["controller_family"] == "pre_stage_reacquire_fsm_v1"
    assert first_row["strategy_name"] == "goal_side_escape_left"
    assert first_row["objective_name"] == "pre_stage_reacquire_fsm"
    assert first_row["selected_command"] == command.to_dict()
    assert first_row["pre_stage_reacquire_fsm_active"] is True
    assert first_row["pre_stage_reacquire_fsm_phase"] == "goal_side_escape"
    assert first_row["pre_stage_reacquire_fsm_release_reason"] == ""
    assert first_row["pre_stage_reacquire_fsm_release_blockers"] == ["robot_on_goal_side"]
    assert first_row["pre_stage_reacquire_fsm_measured_handoff_ready"] is False
    assert first_row["pre_stage_reacquire_fsm_projected_handoff_ready"] is False
    assert first_row["pre_stage_reacquire_fsm_measured_pre_stage"]["robot_on_goal_side"] is True
    assert first_row["pre_stage_reacquire_fsm_projected_pre_stage"]["robot_on_goal_side"] is False
    assert first_row["pre_stage_reacquire_fsm_projection_m"] == 5.44
    assert first_row["pre_stage_reacquire_fsm_lateral_error_m"] == 0.15
    assert first_row["pre_stage_reacquire_fsm_distance_m"] == 6.34
    assert first_row["pre_stage_reacquire_fsm_yaw_error_deg"] == 180.0
    assert first_row["pre_stage_reacquire_fsm_projected_yaw_gain_deg"] == 8.0
    assert first_row["pre_stage_reacquire_fsm_ball_motion_m"] == 0.0
    assert first_row["pre_stage_reacquire_fsm_min_ball_clearance_m"] == 0.69
    assert first_row["pre_stage_reacquire_fsm_target_pose"] == {"x": 6.548, "y": 0.85}
    assert first_row["pre_stage_reacquire_fsm_candidate_count"] == 1
    assert first_row["pre_stage_reacquire_fsm_accepted_count"] == 1
    assert first_row["pre_stage_reacquire_fsm_rejected_count"] == 0
    assert first_row["pre_stage_reacquire_fsm_rejection_reasons"] == []


def test_pre_stage_target_aborts_fsm_on_ball_motion_guard(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    runner.gather_control_family = "pre_stage_reacquire_fsm_v1"
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    state_rows: list[dict[str, object]] = []
    command_log: list[dict[str, object]] = []
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    ball_poses = [
        {"x": 5.448, "y": 0.0, "z": 0.05},
        {"x": 5.501, "y": 0.0, "z": 0.05},
    ]
    index = {"value": 0}
    active_command = gather_runner.PlaceControlCommand(
        mode="pre_stage_reacquire_fsm",
        linear_x=0.10,
        angular_z=0.20,
        target_speed_scale=0.70,
        rationale="Pre-stage reacquire FSM override.",
    )

    def fake_decision(*args, **kwargs):
        ball_motion_m = kwargs.get("ball_motion_m")
        if ball_motion_m is not None and ball_motion_m > 0.035:
            return SimpleNamespace(
                active=False,
                phase="baseline_release",
                strategy_name="",
                objective_name="",
                progress_score=None,
                command=None,
                release_reason="ball_motion_guard",
                release_blockers=("ball_motion_guard",),
                measured_snapshot={"pre_stage_pose_reached": False},
                projected_snapshot={},
                measured_handoff_ready=False,
                projected_handoff_ready=None,
                projection_m=5.44,
                lateral_error_m=0.0,
                distance_m=6.34,
                yaw_error_deg=180.0,
                projected_yaw_gain_deg=None,
                ball_motion_m=ball_motion_m,
                min_ball_clearance_m=None,
                target_pose={},
                target_distance_m=None,
                target_heading_error_rad=None,
                candidate_count=0,
                accepted_count=0,
                rejected_count=0,
                rejection_reasons=(),
            )
        return SimpleNamespace(
            active=True,
            phase="goal_side_escape",
            strategy_name="goal_side_escape_left",
            objective_name="pre_stage_reacquire_fsm",
            progress_score=0.2,
            command=active_command,
            release_reason="",
            release_blockers=("robot_on_goal_side",),
            measured_snapshot={"pre_stage_pose_reached": False},
            projected_snapshot={"pre_stage_pose_reached": False},
            measured_handoff_ready=False,
            projected_handoff_ready=False,
            projection_m=5.44,
            lateral_error_m=0.0,
            distance_m=6.34,
            yaw_error_deg=180.0,
            projected_projection_gain=0.1,
            projected_lateral_gain=0.0,
            projected_distance_gain=0.1,
            projected_yaw_gain_deg=0.0,
            ball_motion_m=ball_motion_m,
            min_ball_clearance_m=0.7,
            target_pose={},
            target_distance_m=6.0,
            target_heading_error_rad=0.0,
            candidate_count=1,
            accepted_count=1,
            rejected_count=0,
            rejection_reasons=(),
        )

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def fake_control_loop_state(**kwargs):
        ball_pose = ball_poses[min(index["value"], len(ball_poses) - 1)]
        index["value"] += 1
        return {}, robot_pose, ball_pose

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda path, payload: state_rows.append(dict(payload)))
    monkeypatch.setattr(gather_runner, "decide_pre_stage_reacquire_fsm_command", fake_decision)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
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
    monkeypatch.setattr(runner, "_control_loop_state", fake_control_loop_state)

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-reacquire-fsm-ball-motion",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert pre_stage_pass is False
    assert payload["failure_reason"] == "pre_stage_ball_motion_guard"
    assert payload["pre_stage_handoff_pass"] is False
    assert state_rows[-1]["pre_stage_reacquire_fsm_release_reason"] == "ball_motion_guard"
    assert state_rows[-1]["selected_command"]["mode"] == "pre_stage_reacquire_fsm_abort"
    assert command_log[-1]["enabled"] is False
    assert command_log[-1]["mode"] == "pre_stage_ball_motion_guard"


def test_pre_stage_target_records_pre_stage_path_tracker_debug_fields(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    runner.gather_control_family = "pre_stage_path_tracker_v1"
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    state_rows: list[dict[str, object]] = []
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}
    ready_pose = {"x": 6.348, "y": 0.0, "yaw": gather_runner.math.pi}
    sequence = [ready_pose, ready_pose, ready_pose]
    index = {"value": 0}

    command = gather_runner.PlaceControlCommand(
        mode="pre_stage_path_tracker",
        linear_x=0.12,
        angular_z=-0.22,
        target_speed_scale=0.70,
        rationale="Pre-stage path tracker override.",
    )
    decision = SimpleNamespace(
        active=True,
        waypoint_index=1,
        waypoint_kind="approach",
        waypoint_count=4,
        strategy_name="path_approach",
        objective_name="pre_stage_path_tracker",
        progress_score=112.5,
        command=command,
        release_reason="",
        release_blockers=("distance_not_converged",),
        measured_snapshot={"pre_stage_pose_reached": False, "robot_on_goal_side": False},
        projected_snapshot={"pre_stage_pose_reached": False, "pre_stage_pose_distance_m": 0.72},
        measured_handoff_ready=False,
        projected_handoff_ready=False,
        waypoint_pose={"x": 6.568, "y": -0.82, "yaw": 3.141593},
        waypoint_distance_m=0.91,
        waypoint_heading_error_rad=-0.18,
        waypoint_reached=True,
        projection_m=-0.48,
        lateral_error_m=0.36,
        distance_m=0.94,
        yaw_error_deg=35.0,
        projected_projection_gain=0.04,
        projected_lateral_gain=0.03,
        projected_distance_gain=0.08,
        projected_yaw_gain_deg=4.0,
        ball_motion_m=0.0,
        min_ball_clearance_m=0.71,
        segment_ball_clearance_m=0.88,
        candidate_count=1,
        accepted_count=1,
        rejected_count=0,
        rejection_reasons=(),
    )

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def fake_control_loop_state(**kwargs):
        current = sequence[min(index["value"], len(sequence) - 1)]
        index["value"] += 1
        return {}, current, ball_pose

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda path, payload: state_rows.append(dict(payload)))
    monkeypatch.setattr(gather_runner, "decide_pre_stage_path_tracker_command", lambda *args, **kwargs: decision)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_control_loop_state", fake_control_loop_state)

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-path-tracker",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert pre_stage_pass is True
    assert payload["pre_stage_pose_reached"] is True
    assert state_rows
    first_row = state_rows[0]
    assert first_row["controller_family"] == "pre_stage_path_tracker_v1"
    assert first_row["strategy_name"] == "path_approach"
    assert first_row["objective_name"] == "pre_stage_path_tracker"
    assert first_row["selected_command"] == command.to_dict()
    assert first_row["pre_stage_path_tracker_active"] is True
    assert first_row["pre_stage_path_tracker_waypoint_index"] == 1
    assert first_row["pre_stage_path_tracker_waypoint_kind"] == "approach"
    assert first_row["pre_stage_path_tracker_waypoint_count"] == 4
    assert first_row["pre_stage_path_tracker_release_reason"] == ""
    assert first_row["pre_stage_path_tracker_release_blockers"] == ["distance_not_converged"]
    assert first_row["pre_stage_path_tracker_measured_handoff_ready"] is False
    assert first_row["pre_stage_path_tracker_projected_handoff_ready"] is False
    assert first_row["pre_stage_path_tracker_measured_pre_stage"]["robot_on_goal_side"] is False
    assert first_row["pre_stage_path_tracker_projected_pre_stage"]["pre_stage_pose_distance_m"] == 0.72
    assert first_row["pre_stage_path_tracker_waypoint_pose"] == {"x": 6.568, "y": -0.82, "yaw": 3.141593}
    assert first_row["pre_stage_path_tracker_waypoint_distance_m"] == 0.91
    assert first_row["pre_stage_path_tracker_waypoint_heading_error_rad"] == -0.18
    assert first_row["pre_stage_path_tracker_waypoint_reached"] is True
    assert first_row["pre_stage_path_tracker_projection_m"] == -0.48
    assert first_row["pre_stage_path_tracker_lateral_error_m"] == 0.36
    assert first_row["pre_stage_path_tracker_distance_m"] == 0.94
    assert first_row["pre_stage_path_tracker_yaw_error_deg"] == 35.0
    assert first_row["pre_stage_path_tracker_projected_yaw_gain_deg"] == 4.0
    assert first_row["pre_stage_path_tracker_ball_motion_m"] == 0.0
    assert first_row["pre_stage_path_tracker_min_ball_clearance_m"] == 0.71
    assert first_row["pre_stage_path_tracker_segment_ball_clearance_m"] == 0.88
    assert first_row["pre_stage_path_tracker_candidate_count"] == 1
    assert first_row["pre_stage_path_tracker_accepted_count"] == 1
    assert first_row["pre_stage_path_tracker_rejected_count"] == 0
    assert first_row["pre_stage_path_tracker_rejection_reasons"] == []
    assert first_row["pre_stage_path_tracker_progress_timeout"] is False


def test_pre_stage_target_records_pre_stage_trajectory_owner_debug_fields(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    runner.gather_control_family = "pre_stage_trajectory_owner_v1"
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    state_rows: list[dict[str, object]] = []
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}
    ready_pose = {"x": 6.348, "y": 0.0, "yaw": gather_runner.math.pi}
    sequence = [ready_pose, ready_pose, ready_pose]
    index = {"value": 0}

    command = gather_runner.PlaceControlCommand(
        mode="pre_stage_trajectory_owner",
        linear_x=0.18,
        angular_z=-0.24,
        target_speed_scale=0.78,
        rationale="Pre-stage trajectory owner override.",
    )
    decision = SimpleNamespace(
        active=True,
        milestone_index=1,
        milestone_kind="corridor_approach",
        milestone_count=4,
        strategy_name="trajectory_corridor_approach",
        objective_name="pre_stage_trajectory_owner",
        progress_score=135.5,
        progress_rate_mps=0.11,
        command=command,
        release_reason="",
        release_blockers=("distance_not_converged",),
        measured_snapshot={"pre_stage_pose_reached": False, "robot_on_goal_side": False},
        projected_snapshot={"pre_stage_pose_reached": False, "pre_stage_pose_distance_m": 0.64},
        measured_handoff_ready=False,
        projected_handoff_ready=False,
        target_pose={"x": 6.42, "y": -0.74, "yaw": 3.141593},
        target_distance_m=0.82,
        target_heading_error_rad=-0.16,
        milestone_reached=True,
        side_sign=-1.0,
        next_side_sign=-1.0,
        replan_count=0,
        next_replan_count=0,
        replan_reason="",
        projection_m=-0.42,
        lateral_error_m=0.31,
        distance_m=0.82,
        yaw_error_deg=32.0,
        projected_projection_gain=0.05,
        projected_lateral_gain=0.04,
        projected_distance_gain=0.09,
        projected_yaw_gain_deg=5.0,
        ball_motion_m=0.0,
        min_ball_clearance_m=0.76,
        segment_ball_clearance_m=0.92,
        measured_ball_clearance_m=1.08,
        candidate_count=1,
        accepted_count=1,
        rejected_count=0,
        rejection_reasons=(),
    )

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def fake_control_loop_state(**kwargs):
        current = sequence[min(index["value"], len(sequence) - 1)]
        index["value"] += 1
        return {}, current, ball_pose

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda path, payload: state_rows.append(dict(payload)))
    monkeypatch.setattr(gather_runner, "decide_pre_stage_trajectory_owner_command", lambda *args, **kwargs: decision)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_control_loop_state", fake_control_loop_state)

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-trajectory-owner",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert pre_stage_pass is True
    assert payload["pre_stage_pose_reached"] is True
    assert state_rows
    first_row = state_rows[0]
    assert first_row["controller_family"] == "pre_stage_trajectory_owner_v1"
    assert first_row["strategy_name"] == "trajectory_corridor_approach"
    assert first_row["objective_name"] == "pre_stage_trajectory_owner"
    assert first_row["selected_command"] == command.to_dict()
    assert first_row["pre_stage_trajectory_owner_active"] is True
    assert first_row["pre_stage_trajectory_owner_milestone_index"] == 1
    assert first_row["pre_stage_trajectory_owner_milestone_kind"] == "corridor_approach"
    assert first_row["pre_stage_trajectory_owner_milestone_count"] == 4
    assert first_row["pre_stage_trajectory_owner_target_pose"] == {"x": 6.42, "y": -0.74, "yaw": 3.141593}
    assert first_row["pre_stage_trajectory_owner_target_distance_m"] == 0.82
    assert first_row["pre_stage_trajectory_owner_target_heading_error_rad"] == -0.16
    assert first_row["pre_stage_trajectory_owner_milestone_reached"] is True
    assert first_row["pre_stage_trajectory_owner_progress_rate_mps"] == 0.11
    assert first_row["pre_stage_trajectory_owner_side_sign"] == -1.0
    assert first_row["pre_stage_trajectory_owner_replan_count"] == 0
    assert first_row["pre_stage_trajectory_owner_replan_reason"] == ""
    assert first_row["pre_stage_trajectory_owner_release_reason"] == ""
    assert first_row["pre_stage_trajectory_owner_release_blockers"] == ["distance_not_converged"]
    assert first_row["pre_stage_trajectory_owner_measured_handoff_ready"] is False
    assert first_row["pre_stage_trajectory_owner_projected_handoff_ready"] is False
    assert first_row["pre_stage_trajectory_owner_measured_pre_stage"]["robot_on_goal_side"] is False
    assert first_row["pre_stage_trajectory_owner_projected_pre_stage"]["pre_stage_pose_distance_m"] == 0.64
    assert first_row["pre_stage_trajectory_owner_projection_m"] == -0.42
    assert first_row["pre_stage_trajectory_owner_lateral_error_m"] == 0.31
    assert first_row["pre_stage_trajectory_owner_distance_m"] == 0.82
    assert first_row["pre_stage_trajectory_owner_yaw_error_deg"] == 32.0
    assert first_row["pre_stage_trajectory_owner_projected_yaw_gain_deg"] == 5.0
    assert first_row["pre_stage_trajectory_owner_ball_motion_m"] == 0.0
    assert first_row["pre_stage_trajectory_owner_min_ball_clearance_m"] == 0.76
    assert first_row["pre_stage_trajectory_owner_segment_ball_clearance_m"] == 0.92
    assert first_row["pre_stage_trajectory_owner_measured_ball_clearance_m"] == 1.08
    assert first_row["pre_stage_trajectory_owner_candidate_count"] == 1
    assert first_row["pre_stage_trajectory_owner_accepted_count"] == 1
    assert first_row["pre_stage_trajectory_owner_rejected_count"] == 0
    assert first_row["pre_stage_trajectory_owner_rejection_reasons"] == []


def test_pre_stage_target_aborts_path_tracker_on_ball_motion_guard(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    runner.gather_control_family = "pre_stage_path_tracker_v1"
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    state_rows: list[dict[str, object]] = []
    command_log: list[dict[str, object]] = []
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    ball_poses = [
        {"x": 5.448, "y": 0.0, "z": 0.05},
        {"x": 5.501, "y": 0.0, "z": 0.05},
    ]
    index = {"value": 0}
    active_command = gather_runner.PlaceControlCommand(
        mode="pre_stage_path_tracker",
        linear_x=0.10,
        angular_z=0.20,
        target_speed_scale=0.70,
        rationale="Pre-stage path tracker override.",
    )

    def fake_decision(*args, **kwargs):
        ball_motion_m = kwargs.get("ball_motion_m")
        if ball_motion_m is not None and ball_motion_m > 0.035:
            return SimpleNamespace(
                active=False,
                waypoint_index=0,
                waypoint_kind="",
                waypoint_count=0,
                strategy_name="",
                objective_name="",
                progress_score=None,
                command=None,
                release_reason="ball_motion_guard",
                release_blockers=("ball_motion_guard",),
                measured_snapshot={"pre_stage_pose_reached": False},
                projected_snapshot={},
                measured_handoff_ready=False,
                projected_handoff_ready=None,
                waypoint_pose={},
                waypoint_distance_m=None,
                waypoint_heading_error_rad=None,
                waypoint_reached=False,
                projection_m=5.44,
                lateral_error_m=0.0,
                distance_m=6.34,
                yaw_error_deg=180.0,
                projected_yaw_gain_deg=None,
                ball_motion_m=ball_motion_m,
                min_ball_clearance_m=None,
                segment_ball_clearance_m=None,
                candidate_count=0,
                accepted_count=0,
                rejected_count=0,
                rejection_reasons=(),
            )
        return SimpleNamespace(
            active=True,
            waypoint_index=0,
            waypoint_kind="escape",
            waypoint_count=4,
            strategy_name="path_escape",
            objective_name="pre_stage_path_tracker",
            progress_score=0.2,
            command=active_command,
            release_reason="",
            release_blockers=("robot_on_goal_side",),
            measured_snapshot={"pre_stage_pose_reached": False},
            projected_snapshot={"pre_stage_pose_reached": False},
            measured_handoff_ready=False,
            projected_handoff_ready=False,
            waypoint_pose={},
            waypoint_distance_m=6.0,
            waypoint_heading_error_rad=0.0,
            waypoint_reached=False,
            projection_m=5.44,
            lateral_error_m=0.0,
            distance_m=6.34,
            yaw_error_deg=180.0,
            projected_projection_gain=0.1,
            projected_lateral_gain=0.0,
            projected_distance_gain=0.1,
            projected_yaw_gain_deg=0.0,
            ball_motion_m=ball_motion_m,
            min_ball_clearance_m=0.7,
            segment_ball_clearance_m=0.8,
            candidate_count=1,
            accepted_count=1,
            rejected_count=0,
            rejection_reasons=(),
        )

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def fake_control_loop_state(**kwargs):
        ball_pose = ball_poses[min(index["value"], len(ball_poses) - 1)]
        index["value"] += 1
        return {}, robot_pose, ball_pose

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda path, payload: state_rows.append(dict(payload)))
    monkeypatch.setattr(gather_runner, "decide_pre_stage_path_tracker_command", fake_decision)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
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
    monkeypatch.setattr(runner, "_control_loop_state", fake_control_loop_state)

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-path-tracker-ball-motion",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert pre_stage_pass is False
    assert payload["failure_reason"] == "pre_stage_path_tracker_ball_motion_guard"
    assert payload["pre_stage_handoff_pass"] is False
    assert state_rows[-1]["pre_stage_path_tracker_release_reason"] == "ball_motion_guard"
    assert state_rows[-1]["selected_command"]["mode"] == "pre_stage_path_tracker_abort"
    assert command_log[-1]["enabled"] is False
    assert command_log[-1]["mode"] == "pre_stage_path_tracker_ball_motion_guard"


def test_nav2_reacquire_does_not_activate_when_pre_stage_handoff_ready(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    runner.gather_control_family = "nav2_reacquire_v1"
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    command_log: list[dict[str, object]] = []
    ball_pose = {"x": 1.0, "y": 0.0, "z": 0.05}
    ready_robot_pose = {"x": 0.1, "y": 0.0, "yaw": 0.0}

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def forbidden_dispatch(**kwargs):
        raise AssertionError(f"nav2 reacquire should not dispatch when handoff is ready: {kwargs}")

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_dispatch_nav2_reacquire_goal", forbidden_dispatch)
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
    monkeypatch.setattr(
        runner,
        "_control_loop_state",
        lambda **kwargs: ({"compose_project": "gate"}, ready_robot_pose, ball_pose),
    )

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-nav2-ready",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert pre_stage_pass is True
    assert payload["pre_stage_handoff_pass"] is True
    assert all(str(item["mode"]) != "nav2_reacquire_goal" for item in command_log)


def test_nav2_reacquire_failed_dispatch_returns_pre_stage_failure_with_goal_side_evidence(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    runner.gather_control_family = "nav2_reacquire_v1"
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    state_rows: list[dict[str, object]] = []
    command_log: list[dict[str, object]] = []
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}
    dispatch_calls: list[dict[str, object]] = []

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def fake_dispatch(**kwargs):
        dispatch_calls.append(dict(kwargs))
        return {
            "dispatch_status": "server_unavailable",
            "accepted": False,
            "success": False,
            "status_code": 0,
            "elapsed_s": 0.25,
            "error": "nav2_action_server_unavailable",
        }

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda path, payload: state_rows.append(dict(payload)))
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_dispatch_nav2_reacquire_goal", fake_dispatch)
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
    monkeypatch.setattr(
        runner,
        "_control_loop_state",
        lambda **kwargs: ({"compose_project": "gate"}, robot_pose, ball_pose),
    )

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-nav2-fail",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert pre_stage_pass is False
    assert payload["failure_reason"] == "nav2_reacquire_failed"
    assert payload["failure_stage"] == "pre_stage"
    assert payload["approach_failure_reason"] == "entered_goal_side_before_capture"
    assert payload["entered_goal_side_before_capture"] is True
    assert payload["nav2_reacquire_result"]["dispatch_status"] == "server_unavailable"
    assert dispatch_calls
    assert dispatch_calls[0]["compose_project"] == "gate"
    assert dispatch_calls[0]["goal_pose"]["kind"] == "fallback_flank"
    assert any(item["event_type"] == "nav2_reacquire_dispatch" for item in state_rows)
    complete_rows = [item for item in state_rows if item["event_type"] == "nav2_reacquire_complete"]
    assert complete_rows
    assert complete_rows[0]["controller_family"] == "nav2_reacquire_v1"
    assert complete_rows[0]["nav2_dispatch_status"] == "server_unavailable"
    assert complete_rows[0]["pre_stage_at_dispatch"]["entered_goal_side_before_capture"] is True
    assert complete_rows[0]["pre_stage_at_completion"]["entered_goal_side_before_capture"] is True
    assert command_log[0]["mode"] == "nav2_reacquire_goal"
    assert command_log[-1]["mode"] == "nav2_reacquire_failed"
    assert all(not bool(item["enabled"]) for item in command_log)


def test_nav2_reacquire_success_returns_to_baseline_pre_stage_handoff(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    runner.gather_control_family = "nav2_reacquire_v1"
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    state_rows: list[dict[str, object]] = []
    command_log: list[dict[str, object]] = []
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}
    initial_robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    ready_robot_pose = {"x": 6.348, "y": 0.0, "yaw": gather_runner.math.pi}
    states = [
        ({"compose_project": "gate"}, initial_robot_pose, ball_pose),
        ({"compose_project": "gate"}, ready_robot_pose, ball_pose),
        ({"compose_project": "gate"}, ready_robot_pose, ball_pose),
        ({"compose_project": "gate"}, ready_robot_pose, ball_pose),
        ({"compose_project": "gate"}, ready_robot_pose, ball_pose),
    ]

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def fake_control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {"compose_project": "gate"}, ready_robot_pose, ball_pose

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda path, payload: state_rows.append(dict(payload)))
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_dispatch_nav2_reacquire_goal",
        lambda **kwargs: {
            "dispatch_status": "goal_succeeded",
            "accepted": True,
            "success": True,
            "status_code": 4,
            "elapsed_s": 2.0,
            "error": "",
        },
    )
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
    monkeypatch.setattr(runner, "_control_loop_state", fake_control_loop_state)

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-nav2-success",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    modes = [str(item["mode"]) for item in command_log]
    complete_rows = [item for item in state_rows if item.get("event_type") == "nav2_reacquire_complete"]

    assert pre_stage_pass is True
    assert payload["pre_stage_pose_reached"] is True
    assert payload["pre_stage_handoff_pass"] is True
    assert "nav2_reacquire_goal" in modes
    assert "nav2_reacquire_complete" in modes
    assert modes[-1] == "pre_stage_ready"
    assert command_log[-1]["enabled"] is False
    assert complete_rows
    assert complete_rows[0]["nav2_dispatch_status"] == "goal_succeeded"
    assert complete_rows[0]["pre_stage_at_completion"]["pre_stage_pose_reached"] is True


def test_nav2_follow_path_reacquire_does_not_activate_when_pre_stage_handoff_ready(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    runner.gather_control_family = "nav2_follow_path_reacquire_v1"
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    command_log: list[dict[str, object]] = []
    ball_pose = {"x": 1.0, "y": 0.0, "z": 0.05}
    ready_robot_pose = {"x": 0.1, "y": 0.0, "yaw": 0.0}

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def forbidden_dispatch(**kwargs):
        raise AssertionError(f"FollowPath should not dispatch when handoff is ready: {kwargs}")

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_dispatch_nav2_follow_path_reacquire", forbidden_dispatch)
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
    monkeypatch.setattr(
        runner,
        "_control_loop_state",
        lambda **kwargs: ({"compose_project": "gate"}, ready_robot_pose, ball_pose),
    )

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-follow-path-ready",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert pre_stage_pass is True
    assert payload["pre_stage_handoff_pass"] is True
    assert all(str(item["mode"]) != "nav2_follow_path_reacquire_path" for item in command_log)


def test_nav2_follow_path_failed_dispatch_returns_pre_stage_failure_with_goal_side_evidence(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    runner.gather_control_family = "nav2_follow_path_reacquire_v1"
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    state_rows: list[dict[str, object]] = []
    command_log: list[dict[str, object]] = []
    dispatch_calls: list[dict[str, object]] = []
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def fake_dispatch(**kwargs):
        dispatch_calls.append(dict(kwargs))
        return {
            "dispatch_status": "server_unavailable",
            "accepted": False,
            "success": False,
            "status_code": 0,
            "elapsed_s": 0.25,
            "error": "follow_path_action_server_unavailable",
            "feedback_count": 2,
            "feedback_samples": [{"elapsed_s": 0.1, "feedback": {"speed": 0.02}}],
            "feedback_last": {"elapsed_s": 0.2, "feedback": {"speed": 0.01}},
            "cancel_requested": False,
            "status_text": "STATUS_UNKNOWN",
            "controller_log_excerpt": {"excerpt": ["controller_server: MPPI failed to converge"]},
            "cmd_vel_counts": {"/cmd_vel_nav": 3},
            "cmd_vel_samples": [{"elapsed_s": 0.1, "topic": "/cmd_vel_nav", "linear_x": 0.02, "angular_z": 0.1}],
            "odom_count": 2,
            "odom_delta": {"distance_m": 0.0, "dyaw_deg": 0.0},
            "path_progress_samples": [{"elapsed_s": 0.2, "terminal_path_distance_m": 6.348, "terminal_yaw_error_deg": 180.0}],
            "path_progress_last": {"elapsed_s": 0.2, "terminal_path_distance_m": 6.348, "terminal_yaw_error_deg": 180.0},
        }

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda path, payload: state_rows.append(dict(payload)))
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_dispatch_nav2_follow_path_reacquire", fake_dispatch)
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
    monkeypatch.setattr(
        runner,
        "_control_loop_state",
        lambda **kwargs: ({"compose_project": "gate"}, robot_pose, ball_pose),
    )

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-follow-path-fail",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert pre_stage_pass is False
    assert payload["failure_reason"] == "nav2_follow_path_failed"
    assert payload["approach_failure_reason"] == "entered_goal_side_before_capture"
    assert payload["entered_goal_side_before_capture"] is True
    assert payload["nav2_follow_path_result"]["dispatch_status"] == "server_unavailable"
    assert dispatch_calls
    assert dispatch_calls[0]["compose_project"] == "gate"
    assert dispatch_calls[0]["controller_id"] == "FollowPath"
    assert dispatch_calls[0]["goal_checker_id"] == "general_goal_checker"
    assert len(dispatch_calls[0]["path_poses"]) == 4
    assert any(item["event_type"] == "nav2_follow_path_reacquire_dispatch" for item in state_rows)
    complete_rows = [
        item for item in state_rows if item["event_type"] == "nav2_follow_path_reacquire_complete"
    ]
    assert complete_rows
    assert complete_rows[0]["controller_family"] == "nav2_follow_path_reacquire_v1"
    assert complete_rows[0]["nav2_follow_path_dispatch_status"] == "server_unavailable"
    assert complete_rows[0]["pre_stage_at_dispatch"]["entered_goal_side_before_capture"] is True
    assert command_log[0]["mode"] == "nav2_follow_path_reacquire_path"
    assert command_log[-1]["mode"] == "nav2_follow_path_failed"
    assert all(not bool(item["enabled"]) for item in command_log)


def test_nav2_mppi_follow_path_dispatch_uses_mppi_controller_and_dense_path(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    runner.gather_control_family = "nav2_mppi_follow_path_reacquire_v1"
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    state_rows: list[dict[str, object]] = []
    dispatch_calls: list[dict[str, object]] = []
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def fake_dispatch(**kwargs):
        dispatch_calls.append(dict(kwargs))
        return {
            "dispatch_status": "server_unavailable",
            "accepted": False,
            "success": False,
            "status_code": 0,
            "elapsed_s": 0.25,
            "error": "follow_path_action_server_unavailable",
            "feedback_count": 2,
            "feedback_samples": [{"elapsed_s": 0.1, "feedback": {"speed": 0.02}}],
            "feedback_last": {"elapsed_s": 0.2, "feedback": {"speed": 0.01}},
            "cancel_requested": False,
            "status_text": "STATUS_UNKNOWN",
            "controller_log_excerpt": {"excerpt": ["controller_server: MPPI failed to converge"]},
            "cmd_vel_counts": {"/cmd_vel_nav": 3},
            "cmd_vel_samples": [{"elapsed_s": 0.1, "topic": "/cmd_vel_nav", "linear_x": 0.02, "angular_z": 0.1}],
            "odom_count": 2,
            "odom_delta": {"distance_m": 0.0, "dyaw_deg": 0.0},
            "path_progress_samples": [{"elapsed_s": 0.2, "terminal_path_distance_m": 6.348, "terminal_yaw_error_deg": 180.0}],
            "path_progress_last": {"elapsed_s": 0.2, "terminal_path_distance_m": 6.348, "terminal_yaw_error_deg": 180.0},
        }

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda path, payload: state_rows.append(dict(payload)))
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_dispatch_nav2_follow_path_reacquire", fake_dispatch)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_control_loop_state",
        lambda **kwargs: ({"compose_project": "gate"}, robot_pose, ball_pose),
    )

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-mppi-follow-path-fail",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    dispatch_rows = [item for item in state_rows if item["event_type"] == "nav2_follow_path_reacquire_dispatch"]
    complete_rows = [item for item in state_rows if item["event_type"] == "nav2_follow_path_reacquire_complete"]
    assert pre_stage_pass is False
    assert payload["failure_reason"] == "nav2_follow_path_failed"
    assert dispatch_calls
    assert dispatch_calls[0]["controller_id"] == "MppiFollowPath"
    assert dispatch_calls[0]["timeout_s"] == gather_runner.DEFAULT_NAV2_MPPI_FOLLOW_PATH_GOAL_TIMEOUT_S
    assert len(dispatch_calls[0]["path_poses"]) > 4
    assert dispatch_calls[0]["path_poses"][0]["kind"] == "start"
    assert dispatch_rows
    assert dispatch_rows[0]["controller_family"] == "nav2_mppi_follow_path_reacquire_v1"
    assert dispatch_rows[0]["strategy_name"] == "nav2_mppi_follow_path_reacquire"
    assert dispatch_rows[0]["nav2_follow_path_controller_id"] == "MppiFollowPath"
    assert complete_rows
    diagnostics = complete_rows[0]["nav2_follow_path_diagnostics"]
    assert diagnostics["controller_id"] == "MppiFollowPath"
    assert diagnostics["feedback_count"] == 2
    assert diagnostics["feedback_samples"] == [{"elapsed_s": 0.1, "feedback": {"speed": 0.02}}]
    assert diagnostics["status_text"] == "STATUS_UNKNOWN"
    assert diagnostics["controller_log_excerpt"]["excerpt"]
    assert diagnostics["cmd_vel_counts"]["/cmd_vel_nav"] == 3
    assert diagnostics["cmd_vel_samples"][0]["angular_z"] == 0.1
    assert diagnostics["odom_count"] == 2
    assert diagnostics["odom_delta"]["distance_m"] == 0.0
    assert diagnostics["path_progress_last"]["terminal_path_distance_m"] == 6.348
    assert diagnostics["robot_motion_m"] == 0.0
    assert diagnostics["ball_motion_m"] == 0.0
    assert diagnostics["measured_handoff_ready"] is False
    assert "nav2_follow_path_diagnostics" in payload


def test_nav2_follow_path_success_returns_to_measured_handoff_dwell(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    runner.gather_control_family = "nav2_follow_path_reacquire_v1"
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    state_rows: list[dict[str, object]] = []
    command_log: list[dict[str, object]] = []
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}
    initial_robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    ready_robot_pose = {"x": 6.348, "y": 0.0, "yaw": gather_runner.math.pi}
    states = [
        ({"compose_project": "gate"}, initial_robot_pose, ball_pose),
        ({"compose_project": "gate"}, ready_robot_pose, ball_pose),
        ({"compose_project": "gate"}, ready_robot_pose, ball_pose),
        ({"compose_project": "gate"}, ready_robot_pose, ball_pose),
        ({"compose_project": "gate"}, ready_robot_pose, ball_pose),
        ({"compose_project": "gate"}, ready_robot_pose, ball_pose),
    ]

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def fake_control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {"compose_project": "gate"}, ready_robot_pose, ball_pose

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda path, payload: state_rows.append(dict(payload)))
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_dispatch_nav2_follow_path_reacquire",
        lambda **kwargs: {
            "dispatch_status": "goal_succeeded",
            "accepted": True,
            "success": True,
            "status_code": 4,
            "elapsed_s": 2.0,
            "error": "",
        },
    )
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
    monkeypatch.setattr(runner, "_control_loop_state", fake_control_loop_state)

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-follow-path-success",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    modes = [str(item["mode"]) for item in command_log]
    complete_rows = [
        item for item in state_rows if item.get("event_type") == "nav2_follow_path_reacquire_complete"
    ]

    assert pre_stage_pass is True
    assert payload["pre_stage_pose_reached"] is True
    assert payload["pre_stage_handoff_pass"] is True
    assert "nav2_follow_path_reacquire_path" in modes
    assert "nav2_follow_path_reacquire_complete" in modes
    assert modes[-1] == "pre_stage_ready"
    assert command_log[-1]["enabled"] is False
    assert complete_rows
    assert complete_rows[0]["nav2_follow_path_dispatch_status"] == "goal_succeeded"
    assert complete_rows[0]["pre_stage_at_completion"]["pre_stage_pose_reached"] is True
    assert complete_rows[0]["nav2_follow_path_measured_handoff_ready"] is True


def test_nav2_follow_path_ball_drift_fails_pre_stage_without_masking_result(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    runner.gather_control_family = "nav2_follow_path_reacquire_v1"
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    command_log: list[dict[str, object]] = []
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}
    moved_ball_pose = {"x": 5.498, "y": 0.0, "z": 0.05}
    initial_robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    ready_robot_pose = {"x": 6.348, "y": 0.0, "yaw": gather_runner.math.pi}
    states = [
        ({"compose_project": "gate"}, initial_robot_pose, ball_pose),
        ({"compose_project": "gate"}, ready_robot_pose, moved_ball_pose),
    ]

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def fake_control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {"compose_project": "gate"}, ready_robot_pose, moved_ball_pose

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_dispatch_nav2_follow_path_reacquire",
        lambda **kwargs: {
            "dispatch_status": "goal_succeeded",
            "accepted": True,
            "success": True,
            "status_code": 4,
            "elapsed_s": 2.0,
            "error": "",
        },
    )
    monkeypatch.setattr(
        runner,
        "_set_manual_drive",
        lambda enabled, linear_x=0.0, angular_z=0.0, mode="idle", rationale="": command_log.append(
            {"enabled": enabled, "linear_x": linear_x, "angular_z": angular_z, "mode": mode}
        ),
    )
    monkeypatch.setattr(runner, "_control_loop_state", fake_control_loop_state)

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-follow-path-ball-drift",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert pre_stage_pass is False
    assert payload["failure_reason"] == "nav2_follow_path_ball_motion_guard"
    assert payload["nav2_follow_path_ball_motion_m"] == 0.05
    assert command_log[-1]["mode"] == "nav2_follow_path_ball_motion_guard"
    assert command_log[-1]["enabled"] is False


def test_nav2_follow_path_post_action_non_handoff_ready_fails_pre_stage(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.1
    runner.gather_control_family = "nav2_follow_path_reacquire_v1"
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_dispatch_nav2_follow_path_reacquire",
        lambda **kwargs: {
            "dispatch_status": "goal_succeeded",
            "accepted": True,
            "success": True,
            "status_code": 4,
            "elapsed_s": 2.0,
            "error": "",
        },
    )
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_control_loop_state",
        lambda **kwargs: ({"compose_project": "gate"}, robot_pose, ball_pose),
    )

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-follow-path-non-ready",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert pre_stage_pass is False
    assert payload["failure_reason"] == "nav2_follow_path_post_action_not_handoff_ready"
    assert payload["pre_stage_handoff_pass"] is False


def test_pre_stage_target_timeout_marks_goal_side_entry_when_observed(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.poll_s = 0.5
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def fake_control_loop_state(**kwargs):
        return {}, robot_pose, ball_pose

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(gather_runner, "append_jsonl", lambda path, payload: None)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_control_loop_state", fake_control_loop_state)

    pre_stage_pass, payload = runner._pre_stage_target(
        session_id="session-pre-stage-timeout-goal-side",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    timeout_payload = read_json(mission_root / f"{target.id}_pre_stage_timeout.json")
    assert pre_stage_pass is False
    assert payload["failure_reason"] == "pre_stage_timeout"
    assert payload["approach_failure_reason"] == "entered_goal_side_before_capture"
    assert payload["entered_goal_side_before_capture"] is True
    assert timeout_payload["entered_goal_side_before_capture"] is True


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


def test_run_target_uses_latest_retry_progress_for_terminal_capture_entry_timeout(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.max_retries_per_target = 1
    runner.visit_runtime_state.update({"remaining_targets": [runner.targets[0].id], "visited_targets": []})
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    call_flags: list[tuple[bool, bool]] = []
    pre_stage_calls: list[str] = []
    pre_stage_payloads = iter(
        [
            {
                "pre_stage_pose_world": {"x": 0.10, "y": 0.00},
                "pre_stage_pose_reached": True,
                "pre_stage_time_s": 1.0,
                "pre_stage_handoff_pass": True,
            },
            {
                "pre_stage_pose_world": {"x": 0.25, "y": 0.05},
                "pre_stage_pose_reached": True,
                "pre_stage_time_s": 2.5,
                "pre_stage_handoff_pass": True,
            },
        ]
    )

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
            next(pre_stage_payloads),
        )[1:],
    )

    def fake_capture_target(*, prefer_zone_recovery: bool, enable_goal_side_stage: bool, **kwargs):
        call_flags.append((prefer_zone_recovery, enable_goal_side_stage))
        if len(call_flags) == 1:
            return False, {
                "failure_reason": "capture_entry_goal_side_loss",
                "failure_stage": "capture_entry",
                "capture_state": {},
                "zone_score": {},
                "approach_side_verdict": {"pass": False, "reason": "entered_goal_side_before_capture"},
                "staging_pose_reached": True,
                "entered_goal_side_before_capture": True,
                "first_contact_push_alignment_deg": None,
                "push_direction_yaw_deg": 15.0,
                "stage_time_s": 0.75,
                "capture_entry_reached": False,
                "capture_entry_time_s": 0.0,
                "approach_failure_reason": "entered_goal_side_before_capture",
            }
        return False, {
            "failure_reason": "capture_entry_timeout",
            "failure_stage": "capture_entry",
            "capture_state": {},
            "zone_score": {},
            "approach_side_verdict": {"pass": False, "reason": "capture_entry_timeout"},
            "staging_pose_reached": True,
            "entered_goal_side_before_capture": False,
            "first_contact_push_alignment_deg": 7.5,
            "push_direction_yaw_deg": 90.0,
            "stage_time_s": 1.5,
            "capture_entry_reached": True,
            "capture_entry_time_s": 4.0,
            "approach_failure_reason": "capture_entry_timeout",
        }

    monkeypatch.setattr(runner, "_capture_target", fake_capture_target)

    result = runner._run_target(
        session_id="session-latest-retry",
        target=target,
        route_index=1,
        gather_sequence_path=tmp_path / "gather_sequence.jsonl",
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
    )

    assert result["pass"] is False
    assert result["failure_reason"] == "capture_entry_timeout"
    assert result["failure_stage"] == "capture_entry"
    assert call_flags == [(False, True), (False, True)]
    assert pre_stage_calls == [target.id, target.id]
    assert result["pre_stage_pose_world"] == {"x": 0.25, "y": 0.05}
    assert result["pre_stage_pose_reached"] is True
    assert result["pre_stage_time_s"] == 2.5
    assert result["pre_stage_handoff_pass"] is True
    assert result["staging_pose_reached"] is True
    assert result["entered_goal_side_before_capture"] is False
    assert result["capture_entry_reached"] is True
    assert result["capture_entry_time_s"] == 4.0
    assert result["approach_side_verdict"] == {"pass": False, "reason": "capture_entry_timeout"}
    assert result["approach_failure_reason"] == "capture_entry_timeout"
    assert result["latest_approach_progress"]["reason"] == "capture_entry_timeout"
    assert result["latest_approach_progress"]["pre_stage"]["pose_world"] == {"x": 0.25, "y": 0.05}
    assert result["latest_approach_progress"]["capture_entry"]["entered_goal_side_before_capture"] is False
    assert result["latest_approach_progress"]["capture_entry"]["failure_reason"] == "capture_entry_timeout"
    assert result["fresh_attempt_approach"]["reason"] == "entered_goal_side_before_capture"
    assert result["fresh_attempt_approach"]["pre_stage"]["pose_world"] == {"x": 0.10, "y": 0.0}
    assert result["fresh_attempt_approach"]["capture_entry"]["entered_goal_side_before_capture"] is True


def test_target_failure_result_prefers_latest_approach_progress_over_stale_fresh_attempt(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    target = runner.targets[0]
    fresh_attempt_approach = {
        "pass": False,
        "reason": "entered_goal_side_before_capture",
        "pre_stage": {
            "pose_world": {},
            "pose_reached": False,
            "time_s": 0.0,
            "handoff_pass": False,
        },
        "stage": {
            "pose_reached": False,
            "time_s": 0.0,
        },
        "capture_entry": {
            "pass": False,
            "entered_goal_side_before_capture": True,
            "first_contact_push_alignment_deg": None,
            "push_direction_yaw_deg": 0.0,
            "time_s": 0.0,
            "failure_reason": "entered_goal_side_before_capture",
        },
    }
    latest_approach_progress = {
        "pass": True,
        "reason": "",
        "pre_stage": {
            "pose_world": {"x": -1.548, "y": 0.0},
            "pose_reached": True,
            "time_s": 25.813,
            "handoff_pass": True,
        },
        "stage": {
            "pose_reached": True,
            "time_s": 5.812,
        },
        "capture_entry": {
            "pass": True,
            "entered_goal_side_before_capture": False,
            "first_contact_push_alignment_deg": None,
            "push_direction_yaw_deg": 0.0,
            "time_s": 3.141,
            "failure_reason": "",
        },
    }

    payload = runner._target_failure_result(
        target=target,
        failure_reason="place_timeout",
        failure_stage="place",
        attempts=3,
        capture_loss_count=0,
        route_index=1,
        attempt_kind="place_controller_reentry",
        approach_side_verdict={"pass": False, "reason": "missing_first_contact_alignment"},
        staging_pose_reached=False,
        first_contact_push_alignment_deg=None,
        capture_entry_reached=False,
        capture_entry_time_s=0.0,
        approach_failure_reason="missing_first_contact_alignment",
        latest_approach_progress=latest_approach_progress,
        fresh_attempt_approach=fresh_attempt_approach,
    )

    assert payload["failure_reason"] == "place_timeout"
    assert payload["failure_stage"] == "place"
    assert payload["approach_side_verdict"] == {"pass": True, "reason": ""}
    assert payload["approach_failure_reason"] == ""
    assert payload["pre_stage_pose_world"] == {"x": -1.548, "y": 0.0}
    assert payload["pre_stage_pose_reached"] is True
    assert payload["pre_stage_handoff_pass"] is True
    assert payload["staging_pose_reached"] is True
    assert payload["capture_entry_reached"] is True
    assert payload["capture_entry_time_s"] == 3.141
    assert payload["first_contact_push_alignment_deg"] is None
    assert payload["fresh_attempt_approach"]["pass"] is False
    assert payload["fresh_attempt_approach"]["reason"] == "entered_goal_side_before_capture"


def test_target_failure_result_preserves_close_in_pre_stage_success_before_capture_entry_timeout(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    target = runner.targets[0]
    fresh_attempt_approach = {
        "pass": False,
        "reason": "entered_goal_side_before_capture",
        "pre_stage": {
            "pose_world": {},
            "pose_reached": False,
            "time_s": 0.0,
            "handoff_pass": False,
        },
        "stage": {
            "pose_reached": False,
            "time_s": 0.0,
        },
        "capture_entry": {
            "pass": False,
            "entered_goal_side_before_capture": True,
            "first_contact_push_alignment_deg": None,
            "push_direction_yaw_deg": 0.0,
            "time_s": 0.0,
            "failure_reason": "entered_goal_side_before_capture",
        },
    }
    latest_approach_progress = {
        "pass": False,
        "reason": "capture_entry_timeout",
        "pre_stage": {
            "pose_world": {"x": 5.191657, "y": 2.791657},
            "pose_reached": True,
            "time_s": 30.359,
            "handoff_pass": True,
        },
        "stage": {
            "pose_reached": True,
            "time_s": 5.812,
        },
        "capture_entry": {
            "pass": False,
            "entered_goal_side_before_capture": False,
            "first_contact_push_alignment_deg": None,
            "push_direction_yaw_deg": -135.0,
            "time_s": 4.281,
            "failure_reason": "capture_entry_timeout",
        },
    }

    payload = runner._target_failure_result(
        target=target,
        failure_reason="capture_entry_timeout",
        failure_stage="capture_entry",
        attempts=3,
        capture_loss_count=0,
        route_index=1,
        attempt_kind="initial_visit",
        approach_side_verdict={"pass": False, "reason": "entered_goal_side_before_capture"},
        staging_pose_reached=False,
        entered_goal_side_before_capture=False,
        first_contact_push_alignment_deg=None,
        capture_entry_reached=False,
        capture_entry_time_s=0.0,
        approach_failure_reason="entered_goal_side_before_capture",
        latest_approach_progress=latest_approach_progress,
        fresh_attempt_approach=fresh_attempt_approach,
    )

    assert payload["failure_reason"] == "capture_entry_timeout"
    assert payload["failure_stage"] == "capture_entry"
    assert payload["pre_stage_pose_world"] == {"x": 5.191657, "y": 2.791657}
    assert payload["pre_stage_pose_reached"] is True
    assert payload["pre_stage_handoff_pass"] is True
    assert payload["staging_pose_reached"] is True
    assert payload["entered_goal_side_before_capture"] is False
    assert payload["capture_entry_reached"] is False
    assert payload["capture_entry_time_s"] == 4.281
    assert payload["approach_side_verdict"] == {"pass": False, "reason": "capture_entry_timeout"}
    assert payload["approach_failure_reason"] == "capture_entry_timeout"
    assert "reached" not in payload["latest_approach_progress"]["capture_entry"]
    assert payload["latest_approach_progress"]["capture_entry"]["time_s"] == 4.281
    assert payload["fresh_attempt_approach"]["pre_stage"]["pose_reached"] is False
    assert payload["fresh_attempt_approach"]["reason"] == "entered_goal_side_before_capture"


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


def test_capture_target_close_in_stage_ready_hands_off_into_capture_entry(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.capture_timeout_s = 10.0
    runner.args.poll_s = 0.5
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    state_rows: list[dict[str, object]] = []

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(
        gather_runner,
        "append_jsonl",
        lambda _path, payload: state_rows.append(dict(payload)) if isinstance(payload, dict) else None,
    )
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_control_loop_state",
        lambda **kwargs: (
            {},
            {"x": 4.949843, "y": 2.772459, "yaw": -2.084216},
            {"x": 4.555261, "y": 2.155261, "z": 0.05},
        ),
    )

    capture_pass, payload = runner._capture_target(
        session_id="session-close-in-stage-ready",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
        enable_goal_side_stage=True,
    )

    assert capture_pass is False
    assert payload["failure_stage"] == "capture_entry"
    assert payload["staging_pose_reached"] is True
    assert payload["capture_entry_reached"] is False
    phase_entries = [str(row.get("phase", "")) for row in state_rows]
    assert phase_entries.count("stage") > 0
    assert phase_entries.count("capture_entry") > 0
    assert phase_entries.index("stage") < phase_entries.index("capture_entry")


def test_capture_target_latched_stage_ready_hands_off_after_one_off_band_sample(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.capture_timeout_s = 10.0
    runner.args.poll_s = 0.5
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    state_rows: list[dict[str, object]] = []
    approach_calls = {"count": 0}

    class _FakeCommand:
        def __init__(self, mode: str):
            self.mode = mode
            self.linear_x = 0.0
            self.angular_z = 0.0
            self.rationale = mode

        def to_dict(self) -> dict[str, object]:
            return {
                "mode": self.mode,
                "linear_x": self.linear_x,
                "angular_z": self.angular_z,
                "rationale": self.rationale,
            }

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def fake_approach_snapshot(*args, **kwargs):
        approach_calls["count"] += 1
        return {
            "robot_on_goal_side": False,
            "staging_pose_reached": approach_calls["count"] == 3,
            "push_direction_yaw_deg": 0.0,
        }

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(
        gather_runner,
        "append_jsonl",
        lambda _path, payload: state_rows.append(dict(payload)) if isinstance(payload, dict) else None,
    )
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_control_loop_state",
        lambda **kwargs: (
            {},
            {"x": 0.0, "y": 0.0, "yaw": 0.0},
            {"x": 1.0, "y": 0.0, "z": 0.05},
        ),
    )
    monkeypatch.setattr(gather_runner, "goal_side_approach_snapshot", fake_approach_snapshot)
    monkeypatch.setattr(
        gather_runner,
        "compute_stage_command",
        lambda *args, **kwargs: _FakeCommand("stage_ready" if approach_calls["count"] == 3 else "stage_align"),
    )
    monkeypatch.setattr(
        gather_runner,
        "capture_entry_snapshot",
        lambda *args, **kwargs: {
            "ball_x_m": 0.54,
            "ball_y_m": 0.09,
            "bearing_rad": 0.16,
            "robot_on_goal_side": False,
            "capture_entry_reached": False,
        },
    )
    monkeypatch.setattr(gather_runner, "compute_capture_entry_command", lambda *args, **kwargs: _FakeCommand("capture_entry"))

    capture_pass, payload = runner._capture_target(
        session_id="session-latched-stage-ready",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
        enable_goal_side_stage=True,
    )

    assert capture_pass is False
    assert payload["failure_stage"] == "capture_entry"
    assert payload["staging_pose_reached"] is True
    assert payload["capture_entry_reached"] is False
    phase_entries = [str(row.get("phase", "")) for row in state_rows]
    assert phase_entries.count("stage") > 0
    assert phase_entries.count("capture_entry") > 0
    assert phase_entries.index("stage") < phase_entries.index("capture_entry")
    stage_rows = [row for row in state_rows if row.get("phase") == "stage"]
    first_ready_index = next(
        index
        for index, row in enumerate(stage_rows)
        if isinstance(row.get("selected_command"), dict)
        and row["selected_command"].get("mode") == "stage_ready"
    )
    assert all(
        not (
            isinstance(row.get("selected_command"), dict)
            and row["selected_command"].get("mode") in {"stage_align", "stage_traverse"}
        )
        for row in stage_rows[first_ready_index + 1 :]
    )
    assert not (mission_root / f"{target.id}_stage_timeout.json").exists()


def test_capture_target_capture_entry_timeout_returns_capture_entry_failure(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.capture_timeout_s = 10.0
    runner.args.poll_s = 0.5
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    state_rows: list[dict[str, object]] = []

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(
        gather_runner,
        "append_jsonl",
        lambda _path, payload: state_rows.append(dict(payload)) if isinstance(payload, dict) else None,
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
    phase_entries = [str(row.get("phase", "")) for row in state_rows]
    assert phase_entries.count("capture_entry") > 0
    assert "capture" not in phase_entries


def test_capture_target_late_ready_sample_skips_same_loop_capture_entry_timeout(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.capture_timeout_s = 6.0
    runner.args.poll_s = 0.5
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    state_rows: list[dict[str, object]] = []
    capture_entry_calls = {"count": 0}

    class _FakeCommand:
        def __init__(self, mode: str):
            self.mode = mode
            self.linear_x = 0.0
            self.angular_z = 0.0
            self.rationale = mode

        def to_dict(self) -> dict[str, object]:
            return {
                "mode": self.mode,
                "linear_x": self.linear_x,
                "angular_z": self.angular_z,
                "rationale": self.rationale,
            }

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    def fake_capture_entry_snapshot(*args, **kwargs):
        capture_entry_calls["count"] += 1
        ready = capture_entry_calls["count"] == 8
        if ready:
            ball_x_m = 0.599572
            ball_y_m = 0.001913
            bearing_rad = 0.003191
        elif capture_entry_calls["count"] > 8:
            ball_x_m = 0.602147
            ball_y_m = -0.04357
            bearing_rad = -0.072232
        else:
            ball_x_m = 0.649495
            ball_y_m = -0.018137
            bearing_rad = -0.027918
        return {
            "ball_x_m": ball_x_m,
            "ball_y_m": ball_y_m,
            "bearing_rad": bearing_rad,
            "robot_on_goal_side": False,
            "capture_entry_reached": ready,
        }

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(
        gather_runner,
        "append_jsonl",
        lambda _path, payload: state_rows.append(dict(payload)) if isinstance(payload, dict) else None,
    )
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_control_loop_state",
        lambda **kwargs: (
            {},
            {"x": 0.0, "y": 0.0, "yaw": 0.0},
            {"x": 1.0, "y": 0.0, "z": 0.05},
        ),
    )
    monkeypatch.setattr(
        gather_runner,
        "goal_side_approach_snapshot",
        lambda *args, **kwargs: {
            "robot_on_goal_side": False,
            "staging_pose_reached": True,
            "push_direction_yaw_deg": 0.0,
        },
    )
    monkeypatch.setattr(gather_runner, "compute_stage_command", lambda *args, **kwargs: _FakeCommand("stage_ready"))
    monkeypatch.setattr(gather_runner, "capture_entry_snapshot", fake_capture_entry_snapshot)
    monkeypatch.setattr(
        gather_runner,
        "compute_capture_entry_command",
        lambda *args, **kwargs: _FakeCommand("capture_entry_centered_close"),
    )

    capture_pass, payload = runner._capture_target(
        session_id="session-capture-entry-late-ready",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
        enable_goal_side_stage=True,
    )

    timeout_path = mission_root / f"{target.id}_capture_entry_timeout.json"

    assert capture_pass is False
    assert payload["failure_stage"] == "capture"
    assert payload["capture_entry_reached"] is True
    assert payload["capture_entry_time_s"] >= 4.0
    assert capture_entry_calls["count"] >= 9
    phase_entries = [str(row.get("phase", "")) for row in state_rows]
    assert phase_entries.count("capture_entry") > 0
    assert "capture" in phase_entries
    assert phase_entries.index("capture_entry") < phase_entries.index("capture")
    assert not timeout_path.exists()


def test_capture_target_centered_extended_corridor_hands_off_before_capture_timeout(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.capture_timeout_s = 1.2
    runner.args.poll_s = 0.1
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    state_rows: list[dict[str, object]] = []

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(
        gather_runner,
        "append_jsonl",
        lambda _path, payload: state_rows.append(dict(payload)) if isinstance(payload, dict) else None,
    )
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_control_loop_state",
        lambda **kwargs: (
            {},
            {"x": 0.46, "y": -0.01, "yaw": 0.0},
            {"x": 1.0, "y": 0.0, "z": 0.05},
        ),
    )

    capture_pass, payload = runner._capture_target(
        session_id="session-capture-entry-centered-pass",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
        enable_goal_side_stage=True,
    )

    assert capture_pass is False
    assert payload["failure_stage"] == "capture"
    assert payload["capture_entry_reached"] is True
    assert payload["capture_entry_time_s"] >= 0.3
    phase_entries = [str(row.get("phase", "")) for row in state_rows]
    assert "capture_entry" in phase_entries
    assert "capture" in phase_entries
    assert phase_entries.index("capture_entry") < phase_entries.index("capture")
    capture_rows = [row for row in state_rows if row.get("phase") == "capture"]
    assert capture_rows
    capture_row = capture_rows[-1]
    assert capture_row["selected_command"]["mode"] == "capture"
    assert capture_row["capture_entry"]["capture_entry_reached"] is True
    assert capture_row["capture_diagnostics"]["selected_command_mode"] == "capture"
    assert capture_row["capture_diagnostics"]["command_source"] == "capture_command"
    assert capture_row["capture_diagnostics"]["command_limited"] is False
    assert capture_row["capture_diagnostics"]["raw_selected_command"]["mode"] == "capture"
    assert capture_row["capture_diagnostics"]["captured_now"] is False
    assert capture_row["capture_diagnostics"]["terminal_cause"] == ""
    assert capture_row["capture_diagnostics"]["robot_delta_from_capture_entry_handoff_m"] is not None
    assert payload["capture_diagnostics"]["terminal_cause"] == "capture_timeout"
    assert payload["capture_diagnostics"]["selected_command_mode"] == "capture"


def test_capture_target_off_axis_extended_corridor_still_times_out_in_capture_entry(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.capture_timeout_s = 10.0
    runner.args.poll_s = 0.5
    mission_root = tmp_path / "artifacts" / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    target = runner.targets[0]
    clock = {"now": 0.0}
    phase_entries: list[str] = []
    state_rows: list[dict[str, object]] = []

    def fake_monotonic():
        return clock["now"]

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(gather_runner.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", fake_sleep)
    monkeypatch.setattr(
        gather_runner,
        "append_jsonl",
        lambda _path, payload: (
            state_rows.append(payload) or phase_entries.append(str(payload.get("phase", "")))
            if isinstance(payload, dict)
            else None
        ),
    )
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_control_loop_state",
        lambda **kwargs: (
            {},
            {"x": 0.46, "y": -0.09, "yaw": 0.0},
            {"x": 1.0, "y": 0.0, "z": 0.05},
        ),
    )

    capture_pass, payload = runner._capture_target(
        session_id="session-capture-entry-off-axis-timeout",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
        mission_root=mission_root,
        enable_goal_side_stage=True,
    )

    assert capture_pass is False
    assert payload["failure_stage"] == "capture_entry"
    assert payload["capture_entry_reached"] is False
    assert payload["capture_entry_time_s"] >= 4.0
    assert phase_entries.count("capture_entry") > 0
    assert "capture" not in phase_entries
    capture_entry_rows = [row for row in state_rows if row.get("phase") == "capture_entry"]
    assert capture_entry_rows
    diagnostics = capture_entry_rows[-1]["capture_entry_diagnostics"]
    assert diagnostics["timeout_cause"] == "ready_band_never_reached"
    assert diagnostics["selected_command_mode"] == "capture_entry"
    assert diagnostics["manager_directive"] == "close_capture_gap"
    assert abs(float(diagnostics["ball_x_m"]) - 0.54) <= 0.02
    assert abs(float(diagnostics["ball_y_m"]) - 0.09) <= 0.02
    assert abs(float(diagnostics["robot_delta_from_handoff_m"]) - 0.0) <= 1.0e-6
    assert abs(float(diagnostics["ball_delta_from_handoff_m"]) - 0.0) <= 1.0e-6
    assert payload["capture_entry_diagnostics"]["timeout_cause"] == "ready_band_never_reached"
    assert abs(float(payload["capture_entry_diagnostics"]["robot_delta_from_handoff_m"]) - 0.0) <= 1.0e-6
    assert payload["capture_entry_snapshot"]["capture_entry_reached"] is False


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
            {"x": 0.46, "y": -0.01, "yaw": 0.0},
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


def test_place_target_stationary_far_from_zone_local_recovery_nudges_after_delay(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.args.place_timeout_s = 1.6
    runner.args.poll_s = 0.25
    mission_root = tmp_path / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    runner._init_runtime_state(session_id="session-1", mission_root=mission_root)

    clock = {"now": 0.0}
    robot_pose = {"x": -1.161239, "y": 0.079721, "yaw": -0.154098}
    ball_pose = {"x": -0.648, "y": 0.0, "z": 0.05}

    def _fake_monotonic():
        return clock["now"]

    def _fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(gather_runner.time, "monotonic", _fake_monotonic)
    monkeypatch.setattr(gather_runner.time, "sleep", _fake_sleep)
    monkeypatch.setattr(runner, "_control_loop_state", lambda **kwargs: ({}, robot_pose, ball_pose))
    monkeypatch.setattr(runner, "_update_prior_from_ball_pose", lambda target_id, ball_pose: None)

    command_log: list[dict[str, object]] = []
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

    hold_indices = [index for index, item in enumerate(command_log) if item["mode"] == "capture_recovery_hold"]
    nudge_indices = [
        index
        for index, item in enumerate(command_log)
        if item["mode"] == "capture_recovery" and float(item["linear_x"]) > 0.0
    ]

    assert passed is False
    assert payload["failure_reason"] == "place_timeout"
    assert payload["failure_stage"] == "place"
    assert payload["local_recovery_attempted"] is True
    assert hold_indices
    assert nudge_indices
    assert min(nudge_indices) > min(hold_indices)
    assert any(
        "bounded forward recapture nudge" in str(item["rationale"]).lower()
        for item in command_log
        if item["mode"] == "capture_recovery"
    )
    assert command_log[-1]["mode"] == "place_timeout"


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


def test_object_centric_place_recovery_keeps_far_recapture_push(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 4.69418, "y": 2.378654, "yaw": -1.991557}, {"x": 4.556202, "y": 2.117243, "z": 0.05}),
        ({}, {"x": 4.688528, "y": 2.367859, "yaw": -2.252642}, {"x": 4.558144, "y": 2.038701, "z": 0.05}),
        ({}, {"x": 4.688528, "y": 2.367859, "yaw": -1.882207}, {"x": 4.561107, "y": 1.918943, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 4.688528, "y": 2.367859, "yaw": -1.882207}, {"x": 4.561107, "y": 1.918943, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    far_recapture_commands = [
        item
        for item in command_log
        if item["mode"] in {"object_place_recapture_drive", "object_place_far_line_recenter"}
    ]
    assert far_recapture_commands
    assert max(float(item["linear_x"]) for item in far_recapture_commands) > 0.0
    assert all(item["mode"] != "capture_recovery_hold" for item in command_log)


def test_object_centric_place_recovery_recenters_far_recapture_lateral_drift(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 5.698247, "y": -0.086831, "yaw": 2.783439}, {"x": 5.448, "y": 0.0, "z": 0.05}),
        ({}, {"x": 5.5499, "y": -0.02795, "yaw": 3.049913}, {"x": 5.20407, "y": 0.165779, "z": 0.05}),
        ({}, {"x": 5.5499, "y": -0.02795, "yaw": 3.049913}, {"x": 5.20407, "y": 0.165779, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 5.5499, "y": -0.02795, "yaw": 3.049913}, {"x": 5.20407, "y": 0.165779, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    recenter_commands = [item for item in command_log if item["mode"] == "object_place_lateral_recenter"]
    assert recenter_commands
    assert all(float(item["linear_x"]) == 0.0 for item in recenter_commands)
    assert max(float(item["angular_z"]) for item in recenter_commands) > 0.0


def test_object_centric_place_recovery_preserves_keepup_near_recapture_edge(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 5.404268, "y": -0.105692, "yaw": -2.674277}, {"x": 4.851202, "y": -0.548933, "z": 0.05}),
        ({}, {"x": 5.394441, "y": -0.110745, "yaw": -2.650547}, {"x": 4.812162, "y": -0.584774, "z": 0.05}),
        ({}, {"x": 5.376267, "y": -0.121163, "yaw": -2.611708}, {"x": 4.735505, "y": -0.655147, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 5.376267, "y": -0.121163, "yaw": -2.611708}, {"x": 4.735505, "y": -0.655147, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    keepup_commands = [
        item
        for item in command_log
        if item["mode"] == "object_place_recapture_drive" and float(item["linear_x"]) >= 0.06
    ]
    assert keepup_commands
    assert max(float(item["linear_x"]) for item in keepup_commands) >= 0.06


def test_object_centric_place_recovery_preserves_near_zone_recapture_drive(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 4.023405, "y": -0.251181, "yaw": -3.066374}, {"x": 3.183476, "y": -0.376122, "z": 0.05}),
        ({}, {"x": 4.023405, "y": -0.251181, "yaw": -3.066374}, {"x": 3.183476, "y": -0.376122, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 4.023405, "y": -0.251181, "yaw": -3.066374}, {"x": 3.183476, "y": -0.376122, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    near_zone_commands = [item for item in command_log if item["mode"] == "object_place_near_zone_recapture_drive"]
    assert near_zone_commands
    assert max(float(item["linear_x"]) for item in near_zone_commands) <= 0.04
    assert max(abs(float(item["angular_z"])) for item in near_zone_commands) >= 0.12


def test_object_centric_place_recovery_preserves_latest_zero_finish_keepup(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 4.689164, "y": -0.146194, "yaw": -2.962577}, {"x": 4.291016, "y": -0.262700, "z": 0.05}),
        ({}, {"x": 4.054540, "y": -0.248286, "yaw": -3.037836}, {"x": 3.182366, "y": -0.482841, "z": 0.05}),
        ({}, {"x": 4.054540, "y": -0.248286, "yaw": -3.037276}, {"x": 3.147311, "y": -0.489802, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 4.054540, "y": -0.248286, "yaw": -3.037276}, {"x": 3.147311, "y": -0.489802, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    near_zone_commands = [item for item in command_log if item["mode"] == "object_place_near_zone_recapture_drive"]
    assert near_zone_commands
    assert max(float(item["linear_x"]) for item in near_zone_commands) <= 0.018
    assert all(item["mode"] != "release_roll_away" for item in command_log)


def test_object_centric_place_recovery_preserves_near_zone_lateral_recenter(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 3.897466, "y": -0.316284, "yaw": -3.087496}, {"x": 3.280489, "y": -0.491072, "z": 0.05}),
        ({}, {"x": 3.884518, "y": -0.315963, "yaw": 3.083363}, {"x": 3.211271, "y": -0.502858, "z": 0.05}),
        ({}, {"x": 3.884518, "y": -0.315963, "yaw": 3.083363}, {"x": 3.211271, "y": -0.502858, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 3.884518, "y": -0.315963, "yaw": 3.083363}, {"x": 3.211271, "y": -0.502858, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    recenter_commands = [item for item in command_log if item["mode"] == "object_place_lateral_recenter"]
    assert recenter_commands
    assert all(float(item["linear_x"]) == 0.0 for item in recenter_commands)
    assert all(item["mode"] not in {"capture_recovery", "capture_recovery_hold"} for item in command_log)


def test_object_centric_place_holds_unsecured_ball_inside_retrieval_corral(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
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

    robot_pose = {"x": 3.540, "y": -0.160, "yaw": 2.937}
    centered_ball = {"x": 2.349, "y": 0.049, "z": 0.05}

    def _control_loop_state(**kwargs):
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
    modes = [str(item["mode"]) for item in command_log]
    assert "object_place_inside_retrieval_hold" in modes
    assert "settle_no_chase" in modes
    first_settle_index = modes.index("settle_no_chase")
    assert all(
        mode not in {"retrieval_shepherd", "capture_recovery", "capture_recovery_hold"}
        for mode in modes[:first_settle_index]
    )


def test_object_centric_place_starts_no_chase_for_moving_center_zone_ball(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
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

    robot_pose = {"x": 3.546642, "y": -0.140912, "yaw": 2.630410}
    moving_center_ball = {"x": 2.527145, "y": -0.130904, "z": 0.05}
    states = [
        ({}, robot_pose, {"x": 2.561844, "y": -0.131995, "z": 0.05}),
        ({}, robot_pose, moving_center_ball),
        ({}, robot_pose, moving_center_ball),
        ({}, robot_pose, moving_center_ball),
        ({}, robot_pose, moving_center_ball),
        ({}, robot_pose, moving_center_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, robot_pose, moving_center_ball

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
    assert payload["settle_no_chase_activated"] is True
    assert payload["release_gate_blocked_reason"] == "none"
    assert any(item["mode"] == "settle_no_chase" for item in command_log)


def test_object_centric_place_starts_no_chase_for_low_lateral_center_rollthrough(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
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

    robot_pose = {"x": 3.921, "y": -0.083, "yaw": 3.048}
    settled_center_ball = {"x": 2.400, "y": -0.030, "z": 0.05}
    states = [
        ({}, robot_pose, {"x": 2.597, "y": -0.037, "z": 0.05}),
        ({}, robot_pose, {"x": 2.465, "y": -0.031, "z": 0.05}),
        ({}, robot_pose, {"x": 2.432, "y": -0.030, "z": 0.05}),
        ({}, robot_pose, settled_center_ball),
        ({}, robot_pose, settled_center_ball),
        ({}, robot_pose, settled_center_ball),
        ({}, robot_pose, settled_center_ball),
        ({}, robot_pose, settled_center_ball),
        ({}, robot_pose, settled_center_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, robot_pose, settled_center_ball

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
    assert payload["settle_no_chase_activated"] is True
    assert any(item["mode"] == "settle_no_chase" for item in command_log)


def test_object_centric_place_blocks_no_chase_for_single_stale_center_rollthrough_sample(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    robot_pose = {"x": 4.748657, "y": -0.002424, "yaw": 3.107756}
    stale_center_ball = {"x": 2.564882, "y": -0.039820, "z": 0.05}
    states = [
        ({}, robot_pose, {"x": 2.617130, "y": -0.038168, "z": 0.05}),
        ({}, robot_pose, stale_center_ball),
        ({}, robot_pose, stale_center_ball),
        ({}, robot_pose, {"x": 2.466712, "y": -0.042923, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, robot_pose, {"x": 2.416019, "y": -0.044526, "z": 0.05}

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
    assert payload["settle_no_chase_activated"] is False
    assert all(item["mode"] != "settle_no_chase" for item in command_log)


def test_object_centric_place_preserves_positive_world_edge_hold_during_local_recovery(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    recapture_entry_robot = {"x": 5.243663, "y": -0.001597, "yaw": 3.100962}
    positive_edge_robot = {"x": 5.210430, "y": -0.003143, "yaw": 2.109981}
    terminal_edge_robot = {"x": 5.209441, "y": -0.000869, "yaw": 1.963221}
    recapture_entry_ball = {"x": 4.841624, "y": 0.068254, "z": 0.05}
    positive_edge_ball = {"x": 3.796629, "y": 0.537616, "z": 0.05}
    terminal_edge_ball = {"x": 3.758530, "y": 0.554729, "z": 0.05}
    states = [
        ({}, recapture_entry_robot, recapture_entry_ball),
        ({}, positive_edge_robot, positive_edge_ball),
        ({}, terminal_edge_robot, terminal_edge_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, terminal_edge_robot, terminal_edge_ball

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
    assert any(
        item["mode"] == "object_place_lateral_recenter" and float(item["angular_z"]) <= -0.75
        for item in command_log
    )
    assert all(item["mode"] != "release_roll_away" for item in command_log)


def test_object_centric_place_preserves_far_reorient_during_high_lateral_local_recovery(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    recapture_entry_robot = {"x": 5.491187, "y": -0.040509, "yaw": 2.972132}
    high_lateral_robot = {"x": 5.362558, "y": -0.033062, "yaw": 1.437501}
    reorient_robot = {"x": 5.362558, "y": -0.033062, "yaw": 1.231217}
    recapture_entry_ball = {"x": 5.076434, "y": 0.014904, "z": 0.05}
    high_lateral_ball = {"x": 4.122304, "y": 0.388281, "z": 0.05}
    reorient_ball = {"x": 4.076648, "y": 0.406147, "z": 0.05}
    states = [
        ({}, recapture_entry_robot, recapture_entry_ball),
        ({}, high_lateral_robot, high_lateral_ball),
        ({}, reorient_robot, reorient_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, reorient_robot, reorient_ball

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
    assert any(
        item["mode"] == "capture_recovery_turn" and float(item["angular_z"]) >= 0.85
        for item in command_log
    )
    assert all(item["mode"] != "release_roll_away" for item in command_log)


def test_object_centric_place_preserves_latest_zero_far_negative_x_reorient(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    recapture_entry_robot = {"x": 5.425296, "y": -0.032842, "yaw": 3.026466}
    high_lateral_robot = {"x": 5.393983, "y": -0.019308, "yaw": 1.353937}
    reorient_robot = {"x": 5.393983, "y": -0.019308, "yaw": 1.152615}
    recapture_entry_ball = {"x": 4.646811, "y": 0.216956, "z": 0.05}
    high_lateral_ball = {"x": 4.208882, "y": 0.389998, "z": 0.05}
    reorient_ball = {"x": 4.165617, "y": 0.407093, "z": 0.05}
    states = [
        ({}, recapture_entry_robot, recapture_entry_ball),
        ({}, high_lateral_robot, high_lateral_ball),
        ({}, reorient_robot, reorient_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, reorient_robot, reorient_ball

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
    assert payload["local_recovery_attempted"] is True
    assert any(
        item["mode"] == "capture_recovery_turn" and float(item["angular_z"]) >= 0.85
        for item in command_log
    )
    assert all(item["mode"] != "release_roll_away" for item in command_log)


def test_object_centric_place_preserves_latest_zero_deeper_far_negative_x_reorient(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    recapture_entry_robot = {"x": 5.193506, "y": -0.003195, "yaw": 3.048016}
    reorient_entry_robot = {"x": 5.193506, "y": -0.003195, "yaw": 1.221753}
    terminal_reorient_robot = {"x": 5.193506, "y": -0.003195, "yaw": 1.024585}
    recapture_entry_ball = {"x": 4.637266, "y": 0.153496, "z": 0.05}
    reorient_entry_ball = {"x": 4.044365, "y": 0.396935, "z": 0.05}
    terminal_reorient_ball = {"x": 4.005398, "y": 0.412934, "z": 0.05}
    states = [
        ({}, recapture_entry_robot, recapture_entry_ball),
        ({}, reorient_entry_robot, reorient_entry_ball),
        ({}, terminal_reorient_robot, terminal_reorient_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, terminal_reorient_robot, terminal_reorient_ball

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
    assert payload["local_recovery_attempted"] is True
    assert any(
        item["mode"] == "capture_recovery_turn" and float(item["angular_z"]) >= 0.85
        for item in command_log
    )
    assert all(item["mode"] != "release_roll_away" for item in command_log)


def test_object_centric_place_preserves_latest_zero_deepest_far_negative_x_reorient(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    recapture_entry_robot = {"x": 5.193506, "y": -0.003195, "yaw": 3.048016}
    reorient_entry_robot = {"x": 5.139726, "y": 0.004154, "yaw": 1.068533}
    terminal_reorient_robot = {"x": 5.139726, "y": 0.004154, "yaw": 0.902574}
    recapture_entry_ball = {"x": 4.637266, "y": 0.153496, "z": 0.05}
    reorient_entry_ball = {"x": 4.011377, "y": 0.394718, "z": 0.05}
    terminal_reorient_ball = {"x": 4.011377, "y": 0.394718, "z": 0.05}
    states = [
        ({}, recapture_entry_robot, recapture_entry_ball),
        ({}, reorient_entry_robot, reorient_entry_ball),
        ({}, terminal_reorient_robot, terminal_reorient_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, terminal_reorient_robot, terminal_reorient_ball

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
    assert payload["local_recovery_attempted"] is True
    assert any(
        item["mode"] == "capture_recovery_turn" and float(item["angular_z"]) >= 0.85
        for item in command_log
    )
    assert all(item["mode"] != "release_roll_away" for item in command_log)


def test_object_centric_place_preserves_same_side_low_x_edge_hold_during_local_recovery(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    recapture_entry_robot = {"x": 5.101721, "y": 0.009222, "yaw": -3.017964}
    same_side_edge_entry_robot = {"x": 4.979227, "y": 0.017618, "yaw": 2.428310}
    terminal_edge_robot = {"x": 4.979227, "y": 0.017618, "yaw": 1.940913}
    recapture_entry_ball = {"x": 4.670404, "y": 0.070749, "z": 0.05}
    same_side_edge_entry_ball = {"x": 3.355849, "y": 0.425937, "z": 0.05}
    terminal_edge_ball = {"x": 3.313291, "y": 0.437436, "z": 0.05}
    states = [
        ({}, recapture_entry_robot, recapture_entry_ball),
        ({}, same_side_edge_entry_robot, same_side_edge_entry_ball),
        ({}, terminal_edge_robot, terminal_edge_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, terminal_edge_robot, terminal_edge_ball

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
    assert payload["local_recovery_attempted"] is True
    assert any(
        item["mode"] == "object_place_near_zone_wide_reel"
        and float(item["linear_x"]) == 0.0
        and float(item["angular_z"]) <= -0.45
        for item in command_log
    )
    assert all(item["mode"] != "release_roll_away" for item in command_log)


def test_object_centric_place_preserves_high_x_final_edge_hold_during_local_recovery(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    recapture_entry_robot = {"x": 5.511623, "y": -0.030283, "yaw": 2.818823}
    high_x_edge_entry_robot = {"x": 5.087228, "y": 0.017337, "yaw": 2.688127}
    terminal_edge_robot = {"x": 5.087228, "y": 0.017337, "yaw": 3.011586}
    recapture_entry_ball = {"x": 5.085754, "y": -0.015761, "z": 0.05}
    high_x_edge_entry_ball = {"x": 3.190756, "y": 0.383169, "z": 0.05}
    terminal_edge_ball = {"x": 3.137094, "y": 0.394466, "z": 0.05}
    states = [
        ({}, recapture_entry_robot, recapture_entry_ball),
        ({}, high_x_edge_entry_robot, high_x_edge_entry_ball),
        ({}, terminal_edge_robot, terminal_edge_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, terminal_edge_robot, terminal_edge_ball

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
    assert payload["local_recovery_attempted"] is True
    assert any(
        item["mode"] == "object_place_near_zone_wide_reel"
        and float(item["linear_x"]) == 0.0
        and float(item["angular_z"]) <= -0.35
        for item in command_log
    )
    assert all(item["mode"] != "release_roll_away" for item in command_log)


def test_object_centric_place_preserves_stale_high_x_final_edge_hold_during_local_recovery(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    recapture_entry_robot = {"x": 5.511623, "y": -0.030283, "yaw": 2.818823}
    high_x_edge_entry_robot = {"x": 5.022008, "y": 0.016536, "yaw": 2.387891}
    terminal_edge_robot = {"x": 5.022008, "y": 0.016536, "yaw": 2.661431}
    recapture_entry_ball = {"x": 5.085754, "y": -0.015761, "z": 0.05}
    high_x_edge_entry_ball = {"x": 3.040647, "y": 0.554660, "z": 0.05}
    terminal_edge_ball = {"x": 3.040647, "y": 0.554660, "z": 0.05}
    states = [
        ({}, recapture_entry_robot, recapture_entry_ball),
        ({}, high_x_edge_entry_robot, high_x_edge_entry_ball),
        ({}, terminal_edge_robot, terminal_edge_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, terminal_edge_robot, terminal_edge_ball

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
    assert payload["local_recovery_attempted"] is True
    assert any(
        item["mode"] == "object_place_near_zone_wide_reel"
        and float(item["linear_x"]) == 0.0
        and float(item["angular_z"]) <= -0.45
        for item in command_log
    )
    assert all(item["mode"] != "release_roll_away" for item in command_log)


def test_object_centric_place_preserves_mid_x_opposed_edge_hold_during_local_recovery(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    recapture_entry_robot = {"x": 5.511623, "y": -0.030283, "yaw": 2.818823}
    opposed_edge_entry_robot = {"x": 4.913819, "y": 0.019717, "yaw": 2.582049}
    terminal_edge_robot = {"x": 4.912046, "y": 0.020860, "yaw": 2.574674}
    recapture_entry_ball = {"x": 5.085754, "y": -0.015761, "z": 0.05}
    opposed_edge_entry_ball = {"x": 3.453349, "y": -0.344227, "z": 0.05}
    terminal_edge_ball = {"x": 3.406073, "y": -0.355983, "z": 0.05}
    states = [
        ({}, recapture_entry_robot, recapture_entry_ball),
        ({}, opposed_edge_entry_robot, opposed_edge_entry_ball),
        ({}, terminal_edge_robot, terminal_edge_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, terminal_edge_robot, terminal_edge_ball

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
    assert payload["local_recovery_attempted"] is True
    assert any(
        item["mode"] == "object_place_near_zone_wide_reel"
        and float(item["linear_x"]) == 0.0
        and float(item["angular_z"]) >= 0.45
        for item in command_log
    )
    assert all(item["mode"] != "release_roll_away" for item in command_log)


def test_object_centric_place_preserves_high_x_opposed_edge_hold_during_local_recovery(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    recapture_entry_robot = {"x": 5.511623, "y": -0.030283, "yaw": 2.818823}
    opposed_edge_entry_robot = {"x": 5.033396, "y": 0.014405, "yaw": -2.935897}
    terminal_edge_robot = {"x": 5.027208, "y": 0.011826, "yaw": -2.610997}
    recapture_entry_ball = {"x": 5.085754, "y": -0.015761, "z": 0.05}
    opposed_edge_entry_ball = {"x": 3.430477, "y": 0.482467, "z": 0.05}
    terminal_edge_ball = {"x": 3.385274, "y": 0.496924, "z": 0.05}
    states = [
        ({}, recapture_entry_robot, recapture_entry_ball),
        ({}, opposed_edge_entry_robot, opposed_edge_entry_ball),
        ({}, terminal_edge_robot, terminal_edge_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, terminal_edge_robot, terminal_edge_ball

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
    assert payload["local_recovery_attempted"] is True
    assert any(
        item["mode"] == "object_place_near_zone_wide_reel"
        and float(item["linear_x"]) == 0.0
        and float(item["angular_z"]) <= -0.45
        for item in command_log
    )
    assert all(item["mode"] != "release_roll_away" for item in command_log)


def test_object_centric_place_starts_no_chase_for_retrieval_shoulder_rollthrough(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
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

    live_robot = {"x": 3.798, "y": 0.050, "yaw": -2.917}
    shoulder_ball = {"x": 2.550, "y": 0.258, "z": 0.05}
    states = [
        ({}, live_robot, {"x": 2.664, "y": 0.242, "z": 0.05}),
        ({}, live_robot, {"x": 2.625, "y": 0.248, "z": 0.05}),
        ({}, live_robot, shoulder_ball),
        ({}, live_robot, shoulder_ball),
        ({}, live_robot, shoulder_ball),
        ({}, live_robot, shoulder_ball),
        ({}, live_robot, shoulder_ball),
        ({}, live_robot, shoulder_ball),
        ({}, live_robot, shoulder_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, live_robot, shoulder_ball

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
    assert payload["settle_no_chase_activated"] is True
    assert payload["release_gate_blocked_reason"] == "none"
    assert any(item["mode"] == "settle_no_chase" for item in command_log)


def test_object_centric_place_starts_no_chase_for_high_local_lateral_retrieval_shoulder(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
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

    live_robot = {"x": 4.161, "y": -0.119, "yaw": 2.364}
    shoulder_ball = {"x": 2.597, "y": -0.282, "z": 0.05}
    states = [
        ({}, live_robot, {"x": 2.635, "y": -0.278, "z": 0.05}),
        ({}, live_robot, shoulder_ball),
        ({}, live_robot, shoulder_ball),
        ({}, live_robot, shoulder_ball),
        ({}, live_robot, shoulder_ball),
        ({}, live_robot, shoulder_ball),
        ({}, live_robot, shoulder_ball),
        ({}, live_robot, shoulder_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, live_robot, shoulder_ball

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
    assert payload["settle_no_chase_activated"] is True
    assert payload["release_gate_blocked_reason"] == "none"
    assert any(item["mode"] == "settle_no_chase" for item in command_log)


def test_object_centric_place_starts_no_chase_for_inside_retrieval_rollthrough(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
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

    live_robot = {"x": 3.786819, "y": -0.173937, "yaw": 2.552909}
    rollthrough_ball = {"x": 2.810206, "y": -0.311309, "z": 0.05}
    states = [
        ({}, live_robot, {"x": 2.893745, "y": -0.305391, "z": 0.05}),
        ({}, live_robot, {"x": 2.865580, "y": -0.307391, "z": 0.05}),
        ({}, live_robot, {"x": 2.837335, "y": -0.309393, "z": 0.05}),
        ({}, live_robot, rollthrough_ball),
        ({}, live_robot, rollthrough_ball),
        ({}, live_robot, rollthrough_ball),
        ({}, live_robot, rollthrough_ball),
        ({}, live_robot, rollthrough_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, live_robot, rollthrough_ball

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
    assert payload["settle_no_chase_activated"] is True
    assert payload["release_gate_blocked_reason"] == "none"
    assert any(item["mode"] == "settle_no_chase" for item in command_log)


def test_object_centric_place_starts_no_chase_for_inside_retrieval_high_lateral_roll(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
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

    live_robot = {"x": 4.801, "y": -0.129, "yaw": 2.790}
    high_lateral_ball = {"x": 3.024, "y": -0.295, "z": 0.05}
    states = [
        ({}, live_robot, {"x": 3.095, "y": -0.290, "z": 0.05}),
        ({}, live_robot, {"x": 3.060, "y": -0.293, "z": 0.05}),
        ({}, live_robot, high_lateral_ball),
        ({}, live_robot, high_lateral_ball),
        ({}, live_robot, high_lateral_ball),
        ({}, live_robot, high_lateral_ball),
        ({}, live_robot, high_lateral_ball),
        ({}, live_robot, high_lateral_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, live_robot, high_lateral_ball

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
    assert payload["settle_no_chase_activated"] is True
    assert payload["release_gate_blocked_reason"] == "none"
    assert any(item["mode"] == "settle_no_chase" for item in command_log)


def test_object_centric_place_ignores_single_stale_high_lateral_no_chase_sample(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    live_robot = {"x": 4.649462, "y": -0.008525, "yaw": -2.905234}
    stale_edge_sample = {"x": 2.863355, "y": 0.520620, "z": 0.05}
    states = [
        ({}, live_robot, stale_edge_sample),
        ({}, live_robot, stale_edge_sample),
        ({}, live_robot, {"x": 2.815591, "y": 0.534477, "z": 0.05}),
        ({}, live_robot, {"x": 2.767228, "y": 0.548507, "z": 0.05}),
        ({}, live_robot, {"x": 2.720264, "y": 0.562132, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, live_robot, {"x": 2.674099, "y": 0.575524, "z": 0.05}

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
    assert payload["settle_no_chase_activated"] is False
    assert all(item["mode"] != "settle_no_chase" for item in command_log)


def test_object_centric_place_ignores_single_stale_no_chase_sample_for_unsecured_ball(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    live_robot = {"x": 3.972, "y": -0.041, "yaw": 2.819}
    center_sample = {"x": 2.378, "y": -0.072, "z": 0.05}
    states = [
        ({}, live_robot, center_sample),
        ({}, live_robot, center_sample),
        ({}, live_robot, {"x": 2.343, "y": -0.073, "z": 0.05}),
        ({}, live_robot, {"x": 2.307, "y": -0.073, "z": 0.05}),
        ({}, live_robot, {"x": 2.273, "y": -0.074, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, live_robot, {"x": 2.238, "y": -0.074, "z": 0.05}

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
    assert payload["settle_no_chase_activated"] is False
    assert all(item["mode"] != "settle_no_chase" for item in command_log)


def test_object_centric_place_waits_to_no_chase_until_moving_ball_is_centered(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    robot_pose = {"x": 3.353616, "y": 0.945910, "yaw": -2.446903}
    previous_ball = {"x": 2.658363, "y": 0.202674, "z": 0.05}
    moving_not_centered_ball = {"x": 2.635335, "y": 0.178370, "z": 0.05}
    states = [
        ({}, robot_pose, previous_ball),
        ({}, robot_pose, moving_not_centered_ball),
        ({}, robot_pose, moving_not_centered_ball),
        ({}, robot_pose, moving_not_centered_ball),
        ({}, robot_pose, moving_not_centered_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, robot_pose, moving_not_centered_ball

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
    assert payload["failure_stage"] == "place"
    assert payload["settle_no_chase_activated"] is False
    assert all(item["mode"] != "settle_no_chase" for item in command_log)


def test_object_centric_place_starts_no_chase_for_deep_unsecured_retrieval_ball(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
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

    live_robot = {"x": 3.426054, "y": 0.83522, "yaw": -3.096978}
    deep_moving_ball = {"x": 2.725738, "y": -0.129731, "z": 0.05}
    centered_ball = {"x": 2.4, "y": 0.0, "z": 0.05}
    states = [
        ({}, live_robot, {"x": 2.748106, "y": -0.101795, "z": 0.05}),
        ({}, live_robot, deep_moving_ball),
        ({}, live_robot, centered_ball),
        ({}, live_robot, centered_ball),
        ({}, live_robot, centered_ball),
        ({}, live_robot, centered_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, live_robot, centered_ball

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
    assert payload["settle_no_chase_activated"] is True
    assert payload["release_gate_blocked_reason"] == "none"
    assert any(item["mode"] == "settle_no_chase" for item in command_log)


def test_object_centric_place_does_not_start_no_chase_after_ball_slips_behind(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    robot_pose = {"x": 3.844664, "y": -0.278383, "yaw": 1.636664}
    slipped_ball = {"x": 2.480997, "y": -0.551251, "z": 0.05}

    def _control_loop_state(**kwargs):
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
    assert payload["failure_stage"] == "place"
    assert payload["settle_no_chase_activated"] is False
    assert all(item["mode"] != "settle_no_chase" for item in command_log)


def test_object_centric_no_chase_recontacts_before_leaving_retrieval_overlap(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
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

    center_robot = {"x": 3.546642, "y": -0.140912, "yaw": 2.630410}
    center_ball = {"x": 2.527145, "y": -0.130904, "z": 0.05}
    edge_robot = {"x": 3.939261, "y": 0.146912, "yaw": -1.682438}
    edge_overlap_ball = {"x": 1.910181, "y": 0.611092, "z": 0.05}
    states = [
        ({}, center_robot, {"x": 2.561844, "y": -0.131995, "z": 0.05}),
        ({}, center_robot, center_ball),
        ({}, center_robot, center_ball),
        ({}, center_robot, center_ball),
        ({}, edge_robot, edge_overlap_ball),
        ({}, center_robot, center_ball),
        ({}, center_robot, center_ball),
        ({}, center_robot, center_ball),
        ({}, center_robot, center_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, center_robot, center_ball

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
    assert payload["release_recontact_count"] == 1
    assert payload["settle_no_chase_activated"] is True
    assert any(item["mode"] == "settle_no_chase" for item in command_log)


def test_object_centric_place_shepherds_shallow_unsecured_ball_inside_retrieval_corral(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    robot_pose = {"x": 3.817853, "y": -0.218638, "yaw": 3.077252}
    shallow_ball = {"x": 2.941005, "y": -0.362959, "z": 0.05}

    def _control_loop_state(**kwargs):
        return {}, robot_pose, shallow_ball

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
    assert payload["failure_stage"] == "place"
    shepherd_commands = [item for item in command_log if item["mode"] == "object_place_inside_retrieval_shepherd"]
    assert shepherd_commands
    assert all(item["enabled"] is True for item in shepherd_commands)
    assert max(float(item["linear_x"]) for item in shepherd_commands) <= 0.014
    assert all(item["mode"] not in {"capture_recovery", "capture_recovery_hold"} for item in command_log)


def test_object_centric_place_shepherds_retrieval_edge_overlap(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    robot_pose = {"x": 3.871232, "y": -0.082077, "yaw": 3.129361}
    overlap_ball = {"x": 3.169866, "y": -0.102835, "z": 0.05}

    def _control_loop_state(**kwargs):
        return {}, robot_pose, overlap_ball

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
    assert payload["failure_stage"] == "place"
    shepherd_commands = [item for item in command_log if item["mode"] == "object_place_inside_retrieval_shepherd"]
    assert shepherd_commands
    assert max(float(item["linear_x"]) for item in shepherd_commands) <= 0.006
    assert all(item["mode"] not in {"retrieval_hold", "capture_recovery", "capture_recovery_hold"} for item in command_log)


def test_object_centric_place_holds_latest_zero_high_x_negative_edge_inside_retrieval(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    edge_entry_robot = {"x": 4.843193, "y": -0.008037, "yaw": -2.999394}
    terminal_inside_robot = {"x": 4.843193, "y": -0.008037, "yaw": -3.099394}
    edge_entry_ball = {"x": 3.051366, "y": -0.418591, "z": 0.05}
    terminal_inside_ball = {"x": 3.002925, "y": -0.429871, "z": 0.05}
    states = [
        ({}, edge_entry_robot, edge_entry_ball),
        ({}, terminal_inside_robot, terminal_inside_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, terminal_inside_robot, terminal_inside_ball

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
    assert payload["failure_stage"] == "place"
    hold_commands = [item for item in command_log if item["mode"] == "object_place_inside_retrieval_hold"]
    assert hold_commands
    assert all(item["enabled"] is False for item in hold_commands)
    assert all(float(item["linear_x"]) == 0.0 and float(item["angular_z"]) == 0.0 for item in hold_commands)
    first_hold_index = next(
        index for index, item in enumerate(command_log) if item["mode"] == "object_place_inside_retrieval_hold"
    )
    assert all(
        not (item["mode"] == "object_place_inside_retrieval_shepherd" and float(item["linear_x"]) > 0.0)
        for item in command_log[first_hold_index:]
    )


def test_object_centric_place_recovery_preserves_lateral_recenter(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 5.668368, "y": 0.06432, "yaw": -2.876083}, {"x": 5.30795, "y": -0.120153, "z": 0.05}),
        ({}, {"x": 5.661493, "y": 0.063102, "yaw": -3.020963}, {"x": 5.266925, "y": -0.154873, "z": 0.05}),
        ({}, {"x": 5.661493, "y": 0.063102, "yaw": -3.020963}, {"x": 5.266925, "y": -0.154873, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 5.661493, "y": 0.063102, "yaw": -3.020963}, {"x": 5.266925, "y": -0.154873, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    recenter_commands = [item for item in command_log if item["mode"] == "object_place_lateral_recenter"]
    assert recenter_commands
    assert all(float(item["linear_x"]) == 0.0 for item in recenter_commands)
    assert all(float(item["angular_z"]) < 0.0 for item in recenter_commands)


def test_object_centric_place_recovery_preserves_far_lateral_recenter_outside_recapture(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 4.966751, "y": -0.208337, "yaw": -2.882975}, {"x": 4.416685, "y": -0.452844, "z": 0.05}),
        ({}, {"x": 4.935988, "y": -0.213790, "yaw": -3.056155}, {"x": 4.383710, "y": -0.465903, "z": 0.05}),
        ({}, {"x": 4.935988, "y": -0.213790, "yaw": -3.056155}, {"x": 4.383710, "y": -0.465903, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 4.935988, "y": -0.213790, "yaw": -3.056155}, {"x": 4.383710, "y": -0.465903, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    recenter_commands = [item for item in command_log if item["mode"] == "object_place_lateral_recenter"]
    assert recenter_commands
    assert all(float(item["linear_x"]) == 0.0 for item in recenter_commands)
    assert all(item["mode"] not in {"capture_recovery", "capture_recovery_hold"} for item in command_log)


def test_object_centric_place_recovery_preserves_forward_far_lateral_recenter(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 4.882334, "y": -0.260975, "yaw": -2.877648}, {"x": 4.133749, "y": -0.627520, "z": 0.05}),
        ({}, {"x": 4.829201, "y": -0.268236, "yaw": -2.947252}, {"x": 4.058018, "y": -0.661010, "z": 0.05}),
        ({}, {"x": 4.781566, "y": -0.287712, "yaw": -2.919598}, {"x": 3.946967, "y": -0.710120, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 4.781566, "y": -0.287712, "yaw": -2.919598}, {"x": 3.946967, "y": -0.710120, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    recenter_commands = [item for item in command_log if item["mode"] == "object_place_lateral_recenter"]
    assert recenter_commands
    assert all(float(item["linear_x"]) == 0.0 for item in recenter_commands)
    assert all(item["mode"] not in {"capture_recovery", "capture_recovery_hold"} for item in command_log)


def test_object_centric_place_recovery_preserves_latest_wide_far_lateral_recenter(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.25
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

    states = [
        ({}, {"x": 5.150, "y": 0.0, "yaw": 3.141593}, {"x": 5.448, "y": 0.0, "z": 0.05}),
        ({}, {"x": 5.177560, "y": -0.152114, "yaw": -2.912301}, {"x": 4.661209, "y": -0.414212, "z": 0.05}),
        ({}, {"x": 4.872030, "y": -0.263390, "yaw": -2.985890}, {"x": 3.946211, "y": -0.790637, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 4.872030, "y": -0.263390, "yaw": -2.985890}, {
            "x": 3.946211,
            "y": -0.790637,
            "z": 0.05,
        }

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
    assert payload["failure_stage"] == "place"
    recenter_commands = [item for item in command_log if item["mode"] == "object_place_lateral_recenter"]
    assert recenter_commands
    assert all(float(item["linear_x"]) == 0.0 for item in recenter_commands)
    assert min(float(item["angular_z"]) for item in recenter_commands) < 0.0
    assert all(item["mode"] != "release_roll_away" for item in command_log)


def test_object_centric_place_recovery_preserves_far_keepup_outside_recapture(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 4.418972, "y": -0.416256, "yaw": -2.811240}, {"x": 3.687352, "y": -0.849203, "z": 0.05}),
        ({}, {"x": 4.409990, "y": -0.419350, "yaw": -2.806556}, {"x": 3.660217, "y": -0.861470, "z": 0.05}),
        ({}, {"x": 4.399423, "y": -0.423122, "yaw": -2.795907}, {"x": 3.628719, "y": -0.875709, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 4.399423, "y": -0.423122, "yaw": -2.795907}, {"x": 3.628719, "y": -0.875709, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    keepup_commands = [item for item in command_log if item["mode"] == "object_place_recapture_drive"]
    assert keepup_commands
    assert max(float(item["linear_x"]) for item in keepup_commands) > 0.0
    assert all(item["mode"] not in {"capture_recovery", "capture_recovery_hold"} for item in command_log)


def test_object_centric_place_recovery_preserves_far_recapture_reel_outside_recapture(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 4.688528, "y": 2.367859, "yaw": -1.882207}, {"x": 4.561107, "y": 1.918943, "z": 0.05}),
        ({}, {"x": 5.286221, "y": -0.114683, "yaw": -2.959096}, {"x": 4.131349, "y": -0.581556, "z": 0.05}),
        ({}, {"x": 5.004266, "y": -0.026968, "yaw": 2.63545}, {"x": 3.763898, "y": 0.032231, "z": 0.05}),
        ({}, {"x": 5.220518, "y": 0.035618, "yaw": 2.904654}, {"x": 4.178999, "y": 0.968452, "z": 0.05}),
        ({}, {"x": 5.180412, "y": -0.095391, "yaw": -2.729457}, {"x": 3.807159, "y": -0.421644, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 5.286221, "y": -0.114683, "yaw": -2.959096}, {"x": 4.131349, "y": -0.581556, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    reel_commands = [item for item in command_log if item["mode"] == "object_place_far_recapture_reel"]
    assert reel_commands
    assert max(float(item["linear_x"]) for item in reel_commands) > 0.0
    assert max(float(item["angular_z"]) for item in reel_commands) > 0.45
    assert len(reel_commands) >= 3
    assert all(item["mode"] not in {"capture_recovery", "capture_recovery_hold", "release_roll_away"} for item in command_log)


def test_object_centric_place_recovery_preserves_outer_near_zone_wide_reel(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 4.688528, "y": 2.367859, "yaw": -1.882207}, {"x": 4.561107, "y": 1.918943, "z": 0.05}),
        ({}, {"x": 4.781375, "y": 0.002758, "yaw": 2.650113}, {"x": 3.333699, "y": 0.706385, "z": 0.05}),
        ({}, {"x": 4.762638, "y": 0.006483, "yaw": 3.061473}, {"x": 3.292312, "y": 0.728096, "z": 0.05}),
        ({}, {"x": 4.762638, "y": 0.006483, "yaw": 3.061473}, {"x": 3.292312, "y": 0.728096, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 4.762638, "y": 0.006483, "yaw": 3.061473}, {"x": 3.292312, "y": 0.728096, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    reel_commands = [item for item in command_log if item["mode"] == "object_place_near_zone_wide_reel"]
    assert reel_commands
    assert max(float(item["linear_x"]) for item in reel_commands) > 0.0
    assert min(float(item["angular_z"]) for item in reel_commands) < -0.45
    assert all(item["mode"] not in {"capture_recovery", "capture_recovery_hold", "release_roll_away"} for item in command_log)


def test_object_centric_place_recovery_preserves_low_x_near_zone_wide_reel(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 4.392772, "y": -0.109889, "yaw": 3.02611}, {"x": 3.829318, "y": -0.228337, "z": 0.05}),
        ({}, {"x": 4.349147, "y": -0.115901, "yaw": -3.04577}, {"x": 3.538411, "y": -0.298348, "z": 0.05}),
        ({}, {"x": 4.326316, "y": -0.1167, "yaw": 3.083367}, {"x": 3.505316, "y": -0.306313, "z": 0.05}),
        ({}, {"x": 4.326316, "y": -0.1167, "yaw": 3.083367}, {"x": 3.505316, "y": -0.306313, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 4.326316, "y": -0.1167, "yaw": 3.083367}, {"x": 3.505316, "y": -0.306313, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    reel_commands = [item for item in command_log if item["mode"] == "object_place_near_zone_wide_reel"]
    assert reel_commands
    assert max(float(item["linear_x"]) for item in reel_commands) > 0.0
    assert max(float(item["angular_z"]) for item in reel_commands) > 0.45
    assert all(item["mode"] not in {"capture_recovery", "capture_recovery_hold", "release_roll_away"} for item in command_log)


def test_object_centric_place_recovery_preserves_high_x_near_zone_edge_wide_reel(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 4.688528, "y": 2.367859, "yaw": -1.882207}, {"x": 4.561107, "y": 1.918943, "z": 0.05}),
        ({}, {"x": 4.953242, "y": 0.008763, "yaw": 2.459923}, {"x": 3.19051, "y": 0.410466, "z": 0.05}),
        ({}, {"x": 4.951442, "y": 0.010059, "yaw": 2.749263}, {"x": 3.148718, "y": 0.419865, "z": 0.05}),
        ({}, {"x": 4.951442, "y": 0.010059, "yaw": 2.749263}, {"x": 3.148718, "y": 0.419865, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 4.951442, "y": 0.010059, "yaw": 2.749263}, {"x": 3.148718, "y": 0.419865, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    assert payload["local_recovery_attempted"] is True
    reel_commands = [item for item in command_log if item["mode"] == "object_place_near_zone_wide_reel"]
    assert reel_commands
    assert any(float(item["linear_x"]) == 0.0 for item in reel_commands)
    assert max(float(item["angular_z"]) for item in reel_commands) > 0.45
    assert all(item["mode"] not in {"capture_recovery", "capture_recovery_hold", "release_roll_away"} for item in command_log)


def test_object_centric_place_preserves_high_x_escape_edge_after_inside_rollout(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 5.015922, "y": 0.013950, "yaw": 3.073187}, {"x": 4.445784, "y": -0.039761, "z": 0.05}),
        ({}, {"x": 4.819610, "y": 0.000922, "yaw": 2.830849}, {"x": 1.770361, "y": -0.448410, "z": 0.05}),
        ({}, {"x": 4.819610, "y": 0.000922, "yaw": 2.659589}, {"x": 1.724528, "y": -0.455410, "z": 0.05}),
        ({}, {"x": 4.819610, "y": 0.000922, "yaw": 2.659589}, {"x": 1.724528, "y": -0.455410, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 4.819610, "y": 0.000922, "yaw": 2.659589}, {"x": 1.724528, "y": -0.455410, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    assert payload["local_recovery_attempted"] is True
    reel_commands = [item for item in command_log if item["mode"] == "object_place_near_zone_wide_reel"]
    assert reel_commands
    assert all(float(item["linear_x"]) == 0.0 for item in reel_commands)
    assert max(float(item["angular_z"]) for item in reel_commands) > 0.45
    assert all(item["mode"] not in {"capture_recovery", "capture_recovery_hold", "release_roll_away"} for item in command_log)


def test_object_centric_place_recovery_preserves_low_x_high_lateral_near_zone_reel(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 4.688528, "y": 2.367859, "yaw": -1.882207}, {"x": 4.561107, "y": 1.918943, "z": 0.05}),
        ({}, {"x": 4.543265, "y": -0.000564, "yaw": -2.789976}, {"x": 3.639395, "y": 0.118687, "z": 0.05}),
        ({}, {"x": 4.543265, "y": -0.000564, "yaw": -2.691081}, {"x": 3.587776, "y": 0.126222, "z": 0.05}),
        ({}, {"x": 4.543265, "y": -0.000564, "yaw": -2.576281}, {"x": 3.536379, "y": 0.133725, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 4.543265, "y": -0.000564, "yaw": -2.576281}, {"x": 3.536379, "y": 0.133725, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    assert payload["local_recovery_attempted"] is True
    reel_commands = [item for item in command_log if item["mode"] == "object_place_near_zone_wide_reel"]
    assert reel_commands
    assert min(float(item["angular_z"]) for item in reel_commands) < -0.45
    assert max(float(item["linear_x"]) for item in reel_commands) <= 0.014
    assert all(item["mode"] not in {"capture_recovery", "capture_recovery_hold", "release_roll_away"} for item in command_log)


def test_object_centric_place_recovery_preserves_far_wide_lateral_recenter(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 4.688528, "y": 2.367859, "yaw": -1.882207}, {"x": 4.561107, "y": 1.918943, "z": 0.05}),
        ({}, {"x": 5.479095, "y": -0.059575, "yaw": 3.0124}, {"x": 4.583494, "y": -0.450093, "z": 0.05}),
        ({}, {"x": 5.479095, "y": -0.059575, "yaw": 3.0124}, {"x": 4.583494, "y": -0.450093, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 5.479095, "y": -0.059575, "yaw": 3.0124}, {"x": 4.583494, "y": -0.450093, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    wide_recenter_commands = [item for item in command_log if item["mode"] == "object_place_far_wide_lateral_recenter"]
    assert wide_recenter_commands
    assert all(float(item["linear_x"]) == 0.0 for item in wide_recenter_commands)
    assert min(float(item["angular_z"]) for item in wide_recenter_commands) < -0.45
    assert all(item["mode"] not in {"capture_recovery", "capture_recovery_hold", "release_roll_away"} for item in command_log)


def test_object_centric_place_recovery_preserves_same_side_high_lateral_far_recenter(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    recapture_entry_robot = {"x": 5.193506, "y": -0.003195, "yaw": 3.048016}
    high_lateral_robot = {"x": 5.384625, "y": -0.021094, "yaw": 1.805223}
    terminal_high_lateral_robot = {"x": 5.384625, "y": -0.021094, "yaw": 1.570593}
    recapture_entry_ball = {"x": 4.637266, "y": 0.153496, "z": 0.05}
    high_lateral_ball = {"x": 3.827900, "y": 0.524276, "z": 0.05}
    terminal_high_lateral_ball = {"x": 3.782314, "y": 0.542019, "z": 0.05}
    states = [
        ({}, recapture_entry_robot, recapture_entry_ball),
        ({}, high_lateral_robot, high_lateral_ball),
        ({}, terminal_high_lateral_robot, terminal_high_lateral_ball),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, terminal_high_lateral_robot, terminal_high_lateral_ball

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
    assert payload["failure_stage"] == "place"
    assert payload["local_recovery_attempted"] is True
    wide_recenter_commands = [item for item in command_log if item["mode"] == "object_place_far_wide_lateral_recenter"]
    assert wide_recenter_commands
    assert all(float(item["linear_x"]) == 0.0 for item in wide_recenter_commands)
    assert max(float(item["angular_z"]) for item in wide_recenter_commands) > 0.75
    assert all(item["mode"] not in {"capture_recovery", "capture_recovery_hold", "release_roll_away"} for item in command_log)


def test_object_centric_place_recovery_preserves_far_captured_gap_keepup(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 5.035712, "y": 0.022386, "yaw": -3.088952}, {"x": 4.701802, "y": -0.043917, "z": 0.05}),
        ({}, {"x": 5.035712, "y": 0.022386, "yaw": -3.064912}, {"x": 4.664488, "y": -0.060630, "z": 0.05}),
        ({}, {"x": 5.035712, "y": 0.022386, "yaw": -3.096912}, {"x": 4.625905, "y": -0.077911, "z": 0.05}),
        ({}, {"x": 5.035712, "y": 0.022386, "yaw": 3.058828}, {"x": 4.550563, "y": -0.111656, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 5.035712, "y": 0.022386, "yaw": 3.058828}, {"x": 4.550563, "y": -0.111656, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    gap_keepup_commands = [
        item
        for item in command_log
        if item["mode"] in {"object_place_drive_to_zone", "object_place_recapture_drive"}
    ]
    assert gap_keepup_commands
    assert max(float(item["linear_x"]) for item in gap_keepup_commands) > 0.0
    assert any(item["mode"] == "object_place_recapture_drive" for item in gap_keepup_commands)
    assert all(item["mode"] not in {"capture_recovery", "capture_recovery_hold", "release_roll_away"} for item in command_log)


def test_object_centric_place_recovery_preserves_far_wide_opposed_local_lateral_recenter(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 4.688528, "y": 2.367859, "yaw": -1.882207}, {"x": 4.561107, "y": 1.918943, "z": 0.05}),
        ({}, {"x": 4.776, "y": -0.006, "yaw": -2.714}, {"x": 3.865, "y": 0.127, "z": 0.05}),
        ({}, {"x": 4.766, "y": -0.012, "yaw": -2.594}, {"x": 3.718, "y": 0.154, "z": 0.05}),
        ({}, {"x": 4.763059, "y": -0.013893, "yaw": -2.496476}, {"x": 3.668598, "y": 0.162922, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 4.763059, "y": -0.013893, "yaw": -2.496476}, {"x": 3.668598, "y": 0.162922, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    assert payload["local_recovery_attempted"] is True
    wide_recenter_commands = [item for item in command_log if item["mode"] == "object_place_far_wide_lateral_recenter"]
    assert wide_recenter_commands
    assert min(float(item["angular_z"]) for item in wide_recenter_commands) < -0.45
    assert all(item["mode"] not in {"capture_recovery", "capture_recovery_hold", "release_roll_away"} for item in command_log)


def test_object_centric_place_recovery_preserves_middle_band_far_line_recenter(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 4.688528, "y": 2.367859, "yaw": -1.882207}, {"x": 4.561107, "y": 1.918943, "z": 0.05}),
        ({}, {"x": 4.767767, "y": -0.082648, "yaw": -2.88414}, {"x": 3.733392, "y": -0.201453, "z": 0.05}),
        ({}, {"x": 4.767767, "y": -0.082648, "yaw": -2.88414}, {"x": 3.733392, "y": -0.201453, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 4.767767, "y": -0.082648, "yaw": -2.88414}, {"x": 3.733392, "y": -0.201453, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    recenter_commands = [item for item in command_log if item["mode"] == "object_place_lateral_recenter"]
    assert recenter_commands
    assert all(float(item["linear_x"]) == 0.0 for item in recenter_commands)
    assert all(item["mode"] not in {"capture_recovery", "capture_recovery_hold", "release_roll_away"} for item in command_log)


def test_object_centric_place_recovery_preserves_outer_near_zone_line_keepup(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 4.659868, "y": -0.068780, "yaw": 3.061464}, {"x": 3.957698, "y": -0.132648, "z": 0.05}),
        ({}, {"x": 4.563013, "y": -0.069812, "yaw": -3.080568}, {"x": 3.619218, "y": -0.149185, "z": 0.05}),
        ({}, {"x": 4.563013, "y": -0.069812, "yaw": -2.938548}, {"x": 3.583252, "y": -0.150942, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 4.563013, "y": -0.069812, "yaw": -2.938548}, {"x": 3.583252, "y": -0.150942, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    line_keepup_commands = [item for item in command_log if item["mode"] == "object_place_far_line_recenter"]
    assert line_keepup_commands
    assert max(float(item["linear_x"]) for item in line_keepup_commands) >= 0.025
    assert all(item["mode"] not in {"capture_recovery", "release_roll_away"} for item in command_log)


def test_object_centric_place_recovery_preserves_moving_far_middle_lateral_line_keepup(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 5.223762, "y": -0.077807, "yaw": -3.056275}, {"x": 4.570348, "y": -0.320465, "z": 0.05}),
        ({}, {"x": 5.223762, "y": -0.077807, "yaw": -3.056275}, {"x": 4.531365, "y": -0.341697, "z": 0.05}),
        ({}, {"x": 5.223762, "y": -0.077807, "yaw": -3.140955}, {"x": 4.489411, "y": -0.364547, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 5.223762, "y": -0.077807, "yaw": -3.140955}, {"x": 4.489411, "y": -0.364547, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    line_keepup_commands = [item for item in command_log if item["mode"] == "object_place_far_line_recenter"]
    assert line_keepup_commands
    assert max(float(item["linear_x"]) for item in line_keepup_commands) > 0.0
    assert all(item["mode"] not in {"capture_recovery", "capture_recovery_hold", "release_roll_away"} for item in command_log)


def test_object_centric_place_recovery_preserves_high_x_far_line_recenter(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 4.688528, "y": 2.367859, "yaw": -1.882207}, {"x": 4.561107, "y": 1.918943, "z": 0.05}),
        ({}, {"x": 5.16131, "y": 0.080435, "yaw": 2.968147}, {"x": 3.701421, "y": 1.144426, "z": 0.05}),
        ({}, {"x": 5.153666, "y": 0.08338, "yaw": 2.543747}, {"x": 3.664873, "y": 1.173711, "z": 0.05}),
        ({}, {"x": 5.153666, "y": 0.08338, "yaw": 2.543747}, {"x": 3.664873, "y": 1.173711, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 5.153666, "y": 0.08338, "yaw": 2.543747}, {"x": 3.664873, "y": 1.173711, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    recenter_commands = [item for item in command_log if item["mode"] == "object_place_lateral_recenter"]
    assert recenter_commands
    assert all(float(item["linear_x"]) == 0.0 for item in recenter_commands)
    assert max(float(item["angular_z"]) for item in recenter_commands) >= 0.45
    assert all(item["mode"] not in {"capture_recovery", "capture_recovery_hold", "release_roll_away"} for item in command_log)


def test_object_centric_place_recovery_preserves_late_zero_high_x_far_line_boundary(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    states = [
        ({}, {"x": 4.688528, "y": 2.367859, "yaw": -1.882207}, {"x": 4.561107, "y": 1.918943, "z": 0.05}),
        ({}, {"x": 5.280991, "y": -0.182392, "yaw": -2.167528}, {"x": 3.634386, "y": -1.231736, "z": 0.05}),
        ({}, {"x": 5.27704, "y": -0.186986, "yaw": -2.439828}, {"x": 3.60319, "y": -1.252923, "z": 0.05}),
        ({}, {"x": 5.27704, "y": -0.186986, "yaw": -2.439828}, {"x": 3.60319, "y": -1.252923, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, {"x": 5.27704, "y": -0.186986, "yaw": -2.439828}, {"x": 3.60319, "y": -1.252923, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    assert payload["local_recovery_attempted"] is True
    recenter_commands = [item for item in command_log if item["mode"] == "object_place_lateral_recenter"]
    assert recenter_commands
    assert all(float(item["linear_x"]) == 0.0 for item in recenter_commands)
    assert min(float(item["angular_z"]) for item in recenter_commands) <= -0.45
    assert all(item["mode"] not in {"capture_recovery", "capture_recovery_hold", "release_roll_away"} for item in command_log)


def test_object_centric_place_recovery_preserves_low_x_far_line_keepup(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = "object_centric_gather_policy_v1"
    runner.args.place_timeout_s = 1.0
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

    robot_pose = {"x": 5.294000, "y": -0.058000, "yaw": 2.936000}
    states = [
        ({}, robot_pose, {"x": 4.878253, "y": 0.129931, "z": 0.05}),
        ({}, robot_pose, {"x": 4.844693, "y": 0.161069, "z": 0.05}),
        ({}, robot_pose, {"x": 4.811133, "y": 0.192207, "z": 0.05}),
        ({}, robot_pose, {"x": 4.811133, "y": 0.192207, "z": 0.05}),
    ]

    def _control_loop_state(**kwargs):
        if states:
            return states.pop(0)
        return {}, robot_pose, {"x": 4.811133, "y": 0.192207, "z": 0.05}

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
    assert payload["failure_stage"] == "place"
    line_commands = [item for item in command_log if item["mode"] == "object_place_lateral_recenter"]
    assert line_commands
    assert all(float(item["linear_x"]) == 0.0 for item in line_commands)
    assert max(float(item["angular_z"]) for item in line_commands) >= 0.25
    assert all(item["mode"] not in {"capture_recovery", "capture_recovery_hold", "release_roll_away"} for item in command_log)


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


def test_run_target_fetch_to_pose_accepts_rollthrough_delivery_intersection(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.mission_objective = "fetch_to_pose"
    runner.fetch_delivery_radius_m = 0.25

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
    monkeypatch.setattr(runner, "_record_target_position", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_capture_target",
        lambda **kwargs: (True, {"capture_state": {"captured": True}, "zone_score": {}, "handoff_kind": "secure_capture"}),
    )

    def _fetch_to_pose_target(**kwargs):
        gather_runner.append_jsonl(
            kwargs["state_history_path"],
            {
                "generated_utc": "2026-05-13T00:00:00Z",
                "event_type": "fetch_to_pose_tick",
                "phase": "fetch_to_pose",
                "target_id": "ball_1",
                "ball_pose": {"x": 2.4, "y": 0.0, "z": 0.05},
            },
        )
        return (
            True,
            {
                "failure_reason": "",
                "failure_stage": "",
                "final_ball_pose": {"x": 2.4, "y": 0.0, "z": 0.05},
                "fetch_elapsed_s": 1.25,
                "settle_exit_reason": "trajectory_intersects_delivery_radius",
                "rolled_away_after_release": False,
            },
        )

    monkeypatch.setattr(runner, "_fetch_to_pose_target", _fetch_to_pose_target)
    monkeypatch.setattr(
        runner,
        "_place_target",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("fetch_to_pose should not run legacy place")),
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
    assert result["mission_objective"] == "fetch_to_pose"
    assert result["fetch_to_pose_reached"] is True
    assert result["fetch_to_pose_time_s"] == 1.25
    assert result["shot_outcome"]["reason"] == "trajectory_intersects_delivery_radius"
    assert result["settled_in_corral_pass"] is False
    rows = [
        json.loads(line)
        for line in (tmp_path / "state_history.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(row.get("phase") == "fetch_to_pose" for row in rows)


def test_contact_ready_fetch_gate_starts_robot_behind_ball_and_preserves_nav2_monitor_payload(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.mission_objective = "fetch_to_pose"
    runner.fetch_gate_mode = "contact_ready"
    runner.gather_control_family = gather_runner.NAV2_FOLLOW_PATH_CORRIDOR_PUSH_CONTROL_FAMILY
    runner.args.fetch_target_x = 0.95
    runner.args.fetch_target_y = 0.0
    runner.args.fetch_target_z = 0.001
    runner.fetch_delivery_radius_m = 0.30
    runner.visit_runtime_state = {
        "visited_targets": [],
        "remaining_targets": ["ball_1"],
        "target_positions": {},
    }
    runner.gather_runtime_state = {
        "placed_targets": [],
        "remaining_targets": ["ball_1"],
        "manual_drive": {},
    }
    state_history_path = tmp_path / "state_history.jsonl"
    gather_sequence_path = tmp_path / "gather_sequence.jsonl"
    target = runner.targets_by_id["ball_1"]
    set_pose_calls: list[dict[str, float]] = []
    truth_pose_waits: list[dict[str, object]] = []

    monkeypatch.setattr(
        gather_runner,
        "fetch_dashboard_state",
        lambda dashboard_url, timeout_s=0: {
            "compose_project": "session-contact-ready",
            "world_name": "default",
            "belief": {"latest_robot_pose": {"x": 0.03, "y": 0.0, "yaw": 0.0}},
        },
    )
    monkeypatch.setattr(runner, "_safe_stop", lambda: None)
    monkeypatch.setattr(runner, "_wait_for_pursuit_quiet", lambda timeout_s: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **kwargs: runner.gather_runtime_state.update(kwargs))
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **kwargs: runner.visit_runtime_state.update(kwargs))
    monkeypatch.setattr(
        runner,
        "_ball_truth_pose",
        lambda session_id, target: {"x": 0.38, "y": 0.0, "z": 0.021336},
    )
    monkeypatch.setattr(
        runner,
        "_set_robot_pose",
        lambda state, *, x, y, yaw: set_pose_calls.append({"x": x, "y": y, "yaw": yaw}),
    )
    monkeypatch.setattr(
        runner,
        "_wait_for_robot_pose_near",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("dashboard pose stale")),
    )
    monkeypatch.setattr(
        runner,
        "_wait_for_robot_truth_pose_near",
        lambda **kwargs: truth_pose_waits.append(kwargs) or {},
    )

    def fake_fetch_to_pose_target(**kwargs):
        assert kwargs["attempt_kind"] == "contact_ready_gate"
        return (
            True,
            {
                "failure_reason": "",
                "failure_stage": "",
                "final_ball_pose": {"x": 0.95, "y": 0.0, "z": 0.021336},
                "fetch_elapsed_s": 1.25,
                "settle_exit_reason": "trajectory_intersects_delivery_radius",
                "rolled_away_after_release": False,
                "nav2_follow_path_corridor_push": {
                    "dispatch_status": "monitor_success",
                    "monitor_cancel_reason": "success",
                    "monitor_sample": {
                        "delivery_distance_m": 0.0,
                        "lateral_error_m": 0.0,
                        "robot_ball_distance_m": 0.12,
                    },
                    "status_code": 5,
                },
            },
        )

    monkeypatch.setattr(runner, "_fetch_to_pose_target", fake_fetch_to_pose_target)

    result = runner._run_contact_ready_fetch_target(
        session_id="session-contact-ready",
        target=target,
        route_index=1,
        gather_sequence_path=gather_sequence_path,
        state_history_path=state_history_path,
    )

    assert result["pass"] is True
    assert result["attempt_kind"] == "contact_ready_gate"
    assert result["pre_stage_pose_reached"] is True
    assert result["capture_entry_reached"] is True
    assert set_pose_calls == [{"x": 0.03, "y": 0.0, "yaw": 0.0}]
    assert truth_pose_waits and truth_pose_waits[0]["session_id"] == "session-contact-ready"
    assert result["shot_outcome"]["closest_approach_distance_m"] == 0.0
    assert result["shot_outcome"]["nav2_follow_path_corridor_push"]["dispatch_status"] == "monitor_success"
    assert result["shot_outcome"]["nav2_follow_path_corridor_push"]["monitor_sample"]["robot_ball_distance_m"] == 0.12
    events = [
        json.loads(line)["event_type"]
        for line in state_history_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert "nav2_follow_path_corridor_push_contact_ready_gate_start" in events
    assert "nav2_follow_path_corridor_push_contact_ready_gate_result" in events
    ready_rows = [
        json.loads(line)
        for line in state_history_path.read_text(encoding="utf-8").splitlines()
        if "nav2_follow_path_corridor_push_contact_ready_gate_ready" in line
    ]
    assert ready_rows[0]["pose_confirmation_source"] == "truth_state"
    assert ready_rows[0]["dashboard_pose_wait_error"] == "dashboard pose stale"


def test_fetch_to_pose_outcome_ignores_pre_fetch_ball_samples(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.fetch_delivery_radius_m = 0.25
    state_history_path = tmp_path / "state_history.jsonl"
    target = runner.targets_by_id["ball_1"]

    gather_runner.append_jsonl(
        state_history_path,
        {
            "generated_utc": "2026-05-13T00:00:00Z",
            "event_type": "capture_tick",
            "phase": "capture",
            "target_id": target.id,
            "ball_pose": {"x": 2.4, "y": 0.0, "z": 0.05},
        },
    )
    gather_runner.append_jsonl(
        state_history_path,
        {
            "generated_utc": "2026-05-13T00:00:01Z",
            "event_type": "fetch_to_pose_tick",
            "phase": "fetch_to_pose",
            "target_id": target.id,
            "ball_pose": {"x": 3.0, "y": 0.0, "z": 0.05},
        },
    )

    outcome = runner._build_fetch_to_pose_outcome(
        target=target,
        state_history_path=state_history_path,
        final_ball_pose={"x": 3.0, "y": 0.0, "z": 0.05},
        place_payload={},
    )

    assert outcome["pass"] is False
    assert outcome["closest_approach_distance_m"] == 0.6
    assert outcome["sample_count"] == 2


def test_fetch_to_pose_outcome_preserves_ai_push_coast_fields(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.fetch_delivery_radius_m = 0.25
    state_history_path = tmp_path / "state_history.jsonl"
    target = runner.targets_by_id["ball_1"]
    gather_runner.append_jsonl(
        state_history_path,
        {
            "generated_utc": "2026-05-13T00:00:01Z",
            "event_type": "fetch_to_pose_tick",
            "phase": "fetch_to_pose",
            "target_id": target.id,
            "ball_pose": {"x": 3.0, "y": 0.0, "z": 0.05},
        },
    )

    outcome = runner._build_fetch_to_pose_outcome(
        target=target,
        state_history_path=state_history_path,
        final_ball_pose={"x": 3.0, "y": 0.0, "z": 0.05},
        place_payload={
            "ai_push_coast_mode": "shadow",
            "ai_push_coast_shadow": {"model_id": "heuristic_hybrid_stage_supervisor_v0"},
            "ai_push_coast_proposal": {"maneuver_class": "terminal_repush"},
            "ai_push_coast_guard": {"accepted": False, "reasons": ["shadow_mode"]},
            "ai_push_coast_latency_ms": 0.25,
        },
    )

    assert outcome["ai_push_coast_mode"] == "shadow"
    assert outcome["ai_push_coast_shadow"]["model_id"] == "heuristic_hybrid_stage_supervisor_v0"
    assert outcome["ai_push_coast_proposal"]["maneuver_class"] == "terminal_repush"
    assert outcome["ai_push_coast_guard"]["reasons"] == ["shadow_mode"]
    assert outcome["ai_push_coast_latency_ms"] == 0.25


def test_fetch_to_pose_waits_for_launch_window_before_short_stop(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = gather_runner.OBJECT_CENTRIC_GATHER_POLICY_CONTROL_FAMILY
    runner.fetch_delivery_radius_m = 0.25
    runner.args.place_timeout_s = 2.5
    runner.args.poll_s = 0.5

    monkeypatch.setattr(gather_runner, "DEFAULT_OBJECT_CENTRIC_PLACE_TIMEOUT_S", 2.5)
    monkeypatch.setattr(gather_runner, "DEFAULT_FETCH_TO_POSE_MIN_LAUNCH_OBSERVE_S", 2.0)
    clock = {"now": 0.0}
    monkeypatch.setattr(gather_runner.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(gather_runner.time, "sleep", lambda seconds: clock.__setitem__("now", clock["now"] + seconds))
    monkeypatch.setattr(runner, "_update_prior_from_ball_pose", lambda target_id, ball_pose: None)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **updates: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **updates: None)

    robot_pose = {"x": 4.736887, "y": 2.375382, "yaw": -2.234298}
    ball_pose = {"x": 4.555261, "y": 2.155261, "z": 0.05}
    monkeypatch.setattr(
        runner,
        "_control_loop_state",
        lambda session_id, target: ({}, robot_pose, ball_pose),
    )
    command_log: list[dict[str, object]] = []
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

    passed, payload = runner._fetch_to_pose_target(
        session_id="session-1",
        target=runner.targets_by_id["ball_1"],
        state_history_path=tmp_path / "state_history.jsonl",
    )

    assert passed is False
    assert payload["failure_reason"] == "fetch_to_pose_ball_stopped_short"
    assert payload["fetch_ball_moved_since_fetch"] is False
    assert payload["fetch_elapsed_s"] >= 2.0
    assert payload["fetch_launch_motion_evidence_m"] == 0.03
    assert payload["fetch_max_commanded_linear_x_mps"] == 0.08
    assert payload["fetch_max_target_speed_scale"] == 0.35
    launch_commands = [item for item in command_log if item["enabled"] and item["mode"] == "object_fetch_to_pose_launch"]
    assert len(launch_commands) >= 4
    rows = [
        json.loads(line)
        for line in (tmp_path / "state_history.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(row["fetch_to_pose"]["elapsed_s"] >= 1.5 for row in rows)
    assert all(row["fetch_to_pose"]["ball_moved_since_fetch"] is False for row in rows)


def test_nav2_corridor_push_dispatch_uses_live_monitor_payload(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = gather_runner.NAV2_FOLLOW_PATH_CORRIDOR_PUSH_CONTROL_FAMILY
    runner.fetch_delivery_radius_m = 0.25
    target = runner.targets_by_id["ball_1"]
    robot_pose = {"x": 0.45, "y": 0.0, "yaw": 0.0}
    ball_pose = {"x": 1.0, "y": 0.0, "z": 0.05}
    captured_dispatch: dict[str, object] = {}
    command_log: list[dict[str, object]] = []

    monkeypatch.setattr(
        runner,
        "_control_loop_state",
        lambda session_id, target: (
            {"compose_project": "chasecar_dashboard_contact_ready"},
            robot_pose,
            ball_pose,
        ),
    )
    monkeypatch.setattr(runner, "_update_prior_from_ball_pose", lambda target_id, ball_pose: None)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **updates: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **updates: None)
    monkeypatch.setattr(
        runner,
        "_set_manual_drive",
        lambda enabled, linear_x=0.0, angular_z=0.0, mode="idle", rationale="": command_log.append(
            {"enabled": enabled, "mode": mode, "rationale": rationale}
        ),
    )

    def fake_dispatch(**kwargs):
        captured_dispatch.update(kwargs)
        return {
            "dispatch_status": "monitor_ball_escape",
            "accepted": True,
            "success": False,
            "timed_out": False,
            "cancel_requested": True,
            "monitor_cancel_reason": "ball_escape",
            "monitor_sample": {"lateral_error_m": 0.62},
        }

    monkeypatch.setattr(runner, "_dispatch_nav2_follow_path_reacquire", fake_dispatch)

    passed, payload = runner._fetch_to_pose_target(
        session_id="session-nav2-corridor-monitor",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
    )

    monitor = captured_dispatch["monitor"]
    assert passed is False
    assert payload["failure_reason"] == "nav2_corridor_push_ball_escape"
    assert captured_dispatch["compose_project"] == "chasecar_dashboard_contact_ready"
    assert monitor["enabled"] is True
    assert monitor["target_model_name"] == "visit_mission_target_ball_1"
    assert monitor["truth_state_path"].endswith(
        "/artifacts/session/session-nav2-corridor-monitor/visual/truth_state.json"
    )
    assert monitor["delivery_radius_m"] == 0.25
    assert payload["nav2_follow_path_corridor_push"]["monitor_cancel_live"] is True
    assert payload["nav2_follow_path_corridor_push"]["monitor_cancel_reason"] == "ball_escape"
    assert any(item["mode"] == "nav2_follow_path_corridor_push" for item in command_log)


def test_nav2_corridor_push_monitor_success_observes_delivery_pass(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = gather_runner.NAV2_FOLLOW_PATH_CORRIDOR_PUSH_CONTROL_FAMILY
    runner.fetch_delivery_radius_m = 0.25
    target = runner.targets_by_id["ball_1"]
    robot_pose = {"x": 0.45, "y": 0.0, "yaw": 0.0}
    ball_samples = [
        {"x": 1.0, "y": 0.0, "z": 0.05},
        {"x": float(runner.zone.world_x), "y": float(runner.zone.world_y), "z": 0.05},
    ]

    def fake_control_loop_state(session_id, target):
        index = 0 if len(ball_samples) > 1 else 0
        ball_pose = ball_samples.pop(index) if len(ball_samples) > 1 else ball_samples[0]
        return {}, robot_pose, ball_pose

    monkeypatch.setattr(runner, "_control_loop_state", fake_control_loop_state)
    monkeypatch.setattr(runner, "_update_prior_from_ball_pose", lambda target_id, ball_pose: None)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **updates: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **updates: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_dispatch_nav2_follow_path_reacquire",
        lambda **kwargs: {
            "dispatch_status": "monitor_success",
            "accepted": True,
            "success": True,
            "timed_out": False,
            "cancel_requested": True,
            "monitor_cancel_reason": "success",
            "monitor_sample": {"delivery_distance_m": 0.0},
        },
    )

    passed, payload = runner._fetch_to_pose_target(
        session_id="session-nav2-corridor-success",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
    )

    assert passed is True
    assert payload["failure_reason"] == ""
    assert payload["settle_exit_reason"] == "trajectory_intersects_delivery_radius"
    assert payload["nav2_follow_path_corridor_push"]["dispatch_status"] == "monitor_success"
    assert payload["nav2_follow_path_corridor_push"]["monitor_cancel_reason"] == "success"


def test_ai_push_coast_corridor_push_uses_bounded_push_through(tmp_path, monkeypatch):
    runner = _make_runner(tmp_path, monkeypatch)
    runner.gather_control_family = gather_runner.AI_PUSH_COAST_SERVO_CONTROL_FAMILY
    runner.ai_push_coast_mode = gather_runner.AI_PUSH_COAST_MODE_SHADOW
    runner.fetch_delivery_radius_m = 0.25
    target = runner.targets_by_id["ball_1"]
    robot_pose = {"x": 0.45, "y": 0.0, "yaw": 0.0}
    ball_samples = [
        {"x": 1.0, "y": 0.0, "z": 0.05},
        {"x": float(runner.zone.world_x), "y": float(runner.zone.world_y), "z": 0.05},
    ]
    captured_build: dict[str, object] = {}

    def fake_control_loop_state(session_id, target):
        ball_pose = ball_samples.pop(0) if len(ball_samples) > 1 else ball_samples[0]
        return {}, robot_pose, ball_pose

    class FakePlan:
        def to_dict(self):
            return {
                "active": True,
                "reason": "follow_path_corridor_push",
                "controller_id": "FollowPath",
                "goal_checker_id": "general_goal_checker",
                "path_poses": [
                    {"kind": "start", "frame_id": "odom", "x": 0.45, "y": 0.0, "yaw": 0.0},
                    {"kind": "corridor_push_through", "frame_id": "odom", "x": 1.25, "y": 0.0, "yaw": 0.0},
                ],
                "trigger": {"push_through_m": gather_runner.DEFAULT_AI_PUSH_COAST_CORRIDOR_PUSH_THROUGH_M},
            }

    def fake_build_plan(robot_pose_arg, ball_pose_arg, delivery_pose_arg, **kwargs):
        captured_build.update(kwargs)
        return FakePlan()

    monkeypatch.setattr(runner, "_control_loop_state", fake_control_loop_state)
    monkeypatch.setattr(runner, "_update_prior_from_ball_pose", lambda target_id, ball_pose: None)
    monkeypatch.setattr(runner, "_update_gather_runtime_state", lambda **updates: None)
    monkeypatch.setattr(runner, "_update_visit_runtime_state", lambda **updates: None)
    monkeypatch.setattr(runner, "_set_manual_drive", lambda *args, **kwargs: None)
    monkeypatch.setattr(gather_runner, "build_nav2_follow_path_corridor_push_plan", fake_build_plan)
    monkeypatch.setattr(
        runner,
        "_dispatch_nav2_follow_path_reacquire",
        lambda **kwargs: {
            "dispatch_status": "monitor_success",
            "accepted": True,
            "success": True,
            "timed_out": False,
            "cancel_requested": True,
            "monitor_cancel_reason": "success",
            "monitor_sample": {"delivery_distance_m": 0.0},
        },
    )

    passed, payload = runner._fetch_to_pose_target(
        session_id="session-ai-corridor-push-cap",
        target=target,
        state_history_path=tmp_path / "state_history.jsonl",
    )

    assert passed is True
    assert captured_build["push_through_m"] == gather_runner.DEFAULT_AI_PUSH_COAST_CORRIDOR_PUSH_THROUGH_M
    assert payload["nav2_follow_path_corridor_push"]["dispatch_status"] == "monitor_success"


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


def test_object_centric_capture_target_waits_for_secure_capture_instead_of_soft_handoff(tmp_path, monkeypatch):
    args = _make_args(tmp_path)
    args.gather_control_family = "object_centric_gather_policy_v1"
    args.capture_timeout_s = 2.0
    args.poll_s = 0.25
    monkeypatch.setattr(gather_runner, "choose_docker_cli", lambda: "docker")
    runner = gather_runner.GatherMissionRunner(args)
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
        {"x": 0.33, "y": 0.0, "z": 0.05},
        {"x": 0.33, "y": 0.0, "z": 0.05},
        {"x": 0.28, "y": 0.0, "z": 0.05},
    ]

    def _control_loop_state(**kwargs):
        index = min(int(clock["now"] / runner.args.poll_s), len(ball_states) - 1)
        return {}, robot_pose, ball_states[index]

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
    assert payload["handoff_kind"] == "secure_capture"
    assert payload.get("soft_capture_handoff", False) is False
    assert payload["capture_state"]["ball_x_m"] <= 0.30
    assert any(item["mode"] in {"object_capture_seat", "object_capture_finish_seat"} for item in command_log)
    assert command_log[-1]["mode"] == "captured"


def test_object_centric_capture_target_holds_zone_entry_after_place_loss_recapture(tmp_path, monkeypatch):
    args = _make_args(tmp_path)
    args.gather_control_family = "object_centric_gather_policy_v1"
    args.capture_timeout_s = 2.0
    args.poll_s = 0.25
    monkeypatch.setattr(gather_runner, "choose_docker_cli", lambda: "docker")
    runner = gather_runner.GatherMissionRunner(args)
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

    robot_pose = {"x": 3.579527, "y": 0.00103, "yaw": -3.11493}
    ball_pose = {"x": 2.388145, "y": 0.028296, "z": 0.05}

    def _control_loop_state(**kwargs):
        return {}, robot_pose, ball_pose

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
    assert any(item["mode"] == "object_capture_zone_entry_hold" for item in command_log)
    assert all(item["mode"] != "object_capture_push" for item in command_log)
    assert command_log[-1]["mode"] == "capture_handoff"


def test_object_centric_capture_target_blocks_secure_handoff_while_close_yaw_settles(tmp_path, monkeypatch):
    args = _make_args(tmp_path)
    args.gather_control_family = "object_centric_gather_policy_v1"
    args.capture_timeout_s = 0.6
    args.poll_s = 0.25
    monkeypatch.setattr(gather_runner, "choose_docker_cli", lambda: "docker")
    runner = gather_runner.GatherMissionRunner(args)
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

    robot_pose = {"x": 5.731545, "y": -0.079249, "yaw": 2.811904}
    ball_pose = {"x": 5.448, "y": 0.0, "z": 0.05}

    def _control_loop_state(**kwargs):
        return {}, robot_pose, ball_pose

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
    assert payload["capture_state"]["captured"] is True
    assert payload["capture_diagnostics"]["secure_capture_ready"] is False
    assert payload["capture_diagnostics"]["selected_command_mode"] == "object_capture_close_yaw_settle"
    assert any(item["mode"] == "object_capture_close_yaw_settle" for item in command_log)
    assert all(item["mode"] != "captured" for item in command_log)


def test_object_centric_capture_target_recenters_wide_place_loss_recapture(tmp_path, monkeypatch):
    args = _make_args(tmp_path)
    args.gather_control_family = "object_centric_gather_policy_v1"
    args.capture_timeout_s = 0.6
    args.poll_s = 0.25
    monkeypatch.setattr(gather_runner, "choose_docker_cli", lambda: "docker")
    runner = gather_runner.GatherMissionRunner(args)
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

    robot_pose = {"x": 4.992832, "y": 0.150434, "yaw": -2.845231}
    ball_pose = {"x": 4.486433, "y": 0.416483, "z": 0.05}

    def _control_loop_state(**kwargs):
        return {}, robot_pose, ball_pose

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
        attempt_kind="place_loss_recapture",
    )

    assert passed is False
    assert payload["failure_reason"] == "capture_timeout"
    assert payload["capture_state"]["within_recapture_window"] is False
    assert payload["capture_diagnostics"]["selected_command_mode"] == "object_capture_lateral_recenter"
    recenter_commands = [item for item in command_log if item["mode"] == "object_capture_lateral_recenter"]
    assert recenter_commands
    assert all(float(item["linear_x"]) == 0.0 for item in recenter_commands)
    assert min(float(item["angular_z"]) for item in recenter_commands) < -0.45
    assert all(item["mode"] != "object_capture_push" for item in command_log)


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
