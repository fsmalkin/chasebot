import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import dashboard_service  # noqa: E402


def test_scenario_catalog_registers_physics_calibrated_golf_fetch():
    scenario = dashboard_service.SCENARIOS_BY_ID["golf_ball_circle_delivery_uat"]

    assert scenario.mode == "gather_mission"
    assert scenario.runner_scenario_id == "corral_single_ball_place"
    assert scenario.mission_objective == "fetch_to_pose"
    assert scenario.world_file == "yolo_test_world_v6_calibrated_golf_turf.world"
    assert scenario.surface_profile == "calibrated_golf_turf"
    assert scenario.robot_sdf_name == "jetbot_core_ignition_v1.7.0.sdf"
    assert scenario.target_x == 0.38
    assert scenario.target_z == 0.021336
    assert scenario.fetch_target_x == 0.95
    assert scenario.fetch_target_y == 0.0
    assert scenario.fetch_target_z == 0.001
    assert scenario.fetch_delivery_radius_m == 0.30
    assert scenario.target_model_sdf == "ros2_config/calibrated_golf_ball.sdf"
    assert scenario.zone_model_sdf == "ros2_config/golf_ball_delivery_zone_marker.sdf"
    assert scenario.max_retries_per_target == 0


def test_self_contained_scenario_ids_include_new_fetch_scenario():
    assert "golf_ball_circle_delivery_uat" in dashboard_service.SELF_CONTAINED_SCENARIO_IDS


def test_scenario_api_payload_exposes_fetch_fields():
    payload = dashboard_service.SCENARIOS_BY_ID["golf_ball_circle_delivery_uat"].to_api()

    assert payload["mission_objective"] == "fetch_to_pose"
    assert payload["fetch_target_x"] == 0.95
    assert payload["fetch_target_z"] == 0.001
    assert payload["fetch_delivery_radius_m"] == 0.30
    assert payload["target_layout_json"] == "ros2_config/target_layouts/golf_ball_circle_delivery_zero.json"
    assert payload["target_model_sdf"] == "ros2_config/calibrated_golf_ball.sdf"
    assert payload["zone_model_sdf"] == "ros2_config/golf_ball_delivery_zone_marker.sdf"
