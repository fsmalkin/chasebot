from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_TOOLS_DIR = REPO_ROOT / "tools" / "robot_factory_bridge"
if str(BRIDGE_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_TOOLS_DIR))

import chasecar_bridge_stack_path_gate as gate  # noqa: E402


def test_validate_args_rejects_zero_command():
    args = gate.parse_args(["--command-linear-x", "0", "--command-angular-z", "0"])

    assert "nonzero_command_required" in gate.validate_args(args)


def test_validate_args_requires_motion_confirmation_for_live_mode():
    args = gate.parse_args(["--execute-motion"])

    assert "operator_ready_confirmation_required" in gate.validate_args(args)


def test_validate_args_accepts_conservative_turn_only_command():
    args = gate.parse_args(["--command-linear-x", "0", "--command-angular-z", "0.2"])

    assert gate.validate_args(args) == []


def test_compute_pass_requires_locked_refusal_and_final_camera():
    summary = {
        "issues": [],
        "camera_readiness_gate": {"pass": True},
        "command": {"linear_x": 0.0, "angular_z": 0.2},
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
