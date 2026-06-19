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
REAL_STACK_BOOT_REPORT_FILENAME = "real_stack_boot_report.json"
REAL_STACK_BOOT_REPORT_MD_FILENAME = "real_stack_boot_report.md"


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


def read_source_text(relative_path: str) -> tuple[Path, str]:
    source_path = stack_gate.REPO_ROOT / relative_path
    if not source_path.is_file():
        return source_path, ""
    return source_path, source_path.read_text(encoding="utf-8")


def source_component(
    *,
    name: str,
    relative_path: str,
    governing_symbols: dict[str, str],
    bridge_runtime_status: str,
    route_or_gap: str,
    evidence: str,
) -> dict[str, Any]:
    source_path, source_text = read_source_text(relative_path)
    symbols = {symbol: (needle in source_text if source_text else False) for symbol, needle in governing_symbols.items()}
    return {
        "name": name,
        "source_path": stack_gate.repo_display_path(source_path),
        "source_present": source_path.is_file(),
        "governing_symbols": symbols,
        "bridge_runtime_status": bridge_runtime_status,
        "route_or_gap": route_or_gap,
        "evidence": evidence,
    }


def build_policy_smoke(args: argparse.Namespace) -> dict[str, Any]:
    analysis = {
        "detected": True,
        "centered": True,
        "target_profile": args.target_profile,
        "center_error": 0.0,
        "area_ratio": min(float(args.stack_forward_stop_area_ratio) * 0.25, 0.05),
        "bbox": [120, 70, 200, 170],
        "recommendation": {
            "linear_x": 0.0,
            "angular_z": 0.0,
        },
    }
    decision_id = "real_stack_boot_report:%s" % utc_stamp()
    stack_state = stack_gate.stack_state_from_analysis(analysis, decision_id=decision_id)
    policy_snapshot = stack_gate.supervisor_policy.build_policy_snapshot(stack_state, sim_gate_ready=True)
    command, command_issues, stop_reason = stack_gate.stack_command_from_policy(analysis, policy_snapshot, args)
    return {
        "decision_id": decision_id,
        "policy_stage": policy_snapshot.get("stage", ""),
        "policy_preferred_intent": policy_snapshot.get("preferred_intent", ""),
        "policy_allowed_intents": policy_snapshot.get("allowed_intents", []),
        "policy_reason": policy_snapshot.get("reason", ""),
        "command": command,
        "command_issues": command_issues,
        "stop_reason": stop_reason,
        "pass": bool(
            policy_snapshot.get("preferred_intent") == "plan_to_target"
            and not command_issues
            and stack_gate.command_nonzero(command)
        ),
    }


def build_real_stack_boot_report(args: argparse.Namespace) -> dict[str, Any]:
    policy_smoke = build_policy_smoke(args)
    components = {
        "supervisor_policy": source_component(
            name="supervisor_policy",
            relative_path="scripts/brain_supervisor_policy.py",
            governing_symbols={
                "build_policy_snapshot": "def build_policy_snapshot",
                "policy_signal_snapshot": "def policy_signal_snapshot",
                "intent_readiness_snapshot": "def intent_readiness_snapshot",
            },
            bridge_runtime_status="routed",
            route_or_gap=(
                "tools/robot_factory_bridge/chasecar_bridge_stack_path_gate.py:"
                "run_chasecar_stack_fetch_adapter_policy calls build_policy_snapshot."
            ),
            evidence="The bridge runner builds a stack_state from the live camera analysis before command selection.",
        ),
        "factory_bridge_stack_adapter": source_component(
            name="factory_bridge_stack_adapter",
            relative_path="tools/robot_factory_bridge/chasecar_bridge_stack_path_gate.py",
            governing_symbols={
                "run_chasecar_stack_fetch_adapter_policy": "def run_chasecar_stack_fetch_adapter_policy",
                "stack_state_from_analysis": "def stack_state_from_analysis",
                "stack_command_from_policy": "def stack_command_from_policy",
                "relay_bash": "def relay_bash",
            },
            bridge_runtime_status="routed",
            route_or_gap="Maps the supervisor policy intent to bounded bridge cmd_vel through the runtime JSON relay.",
            evidence="Every closed-loop step invokes stack_gate.run with chasecar_stack_fetch_adapter_v0.",
        ),
        "supervisor_loop": source_component(
            name="supervisor_loop",
            relative_path="scripts/brain_supervisor_loop.py",
            governing_symbols={
                "SupervisorController": "class SupervisorController",
                "evaluate_once": "def evaluate_once",
                "fetch_dashboard_state": "fetch_dashboard_state",
            },
            bridge_runtime_status="source_present_gap",
            route_or_gap=(
                "The loop is a dashboard shadow evaluator; the factory bridge runner currently supplies a direct "
                "camera snapshot, stack_state, and relay command instead of dashboard preview/dispatch surfaces."
            ),
            evidence="Use this as the next bridge adapter target after object pose and dashboard state are bridge-backed.",
        ),
        "brain_intent_executor": source_component(
            name="brain_intent_executor",
            relative_path="scripts/brain_intent_executor.py",
            governing_symbols={
                "BrainIntentExecutor": "class BrainIntentExecutor",
                "NavigateToPose": "NavigateToPose",
                "cmd_vel": "cmd_vel",
            },
            bridge_runtime_status="source_present_gap",
            route_or_gap=(
                "The executor is a ROS/Nav2 node that requires odom, detections, action servers, and ROS topics; "
                "the JetBot factory bridge exposes HTTP camera, health, lock, and cmd_vel endpoints."
            ),
            evidence="The current bridge path reuses the command contract and relay while preserving the factory image.",
        ),
        "object_centric_fetch_policy": source_component(
            name="object_centric_fetch_policy",
            relative_path="scripts/gather_object_centric_policy_helpers.py",
            governing_symbols={
                "fetch_to_pose": "fetch_to_pose",
                "ball": "ball",
                "target": "target",
            },
            bridge_runtime_status="source_present_gap",
            route_or_gap=(
                "The policy requires measured robot, ball, and delivery target pose plus contact evidence; "
                "the current v0 bridge target is a color rectangle in a single CSI frame."
            ),
            evidence="The progress scorecard is the current safety gate until bridge observations include object pose and delivery geometry.",
        ),
    }
    sim_vs_hardware_differences = [
        {
            "area": "perception",
            "sim_stack_surface": "D415/YOLO image and 3D ball-position topics.",
            "bridge_surface": "Factory CSI camera snapshot plus color-target analysis.",
            "next_adapter": "Publish bridge-derived target observations into the same state shape as the runtime dashboard.",
        },
        {
            "area": "state",
            "sim_stack_surface": "Robot pose, ball pose, delivery pose, target freshness, and corridor geometry.",
            "bridge_surface": "Target bbox, area ratio, center error, and a placeholder robot pose in stack_state.",
            "next_adapter": "Add calibrated object-pose estimation or fiducial/marker geometry before contact-rich fetch.",
        },
        {
            "area": "execution",
            "sim_stack_surface": "BrainIntentExecutor dispatches ROS/Nav2 goals and cmd_vel topics.",
            "bridge_surface": "Runtime JSON handoff to gather_motion_bridge, ROS cmd_vel relay, and HTTP /cmd_vel.",
            "next_adapter": "Choose whether to run a ROS executor shim against bridge-backed topics or keep a direct HTTP executor for v0.",
        },
        {
            "area": "success_evidence",
            "sim_stack_surface": "Fetch-to-pose pass uses ball trajectory intersection with a delivery radius.",
            "bridge_surface": "Progress scorecard uses target area and centering after bounded pulses.",
            "next_adapter": "Track the ball and delivery marker so hardware scorecards use the fetch-to-pose contract.",
        },
    ]
    report = {
        "generated_utc": utc_now(),
        "type": "factory_bridge_real_stack_boot_report",
        "selected_entrypoint": stack_gate.POLICY_CHASECAR_STACK_FETCH_ADAPTER_V0,
        "stack_family": "planner_routed_fetch_to_pose",
        "runtime_target_reference": "robot_fidelity_orin",
        "inference_backend_reference": "tensorrt_int8",
        "bridge_safety_gate": "factory_bridge_locked_by_default_plus_progress_scorecard",
        "full_onboard_stack_booted": False,
        "claim": (
            "The live v0 hardware lane runs the shared supervisor policy through a bridge adapter and records the "
            "remaining ROS/Nav2/object-pose gaps before claiming full stack onboarding."
        ),
        "policy_smoke": policy_smoke,
        "components": components,
        "sim_vs_hardware_differences": sim_vs_hardware_differences,
        "minimum_next_adapters": [
            "Bridge-backed dashboard state for supervisor_loop.evaluate_once.",
            "Object-pose observation for ball and delivery target geometry.",
            "Executor choice between ROS topic shim and direct bridge intent executor.",
            "Fetch-to-pose hardware scorecard based on ball trajectory, delivery radius, and contact safety.",
        ],
        "pass": bool(policy_smoke.get("pass", False) and components["supervisor_policy"]["source_present"]),
    }
    return report


def real_stack_boot_report_markdown(report: dict[str, Any]) -> str:
    components = report.get("components") if isinstance(report.get("components"), dict) else {}
    lines = [
        "# Real Stack Boot Report",
        "",
        "- Pass: `%s`" % bool(report.get("pass", False)),
        "- Selected entrypoint: `%s`" % report.get("selected_entrypoint", ""),
        "- Bridge safety gate: `%s`" % report.get("bridge_safety_gate", ""),
        "- Full onboard stack booted: `%s`" % bool(report.get("full_onboard_stack_booted", False)),
        "",
        "## Policy Smoke",
        "",
    ]
    smoke = report.get("policy_smoke") if isinstance(report.get("policy_smoke"), dict) else {}
    lines.extend(
        [
            "- Stage: `%s`" % smoke.get("policy_stage", ""),
            "- Preferred intent: `%s`" % smoke.get("policy_preferred_intent", ""),
            "- Stop reason: `%s`" % smoke.get("stop_reason", ""),
            "- Command: `%s`" % json.dumps(smoke.get("command", {}), sort_keys=True),
            "",
            "## Components",
            "",
            "| Component | Source | Bridge status | Route or gap |",
            "| --- | --- | --- | --- |",
        ]
    )
    for component in components.values():
        if not isinstance(component, dict):
            continue
        lines.append(
            "| %s | `%s` | `%s` | %s |"
            % (
                component.get("name", ""),
                component.get("source_path", ""),
                component.get("bridge_runtime_status", ""),
                str(component.get("route_or_gap", "")).replace("|", "/"),
            )
        )
    lines.extend(["", "## Sim To Hardware Differences", "", "| Area | Sim stack surface | Bridge surface | Next adapter |", "| --- | --- | --- | --- |"])
    for item in report.get("sim_vs_hardware_differences", []):
        if not isinstance(item, dict):
            continue
        lines.append(
            "| %s | %s | %s | %s |"
            % (
                item.get("area", ""),
                str(item.get("sim_stack_surface", "")).replace("|", "/"),
                str(item.get("bridge_surface", "")).replace("|", "/"),
                str(item.get("next_adapter", "")).replace("|", "/"),
            )
        )
    return "\n".join(lines) + "\n"


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
    real_stack_report = build_real_stack_boot_report(args)
    real_stack_report_path = artifact_root / REAL_STACK_BOOT_REPORT_FILENAME
    real_stack_report_md_path = artifact_root / REAL_STACK_BOOT_REPORT_MD_FILENAME
    real_stack_report["json_path"] = str(real_stack_report_path)
    real_stack_report["markdown_path"] = str(real_stack_report_md_path)
    write_json(real_stack_report_path, real_stack_report)
    write_text(real_stack_report_md_path, real_stack_boot_report_markdown(real_stack_report))
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
        "real_stack_boot_report": real_stack_report,
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
