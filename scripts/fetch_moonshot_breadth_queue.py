#!/usr/bin/env python3
"""Prepare broad planner-routed fetch UAT seeds behind the regression manifest."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from datetime import timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import fetch_moonshot_regression_manifest as regression_manifest
import fetch_planner_handoff_gate as planner_gate
import fetch_planner_route_replay_batch as replay_batch
import fetch_planner_route_uat_analyzer as route_analyzer
import fetch_planner_seeded_generalization_gate as seeded_gate


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
QUEUE_KIND = "fetch_moonshot_breadth_queue"
DEFAULT_SEEDS = (20260630, 20260631, 20260632)
DEFAULT_RANDOM_CASES = 30
DEFAULT_MAX_PER_ROUTE = 2
DEFAULT_QUALITY_ORDER = "roughest"
EXECUTABLE_ROUTES = tuple(replay_batch.EXECUTABLE_ROUTES)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def resolve_path(raw_path: str | Path) -> Path:
    path = Path(str(raw_path or "").strip())
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def artifact_display_path(path: Path | str) -> str:
    path = resolve_path(path)
    try:
        return str(path.relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def float_value(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _ns(**kwargs: Any) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


def default_seeds(raw: list[int] | None) -> list[int]:
    return [int(seed) for seed in (raw or list(DEFAULT_SEEDS))]


def queue_root(campaign_id: str) -> Path:
    return SESSION_ROOT / campaign_id / QUEUE_KIND


def regression_preflight_campaign_id(campaign_id: str) -> str:
    return f"{campaign_id}_regression_preflight"


def seed_dry_campaign_id(campaign_id: str, seed: int) -> str:
    return f"{campaign_id}_seed{int(seed)}_dry"


def build_regression_args(args: argparse.Namespace) -> SimpleNamespace:
    return _ns(
        campaign_id=regression_preflight_campaign_id(str(args.campaign_id)),
        regression_set_id=str(args.regression_set_id),
        saved_anchor_summary=str(args.saved_anchor_summary),
        setup_contact_audit=str(args.setup_contact_audit),
        seeded_gate=list(args.regression_seeded_gate or []),
        boundary_replay_summary=str(args.boundary_replay_summary),
        boundary_row=list(args.boundary_row or []),
        control_preflight=list(args.control_preflight or []),
        fetch_delivery_radius_m=float(args.fetch_delivery_radius_m),
        min_random_cases=int(args.min_random_cases),
    )


def build_seeded_gate_args(args: argparse.Namespace, *, seed: int) -> SimpleNamespace:
    return _ns(
        campaign_id=seed_dry_campaign_id(str(args.campaign_id), int(seed)),
        dry_run=True,
        random_cases=max(int(args.random_cases), 1),
        seed=int(seed),
        scene_set=str(args.scene_set or planner_gate.DEFAULT_SCENE_SET),
        scene_descriptor_json=list(args.scene_descriptor_json or []),
        scene_dir=str(args.scene_dir or ""),
        planner_mode=str(args.planner_mode),
        openai_model=str(args.openai_model or planner_gate.DEFAULT_OPENAI_MODEL),
        openai_api_key=str(args.openai_api_key or ""),
        openai_base_url=str(args.openai_base_url or planner_gate.DEFAULT_OPENAI_BASE_URL),
        openai_org_id=str(args.openai_org_id or ""),
        openai_project_id=str(args.openai_project_id or ""),
        reasoning_effort=str(args.reasoning_effort or planner_gate.DEFAULT_REASONING_EFFORT),
        planner_timeout_s=float(args.planner_timeout_s),
        max_per_route=max(int(args.max_per_route), 1),
        route=list(args.route or []),
        scene_id=list(args.scene_id or []),
        skip_scene_id=list(args.skip_scene_id or []),
        quality_order=str(args.quality_order or DEFAULT_QUALITY_ORDER),
        dashboard_url=str(args.dashboard_url or ""),
        compose_project=str(args.compose_project or ""),
        fresh_dashboard_session_per_run=bool(args.fresh_dashboard_session_per_run),
        allow_operator_view_degraded=bool(args.allow_operator_view_degraded),
        world_file=str(args.world_file),
        surface_profile=str(args.surface_profile),
        robot_sdf_name=str(args.robot_sdf_name),
        env_ready_timeout_s=float(args.env_ready_timeout_s),
        env_stop_timeout_s=float(args.env_stop_timeout_s),
        fetch_delivery_radius_m=float(args.fetch_delivery_radius_m),
        python_exe=str(args.python_exe or sys.executable),
        timeout_s=float(args.timeout_s),
        package_timeout_s=float(args.package_timeout_s),
        no_visual_package=bool(args.no_visual_package),
        resume_skip_existing=False,
        stop_on_fail=False,
    )


def run_regression_preflight(args: argparse.Namespace) -> dict[str, Any]:
    regression_args = build_regression_args(args)
    root = ensure_dir(SESSION_ROOT / str(regression_args.campaign_id) / regression_manifest.MANIFEST_KIND)
    summary = regression_manifest.build_summary(regression_args)
    summary_path = root / "regression_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["summary_path"] = artifact_display_path(summary_path)
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    regression_manifest.write_json(summary_path, summary)
    regression_manifest.write_scorecard(scorecard_path, summary)
    return summary


def run_seed_dry_gate(args: argparse.Namespace, *, seed: int) -> dict[str, Any]:
    return seeded_gate.run_gate(build_seeded_gate_args(args, seed=int(seed)))


def replay_payload_for(seed_summary: dict[str, Any]) -> dict[str, Any]:
    replay_path = str(seed_summary.get("replay_summary_path", "") or "").strip()
    return read_json(resolve_path(replay_path)) if replay_path else {}


def route_risk_weight(risk: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(str(risk or "").lower(), 0)


def quality_score(row: dict[str, Any]) -> float:
    quality = dict_value(row.get("route_quality"))
    return float_value(quality.get("quality_score"), 100.0)


def summarize_selected_rows(rows: list[Any]) -> dict[str, Any]:
    selected: list[dict[str, Any]] = [row for row in rows if isinstance(row, dict)]
    route_counts = {route: sum(1 for row in selected if row.get("route_label") == route) for route in EXECUTABLE_ROUTES}
    risk_counts = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
    watch_count = 0
    roughness_points = 0.0
    selected_scenes: list[dict[str, Any]] = []
    for row in selected:
        quality = dict_value(row.get("route_quality"))
        risk = str(quality.get("predicted_first_contact_risk", "") or "").lower()
        if risk not in risk_counts:
            risk = "unknown"
        risk_counts[risk] += 1
        predicted_contact = str(quality.get("predicted_contact_quality", "") or "")
        if predicted_contact == "watch" or risk in {"high", "medium"}:
            watch_count += 1
        score = quality_score(row)
        roughness_points += max(0.0, 100.0 - score)
        selected_scenes.append(
            {
                "scene_id": str(row.get("scene_id", "") or ""),
                "route_label": str(row.get("route_label", "") or ""),
                "quality_score": round(score, 3),
                "predicted_contact_quality": predicted_contact,
                "predicted_first_contact_risk": risk,
                "flags": list_value(quality.get("flags")),
                "setup_debt": dict_value(quality.get("setup_debt")),
            }
        )
    return {
        "selected_count": len(selected),
        "selected_route_counts": route_counts,
        "selected_route_coverage_count": sum(1 for count in route_counts.values() if count > 0),
        "risk_counts": risk_counts,
        "watch_count": watch_count,
        "roughness_points": round(roughness_points, 3),
        "selected_scenes": selected_scenes,
    }


def evaluate_seed_candidate(
    seed_summary: dict[str, Any],
    replay_payload: dict[str, Any],
    *,
    max_per_route: int,
    random_cases: int,
) -> dict[str, Any]:
    planner_summary = dict_value(seed_summary.get("planner_summary"))
    replay_summary = dict_value(seed_summary.get("replay_summary"))
    rows_summary = summarize_selected_rows(list_value(replay_payload.get("rows")))
    selected_route_counts = dict_value(rows_summary.get("selected_route_counts"))
    route_counts = dict_value(planner_summary.get("route_counts"))
    expected_count = max(int_value(seed_summary.get("expected_executable_count")), len(EXECUTABLE_ROUTES) * max(int(max_per_route), 1))
    issues: list[str] = []
    if not bool(seed_summary.get("pass", False)):
        issues.append("dry_gate_not_pass")
    if not bool(seed_summary.get("dry_run", False)):
        issues.append("seed_gate_not_dry_run")
    if int_value(seed_summary.get("random_cases")) < int(random_cases):
        issues.append("random_cases_below_requested")
    if int_value(planner_summary.get("pass_count")) < int(random_cases):
        issues.append("planner_pass_count_below_requested")
    if int_value(planner_summary.get("wrong_fetch_dispatch_count")) != 0:
        issues.append("wrong_fetch_dispatch")
    if int_value(replay_summary.get("selected_count")) < expected_count:
        issues.append("selected_count_below_expected")
    if rows_summary["selected_count"] < expected_count:
        issues.append("replay_rows_below_expected")
    for route in EXECUTABLE_ROUTES:
        if int_value(selected_route_counts.get(route)) < int(max_per_route):
            issues.append(f"selected_route_below_{max_per_route}:{route}")
    route_spread_count = sum(1 for count in route_counts.values() if int_value(count) > 0)
    breadth_score = round(
        (route_spread_count * 1000.0)
        + (rows_summary["selected_route_coverage_count"] * 300.0)
        + (rows_summary["watch_count"] * 25.0)
        + (rows_summary["risk_counts"].get("high", 0) * 60.0)
        + (rows_summary["risk_counts"].get("medium", 0) * 20.0)
        + rows_summary["roughness_points"],
        3,
    )
    return {
        "seed": seed_summary.get("seed"),
        "campaign_id": str(seed_summary.get("campaign_id", "") or ""),
        "pass": not issues,
        "issues": issues,
        "breadth_score": breadth_score,
        "planner_pass_count": int_value(planner_summary.get("pass_count")),
        "wrong_fetch_dispatch_count": int_value(planner_summary.get("wrong_fetch_dispatch_count")),
        "route_counts": route_counts,
        "route_spread_count": route_spread_count,
        "expected_executable_count": expected_count,
        "replay_summary_path": str(seed_summary.get("replay_summary_path", "") or ""),
        "gate_summary_path": str(seed_summary.get("summary_path", "") or ""),
        "scorecard_path": str(seed_summary.get("scorecard_path", "") or ""),
        **rows_summary,
    }


def live_command_for_seed(args: argparse.Namespace, *, seed: int) -> str:
    live_campaign_id = f"live_planner_seeded_generalization_gate_seed{int(seed)}_breadth_{current_utc_stamp()}"
    parts = [
        "python",
        r"scripts\fetch_planner_seeded_generalization_gate.py",
        "--campaign-id",
        live_campaign_id,
        "--random-cases",
        str(max(int(args.random_cases), 1)),
        "--seed",
        str(int(seed)),
        "--max-per-route",
        str(max(int(args.max_per_route), 1)),
        "--quality-order",
        str(args.quality_order or DEFAULT_QUALITY_ORDER),
        "--fresh-dashboard-session-per-run",
        "--dashboard-url",
        str(args.dashboard_url or "http://127.0.0.1:8879"),
        "--stop-on-fail",
    ]
    if bool(args.allow_operator_view_degraded):
        parts.append("--allow-operator-view-degraded")
    return " ".join(parts)


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    campaign_id = str(args.campaign_id or "").strip() or f"fetch_moonshot_breadth_queue_{current_utc_stamp()}"
    args.campaign_id = campaign_id
    seeds = default_seeds(list(args.seed or []))
    regression_summary = run_regression_preflight(args)
    candidates: list[dict[str, Any]] = []
    for seed in seeds:
        seed_summary = run_seed_dry_gate(args, seed=int(seed))
        candidate = evaluate_seed_candidate(
            seed_summary,
            replay_payload_for(seed_summary),
            max_per_route=max(int(args.max_per_route), 1),
            random_cases=max(int(args.random_cases), 1),
        )
        candidates.append(candidate)
    ready_candidates = [row for row in candidates if bool(row.get("pass", False))]
    ready_candidates.sort(key=lambda row: (-float_value(row.get("breadth_score")), int_value(row.get("seed"))))
    recommended = ready_candidates[0] if ready_candidates else {}
    pass_queue = bool(regression_summary.get("pass", False) and ready_candidates)
    return {
        "generated_utc": utc_now(),
        "type": QUEUE_KIND,
        "campaign_id": campaign_id,
        "pass": pass_queue,
        "promotion_evidence": False,
        "milestone_interpretation": (
            "planner_routed_broad_uat_seed_ready"
            if pass_queue
            else "planner_routed_broad_uat_seed_queue_incomplete"
        ),
        "random_cases": max(int(args.random_cases), 1),
        "max_per_route": max(int(args.max_per_route), 1),
        "quality_order": str(args.quality_order or DEFAULT_QUALITY_ORDER),
        "regression_preflight_pass": bool(regression_summary.get("pass", False)),
        "regression_preflight_path": str(regression_summary.get("summary_path", "") or ""),
        "regression_preflight_scorecard_path": str(regression_summary.get("scorecard_path", "") or ""),
        "candidate_count": len(candidates),
        "ready_candidate_count": len(ready_candidates),
        "recommended_seed": recommended.get("seed", ""),
        "recommended_breadth_score": recommended.get("breadth_score", 0),
        "recommended_live_command": live_command_for_seed(args, seed=int_value(recommended.get("seed"))) if recommended else "",
        "seed_candidates": sorted(candidates, key=lambda row: (-float_value(row.get("breadth_score")), int_value(row.get("seed")))),
    }


def artifact_link(path: str) -> str:
    return f"[artifact](/{path})" if str(path).startswith("artifacts/session/") else str(path)


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Fetch Moonshot Breadth Queue",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        f"- random_cases: `{summary.get('random_cases', '')}`",
        f"- max_per_route: `{summary.get('max_per_route', '')}`",
        f"- quality_order: `{summary.get('quality_order', '')}`",
        f"- regression_preflight_pass: `{summary.get('regression_preflight_pass', False)}` {artifact_link(str(summary.get('regression_preflight_scorecard_path', '') or summary.get('regression_preflight_path', '')))}",
        f"- ready_candidate_count: `{summary.get('ready_candidate_count', 0)}/{summary.get('candidate_count', 0)}`",
        f"- recommended_seed: `{summary.get('recommended_seed', '')}`",
        "",
        "## Recommended Live Command",
        "",
        "```powershell",
        str(summary.get("recommended_live_command", "") or "# no ready seed candidate"),
        "```",
        "",
        "## Candidate Seeds",
        "",
    ]
    for row in list_value(summary.get("seed_candidates")):
        risk_counts = dict_value(row.get("risk_counts"))
        selected_counts = dict_value(row.get("selected_route_counts"))
        lines.append(
            f"- seed=`{row.get('seed', '')}` pass=`{row.get('pass', False)}` "
            f"score=`{row.get('breadth_score', 0)}` routes=`{row.get('route_spread_count', 0)}` "
            f"selected=`{selected_counts}` risk=`{risk_counts}` "
            f"wrong_fetch=`{row.get('wrong_fetch_dispatch_count', 0)}` "
            f"issues=`{row.get('issues', [])}` {artifact_link(str(row.get('scorecard_path', '') or row.get('gate_summary_path', '')))}"
        )
        for scene in list_value(row.get("selected_scenes"))[:6]:
            lines.append(
                f"  - `{scene.get('scene_id', '')}` route=`{scene.get('route_label', '')}` "
                f"score=`{scene.get('quality_score', '')}` risk=`{scene.get('predicted_first_contact_risk', '')}` "
                f"flags=`{scene.get('flags', [])}`"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare broad planner-routed fetch UAT seed candidates.")
    parser.add_argument("--campaign-id", default=f"fetch_moonshot_breadth_queue_{current_utc_stamp()}")
    parser.add_argument("--seed", action="append", type=int, default=[])
    parser.add_argument("--random-cases", type=int, default=DEFAULT_RANDOM_CASES)
    parser.add_argument("--max-per-route", type=int, default=DEFAULT_MAX_PER_ROUTE)
    parser.add_argument("--quality-order", choices=("source", "cleanest", "roughest"), default=DEFAULT_QUALITY_ORDER)
    parser.add_argument("--dashboard-url", default="http://127.0.0.1:8879")
    parser.add_argument("--compose-project", default="")
    parser.add_argument("--allow-operator-view-degraded", action="store_true")
    parser.add_argument("--fresh-dashboard-session-per-run", action="store_true", default=True)
    parser.add_argument("--scene-set", default=planner_gate.DEFAULT_SCENE_SET)
    parser.add_argument("--scene-descriptor-json", action="append", default=[])
    parser.add_argument("--scene-dir", default="")
    parser.add_argument("--planner-mode", choices=(planner_gate.PLANNER_MODE_DETERMINISTIC, planner_gate.PLANNER_MODE_LLM_SHADOW), default=planner_gate.PLANNER_MODE_DETERMINISTIC)
    parser.add_argument("--openai-model", default=planner_gate.DEFAULT_OPENAI_MODEL)
    parser.add_argument("--openai-api-key", default="")
    parser.add_argument("--openai-base-url", default=planner_gate.DEFAULT_OPENAI_BASE_URL)
    parser.add_argument("--openai-org-id", default="")
    parser.add_argument("--openai-project-id", default="")
    parser.add_argument("--reasoning-effort", default=planner_gate.DEFAULT_REASONING_EFFORT)
    parser.add_argument("--planner-timeout-s", type=float, default=45.0)
    parser.add_argument("--route", action="append", choices=EXECUTABLE_ROUTES, default=[])
    parser.add_argument("--scene-id", action="append", default=[])
    parser.add_argument("--skip-scene-id", action="append", default=[])
    parser.add_argument("--world-file", default="yolo_test_world_v6_calibrated_golf_turf.world")
    parser.add_argument("--surface-profile", default="calibrated_golf_turf")
    parser.add_argument("--robot-sdf-name", default="jetbot_core_ignition_v1.7.0.sdf")
    parser.add_argument("--env-ready-timeout-s", type=float, default=replay_batch.DEFAULT_ENV_READY_TIMEOUT_S)
    parser.add_argument("--env-stop-timeout-s", type=float, default=90.0)
    parser.add_argument("--fetch-delivery-radius-m", type=float, default=0.300)
    parser.add_argument("--python-exe", default=sys.executable)
    parser.add_argument("--timeout-s", type=float, default=180.0)
    parser.add_argument("--package-timeout-s", type=float, default=180.0)
    parser.add_argument("--no-visual-package", action="store_true")
    parser.add_argument("--regression-set-id", default=regression_manifest.DEFAULT_REGRESSION_SET_ID)
    parser.add_argument("--saved-anchor-summary", default=regression_manifest.DEFAULT_SAVED_ANCHOR_SUMMARY)
    parser.add_argument("--setup-contact-audit", default=regression_manifest.DEFAULT_SETUP_CONTACT_AUDIT)
    parser.add_argument("--regression-seeded-gate", action="append", default=[])
    parser.add_argument("--boundary-replay-summary", default=regression_manifest.DEFAULT_BOUNDARY_REPLAY_SUMMARY)
    parser.add_argument("--boundary-row", action="append", default=[])
    parser.add_argument("--control-preflight", action="append", default=[])
    parser.add_argument("--min-random-cases", type=int, default=30)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ensure_dir(queue_root(str(args.campaign_id)))
    summary = build_summary(args)
    summary_path = root / "breadth_queue_summary.json"
    scorecard_path = root / "scorecard.md"
    summary["summary_path"] = artifact_display_path(summary_path)
    summary["scorecard_path"] = artifact_display_path(scorecard_path)
    write_json(summary_path, summary)
    write_scorecard(scorecard_path, summary)
    print(f"FETCH_MOONSHOT_BREADTH_QUEUE_SUMMARY={summary_path}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
