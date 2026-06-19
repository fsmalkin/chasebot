from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_TOOLS_DIR = REPO_ROOT / "tools" / "robot_factory_bridge"
if str(BRIDGE_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_TOOLS_DIR))

import chasecar_bridge_stack_closed_loop_runner as runner  # noqa: E402
import chasecar_bridge_stack_path_gate as gate  # noqa: E402


def passing_gate_summary(
    artifact_dir: str,
    *,
    area_ratio: float = 0.10,
    center_error: float = 0.01,
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


def final_progress_observation(*, area_ratio: float = 0.12, center_error: float = 0.0) -> dict:
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
            }
        },
    }


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
    assert args.require_progress_scorecard is True
    assert args.score_final_progress_observation is True


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
    assert (tmp_path / "real_stack_boot_report.json").exists()
    assert summary["steps"][0]["policy_preferred_intent"] == "plan_to_target"
    assert summary["progress_scorecard"]["pass"] is True
    assert len(summary["progress_scorecard"]["transitions"]) == 2


def test_target_too_close_is_safe_terminal_after_completed_step(tmp_path, monkeypatch):
    gate_summaries = [
        passing_gate_summary(str(tmp_path / "step_01")),
        {
            **passing_gate_summary(str(tmp_path / "step_02")),
            "pass": False,
            "issues": ["policy_decision_not_pass"],
            "command": {"linear_x": 0.0, "angular_z": 0.0},
            "policy_decision": {
                "pass": False,
                "stop_reason": "target_inside_stack_forward_stop_area",
                "issues": ["target_inside_stack_forward_stop_area"],
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
    assert summary["terminal_reason"] == "target_too_close"
    assert summary["steps"][1]["safe_terminal_stop"] is True


def test_target_too_close_skips_live_motion_requirement(tmp_path, monkeypatch):
    terminal = {
        **passing_gate_summary(str(tmp_path / "step_01")),
        "pass": False,
        "issues": ["policy_decision_not_pass"],
        "command": {"linear_x": 0.0, "angular_z": 0.0},
        "policy_decision": {
            "pass": False,
            "stop_reason": "target_inside_stack_forward_stop_area",
            "issues": ["target_inside_stack_forward_stop_area"],
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
            "--min-completed-steps",
            "0",
        ]
    )
    summary = runner.run(args)

    assert summary["pass"] is True
    assert summary["terminal_reason"] == "target_too_close"
    assert summary["steps"][0]["issues"] == []


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

    args = runner.parse_args(["--artifact-dir", str(tmp_path), "--execute-motion", "--confirm-operator-ready"])
    summary = runner.run(args)

    assert summary["pass"] is False
    assert "progress_scorecard_failed" in summary["issues"]
    assert summary["progress_scorecard"]["pass"] is False
    assert any("target_area_regressed" in issue for issue in summary["progress_scorecard"]["issues"])


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
