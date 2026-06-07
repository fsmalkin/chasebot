#!/usr/bin/env python3
"""Roll up multi-ball retrieval UAT evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
ROLLUP_KIND = "fetch_multiball_uat_rollup"
LOCAL_SETUP_ROUTE = "local_setup_capture"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_path(path_text: str | Path) -> Path:
    path = Path(str(path_text or "").strip())
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def artifact_display_path(path_text: str | Path) -> str:
    path = resolve_path(path_text)
    try:
        return str(path.relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def read_json(path_text: str | Path) -> dict[str, Any]:
    path = resolve_path(path_text)
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def number_value(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def command_has_flag(row: dict[str, Any], flag: str) -> bool:
    return flag in [str(item) for item in list_value(row.get("command"))]


def step_fetch_pass(row: dict[str, Any]) -> bool:
    mission = dict_value(row.get("mission"))
    return bool(mission.get("fetch_to_pose_pass", False))


def step_handoff_pass(row: dict[str, Any]) -> bool:
    mission = dict_value(row.get("mission"))
    if not bool(mission.get("measured_push_ready_handoff_required", False)):
        return True
    return bool(mission.get("measured_push_ready_handoff_pass", False))


def step_hidden_nav2(row: dict[str, Any]) -> bool:
    if str(row.get("route_label", "") or "") != LOCAL_SETUP_ROUTE:
        return False
    mission = dict_value(row.get("mission"))
    return bool(
        command_has_flag(row, "--nav2-reposition-before-fetch")
        or mission.get("pre_fetch_reposition_attempted", False)
        or mission.get("planner_route_executed", False)
    )


def sequence_decision_evidence(plan: dict[str, Any]) -> dict[tuple[str, int, str], dict[str, Any]]:
    scene_id = str(plan.get("scene_id", "") or "")
    evidence_by_key: dict[tuple[str, int, str], dict[str, Any]] = {}
    for index, step in enumerate(list_value(plan.get("sequence")), start=1):
        if not isinstance(step, dict):
            continue
        ball_id = str(step.get("ball_id", "") or "")
        decision = dict_value(step.get("decision"))
        guard = dict_value(decision.get("llm_supervised_guard"))
        attempts = list_value(decision.get("provider_attempts"))
        provider_status = str(guard.get("provider_status", "") or "")
        if not provider_status and attempts:
            provider_status = str(dict_value(attempts[-1]).get("status", "") or "")
        if not provider_status:
            provider_status = "not_used"
        provider_attempt_count = len(attempts)
        if provider_attempt_count <= 0 and provider_status != "not_used":
            provider_attempt_count = 1
        evidence_by_key[(scene_id, index, ball_id)] = {
            "planner_mode": decision.get("planner_mode") or plan.get("planner_mode") or "",
            "planner_mode_effective": decision.get("planner_mode_effective") or plan.get("planner_mode") or "",
            "provider_status": provider_status,
            "provider_error": decision.get("provider_error", ""),
            "provider_attempt_count": provider_attempt_count,
            "guard_agrees": bool(decision.get("guard_agrees", True)),
            "guard_accepted": bool(guard.get("accepted", decision.get("guard_agrees", True))),
            "guard_decision": guard.get("decision", ""),
            "guard_route_label": decision.get("guard_route_label", guard.get("guard_route_label", "")),
            "llm_route_label": decision.get("llm_route_label", ""),
            "llm_confidence": decision.get("llm_confidence", decision.get("confidence")),
            "confidence": decision.get("confidence"),
            "rationale_short": decision.get("llm_rationale_short", decision.get("rationale_short", "")),
        }
    return evidence_by_key


def selected_planner_evidence(summary: dict[str, Any]) -> dict[tuple[str, int, str], dict[str, Any]]:
    evidence: dict[tuple[str, int, str], dict[str, Any]] = {}
    for scene in list_value(summary.get("scene_rows")):
        if not isinstance(scene, dict):
            continue
        plan_path = str(scene.get("sequence_plan_path", "") or "")
        if not plan_path:
            continue
        evidence.update(sequence_decision_evidence(read_json(plan_path)))
    return evidence


def visual_links(visual_package: dict[str, Any], dashboard_base_url: str) -> list[dict[str, Any]]:
    base = str(dashboard_base_url or "").rstrip("/")
    rows: list[dict[str, Any]] = []
    for video in list_value(visual_package.get("videos")):
        if not isinstance(video, dict) or not bool(video.get("browser_playable", False)):
            continue
        url = str(video.get("url", "") or "")
        path = str(video.get("path", "") or "")
        full_url = f"{base}{url}" if base and url.startswith("/") else url
        rows.append(
            {
                "role": video.get("role", ""),
                "name": video.get("name", ""),
                "path": path,
                "url": full_url,
                "duration_s": video.get("duration_s"),
                "size_bytes": video.get("size_bytes"),
            }
        )
    for review in list_value(visual_package.get("keyframe_reviews")):
        if not isinstance(review, dict) or not bool(review.get("ok", False)):
            continue
        url = str(review.get("url", "") or "")
        rows.append(
            {
                "role": "frame_sequence_review",
                "name": review.get("output_name", "keyframe_review_contact_sheet.png"),
                "path": review.get("path", ""),
                "url": f"{base}{url}" if base and url.startswith("/") else url,
                "selected_count": review.get("selected_count"),
                "selected_frame_ids": review.get("selected_frame_ids", []),
            }
        )
    role_order = {
        "onboard_camera": 0,
        "frame_sequence_review": 1,
        "external_context": 2,
    }
    return sorted(rows, key=lambda item: (role_order.get(str(item.get("role", "")), 9), str(item.get("name", ""))))


def stage_label_for_step(row: dict[str, Any], planner_evidence: dict[str, Any]) -> str:
    mission = dict_value(row.get("mission"))
    provider_status = str(planner_evidence.get("provider_status", "") or "not_used")
    if provider_status not in ("", "not_used", "ok"):
        return "planning"
    if bool(planner_evidence.get("guard_agrees", True)) is False or bool(planner_evidence.get("guard_accepted", True)) is False:
        return "planning"
    if step_hidden_nav2(row):
        return "setup"
    if not step_fetch_pass(row):
        text = " ".join(
            str(value or "")
            for value in [
                row.get("failure_reason", ""),
                mission.get("outcome_reason", ""),
                mission.get("measured_push_ready_handoff_reason", ""),
                mission.get("pre_fetch_reposition_error", ""),
                mission.get("pre_fetch_reposition_dispatch_status", ""),
            ]
        ).lower()
        if "nav2" in text or "reposition" in text:
            return "setup"
        if "capture" in text or "contact" in text or "handoff" in text:
            return "capture"
        if "closest" in text or "delivery" in text or "terminal" in text:
            return "terminal_arrival"
        return "recovery"
    contact_flags = list_value(mission.get("contact_quality_flags")) + list_value(mission.get("first_contact_quality_flags"))
    if contact_flags:
        return "push_contact_quality_watch"
    return "complete"


def summarize_step(
    row: dict[str, Any],
    *,
    planner_evidence: dict[str, Any],
    gate_path: Path,
    gate_dry_run: bool,
) -> dict[str, Any]:
    mission = dict_value(row.get("mission"))
    closest = number_value(mission.get("closest_approach_distance_m"))
    contact_flags = list_value(mission.get("contact_quality_flags")) + list_value(mission.get("first_contact_quality_flags"))
    return {
        "scene_id": row.get("scene_id", ""),
        "step_index": row.get("step_index", 0),
        "ball_id": row.get("ball_id", ""),
        "route_label": row.get("route_label", ""),
        "route_executor": row.get("route_executor", ""),
        "fetch_to_pose_pass": step_fetch_pass(row),
        "measured_push_ready_handoff_pass": step_handoff_pass(row),
        "closest_approach_distance_m": closest,
        "outcome_reason": mission.get("outcome_reason", ""),
        "contact_quality_flags": [str(flag) for flag in contact_flags],
        "hidden_nav2_prefetch": step_hidden_nav2(row),
        "stage_label": stage_label_for_step(row, planner_evidence),
        "planner_evidence": planner_evidence,
        "mission_summary_path": row.get("mission_summary_path", ""),
        "layout_path": row.get("layout_path", ""),
        "gate_summary_path": artifact_display_path(gate_path),
        "gate_dry_run": bool(gate_dry_run),
    }


def summarize_gate(path: Path, *, dashboard_base_url: str) -> dict[str, Any]:
    summary = read_json(path)
    evidence_by_key = selected_planner_evidence(summary)
    step_rows: list[dict[str, Any]] = []
    for row in list_value(summary.get("step_rows")):
        if not isinstance(row, dict):
            continue
        key = (str(row.get("scene_id", "") or ""), int(row.get("step_index", 0) or 0), str(row.get("ball_id", "") or ""))
        step_rows.append(
            summarize_step(
                row,
                planner_evidence=evidence_by_key.get(key, {}),
                gate_path=path,
                gate_dry_run=bool(summary.get("dry_run", False)),
            )
        )
    visual_package = dict_value(summary.get("visual_package"))
    return {
        "campaign_id": summary.get("campaign_id", ""),
        "gate_summary_path": artifact_display_path(path),
        "scorecard_path": summary.get("scorecard_path", ""),
        "pass": bool(summary.get("pass", False)),
        "dry_run": bool(summary.get("dry_run", False)),
        "profile": summary.get("profile", ""),
        "planner_mode": summary.get("planner_mode", ""),
        "scene_count": summary.get("scene_count", 0),
        "planned_step_count": summary.get("planned_step_count", 0),
        "expected_session_id": summary.get("expected_session_id", ""),
        "visual_package_pass": bool(summary.get("visual_package_pass", False)),
        "visual_package_effective_pass": bool(summary.get("visual_package_effective_pass", False)),
        "multiball_visual_evidence_pass": bool(summary.get("multiball_visual_evidence_pass", False)),
        "visual_package_summary_path": summary.get("visual_package_summary_path", ""),
        "scene_rows": [
            {
                "scene_id": scene.get("scene_id", ""),
                "pass": bool(scene.get("pass", False)),
                "ball_count": scene.get("ball_count", 0),
                "retrieval_order": scene.get("retrieval_order", []),
                "planner_ready": bool(scene.get("planner_ready", False)),
                "fetch_to_pose_pass_count": scene.get("fetch_to_pose_pass_count", 0),
                "fetch_to_pose_fail_count": scene.get("fetch_to_pose_fail_count", 0),
                "sequence_plan_path": scene.get("sequence_plan_path", ""),
            }
            for scene in list_value(summary.get("scene_rows"))
            if isinstance(scene, dict)
        ],
        "step_rows": step_rows,
        "video_links": visual_links(visual_package, dashboard_base_url),
    }


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        label = str(row.get(key, "") or "")
        counts[label] = counts.get(label, 0) + 1
    return counts


def aggregate_provider_status(step_rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in step_rows:
        evidence = dict_value(row.get("planner_evidence"))
        status = str(evidence.get("provider_status", "") or "not_used")
        counts[status] = counts.get(status, 0) + 1
    return counts


def summarize_rollup(args: argparse.Namespace) -> dict[str, Any]:
    gate_paths = [resolve_path(path) for path in list_value(args.gate_summary)]
    gates = [summarize_gate(path, dashboard_base_url=str(args.dashboard_base_url or "")) for path in gate_paths]
    all_steps = [step for gate in gates for step in list_value(gate.get("step_rows")) if isinstance(step, dict)]
    all_scenes = [scene for gate in gates for scene in list_value(gate.get("scene_rows")) if isinstance(scene, dict)]
    live_gates = [gate for gate in gates if not bool(gate.get("dry_run", False))]
    live_steps = [step for step in all_steps if not bool(step.get("gate_dry_run", False))]
    llm_supervised_gates = [
        gate for gate in live_gates if str(gate.get("planner_mode", "") or "").startswith("llm_supervised")
    ]
    hidden_nav2_steps = [step for step in all_steps if bool(step.get("hidden_nav2_prefetch", False))]
    step_failures = [step for step in all_steps if not bool(step.get("fetch_to_pose_pass", False))]
    handoff_failures = [step for step in all_steps if not bool(step.get("measured_push_ready_handoff_pass", False))]
    visual_failures = [
        gate
        for gate in live_gates
        if not bool(gate.get("visual_package_effective_pass", False))
        or not bool(gate.get("multiball_visual_evidence_pass", False))
    ]
    provider_problems = [
        step
        for step in all_steps
        if str(dict_value(step.get("planner_evidence")).get("provider_status", "") or "") not in ("", "not_used", "ok")
        or bool(dict_value(step.get("planner_evidence")).get("guard_agrees", True)) is False
        or bool(dict_value(step.get("planner_evidence")).get("guard_accepted", True)) is False
    ]
    provider_retry_count = sum(
        1
        for step in all_steps
        if int(dict_value(step.get("planner_evidence")).get("provider_attempt_count", 0) or 0) > 1
    )
    issues: list[str] = []
    if not gates:
        issues.append("no_gate_summaries")
    if len(live_gates) < int(args.min_live_gates):
        issues.append("live_gate_count_below_minimum")
    if len(all_scenes) < int(args.min_scenes):
        issues.append("scene_count_below_minimum")
    if len(live_steps) < int(args.min_steps):
        issues.append("live_step_count_below_minimum")
    if len(llm_supervised_gates) < int(args.min_llm_supervised_gates):
        issues.append("llm_supervised_gate_count_below_minimum")
    if any(not bool(gate.get("pass", False)) for gate in gates):
        issues.append("gate_failures_remain")
    if step_failures:
        issues.append("step_failures_remain")
    if handoff_failures:
        issues.append("measured_push_ready_handoff_failures_remain")
    if visual_failures:
        issues.append("visual_package_failures_remain")
    if hidden_nav2_steps:
        issues.append("hidden_nav2_prefetch_in_local_setup")
    if provider_problems:
        issues.append("planner_provider_or_guard_problems")
    pass_value = not issues
    return {
        "generated_utc": utc_now(),
        "type": ROLLUP_KIND,
        "campaign_id": str(args.campaign_id),
        "gate_summary_paths": [artifact_display_path(path) for path in gate_paths],
        "dashboard_base_url": str(args.dashboard_base_url or ""),
        "pass": pass_value,
        "promotion_evidence": False,
        "milestone_interpretation": (
            "multiball_llm_supervised_visual_uat_green_not_promotion"
            if pass_value
            else "multiball_llm_supervised_visual_uat_has_gaps"
        ),
        "gate_count": len(gates),
        "live_gate_count": len(live_gates),
        "llm_supervised_live_gate_count": len(llm_supervised_gates),
        "scene_count": len(all_scenes),
        "live_step_count": len(live_steps),
        "step_count": len(all_steps),
        "fetch_to_pose_pass_count": sum(1 for step in all_steps if bool(step.get("fetch_to_pose_pass", False))),
        "fetch_to_pose_fail_count": len(step_failures),
        "measured_push_ready_handoff_fail_count": len(handoff_failures),
        "hidden_nav2_prefetch_count": len(hidden_nav2_steps),
        "planner_provider_problem_count": len(provider_problems),
        "provider_retry_count": provider_retry_count,
        "route_counts": count_by(all_steps, "route_label"),
        "route_executor_counts": count_by(all_steps, "route_executor"),
        "planner_mode_counts": count_by(gates, "planner_mode"),
        "provider_status_counts": aggregate_provider_status(all_steps),
        "stage_label_counts": count_by(all_steps, "stage_label"),
        "min_live_gates": int(args.min_live_gates),
        "min_scenes": int(args.min_scenes),
        "min_steps": int(args.min_steps),
        "min_llm_supervised_gates": int(args.min_llm_supervised_gates),
        "issues": issues,
        "next_recommended_rung": (
            "run_a_broader_supervised_live_batch_with_route_diversity_then_seeded_gate"
            if pass_value
            else "repair_the_first_reported_gap_before_more_broadening"
        ),
        "gates": gates,
        "steps": all_steps,
        "visual_proof": [
            {
                "campaign_id": gate.get("campaign_id", ""),
                "expected_session_id": gate.get("expected_session_id", ""),
                "links": gate.get("video_links", []),
            }
            for gate in gates
        ],
    }


def markdown_link(label: str, url: str) -> str:
    return f"[{label}]({url})" if url else label


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Multi-Ball UAT Rollup",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        f"- live_gate_count: `{summary.get('live_gate_count', 0)}`",
        f"- llm_supervised_live_gate_count: `{summary.get('llm_supervised_live_gate_count', 0)}`",
        f"- scene_count: `{summary.get('scene_count', 0)}`",
        f"- live_step_count: `{summary.get('live_step_count', 0)}`",
        f"- fetch_to_pose_pass_count: `{summary.get('fetch_to_pose_pass_count', 0)}`",
        f"- fetch_to_pose_fail_count: `{summary.get('fetch_to_pose_fail_count', 0)}`",
        f"- hidden_nav2_prefetch_count: `{summary.get('hidden_nav2_prefetch_count', 0)}`",
        f"- planner_provider_problem_count: `{summary.get('planner_provider_problem_count', 0)}`",
        f"- provider_retry_count: `{summary.get('provider_retry_count', 0)}`",
        f"- route_counts: `{summary.get('route_counts', {})}`",
        f"- route_executor_counts: `{summary.get('route_executor_counts', {})}`",
        f"- provider_status_counts: `{summary.get('provider_status_counts', {})}`",
        f"- stage_label_counts: `{summary.get('stage_label_counts', {})}`",
        f"- issues: `{summary.get('issues', [])}`",
        f"- next_recommended_rung: `{summary.get('next_recommended_rung', '')}`",
        "",
        "## Visual Proof",
        "",
        "| Campaign | Session | Onboard | Topdown | World | Keyframes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for proof in list_value(summary.get("visual_proof")):
        links = [link for link in list_value(proof.get("links")) if isinstance(link, dict)]
        onboard = next((link for link in links if link.get("role") == "onboard_camera"), {})
        topdown = next(
            (link for link in links if link.get("role") == "external_context" and "topdown" in str(link.get("name", ""))),
            {},
        )
        world = next(
            (link for link in links if link.get("role") == "external_context" and "world" in str(link.get("name", ""))),
            {},
        )
        keyframes = next((link for link in links if link.get("role") == "frame_sequence_review"), {})
        lines.append(
            f"| `{proof.get('campaign_id', '')}` | `{proof.get('expected_session_id', '')}` | "
            f"{markdown_link('onboard', str(onboard.get('url', '') or ''))} | "
            f"{markdown_link('topdown', str(topdown.get('url', '') or ''))} | "
            f"{markdown_link('world', str(world.get('url', '') or ''))} | "
            f"{markdown_link('keyframes', str(keyframes.get('url', '') or ''))} |"
        )
    lines.extend(
        [
            "",
            "## Gate Results",
            "",
            "| Campaign | Pass | Planner | Visual | Multi-ball visual | Steps |",
            "| --- | --- | --- | --- | --- | ---: |",
        ]
    )
    for gate in list_value(summary.get("gates")):
        lines.append(
            f"| `{gate.get('campaign_id', '')}` | `{gate.get('pass', False)}` | "
            f"`{gate.get('planner_mode', '')}` | `{gate.get('visual_package_effective_pass', False)}` | "
            f"`{gate.get('multiball_visual_evidence_pass', False)}` | `{gate.get('planned_step_count', 0)}` |"
        )
    lines.extend(
        [
            "",
            "## Step Results",
            "",
            "| Scene | Step | Ball | Route | Executor | Pass | Handoff | Closest | Stage | Provider |",
            "| --- | ---: | --- | --- | --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for step in list_value(summary.get("steps")):
        evidence = dict_value(step.get("planner_evidence"))
        lines.append(
            f"| `{step.get('scene_id', '')}` | `{step.get('step_index', '')}` | `{step.get('ball_id', '')}` | "
            f"`{step.get('route_label', '')}` | `{step.get('route_executor', '')}` | "
            f"`{step.get('fetch_to_pose_pass', False)}` | `{step.get('measured_push_ready_handoff_pass', False)}` | "
            f"`{step.get('closest_approach_distance_m', '')}` | `{step.get('stage_label', '')}` | "
            f"`{evidence.get('provider_status', '')}` |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Roll up multi-ball retrieval UAT evidence.")
    parser.add_argument("--campaign-id", default=f"multiball_uat_rollup_{current_utc_stamp()}")
    parser.add_argument("--gate-summary", action="append", required=True)
    parser.add_argument("--dashboard-base-url", default="")
    parser.add_argument("--min-live-gates", type=int, default=2)
    parser.add_argument("--min-scenes", type=int, default=2)
    parser.add_argument("--min-steps", type=int, default=6)
    parser.add_argument("--min-llm-supervised-gates", type=int, default=2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(SESSION_ROOT / str(args.campaign_id) / ROLLUP_KIND)
    summary = summarize_rollup(args)
    summary["summary_path"] = artifact_display_path(root / "multiball_uat_summary.json")
    summary["scorecard_path"] = artifact_display_path(root / "scorecard.md")
    write_json(root / "multiball_uat_summary.json", summary)
    write_scorecard(root / "scorecard.md", summary)
    print(f"FETCH_MULTIBALL_UAT_ROLLUP_SUMMARY={root / 'multiball_uat_summary.json'}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
