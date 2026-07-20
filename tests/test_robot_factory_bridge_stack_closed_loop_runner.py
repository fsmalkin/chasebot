from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_TOOLS_DIR = REPO_ROOT / "tools" / "robot_factory_bridge"
if str(BRIDGE_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_TOOLS_DIR))
sys.modules.setdefault("onnxruntime", SimpleNamespace(__version__="test-stub"))

import chasecar_bridge_stack_closed_loop_runner as runner  # noqa: E402
import chasecar_bridge_stack_path_gate as gate  # noqa: E402


def passing_gate_summary(
    artifact_dir: str,
    *,
    area_ratio: float = 0.10,
    center_error: float = 0.01,
    bbox_height_ratio: float = 0.24,
    motion_pass: bool = True,
    visual_motion: bool = True,
) -> dict:
    command = {"linear_x": 0.025, "angular_z": 0.03}
    relay = {
        "relay": {
            "counters": {"http_refusals": 7},
            "last_input": {
                "raw_linear_x": command["linear_x"],
                "raw_angular_z": command["angular_z"],
            },
        }
    }
    return {
        "artifact_dir": artifact_dir,
        "pass": True,
        "issues": [],
        "policy_entrypoint": gate.POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0,
        "command": command,
        "policy_decision": {
            "pass": True,
            "stop_reason": "fetch_to_pose_approach_command",
            "observation": {
                "target_profile": "blue",
                "detected": True,
                "centered": True,
                "center_error": center_error,
                "area_ratio": area_ratio,
                "annotated_image_path": "annotated.jpg",
            },
            "stack_policy": {"stage": "plan", "preferred_intent": "plan_to_target"},
            "analysis": {
                "detector_backend": "yolo_onnx_or_color:color",
                "detector_arbitration": {"selected": "color", "reason": "yolo_target_not_detected"},
                "yolo_onnx_primary_detected": False,
                "yolo_onnx_primary_area_ratio": 0.0,
                "yolo_onnx_primary_center_error": None,
                "bbox_height_ratio": bbox_height_ratio,
            },
        },
        "relay_summary": relay,
        "motion_proof": {
            "pass": motion_pass,
            "relay_counters": {"cmd_vel_posts": 8},
            "nonzero_success_event_count": 8,
            "relay_summary": relay,
            "visual_motion": {
                "movement_detected": visual_motion,
                "issues": [] if visual_motion else ["visual_motion_not_confirmed"],
                "contact_sheet_path": "before_after.jpg",
            },
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


def test_step_record_surfaces_detector_evidence(tmp_path):
    summary = passing_gate_summary(str(tmp_path / "step_01"))

    record = runner.step_record(
        1,
        summary,
        execute_motion=False,
        allow_scorecard_motion_proof=False,
    )

    assert record["detector_backend"] == "yolo_onnx_or_color:color"
    assert record["detector_arbitration_selected"] == "color"
    assert record["detector_arbitration_reason"] == "yolo_target_not_detected"
    assert record["yolo_onnx_primary_detected"] is False
    assert record["yolo_onnx_primary_area_ratio"] == 0.0
    assert record["progress_detector_backend"] == "yolo_onnx_or_color:color"
    assert record["progress_target_area_ratio"] == 0.10


def final_progress_observation(
    *,
    area_ratio: float = 0.12,
    center_error: float = 0.0,
    bbox_height_ratio: float = 0.26,
) -> dict:
    return {
        "pass": True,
        "issues": [],
        "policy_decision": {
            "observation": {
                "target_profile": "blue",
                "detected": True,
                "centered": True,
                "center_error": center_error,
                "area_ratio": area_ratio,
                "annotated_image_path": "final_annotated.jpg",
            },
            "analysis": {"bbox_height_ratio": bbox_height_ratio},
        },
    }


def test_progress_scorecard_uses_color_fallback_geometry_for_yolo_selected_step(tmp_path):
    step_summary = passing_gate_summary(
        str(tmp_path / "step_01"),
        area_ratio=0.028377,
        center_error=-0.053125,
    )
    step_summary["policy_decision"]["analysis"] = {
        "detector_backend": "yolo_onnx_or_color:yolo_onnx",
        "detector_arbitration": {
            "selected": "yolo_onnx",
            "reason": "yolo_candidate_not_smaller_than_color_target",
        },
        "color_fallback_detected": True,
        "color_fallback_area_ratio": 0.016080729166666665,
        "color_fallback_center_error": -0.06857793522267208,
    }
    step_record = runner.step_record(
        1,
        step_summary,
        execute_motion=True,
        allow_scorecard_motion_proof=True,
    )
    final_observation = {
        "pass": True,
        "issues": [],
        "policy_decision": {
            "observation": {
                "target_profile": "green",
                "detected": True,
                "centered": True,
                "center_error": -0.09050799531981273,
                "area_ratio": 0.016692708333333334,
                "annotated_image_path": "final_annotated_color.jpg",
            },
            "stack_policy": {"stage": "plan", "preferred_intent": "plan_to_target"},
            "analysis": {
                "detector_backend": "yolo_onnx_or_color:color",
                "detector_arbitration": {"selected": "color", "reason": "yolo_target_not_detected"},
            },
        },
    }
    args = runner.parse_args(["--execute-motion", "--confirm-operator-ready"])

    scorecard = runner.build_progress_scorecard(
        {"completed_steps": 1, "steps": [step_record]},
        args,
        final_observation,
    )

    assert scorecard["pass"] is True
    transition = scorecard["transitions"][0]
    assert transition["previous"]["progress_detector_backend"] == "color_fallback"
    assert transition["current"]["progress_detector_backend"] == "yolo_onnx_or_color:color"
    assert transition["deltas"]["area_ratio"] > 0.0005
    assert "target_area_increased" in transition["evidence"]


class FakeBridgeClient:
    def __init__(self, *_args, **_kwargs):
        pass

    def health(self):
        return 200, {
            "ok": True,
            "motion_enabled": False,
            "left_motor": 0.0,
            "right_motor": 0.0,
            "camera": {"enabled": True},
        }


def test_parser_defaults_to_stack_adapter_blue_loop():
    args = runner.parse_args([])

    assert args.policy_entrypoint == gate.POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0
    assert args.target_profile == "blue"
    assert args.steps == 2
    assert args.stack_forward_stop_area_ratio == 0.20
    assert args.stack_forward_stop_bbox_height_ratio == 0.0
    assert args.require_progress_scorecard is True
    assert args.score_final_progress_observation is True
    assert args.require_nav_target_success is False
    assert args.nav_target_success_area_ratio == 0.0
    assert args.nav_target_success_bbox_height_ratio == 0.0
    assert args.step_retries == 1


def test_relay_raw_command_reads_direct_http_event_payload():
    relay_summary = {
        "relay": {
            "events": [
                {
                    "action": "cmd_vel",
                    "payload": {
                        "linear_x": 0.04,
                        "angular_z": 0.0,
                        "raw": {"linear_x": 0.025, "angular_z": 0.0},
                    },
                }
            ]
        }
    }

    assert runner.relay_raw_command(relay_summary) == {"linear_x": 0.025, "angular_z": 0.0}


def test_real_stack_boot_report_is_written_for_dry_run(tmp_path):
    args = runner.parse_args(["--artifact-dir", str(tmp_path), "--dry-run"])
    summary = runner.run(args)
    report = summary["real_stack_boot_report"]

    assert summary["pass"] is True
    assert report["pass"] is True
    assert report["selected_entrypoint"] == gate.POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0
    assert report["policy_smoke"]["policy_preferred_intent"] == "plan_to_target"
    assert report["components"]["supervisor_policy"]["bridge_runtime_status"] == "routed"
    assert report["components"]["brain_intent_executor"]["bridge_runtime_status"] == "source_present_gap"
    assert (tmp_path / "real_stack_boot_report.json").exists()
    assert (tmp_path / "real_stack_boot_report.md").exists()


def test_closed_loop_runs_two_steps_and_writes_summary(tmp_path, monkeypatch):
    calls = []
    gate_summaries = [
        passing_gate_summary(str(tmp_path / "step_01"), area_ratio=0.10, center_error=0.02),
        passing_gate_summary(str(tmp_path / "step_02"), area_ratio=0.11, center_error=0.01),
    ]

    def fake_gate_run(args):
        calls.append(Path(args.artifact_dir).name)
        return gate_summaries.pop(0)

    monkeypatch.setattr(runner.stack_gate, "run", fake_gate_run)
    monkeypatch.setattr(runner.bridge_client, "BridgeClient", FakeBridgeClient)
    monkeypatch.setattr(runner, "capture_final_progress_observation", lambda _args, _root: final_progress_observation())

    args = runner.parse_args(["--artifact-dir", str(tmp_path), "--execute-motion", "--confirm-operator-ready"])
    summary = runner.run(args)

    assert summary["pass"] is True
    assert summary["completed_steps"] == 2
    assert calls == ["step_01", "step_02"]
    assert (tmp_path / "closed_loop_summary.json").exists()
    assert (tmp_path / "progress_scorecard.json").exists()
    assert (tmp_path / "progress_scorecard.md").exists()
    assert (tmp_path / "nav_target_success.json").exists()
    assert (tmp_path / "nav_target_success.md").exists()
    assert (tmp_path / "real_stack_boot_report.json").exists()
    assert summary["steps"][0]["policy_preferred_intent"] == "plan_to_target"
    assert summary["progress_scorecard"]["pass"] is True
    assert len(summary["progress_scorecard"]["transitions"]) == 2


def test_closed_loop_retries_safe_policy_timeout(tmp_path, monkeypatch):
    calls = []
    timeout_summary = {
        "artifact_dir": str(tmp_path / "step_01"),
        "pass": False,
        "issues": ["runner_exception:TimeoutError('timed out')"],
        "policy_entrypoint": gate.POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0,
        "command": {},
        "final_locked_health": {
            "response": {
                "motion_enabled": False,
                "left_motor": 0.0,
                "right_motor": 0.0,
            }
        },
        "final_camera_readiness_gate": {"pass": True},
    }
    gate_summaries = [
        timeout_summary,
        passing_gate_summary(str(tmp_path / "step_01_retry_01"), area_ratio=0.10, center_error=0.02),
    ]

    def fake_gate_run(args):
        calls.append(Path(args.artifact_dir).name)
        return gate_summaries.pop(0)

    monkeypatch.setattr(runner.stack_gate, "run", fake_gate_run)
    monkeypatch.setattr(runner.bridge_client, "BridgeClient", FakeBridgeClient)
    monkeypatch.setattr(runner, "capture_final_progress_observation", lambda _args, _root: final_progress_observation())

    args = runner.parse_args(
        [
            "--artifact-dir",
            str(tmp_path),
            "--steps",
            "1",
            "--execute-motion",
            "--confirm-operator-ready",
        ]
    )
    summary = runner.run(args)

    assert summary["pass"] is True
    assert calls == ["step_01", "step_01_retry_01"]
    assert summary["steps"][0]["artifact_dir"].endswith("step_01_retry_01")
    assert summary["steps"][0]["attempts"][0]["retry_reason"] == "policy_observation_timeout"
    assert summary["steps"][0]["attempts"][0]["final_safe"] is True
    assert summary["completed_steps"] == 1


def test_closed_loop_retries_safe_motion_camera_timeout(tmp_path, monkeypatch):
    calls = []
    motion_timeout = passing_gate_summary(str(tmp_path / "step_01"), area_ratio=0.10, center_error=0.02)
    motion_timeout["pass"] = False
    motion_timeout["motion_proof"] = {
        "pass": False,
        "issues": ["motion_camera_readiness_gate_not_pass"],
        "visual_motion": {"movement_detected": False, "issues": ["visual_motion_not_confirmed"]},
    }
    gate_summaries = [
        motion_timeout,
        passing_gate_summary(str(tmp_path / "step_01_retry_01"), area_ratio=0.11, center_error=0.01),
    ]

    def fake_gate_run(args):
        calls.append(Path(args.artifact_dir).name)
        return gate_summaries.pop(0)

    monkeypatch.setattr(runner.stack_gate, "run", fake_gate_run)
    monkeypatch.setattr(runner.bridge_client, "BridgeClient", FakeBridgeClient)
    monkeypatch.setattr(runner, "capture_final_progress_observation", lambda _args, _root: final_progress_observation())

    args = runner.parse_args(
        [
            "--artifact-dir",
            str(tmp_path),
            "--steps",
            "1",
            "--execute-motion",
            "--confirm-operator-ready",
        ]
    )
    summary = runner.run(args)

    assert summary["pass"] is True
    assert calls == ["step_01", "step_01_retry_01"]
    assert summary["steps"][0]["attempts"][0]["retry_reason"] == "motion_camera_readiness_timeout"
    assert "live_relay_command_mismatch" not in summary["steps"][0]["attempts"][0]["issues"]


def test_closed_loop_retries_safe_motion_runner_timeout(tmp_path, monkeypatch):
    calls = []
    motion_timeout = passing_gate_summary(str(tmp_path / "step_01"), area_ratio=0.10, center_error=0.02)
    motion_timeout["pass"] = False
    motion_timeout["motion_proof"] = {
        "pass": False,
        "issues": [
            "motion_runner_exception:TimeoutError('timed out')",
            "motion_visual_evidence_failed:KeyError('before_snapshot')",
        ],
        "visual_motion": {"movement_detected": False, "issues": ["visual_motion_not_confirmed"]},
    }
    gate_summaries = [
        motion_timeout,
        passing_gate_summary(str(tmp_path / "step_01_retry_01"), area_ratio=0.11, center_error=0.01),
    ]

    def fake_gate_run(args):
        calls.append(Path(args.artifact_dir).name)
        return gate_summaries.pop(0)

    monkeypatch.setattr(runner.stack_gate, "run", fake_gate_run)
    monkeypatch.setattr(runner.bridge_client, "BridgeClient", FakeBridgeClient)
    monkeypatch.setattr(runner, "capture_final_progress_observation", lambda _args, _root: final_progress_observation())

    args = runner.parse_args(
        [
            "--artifact-dir",
            str(tmp_path),
            "--steps",
            "1",
            "--execute-motion",
            "--confirm-operator-ready",
        ]
    )
    summary = runner.run(args)

    assert summary["pass"] is True
    assert calls == ["step_01", "step_01_retry_01"]
    assert summary["steps"][0]["attempts"][0]["retry_reason"] == "motion_runner_timeout"


def test_close_target_stop_is_safe_terminal_after_completed_step(tmp_path, monkeypatch):
    gate_summaries = [
        passing_gate_summary(str(tmp_path / "step_01")),
        {
            **passing_gate_summary(str(tmp_path / "step_02")),
            "pass": True,
            "issues": [],
            "safe_terminal_stop": True,
            "command": {"linear_x": 0.0, "angular_z": 0.0},
            "policy_decision": {
                "pass": True,
                "stop_reason": "target_inside_stack_forward_stop_area",
                "safe_terminal_stop": True,
                "issues": [],
                "observation": {
                    "target_profile": "blue",
                    "detected": True,
                    "centered": True,
                    "area_ratio": 0.24,
                },
                "stack_policy": {"stage": "plan", "preferred_intent": "plan_to_target"},
            },
            "relay_summary": {},
            "motion_proof": {},
        },
    ]

    def fake_gate_run(_args):
        return gate_summaries.pop(0)

    monkeypatch.setattr(runner.stack_gate, "run", fake_gate_run)
    monkeypatch.setattr(runner.bridge_client, "BridgeClient", FakeBridgeClient)

    args = runner.parse_args(["--artifact-dir", str(tmp_path), "--steps", "3"])
    summary = runner.run(args)

    assert summary["pass"] is True
    assert summary["completed_steps"] == 1
    assert summary["terminal_reason"] == "target_inside_stack_forward_stop_area"
    assert summary["safe_terminal_stop"] is True
    assert summary["steps"][1]["safe_terminal_stop"] is True


def test_close_target_stop_skips_live_motion_requirement(tmp_path, monkeypatch):
    terminal = {
        **passing_gate_summary(str(tmp_path / "step_01")),
        "pass": True,
        "issues": [],
        "safe_terminal_stop": True,
        "command": {"linear_x": 0.0, "angular_z": 0.0},
        "policy_decision": {
            "pass": True,
            "stop_reason": "target_inside_stack_forward_stop_area",
            "safe_terminal_stop": True,
            "issues": [],
            "observation": {
                "target_profile": "blue",
                "detected": True,
                "centered": True,
                "area_ratio": 0.24,
            },
            "stack_policy": {"stage": "plan", "preferred_intent": "plan_to_target"},
        },
        "relay_summary": {},
        "motion_proof": {},
    }

    monkeypatch.setattr(runner.stack_gate, "run", lambda _args: terminal)
    monkeypatch.setattr(runner.bridge_client, "BridgeClient", FakeBridgeClient)

    args = runner.parse_args(
        [
            "--artifact-dir",
            str(tmp_path),
            "--execute-motion",
            "--confirm-operator-ready",
        ]
    )
    summary = runner.run(args)

    assert summary["pass"] is True
    assert summary["terminal_reason"] == "target_inside_stack_forward_stop_area"
    assert summary["safe_terminal_stop"] is True
    assert summary["steps"][0]["issues"] == []


def test_nav_target_success_required_passes_from_final_observation(tmp_path, monkeypatch):
    gate_summaries = [
        passing_gate_summary(str(tmp_path / "step_01"), area_ratio=0.10, center_error=0.02),
        passing_gate_summary(str(tmp_path / "step_02"), area_ratio=0.14, center_error=0.01),
    ]

    monkeypatch.setattr(runner.stack_gate, "run", lambda _args: gate_summaries.pop(0))
    monkeypatch.setattr(runner.bridge_client, "BridgeClient", FakeBridgeClient)
    monkeypatch.setattr(
        runner,
        "capture_final_progress_observation",
        lambda _args, _root: final_progress_observation(area_ratio=0.22, center_error=0.0),
    )

    args = runner.parse_args(
        [
            "--artifact-dir",
            str(tmp_path),
            "--execute-motion",
            "--confirm-operator-ready",
            "--require-nav-target-success",
        ]
    )
    summary = runner.run(args)

    assert summary["pass"] is True
    assert summary["nav_target_success"]["pass"] is True
    assert "target_area_success_threshold_met" in summary["nav_target_success"]["evidence"]


def test_nav_target_success_required_accepts_bbox_height_threshold(tmp_path, monkeypatch):
    gate_summaries = [
        passing_gate_summary(str(tmp_path / "step_01"), area_ratio=0.10, center_error=0.02, bbox_height_ratio=0.24),
        passing_gate_summary(str(tmp_path / "step_02"), area_ratio=0.12, center_error=0.01, bbox_height_ratio=0.26),
    ]

    monkeypatch.setattr(runner.stack_gate, "run", lambda _args: gate_summaries.pop(0))
    monkeypatch.setattr(runner.bridge_client, "BridgeClient", FakeBridgeClient)
    monkeypatch.setattr(
        runner,
        "capture_final_progress_observation",
        lambda _args, _root: final_progress_observation(
            area_ratio=0.13,
            center_error=0.0,
            bbox_height_ratio=0.30,
        ),
    )

    args = runner.parse_args(
        [
            "--artifact-dir",
            str(tmp_path),
            "--execute-motion",
            "--confirm-operator-ready",
            "--require-nav-target-success",
            "--nav-target-success-area-ratio",
            "0.20",
            "--nav-target-success-bbox-height-ratio",
            "0.28",
        ]
    )
    summary = runner.run(args)

    assert summary["pass"] is True
    assert summary["nav_target_success"]["pass"] is True
    assert "target_bbox_height_success_threshold_met" in summary["nav_target_success"]["evidence"]
    assert "target_area_below_success_threshold" not in summary["nav_target_success"]["issues"]


def test_nav_target_success_required_fails_without_target_reached(tmp_path, monkeypatch):
    gate_summaries = [
        passing_gate_summary(str(tmp_path / "step_01"), area_ratio=0.10, center_error=0.02),
        passing_gate_summary(str(tmp_path / "step_02"), area_ratio=0.12, center_error=0.01),
    ]

    monkeypatch.setattr(runner.stack_gate, "run", lambda _args: gate_summaries.pop(0))
    monkeypatch.setattr(runner.bridge_client, "BridgeClient", FakeBridgeClient)
    monkeypatch.setattr(
        runner,
        "capture_final_progress_observation",
        lambda _args, _root: final_progress_observation(area_ratio=0.13, center_error=0.0),
    )

    args = runner.parse_args(
        [
            "--artifact-dir",
            str(tmp_path),
            "--execute-motion",
            "--confirm-operator-ready",
            "--require-nav-target-success",
        ]
    )
    summary = runner.run(args)

    assert summary["pass"] is False
    assert "nav_target_success_failed" in summary["issues"]
    assert summary["nav_target_success"]["pass"] is False
    assert "target_area_below_success_threshold" in summary["nav_target_success"]["issues"]


def test_nav_target_success_required_accepts_safe_terminal_close_target_stop(tmp_path, monkeypatch):
    terminal = {
        **passing_gate_summary(str(tmp_path / "step_01")),
        "pass": True,
        "issues": [],
        "safe_terminal_stop": True,
        "command": {"linear_x": 0.0, "angular_z": 0.0},
        "policy_decision": {
            "pass": True,
            "stop_reason": "target_inside_stack_forward_stop_area",
            "safe_terminal_stop": True,
            "issues": [],
            "observation": {
                "target_profile": "blue",
                "detected": True,
                "centered": True,
                "center_error": 0.0,
                "area_ratio": 0.24,
                "annotated_image_path": "terminal.jpg",
            },
            "stack_policy": {"stage": "plan", "preferred_intent": "plan_to_target"},
        },
        "relay_summary": {},
        "motion_proof": {},
    }

    monkeypatch.setattr(runner.stack_gate, "run", lambda _args: terminal)
    monkeypatch.setattr(runner.bridge_client, "BridgeClient", FakeBridgeClient)

    args = runner.parse_args(
        [
            "--artifact-dir",
            str(tmp_path),
            "--require-nav-target-success",
        ]
    )
    summary = runner.run(args)

    assert summary["pass"] is True
    assert summary["nav_target_success"]["pass"] is True
    assert "safe_terminal_stop" in summary["nav_target_success"]["evidence"]
    assert (
        "terminal_reason_target_inside_stack_forward_stop_area"
        in summary["nav_target_success"]["evidence"]
    )


def test_progress_scorecard_allows_search_reacquire_step():
    previous = {
        "label": "step_01",
        "target_detected": True,
        "target_centered": True,
        "target_area_ratio": 0.08,
        "target_abs_center_error": 0.01,
        "policy_preferred_intent": "plan_to_target",
    }
    current = {
        "label": "step_02",
        "target_detected": False,
        "target_centered": False,
        "target_area_ratio": 0.0,
        "target_abs_center_error": None,
        "policy_preferred_intent": "search_for_target",
    }
    args = runner.parse_args([])

    transition = runner.score_target_progress_transition(
        previous,
        current,
        args,
        transition_id="step_01_to_step_02",
        motion_step_index=1,
    )

    assert transition["pass"] is True
    assert transition["skipped"] is True
    assert transition["evidence"] == ["search_reacquire_step_unscored"]


def test_progress_scorecard_accepts_target_reacquired_after_search():
    previous = {
        "label": "step_01",
        "target_detected": False,
        "target_centered": False,
        "target_area_ratio": 0.0,
        "target_abs_center_error": None,
        "policy_preferred_intent": "search_for_target",
    }
    current = {
        "label": "step_02",
        "target_detected": True,
        "target_centered": True,
        "target_area_ratio": 0.07,
        "target_abs_center_error": 0.02,
        "policy_preferred_intent": "plan_to_target",
    }
    args = runner.parse_args([])

    transition = runner.score_target_progress_transition(
        previous,
        current,
        args,
        transition_id="step_01_to_step_02",
        motion_step_index=1,
    )

    assert transition["pass"] is True
    assert transition["skipped"] is False
    assert transition["evidence"] == ["target_reacquired_after_search"]


def test_progress_scorecard_failure_fails_live_loop(tmp_path, monkeypatch):
    gate_summaries = [
        passing_gate_summary(str(tmp_path / "step_01"), area_ratio=0.12, center_error=0.01),
        passing_gate_summary(str(tmp_path / "step_02"), area_ratio=0.06, center_error=0.18),
    ]

    monkeypatch.setattr(runner.stack_gate, "run", lambda _args: gate_summaries.pop(0))
    monkeypatch.setattr(runner.bridge_client, "BridgeClient", FakeBridgeClient)
    monkeypatch.setattr(
        runner,
        "capture_final_progress_observation",
        lambda _args, _root: final_progress_observation(area_ratio=0.05, center_error=0.18),
    )

    args = runner.parse_args(
        ["--artifact-dir", str(tmp_path), "--execute-motion", "--confirm-operator-ready", "--steps", "1"]
    )
    summary = runner.run(args)

    assert summary["pass"] is False
    assert "progress_scorecard_failed" in summary["issues"]
    assert summary["progress_scorecard"]["pass"] is False
    assert any("target_area_regressed" in issue for issue in summary["progress_scorecard"]["issues"])


def test_progress_scorecard_accepts_stable_centered_motion(tmp_path, monkeypatch):
    gate_summary = passing_gate_summary(
        str(tmp_path / "step_01"),
        area_ratio=0.0132,
        center_error=-0.02,
    )

    monkeypatch.setattr(runner.stack_gate, "run", lambda _args: gate_summary)
    monkeypatch.setattr(runner.bridge_client, "BridgeClient", FakeBridgeClient)
    monkeypatch.setattr(
        runner,
        "capture_final_progress_observation",
        lambda _args, _root: final_progress_observation(area_ratio=0.0116, center_error=-0.08),
    )

    args = runner.parse_args(["--artifact-dir", str(tmp_path), "--execute-motion", "--confirm-operator-ready"])
    summary = runner.run(args)

    assert summary["pass"] is True
    assert summary["progress_scorecard"]["pass"] is True
    transition = summary["progress_scorecard"]["transitions"][0]
    assert "target_centered_without_area_regression" in transition["evidence"]
    assert "progress_scorecard_no_positive_progress" not in summary["progress_scorecard"]["issues"]


def test_progress_scorecard_accepts_bbox_height_gain(tmp_path, monkeypatch):
    gate_summary = passing_gate_summary(
        str(tmp_path / "step_01"),
        area_ratio=0.0132,
        center_error=0.02,
        bbox_height_ratio=0.24,
    )

    monkeypatch.setattr(runner.stack_gate, "run", lambda _args: gate_summary)
    monkeypatch.setattr(runner.bridge_client, "BridgeClient", FakeBridgeClient)
    monkeypatch.setattr(
        runner,
        "capture_final_progress_observation",
        lambda _args, _root: final_progress_observation(
            area_ratio=0.0128,
            center_error=0.02,
            bbox_height_ratio=0.247,
        ),
    )

    args = runner.parse_args(
        ["--artifact-dir", str(tmp_path), "--execute-motion", "--confirm-operator-ready", "--steps", "1"]
    )
    summary = runner.run(args)

    assert summary["pass"] is True
    transition = summary["progress_scorecard"]["transitions"][0]
    assert transition["deltas"]["bbox_height_ratio"] == pytest.approx(0.007)
    assert "target_bbox_height_increased" in transition["evidence"]


def test_progress_scorecard_can_resolve_pending_visual_motion(tmp_path, monkeypatch):
    gate_summaries = [
        passing_gate_summary(
            str(tmp_path / "step_01"),
            area_ratio=0.10,
            center_error=0.02,
            motion_pass=False,
            visual_motion=False,
        ),
        passing_gate_summary(
            str(tmp_path / "step_02"),
            area_ratio=0.12,
            center_error=0.01,
            motion_pass=False,
            visual_motion=False,
        ),
    ]

    monkeypatch.setattr(runner.stack_gate, "run", lambda _args: gate_summaries.pop(0))
    monkeypatch.setattr(runner.bridge_client, "BridgeClient", FakeBridgeClient)
    monkeypatch.setattr(runner, "capture_final_progress_observation", lambda _args, _root: final_progress_observation())

    args = runner.parse_args(["--artifact-dir", str(tmp_path), "--execute-motion", "--confirm-operator-ready"])
    summary = runner.run(args)

    assert summary["pass"] is True
    assert summary["completed_steps"] == 2
    assert summary["steps"][0]["motion_proof_pending_progress_scorecard"] is True
    assert summary["progress_scorecard"]["pass"] is True


def test_command_mismatch_fails_loop(tmp_path, monkeypatch):
    bad = passing_gate_summary(str(tmp_path / "step_01"))
    bad["relay_summary"]["relay"]["last_input"]["raw_linear_x"] = 0.0

    monkeypatch.setattr(runner.stack_gate, "run", lambda _args: bad)
    monkeypatch.setattr(runner.bridge_client, "BridgeClient", FakeBridgeClient)

    args = runner.parse_args(["--artifact-dir", str(tmp_path)])
    summary = runner.run(args)

    assert summary["pass"] is False
    assert summary["terminal_reason"] == "command_mismatch"
    assert "command_mismatch:locked_relay_command_mismatch" in summary["issues"]
