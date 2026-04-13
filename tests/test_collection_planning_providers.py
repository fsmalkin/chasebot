from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from llm_provider_base import ProviderError  # noqa: E402
from llm_provider_local import LocalStubProvider  # noqa: E402
from llm_provider_openai import OpenAIResponsesProvider  # noqa: E402


def test_openai_provider_plan_collection_route_validates_response(monkeypatch):
    provider = OpenAIResponsesProvider(api_key="test-key", model="test-model")

    def mock_call(**_kwargs):
        return {
            "output": [
                {
                    "type": "function_call",
                    "name": "plan_collection_route",
                    "arguments": '{"target_order": ["ball_b", "ball_a"], "rationale_short": "start center"}',
                }
            ]
        }

    monkeypatch.setattr("llm_provider_openai.call_openai_responses", mock_call)

    result = provider.plan_collection_route(
        remaining_target_ids=["ball_a", "ball_b"],
        target_details=[],
        zone_details={"world_x": 2.4, "world_y": 0.0, "radius_m": 0.2},
        placed_targets=[],
        mission_state={},
        timeout_s=10.0,
    )
    assert result == ["ball_b", "ball_a"]

    def mock_call_bad(**_kwargs):
        return {
            "output": [
                {
                    "type": "function_call",
                    "name": "plan_collection_route",
                    "arguments": '{"target_order": ["ball_b"], "rationale_short": "oops"}',
                }
            ]
        }

    monkeypatch.setattr("llm_provider_openai.call_openai_responses", mock_call_bad)

    with pytest.raises(ProviderError, match="expected exactly"):
        provider.plan_collection_route(
            remaining_target_ids=["ball_a", "ball_b"],
            target_details=[],
            zone_details={"world_x": 2.4, "world_y": 0.0, "radius_m": 0.2},
            placed_targets=[],
            mission_state={},
            timeout_s=10.0,
        )


def test_local_stub_provider_plan_collection_route_uses_env(monkeypatch):
    provider = LocalStubProvider(model="local-stub")
    monkeypatch.setenv("CHASECAR_LOCAL_STUB_COLLECTION_ROUTE_JSON", '["ball_b","ball_a"]')

    result = provider.plan_collection_route(
        remaining_target_ids=["ball_a", "ball_b"],
        target_details=[],
        zone_details={},
        placed_targets=[],
        mission_state={},
        timeout_s=1.0,
    )

    assert result == ["ball_b", "ball_a"]


def test_local_stub_provider_plan_collection_route_defaults_to_remaining_ids(monkeypatch):
    provider = LocalStubProvider(model="local-stub")
    monkeypatch.delenv("CHASECAR_LOCAL_STUB_COLLECTION_ROUTE_JSON", raising=False)

    result = provider.plan_collection_route(
        remaining_target_ids=["ball_a", "ball_b"],
        target_details=[],
        zone_details={},
        placed_targets=[],
        mission_state={},
        timeout_s=1.0,
    )

    assert result == ["ball_a", "ball_b"]
