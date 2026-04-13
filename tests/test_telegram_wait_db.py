from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from telegram_wait_bridge.db import ActiveWaitConflictError, Database


def test_create_wait_request_blocks_second_active_wait(tmp_path: Path) -> None:
    db = Database(str(tmp_path / "state.db"))
    try:
        db.upsert_chat(chat_id=123, username="tester", first_name="Test", last_name="User")
        first = db.create_wait_request(chat_id=123, prompt_text="First prompt", timeout_seconds=60)

        try:
            db.create_wait_request(chat_id=123, prompt_text="Second prompt", timeout_seconds=60)
        except ActiveWaitConflictError as exc:
            assert str(first["id"]) == exc.existing_wait_id
        else:
            raise AssertionError("Expected ActiveWaitConflictError for a second active wait")
    finally:
        db.close()


def test_find_wait_request_by_prompt_message_returns_active_match(tmp_path: Path) -> None:
    db = Database(str(tmp_path / "state.db"))
    try:
        db.upsert_chat(chat_id=123, username="tester", first_name="Test", last_name="User")
        created = db.create_wait_request(chat_id=123, prompt_text="Prompt", timeout_seconds=60)
        db.mark_wait_request_sent(wait_id=str(created["id"]), prompt_message_id=987)

        matched = db.find_wait_request_by_prompt_message(chat_id=123, prompt_message_id=987)

        assert matched is not None
        assert str(created["id"]) == matched["id"]
    finally:
        db.close()


def test_cancel_wait_request_marks_terminal(tmp_path: Path) -> None:
    db = Database(str(tmp_path / "state.db"))
    try:
        db.upsert_chat(chat_id=123, username="tester", first_name="Test", last_name="User")
        created = db.create_wait_request(chat_id=123, prompt_text="Prompt", timeout_seconds=60)

        cancelled = db.cancel_wait_request(wait_id=str(created["id"]), reason="No longer needed")

        assert cancelled is not None
        assert cancelled["status"] == "cancelled"
        assert cancelled["error_text"] == "No longer needed"
    finally:
        db.close()
