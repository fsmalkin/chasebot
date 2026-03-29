from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


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


def test_proof_runner_records_deterministic_recommendation_history(tmp_path, monkeypatch):
    monkeypatch.setattr(proof_runner, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(proof_runner, "PROOF_RUNTIME_STATE_PATH", tmp_path / "runtime" / "llm_turn_then_go_runtime.json")
    monkeypatch.setattr(proof_runner, "choose_docker_cli", lambda: "docker")

    class _Provider:
        provider_name = "local_stub"
        model_name = "stub-model"

        def is_enabled(self):
            return True, ""

        def recommend(self, **_kwargs):
            raise AssertionError("provider fallback should not run when deterministic recommendation is ready")

    monkeypatch.setattr(proof_runner.ProofRunner, "_build_provider", lambda self, args: _Provider())

    args = SimpleNamespace(
        dashboard_url="http://127.0.0.1:8860",
        contract=str(CONTRACT_PATH),
        provider="local_stub",
        model="stub-model",
        reasoning_effort="medium",
        scenario_id="llm_turn_then_go_proof",
        scenario_label="LLM Turn + Go",
        artifact_kind="llm_turn_then_go_proof",
        task="turn until the ball is visible",
        timeout_s=1.0,
        environment_timeout_s=1.0,
        target_model_sdf=str(REPO_ROOT / "ros2_config" / "frisbee_target_ball.sdf"),
        target_model_name="llm_turn_then_go_target",
        target_behind_m=1.1,
        target_lateral_m=0.0,
        target_z_m=0.05,
        start_visible=False,
        max_runtime_s=0.01,
        poll_s=0.01,
        dispatch_cooldown_s=0.0,
        skip_search_requirement=False,
        keep_environment=True,
    )
    runner = proof_runner.ProofRunner(args)

    ready_state = {
        "control_plane_ready": True,
        "environment_state": "environment_ready",
        "scenario_state": "ready",
        "session_id": "20260327T060000Z",
        "compose_project": "chasecar_dashboard_20260327t060000z",
        "world_name": "yolo_test_world",
        "belief": {"latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0}, "latest_target_distance_m": 1.2},
        "perception": {"detection_topic_seen": True, "target_visible_now": False},
        "brain": {
            "search_active": False,
            "target_locked": False,
            "target_visible_recent": False,
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

    monkeypatch.setattr(runner, "_ensure_environment_ready", lambda: (ready_state, False))
    monkeypatch.setattr(runner, "_wait_for_robot_pose", lambda timeout_s: ready_state)
    monkeypatch.setattr(
        runner,
        "_spawn_target_relative_to_robot",
        lambda state, proof_root: {
            "robot_pose_after_turnaway": {"yaw": 0.0},
            "target_world": {"x": 1.1, "y": 0.0, "z": 0.05},
            "pass": True,
        },
    )
    monkeypatch.setattr(runner, "_wait_for_robot_yaw", lambda expected_yaw, timeout_s: ready_state)
    monkeypatch.setattr(runner, "_request", lambda method, path, payload=None, timeout_s=None: (202, {"accepted": True, "message": "queued"}))
    monkeypatch.setattr(proof_runner, "fetch_dashboard_state", lambda dashboard_url, timeout_s: ready_state)
    monkeypatch.setattr(
        proof_runner,
        "attempt_deterministic_recommendation",
        lambda **_kwargs: SimpleNamespace(
            decision={
                "status": "recommendation",
                "task_text": "turn until the ball is visible",
                "intent": "search_for_target",
                "args": {"target_class": "ball"},
                "rationale_short": "The ball is not visible yet, so bounded search is next.",
                "missing_prerequisites": [],
                "expected_observations": [],
                "confidence": 1.0,
            },
            preview_status=200,
            preview_payload={
                "preview": {
                    "contract_valid": True,
                    "ready_to_dispatch": True,
                    "payload": {"intent": "search_for_target", "args": {"target_class": "ball"}},
                    "readiness": {"ready_to_dispatch": True, "missing_keys": []},
                    "expected_boundary_activity": [],
                }
            },
            evaluation_kind="deterministic_recommendation",
        ),
    )
    monkeypatch.setattr(
        proof_runner,
        "dispatch_intent",
        lambda dashboard_url, intent, args, timeout_s: (202, {"accepted": True, "message": "intent queued"}),
    )
    monotonic_values = iter([0.0, 1.0, 2.0, 3.0, 4.0, 6.0])
    monkeypatch.setattr(proof_runner.time, "monotonic", lambda: next(monotonic_values, 6.0))
    monkeypatch.setattr(proof_runner.time, "sleep", lambda *_args, **_kwargs: None)

    result = runner.run()

    decision_history = Path(result["proof_root"]) / "decision_history.jsonl"
    lines = [line for line in decision_history.read_text(encoding="utf-8").splitlines() if line.strip()]
    evaluation_entries = [entry for entry in lines if "deterministic_recommendation" in entry]

    assert result["pass"] is False
    assert evaluation_entries
    assert any('"evaluation_kind": "deterministic_recommendation"' in entry for entry in evaluation_entries)
    assert any('"provider": "deterministic_recommendation"' in entry for entry in evaluation_entries)
