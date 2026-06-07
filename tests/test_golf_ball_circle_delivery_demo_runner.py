import sys
import json
import math
import inspect
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from golf_ball_circle_delivery_demo_runner import build_shot_outcome  # noqa: E402
from golf_ball_circle_delivery_demo_runner import ball_motion_from_shot_outcome  # noqa: E402
from golf_ball_circle_delivery_demo_runner import ball_samples_from_contact_samples  # noqa: E402
from golf_ball_circle_delivery_demo_runner import build_ai_push_coast_terminal_decision  # noqa: E402
from golf_ball_circle_delivery_demo_runner import build_approach_contact_metrics  # noqa: E402
from golf_ball_circle_delivery_demo_runner import line_servo_command  # noqa: E402
from golf_ball_circle_delivery_demo_runner import parse_args  # noqa: E402
from golf_ball_circle_delivery_demo_runner import apply_target_layout  # noqa: E402
from golf_ball_circle_delivery_demo_runner import apply_planner_route_execution_defaults  # noqa: E402
from golf_ball_circle_delivery_demo_runner import build_nav2_reposition_setup_pose  # noqa: E402
from golf_ball_circle_delivery_demo_runner import build_nav2_relative_setup_goal  # noqa: E402
from golf_ball_circle_delivery_demo_runner import nav2_field_clamped_setup_goal  # noqa: E402
from golf_ball_circle_delivery_demo_runner import local_setup_nav2_setup_pose_admissibility  # noqa: E402
from golf_ball_circle_delivery_demo_runner import docker_exec_service  # noqa: E402
from golf_ball_circle_delivery_demo_runner import ensure_base_controller_active  # noqa: E402
from golf_ball_circle_delivery_demo_runner import dispatch_nav2_reposition_before_fetch  # noqa: E402
from golf_ball_circle_delivery_demo_runner import NAV2_REPOSITION_BEHAVIOR_TREE  # noqa: E402
from golf_ball_circle_delivery_demo_runner import parse_nav2_reposition_result  # noqa: E402
from golf_ball_circle_delivery_demo_runner import nav2_reposition_measured_goal_validation  # noqa: E402
from golf_ball_circle_delivery_demo_runner import apply_nav2_measured_goal_validation  # noqa: E402
from golf_ball_circle_delivery_demo_runner import apply_local_setup_nav2_coarse_acceptance  # noqa: E402
from golf_ball_circle_delivery_demo_runner import summarize_line_servo_effective_command  # noqa: E402
from golf_ball_circle_delivery_demo_runner import transform_nav2_reposition_layout_to_current_robot  # noqa: E402
from golf_ball_circle_delivery_demo_runner import nav2_precontact_fallback_to_local_recovery_decision  # noqa: E402
from golf_ball_circle_delivery_demo_runner import nav2_precontact_refinement_to_local_recovery_decision  # noqa: E402
from golf_ball_circle_delivery_demo_runner import _post_nav2_setup_is_push_ready  # noqa: E402
from golf_ball_circle_delivery_demo_runner import apply_nav2_precontact_fallback_route_defaults  # noqa: E402
from golf_ball_circle_delivery_demo_runner import measured_push_ready_handoff_from_approach_metrics  # noqa: E402
from golf_ball_circle_delivery_demo_runner import measured_push_ready_handoff_from_setup_samples  # noqa: E402
from golf_ball_circle_delivery_demo_runner import setup_owner_route_label_for_planner_route  # noqa: E402
from golf_ball_circle_delivery_demo_runner import extend_contact_samples  # noqa: E402
from golf_ball_circle_delivery_demo_runner import set_model_pose  # noqa: E402
import passive_ball_roll_calibration_runner as passive_runner  # noqa: E402


def test_shot_outcome_uses_segment_intersection_for_delivery_circle():
    samples = [
        {"t_s": 0.0, "position": {"x": 0.20, "y": 0.0, "z": 0.021336}},
        {"t_s": 0.5, "position": {"x": 1.20, "y": 0.0, "z": 0.021336}},
    ]

    outcome = build_shot_outcome(samples, target_x=0.95, target_y=0.0, target_z=0.001, radius_m=0.30)

    assert outcome["pass"] is True
    assert outcome["closest_approach_distance_m"] == pytest.approx(0.0)
    assert outcome["fetch_pose_world"] == {"x": 0.95, "y": 0.0, "z": 0.001, "radius_m": 0.3}


def test_ball_motion_from_shot_outcome_measures_start_to_end_motion():
    outcome = {
        "ball_start_pose": {"x": 0.20, "y": 0.0},
        "ball_end_pose": {"x": 0.50, "y": 0.4},
    }

    assert ball_motion_from_shot_outcome(outcome) == pytest.approx(0.5)


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


def test_parse_args_accepts_ai_push_coast_guarded_live(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "golf_ball_circle_delivery_demo_runner.py",
            "--ai-push-coast-mode",
            "guarded_live",
            "--terminal-correction-extra-margin-m",
            "0.05",
        ],
    )

    args = parse_args()

    assert args.ai_push_coast_mode == "guarded_live"
    assert args.terminal_correction_extra_margin_m == pytest.approx(0.05)


def test_parse_args_accepts_persistent_scene_fetch_flags(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "golf_ball_circle_delivery_demo_runner.py",
            "--use-existing-target-model",
            "--preserve-robot-pose",
            "--pre-fetch-setup-correction-s",
            "14.0",
        ],
    )

    args = parse_args()

    assert args.use_existing_target_model is True
    assert args.preserve_robot_pose is True
    assert args.pre_fetch_setup_correction_s == pytest.approx(14.0)


def test_extend_contact_samples_preserves_one_timeline():
    existing = [{"sample_index": 0, "t_s": 0.0, "phase_a": True}]
    added = extend_contact_samples(
        existing,
        [{"sample_index": 0, "t_s": 0.0}, {"sample_index": 1, "t_s": 0.1}],
        phase_key="phase_b",
        poll_period_s=0.1,
    )

    assert added == [
        {"sample_index": 1, "t_s": 0.1, "phase_b": True},
        {"sample_index": 2, "t_s": 0.2, "phase_b": True},
    ]
    assert existing[-1]["sample_index"] == 2


def test_ai_push_coast_terminal_decision_accepts_clean_near_contract_miss():
    args = SimpleNamespace(
        zone_x=1.12,
        zone_y=0.0,
        zone_z=0.001,
        fetch_delivery_radius_m=0.30,
        nav2_reposition_before_fetch=True,
        first_contact_motion_threshold_m=0.005,
        ai_push_coast_mode="guarded_live",
    )
    contact_samples = [
        {
            "sample_index": 0,
            "t_s": 0.0,
            "robot_pose": {"position": {"x": 0.30, "y": 0.0, "z": 0.0}, "yaw": 0.0},
            "ball_pose": {"position": {"x": 0.50, "y": 0.0, "z": 0.021336}, "yaw": 0.0},
        },
        {
            "sample_index": 1,
            "t_s": 0.4,
            "robot_pose": {"position": {"x": 0.45, "y": 0.0, "z": 0.0}, "yaw": 0.0},
            "ball_pose": {"position": {"x": 0.50, "y": 0.0, "z": 0.021336}, "yaw": 0.0},
        },
        {
            "sample_index": 2,
            "t_s": 0.8,
            "robot_pose": {"position": {"x": 0.54, "y": 0.0, "z": 0.0}, "yaw": 0.0},
            "ball_pose": {"position": {"x": 0.54, "y": 0.0, "z": 0.021336}, "yaw": 0.0},
        },
        {
            "sample_index": 3,
            "t_s": 1.2,
            "robot_pose": {"position": {"x": 0.66, "y": 0.0, "z": 0.0}, "yaw": 0.0},
            "ball_pose": {"position": {"x": 0.72, "y": 0.0, "z": 0.021336}, "yaw": 0.0},
        },
    ]
    shot = build_shot_outcome(
        ball_samples_from_contact_samples(contact_samples),
        target_x=args.zone_x,
        target_y=args.zone_y,
        target_z=args.zone_z,
        radius_m=args.fetch_delivery_radius_m,
    )
    approach = build_approach_contact_metrics(
        contact_samples,
        ball_start_x=0.50,
        ball_start_y=0.0,
        target_x=args.zone_x,
        target_y=args.zone_y,
    )

    decision = build_ai_push_coast_terminal_decision(
        args=args,
        contact_samples=contact_samples,
        shot_outcome=shot,
        approach_metrics=approach,
        pre_fetch_reposition={"attempted": True, "dispatch_status": "goal_finished", "success": True},
    )

    assert decision["ai_push_coast_proposal"]["maneuver_class"] == "terminal_repush"
    assert decision["ai_push_coast_guard"]["accepted"] is True


def test_docker_exec_service_returns_timeout_result(monkeypatch):
    def fake_run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["docker", "compose"], timeout=10.0, output="partial-out", stderr="partial-err")

    monkeypatch.setattr(subprocess, "run", fake_run)

    rc, output = docker_exec_service("project", "gate-stack", "ros2 topic pub", timeout_s=10.0)

    assert rc == 124
    assert "partial-out" in output
    assert "partial-err" in output
    assert "timeout_after_s=10.000" in output


def test_set_model_pose_accepts_timeout_after_success(monkeypatch):
    import golf_ball_circle_delivery_demo_runner as runner

    monkeypatch.setattr(runner, "docker_exec", lambda *_args, **_kwargs: (124, "data: true\n\ntimeout_after_s=10.000"))

    result = set_model_pose(
        compose_project="project",
        world_name="world",
        model_name="jetbot",
        x=0.0,
        y=0.0,
        z=0.0,
        yaw=0.0,
    )

    assert result["pass"] is True
    assert result["returncode"] == 124
    assert result["timed_out_after_success"] is True


def test_ensure_base_controller_active_accepts_existing_active_controller(monkeypatch):
    import golf_ball_circle_delivery_demo_runner as runner

    calls = []

    def fake_exec(compose_project, service, script, *, timeout_s):
        calls.append((compose_project, service, script, timeout_s))
        return 0, "jetbot_base_controller diff_drive_controller/DiffDriveController active\nBASE_CONTROLLER_ACTIVE=1\n"

    monkeypatch.setattr(runner, "docker_exec_service", fake_exec)

    result = ensure_base_controller_active(compose_project="project", timeout_s=2.0)

    assert result["pass"] is True
    assert result["repaired"] is False
    assert result["returncode"] == 0
    assert calls[0][0] == "project"
    assert calls[0][1] == "sim-gate"
    assert "/controller_manager/list_controllers" in calls[0][2]


def test_ensure_base_controller_active_records_repair_success(monkeypatch):
    import golf_ball_circle_delivery_demo_runner as runner

    def fake_exec(*_args, **_kwargs):
        return 0, "Could not contact service\nLoaded jetbot_base_controller\nConfigured and activated\nBASE_CONTROLLER_ACTIVE=1\n"

    monkeypatch.setattr(runner, "docker_exec_service", fake_exec)

    result = ensure_base_controller_active(compose_project="project")

    assert result["pass"] is True
    assert result["repaired"] is True
    assert "Configured and activated" in result["output_tail"]


def test_ensure_base_controller_active_final_relist_after_repair_window(monkeypatch):
    import golf_ball_circle_delivery_demo_runner as runner

    calls = []

    def fake_exec(compose_project, service, script, *, timeout_s):
        calls.append((compose_project, service, script, timeout_s))
        return (
            0,
            "ListControllers_Response(controller=[])\n"
            "Configured and activated jetbot_base_controller\n"
            "ListControllers_Response(controller=[ControllerState(name='jetbot_base_controller', state='active')])\n"
            "BASE_CONTROLLER_ACTIVE=1\n",
        )

    monkeypatch.setattr(runner, "docker_exec_service", fake_exec)

    result = ensure_base_controller_active(compose_project="project", timeout_s=1.0)

    assert result["pass"] is True
    assert result["repaired"] is True
    script = calls[0][2]
    final_check = script.split("done", maxsplit=1)[1]
    assert "/controller_manager/list_controllers" in final_check
    assert "BASE_CONTROLLER_ACTIVE=0" in final_check


def test_ensure_base_controller_active_fails_closed_when_unavailable(monkeypatch):
    import golf_ball_circle_delivery_demo_runner as runner

    monkeypatch.setattr(runner, "docker_exec_service", lambda *_args, **_kwargs: (2, "BASE_CONTROLLER_ACTIVE=0"))

    result = ensure_base_controller_active(compose_project="project", timeout_s=1.0)

    assert result["pass"] is False
    assert result["returncode"] == 2


def test_passive_docker_exec_returns_timeout_result(monkeypatch):
    def fake_run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["docker", "compose"], timeout=20.0, output="remove-out", stderr="remove-err")

    monkeypatch.setattr(passive_runner.subprocess, "run", fake_run)

    rc, output = passive_runner.docker_exec("project", "gz service remove", timeout_s=20.0)

    assert rc == 124
    assert "remove-out" in output
    assert "remove-err" in output
    assert "timeout_after_s=20.000" in output


def test_apply_target_layout_sets_ball_pose_from_layout(tmp_path):
    layout_path = tmp_path / "layout.json"
    layout_path.write_text(
        json.dumps(
            {
                "layout_family": "bounded_random_golf_ball_circle_delivery",
                "random_profile": "local_visual_v1",
                "planner_route_label": "nav2_reposition_first",
                "route_executor": "nav2_forward_reposition_then_fetch",
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
    assert layout["planner_route_label"] == "nav2_reposition_first"
    assert layout["route_executor"] == "nav2_forward_reposition_then_fetch"


def _route_default_args(**overrides):
    values = {
        "planner_route_label": "",
        "route_executor": "",
        "forward_only_pre_contact_required": False,
        "drive_mode": "constant",
        "drive_linear_x_mps": 0.12,
        "drive_duration_s": 7.0,
        "sample_duration_s": 9.0,
        "line_servo_push_linear_x_mps": 0.055,
        "line_servo_min_linear_x_mps": 0.025,
        "line_servo_max_angular_z_rps": 0.18,
        "line_servo_yaw_gain": 1.2,
        "line_servo_contact_lateral_ready_m": 0.035,
        "line_servo_contact_yaw_ready_deg": 5.729578,
        "stop_on_delivery": False,
        "delivery_stop_radius_m": 0.0,
        "post_delivery_sample_s": 0.0,
        "nav2_reposition_before_fetch": False,
        "nav2_reposition_transform_layout_to_current_robot": False,
        "nav2_reposition_frame_id": "odom",
        "nav2_reposition_goal_frame_mode": "nav2_relative",
        "nav2_reposition_setup_standoff_m": 0.38,
        "nav2_pre_setup_standoff_m": 0.0,
        "nav2_reposition_refine_attempts": 0,
        "nav2_reposition_timeout_s": 24.0,
        "nav2_reposition_server_wait_s": 8.0,
        "nav2_reposition_pose_wait_s": 3.0,
        "nav2_reposition_continue_on_failure": False,
        "disable_nav2_precontact_fallback": False,
        "robot_x": 0.06,
        "robot_y": 0.0,
        "robot_yaw": 0.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_planner_route_defaults_turn_frozen_fetch_layout_into_line_servo():
    args = _route_default_args()
    layout = {
        "planner_route_label": "fetch_ready_local",
        "route_executor": "local_fetch_to_pose",
        "random_draw": {
            "planner_route_label": "fetch_ready_local",
            "robot_pose": {"x": -0.109148, "y": -0.035637, "yaw": 0.253126},
        },
    }

    defaults = apply_planner_route_execution_defaults(args, layout, explicit_args=set())

    assert defaults["applied"] is True
    assert args.planner_route_label == "fetch_ready_local"
    assert args.route_executor == "local_fetch_to_pose"
    assert args.forward_only_pre_contact_required is True
    assert args.drive_mode == "line_servo"
    assert args.drive_linear_x_mps == pytest.approx(0.10)
    assert args.drive_duration_s == pytest.approx(70.0)
    assert args.sample_duration_s == pytest.approx(74.0)
    assert args.stop_on_delivery is True
    assert args.delivery_stop_radius_m == pytest.approx(0.20)
    assert args.post_delivery_sample_s == pytest.approx(4.0)
    assert args.line_servo_min_linear_x_mps == pytest.approx(0.012)
    assert args.line_servo_contact_lateral_ready_m == pytest.approx(0.028)
    assert args.line_servo_contact_yaw_ready_deg == pytest.approx(3.0)
    assert defaults["line_servo_quality_defaults"]["pre_contact_smoothing_requested"] is False
    assert args.nav2_reposition_before_fetch is False
    assert args.robot_x == pytest.approx(-0.109148)
    assert args.robot_y == pytest.approx(-0.035637)
    assert args.robot_yaw == pytest.approx(0.253126)


def test_planner_route_defaults_tighten_fetch_ready_contact_for_smoothing_watch():
    args = _route_default_args()
    layout = {
        "planner_route_label": "fetch_ready_local",
        "route_executor": "local_fetch_to_pose",
        "random_draw": {
            "planner_route_label": "fetch_ready_local",
            "robot_pose": {"x": -0.058007, "y": 0.004356, "yaw": 0.090413},
            "route_quality": {
                "predicted_contact_quality": "watch",
                "flags": ["initial_lateral_setup_debt"],
                "recommendations": ["local_line_servo_contact", "pre_contact_smoothing"],
            },
        },
    }

    defaults = apply_planner_route_execution_defaults(args, layout, explicit_args=set())

    assert defaults["applied"] is True
    assert args.line_servo_contact_lateral_ready_m == pytest.approx(0.024)
    assert defaults["line_servo_quality_defaults"]["contact_lateral_ready_m"] == pytest.approx(0.024)
    assert defaults["line_servo_quality_defaults"]["pre_contact_smoothing_requested"] is True


def test_planner_route_defaults_enable_nav2_setup_for_frozen_reposition_layout():
    args = _route_default_args()
    layout = {
        "planner_route_label": "nav2_reposition_first",
        "route_executor": "nav2_forward_reposition_then_fetch",
        "random_draw": {"planner_route_label": "nav2_reposition_first"},
    }

    defaults = apply_planner_route_execution_defaults(args, layout, explicit_args=set())

    assert defaults["applied"] is True
    assert args.drive_mode == "line_servo"
    assert args.nav2_reposition_before_fetch is True
    assert args.nav2_reposition_transform_layout_to_current_robot is True
    assert args.nav2_reposition_goal_frame_mode == "nav2_relative"
    assert args.nav2_reposition_setup_standoff_m == pytest.approx(0.38)
    assert args.drive_duration_s == pytest.approx(74.0)
    assert args.sample_duration_s == pytest.approx(78.0)
    assert args.robot_x == pytest.approx(0.0)
    assert args.robot_y == pytest.approx(0.0)
    assert args.robot_yaw == pytest.approx(0.0)


def test_planner_route_defaults_downgrade_near_field_nav2_layout_to_recovery():
    args = _route_default_args()
    layout = {
        "planner_route_label": "nav2_reposition_first",
        "route_executor": "nav2_forward_reposition_then_fetch",
        "random_draw": {
            "planner_route_label": "nav2_reposition_first",
            "route_executor": "nav2_forward_reposition_then_fetch",
            "ball_target_distance_m": 0.680424,
            "robot_ball_distance_m": 0.846004,
            "robot_lateral_error_m": 0.100922,
            "robot_yaw_error_deg": -4.807588,
            "robot_pose": {"x": -0.533879, "y": -0.346212, "yaw": 0.211588},
        },
    }

    defaults = apply_planner_route_execution_defaults(args, layout, explicit_args=set())

    assert defaults["applied"] is True
    assert defaults["planner_route_requested_label"] == "nav2_reposition_first"
    assert defaults["planner_route_label"] == "recovery_or_reaim"
    assert defaults["route_executor"] == "bounded_recovery_reaim"
    assert defaults["route_admissibility"]["changed"] is True
    assert args.planner_route_label == "recovery_or_reaim"
    assert args.route_executor == "bounded_recovery_reaim"
    assert args.nav2_reposition_before_fetch is False
    assert args.nav2_reposition_transform_layout_to_current_robot is False
    assert args.drive_duration_s == pytest.approx(148.0)
    assert args.sample_duration_s == pytest.approx(152.0)
    assert args.robot_x == pytest.approx(-0.533879)
    assert args.robot_y == pytest.approx(-0.346212)
    assert args.robot_yaw == pytest.approx(0.211588)


def test_planner_route_defaults_downgrade_quality_blocked_near_field_nav2_layout_to_recovery():
    args = _route_default_args(nav2_reposition_before_fetch=True, nav2_reposition_transform_layout_to_current_robot=True)
    layout = {
        "planner_route_label": "nav2_reposition_first",
        "route_executor": "nav2_forward_reposition_then_fetch",
        "random_draw": {
            "planner_route_label": "nav2_reposition_first",
            "route_executor": "nav2_forward_reposition_then_fetch",
            "ball_target_distance_m": 0.633705,
            "robot_ball_distance_m": 0.883985,
            "robot_lateral_error_m": 0.077212,
            "robot_yaw_error_deg": -147.72473,
            "robot_pose": {"x": 0.745385, "y": 0.158287, "yaw": -0.398204},
            "route_quality": {
                "flags": [
                    "nav2_reposition_near_field_not_admissible",
                    "nav2_reposition_required",
                    "opposite_side_of_circle",
                ],
                "predicted_contact_quality": "blocker",
                "predicted_first_contact_quality": "blocker",
            },
        },
    }

    defaults = apply_planner_route_execution_defaults(
        args,
        layout,
        explicit_args={"--nav2-reposition-before-fetch", "--nav2-reposition-transform-layout-to-current-robot"},
    )

    assert defaults["applied"] is True
    assert defaults["planner_route_requested_label"] == "nav2_reposition_first"
    assert defaults["planner_route_label"] == "recovery_or_reaim"
    assert defaults["route_admissibility"]["changed"] is True
    assert defaults["route_admissibility"]["reason"] == "route_quality_blocked_near_field_prefers_bounded_recovery_reaim"
    assert args.nav2_reposition_before_fetch is False
    assert args.nav2_reposition_transform_layout_to_current_robot is False
    assert args.robot_x == pytest.approx(0.745385)
    assert args.robot_y == pytest.approx(0.158287)
    assert args.robot_yaw == pytest.approx(-0.398204)


def test_planner_route_defaults_give_local_setup_capture_measured_setup_budget():
    args = _route_default_args()
    layout = {
        "planner_route_label": "local_setup_capture",
        "route_executor": "measured_local_setup_capture",
        "random_draw": {
            "planner_route_label": "local_setup_capture",
            "route_executor": "measured_local_setup_capture",
            "robot_pose": {"x": 1.580776, "y": 0.898054, "yaw": -2.647472},
        },
    }

    defaults = apply_planner_route_execution_defaults(args, layout, explicit_args=set())

    assert defaults["applied"] is True
    assert args.planner_route_label == "local_setup_capture"
    assert args.route_executor == "measured_local_setup_capture"
    assert args.drive_duration_s == pytest.approx(238.0)
    assert args.sample_duration_s == pytest.approx(242.0)
    assert defaults["nav2_setup_assist_requested"] is False
    assert args.nav2_reposition_before_fetch is False


def test_planner_route_defaults_enable_nav2_setup_assist_for_wide_local_setup_debt():
    args = _route_default_args()
    layout = {
        "planner_route_label": "local_setup_capture",
        "route_executor": "measured_local_setup_capture",
        "random_draw": {
            "planner_route_label": "local_setup_capture",
            "route_executor": "measured_local_setup_capture",
            "robot_pose": {"x": 0.759475, "y": -0.205184, "yaw": 0.822426},
            "route_quality": {
                "flags": ["local_setup_capture_required", "wide_lateral_setup_debt", "wide_yaw_setup_debt"],
                "setup_debt": {
                    "lateral_m": 0.242012,
                    "yaw_deg": 73.280844,
                    "robot_ball_distance_m": 0.678441,
                },
            },
        },
    }

    defaults = apply_planner_route_execution_defaults(args, layout, explicit_args=set())

    assert defaults["applied"] is True
    assert defaults["planner_route_label"] == "local_setup_capture"
    assert defaults["route_executor"] == "measured_local_setup_capture"
    assert defaults["nav2_setup_assist_requested"] is True
    assert args.nav2_reposition_before_fetch is True
    assert args.nav2_reposition_transform_layout_to_current_robot is True
    assert args.nav2_reposition_goal_frame_mode == "nav2_relative"
    assert args.nav2_reposition_setup_standoff_m == pytest.approx(0.65)
    assert args.nav2_reposition_timeout_s == pytest.approx(48.0)
    assert args.nav2_pre_setup_standoff_m == pytest.approx(0.90)
    assert args.nav2_reposition_refine_attempts == 0


def test_nav2_precontact_fallback_accepts_clean_abort_inside_local_envelope():
    args = _route_default_args(
        planner_route_label="nav2_reposition_first",
        route_executor="nav2_forward_reposition_then_fetch",
        ball_x=0.38,
        ball_y=0.0,
        zone_x=0.95,
        zone_y=0.0,
    )
    samples = [
        {
            "robot_pose": {"x": -0.64, "y": 0.08, "yaw": 0.0, "z": 0.0},
            "ball_pose": {"x": 0.38, "y": 0.0, "yaw": 0.0, "z": 0.021336},
        }
    ]

    decision = nav2_precontact_fallback_to_local_recovery_decision(
        args=args,
        target_layout={},
        pre_fetch_reposition={"success": False, "status_text": "STATUS_ABORTED"},
        pre_fetch_reposition_samples=samples,
    )

    assert decision["eligible"] is True
    assert decision["reason"] == "pre_contact_nav2_failure_inside_local_recovery_envelope"
    assert decision["fallback_route_label"] == "recovery_or_reaim"
    assert decision["geometry"]["source"] == "post_nav2_pose_sample"
    assert decision["geometry"]["robot_ball_distance_m"] == pytest.approx(1.023132)
    assert decision["ball_motion_m"] == pytest.approx(0.0)


def test_nav2_precontact_fallback_accepts_seed20260629_clean_abort_boundary():
    args = _route_default_args(
        planner_route_label="nav2_reposition_first",
        route_executor="nav2_forward_reposition_then_fetch",
        ball_x=1.220412,
        ball_y=-0.069372,
        zone_x=1.691683,
        zone_y=-0.076119,
    )
    samples = [
        {
            "robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0, "z": 0.0},
            "ball_pose": {"x": 1.220412, "y": -0.069372, "yaw": 0.0, "z": 0.021336},
        }
    ]

    decision = nav2_precontact_fallback_to_local_recovery_decision(
        args=args,
        target_layout={},
        pre_fetch_reposition={"success": False, "status_text": "STATUS_ABORTED"},
        pre_fetch_reposition_samples=samples,
    )

    assert decision["eligible"] is True
    assert decision["reason"] == "pre_contact_nav2_failure_inside_local_recovery_envelope"
    assert decision["fallback_route_label"] == "recovery_or_reaim"
    assert decision["geometry"]["robot_ball_distance_m"] == pytest.approx(1.222382)
    assert decision["thresholds"]["robot_ball_distance_limit_m"] == pytest.approx(1.3)
    assert decision["ball_motion_m"] == pytest.approx(0.0)


def test_nav2_precontact_fallback_accepts_wide_setup_after_timeout_without_ball_motion():
    args = _route_default_args(
        planner_route_label="nav2_reposition_first",
        route_executor="nav2_forward_reposition_then_fetch",
        ball_x=0.0,
        ball_y=0.0,
        zone_x=0.76,
        zone_y=0.0,
    )
    samples = [
        {
            "robot_pose": {"x": -0.6, "y": 1.0, "yaw": math.radians(150.0), "z": 0.0},
            "ball_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0, "z": 0.021336},
        }
    ]

    decision = nav2_precontact_fallback_to_local_recovery_decision(
        args=args,
        target_layout={},
        pre_fetch_reposition={"success": False, "status_text": "goal_result_timeout"},
        pre_fetch_reposition_samples=samples,
    )

    assert decision["eligible"] is True
    assert decision["reason"] == "pre_contact_nav2_failure_inside_wide_setup_fallback_envelope"
    assert decision["local_recovery_admissible"] is False
    assert decision["wide_setup_admissible"] is True
    assert decision["fallback_route_label"] == "local_setup_capture"
    assert decision["fallback_route_executor"] == "measured_local_setup_capture"
    assert decision["geometry"]["robot_lateral_error_m"] == pytest.approx(1.0)
    assert decision["geometry"]["robot_yaw_error_deg"] == pytest.approx(150.0)


def test_nav2_precontact_fallback_accepts_observed_scene02_wide_lateral_setup_mismatch():
    args = _route_default_args(
        planner_route_label="nav2_reposition_first",
        route_executor="nav2_forward_reposition_then_fetch",
        ball_x=0.12877,
        ball_y=-0.011075,
        zone_x=0.95,
        zone_y=0.0,
    )
    samples = [
        {
            "robot_pose": {"x": 0.369758, "y": -1.705235, "yaw": 0.900226, "z": 0.0},
            "ball_pose": {"x": 0.12877, "y": -0.011075, "yaw": 0.0, "z": 0.021336},
        }
    ]

    decision = nav2_precontact_fallback_to_local_recovery_decision(
        args=args,
        target_layout={},
        pre_fetch_reposition={"success": False, "status_text": "goal_succeeded_measured_pose_mismatch"},
        pre_fetch_reposition_samples=samples,
    )

    assert decision["eligible"] is True
    assert decision["reason"] == "pre_contact_nav2_failure_inside_wide_setup_fallback_envelope"
    assert decision["local_recovery_admissible"] is False
    assert decision["wide_setup_admissible"] is True
    assert decision["fallback_route_label"] == "local_setup_capture"
    assert decision["fallback_route_executor"] == "measured_local_setup_capture"
    assert decision["geometry"]["robot_lateral_error_m"] > 1.6


def test_nav2_success_refinement_accepts_dirty_post_nav2_setup():
    args = _route_default_args(
        planner_route_label="nav2_reposition_first",
        route_executor="nav2_forward_reposition_then_fetch",
        ball_x=0.0,
        ball_y=0.0,
        zone_x=0.62,
        zone_y=0.0,
    )
    samples = [
        {
            "robot_pose": {"x": -0.33, "y": 0.06, "yaw": math.radians(-28.0), "z": 0.0},
            "ball_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0, "z": 0.021336},
        }
    ]

    decision = nav2_precontact_refinement_to_local_recovery_decision(
        args=args,
        target_layout={},
        pre_fetch_reposition={"success": True, "status_text": "goal_succeeded"},
        pre_fetch_reposition_samples=samples,
    )

    assert decision["eligible"] is True
    assert decision["reason"] == "nav2_success_needs_local_recovery_refinement"
    assert decision["push_ready"] is False
    assert decision["local_recovery_admissible"] is True
    assert decision["geometry"]["robot_lateral_error_m"] == pytest.approx(0.06)
    assert decision["geometry"]["robot_yaw_error_deg"] == pytest.approx(28.0)


def test_local_setup_capture_uses_nav2_success_refinement_for_dirty_setup():
    args = _route_default_args(
        planner_route_label="local_setup_capture",
        route_executor="measured_local_setup_capture",
        ball_x=0.0,
        ball_y=0.0,
        zone_x=0.62,
        zone_y=0.0,
    )
    samples = [
        {
            "robot_pose": {"x": -0.33, "y": 0.06, "yaw": math.radians(-28.0), "z": 0.0},
            "ball_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0, "z": 0.021336},
        }
    ]

    decision = nav2_precontact_refinement_to_local_recovery_decision(
        args=args,
        target_layout={},
        pre_fetch_reposition={"success": True, "status_text": "goal_succeeded_local_setup_coarse_accept"},
        pre_fetch_reposition_samples=samples,
    )

    assert decision["eligible"] is True
    assert decision["reason"] == "nav2_success_needs_local_recovery_refinement"
    assert decision["requested_route_label"] == "local_setup_capture"


def test_local_setup_capture_keeps_front_side_nav2_success_in_wide_refinement():
    args = _route_default_args(
        planner_route_label="local_setup_capture",
        route_executor="measured_local_setup_capture",
        ball_x=1.328716,
        ball_y=-0.574301,
        zone_x=0.95,
        zone_y=0.0,
    )
    samples = [
        {
            "robot_pose": {"x": 1.09287, "y": -0.355073, "yaw": 2.074985, "z": 0.0},
            "ball_pose": {"x": 1.328716, "y": -0.574301, "yaw": 0.0, "z": 0.021336},
        }
    ]

    decision = nav2_precontact_refinement_to_local_recovery_decision(
        args=args,
        target_layout={},
        pre_fetch_reposition={"success": True, "status_text": "goal_succeeded_local_setup_coarse_accept"},
        pre_fetch_reposition_samples=samples,
    )

    assert decision["eligible"] is True
    assert decision["reason"] == "nav2_success_needs_wide_setup_refinement"
    assert decision["local_recovery_admissible"] is False
    assert decision["wide_setup_admissible"] is True
    assert decision["geometry"]["robot_longitudinal_projection_m"] > 0.0


def test_post_nav2_setup_requires_behind_ball_projection_for_push_ready():
    front_side_geometry = {
        "available": True,
        "robot_ball_distance_m": 0.32,
        "robot_longitudinal_projection_m": 0.31,
        "robot_lateral_error_m": 0.01,
        "robot_yaw_error_deg": 1.0,
    }
    behind_geometry = dict(front_side_geometry)
    behind_geometry["robot_longitudinal_projection_m"] = -0.31

    assert _post_nav2_setup_is_push_ready(front_side_geometry) is False
    assert _post_nav2_setup_is_push_ready(behind_geometry) is True


def test_nav2_precontact_fallback_route_defaults_use_measured_local_setup_for_wide_setup():
    args = _route_default_args(
        planner_route_label="nav2_reposition_first",
        route_executor="nav2_forward_reposition_then_fetch",
        drive_duration_s=74.0,
        sample_duration_s=78.0,
    )

    applied = apply_nav2_precontact_fallback_route_defaults(
        args,
        set(),
        {
            "fallback_route_label": "local_setup_capture",
            "fallback_route_executor": "measured_local_setup_capture",
        },
    )

    assert applied["route_label"] == "local_setup_capture"
    assert applied["route_executor"] == "measured_local_setup_capture"
    assert args.planner_route_label == "local_setup_capture"
    assert args.route_executor == "measured_local_setup_capture"
    assert args.drive_duration_s == pytest.approx(238.0)
    assert args.sample_duration_s == pytest.approx(242.0)


def test_nav2_precontact_fallback_rejects_ball_motion_before_handoff():
    args = _route_default_args(
        planner_route_label="nav2_reposition_first",
        route_executor="nav2_forward_reposition_then_fetch",
        ball_x=0.38,
        ball_y=0.0,
        zone_x=0.95,
        zone_y=0.0,
    )
    samples = [
        {
            "robot_pose": {"x": -0.64, "y": 0.08, "yaw": 0.0, "z": 0.0},
            "ball_pose": {"x": 0.43, "y": 0.0, "yaw": 0.0, "z": 0.021336},
        }
    ]

    decision = nav2_precontact_fallback_to_local_recovery_decision(
        args=args,
        target_layout={},
        pre_fetch_reposition={"success": False, "status_text": "STATUS_ABORTED"},
        pre_fetch_reposition_samples=samples,
    )

    assert decision["eligible"] is False
    assert decision["reason"] == "nav2_moved_ball_before_fallback"
    assert decision["ball_motion_m"] == pytest.approx(0.05)


def test_measured_push_ready_handoff_requires_terminal_ready_and_first_contact_quality():
    handoff = measured_push_ready_handoff_from_approach_metrics(
        {
            "terminal_pre_contact_contact_ready_gated": True,
            "first_contact_quality_pass": True,
            "first_contact_t_s": 2.5,
            "terminal_pre_contact_sample_count": 8,
            "terminal_pre_contact_quality_sample_count": 3,
        },
        local_fetch_dispatched=True,
        planner_route_label="nav2_reposition_first",
    )

    assert handoff["required"] is True
    assert handoff["pass"] is True
    assert handoff["terminal_pre_contact_contact_ready_gated"] is True
    assert handoff["first_contact_quality_pass"] is True


def test_measured_push_ready_handoff_blocks_fetch_without_terminal_gate():
    handoff = measured_push_ready_handoff_from_approach_metrics(
        {
            "terminal_pre_contact_contact_ready_gated": False,
            "first_contact_quality_pass": True,
        },
        local_fetch_dispatched=True,
        planner_route_label="recovery_or_reaim",
    )

    assert handoff["required"] is True
    assert handoff["pass"] is False


def test_measured_push_ready_handoff_not_required_for_no_go_route():
    handoff = measured_push_ready_handoff_from_approach_metrics(
        {},
        local_fetch_dispatched=False,
        planner_route_label="ambiguous_or_unsafe_no_go",
    )

    assert handoff["required"] is False
    assert handoff["pass"] is True


def test_measured_setup_handoff_accepts_contact_ready_without_ball_motion():
    handoff = measured_push_ready_handoff_from_setup_samples(
        [
            {
                "line_servo_command": {
                    "phase": "first_contact_align",
                    "contact_ready": True,
                    "ball_moved": False,
                    "distance_to_contact_m": 0.028,
                    "robot_lateral_error_m": 0.012,
                    "line_yaw_error_rad": 0.02,
                },
                "setup_contact_ready_triggered": True,
            }
        ],
        planner_route_label="local_setup_capture",
    )

    assert handoff["required"] is True
    assert handoff["pass"] is True
    assert handoff["setup_contact_ready"] is True
    assert handoff["setup_ball_motion_before_ready"] is False
    assert handoff["ready_robot_yaw_error_deg"] == pytest.approx(1.145916)


def test_measured_setup_handoff_is_required_for_recovery_reaim_route():
    handoff = measured_push_ready_handoff_from_setup_samples(
        [
            {
                "line_servo_command": {
                    "phase": "recovery_line_acquire",
                    "contact_ready": True,
                    "ball_moved": False,
                    "distance_to_contact_m": 0.20,
                    "robot_lateral_error_m": 0.010,
                    "line_yaw_error_rad": -0.03,
                },
                "setup_contact_ready_triggered": True,
            }
        ],
        planner_route_label="recovery_or_reaim",
    )

    assert handoff["required"] is True
    assert handoff["pass"] is True
    assert handoff["setup_contact_ready"] is True
    assert handoff["setup_ball_motion_before_ready"] is False


def test_measured_setup_handoff_blocks_recovery_without_contact_ready():
    handoff = measured_push_ready_handoff_from_setup_samples(
        [
            {
                "line_servo_command": {
                    "phase": "recovery_contact_yaw_hold",
                    "contact_ready": False,
                    "ball_moved": False,
                    "distance_to_contact_m": 0.18,
                    "robot_lateral_error_m": 0.012,
                    "line_yaw_error_rad": 0.12,
                },
            }
        ],
        planner_route_label="recovery_or_reaim",
    )

    assert handoff["required"] is True
    assert handoff["pass"] is False
    assert handoff["setup_contact_ready"] is False
    assert handoff["reasons"] == ["contact_ready_not_observed"]


def test_setup_owner_route_label_uses_local_setup_for_recovery():
    assert setup_owner_route_label_for_planner_route("recovery_or_reaim") == "local_setup_capture"
    assert setup_owner_route_label_for_planner_route("local_setup_capture") == "local_setup_capture"
    assert setup_owner_route_label_for_planner_route("fetch_ready_local") == "fetch_ready_local"


def test_measured_setup_handoff_blocks_ball_motion_before_ready():
    handoff = measured_push_ready_handoff_from_setup_samples(
        [
            {
                "line_servo_command": {
                    "phase": "push_coast_realign",
                    "contact_ready": False,
                    "ball_moved": True,
                    "distance_to_contact_m": 0.22,
                    "robot_lateral_error_m": 0.16,
                    "line_yaw_error_rad": 2.8,
                },
                "setup_ball_motion_triggered": True,
            }
        ],
        planner_route_label="local_setup_capture",
    )

    assert handoff["required"] is True
    assert handoff["pass"] is False
    assert handoff["setup_contact_ready"] is False
    assert handoff["setup_ball_motion_before_ready"] is True
    assert handoff["reasons"] == ["contact_ready_not_observed", "ball_moved_before_push_ready"]


def test_planner_route_defaults_extend_recovery_execution_window_without_nav2_setup():
    args = _route_default_args()
    layout = {
        "planner_route_label": "recovery_or_reaim",
        "route_executor": "bounded_recovery_reaim",
        "random_draw": {"planner_route_label": "recovery_or_reaim"},
    }

    defaults = apply_planner_route_execution_defaults(args, layout, explicit_args=set())

    assert defaults["applied"] is True
    assert args.nav2_reposition_before_fetch is False
    assert args.drive_duration_s == pytest.approx(148.0)
    assert args.sample_duration_s == pytest.approx(152.0)
    assert args.line_servo_contact_lateral_ready_m == pytest.approx(0.030)
    assert defaults["line_servo_quality_defaults"]["contact_lateral_ready_m"] == pytest.approx(0.030)


def test_planner_route_defaults_preserve_explicit_cli_overrides():
    args = _route_default_args(drive_mode="constant", drive_duration_s=5.0, stop_on_delivery=False, robot_x=0.25)
    layout = {
        "planner_route_label": "fetch_ready_local",
        "route_executor": "local_fetch_to_pose",
        "random_draw": {"robot_pose": {"x": -0.1, "y": 0.1, "yaw": 0.2}},
    }

    apply_planner_route_execution_defaults(
        args,
        layout,
        explicit_args={"--drive-mode", "--drive-duration-s", "--stop-on-delivery", "--robot-x"},
    )

    assert args.drive_mode == "constant"
    assert args.drive_duration_s == pytest.approx(5.0)
    assert args.stop_on_delivery is False
    assert args.sample_duration_s == pytest.approx(74.0)
    assert args.robot_x == pytest.approx(0.25)
    assert args.robot_y == pytest.approx(0.1)
    assert args.robot_yaw == pytest.approx(0.2)


def test_planner_route_defaults_preserve_equals_style_cli_overrides():
    args = _route_default_args(drive_duration_s=5.0)
    layout = {
        "planner_route_label": "fetch_ready_local",
        "route_executor": "local_fetch_to_pose",
        "random_draw": {"robot_pose": {"x": -0.1, "y": 0.1, "yaw": 0.2}},
    }

    apply_planner_route_execution_defaults(args, layout, explicit_args={"--drive-duration-s=5.0"})

    assert args.drive_duration_s == pytest.approx(5.0)
    assert args.sample_duration_s == pytest.approx(74.0)


def test_parse_args_accepts_planner_route_metadata(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "golf_ball_circle_delivery_demo_runner.py",
            "--planner-route-label",
            "nav2_reposition_first",
            "--route-executor",
            "nav2_forward_reposition_then_fetch",
            "--forward-only-pre-contact-required",
            "--stop-on-delivery",
            "--delivery-stop-radius-m",
            "0.20",
            "--post-delivery-sample-s",
            "4.0",
            "--drive-mode",
            "line_servo",
            "--line-servo-push-linear-x-mps",
            "0.05",
            "--line-servo-max-angular-z-rps",
            "0.16",
            "--line-servo-yaw-gain",
            "1.4",
        ],
    )

    args = parse_args()

    assert args.planner_route_label == "nav2_reposition_first"
    assert args.route_executor == "nav2_forward_reposition_then_fetch"
    assert args.forward_only_pre_contact_required is True
    assert args.stop_on_delivery is True
    assert args.delivery_stop_radius_m == pytest.approx(0.20)
    assert args.post_delivery_sample_s == pytest.approx(4.0)
    assert args.drive_mode == "line_servo"
    assert args.line_servo_push_linear_x_mps == pytest.approx(0.05)
    assert args.line_servo_max_angular_z_rps == pytest.approx(0.16)
    assert args.line_servo_yaw_gain == pytest.approx(1.4)
    assert args.line_servo_min_linear_x_mps == pytest.approx(0.025)
    assert args.line_servo_contact_lateral_ready_m == pytest.approx(0.035)
    assert args.line_servo_contact_yaw_ready_deg == pytest.approx(5.729578)


def test_parse_args_accepts_planner_route_only_proof(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "golf_ball_circle_delivery_demo_runner.py",
            "--planner-route-label",
            "ambiguous_or_unsafe_no_go",
            "--route-executor",
            "safe_no_go",
            "--planner-route-only-proof",
            "--drive-linear-x-mps",
            "0",
            "--sample-duration-s",
            "5",
        ],
    )

    args = parse_args()

    assert args.planner_route_label == "ambiguous_or_unsafe_no_go"
    assert args.route_executor == "safe_no_go"
    assert args.planner_route_only_proof is True
    assert args.drive_linear_x_mps == pytest.approx(0.0)
    assert args.sample_duration_s == pytest.approx(5.0)


def test_parse_args_accepts_nav2_reposition_before_fetch(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "golf_ball_circle_delivery_demo_runner.py",
            "--planner-route-label",
            "nav2_reposition_first",
            "--nav2-reposition-before-fetch",
            "--nav2-reposition-frame-id",
            "odom",
            "--nav2-reposition-goal-frame-mode",
            "nav2_relative",
            "--nav2-reposition-transform-layout-to-current-robot",
            "--nav2-reposition-setup-standoff-m",
            "0.42",
            "--nav2-pre-setup-standoff-m",
            "0.9",
            "--nav2-reposition-timeout-s",
            "19.0",
            "--nav2-reposition-server-wait-s",
            "4.0",
            "--nav2-reposition-pose-wait-s",
            "2.5",
            "--nav2-reposition-continue-on-failure",
        ],
    )

    args = parse_args()

    assert args.nav2_reposition_before_fetch is True
    assert args.nav2_reposition_frame_id == "odom"
    assert args.nav2_reposition_goal_frame_mode == "nav2_relative"
    assert args.nav2_reposition_transform_layout_to_current_robot is True
    assert args.nav2_reposition_setup_standoff_m == pytest.approx(0.42)
    assert args.nav2_pre_setup_standoff_m == pytest.approx(0.9)
    assert args.nav2_reposition_timeout_s == pytest.approx(19.0)
    assert args.nav2_reposition_server_wait_s == pytest.approx(4.0)
    assert args.nav2_reposition_pose_wait_s == pytest.approx(2.5)
    assert args.nav2_reposition_continue_on_failure is True


def test_build_nav2_reposition_setup_pose_uses_ball_target_line():
    pose = build_nav2_reposition_setup_pose(
        ball_x=0.4457,
        ball_y=0.212988,
        target_x=0.95,
        target_y=0.0,
        setup_standoff_m=0.38,
        frame_id="odom",
    )

    line_yaw = math.atan2(0.0 - 0.212988, 0.95 - 0.4457)
    assert pose["frame_id"] == "odom"
    assert pose["yaw"] == pytest.approx(line_yaw, abs=1.0e-6)
    assert pose["line_yaw_rad"] == pytest.approx(line_yaw, abs=1.0e-6)
    assert pose["x"] == pytest.approx(0.4457 - math.cos(line_yaw) * 0.38, abs=1.0e-6)
    assert pose["y"] == pytest.approx(0.212988 - math.sin(line_yaw) * 0.38, abs=1.0e-6)
    assert pose["setup_standoff_m"] == pytest.approx(0.38)
    assert pose["requested_setup_standoff_m"] == pytest.approx(0.38)
    assert pose["field_bounded"] is False
    assert pose["source"] == "ball_target_line_setup_pose"
    assert pose["orientation"]["w"] == pytest.approx(math.cos(line_yaw * 0.5), abs=1.0e-6)


def test_build_nav2_reposition_setup_pose_shortens_edge_setup_to_field_bounds():
    pose = build_nav2_reposition_setup_pose(
        ball_x=1.656822,
        ball_y=-0.351905,
        target_x=0.95,
        target_y=0.0,
        setup_standoff_m=0.9,
        frame_id="odom",
    )

    line_yaw = math.atan2(0.0 - (-0.351905), 0.95 - 1.656822)
    assert pose["field_bounded"] is True
    assert pose["source"] == "ball_target_line_setup_pose_field_bounded"
    assert pose["requested_setup_standoff_m"] == pytest.approx(0.9)
    assert pose["setup_standoff_m"] < 0.9
    assert pose["setup_standoff_m"] > 0.38
    assert pose["yaw"] == pytest.approx(line_yaw, abs=1.0e-6)
    assert pose["x"] <= 2.15
    assert pose["y"] >= -1.30
    assert pose["y"] <= 1.30


def test_local_setup_nav2_admissibility_allows_field_bounded_far_pre_setup():
    pose = build_nav2_reposition_setup_pose(
        ball_x=1.328716,
        ball_y=-0.574301,
        target_x=0.95,
        target_y=0.0,
        setup_standoff_m=0.9,
        frame_id="odom",
    )

    decision = local_setup_nav2_setup_pose_admissibility(
        planner_route_label="local_setup_capture",
        setup_pose=pose,
        stage="nav2_pre_setup",
    )

    assert decision["pass"] is True
    assert decision["reason"] == "nav2_field_bounded_pre_setup_admissible"
    assert decision["field_bounded"] is True
    assert decision["setup_pose"]["source"] == "ball_target_line_setup_pose_field_bounded"
    assert decision["setup_standoff_m"] >= decision["field_bounded_pre_setup_min_standoff_m"]


def test_local_setup_nav2_admissibility_rejects_field_bounded_close_setup():
    pose = {
        "x": 2.15,
        "y": -1.30,
        "yaw": 0.0,
        "field_bounded": True,
        "setup_standoff_m": 0.25,
        "source": "ball_target_line_setup_pose_field_bounded",
    }

    decision = local_setup_nav2_setup_pose_admissibility(
        planner_route_label="local_setup_capture",
        setup_pose=pose,
        stage="nav2_setup",
    )

    assert decision["pass"] is False
    assert decision["reason"] == "nav2_setup_field_bounded_not_nav2_admissible"
    assert decision["field_bounded"] is True
    assert decision["setup_standoff_m"] == pytest.approx(0.25)


def test_local_setup_nav2_admissibility_allows_unbounded_setup_and_other_routes():
    pose = build_nav2_reposition_setup_pose(
        ball_x=0.4457,
        ball_y=0.212988,
        target_x=0.95,
        target_y=0.0,
        setup_standoff_m=0.38,
        frame_id="odom",
    )

    local_decision = local_setup_nav2_setup_pose_admissibility(
        planner_route_label="local_setup_capture",
        setup_pose=pose,
        stage="nav2_setup",
    )
    nav2_decision = local_setup_nav2_setup_pose_admissibility(
        planner_route_label="nav2_reposition_first",
        setup_pose={**pose, "field_bounded": True},
        stage="nav2_setup",
    )

    assert local_decision["pass"] is True
    assert local_decision["reason"] == "nav2_setup_pose_admissible"
    assert nav2_decision["pass"] is True


def test_build_nav2_relative_setup_goal_preserves_truth_delta_in_nav2_frame():
    world_setup_pose = {
        "frame_id": "odom",
        "x": 0.09564,
        "y": 0.360834,
        "yaw": -0.399619,
        "line_yaw_rad": -0.399619,
    }
    world_robot_pose = {"x": -0.389734, "y": 0.662437, "yaw": -0.572531}
    nav2_robot_pose = {"x": 0.0, "y": 0.0, "yaw": 1.73}

    goal = build_nav2_relative_setup_goal(
        world_setup_pose=world_setup_pose,
        world_robot_pose=world_robot_pose,
        nav2_robot_pose=nav2_robot_pose,
        frame_id="odom",
    )

    assert goal["source"] == "nav2_relative_from_truth_delta"
    assert goal["x"] == pytest.approx(0.09564 - (-0.389734), abs=1.0e-6)
    assert goal["y"] == pytest.approx(0.360834 - 0.662437, abs=1.0e-6)
    assert goal["yaw"] == pytest.approx(1.73 + (-0.399619 - (-0.572531)), abs=1.0e-6)
    assert goal["world_setup_pose"] == world_setup_pose
    assert goal["world_robot_pose"] == world_robot_pose
    assert goal["nav2_robot_pose"] == nav2_robot_pose


def test_nav2_field_clamped_setup_goal_preserves_local_setup_relative_goal():
    goal = nav2_field_clamped_setup_goal(
        {
            "frame_id": "odom",
            "x": 2.482023,
            "y": -1.44,
            "yaw": -1.033222,
            "source": "nav2_relative_from_truth_delta",
        },
        planner_route_label="local_setup_capture",
    )

    assert goal["x"] == pytest.approx(2.482023)
    assert goal["y"] == pytest.approx(-1.44)
    assert "field_bounded" not in goal
    assert goal["source"] == "nav2_relative_from_truth_delta"


def test_transform_nav2_reposition_layout_to_current_robot_preserves_scene_geometry():
    args = SimpleNamespace(
        robot_x=0.0,
        robot_y=0.0,
        robot_yaw=0.0,
        ball_x=0.4457,
        ball_y=0.212988,
        ball_z=0.021336,
        zone_x=0.95,
        zone_y=0.0,
        zone_z=0.001,
        fetch_delivery_radius_m=0.3,
    )
    layout = {
        "random_draw": {
            "robot_pose": {"x": -0.389734, "y": 0.662437, "yaw": -0.572531, "z": 0.0},
            "ball_pose": {"x": 0.4457, "y": 0.212988, "yaw": 0.0, "z": 0.021336},
            "target_pose": {"x": 0.95, "y": 0.0, "z": 0.001, "radius_m": 0.3},
        }
    }

    transform = transform_nav2_reposition_layout_to_current_robot(args, layout)

    assert transform["applied"] is True
    scene_robot = layout["random_draw"]["robot_pose"]
    scene_ball = layout["random_draw"]["ball_pose"]
    scene_target = layout["random_draw"]["target_pose"]
    original_robot_ball = math.hypot(scene_ball["x"] - scene_robot["x"], scene_ball["y"] - scene_robot["y"])
    original_ball_target = math.hypot(scene_target["x"] - scene_ball["x"], scene_target["y"] - scene_ball["y"])
    transformed_robot_ball = math.hypot(args.ball_x - args.robot_x, args.ball_y - args.robot_y)
    transformed_ball_target = math.hypot(args.zone_x - args.ball_x, args.zone_y - args.ball_y)
    assert transformed_robot_ball == pytest.approx(original_robot_ball, abs=1.0e-6)
    assert transformed_ball_target == pytest.approx(original_ball_target, abs=1.0e-6)
    assert transform["target_robot_pose"] == {"x": 0.0, "y": 0.0, "yaw": 0.0}
    assert transform["transformed_ball_pose"]["x"] == pytest.approx(args.ball_x)
    assert transform["transformed_target_pose"]["x"] == pytest.approx(args.zone_x)


def test_parse_nav2_reposition_result_extracts_marker_payload():
    output = "\n".join(
        [
            "noise",
            'NAV2_REPOSITION_RESULT={"accepted":true,"dispatch_status":"goal_succeeded","success":true,"status_code":4}',
        ]
    )

    result = parse_nav2_reposition_result(output, rc=0)

    assert result["success"] is True
    assert result["accepted"] is True
    assert result["dispatch_status"] == "goal_succeeded"
    assert result["status_text"] == "STATUS_SUCCEEDED"
    assert result["process_returncode"] == 0


def test_nav2_measured_goal_validation_accepts_close_measured_pose():
    validation = nav2_reposition_measured_goal_validation(
        goal_pose={"x": 0.50, "y": -0.10, "yaw": 0.20},
        post_reposition_robot_pose={"position": {"x": 0.56, "y": -0.14, "z": 0.0}, "yaw": 0.28},
    )

    assert validation["pass"] is True
    assert validation["reason"] == "measured_goal_reached"
    assert validation["position_error_m"] < 0.25
    assert validation["yaw_error_deg"] < 25.0


def test_apply_nav2_measured_goal_validation_fail_closes_action_success_pose_mismatch():
    reposition = {
        "success": True,
        "dispatch_status": "goal_succeeded",
        "post_reposition_robot_pose": {
            "position": {"x": 0.361856, "y": -1.706868, "z": 0.0},
            "yaw": 0.872545,
        },
    }

    apply_nav2_measured_goal_validation(
        reposition,
        {"x": -0.251195, "y": -0.016199, "yaw": 0.013485},
    )

    assert reposition["action_success"] is True
    assert reposition["success"] is False
    assert reposition["dispatch_status"] == "goal_succeeded_measured_pose_mismatch"
    assert reposition["measured_goal_validation"]["reason"] == "measured_goal_pose_mismatch"
    assert reposition["measured_goal_validation"]["position_error_m"] > 1.0


def test_local_setup_nav2_coarse_accepts_ball_stable_local_envelope():
    args = SimpleNamespace(
        planner_route_label="local_setup_capture",
        zone_x=0.95,
        zone_y=0.0,
    )
    target_layout = {"random_draw": {"ball_pose": {"x": 1.20, "y": 0.60}}}
    reposition = {
        "success": False,
        "action_success": True,
        "post_reposition_robot_pose": {
            "position": {"x": 1.52, "y": 0.72, "z": 0.0},
            "yaw": -2.0,
        },
        "post_reposition_ball_pose": {
            "position": {"x": 1.20, "y": 0.60, "z": 0.021336},
            "yaw": 0.0,
        },
    }

    acceptance = apply_local_setup_nav2_coarse_acceptance(
        args=args,
        target_layout=target_layout,
        pre_fetch_reposition=reposition,
    )

    assert acceptance["applied"] is True
    assert acceptance["accepted"] is True
    assert acceptance["ball_motion_m"] == pytest.approx(0.0)
    assert acceptance["geometry"]["robot_ball_distance_m"] < 3.0


def test_local_setup_nav2_coarse_rejects_ball_motion():
    args = SimpleNamespace(
        planner_route_label="local_setup_capture",
        zone_x=0.95,
        zone_y=0.0,
    )
    target_layout = {"random_draw": {"ball_pose": {"x": 1.20, "y": 0.60}}}
    reposition = {
        "success": True,
        "post_reposition_robot_pose": {
            "position": {"x": 1.52, "y": 0.72, "z": 0.0},
            "yaw": -2.0,
        },
        "post_reposition_ball_pose": {
            "position": {"x": 1.25, "y": 0.65, "z": 0.021336},
            "yaw": 0.0,
        },
    }

    acceptance = apply_local_setup_nav2_coarse_acceptance(
        args=args,
        target_layout=target_layout,
        pre_fetch_reposition=reposition,
    )

    assert acceptance["accepted"] is False
    assert "ball_moved_during_nav2_setup" in acceptance["reasons"]


def test_local_setup_nav2_coarse_rejects_backward_yaw_setup():
    args = SimpleNamespace(
        planner_route_label="local_setup_capture",
        zone_x=0.95,
        zone_y=0.0,
    )
    target_layout = {"random_draw": {"ball_pose": {"x": 1.328716, "y": -0.574301}}}
    reposition = {
        "success": False,
        "action_success": True,
        "post_reposition_robot_pose": {
            "position": {"x": 0.7485822483870924, "y": -0.2935629190560496, "z": 0.0},
            "yaw": -1.192535915024442,
        },
        "post_reposition_ball_pose": {
            "position": {"x": 1.328716, "y": -0.574301, "z": 0.021336},
            "yaw": 0.0,
        },
    }

    acceptance = apply_local_setup_nav2_coarse_acceptance(
        args=args,
        target_layout=target_layout,
        pre_fetch_reposition=reposition,
    )

    assert acceptance["accepted"] is False
    assert "yaw_error_outside_local_setup_envelope" in acceptance["reasons"]
    assert acceptance["geometry"]["robot_yaw_error_deg"] > 165.0


def test_nav2_reposition_client_uses_repo_bt_and_ros_status_compatible_rejection():
    source = inspect.getsource(dispatch_nav2_reposition_before_fetch)

    assert NAV2_REPOSITION_BEHAVIOR_TREE.endswith("/ros2_config/behavior_trees/navigate_to_pose_w_replanning.xml")
    assert "\"behavior_tree\": NAV2_REPOSITION_BEHAVIOR_TREE" in source
    assert "goal.behavior_tree = str(payload.get(\"behavior_tree\") or \"\")" in source
    assert "STATUS_REJECTED" in source
    assert "GoalStatus.STATUS_REJECTED" not in source


def test_line_servo_command_stays_forward_only_and_reduces_setup_error():
    command = line_servo_command(
        robot_pose={"x": -0.389734, "y": 0.662437, "yaw": -0.572531},
        ball_pose={"x": 0.4457, "y": 0.212988, "yaw": 0.0},
        target_x=1.18108,
        target_y=-0.221366,
        ball_start_pose={"x": 0.4457, "y": 0.212988, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
    )

    assert command["phase"] == "setup_converge"
    assert command["linear_x_mps"] > 0.0
    assert command["angular_z_rps"] > 0.0
    assert abs(command["angular_z_rps"]) <= 0.18


def test_line_servo_command_slows_after_ball_motion():
    command = line_servo_command(
        robot_pose={"x": 0.30, "y": 0.16, "yaw": -0.36},
        ball_pose={"x": 0.50, "y": 0.18, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 0.4457, "y": 0.212988, "yaw": 0.0},
        motion_threshold_m=0.005,
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
    )

    assert command["phase"] == "push_coast_realign"
    assert command["ball_moved"] is True
    assert command["linear_x_mps"] <= 0.055


def test_line_servo_command_reaims_close_offset_contact_before_push():
    command = line_servo_command(
        robot_pose={"x": 0.199536, "y": -0.083082, "yaw": 0.068093},
        ball_pose={"x": 0.375666, "y": -0.131166, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 0.375666, "y": -0.131166, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
    )

    assert command["phase"] == "contact_final_reaim"
    assert command["contact_final_reaim_active"] is True
    assert command["contact_ready"] is False
    assert command["linear_x_mps"] <= 0.035
    assert command["angular_z_rps"] < 0.0
    assert command["robot_lateral_error_m"] > 0.07


def test_line_servo_command_uses_deeper_setup_for_recovery_route():
    default_command = line_servo_command(
        robot_pose={"x": -0.022148, "y": -0.106481, "yaw": 0.527487},
        ball_pose={"x": 0.375666, "y": -0.131166, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 0.375666, "y": -0.131166, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
    )
    recovery_command = line_servo_command(
        robot_pose={"x": -0.022148, "y": -0.106481, "yaw": 0.527487},
        ball_pose={"x": 0.375666, "y": -0.131166, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 0.375666, "y": -0.131166, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
        route_label="recovery_or_reaim",
    )

    assert default_command["setup_standoff_m"] == pytest.approx(0.20)
    assert recovery_command["setup_standoff_m"] == pytest.approx(0.34)
    assert default_command["max_angular_z_rps"] == pytest.approx(0.18)
    assert recovery_command["max_angular_z_rps"] == pytest.approx(0.45)
    assert default_command["contact_lateral_ready_m"] == pytest.approx(0.035)
    assert recovery_command["contact_lateral_ready_m"] == pytest.approx(0.030)
    assert recovery_command["route_label"] == "recovery_or_reaim"
    assert recovery_command["phase"] == "setup_converge_yaw_hold"
    assert recovery_command["recovery_yaw_hold"] is True
    assert recovery_command["linear_x_mps"] == 0.0
    assert abs(recovery_command["angular_z_rps"]) > abs(default_command["angular_z_rps"])
    assert recovery_command["desired_yaw_rad"] < default_command["desired_yaw_rad"]


def test_line_servo_command_promotes_recovery_setup_pocket_to_line_acquire():
    command = line_servo_command(
        robot_pose={"x": 0.029869529679984037, "y": -0.004152838227441682, "yaw": -0.3078394324501684},
        ball_pose={"x": 0.446611, "y": -0.132599, "yaw": 0.0},
        target_x=1.18108,
        target_y=-0.221366,
        ball_start_pose={"x": 0.446611, "y": -0.132599, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
        route_label="recovery_or_reaim",
    )

    assert command["phase"] == "recovery_line_acquire"
    assert command["contact_ready"] is False
    assert command["distance_to_setup_m"] <= command["recovery_setup_pocket_m"]
    assert command["robot_lateral_error_m"] <= command["recovery_line_acquire_lateral_m"]
    assert command["desired_yaw_rad"] == pytest.approx(command["line_yaw_rad"], abs=1.0e-6)
    assert command["linear_x_mps"] >= 0.055
    assert command["angular_z_rps"] > 0.0


def test_line_servo_command_orbits_wrong_side_local_setup_instead_of_crossing_ball():
    command = line_servo_command(
        robot_pose={"x": 0.842, "y": 0.272, "yaw": 2.80},
        ball_pose={"x": 0.572109, "y": 0.268491, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 0.572109, "y": 0.268491, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.030,
        contact_yaw_ready_rad=math.radians(3.0),
        route_label="local_setup_capture",
    )

    assert command["phase"].startswith("recovery_orbit_setup")
    assert command["recovery_wrong_side_orbit_active"] is True
    assert command["contact_ready"] is False
    assert command["robot_longitudinal_projection_m"] > 0.0
    assert command["linear_x_mps"] <= 0.045
    assert abs(command["desired_yaw_rad"] - command["setup_yaw_rad"]) > 0.20


def test_line_servo_command_holds_linear_motion_when_close_yaw_not_ready():
    command = line_servo_command(
        robot_pose={"x": 0.507041, "y": 0.349108, "yaw": -0.740095},
        ball_pose={"x": 0.576084, "y": 0.271026, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 0.572109, "y": 0.268491, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=math.radians(3.0),
        route_label="local_setup_capture",
    )

    assert command["recovery_contact_micro_yaw_hold_active"] is True
    assert command["phase"].startswith("recovery_contact_micro_yaw_hold")
    assert command["local_setup_trajectory_stage"] == "close_yaw_align"
    assert command["local_setup_contact_risk_freeze"] is True
    assert command["contact_ready"] is False
    assert command["distance_to_contact_m"] <= 0.055
    assert command["linear_x_mps"] == 0.0
    assert command["angular_z_rps"] == 0.0


def test_line_servo_command_keeps_safe_behind_lateral_debt_in_side_setup():
    command = line_servo_command(
        robot_pose={"x": 1.4124001025450685, "y": 0.8558706226344617, "yaw": -2.73320903211721},
        ball_pose={"x": 1.2411847480885942, "y": 0.6659736545248174, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 1.2411847480885942, "y": 0.6659736545248174, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=math.radians(3.0),
        route_label="local_setup_capture",
    )

    assert command["recovery_close_misaligned_escape_active"] is False
    assert command["phase"] == "local_setup_trajectory_side_setup_yaw_lock"
    assert command["local_setup_trajectory_stage"] == "side_setup"
    assert command["local_setup_near_contact_yaw_lock"] is True
    assert command["contact_ready"] is False
    assert command["ball_moved"] is False
    assert command["robot_lateral_error_m"] > command["setup_lateral_ready_m"]
    assert command["setup_heading_toward_ball"] is False
    assert command["linear_x_mps"] == 0.0


def test_line_servo_command_does_not_creep_into_ball_when_lateral_gate_is_not_ready():
    command = line_servo_command(
        robot_pose={"x": 1.821395412721273, "y": -0.4916902683277605, "yaw": 2.33689586428015},
        ball_pose={"x": 1.656822, "y": -0.351905, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 1.656822, "y": -0.351905, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=math.radians(3.0),
        route_label="local_setup_capture",
    )

    assert command["recovery_close_misaligned_escape_active"] is True
    assert command["phase"].startswith("recovery_close_misaligned_escape")
    assert command["contact_ready"] is False
    assert command["distance_to_contact_m"] < 0.12
    assert command["robot_lateral_error_m"] > command["contact_lateral_ready_m"]
    assert command["linear_x_mps"] <= 0.018
    assert command["recovery_close_escape_heading_toward_ball"] is False


def test_local_setup_keeps_side_setup_until_lateral_debt_is_inside_setup_gate():
    command = line_servo_command(
        robot_pose={"x": 1.4336860729107566, "y": 0.9189536984262521, "yaw": -2.589925600406849},
        ball_pose={"x": 1.23928, "y": 0.670304, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 1.23928, "y": 0.670304, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=math.radians(3.0),
        route_label="local_setup_capture",
    )

    assert command["phase"] == "local_setup_trajectory_side_setup"
    assert command["local_setup_trajectory_stage"] == "side_setup"
    assert command["local_setup_trajectory_active"] is True
    assert command["recovery_contact_yaw_hold_active"] is False
    assert command["recovery_line_acquire_yaw_crawl_active"] is False
    assert command["robot_lateral_error_m"] > command["setup_lateral_ready_m"]
    assert command["desired_yaw_rad"] == pytest.approx(command["setup_yaw_rad"], abs=1.0e-6)


def test_local_setup_keeps_behind_setup_when_farther_pocket_has_projection_debt():
    command = line_servo_command(
        robot_pose={"x": 1.4001491580890113, "y": 0.9553145713583798, "yaw": -2.661138511175531},
        ball_pose={"x": 1.23928, "y": 0.670304, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 1.23928, "y": 0.670304, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=math.radians(3.0),
        route_label="local_setup_capture",
    )

    assert command["phase"] == "local_setup_trajectory_behind_setup"
    assert command["local_setup_trajectory_stage"] == "behind_setup"
    assert command["local_setup_trajectory_active"] is True
    assert command["recovery_contact_yaw_hold_active"] is False
    assert command["recovery_line_acquire_yaw_crawl_active"] is False
    assert command["robot_lateral_error_m"] > command["contact_lateral_ready_m"] * 1.05
    assert command["setup_projection_error_m"] > 0.12
    assert command["desired_yaw_rad"] == pytest.approx(command["setup_yaw_rad"], abs=1.0e-6)


def test_local_setup_trajectory_uses_behind_setup_before_farther_setup_pocket():
    command = line_servo_command(
        robot_pose={"x": 1.3971764942473286, "y": 0.9611291587929407, "yaw": -2.5311180345265054},
        ball_pose={"x": 1.23928, "y": 0.670304, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 1.23928, "y": 0.670304, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=math.radians(3.0),
        route_label="local_setup_capture",
    )

    assert command["phase"] == "local_setup_trajectory_behind_setup"
    assert command["local_setup_trajectory_stage"] == "behind_setup"
    assert command["local_setup_trajectory_active"] is True
    assert command["linear_x_mps"] > 0.0
    assert command["desired_yaw_rad"] == pytest.approx(command["setup_yaw_rad"], abs=1.0e-6)
    assert abs(command["setup_yaw_rad"] - command["line_yaw_rad"]) > 1.0
    assert command["recovery_yaw_hold"] is False
    assert command["angular_z_rps"] < 0.0


def test_local_setup_safe_side_orbit_crawls_after_moderate_yaw_alignment():
    command = line_servo_command(
        robot_pose={"x": 0.9976737159815053, "y": -0.19887268037269532, "yaw": -1.7910671969844927},
        ball_pose={"x": 1.328716, "y": -0.574301, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 1.328716, "y": -0.574301, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.030,
        contact_yaw_ready_rad=math.radians(3.0),
        route_label="local_setup_capture",
    )

    assert command["phase"] == "recovery_orbit_setup_yaw_crawl"
    assert command["local_setup_trajectory_stage"] == "safe_side_orbit"
    assert command["local_setup_safe_side_orbit_yaw_guard"] is False
    assert command["local_setup_safe_side_orbit_yaw_crawl"] is True
    assert command["recovery_wrong_side_orbit_active"] is True
    assert command["linear_x_mps"] == pytest.approx(0.018)
    assert command["angular_z_rps"] > 0.0


def test_local_setup_safe_side_orbit_holds_on_large_yaw_error():
    command = line_servo_command(
        robot_pose={"x": 0.9605262530207337, "y": -0.2223489478157923, "yaw": -2.97406935799141},
        ball_pose={"x": 1.328716, "y": -0.574301, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 1.328716, "y": -0.574301, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.030,
        contact_yaw_ready_rad=math.radians(3.0),
        route_label="local_setup_capture",
    )

    assert command["phase"] == "recovery_orbit_setup_yaw_guard"
    assert command["local_setup_safe_side_orbit_yaw_guard"] is True
    assert command["local_setup_safe_side_orbit_yaw_crawl"] is False
    assert command["linear_x_mps"] == 0.0


def test_local_setup_trajectory_uses_lateral_trim_near_push_ready_pocket():
    command = line_servo_command(
        robot_pose={"x": 1.4345020228695726, "y": 1.0217131088556357, "yaw": -2.05821474095024},
        ball_pose={"x": 1.23928, "y": 0.670304, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 1.23928, "y": 0.670304, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=math.radians(3.0),
        route_label="local_setup_capture",
    )

    assert command["phase"] == "local_setup_trajectory_lateral_trim"
    assert command["local_setup_trajectory_stage"] == "lateral_trim"
    assert command["near_contact_lateral_trim_active"] is True
    assert command["local_setup_near_contact_yaw_lock"] is False
    assert command["robot_lateral_error_m"] > command["contact_lateral_ready_m"]
    assert command["setup_projection_error_m"] == pytest.approx(0.06, abs=1.0e-6)
    assert command["linear_x_mps"] == pytest.approx(0.014)
    assert abs(command["yaw_error_rad"]) < 0.10


def test_local_setup_trajectory_keeps_line_acquire_after_near_contact_projection_drift():
    command = line_servo_command(
        robot_pose={"x": 1.8567679511167812, "y": 0.20449122152517193, "yaw": -3.0561989727966625},
        ball_pose={"x": 1.50223, "y": 0.145572, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 1.50223, "y": 0.145572, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=math.radians(3.0),
        route_label="local_setup_capture",
    )

    assert command["phase"] == "local_setup_trajectory_line_acquire"
    assert command["local_setup_trajectory_stage"] == "line_acquire"
    assert command["near_contact_line_acquire_active"] is True
    assert command["distance_to_contact_m"] == pytest.approx(0.250085, abs=1.0e-6)
    assert command["setup_projection_error_m"] == pytest.approx(0.102155, abs=1.0e-6)
    assert abs(command["line_yaw_error_rad"]) < 0.20
    assert abs(command["desired_yaw_rad"] - command["line_yaw_rad"]) < 0.25
    assert abs(command["desired_yaw_rad"] - command["setup_yaw_rad"]) > 1.0
    assert command["linear_x_mps"] > 0.0


def test_local_setup_trajectory_keeps_line_acquire_when_projection_barely_exceeds_old_gate():
    command = line_servo_command(
        robot_pose={"x": 1.8142861614059245, "y": 0.19610952050065733, "yaw": -2.8887327553627378},
        ball_pose={"x": 1.50223, "y": 0.145572, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 1.50223, "y": 0.145572, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=math.radians(3.0),
        route_label="local_setup_capture",
    )

    assert command["phase"] == "local_setup_trajectory_line_acquire"
    assert command["local_setup_trajectory_stage"] == "line_acquire"
    assert command["near_contact_line_acquire_active"] is True
    assert command["setup_projection_error_m"] == pytest.approx(0.14537, abs=1.0e-5)
    assert abs(command["line_yaw_error_rad"]) < 0.01
    assert abs(command["desired_yaw_rad"] - command["line_yaw_rad"]) < 0.25
    assert abs(command["desired_yaw_rad"] - command["setup_yaw_rad"]) > 1.0


def test_local_setup_trajectory_keeps_line_acquire_below_old_distance_floor_when_aligned():
    command = line_servo_command(
        robot_pose={"x": 1.787843317691804, "y": 0.18915883248261217, "yaw": -2.8845250563605376},
        ball_pose={"x": 1.50223, "y": 0.145572, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 1.50223, "y": 0.145572, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=math.radians(3.0),
        route_label="local_setup_capture",
    )

    assert command["phase"] == "local_setup_trajectory_line_acquire"
    assert command["local_setup_trajectory_stage"] == "line_acquire"
    assert command["near_contact_line_acquire_active"] is True
    assert command["distance_to_contact_m"] == pytest.approx(0.17992, abs=1.0e-5)
    assert command["setup_projection_error_m"] == pytest.approx(0.172711, abs=1.0e-5)
    assert abs(command["line_yaw_error_rad"]) < 0.01
    assert abs(command["desired_yaw_rad"] - command["line_yaw_rad"]) < 0.25
    assert abs(command["desired_yaw_rad"] - command["setup_yaw_rad"]) > 1.0


def test_local_setup_trajectory_uses_close_side_escape_before_side_setup_contact_risk():
    command = line_servo_command(
        robot_pose={"x": 1.7814065651092068, "y": -0.669354759879795, "yaw": 0.7453161254591563},
        ball_pose={"x": 1.656822, "y": -0.351905, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 1.656822, "y": -0.351905, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=math.radians(3.0),
        route_label="local_setup_capture",
    )

    assert command["phase"] == "recovery_close_misaligned_escape"
    assert command["local_setup_trajectory_stage"] == "close_escape"
    assert command["local_setup_trajectory_active"] is True
    assert command["local_setup_close_side_escape_active"] is True
    assert command["recovery_close_misaligned_escape_active"] is True
    assert abs(command["line_yaw_error_rad"]) > 1.0
    assert command["recovery_close_escape_pose"]
    assert command["recovery_close_escape_pose"]["x"] > 1.90
    assert 0.018 < command["linear_x_mps"] <= 0.045


def test_local_setup_trajectory_side_setup_keeps_speed_with_moderate_waypoint_yaw_error():
    command = line_servo_command(
        robot_pose={"x": 1.5179669057979532, "y": 0.9233938478588862, "yaw": 2.3880189011178707},
        ball_pose={"x": 1.23928, "y": 0.670304, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 1.23928, "y": 0.670304, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=math.radians(3.0),
        route_label="local_setup_capture",
    )

    assert command["phase"] == "local_setup_trajectory_side_setup"
    assert command["local_setup_trajectory_stage"] == "side_setup"
    assert command["robot_lateral_error_m"] > 0.15
    assert 0.25 < abs(command["yaw_error_rad"]) < 0.50
    assert command["linear_x_mps"] >= 0.070


def test_line_servo_command_allows_first_contact_when_geometry_ready():
    command = line_servo_command(
        robot_pose={"x": 0.270, "y": -0.156, "yaw": 0.2245},
        ball_pose={"x": 0.375666, "y": -0.131166, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 0.375666, "y": -0.131166, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
    )

    assert command["phase"] == "first_contact_align"
    assert command["contact_ready"] is True
    assert command["linear_x_mps"] >= 0.055


def test_line_servo_command_prioritizes_yaw_when_lateral_is_ready():
    command = line_servo_command(
        robot_pose={"x": 0.265, "y": -0.127, "yaw": 0.113},
        ball_pose={"x": 0.375666, "y": -0.131166, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 0.375666, "y": -0.131166, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
        route_label="recovery_or_reaim",
    )

    assert command["contact_ready"] is False
    assert command["robot_lateral_error_m"] < 0.030
    assert command["yaw_priority_lateral_m"] == pytest.approx(0.032)
    assert command["desired_yaw_rad"] == pytest.approx(command["line_yaw_rad"], abs=1.0e-6)
    assert command["angular_z_rps"] > 0.10


def test_line_servo_command_uses_slow_final_crawl_for_quality_tuned_contact():
    command = line_servo_command(
        robot_pose={"x": 0.264, "y": -0.125, "yaw": 0.100},
        ball_pose={"x": 0.375666, "y": -0.131166, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 0.375666, "y": -0.131166, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
    )

    assert command["phase"] == "contact_final_reaim"
    assert command["contact_final_reaim_active"] is True
    assert command["contact_ready"] is False
    assert command["linear_x_mps"] <= 0.018
    assert command["contact_lateral_ready_m"] == pytest.approx(0.028)
    assert command["contact_yaw_ready_rad"] == pytest.approx(0.05236)


def test_line_servo_command_uses_contact_final_reaim_for_fetch_ready_lateral_watch():
    command = line_servo_command(
        robot_pose={"x": 0.163824, "y": -0.000171, "yaw": -0.038539},
        ball_pose={"x": 0.266267, "y": 0.026575, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 0.266267, "y": 0.026575, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="fetch_ready_local",
    )

    assert command["phase"] == "contact_final_reaim"
    assert command["contact_final_reaim_active"] is True
    assert command["recovery_final_reaim_active"] is False
    assert command["contact_ready"] is False
    assert command["linear_x_mps"] <= 0.018
    assert command["lateral_reaim_gain"] == pytest.approx(4.5)
    assert command["lateral_reaim_rad"] < -0.10
    assert command["angular_z_rps"] > 0.10


def test_line_servo_command_crawls_close_fetch_ready_setup_debt_before_contact():
    command = line_servo_command(
        robot_pose={"x": 0.256813, "y": -0.27993, "yaw": 0.114764},
        ball_pose={"x": 0.516185, "y": -0.135987, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 0.516185, "y": -0.135987, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="fetch_ready_local",
    )

    assert command["phase"] == "local_close_settle"
    assert command["local_close_settle_active"] is True
    assert command["contact_ready"] is False
    assert command["ball_moved"] is False
    assert command["linear_x_mps"] == pytest.approx(0.012)
    assert command["angular_z_rps"] > 0.0
    assert command["desired_yaw_rad"] != pytest.approx(command["setup_yaw_rad"], abs=1.0e-6)


def test_line_servo_command_keeps_ready_fetch_local_on_first_contact_align():
    command = line_servo_command(
        robot_pose={"x": 0.294, "y": -0.193, "yaw": 0.305},
        ball_pose={"x": 0.516185, "y": -0.135987, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 0.516185, "y": -0.135987, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="fetch_ready_local",
    )

    assert command["contact_ready"] is True
    assert command["local_close_settle_active"] is False
    assert command["phase"] == "first_contact_align"
    assert command["linear_x_mps"] >= 0.055


def test_line_servo_command_releases_near_threshold_lateral_reaim_to_line_yaw():
    command = line_servo_command(
        robot_pose={"x": 0.428545, "y": -0.193242, "yaw": 0.437994},
        ball_pose={"x": 0.516185, "y": -0.135987, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 0.516185, "y": -0.135987, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="fetch_ready_local",
    )

    assert command["phase"] == "contact_final_reaim"
    assert command["contact_final_reaim_active"] is True
    assert abs(command["robot_lateral_error_m"]) < command["lateral_reaim_release_m"]
    assert command["desired_yaw_rad"] == pytest.approx(command["line_yaw_rad"], abs=1.0e-6)
    assert command["angular_z_rps"] < -0.10
    assert command["linear_x_mps"] == pytest.approx(0.012)


def test_line_servo_command_uses_recovery_final_reaim_before_rough_contact():
    command = line_servo_command(
        robot_pose={"x": 0.240562, "y": 0.060826, "yaw": 0.437386},
        ball_pose={"x": 0.343338, "y": 0.080267, "yaw": 0.0},
        target_x=0.720524,
        target_y=0.328572,
        ball_start_pose={"x": 0.343338, "y": 0.080267, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="recovery_or_reaim",
    )

    assert command["phase"].startswith("recovery_contact_micro_yaw_hold")
    assert command["contact_final_reaim_active"] is True
    assert command["recovery_final_reaim_active"] is True
    assert command["recovery_contact_micro_yaw_hold_active"] is True
    assert command["contact_ready"] is False
    assert command["recovery_yaw_crawl"] is True
    assert command["linear_x_mps"] == pytest.approx(0.0)
    assert command["lateral_reaim_gain"] == pytest.approx(6.5)
    assert abs(command["lateral_reaim_rad"]) > 0.20
    assert abs(command["angular_z_rps"]) > 0.05


def test_line_servo_command_slow_settles_recovery_before_lateral_debt_contact():
    command = line_servo_command(
        robot_pose={"x": 0.036234784034820486, "y": -0.0076015416736510775, "yaw": -0.2723023185060549},
        ball_pose={"x": 0.256262, "y": -0.173996, "yaw": 0.0},
        target_x=0.852117,
        target_y=-0.416259,
        ball_start_pose={"x": 0.256262, "y": -0.173996, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="recovery_or_reaim",
    )

    assert command["phase"] == "recovery_close_settle"
    assert command["recovery_close_settle_active"] is True
    assert command["recovery_final_reaim_active"] is False
    assert command["contact_ready"] is False
    assert command["ball_moved"] is False
    assert command["linear_x_mps"] == pytest.approx(0.022)
    assert command["desired_yaw_rad"] != pytest.approx(command["line_yaw_rad"], abs=1.0e-6)
    assert command["angular_z_rps"] < -0.18


def test_line_servo_command_keeps_recovery_line_acquire_for_yaw_only_debt():
    command = line_servo_command(
        robot_pose={"x": 0.005473859501502381, "y": -0.13724875233939107, "yaw": -1.009872374450183},
        ball_pose={"x": 0.229489, "y": -0.289834, "yaw": 0.0},
        target_x=0.743987,
        target_y=-0.561764,
        ball_start_pose={"x": 0.229489, "y": -0.289834, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="recovery_or_reaim",
    )

    assert command["phase"] == "recovery_line_acquire"
    assert command["recovery_close_settle_active"] is False
    assert command["contact_ready"] is False
    assert command["ball_moved"] is False
    assert command["linear_x_mps"] == pytest.approx(0.035)
    assert command["desired_yaw_rad"] == pytest.approx(command["line_yaw_rad"], abs=1.0e-6)
    assert command["angular_z_rps"] == pytest.approx(0.45)


def test_line_servo_command_holds_close_recovery_contact_until_yaw_is_safe():
    command = line_servo_command(
        robot_pose={"x": 0.089, "y": 0.088, "yaw": 0.157},
        ball_pose={"x": 0.335058, "y": 0.013191, "yaw": 0.0},
        target_x=0.90467,
        target_y=-0.202663,
        ball_start_pose={"x": 0.335058, "y": 0.013191, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="recovery_or_reaim",
    )

    assert command["phase"] == "recovery_contact_yaw_hold"
    assert command["recovery_contact_yaw_hold_active"] is True
    assert command["contact_ready"] is False
    assert command["ball_moved"] is False
    assert command["linear_x_mps"] == pytest.approx(0.0)
    assert command["desired_yaw_rad"] == pytest.approx(command["line_yaw_rad"], abs=1.0e-6)
    assert command["angular_z_rps"] < 0.0


def test_line_servo_command_holds_forward_motion_for_large_recovery_yaw_setup():
    command = line_servo_command(
        robot_pose={"x": -0.001425, "y": -0.000102, "yaw": 0.142985},
        ball_pose={"x": 0.191488, "y": 0.282240, "yaw": 0.0},
        target_x=0.736454,
        target_y=0.501597,
        ball_start_pose={"x": 0.191488, "y": 0.282240, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="recovery_or_reaim",
    )

    assert command["phase"] == "setup_converge_yaw_hold"
    assert command["recovery_yaw_hold"] is True
    assert command["linear_x_mps"] == 0.0
    assert command["angular_z_rps"] > 0.0


def test_line_servo_command_crawls_before_bad_recovery_contact():
    command = line_servo_command(
        robot_pose={"x": 0.141097, "y": 0.183878, "yaw": 0.887840},
        ball_pose={"x": 0.191488, "y": 0.282240, "yaw": 0.0},
        target_x=0.736454,
        target_y=0.501597,
        ball_start_pose={"x": 0.191488, "y": 0.282240, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="recovery_or_reaim",
    )

    assert command["phase"] == "recovery_final_reaim_yaw_crawl"
    assert command["recovery_final_reaim_active"] is True
    assert command["recovery_yaw_hold"] is False
    assert command["recovery_yaw_crawl"] is True
    assert 0.0 < command["linear_x_mps"] <= 0.018


def test_line_servo_command_crawls_after_recovery_yaw_is_aligned():
    command = line_servo_command(
        robot_pose={"x": 0.018971, "y": 0.171450, "yaw": 0.631949},
        ball_pose={"x": 0.191488, "y": 0.282240, "yaw": 0.0},
        target_x=0.736454,
        target_y=0.501597,
        ball_start_pose={"x": 0.191488, "y": 0.282240, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="recovery_or_reaim",
    )

    assert command["phase"] == "recovery_final_reaim_yaw_crawl"
    assert command["recovery_yaw_hold"] is False
    assert command["recovery_yaw_crawl"] is True
    assert command["linear_x_mps"] > 0.0


def test_line_servo_command_trims_marginal_recovery_lateral_before_contact():
    command = line_servo_command(
        robot_pose={"x": 0.4249231662198784, "y": -0.0030443472353794713, "yaw": -0.4681157193344324},
        ball_pose={"x": 0.523409, "y": -0.021146, "yaw": 0.0},
        target_x=0.941937,
        target_y=-0.232753,
        ball_start_pose={"x": 0.523409, "y": -0.021146, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="recovery_or_reaim",
    )

    assert command["phase"] == "recovery_contact_lateral_trim_yaw_crawl"
    assert command["recovery_contact_lateral_trim_active"] is True
    assert command["ball_moved"] is False
    assert command["contact_ready"] is False
    assert abs(command["line_yaw_error_rad"]) < 1.0e-6
    assert command["desired_yaw_rad"] != pytest.approx(command["line_yaw_rad"], abs=1.0e-6)
    assert command["linear_x_mps"] == pytest.approx(0.012)
    assert command["angular_z_rps"] > 0.0


def test_line_servo_command_holds_local_line_acquire_with_yaw_debt():
    ball_pose = {"x": 0.3610972075079202, "y": 0.14503766794985307, "yaw": 0.0}
    target_x = 0.95
    target_y = 0.0
    line_yaw = math.atan2(target_y - ball_pose["y"], target_x - ball_pose["x"])
    behind_x = ball_pose["x"] - math.cos(line_yaw) * 0.11
    behind_y = ball_pose["y"] - math.sin(line_yaw) * 0.11
    standoff_debt_m = 0.21
    lateral_debt_m = -0.02
    robot_pose = {
        "x": behind_x - math.cos(line_yaw) * standoff_debt_m - math.sin(line_yaw) * lateral_debt_m,
        "y": behind_y - math.sin(line_yaw) * standoff_debt_m + math.cos(line_yaw) * lateral_debt_m,
        "yaw": line_yaw + 0.16,
    }

    command = line_servo_command(
        robot_pose=robot_pose,
        ball_pose=ball_pose,
        target_x=target_x,
        target_y=target_y,
        ball_start_pose=ball_pose,
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="fetch_ready_local",
    )

    assert command["phase"] == "local_contact_yaw_hold"
    assert command["local_line_acquire_yaw_hold_active"] is True
    assert command["local_contact_yaw_hold_active"] is True
    assert command["linear_x_mps"] == 0.0
    assert command["angular_z_rps"] < 0.0


def test_line_servo_command_keeps_close_local_yaw_hold_until_contact_ready():
    ball_pose = {"x": 0.3610972075079202, "y": 0.14503766794985307, "yaw": 0.0}
    target_x = 0.95
    target_y = 0.0
    line_yaw = math.atan2(target_y - ball_pose["y"], target_x - ball_pose["x"])
    behind_x = ball_pose["x"] - math.cos(line_yaw) * 0.11
    behind_y = ball_pose["y"] - math.sin(line_yaw) * 0.11
    standoff_debt_m = 0.16
    lateral_debt_m = -0.006
    robot_pose = {
        "x": behind_x - math.cos(line_yaw) * standoff_debt_m - math.sin(line_yaw) * lateral_debt_m,
        "y": behind_y - math.sin(line_yaw) * standoff_debt_m + math.cos(line_yaw) * lateral_debt_m,
        "yaw": line_yaw + 0.06,
    }

    command = line_servo_command(
        robot_pose=robot_pose,
        ball_pose=ball_pose,
        target_x=target_x,
        target_y=target_y,
        ball_start_pose=ball_pose,
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="fetch_ready_local",
    )

    assert command["phase"] == "local_contact_yaw_hold"
    assert command["local_line_acquire_yaw_hold_active"] is False
    assert command["local_contact_yaw_hold_active"] is True
    assert command["contact_ready"] is False
    assert command["local_contact_yaw_hold_threshold_rad"] == pytest.approx(0.05236)
    assert command["linear_x_mps"] == 0.0
    assert command["angular_z_rps"] < 0.0


def _robot_pose_on_contact_line(
    *,
    ball_pose: dict[str, float],
    target_x: float,
    target_y: float,
    distance_to_contact_m: float,
    lateral_error_m: float,
    line_yaw_error_deg: float,
    contact_standoff_m: float = 0.11,
) -> dict[str, float]:
    line_yaw = math.atan2(target_y - ball_pose["y"], target_x - ball_pose["x"])
    behind_x = ball_pose["x"] - math.cos(line_yaw) * contact_standoff_m
    behind_y = ball_pose["y"] - math.sin(line_yaw) * contact_standoff_m
    return {
        "x": behind_x - math.cos(line_yaw) * distance_to_contact_m - math.sin(line_yaw) * lateral_error_m,
        "y": behind_y - math.sin(line_yaw) * distance_to_contact_m + math.cos(line_yaw) * lateral_error_m,
        "yaw": line_yaw - math.radians(line_yaw_error_deg),
    }


def test_line_servo_command_keeps_push_ready_handoff_on_contact_line():
    ball_pose = {"x": 1.328716, "y": -0.574301, "yaw": 0.0}
    target_x = 0.95
    target_y = 0.0
    robot_pose = _robot_pose_on_contact_line(
        ball_pose=ball_pose,
        target_x=target_x,
        target_y=target_y,
        distance_to_contact_m=0.266681,
        lateral_error_m=0.006512,
        line_yaw_error_deg=-2.795232,
    )

    command = line_servo_command(
        robot_pose=robot_pose,
        ball_pose=ball_pose,
        target_x=target_x,
        target_y=target_y,
        ball_start_pose=ball_pose,
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="fetch_ready_local",
    )

    assert command["phase"] == "push_ready_line_commit"
    assert command["push_ready_line_commit_active"] is True
    assert command["contact_ready"] is True
    assert command["desired_yaw_rad"] == pytest.approx(command["line_yaw_rad"], abs=1.0e-6)
    assert command["desired_yaw_rad"] != pytest.approx(command["setup_yaw_rad"], abs=1.0e-3)
    assert command["linear_x_mps"] == pytest.approx(0.055)


def test_line_servo_command_keeps_non_ready_handoff_out_of_line_commit():
    ball_pose = {"x": 1.328716, "y": -0.574301, "yaw": 0.0}
    target_x = 0.95
    target_y = 0.0
    robot_pose = _robot_pose_on_contact_line(
        ball_pose=ball_pose,
        target_x=target_x,
        target_y=target_y,
        distance_to_contact_m=0.266681,
        lateral_error_m=0.006512,
        line_yaw_error_deg=6.0,
    )

    command = line_servo_command(
        robot_pose=robot_pose,
        ball_pose=ball_pose,
        target_x=target_x,
        target_y=target_y,
        ball_start_pose=ball_pose,
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="fetch_ready_local",
    )

    assert command["push_ready_line_commit_active"] is False
    assert command["contact_ready"] is False
    assert command["phase"] != "push_ready_line_commit"


def test_line_servo_command_holds_close_safe_side_orbit_until_aimed():
    command = line_servo_command(
        robot_pose={"x": 0.677466, "y": -0.064227, "yaw": 0.231441},
        ball_pose={"x": 0.573611, "y": -0.405348, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 0.573611, "y": -0.405348, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="local_setup_capture",
    )

    assert command["phase"] == "recovery_orbit_setup_yaw_guard"
    assert command["local_setup_trajectory_stage"] == "safe_side_orbit"
    assert command["local_setup_safe_side_orbit_yaw_guard"] is True
    assert command["ball_moved"] is False
    assert command["linear_x_mps"] == 0.0
    assert abs(command["yaw_error_rad"]) > 0.35
    assert command["distance_to_contact_m"] == pytest.approx(0.458029, abs=1.0e-6)


def test_line_servo_command_keeps_near_contact_line_acquire_at_projection_edge():
    ball_pose = {"x": 0.573611, "y": -0.405348, "yaw": 0.0}
    target_x = 0.95
    target_y = 0.0
    robot_pose = _robot_pose_on_contact_line(
        ball_pose=ball_pose,
        target_x=target_x,
        target_y=target_y,
        distance_to_contact_m=0.160,
        lateral_error_m=0.029,
        line_yaw_error_deg=0.5,
    )

    command = line_servo_command(
        robot_pose=robot_pose,
        ball_pose=ball_pose,
        target_x=target_x,
        target_y=target_y,
        ball_start_pose=ball_pose,
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="local_setup_capture",
    )

    assert command["phase"] == "local_setup_trajectory_line_acquire"
    assert command["near_contact_line_acquire_active"] is True
    assert command["local_setup_trajectory_stage"] == "line_acquire"
    assert command["contact_ready"] is False
    assert command["setup_projection_error_m"] == pytest.approx(0.19, abs=1.0e-6)


def test_line_servo_command_trims_hairline_lateral_error_instead_of_freezing():
    ball_pose = {"x": 0.573611, "y": -0.405348, "yaw": 0.0}
    target_x = 0.95
    target_y = 0.0
    robot_pose = _robot_pose_on_contact_line(
        ball_pose=ball_pose,
        target_x=target_x,
        target_y=target_y,
        distance_to_contact_m=0.144699,
        lateral_error_m=0.030649,
        line_yaw_error_deg=0.001,
    )

    command = line_servo_command(
        robot_pose=robot_pose,
        ball_pose=ball_pose,
        target_x=target_x,
        target_y=target_y,
        ball_start_pose=ball_pose,
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="local_setup_capture",
    )

    assert command["phase"] == "local_setup_trajectory_line_acquire"
    assert command["local_setup_contact_risk_freeze"] is False
    assert command["near_contact_line_acquire_active"] is True
    assert command["linear_x_mps"] > 0.0
    assert command["contact_ready"] is False
    assert command["robot_lateral_error_m"] == pytest.approx(0.030649, abs=1.0e-6)


def test_line_servo_command_yaw_trims_close_contact_instead_of_freezing():
    ball_pose = {"x": 0.573611, "y": -0.405348, "yaw": 0.0}
    target_x = 0.95
    target_y = 0.0
    robot_pose = _robot_pose_on_contact_line(
        ball_pose=ball_pose,
        target_x=target_x,
        target_y=target_y,
        distance_to_contact_m=0.129969,
        lateral_error_m=0.030242,
        line_yaw_error_deg=5.941286,
    )

    command = line_servo_command(
        robot_pose=robot_pose,
        ball_pose=ball_pose,
        target_x=target_x,
        target_y=target_y,
        ball_start_pose=ball_pose,
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="local_setup_capture",
    )

    assert command["phase"] == "local_setup_trajectory_yaw_trim"
    assert command["near_contact_yaw_trim_active"] is True
    assert command["local_setup_contact_risk_freeze"] is False
    assert command["linear_x_mps"] == 0.0
    assert command["angular_z_rps"] > 0.0
    assert command["desired_yaw_rad"] == pytest.approx(command["line_yaw_rad"], abs=1.0e-6)


def test_line_servo_command_yaw_trims_final_recovery_approach_before_timeout():
    ball_pose = {"x": 0.573611, "y": -0.405348, "yaw": 0.0}
    target_x = 0.95
    target_y = 0.0
    robot_pose = _robot_pose_on_contact_line(
        ball_pose=ball_pose,
        target_x=target_x,
        target_y=target_y,
        distance_to_contact_m=0.22926,
        lateral_error_m=0.030886,
        line_yaw_error_deg=5.598313,
    )

    command = line_servo_command(
        robot_pose=robot_pose,
        ball_pose=ball_pose,
        target_x=target_x,
        target_y=target_y,
        ball_start_pose=ball_pose,
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.030,
        contact_yaw_ready_rad=0.05236,
        route_label="local_setup_capture",
    )

    assert command["phase"] == "local_setup_trajectory_yaw_trim"
    assert command["near_contact_yaw_trim_active"] is True
    assert command["near_contact_line_acquire_active"] is False
    assert command["local_setup_contact_risk_freeze"] is False
    assert command["linear_x_mps"] == 0.0
    assert command["angular_z_rps"] > 0.0
    assert command["desired_yaw_rad"] == pytest.approx(command["line_yaw_rad"], abs=1.0e-6)


def test_line_servo_command_keeps_sub_012m_final_line_acquire():
    ball_pose = {"x": 0.573611, "y": -0.405348, "yaw": 0.0}
    target_x = 0.95
    target_y = 0.0
    robot_pose = _robot_pose_on_contact_line(
        ball_pose=ball_pose,
        target_x=target_x,
        target_y=target_y,
        distance_to_contact_m=0.119853,
        lateral_error_m=0.029750,
        line_yaw_error_deg=2.80,
    )

    command = line_servo_command(
        robot_pose=robot_pose,
        ball_pose=ball_pose,
        target_x=target_x,
        target_y=target_y,
        ball_start_pose=ball_pose,
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="local_setup_capture",
    )

    assert command["phase"] == "local_setup_trajectory_line_acquire"
    assert command["near_contact_line_acquire_active"] is True
    assert command["local_setup_trajectory_stage"] == "line_acquire"
    assert command["linear_x_mps"] > 0.0
    assert command["phase"] != "local_setup_trajectory_behind_setup_yaw_lock"


def test_line_servo_command_final_line_acquire_trims_lateral_ready_edge():
    ball_pose = {"x": 0.573611, "y": -0.405348, "yaw": 0.0}
    target_x = 0.95
    target_y = 0.0
    robot_pose = _robot_pose_on_contact_line(
        ball_pose=ball_pose,
        target_x=target_x,
        target_y=target_y,
        distance_to_contact_m=0.192546,
        lateral_error_m=0.030681,
        line_yaw_error_deg=0.076,
    )

    command = line_servo_command(
        robot_pose=robot_pose,
        ball_pose=ball_pose,
        target_x=target_x,
        target_y=target_y,
        ball_start_pose=ball_pose,
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.030,
        contact_yaw_ready_rad=0.05236,
        route_label="local_setup_capture",
    )

    assert command["phase"] == "local_setup_trajectory_line_acquire"
    assert command["near_contact_line_acquire_active"] is True
    assert command["desired_yaw_rad"] < command["line_yaw_rad"]
    assert command["angular_z_rps"] < 0.0
    assert command["linear_x_mps"] > 0.0


def test_line_servo_command_holds_recovery_line_acquire_with_yaw_debt():
    ball_pose = {"x": 0.3254663336413385, "y": -0.03290000505426448, "yaw": 0.0}
    target_x = 0.95
    target_y = 0.0
    line_yaw = math.atan2(target_y - ball_pose["y"], target_x - ball_pose["x"])
    behind_x = ball_pose["x"] - math.cos(line_yaw) * 0.11
    behind_y = ball_pose["y"] - math.sin(line_yaw) * 0.11
    standoff_debt_m = 0.21
    lateral_debt_m = 0.02
    robot_pose = {
        "x": behind_x - math.cos(line_yaw) * standoff_debt_m - math.sin(line_yaw) * lateral_debt_m,
        "y": behind_y - math.sin(line_yaw) * standoff_debt_m + math.cos(line_yaw) * lateral_debt_m,
        "yaw": line_yaw - 0.36,
    }

    command = line_servo_command(
        robot_pose=robot_pose,
        ball_pose=ball_pose,
        target_x=target_x,
        target_y=target_y,
        ball_start_pose=ball_pose,
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="recovery_or_reaim",
    )

    assert command["phase"] == "recovery_contact_yaw_hold"
    assert command["recovery_line_acquire_yaw_hold_active"] is True
    assert command["recovery_contact_yaw_hold_active"] is True
    assert command["ball_moved"] is False
    assert command["linear_x_mps"] == 0.0
    assert command["angular_z_rps"] > 0.0
    assert command["distance_to_contact_m"] == pytest.approx(0.21095)


def test_line_servo_command_keeps_close_recovery_yaw_hold_until_contact_ready():
    ball_pose = {"x": 0.3254663336413385, "y": -0.03290000505426448, "yaw": 0.0}
    target_x = 0.95
    target_y = 0.0
    line_yaw = math.atan2(target_y - ball_pose["y"], target_x - ball_pose["x"])
    behind_x = ball_pose["x"] - math.cos(line_yaw) * 0.11
    behind_y = ball_pose["y"] - math.sin(line_yaw) * 0.11
    standoff_debt_m = 0.16
    lateral_debt_m = 0.006
    robot_pose = {
        "x": behind_x - math.cos(line_yaw) * standoff_debt_m - math.sin(line_yaw) * lateral_debt_m,
        "y": behind_y - math.sin(line_yaw) * standoff_debt_m + math.cos(line_yaw) * lateral_debt_m,
        "yaw": line_yaw - 0.06,
    }

    command = line_servo_command(
        robot_pose=robot_pose,
        ball_pose=ball_pose,
        target_x=target_x,
        target_y=target_y,
        ball_start_pose=ball_pose,
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="recovery_or_reaim",
    )

    assert command["phase"] == "recovery_contact_yaw_hold"
    assert command["recovery_line_acquire_yaw_hold_active"] is False
    assert command["recovery_contact_yaw_hold_active"] is True
    assert command["contact_ready"] is False
    assert command["recovery_contact_yaw_hold_threshold_rad"] == pytest.approx(0.05236)
    assert command["linear_x_mps"] == 0.0
    assert command["angular_z_rps"] > 0.0


def test_line_servo_command_holds_scene16_recovery_line_acquire_before_bad_contact():
    command = line_servo_command(
        robot_pose={"x": 0.048842093837524046, "y": -0.052551161111039434, "yaw": -0.6515225996204963},
        ball_pose={"x": 0.317743, "y": -0.100578, "yaw": 0.0},
        target_x=0.989887,
        target_y=-0.022502,
        ball_start_pose={"x": 0.317743, "y": -0.100578, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.45,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="recovery_or_reaim",
    )

    assert command["phase"] == "recovery_contact_yaw_hold"
    assert command["recovery_line_acquire_yaw_hold_active"] is True
    assert command["recovery_contact_yaw_hold_active"] is True
    assert command["distance_to_contact_m"] == pytest.approx(0.170793, abs=1.0e-6)
    assert command["robot_lateral_error_m"] == pytest.approx(0.078733, abs=1.0e-6)
    assert command["line_yaw_error_rad"] == pytest.approx(0.767164, abs=1.0e-6)
    assert command["linear_x_mps"] == 0.0
    assert command["desired_yaw_rad"] == pytest.approx(command["line_yaw_rad"], abs=1.0e-6)
    assert command["angular_z_rps"] > 0.0


def test_line_servo_command_crawls_scene28_recovery_line_acquire_stall():
    command = line_servo_command(
        robot_pose={"x": 0.06446112985287243, "y": -0.0024354895530302764, "yaw": -0.36828310412231374},
        ball_pose={"x": 0.394918, "y": -0.051813, "yaw": 0.0},
        target_x=0.95,
        target_y=0.0,
        ball_start_pose={"x": 0.394918, "y": -0.051813, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="recovery_or_reaim",
    )

    assert command["phase"] == "recovery_line_acquire_yaw_crawl"
    assert command["recovery_line_acquire_yaw_hold_active"] is True
    assert command["recovery_line_acquire_yaw_crawl_active"] is True
    assert command["recovery_contact_yaw_hold_active"] is False
    assert command["recovery_yaw_crawl"] is True
    assert command["ball_moved"] is False
    assert command["distance_to_contact_m"] == pytest.approx(0.228831, abs=1.0e-6)
    assert command["robot_lateral_error_m"] == pytest.approx(0.079876, abs=1.0e-6)
    assert abs(command["line_yaw_error_rad"]) <= command["recovery_close_line_acquire_yaw_hold_threshold_rad"]
    assert 0.0 < command["linear_x_mps"] <= 0.018
    assert command["desired_yaw_rad"] == pytest.approx(command["line_yaw_rad"], abs=1.0e-6)
    assert command["angular_z_rps"] > 0.0


def test_line_servo_command_crawls_out_of_recovery_setup_oscillation():
    command = line_servo_command(
        robot_pose={"x": -0.006171, "y": -0.054051, "yaw": -1.799786},
        ball_pose={"x": 0.212506, "y": -0.251974, "yaw": 0.0},
        target_x=0.920053,
        target_y=-0.483691,
        ball_start_pose={"x": 0.212506, "y": -0.251974, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="recovery_or_reaim",
    )

    assert command["phase"] == "setup_converge_yaw_crawl"
    assert command["recovery_close_settle_active"] is False
    assert command["recovery_yaw_hold"] is False
    assert command["recovery_yaw_crawl"] is True
    assert 0.0 < command["linear_x_mps"] <= 0.025


def test_line_servo_command_realigns_after_early_bad_recovery_contact():
    command = line_servo_command(
        robot_pose={"x": 0.148472, "y": 0.192613, "yaw": 0.853240},
        ball_pose={"x": 0.195257, "y": 0.286283, "yaw": 0.0},
        target_x=0.736454,
        target_y=0.501597,
        ball_start_pose={"x": 0.191488, "y": 0.282240, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="recovery_or_reaim",
    )

    assert command["phase"] == "push_coast_realign"
    assert command["ball_moved"] is True
    assert command["contact_ready"] is False
    assert command["linear_x_mps"] <= 0.035
    assert command["desired_yaw_rad"] != pytest.approx(command["line_yaw_rad"], abs=1.0e-6)


def test_line_servo_command_realigns_slowly_when_recovery_ball_moves_before_yaw_is_ready():
    command = line_servo_command(
        robot_pose={"x": 0.094894, "y": 0.088367, "yaw": 0.090335},
        ball_pose={"x": 0.336253, "y": 0.003492, "yaw": 0.0},
        target_x=0.90467,
        target_y=-0.202663,
        ball_start_pose={"x": 0.335058, "y": 0.013191, "yaw": 0.0},
        max_linear_x_mps=0.10,
        push_linear_x_mps=0.055,
        min_linear_x_mps=0.012,
        max_angular_z_rps=0.18,
        yaw_gain=1.20,
        contact_lateral_ready_m=0.028,
        contact_yaw_ready_rad=0.05236,
        route_label="recovery_or_reaim",
    )

    assert command["phase"] == "push_coast_realign"
    assert command["ball_moved"] is True
    assert command["contact_ready"] is False
    assert command["linear_x_mps"] <= 0.018
    assert command["desired_yaw_rad"] == pytest.approx(command["line_yaw_rad"], abs=1.0e-6)
    assert command["angular_z_rps"] < 0.0


def test_summarize_line_servo_effective_command_preserves_route_caps():
    summary = summarize_line_servo_effective_command(
        [
            {"sample_index": 0},
            {
                "sample_index": 1,
                "line_servo_command": {
                    "route_label": "recovery_or_reaim",
                    "setup_standoff_m": 0.34,
                    "contact_standoff_m": 0.11,
                    "contact_lateral_ready_m": 0.03,
                    "contact_yaw_ready_rad": 0.05236,
                    "recovery_line_acquire_lateral_m": 0.08,
                    "recovery_setup_pocket_m": 0.12,
                    "yaw_priority_lateral_m": 0.032,
                    "max_angular_z_rps": 0.45,
                },
            },
        ]
    )

    assert summary == {
        "line_servo_effective_setup_standoff_m": 0.34,
        "line_servo_effective_contact_standoff_m": 0.11,
        "line_servo_effective_contact_lateral_ready_m": 0.03,
        "line_servo_effective_contact_yaw_ready_rad": 0.05236,
        "line_servo_effective_recovery_line_acquire_lateral_m": 0.08,
        "line_servo_effective_recovery_setup_pocket_m": 0.12,
        "line_servo_effective_yaw_priority_lateral_m": 0.032,
        "line_servo_effective_max_angular_z_rps": 0.45,
        "line_servo_effective_route_label": "recovery_or_reaim",
    }


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
    assert metrics["first_contact_quality_pass"] is True
    assert metrics["flags"] == []
    assert metrics["first_contact_quality_flags"] == []
    assert metrics["first_contact_index"] == 2
    assert metrics["max_abs_robot_lateral_error_pre_contact_m"] == pytest.approx(0.001)
    assert metrics["robot_yaw_error_sign_changes_pre_contact"] == 0
    assert metrics["max_abs_robot_lateral_error_terminal_pre_contact_m"] == pytest.approx(0.001)
    assert metrics["robot_yaw_error_sign_changes_terminal_pre_contact"] == 0


def test_contact_trace_metrics_do_not_flag_initial_setup_debt_after_terminal_settle():
    samples = [
        {
            "sample_index": 0,
            "t_s": 0.0,
            "robot_pose": {"position": {"x": 0.00, "y": 0.12, "z": 0.0}, "yaw": 0.25},
            "ball_pose": {"position": {"x": 0.38, "y": 0.0, "z": 0.021336}, "yaw": 0.0},
        },
        {
            "sample_index": 1,
            "t_s": 2.0,
            "robot_pose": {"position": {"x": 0.20, "y": 0.02, "z": 0.0}, "yaw": 0.02},
            "ball_pose": {"position": {"x": 0.38, "y": 0.0, "z": 0.021336}, "yaw": 0.0},
        },
        {
            "sample_index": 2,
            "t_s": 2.6,
            "robot_pose": {"position": {"x": 0.34, "y": 0.01, "z": 0.0}, "yaw": 0.01},
            "ball_pose": {"position": {"x": 0.38, "y": 0.0, "z": 0.021336}, "yaw": 0.0},
        },
        {
            "sample_index": 3,
            "t_s": 2.8,
            "robot_pose": {"position": {"x": 0.40, "y": 0.01, "z": 0.0}, "yaw": 0.01},
            "ball_pose": {"position": {"x": 0.39, "y": 0.0, "z": 0.021336}, "yaw": 0.0},
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
    assert metrics["first_contact_quality_pass"] is True
    assert metrics["flags"] == []
    assert metrics["max_abs_robot_lateral_error_pre_contact_m"] == pytest.approx(0.12)
    assert metrics["max_abs_robot_lateral_error_terminal_pre_contact_m"] == pytest.approx(0.02)
    assert metrics["max_abs_robot_yaw_error_pre_contact_deg"] > 3.0
    assert metrics["max_abs_robot_yaw_error_terminal_pre_contact_deg"] < 3.0


def test_contact_trace_metrics_gate_terminal_quality_after_contact_ready():
    samples = [
        {
            "sample_index": 0,
            "t_s": 0.0,
            "robot_pose": {"position": {"x": 0.22, "y": 0.0, "z": 0.0}, "yaw": 0.061},
            "ball_pose": {"position": {"x": 0.38, "y": 0.0, "z": 0.021336}, "yaw": 0.0},
            "line_servo_command": {"phase": "contact_final_reaim", "contact_ready": False},
        },
        {
            "sample_index": 1,
            "t_s": 0.4,
            "robot_pose": {"position": {"x": 0.30, "y": 0.0, "z": 0.0}, "yaw": 0.055},
            "ball_pose": {"position": {"x": 0.38, "y": 0.0, "z": 0.021336}, "yaw": 0.0},
            "line_servo_command": {"phase": "contact_final_reaim", "contact_ready": False},
        },
        {
            "sample_index": 2,
            "t_s": 0.6,
            "robot_pose": {"position": {"x": 0.34, "y": 0.0, "z": 0.0}, "yaw": 0.040},
            "ball_pose": {"position": {"x": 0.38, "y": 0.0, "z": 0.021336}, "yaw": 0.0},
            "line_servo_command": {"phase": "first_contact_align", "contact_ready": True},
        },
        {
            "sample_index": 3,
            "t_s": 1.0,
            "robot_pose": {"position": {"x": 0.40, "y": 0.0, "z": 0.0}, "yaw": 0.020},
            "ball_pose": {"position": {"x": 0.39, "y": 0.0, "z": 0.021336}, "yaw": 0.0},
            "line_servo_command": {"phase": "push_coast", "contact_ready": True},
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
    assert metrics["terminal_pre_contact_contact_ready_gated"] is True
    assert metrics["terminal_pre_contact_sample_count"] == 4
    assert metrics["terminal_pre_contact_quality_sample_count"] == 2
    assert metrics["max_abs_robot_yaw_error_terminal_window_deg"] > 3.0
    assert metrics["max_abs_robot_yaw_error_terminal_pre_contact_deg"] < 3.0


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
    assert metrics["first_contact_quality_pass"] is False
    assert "pre_contact_lateral_error" in metrics["flags"]
    assert "pre_contact_yaw_oscillation" in metrics["flags"]
    assert "ball_lateral_knock_away" in metrics["flags"]
    assert "first_contact_ball_lateral_error" in metrics["first_contact_quality_flags"]


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
