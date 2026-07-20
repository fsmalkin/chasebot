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


def _write_supervised_gate(
    path: Path,
    *,
    ready: bool = True,
    accepted: int = 3,
    vetoed: int = 0,
    provider_ok: int = 3,
    route_pass: bool | None = None,
    guard_agreement_count: int | None = None,
    veto_reasons: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    total = 3
    route_pass = ready if route_pass is None else route_pass
    guard_agreement_count = (
        total if guard_agreement_count is None and vetoed == 0 else guard_agreement_count
    )
    guard_agreement_count = total - vetoed if guard_agreement_count is None else guard_agreement_count
    veto_reasons = veto_reasons or []
    payload = {
        "campaign_id": path.parents[1].name,
        "planner_mode": "llm_supervised_guarded",
        "scene_set": "mixed_fetch_planner_v1",
        "seed": 456,
        "random_cases": total,
        "pass": route_pass,
        "pass_count": total if route_pass else 2,
        "fail_count": 0 if route_pass else 1,
        "llm_shadow_provider_ok_count": provider_ok,
        "llm_shadow_ready": False,
        "llm_supervised_ready": ready and accepted == total and vetoed == 0 and provider_ok == total,
        "llm_supervised_accept_count": accepted,
        "llm_supervised_veto_count": vetoed,
        "provider_status_counts": {"ok": provider_ok, "error": total - provider_ok},
        "planner_mode_effective_counts": {
            "llm_supervised_guarded": accepted,
            "deterministic_fallback": vetoed,
        },
        "guard_agreement_count": guard_agreement_count,
        "guard_disagreement_count": total - guard_agreement_count,
        "wrong_fetch_dispatch_count": 0,
        "results": [
            {
                "llm_supervised_guard": {
                    "decision": "vetoed",
                    "veto_reasons": veto_reasons,
                }
            }
            for _ in range(vetoed)
        ],
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


def test_llm_supervised_evidence_aggregates_accepted_gates(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence, "REPO_ROOT", tmp_path)
    gate_a = tmp_path / "artifacts" / "session" / "gate_a" / "fetch_planner_handoff_gate" / "gate_summary.json"
    gate_b = tmp_path / "artifacts" / "session" / "gate_b" / "fetch_planner_handoff_gate" / "gate_summary.json"
    _write_supervised_gate(gate_a)
    _write_supervised_gate(gate_b)
    args = SimpleNamespace(
        campaign_id="supervised_rollup",
        expected_planner_mode="llm_supervised_guarded",
        planner_summary=[str(gate_a), str(gate_b)],
    )

    summary = evidence.build_summary(args)

    assert summary["pass"] is True
    assert summary["milestone_interpretation"] == "llm_supervised_route_selection_green"
    assert summary["total_cases"] == 6
    assert summary["provider_ok_count"] == 6
    assert summary["guard_agreement_count"] == 6
    assert summary["llm_supervised_accept_count"] == 6
    assert summary["llm_supervised_veto_count"] == 0
    assert summary["all_supervised_ready"] is True


def test_llm_supervised_evidence_blocks_on_veto_or_provider_gap(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence, "REPO_ROOT", tmp_path)
    gate = tmp_path / "artifacts" / "session" / "gate_bad" / "fetch_planner_handoff_gate" / "gate_summary.json"
    _write_supervised_gate(gate, ready=False, accepted=2, vetoed=1, provider_ok=2)
    args = SimpleNamespace(
        campaign_id="supervised_rollup_bad",
        expected_planner_mode="llm_supervised_guarded",
        planner_summary=[str(gate)],
    )

    summary = evidence.build_summary(args)

    assert summary["pass"] is False
    assert summary["milestone_interpretation"] == "llm_supervised_route_selection_incomplete"
    assert "provider_not_ok_for_all_cases" in summary["blocking_reasons"]
    assert "guard_disagreement" in summary["blocking_reasons"]
    assert "supervised_not_accepted_for_all_cases" in summary["watch_reasons"]
    assert "supervised_veto_present" in summary["watch_reasons"]


def test_llm_supervised_evidence_accepts_confidence_veto_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence, "REPO_ROOT", tmp_path)
    gate = tmp_path / "artifacts" / "session" / "gate_confidence" / "fetch_planner_handoff_gate" / "gate_summary.json"
    _write_supervised_gate(
        gate,
        ready=False,
        accepted=2,
        vetoed=1,
        provider_ok=3,
        route_pass=True,
        guard_agreement_count=3,
        veto_reasons=["confidence_below_threshold"],
    )
    args = SimpleNamespace(
        campaign_id="supervised_confidence_rollup",
        expected_planner_mode="llm_supervised_guarded",
        planner_summary=[str(gate)],
    )

    summary = evidence.build_summary(args)

    assert summary["pass"] is True
    assert summary["milestone_interpretation"] == "llm_supervised_guarded_fallback_green"
    assert summary["strict_supervised_acceptance_ready"] is False
    assert summary["supervised_guarded_fallback_ready"] is True
    assert summary["llm_supervised_veto_reason_counts"] == {"confidence_below_threshold": 1}
    assert summary["blocking_reasons"] == []
    assert "supervised_veto_present" in summary["watch_reasons"]
