from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import brain_llm_recommender as recommender  # noqa: E402


CONTRACT_PATH = REPO_ROOT / "runtime" / "contracts" / "llm_control_contract.yaml"


def load_contract():
    return recommender.load_contract(CONTRACT_PATH)


def ready_state() -> dict[str, object]:
    return {
        "control_plane_ready": True,
        "environment_state": "environment_ready",
        "scenario_state": "ready",
        "session_id": "20260314T123456Z",
        "phase": "environment_ready",
        "target_id": "",
        "target_transition_active": False,
        "last_result": "",
        "last_feedback": "",
        "perception": {
            "detection_topic_seen": True,
            "target_visible_now": True,
            "target_visible_ratio": 0.42,
            "latest_detection_world": {"x": 1.1, "y": 0.0},
            "truth_status": "aligned",
        },
        "belief": {
            "latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
            "latest_goal_pose": {"x": 1.0, "y": 0.0, "yaw": 0.0},
            "latest_target_distance_m": 1.1,
            "distance_trend": "shrinking",
        },
        "outcome": {
            "feedback_recent": True,
            "nav_goal_recent": True,
            "cmd_vel_recent": False,
            "boundary_activity_seen": True,
        },
        "decision": {},
    }


def preview_ready(intent: str, args: dict[str, object]) -> tuple[int, dict[str, object]]:
    return (
        200,
        {
            "accepted": True,
            "preview": {
                "contract_valid": True,
                "ready_to_dispatch": True,
                "intent": intent,
                "args": args,
                "payload": {"intent": intent, "args": args, "seq": 1},
                "readiness": {"ready_to_dispatch": True, "missing_keys": []},
                "expected_boundary_activity": ["feedback on /chasecar/brain/feedback"],
            },
        },
    )


def function_call_response(payload: dict[str, object]) -> dict[str, object]:
    return {
        "output": [
            {
                "type": "function_call",
                "name": "emit_frozen_decision",
                "arguments": json.dumps(payload),
                "status": "completed",
            }
        ]
    }


def test_validate_decision_accepts_valid_recommendation():
    contract = load_contract()
    decision = recommender.validate_decision_against_contract(
        {
            "status": "recommendation",
            "task_text": "go get the ball",
            "intent": "plan_to_target",
            "args": {"approach_distance_m": 0.25},
            "rationale_short": "Target is already visible and planning is the next step.",
            "missing_prerequisites": [],
            "expected_observations": ["nav goal activity"],
            "confidence": 0.8,
        },
        contract,
    )
    assert decision["intent"] == "plan_to_target"
    assert decision["args"]["approach_distance_m"] == 0.25


def test_validate_decision_rejects_unknown_intent():
    contract = load_contract()
    with pytest.raises(ValueError, match="outside frozen contract"):
        recommender.validate_decision_against_contract(
            {
                "status": "recommendation",
                "task_text": "do something novel",
                "intent": "invent_new_behavior",
                "args": {},
                "rationale_short": "bad",
                "missing_prerequisites": [],
                "expected_observations": [],
                "confidence": 0.2,
            },
            contract,
        )


def test_validate_decision_rejects_missing_required_args():
    contract = load_contract()
    with pytest.raises(ValueError, match="Missing required args"):
        recommender.validate_decision_against_contract(
            {
                "status": "recommendation",
                "task_text": "plan to the target",
                "intent": "plan_to_target",
                "args": {},
                "rationale_short": "bad",
                "missing_prerequisites": [],
                "expected_observations": [],
                "confidence": 0.2,
            },
            contract,
        )


def test_validate_decision_rejects_extra_args():
    contract = load_contract()
    with pytest.raises(ValueError, match="Unexpected args"):
        recommender.validate_decision_against_contract(
            {
                "status": "recommendation",
                "task_text": "acquire the ball",
                "intent": "acquire_target",
                "args": {"target_class": "ball", "speed": "fast"},
                "rationale_short": "bad",
                "missing_prerequisites": [],
                "expected_observations": [],
                "confidence": 0.2,
            },
            contract,
        )


def test_run_recommendation_blocks_when_environment_not_ready(tmp_path, monkeypatch):
    monkeypatch.setattr(recommender, "fetch_dashboard_state", lambda dashboard_url, timeout_s: {
        "control_plane_ready": True,
        "environment_state": "stopped",
        "session_id": "",
    })

    result = recommender.run_recommendation(
        task_text="track the target",
        contract_path=CONTRACT_PATH,
        repo_root=tmp_path,
        openai_api_key="test-key",
    )

    summary = result["summary"]
    assert result["exit_code"] == 0
    assert summary["decision"]["status"] == "blocked"
    assert "environment_ready" in summary["decision"]["missing_prerequisites"]
    assert Path(result["artifacts"]["summary_path"]).exists()


def test_run_recommendation_recommends_and_dispatches_when_approved(tmp_path, monkeypatch):
    monkeypatch.setattr(recommender, "fetch_dashboard_state", lambda dashboard_url, timeout_s: ready_state())
    monkeypatch.setattr(
        recommender,
        "call_openai_responses",
        lambda **kwargs: function_call_response(
            {
                "status": "recommendation",
                "task_text": "plan toward the visible ball",
                "intent": "plan_to_target",
                "args": {"approach_distance_m": 0.25},
                "rationale_short": "The target is visible and planning is the next safe step.",
                "missing_prerequisites": [],
                "expected_observations": ["nav goal activity", "feedback on /chasecar/brain/feedback"],
                "confidence": 0.82,
            }
        ),
    )
    monkeypatch.setattr(recommender, "preview_intent", lambda dashboard_url, intent, args, timeout_s: preview_ready(intent, args))
    monkeypatch.setattr(
        recommender,
        "dispatch_intent",
        lambda dashboard_url, intent, args, timeout_s: (202, {"accepted": True, "message": "intent queued"}),
    )

    result = recommender.run_recommendation(
        task_text="plan toward the visible ball",
        contract_path=CONTRACT_PATH,
        repo_root=tmp_path,
        openai_api_key="test-key",
        approve=True,
    )

    summary = result["summary"]
    assert result["exit_code"] == 0
    assert summary["decision"]["status"] == "recommendation"
    assert summary["decision"]["intent"] == "plan_to_target"
    assert summary["approved"] is True
    assert summary["dispatch_status"] == 202
    assert Path(result["artifacts"]["dispatch_path"]).exists()


def test_run_recommendation_blocks_when_preview_is_not_ready(tmp_path, monkeypatch):
    monkeypatch.setattr(recommender, "fetch_dashboard_state", lambda dashboard_url, timeout_s: ready_state())
    monkeypatch.setattr(
        recommender,
        "call_openai_responses",
        lambda **kwargs: function_call_response(
            {
                "status": "recommendation",
                "task_text": "track the target",
                "intent": "track_target",
                "args": {},
                "rationale_short": "Tracking should continue the current pursuit.",
                "missing_prerequisites": [],
                "expected_observations": ["continued cmd_vel activity"],
                "confidence": 0.71,
            }
        ),
    )
    monkeypatch.setattr(
        recommender,
        "preview_intent",
        lambda dashboard_url, intent, args, timeout_s: (
            200,
            {
                "preview": {
                    "contract_valid": True,
                    "ready_to_dispatch": False,
                    "readiness": {"ready_to_dispatch": False, "missing_keys": ["cmd_vel_recent"]},
                    "expected_boundary_activity": ["continued cmd_vel activity"],
                }
            },
        ),
    )

    result = recommender.run_recommendation(
        task_text="track the target",
        contract_path=CONTRACT_PATH,
        repo_root=tmp_path,
        openai_api_key="test-key",
    )

    summary = result["summary"]
    assert summary["decision"]["status"] == "blocked"
    assert "cmd_vel_recent" in summary["decision"]["missing_prerequisites"]
    assert summary["approved"] is False
    assert summary["dispatch_status"] == 0


def test_run_recommendation_uses_deterministic_fast_path_without_openai_key(tmp_path, monkeypatch):
    state = ready_state()
    state["perception"]["target_visible_now"] = False
    state["perception"]["latest_detection_world"] = None
    state["belief"]["latest_goal_pose"] = None
    state["sim_gate_ready"] = True
    state["outcome"] = {
        "feedback_recent": False,
        "nav_goal_recent": False,
        "cmd_vel_recent": False,
        "boundary_activity_seen": False,
    }
    state["brain"] = {
        "target_locked": False,
        "track_active": False,
        "goal_in_progress": False,
        "search_active": False,
        "target_visible_recent": False,
    }

    openai_called = {"value": False}

    def _unexpected_openai_call(**_kwargs):
        openai_called["value"] = True
        raise AssertionError("OpenAI provider should not be called when the deterministic path is valid.")

    monkeypatch.setattr(recommender, "fetch_dashboard_state", lambda dashboard_url, timeout_s: state)
    monkeypatch.setattr(recommender, "call_openai_responses", _unexpected_openai_call)
    monkeypatch.setattr(
        recommender,
        "attempt_deterministic_recommendation",
        lambda **_kwargs: SimpleNamespace(
            decision={
                "status": "recommendation",
                "task_text": "turn until the ball is visible",
                "intent": "search_for_target",
                "args": {"target_class": "ball"},
                "rationale_short": "The target is not visible yet, so bounded search is next.",
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
        recommender,
        "dispatch_intent",
        lambda dashboard_url, intent, args, timeout_s: (202, {"accepted": True, "message": "intent queued"}),
    )

    result = recommender.run_recommendation(
        task_text="turn until the ball is visible",
        contract_path=CONTRACT_PATH,
        repo_root=tmp_path,
        approve=True,
    )

    summary = result["summary"]
    assert result["exit_code"] == 0
    assert openai_called["value"] is False
    assert summary["decision"]["status"] == "recommendation"
    assert summary["decision"]["intent"] == "search_for_target"
    assert summary["decision"]["args"] == {"target_class": "ball"}
    assert summary["evaluation_kind"] == "deterministic_recommendation"
    assert summary["approved"] is True
    assert summary["dispatch_status"] == 202


def test_run_recommendation_blocks_on_malformed_model_output(tmp_path, monkeypatch):
    monkeypatch.setattr(recommender, "fetch_dashboard_state", lambda dashboard_url, timeout_s: ready_state())
    monkeypatch.setattr(
        recommender,
        "call_openai_responses",
        lambda **kwargs: {
            "output": [
                {
                    "type": "function_call",
                    "name": "emit_frozen_decision",
                    "arguments": "{not-json",
                }
            ]
        },
    )

    result = recommender.run_recommendation(
        task_text="acquire the target",
        contract_path=CONTRACT_PATH,
        repo_root=tmp_path,
        openai_api_key="test-key",
    )

    summary = result["summary"]
    assert result["exit_code"] == 2
    assert summary["decision"]["status"] == "blocked"
    assert "model_output_invalid" in summary["decision"]["missing_prerequisites"]
    assert summary["hard_error"]
