#!/usr/bin/env python3
"""Provider abstractions for bounded LLM supervisor decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol, Tuple


class ProviderError(RuntimeError):
    """Raised when a provider cannot produce a valid bounded decision."""


@dataclass(frozen=True)
class ProviderDecisionResult:
    decision: Dict[str, Any]
    request_payload: Dict[str, Any]
    response_payload: Dict[str, Any]
    provider: str
    model: str


class DecisionProvider(Protocol):
    provider_name: str
    model_name: str

    def is_enabled(self) -> Tuple[bool, str]:
        """Return enabled status plus a human-readable reason when disabled."""

    def recommend(
        self,
        *,
        task_text: str,
        digest: Dict[str, Any],
        contract: Dict[str, Any],
        timeout_s: float,
    ) -> ProviderDecisionResult:
        """Return one bounded decision plus request/response artifacts."""

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
        """Return a complete ordered route for a gather/collection scenario."""
