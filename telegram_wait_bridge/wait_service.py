"""Shared wait-bridge helpers used by the daemon and MCP server."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from telegram_wait_bridge.config import Settings
from telegram_wait_bridge.db import ACTIVE_WAIT_STATUSES, Database

MAX_PROMPT_CHARS = 3900
TERMINAL_WAIT_STATUSES = {"fulfilled", "timed_out", "cancelled", "failed"}


def resolve_chat_id(settings: Settings, requested_chat_id: Optional[int]) -> int:
    if requested_chat_id is not None:
        if requested_chat_id not in settings.allowed_chat_ids:
            raise ValueError(f"Chat id {requested_chat_id} is not in the configured allowlist")
        return requested_chat_id

    if settings.default_chat_id is not None:
        return settings.default_chat_id

    if len(settings.allowed_chat_ids) == 1:
        return next(iter(settings.allowed_chat_ids))

    raise ValueError("chat_id is required when multiple allowed chat ids are configured")


def clamp_timeout(settings: Settings, timeout_seconds: Optional[int]) -> int:
    if timeout_seconds is None:
        return settings.wait_default_timeout_sec
    if timeout_seconds < 5:
        raise ValueError("timeout_seconds must be at least 5 seconds")
    return min(timeout_seconds, settings.wait_max_timeout_sec)


def validate_prompt_text(message: str) -> str:
    text = message.strip()
    if not text:
        raise ValueError("message must not be empty")
    if len(text) > MAX_PROMPT_CHARS:
        raise ValueError(f"message is too long; maximum supported length is {MAX_PROMPT_CHARS} characters")
    return text


def format_prompt_for_delivery(prompt_text: str) -> str:
    return prompt_text.rstrip()


def serialize_wait_request(wait_request: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "wait_id": wait_request["id"],
        "chat_id": wait_request["chat_id"],
        "status": wait_request["status"],
        "prompt_message_id": wait_request.get("prompt_message_id"),
        "reply_text": wait_request.get("reply_text"),
        "reply_message_id": wait_request.get("reply_message_id"),
        "reply_from_user_id": wait_request.get("reply_from_user_id"),
        "error_text": wait_request.get("error_text"),
        "created_at": wait_request.get("created_at"),
        "expires_at": wait_request.get("expires_at"),
        "resolved_at": wait_request.get("resolved_at"),
        "is_terminal": wait_request["status"] in TERMINAL_WAIT_STATUSES,
    }


def wait_until_dispatched(db: Database, wait_id: str, poll_interval_sec: float, max_wait_sec: int) -> Dict[str, Any]:
    deadline = time.monotonic() + max_wait_sec
    current = db.get_wait_request(wait_id)
    if current is None:
        raise ValueError(f"Unknown wait request: {wait_id}")

    while time.monotonic() < deadline:
        current = db.get_wait_request(wait_id)
        if current is None:
            raise ValueError(f"Unknown wait request: {wait_id}")
        if current["status"] not in {"queued", "sending"}:
            return current
        time.sleep(poll_interval_sec)

    current = db.get_wait_request(wait_id)
    if current is None:
        raise ValueError(f"Unknown wait request: {wait_id}")
    return current


def wait_until_terminal(
    db: Database,
    wait_id: str,
    poll_interval_sec: float,
    max_wait_sec: Optional[int],
) -> Dict[str, Any]:
    deadline = None if max_wait_sec is None else time.monotonic() + max_wait_sec

    while True:
        current = db.get_wait_request(wait_id)
        if current is None:
            raise ValueError(f"Unknown wait request: {wait_id}")
        if current["status"] in TERMINAL_WAIT_STATUSES:
            return current
        if deadline is not None and time.monotonic() >= deadline:
            return current
        time.sleep(poll_interval_sec)


def active_statuses() -> tuple[str, ...]:
    return ACTIVE_WAIT_STATUSES
