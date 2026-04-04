#!/usr/bin/env python3
"""Shared helpers for the LLM recommender and shadow supervisor."""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

import yaml

from brain_state_digest import CANONICAL_ARGS_BY_INTENT
from brain_state_digest import build_state_digest


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = REPO_ROOT / "runtime" / "dashboard"
SUPERVISOR_RUNTIME_STATE_PATH = RUNTIME_DIR / "llm_supervisor_state.json"

DEFAULT_DASHBOARD_URL = "http://127.0.0.1:8860"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_MODEL = "gpt-5.4"
DEFAULT_REASONING_EFFORT = "medium"
DEFAULT_SHADOW_TASK_TEXT = (
    "Observe the current authoritative dashboard state and recommend at most one next frozen intent, "
    "or return blocked."
)
NO_SESSION_ID = "_no_session"
RECOMMENDATION_TYPE = "brain_llm_recommendation"


class RecommendationError(RuntimeError):
    """Raised when the recommender or supervisor cannot complete a deterministic flow."""


@dataclass(frozen=True)
class RunArtifacts:
    session_id: str
    root: Path
    request_path: Path
    response_path: Path
    summary_path: Path
    dispatch_path: Path
    history_path: Path


@dataclass(frozen=True)
class SupervisorArtifacts:
    session_id: str
    base_root: Path
    run_root: Path
    latest_path: Path
    history_path: Path
    digest_path: Path
    provider_request_path: Path
    provider_response_path: Path
    evaluation_path: Path


@dataclass(frozen=True)
class DeterministicRecommendation:
    decision: Dict[str, Any]
    preview_status: int
    preview_payload: Dict[str, Any]
    preview: Dict[str, Any]
    evaluation_kind: str = "deterministic_recommendation"
    preferred_intent: str = ""
    policy_stage: str = ""
    policy_reason: str = ""
    policy_snapshot: Dict[str, Any] | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def read_jsonl(path: Path, limit: int = 0) -> list[Dict[str, Any]]:
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception:
        return []
    if limit > 0:
        lines = lines[-limit:]
    payloads: list[Dict[str, Any]] = []
    for line in lines:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            payloads.append(item)
    return payloads


def normalize_openai_base_url(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return DEFAULT_OPENAI_BASE_URL
    if cleaned.endswith("/v1/responses"):
        return cleaned
    return cleaned.rstrip("/") + "/v1/responses"


def http_json(
    url: str,
    *,
    method: str = "GET",
    payload: Dict[str, Any] | None = None,
    headers: Dict[str, str] | None = None,
    timeout_s: float = 30.0,
) -> Tuple[int, Dict[str, Any]]:
    data = None
    merged_headers = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        merged_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=data, headers=merged_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=max(timeout_s, 0.1)) as response:
            body = response.read().decode("utf-8")
            return response.getcode(), json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, json.loads(body) if body else {}


def load_contract(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError("Contract YAML must deserialize to a mapping.")
    return payload


def contract_intents_by_name(contract: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    by_name: Dict[str, Dict[str, Any]] = {}
    for item in list(contract.get("intents", [])):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if name:
            by_name[name] = dict(item)
    return by_name


def allowed_intent_names(contract: Dict[str, Any]) -> list[str]:
    return sorted(contract_intents_by_name(contract).keys())


def blocked_decision(
    task_text: str,
    reason: str,
    *,
    missing_prerequisites: Iterable[str] | None = None,
    expected_observations: Iterable[str] | None = None,
    confidence: float = 0.0,
) -> Dict[str, Any]:
    return {
        "status": "blocked",
        "task_text": task_text,
        "intent": "",
        "args": {},
        "rationale_short": str(reason),
        "missing_prerequisites": [str(item) for item in list(missing_prerequisites or [])],
        "expected_observations": [str(item) for item in list(expected_observations or [])],
        "confidence": float(confidence),
    }


def normalize_model_decision(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Model output must be a JSON object.")

    required = {
        "status",
        "task_text",
        "intent",
        "args",
        "rationale_short",
        "missing_prerequisites",
        "expected_observations",
        "confidence",
    }
    missing = sorted(required - set(payload.keys()))
    if missing:
        raise ValueError(f"Model output missing keys: {', '.join(missing)}")

    status = str(payload.get("status", "")).strip()
    if status not in {"recommendation", "blocked"}:
        raise ValueError(f"Unsupported status: {status}")

    intent = str(payload.get("intent", "")).strip()
    raw_args = payload.get("args", {})
    if not isinstance(raw_args, dict):
        raise ValueError("args must be a JSON object.")
    args = {str(key): value for key, value in raw_args.items() if value is not None}

    missing_prerequisites = payload.get("missing_prerequisites", [])
    if not isinstance(missing_prerequisites, list) or not all(isinstance(item, str) for item in missing_prerequisites):
        raise ValueError("missing_prerequisites must be a string array.")

    expected_observations = payload.get("expected_observations", [])
    if not isinstance(expected_observations, list) or not all(isinstance(item, str) for item in expected_observations):
        raise ValueError("expected_observations must be a string array.")

    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)) or not math.isfinite(float(confidence)):
        raise ValueError("confidence must be a finite number.")

    normalized = {
        "status": status,
        "task_text": str(payload.get("task_text", "")),
        "intent": intent,
        "args": dict(args),
        "rationale_short": str(payload.get("rationale_short", "")),
        "missing_prerequisites": [str(item) for item in missing_prerequisites],
        "expected_observations": [str(item) for item in expected_observations],
        "confidence": float(confidence),
    }
    if status == "recommendation" and not intent:
        raise ValueError("Recommendation must include a frozen intent.")
    if status == "blocked" and (intent or normalized["args"]):
        raise ValueError("Blocked results must not include intent args.")
    return normalized


def validate_decision_against_contract(decision: Dict[str, Any], contract: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(decision)
    if normalized["status"] != "recommendation":
        normalized["intent"] = ""
        normalized["args"] = {}
        return normalized

    intents = contract_intents_by_name(contract)
    intent_name = normalized["intent"]
    if intent_name not in intents:
        raise ValueError(f"Intent outside frozen contract: {intent_name}")

    args = dict(normalized.get("args", {}))
    required_args = [str(value) for value in list(intents[intent_name].get("required_args", []))]
    extra_args = sorted(name for name in args.keys() if str(name) not in required_args)
    if extra_args:
        raise ValueError(f"Unexpected args for {intent_name}: {', '.join(extra_args)}")

    missing_args = [name for name in required_args if name not in args]
    if missing_args:
        raise ValueError(f"Missing required args for {intent_name}: {', '.join(missing_args)}")

    normalized_args: Dict[str, Any] = {}
    for key, value in args.items():
        if key == "target_class":
            if not isinstance(value, str) or not value.strip():
                raise ValueError("target_class must be a non-empty string.")
            normalized_args[key] = value.strip()
        elif key == "approach_distance_m":
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ValueError("approach_distance_m must be numeric.")
            normalized_args[key] = float(value)
        elif key == "target_id":
            if not isinstance(value, str) or not value.strip():
                raise ValueError("target_id must be a non-empty string.")
            normalized_args[key] = value.strip()
        else:
            normalized_args[key] = value
    normalized["args"] = normalized_args
    return normalized


def validate_decision_against_canonical_space(decision: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(decision)
    if normalized["status"] != "recommendation":
        normalized["intent"] = ""
        normalized["args"] = {}
        return normalized

    intent_name = normalized["intent"]
    expected_args = CANONICAL_ARGS_BY_INTENT.get(intent_name)
    if expected_args is None:
        raise ValueError(f"Intent outside canonical action space: {intent_name}")

    candidate_args = dict(normalized.get("args", {}))
    if intent_name == "plan_to_target" and "approach_distance_m" in candidate_args:
        candidate_args["approach_distance_m"] = float(candidate_args["approach_distance_m"])
    # visit_target has a dynamic target_id — validate keys match but allow any non-empty value
    if intent_name == "visit_target":
        if set(candidate_args.keys()) != set(expected_args.keys()):
            raise ValueError(
                f"Non-canonical arg keys for {intent_name}: expected {sorted(expected_args.keys())}, "
                f"got {sorted(candidate_args.keys())}"
            )
        target_id = str(candidate_args.get("target_id", "")).strip()
        if not target_id:
            raise ValueError("visit_target requires a non-empty target_id.")
        candidate_args["target_id"] = target_id
    elif candidate_args != expected_args:
        raise ValueError(
            f"Non-canonical args for {intent_name}: expected {json.dumps(expected_args, sort_keys=True)}, "
            f"got {json.dumps(candidate_args, sort_keys=True)}"
        )
    normalized["args"] = candidate_args
    return normalized


def fetch_dashboard_state(dashboard_url: str, timeout_s: float) -> Dict[str, Any]:
    status, payload = http_json(f"{dashboard_url.rstrip('/')}/api/state", timeout_s=timeout_s)
    if status != 200:
        raise RecommendationError(f"Dashboard state request failed with status {status}.")
    return payload


def preview_intent(dashboard_url: str, intent: str, args: Dict[str, Any], timeout_s: float) -> Tuple[int, Dict[str, Any]]:
    return http_json(
        f"{dashboard_url.rstrip('/')}/api/intents/preview",
        method="POST",
        payload={"intent": intent, "args": args},
        timeout_s=timeout_s,
    )


def dispatch_intent(dashboard_url: str, intent: str, args: Dict[str, Any], timeout_s: float) -> Tuple[int, Dict[str, Any]]:
    return http_json(
        f"{dashboard_url.rstrip('/')}/api/intents/dispatch",
        method="POST",
        payload={"intent": intent, "args": args},
        timeout_s=timeout_s,
    )


def preview_summary(preview_status: int, preview_payload: Dict[str, Any]) -> Dict[str, Any]:
    preview = preview_payload.get("preview") if isinstance(preview_payload, dict) and isinstance(preview_payload.get("preview"), dict) else {}
    readiness = preview.get("readiness") if isinstance(preview.get("readiness"), dict) else {}
    return {
        "status": preview_status,
        "contract_valid": bool(preview.get("contract_valid", False)),
        "ready_to_dispatch": bool(preview.get("ready_to_dispatch", False)),
        "missing_keys": [str(item) for item in list(readiness.get("missing_keys", []))],
        "expected_boundary_activity": [str(item) for item in list(preview.get("expected_boundary_activity", []))],
        "payload": preview.get("payload", {}),
    }


def attempt_deterministic_recommendation(
    *,
    task_text: str,
    state: Dict[str, Any],
    contract: Dict[str, Any],
    dashboard_url: str,
    timeout_s: float,
    digest: Dict[str, Any] | None = None,
) -> DeterministicRecommendation | None:
    digest_payload = digest if isinstance(digest, dict) and digest else build_state_digest(state, contract)
    policy = digest_payload.get("policy") if isinstance(digest_payload.get("policy"), dict) else {}
    preferred_intent = str(policy.get("preferred_intent", "")).strip()
    if not preferred_intent:
        return None
    canonical_args = CANONICAL_ARGS_BY_INTENT.get(preferred_intent)
    if canonical_args is None:
        return None
    # visit_target requires LLM judgment to choose a target_id — skip deterministic path
    if preferred_intent == "visit_target":
        return None

    decision = {
        "status": "recommendation",
        "task_text": task_text,
        "intent": preferred_intent,
        "args": dict(canonical_args),
        "rationale_short": str(policy.get("reason", "")).strip() or f"Policy preferred {preferred_intent}.",
        "missing_prerequisites": [],
        "expected_observations": [],
        "confidence": 1.0,
        "evaluation_kind": "deterministic_recommendation",
    }
    decision = validate_decision_against_contract(decision, contract)
    decision = validate_decision_against_canonical_space(decision)

    try:
        preview_status, preview_payload = preview_intent(
            dashboard_url,
            preferred_intent,
            dict(decision.get("args", {})),
            timeout_s=timeout_s,
        )
    except Exception:
        return None
    preview = preview_summary(preview_status, preview_payload)
    if preview_status != 200 or not preview["contract_valid"] or not preview["ready_to_dispatch"]:
        return None

    return DeterministicRecommendation(
        decision=decision,
        preview_status=preview_status,
        preview_payload=preview_payload,
        preview=preview,
        preferred_intent=preferred_intent,
        policy_stage=str(policy.get("stage", "")),
        policy_reason=str(policy.get("reason", "")),
        policy_snapshot=dict(policy),
    )


def blocked_from_preview(
    *,
    task_text: str,
    decision: Dict[str, Any],
    preview_status: int,
    preview_payload: Dict[str, Any],
) -> Dict[str, Any]:
    summary = preview_summary(preview_status, preview_payload)
    return blocked_decision(
        task_text,
        "Preview gate blocked the recommended intent.",
        missing_prerequisites=summary.get("missing_keys") or ["preview_ready_to_dispatch"],
        expected_observations=summary.get("expected_boundary_activity") or [],
        confidence=float(decision.get("confidence", 0.0) or 0.0),
    )


def decision_signature(decision: Dict[str, Any]) -> str:
    return json.dumps(
        {
            "status": str(decision.get("status", "")),
            "intent": str(decision.get("intent", "")),
            "args": dict(decision.get("args", {})),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def resolve_recommendation_artifacts(repo_root: Path, session_id: str) -> RunArtifacts:
    session_key = session_id.strip() or NO_SESSION_ID
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base_root = repo_root / "artifacts" / "session" / session_key / "llm_recommendation"
    run_root = base_root / ts
    return RunArtifacts(
        session_id=session_key,
        root=run_root,
        request_path=run_root / "request.json",
        response_path=run_root / "response.json",
        summary_path=run_root / "recommendation_summary.json",
        dispatch_path=run_root / "dispatch_summary.json",
        history_path=base_root / "history.jsonl",
    )


def resolve_supervisor_artifacts(repo_root: Path, session_id: str, *, timestamp: str | None = None) -> SupervisorArtifacts:
    session_key = session_id.strip() or NO_SESSION_ID
    ts = timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base_root = repo_root / "artifacts" / "session" / session_key / "llm_supervisor"
    run_root = base_root / ts
    return SupervisorArtifacts(
        session_id=session_key,
        base_root=base_root,
        run_root=run_root,
        latest_path=base_root / "latest.json",
        history_path=base_root / "history.jsonl",
        digest_path=run_root / "digest.json",
        provider_request_path=run_root / "provider_request.json",
        provider_response_path=run_root / "provider_response.json",
        evaluation_path=run_root / "evaluation.json",
    )


def empty_supervisor_runtime_state() -> Dict[str, Any]:
    return {
        "mode": "shadow",
        "provider": "",
        "model": "",
        "running": False,
        "status": "disabled",
        "latest_decision": {},
        "last_evaluated_utc": "",
        "last_polled_utc": "",
        "history_path": "",
        "latest_path": "",
        "state_hash": "",
        "preview": {},
        "suppression_reason": "",
        "session_id": "",
        "recent_history": [],
    }


def load_supervisor_runtime_state() -> Dict[str, Any]:
    payload = read_json(SUPERVISOR_RUNTIME_STATE_PATH)
    merged = empty_supervisor_runtime_state()
    for key, value in payload.items():
        merged[key] = value
    return merged


def write_supervisor_runtime_state(payload: Dict[str, Any]) -> None:
    merged = empty_supervisor_runtime_state()
    for key, value in payload.items():
        merged[key] = value
    write_json(SUPERVISOR_RUNTIME_STATE_PATH, merged)
