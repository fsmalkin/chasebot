from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_TOOLS_DIR = REPO_ROOT / "tools" / "robot_factory_bridge"
if str(BRIDGE_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_TOOLS_DIR))

import chasecar_bridge_gate_ladder_report as report  # noqa: E402


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def safe_health() -> dict:
    return {
        "ok": True,
        "motion_enabled": False,
        "left_motor": 0.0,
        "right_motor": 0.0,
        "camera": {
            "enabled": True,
            "loaded": True,
            "error": None,
            "backend": "v4l2_bayer",
            "cached_fps": 1.2,
            "frame_age_s": 0.4,
        },
    }


def gate_by_id(payload: dict, gate_id: str) -> dict:
    return next(gate for gate in payload["gates"] if gate["id"] == gate_id)


def test_gate_ladder_selects_yolo_reacquire_after_visible_approach_and_motion_pass(tmp_path):
    health_path = write_json(tmp_path / "health.json", safe_health())
    locked_path = write_json(
        tmp_path / "locked" / "overnight_loop_summary.json",
        {
            "type": "factory_bridge_overnight_endurance_loop",
            "pass": True,
            "completed_cycles": 1,
            "stop_reason": "max_cycles_reached",
            "cycles": [
                {
                    "closed_loop_pass": True,
                    "accepted_motor_event_count": 0,
                    "detector_evidence": {"yolo_onnx_primary_detected_steps": 1},
                }
            ],
        },
    )
    approach_path = write_json(
        tmp_path / "approach" / "overnight_loop_summary.json",
        {
            "type": "factory_bridge_overnight_endurance_loop",
            "pass": True,
            "completed_cycles": 1,
            "stop_reason": "max_cycles_reached",
            "cycles": [
                {
                    "closed_loop_pass": True,
                    "accepted_motor_event_count": 5,
                    "inverse_reset_pass": True,
                    "detector_evidence": {
                        "detector_arbitration_selected_counts": {"yolo_onnx": 5},
                        "yolo_onnx_primary_detected_steps": 5,
                    },
                }
            ],
        },
    )
    turn_path = write_json(
        tmp_path / "turn" / "turn_response_summary.json",
        {
            "type": "manual_turn_response_probe",
            "pass": True,
            "final_health": safe_health(),
            "contact_sheet": {"available": True},
        },
    )
    scan_path = write_json(
        tmp_path / "scan" / "cycle_0001" / "scan_reacquire" / "scan_reacquire_summary.json",
        {
            "pass": False,
            "stop_reason": "scan_steps_exhausted",
            "observations": [
                {
                    "analysis": {
                        "detector_backend": "yolo_onnx",
                        "detected": False,
                        "issues": ["target_not_detected"],
                    }
                }
            ],
        },
    )
    failed_reacquire_path = write_json(
        tmp_path / "scan" / "overnight_loop_summary.json",
        {
            "type": "factory_bridge_overnight_endurance_loop",
            "pass": False,
            "completed_cycles": 0,
            "stop_reason": "scan_reacquire_not_passed",
            "cycles": [
                {
                    "scan_reacquire_pass": False,
                    "scan_reacquire_summary_path": str(scan_path),
                }
            ],
        },
    )

    args = report.parse_args(
        [
            "--health-json",
            str(health_path),
            "--evidence",
            str(locked_path),
            "--evidence",
            str(approach_path),
            "--evidence",
            str(turn_path),
            "--evidence",
            str(failed_reacquire_path),
        ]
    )

    payload = report.build_report(args)

    assert gate_by_id(payload, "access_safety")["status"] == "pass"
    assert gate_by_id(payload, "camera_freshness")["status"] == "pass"
    assert gate_by_id(payload, "yolo_visible_target")["status"] == "pass"
    assert gate_by_id(payload, "locked_transport")["status"] == "pass"
    assert gate_by_id(payload, "motion_primitive")["status"] == "pass"
    assert gate_by_id(payload, "visible_approach")["status"] == "pass"
    assert gate_by_id(payload, "yolo_reacquire")["status"] == "fail"
    assert payload["next_gate"]["id"] == "yolo_reacquire"
    assert "YOLO-only target reacquire" in payload["next_gate"]["next_goal"]


def test_initially_visible_yolo_scan_does_not_promote_reacquire(tmp_path):
    health_path = write_json(tmp_path / "health.json", safe_health())
    scan_path = write_json(
        tmp_path / "scan" / "cycle_0001" / "scan_reacquire" / "scan_reacquire_summary.json",
        {
            "pass": True,
            "stop_reason": "target_visible_initially",
            "accepted_motor_events": [],
            "observations": [
                {
                    "analysis": {
                        "detector_backend": "yolo_onnx",
                        "detected": True,
                    }
                }
            ],
        },
    )
    visible_initial_path = write_json(
        tmp_path / "scan" / "overnight_loop_summary.json",
        {
            "type": "factory_bridge_overnight_endurance_loop",
            "pass": True,
            "completed_cycles": 1,
            "stop_reason": "max_cycles_reached",
            "cycles": [
                {
                    "scan_reacquire_pass": True,
                    "scan_reacquire_summary_path": str(scan_path),
                }
            ],
        },
    )

    args = report.parse_args(
        [
            "--health-json",
            str(health_path),
            "--evidence",
            str(visible_initial_path),
        ]
    )

    payload = report.build_report(args)

    assert gate_by_id(payload, "yolo_visible_target")["status"] == "pass"
    assert gate_by_id(payload, "yolo_reacquire")["status"] == "pending"


def test_yolo_scan_failure_marks_reacquire_even_when_reset_also_fails(tmp_path):
    health_path = write_json(tmp_path / "health.json", safe_health())
    scan_path = write_json(
        tmp_path / "scan" / "cycle_0001" / "scan_reacquire" / "scan_reacquire_summary.json",
        {
            "pass": False,
            "stop_reason": "scan_steps_exhausted",
            "observations": [
                {
                    "analysis": {
                        "detector_backend": "yolo_onnx",
                        "detected": False,
                    }
                }
            ],
        },
    )
    failed_reset_path = write_json(
        tmp_path / "scan" / "overnight_loop_summary.json",
        {
            "type": "factory_bridge_overnight_endurance_loop",
            "pass": False,
            "completed_cycles": 0,
            "stop_reason": "scan_inverse_reset_not_passed",
            "cycles": [
                {
                    "scan_reacquire_pass": False,
                    "scan_reacquire_summary_path": str(scan_path),
                    "scan_inverse_reset_pass": False,
                }
            ],
        },
    )

    args = report.parse_args(
        [
            "--health-json",
            str(health_path),
            "--evidence",
            str(failed_reset_path),
        ]
    )

    payload = report.build_report(args)

    assert gate_by_id(payload, "yolo_reacquire")["status"] == "fail"
    assert payload["next_gate"]["id"] == "yolo_visible_target"


def test_gate_ladder_fails_access_safety_for_unlocked_bridge(tmp_path):
    unsafe = safe_health()
    unsafe["motion_enabled"] = True
    health_path = write_json(tmp_path / "health.json", unsafe)

    args = report.parse_args(["--health-json", str(health_path)])

    payload = report.build_report(args)

    assert gate_by_id(payload, "access_safety")["status"] == "fail"
    assert payload["next_gate"]["id"] == "access_safety"
