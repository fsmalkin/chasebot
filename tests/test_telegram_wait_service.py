from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from telegram_wait_bridge.wait_service import MAX_PROMPT_CHARS, resolve_chat_id, validate_prompt_text


def test_resolve_chat_id_prefers_default() -> None:
    settings = SimpleNamespace(default_chat_id=42, allowed_chat_ids={42})

    assert resolve_chat_id(settings, None) == 42


def test_resolve_chat_id_rejects_non_allowlisted_chat() -> None:
    settings = SimpleNamespace(default_chat_id=None, allowed_chat_ids={42})

    with pytest.raises(ValueError):
        resolve_chat_id(settings, 43)


def test_validate_prompt_text_rejects_blank_and_overlong() -> None:
    with pytest.raises(ValueError):
        validate_prompt_text("   ")

    with pytest.raises(ValueError):
        validate_prompt_text("x" * (MAX_PROMPT_CHARS + 1))
