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


def write_text(path: Path | str, payload: str) -> None:
    path = Path(path)
    ensure_dir(path.parent)
    path.write_text(payload, encoding="utf-8")


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


def as_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def target_snapshot_from_record(record: dict[str, Any], *, label: str) -> dict[str, Any]:
    center_error = as_float_or_none(record.get("target_center_error"))
    return {
        "label": label,
        "step_index": record.get("index"),
        "target_detected": bool(record.get("target_detected", False)),
        "target_centered": bool(record.get("target_centered", False)),
        "target_center_error": center_error,
        "target_abs_center_error": abs(center_error) if center_error is not None else None,
        "target_area_ratio": as_float_or_none(record.get("target_area_ratio")),
        "annotated_image_path": record.get("annotated_image_path", ""),
    }


def target_snapshot_from_policy_decision(decision: dict[str, Any], *, label: str) -> dict[str, Any]:
    observation = decision.get("observation") if isinstance(decision.get("observation"), dict) else {}
    center_error = as_float_or_none(observation.get("center_error"))
    return {
        "label": label,
        "step_index": None,
        "target_detected": bool(observation.get("detected", False)),
        "target_centered": bool(observation.get("centered", False)),
        "target_center_error": center_error,
        "target_abs_center_error": abs(center_error) if center_error is not None else None,
        "target_area_ratio": as_float_or_none(observation.get("area_ratio")),
        "annotated_image_path": observation.get("annotated_image_path", ""),
    }


def progress_thresholds(args: argparse.Namespace) -> dict[str, float]:
    return {
        "min_area_gain_ratio": float(args.min_progress_area_gain_ratio),
        "max_area_regression_ratio": float(args.max_progress_area_regression_ratio),
        "min_center_gain": float(args.min_progress_center_gain),
        "max_center_regression": float(args.max_progress_center_regression),
        "max_center_error": float(args.max_progress_center_error),
    }


def score_target_progress_transition(
    previous: dict[str, Any],
    current: dict[str, Any],
    args: argparse.Namespace,
    *,
    transition_id: str,
    motion_step_index: int | None,
    motion_contact_sheet_path: str = "",
) -> dict[str, Any]:
    thresholds = progress_thresholds(args)
    issues: list[str] = []
    evidence: list[str] = []

    if not bool(previous.get("target_detected", False)):
        issues.append("previous_target_not_detected")
    if not bool(current.get("target_detected", False)):
        issues.append("current_target_not_detected")

    previous_area = as_float_or_none(previous.get("target_area_ratio"))
    current_area = as_float_or_none(current.get("target_area_ratio"))
    previous_center_abs = as_float_or_none(previous.get("target_abs_center_error"))
    current_center_abs = as_float_or_none(current.get("target_abs_center_error"))
    area_delta = None
    center_abs_delta = None
    if previous_area is None or current_area is None:
        issues.append("target_area_missing")
    else:
        area_delta = current_area - previous_area
    if previous_center_abs is None or current_center_abs is None:
        issues.append("target_center_error_missing")
    else:
        center_abs_delta = previous_center_abs - current_center_abs

    area_gain = area_delta is not None and area_delta >= thresholds["min_area_gain_ratio"]
    area_preserved = area_delta is not None and area_delta >= -thresholds["max_area_regression_ratio"]
    center_gain = center_abs_delta is not None and center_abs_delta >= thresholds["min_center_gain"]
    center_preserved = bool(current.get("target_centered", False)) or (
        current_center_abs is not None and current_center_abs <= thresholds["max_center_error"]
    )
    area_regressed = area_delta is not None and area_delta < -thresholds["max_area_regression_ratio"]
    center_regressed = (
        center_abs_delta is not None
        and center_abs_delta < -thresholds["max_center_regression"]
        and not center_preserved
    )

    if area_gain:
        evidence.append("target_area_increased")
    if center_gain:
        evidence.append("target_centering_improved")
    if area_preserved and center_preserved:
        evidence.append("target_centered_without_area_regression")
    if area_regressed:
        issues.append("target_area_regressed")
    if center_regressed:
        issues.append("target_centering_regressed")
    if not evidence and not issues:
        issues.append("target_progress_not_confirmed")

    passed = bool(evidence and not issues)
    return {
        "transition_id": transition_id,
        "motion_step_index": motion_step_index,
        "pass": passed,
        "issues": issues,
        "evidence": evidence,
        "previous": previous,
        "current": current,
        "deltas": {
            "area_ratio": area_delta,
            "abs_center_error": center_abs_delta,
        },
        "motion_contact_sheet_path": motion_contact_sheet_path,
    }


def capture_final_progress_observation(args: argparse.Namespace, artifact_root: Path) -> dict[str, Any]:
    client = bridge_client.BridgeClient(args.base_url, args.timeout_s)
    artifact_dir = ensure_dir(artifact_root / "final_progress_observation")
    result: dict[str, Any] = {
        "generated_utc": utc_now(),
        "artifact_dir": str(artifact_dir),
        "issues": [],
        "pass": False,
    }
    readiness = stack_gate.camera_readiness_summary(client, args, "final_progress_observation")
    result["camera_readiness_gate"] = readiness
    if not bool(readiness.get("pass", False)):
        result["issues"].append("final_progress_camera_readiness_gate_not_pass")
        write_json(artifact_dir / "final_progress_observation.json", result)
        return result

    decision = stack_gate.run_chasecar_stack_fetch_adapter_policy(client, args, artifact_dir)
    result["policy_decision"] = decision
    result["observation"] = decision.get("observation", {})
    if not bool(result["observation"].get("detected", False)):
        result["issues"].append("final_progress_target_not_detected")
    result["pass"] = not result["issues"]
    write_json(artifact_dir / "final_progress_observation.json", result)
    return result


def build_progress_scorecard(
    summary: dict[str, Any],
    args: argparse.Namespace,
    final_observation: dict[str, Any] | None,
) -> dict[str, Any]:
    terminal_without_motion = (
        summary.get("terminal_reason") == "target_too_close"
        and int(summary.get("completed_steps", 0) or 0) == 0
    )
    required = bool(args.execute_motion and args.require_progress_scorecard and not terminal_without_motion)
    steps = summary.get("steps") if isinstance(summary.get("steps"), list) else []
    scorecard: dict[str, Any] = {
        "generated_utc": utc_now(),
        "required": required,
        "target_profile": args.target_profile,
        "thresholds": progress_thresholds(args),
        "transitions": [],
        "issues": [],
        "pass": False,
    }

    for index in range(1, len(steps)):
        previous_record = steps[index - 1]
        current_record = steps[index]
        previous = target_snapshot_from_record(previous_record, label="step_%02d" % int(previous_record.get("index", index)))
        current = target_snapshot_from_record(current_record, label="step_%02d" % int(current_record.get("index", index + 1)))
        transition = score_target_progress_transition(
            previous,
            current,
            args,
            transition_id="%s_to_%s" % (previous["label"], current["label"]),
            motion_step_index=previous_record.get("index"),
            motion_contact_sheet_path=str(previous_record.get("motion_contact_sheet_path", "")),
        )
        scorecard["transitions"].append(transition)

    if (
        final_observation
        and steps
        and not bool(steps[-1].get("safe_terminal_stop", False))
        and bool(steps[-1].get("pass", False))
    ):
        final_decision = (
            final_observation.get("policy_decision")
            if isinstance(final_observation.get("policy_decision"), dict)
            else {}
        )
        previous_record = steps[-1]
        previous = target_snapshot_from_record(
            previous_record,
            label="step_%02d" % int(previous_record.get("index", len(steps))),
        )
        current = target_snapshot_from_policy_decision(final_decision, label="final_progress_observation")
        transition = score_target_progress_transition(
            previous,
            current,
            args,
            transition_id="%s_to_final_progress_observation" % previous["label"],
            motion_step_index=previous_record.get("index"),
            motion_contact_sheet_path=str(previous_record.get("motion_contact_sheet_path", "")),
        )
        scorecard["transitions"].append(transition)
    elif final_observation and final_observation.get("issues"):
        scorecard["issues"].extend(str(issue) for issue in final_observation.get("issues", []))

    if required and not scorecard["transitions"]:
        scorecard["issues"].append("progress_scorecard_no_scored_transitions")
    if required and scorecard["transitions"]:
        positive_progress = any(
            "target_area_increased" in (transition.get("evidence") or [])
            or "target_centering_improved" in (transition.get("evidence") or [])
            for transition in scorecard["transitions"]
        )
        if not positive_progress:
            scorecard["issues"].append("progress_scorecard_no_positive_progress")
    for transition in scorecard["transitions"]:
        if not transition.get("pass", False):
            for issue in transition.get("issues", []) or ["target_progress_transition_failed"]:
                scorecard["issues"].append("%s:%s" % (transition.get("transition_id", "transition"), issue))

    scorecard["pass"] = bool((not required) or (not scorecard["issues"] and scorecard["transitions"]))
    return scorecard


def progress_scorecard_markdown(scorecard: dict[str, Any]) -> str:
    lines = [
        "# Closed-Loop Progress Scorecard",
        "",
        "- Pass: `%s`" % bool(scorecard.get("pass", False)),
        "- Required: `%s`" % bool(scorecard.get("required", False)),
        "- Target profile: `%s`" % scorecard.get("target_profile", ""),
        "",
        "| Transition | Area delta | Abs-center delta | Evidence | Issues |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for transition in scorecard.get("transitions", []):
        deltas = transition.get("deltas") if isinstance(transition.get("deltas"), dict) else {}
        area_delta = deltas.get("area_ratio")
        center_delta = deltas.get("abs_center_error")
        evidence = ", ".join(str(item) for item in transition.get("evidence", [])) or "-"
        issues = ", ".join(str(item) for item in transition.get("issues", [])) or "-"
        lines.append(
            "| %s | %s | %s | %s | %s |"
            % (
                transition.get("transition_id", ""),
                "%.6f" % area_delta if isinstance(area_delta, (int, float)) else "-",
                "%.6f" % center_delta if isinstance(center_delta, (int, float)) else "-",
                evidence,
                issues,
            )
        )
    if scorecard.get("issues"):
        lines.extend(["", "## Issues", ""])
        lines.extend("- `%s`" % issue for issue in scorecard.get("issues", []))
    return "\n".join(lines) + "\n"


def classify_step(
    summary: dict[str, Any],
    *,
    execute_motion: bool,
    allow_scorecard_motion_proof: bool,
) -> tuple[str, bool, list[str]]:
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
            motion_issues = list(motion.get("issues", [])) if isinstance(motion.get("issues"), list) else []
            visual_issues = (
                list(visual_motion.get("issues", [])) if isinstance(visual_motion.get("issues"), list) else []
            )
            unexpected_issues = [issue for issue in motion_issues + visual_issues if issue != "visual_motion_not_confirmed"]
            if (
                allow_scorecard_motion_proof
                and not unexpected_issues
                and int(motion.get("nonzero_success_event_count", 0) or 0) > 0
            ):
                return "motion_pending_progress_scorecard", False, []
            issues.append("visual_motion_not_confirmed")
            return "visual_contradiction", False, issues
    if not bool(summary.get("pass", False)):
        return stop_reason or "step_failed", False, issues or ["step_not_pass"]
    return stop_reason or "step_passed", False, []


def step_record(
    index: int,
    summary: dict[str, Any],
    *,
    execute_motion: bool,
    allow_scorecard_motion_proof: bool,
) -> dict[str, Any]:
    policy = summary.get("policy_decision") if isinstance(summary.get("policy_decision"), dict) else {}
    observation = policy.get("observation") if isinstance(policy.get("observation"), dict) else {}
    motion = summary.get("motion_proof") if isinstance(summary.get("motion_proof"), dict) else {}
    visual_motion = motion.get("visual_motion") if isinstance(motion.get("visual_motion"), dict) else {}
    stop_reason, safe_terminal, issues = classify_step(
        summary,
        execute_motion=execute_motion,
        allow_scorecard_motion_proof=allow_scorecard_motion_proof,
    )
    source_pass = bool(summary.get("pass", False))
    effective_pass = bool(source_pass or (stop_reason == "motion_pending_progress_scorecard" and not issues))
    return {
        "index": int(index),
        "artifact_dir": str(summary.get("artifact_dir", "")),
        "pass": effective_pass,
        "source_pass": source_pass,
        "motion_proof_pending_progress_scorecard": bool(stop_reason == "motion_pending_progress_scorecard"),
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
        record = step_record(
            index,
            step_summary,
            execute_motion=bool(args.execute_motion),
            allow_scorecard_motion_proof=bool(args.require_progress_scorecard),
        )
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

    final_progress_observation = None
    if (
        bool(args.execute_motion)
        and bool(args.score_final_progress_observation)
        and summary["steps"]
        and not bool(summary["steps"][-1].get("safe_terminal_stop", False))
    ):
        try:
            final_progress_observation = capture_final_progress_observation(args, artifact_root)
            summary["final_progress_observation"] = final_progress_observation
        except Exception as exc:
            summary["issues"].append("final_progress_observation_failed:%r" % (exc,))

    progress_scorecard = build_progress_scorecard(summary, args, final_progress_observation)
    scorecard_path = artifact_root / "progress_scorecard.json"
    scorecard_md_path = artifact_root / "progress_scorecard.md"
    progress_scorecard["json_path"] = str(scorecard_path)
    progress_scorecard["markdown_path"] = str(scorecard_md_path)
    write_json(scorecard_path, progress_scorecard)
    write_text(scorecard_md_path, progress_scorecard_markdown(progress_scorecard))
    summary["progress_scorecard"] = progress_scorecard
    if bool(args.execute_motion) and bool(args.require_progress_scorecard) and not progress_scorecard.get("pass", False):
        summary["issues"].append("progress_scorecard_failed")

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
    parser.add_argument("--min-progress-area-gain-ratio", type=float, default=0.0005)
    parser.add_argument("--max-progress-area-regression-ratio", type=float, default=0.04)
    parser.add_argument("--min-progress-center-gain", type=float, default=0.01)
    parser.add_argument("--max-progress-center-regression", type=float, default=0.04)
    parser.add_argument("--max-progress-center-error", type=float, default=0.16)
    parser.add_argument("--require-progress-scorecard", dest="require_progress_scorecard", action="store_true")
    parser.add_argument("--no-require-progress-scorecard", dest="require_progress_scorecard", action="store_false")
    parser.add_argument(
        "--score-final-progress-observation",
        dest="score_final_progress_observation",
        action="store_true",
    )
    parser.add_argument(
        "--skip-final-progress-observation",
        dest="score_final_progress_observation",
        action="store_false",
    )
    parser.set_defaults(require_progress_scorecard=True, score_final_progress_observation=True)
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
