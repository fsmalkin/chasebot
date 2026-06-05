from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_generalized_milestone_readiness as readiness  # noqa: E402


def _args(tmp_path: Path, **overrides):
    payload = {
        "campaign_id": "milestone_ready",
        "provider_readiness_summary": str(tmp_path / "provider_readiness.json"),
        "provider_comparison_summary": str(tmp_path / "provider_comparison.json"),
        "dashboard_visual_evidence_summary": str(tmp_path / "dashboard_audit.json"),
        "hardware_transfer_readiness_summary": str(tmp_path / "hardware_readiness.json"),
        "geometry_breadth_summary": str(tmp_path / "geometry_breadth.json"),
        "uat_watchlist_summary": str(tmp_path / "uat_watchlist.json"),
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(readiness.json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _green_provider_readiness(path: Path) -> Path:
    return _write_json(
        path,
        {
            "provider_rerun_ready": False,
            "provider_backed_authority_proven": False,
            "blockers": ["missing_openai_api_key"],
            "breadth_rollup": {
                "pass": True,
                "total_random_cases": 300,
                "total_selected_count": 27,
                "total_wrong_fetch_dispatch_count": 0,
                "total_contact_watch_count": 0,
                "total_first_contact_blocker_count": 0,
            },
        },
    )


def _green_provider_comparison(path: Path) -> Path:
    return _write_json(
        path,
        {
            "guarded_provider_rerun_ready": False,
            "strict_provider_authority_ready": False,
            "blockers": [
                "provider_planner:provider_not_ok_for_all_cases",
                "provider_planner:non_confidence_veto:missing_llm_route",
            ],
            "provider_replay": {"pass": True, "mission_pass_count": 9},
            "provider_route_uat": {
                "pass": True,
                "milestone_interpretation": "randomized_route_owner_visual_uat_green",
            },
        },
    )


def _green_dashboard_audit(path: Path) -> Path:
    return _write_json(
        path,
        {
            "pass": True,
            "uat_sample_count": 15,
            "uat_sample_pass_count": 15,
            "evidence_card_count": 8,
            "evidence_card_pass_count": 8,
            "route_counts": {
                "fetch_ready_local": 3,
                "nav2_reposition_first": 3,
                "recovery_or_reaim": 3,
                "scan_or_perceive_first": 3,
                "ambiguous_or_unsafe_no_go": 3,
            },
        },
    )


def _green_geometry_breadth(path: Path) -> Path:
    return _write_json(
        path,
        {
            "pass": True,
            "scene_count": 300,
            "seeds": [20260648, 20260649, 20260650],
            "route_counts": {
                "fetch_ready_local": 70,
                "nav2_reposition_first": 57,
                "recovery_or_reaim": 52,
                "scan_or_perceive_first": 65,
                "ambiguous_or_unsafe_no_go": 56,
            },
            "flag_counts": {
                "bounded_recovery_required": 52,
                "corridor_unusable": 56,
                "initial_lateral_setup_debt": 62,
                "initial_yaw_setup_debt": 77,
                "nav2_reposition_required": 57,
                "perception_refresh_required": 65,
                "target_distance_outside_local_fetch_window": 56,
            },
            "ranges": {
                "ball_target_angle_abs_deg": {"span": 41.779826},
                "ball_target_distance_m": {"span": 1.396765},
                "lateral_m": {"span": 0.209051},
                "robot_ball_distance_m": {"span": 1.016048},
                "yaw_deg": {"span": 30.595971},
            },
            "minimum_spans": {
                "ball_target_angle_abs_deg": 30.0,
                "ball_target_distance_m": 1.0,
                "lateral_m": 0.15,
                "robot_ball_distance_m": 0.8,
                "yaw_deg": 20.0,
            },
        },
    )


def _green_uat_watchlist(path: Path) -> Path:
    return _write_json(
        path,
        {
            "pass": True,
            "sample_count": 15,
            "milestone_interpretation": "dashboard_uat_watchlist_ready",
            "route_counts": {
                "fetch_ready_local": 3,
                "nav2_reposition_first": 3,
                "recovery_or_reaim": 3,
                "scan_or_perceive_first": 3,
                "ambiguous_or_unsafe_no_go": 3,
            },
            "review_guidance": [
                "watch onboard raw_camera_browser first",
                "cross-check keyframe sheet across start/setup and final rest",
            ],
        },
    )


def _green_hardware_readiness(path: Path) -> Path:
    return _write_json(
        path,
        {
            "pass": True,
            "hardware_transfer_ready": True,
            "hardware_proven": False,
            "readiness_level": "ready_for_hardware_rehearsal",
            "open_hardware_gates": [
                "robot_side_live_rehearsal_not_run",
                "onboard_tensorrt_execution_not_proven",
                "physical_camera_visual_package_not_recorded",
                "field_physics_not_proven",
            ],
        },
    )


def _green_fixture(tmp_path: Path) -> SimpleNamespace:
    args = _args(tmp_path)
    _green_provider_readiness(Path(args.provider_readiness_summary))
    _green_provider_comparison(Path(args.provider_comparison_summary))
    _green_dashboard_audit(Path(args.dashboard_visual_evidence_summary))
    _green_hardware_readiness(Path(args.hardware_transfer_readiness_summary))
    _green_geometry_breadth(Path(args.geometry_breadth_summary))
    _green_uat_watchlist(Path(args.uat_watchlist_summary))
    return args


def test_milestone_readiness_is_operator_uat_ready_without_overclaiming(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(readiness, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(readiness, "SESSION_ROOT", tmp_path / "artifacts" / "session")

    summary = readiness.build_summary(_green_fixture(tmp_path))

    assert summary["pass"] is True
    assert summary["operator_uat_ready"] is True
    assert summary["milestone_complete"] is False
    assert summary["provider_backed_authority_proven"] is False
    assert summary["hardware_proven"] is False
    assert summary["readiness_level"] == "operator_uat_ready_provider_and_physical_pending"
    assert "provider_backed_llm_routing_not_proven" in summary["open_gates"]
    assert "robot_side_live_rehearsal_not_run" in summary["open_gates"]


def test_milestone_readiness_fails_when_dashboard_visual_audit_is_incomplete(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(readiness, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(readiness, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    args = _green_fixture(tmp_path)
    _write_json(
        Path(args.dashboard_visual_evidence_summary),
        {"pass": False, "uat_sample_count": 15, "uat_sample_pass_count": 14, "evidence_card_pass_count": 3},
    )

    summary = readiness.build_summary(args)

    assert summary["pass"] is False
    assert summary["operator_uat_ready"] is False
    assert "dashboard_visual_evidence:dashboard_visual_audit_not_green" in summary["issues"]


def test_milestone_readiness_fails_when_geometry_breadth_is_too_narrow(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(readiness, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(readiness, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    args = _green_fixture(tmp_path)
    geometry_path = Path(args.geometry_breadth_summary)
    payload = readiness.json.loads(geometry_path.read_text(encoding="utf-8"))
    payload["ranges"]["yaw_deg"]["span"] = 4.0
    _write_json(geometry_path, payload)

    summary = readiness.build_summary(args)

    assert summary["pass"] is False
    assert any(
        issue.startswith("planner_geometry_breadth:geometry_span_failures:yaw_deg")
        for issue in summary["issues"]
    )


def test_milestone_readiness_fails_when_uat_watchlist_drops_route_family(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(readiness, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(readiness, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    args = _green_fixture(tmp_path)
    watchlist_path = Path(args.uat_watchlist_summary)
    payload = readiness.json.loads(watchlist_path.read_text(encoding="utf-8"))
    payload["route_counts"]["recovery_or_reaim"] = 2
    _write_json(watchlist_path, payload)

    summary = readiness.build_summary(args)

    assert summary["pass"] is False
    assert (
        "operator_uat_watchlist:uat_watchlist_route_counts_below_3:recovery_or_reaim"
        in summary["issues"]
    )


def test_milestone_readiness_flags_unexpected_provider_blocker(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(readiness, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(readiness, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    args = _green_fixture(tmp_path)
    provider_path = Path(args.provider_readiness_summary)
    payload = readiness.json.loads(provider_path.read_text(encoding="utf-8"))
    payload["blockers"] = ["missing_openai_api_key", "dashboard_plan:dashboard_uat_samples_below_15"]
    _write_json(provider_path, payload)

    summary = readiness.build_summary(args)

    assert summary["pass"] is False
    assert "provider_readiness:provider_readiness_has_unexpected_blockers" in summary["issues"]


def test_milestone_readiness_scorecard_names_green_evidence_and_open_gates(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(readiness, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(readiness, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    summary = readiness.build_summary(_green_fixture(tmp_path))
    scorecard = tmp_path / "scorecard.md"

    readiness.write_scorecard(scorecard, summary)

    text = scorecard.read_text(encoding="utf-8")
    assert "Generalized Fetch-To-Pose Milestone Readiness" in text
    assert "three_seed_deterministic_breadth_rollup_green" in text
    assert "planner_geometry_breadth_green" in text
    assert "operator_uat_watchlist_ready" in text
    assert "provider_backed_llm_routing_not_proven" in text
    assert "hardware_proven: `False`" in text
