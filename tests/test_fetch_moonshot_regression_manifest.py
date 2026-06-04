from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_moonshot_regression_manifest as manifest  # noqa: E402


def _args(tmp_path: Path, **overrides):
    payload = {
        "campaign_id": "regression",
        "regression_set_id": "test_regression_set",
        "saved_anchor_summary": str(
            tmp_path
            / "artifacts"
            / "session"
            / "saved"
            / "fetch_planner_route_uat_analyzer"
            / "route_uat_summary.json"
        ),
        "setup_contact_audit": str(
            tmp_path
            / "artifacts"
            / "session"
            / "audit"
            / "fetch_saved_anchor_setup_contact_audit"
            / "audit_summary.json"
        ),
        "seeded_gate": [
            "seedtest="
            + str(
                tmp_path
                / "artifacts"
                / "session"
                / "seed"
                / "fetch_planner_seeded_generalization_gate"
                / "gate_summary.json"
            )
        ],
        "boundary_replay_summary": str(
            tmp_path
            / "artifacts"
            / "session"
            / "seed_replay"
            / "fetch_planner_route_replay_batch"
            / "batch_summary.json"
        ),
        "boundary_row": ["seed_scene_nav2=nav2_reposition_first:test_boundary"],
        "fetch_delivery_radius_m": 0.3,
        "min_random_cases": 30,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _patch_roots(tmp_path, monkeypatch):
    session_root = tmp_path / "artifacts" / "session"
    monkeypatch.setattr(manifest, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(manifest, "SESSION_ROOT", session_root)
    return session_root


def _write(path: Path, payload: dict) -> Path:
    manifest.write_json(path, payload)
    return path


def _green_saved_anchor(session_root: Path) -> Path:
    path = session_root / "saved" / "fetch_planner_route_uat_analyzer" / "route_uat_summary.json"
    return _write(
        path,
        {
            "type": "fetch_planner_route_uat_analyzer",
            "pass": True,
            "evidence_scope": "saved_anchor_repeatability",
            "saved_anchor_repeatability_green": True,
            "saved_anchor_scene_counts": {
                "saved_anchor_zero": 3,
                "saved_anchor_left05": 3,
                "saved_anchor_right05": 3,
            },
            "mission_green": True,
            "visual_package_green": True,
            "execution_quality_status": "clean",
            "setup_quality_status": "clean",
            "contact_quality_status": "clean",
            "first_contact_blocker_count": 0,
            "milestone_interpretation": "saved_anchor_repeatability_green",
            "missions": [
                {"closest_approach_distance_m": 0.196},
                {"closest_approach_distance_m": 0.194},
            ],
            "visual_packages": [{"pass": True}],
        },
    )


def _green_audit(session_root: Path) -> Path:
    path = session_root / "audit" / "fetch_saved_anchor_setup_contact_audit" / "audit_summary.json"
    return _write(
        path,
        {
            "stage_quality_green": True,
            "pass_count": 3,
            "setup_contact_blocker_count": 0,
            "setup_capture_blocker_count": 0,
            "push_coast_blocker_count": 0,
            "first_contact_blocker_count": 0,
            "invalid_geometry_count": 0,
            "invalid_model_provenance_count": 0,
            "overall_interpretation": "stage_quality_green",
        },
    )


def _green_seeded_gate(session_root: Path) -> tuple[Path, Path]:
    planner = session_root / "seed_planner" / "fetch_planner_handoff_gate" / "gate_summary.json"
    replay = session_root / "seed_replay" / "fetch_planner_route_replay_batch" / "batch_summary.json"
    analyzer = session_root / "seed_analysis" / "fetch_planner_route_uat_analyzer" / "route_uat_summary.json"
    mission = session_root / "mission" / "mission_verdict.json"
    package = session_root / "package" / "fetch_visual_uat_package" / "package_summary.json"
    _write(mission, {"pass": True})
    _write(package, {"pass": True})
    visual = {
        "pass": True,
        "mobile_watchable": True,
        "onboard_camera_watchable": True,
        "videos": [
            {
                "role": "onboard_camera",
                "browser_playable": True,
                "url": "/artifacts/session/session/visual/raw_camera_browser.mp4",
            },
            {
                "role": "external_context",
                "browser_playable": True,
                "url": "/artifacts/session/session/visual/topdown_telemetry_browser.mp4",
            },
        ],
        "keyframe_reviews": [
            {
                "ok": True,
                "url": "/artifacts/session/session/visual/keyframe_review_contact_sheet.png",
            }
        ],
    }
    rows = []
    route_labels = [
        "nav2_reposition_first",
        "nav2_reposition_first",
        "fetch_ready_local",
        "fetch_ready_local",
        "recovery_or_reaim",
        "recovery_or_reaim",
    ]
    for index, route_label in enumerate(route_labels):
        rows.append(
            {
                "scene_id": "seed_scene_nav2" if index == 0 else f"seed_scene_{index:02d}",
                "route_label": route_label,
                "returncode": 0,
                "failure_reason": "",
                "mission": {"pass": True, "closest_approach_distance_m": 0.195},
                "visual_package": visual,
                "mission_summary_path": manifest.artifact_display_path(mission),
                "visual_package_summary_path": manifest.artifact_display_path(package),
            }
        )
    _write(
        planner,
        {
            "pass": True,
            "pass_count": 30,
            "random_cases": 30,
            "wrong_fetch_dispatch_count": 0,
        },
    )
    _write(
        replay,
        {
            "pass": True,
            "selected_count": 6,
            "mission_pass_count": 6,
            "mission_fail_count": 0,
            "visual_package_pass_count": 6,
            "rows": rows,
        },
    )
    _write(
        analyzer,
        {
            "pass": True,
            "execution_quality_status": "clean",
            "setup_quality_status": "clean",
            "contact_quality_status": "clean",
            "first_contact_blocker_count": 0,
        },
    )
    parent = session_root / "seed" / "fetch_planner_seeded_generalization_gate" / "gate_summary.json"
    _write(
        parent,
        {
            "type": "fetch_planner_seeded_generalization_gate",
            "pass": True,
            "promotion_evidence": True,
            "dry_run": False,
            "fresh_dashboard_session_per_run": True,
            "planner_gate_pass": True,
            "replay_pass": True,
            "analyzer_pass": True,
            "seed": 1,
            "random_cases": 30,
            "expected_executable_count": 6,
            "planner_summary_path": manifest.artifact_display_path(planner),
            "replay_summary_path": manifest.artifact_display_path(replay),
            "analyzer_summary_path": manifest.artifact_display_path(analyzer),
            "planner_summary": {
                "pass_count": 30,
                "wrong_fetch_dispatch_count": 0,
                "route_counts": {"fetch_ready_local": 10},
            },
            "replay_summary": {
                "selected_count": 6,
                "mission_pass_count": 6,
                "mission_fail_count": 0,
                "visual_package_pass_count": 6,
            },
            "analyzer_summary": {
                "execution_quality_status": "clean",
                "setup_quality_status": "clean",
                "contact_quality_status": "clean",
                "first_contact_blocker_count": 0,
            },
            "milestone_interpretation": "planner_routed_seeded_generalization_promotion_green",
        },
    )
    return parent, replay


def test_moonshot_regression_manifest_scores_green_evidence(tmp_path, monkeypatch):
    session_root = _patch_roots(tmp_path, monkeypatch)
    _green_saved_anchor(session_root)
    _green_audit(session_root)
    _green_seeded_gate(session_root)

    summary = manifest.build_summary(_args(tmp_path))

    assert summary["pass"] is True
    assert summary["milestone_interpretation"] == "planner_routed_moonshot_regression_set_green"
    assert summary["saved_anchor_repeatability"]["pass"] is True
    assert summary["setup_contact_audit"]["pass"] is True
    assert summary["seeded_gates"][0]["pass"] is True
    assert summary["boundary_rows"][0]["pass"] is True
    assert summary["boundary_rows"][0]["onboard_video_url"].endswith("raw_camera_browser.mp4")
    assert summary["totals"]["seeded_live_mission_pass_count"] == 6

    scorecard = tmp_path / "scorecard.md"
    manifest.write_scorecard(scorecard, summary)
    text = scorecard.read_text(encoding="utf-8")
    assert "Fetch Moonshot Regression Manifest" in text
    assert "seed_scene_nav2" in text


def test_default_seeded_gates_include_rough_breadth_seeds():
    labels = [label for label, _path in manifest.DEFAULT_SEEDED_GATES]

    assert labels == [
        "seed20260627",
        "seed20260628",
        "seed20260629",
        "seed20260630",
        "seed20260631",
        "seed20260632",
        "seed20260633",
    ]


def test_moonshot_regression_manifest_fails_closed_on_boundary_visual_gap(tmp_path, monkeypatch):
    session_root = _patch_roots(tmp_path, monkeypatch)
    _green_saved_anchor(session_root)
    _green_audit(session_root)
    _green_seeded_gate(session_root)
    replay = (
        session_root
        / "seed_replay"
        / "fetch_planner_route_replay_batch"
        / "batch_summary.json"
    )
    payload, issues = manifest.read_json(replay)
    assert issues == []
    payload["rows"][0]["mission"]["closest_approach_distance_m"] = 0.451
    payload["rows"][0]["visual_package"]["onboard_camera_watchable"] = False
    manifest.write_json(replay, payload)

    summary = manifest.build_summary(_args(tmp_path))

    assert summary["pass"] is False
    boundary = summary["boundary_rows"][0]
    assert boundary["pass"] is False
    assert "boundary_row_outside_delivery_radius" in boundary["issues"]
    assert "boundary_row_onboard_not_watchable" in boundary["issues"]
