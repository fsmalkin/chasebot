from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gather_nav2_follow_path_reacquire_helpers as follow_path  # noqa: E402
from gather_mission_helpers import build_zone_spec  # noqa: E402
from gather_mission_helpers import pre_stage_arrival_snapshot  # noqa: E402


def _plan(robot_pose, ball_pose, **kwargs):
    zone = build_zone_spec("corral_single_ball_place")
    snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone)
    return follow_path.build_nav2_follow_path_reacquire_plan(
        robot_pose,
        ball_pose,
        zone=zone,
        snapshot=snapshot,
        **kwargs,
    )


def test_nav2_follow_path_public_interface_exports_family_and_path_payload():
    assert follow_path.NAV2_FOLLOW_PATH_REACQUIRE_CONTROL_FAMILY == "nav2_follow_path_reacquire_v1"
    assert follow_path.NAV2_MPPI_FOLLOW_PATH_REACQUIRE_CONTROL_FAMILY == "nav2_mppi_follow_path_reacquire_v1"
    assert follow_path.NAV2_FOLLOW_PATH_CORRIDOR_PUSH_CONTROL_FAMILY == "nav2_followpath_corridor_push_v1"
    assert follow_path.NAV2_FOLLOW_PATH_RESULT_MARKER == "NAV2_FOLLOW_PATH_RESULT="

    plan = _plan({"x": 0.0, "y": 0.0, "yaw": 0.0}, {"x": 5.448, "y": 0.0, "z": 0.05})
    payload = plan.to_dict()

    assert payload["active"] is True
    assert payload["reason"] == "follow_path_reacquire"
    assert payload["controller_id"] == "FollowPath"
    assert payload["goal_checker_id"] == "general_goal_checker"
    assert payload["path_kinds"] == ["escape_clear", "corridor_approach", "port", "handoff_yaw"]
    assert len(payload["path_poses"]) == 4
    assert payload["min_path_ball_clearance_m"] >= 0.50


def test_nav2_follow_path_corridor_push_builds_contact_path_through_delivery_pose():
    plan = follow_path.build_nav2_follow_path_corridor_push_plan(
        {"x": -0.65, "y": 0.0, "yaw": 0.0},
        {"x": 0.0, "y": 0.0, "z": 0.05},
        {"x": 1.0, "y": 0.0, "z": 0.001, "radius_m": 0.3},
    )
    payload = plan.to_dict()

    assert payload["active"] is True
    assert payload["reason"] == "follow_path_corridor_push"
    assert payload["controller_id"] == "FollowPath"
    assert payload["goal_checker_id"] == "general_goal_checker"
    assert payload["path_kinds"][0] == "start"
    semantic_kinds = [
        pose["kind"]
        for pose in payload["path_poses"]
        if pose["kind"]
        in {
            "start",
            "corridor_contact_ready",
            "corridor_contact",
            "corridor_delivery_intersection",
            "corridor_push_through",
        }
    ]
    assert semantic_kinds == [
        "start",
        "corridor_contact_ready",
        "corridor_contact",
        "corridor_delivery_intersection",
        "corridor_push_through",
    ]
    assert payload["path_poses"][-1]["x"] > 1.0
    assert payload["trigger"]["robot_lateral_signed_m"] == 0.0
    assert payload["trigger"]["ball_target_distance_m"] == 1.0


def test_nav2_follow_path_corridor_push_allows_lateral_start_but_tracks_ball_target_line():
    plan = follow_path.build_nav2_follow_path_corridor_push_plan(
        {"x": -0.65, "y": 0.25, "yaw": 0.0},
        {"x": 0.0, "y": 0.0, "z": 0.05},
        {"x": 1.0, "y": 0.0, "z": 0.001, "radius_m": 0.3},
        max_path_spacing_m=0.0,
    )
    payload = plan.to_dict()

    assert payload["active"] is True
    assert payload["trigger"]["robot_lateral_signed_m"] == 0.25
    corridor_points = [
        pose for pose in payload["path_poses"] if pose["kind"] in {"corridor_contact", "corridor_delivery_intersection"}
    ]
    assert [pose["y"] for pose in corridor_points] == [0.0, 0.0]


def test_nav2_follow_path_corridor_push_arrives_contact_ready_on_push_yaw():
    plan = follow_path.build_nav2_follow_path_corridor_push_plan(
        {"x": -0.65, "y": 0.25, "yaw": 0.0},
        {"x": 0.0, "y": 0.0, "z": 0.05},
        {"x": 1.0, "y": 0.0, "z": 0.001, "radius_m": 0.3},
        max_path_spacing_m=0.12,
    )
    payload = plan.to_dict()

    contact_ready = next(pose for pose in payload["path_poses"] if pose["kind"] == "corridor_contact_ready")
    contact = next(pose for pose in payload["path_poses"] if pose["kind"] == "corridor_contact")
    assert contact_ready["yaw_deg"] == 0.0
    assert contact["yaw_deg"] == 0.0
    assert payload["path_poses"][1]["yaw_deg"] == 0.0


def test_nav2_follow_path_corridor_push_reports_missing_geometry():
    plan = follow_path.build_nav2_follow_path_corridor_push_plan(
        {"x": -0.65, "y": 0.0, "yaw": 0.0},
        {},
        {"x": 1.0, "y": 0.0, "z": 0.001, "radius_m": 0.3},
    )

    assert plan.active is False
    assert plan.reason == "missing_corridor_push_geometry"


def test_nav2_mppi_follow_path_uses_dedicated_controller_and_dense_path():
    zone = build_zone_spec("corral_single_ball_place")
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    ball_pose = {"x": 4.555261, "y": 2.155261, "z": 0.05}
    snapshot = pre_stage_arrival_snapshot(robot_pose, ball_pose, zone=zone)

    plan = follow_path.build_nav2_mppi_follow_path_reacquire_plan(
        robot_pose,
        ball_pose,
        zone=zone,
        snapshot=snapshot,
    )
    payload = plan.to_dict()

    assert payload["active"] is True
    assert payload["controller_id"] == "MppiFollowPath"
    assert payload["goal_checker_id"] == "general_goal_checker"
    assert payload["path_kinds"][0] == "start"
    assert "handoff_align" not in payload["path_kinds"]
    assert payload["path_kinds"][-1] == "handoff_yaw"
    assert len(payload["path_poses"]) > 4
    assert payload["path_poses"][0]["x"] == robot_pose["x"]
    assert payload["path_poses"][0]["y"] == robot_pose["y"]
    assert payload["path_poses"][1]["yaw_deg"] > 30.0
    semantic_kinds = [pose["kind"] for pose in payload["path_poses"] if pose["kind"] in {"start", "escape_clear", "corridor_approach", "port", "handoff_yaw"}]
    assert semantic_kinds == ["start", "escape_clear", "corridor_approach", "port", "handoff_yaw"]
    terminal_yaw_deg = payload["path_poses"][-1]["yaw_deg"]
    handoff_segment = [pose for pose in payload["path_poses"] if str(pose["kind"]).startswith("handoff_")]
    assert handoff_segment
    assert all(abs(pose["yaw_deg"] - terminal_yaw_deg) < 1.0e-6 for pose in handoff_segment)
    assert payload["min_path_ball_clearance_m"] >= 0.50


def test_nav2_follow_path_generation_covers_zero_plus_minus_cases():
    robot_pose = {"x": 0.0, "y": 0.0, "yaw": 0.0}
    zero_plan = _plan(robot_pose, {"x": 5.448, "y": 0.0, "z": 0.05})
    plus_plan = _plan(robot_pose, {"x": 4.555261, "y": 2.155261, "z": 0.05})
    minus_plan = _plan(robot_pose, {"x": 4.555261, "y": -2.155261, "z": 0.05})

    for plan in (zero_plan, plus_plan, minus_plan):
        payload = plan.to_dict()
        assert payload["active"] is True
        assert len(payload["path_poses"]) == 4
        assert payload["path_poses"][-1]["kind"] == "handoff_yaw"
        assert payload["min_path_ball_clearance_m"] >= 0.50

    assert zero_plan.to_dict()["path_poses"][-1]["yaw_deg"] in (180.0, -180.0)
    assert plus_plan.to_dict()["path_poses"][-1]["yaw_deg"] < -90.0
    assert minus_plan.to_dict()["path_poses"][-1]["yaw_deg"] > 90.0


def test_nav2_follow_path_does_not_activate_when_handoff_ready():
    plan = _plan({"x": 0.1, "y": 0.0, "yaw": 0.0}, {"x": 1.0, "y": 0.0, "z": 0.05})

    assert plan.active is False
    assert plan.reason == "pre_stage_handoff_already_ready"
    assert plan.to_dict()["path_poses"] == []


def test_nav2_follow_path_reports_missing_geometry_as_inactive():
    zone = build_zone_spec("corral_single_ball_place")
    plan = follow_path.build_nav2_follow_path_reacquire_plan(
        {"x": 0.0, "y": 0.0, "yaw": 0.0},
        {},
        zone=zone,
        snapshot={},
    )

    assert plan.active is False
    assert plan.reason == "missing_follow_path_geometry"


def test_nav2_follow_path_clearance_guard_rejects_unsafe_threshold():
    plan = _plan(
        {"x": 0.0, "y": 0.0, "yaw": 0.0},
        {"x": 5.448, "y": 0.0, "z": 0.05},
        min_ball_clearance_m=10.0,
    )

    payload = plan.to_dict()
    assert payload["active"] is False
    assert payload["reason"] == "follow_path_clearance_guard"
    assert payload["path_poses"]
    assert payload["min_path_ball_clearance_m"] < 10.0
