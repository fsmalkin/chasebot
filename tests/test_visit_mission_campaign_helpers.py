from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from visit_mission_campaign_helpers import campaign_pass  # noqa: E402
from visit_mission_campaign_helpers import first_dispatched_intents_by_target  # noqa: E402
from visit_mission_campaign_helpers import hidden_start_search_first  # noqa: E402


def test_first_dispatched_intents_by_target_picks_first_only():
    sequence = [
        {"event_type": "decision_dispatched", "target_id": "ball_1", "decision": {"intent": "search_for_target"}},
        {"event_type": "decision_dispatched", "target_id": "ball_1", "decision": {"intent": "track_target"}},
        {"event_type": "decision_dispatched", "target_id": "ball_2", "decision": {"intent": "acquire_target"}},
    ]

    result = first_dispatched_intents_by_target(sequence)

    assert result == {"ball_1": "search_for_target", "ball_2": "acquire_target"}


def test_hidden_start_search_first_requires_search_on_hidden_targets():
    target_results = [
        {"target_id": "ball_1", "started_visible": False, "first_dispatched_intent": "search_for_target"},
        {"target_id": "ball_2", "started_visible": True, "first_dispatched_intent": "acquire_target"},
    ]
    assert hidden_start_search_first(target_results) is True

    target_results[0]["first_dispatched_intent"] = "acquire_target"
    assert hidden_start_search_first(target_results) is False


def test_campaign_pass_requires_all_runs_green_and_search_first():
    runs = [
        {"pass": True, "hidden_start_search_first": True},
        {"pass": True, "hidden_start_search_first": True},
    ]
    assert campaign_pass(runs) is True

    runs[1]["hidden_start_search_first"] = False
    assert campaign_pass(runs) is False
