from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import llm_provider_openai as openai_provider  # noqa: E402
import llm_turn_then_go_proof_runner as proof_runner  # noqa: E402
from brain_state_digest import build_state_digest  # noqa: E402
from llm_supervisor_core import load_contract  # noqa: E402
from llm_supervisor_core import validate_decision_against_canonical_space  # noqa: E402
from llm_supervisor_core import validate_decision_against_contract  # noqa: E402


CONTRACT_PATH = REPO_ROOT / "runtime" / "contracts" / "llm_control_contract.yaml"


def test_to_container_repo_path_maps_repo_files():
    target = REPO_ROOT / "ros2_config" / "frisbee_target_ball.sdf"
    assert proof_runner.to_container_repo_path(target) == "/workspaces/chasecar/ros2_config/frisbee_target_ball.sdf"


def test_openai_request_uses_only_search_and_stop_tools_when_target_not_visible():
    contract = load_contract(CONTRACT_PATH)
    state = {
        "control_plane_ready": True,
        "environment_state": "environment_ready",
        "scenario_state": "running",
        "session_id": "20260315T020000Z",
        "sim_gate_ready": True,
        "perception": {
            "detection_topic_seen": False,
            "target_visible_now": False,
        },
        "belief": {
            "robot_pose_available": True,
            "latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
        },
        "brain": {
            "target_locked": False,
            "target_visible_recent": False,
            "search_active": False,
            "goal_in_progress": False,
            "track_active": False,
        },
        "outcome": {
            "feedback_recent": False,
            "nav_goal_recent": False,
            "cmd_vel_recent": False,
            "boundary_activity_seen": False,
        },
    }
    digest = build_state_digest(state, contract)
    request = openai_provider.build_openai_request(
        model="gpt-5-nano",
        reasoning_effort="medium",
        task_text="find the ball",
        digest=digest,
        contract=contract,
    )
    tool_names = [tool["name"] for tool in request["tools"]]

    assert "emit_blocked" in tool_names
    assert "emit_search_for_target" in tool_names
    assert "emit_plan_to_target" not in tool_names
    assert "emit_track_target" not in tool_names


def test_search_for_target_decision_is_contract_valid():
    contract = load_contract(CONTRACT_PATH)
    decision = {
        "status": "recommendation",
        "task_text": "turn until the ball is visible",
        "intent": "search_for_target",
        "args": {"target_class": "ball"},
        "rationale_short": "The ball is not visible yet, so bounded search is the correct next step.",
        "missing_prerequisites": [],
        "expected_observations": ["turn-in-place cmd_vel activity", "target becomes visible"],
        "confidence": 0.88,
    }

    validated = validate_decision_against_contract(decision, contract)
    validated = validate_decision_against_canonical_space(validated)

    assert validated["intent"] == "search_for_target"
    assert validated["args"] == {"target_class": "ball"}
