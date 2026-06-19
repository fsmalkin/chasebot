from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_TOOLS_DIR = REPO_ROOT / "tools" / "robot_factory_bridge"
if str(BRIDGE_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_TOOLS_DIR))

import chasecar_bridge_stack_path_gate as gate  # noqa: E402


def make_blue_target_jpeg(path: Path, width=320, height=240, center_x=80):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (width, height), (35, 32, 30))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, height - 42, width, height), fill=(90, 75, 58))
    draw.rectangle((center_x - 32, 84, center_x + 32, 202), fill=(10, 120, 230))
    image.save(path, format="JPEG", quality=92)


class FakeSnapshotClient:
    def __init__(self, image_path: Path):
        self.image_bytes = image_path.read_bytes()

    def snapshot(self):
        return 200, self.image_bytes


def test_validate_args_rejects_zero_command():
    args = gate.parse_args(["--policy-entrypoint", gate.POLICY_FIXED_COMMAND_V0, "--command-linear-x", "0", "--command-angular-z", "0"])

    assert "nonzero_command_required" in gate.validate_args(args)


def test_validate_args_requires_motion_confirmation_for_live_mode():
    args = gate.parse_args(["--execute-motion"])

    assert "operator_ready_confirmation_required" in gate.validate_args(args)


def test_validate_args_accepts_conservative_turn_only_command():
    args = gate.parse_args(["--policy-entrypoint", gate.POLICY_FIXED_COMMAND_V0, "--command-linear-x", "0", "--command-angular-z", "0.2"])

    assert gate.validate_args(args) == []


def test_visual_target_turn_policy_emits_bounded_turn(tmp_path):
    image_path = tmp_path / "blue_target.jpg"
    make_blue_target_jpeg(image_path)
    args = gate.parse_args(["--policy-entrypoint", gate.POLICY_JETBOT_VISUAL_TARGET_TURN_V0])
    decision = gate.run_policy_entrypoint(FakeSnapshotClient(image_path), args, tmp_path / "policy")

    assert decision["pass"] is True
    assert decision["entrypoint"] == gate.POLICY_JETBOT_VISUAL_TARGET_TURN_V0
    assert decision["observation"]["detected"] is True
    assert decision["command"]["linear_x"] == 0.0
    assert decision["command"]["angular_z"] > 0.0
    assert Path(decision["observation"]["annotated_image_path"]).exists()


def test_compute_pass_requires_locked_refusal_and_final_camera():
    summary = {
        "issues": [],
        "camera_readiness_gate": {"pass": True},
        "command": {"linear_x": 0.0, "angular_z": 0.2},
        "policy_decision": {"pass": True},
        "relay_summary": {
            "relay": {
                "counters": {
                    "messages_received": 5,
                    "cmd_vel_posts": 4,
                    "http_refusals": 4,
                    "dry_run_actions": 0,
                }
            }
        },
        "final_locked_health": {
            "response": {
                "motion_enabled": False,
                "left_motor": 0.0,
                "right_motor": 0.0,
            }
        },
        "final_camera_readiness_gate": {"pass": True},
    }

    assert gate.compute_pass(summary) is True
    summary["relay_summary"]["relay"]["counters"]["http_refusals"] = 0
    assert gate.compute_pass(summary) is False


def test_relay_nonzero_success_events_requires_motor_response():
    summary = {
        "relay": {
            "events": [
                {
                    "http_status": 200,
                    "payload": {"linear_x": 0.0, "angular_z": 0.8},
                    "response": {"last_command": {"left": -0.1, "right": 0.1}},
                },
                {
                    "http_status": 423,
                    "payload": {"linear_x": 0.0, "angular_z": 0.8},
                    "response": {},
                },
            ]
        }
    }

    assert len(gate.relay_nonzero_success_events(summary)) == 1
