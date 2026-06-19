#!/usr/bin/env python3
"""Run a bounded closed-loop Chasecar stack adapter sequence through the factory bridge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from types import SimpleNamespace
from typing import Any

import chasecar_bridge_client as bridge_client
import chasecar_bridge_stack_path_gate as stack_gate


DEFAULT_ARTIFACT_STEM = "factory_bridge_stack_closed_loop"
SAFE_TERMINAL_POLICY_STOPS = {"target_inside_stack_forward_stop_area"}


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def utc_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def ensure_dir(path: Path | str) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path | str, payload: dict[str, Any]) -> None:
    path = Path(path)
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def default_artifact_dir() -> Path:
    return Path("artifacts") / "session" / ("%s_%s" % (DEFAULT_ARTIFACT_STEM, utc_stamp()))


def copy_step_args(args: argparse.Namespace, artifact_dir: Path) -> argparse.Namespace:
    step_args = SimpleNamespace(**vars(args))
    step_args.artifact_dir = str(artifact_dir)
    step_args.dry_run = False
    step_args.policy_entrypoint = stack_gate.POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0
    return step_args


def relay_raw_command(relay_summary: dict[str, Any]) -> dict[str, float]:
    relay = relay_summary.get("relay") if isinstance(relay_summary.get("relay"), dict) else {}
    latest = relay.get("last_input") if isinstance(relay.get("last_input"), dict) else {}
    return {
        "linear_x": float(latest.get("raw_linear_x", 0.0) or 0.0),
        "angular_z": float(latest.get("raw_angular_z", 0.0) or 0.0),
    }


def commands_match(expected: dict[str, Any], observed: dict[str, Any], tolerance: float = 1.0e-5) -> bool:
    for key in ("linear_x", "angular_z"):
        if abs(float(expected.get(key, 0.0) or 0.0) - float(observed.get(key, 0.0) or 0.0)) > tolerance:
            return False
    return True


def command_mismatch_reasons(summary: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    command = summary.get("command") if isinstance(summary.get("command"), dict) else {}
    if not commands_match(command, relay_raw_command(summary.get("relay_summary", {}))):
        reasons.append("locked_relay_command_mismatch")
    motion = summary.get("motion_proof") if isinstance(summary.get("motion_proof"), dict) else {}
    if motion and not commands_match(command, relay_raw_command(motion.get("relay_summary", {}))):
        reasons.append("live_relay_command_mismatch")
    return reasons


def final_state_safe(summary: dict[str, Any]) -> bool:
    return stack_gate.safe_final_state(summary.get("final_locked_health", {})) and bool(
        summary.get("final_camera_readiness_gate", {}).get("pass", False)
    )


def classify_step(summary: dict[str, Any], *, execute_motion: bool) -> tuple[str, bool, list[str]]:
    policy = summary.get("policy_decision") if isinstance(summary.get("policy_decision"), dict) else {}
    stop_reason = str(policy.get("stop_reason", "") or "")
    safe_terminal = stop_reason in SAFE_TERMINAL_POLICY_STOPS and final_state_safe(summary)
    issues = list(summary.get("issues", [])) if isinstance(summary.get("issues"), list) else []
    reasons = command_mismatch_reasons(summary)
    if reasons:
        issues.extend(reasons)
        return "command_mismatch", False, issues
    if not final_state_safe(summary):
        issues.append("unsafe_final_bridge_state")
        return "unsafe_bridge_state", False, issues
    if safe_terminal:
        return "target_too_close", True, []
    if execute_motion:
        motion = summary.get("motion_proof") if isinstance(summary.get("motion_proof"), dict) else {}
        visual_motion = motion.get("visual_motion") if isinstance(motion.get("visual_motion"), dict) else {}
        if not bool(motion.get("pass", False)) or not bool(visual_motion.get("movement_detected", False)):
            issues.append("visual_motion_not_confirmed")
            return "visual_contradiction", False, issues
    if not bool(summary.get("pass", False)):
        return stop_reason or "step_failed", False, issues or ["step_not_pass"]
    return stop_reason or "step_passed", False, []


def step_record(index: int, summary: dict[str, Any], *, execute_motion: bool) -> dict[str, Any]:
    policy = summary.get("policy_decision") if isinstance(summary.get("policy_decision"), dict) else {}
    observation = policy.get("observation") if isinstance(policy.get("observation"), dict) else {}
    motion = summary.get("motion_proof") if isinstance(summary.get("motion_proof"), dict) else {}
    visual_motion = motion.get("visual_motion") if isinstance(motion.get("visual_motion"), dict) else {}
    stop_reason, safe_terminal, issues = classify_step(summary, execute_motion=execute_motion)
    return {
        "index": int(index),
        "artifact_dir": str(summary.get("artifact_dir", "")),
        "pass": bool(summary.get("pass", False)),
        "safe_terminal_stop": bool(safe_terminal),
        "stop_reason": stop_reason,
        "issues": issues,
        "policy_entrypoint": summary.get("policy_entrypoint", ""),
        "policy_stop_reason": policy.get("stop_reason", ""),
        "policy_stage": (policy.get("stack_policy") if isinstance(policy.get("stack_policy"), dict) else {}).get("stage", ""),
        "policy_preferred_intent": (
            policy.get("stack_policy") if isinstance(policy.get("stack_policy"), dict) else {}
        ).get("preferred_intent", ""),
        "target_profile": observation.get("target_profile", ""),
        "target_detected": bool(observation.get("detected", False)),
        "target_centered": bool(observation.get("centered", False)),
        "target_center_error": observation.get("center_error"),
        "target_area_ratio": observation.get("area_ratio"),
        "command": summary.get("command", {}),
        "locked_refusals": (
            summary.get("relay_summary", {}).get("relay", {}).get("counters", {}).get("http_refusals", 0)
            if isinstance(summary.get("relay_summary"), dict)
            else 0
        ),
        "live_posts": (
            motion.get("relay_counters", {}).get("cmd_vel_posts", 0) if isinstance(motion.get("relay_counters"), dict) else 0
        ),
        "live_nonzero_motor_events": motion.get("nonzero_success_event_count", 0),
        "live_visual_motion": bool(visual_motion.get("movement_detected", False)),
        "annotated_image_path": observation.get("annotated_image_path", ""),
        "motion_contact_sheet_path": visual_motion.get("contact_sheet_path", ""),
        "final_motion_enabled": (
            summary.get("final_locked_health", {}).get("response", {}).get("motion_enabled")
            if isinstance(summary.get("final_locked_health"), dict)
            else None
        ),
        "final_left_motor": (
            summary.get("final_locked_health", {}).get("response", {}).get("left_motor")
            if isinstance(summary.get("final_locked_health"), dict)
            else None
        ),
        "final_right_motor": (
            summary.get("final_locked_health", {}).get("response", {}).get("right_motor")
            if isinstance(summary.get("final_locked_health"), dict)
            else None
        ),
        "final_camera_ready": bool(summary.get("final_camera_readiness_gate", {}).get("pass", False)),
    }


def independent_health(args: argparse.Namespace) -> dict[str, Any]:
    client = bridge_client.BridgeClient(args.base_url, args.timeout_s)
    status, payload = client.health()
    return {"http_status": status, "response": payload, "checked_utc": utc_now()}


def run(args: argparse.Namespace) -> dict[str, Any]:
    artifact_root = ensure_dir(args.artifact_dir or default_artifact_dir())
    summary: dict[str, Any] = {
        "generated_utc": utc_now(),
        "type": "factory_bridge_stack_closed_loop_runner",
        "artifact_dir": str(artifact_root),
        "base_url": args.base_url,
        "policy_entrypoint": stack_gate.POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0,
        "target_profile": args.target_profile,
        "execute_motion": bool(args.execute_motion),
        "max_steps": int(args.steps),
        "min_completed_steps": int(args.min_completed_steps),
        "step_settle_s": float(args.step_settle_s),
        "stop_area_ratio": float(args.stack_forward_stop_area_ratio),
        "steps": [],
        "issues": [],
        "pass": False,
    }
    write_json(artifact_root / "closed_loop_summary.json", summary)
    if args.dry_run:
        summary["plan_only"] = True
        summary["pass"] = True
        write_json(artifact_root / "closed_loop_summary.json", summary)
        return summary

    completed_steps = 0
    terminal_reason = "max_steps_completed"
    for index in range(1, int(args.steps) + 1):
        step_dir = artifact_root / ("step_%02d" % index)
        step_summary = stack_gate.run(copy_step_args(args, step_dir))
        write_json(step_dir / "closed_loop_step_source_summary.json", step_summary)
        record = step_record(index, step_summary, execute_motion=bool(args.execute_motion))
        summary["steps"].append(record)

        if record["safe_terminal_stop"]:
            terminal_reason = str(record["stop_reason"])
            break
        if record["issues"] or not record["pass"]:
            terminal_reason = str(record["stop_reason"] or "step_failed")
            summary["issues"].extend("%s:%s" % (terminal_reason, issue) for issue in record["issues"])
            if not record["issues"]:
                summary["issues"].append("%s:step_not_pass" % terminal_reason)
            break

        completed_steps += 1
        if float(args.step_settle_s) > 0 and index < int(args.steps):
            time.sleep(float(args.step_settle_s))

    summary["completed_steps"] = completed_steps
    summary["terminal_reason"] = terminal_reason
    try:
        final_health = independent_health(args)
        summary["final_independent_health"] = final_health
        if not stack_gate.safe_final_state(final_health):
            summary["issues"].append("independent_final_health_not_safe")
    except Exception as exc:
        summary["issues"].append("independent_final_health_failed:%r" % (exc,))

    enough_steps = completed_steps >= int(args.min_completed_steps)
    safe_terminal = terminal_reason == "target_too_close" and enough_steps
    summary["pass"] = bool((not summary["issues"]) and (enough_steps or safe_terminal))
    write_json(artifact_root / "closed_loop_summary.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = stack_gate.build_parser()
    parser.description = "Run repeated observe-policy-command-relock steps through the factory bridge."
    parser.set_defaults(
        policy_entrypoint=stack_gate.POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0,
        target_profile="blue",
        max_bridge_linear_x=0.08,
        max_bridge_angular_z=0.8,
        max_motor_speed=0.7,
        stack_forward_stop_area_ratio=0.20,
    )
    parser.add_argument("--steps", type=int, default=2)
    parser.add_argument("--min-completed-steps", type=int, default=1)
    parser.add_argument("--step-settle-s", type=float, default=0.5)
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run(args)
    print(json.dumps(summary, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if summary.get("pass", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
