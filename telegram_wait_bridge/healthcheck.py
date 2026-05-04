"""Container health check for the Telegram wait daemon."""

from __future__ import annotations

import os
import sys

from telegram_wait_bridge.config import load_settings
from telegram_wait_bridge.db import Database
from telegram_wait_bridge.wait_daemon import GETUPDATES_CONFLICT_STATE_KEY

GETUPDATES_CONFLICT_THRESHOLD_DEFAULT = 3


def _conflict_threshold() -> int:
    raw = os.getenv("GETUPDATES_CONFLICT_THRESHOLD", str(GETUPDATES_CONFLICT_THRESHOLD_DEFAULT)).strip()
    try:
        value = int(raw)
    except ValueError:
        return GETUPDATES_CONFLICT_THRESHOLD_DEFAULT
    return value if value > 0 else GETUPDATES_CONFLICT_THRESHOLD_DEFAULT


def main() -> int:
    settings = load_settings(require_allowed_chat_ids=False)
    db = Database(settings.db_path)
    try:
        if not db.is_state_fresh("daemon_heartbeat", settings.daemon_health_max_age_sec):
            print("daemon heartbeat is stale or missing", file=sys.stderr)
            return 1
        raw_conflicts = db.get_state(GETUPDATES_CONFLICT_STATE_KEY)
        try:
            consecutive = int(raw_conflicts) if raw_conflicts is not None else 0
        except ValueError:
            consecutive = 0
        threshold = _conflict_threshold()
        if consecutive >= threshold:
            print(
                f"telegram getUpdates Conflict persisting (consecutive={consecutive}, threshold={threshold}). "
                "Another bot poller is stealing replies; stop the duplicate daemon.",
                file=sys.stderr,
            )
            return 1
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
