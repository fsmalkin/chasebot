import sys
import json
import math
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from golf_ball_circle_delivery_demo_runner import build_shot_outcome  # noqa: E402
from golf_ball_circle_delivery_demo_runner import ball_samples_from_contact_samples  # noqa: E402
from golf_ball_circle_delivery_demo_runner import build_approach_contact_metrics  # noqa: E402
from golf_ball_circle_delivery_demo_runner import line_servo_command  # noqa: E402
from golf_ball_circle_delivery_demo_runner import parse_args  # noqa: E402
from golf_ball_circle_delivery_demo_runner import apply_target_layout  # noqa: E402
from golf_ball_circle_delivery_demo_runner import build_nav2_reposition_setup_pose  # noqa: E402
from golf_ball_circle_delivery_demo_runner import build_nav2_relative_setup_goal  # noqa: E402
from golf_ball_circle_delivery_demo_runner import dispatch_nav2_reposition_before_fetch  # noqa: E402
from golf_ball_circle_delivery_demo_runner import NAV2_REPOSITION_BEHAVIOR_TREE  # noqa: E402
from golf_ball_circle_delivery_demo_runner import parse_nav2_reposition_result  # noqa: E402
from golf_ball_circle_delivery_demo_runner import summarize_line_servo_effective_command  # noqa: E402
from golf_ball_circle_delivery_demo_runner import transform_nav2_reposition_layout_to_current_robot  # noqa: E402


def test_shot_outcome_uses_segment_intersection_for_delivery_circle():
    samples = [
        {"t_s": 0.0, "position": {"x": 0.20, "y": 0.0, "z": 0.021336}},
        {"t_s": 0.5, "position": {"x": 1.20, "y": 0.0, "z": 0.021336}},
    ]

    outcome = build_shot_outcome(samples, target_x=0.95, target_y=0.0, target_z=0.001, radius_m=0.30)

    assert outcome["pass"] is True
    assert outcome["closest_approach_distance_m"] == pytest.approx(0.0)
    assert outcome["fetch_pose_world"] == {"x": 0.95, "y": 0.0, "z": 0.001, "radius_m": 0.3}


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
    assert pose["orientation"]["w"] == pytest.approx(math.cos(line_yaw * 0.5), abs=1.0e-6)


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

    assert command["phase"] == "push_coast"
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

    assert command["phase"] == "setup_reaim"
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
    assert recovery_command["phase"] == "setup_converge"
    assert recovery_command["linear_x_mps"] > 0.0
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
