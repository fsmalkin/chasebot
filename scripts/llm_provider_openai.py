#!/usr/bin/env python3
"""OpenAI Responses provider for bounded frozen-intent decisions."""

from __future__ import annotations

import json
from typing import Any, Dict

from brain_state_digest import CANONICAL_ARGS_BY_INTENT
from llm_provider_base import ProviderDecisionResult, ProviderError
from llm_supervisor_core import (
    DEFAULT_OPENAI_BASE_URL,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_REASONING_EFFORT,
    allowed_intent_names,
    http_json,
    normalize_openai_base_url,
)


TOOL_NAME = "emit_frozen_decision"


def decision_schema(contract: Dict[str, Any]) -> Dict[str, Any]:
    intent_enum = [""] + allowed_intent_names(contract)
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "status",
            "task_text",
            "intent",
            "args",
            "rationale_short",
            "missing_prerequisites",
            "expected_observations",
            "confidence",
        ],
        "properties": {
            "status": {"type": "string", "enum": ["recommendation", "blocked"]},
            "task_text": {"type": "string"},
            "intent": {"type": "string", "enum": intent_enum},
            "args": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "target_class": {"type": "string", "enum": ["ball"]},
                    "approach_distance_m": {"type": "number", "enum": [0.25]},
                },
            },
            "rationale_short": {"type": "string"},
            "missing_prerequisites": {"type": "array", "items": {"type": "string"}},
            "expected_observations": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        },
    }


def build_supervisor_prompt(task_text: str, digest: Dict[str, Any]) -> str:
    return (
        "Task:\n"
        f"{task_text.strip()}\n\n"
        "Current fixed-shape dashboard digest:\n"
        f"{json.dumps(digest, indent=2, sort_keys=True)}\n\n"
        "Choose exactly one bounded frozen decision via the function tool. "
        "If the state is not actionable, uncertain, or unsafe, emit blocked."
    )


def build_openai_request(
    *,
    model: str,
    reasoning_effort: str,
    task_text: str,
    digest: Dict[str, Any],
    contract: Dict[str, Any],
) -> Dict[str, Any]:
    tool = {
        "type": "function",
        "name": TOOL_NAME,
        "description": (
            "Emit exactly one bounded frozen robot decision. "
            "Allowed recommendations are acquire_target(ball), plan_to_target(0.25), "
            "track_target(), abort(), safe_stop(), or blocked."
        ),
        "strict": True,
        "parameters": decision_schema(contract),
    }
    return {
        "model": model,
        "store": False,
        "parallel_tool_calls": False,
        "reasoning": {"effort": reasoning_effort},
        "instructions": (
            "You are a read-only shadow supervisor for a robot operator console. "
            "You must use the emit_frozen_decision function. "
            "Do not invent actions, do not plan multiple steps, and use only canonical arguments: "
            f"{json.dumps(CANONICAL_ARGS_BY_INTENT, sort_keys=True)}. "
            "When the state is not ready or you are unsure, return blocked."
        ),
        "input": build_supervisor_prompt(task_text, digest),
        "tool_choice": "required",
        "tools": [tool],
    }


def call_openai_responses(
    *,
    api_key: str,
    request_payload: Dict[str, Any],
    base_url: str,
    timeout_s: float,
    org_id: str = "",
    project_id: str = "",
) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if org_id:
        headers["OpenAI-Organization"] = org_id
    if project_id:
        headers["OpenAI-Project"] = project_id
    status, payload = http_json(
        normalize_openai_base_url(base_url),
        method="POST",
        payload=request_payload,
        headers=headers,
        timeout_s=timeout_s,
    )
    if status != 200:
        error_text = payload.get("error") if isinstance(payload, dict) else payload
        raise ProviderError(f"OpenAI Responses request failed with status {status}: {error_text}")
    return payload


def extract_tool_decision(raw_response: Dict[str, Any]) -> Dict[str, Any]:
    for item in list(raw_response.get("output", [])):
        if not isinstance(item, dict):
            continue
        if item.get("type") != "function_call":
            continue
        if str(item.get("name", "")).strip() != TOOL_NAME:
            continue
        arguments = item.get("arguments", "")
        if not isinstance(arguments, str) or not arguments.strip():
            raise ProviderError("Function call did not contain JSON arguments.")
        try:
            payload = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"Function call arguments were not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ProviderError("Function call arguments must decode to an object.")
        return payload
    raise ProviderError("OpenAI response did not contain the required function call.")


class OpenAIResponsesProvider:
    provider_name = "openai_responses"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_OPENAI_MODEL,
        reasoning_effort: str = DEFAULT_REASONING_EFFORT,
        base_url: str = DEFAULT_OPENAI_BASE_URL,
        org_id: str = "",
        project_id: str = "",
    ) -> None:
        self.api_key = api_key.strip()
        self.model_name = model.strip() or DEFAULT_OPENAI_MODEL
        self.reasoning_effort = reasoning_effort.strip() or DEFAULT_REASONING_EFFORT
        self.base_url = base_url.strip() or DEFAULT_OPENAI_BASE_URL
        self.org_id = org_id.strip()
        self.project_id = project_id.strip()

    def is_enabled(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, "OPENAI_API_KEY is not set."
        return True, ""

    def recommend(
        self,
        *,
        task_text: str,
        digest: Dict[str, Any],
        contract: Dict[str, Any],
        timeout_s: float,
    ) -> ProviderDecisionResult:
        request_payload = build_openai_request(
            model=self.model_name,
            reasoning_effort=self.reasoning_effort,
            task_text=task_text,
            digest=digest,
            contract=contract,
        )
        response_payload = call_openai_responses(
            api_key=self.api_key,
            request_payload=request_payload,
            base_url=self.base_url,
            timeout_s=timeout_s,
            org_id=self.org_id,
            project_id=self.project_id,
        )
        decision = extract_tool_decision(response_payload)
        return ProviderDecisionResult(
            decision=decision,
            request_payload=request_payload,
            response_payload=response_payload,
            provider=self.provider_name,
            model=self.model_name,
        )
