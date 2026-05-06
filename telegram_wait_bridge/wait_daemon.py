"""Long-lived Telegram daemon for the Docker MCP wait bridge."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Tuple

from telegram_wait_bridge.config import Settings, load_settings
from telegram_wait_bridge.db import Database
from telegram_wait_bridge.telegram_api import TelegramApi
from telegram_wait_bridge.wait_service import format_prompt_for_delivery

LOG = logging.getLogger("telegram-daemon")

HELP_TEXT = (
    "This bot is running in wait-bridge mode.\n"
    "Use Telegram's direct reply action on the specific prompt message you want to answer."
)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    settings = load_settings(require_allowed_chat_ids=True)
    LOG.info("Wait daemon starting with DB at %s", settings.db_path)
    db = Database(settings.db_path)
    telegram = TelegramApi(settings.telegram_bot_token)

    try:
        offset = _read_offset(db)
        while True:
            try:
                _touch_heartbeat(db)
                expired = db.expire_wait_requests()
                if expired:
                    LOG.info("Expired %s wait request(s)", expired)

                _dispatch_queued_waits(db=db, telegram=telegram)

                timeout_sec = 1 if db.has_queued_wait_requests() else settings.wait_daemon_idle_poll_timeout_sec
                updates = telegram.get_updates(offset=offset, timeout_sec=timeout_sec)
                _touch_heartbeat(db)

                for update in updates:
                    offset = _next_offset(offset, update)
                    db.set_state("telegram_offset", str(offset))
                    _handle_update(update=update, settings=settings, db=db, telegram=telegram)
            except Exception as exc:
                db.set_state("daemon_last_error", str(exc)[:1000])
                LOG.exception("Daemon loop error: %s", exc)
                time.sleep(settings.telegram_retry_sec)
    finally:
        telegram.close()
        db.close()


def _touch_heartbeat(db: Database) -> None:
    db.set_state("daemon_heartbeat", time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()))


def _read_offset(db: Database) -> int:
    raw = db.get_state("telegram_offset")
    if raw is None:
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0


def _next_offset(current: int, update: Dict[str, Any]) -> int:
    update_id = update.get("update_id")
    if isinstance(update_id, int):
        return max(current, update_id + 1)
    return current


def _dispatch_queued_waits(db: Database, telegram: TelegramApi) -> None:
    while True:
        wait_request = db.claim_next_wait_request()
        if wait_request is None:
            return

        wait_id = str(wait_request["id"])
        chat_id = int(wait_request["chat_id"])
        prompt_text = str(wait_request["prompt_text"])
        try:
            sent_messages = telegram.send_message(
                chat_id=chat_id,
                text=format_prompt_for_delivery(prompt_text),
                allow_chunking=False,
            )
            if not sent_messages:
                raise RuntimeError("Telegram sendMessage returned no sent message metadata")
            message_id = sent_messages[0].get("message_id")
            if not isinstance(message_id, int):
                raise RuntimeError("Telegram sendMessage did not return an integer message_id")
            db.mark_wait_request_sent(wait_id=wait_id, prompt_message_id=message_id)
            LOG.info("Dispatched wait id=%s chat_id=%s message_id=%s", wait_id, chat_id, message_id)
        except Exception as exc:
            db.fail_wait_request(wait_id=wait_id, error_text=str(exc)[:2000])
            LOG.exception("Failed to dispatch wait id=%s chat_id=%s", wait_id, chat_id)


def _handle_update(update: Dict[str, Any], settings: Settings, db: Database, telegram: TelegramApi) -> None:
    payload = _extract_message(update)
    if payload is None:
        return

    message, text = payload
    chat = message.get("chat", {})
    chat_id = int(chat.get("id"))
    if chat_id not in settings.allowed_chat_ids:
        LOG.warning("Ignoring unauthorized chat_id=%s", chat_id)
        return

    username = _username_from_message(message)
    first_name = _safe_str(chat.get("first_name"))
    last_name = _safe_str(chat.get("last_name"))
    db.upsert_chat(chat_id=chat_id, username=username, first_name=first_name, last_name=last_name)

    command = text.split()[0].lower()
    if command in {"/start", "/help"}:
        telegram.send_message(chat_id=chat_id, text=HELP_TEXT)
        return

    if command == "/status":
        telegram.send_message(chat_id=chat_id, text=_format_status(db.get_active_wait_for_chat(chat_id)))
        return

    reply_to_message_id = _reply_to_message_id(message)
    if reply_to_message_id is not None:
        active_wait = db.find_wait_request_by_prompt_message(chat_id=chat_id, prompt_message_id=reply_to_message_id)
        if active_wait is not None:
            db.fulfill_wait_request(
                wait_id=str(active_wait["id"]),
                reply_text=text,
                reply_message_id=int(message["message_id"]),
                reply_from_user_id=_from_user_id(message),
            )
            LOG.info("Resolved wait id=%s chat_id=%s reply_message_id=%s", active_wait["id"], chat_id, message["message_id"])
            return

    active_wait = db.get_active_wait_for_chat(chat_id)
    if active_wait is not None:
        telegram.send_message(
            chat_id=chat_id,
            text="I still have a pending prompt for you. Use Telegram's direct reply action on that prompt.",
        )


def _extract_message(update: Dict[str, Any]) -> Optional[Tuple[Dict[str, Any], str]]:
    message = update.get("message") or update.get("edited_message")
    if not isinstance(message, dict):
        return None
    text = message.get("text")
    if not isinstance(text, str):
        return None
    return message, text.strip()


def _reply_to_message_id(message: Dict[str, Any]) -> Optional[int]:
    reply_to = message.get("reply_to_message")
    if not isinstance(reply_to, dict):
        return None
    message_id = reply_to.get("message_id")
    return message_id if isinstance(message_id, int) else None


def _from_user_id(message: Dict[str, Any]) -> Optional[int]:
    user = message.get("from")
    if not isinstance(user, dict):
        return None
    user_id = user.get("id")
    return user_id if isinstance(user_id, int) else None


def _username_from_message(message: Dict[str, Any]) -> Optional[str]:
    user = message.get("from")
    if not isinstance(user, dict):
        return None
    return _safe_str(user.get("username"))


def _safe_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _format_status(active_wait: Optional[Dict[str, Any]]) -> str:
    if active_wait is None:
        return "No active prompt right now."
    prompt_message_id = active_wait.get("prompt_message_id")
    prompt_id_text = f" message #{prompt_message_id}" if prompt_message_id else ""
    return f"Waiting for a reply to{prompt_id_text}. Reply directly to the pending prompt message."


if __name__ == "__main__":
    main()
