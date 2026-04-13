"""Container health check for the Telegram wait daemon."""

from __future__ import annotations

import sys

from telegram_wait_bridge.config import load_settings
from telegram_wait_bridge.db import Database


def main() -> int:
    settings = load_settings(require_allowed_chat_ids=False)
    db = Database(settings.db_path)
    try:
        if not db.is_state_fresh("daemon_heartbeat", settings.daemon_health_max_age_sec):
            print("daemon heartbeat is stale or missing", file=sys.stderr)
            return 1
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
