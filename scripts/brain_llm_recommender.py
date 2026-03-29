#!/usr/bin/env python3
"""Headless frozen-intent recommendation helpers backed by OpenAI Responses."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from brain_state_digest import build_state_digest
from llm_provider_openai import build_openai_request, call_openai_responses, extract_tool_decision
from llm_supervisor_core import (
    DEFAULT_DASHBOARD_URL,
    DEFAULT_OPENAI_BASE_URL,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_REASONING_EFFORT,
    RECOMMENDATION_TYPE,
    REPO_ROOT,
    RunArtifacts,
    attempt_deterministic_recommendation,
    allowed_intent_names,
    append_jsonl,
    blocked_decision,
    blocked_from_preview,
    contract_intents_by_name as _contract_intents_by_name,
    decision_signature,
    dispatch_intent,
    fetch_dashboard_state,
    load_contract,
    normalize_model_decision,
    normalize_openai_base_url,
    preview_intent,
    preview_summary,
    resolve_recommendation_artifacts,
    utc_now,
    validate_decision_against_canonical_space,
    validate_decision_against_contract,
    write_json,
)


def contract_intents_by_name(contract: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return _contract_intents_by_name(contract)


def recommendation_schema(contract: Dict[str, Any]) -> Dict[str, Any]:
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
            "args": {"type": "object"},
            "rationale_short": {"type": "string"},
            "missing_prerequisites": {"type": "array", "items": {"type": "string"}},
            "expected_observations": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        },
    }


def capability_limits() -> Dict[str, Any]:
    digest = build_state_digest({}, {"intents": []})
    return dict(digest.get("capability_limits", {}))


def compact_state_context(state: Dict[str, Any], contract: Dict[str, Any]) -> Dict[str, Any]:
    return build_state_digest(state, contract)


def recommendation_prompt(task_text: str, state: Dict[str, Any], contract: Dict[str, Any]) -> str:
    context = compact_state_context(state, contract)
    return (
        "Task request:\n"
        f"{task_text.strip()}\n\n"
        "Current dashboard context:\n"
        f"{json.dumps(context, indent=2, sort_keys=True)}\n\n"
        "Return exactly one frozen intent recommendation or a blocked result.\n"
        "If prerequisites are missing, return status=blocked.\n"
        "Never recommend environment control, scenario launch, or any intent outside the frozen set."
    )


def resolve_artifacts(repo_root: Path, session_id: str) -> RunArtifacts:
    return resolve_recommendation_artifacts(repo_root, session_id)


def approval_requested(*, approve: bool, prompt_approve: bool, decision: Dict[str, Any], preview: Dict[str, Any]) -> bool:
    if not (decision.get("status") == "recommendation" and preview.get("ready_to_dispatch")):
        return False
    if approve:
        return True
    if not prompt_approve:
        return False
    reply = input(
        f"Approve dispatch of {decision['intent']} {json.dumps(decision['args'], sort_keys=True)}? [y/N]: "
    ).strip().lower()
    return reply in {"y", "yes"}


def run_recommendation(
    *,
    task_text: str,
    contract_path: Path,
    dashboard_url: str = DEFAULT_DASHBOARD_URL,
    repo_root: Path = REPO_ROOT,
    approve: bool = False,
    prompt_approve: bool = False,
    model: str = DEFAULT_OPENAI_MODEL,
    reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    openai_api_key: str = "",
    openai_base_url: str = DEFAULT_OPENAI_BASE_URL,
    openai_org_id: str = "",
    openai_project_id: str = "",
    timeout_s: float = 45.0,
) -> Dict[str, Any]:
    contract = load_contract(contract_path)
    dashboard_url = dashboard_url.rstrip("/")
    state: Dict[str, Any] = {}
    preview_payload: Dict[str, Any] = {}
    preview_status = 0
    raw_response: Dict[str, Any] = {}
    openai_request: Dict[str, Any] = {}
    decision: Dict[str, Any] = {}
    dispatch_payload: Dict[str, Any] = {}
    dispatch_status = 0
    hard_error = ""
    evaluation_kind = "provider"
    deterministic = None

    try:
        state = fetch_dashboard_state(dashboard_url, timeout_s=timeout_s)
    except Exception as exc:
        hard_error = str(exc)
        state = {
            "control_plane_ready": False,
            "environment_state": "unknown",
            "session_id": "",
        }

    artifacts = resolve_artifacts(repo_root, str(state.get("session_id", "")))
    digest = build_state_digest(state, contract)
    request_snapshot = {
        "generated_utc": utc_now(),
        "type": RECOMMENDATION_TYPE,
        "task_text": task_text,
        "dashboard_url": dashboard_url,
        "contract_path": str(contract_path),
        "model": model,
        "reasoning_effort": reasoning_effort,
        "state_excerpt": compact_state_context(state, contract) if state else {},
        "capability_limits": capability_limits(),
    }

    if hard_error:
        decision = blocked_decision(
            task_text,
            "Dashboard control plane unavailable.",
            missing_prerequisites=["dashboard_unavailable"],
        )
    elif not bool(state.get("control_plane_ready", False)):
        decision = blocked_decision(
            task_text,
            str(state.get("control_plane_error") or "Dashboard control plane unavailable."),
            missing_prerequisites=["control_plane_unavailable"],
        )
    elif str(state.get("environment_state", "")) != "environment_ready":
        decision = blocked_decision(
            task_text,
            "Environment is not ready for frozen intent recommendation.",
            missing_prerequisites=["environment_ready"],
        )
    else:
        deterministic = attempt_deterministic_recommendation(
            task_text=task_text,
            state=state,
            contract=contract,
            dashboard_url=dashboard_url,
            timeout_s=timeout_s,
            digest=digest,
        )
        if deterministic is not None:
            decision = dict(deterministic.decision)
            preview_status = deterministic.preview_status
            preview_payload = dict(deterministic.preview_payload)
            evaluation_kind = deterministic.evaluation_kind
        elif not openai_api_key:
            hard_error = "OPENAI_API_KEY is required."
            decision = blocked_decision(
                task_text,
                "OpenAI configuration is missing.",
                missing_prerequisites=["OPENAI_API_KEY"],
            )
        else:
            openai_request = build_openai_request(
                model=model,
                reasoning_effort=reasoning_effort,
                task_text=task_text,
                digest=digest,
                contract=contract,
            )
            request_snapshot["openai_request"] = openai_request
            try:
                raw_response = call_openai_responses(
                    api_key=openai_api_key,
                    request_payload=openai_request,
                    base_url=normalize_openai_base_url(openai_base_url),
                    timeout_s=timeout_s,
                    org_id=openai_org_id,
                    project_id=openai_project_id,
                )
                parsed = extract_tool_decision(raw_response, task_text=task_text)
                decision = normalize_model_decision(parsed)
                decision = validate_decision_against_contract(decision, contract)
                decision = validate_decision_against_canonical_space(decision)
            except Exception as exc:
                hard_error = str(exc)
                decision = blocked_decision(
                    task_text,
                    "Model output could not be validated.",
                    missing_prerequisites=["model_output_invalid"],
                )

    if decision.get("status") == "recommendation" and deterministic is None:
        preview_status, preview_payload = preview_intent(
            dashboard_url,
            str(decision.get("intent", "")),
            dict(decision.get("args", {})),
            timeout_s=timeout_s,
        )
        summary = preview_summary(preview_status, preview_payload)
        if preview_status != 200 or not summary["contract_valid"] or not summary["ready_to_dispatch"]:
            decision = blocked_from_preview(
                task_text=task_text,
                decision=decision,
                preview_status=preview_status,
                preview_payload=preview_payload,
            )

    approved = approval_requested(
        approve=approve,
        prompt_approve=prompt_approve,
        decision=decision,
        preview=preview_payload.get("preview", {}) if isinstance(preview_payload, dict) else {},
    )
    if approved:
        dispatch_status, dispatch_payload = dispatch_intent(
            dashboard_url,
            str(decision.get("intent", "")),
            dict(decision.get("args", {})),
            timeout_s=timeout_s,
        )

    response_snapshot = {
        "generated_utc": utc_now(),
        "openai_response": raw_response,
        "hard_error": hard_error,
        "preview_status": preview_status,
        "preview_payload": preview_payload,
        "dispatch_status": dispatch_status,
        "dispatch_payload": dispatch_payload,
        "evaluation_kind": evaluation_kind,
    }
    request_snapshot["evaluation_kind"] = evaluation_kind
    summary = {
        "generated_utc": utc_now(),
        "type": RECOMMENDATION_TYPE,
        "dashboard_url": dashboard_url,
        "contract_path": str(contract_path),
        "contract_status": str(contract.get("contract_status", "")),
        "session_id": str(state.get("session_id", "")),
        "task_text": task_text,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "state_excerpt": compact_state_context(state, contract) if state else {},
        "decision": decision,
        "decision_signature": decision_signature(decision),
        "preview_status": preview_status,
        "preview": preview_summary(preview_status, preview_payload),
        "evaluation_kind": evaluation_kind,
        "approved": bool(approved),
        "dispatch_status": dispatch_status,
        "dispatch_payload": dispatch_payload,
        "hard_error": hard_error,
        "pass": bool(decision.get("status") in {"recommendation", "blocked"} and not hard_error),
    }

    write_json(artifacts.request_path, request_snapshot)
    write_json(artifacts.response_path, response_snapshot)
    write_json(artifacts.summary_path, summary)
    append_jsonl(
        artifacts.history_path,
        {
            "event_type": "recommendation",
            "generated_utc": summary["generated_utc"],
            "task_text": task_text,
            "session_id": str(state.get("session_id", "")),
            "decision_status": decision.get("status", ""),
            "intent": decision.get("intent", ""),
            "approved": bool(approved),
            "evaluation_kind": evaluation_kind,
            "summary_path": str(artifacts.summary_path),
        },
    )

    if approved:
        dispatch_summary = {
            "generated_utc": utc_now(),
            "type": "brain_llm_dispatch",
            "task_text": task_text,
            "session_id": str(state.get("session_id", "")),
            "decision": decision,
            "dispatch_status": dispatch_status,
            "dispatch_payload": dispatch_payload,
            "pass": dispatch_status == 202 and bool(dispatch_payload.get("accepted", False)),
        }
        write_json(artifacts.dispatch_path, dispatch_summary)
        append_jsonl(
            artifacts.history_path,
            {
                "event_type": "dispatch",
                "generated_utc": dispatch_summary["generated_utc"],
                "task_text": task_text,
                "session_id": str(state.get("session_id", "")),
                "intent": decision.get("intent", ""),
                "dispatch_status": dispatch_status,
                "summary_path": str(artifacts.dispatch_path),
            },
        )

    return {
        "summary": summary,
        "artifacts": {
            "request_path": str(artifacts.request_path),
            "response_path": str(artifacts.response_path),
            "summary_path": str(artifacts.summary_path),
            "dispatch_path": str(artifacts.dispatch_path) if approved else "",
            "history_path": str(artifacts.history_path),
        },
        "exit_code": 2 if hard_error else 0,
    }
