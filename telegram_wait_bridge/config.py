"""Configuration helpers for the Telegram wait bridge."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Set

PLACEHOLDER_MARKERS = (
    "replace_me",
    "changeme",
    "your_token_here",
    "your_key_here",
)


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    db_path: str
    allowed_chat_ids: Set[int]
    default_chat_id: Optional[int]
    telegram_poll_timeout_sec: int
    telegram_retry_sec: int
    wait_default_timeout_sec: int
    wait_max_timeout_sec: int
    wait_daemon_idle_poll_timeout_sec: int
    wait_status_poll_interval_sec: float
    wait_send_poll_interval_sec: float
    wait_send_max_delay_sec: int
    daemon_health_max_age_sec: int


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    if lowered.startswith("sk-replace"):
        return True
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def _required(name: str, reject_placeholders: bool = True) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} environment variable is required")
    if reject_placeholders and _is_placeholder(value):
        raise ValueError(f"{name} appears to be a placeholder value")
    return value


def _read_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got: {raw}") from exc
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got: {value}")
    return value


def _read_float(name: str, default: float, minimum: float = 0.1) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got: {raw}") from exc
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got: {value}")
    return value


def _read_optional_chat_id(name: str) -> Optional[int]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer chat id, got: {raw}") from exc


def _read_allowed_chat_ids() -> Set[int]:
    raw = os.getenv("ALLOWED_CHAT_IDS", "").strip()
    default_chat_id = _read_optional_chat_id("TELEGRAM_CHAT_ID")
    if not raw:
        return {default_chat_id} if default_chat_id is not None else set()
    parsed: Set[int] = set()
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        try:
            parsed.add(int(item))
        except ValueError as exc:
            raise ValueError(f"ALLOWED_CHAT_IDS contains non-integer value: {item}") from exc
    if default_chat_id is not None:
        parsed.add(default_chat_id)
    return parsed


def load_settings(require_openai_api_key: bool = False, require_allowed_chat_ids: bool = False) -> Settings:
    telegram_bot_token = _required("TELEGRAM_BOT_TOKEN")
    if require_openai_api_key:
        raise ValueError("OpenAI-backed worker mode is not implemented in chasecar's Telegram wait bridge")
    allowed_chat_ids = _read_allowed_chat_ids()
    if require_allowed_chat_ids and not allowed_chat_ids:
        raise ValueError("Configure ALLOWED_CHAT_IDS or TELEGRAM_CHAT_ID before starting the wait bridge")

    telegram_poll_timeout_sec = _read_int("TELEGRAM_POLL_TIMEOUT_SEC", default=30, minimum=1)
    telegram_retry_sec = _read_int("TELEGRAM_RETRY_SEC", default=5, minimum=1)
    wait_daemon_idle_poll_timeout_sec = _read_int(
        "WAIT_DAEMON_IDLE_POLL_TIMEOUT_SEC",
        default=1,
        minimum=1,
    )
    daemon_health_max_age_sec = _read_int(
        "DAEMON_HEALTH_MAX_AGE_SEC",
        default=max(90, telegram_poll_timeout_sec + telegram_retry_sec + 45),
        minimum=5,
    )

    return Settings(
        telegram_bot_token=telegram_bot_token,
        db_path=os.getenv("DB_PATH", "/app/data/state.db").strip() or "/app/data/state.db",
        allowed_chat_ids=allowed_chat_ids,
        default_chat_id=_read_optional_chat_id("TELEGRAM_CHAT_ID"),
        telegram_poll_timeout_sec=telegram_poll_timeout_sec,
        telegram_retry_sec=telegram_retry_sec,
        wait_default_timeout_sec=_read_int("WAIT_DEFAULT_TIMEOUT_SEC", default=900, minimum=5),
        wait_max_timeout_sec=_read_int("WAIT_MAX_TIMEOUT_SEC", default=86400, minimum=30),
        wait_daemon_idle_poll_timeout_sec=wait_daemon_idle_poll_timeout_sec,
        wait_status_poll_interval_sec=_read_float("WAIT_STATUS_POLL_INTERVAL_SEC", default=1.0, minimum=0.1),
        wait_send_poll_interval_sec=_read_float("WAIT_SEND_POLL_INTERVAL_SEC", default=0.5, minimum=0.1),
        wait_send_max_delay_sec=_read_int("WAIT_SEND_MAX_DELAY_SEC", default=20, minimum=1),
        daemon_health_max_age_sec=daemon_health_max_age_sec,
    )
