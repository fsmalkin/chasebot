from __future__ import annotations

import io
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_TOOLS_DIR = REPO_ROOT / "tools" / "robot_factory_bridge"
if str(BRIDGE_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_TOOLS_DIR))

import chasecar_bridge_color_target_smoke as smoke  # noqa: E402


def make_blue_bottle_jpeg(width=320, height=240, center_x=150):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (width, height), (35, 32, 30))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, height - 42, width, height), fill=(90, 75, 58))
    draw.rectangle((center_x - 14, 90, center_x + 14, 172), fill=(20, 88, 210))
    draw.rectangle((center_x - 9, 104, center_x + 9, 158), fill=(35, 115, 245))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


class FakeSnapshotClient:
    def __init__(self, image_bytes):
        self.image_bytes = image_bytes

    def snapshot(self):
        return 200, self.image_bytes


class FakeHealthClient:
    def __init__(self, health):
        self.health_payload = health

    def health(self):
        return 200, self.health_payload


def test_blue_profile_defaults_are_conservative_and_forward_enabled():
    args = smoke.parse_args(["--target-profile", "blue", "--visual-turn-sign", "-1"])
    behavior_args = smoke.build_behavior_args(args)

    assert behavior_args.target_profile == "blue"
    assert behavior_args.target_min_saturation == 0.25
    assert behavior_args.target_min_value == 0.20
    assert behavior_args.target_max_bbox_width_ratio == 0.85
    assert behavior_args.max_visual_linear_x == 0.08
    assert behavior_args.allow_forward is True
    assert behavior_args.visual_turn_sign == -1.0


def test_camera_loop_writes_runtime_commands_and_contact_sheet(tmp_path):
    args = smoke.parse_args(
        [
            "--target-profile",
            "blue",
            "--artifact-dir",
            str(tmp_path),
            "--loop-frames",
            "2",
            "--loop-interval-s",
            "0",
        ]
    )
    behavior_args = smoke.build_behavior_args(args)
    runtime_path = tmp_path / "runtime.json"

    summary = smoke.run_camera_loop(
        client=FakeSnapshotClient(make_blue_bottle_jpeg()),
        args=args,
        behavior_args=behavior_args,
        artifact_dir=tmp_path,
        runtime_path=runtime_path,
        mode="test_blue_loop",
        source="test:blue_loop",
    )

    assert smoke.phase_records_detected(summary) is True
    assert len(summary["records"]) == 2
    assert summary["records"][0]["command"]["linear_x"] == 0.08
    assert summary["records"][0]["command"]["angular_z"] > 0.0
    assert Path(summary["contact_sheet"]).exists()
    final_runtime = smoke.load_json(runtime_path)
    assert final_runtime["manual_drive"]["enabled"] is False
    assert final_runtime["manual_drive"]["command"] == {"angular_z": 0.0, "linear_x": 0.0}


def test_relay_bash_waits_for_summary_before_proof_window(tmp_path):
    args = smoke.parse_args(["--relay-start-timeout-s", "1.0", "--relay-window-s", "1.25"])

    script = smoke.relay_bash(args, tmp_path / "relay", tmp_path / "runtime.json", require_motion_enabled=False)

    assert "stop_child()" in script
    assert 'if [ -s "$ART/relay_summary.json" ]; then' in script
    assert "for _ in $(seq 1 2); do" in script
    assert "sleep 1.25" in script
    assert 'kill -TERM "$child_pid"' in script
    assert 'kill -KILL "$child_pid"' in script


def test_unconfirmed_motion_is_refused_before_hardware_steps():
    args = smoke.parse_args(["--execute-motion"])

    assert "operator_ready_confirmation_required" in smoke.validate_safety_args(args)


def test_strong_turn_proof_requires_explicit_no_forward_guardrails():
    unsafe_args = smoke.parse_args(
        [
            "--execute-motion",
            "--confirm-operator-ready",
            "--allow-strong-turn-proof",
            "--max-bridge-angular-z",
            "1.8",
        ]
    )

    assert "strong_turn_proof_requires_no_forward" in smoke.validate_safety_args(unsafe_args)

    guarded_args = smoke.parse_args(
        [
            "--execute-motion",
            "--confirm-operator-ready",
            "--allow-strong-turn-proof",
            "--no-allow-forward",
            "--visual-forward-x",
            "0",
            "--max-visual-linear-x",
            "0",
            "--max-bridge-linear-x",
            "0",
            "--max-bridge-angular-z",
            "1.8",
            "--relay-window-s",
            "4.0",
            "--command-duration-s",
            "0.16",
        ]
    )

    assert smoke.validate_safety_args(guarded_args) == []


def test_camera_readiness_gate_fails_fast_on_unloaded_camera():
    args = smoke.parse_args(["--camera-ready-timeout-s", "0"])
    client = FakeHealthClient(
        {
            "ok": True,
            "camera": {
                "enabled": True,
                "loaded": False,
                "cached_fps": 0.0,
                "cached_bytes": 0,
                "frame_age_s": None,
                "error": "RuntimeError('Could not initialize camera.')",
            },
        }
    )

    summary = smoke.camera_readiness_summary(client, args, "test")

    assert summary["pass"] is False
    assert "camera_not_loaded" in summary["issues"]
    assert "camera_frame_too_small" in summary["issues"]
    assert any(issue.startswith("camera_error:") for issue in summary["issues"])


def test_detection_gate_allows_one_warmup_miss_when_final_frame_detects():
    summary = {
        "records": [
            {"detected": False},
            {"detected": True},
            {"detected": True},
            {"detected": True},
        ]
    }

    detection_summary = smoke.phase_detection_summary(summary)

    assert detection_summary["detected_frames"] == 3
    assert detection_summary["required_detected_frames"] == 3
    assert detection_summary["final_frame_detected"] is True
    assert smoke.phase_records_detected(summary) is True


def test_compute_pass_requires_locked_and_motion_evidence():
    summary = {
        "issues": [],
        "execute_motion": True,
        "locked_relay_proof": {
            "records": [{"detected": True}],
            "relay_counters": {"messages_received": 4, "http_refusals": 2},
        },
        "motion_proof": {
            "records": [
                {"detected": True, "center_error": -0.10},
                {"detected": True, "center_error": 0.04},
            ],
            "center_error_summary": {
                "available": True,
                "max_abs_center_error": 0.10,
                "start_abs_center_error": 0.10,
                "end_abs_center_error": 0.04,
                "improved_or_controlled": True,
            },
            "relay_counters": {"cmd_vel_posts": 3, "http_errors": 0},
            "nonzero_event_count": 2,
        },
        "visual_motion": {"movement_detected": True},
        "final_locked_health": {
            "response": {
                "motion_enabled": False,
                "left_motor": 0.0,
                "right_motor": 0.0,
            }
        },
    }

    assert smoke.compute_pass(summary) is True
    summary["motion_proof"]["center_error_summary"]["improved_or_controlled"] = False
    assert smoke.compute_pass(summary) is False
