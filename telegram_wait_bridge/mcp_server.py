"""Custom stdio MCP server for the Telegram wait bridge."""

from __future__ import annotations

from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from telegram_wait_bridge.config import Settings, load_settings
from telegram_wait_bridge.db import ACTIVE_WAIT_STATUSES, Database
from telegram_wait_bridge.wait_service import (
    clamp_timeout,
    resolve_chat_id,
    serialize_wait_request,
    validate_prompt_text,
    wait_until_dispatched,
    wait_until_terminal,
)

INSTRUCTIONS = (
    "Use telegram_send to send a Telegram prompt to the configured user, then use telegram_wait "
    "to block until they reply. Replies must be direct Telegram replies to the prompt message."
)

mcp = FastMCP("chasecar-telegram-wait", instructions=INSTRUCTIONS, log_level="INFO")


def _load_settings() -> Settings:
    return load_settings(require_allowed_chat_ids=True)


def _ensure_daemon_healthy(db: Database, settings: Settings) -> None:
    if not db.is_state_fresh("daemon_heartbeat", settings.daemon_health_max_age_sec):
        raise ValueError(
            "telegram-daemon is not healthy. Start the runtime container before sending wait prompts."
        )


@mcp.tool(description="Send a Telegram prompt and create a wait request.", structured_output=True)
def telegram_send(
    message: str,
    chat_id: Optional[int] = None,
    timeout_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    settings = _load_settings()
    db = Database(settings.db_path)
    try:
        _ensure_daemon_healthy(db, settings)
        resolved_chat_id = resolve_chat_id(settings, chat_id)
        prompt_text = validate_prompt_text(message)
        effective_timeout = clamp_timeout(settings, timeout_seconds)
        created = db.create_wait_request(
            chat_id=resolved_chat_id,
            prompt_text=prompt_text,
            timeout_seconds=effective_timeout,
        )

        dispatched = wait_until_dispatched(
            db=db,
            wait_id=str(created["id"]),
            poll_interval_sec=settings.wait_send_poll_interval_sec,
            max_wait_sec=settings.wait_send_max_delay_sec,
        )
        payload = serialize_wait_request(dispatched)
        payload["delivery_confirmed"] = dispatched["status"] == "awaiting_reply"
        return payload
    finally:
        db.close()


@mcp.tool(description="Wait for a Telegram reply to reach a terminal state.", structured_output=True)
def telegram_wait(wait_id: str, max_wait_seconds: Optional[int] = None) -> Dict[str, Any]:
    settings = _load_settings()
    db = Database(settings.db_path)
    try:
        caller_wait = None
        if max_wait_seconds is not None:
            if max_wait_seconds < 1:
                raise ValueError("max_wait_seconds must be at least 1")
            caller_wait = min(max_wait_seconds, settings.wait_max_timeout_sec)

        current = wait_until_terminal(
            db=db,
            wait_id=wait_id,
            poll_interval_sec=settings.wait_status_poll_interval_sec,
            max_wait_sec=caller_wait,
        )
        payload = serialize_wait_request(current)
        payload["wait_complete"] = current["status"] not in ACTIVE_WAIT_STATUSES
        return payload
    finally:
        db.close()


@mcp.tool(description="Cancel a pending Telegram wait request.", structured_output=True)
def telegram_cancel(wait_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
    settings = _load_settings()
    db = Database(settings.db_path)
    try:
        cancelled = db.cancel_wait_request(wait_id=wait_id, reason=reason)
        if cancelled is None:
            raise ValueError(f"Unknown wait request: {wait_id}")
        payload = serialize_wait_request(cancelled)
        payload["wait_complete"] = cancelled["status"] not in ACTIVE_WAIT_STATUSES
        return payload
    finally:
        db.close()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
