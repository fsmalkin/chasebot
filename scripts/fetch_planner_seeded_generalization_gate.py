#!/usr/bin/env python3
"""Canonical seeded generalization gate for planner-routed fetch."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from datetime import timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import fetch_planner_handoff_gate as planner_gate
import fetch_planner_route_replay_batch as replay_batch
import fetch_planner_route_uat_analyzer as route_analyzer


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
GATE_KIND = "fetch_planner_seeded_generalization_gate"
DEFAULT_RANDOM_CASES = 30
DEFAULT_SEED = 20260627
DEFAULT_MAX_PER_ROUTE = 2
EXPECTED_EXECUTABLE_ROUTES = tuple(replay_batch.EXECUTABLE_ROUTES)


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def artifact_display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def gate_root(campaign_id: str) -> Path:
    return SESSION_ROOT / campaign_id / GATE_KIND


def planner_summary_path(campaign_id: str) -> Path:
    return SESSION_ROOT / campaign_id / planner_gate.PLANNER_GATE_KIND / "gate_summary.json"


def replay_summary_path(campaign_id: str) -> Path:
    return SESSION_ROOT / campaign_id / replay_batch.BATCH_KIND / "batch_summary.json"


def analyzer_summary_path(campaign_id: str) -> Path:
    return SESSION_ROOT / campaign_id / route_analyzer.ANALYZER_KIND / "route_uat_summary.json"


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _ns(**kwargs: Any) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


def build_planner_args(args: argparse.Namespace, *, campaign_id: str) -> SimpleNamespace:
    return _ns(
        campaign_id=campaign_id,
        scene_set=str(args.scene_set or planner_gate.DEFAULT_SCENE_SET),
        scene_descriptor_json=list(args.scene_descriptor_json or []),
        scene_dir=str(args.scene_dir or ""),
        random_cases=max(int(args.random_cases), 1),
        seed=int(args.seed),
        planner_mode=str(args.planner_mode),
        dry_run=bool(args.dry_run),
        openai_model=str(args.openai_model or planner_gate.DEFAULT_OPENAI_MODEL),
        openai_api_key=str(args.openai_api_key or ""),
        openai_base_url=str(args.openai_base_url or planner_gate.DEFAULT_OPENAI_BASE_URL),
        openai_org_id=str(args.openai_org_id or ""),
        openai_project_id=str(args.openai_project_id or ""),
        reasoning_effort=str(args.reasoning_effort or planner_gate.DEFAULT_REASONING_EFFORT),
        timeout_s=float(args.planner_timeout_s),
    )


def build_replay_args(args: argparse.Namespace, *, campaign_id: str, gate_summary: Path) -> SimpleNamespace:
    return _ns(
        campaign_id=campaign_id,
        gate_summary=str(gate_summary),
        route=list(args.route or []),
        scene_id=list(args.scene_id or []),
        skip_scene_id=list(args.skip_scene_id or []),
        max_per_route=max(int(args.max_per_route), 1),
        quality_order=str(args.quality_order or "source"),
        dry_run=bool(args.dry_run),
        dashboard_url=str(args.dashboard_url or ""),
        compose_project=str(args.compose_project or ""),
        fresh_dashboard_session_per_run=bool(args.fresh_dashboard_session_per_run),
        allow_operator_view_degraded=bool(getattr(args, "allow_operator_view_degraded", False)),
        world_file=str(args.world_file or "yolo_test_world_v6_calibrated_golf_turf.world"),
        surface_profile=str(args.surface_profile or "calibrated_golf_turf"),
        robot_sdf_name=str(args.robot_sdf_name or "jetbot_core_ignition_v1.7.0.sdf"),
        env_ready_timeout_s=float(args.env_ready_timeout_s),
        env_stop_timeout_s=float(args.env_stop_timeout_s),
        fetch_delivery_radius_m=float(args.fetch_delivery_radius_m),
        python_exe=str(args.python_exe or sys.executable),
        timeout_s=float(args.timeout_s),
        package_timeout_s=float(args.package_timeout_s),
        no_visual_package=bool(args.no_visual_package),
        resume_skip_existing=bool(args.resume_skip_existing),
        stop_on_fail=bool(args.stop_on_fail),
    )


def analyzer_inputs_from_replay(replay_summary: dict[str, Any]) -> tuple[list[str], list[str]]:
    mission_paths: list[str] = []
    package_paths: list[str] = []
    rows = replay_summary.get("rows") if isinstance(replay_summary.get("rows"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        mission_path = str(row.get("mission_summary_path", "") or "").strip()
        package_path = str(row.get("visual_package_summary_path", "") or "").strip()
        if mission_path:
            mission_paths.append(mission_path)
        if package_path:
            package_paths.append(package_path)
    return mission_paths, package_paths


def build_analyzer_args(
    args: argparse.Namespace,
    *,
    campaign_id: str,
    planner_summary: Path,
    replay_summary: dict[str, Any],
) -> SimpleNamespace:
    mission_paths, package_paths = analyzer_inputs_from_replay(replay_summary)
    return _ns(
        campaign_id=campaign_id,
        evidence_scope=route_analyzer.SCOPE_ROUTE_OWNER_VISUAL_UAT,
        repeatability_runs_per_anchor=3,
        planner_summary=[str(planner_summary)],
        mission_summary=mission_paths,
        visual_package_summary=package_paths,
    )


def run_analyzer(args: argparse.Namespace, *, campaign_id: str, planner_summary: Path, replay_summary: dict[str, Any]) -> dict[str, Any]:
    analyzer_args = build_analyzer_args(
        args,
        campaign_id=campaign_id,
        planner_summary=planner_summary,
        replay_summary=replay_summary,
    )
    root = ensure_dir(SESSION_ROOT / campaign_id / route_analyzer.ANALYZER_KIND)
    summary = route_analyzer.build_summary(analyzer_args)
    summary_path = root / "route_uat_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["summary_path"] = artifact_display_path(summary_path)
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    route_analyzer.write_json(summary_path, summary)
    route_analyzer.write_scorecard(scorecard_path, summary)
    return summary


def expected_executable_count(args: argparse.Namespace) -> int:
    routes = tuple(args.route or EXPECTED_EXECUTABLE_ROUTES)
    executable_routes = [route for route in routes if route in EXPECTED_EXECUTABLE_ROUTES]
    return max(int(args.max_per_route), 1) * len(executable_routes)


def promotion_ready(
    *,
    args: argparse.Namespace,
    planner_summary: dict[str, Any],
    replay_summary: dict[str, Any],
    analyzer_summary: dict[str, Any],
) -> bool:
    selected_count = int(replay_summary.get("selected_count", 0) or 0)
    expected_count = expected_executable_count(args)
    return bool(
        not bool(args.dry_run)
        and not bool(args.no_visual_package)
        and not list(args.route or [])
        and bool(args.fresh_dashboard_session_per_run)
        and bool(planner_summary.get("pass", False))
        and bool(replay_summary.get("pass", False))
        and bool(analyzer_summary.get("pass", False))
        and selected_count >= expected_count
        and int(replay_summary.get("mission_pass_count", 0) or 0) == selected_count
        and int(replay_summary.get("visual_package_pass_count", 0) or 0) == selected_count
        and str(analyzer_summary.get("execution_quality_status", "")) == "clean"
        and str(analyzer_summary.get("setup_quality_status", "")) == "clean"
        and str(analyzer_summary.get("contact_quality_status", "")) == "clean"
        and int(analyzer_summary.get("first_contact_blocker_count", 0) or 0) == 0
    )


def first_replay_failure(replay_summary: dict[str, Any]) -> dict[str, Any]:
    rows = replay_summary.get("rows") if isinstance(replay_summary.get("rows"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        mission = row.get("mission") if isinstance(row.get("mission"), dict) else {}
        visual_package = row.get("visual_package") if isinstance(row.get("visual_package"), dict) else {}
        failed = bool(
            str(row.get("failure_reason", "") or "").strip()
            or (row.get("returncode") not in {None, 0})
            or (mission and not bool(mission.get("pass", False)))
            or (visual_package and not bool(visual_package.get("pass", False)))
        )
        if failed:
            return {
                "scene_id": str(row.get("scene_id", "") or ""),
                "route_label": str(row.get("route_label", "") or ""),
                "returncode": row.get("returncode"),
                "failure_reason": str(row.get("failure_reason", "") or ""),
                "expected_session_id": str(row.get("expected_session_id", "") or ""),
            }
    return {}


def interpretation_for(summary: dict[str, Any]) -> str:
    if bool(summary.get("promotion_evidence", False)):
        return "planner_routed_seeded_generalization_promotion_green"
    if bool(summary.get("dry_run", False)) and bool(summary.get("planner_gate_pass", False)) and bool(summary.get("replay_pass", False)):
        return "planner_routed_seeded_generalization_dry_run_ready"
    if bool(summary.get("analyzer_pass", False)):
        return "planner_routed_seeded_generalization_visual_uat_green"
    return "planner_routed_seeded_generalization_incomplete"


def run_gate(args: argparse.Namespace) -> dict[str, Any]:
    campaign_id = str(args.campaign_id or "").strip() or f"live_fetch_planner_seeded_generalization_gate_{current_utc_stamp()}"
    root = ensure_dir(gate_root(campaign_id))
    planner_campaign_id = f"{campaign_id}_planner"
    replay_campaign_id = f"{campaign_id}_replay"
    analyzer_campaign_id = f"{campaign_id}_analysis"

    planner_summary = planner_gate.run_gate(build_planner_args(args, campaign_id=planner_campaign_id))
    planner_path = planner_summary_path(planner_campaign_id)
    replay_summary = replay_batch.run_batch(
        build_replay_args(args, campaign_id=replay_campaign_id, gate_summary=planner_path)
    )
    analyzer_summary: dict[str, Any] = {}
    if not bool(args.dry_run):
        analyzer_summary = run_analyzer(
            args,
            campaign_id=analyzer_campaign_id,
            planner_summary=planner_path,
            replay_summary=replay_summary,
        )

    promotion_evidence = promotion_ready(
        args=args,
        planner_summary=planner_summary,
        replay_summary=replay_summary,
        analyzer_summary=analyzer_summary,
    )
    gate_pass = bool(
        planner_summary.get("pass", False)
        and replay_summary.get("pass", False)
        and (bool(args.dry_run) or analyzer_summary.get("pass", False))
    )
    summary = {
        "generated_utc": utc_now(),
        "type": GATE_KIND,
        "campaign_id": campaign_id,
        "dry_run": bool(args.dry_run),
        "seed": int(args.seed),
        "random_cases": max(int(args.random_cases), 1),
        "max_per_route": max(int(args.max_per_route), 1),
        "expected_executable_count": expected_executable_count(args),
        "fresh_dashboard_session_per_run": bool(args.fresh_dashboard_session_per_run),
        "planner_mode": str(args.planner_mode),
        "pass": gate_pass,
        "promotion_evidence": promotion_evidence,
        "milestone_interpretation": "",
        "planner_gate_pass": bool(planner_summary.get("pass", False)),
        "replay_pass": bool(replay_summary.get("pass", False)),
        "analyzer_pass": bool(analyzer_summary.get("pass", False)) if analyzer_summary else False,
        "analyzer_ran": bool(analyzer_summary),
        "planner_campaign_id": planner_campaign_id,
        "replay_campaign_id": replay_campaign_id,
        "analyzer_campaign_id": analyzer_campaign_id if analyzer_summary else "",
        "planner_summary_path": artifact_display_path(planner_path),
        "replay_summary_path": artifact_display_path(replay_summary_path(replay_campaign_id)),
        "analyzer_summary_path": artifact_display_path(analyzer_summary_path(analyzer_campaign_id)) if analyzer_summary else "",
        "planner_scorecard_path": artifact_display_path(planner_path.with_name("scorecard.md")),
        "replay_scorecard_path": artifact_display_path(replay_summary_path(replay_campaign_id).with_name("scorecard.md")),
        "analyzer_scorecard_path": artifact_display_path(analyzer_summary_path(analyzer_campaign_id).with_name("scorecard.md")) if analyzer_summary else "",
        "planner_summary": {
            "pass_count": planner_summary.get("pass_count", 0),
            "fail_count": planner_summary.get("fail_count", 0),
            "wrong_fetch_dispatch_count": planner_summary.get("wrong_fetch_dispatch_count", 0),
            "route_counts": planner_summary.get("route_counts", {}),
        },
        "replay_summary": {
            "selected_count": replay_summary.get("selected_count", 0),
            "mission_pass_count": replay_summary.get("mission_pass_count", 0),
            "mission_fail_count": replay_summary.get("mission_fail_count", 0),
            "visual_package_pass_count": replay_summary.get("visual_package_pass_count", 0),
            "requested_route_count": replay_summary.get("requested_route_count", {}),
        },
        "replay_first_failure": first_replay_failure(replay_summary),
        "analyzer_summary": {
            "milestone_interpretation": analyzer_summary.get("milestone_interpretation", ""),
            "execution_quality_status": analyzer_summary.get("execution_quality_status", ""),
            "setup_quality_status": analyzer_summary.get("setup_quality_status", ""),
            "contact_quality_status": analyzer_summary.get("contact_quality_status", ""),
            "first_contact_blocker_count": analyzer_summary.get("first_contact_blocker_count", 0),
        } if analyzer_summary else {},
    }
    summary["milestone_interpretation"] = interpretation_for(summary)
    summary["summary_path"] = artifact_display_path(root / "gate_summary.json")
    summary["scorecard_path"] = artifact_display_path(root / "scorecard.md")
    write_json(root / "gate_summary.json", summary)
    write_scorecard(root / "scorecard.md", summary)
    return summary


def artifact_link(path: str) -> str:
    return f"[summary](/{path})" if str(path).startswith("artifacts/session/") else str(path)


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    lines = [
        "# Fetch Planner Seeded Generalization Gate",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- dry_run: `{summary.get('dry_run', False)}`",
        f"- seed: `{summary.get('seed', '')}`",
        f"- random_cases: `{summary.get('random_cases', '')}`",
        f"- max_per_route: `{summary.get('max_per_route', '')}`",
        f"- expected_executable_count: `{summary.get('expected_executable_count', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        "",
        "## Child Evidence",
        "",
        f"- planner_gate pass=`{summary.get('planner_gate_pass', False)}` {artifact_link(str(summary.get('planner_scorecard_path', '') or summary.get('planner_summary_path', '')))}",
        f"- replay_batch pass=`{summary.get('replay_pass', False)}` {artifact_link(str(summary.get('replay_scorecard_path', '') or summary.get('replay_summary_path', '')))}",
        (
            f"- route_analyzer pass=`{summary.get('analyzer_pass', False)}` "
            f"{artifact_link(str(summary.get('analyzer_scorecard_path', '') or summary.get('analyzer_summary_path', '')))}"
            if summary.get("analyzer_ran", False)
            else "- route_analyzer: `skipped_dry_run`"
        ),
        "",
        "## Summary",
        "",
        f"- planner: `{summary.get('planner_summary', {})}`",
        f"- replay: `{summary.get('replay_summary', {})}`",
        f"- analyzer: `{summary.get('analyzer_summary', {})}`",
    ]
    if summary.get("replay_first_failure"):
        lines.extend(
            [
                "",
                "## First Replay Failure",
                "",
                f"- `{summary.get('replay_first_failure', {})}`",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the planner-routed seeded fetch generalization gate.")
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--random-cases", type=int, default=DEFAULT_RANDOM_CASES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--scene-set", default=planner_gate.DEFAULT_SCENE_SET)
    parser.add_argument("--scene-descriptor-json", action="append", default=[])
    parser.add_argument("--scene-dir", default="")
    parser.add_argument("--planner-mode", choices=(planner_gate.PLANNER_MODE_DETERMINISTIC, planner_gate.PLANNER_MODE_LLM_SHADOW), default=planner_gate.PLANNER_MODE_DETERMINISTIC)
    parser.add_argument("--openai-model", default=planner_gate.DEFAULT_OPENAI_MODEL)
    parser.add_argument("--openai-api-key", default=os.environ.get("OPENAI_API_KEY", ""))
    parser.add_argument("--openai-base-url", default=os.environ.get("OPENAI_BASE_URL", planner_gate.DEFAULT_OPENAI_BASE_URL))
    parser.add_argument("--openai-org-id", default=os.environ.get("OPENAI_ORG_ID", ""))
    parser.add_argument("--openai-project-id", default=os.environ.get("OPENAI_PROJECT_ID", ""))
    parser.add_argument("--reasoning-effort", default=planner_gate.DEFAULT_REASONING_EFFORT)
    parser.add_argument("--planner-timeout-s", type=float, default=45.0)
    parser.add_argument("--max-per-route", type=int, default=DEFAULT_MAX_PER_ROUTE)
    parser.add_argument("--route", action="append", choices=EXPECTED_EXECUTABLE_ROUTES, default=[])
    parser.add_argument("--scene-id", action="append", default=[])
    parser.add_argument("--skip-scene-id", action="append", default=[])
    parser.add_argument("--quality-order", choices=("source", "cleanest", "roughest"), default="source")
    parser.add_argument("--dashboard-url", default="http://127.0.0.1:8879")
    parser.add_argument("--compose-project", default="")
    parser.add_argument("--fresh-dashboard-session-per-run", action="store_true")
    parser.add_argument(
        "--allow-operator-view-degraded",
        action="store_true",
        help="Allow fresh dashboard sessions to proceed when the Xpra operator view is degraded but recorded visual evidence can still be produced.",
    )
    parser.add_argument("--world-file", default="yolo_test_world_v6_calibrated_golf_turf.world")
    parser.add_argument("--surface-profile", default="calibrated_golf_turf")
    parser.add_argument("--robot-sdf-name", default="jetbot_core_ignition_v1.7.0.sdf")
    parser.add_argument("--env-ready-timeout-s", type=float, default=540.0)
    parser.add_argument("--env-stop-timeout-s", type=float, default=90.0)
    parser.add_argument("--fetch-delivery-radius-m", type=float, default=0.300)
    parser.add_argument("--python-exe", default=sys.executable)
    parser.add_argument("--timeout-s", type=float, default=180.0)
    parser.add_argument("--package-timeout-s", type=float, default=180.0)
    parser.add_argument("--no-visual-package", action="store_true")
    parser.add_argument("--resume-skip-existing", action="store_true")
    parser.add_argument("--stop-on-fail", action="store_true")
    return parser.parse_args()


def main() -> int:
    summary = run_gate(parse_args())
    print(f"FETCH_PLANNER_SEEDED_GENERALIZATION_GATE_SUMMARY={SESSION_ROOT / summary['campaign_id'] / GATE_KIND / 'gate_summary.json'}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
