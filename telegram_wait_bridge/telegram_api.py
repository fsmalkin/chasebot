"""Minimal Telegram Bot API client."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

import httpx


class TelegramConflictError(RuntimeError):
    """Raised when Telegram rejects getUpdates because another poller owns the bot."""


class TelegramApi:
    def __init__(self, bot_token: str) -> None:
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.client = httpx.Client(timeout=60.0)

    def close(self) -> None:
        self.client.close()

    def _post(self, method: str, payload: Dict[str, Any], timeout: float) -> Any:
        response = self.client.post(f"{self.base_url}/{method}", json=payload, timeout=timeout)
        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.is_error:
            description = body.get("description") if isinstance(body, dict) else None
            if description:
                raise self._build_error(method, description)
            response.raise_for_status()
        if not body.get("ok"):
            description = body.get("description", "unknown Telegram API error")
            raise self._build_error(method, description)
        return body.get("result")

    @staticmethod
    def _build_error(method: str, description: str) -> RuntimeError:
        message = f"Telegram API {method} failed: {description}"
        if method == "getUpdates" and "Conflict" in description:
            return TelegramConflictError(message)
        return RuntimeError(message)

    def get_updates(self, offset: int, timeout_sec: int) -> List[Dict[str, Any]]:
        payload = {
            "offset": offset,
            "timeout": timeout_sec,
            "allowed_updates": ["message", "edited_message"],
        }
        timeout = float(timeout_sec + 10)
        result = self._post("getUpdates", payload, timeout=timeout)
        return result if isinstance(result, list) else []

    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to_message_id: Optional[int] = None,
        allow_chunking: bool = True,
    ) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        chunks = list(_chunk_text(text))
        if not allow_chunking and len(chunks) > 1:
            raise ValueError("send_message received text that would require multiple Telegram messages")
        for chunk in chunks:
            payload: Dict[str, Any] = {
                "chat_id": chat_id,
                "text": chunk,
                "disable_web_page_preview": True,
            }
            if reply_to_message_id is not None:
                payload["reply_to_message_id"] = reply_to_message_id
            result = self._post("sendMessage", payload, timeout=30.0)
            if isinstance(result, dict):
                messages.append(result)
        return messages


def _chunk_text(text: str, max_len: int = 3900) -> Iterable[str]:
    remaining = text.strip()
    if not remaining:
        yield "(empty)"
        return
    while len(remaining) > max_len:
        split_at = remaining.rfind("\n", 0, max_len)
        if split_at <= 0:
            split_at = max_len
        yield remaining[:split_at]
        remaining = remaining[split_at:].lstrip()
    yield remaining
