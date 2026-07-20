from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import chasecar_env  # noqa: E402


def test_load_repo_dotenv_sets_missing_key_without_overriding(tmp_path: Path, monkeypatch):
    dotenv = tmp_path / ".env"
    dotenv.write_text("OPENAI_API_KEY=from-dotenv\nEXISTING=value-from-dotenv\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("EXISTING", "process-value")

    loaded = chasecar_env.load_repo_dotenv(tmp_path)

    assert loaded == dotenv
    assert os.environ["OPENAI_API_KEY"] == "from-dotenv"
    assert os.environ["EXISTING"] == "process-value"
