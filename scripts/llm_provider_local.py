#!/usr/bin/env python3
"""Local provider placeholders for the bounded shadow supervisor."""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from llm_provider_base import ProviderDecisionResult, ProviderError
from llm_supervisor_core import blocked_decision


class LocalStubProvider:
    provider_name = "local_stub"

    def __init__(self, *, model: str = "local-stub") -> None:
        self.model_name = model

    def is_enabled(self) -> tuple[bool, str]:
        return True, ""

    def recommend(
        self,
        *,
        task_text: str,
        digest: Dict[str, Any],
        contract: Dict[str, Any],
        timeout_s: float,
    ) -> ProviderDecisionResult:
        raw = os.environ.get("CHASECAR_LOCAL_STUB_DECISION_JSON", "").strip()
        if raw:
            try:
                decision = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ProviderError(f"CHASECAR_LOCAL_STUB_DECISION_JSON is not valid JSON: {exc}") from exc
        else:
            decision = blocked_decision(
                task_text,
                "Local stub provider has no active model backend.",
                missing_prerequisites=["local_model_backend_unavailable"],
            )
        return ProviderDecisionResult(
            decision=decision,
            request_payload={"provider": self.provider_name, "mode": "stub"},
            response_payload={"provider": self.provider_name, "raw_stub": raw},
            provider=self.provider_name,
            model=self.model_name,
        )


class LocalModelProvider:
    provider_name = "local_model"

    def __init__(self, *, model: str = "local-model") -> None:
        self.model_name = model

    def is_enabled(self) -> tuple[bool, str]:
        return False, "Local model backend is not implemented in this slice."

    def recommend(
        self,
        *,
        task_text: str,
        digest: Dict[str, Any],
        contract: Dict[str, Any],
        timeout_s: float,
    ) -> ProviderDecisionResult:
        raise ProviderError("Local model backend is not implemented in this slice.")
