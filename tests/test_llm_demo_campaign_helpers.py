from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from llm_demo_campaign_helpers import campaign_pass  # noqa: E402
from llm_demo_campaign_helpers import summarize_demo_run  # noqa: E402


def test_summarize_demo_run_reads_first_decision_and_invalid_counts(tmp_path):
    proof_root = tmp_path / "proof"
    proof_root.mkdir(parents=True)
    (proof_root / "summary.json").write_text(
        json.dumps({"session_id": "session-a", "pass": True}),
        encoding="utf-8",
    )
    (proof_root / "proof_verdict.json").write_text(
        json.dumps({"session_id": "session-a", "pass": True}),
        encoding="utf-8",
    )
    (proof_root / "decision_history.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"decision": {"status": "blocked", "intent": "", "missing_prerequisites": ["provider_output_invalid"]}}),
                json.dumps({"decision": {"status": "recommendation", "intent": "search_for_target", "missing_prerequisites": []}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    output = f"LLM_TURN_THEN_GO_PROOF_SUMMARY={proof_root / 'proof_verdict.json'}\n"
    summary = summarize_demo_run(
        run_index=1,
        return_code=0,
        output=output,
        summary_marker="LLM_TURN_THEN_GO_PROOF_SUMMARY=",
    )

    assert summary["session_id"] == "session-a"
    assert summary["first_decision_seen"] == "blocked"
    assert summary["invalid_provider_output_count"] == 1
    assert summary["blocked_only"] is False


def test_campaign_pass_requires_all_runs_green():
    assert campaign_pass(
        [
            {"pass": True, "invalid_provider_output_count": 0, "blocked_only": False},
            {"pass": True, "invalid_provider_output_count": 0, "blocked_only": False},
        ]
    ) is True
    assert campaign_pass(
        [
            {"pass": True, "invalid_provider_output_count": 0, "blocked_only": False},
            {"pass": False, "invalid_provider_output_count": 0, "blocked_only": False},
        ]
    ) is False
