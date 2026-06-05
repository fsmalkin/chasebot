from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_planner_handoff_gate as planner_gate  # noqa: E402
import fetch_planner_route_replay_batch as replay_batch  # noqa: E402
import fetch_planner_route_uat_analyzer as route_analyzer  # noqa: E402
import fetch_planner_seeded_generalization_gate as seeded_gate  # noqa: E402


def _args(**overrides):
    payload = {
        "campaign_id": "seeded_gate",
        "dry_run": True,
        "random_cases": 30,
        "seed": 20260627,
        "scene_set": planner_gate.DEFAULT_SCENE_SET,
        "scene_descriptor_json": [],
        "scene_dir": "",
        "reuse_planner_summary": "",
        "reuse_replay_summary": "",
        "planner_mode": planner_gate.PLANNER_MODE_DETERMINISTIC,
        "openai_model": planner_gate.DEFAULT_OPENAI_MODEL,
        "openai_api_key": "",
        "openai_base_url": planner_gate.DEFAULT_OPENAI_BASE_URL,
        "openai_org_id": "",
        "openai_project_id": "",
        "reasoning_effort": planner_gate.DEFAULT_REASONING_EFFORT,
        "planner_timeout_s": 45.0,
        "max_per_route": 2,
        "route": [],
        "scene_id": [],
        "skip_scene_id": [],
        "quality_order": "source",
        "dashboard_url": "http://127.0.0.1:8879",
        "compose_project": "",
        "fresh_dashboard_session_per_run": True,
        "allow_operator_view_degraded": False,
        "world_file": "yolo_test_world_v6_calibrated_golf_turf.world",
        "surface_profile": "calibrated_golf_turf",
        "robot_sdf_name": "jetbot_core_ignition_v1.7.0.sdf",
        "env_ready_timeout_s": replay_batch.DEFAULT_ENV_READY_TIMEOUT_S,
        "env_stop_timeout_s": 90.0,
        "fetch_delivery_radius_m": 0.3,
        "python_exe": sys.executable,
        "timeout_s": 180.0,
        "package_timeout_s": 180.0,
        "no_visual_package": False,
        "resume_skip_existing": False,
        "stop_on_fail": False,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _patch_roots(tmp_path, monkeypatch):
    session_root = tmp_path / "artifacts" / "session"
    monkeypatch.setattr(seeded_gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(seeded_gate, "SESSION_ROOT", session_root)
    monkeypatch.setattr(planner_gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(replay_batch, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(replay_batch, "SESSION_ROOT", session_root)
    monkeypatch.setattr(route_analyzer, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(route_analyzer, "SESSION_ROOT", session_root)


def test_planner_seeded_generalization_gate_dry_run_composes_child_surfaces(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)

    summary = seeded_gate.run_gate(_args())

    assert summary["pass"] is True
    assert summary["dry_run"] is True
    assert summary["promotion_evidence"] is False
    assert summary["milestone_interpretation"] == "planner_routed_seeded_generalization_dry_run_ready"
    assert summary["planner_gate_pass"] is True
    assert summary["replay_pass"] is True
    assert summary["replay_summary"]["selected_count"] == 6
    assert summary["expected_executable_count"] == 6
    assert (tmp_path / summary["planner_summary_path"]).is_file()
    assert (tmp_path / summary["replay_summary_path"]).is_file()
    assert (tmp_path / summary["summary_path"]).is_file()


def test_planner_seeded_generalization_promotion_requires_full_clean_live_surface():
    args = _args(dry_run=False, fresh_dashboard_session_per_run=True)
    replay_summary = {
        "pass": True,
        "selected_count": 6,
        "mission_pass_count": 6,
        "visual_package_pass_count": 6,
    }
    analyzer_summary = {
        "pass": True,
        "execution_quality_status": "clean",
        "setup_quality_status": "clean",
        "contact_quality_status": "clean",
        "first_contact_blocker_count": 0,
    }

    assert seeded_gate.promotion_ready(
        args=args,
        planner_summary={"pass": True},
        replay_summary=replay_summary,
        analyzer_summary=analyzer_summary,
    )

    analyzer_summary["setup_quality_status"] = "watch"
    assert not seeded_gate.promotion_ready(
        args=args,
        planner_summary={"pass": True},
        replay_summary=replay_summary,
        analyzer_summary=analyzer_summary,
    )


def test_planner_seeded_generalization_supervised_promotion_requires_provider_authority():
    args = _args(
        dry_run=False,
        fresh_dashboard_session_per_run=True,
        planner_mode=planner_gate.PLANNER_MODE_LLM_SUPERVISED_GUARDED,
    )
    replay_summary = {
        "pass": True,
        "selected_count": 6,
        "mission_pass_count": 6,
        "visual_package_pass_count": 6,
    }
    analyzer_summary = {
        "pass": True,
        "execution_quality_status": "clean",
        "setup_quality_status": "clean",
        "contact_quality_status": "clean",
        "first_contact_blocker_count": 0,
    }
    missing_provider_summary = {
        "pass": True,
        "provider_status_counts": {"skipped_missing_openai_api_key": 30},
        "llm_supervised_ready": False,
    }
    provider_backed_summary = {
        "pass": True,
        "random_cases": 30,
        "pass_count": 30,
        "fail_count": 0,
        "provider_status_counts": {"ok": 30},
        "guard_agreement_count": 30,
        "wrong_fetch_dispatch_count": 0,
        "llm_supervised_ready": True,
    }

    assert not seeded_gate.planner_authority_ready(args, missing_provider_summary)
    assert not seeded_gate.promotion_ready(
        args=args,
        planner_summary=missing_provider_summary,
        replay_summary=replay_summary,
        analyzer_summary=analyzer_summary,
    )

    assert seeded_gate.planner_authority_ready(args, provider_backed_summary)
    assert seeded_gate.promotion_ready(
        args=args,
        planner_summary=provider_backed_summary,
        replay_summary=replay_summary,
        analyzer_summary=analyzer_summary,
    )


def test_planner_seeded_generalization_accepts_confidence_only_guarded_fallback_authority():
    args = _args(
        dry_run=False,
        fresh_dashboard_session_per_run=True,
        planner_mode=planner_gate.PLANNER_MODE_LLM_SUPERVISED_GUARDED,
    )
    planner_summary = {
        "pass": True,
        "random_cases": 3,
        "pass_count": 3,
        "fail_count": 0,
        "provider_status_counts": {"ok": 3},
        "guard_agreement_count": 3,
        "wrong_fetch_dispatch_count": 0,
        "llm_supervised_ready": False,
        "llm_supervised_accept_count": 2,
        "llm_supervised_veto_count": 1,
        "results": [
            {
                "llm_supervised_guard": {
                    "decision": "vetoed",
                    "veto_reasons": ["confidence_below_threshold"],
                }
            }
        ],
    }

    assert seeded_gate.strict_planner_authority_ready(args, planner_summary) is False
    assert seeded_gate.guarded_fallback_authority_ready(args, planner_summary) is True
    assert seeded_gate.planner_authority_ready(args, planner_summary) is True
    assert seeded_gate.supervised_veto_reason_counts(planner_summary) == {"confidence_below_threshold": 1}


def test_planner_seeded_generalization_blocks_non_confidence_guarded_fallback_authority():
    args = _args(
        dry_run=False,
        fresh_dashboard_session_per_run=True,
        planner_mode=planner_gate.PLANNER_MODE_LLM_SUPERVISED_GUARDED,
    )
    planner_summary = {
        "pass": True,
        "random_cases": 3,
        "pass_count": 3,
        "fail_count": 0,
        "provider_status_counts": {"ok": 3},
        "guard_agreement_count": 3,
        "wrong_fetch_dispatch_count": 0,
        "llm_supervised_ready": False,
        "llm_supervised_accept_count": 2,
        "llm_supervised_veto_count": 1,
        "results": [
            {
                "llm_supervised_guard": {
                    "decision": "vetoed",
                    "veto_reasons": ["guard_disagreement"],
                }
            }
        ],
    }

    assert seeded_gate.guarded_fallback_authority_ready(args, planner_summary) is False
    assert seeded_gate.planner_authority_ready(args, planner_summary) is False


def test_planner_seeded_generalization_extracts_first_replay_failure():
    failure = seeded_gate.first_replay_failure(
        {
            "rows": [
                {
                    "scene_id": "scene04",
                    "route_label": planner_gate.ROUTE_RECOVERY_OR_REAIM,
                    "returncode": -1,
                    "failure_reason": "fresh_dashboard_session_start_failed",
                    "expected_session_id": "session_a",
                }
            ]
        }
    )

    assert failure == {
        "scene_id": "scene04",
        "route_label": planner_gate.ROUTE_RECOVERY_OR_REAIM,
        "returncode": -1,
        "failure_reason": "fresh_dashboard_session_start_failed",
        "expected_session_id": "session_a",
    }


def test_seeded_gate_passes_operator_view_degraded_option_to_replay(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    args = _args(allow_operator_view_degraded=True)
    replay_args = seeded_gate.build_replay_args(
        args,
        campaign_id="seeded_gate_replay",
        gate_summary=tmp_path / "gate_summary.json",
    )

    assert replay_args.allow_operator_view_degraded is True


def test_seeded_gate_can_reuse_child_summaries_for_parent_promotion(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    planner_path = tmp_path / "artifacts" / "session" / "planner" / planner_gate.PLANNER_GATE_KIND / "gate_summary.json"
    replay_path = tmp_path / "artifacts" / "session" / "replay" / replay_batch.BATCH_KIND / "batch_summary.json"
    seeded_gate.write_json(
        planner_path,
        {
            "campaign_id": "planner",
            "pass": True,
            "pass_count": 30,
            "fail_count": 0,
            "wrong_fetch_dispatch_count": 0,
            "route_counts": {
                planner_gate.ROUTE_FETCH_READY: 2,
                planner_gate.ROUTE_NAV2_REPOSITION: 2,
                planner_gate.ROUTE_RECOVERY_OR_REAIM: 2,
            },
        },
    )
    seeded_gate.write_json(
        replay_path,
        {
            "campaign_id": "replay",
            "pass": True,
            "selected_count": 6,
            "mission_pass_count": 6,
            "mission_fail_count": 0,
            "visual_package_pass_count": 6,
            "rows": [],
        },
    )

    def fail_planner(*_args, **_kwargs):
        raise AssertionError("planner should be reused")

    def fail_replay(*_args, **_kwargs):
        raise AssertionError("replay should be reused")

    def clean_analyzer(*_args, **_kwargs):
        return {
            "pass": True,
            "milestone_interpretation": "randomized_route_owner_visual_uat_green",
            "execution_quality_status": "clean",
            "setup_quality_status": "clean",
            "contact_quality_status": "clean",
            "first_contact_blocker_count": 0,
        }

    monkeypatch.setattr(planner_gate, "run_gate", fail_planner)
    monkeypatch.setattr(replay_batch, "run_batch", fail_replay)
    monkeypatch.setattr(seeded_gate, "run_analyzer", clean_analyzer)

    summary = seeded_gate.run_gate(
        _args(
            dry_run=False,
            reuse_planner_summary=str(planner_path),
            reuse_replay_summary=str(replay_path),
        )
    )

    assert summary["pass"] is True
    assert summary["promotion_evidence"] is True
    assert summary["planner_authority_ready"] is True
    assert summary["milestone_interpretation"] == "planner_routed_seeded_generalization_promotion_green"
    assert summary["planner_summary_path"].endswith("/planner/fetch_planner_handoff_gate/gate_summary.json")
    assert summary["replay_summary_path"].endswith("/replay/fetch_planner_route_replay_batch/batch_summary.json")
