"""Shared environment loading helpers for Chasecar scripts."""

from __future__ import annotations

import os
from pathlib import Path


def load_repo_dotenv(repo_root: Path) -> Path | None:
    """Load key=value pairs from repo .env without overriding process env."""
    dotenv_path = Path(repo_root) / ".env"
    if not dotenv_path.is_file():
        return None
    with dotenv_path.open(encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    return dotenv_path
