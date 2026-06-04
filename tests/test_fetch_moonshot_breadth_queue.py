from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_moonshot_breadth_queue as queue  # noqa: E402
import fetch_moonshot_regression_manifest as manifest  # noqa: E402
import fetch_planner_seeded_generalization_gate as seeded_gate  # noqa: E402


def _args(tmp_path: Path, **overrides):
    payload = {
        "campaign_id": "breadth",
        "seed": [101, 102],
        "random_cases": 30,
        "max_per_route": 2,
        "quality_order": "roughest",
        "dashboard_url": "http://127.0.0.1:8879",
        "compose_project": "",
        "allow_operator_view_degraded": True,
        "fresh_dashboard_session_per_run": True,
        "scene_set": "mixed_fetch_planner_v1",
        "scene_descriptor_json": [],
        "scene_dir": "",
        "planner_mode": "deterministic",
        "openai_model": "gpt-test",
        "openai_api_key": "",
        "openai_base_url": "https://api.openai.com/v1",
        "openai_org_id": "",
        "openai_project_id": "",
        "reasoning_effort": "low",
        "planner_timeout_s": 45.0,
        "route": [],
        "scene_id": [],
        "skip_scene_id": [],
        "world_file": "world.sdf",
        "surface_profile": "calibrated_golf_turf",
        "robot_sdf_name": "robot.sdf",
        "env_ready_timeout_s": 540.0,
        "env_stop_timeout_s": 90.0,
        "fetch_delivery_radius_m": 0.3,
        "python_exe": sys.executable,
        "timeout_s": 180.0,
        "package_timeout_s": 180.0,
        "no_visual_package": False,
        "regression_set_id": "test_regression_set",
        "saved_anchor_summary": "saved.json",
        "setup_contact_audit": "audit.json",
        "regression_seeded_gate": [],
        "boundary_replay_summary": "replay.json",
        "boundary_row": [],
        "min_random_cases": 30,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _patch_roots(tmp_path, monkeypatch):
    session_root = tmp_path / "artifacts" / "session"
    monkeypatch.setattr(queue, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(queue, "SESSION_ROOT", session_root)
    monkeypatch.setattr(manifest, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(manifest, "SESSION_ROOT", session_root)
    monkeypatch.setattr(seeded_gate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(seeded_gate, "SESSION_ROOT", session_root)
    return session_root


def _rows(*, high_risk: int) -> list[dict]:
    routes = [
        "fetch_ready_local",
        "fetch_ready_local",
        "nav2_reposition_first",
        "nav2_reposition_first",
        "recovery_or_reaim",
        "recovery_or_reaim",
    ]
    rows: list[dict] = []
    for index, route in enumerate(routes):
        risk = "high" if index < high_risk else "medium"
        rows.append(
            {
                "scene_id": f"scene{index:02d}",
                "route_label": route,
                "route_quality": {
                    "quality_score": 40.0 + index,
                    "predicted_contact_quality": "watch",
                    "predicted_first_contact_risk": risk,
                    "flags": ["synthetic"],
                    "setup_debt": {"yaw_deg": 10 + index},
                },
            }
        )
    return rows


def _seed_summary(seed: int) -> dict:
    return {
        "pass": True,
        "dry_run": True,
        "seed": seed,
        "campaign_id": f"seed{seed}",
        "random_cases": 30,
        "expected_executable_count": 6,
        "planner_summary": {
            "pass_count": 30,
            "wrong_fetch_dispatch_count": 0,
            "route_counts": {
                "fetch_ready_local": 6,
                "nav2_reposition_first": 6,
                "recovery_or_reaim": 6,
                "scan_or_perceive_first": 6,
                "ambiguous_or_unsafe_no_go": 6,
            },
        },
        "replay_summary": {
            "selected_count": 6,
            "mission_pass_count": 0,
            "visual_package_pass_count": 0,
        },
        "summary_path": f"artifacts/session/seed{seed}/summary.json",
        "scorecard_path": f"artifacts/session/seed{seed}/scorecard.md",
    }


def test_breadth_queue_scores_harder_ready_seed_higher():
    easier = queue.evaluate_seed_candidate(
        _seed_summary(101),
        {"rows": _rows(high_risk=1)},
        max_per_route=2,
        random_cases=30,
    )
    harder = queue.evaluate_seed_candidate(
        _seed_summary(102),
        {"rows": _rows(high_risk=4)},
        max_per_route=2,
        random_cases=30,
    )

    assert easier["pass"] is True
    assert harder["pass"] is True
    assert harder["breadth_score"] > easier["breadth_score"]
    assert harder["selected_route_counts"] == {
        "fetch_ready_local": 2,
        "nav2_reposition_first": 2,
        "recovery_or_reaim": 2,
    }


def test_breadth_queue_build_summary_runs_regression_preflight_and_dry_seeds(tmp_path, monkeypatch):
    session_root = _patch_roots(tmp_path, monkeypatch)

    def fake_preflight(args):
        return {
            "pass": True,
            "summary_path": "artifacts/session/preflight/regression_summary.json",
            "scorecard_path": "artifacts/session/preflight/scorecard.md",
        }

    def fake_seed_gate(args, *, seed: int):
        replay_path = (
            session_root
            / f"seed{seed}_replay"
            / "fetch_planner_route_replay_batch"
            / "batch_summary.json"
        )
        queue.write_json(replay_path, {"rows": _rows(high_risk=4 if seed == 102 else 1)})
        summary = _seed_summary(seed)
        summary["replay_summary_path"] = queue.artifact_display_path(replay_path)
        return summary

    monkeypatch.setattr(queue, "run_regression_preflight", fake_preflight)
    monkeypatch.setattr(queue, "run_seed_dry_gate", fake_seed_gate)

    summary = queue.build_summary(_args(tmp_path))

    assert summary["pass"] is True
    assert summary["regression_preflight_pass"] is True
    assert summary["ready_candidate_count"] == 2
    assert summary["recommended_seed"] == 102
    assert "--allow-operator-view-degraded" in summary["recommended_live_command"]
    assert "--seed 102" in summary["recommended_live_command"]

    scorecard = tmp_path / "scorecard.md"
    queue.write_scorecard(scorecard, summary)
    text = scorecard.read_text(encoding="utf-8")
    assert "Fetch Moonshot Breadth Queue" in text
    assert "Recommended Live Command" in text
