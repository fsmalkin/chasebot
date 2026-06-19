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


def make_no_target_jpeg(path: Path, width=320, height=240):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (width, height), (42, 40, 36))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, height - 42, width, height), fill=(92, 78, 62))
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


def test_default_policy_is_chasecar_stack_adapter():
    args = gate.parse_args([])

    assert args.policy_entrypoint == gate.POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0


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


def test_chasecar_stack_adapter_turns_to_acquire_off_center_target(tmp_path):
    image_path = tmp_path / "blue_target.jpg"
    make_blue_target_jpeg(image_path, center_x=80)
    args = gate.parse_args(["--policy-entrypoint", gate.POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0])
    decision = gate.run_policy_entrypoint(FakeSnapshotClient(image_path), args, tmp_path / "policy")

    assert decision["pass"] is True
    assert decision["entrypoint"] == gate.POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0
    assert decision["stack_policy"]["preferred_intent"] == "acquire_target"
    assert decision["command"]["linear_x"] == 0.0
    assert decision["command"]["angular_z"] > 0.0
    assert decision["stack_lineage"]["stack_family"] == "planner_routed_fetch_to_pose"
    assert Path(decision["observation"]["annotated_image_path"]).exists()


def test_chasecar_stack_adapter_emits_forward_fetch_approach_when_centered(tmp_path):
    image_path = tmp_path / "blue_target.jpg"
    make_blue_target_jpeg(image_path, center_x=160)
    args = gate.parse_args(["--policy-entrypoint", gate.POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0])
    decision = gate.run_policy_entrypoint(FakeSnapshotClient(image_path), args, tmp_path / "policy")

    assert decision["pass"] is True
    assert decision["stack_policy"]["preferred_intent"] == "plan_to_target"
    assert decision["stop_reason"] == "fetch_to_pose_approach_command"
    assert decision["observation"]["centered"] is True
    assert decision["command"]["linear_x"] > 0.0
    assert abs(decision["command"]["angular_z"]) < 0.02
    assert decision["stack_lineage"]["learned_low_level_fetch_policy_loaded"] is False


def test_chasecar_stack_adapter_searches_when_target_missing(tmp_path):
    image_path = tmp_path / "no_target.jpg"
    make_no_target_jpeg(image_path)
    args = gate.parse_args(["--policy-entrypoint", gate.POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0, "--stack-search-angular-z", "0.16"])

    decision = gate.run_policy_entrypoint(FakeSnapshotClient(image_path), args, tmp_path / "policy")

    assert decision["pass"] is True
    assert decision["stack_policy"]["preferred_intent"] == "search_for_target"
    assert decision["stop_reason"] == "search_for_target_turn_command"
    assert decision["observation"]["detected"] is False
    assert decision["command"]["linear_x"] == 0.0
    assert decision["command"]["angular_z"] == 0.16


def test_stack_plan_to_target_zeroes_angular_when_target_centered():
    args = gate.parse_args(["--stack-forward-x", "0.035", "--max-stack-linear-x", "0.05"])
    analysis = {
        "detected": True,
        "centered": True,
        "area_ratio": 0.08,
        "recommendation": {"linear_x": 0.0, "angular_z": 0.4},
    }
    policy = {"stage": "plan", "preferred_intent": "plan_to_target"}

    command, issues, stop_reason = gate.stack_command_from_policy(analysis, policy, args)

    assert issues == []
    assert stop_reason == "fetch_to_pose_approach_command"
    assert command["linear_x"] == 0.035
    assert command["angular_z"] == 0.0


def test_stack_search_for_target_emits_bounded_turn_when_target_missing():
    args = gate.parse_args(["--stack-search-angular-z", "0.16", "--max-policy-angular-z", "0.3"])
    analysis = {
        "detected": False,
        "centered": False,
        "area_ratio": 0.0,
        "recommendation": {"linear_x": 0.0, "angular_z": 0.0},
    }
    policy = {"stage": "search", "preferred_intent": "search_for_target"}

    command, issues, stop_reason = gate.stack_command_from_policy(analysis, policy, args)

    assert issues == []
    assert stop_reason == "search_for_target_turn_command"
    assert command["linear_x"] == 0.0
    assert command["angular_z"] == 0.16


def test_stack_acquire_turn_sign_can_be_reversed_for_hardware():
    args = gate.parse_args(["--stack-acquire-turn-sign", "-1", "--visual-angular-gain", "4.0"])
    analysis = {
        "detected": True,
        "centered": False,
        "center_error": -0.20,
        "area_ratio": 0.08,
        "recommendation": {"linear_x": 0.0, "angular_z": 0.4},
    }
    policy = {"stage": "acquire", "preferred_intent": "acquire_target"}

    command, issues, stop_reason = gate.stack_command_from_policy(analysis, policy, args)

    assert issues == []
    assert stop_reason == "acquire_target_turn_command"
    assert command["linear_x"] == 0.0
    assert command["angular_z"] < 0.0


def test_stack_acquire_turn_uses_separate_angular_cap():
    args = gate.parse_args(["--stack-acquire-max-angular-z", "0.12", "--visual-angular-gain", "4.0"])
    analysis = {
        "detected": True,
        "centered": False,
        "center_error": 0.80,
        "area_ratio": 0.08,
        "recommendation": {"linear_x": 0.0, "angular_z": -0.4},
    }
    policy = {"stage": "acquire", "preferred_intent": "acquire_target"}

    command, issues, stop_reason = gate.stack_command_from_policy(analysis, policy, args)

    assert issues == []
    assert stop_reason == "acquire_target_turn_command"
    assert command["angular_z"] == -0.12


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


def test_deploy_bridge_uses_relay_linear_and_angular_caps(tmp_path, monkeypatch):
    captured = {}

    class Result:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return Result()

    monkeypatch.setattr(gate.subprocess, "run", fake_run)
    args = gate.parse_args(["--max-bridge-linear-x", "0.14", "--max-bridge-angular-z", "0.8"])

    payload = gate.deploy_bridge(args, tmp_path, enable_motion=True)

    assert payload["returncode"] == 0
    command = captured["command"]
    assert command[command.index("-MaxLinearX") + 1] == "0.14"
    assert command[command.index("-MaxAngularZ") + 1] == "0.8"
    assert command[command.index("-MaxMotorSpeed") + 1] == str(args.max_motor_speed)
