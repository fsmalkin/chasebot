from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import brain_supervisor_loop as supervisor_loop  # noqa: E402
from brain_state_digest import build_state_digest, state_digest_hash  # noqa: E402
from llm_supervisor_core import load_contract, read_jsonl, resolve_supervisor_artifacts  # noqa: E402


CONTRACT_PATH = REPO_ROOT / "runtime" / "contracts" / "llm_control_contract.yaml"


class FakeProvider:
    provider_name = "fake_provider"

    def __init__(self, decision: dict[str, object]) -> None:
        self.model_name = "fake-model"
        self.decision = decision
        self.calls = 0

    def is_enabled(self) -> tuple[bool, str]:
        return True, ""

    def recommend(self, *, task_text, digest, contract, timeout_s):
        self.calls += 1
        return type(
            "ProviderResult",
            (),
            {
                "decision": self.decision,
                "request_payload": {"task_text": task_text, "state_hash": state_digest_hash(digest)},
                "response_payload": {"decision": self.decision},
                "provider": self.provider_name,
                "model": self.model_name,
            },
        )()


def ready_state() -> dict[str, object]:
    return {
        "control_plane_ready": True,
        "environment_state": "environment_ready",
        "scenario_state": "ready",
        "session_id": "20260314T193000Z",
        "phase": "M3",
        "target_id": "single_target",
        "target_transition_active": False,
        "last_result": "",
        "last_feedback": "",
        "motion_evidence": True,
        "perception": {
            "detection_topic_seen": True,
            "target_visible_now": True,
            "target_visible_ratio": 0.65,
            "latest_detection_world": {"x": 1.0, "y": 0.0},
            "latest_truth_target_world": {"x": 1.0, "y": 0.0},
            "truth_alignment_ok": True,
            "truth_status": "aligned",
        },
        "belief": {
            "latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
            "latest_goal_pose": {"x": 0.8, "y": 0.0, "yaw": 0.0},
            "latest_target_distance_m": 1.0,
            "distance_trend": "shrinking",
        },
        "outcome": {
            "feedback_recent": True,
            "nav_goal_recent": True,
            "cmd_vel_recent": True,
            "boundary_activity_seen": True,
        },
    }


def test_state_digest_hash_is_stable_for_same_payload():
    contract = load_contract(CONTRACT_PATH)
    state = ready_state()
    digest_a = build_state_digest(state, contract)
    digest_b = build_state_digest(json.loads(json.dumps(state)), contract)
    assert digest_a == digest_b
    assert state_digest_hash(digest_a) == state_digest_hash(digest_b)


def test_supervisor_blocks_when_environment_not_ready(tmp_path, monkeypatch):
    captured_runtime: list[dict[str, object]] = []
    monkeypatch.setattr(
        supervisor_loop,
        "fetch_dashboard_state",
        lambda dashboard_url, timeout_s: {"control_plane_ready": True, "environment_state": "stopped", "session_id": ""},
    )
    monkeypatch.setattr(supervisor_loop, "write_supervisor_runtime_state", lambda payload: captured_runtime.append(payload))

    provider = FakeProvider({"status": "blocked", "task_text": "", "intent": "", "args": {}, "rationale_short": "", "missing_prerequisites": [], "expected_observations": [], "confidence": 0.0})
    controller = supervisor_loop.SupervisorController(
        provider=provider,
        contract_path=CONTRACT_PATH,
        dashboard_url="http://127.0.0.1:8860",
        repo_root=tmp_path,
        task_text="monitor and choose the next frozen intent",
        poll_s=1.0,
        max_staleness_s=8.0,
        timeout_s=1.0,
    )

    result = controller.evaluate_once()
    artifacts = resolve_supervisor_artifacts(tmp_path, "")
    latest = json.loads(artifacts.latest_path.read_text(encoding="utf-8"))

    assert result["status"] == "blocked"
    assert latest["decision"]["status"] == "blocked"
    assert "environment_ready" in latest["decision"]["missing_prerequisites"]
    assert provider.calls == 0
    assert captured_runtime[-1]["status"] == "blocked"


def test_supervisor_preview_block_turns_recommendation_into_blocked(tmp_path, monkeypatch):
    captured_runtime: list[dict[str, object]] = []
    monkeypatch.setattr(supervisor_loop, "fetch_dashboard_state", lambda dashboard_url, timeout_s: ready_state())
    monkeypatch.setattr(
        supervisor_loop,
        "preview_intent",
        lambda dashboard_url, intent, args, timeout_s: (
            200,
            {
                "preview": {
                    "contract_valid": True,
                    "ready_to_dispatch": False,
                    "readiness": {"ready_to_dispatch": False, "missing_keys": ["nav_goal_recent"]},
                    "expected_boundary_activity": ["nav goal activity"],
                }
            },
        ),
    )
    monkeypatch.setattr(supervisor_loop, "write_supervisor_runtime_state", lambda payload: captured_runtime.append(payload))

    provider = FakeProvider(
        {
            "status": "recommendation",
            "task_text": "plan",
            "intent": "plan_to_target",
            "args": {"approach_distance_m": 0.25},
            "rationale_short": "Planning is the next safe step.",
            "missing_prerequisites": [],
            "expected_observations": ["nav goal activity"],
            "confidence": 0.9,
        }
    )
    controller = supervisor_loop.SupervisorController(
        provider=provider,
        contract_path=CONTRACT_PATH,
        dashboard_url="http://127.0.0.1:8860",
        repo_root=tmp_path,
        task_text="monitor and choose the next frozen intent",
        poll_s=1.0,
        max_staleness_s=8.0,
        timeout_s=1.0,
    )

    result = controller.evaluate_once()
    artifacts = resolve_supervisor_artifacts(tmp_path, "20260314T193000Z")
    latest = json.loads(artifacts.latest_path.read_text(encoding="utf-8"))

    assert result["status"] == "blocked"
    assert latest["evaluation_kind"] == "preview_blocked"
    assert "nav_goal_recent" in latest["decision"]["missing_prerequisites"]
    assert provider.calls == 1
    assert captured_runtime[-1]["preview"]["ready_to_dispatch"] is False


def test_supervisor_suppresses_duplicate_provider_calls(tmp_path, monkeypatch):
    captured_runtime: list[dict[str, object]] = []
    monkeypatch.setattr(supervisor_loop, "fetch_dashboard_state", lambda dashboard_url, timeout_s: ready_state())
    monkeypatch.setattr(
        supervisor_loop,
        "preview_intent",
        lambda dashboard_url, intent, args, timeout_s: (
            200,
            {
                "preview": {
                    "contract_valid": True,
                    "ready_to_dispatch": True,
                    "readiness": {"ready_to_dispatch": True, "missing_keys": []},
                    "expected_boundary_activity": ["feedback on /chasecar/brain/feedback"],
                }
            },
        ),
    )
    monkeypatch.setattr(supervisor_loop, "write_supervisor_runtime_state", lambda payload: captured_runtime.append(payload))

    provider = FakeProvider(
        {
            "status": "recommendation",
            "task_text": "track",
            "intent": "track_target",
            "args": {},
            "rationale_short": "Tracking should continue.",
            "missing_prerequisites": [],
            "expected_observations": ["continued cmd_vel activity"],
            "confidence": 0.7,
        }
    )
    controller = supervisor_loop.SupervisorController(
        provider=provider,
        contract_path=CONTRACT_PATH,
        dashboard_url="http://127.0.0.1:8860",
        repo_root=tmp_path,
        task_text="monitor and choose the next frozen intent",
        poll_s=1.0,
        max_staleness_s=8.0,
        timeout_s=1.0,
    )

    first = controller.evaluate_once()
    second = controller.evaluate_once()
    artifacts = resolve_supervisor_artifacts(tmp_path, "20260314T193000Z")
    history = read_jsonl(artifacts.history_path)

    assert first["status"] == "recommendation"
    assert second["status"] == "recommendation"
    assert provider.calls == 1
    assert any(entry["event_type"] == "suppressed" for entry in history)
    assert captured_runtime[-1]["suppression_reason"] == "unchanged_state_within_staleness_window"
