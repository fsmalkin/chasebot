#!/usr/bin/env python3
"""Shadow-mode LLM supervisor that observes dashboard state and never dispatches."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from brain_state_digest import build_state_digest, state_digest_hash
from llm_provider_base import DecisionProvider
from llm_provider_local import LocalModelProvider, LocalStubProvider
from llm_provider_openai import OpenAIResponsesProvider
from llm_supervisor_core import (
    DEFAULT_DASHBOARD_URL,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_REASONING_EFFORT,
    DEFAULT_SHADOW_TASK_TEXT,
    REPO_ROOT,
    RecommendationError,
    attempt_deterministic_recommendation,
    append_jsonl,
    blocked_decision,
    blocked_from_preview,
    decision_signature,
    fetch_dashboard_state,
    load_contract,
    normalize_model_decision,
    preview_intent,
    preview_summary,
    read_jsonl,
    resolve_supervisor_artifacts,
    utc_now,
    validate_decision_against_canonical_space,
    validate_decision_against_contract,
    write_json,
    write_supervisor_runtime_state,
)


def _supervisor_default_model() -> str:
    for env_name in ("OPENAI_SUPERVISOR_MODEL", "OPENAI_MODEL"):
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
    return DEFAULT_OPENAI_MODEL


def _supervisor_default_reasoning() -> str:
    for env_name in ("OPENAI_SUPERVISOR_REASONING_EFFORT", "OPENAI_REASONING_EFFORT"):
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
    return DEFAULT_REASONING_EFFORT


class SupervisorController:
    def __init__(
        self,
        *,
        provider: DecisionProvider,
        contract_path: Path,
        dashboard_url: str,
        repo_root: Path,
        task_text: str,
        poll_s: float,
        max_staleness_s: float,
        timeout_s: float,
    ) -> None:
        self.provider = provider
        self.contract = load_contract(contract_path)
        self.dashboard_url = dashboard_url.rstrip("/")
        self.repo_root = repo_root
        self.task_text = task_text
        self.poll_s = max(poll_s, 0.1)
        self.max_staleness_s = max(max_staleness_s, self.poll_s)
        self.timeout_s = max(timeout_s, 0.1)
        self.last_state_hash = ""
        self.last_decision_signature = ""
        self.last_evaluated_monotonic = 0.0
        self.last_suppression_hash = ""

    def _runtime_payload(
        self,
        *,
        status: str,
        session_id: str,
        provider: str,
        model: str,
        latest_decision: Dict[str, Any] | None,
        state_hash: str,
        history_path: str,
        latest_path: str,
        preview: Dict[str, Any] | None,
        suppression_reason: str = "",
        recent_history: list[Dict[str, Any]] | None = None,
        running: bool = True,
        last_evaluated_utc: str = "",
    ) -> Dict[str, Any]:
        return {
            "mode": "shadow",
            "provider": provider,
            "model": model,
            "running": running,
            "status": status,
            "latest_decision": latest_decision or {},
            "last_evaluated_utc": last_evaluated_utc,
            "last_polled_utc": utc_now(),
            "history_path": history_path,
            "latest_path": latest_path,
            "state_hash": state_hash,
            "preview": preview or {},
            "suppression_reason": suppression_reason,
            "session_id": session_id,
            "recent_history": recent_history or [],
        }

    def _write_runtime(self, payload: Dict[str, Any]) -> None:
        write_supervisor_runtime_state(payload)

    def _record_suppression(self, *, session_id: str, state_hash: str) -> Dict[str, Any]:
        artifacts = resolve_supervisor_artifacts(self.repo_root, session_id)
        latest_payload = {}
        try:
            latest_payload = json.loads(artifacts.latest_path.read_text(encoding="utf-8"))
        except Exception:
            latest_payload = {}
        if self.last_suppression_hash != state_hash:
            append_jsonl(
                artifacts.history_path,
                {
                    "event_type": "suppressed",
                    "generated_utc": utc_now(),
                    "provider": self.provider.provider_name,
                    "model": self.provider.model_name,
                    "session_id": session_id,
                    "state_hash": state_hash,
                    "suppression_reason": "unchanged_state_within_staleness_window",
                },
            )
            self.last_suppression_hash = state_hash
        runtime_payload = self._runtime_payload(
            status=str((latest_payload.get("decision") or {}).get("status", "waiting") or "waiting"),
            session_id=artifacts.session_id,
            provider=self.provider.provider_name,
            model=self.provider.model_name,
            latest_decision=latest_payload.get("decision", {}) if isinstance(latest_payload.get("decision"), dict) else {},
            state_hash=state_hash,
            history_path=str(artifacts.history_path),
            latest_path=str(artifacts.latest_path),
            preview=latest_payload.get("preview", {}) if isinstance(latest_payload.get("preview"), dict) else {},
            suppression_reason="unchanged_state_within_staleness_window",
            recent_history=read_jsonl(artifacts.history_path, limit=5),
            running=True,
            last_evaluated_utc=str(latest_payload.get("generated_utc", "") or ""),
        )
        self._write_runtime(runtime_payload)
        return runtime_payload

    def evaluate_once(self) -> Dict[str, Any]:
        try:
            state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.timeout_s)
            state_error = ""
        except Exception as exc:
            state_error = str(exc)
            state = {
                "control_plane_ready": False,
                "environment_state": "unknown",
                "scenario_state": "unknown",
                "session_id": "",
                "last_feedback": "",
                "last_result": "",
            }

        session_id = str(state.get("session_id", "") or "")
        digest = build_state_digest(state, self.contract)
        state_hash = state_digest_hash(digest)
        deterministic = None

        enabled, disabled_reason = self.provider.is_enabled()
        artifacts = resolve_supervisor_artifacts(self.repo_root, session_id)
        if not enabled:
            deterministic_probe = attempt_deterministic_recommendation(
                task_text=self.task_text,
                state=state,
                contract=self.contract,
                dashboard_url=self.dashboard_url,
                timeout_s=self.timeout_s,
                digest=digest,
            )
            if deterministic_probe is None:
                runtime_payload = self._runtime_payload(
                    status="disabled",
                    session_id=artifacts.session_id,
                    provider=self.provider.provider_name,
                    model=self.provider.model_name,
                    latest_decision=blocked_decision(
                        self.task_text,
                        disabled_reason or "Provider disabled.",
                        missing_prerequisites=["provider_disabled"],
                    ),
                    state_hash=state_hash,
                    history_path=str(artifacts.history_path),
                    latest_path=str(artifacts.latest_path),
                    preview={},
                    suppression_reason=disabled_reason or "provider_disabled",
                    recent_history=read_jsonl(artifacts.history_path, limit=5),
                    running=True,
                )
                self._write_runtime(runtime_payload)
                return runtime_payload
            deterministic = deterministic_probe

        now_monotonic = time.monotonic()
        is_stale = not self.last_evaluated_monotonic or (now_monotonic - self.last_evaluated_monotonic) >= self.max_staleness_s
        if self.last_state_hash == state_hash and not is_stale:
            return self._record_suppression(session_id=artifacts.session_id, state_hash=state_hash)

        self.last_suppression_hash = ""
        evaluation_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        artifacts = resolve_supervisor_artifacts(self.repo_root, session_id, timestamp=evaluation_ts)
        if deterministic is None:
            deterministic = attempt_deterministic_recommendation(
                task_text=self.task_text,
                state=state,
                contract=self.contract,
                dashboard_url=self.dashboard_url,
                timeout_s=self.timeout_s,
                digest=digest,
            )
        provider_request: Dict[str, Any] = {}
        provider_response: Dict[str, Any] = {}
        preview_payload: Dict[str, Any] = {}
        preview_status = 0
        evaluation_kind = "provider"
        hard_error = ""

        if deterministic is not None:
            decision = dict(deterministic.decision)
            preview_status = deterministic.preview_status
            preview_payload = dict(deterministic.preview_payload)
            evaluation_kind = deterministic.evaluation_kind
        elif state_error:
            evaluation_kind = "deterministic_blocked"
            decision = blocked_decision(
                self.task_text,
                "Dashboard control plane unavailable.",
                missing_prerequisites=["dashboard_unavailable"],
            )
        elif not bool(state.get("control_plane_ready", False)):
            evaluation_kind = "deterministic_blocked"
            decision = blocked_decision(
                self.task_text,
                str(state.get("control_plane_error") or "Dashboard control plane unavailable."),
                missing_prerequisites=["control_plane_unavailable"],
            )
        elif str(state.get("environment_state", "")) != "environment_ready":
            evaluation_kind = "deterministic_blocked"
            decision = blocked_decision(
                self.task_text,
                "Environment is not ready for shadow recommendations.",
                missing_prerequisites=["environment_ready"],
            )
        else:
            try:
                result = self.provider.recommend(
                    task_text=self.task_text,
                    digest=digest,
                    contract=self.contract,
                    timeout_s=self.timeout_s,
                )
                provider_request = result.request_payload
                provider_response = result.response_payload
                decision = normalize_model_decision(result.decision)
                decision = validate_decision_against_contract(decision, self.contract)
                decision = validate_decision_against_canonical_space(decision)
            except Exception as exc:
                hard_error = str(exc)
                evaluation_kind = "provider_error"
                decision = blocked_decision(
                    self.task_text,
                    "Provider output could not be validated.",
                    missing_prerequisites=["provider_output_invalid"],
                )

        if decision.get("status") == "recommendation" and deterministic is None:
            preview_status, preview_payload = preview_intent(
                self.dashboard_url,
                str(decision.get("intent", "")),
                dict(decision.get("args", {})),
                timeout_s=self.timeout_s,
            )
            summary = preview_summary(preview_status, preview_payload)
            if preview_status != 200 or not summary["contract_valid"] or not summary["ready_to_dispatch"]:
                evaluation_kind = "preview_blocked"
                decision = blocked_from_preview(
                    task_text=self.task_text,
                    decision=decision,
                    preview_status=preview_status,
                    preview_payload=preview_payload,
                )

        novelty = "blocked" if decision.get("status") == "blocked" else (
            "repeated" if decision_signature(decision) == self.last_decision_signature else "new"
        )
        evaluation_payload = {
            "generated_utc": utc_now(),
            "mode": "shadow",
            "provider": self.provider.provider_name,
            "model": self.provider.model_name,
            "session_id": artifacts.session_id,
            "task_text": self.task_text,
            "state_hash": state_hash,
            "decision": decision,
            "preview": preview_summary(preview_status, preview_payload),
            "evaluation_kind": evaluation_kind,
            "decision_novelty": novelty,
            "suppression_reason": "",
            "hard_error": hard_error,
            "pass": hard_error == "",
        }

        write_json(artifacts.digest_path, digest)
        write_json(artifacts.provider_request_path, provider_request)
        write_json(artifacts.provider_response_path, provider_response)
        write_json(artifacts.evaluation_path, evaluation_payload)
        write_json(artifacts.latest_path, evaluation_payload)
        append_jsonl(
            artifacts.history_path,
            {
                "event_type": "evaluation",
                "generated_utc": evaluation_payload["generated_utc"],
                "provider": self.provider.provider_name,
                "model": self.provider.model_name,
                "session_id": artifacts.session_id,
                "status": decision.get("status", ""),
                "intent": decision.get("intent", ""),
                "state_hash": state_hash,
                "evaluation_kind": evaluation_kind,
                "decision_novelty": novelty,
                "summary_path": str(artifacts.evaluation_path),
            },
        )

        runtime_payload = self._runtime_payload(
            status=str(decision.get("status", "waiting")),
            session_id=artifacts.session_id,
            provider=self.provider.provider_name,
            model=self.provider.model_name,
            latest_decision=decision,
            state_hash=state_hash,
            history_path=str(artifacts.history_path),
            latest_path=str(artifacts.latest_path),
            preview=preview_summary(preview_status, preview_payload),
            recent_history=read_jsonl(artifacts.history_path, limit=5),
            running=True,
            last_evaluated_utc=evaluation_payload["generated_utc"],
        )
        self._write_runtime(runtime_payload)
        self.last_state_hash = state_hash
        self.last_decision_signature = decision_signature(decision)
        self.last_evaluated_monotonic = now_monotonic
        return runtime_payload

    def run_forever(self) -> int:
        while True:
            self.evaluate_once()
            time.sleep(self.poll_s)


def build_provider(args: argparse.Namespace) -> DecisionProvider:
    provider_name = str(args.provider).strip().lower()
    if provider_name == "openai":
        return OpenAIResponsesProvider(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            base_url=os.environ.get("OPENAI_BASE_URL", ""),
            org_id=os.environ.get("OPENAI_ORG_ID", ""),
            project_id=os.environ.get("OPENAI_PROJECT_ID", ""),
        )
    if provider_name == "local_stub":
        return LocalStubProvider(model=args.model)
    if provider_name == "local_model":
        return LocalModelProvider(model=args.model)
    raise RecommendationError(f"Unsupported supervisor provider: {args.provider}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the shadow-mode LLM supervisor loop.")
    parser.add_argument(
        "--dashboard-url",
        default=os.environ.get("CHASECAR_DASHBOARD_URL", DEFAULT_DASHBOARD_URL),
        help="Dashboard base URL used for authoritative state and preview gates.",
    )
    parser.add_argument(
        "--contract",
        default=str(REPO_ROOT / "runtime" / "contracts" / "llm_control_contract.yaml"),
        help="Path to the frozen control contract.",
    )
    parser.add_argument(
        "--provider",
        default=os.environ.get("CHASECAR_LLM_PROVIDER", "openai"),
        help="Decision provider: openai, local_stub, or local_model.",
    )
    parser.add_argument("--model", default=_supervisor_default_model(), help="Provider model name.")
    parser.add_argument(
        "--reasoning-effort",
        default=_supervisor_default_reasoning(),
        help="Provider reasoning effort setting.",
    )
    parser.add_argument(
        "--task",
        default=os.environ.get("CHASECAR_LLM_SUPERVISOR_TASK", DEFAULT_SHADOW_TASK_TEXT),
        help="Bounded task text sent to the provider.",
    )
    parser.add_argument("--poll-s", type=float, default=float(os.environ.get("CHASECAR_LLM_SUPERVISOR_POLL_S", "1.0")))
    parser.add_argument(
        "--max-staleness-s",
        type=float,
        default=float(os.environ.get("CHASECAR_LLM_SUPERVISOR_MAX_STALENESS_S", "8.0")),
    )
    parser.add_argument("--timeout-s", type=float, default=45.0)
    parser.add_argument("--once", action="store_true", help="Run a single evaluation and exit.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    provider = build_provider(args)
    controller = SupervisorController(
        provider=provider,
        contract_path=Path(args.contract).resolve(),
        dashboard_url=args.dashboard_url,
        repo_root=REPO_ROOT,
        task_text=args.task,
        poll_s=args.poll_s,
        max_staleness_s=args.max_staleness_s,
        timeout_s=args.timeout_s,
    )
    if args.once:
        payload = controller.evaluate_once()
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    return controller.run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
