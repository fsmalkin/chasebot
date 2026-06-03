import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_planner_route_uat_analyzer as analyzer  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    analyzer.write_json(path, payload)


def _args(tmp_path: Path, *, planner: Path, missions: list[Path], visual_package: Path):
    return type(
        "Args",
        (),
        {
            "campaign_id": "uat",
            "planner_summary": [str(planner)],
            "mission_summary": [str(path) for path in missions],
            "visual_package_summary": [str(visual_package)],
        },
    )()


def _mission(
    path: Path,
    route: str,
    *,
    closest: float = 0.19,
    flags: list[str] | None = None,
    first_flags: list[str] | None = None,
    route_quality: dict | None = None,
) -> None:
    _write_json(
        path,
        {
            "session_id": path.parent.name,
            "planner_route_label": route,
            "route_executor": f"{route}_executor",
            "fetch_to_pose_pass": True,
            "mission_completed_pass": True,
            "shot_outcome": {
                "closest_approach_distance_m": closest,
                "reason": "trajectory_intersects_delivery_radius",
            },
            "approach_contact_metrics": {
                "flags": flags or [],
                "first_contact_quality_flags": first_flags or [],
                "first_contact_quality_pass": not bool(first_flags),
                "first_contact_t_s": 4.2,
            },
            "random_draw": {"route_quality": route_quality or {}},
            "planner_route": {"route_quality": route_quality or {}},
            "model_provenance": {"model_provenance_valid": True},
        },
    )


def test_planner_route_uat_analyzer_scores_green_randomized_route_uat(tmp_path, monkeypatch):
    monkeypatch.setattr(analyzer, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    monkeypatch.setattr(analyzer, "REPO_ROOT", tmp_path)
    root = analyzer.SESSION_ROOT
    planner = root / "planner" / "fetch_planner_handoff_gate" / "gate_summary.json"
    _write_json(
        planner,
        {
            "campaign_id": "planner",
            "pass": True,
            "pass_count": 15,
            "fail_count": 0,
            "random_cases": 15,
            "wrong_fetch_dispatch_count": 0,
            "fetch_dispatch_count": 2,
            "scene_source": "generated",
            "seed": 20260607,
            "route_counts": {
                analyzer.ROUTE_FETCH_READY: 2,
                analyzer.ROUTE_NAV2_REPOSITION: 6,
                analyzer.ROUTE_RECOVERY_OR_REAIM: 4,
                analyzer.ROUTE_SCAN_OR_PERCEIVE: 2,
                analyzer.ROUTE_NO_GO: 1,
            },
        },
    )
    missions = [
        root / "fetch_session" / "mission_verdict.json",
        root / "nav2_session" / "mission_verdict.json",
        root / "recovery_session" / "mission_verdict.json",
    ]
    _mission(missions[0], analyzer.ROUTE_FETCH_READY, flags=["pre_contact_lateral_error"])
    _mission(missions[1], analyzer.ROUTE_NAV2_REPOSITION, closest=0.196)
    _mission(missions[2], analyzer.ROUTE_RECOVERY_OR_REAIM, closest=0.247)
    visual_package = root / "uat" / "fetch_visual_uat_package" / "package_summary.json"
    _write_json(
        visual_package,
        {
            "campaign_id": "uat",
            "type": "fetch_visual_uat_package",
            "pass": True,
            "mobile_watchable": True,
            "onboard_camera_watchable": True,
            "visual_confirmation_seen": True,
            "local_fetch_visual_confirmed": True,
            "milestone_interpretation": "mobile_visual_uat_ready_not_promotion",
            "promotion_evidence": False,
            "warnings": ["visual_confirmation_keyframe_recovery"],
            "video_recovery": [{"attempted": True, "ok": True}],
            "videos": [{"name": "raw_camera_browser.mp4"}],
            "scorecard_path": "artifacts/session/uat/fetch_visual_uat_package/scorecard.md",
        },
    )

    summary = analyzer.build_summary(_args(tmp_path, planner=planner, missions=missions, visual_package=visual_package))

    assert summary["pass"] is True
    assert summary["promotion_evidence"] is False
    assert summary["milestone_interpretation"] == "randomized_route_owner_visual_uat_green"
    assert summary["execution_quality_status"] == "watch"
    assert summary["setup_quality_status"] == "watch"
    assert summary["contact_quality_status"] == "clean"
    assert summary["setup_watch_count"] == 1
    assert summary["contact_watch_count"] == 0
    rows = {row["route_label"]: row for row in summary["route_rows"]}
    assert rows[analyzer.ROUTE_FETCH_READY]["coverage_status"] == "live_executable_passed"
    assert rows[analyzer.ROUTE_FETCH_READY]["live_setup_watch_count"] == 1
    assert rows[analyzer.ROUTE_FETCH_READY]["live_watch_count"] == 0
    assert rows[analyzer.ROUTE_FETCH_READY]["live_execution_watch_count"] == 1
    assert rows[analyzer.ROUTE_NAV2_REPOSITION]["coverage_status"] == "live_executable_passed"
    assert rows[analyzer.ROUTE_RECOVERY_OR_REAIM]["coverage_status"] == "live_executable_passed"
    assert rows[analyzer.ROUTE_SCAN_OR_PERCEIVE]["coverage_status"] == "planner_only_classified"
    assert rows[analyzer.ROUTE_NO_GO]["coverage_status"] == "planner_only_classified"

    scorecard = tmp_path / "scorecard.md"
    analyzer.write_scorecard(scorecard, summary)
    text = scorecard.read_text(encoding="utf-8")
    assert "route=`nav2_reposition_first`" in text
    assert "Setup watches" in text
    assert "setup_watch=`1`" in text
    assert "recoveries=`1/1`" in text


def test_planner_route_uat_analyzer_preserves_route_quality_predictions(tmp_path, monkeypatch):
    monkeypatch.setattr(analyzer, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    monkeypatch.setattr(analyzer, "REPO_ROOT", tmp_path)
    root = analyzer.SESSION_ROOT
    planner = root / "planner" / "fetch_planner_handoff_gate" / "gate_summary.json"
    _write_json(
        planner,
        {
            "campaign_id": "planner",
            "pass": True,
            "pass_count": 5,
            "random_cases": 5,
            "wrong_fetch_dispatch_count": 0,
            "route_counts": {
                analyzer.ROUTE_FETCH_READY: 1,
                analyzer.ROUTE_NAV2_REPOSITION: 1,
                analyzer.ROUTE_RECOVERY_OR_REAIM: 1,
                analyzer.ROUTE_SCAN_OR_PERCEIVE: 1,
                analyzer.ROUTE_NO_GO: 1,
            },
        },
    )
    missions = [
        root / "fetch_session" / "mission_verdict.json",
        root / "nav2_session" / "mission_verdict.json",
        root / "recovery_session" / "mission_verdict.json",
    ]
    _mission(
        missions[0],
        analyzer.ROUTE_FETCH_READY,
        route_quality={
            "predicted_contact_quality": "watch",
            "predicted_first_contact_risk": "medium",
            "quality_score": 61.25,
            "flags": ["initial_lateral_setup_debt"],
        },
    )
    _mission(missions[1], analyzer.ROUTE_NAV2_REPOSITION)
    _mission(missions[2], analyzer.ROUTE_RECOVERY_OR_REAIM)
    visual_package = root / "uat" / "fetch_visual_uat_package" / "package_summary.json"
    _write_json(
        visual_package,
        {
            "campaign_id": "uat",
            "pass": True,
            "mobile_watchable": True,
            "onboard_camera_watchable": True,
            "visual_confirmation_seen": True,
            "local_fetch_visual_confirmed": True,
            "videos": [{"name": "raw_camera_browser.mp4"}],
        },
    )

    summary = analyzer.build_summary(_args(tmp_path, planner=planner, missions=missions, visual_package=visual_package))

    assert summary["quality_prediction_counts"]["watch"] == 1
    assert summary["first_contact_risk_counts"]["medium"] == 1
    mission = next(item for item in summary["missions"] if item["route_label"] == analyzer.ROUTE_FETCH_READY)
    assert mission["predicted_contact_quality"] == "watch"
    assert mission["predicted_first_contact_risk"] == "medium"
    assert mission["route_quality_score"] == 61.25
    assert mission["route_quality_flags"] == ["initial_lateral_setup_debt"]

    scorecard = tmp_path / "scorecard.md"
    analyzer.write_scorecard(scorecard, summary)
    text = scorecard.read_text(encoding="utf-8")
    assert "Predicted contact quality" in text
    assert "predicted=`watch`" in text


def test_planner_route_uat_analyzer_requires_all_executable_routes(tmp_path, monkeypatch):
    monkeypatch.setattr(analyzer, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    monkeypatch.setattr(analyzer, "REPO_ROOT", tmp_path)
    root = analyzer.SESSION_ROOT
    planner = root / "planner" / "fetch_planner_handoff_gate" / "gate_summary.json"
    _write_json(
        planner,
        {
            "campaign_id": "planner",
            "pass": True,
            "pass_count": 5,
            "random_cases": 5,
            "wrong_fetch_dispatch_count": 0,
            "route_counts": {
                analyzer.ROUTE_FETCH_READY: 1,
                analyzer.ROUTE_NAV2_REPOSITION: 1,
                analyzer.ROUTE_RECOVERY_OR_REAIM: 1,
                analyzer.ROUTE_SCAN_OR_PERCEIVE: 1,
                analyzer.ROUTE_NO_GO: 1,
            },
        },
    )
    mission = root / "fetch_session" / "mission_verdict.json"
    _mission(mission, analyzer.ROUTE_FETCH_READY)
    visual_package = root / "uat" / "fetch_visual_uat_package" / "package_summary.json"
    _write_json(
        visual_package,
        {
            "campaign_id": "uat",
            "pass": True,
            "mobile_watchable": True,
            "onboard_camera_watchable": True,
        },
    )

    summary = analyzer.build_summary(_args(tmp_path, planner=planner, missions=[mission], visual_package=visual_package))

    assert summary["pass"] is False
    assert summary["executable_route_green"] is False
    rows = {row["route_label"]: row for row in summary["route_rows"]}
    assert rows[analyzer.ROUTE_NAV2_REPOSITION]["coverage_status"] == "missing_live_executable"
    assert rows[analyzer.ROUTE_RECOVERY_OR_REAIM]["coverage_status"] == "missing_live_executable"


def test_planner_route_uat_analyzer_treats_robot_posture_first_contact_flags_as_watch(tmp_path, monkeypatch):
    monkeypatch.setattr(analyzer, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    monkeypatch.setattr(analyzer, "REPO_ROOT", tmp_path)
    root = analyzer.SESSION_ROOT
    planner = root / "planner" / "fetch_planner_handoff_gate" / "gate_summary.json"
    _write_json(
        planner,
        {
            "campaign_id": "planner",
            "pass": True,
            "pass_count": 5,
            "random_cases": 5,
            "wrong_fetch_dispatch_count": 0,
            "route_counts": {
                analyzer.ROUTE_FETCH_READY: 1,
                analyzer.ROUTE_NAV2_REPOSITION: 1,
                analyzer.ROUTE_RECOVERY_OR_REAIM: 1,
                analyzer.ROUTE_SCAN_OR_PERCEIVE: 1,
                analyzer.ROUTE_NO_GO: 1,
            },
        },
    )
    missions = [
        root / "fetch_session" / "mission_verdict.json",
        root / "nav2_session" / "mission_verdict.json",
        root / "recovery_session" / "mission_verdict.json",
    ]
    _mission(
        missions[0],
        analyzer.ROUTE_FETCH_READY,
        first_flags=["first_contact_lateral_error", "first_contact_yaw_error"],
    )
    _mission(missions[1], analyzer.ROUTE_NAV2_REPOSITION)
    _mission(missions[2], analyzer.ROUTE_RECOVERY_OR_REAIM)
    visual_package = root / "uat" / "fetch_visual_uat_package" / "package_summary.json"
    _write_json(
        visual_package,
        {
            "campaign_id": "uat",
            "pass": True,
            "mobile_watchable": True,
            "onboard_camera_watchable": True,
            "visual_confirmation_seen": True,
            "local_fetch_visual_confirmed": True,
            "videos": [{"name": "raw_camera_browser.mp4"}],
        },
    )

    summary = analyzer.build_summary(_args(tmp_path, planner=planner, missions=missions, visual_package=visual_package))

    assert summary["pass"] is True
    assert summary["execution_quality_status"] == "watch"
    assert summary["setup_quality_status"] == "clean"
    assert summary["contact_quality_status"] == "watch"
    assert summary["first_contact_blocker_count"] == 0
    mission = next(item for item in summary["missions"] if item["route_label"] == analyzer.ROUTE_FETCH_READY)
    assert mission["execution_quality"] == "watch"
    assert mission["setup_quality"] == "clean"
    assert mission["contact_quality"] == "watch"
    assert mission["first_contact_blocker_flags"] == []


def test_planner_route_uat_analyzer_splits_setup_watch_from_contact_watch(tmp_path, monkeypatch):
    monkeypatch.setattr(analyzer, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    monkeypatch.setattr(analyzer, "REPO_ROOT", tmp_path)
    root = analyzer.SESSION_ROOT
    planner = root / "planner" / "fetch_planner_handoff_gate" / "gate_summary.json"
    _write_json(
        planner,
        {
            "campaign_id": "planner",
            "pass": True,
            "pass_count": 5,
            "random_cases": 5,
            "wrong_fetch_dispatch_count": 0,
            "route_counts": {
                analyzer.ROUTE_FETCH_READY: 1,
                analyzer.ROUTE_NAV2_REPOSITION: 1,
                analyzer.ROUTE_RECOVERY_OR_REAIM: 1,
                analyzer.ROUTE_SCAN_OR_PERCEIVE: 1,
                analyzer.ROUTE_NO_GO: 1,
            },
        },
    )
    missions = [
        root / "fetch_session" / "mission_verdict.json",
        root / "nav2_session" / "mission_verdict.json",
        root / "recovery_session" / "mission_verdict.json",
    ]
    _mission(missions[0], analyzer.ROUTE_FETCH_READY, flags=["pre_contact_lateral_error", "pre_contact_yaw_error"])
    _mission(missions[1], analyzer.ROUTE_NAV2_REPOSITION, flags=["ball_lateral_knock_away"])
    _mission(missions[2], analyzer.ROUTE_RECOVERY_OR_REAIM)
    visual_package = root / "uat" / "fetch_visual_uat_package" / "package_summary.json"
    _write_json(
        visual_package,
        {
            "campaign_id": "uat",
            "pass": True,
            "mobile_watchable": True,
            "onboard_camera_watchable": True,
            "visual_confirmation_seen": True,
            "local_fetch_visual_confirmed": True,
            "videos": [{"name": "raw_camera_browser.mp4"}],
        },
    )

    summary = analyzer.build_summary(_args(tmp_path, planner=planner, missions=missions, visual_package=visual_package))

    assert summary["execution_quality_status"] == "watch"
    assert summary["setup_quality_status"] == "watch"
    assert summary["contact_quality_status"] == "watch"
    assert summary["setup_watch_count"] == 1
    assert summary["contact_watch_count"] == 1
    setup_mission = next(item for item in summary["missions"] if item["route_label"] == analyzer.ROUTE_FETCH_READY)
    contact_mission = next(item for item in summary["missions"] if item["route_label"] == analyzer.ROUTE_NAV2_REPOSITION)
    assert setup_mission["setup_quality"] == "watch"
    assert setup_mission["contact_quality"] == "clean"
    assert setup_mission["setup_watch_flags"] == ["pre_contact_lateral_error", "pre_contact_yaw_error"]
    assert setup_mission["contact_watch_flags"] == []
    assert contact_mission["setup_quality"] == "clean"
    assert contact_mission["contact_quality"] == "watch"
    assert contact_mission["contact_watch_flags"] == ["ball_lateral_knock_away"]


def test_planner_route_uat_analyzer_blocks_missing_first_contact(tmp_path, monkeypatch):
    monkeypatch.setattr(analyzer, "SESSION_ROOT", tmp_path / "artifacts" / "session")
    monkeypatch.setattr(analyzer, "REPO_ROOT", tmp_path)
    root = analyzer.SESSION_ROOT
    planner = root / "planner" / "fetch_planner_handoff_gate" / "gate_summary.json"
    _write_json(
        planner,
        {
            "campaign_id": "planner",
            "pass": True,
            "pass_count": 1,
            "random_cases": 1,
            "wrong_fetch_dispatch_count": 0,
            "route_counts": {analyzer.ROUTE_FETCH_READY: 1},
        },
    )
    mission = root / "fetch_session" / "mission_verdict.json"
    _mission(mission, analyzer.ROUTE_FETCH_READY, first_flags=["missing_first_contact"])
    visual_package = root / "uat" / "fetch_visual_uat_package" / "package_summary.json"
    _write_json(
        visual_package,
        {
            "campaign_id": "uat",
            "pass": True,
            "mobile_watchable": True,
            "onboard_camera_watchable": True,
            "visual_confirmation_seen": True,
            "local_fetch_visual_confirmed": True,
            "videos": [{"name": "raw_camera_browser.mp4"}],
        },
    )

    summary = analyzer.build_summary(_args(tmp_path, planner=planner, missions=[mission], visual_package=visual_package))

    assert summary["pass"] is False
    assert summary["contact_quality_status"] == "blocker"
    assert summary["first_contact_blocker_count"] == 1
    assert summary["missions"][0]["first_contact_blocker_flags"] == ["missing_first_contact"]
