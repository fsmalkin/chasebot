#!/usr/bin/env python3
"""OpenAI Responses provider for bounded frozen-intent decisions."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List

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


LEGACY_TOOL_NAME = "emit_frozen_decision"
BLOCKED_TOOL_NAME = "emit_blocked"
INTENT_TOOL_NAMES = {
    "search_for_target": "emit_search_for_target",
    "acquire_target": "emit_acquire_target",
    "plan_to_target": "emit_plan_to_target",
    "track_target": "emit_track_target",
    "abort": "emit_abort",
    "safe_stop": "emit_safe_stop",
}
TOOL_NAME_TO_INTENT = {tool_name: intent_name for intent_name, tool_name in INTENT_TOOL_NAMES.items()}


def _decision_metadata_properties() -> Dict[str, Dict[str, Any]]:
    return {
        "rationale_short": {"type": "string"},
        "missing_prerequisites": {"type": "array", "items": {"type": "string"}},
        "expected_observations": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    }


def _strict_schema(properties: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties.keys()),
        "properties": properties,
    }


def blocked_tool_schema() -> Dict[str, Any]:
    return _strict_schema(_decision_metadata_properties())


def intent_tool_schema(intent_name: str) -> Dict[str, Any]:
    properties = dict(_decision_metadata_properties())
    if intent_name in {"search_for_target", "acquire_target"}:
        properties["target_class"] = {"type": "string", "enum": ["ball"]}
    elif intent_name == "plan_to_target":
        properties["approach_distance_m"] = {"type": "number", "enum": [0.25]}
    return _strict_schema(properties)


def _tool_description(intent_name: str, description: str) -> str:
    canonical_args = CANONICAL_ARGS_BY_INTENT.get(intent_name, {})
    if canonical_args:
        canonical_text = json.dumps(canonical_args, sort_keys=True)
        return f"{description} Canonical args: {canonical_text}."
    return description


def _contract_descriptions(contract: Dict[str, Any]) -> Dict[str, str]:
    descriptions: Dict[str, str] = {}
    for item in list(contract.get("intents", [])):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        descriptions[name] = str(item.get("description", "")).strip()
    return descriptions


def _ready_intents_from_digest(digest: Dict[str, Any], contract: Dict[str, Any]) -> List[str]:
    allowed = set(allowed_intent_names(contract))
    ready: List[str] = []
    for item in list(digest.get("frozen_action_space", [])):
        if not isinstance(item, dict):
            continue
        intent_name = str(item.get("name", "")).strip()
        if intent_name not in allowed:
            continue
        gate_hint = item.get("gate_hint") if isinstance(item.get("gate_hint"), dict) else {}
        if gate_hint.get("ready"):
            ready.append(intent_name)
    return ready


def build_supervisor_prompt(task_text: str, digest: Dict[str, Any], ready_intents: Iterable[str]) -> str:
    return (
        "Task:\n"
        f"{task_text.strip()}\n\n"
        "Current fixed-shape dashboard digest:\n"
        f"{json.dumps(digest, indent=2, sort_keys=True)}\n\n"
        "Currently ready intents:\n"
        f"{json.dumps(list(ready_intents), indent=2)}\n\n"
        "Choose exactly one bounded decision via the provided function tools. "
        "If the state is not actionable, uncertain, or unsafe, use emit_blocked."
    )


def build_openai_request(
    *,
    model: str,
    reasoning_effort: str,
    task_text: str,
    digest: Dict[str, Any],
    contract: Dict[str, Any],
) -> Dict[str, Any]:
    descriptions = _contract_descriptions(contract)
    ready_intents = _ready_intents_from_digest(digest, contract)
    tools = [
        {
            "type": "function",
            "name": BLOCKED_TOOL_NAME,
            "description": "Return a blocked decision when no safe or valid frozen action should be taken.",
            "strict": True,
            "parameters": blocked_tool_schema(),
        }
    ]
    for intent_name in ready_intents:
        tool_name = INTENT_TOOL_NAMES.get(intent_name)
        if not tool_name:
            continue
        description = descriptions.get(intent_name, f"Emit {intent_name}.")
        tools.append(
            {
                "type": "function",
                "name": tool_name,
                "description": _tool_description(intent_name, description),
                "strict": True,
                "parameters": intent_tool_schema(intent_name),
            }
        )
    return {
        "model": model,
        "store": False,
        "parallel_tool_calls": False,
        "reasoning": {"effort": reasoning_effort},
        "instructions": (
            "You are a bounded robot supervisor. "
            "Use exactly one function tool. "
            "Only the tools currently provided are legal in this state. "
            "Do not invent actions, do not plan multiple steps, and use only canonical arguments. "
            "When the state is not ready or you are unsure, use emit_blocked."
        ),
        "input": build_supervisor_prompt(task_text, digest, ready_intents),
        "tool_choice": "required",
        "tools": tools,
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


def _parse_function_payload(arguments: Any) -> Dict[str, Any]:
    if not isinstance(arguments, str) or not arguments.strip():
        raise ProviderError("Function call did not contain JSON arguments.")
    try:
        payload = json.loads(arguments)
    except json.JSONDecodeError as exc:
        raise ProviderError(f"Function call arguments were not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProviderError("Function call arguments must decode to an object.")
    return payload


def _decision_from_tool_call(tool_name: str, payload: Dict[str, Any], task_text: str) -> Dict[str, Any]:
    if tool_name == LEGACY_TOOL_NAME:
        return payload

    decision = {
        "status": "blocked" if tool_name == BLOCKED_TOOL_NAME else "recommendation",
        "task_text": task_text,
        "intent": "",
        "args": {},
        "rationale_short": str(payload.get("rationale_short", "")),
        "missing_prerequisites": [str(item) for item in list(payload.get("missing_prerequisites", []))],
        "expected_observations": [str(item) for item in list(payload.get("expected_observations", []))],
        "confidence": float(payload.get("confidence", 0.0)),
    }
    if tool_name == BLOCKED_TOOL_NAME:
        return decision

    intent_name = TOOL_NAME_TO_INTENT.get(tool_name, "")
    if not intent_name:
        raise ProviderError(f"OpenAI response used an unknown tool: {tool_name}")
    decision["intent"] = intent_name
    if intent_name in {"search_for_target", "acquire_target"}:
        decision["args"] = {"target_class": str(payload.get("target_class", "")).strip()}
    elif intent_name == "plan_to_target":
        decision["args"] = {"approach_distance_m": float(payload.get("approach_distance_m", 0.25))}
    else:
        decision["args"] = {}
    return decision


def extract_tool_decision(raw_response: Dict[str, Any], *, task_text: str) -> Dict[str, Any]:
    for item in list(raw_response.get("output", [])):
        if not isinstance(item, dict):
            continue
        if item.get("type") != "function_call":
            continue
        tool_name = str(item.get("name", "")).strip()
        if tool_name not in {LEGACY_TOOL_NAME, BLOCKED_TOOL_NAME, *TOOL_NAME_TO_INTENT.keys()}:
            continue
        payload = _parse_function_payload(item.get("arguments", ""))
        return _decision_from_tool_call(tool_name, payload, task_text)
    raise ProviderError("OpenAI response did not contain a recognized function call.")


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
        decision = extract_tool_decision(response_payload, task_text=task_text)
        return ProviderDecisionResult(
            decision=decision,
            request_payload=request_payload,
            response_payload=response_payload,
            provider=self.provider_name,
            model=self.model_name,
        )
