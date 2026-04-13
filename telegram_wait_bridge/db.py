"""SQLite persistence for chats, queue state, and job history."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


ACTIVE_WAIT_STATUSES = ("queued", "sending", "awaiting_reply")


@dataclass
class ActiveWaitConflictError(RuntimeError):
    existing_wait_id: str

    def __str__(self) -> str:
        return f"Chat already has an active wait request: {self.existing_wait_id}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _utc_after_seconds(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).replace(microsecond=0).isoformat()


class Database:
    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, timeout=30, isolation_level=None, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA busy_timeout=5000;")
        self._init_schema()

    def close(self) -> None:
        self.conn.close()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                from_username TEXT,
                user_text TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed')),
                response_id TEXT,
                result_text TEXT,
                error_text TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                FOREIGN KEY (chat_id) REFERENCES chats(chat_id)
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_status_id ON jobs(status, id);
            CREATE INDEX IF NOT EXISTS idx_jobs_chat_status_id ON jobs(chat_id, status, id);

            CREATE TABLE IF NOT EXISTS wait_requests (
                id TEXT PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                prompt_text TEXT NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN ('queued', 'sending', 'awaiting_reply', 'fulfilled', 'timed_out', 'cancelled', 'failed')
                ),
                prompt_message_id INTEGER,
                reply_text TEXT,
                reply_message_id INTEGER,
                reply_from_user_id INTEGER,
                error_text TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                resolved_at TEXT,
                FOREIGN KEY (chat_id) REFERENCES chats(chat_id)
            );

            CREATE INDEX IF NOT EXISTS idx_wait_requests_status_created
            ON wait_requests(status, created_at);

            CREATE INDEX IF NOT EXISTS idx_wait_requests_chat_status_created
            ON wait_requests(chat_id, status, created_at);

            CREATE INDEX IF NOT EXISTS idx_wait_requests_prompt_lookup
            ON wait_requests(chat_id, prompt_message_id, status);
            """
        )

    def get_state(self, key: str) -> Optional[str]:
        row = self.conn.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row["value"])

    def set_state(self, key: str, value: str) -> None:
        self.conn.execute(
            """
            INSERT INTO state (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )

    def upsert_chat(
        self,
        chat_id: int,
        username: Optional[str],
        first_name: Optional[str],
        last_name: Optional[str],
    ) -> None:
        now = _utc_now()
        self.conn.execute(
            """
            INSERT INTO chats (chat_id, username, first_name, last_name, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                updated_at = excluded.updated_at
            """,
            (chat_id, username, first_name, last_name, now),
        )

    def enqueue_job(self, chat_id: int, from_username: Optional[str], user_text: str) -> int:
        now = _utc_now()
        cur = self.conn.execute(
            """
            INSERT INTO jobs (chat_id, from_username, user_text, status, created_at)
            VALUES (?, ?, ?, 'queued', ?)
            """,
            (chat_id, from_username, user_text, now),
        )
        return int(cur.lastrowid)

    def count_open_jobs_for_chat(self, chat_id: int) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM jobs
            WHERE chat_id = ? AND status IN ('queued', 'running')
            """,
            (chat_id,),
        ).fetchone()
        return int(row["count"]) if row else 0

    def latest_job_for_chat(self, chat_id: int) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            """
            SELECT id, status, response_id, result_text, error_text, created_at, started_at, finished_at
            FROM jobs
            WHERE chat_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (chat_id,),
        ).fetchone()
        return None if row is None else dict(row)

    def claim_next_job(self) -> Optional[Dict[str, Any]]:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            row = self.conn.execute(
                """
                SELECT id, chat_id, from_username, user_text, created_at
                FROM jobs AS candidate
                WHERE candidate.status = 'queued'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM jobs AS running
                      WHERE running.chat_id = candidate.chat_id
                        AND running.status = 'running'
                  )
                ORDER BY candidate.id ASC
                LIMIT 1
                """
            ).fetchone()

            if row is None:
                self.conn.execute("COMMIT")
                return None

            now = _utc_now()
            self.conn.execute(
                "UPDATE jobs SET status = 'running', started_at = ? WHERE id = ?",
                (now, row["id"]),
            )
            self.conn.execute("COMMIT")
            claimed = dict(row)
            claimed["status"] = "running"
            claimed["started_at"] = now
            return claimed
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def set_response_id(self, job_id: int, response_id: str) -> None:
        self.conn.execute("UPDATE jobs SET response_id = ? WHERE id = ?", (response_id, job_id))

    def complete_job(self, job_id: int, result_text: str) -> None:
        now = _utc_now()
        self.conn.execute(
            """
            UPDATE jobs
            SET status = 'completed',
                result_text = ?,
                error_text = NULL,
                finished_at = ?
            WHERE id = ?
            """,
            (result_text, now, job_id),
        )

    def fail_job(self, job_id: int, error_text: str) -> None:
        now = _utc_now()
        self.conn.execute(
            """
            UPDATE jobs
            SET status = 'failed',
                error_text = ?,
                finished_at = ?
            WHERE id = ?
            """,
            (error_text, now, job_id),
        )

    def recent_completed_jobs(self, chat_id: int, limit: int) -> List[Dict[str, str]]:
        if limit <= 0:
            return []
        rows = self.conn.execute(
            """
            SELECT user_text, result_text
            FROM jobs
            WHERE chat_id = ?
              AND status = 'completed'
              AND result_text IS NOT NULL
            ORDER BY id DESC
            LIMIT ?
            """,
            (chat_id, limit),
        ).fetchall()
        history = [dict(row) for row in rows]
        history.reverse()
        return history

    def create_wait_request(self, chat_id: int, prompt_text: str, timeout_seconds: int) -> Dict[str, Any]:
        wait_id = str(uuid4())
        now = _utc_now()
        expires_at = _utc_after_seconds(timeout_seconds)
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            existing = self.conn.execute(
                """
                SELECT id
                FROM wait_requests
                WHERE chat_id = ?
                  AND status IN ('queued', 'sending', 'awaiting_reply')
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (chat_id,),
            ).fetchone()
            if existing is not None:
                raise ActiveWaitConflictError(str(existing["id"]))

            self.conn.execute(
                """
                INSERT INTO wait_requests (
                    id,
                    chat_id,
                    prompt_text,
                    status,
                    created_at,
                    updated_at,
                    expires_at
                )
                VALUES (?, ?, ?, 'queued', ?, ?, ?)
                """,
                (wait_id, chat_id, prompt_text, now, now, expires_at),
            )
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise
        return self.get_wait_request(wait_id)

    def get_wait_request(self, wait_id: str) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            """
            SELECT id, chat_id, prompt_text, status, prompt_message_id, reply_text, reply_message_id,
                   reply_from_user_id, error_text, created_at, updated_at, expires_at, resolved_at
            FROM wait_requests
            WHERE id = ?
            """,
            (wait_id,),
        ).fetchone()
        return None if row is None else dict(row)

    def get_active_wait_for_chat(self, chat_id: int) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            """
            SELECT id, chat_id, prompt_text, status, prompt_message_id, reply_text, reply_message_id,
                   reply_from_user_id, error_text, created_at, updated_at, expires_at, resolved_at
            FROM wait_requests
            WHERE chat_id = ?
              AND status IN ('queued', 'sending', 'awaiting_reply')
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (chat_id,),
        ).fetchone()
        return None if row is None else dict(row)

    def has_queued_wait_requests(self) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM wait_requests WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        return row is not None

    def claim_next_wait_request(self) -> Optional[Dict[str, Any]]:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            row = self.conn.execute(
                """
                SELECT id, chat_id, prompt_text, created_at, updated_at, expires_at
                FROM wait_requests
                WHERE status = 'queued'
                ORDER BY created_at ASC
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                self.conn.execute("COMMIT")
                return None

            now = _utc_now()
            self.conn.execute(
                "UPDATE wait_requests SET status = 'sending', updated_at = ? WHERE id = ?",
                (now, row["id"]),
            )
            self.conn.execute("COMMIT")
            claimed = dict(row)
            claimed["status"] = "sending"
            claimed["updated_at"] = now
            return claimed
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def mark_wait_request_sent(self, wait_id: str, prompt_message_id: int) -> None:
        now = _utc_now()
        self.conn.execute(
            """
            UPDATE wait_requests
            SET status = 'awaiting_reply',
                prompt_message_id = ?,
                error_text = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (prompt_message_id, now, wait_id),
        )

    def fulfill_wait_request(
        self,
        wait_id: str,
        reply_text: str,
        reply_message_id: int,
        reply_from_user_id: Optional[int],
    ) -> None:
        now = _utc_now()
        self.conn.execute(
            """
            UPDATE wait_requests
            SET status = 'fulfilled',
                reply_text = ?,
                reply_message_id = ?,
                reply_from_user_id = ?,
                error_text = NULL,
                updated_at = ?,
                resolved_at = ?
            WHERE id = ?
            """,
            (reply_text, reply_message_id, reply_from_user_id, now, now, wait_id),
        )

    def fail_wait_request(self, wait_id: str, error_text: str) -> None:
        now = _utc_now()
        self.conn.execute(
            """
            UPDATE wait_requests
            SET status = 'failed',
                error_text = ?,
                updated_at = ?,
                resolved_at = ?
            WHERE id = ?
            """,
            (error_text, now, now, wait_id),
        )

    def cancel_wait_request(self, wait_id: str, reason: Optional[str] = None) -> Optional[Dict[str, Any]]:
        current = self.get_wait_request(wait_id)
        if current is None:
            return None
        if current["status"] not in ACTIVE_WAIT_STATUSES:
            return current
        now = _utc_now()
        self.conn.execute(
            """
            UPDATE wait_requests
            SET status = 'cancelled',
                error_text = ?,
                updated_at = ?,
                resolved_at = ?
            WHERE id = ?
            """,
            (reason or "Cancelled by operator", now, now, wait_id),
        )
        return self.get_wait_request(wait_id)

    def expire_wait_requests(self) -> int:
        now = _utc_now()
        cur = self.conn.execute(
            """
            UPDATE wait_requests
            SET status = 'timed_out',
                error_text = 'Timed out waiting for reply',
                updated_at = ?,
                resolved_at = ?
            WHERE status IN ('queued', 'sending', 'awaiting_reply')
              AND expires_at <= ?
            """,
            (now, now, now),
        )
        return int(cur.rowcount or 0)

    def find_wait_request_by_prompt_message(self, chat_id: int, prompt_message_id: int) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            """
            SELECT id, chat_id, prompt_text, status, prompt_message_id, reply_text, reply_message_id,
                   reply_from_user_id, error_text, created_at, updated_at, expires_at, resolved_at
            FROM wait_requests
            WHERE chat_id = ?
              AND prompt_message_id = ?
              AND status = 'awaiting_reply'
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (chat_id, prompt_message_id),
        ).fetchone()
        return None if row is None else dict(row)

    def is_state_fresh(self, key: str, max_age_sec: int) -> bool:
        raw = self.get_state(key)
        if raw is None:
            return False
        try:
            age = datetime.now(timezone.utc) - _parse_timestamp(raw)
        except ValueError:
            return False
        return age.total_seconds() <= max_age_sec
