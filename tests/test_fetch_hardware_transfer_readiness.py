from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_hardware_transfer_readiness as readiness  # noqa: E402


def _args(tmp_path: Path, **overrides):
    payload = {
        "campaign_id": "hardware_ready",
        "regression_manifest": str(tmp_path / "regression.json"),
        "dashboard_plan": str(tmp_path / "dashboard.json"),
        "hardware_contract": str(tmp_path / "hardware_contract.md"),
        "hardware_constraints": str(tmp_path / "hardware_constraints.md"),
        "tensorrt_readme": str(tmp_path / "tensorrt.md"),
        "min_seeded_gates": 8,
        "min_live_missions": 48,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(readiness.json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _green_regression(path: Path) -> Path:
    return _write_json(
        path,
        {
            "pass": True,
            "milestone_interpretation": "planner_routed_moonshot_regression_set_green",
            "totals": {
                "issue_count": 0,
                "seeded_gate_count": 8,
                "seeded_gate_green_count": 8,
                "seeded_live_mission_pass_count": 48,
                "seeded_visual_package_pass_count": 48,
                "control_preflight_green_count": 1,
            },
        },
    )


def _green_dashboard(path: Path) -> Path:
    return _write_json(
        path,
        {
            "status_label": "Mixed all-routes seed 20260643 is green",
            "status_detail": "seed 20260643 passed with browser-watchable evidence",
            "uat_review_bundle": {
                "route_samples": [
                    {
                        "label": f"sample{i}",
                        "video_url": f"/artifacts/session/sample{i}/visual/raw_camera_browser.mp4",
                        "topdown_url": f"/artifacts/session/sample{i}/visual/topdown_telemetry_browser.mp4",
                        "world_url": f"/artifacts/session/sample{i}/visual/world_stream.mp4",
                        "contact_sheet_url": f"/artifacts/session/sample{i}/visual/keyframe_review_contact_sheet.png",
                    }
                    for i in range(6)
                ]
            },
        },
    )


def _green_hardware_rehearsal_dashboard(path: Path) -> Path:
    return _write_json(
        path,
        {
            "status_label": "Hardware rehearsal green through seed 20260635",
            "status_detail": "seed 20260635 passed the hardware rehearsal ladder",
            "uat_review_bundle": {
                "route_samples": [
                    {
                        "label": f"sample{i}",
                        "video_url": f"/artifacts/session/sample{i}/visual/raw_camera_browser.mp4",
                        "topdown_url": f"/artifacts/session/sample{i}/visual/topdown_telemetry_browser.mp4",
                        "world_url": f"/artifacts/session/sample{i}/visual/world_stream.mp4",
                        "contact_sheet_url": f"/artifacts/session/sample{i}/visual/keyframe_review_contact_sheet.png",
                    }
                    for i in range(6)
                ]
            },
        },
    )


def _green_docs(tmp_path: Path) -> None:
    _write_text(
        tmp_path / "hardware_contract.md",
        "Jetson Orin Nano 8GB\nruntime_target=robot_fidelity_orin\ninference_backend=tensorrt_int8\n",
    )
    _write_text(
        tmp_path / "hardware_constraints.md",
        "Jetson Orin Nano 8GB\ncmd_vel\nController update rate\n100 Hz\n",
    )
    _write_text(
        tmp_path / "tensorrt.md",
        "tensorrt_int8\nbuild INT8 engine\nRuntimeTarget robot_fidelity_orin\n",
    )


def _green_fixture(tmp_path: Path) -> SimpleNamespace:
    args = _args(tmp_path)
    _green_regression(Path(args.regression_manifest))
    _green_dashboard(Path(args.dashboard_plan))
    _green_docs(tmp_path)
    return args


def test_hardware_transfer_readiness_is_rehearsal_ready_without_claiming_hardware_proof(tmp_path: Path):
    args = _green_fixture(tmp_path)

    summary = readiness.build_summary(args)

    assert summary["pass"] is True
    assert summary["hardware_transfer_ready"] is True
    assert summary["readiness_level"] == "ready_for_hardware_rehearsal"
    assert summary["hardware_proven"] is False
    assert summary["promotion_evidence"] is False
    assert "robot_side_live_rehearsal_not_run" in summary["open_hardware_gates"]


def test_hardware_transfer_readiness_accepts_hardware_rehearsal_dashboard_status(tmp_path: Path):
    args = _green_fixture(tmp_path)
    _green_hardware_rehearsal_dashboard(Path(args.dashboard_plan))

    summary = readiness.build_summary(args)

    assert summary["pass"] is True
    assert summary["dashboard_plan"]["status_label"] == "Hardware rehearsal green through seed 20260635"
    assert "seed20260643" in summary["required_next_rehearsal"]["minimum_live_contract"]


def test_hardware_transfer_readiness_fails_closed_when_visual_package_is_missing(tmp_path: Path):
    args = _green_fixture(tmp_path)
    _write_json(
        Path(args.dashboard_plan),
        {
            "status_label": "Hardware rehearsal green through seed 20260635",
            "status_detail": "seed 20260635 passed",
            "uat_review_bundle": {"route_samples": []},
        },
    )

    summary = readiness.build_summary(args)

    assert summary["pass"] is False
    assert summary["hardware_transfer_ready"] is False
    assert summary["readiness_level"] == "hardware_rehearsal_blocked"
    assert "dashboard_uat_samples_below_6" in summary["dashboard_plan"]["issues"]


def test_hardware_transfer_scorecard_names_open_gates(tmp_path: Path):
    scorecard = tmp_path / "scorecard.md"
    summary = readiness.build_summary(_green_fixture(tmp_path))

    readiness.write_scorecard(scorecard, summary)

    text = scorecard.read_text(encoding="utf-8")
    assert "hardware_proven: `False`" in text
    assert "robot_side_live_rehearsal_not_run" in text
    assert "runtime_target: `robot_fidelity_orin`" in text
