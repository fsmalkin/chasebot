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

    def plan_collection_route(
        self,
        *,
        remaining_target_ids: list[str],
        target_details: Dict[str, Any] | list[Dict[str, Any]],
        zone_details: Dict[str, Any],
        placed_targets: list[str],
        mission_state: Dict[str, Any],
        timeout_s: float,
    ) -> list[str]:
        raw = os.environ.get("CHASECAR_LOCAL_STUB_COLLECTION_ROUTE_JSON", "").strip()
        if not raw:
            return list(remaining_target_ids)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"CHASECAR_LOCAL_STUB_COLLECTION_ROUTE_JSON is not valid JSON: {exc}") from exc
        if isinstance(payload, dict):
            target_order = list(payload.get("target_order", []))
        elif isinstance(payload, list):
            target_order = list(payload)
        else:
            raise ProviderError("CHASECAR_LOCAL_STUB_COLLECTION_ROUTE_JSON must decode to an object or array.")
        order_ids = [str(item).strip() for item in target_order if str(item).strip()]
        if set(order_ids) != set(remaining_target_ids):
            raise ProviderError(
                f"Local stub collection route returned {order_ids} but expected exactly {remaining_target_ids}"
            )
        return order_ids


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

    def plan_collection_route(
        self,
        *,
        remaining_target_ids: list[str],
        target_details: list[Dict[str, Any]],
        zone_details: Dict[str, Any],
        placed_targets: list[str],
        mission_state: Dict[str, Any],
        timeout_s: float,
    ) -> list[str]:
        raise ProviderError("Local model backend is not implemented in this slice.")
