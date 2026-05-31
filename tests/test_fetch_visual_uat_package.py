import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_visual_uat_package as package  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    package.write_json(path, payload)


def test_visual_uat_package_scores_mobile_ready(tmp_path, monkeypatch):
    session_root = tmp_path / "artifacts" / "session"
    monkeypatch.setattr(package, "SESSION_ROOT", session_root)
    monkeypatch.setattr(package, "REPO_ROOT", tmp_path)

    planner = session_root / "planner" / "fetch_planner_handoff_gate" / "gate_summary.json"
    _write_json(
        planner,
        {
            "campaign_id": "planner",
            "type": "fetch_planner_handoff_gate",
            "pass": True,
            "pass_count": 5,
            "fail_count": 0,
            "random_cases": 5,
            "fetch_dispatch_count": 1,
            "wrong_fetch_dispatch_count": 0,
            "route_counts": {"fetch_ready_local": 1},
        },
    )
    mission = session_root / "mission" / "gather_mission_repeatability" / "campaign_run_summary.json"
    _write_json(
        mission,
        {
            "campaign_id": "mission",
            "mission_objective": "fetch_to_pose",
            "ai_push_coast_mode": "guarded_live",
            "fetch_to_pose_pass_count": 1,
            "fetch_to_pose_fail_count": 0,
            "promotion_gate_pass": True,
        },
    )
    visual = session_root / "mission" / "visual"
    visual.mkdir(parents=True)
    (visual / "world_stream.mp4").write_bytes(b"w" * package.VIDEO_MIN_BYTES)
    (visual / "topdown_telemetry_browser.mp4").write_bytes(b"t" * package.VIDEO_MIN_BYTES)
    (visual / "raw_camera_browser.mp4").write_bytes(b"r" * package.VIDEO_MIN_BYTES)

    args = type(
        "Args",
        (),
        {
            "campaign_id": "uat",
            "planner_summary": [str(planner)],
            "seeded_evidence_summary": [],
            "mission_summary": [str(mission)],
            "visual_dir": [str(visual)],
        },
    )()

    summary = package.build_summary(args)

    assert summary["pass"] is True
    assert summary["mobile_watchable"] is True
    assert summary["onboard_camera_watchable"] is True
    assert summary["planner_gate_green"] is True
    assert summary["local_fetch_pass_seen"] is True
    assert {video["name"] for video in summary["videos"]} == {
        "world_stream.mp4",
        "topdown_telemetry_browser.mp4",
        "raw_camera_browser.mp4",
    }
    raw_video = next(video for video in summary["videos"] if video["name"] == "raw_camera_browser.mp4")
    assert raw_video["role"] == "onboard_camera"
    assert raw_video["browser_compatible"] is True
    assert summary["videos"][0]["url"].startswith("/artifacts/session/")


def test_visual_uat_package_warns_when_core_video_missing(tmp_path, monkeypatch):
    session_root = tmp_path / "artifacts" / "session"
    monkeypatch.setattr(package, "SESSION_ROOT", session_root)
    monkeypatch.setattr(package, "REPO_ROOT", tmp_path)

    planner = session_root / "planner" / "fetch_planner_handoff_gate" / "gate_summary.json"
    _write_json(
        planner,
        {
            "campaign_id": "planner",
            "pass": True,
            "pass_count": 5,
            "random_cases": 5,
            "wrong_fetch_dispatch_count": 0,
        },
    )
    mission = session_root / "mission" / "summary.json"
    _write_json(mission, {"campaign_id": "mission", "fetch_to_pose_pass": True, "pass": True})
    visual = session_root / "mission" / "visual"
    visual.mkdir(parents=True)
    (visual / "world_stream.mp4").write_bytes(b"world")

    args = type(
        "Args",
        (),
        {
            "campaign_id": "uat",
            "planner_summary": [str(planner)],
            "seeded_evidence_summary": [],
            "mission_summary": [str(mission)],
            "visual_dir": [str(visual)],
        },
    )()

    summary = package.build_summary(args)

    assert summary["pass"] is False
    assert summary["mobile_watchable"] is False
    assert "missing_or_tiny_required_mobile_video" in summary["warnings"]
    assert "missing_or_tiny_onboard_raw_camera_video" in summary["warnings"]
