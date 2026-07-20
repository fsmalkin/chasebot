from pathlib import Path
import xml.etree.ElementTree as ET

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_nav2_controller_default_goal_checker_is_configured():
    for rel_path in [
        "ros2_config/params/nav2_params.yaml",
        "ros2_config/params/nav2_params_simple.yaml",
    ]:
        payload = yaml.safe_load((REPO_ROOT / rel_path).read_text(encoding="utf-8"))
        params = payload["controller_server"]["ros__parameters"]
        assert "general_goal_checker" in params["goal_checker_plugins"]
        assert params["general_goal_checker"]["plugin"] == "nav2_controller::SimpleGoalChecker"


def test_nav2_params_select_repo_navigate_to_pose_behavior_tree():
    expected_path = "/workspaces/chasecar/ros2_config/behavior_trees/navigate_to_pose_w_replanning.xml"
    for rel_path in [
        "ros2_config/params/nav2_params.yaml",
        "ros2_config/params/nav2_params_simple.yaml",
    ]:
        payload = yaml.safe_load((REPO_ROOT / rel_path).read_text(encoding="utf-8"))
        params = payload["bt_navigator"]["ros__parameters"]
        assert params["default_nav_to_pose_bt_xml"] == expected_path
        assert (REPO_ROOT / "ros2_config/behavior_trees/navigate_to_pose_w_replanning.xml").exists()


def test_nav2_navigate_to_pose_bt_sets_follow_path_goal_checker():
    tree_path = REPO_ROOT / "ros2_config/behavior_trees/navigate_to_pose_w_replanning.xml"
    tree = ET.parse(tree_path)

    follow_path_nodes = tree.findall(".//FollowPath")

    assert follow_path_nodes
    for node in follow_path_nodes:
        assert node.attrib["goal_checker_id"] == "general_goal_checker"


def test_nav2_navigate_to_pose_bt_omits_recovery_motion_for_last_meter_setup():
    tree_path = REPO_ROOT / "ros2_config/behavior_trees/navigate_to_pose_w_replanning.xml"
    tree = ET.parse(tree_path)

    assert tree.getroot().attrib["BTCPP_format"] == "4"
    assert tree.findall(".//SequenceStar") == []
    assert tree.findall(".//Spin") == []
    assert tree.findall(".//BackUp") == []
