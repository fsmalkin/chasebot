from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_TOOLS_DIR = REPO_ROOT / "tools" / "robot_factory_bridge"
if str(BRIDGE_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_TOOLS_DIR))

import chasecar_bridge_overnight_endurance_loop as loop  # noqa: E402


class FakeResetClient:
    def __init__(self):
        self.calls = []

    def stop(self, source):
        self.calls.append(("stop", source))
        return 200, {"ok": True}

    def set_motion_enabled(self, enabled, source):
        self.calls.append(("set_motion_enabled", enabled, source))
        return 200, self.health()[1]

    def motors(self, left, right, duration_s, source):
        self.calls.append(("motors", left, right, duration_s, source))
        return 200, self.health()[1]

    def health(self):
        self.calls.append(("health",))
        return 200, {"motion_enabled": False, "left_motor": 0.0, "right_motor": 0.0}


def test_yolo_color_override_multiplier_flows_to_scan_and_closed_loop(tmp_path):
    args = loop.parse_args(
        [
            "--yolo-color-override-area-multiplier",
            "1.6",
            "--target-profile",
            "green",
            "--target-min-luma",
            "20",
            "--target-min-saturation",
            "0.12",
            "--target-min-value",
            "0.08",
            "--target-border-margin-ratio",
            "0.04",
            "--target-max-area-ratio",
            "0.20",
            "--target-max-bbox-width-ratio",
            "0.35",
            "--target-max-bbox-height-ratio",
            "0.80",
            "--target-min-bbox-aspect-ratio",
            "0.10",
            "--target-max-bbox-aspect-ratio",
            "0.8",
        ]
    )

    scan_args = loop.scan_detection_args(args)
    closed_loop_args = loop.build_closed_loop_args(args, tmp_path / "closed_loop")

    assert scan_args.yolo_color_override_area_multiplier == 1.6
    assert closed_loop_args.yolo_color_override_area_multiplier == 1.6
    assert scan_args.target_profile == "green"
    assert closed_loop_args.target_profile == "green"
    assert scan_args.target_min_luma == 20
    assert closed_loop_args.target_min_luma == 20
    assert scan_args.target_min_saturation == 0.12
    assert closed_loop_args.target_min_saturation == 0.12
    assert scan_args.target_min_value == 0.08
    assert closed_loop_args.target_min_value == 0.08
    assert scan_args.target_border_margin_ratio == 0.04
    assert closed_loop_args.target_border_margin_ratio == 0.04
    assert scan_args.target_max_area_ratio == 0.20
    assert closed_loop_args.target_max_area_ratio == 0.20
    assert scan_args.target_max_bbox_width_ratio == 0.35
    assert closed_loop_args.target_max_bbox_width_ratio == 0.35
    assert scan_args.target_max_bbox_height_ratio == 0.80
    assert closed_loop_args.target_max_bbox_height_ratio == 0.80
    assert scan_args.target_min_bbox_aspect_ratio == 0.10
    assert closed_loop_args.target_min_bbox_aspect_ratio == 0.10
    assert scan_args.target_max_bbox_aspect_ratio == 0.8
    assert closed_loop_args.target_max_bbox_aspect_ratio == 0.8


def test_camera_fetch_mode_flows_to_closed_loop(tmp_path):
    args = loop.parse_args(
        [
            "--camera-fetch-mode",
            "ssh",
            "--camera-fetch-timeout-s",
            "7",
            "--snapshot-attempts",
            "3",
            "--snapshot-retry-interval-s",
            "0.4",
            "--robot-host",
            "192.168.1.11",
            "--robot-user",
            "jetson",
            "--port",
            "8765",
        ]
    )

    closed_loop_args = loop.build_closed_loop_args(args, tmp_path / "closed_loop")

    assert closed_loop_args.camera_fetch_mode == "ssh"
    assert closed_loop_args.camera_fetch_timeout_s == 7
    assert closed_loop_args.snapshot_attempts == 3
    assert closed_loop_args.snapshot_retry_interval_s == 0.4
    assert closed_loop_args.robot_host == "192.168.1.11"
    assert closed_loop_args.robot_user == "jetson"
    assert closed_loop_args.port == 8765


def test_basement_green_preset_sets_hardware_target_thresholds(tmp_path):
    args = loop.parse_args(["--target-preset", "basement_green_v0"])
    scan_args = loop.scan_detection_args(args)
    closed_loop_args = loop.build_closed_loop_args(args, tmp_path / "closed_loop")

    assert args.target_profile == "green"
    assert args.target_min_luma == 20.0
    assert args.target_min_saturation == 0.12
    assert args.target_min_value == 0.08
    assert args.target_min_area_ratio == 0.005
    assert args.target_max_area_ratio == 0.20
    assert args.target_max_bbox_width_ratio == 0.35
    assert args.target_max_bbox_height_ratio == 0.80
    assert args.target_border_margin_ratio == 0.0
    assert args.target_min_bbox_aspect_ratio == 0.10
    assert args.target_max_bbox_aspect_ratio == 0.75
    assert args.target_min_centroid_y_ratio == 0.0
    assert args.target_max_centroid_y_ratio == 0.86
    assert args.yolo_target_min_area_ratio == 0.005
    assert args.camera_min_fps == 1.0
    assert args.visual_center_deadband == 0.12
    assert args.visual_turn_sign == 1.0
    assert args.stack_acquire_turn_sign == 1.0
    assert scan_args.target_profile == "green"
    assert scan_args.target_max_centroid_y_ratio == 0.86
    assert scan_args.visual_turn_sign == 1.0
    assert scan_args.stack_acquire_turn_sign == 1.0
    assert closed_loop_args.target_profile == "green"
    assert closed_loop_args.camera_min_fps == 1.0
    assert closed_loop_args.visual_center_deadband == 0.12
    assert closed_loop_args.target_max_centroid_y_ratio == 0.86
    assert closed_loop_args.visual_turn_sign == 1.0
    assert closed_loop_args.stack_acquire_turn_sign == 1.0


def test_overnight_loop_keeps_motion_locked_by_default(tmp_path):
    args = loop.parse_args([])
    closed_loop_args = loop.build_closed_loop_args(args, tmp_path / "closed_loop")

    assert loop.validate_args(args) == []
    assert loop.live_motion_approved(args) is False
    assert closed_loop_args.execute_motion is False
    assert closed_loop_args.confirm_operator_ready is False
    assert closed_loop_args.require_nav_target_success is True


def test_overnight_loop_can_disable_nav_success_for_locked_smoke(tmp_path):
    args = loop.parse_args(["--no-require-nav-target-success"])
    closed_loop_args = loop.build_closed_loop_args(args, tmp_path / "closed_loop")

    assert closed_loop_args.execute_motion is False
    assert closed_loop_args.require_nav_target_success is False


def test_overnight_loop_requires_operator_confirmation_for_live_motion(tmp_path):
    unconfirmed = loop.parse_args(["--execute-motion"])

    assert "operator_ready_confirmation_required" in loop.validate_args(unconfirmed)

    confirmed_without_budgets = loop.parse_args(["--execute-motion", "--confirm-operator-ready"])

    assert "live_motion_operator_stop_file_required" in loop.validate_args(confirmed_without_budgets)
    assert "live_motion_motor_event_budget_required" in loop.validate_args(confirmed_without_budgets)
    assert "live_motion_motor_duration_budget_required" in loop.validate_args(confirmed_without_budgets)

    confirmed = loop.parse_args(
        [
            "--execute-motion",
            "--confirm-operator-ready",
            "--operator-stop-file",
            str(tmp_path / "STOP"),
            "--max-accepted-motor-events-per-cycle",
            "1",
            "--max-accepted-motor-duration-s-per-cycle",
            "0.30",
        ]
    )
    closed_loop_args = loop.build_closed_loop_args(confirmed, tmp_path / "closed_loop")

    assert loop.validate_args(confirmed) == []
    assert loop.live_motion_approved(confirmed) is True
    assert closed_loop_args.execute_motion is True
    assert closed_loop_args.confirm_operator_ready is True


def test_operator_stop_file_relocks_and_writes_terminal_rollup(tmp_path, monkeypatch):
    stop_file = tmp_path / "STOP"
    stop_file.write_text("stop\n", encoding="utf-8")
    client = FakeResetClient()
    monkeypatch.setattr(loop.bridge_client, "BridgeClient", lambda *_args, **_kwargs: client)
    args = loop.parse_args(["--artifact-dir", str(tmp_path / "run"), "--operator-stop-file", str(stop_file)])

    summary = loop.run(args)

    assert loop.operator_stop_requested(args) is True
    assert summary["pass"] is False
    assert summary["stop_reason"] == "operator_stop_requested"
    assert summary["completed_cycles"] == 0
    assert summary["final_health"]["response"]["motion_enabled"] is False
    assert any(call[0] == "stop" for call in client.calls)
    assert any(call[0] == "set_motion_enabled" and call[1] is False for call in client.calls)
    assert (tmp_path / "run" / "overnight_loop_summary.json").is_file()


def test_inverse_reset_rejects_motor_events_without_live_authorization(tmp_path):
    args = loop.parse_args([])
    client = FakeResetClient()
    events = [{"left": 0.2, "right": 0.1, "duration_s": 0.2, "source": "test"}]

    summary = loop.reverse_reset(client, events, args, tmp_path)

    assert summary["pass"] is False
    assert "inverse_reset_motion_not_authorized" in summary["issues"]
    assert not any(call[0] == "motors" for call in client.calls)
    assert not any(call[0] == "set_motion_enabled" and call[1] is True for call in client.calls)
    assert any(call[0] == "set_motion_enabled" and call[1] is False for call in client.calls)


def test_motor_event_budget_allows_unlimited_by_default():
    args = loop.parse_args([])
    events = [
        {"left": 0.1, "right": 0.1, "duration_s": 0.2},
        {"left": 0.1, "right": 0.1, "duration_s": 0.2},
    ]

    assert loop.accepted_motor_duration_s(events) == 0.4
    assert loop.motor_event_budget_issues(events, args) == []


def test_motor_event_budget_rejects_excess_count_and_duration():
    args = loop.parse_args(
        [
            "--max-accepted-motor-events-per-cycle",
            "1",
            "--max-accepted-motor-duration-s-per-cycle",
            "0.25",
        ]
    )
    events = [
        {"left": 0.1, "right": 0.1, "duration_s": 0.2},
        {"left": 0.1, "right": 0.1, "duration_s": 0.2},
    ]

    issues = loop.motor_event_budget_issues(events, args)

    assert "accepted_motor_event_count_exceeded:2>1" in issues
    assert "accepted_motor_duration_exceeded:0.400>0.250" in issues


def test_detector_evidence_summary_counts_backend_and_yolo_primary():
    summary = loop.detector_evidence_summary(
        {
            "steps": [
                {
                    "detector_backend": "yolo_onnx_or_color:color",
                    "detector_arbitration_selected": "color",
                    "yolo_onnx_primary_detected": False,
                },
                {
                    "detector_backend": "yolo_onnx_or_color:yolo_onnx",
                    "detector_arbitration_selected": "yolo_onnx",
                    "yolo_onnx_primary_detected": True,
                },
            ]
        }
    )

    assert summary["step_count"] == 2
    assert summary["detector_backend_counts"] == {
        "yolo_onnx_or_color:color": 1,
        "yolo_onnx_or_color:yolo_onnx": 1,
    }
    assert summary["detector_arbitration_selected_counts"] == {"color": 1, "yolo_onnx": 1}
    assert summary["yolo_onnx_primary_detected_steps"] == 1


def test_rollup_pass_requires_normal_stop_and_safe_final_health():
    rollup = {
        "cycles": [{"pass": True}],
        "issues": [],
        "stop_reason": "max_cycles_reached",
        "final_health": {
            "response": {
                "motion_enabled": False,
                "left_motor": 0.0,
                "right_motor": 0.0,
            }
        },
    }

    assert loop.rollup_passed(rollup)

    rollup["issues"] = ["final_health_failed:timeout"]
    assert not loop.rollup_passed(rollup)

    rollup["issues"] = []
    rollup["final_health"]["response"]["motion_enabled"] = True
    assert not loop.rollup_passed(rollup)

    rollup["final_health"]["response"]["motion_enabled"] = False
    rollup["stop_reason"] = "scan_reacquire_not_passed"
    assert not loop.rollup_passed(rollup)


def test_rollup_pass_rejects_failed_partial_cycle():
    rollup = {
        "cycles": [{"pass": True}, {"pass": False, "stop_reason": "scan_reacquire_not_passed"}],
        "issues": [],
        "stop_reason": "scan_reacquire_not_passed",
        "final_health": {
            "response": {
                "motion_enabled": False,
                "left_motor": 0.0,
                "right_motor": 0.0,
            }
        },
    }

    assert not loop.rollup_passed(rollup)


def test_unattended_scan_and_reset_defaults_are_low_energy():
    args = loop.parse_args([])

    assert abs(args.scan_left_motor) <= 0.20
    assert abs(args.scan_right_motor) <= 0.20
    assert args.scan_duration_s <= 0.18
    assert args.reset_max_motor_abs <= 0.25
    assert args.reset_max_duration_s <= 0.25
    assert args.relay_window_s >= 2.5


def test_rollup_passed_accepts_planned_success():
    rollup = {
        "cycles": [{"index": 1, "pass": True}],
        "issues": [],
        "stop_reason": "max_cycles_reached",
        "final_health": {
            "response": {
                "motion_enabled": False,
                "left_motor": 0.0,
                "right_motor": 0.0,
            }
        },
    }

    assert loop.rollup_passed(rollup)


def test_rollup_passed_rejects_final_health_failure():
    rollup = {
        "cycles": [{"index": 1, "pass": True}],
        "issues": ["final_health_failed:BridgeClientError('bridge_unreachable')"],
        "stop_reason": "max_cycles_reached",
        "final_health": {
            "response": {
                "motion_enabled": False,
                "left_motor": 0.0,
                "right_motor": 0.0,
            }
        },
    }

    assert not loop.rollup_passed(rollup)


def test_rollup_passed_rejects_failed_scan_cycle_after_successes():
    rollup = {
        "cycles": [
            {"index": 1, "pass": True},
            {"index": 2, "pass": True},
            {"index": 3, "pass": False, "stop_reason": "scan_reacquire_not_passed"},
        ],
        "issues": [],
        "stop_reason": "scan_reacquire_not_passed",
        "final_health": {
            "response": {
                "motion_enabled": False,
                "left_motor": 0.0,
                "right_motor": 0.0,
            }
        },
    }

    assert not loop.rollup_passed(rollup)
