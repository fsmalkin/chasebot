from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_uat_orchestrator_shell_script_uses_lf_line_endings():
    path = REPO_ROOT / "uat" / "orchestrator" / "run_uat_orchestrator.sh"
    payload = path.read_bytes()

    assert payload.startswith(b"#!/usr/bin/env bash\nset -euo pipefail\n")
    assert b"\r\n" not in payload
