from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import visit_mission_repeatability_runner as repeat_runner  # noqa: E402


def test_promotion_gate_pass_for_runs_strict_requires_hidden_start_search_first():
    runs = [{"pass": True, "hidden_start_search_first": False}]

    assert repeat_runner.promotion_gate_pass_for_runs(runs, mode="strict") is False


def test_promotion_gate_pass_for_runs_pass_only_accepts_all_green_runs():
    runs = [{"pass": True, "hidden_start_search_first": False}]

    assert repeat_runner.promotion_gate_pass_for_runs(runs, mode="pass_only") is True
