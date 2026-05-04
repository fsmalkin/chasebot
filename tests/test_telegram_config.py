from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from telegram_wait_bridge.config import load_settings


def test_load_settings_defaults_daemon_idle_poll_to_one_second(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.delenv("ALLOWED_CHAT_IDS", raising=False)
    monkeypatch.delenv("WAIT_DAEMON_IDLE_POLL_TIMEOUT_SEC", raising=False)

    settings = load_settings(require_allowed_chat_ids=True)

    assert settings.wait_daemon_idle_poll_timeout_sec == 1


def test_load_settings_allows_daemon_idle_poll_override(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setenv("WAIT_DAEMON_IDLE_POLL_TIMEOUT_SEC", "2")
    monkeypatch.delenv("ALLOWED_CHAT_IDS", raising=False)

    settings = load_settings(require_allowed_chat_ids=True)

    assert settings.wait_daemon_idle_poll_timeout_sec == 2
