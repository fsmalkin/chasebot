import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_visual_uat_package as package  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    package.write_json(path, payload)


def _stub_browser_video_probe(monkeypatch):
    def _probe(path: Path) -> dict:
        return {
            "size_bytes": path.stat().st_size if path.exists() else 0,
            "ffprobe_valid": True,
            "browser_playable": True,
            "codec_name": "h264",
            "pix_fmt": "yuv420p",
            "duration_s": 1.0,
            "validation_error": "",
        }

    monkeypatch.setattr(package, "inspect_video_file", _probe)


def test_visual_uat_package_scores_mobile_ready(tmp_path, monkeypatch):
    session_root = tmp_path / "artifacts" / "session"
    monkeypatch.setattr(package, "SESSION_ROOT", session_root)
    monkeypatch.setattr(package, "REPO_ROOT", tmp_path)
    _stub_browser_video_probe(monkeypatch)

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
            "fetch_pose_world": {"x": 0.95, "y": 0.0, "z": 0.001, "radius_m": 0.3},
            "visible_delivery_marker_pose": {"x": 0.95, "y": 0.0, "z": 0.001, "radius_m": 0.3},
            "model_provenance": {
                "model_provenance_valid": True,
                "model_provenance_reason": "calibrated_fetch_models",
                "target_model_sdf": "ros2_config/calibrated_golf_ball.sdf",
                "zone_model_sdf": "ros2_config/golf_ball_delivery_zone_marker.sdf",
                "target_model_radius_m": 0.021336,
                "target_model_classification": "calibrated_golf_ball",
                "zone_model_classification": "golf_ball_delivery_zone_marker",
            },
        },
    )
    visual = session_root / "mission" / "visual"
    visual.mkdir(parents=True)
    (visual / "world_stream.mp4").write_bytes(b"w" * package.VIDEO_MIN_BYTES)
    (visual / "topdown_telemetry_browser.mp4").write_bytes(b"t" * package.VIDEO_MIN_BYTES)
    (visual / "raw_camera_browser.mp4").write_bytes(b"r" * package.VIDEO_MIN_BYTES)
    _write_json(
        visual / "visual_demo_summary.json",
        {
            "pass": True,
            "raw_nonblank": True,
            "debug_nonblank": True,
            "target_persistence_ok": True,
            "motion_progress_ok": True,
            "target_visible_ratio": 0.9,
            "raw_frame_count": 20,
            "telemetry_frame_count": 20,
        },
    )
    stage_quality = session_root / "stage" / "fetch_saved_anchor_setup_contact_audit" / "audit_summary.json"
    _write_json(
        stage_quality,
        {
            "type": "fetch_saved_anchor_setup_contact_audit",
            "campaign_id": "stage",
            "stage_quality_green": False,
            "overall_interpretation": "saved_anchor_repeatability_ready_with_contact_watch",
            "saved_anchor_count": 3,
            "stage_quality_pass_count": 3,
            "setup_contact_blocker_count": 0,
            "saved_anchor_pass_with_contact_watch_count": 1,
            "saved_anchors": [
                {
                    "layout": "zero",
                    "pass": True,
                    "delivery_pass": True,
                    "quality_classification": "pass_with_capture_quality_watch",
                    "quality_flags": ["pre_stage_yaw_watch"],
                }
            ],
        },
    )

    args = type(
        "Args",
        (),
        {
            "campaign_id": "uat",
            "planner_summary": [str(planner)],
            "seeded_evidence_summary": [],
            "stage_quality_summary": [str(stage_quality)],
            "mission_summary": [str(mission)],
            "visual_dir": [str(visual)],
        },
    )()

    summary = package.build_summary(args)

    assert summary["pass"] is True
    assert summary["mobile_watchable"] is True
    assert summary["onboard_camera_watchable"] is True
    assert summary["visual_confirmation_seen"] is True
    assert summary["local_fetch_visual_confirmed"] is True
    assert summary["planner_gate_green"] is True
    assert summary["local_fetch_pass_seen"] is True
    assert summary["stage_quality_status"] == "watch"
    assert summary["stage_quality_audits"][0]["watch_count"] == 1
    assert "stage_quality_watch" in summary["warnings"]
    assert summary["fetch_marker_geometry_mismatch_seen"] is False
    assert {video["name"] for video in summary["videos"]} == {
        "world_stream.mp4",
        "topdown_telemetry_browser.mp4",
        "raw_camera_browser.mp4",
    }
    raw_video = next(video for video in summary["videos"] if video["name"] == "raw_camera_browser.mp4")
    assert raw_video["role"] == "onboard_camera"
    assert raw_video["browser_compatible"] is True
    assert summary["videos"][0]["url"].startswith("/artifacts/session/")
    scorecard = tmp_path / "scorecard.md"
    package.write_scorecard(scorecard, summary)
    text = scorecard.read_text(encoding="utf-8")
    assert "[raw_camera_browser.mp4](/artifacts/session/" in text
    assert "`/artifacts/session/" not in text


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


def test_visual_uat_package_requires_healthy_visual_confirmation(tmp_path, monkeypatch):
    session_root = tmp_path / "artifacts" / "session"
    monkeypatch.setattr(package, "SESSION_ROOT", session_root)
    monkeypatch.setattr(package, "REPO_ROOT", tmp_path)
    _stub_browser_video_probe(monkeypatch)

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
    (visual / "world_stream.mp4").write_bytes(b"w" * package.VIDEO_MIN_BYTES)
    (visual / "topdown_telemetry_browser.mp4").write_bytes(b"t" * package.VIDEO_MIN_BYTES)
    (visual / "raw_camera_browser.mp4").write_bytes(b"r" * package.VIDEO_MIN_BYTES)
    _write_json(
        visual / "visual_demo_summary.json",
        {"pass": False, "raw_nonblank": True, "target_persistence_ok": False, "motion_progress_ok": True},
    )
    _write_json(
        visual / "world_stream_summary.json",
        {"pass": False, "world_stream_degraded": True, "failure_class": "world_stream_receive_rate_low"},
    )

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
    assert summary["mobile_watchable"] is True
    assert summary["visual_confirmation_seen"] is False
    assert summary["local_fetch_visual_confirmed"] is False
    assert "no_healthy_visual_confirmation" in summary["warnings"]


def test_visual_uat_package_requires_same_session_visual_confirmation(tmp_path, monkeypatch):
    session_root = tmp_path / "artifacts" / "session"
    monkeypatch.setattr(package, "SESSION_ROOT", session_root)
    monkeypatch.setattr(package, "REPO_ROOT", tmp_path)
    _stub_browser_video_probe(monkeypatch)

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
    passing_mission = session_root / "pass_session" / "gather_mission" / "mission_verdict.json"
    _write_json(
        passing_mission,
        {
            "fetch_to_pose_pass": True,
            "pass": True,
            "model_provenance": {
                "model_provenance_valid": True,
                "target_model_classification": "calibrated_golf_ball",
                "zone_model_classification": "golf_ball_delivery_zone_marker",
            },
        },
    )
    pass_visual = session_root / "pass_session" / "visual"
    pass_visual.mkdir(parents=True)
    (pass_visual / "world_stream.mp4").write_bytes(b"w" * package.VIDEO_MIN_BYTES)
    (pass_visual / "topdown_telemetry_browser.mp4").write_bytes(b"t" * package.VIDEO_MIN_BYTES)
    (pass_visual / "raw_camera_browser.mp4").write_bytes(b"r" * package.VIDEO_MIN_BYTES)
    _write_json(pass_visual / "visual_demo_summary.json", {"pass": False, "target_persistence_ok": False})

    failed_visual = session_root / "failed_session" / "visual"
    failed_visual.mkdir(parents=True)
    (failed_visual / "world_stream.mp4").write_bytes(b"w" * package.VIDEO_MIN_BYTES)
    (failed_visual / "topdown_telemetry_browser.mp4").write_bytes(b"t" * package.VIDEO_MIN_BYTES)
    (failed_visual / "raw_camera_browser.mp4").write_bytes(b"r" * package.VIDEO_MIN_BYTES)
    _write_json(failed_visual / "world_stream_summary.json", {"pass": True})

    args = type(
        "Args",
        (),
        {
            "campaign_id": "uat",
            "planner_summary": [str(planner)],
            "seeded_evidence_summary": [],
            "mission_summary": [str(passing_mission)],
            "visual_dir": [str(pass_visual), str(failed_visual)],
        },
    )()

    summary = package.build_summary(args)

    assert summary["pass"] is False
    assert summary["visual_confirmation_seen"] is True
    assert summary["local_fetch_visual_confirmed"] is False
    assert "passing_local_fetch_lacks_same_session_visual_confirmation" in summary["warnings"]


def test_visual_uat_package_rejects_fetch_marker_geometry_mismatch(tmp_path, monkeypatch):
    session_root = tmp_path / "artifacts" / "session"
    monkeypatch.setattr(package, "SESSION_ROOT", session_root)
    monkeypatch.setattr(package, "REPO_ROOT", tmp_path)
    _stub_browser_video_probe(monkeypatch)

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
    mission = session_root / "pass_session" / "gather_mission" / "mission_verdict.json"
    _write_json(
        mission,
        {
            "scenario_label": "Golf Ball Circle Delivery",
            "mission_objective": "fetch_to_pose",
            "pass": True,
            "fetch_to_pose_pass": True,
            "fetch_pose_world": {"x": 0.95, "y": 0.0, "z": 0.001, "radius_m": 0.3},
            "zone_pose": {"x": 2.4, "y": 0.0, "z": 0.001, "radius_m": 0.762},
            "model_provenance": {
                "model_provenance_valid": True,
                "target_model_classification": "calibrated_golf_ball",
                "zone_model_classification": "golf_ball_delivery_zone_marker",
            },
        },
    )
    visual = session_root / "pass_session" / "visual"
    visual.mkdir(parents=True)
    (visual / "world_stream.mp4").write_bytes(b"w" * package.VIDEO_MIN_BYTES)
    (visual / "topdown_telemetry_browser.mp4").write_bytes(b"t" * package.VIDEO_MIN_BYTES)
    (visual / "raw_camera_browser.mp4").write_bytes(b"r" * package.VIDEO_MIN_BYTES)
    _write_json(visual / "world_stream_summary.json", {"pass": True})

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
    assert summary["raw_local_fetch_pass_seen"] is True
    assert summary["local_fetch_pass_seen"] is False
    assert summary["fetch_marker_geometry_mismatch_seen"] is True
    assert "fetch_marker_geometry_mismatch" in summary["warnings"]
    assert summary["missions"][0]["geometry_consistency"]["reason"] == "center_mismatch"


def test_visual_uat_package_withholds_invalid_browser_video_links(tmp_path, monkeypatch):
    session_root = tmp_path / "artifacts" / "session"
    monkeypatch.setattr(package, "SESSION_ROOT", session_root)
    monkeypatch.setattr(package, "REPO_ROOT", tmp_path)

    def _probe(path: Path) -> dict:
        valid = path.name == "world_stream.mp4"
        return {
            "size_bytes": path.stat().st_size,
            "ffprobe_valid": valid,
            "browser_playable": valid,
            "codec_name": "h264" if valid else "",
            "pix_fmt": "yuv420p" if valid else "",
            "duration_s": 1.0 if valid else 0.0,
            "validation_error": "" if valid else "moov_atom_not_found",
        }

    monkeypatch.setattr(package, "inspect_video_file", _probe)

    visual = session_root / "mission" / "visual"
    visual.mkdir(parents=True)
    (visual / "world_stream.mp4").write_bytes(b"w" * package.VIDEO_MIN_BYTES)
    (visual / "topdown_telemetry_browser.mp4").write_bytes(b"t" * package.VIDEO_MIN_BYTES)
    (visual / "raw_camera_browser.mp4").write_bytes(b"r" * package.VIDEO_MIN_BYTES)

    videos = package.discover_videos([visual])

    raw_video = next(video for video in videos if video["name"] == "raw_camera_browser.mp4")
    world_video = next(video for video in videos if video["name"] == "world_stream.mp4")
    assert raw_video["browser_playable"] is False
    assert raw_video["url"] == ""
    assert raw_video["validation_error"] == "moov_atom_not_found"
    assert world_video["browser_playable"] is True
    assert world_video["url"].startswith("/artifacts/session/")
