from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_planner_llm_shadow_evidence as evidence  # noqa: E402


def _write_gate(path: Path, *, ready: bool = True, wrong_fetch: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "campaign_id": path.parents[1].name,
        "planner_mode": "llm_shadow",
        "scene_set": "mixed_fetch_planner_v1",
        "seed": 123,
        "random_cases": 3,
        "pass": ready and wrong_fetch == 0,
        "pass_count": 3 if ready and wrong_fetch == 0 else 2,
        "fail_count": 0 if ready and wrong_fetch == 0 else 1,
        "llm_shadow_ready": ready and wrong_fetch == 0,
        "llm_shadow_provider_ok_count": 3 if ready else 2,
        "provider_status_counts": {"ok": 3 if ready else 2, "error": 0 if ready else 1},
        "planner_mode_effective_counts": {"llm_shadow": 3 if ready else 2, "deterministic_fallback": 0 if ready else 1},
        "guard_agreement_count": 3 if ready else 2,
        "guard_disagreement_count": 0 if ready else 1,
        "wrong_fetch_dispatch_count": wrong_fetch,
        "route_counts": {
            "fetch_ready_local": 1,
            "nav2_reposition_first": 1,
            "recovery_or_reaim": 1,
        },
        "expected_route_counts": {
            "fetch_ready_local": 1,
            "nav2_reposition_first": 1,
            "recovery_or_reaim": 1,
        },
    }
    path.write_text(evidence.json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_llm_shadow_evidence_aggregates_green_gates(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence, "REPO_ROOT", tmp_path)
    gate_a = tmp_path / "artifacts" / "session" / "gate_a" / "fetch_planner_handoff_gate" / "gate_summary.json"
    gate_b = tmp_path / "artifacts" / "session" / "gate_b" / "fetch_planner_handoff_gate" / "gate_summary.json"
    _write_gate(gate_a)
    _write_gate(gate_b)
    args = SimpleNamespace(campaign_id="shadow_rollup", planner_summary=[str(gate_a), str(gate_b)])

    summary = evidence.build_summary(args)

    assert summary["pass"] is True
    assert summary["milestone_interpretation"] == "llm_shadow_route_selection_green"
    assert summary["gate_count"] == 2
    assert summary["total_cases"] == 6
    assert summary["provider_ok_count"] == 6
    assert summary["guard_agreement_count"] == 6
    assert summary["wrong_fetch_dispatch_count"] == 0
    assert summary["all_shadow_ready"] is True
    assert summary["route_counts"]["fetch_ready_local"] == 2


def test_llm_shadow_evidence_blocks_on_provider_or_dispatch_gap(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence, "REPO_ROOT", tmp_path)
    gate = tmp_path / "artifacts" / "session" / "gate_bad" / "fetch_planner_handoff_gate" / "gate_summary.json"
    _write_gate(gate, ready=False, wrong_fetch=1)
    args = SimpleNamespace(campaign_id="shadow_rollup_bad", planner_summary=[str(gate)])

    summary = evidence.build_summary(args)

    assert summary["pass"] is False
    assert summary["milestone_interpretation"] == "llm_shadow_route_selection_incomplete"
    assert "provider_not_ok_for_all_cases" in summary["blocking_reasons"]
    assert "wrong_fetch_dispatch" in summary["blocking_reasons"]
