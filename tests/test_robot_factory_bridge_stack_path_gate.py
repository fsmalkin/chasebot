from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_TOOLS_DIR = REPO_ROOT / "tools" / "robot_factory_bridge"
if str(BRIDGE_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_TOOLS_DIR))
sys.modules.setdefault("onnxruntime", SimpleNamespace(__version__="test-stub"))

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


def test_yolo_selector_prefers_confidence_over_large_low_confidence_box():
    detections = [
        {"confidence": 0.06, "area_ratio": 0.17, "bbox_xyxy": [9.0, 15.0, 217.0, 266.0]},
        {"confidence": 0.38, "area_ratio": 0.088, "bbox_xyxy": [213.0, 62.0, 300.0, 370.0]},
    ]

    best = gate.yolo_probe.select_best_detection(detections, min_area_ratio=0.04)

    assert best is detections[1]


def test_yolo_cascade_uses_fallback_when_primary_has_no_candidate(tmp_path, monkeypatch):
    from PIL import Image

    image_path = tmp_path / "target.jpg"
    make_blue_target_jpeg(image_path, center_x=160)
    primary_model = tmp_path / "primary.onnx"
    fallback_model = tmp_path / "fallback.onnx"
    primary_model.write_bytes(b"primary")
    fallback_model.write_bytes(b"fallback")
    calls = []

    def fake_run_yolo(_image, _args, *, model_path, confidence_threshold, role):
        calls.append(role)
        if role == "primary":
            return {
                "role": role,
                "model": str(model_path),
                "confidence_threshold": confidence_threshold,
                "detections": [],
                "candidates": [],
                "candidate_count": 0,
                "detection_count": 0,
                "best_detection": None,
                "issues": [],
            }
        detection = {
            "class_id": 39,
            "class_name": "bottle",
            "confidence": 0.045,
            "bbox_xyxy": [150.0, 82.0, 174.0, 150.0],
            "center_x_px": 162.0,
            "center_y_px": 116.0,
            "area_ratio": 0.02125,
            "center_error": 0.0125,
        }
        return {
            "role": role,
            "model": str(model_path),
            "confidence_threshold": confidence_threshold,
            "detections": [detection],
            "candidates": [detection],
            "candidate_count": 1,
            "detection_count": 1,
            "best_detection": detection,
            "issues": [],
        }

    monkeypatch.setattr(gate.yolo_probe, "load_detector_dependencies", lambda require_onnx=True: "")
    monkeypatch.setattr(gate.yolo_probe, "Image", Image)
    monkeypatch.setattr(gate.yolo_probe, "ort", object())
    monkeypatch.setattr(gate.yolo_probe, "annotate", lambda image, detections, path: path.write_bytes(b"annotated"))
    monkeypatch.setattr(gate, "run_yolo_onnx_model", fake_run_yolo)
    args = gate.parse_args(
        [
            "--detector-backend",
            "yolo_onnx",
            "--yolo-onnx-model",
            str(primary_model),
            "--yolo-onnx-fallback-model",
            str(fallback_model),
            "--yolo-onnx-confidence-threshold",
            "0.10",
            "--yolo-onnx-fallback-confidence-threshold",
            "0.03",
            "--yolo-target-min-area-ratio",
            "0.005",
        ]
    )

    analysis = gate.analyze_yolo_onnx_policy_image(
        image_path,
        args,
        annotated_path=tmp_path / "annotated.jpg",
        allow_forward=False,
    )

    assert calls == ["primary", "fallback"]
    assert analysis["detected"] is True
    assert analysis["yolo_onnx_model_role"] == "fallback"
    assert analysis["yolo_onnx_model"] == str(fallback_model)
    assert analysis["confidence"] == 0.045
    assert analysis["yolo_onnx_attempts"][0]["candidate_count"] == 0
    assert analysis["yolo_onnx_attempts"][1]["candidate_count"] == 1


def test_save_snapshot_ssh_fetches_robot_local_camera(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        if cmd[0] == "ssh" and "curl" in cmd[-1]:
            return SimpleNamespace(returncode=0, stdout="200 1234", stderr="")
        if cmd[0] == "scp":
            Path(cmd[-1]).write_bytes(b"jpeg-bytes")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if cmd[0] == "ssh" and "rm -f" in cmd[-1]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError("unexpected command: %r" % (cmd,))

    monkeypatch.setattr(gate.subprocess, "run", fake_run)
    args = gate.parse_args(
        [
            "--camera-fetch-mode",
            "ssh",
            "--robot-host",
            "192.168.1.11",
            "--robot-user",
            "jetson",
            "--camera-fetch-timeout-s",
            "3",
        ]
    )
    output = tmp_path / "camera.jpg"
    unused_source = tmp_path / "unused_source.jpg"
    unused_source.write_bytes(b"unused")

    snapshot = gate.save_snapshot(FakeSnapshotClient(unused_source), output, args)

    assert snapshot["camera_fetch_mode_selected"] == "ssh"
    assert snapshot["source"] == "ssh_local_bridge_camera"
    assert snapshot["http_status"] == 200
    assert snapshot["bytes"] == len(b"jpeg-bytes")
    assert "curl" in calls[0][-1]
    assert calls[1][0] == "scp"
    assert "jetson@192.168.1.11:" in calls[1][-2]


def test_yolo_or_color_prefers_larger_blue_target_over_small_yolo_hit(tmp_path, monkeypatch):
    image_path = tmp_path / "blue_target.jpg"
    make_blue_target_jpeg(image_path, center_x=160)

    def fake_yolo(_image_path, _args, *, annotated_path, allow_forward):
        annotated_path.write_bytes(image_path.read_bytes())
        return {
            "detected": True,
            "issues": [],
            "annotated_image_path": str(annotated_path),
            "detector_backend": "yolo_onnx",
            "area_ratio": 0.01,
            "center_error": -0.7,
            "detections": [
                {
                    "confidence": 0.27,
                    "area_ratio": 0.01,
                    "bbox_xyxy": [20.0, 100.0, 45.0, 130.0],
                }
            ],
            "recommendation": {
                "linear_x": 0.0,
                "angular_z": 0.24,
                "duration_s": 0.2,
                "source": "factory_behavior_runner:yolo_onnx_advisor",
            },
        }

    monkeypatch.setattr(gate, "analyze_yolo_onnx_policy_image", fake_yolo)
    args = gate.parse_args(
        [
            "--detector-backend",
            "yolo_onnx_or_color",
            "--target-min-area-ratio",
            "0.01",
            "--yolo-color-override-area-multiplier",
            "1.35",
        ]
    )

    analysis = gate.analyze_policy_image(
        image_path,
        args,
        gate.build_stack_fetch_policy_args(args),
        annotated_path=tmp_path / "policy_observation_annotated.jpg",
        allow_forward=True,
    )

    assert analysis["detector_backend"] == "yolo_onnx_or_color:color"
    assert analysis["detected"] is True
    assert analysis["yolo_onnx_primary_detected"] is True
    assert analysis["detector_arbitration"]["selected"] == "color"
    assert analysis["area_ratio"] > analysis["yolo_onnx_primary_area_ratio"]


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


def test_yolo_or_color_policy_points_to_selected_color_annotation(tmp_path, monkeypatch):
    image_path = tmp_path / "blue_target.jpg"
    make_blue_target_jpeg(image_path, center_x=160)

    def fake_yolo(_image_path, _args, *, annotated_path, allow_forward):
        annotated_path.write_bytes(image_path.read_bytes())
        return {
            "detected": False,
            "issues": ["target_not_detected"],
            "annotated_image_path": str(annotated_path),
            "detector_backend": "yolo_onnx",
            "area_ratio": 0.0,
            "center_error": None,
            "detections": [],
            "recommendation": {
                "linear_x": 0.0,
                "angular_z": 0.0,
                "duration_s": 0.2,
                "source": "factory_behavior_runner:yolo_onnx_advisor",
            },
        }

    monkeypatch.setattr(gate, "analyze_yolo_onnx_policy_image", fake_yolo)
    args = gate.parse_args(
        [
            "--policy-entrypoint",
            gate.POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0,
            "--detector-backend",
            "yolo_onnx_or_color",
            "--target-min-area-ratio",
            "0.01",
        ]
    )

    decision = gate.run_policy_entrypoint(FakeSnapshotClient(image_path), args, tmp_path / "policy")
    annotated_path = Path(decision["observation"]["annotated_image_path"])

    assert decision["pass"] is True
    assert decision["analysis"]["detector_backend"] == "yolo_onnx_or_color:color"
    assert annotated_path.name == "policy_observation_annotated_color.jpg"
    assert annotated_path.exists()


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


def test_stack_plan_to_target_returns_safe_terminal_stop_when_target_close():
    args = gate.parse_args(["--stack-forward-stop-area-ratio", "0.09"])
    analysis = {
        "detected": True,
        "centered": True,
        "area_ratio": 0.094,
        "recommendation": {"linear_x": 0.025, "angular_z": -0.3},
    }
    policy = {"stage": "plan", "preferred_intent": "plan_to_target"}

    command, issues, stop_reason = gate.stack_command_from_policy(analysis, policy, args)

    assert issues == []
    assert stop_reason == "target_inside_stack_forward_stop_area"
    assert command == {"linear_x": 0.0, "angular_z": 0.0}
    assert gate.safe_terminal_zero_stop(stop_reason, command) is True


def test_stack_plan_to_target_returns_safe_terminal_stop_when_target_bbox_close():
    args = gate.parse_args(
        [
            "--stack-forward-stop-area-ratio",
            "0.50",
            "--stack-forward-stop-bbox-height-ratio",
            "0.35",
        ]
    )
    analysis = {
        "detected": True,
        "centered": True,
        "area_ratio": 0.02,
        "bbox_height_ratio": 0.36,
        "recommendation": {"linear_x": 0.025, "angular_z": -0.3},
    }
    policy = {"stage": "plan", "preferred_intent": "plan_to_target"}

    command, issues, stop_reason = gate.stack_command_from_policy(analysis, policy, args)

    assert issues == []
    assert stop_reason == "target_inside_stack_forward_stop_bbox_height"
    assert command == {"linear_x": 0.0, "angular_z": 0.0}
    assert gate.safe_terminal_zero_stop(stop_reason, command) is True


def test_chasecar_stack_adapter_passes_safe_terminal_stop_when_target_close(tmp_path):
    image_path = tmp_path / "blue_target.jpg"
    make_blue_target_jpeg(image_path, center_x=160)
    args = gate.parse_args(
        [
            "--policy-entrypoint",
            gate.POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0,
            "--stack-forward-stop-area-ratio",
            "0.09",
        ]
    )

    decision = gate.run_policy_entrypoint(FakeSnapshotClient(image_path), args, tmp_path / "policy")

    assert decision["pass"] is True
    assert decision["safe_terminal_stop"] is True
    assert decision["issues"] == []
    assert decision["stop_reason"] == "target_inside_stack_forward_stop_area"
    assert decision["command"] == {"linear_x": 0.0, "angular_z": 0.0}


def test_compute_pass_accepts_safe_terminal_stop_without_relay():
    summary = {
        "issues": [],
        "camera_readiness_gate": {"pass": True},
        "command": {"linear_x": 0.0, "angular_z": 0.0},
        "policy_decision": {
            "pass": True,
            "stop_reason": "target_inside_stack_forward_stop_area",
            "command": {"linear_x": 0.0, "angular_z": 0.0},
        },
        "safe_terminal_stop": True,
        "final_locked_health": {"response": {"motion_enabled": False, "left_motor": 0.0, "right_motor": 0.0}},
        "final_camera_readiness_gate": {"pass": True},
    }

    assert gate.compute_pass(summary) is True


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


def test_stack_search_turn_sign_can_be_reversed_for_hardware():
    args = gate.parse_args(["--visual-turn-sign", "-1", "--stack-search-angular-z", "0.16"])
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
    assert command["angular_z"] == -0.16


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


def test_stack_acquire_turn_uses_min_angular_floor():
    args = gate.parse_args(
        [
            "--stack-acquire-min-angular-z",
            "0.18",
            "--stack-acquire-max-angular-z",
            "0.4",
            "--visual-angular-gain",
            "0.75",
        ]
    )
    analysis = {
        "detected": True,
        "centered": False,
        "center_error": -0.185,
        "area_ratio": 0.08,
        "recommendation": {"linear_x": 0.0, "angular_z": 0.14},
    }
    policy = {"stage": "acquire", "preferred_intent": "acquire_target"}

    command, issues, stop_reason = gate.stack_command_from_policy(analysis, policy, args)

    assert issues == []
    assert stop_reason == "acquire_target_turn_command"
    assert command["linear_x"] == 0.0
    assert command["angular_z"] == 0.18


def test_stack_acquire_turn_floor_respects_separate_angular_cap():
    args = gate.parse_args(
        [
            "--stack-acquire-min-angular-z",
            "0.18",
            "--stack-acquire-max-angular-z",
            "0.12",
            "--visual-angular-gain",
            "0.75",
        ]
    )
    analysis = {
        "detected": True,
        "centered": False,
        "center_error": 0.10,
        "area_ratio": 0.08,
        "recommendation": {"linear_x": 0.0, "angular_z": -0.075},
    }
    policy = {"stage": "acquire", "preferred_intent": "acquire_target"}

    command, issues, stop_reason = gate.stack_command_from_policy(analysis, policy, args)

    assert issues == []
    assert stop_reason == "acquire_target_turn_command"
    assert command["angular_z"] == -0.12


def test_live_motion_turn_only_guard_accepts_turn_command():
    args = gate.parse_args(["--execute-motion", "--confirm-operator-ready", "--live-motion-require-turn-only"])

    assert gate.live_motion_command_issues({"linear_x": 0.0, "angular_z": 0.18}, args) == []


def test_live_motion_turn_only_guard_blocks_forward_command():
    args = gate.parse_args(["--execute-motion", "--confirm-operator-ready", "--live-motion-require-turn-only"])

    assert gate.live_motion_command_issues({"linear_x": 0.025, "angular_z": 0.0}, args) == [
        "live_stack_motion_requires_turn_only"
    ]


def test_live_motion_turn_only_guard_skips_motion_phase_for_forward_command(tmp_path, monkeypatch):
    class FakeBridgeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def health(self):
            return 200, {"ok": True, "motion_enabled": False, "left_motor": 0.0, "right_motor": 0.0}

    def fake_camera_readiness(*_args, **_kwargs):
        return {"pass": True, "issues": []}

    def fake_policy(*_args, **_kwargs):
        return {
            "pass": True,
            "command": {"linear_x": 0.025, "angular_z": 0.0},
            "stop_reason": "fetch_to_pose_approach_command",
        }

    def fake_relay(*_args, **_kwargs):
        return {
            "relay": {
                "counters": {
                    "messages_received": 4,
                    "cmd_vel_posts": 4,
                    "http_refusals": 4,
                    "dry_run_actions": 0,
                }
            }
        }

    def fail_motion(*_args, **_kwargs):
        raise AssertionError("run_motion_phase must not run after turn-only guard fails")

    monkeypatch.setattr(gate.bridge_client, "BridgeClient", FakeBridgeClient)
    monkeypatch.setattr(gate, "set_bridge_motion_state", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(gate, "camera_readiness_summary", fake_camera_readiness)
    monkeypatch.setattr(gate, "run_policy_entrypoint", fake_policy)
    monkeypatch.setattr(gate, "run_relay_phase", fake_relay)
    monkeypatch.setattr(gate, "run_motion_phase", fail_motion)
    args = gate.parse_args(
        [
            "--artifact-dir",
            str(tmp_path),
            "--camera-warmup-s",
            "0",
            "--execute-motion",
            "--confirm-operator-ready",
            "--live-motion-require-turn-only",
        ]
    )

    summary = gate.run(args)

    assert summary["locked_transport_pass"] is True
    assert summary["live_motion_command_issues"] == ["live_stack_motion_requires_turn_only"]
    assert "live_stack_motion_requires_turn_only" in summary["issues"]
    assert "motion_proof" not in summary
    assert summary["pass"] is False


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


def test_compute_pass_rejects_locked_transport_motor_acceptance():
    summary = {
        "issues": [],
        "camera_readiness_gate": {"pass": True},
        "command": {"linear_x": 0.0, "angular_z": 0.2},
        "policy_decision": {"pass": True},
        "relay_summary": {
            "relay": {
                "counters": {
                    "messages_received": 5,
                    "cmd_vel_posts": 2,
                    "http_refusals": 3,
                    "dry_run_actions": 0,
                },
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
                ],
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


def test_run_relay_phase_accepts_summary_created_on_shutdown(tmp_path, monkeypatch):
    artifact_dir = tmp_path / "relay"
    expected = {
        "relay": {
            "counters": {"cmd_vel_posts": 1, "http_refusals": 0},
            "events": [{"http_status": 423, "payload": {"raw": {"linear_x": 0.025, "angular_z": 0.0}}}],
        }
    }

    class FakeProcess:
        returncode = None

        def wait(self, timeout=None):
            gate.write_json(artifact_dir / "relay_summary.json", expected)
            self.returncode = 0
            return 0

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = 0

        def kill(self):
            self.returncode = -9

    def fake_popen(*_args, **_kwargs):
        return FakeProcess()

    monkeypatch.setattr(gate.subprocess, "Popen", fake_popen)
    args = gate.parse_args(["--relay-start-timeout-s", "0.2", "--relay-finish-timeout-s", "0.2"])

    summary = gate.run_relay_phase(args, artifact_dir, tmp_path / "runtime.json")

    assert summary == expected


def test_run_relay_phase_fails_closed_when_shutdown_summary_missing(tmp_path, monkeypatch):
    class FakeProcess:
        returncode = None

        def wait(self, timeout=None):
            self.returncode = 0
            return 0

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = 0

        def kill(self):
            self.returncode = -9

    monkeypatch.setattr(gate.subprocess, "Popen", lambda *_args, **_kwargs: FakeProcess())
    args = gate.parse_args(["--relay-start-timeout-s", "0.2", "--relay-finish-timeout-s", "0.2"])

    try:
        gate.run_relay_phase(args, tmp_path / "relay", tmp_path / "runtime.json")
    except RuntimeError as exc:
        assert "relay_summary_not_created" in str(exc)
    else:
        raise AssertionError("expected missing relay summary to fail closed")


def test_relay_bash_waits_for_summary_before_proof_window(tmp_path):
    args = gate.parse_args(
        [
            "--relay-start-timeout-s",
            "1.0",
            "--relay-window-s",
            "1.25",
        ]
    )

    script = gate.relay_bash(args, tmp_path / "relay", tmp_path / "runtime.json", require_motion_enabled=False)

    assert "stop_child()" in script
    assert 'if [ -s "$ART/relay_summary.json" ]; then' in script
    assert "for _ in $(seq 1 2); do" in script
    assert "sleep 1.25" in script
    assert 'kill -TERM "$child_pid"' in script
    assert 'kill -KILL "$child_pid"' in script


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


def test_set_bridge_motion_state_uses_http_control(tmp_path):
    calls = []

    class FakeClient:
        def set_motion_enabled(self, enabled, source):
            calls.append((enabled, source))
            return 200, {"ok": True, "motion_enabled": enabled, "left_motor": 0.0, "right_motor": 0.0}

    args = gate.parse_args(["--motion-control-mode", "auto"])

    payload = gate.set_bridge_motion_state(FakeClient(), args, tmp_path, enable_motion=False, phase="unit_lock")

    assert payload["pass"] is True
    assert payload["mode"] == "http"
    assert calls == [(False, "chasecar_bridge_stack_path_gate:unit_lock")]
    assert (tmp_path / "motion_control.json").exists()


def test_set_bridge_motion_state_falls_back_to_deploy_for_old_bridge(tmp_path, monkeypatch):
    calls = []

    class FakeClient:
        def set_motion_enabled(self, *_args, **_kwargs):
            raise gate.bridge_client.BridgeHttpError(404, {"ok": False, "error": "not_found"}, b"")

    def fake_deploy(_args, artifact_dir, *, enable_motion):
        calls.append((Path(artifact_dir), enable_motion))
        return {"skipped": False, "enable_motion": enable_motion, "fallback": True}

    monkeypatch.setattr(gate, "deploy_bridge", fake_deploy)
    args = gate.parse_args(["--motion-control-mode", "auto"])

    payload = gate.set_bridge_motion_state(FakeClient(), args, tmp_path, enable_motion=True, phase="unit_enable")

    assert payload["fallback"] is True
    assert calls == [(tmp_path, True)]
    saved = gate.load_json(tmp_path / "motion_control.json")
    assert saved["http_status"] == 404
    assert saved["pass"] is False


def test_deploy_bridge_fails_on_motion_state_mismatch(tmp_path, monkeypatch):
    class Result:
        returncode = 0
        stdout = """
[start] jetson@192.168.1.11:8765 motion_enabled=True camera=True
{
  "ok": true,
  "motion_enabled": false
}
"""
        stderr = ""

    monkeypatch.setattr(gate.subprocess, "run", lambda *_args, **_kwargs: Result())
    args = gate.parse_args([])

    try:
        gate.deploy_bridge(args, tmp_path, enable_motion=True)
    except RuntimeError as exc:
        assert "deploy_bridge_motion_state_mismatch" in str(exc)
    else:
        raise AssertionError("expected deploy mismatch to fail")
