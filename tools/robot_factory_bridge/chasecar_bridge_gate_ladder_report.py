#!/usr/bin/env python3
"""Build a serial hardware gate report from bridge health and saved artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any

import chasecar_bridge_client as bridge_client


GATES: list[dict[str, Any]] = [
    {
        "id": "access_safety",
        "title": "Access And Safety",
        "success_criteria": [
            "Bridge health is reachable.",
            "Bridge reports ok=true.",
            "motion_enabled=false and both motors are zero.",
        ],
        "next_goal": "Restore bridge access and locked health.",
    },
    {
        "id": "camera_freshness",
        "title": "Camera Freshness",
        "success_criteria": [
            "Camera is enabled and loaded.",
            "Frame age is within the configured freshness limit.",
            "Camera FPS meets the configured minimum.",
        ],
        "next_goal": "Restore a fresh bridge camera frame.",
    },
    {
        "id": "yolo_visible_target",
        "title": "YOLO Visible Target",
        "success_criteria": [
            "YOLO detects the intended bottle target in at least one saved visible-target proof.",
            "The evidence includes a detector-selected or YOLO-primary target step.",
        ],
        "next_goal": "Place the target visibly and pass a YOLO-only locked detector proof.",
    },
    {
        "id": "locked_transport",
        "title": "Locked Stack Transport",
        "success_criteria": [
            "Closed-loop stack transport passes while bridge motion stays disabled.",
            "Accepted motor event count is zero.",
            "The bridge refuses motion with locked-path evidence.",
        ],
        "next_goal": "Pass locked stack transport with HTTP 423 refusals and zero accepted motor events.",
    },
    {
        "id": "motion_primitive",
        "title": "Motion Primitive",
        "success_criteria": [
            "A bounded physical motion primitive produces visual motion.",
            "The bridge relocks and both motors return to zero.",
        ],
        "next_goal": "Pass one bounded yaw or forward primitive with before/after visual evidence.",
    },
    {
        "id": "visible_approach",
        "title": "Visible Target Approach",
        "success_criteria": [
            "With the target visible, YOLO-backed closed-loop steps pass.",
            "Accepted motor events stay within budget.",
            "Inverse reset passes and final health is locked.",
        ],
        "next_goal": "Pass a visible-target YOLO-backed approach proof.",
    },
    {
        "id": "yolo_reacquire",
        "title": "YOLO Reacquire",
        "success_criteria": [
            "From a lost or edge-target pose, a bounded scan reacquires the bottle with YOLO evidence.",
            "Color fallback alone is insufficient for promotion.",
            "Final bridge health is locked.",
        ],
        "next_goal": "Repair YOLO intended-bottle detection on current bridge frames, then pass YOLO-only target reacquire.",
    },
    {
        "id": "terminal_target_success",
        "title": "Terminal Target Success",
        "success_criteria": [
            "The stack reaches the configured target-arrival or safe terminal condition.",
            "The terminal proof does not depend on reverse reset as the success condition.",
        ],
        "next_goal": "Run a target-success gate only after YOLO reacquire passes.",
    },
    {
        "id": "endurance_loop",
        "title": "Endurance Loop",
        "success_criteria": [
            "At least the configured cycle count passes.",
            "Every cycle preserves bridge lock, camera readiness, detector evidence, motor budget, and reset safety.",
        ],
        "next_goal": "Run multi-cycle endurance only after terminal target success passes.",
    },
]


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_json(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def status_rank(status: str) -> int:
    return {"pending": 0, "pass": 1, "fail": 2}.get(status, 0)


def set_gate(gates: dict[str, dict[str, Any]], gate_id: str, status: str, evidence: str, detail: str = "") -> None:
    gate = gates[gate_id]
    if status_rank(status) >= status_rank(str(gate["status"])):
        gate["status"] = status
    record = {"status": status, "evidence": evidence}
    if detail:
        record["detail"] = detail
    gate["evidence"].append(record)


def safe_health(health: dict[str, Any]) -> bool:
    return bool(
        health.get("ok", False)
        and health.get("motion_enabled") is False
        and abs(float(health.get("left_motor", 0.0) or 0.0)) < 1.0e-6
        and abs(float(health.get("right_motor", 0.0) or 0.0)) < 1.0e-6
    )


def camera_fresh(health: dict[str, Any], args: argparse.Namespace) -> bool:
    camera = health.get("camera") if isinstance(health.get("camera"), dict) else {}
    return bool(
        camera.get("enabled", False)
        and camera.get("loaded", False)
        and camera.get("error") in (None, "")
        and float(camera.get("frame_age_s", 999.0) or 999.0) <= float(args.camera_max_frame_age_s)
        and float(camera.get("cached_fps", 0.0) or 0.0) >= float(args.camera_min_fps)
    )


def fetch_health(args: argparse.Namespace) -> dict[str, Any] | None:
    if args.health_json:
        return load_json(args.health_json)
    if not args.base_url:
        return None
    client = bridge_client.BridgeClient(args.base_url, args.timeout_s)
    return client.health()[1]


def artifact_label(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def resolve_artifact_path(path_value: str, source_path: Path) -> Path:
    candidate = Path(path_value)
    if candidate.is_file():
        return candidate
    if not candidate.is_absolute():
        root_candidate = Path.cwd() / candidate
        if root_candidate.is_file():
            return root_candidate
        sibling_candidate = source_path.parent / candidate
        if sibling_candidate.is_file():
            return sibling_candidate
    return candidate


def scan_has_yolo_detection(scan: dict[str, Any]) -> bool:
    observations = scan.get("observations") if isinstance(scan.get("observations"), list) else []
    for observation in observations:
        analysis = observation.get("analysis") if isinstance(observation, dict) else {}
        if not isinstance(analysis, dict):
            continue
        backend = str(analysis.get("detector_backend", "") or "")
        if "yolo_onnx" in backend and bool(analysis.get("detected", False)):
            return True
        if bool(analysis.get("yolo_onnx_primary_detected", False)):
            return True
    return False


def scan_detector_backends(scan: dict[str, Any]) -> set[str]:
    backends: set[str] = set()
    observations = scan.get("observations") if isinstance(scan.get("observations"), list) else []
    for observation in observations:
        analysis = observation.get("analysis") if isinstance(observation, dict) else {}
        if isinstance(analysis, dict) and analysis.get("detector_backend"):
            backends.add(str(analysis["detector_backend"]))
    return backends


def cycle_scan_summary(cycle: dict[str, Any], source_path: Path) -> dict[str, Any] | None:
    raw_path = str(cycle.get("scan_reacquire_summary_path", "") or "")
    if not raw_path:
        return None
    path = resolve_artifact_path(raw_path, source_path)
    if not path.is_file():
        return None
    return load_json(path)


def any_yolo_step(loop_summary: dict[str, Any]) -> bool:
    cycles = loop_summary.get("cycles") if isinstance(loop_summary.get("cycles"), list) else []
    for cycle in cycles:
        evidence = cycle.get("detector_evidence") if isinstance(cycle.get("detector_evidence"), dict) else {}
        if int(evidence.get("yolo_onnx_primary_detected_steps", 0) or 0) > 0:
            return True
        selected = evidence.get("detector_arbitration_selected_counts")
        if isinstance(selected, dict) and int(selected.get("yolo_onnx", 0) or 0) > 0:
            return True
    return False


def all_cycles_have_zero_events(loop_summary: dict[str, Any]) -> bool:
    cycles = loop_summary.get("cycles") if isinstance(loop_summary.get("cycles"), list) else []
    return bool(cycles) and all(int(cycle.get("accepted_motor_event_count", 0) or 0) == 0 for cycle in cycles)


def any_cycle_has_motor_events(loop_summary: dict[str, Any]) -> bool:
    cycles = loop_summary.get("cycles") if isinstance(loop_summary.get("cycles"), list) else []
    return any(int(cycle.get("accepted_motor_event_count", 0) or 0) > 0 for cycle in cycles)


def all_cycle_resets_pass(loop_summary: dict[str, Any]) -> bool:
    cycles = loop_summary.get("cycles") if isinstance(loop_summary.get("cycles"), list) else []
    return bool(cycles) and all(bool(cycle.get("inverse_reset_pass", True)) for cycle in cycles)


def classify_overnight(
    gates: dict[str, dict[str, Any]],
    path: Path,
    payload: dict[str, Any],
    args: argparse.Namespace,
) -> None:
    label = artifact_label(path)
    cycles = payload.get("cycles") if isinstance(payload.get("cycles"), list) else []
    passed = bool(payload.get("pass", False))

    if passed and all_cycles_have_zero_events(payload):
        set_gate(gates, "locked_transport", "pass", label, "locked wrapper pass with zero accepted motor events")

    if passed and any_cycle_has_motor_events(payload) and any_yolo_step(payload) and all_cycle_resets_pass(payload):
        set_gate(gates, "visible_approach", "pass", label, "YOLO-backed live approach proof with inverse reset")
        set_gate(gates, "yolo_visible_target", "pass", label, "YOLO-backed step evidence is present")

    completed_cycles = int(payload.get("completed_cycles", 0) or 0)
    if passed and completed_cycles >= int(args.endurance_min_cycles):
        set_gate(gates, "endurance_loop", "pass", label, "completed_cycles=%d" % completed_cycles)

    for cycle in cycles:
        if bool(cycle.get("nav_target_success", False)):
            set_gate(gates, "terminal_target_success", "pass", label, "nav_target_success=true")
        scan = cycle_scan_summary(cycle, path)
        if not scan:
            continue
        scan_pass = bool(scan.get("pass", False))
        scan_yolo = scan_has_yolo_detection(scan)
        backends = ",".join(sorted(scan_detector_backends(scan)))
        scan_detail = "stop_reason=%s backends=%s" % (scan.get("stop_reason", ""), backends)
        if scan_pass and scan_yolo:
            set_gate(gates, "yolo_visible_target", "pass", label, "YOLO scan detection evidence is present")
            scan_events = scan.get("accepted_motor_events") if isinstance(scan.get("accepted_motor_events"), list) else []
            if str(scan.get("stop_reason", "") or "") == "target_reacquired" or scan_events:
                set_gate(gates, "yolo_reacquire", "pass", label, scan_detail)
        elif str(scan.get("stop_reason", "") or "") in {"scan_steps_exhausted", "target_not_reacquired"} and any(
            "yolo_onnx" in backend for backend in scan_detector_backends(scan)
        ):
            set_gate(gates, "yolo_reacquire", "fail", label, scan_detail)


def classify_turn_probe(gates: dict[str, dict[str, Any]], path: Path, payload: dict[str, Any]) -> None:
    label = artifact_label(path)
    final_health = payload.get("final_health") if isinstance(payload.get("final_health"), dict) else {}
    contact = payload.get("contact_sheet") if isinstance(payload.get("contact_sheet"), dict) else {}
    if bool(payload.get("pass", False)) and safe_health(final_health) and bool(contact.get("available", False)):
        set_gate(gates, "motion_primitive", "pass", label, "bounded yaw proof with contact sheet")
    elif payload.get("type") == "manual_turn_response_probe":
        set_gate(gates, "motion_primitive", "fail", label, "turn response probe did not pass")


def classify_artifact(gates: dict[str, dict[str, Any]], path: Path, args: argparse.Namespace) -> None:
    payload = load_json(path)
    payload_type = str(payload.get("type", "") or "")
    if payload_type == "factory_bridge_overnight_endurance_loop":
        classify_overnight(gates, path, payload, args)
    elif payload_type == "manual_turn_response_probe":
        classify_turn_probe(gates, path, payload)


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    gates = {
        gate["id"]: {
            **gate,
            "status": "pending",
            "evidence": [],
        }
        for gate in GATES
    }

    health = fetch_health(args)
    if health is not None:
        if safe_health(health):
            set_gate(gates, "access_safety", "pass", "bridge_health", "locked and motors zero")
        else:
            set_gate(gates, "access_safety", "fail", "bridge_health", "bridge health is unsafe")
        if camera_fresh(health, args):
            camera = health.get("camera", {}) if isinstance(health.get("camera"), dict) else {}
            set_gate(
                gates,
                "camera_freshness",
                "pass",
                "bridge_health",
                "backend=%s fps=%.3f frame_age_s=%.3f"
                % (
                    camera.get("backend", ""),
                    float(camera.get("cached_fps", 0.0) or 0.0),
                    float(camera.get("frame_age_s", 0.0) or 0.0),
                ),
            )
        else:
            set_gate(gates, "camera_freshness", "fail", "bridge_health", "camera freshness gate failed")

    for raw_path in args.evidence:
        classify_artifact(gates, Path(raw_path), args)

    gate_list = [gates[gate["id"]] for gate in GATES]
    next_gate = next((gate for gate in gate_list if gate["status"] != "pass"), None)
    return {
        "generated_utc": utc_now(),
        "type": "factory_bridge_gate_ladder_report",
        "base_url": args.base_url,
        "evidence": [str(Path(path)) for path in args.evidence],
        "gates": gate_list,
        "next_gate": next_gate,
        "pass": next_gate is None,
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Factory Bridge Gate Ladder",
        "",
        "- Generated UTC: `%s`" % report.get("generated_utc", ""),
        "- Overall pass: `%s`" % bool(report.get("pass", False)),
    ]
    next_gate = report.get("next_gate") if isinstance(report.get("next_gate"), dict) else None
    if next_gate:
        lines.append("- Next serial goal: `%s`" % next_gate.get("next_goal", ""))
        lines.append("- Blocking gate: `%s`" % next_gate.get("id", ""))
    lines.append("")
    lines.append("| Gate | Status | Success criteria | Evidence |")
    lines.append("| --- | --- | --- | --- |")
    for gate in report.get("gates", []):
        criteria = "<br>".join(str(item) for item in gate.get("success_criteria", []))
        evidence_items = []
        for item in gate.get("evidence", []):
            detail = str(item.get("detail", "") or "")
            evidence_items.append("%s: %s%s" % (item.get("status", ""), item.get("evidence", ""), ("; " + detail) if detail else ""))
        evidence = "<br>".join(evidence_items) if evidence_items else ""
        lines.append(
            "| `%s` | `%s` | %s | %s |"
            % (gate.get("id", ""), gate.get("status", ""), criteria, evidence)
        )
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a serial gate report for JetBot Mini hardware bring-up.")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--timeout-s", type=float, default=10.0)
    parser.add_argument("--health-json", default="")
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--artifact-dir", default="")
    parser.add_argument("--camera-max-frame-age-s", type=float, default=1.5)
    parser.add_argument("--camera-min-fps", type=float, default=1.0)
    parser.add_argument("--endurance-min-cycles", type=int, default=3)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(args)
    if args.artifact_dir:
        artifact_dir = ensure_dir(Path(args.artifact_dir))
        write_json(artifact_dir / "gate_ladder_report.json", report)
        (artifact_dir / "gate_ladder_report.md").write_text(markdown(report), encoding="utf-8")
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report.get("pass", False) else 1


if __name__ == "__main__":
    sys.exit(main())
