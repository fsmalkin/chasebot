#!/usr/bin/env python3
"""Replay executable planner-routed fetch scenes as visual UAT batches."""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

import fetch_planner_handoff_gate as planner_gate


REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
BATCH_KIND = "fetch_planner_route_replay_batch"
EXECUTABLE_ROUTES = (
    planner_gate.ROUTE_FETCH_READY,
    planner_gate.ROUTE_NAV2_REPOSITION,
    planner_gate.ROUTE_RECOVERY_OR_REAIM,
)
PLANNER_ONLY_ROUTES = (
    planner_gate.ROUTE_SCAN_OR_PERCEIVE,
    planner_gate.ROUTE_NO_GO,
)
REPLAY_ROUTES = EXECUTABLE_ROUTES + PLANNER_ONLY_ROUTES
MISSION_SUMMARY_MARKER = "GATHER_MISSION_SUMMARY="
VISUAL_PACKAGE_MARKER = "FETCH_VISUAL_UAT_PACKAGE_SUMMARY="
DEFAULT_ENV_READY_TIMEOUT_S = 600.0


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def dashboard_api_url(dashboard_url: str, path: str) -> str:
    return str(dashboard_url or "").rstrip("/") + "/" + path.lstrip("/")


def dashboard_state(dashboard_url: str, *, timeout_s: float = 20.0) -> dict[str, Any]:
    if not str(dashboard_url or "").strip():
        return {}
    try:
        with urllib.request.urlopen(dashboard_api_url(dashboard_url, "/api/state"), timeout=max(float(timeout_s), 1.0)) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload if isinstance(payload, dict) else {}
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        return {}


def post_dashboard_json(dashboard_url: str, path: str, payload: dict[str, Any] | None = None, *, timeout_s: float = 30.0) -> dict[str, Any]:
    if not str(dashboard_url or "").strip():
        return {"ok": False, "error": "missing_dashboard_url"}
    body = json.dumps(payload or {}).encode("utf-8")
    request = urllib.request.Request(
        dashboard_api_url(dashboard_url, path),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=max(float(timeout_s), 1.0)) as response:
            parsed = json.loads(response.read().decode("utf-8"))
            return parsed if isinstance(parsed, dict) else {"ok": True}
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc)}


def wait_for_dashboard_state(
    dashboard_url: str,
    *,
    timeout_s: float,
    poll_s: float = 5.0,
    want_ready: bool = False,
    want_stopped: bool = False,
    allow_operator_view_degraded: bool = False,
) -> dict[str, Any]:
    deadline = time.monotonic() + max(float(timeout_s), 1.0)
    last_state: dict[str, Any] = {}
    while time.monotonic() < deadline:
        state = dashboard_state(dashboard_url, timeout_s=min(max(float(poll_s), 1.0), 20.0))
        if state:
            last_state = state
            env_state = str(state.get("environment_state", "") or "")
            phase = str(state.get("phase", "") or "")
            ready = bool(
                env_state == "environment_ready"
                and phase == "environment_ready"
                and state.get("sim_gate_ready")
                and operator_view_acceptable(
                    state,
                    allow_operator_view_degraded=allow_operator_view_degraded,
                )
            )
            stopped = env_state in {"stopped", "error"} or phase == "stopped"
            if want_ready and env_state == "error":
                return state
            if (want_ready and ready) or (want_stopped and stopped):
                return state
            if not want_ready and not want_stopped:
                return state
        time.sleep(max(float(poll_s), 0.2))
    return last_state


def stop_dashboard_environment(dashboard_url: str, *, timeout_s: float) -> dict[str, Any]:
    response = post_dashboard_json(dashboard_url, "/api/env/stop", {}, timeout_s=30.0)
    state = wait_for_dashboard_state(dashboard_url, timeout_s=timeout_s, want_stopped=True)
    return {"request": response, "state": state}


def start_dashboard_environment(args: argparse.Namespace) -> dict[str, Any]:
    body = {
        "world_file": str(args.world_file or ""),
        "surface_profile": str(args.surface_profile or ""),
        "robot_sdf_name": str(args.robot_sdf_name or ""),
        "operator_view_required": not bool(getattr(args, "allow_operator_view_degraded", False)),
        "visual_evidence_required": not bool(getattr(args, "no_visual_package", False)),
    }
    attempts: list[dict[str, Any]] = []
    max_attempts = max(int(getattr(args, "env_start_attempts", 1) or 1), 1)
    dashboard_url = str(args.dashboard_url or "")
    for attempt_index in range(1, max_attempts + 1):
        response = post_dashboard_json(dashboard_url, "/api/env/start", body, timeout_s=60.0)
        state = wait_for_dashboard_state(
            dashboard_url,
            timeout_s=float(args.env_ready_timeout_s),
            poll_s=5.0,
            want_ready=True,
            allow_operator_view_degraded=bool(getattr(args, "allow_operator_view_degraded", False)),
        )
        attempt = {"index": attempt_index, "request": response, "state": state}
        attempts.append(attempt)
        if dashboard_environment_ready(
            state,
            allow_operator_view_degraded=bool(getattr(args, "allow_operator_view_degraded", False)),
        ):
            return {"request": response, "state": state, "attempts": attempts}
        if attempt_index < max_attempts:
            attempt["stop_after_failed_start"] = stop_dashboard_environment(
                dashboard_url,
                timeout_s=float(args.env_stop_timeout_s),
            )
    last = attempts[-1] if attempts else {"request": {}, "state": {}}
    return {"request": last.get("request", {}), "state": last.get("state", {}), "attempts": attempts}


def resolve_path(raw_path: str) -> Path:
    path = Path(str(raw_path or "").strip())
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def artifact_display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return cleaned.strip("_") or "scene"


def _extract_marker(output: str, marker: str) -> str:
    for line in str(output or "").splitlines():
        if marker in line:
            return line.split(marker, 1)[1].strip()
    return ""


def dashboard_start_failure_reason(dashboard_start: dict[str, Any]) -> str:
    state = dashboard_start.get("state") if isinstance(dashboard_start.get("state"), dict) else {}
    request = dashboard_start.get("request") if isinstance(dashboard_start.get("request"), dict) else {}
    reason_parts = ["fresh_dashboard_session_start_failed"]
    for key in ("environment_state", "phase", "last_error"):
        value = str(state.get(key, "") or "").strip()
        if value:
            reason_parts.append(f"{key}={value}")
    request_error = str(request.get("error", "") or "").strip()
    if request_error:
        reason_parts.append(f"request_error={request_error}")
    return "; ".join(reason_parts)


def operator_view_acceptable(state: dict[str, Any], *, allow_operator_view_degraded: bool = False) -> bool:
    if bool(state.get("operator_view_ready", False)):
        return True
    if not allow_operator_view_degraded:
        return False
    if bool(state.get("operator_view_required", True)):
        return False
    return str(state.get("operator_view_status", "") or "") in {
        "degraded",
        "degraded_optional",
        "error",
        "stopped",
        "disabled",
    }


def dashboard_environment_ready(state: dict[str, Any], *, allow_operator_view_degraded: bool = False) -> bool:
    return bool(
        str(state.get("environment_state", "") or "") == "environment_ready"
        and str(state.get("phase", "") or "") == "environment_ready"
        and state.get("sim_gate_ready")
        and operator_view_acceptable(
            state,
            allow_operator_view_degraded=allow_operator_view_degraded,
        )
    )


def _session_id_for_artifact(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(SESSION_ROOT.resolve())
    except ValueError:
        return ""
    return rel.parts[0] if rel.parts else ""


def load_gate_results(gate_summary_path: Path) -> list[dict[str, Any]]:
    summary = read_json(gate_summary_path)
    rows = summary.get("results", []) if isinstance(summary.get("results"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def _route_quality_score(row: dict[str, Any]) -> float:
    quality = row.get("route_quality") if isinstance(row.get("route_quality"), dict) else {}
    try:
        return float(quality.get("quality_score", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def select_executable_results(
    results: list[dict[str, Any]],
    *,
    routes: set[str],
    max_per_route: int,
    scene_ids: set[str],
    skip_scene_ids: set[str],
    quality_order: str = "source",
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    per_route: dict[str, int] = {route: 0 for route in routes}
    candidate_rows = list(results)
    if quality_order == "cleanest":
        candidate_rows = sorted(candidate_rows, key=lambda row: (-_route_quality_score(row), str(row.get("scene_id", ""))))
    elif quality_order == "roughest":
        candidate_rows = sorted(candidate_rows, key=lambda row: (_route_quality_score(row), str(row.get("scene_id", ""))))
    for row in candidate_rows:
        scene_id = str(row.get("scene_id", "") or "")
        route_label = str(row.get("route_label", "") or "")
        if scene_ids and scene_id not in scene_ids:
            continue
        if scene_id in skip_scene_ids:
            continue
        if route_label not in routes:
            continue
        if not bool(row.get("correct", False)):
            continue
        if max_per_route > 0 and per_route.get(route_label, 0) >= max_per_route:
            continue
        selected.append(row)
        per_route[route_label] = per_route.get(route_label, 0) + 1
    return selected


def write_layout_for_result(root: Path, result: dict[str, Any]) -> Path:
    scene_path = resolve_path(str(result.get("scene_path", "") or ""))
    scene = read_json(scene_path)
    if not scene:
        raise ValueError(f"Missing planner scene descriptor: {scene_path}")
    scene_id = _safe_id(str(result.get("scene_id", "") or scene.get("scene_id", "")))
    layout_path = ensure_dir(root / "target_layouts") / f"{scene_id}.json"
    planner_gate.write_fetch_ready_layout_from_scene(
        layout_path,
        scene,
        route_label=str(result.get("route_label", "") or scene.get("expected_route_label", "")),
        route_executor=str(result.get("route_executor", "")),
    )
    return layout_path


def build_replay_command(
    *,
    python_exe: str,
    layout_path: Path,
    dashboard_url: str,
    compose_project: str,
    expected_session_id: str,
    fetch_delivery_radius_m: float,
    planner_route_only_proof: bool = False,
    route_only_sample_duration_s: float = 5.0,
) -> list[str]:
    command = [
        python_exe,
        str(REPO_ROOT / "scripts" / "golf_ball_circle_delivery_demo_runner.py"),
        "--target-layout-json",
        str(layout_path),
        "--fetch-delivery-radius-m",
        f"{float(fetch_delivery_radius_m):.3f}",
    ]
    if planner_route_only_proof:
        command.extend(
            [
                "--planner-route-only-proof",
                "--drive-linear-x-mps",
                "0.000000",
                "--drive-duration-s",
                "0.000000",
                "--sample-duration-s",
                f"{float(route_only_sample_duration_s):.6f}",
            ]
        )
    if str(dashboard_url or "").strip():
        command.extend(["--dashboard-url", str(dashboard_url).strip()])
    if str(compose_project or "").strip():
        command.extend(["--compose-project", str(compose_project).strip()])
    if str(expected_session_id or "").strip():
        command.extend(["--expected-session-id", str(expected_session_id).strip()])
    return command


def build_visual_package_command(
    *,
    python_exe: str,
    package_campaign_id: str,
    gate_summary_path: Path,
    mission_summary_path: Path,
    route_only_proof: bool = False,
) -> list[str]:
    session_id = _session_id_for_artifact(mission_summary_path)
    visual_dir = SESSION_ROOT / session_id / "visual" if session_id else Path("")
    command = [
        python_exe,
        str(REPO_ROOT / "scripts" / "fetch_visual_uat_package.py"),
        "--campaign-id",
        package_campaign_id,
        "--planner-summary",
        str(gate_summary_path),
        "--mission-summary",
        str(mission_summary_path),
        "--visual-dir",
        str(visual_dir),
    ]
    if route_only_proof:
        command.append("--route-only-proof")
    return command


def existing_visual_package_summary_path(campaign_id: str, scene_id: str) -> Path:
    return SESSION_ROOT / f"{campaign_id}_{_safe_id(scene_id)}" / "fetch_visual_uat_package" / "package_summary.json"


def mission_summary_path_from_visual_package(package: dict[str, Any]) -> Path | None:
    missions = package.get("missions") if isinstance(package.get("missions"), list) else []
    if not missions or not isinstance(missions[0], dict):
        return None
    raw_path = str(missions[0].get("path", "") or "").strip()
    return resolve_path(raw_path) if raw_path else None


def _run_command(command: list[str], *, timeout_s: float) -> subprocess.CompletedProcess[str]:
    timeout = max(float(timeout_s), 1.0)
    try:
        return subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        timeout_text = f"timeout_after_s={timeout:.3f}"
        stderr_text = f"{stderr}\n{timeout_text}".strip()
        return subprocess.CompletedProcess(command, 124, stdout=str(stdout or ""), stderr=stderr_text)


def summarize_mission(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    shot = payload.get("shot_outcome") if isinstance(payload.get("shot_outcome"), dict) else {}
    metrics = payload.get("approach_contact_metrics") if isinstance(payload.get("approach_contact_metrics"), dict) else {}
    push_ready = (
        payload.get("measured_push_ready_handoff")
        if isinstance(payload.get("measured_push_ready_handoff"), dict)
        else {}
    )
    pre_fetch_reposition = (
        payload.get("pre_fetch_reposition")
        if isinstance(payload.get("pre_fetch_reposition"), dict)
        else {}
    )
    pre_fetch_fallback = (
        pre_fetch_reposition.get("fallback_to_local_recovery")
        if isinstance(pre_fetch_reposition.get("fallback_to_local_recovery"), dict)
        else {}
    )
    route = payload.get("planner_route") if isinstance(payload.get("planner_route"), dict) else {}
    route_execution = payload.get("planner_route_execution") if isinstance(payload.get("planner_route_execution"), dict) else {}
    route_label = str(payload.get("planner_route_label", route.get("planner_route_label", route_execution.get("route_label", ""))) or "")
    local_fetch_dispatched = bool(payload.get("local_fetch_dispatched", True))
    push_ready_required = bool(local_fetch_dispatched and route_label in EXECUTABLE_ROUTES)
    pre_fetch_attempted = bool(pre_fetch_reposition.get("attempted", False))
    route_attempted = bool(
        route_execution.get("route_executed", False)
        or pre_fetch_attempted
        or (route_label == planner_gate.ROUTE_FETCH_READY and local_fetch_dispatched)
    )
    closest = shot.get("closest_approach_distance_m")
    try:
        closest_value = float(closest)
    except (TypeError, ValueError):
        closest_value = math.nan
    return {
        "path": artifact_display_path(path),
        "session_id": _session_id_for_artifact(path),
        "pass": bool(payload.get("pass", False)),
        "fetch_to_pose_pass": bool(payload.get("fetch_to_pose_pass", False)),
        "planner_route_only_pass": bool(payload.get("planner_route_only_pass", False)),
        "local_fetch_dispatched": local_fetch_dispatched,
        "planner_route_executed": bool(payload.get("planner_route_executed", route_execution.get("route_executed", False))),
        "planner_route_attempted": route_attempted,
        "planner_route_outcome": str(route_execution.get("outcome", "") or ""),
        "route_label": route_label,
        "route_executor": str(payload.get("route_executor", route.get("route_executor", route_execution.get("route_executor", ""))) or ""),
        "pre_fetch_reposition_attempted": pre_fetch_attempted,
        "pre_fetch_reposition_success": bool(pre_fetch_reposition.get("success", False)),
        "pre_fetch_reposition_dispatch_status": str(
            pre_fetch_reposition.get("dispatch_status", pre_fetch_reposition.get("status_text", "")) or ""
        ),
        "pre_fetch_reposition_error": str(pre_fetch_reposition.get("error", "") or ""),
        "pre_fetch_local_recovery_applied": bool(pre_fetch_fallback.get("applied", False)),
        "pre_fetch_local_recovery_reason": str(pre_fetch_fallback.get("reason", "") or ""),
        "pre_fetch_local_recovery_route_label": str(pre_fetch_fallback.get("fallback_route_label", "") or ""),
        "measured_push_ready_handoff_required": push_ready_required,
        "measured_push_ready_handoff_pass": bool(push_ready.get("pass", False)),
        "measured_push_ready_handoff_source": str(push_ready.get("source", "missing") or "missing"),
        "measured_push_ready_handoff_reason": str(push_ready.get("reason", "") or ""),
        "closest_approach_distance_m": round(closest_value, 6) if math.isfinite(closest_value) else None,
        "outcome_reason": str(shot.get("reason", payload.get("fetch_to_pose_failure_reason", "")) or ""),
        "contact_quality_flags": metrics.get("flags", []) if isinstance(metrics.get("flags"), list) else [],
        "first_contact_quality_flags": (
            metrics.get("first_contact_quality_flags", [])
            if isinstance(metrics.get("first_contact_quality_flags"), list)
            else []
        ),
        "stable_contact_approach_pass": bool(metrics.get("stable_contact_approach_pass", False)),
        "first_contact_quality_pass": bool(metrics.get("first_contact_quality_pass", False)),
        "forward_only_pre_contact": bool(payload.get("forward_only_pre_contact", True)),
    }


def executable_mission_success(mission: dict[str, Any]) -> bool:
    if not bool(mission.get("fetch_to_pose_pass", False)):
        return False
    if bool(mission.get("measured_push_ready_handoff_required", False)):
        return bool(mission.get("measured_push_ready_handoff_pass", False))
    return True


def run_batch(args: argparse.Namespace) -> dict[str, Any]:
    campaign_id = str(args.campaign_id or "").strip() or f"live_fetch_planner_route_replay_batch_{current_utc_stamp()}"
    root = ensure_dir(SESSION_ROOT / campaign_id / BATCH_KIND)
    gate_summary_path = resolve_path(str(args.gate_summary))
    requested_routes = tuple(args.route or EXECUTABLE_ROUTES)
    routes = set(requested_routes)
    scene_ids = set(args.scene_id or [])
    skip_scene_ids = set(args.skip_scene_id or [])
    selected = select_executable_results(
        load_gate_results(gate_summary_path),
        routes=routes,
        max_per_route=int(args.max_per_route),
        scene_ids=scene_ids,
        skip_scene_ids=skip_scene_ids,
        quality_order=str(args.quality_order or "source"),
    )
    rows: list[dict[str, Any]] = []
    for index, result in enumerate(selected, start=1):
        scene_id = str(result.get("scene_id", "") or f"scene{index:02d}")
        layout_path = write_layout_for_result(root, result)
        route_label = str(result.get("route_label", "") or "")
        planner_only_route = route_label in PLANNER_ONLY_ROUTES
        if bool(args.resume_skip_existing) and not args.dry_run and not bool(args.no_visual_package):
            existing_package_path = existing_visual_package_summary_path(campaign_id, scene_id)
            existing_package = read_json(existing_package_path) if existing_package_path.is_file() else {}
            if bool(existing_package.get("pass", False)):
                row = {
                    "index": index,
                    "scene_id": scene_id,
                    "route_label": route_label,
                    "route_executor": str(result.get("route_executor", "") or ""),
                    "planner_only_route": planner_only_route,
                    "route_quality": result.get("route_quality", {}) if isinstance(result.get("route_quality"), dict) else {},
                    "layout_path": artifact_display_path(layout_path),
                    "command": [],
                    "fresh_dashboard_session_per_run": bool(args.fresh_dashboard_session_per_run),
                    "allow_operator_view_degraded": bool(getattr(args, "allow_operator_view_degraded", False)),
                    "expected_session_id": "",
                    "compose_project": "",
                    "dashboard_start": {},
                    "dashboard_stop_before_start": {},
                    "dashboard_stop_before_package": {},
                    "dry_run": bool(args.dry_run),
                    "returncode": 0,
                    "failure_reason": "",
                    "mission_summary_path": "",
                    "visual_package_summary_path": artifact_display_path(existing_package_path),
                    "mission": {},
                    "visual_package": existing_package,
                    "stdout_tail": "resume_skip_existing_visual_package",
                    "stderr_tail": "",
                    "resume_skip_existing": True,
                }
                mission_summary_path = mission_summary_path_from_visual_package(existing_package)
                if mission_summary_path and mission_summary_path.is_file():
                    row["mission_summary_path"] = artifact_display_path(mission_summary_path)
                    row["mission"] = summarize_mission(mission_summary_path)
                rows.append(row)
                continue
        run_compose_project = str(args.compose_project or "")
        expected_session_id = ""
        dashboard_start: dict[str, Any] = {}
        dashboard_stop: dict[str, Any] = {}
        if not args.dry_run and bool(args.fresh_dashboard_session_per_run):
            dashboard_stop = stop_dashboard_environment(
                str(args.dashboard_url or ""),
                timeout_s=float(args.env_stop_timeout_s),
            )
            dashboard_start = start_dashboard_environment(args)
            start_state = dashboard_start.get("state") if isinstance(dashboard_start.get("state"), dict) else {}
            run_compose_project = str(start_state.get("compose_project", "") or start_state.get("launcher_project", "") or "")
            expected_session_id = str(start_state.get("session_id", "") or "")
            dashboard_ready = dashboard_environment_ready(
                start_state,
                allow_operator_view_degraded=bool(getattr(args, "allow_operator_view_degraded", False)),
            )
        command = build_replay_command(
            python_exe=str(args.python_exe or sys.executable),
            layout_path=layout_path,
            dashboard_url=str(args.dashboard_url or ""),
            compose_project=run_compose_project,
            expected_session_id=expected_session_id,
            fetch_delivery_radius_m=float(args.fetch_delivery_radius_m),
            planner_route_only_proof=planner_only_route,
            route_only_sample_duration_s=float(getattr(args, "route_only_sample_duration_s", 5.0)),
        )
        row: dict[str, Any] = {
            "index": index,
            "scene_id": scene_id,
            "route_label": route_label,
            "route_executor": str(result.get("route_executor", "") or ""),
            "planner_only_route": planner_only_route,
            "route_quality": result.get("route_quality", {}) if isinstance(result.get("route_quality"), dict) else {},
            "layout_path": artifact_display_path(layout_path),
            "command": command,
            "fresh_dashboard_session_per_run": bool(args.fresh_dashboard_session_per_run),
            "allow_operator_view_degraded": bool(getattr(args, "allow_operator_view_degraded", False)),
            "expected_session_id": expected_session_id,
            "compose_project": run_compose_project,
            "dashboard_start": dashboard_start,
            "dashboard_stop_before_start": dashboard_stop,
            "dashboard_stop_before_package": {},
            "dry_run": bool(args.dry_run),
            "returncode": None,
            "failure_reason": "",
            "mission_summary_path": "",
            "visual_package_summary_path": "",
            "mission": {},
            "visual_package": {},
            "stdout_tail": "",
            "stderr_tail": "",
            "resume_skip_existing": False,
        }
        if not args.dry_run:
            if bool(args.fresh_dashboard_session_per_run) and (
                not run_compose_project or not expected_session_id or not dashboard_ready
            ):
                row["returncode"] = -1
                row["failure_reason"] = dashboard_start_failure_reason(dashboard_start)
                row["stderr_tail"] = str(row["failure_reason"])
                rows.append(row)
                if bool(args.stop_on_fail):
                    break
                continue
            completed = _run_command(command, timeout_s=float(args.timeout_s))
            output = (completed.stdout or "") + "\n" + (completed.stderr or "")
            mission_summary_raw = _extract_marker(output, MISSION_SUMMARY_MARKER)
            row["returncode"] = int(completed.returncode)
            row["stdout_tail"] = "\n".join((completed.stdout or "").splitlines()[-20:])
            row["stderr_tail"] = "\n".join((completed.stderr or "").splitlines()[-20:])
            if mission_summary_raw:
                mission_summary_path = resolve_path(mission_summary_raw)
                row["mission_summary_path"] = artifact_display_path(mission_summary_path)
                row["mission"] = summarize_mission(mission_summary_path)
                if not bool(args.no_visual_package):
                    if bool(args.fresh_dashboard_session_per_run):
                        row["dashboard_stop_before_package"] = stop_dashboard_environment(
                            str(args.dashboard_url or ""),
                            timeout_s=float(args.env_stop_timeout_s),
                        )
                    package_campaign_id = f"{campaign_id}_{_safe_id(scene_id)}"
                    package_command = build_visual_package_command(
                        python_exe=str(args.python_exe or sys.executable),
                        package_campaign_id=package_campaign_id,
                        gate_summary_path=gate_summary_path,
                        mission_summary_path=mission_summary_path,
                        route_only_proof=planner_only_route,
                    )
                    row["visual_package_command"] = package_command
                    package_completed = _run_command(package_command, timeout_s=float(args.package_timeout_s))
                    package_output = (package_completed.stdout or "") + "\n" + (package_completed.stderr or "")
                    package_summary_raw = _extract_marker(package_output, VISUAL_PACKAGE_MARKER)
                    row["visual_package_returncode"] = int(package_completed.returncode)
                    if package_summary_raw:
                        package_summary_path = resolve_path(package_summary_raw)
                        row["visual_package_summary_path"] = artifact_display_path(package_summary_path)
                        row["visual_package"] = read_json(package_summary_path)
                elif bool(args.fresh_dashboard_session_per_run):
                    row["dashboard_stop_before_package"] = stop_dashboard_environment(
                        str(args.dashboard_url or ""),
                        timeout_s=float(args.env_stop_timeout_s),
                    )
            elif bool(args.fresh_dashboard_session_per_run):
                row["dashboard_stop_before_package"] = stop_dashboard_environment(
                    str(args.dashboard_url or ""),
                    timeout_s=float(args.env_stop_timeout_s),
                )
            if bool(args.stop_on_fail) and int(completed.returncode) != 0:
                rows.append(row)
                break
        rows.append(row)

    fetch_to_pose_pass_count = sum(
        1
        for row in rows
        if not bool(row.get("planner_only_route", False)) and bool((row.get("mission") or {}).get("fetch_to_pose_pass", False))
    )
    mission_pass_count = sum(
        1
        for row in rows
        if not bool(row.get("planner_only_route", False)) and executable_mission_success(row.get("mission") or {})
    )
    route_only_pass_count = sum(
        1
        for row in rows
        if bool(row.get("planner_only_route", False)) and bool((row.get("mission") or {}).get("planner_route_only_pass", False))
    )
    route_success_count = mission_pass_count + route_only_pass_count
    mission_fail_count = sum(
        1
        for row in rows
        if row.get("mission")
        and not bool(row.get("planner_only_route", False))
        and not executable_mission_success(row.get("mission") or {})
    )
    push_ready_required_count = sum(
        1
        for row in rows
        if bool((row.get("mission") or {}).get("measured_push_ready_handoff_required", False))
    )
    push_ready_pass_count = sum(
        1
        for row in rows
        if bool((row.get("mission") or {}).get("measured_push_ready_handoff_required", False))
        and bool((row.get("mission") or {}).get("measured_push_ready_handoff_pass", False))
    )
    pre_fetch_reposition_attempt_count = sum(
        1
        for row in rows
        if bool((row.get("mission") or {}).get("pre_fetch_reposition_attempted", False))
    )
    pre_fetch_reposition_success_count = sum(
        1
        for row in rows
        if bool((row.get("mission") or {}).get("pre_fetch_reposition_attempted", False))
        and bool((row.get("mission") or {}).get("pre_fetch_reposition_success", False))
    )
    pre_fetch_local_recovery_applied_count = sum(
        1
        for row in rows
        if bool((row.get("mission") or {}).get("pre_fetch_local_recovery_applied", False))
    )
    visual_pass_count = sum(1 for row in rows if bool((row.get("visual_package") or {}).get("pass", False)))
    summary = {
        "generated_utc": utc_now(),
        "type": BATCH_KIND,
        "campaign_id": campaign_id,
        "dry_run": bool(args.dry_run),
        "fresh_dashboard_session_per_run": bool(args.fresh_dashboard_session_per_run),
        "allow_operator_view_degraded": bool(getattr(args, "allow_operator_view_degraded", False)),
        "resume_skip_existing": bool(args.resume_skip_existing),
        "gate_summary_path": artifact_display_path(gate_summary_path),
        "selected_count": len(rows),
        "skipped_existing_count": sum(1 for row in rows if bool(row.get("resume_skip_existing", False))),
        "requested_route_count": {route: sum(1 for row in rows if row.get("route_label") == route) for route in requested_routes},
        "fetch_to_pose_pass_count": fetch_to_pose_pass_count,
        "mission_pass_count": mission_pass_count,
        "route_only_pass_count": route_only_pass_count,
        "route_success_count": route_success_count,
        "mission_fail_count": mission_fail_count,
        "measured_push_ready_handoff_required_count": push_ready_required_count,
        "measured_push_ready_handoff_pass_count": push_ready_pass_count,
        "measured_push_ready_handoff_fail_count": push_ready_required_count - push_ready_pass_count,
        "pre_fetch_reposition_attempt_count": pre_fetch_reposition_attempt_count,
        "pre_fetch_reposition_success_count": pre_fetch_reposition_success_count,
        "pre_fetch_local_recovery_applied_count": pre_fetch_local_recovery_applied_count,
        "visual_package_pass_count": visual_pass_count,
        "pass": bool(
            rows
            and (args.dry_run or (route_success_count == len(rows) and visual_pass_count == len(rows)))
        ),
        "promotion_evidence": False,
        "milestone_interpretation": "planner_route_replay_batch_dry_run" if args.dry_run else "planner_route_replay_batch_visual_uat",
        "rows": rows,
        "summary_path": artifact_display_path(root / "batch_summary.json"),
        "scorecard_path": artifact_display_path(root / "scorecard.md"),
    }
    write_json(root / "batch_summary.json", summary)
    write_scorecard(root / "scorecard.md", summary)
    return summary


def write_scorecard(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Fetch Planner Route Replay Batch",
        "",
        f"- campaign_id: `{summary.get('campaign_id', '')}`",
        f"- dry_run: `{summary.get('dry_run', False)}`",
        f"- fresh_dashboard_session_per_run: `{summary.get('fresh_dashboard_session_per_run', False)}`",
        f"- allow_operator_view_degraded: `{summary.get('allow_operator_view_degraded', False)}`",
        f"- resume_skip_existing: `{summary.get('resume_skip_existing', False)}`",
        f"- pass: `{summary.get('pass', False)}`",
        f"- selected_count: `{summary.get('selected_count', 0)}`",
        f"- skipped_existing_count: `{summary.get('skipped_existing_count', 0)}`",
        f"- fetch_to_pose_pass_count: `{summary.get('fetch_to_pose_pass_count', 0)}`",
        f"- mission_pass_count: `{summary.get('mission_pass_count', 0)}`",
        f"- route_only_pass_count: `{summary.get('route_only_pass_count', 0)}`",
        f"- route_success_count: `{summary.get('route_success_count', 0)}`",
        f"- mission_fail_count: `{summary.get('mission_fail_count', 0)}`",
        f"- measured_push_ready_handoff_required_count: `{summary.get('measured_push_ready_handoff_required_count', 0)}`",
        f"- measured_push_ready_handoff_pass_count: `{summary.get('measured_push_ready_handoff_pass_count', 0)}`",
        f"- measured_push_ready_handoff_fail_count: `{summary.get('measured_push_ready_handoff_fail_count', 0)}`",
        f"- pre_fetch_reposition_attempt_count: `{summary.get('pre_fetch_reposition_attempt_count', 0)}`",
        f"- pre_fetch_reposition_success_count: `{summary.get('pre_fetch_reposition_success_count', 0)}`",
        f"- pre_fetch_local_recovery_applied_count: `{summary.get('pre_fetch_local_recovery_applied_count', 0)}`",
        f"- visual_package_pass_count: `{summary.get('visual_package_pass_count', 0)}`",
        f"- promotion_evidence: `{summary.get('promotion_evidence', False)}`",
        f"- interpretation: `{summary.get('milestone_interpretation', '')}`",
        "",
        "## Rows",
    ]
    for row in summary.get("rows", []) if isinstance(summary.get("rows"), list) else []:
        mission = row.get("mission") if isinstance(row.get("mission"), dict) else {}
        package = row.get("visual_package") if isinstance(row.get("visual_package"), dict) else {}
        quality = row.get("route_quality") if isinstance(row.get("route_quality"), dict) else {}
        mission_path = str(row.get("mission_summary_path", "") or "")
        package_scorecard = str(package.get("scorecard_path", "") or "")
        mission_link = f" [mission](/{mission_path})" if mission_path.startswith("artifacts/session/") else ""
        package_link = f" [visual_package](/{package_scorecard})" if package_scorecard.startswith("artifacts/session/") else ""
        closest = mission.get("closest_approach_distance_m")
        push_ready_text = ""
        if bool(mission.get("measured_push_ready_handoff_required", False)):
            push_ready_text = (
                f" push_ready=`{mission.get('measured_push_ready_handoff_pass', False)}`"
                f" source=`{mission.get('measured_push_ready_handoff_source', '')}`"
            )
        pre_fetch_text = ""
        if bool(mission.get("pre_fetch_reposition_attempted", False)):
            pre_fetch_text = (
                f" nav2_reposition=`{mission.get('pre_fetch_reposition_success', False)}`"
                f" nav2_status=`{mission.get('pre_fetch_reposition_dispatch_status', '')}`"
                f" local_recovery=`{mission.get('pre_fetch_local_recovery_applied', False)}`"
            )
        closest_text = f" closest=`{float(closest):.3f}m`" if isinstance(closest, (int, float)) else ""
        quality_text = (
            f" score=`{quality.get('quality_score', '')}` "
            f"pred=`{quality.get('predicted_contact_quality', '')}` "
            f"risk=`{quality.get('predicted_first_contact_risk', '')}`"
            if quality
            else ""
        )
        lines.append(
            f"- `{row.get('scene_id', '')}` route=`{row.get('route_label', '')}` "
            f"planner_only=`{row.get('planner_only_route', False)}` "
            f"dry_run=`{row.get('dry_run', False)}` rc=`{row.get('returncode', '')}` "
            f"resume_skip_existing=`{row.get('resume_skip_existing', False)}` "
            f"failure=`{row.get('failure_reason', '')}` "
            f"session=`{row.get('expected_session_id', '')}` "
            f"mission_pass=`{mission.get('fetch_to_pose_pass', mission.get('pass', ''))}` "
            f"route_only_pass=`{mission.get('planner_route_only_pass', '')}` "
            f"visual_pass=`{package.get('pass', '')}`"
            f"{push_ready_text}"
            f"{pre_fetch_text}"
            f"{quality_text}{closest_text}{mission_link}{package_link}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay executable planner-routed fetch scenes.")
    parser.add_argument("--campaign-id", default=f"live_fetch_planner_route_replay_batch_{current_utc_stamp()}")
    parser.add_argument("--gate-summary", required=True)
    parser.add_argument("--route", action="append", choices=REPLAY_ROUTES, default=[])
    parser.add_argument("--scene-id", action="append", default=[])
    parser.add_argument("--skip-scene-id", action="append", default=[])
    parser.add_argument("--max-per-route", type=int, default=1)
    parser.add_argument("--quality-order", choices=["source", "cleanest", "roughest"], default="source")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--dashboard-url", default="")
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
    parser.add_argument("--env-ready-timeout-s", type=float, default=DEFAULT_ENV_READY_TIMEOUT_S)
    parser.add_argument("--env-start-attempts", type=int, default=2)
    parser.add_argument("--env-stop-timeout-s", type=float, default=90.0)
    parser.add_argument("--fetch-delivery-radius-m", type=float, default=0.300)
    parser.add_argument("--route-only-sample-duration-s", type=float, default=5.0)
    parser.add_argument("--python-exe", default=sys.executable)
    parser.add_argument("--timeout-s", type=float, default=180.0)
    parser.add_argument("--package-timeout-s", type=float, default=120.0)
    parser.add_argument("--no-visual-package", action="store_true")
    parser.add_argument(
        "--resume-skip-existing",
        action="store_true",
        help="Reuse passing visual packages already present for this campaign/scene instead of rerunning those rows.",
    )
    parser.add_argument("--stop-on-fail", action="store_true")
    return parser.parse_args()


def main() -> int:
    summary = run_batch(parse_args())
    print(f"FETCH_PLANNER_ROUTE_REPLAY_BATCH_SUMMARY={SESSION_ROOT / summary['campaign_id'] / BATCH_KIND / 'batch_summary.json'}")
    return 0 if bool(summary.get("pass", False)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
