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
        "env_ready_timeout_s": 540.0,
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
