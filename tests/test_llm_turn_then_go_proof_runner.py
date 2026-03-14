from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import llm_provider_openai as openai_provider  # noqa: E402
import llm_turn_then_go_proof_runner as proof_runner  # noqa: E402
from llm_supervisor_core import load_contract  # noqa: E402
from llm_supervisor_core import validate_decision_against_canonical_space  # noqa: E402
from llm_supervisor_core import validate_decision_against_contract  # noqa: E402


CONTRACT_PATH = REPO_ROOT / "runtime" / "contracts" / "llm_control_contract.yaml"


def test_to_container_repo_path_maps_repo_files():
    target = REPO_ROOT / "ros2_config" / "frisbee_target_ball.sdf"
    assert proof_runner.to_container_repo_path(target) == "/workspaces/chasecar/ros2_config/frisbee_target_ball.sdf"


def test_openai_decision_schema_uses_required_nullable_args():
    contract = load_contract(CONTRACT_PATH)
    schema = openai_provider.decision_schema(contract)
    args_schema = schema["properties"]["args"]

    assert args_schema["required"] == ["target_class", "approach_distance_m"]
    assert args_schema["properties"]["target_class"]["enum"] == ["ball", None]
    assert args_schema["properties"]["approach_distance_m"]["enum"] == [0.25, None]


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
