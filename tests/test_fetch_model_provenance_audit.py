from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_model_provenance_audit as audit  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_model_provenance_audit_classifies_valid_fetch_summary(tmp_path):
    root = tmp_path / "artifacts" / "session"
    summary_path = root / "valid" / "gather_mission_repeatability" / "campaign_run_summary.json"
    _write_json(
        summary_path,
        {
            "type": "gather_mission_repeatability",
            "campaign_id": "valid",
            "mission_objective": "fetch_to_pose",
            "fetch_to_pose_pass_count": 1,
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

    args = type(
        "Args",
        (),
        {
            "campaign_id": "audit",
            "root": str(root),
            "provenance_boundary_commit": "680e393",
            "max_rows": 100,
            "include_non_fetch": False,
        },
    )()

    summary = audit.build_summary(args)

    assert summary["pass"] is True
    assert summary["valid_model_provenance_count"] == 1
    assert summary["rows"][0]["model_provenance_status"] == "valid_model_provenance"


def test_model_provenance_audit_quarantines_legacy_target(tmp_path):
    root = tmp_path / "artifacts" / "session"
    verdict_path = root / "legacy" / "gather_mission" / "run" / "mission_verdict.json"
    _write_json(
        verdict_path,
        {
            "type": "gather_mission",
            "mission_objective": "fetch_to_pose",
            "fetch_to_pose_pass": True,
            "model_provenance": {
                "model_provenance_valid": False,
                "model_provenance_reason": "invalid_target_model:legacy_frisbee_target_ball",
                "target_model_sdf": "ros2_config/frisbee_target_ball.sdf",
                "zone_model_sdf": "ros2_config/golf_ball_delivery_zone_marker.sdf",
                "target_model_radius_m": 0.05,
                "target_model_classification": "legacy_frisbee_target_ball",
                "zone_model_classification": "golf_ball_delivery_zone_marker",
            },
        },
    )

    args = type(
        "Args",
        (),
        {
            "campaign_id": "audit",
            "root": str(root),
            "provenance_boundary_commit": "680e393",
            "max_rows": 100,
            "include_non_fetch": False,
        },
    )()

    summary = audit.build_summary(args)

    assert summary["pass"] is False
    assert summary["quarantine_invalid_model_provenance_count"] == 1
    assert summary["rows"][0]["model_provenance_status"] == "quarantine_invalid_model_provenance"


def test_model_provenance_audit_marks_missing_provenance_for_recheck(tmp_path):
    root = tmp_path / "artifacts" / "session"
    summary_path = root / "missing" / "gather_mission_repeatability" / "campaign_run_summary.json"
    _write_json(
        summary_path,
        {
            "type": "gather_mission_repeatability",
            "campaign_id": "missing",
            "mission_objective": "fetch_to_pose",
            "fetch_to_pose_pass_count": 1,
        },
    )

    args = type(
        "Args",
        (),
        {
            "campaign_id": "audit",
            "root": str(root),
            "provenance_boundary_commit": "680e393",
            "max_rows": 100,
            "include_non_fetch": False,
        },
    )()

    summary = audit.build_summary(args)

    assert summary["pass"] is False
    assert summary["needs_recheck_missing_model_provenance_count"] == 1
    assert summary["rows"][0]["model_provenance_status"] == "needs_recheck_missing_model_provenance"


def test_model_provenance_audit_infers_from_recorded_sdf_paths(tmp_path):
    root = tmp_path / "artifacts" / "session"
    summary_path = root / "inferred" / "gather_mission_repeatability" / "campaign_run_summary.json"
    _write_json(
        summary_path,
        {
            "type": "gather_mission_repeatability",
            "campaign_id": "inferred",
            "mission_objective": "fetch_to_pose",
            "fetch_to_pose_pass_count": 1,
            "target_model_sdf": "ros2_config/calibrated_golf_ball.sdf",
            "zone_model_sdf": "ros2_config/golf_ball_delivery_zone_marker.sdf",
        },
    )

    args = type(
        "Args",
        (),
        {
            "campaign_id": "audit",
            "root": str(root),
            "provenance_boundary_commit": "680e393",
            "max_rows": 100,
            "include_non_fetch": False,
        },
    )()

    summary = audit.build_summary(args)

    assert summary["pass"] is True
    assert summary["rows"][0]["model_provenance_status"] == "valid_model_provenance"
    assert summary["rows"][0]["target_model_classification"] == "calibrated_golf_ball"
