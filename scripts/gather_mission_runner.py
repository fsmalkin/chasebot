#!/usr/bin/env python3
"""Deterministic gather mission runner for offline/headless corral-and-place proofs."""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_provider_base import ProviderError
from llm_provider_local import LocalModelProvider
from llm_provider_local import LocalStubProvider
from llm_provider_openai import OpenAIResponsesProvider
from llm_supervisor_core import DEFAULT_DASHBOARD_URL
from llm_supervisor_core import DEFAULT_OPENAI_MODEL
from llm_supervisor_core import DEFAULT_REASONING_EFFORT
from llm_supervisor_core import append_jsonl
from llm_supervisor_core import dispatch_intent
from llm_supervisor_core import fetch_dashboard_state
from llm_supervisor_core import http_json
from llm_supervisor_core import read_json
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json
from gather_mission_helpers import DEFAULT_RELEASE_SETTLE_MAX_WAIT_S
from gather_mission_helpers import DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M
from gather_mission_helpers import DEFAULT_RELEASE_SETTLE_STABLE_WINDOW_S
from gather_mission_helpers import CaptureEnvelope
from gather_mission_helpers import GatherTargetSpec
from gather_mission_helpers import build_gather_targets
from gather_mission_helpers import build_scorecard_markdown
from gather_mission_helpers import build_zone_spec
from gather_mission_helpers import clamp
from gather_mission_helpers import capture_loss_detected
from gather_mission_helpers import capture_snapshot
from gather_mission_helpers import compute_capture_command
from gather_mission_helpers import compute_place_command
from gather_mission_helpers import normalize_angle
from gather_mission_helpers import pose_delta_m
from gather_mission_helpers import release_ready
from gather_mission_helpers import secure_capture
from gather_mission_helpers import summarize_release_settle_trace
from gather_mission_helpers import world_pose_xyyaw
from gather_mission_helpers import zone_snapshot
from gather_mission_helpers import zone_edge_correction_eligible


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = REPO_ROOT / "runtime" / "dashboard"
DEFAULT_GATHER_RUNTIME_STATE_PATH = RUNTIME_DIR / "gather_mission_runtime.json"
DEFAULT_VISIT_RUNTIME_STATE_PATH = RUNTIME_DIR / "visit_mission_runtime.json"
DOCKER_FALLBACK = Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe")
DEFAULT_WORLD_NAME = "yolo_test_world"
DEFAULT_TARGET_MODEL_NAME = "visit_mission_target"
DEFAULT_TARGET_MODEL_SDF = REPO_ROOT / "ros2_config" / "frisbee_target_ball.sdf"
DEFAULT_ZONE_MODEL_NAME = "corral_zone_marker"
DEFAULT_ZONE_MODEL_SDF = REPO_ROOT / "ros2_config" / "corral_zone_marker.sdf"
DEFAULT_MISSION_START_POSE = {"x": 0.0, "y": 0.0, "yaw": 0.0}
DEFAULT_PLACE_RECOVERY_SETTLE_S = 0.20
DEFAULT_PLACE_MARGINAL_CAPTURE_SETTLE_S = 0.25
DEFAULT_POST_VISIT_REVISIT_ESCAPE_TIMEOUT_S = 1.25

_dotenv_path = REPO_ROOT / ".env"
if _dotenv_path.is_file():
    with _dotenv_path.open(encoding="utf-8", errors="ignore") as _handle:
        for _line in _handle:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _key, _, _value = _line.partition("=")
            _key = _key.strip()
            _value = _value.strip().strip("'\"")
            if _key and _key not in os.environ:
                os.environ[_key] = _value


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def choose_docker_cli() -> str:
    found = shutil.which("docker")
    if found:
        return found
    if DOCKER_FALLBACK.exists():
        return str(DOCKER_FALLBACK)
    raise FileNotFoundError("Unable to locate docker CLI.")


def to_container_repo_path(path: Path) -> str:
    resolved = path.resolve()
    relative = resolved.relative_to(REPO_ROOT.resolve())
    return "/workspaces/chasecar/" + str(relative).replace("\\", "/")


def resolve_visit_runtime_state_path(raw_path: str = "") -> Path:
    candidate = str(raw_path or os.environ.get("CHASECAR_VISIT_RUNTIME_PATH") or "").strip()
    if candidate:
        return Path(candidate).resolve()
    return DEFAULT_VISIT_RUNTIME_STATE_PATH.resolve()


def resolve_gather_runtime_state_path(raw_path: str = "") -> Path:
    candidate = str(raw_path or os.environ.get("CHASECAR_GATHER_RUNTIME_PATH") or "").strip()
    if candidate:
        return Path(candidate).resolve()
    return DEFAULT_GATHER_RUNTIME_STATE_PATH.resolve()


def clean_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def clean_number(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def default_settle_exit_reason(
    *,
    failure_reason: str = "",
    settled_in_corral_pass: bool = False,
    corrected: bool = False,
    rolled_away_after_release: bool = False,
) -> str:
    if settled_in_corral_pass:
        return "corrected" if corrected else "settled"
    if rolled_away_after_release or str(failure_reason or "").strip() in {"release_roll_away", "capture_lost"}:
        return "rolled_out"
    if str(failure_reason or "").strip() in {"release_unsettled", "place_timeout", "capture_timeout"}:
        return "timeout"
    return ""


def truth_world_xy(pose: dict[str, Any]) -> dict[str, float] | None:
    position = pose.get("position") if isinstance(pose.get("position"), dict) else {}
    x = clean_number(position.get("x"))
    y = clean_number(position.get("y"))
    z = clean_number(position.get("z"))
    if x is None or y is None:
        return None
    payload = {"x": round(float(x), 6), "y": round(float(y), 6)}
    if z is not None:
        payload["z"] = round(float(z), 6)
    return payload


def build_provider(provider_name: str, *, model: str, reasoning_effort: str):
    normalized = str(provider_name or "").strip().lower() or "openai"
    if normalized == "openai":
        return OpenAIResponsesProvider(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            model=model,
            reasoning_effort=reasoning_effort,
            base_url=os.environ.get("OPENAI_BASE_URL", ""),
            org_id=os.environ.get("OPENAI_ORG_ID", ""),
            project_id=os.environ.get("OPENAI_PROJECT_ID", ""),
        )
    if normalized == "local_stub":
        return LocalStubProvider(model=model or "local-stub")
    if normalized == "local_model":
        return LocalModelProvider(model=model or "local-model")
    raise ValueError(f"Unsupported provider: {provider_name}")


class GatherMissionRunner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.dashboard_url = args.dashboard_url.rstrip("/")
        self.targets = build_gather_targets(args.scenario_id)
        self.targets_by_id = {item.id: item for item in self.targets}
        self.zone = build_zone_spec(args.scenario_id)
        self.capture_envelope = CaptureEnvelope()
        self.docker = choose_docker_cli()
        self.world_file = clean_text(args.world_file)
        self.surface_profile = clean_text(args.surface_profile, "baseline")
        self.visit_runtime_state_path = resolve_visit_runtime_state_path(args.visit_runtime_json)
        self.gather_runtime_state_path = resolve_gather_runtime_state_path(args.gather_runtime_json)
        self.visit_runtime_state: dict[str, Any] = {}
        self.gather_runtime_state: dict[str, Any] = {}
        self._gather_sequence = 0
        self.provider = build_provider(
            args.provider,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
        )
        self._event_keys: set[str] = set()
        self._started_here = False

    def _persist_visit_runtime_state(self) -> None:
        write_json(self.visit_runtime_state_path, self.visit_runtime_state)

    def _persist_gather_runtime_state(self) -> None:
        write_json(self.gather_runtime_state_path, self.gather_runtime_state)

    def _update_visit_runtime_state(self, **updates: Any) -> None:
        self.visit_runtime_state.update(updates)
        self.visit_runtime_state["updated_utc"] = utc_now()
        self._persist_visit_runtime_state()

    def _update_gather_runtime_state(self, **updates: Any) -> None:
        self.gather_runtime_state.update(updates)
        self.gather_runtime_state["updated_utc"] = utc_now()
        self._persist_gather_runtime_state()

    def _append_runtime_event(self, message: str, *, category: str = "mission", key: str = "") -> None:
        event_key = key or message
        if event_key in self._event_keys:
            return
        self._event_keys.add(event_key)
        event = {
            "timestamp_utc": utc_now(),
            "message": str(message),
            "category": str(category),
            "source": "gather_mission",
        }
        for state, persist in (
            (self.visit_runtime_state, self._persist_visit_runtime_state),
            (self.gather_runtime_state, self._persist_gather_runtime_state),
        ):
            events = list(state.get("recent_operator_events", []))
            events.append(event)
            state["recent_operator_events"] = events[-30:]
            state["latest_operator_event"] = event["message"]
            state["updated_utc"] = event["timestamp_utc"]
            persist()

    def _target_failure_result(
        self,
        *,
        target: GatherTargetSpec,
        failure_reason: str,
        failure_stage: str,
        attempts: int,
        capture_loss_count: int,
        route_index: int,
        attempt_kind: str,
        local_recovery_attempted: bool = False,
        revisit_attempted: bool = False,
        settle_metrics: dict[str, Any] | None = None,
        stopped_with_ball_captured: bool = False,
        release_started_with_capture: bool = False,
        stop_capture_state: dict[str, Any] | None = None,
        release_capture_state: dict[str, Any] | None = None,
        clean_retention_pass: bool = False,
        final_inside_retrieval_corral: bool = False,
        final_center_inside_zone: bool = False,
        ball_stopped_in_corral: bool = False,
        rolled_away_after_release: bool = False,
        settled_in_corral_pass: bool = False,
        handoff_kind: str = "",
        zone_edge_correction_count: int = 0,
        place_controller_reentry_count: int = 0,
        post_visit_revisit_count: int = 0,
        settle_exit_reason: str = "",
    ) -> dict[str, Any]:
        resolved_settle_exit_reason = clean_text(
            settle_exit_reason,
            default_settle_exit_reason(
                failure_reason=str(failure_reason),
                settled_in_corral_pass=bool(settled_in_corral_pass),
                corrected=bool(zone_edge_correction_count or place_controller_reentry_count),
                rolled_away_after_release=bool(rolled_away_after_release),
            ),
        )
        payload = {
            "target_id": target.id,
            "label": target.label,
            "pass": False,
            "failure_reason": str(failure_reason),
            "failure_stage": str(failure_stage),
            "attempts": int(attempts),
            "attempt_kind": str(attempt_kind),
            "capture_loss_count": int(capture_loss_count),
            "route_index": int(route_index),
            "local_recovery_attempted": bool(local_recovery_attempted),
            "revisit_attempted": bool(revisit_attempted),
            "surface_profile": self.surface_profile,
            "handoff_kind": clean_text(handoff_kind, "unspecified"),
            "zone_edge_correction_count": int(zone_edge_correction_count),
            "place_controller_reentry_count": int(place_controller_reentry_count),
            "post_visit_revisit_count": int(post_visit_revisit_count),
            "stopped_with_ball_captured": bool(stopped_with_ball_captured),
            "release_started_with_capture": bool(release_started_with_capture),
            "stop_capture_state": stop_capture_state if isinstance(stop_capture_state, dict) else {},
            "release_capture_state": release_capture_state if isinstance(release_capture_state, dict) else {},
            "clean_retention_pass": bool(clean_retention_pass),
            "final_inside_retrieval_corral": bool(final_inside_retrieval_corral),
            "final_center_inside_zone": bool(final_center_inside_zone),
            "ball_stopped_in_corral": bool(ball_stopped_in_corral),
            "rolled_away_after_release": bool(rolled_away_after_release),
            "settled_in_corral_pass": bool(settled_in_corral_pass),
            "settle_exit_reason": resolved_settle_exit_reason,
        }
        if isinstance(settle_metrics, dict):
            payload.update(settle_metrics)
            payload["settle_exit_reason"] = clean_text(payload.get("settle_exit_reason"), resolved_settle_exit_reason)
        return payload

    def _target_success_result(
        self,
        *,
        target: GatherTargetSpec,
        attempts: int,
        capture_loss_count: int,
        route_index: int,
        final_ball_pose: dict[str, Any],
        place_time_s: float,
        attempt_kind: str,
        local_recovery_attempted: bool = False,
        revisit_attempted: bool = False,
        settle_metrics: dict[str, Any] | None = None,
        stopped_with_ball_captured: bool = False,
        release_started_with_capture: bool = False,
        stop_capture_state: dict[str, Any] | None = None,
        release_capture_state: dict[str, Any] | None = None,
        clean_retention_pass: bool | None = None,
        final_inside_retrieval_corral: bool = False,
        final_center_inside_zone: bool = False,
        ball_stopped_in_corral: bool = False,
        rolled_away_after_release: bool = False,
        settled_in_corral_pass: bool | None = None,
        handoff_kind: str = "",
        zone_edge_correction_count: int = 0,
        place_controller_reentry_count: int = 0,
        post_visit_revisit_count: int = 0,
        settle_exit_reason: str = "",
    ) -> dict[str, Any]:
        settle_payload = settle_metrics if isinstance(settle_metrics, dict) else {}
        final_inside_retrieval_corral = bool(settle_payload.get("final_inside_retrieval_corral", final_inside_retrieval_corral))
        final_center_inside_zone = bool(settle_payload.get("final_center_inside_zone", final_center_inside_zone))
        ball_stopped_in_corral = bool(settle_payload.get("ball_stopped_in_corral", ball_stopped_in_corral))
        rolled_away_after_release = bool(settle_payload.get("rolled_away_after_release", rolled_away_after_release))
        retention_pass = (
            int(capture_loss_count) == 0
            and bool(stopped_with_ball_captured)
            and bool(release_started_with_capture)
            if clean_retention_pass is None
            else bool(clean_retention_pass)
        )
        settled_pass = (
            bool(final_inside_retrieval_corral)
            and bool(ball_stopped_in_corral)
            and not bool(rolled_away_after_release)
            and int(post_visit_revisit_count) == 0
            if settled_in_corral_pass is None
            else bool(settled_in_corral_pass)
        )
        if settled_in_corral_pass is None and settle_payload:
            settled_pass = bool(settle_payload.get("settled_in_corral_pass", settled_pass))
        resolved_settle_exit_reason = clean_text(
            settle_payload.get("settle_exit_reason") if isinstance(settle_payload, dict) else "",
            clean_text(
                settle_exit_reason,
                default_settle_exit_reason(
                    settled_in_corral_pass=bool(settled_pass),
                    corrected=bool(
                        zone_edge_correction_count
                        or place_controller_reentry_count
                        or int(settle_payload.get("release_recontact_count", 0) or 0)
                    ),
                    rolled_away_after_release=bool(rolled_away_after_release),
                ),
            ),
        )
        payload = {
            "target_id": target.id,
            "label": target.label,
            "pass": bool(settled_pass),
            "attempts": int(attempts),
            "attempt_kind": str(attempt_kind),
            "capture_loss_count": int(capture_loss_count),
            "route_index": int(route_index),
            "placed": bool(settled_pass),
            "final_ball_pose": final_ball_pose,
            "place_time_s": round(float(place_time_s), 6),
            "local_recovery_attempted": bool(local_recovery_attempted),
            "revisit_attempted": bool(revisit_attempted),
            "surface_profile": self.surface_profile,
            "handoff_kind": clean_text(handoff_kind, "unspecified"),
            "zone_edge_correction_count": int(zone_edge_correction_count),
            "place_controller_reentry_count": int(place_controller_reentry_count),
            "post_visit_revisit_count": int(post_visit_revisit_count),
            "stopped_with_ball_captured": bool(stopped_with_ball_captured),
            "release_started_with_capture": bool(release_started_with_capture),
            "stop_capture_state": stop_capture_state if isinstance(stop_capture_state, dict) else {},
            "release_capture_state": release_capture_state if isinstance(release_capture_state, dict) else {},
            "clean_retention_pass": retention_pass,
            "final_inside_retrieval_corral": bool(final_inside_retrieval_corral),
            "final_center_inside_zone": bool(final_center_inside_zone),
            "ball_stopped_in_corral": bool(ball_stopped_in_corral),
            "rolled_away_after_release": bool(rolled_away_after_release),
            "settled_in_corral_pass": bool(settled_pass),
            "settle_exit_reason": resolved_settle_exit_reason,
        }
        if settle_payload:
            payload.update(settle_payload)
            payload["settle_exit_reason"] = clean_text(payload.get("settle_exit_reason"), resolved_settle_exit_reason)
        return payload

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None, timeout_s: float | None = None) -> tuple[int, dict[str, Any]]:
        return http_json(
            f"{self.dashboard_url}{path}",
            method=method,
            payload=payload,
            timeout_s=timeout_s or self.args.timeout_s,
        )

    def _wait_for_state(self, predicate, timeout_s: float, error_text: str) -> dict[str, Any]:
        deadline = time.monotonic() + max(timeout_s, 0.1)
        last_state: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last_state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
            if predicate(last_state):
                return last_state
            time.sleep(0.5)
        raise RuntimeError(error_text + f" Last state: {json.dumps(last_state, sort_keys=True)}")

    def _ensure_environment_ready(self) -> tuple[dict[str, Any], bool]:
        state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
        if state.get("environment_state") == "environment_ready":
            return state, False
        status, payload = self._request("POST", "/api/env/start", timeout_s=10.0)
        if status not in {200, 202}:
            raise RuntimeError(f"Failed to start environment: {payload}")
        ready_state = self._wait_for_state(
            lambda current: current.get("environment_state") == "environment_ready" and current.get("session_id"),
            timeout_s=self.args.environment_timeout_s,
            error_text="Environment did not become ready for gather mission.",
        )
        return ready_state, True

    def _wait_for_robot_pose(self, timeout_s: float) -> dict[str, Any]:
        return self._wait_for_state(
            lambda current: (
                current.get("environment_state") == "environment_ready"
                and isinstance(current.get("belief"), dict)
                and isinstance(current.get("belief", {}).get("latest_robot_pose"), dict)
                and current.get("compose_project")
            ),
            timeout_s=timeout_s,
            error_text="Robot pose did not become available for gather mission.",
        )

    def _wait_for_robot_pose_near(
        self,
        *,
        x: float,
        y: float,
        yaw: float,
        timeout_s: float = 15.0,
        position_tolerance_m: float = 0.15,
        yaw_tolerance_rad: float = 0.35,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + max(timeout_s, 0.1)
        last_state: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last_state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
            try:
                robot_x, robot_y, robot_yaw = self._robot_pose_components(last_state)
            except RuntimeError:
                time.sleep(self.args.poll_s)
                continue
            position_error = math.hypot(robot_x - x, robot_y - y)
            yaw_error = abs(normalize_angle(robot_yaw - yaw))
            if position_error <= position_tolerance_m and yaw_error <= yaw_tolerance_rad:
                return last_state
            time.sleep(self.args.poll_s)
        raise RuntimeError(f"Robot pose did not settle near commanded start pose: {last_state}")

    def _wait_for_nav2_ready(self, timeout_s: float = 30.0) -> dict[str, Any]:
        deadline = time.monotonic() + max(timeout_s, 0.1)
        last_state: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last_state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
            brain = last_state.get("brain", {}) if isinstance(last_state.get("brain"), dict) else {}
            if bool(brain.get("nav2_server_ready", False)):
                return last_state
            time.sleep(0.5)
        return last_state

    def _wait_for_pursuit_quiet(self, timeout_s: float) -> dict[str, Any]:
        deadline = time.monotonic() + max(timeout_s, 0.1)
        last_state: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last_state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
            brain = last_state.get("brain", {}) if isinstance(last_state.get("brain"), dict) else {}
            outcome = last_state.get("outcome", {}) if isinstance(last_state.get("outcome"), dict) else {}
            if (
                not bool(brain.get("goal_in_progress", False))
                and not bool(brain.get("track_active", False))
                and not bool(outcome.get("nav_goal_recent", False))
                and not bool(outcome.get("cmd_vel_recent", False))
            ):
                return last_state
            time.sleep(0.25)
        return last_state

    def _stop_environment(self) -> None:
        self._request("POST", "/api/env/stop", timeout_s=10.0)
        self._wait_for_state(
            lambda current: current.get("environment_state") == "stopped",
            timeout_s=240.0,
            error_text="Environment did not stop cleanly after gather mission.",
        )

    def _container_id(self, project_name: str, service_name: str) -> str:
        proc = subprocess.run(
            [self.docker, "compose", "-f", str(REPO_ROOT / "docker-compose.yml"), "-p", project_name, "ps", "-q", service_name],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Unable to resolve container id for {service_name}: {proc.stdout}\n{proc.stderr}")
        container_ids = proc.stdout.strip().splitlines()
        if not container_ids:
            raise RuntimeError(f"No running container id found for {service_name}.")
        return container_ids[0].strip()

    def _docker_exec(self, container_id: str, script: str) -> tuple[int, str]:
        proc = subprocess.run(
            [
                self.docker,
                "exec",
                "-i",
                container_id,
                "bash",
                "-lc",
                "cat >/tmp/chasecar_gather_mission.sh && chmod +x /tmp/chasecar_gather_mission.sh && /tmp/chasecar_gather_mission.sh",
            ],
            cwd=str(REPO_ROOT),
            input=script.encode("utf-8"),
            capture_output=True,
            check=False,
        )
        output = (proc.stdout or b"").decode("utf-8", errors="replace")
        output += ("\n" + (proc.stderr or b"").decode("utf-8", errors="replace")) if proc.stderr else ""
        return proc.returncode, output.strip()

    def _safe_stop(self) -> None:
        try:
            self._request("POST", "/api/intents/dispatch", {"intent": "safe_stop", "args": {}}, timeout_s=10.0)
        except Exception:
            pass

    def _robot_pose_components(self, state: dict[str, Any]) -> tuple[float, float, float]:
        belief = state.get("belief", {}) if isinstance(state.get("belief"), dict) else {}
        robot_pose = belief.get("latest_robot_pose", {}) if isinstance(belief.get("latest_robot_pose"), dict) else {}
        robot_x = clean_number(robot_pose.get("x"))
        robot_y = clean_number(robot_pose.get("y"))
        robot_yaw = clean_number(robot_pose.get("yaw"))
        if robot_x is None or robot_y is None or robot_yaw is None:
            raise RuntimeError("Robot pose unavailable for gather mission.")
        return robot_x, robot_y, robot_yaw

    def _set_robot_pose(self, state: dict[str, Any], *, x: float, y: float, yaw: float) -> None:
        compose_project = clean_text(state.get("compose_project"))
        if not compose_project:
            raise RuntimeError("Active compose project missing from dashboard state.")
        world_name = clean_text(state.get("world_name"), DEFAULT_WORLD_NAME)
        sim_gate_container = self._container_id(compose_project, "sim-gate")
        half_yaw = 0.5 * yaw
        robot_qz = math.sin(half_yaw)
        robot_qw = math.cos(half_yaw)
        script = f"""
set -eo pipefail
set +u
source /opt/ros/${{CORE_ROS_DISTRO:-kilted}}/setup.bash
set -u
WORLD_NAME={json.dumps(world_name)}
ROBOT_X={json.dumps(f"{x:.6f}")}
ROBOT_Y={json.dumps(f"{y:.6f}")}
ROBOT_QZ={json.dumps(f"{robot_qz:.6f}")}
ROBOT_QW={json.dumps(f"{robot_qw:.6f}")}
if command -v gz >/dev/null 2>&1; then
  gz service -s "/world/$WORLD_NAME/set_pose/blocking" --reqtype gz.msgs.Pose --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"jetbot\\" position {{ x: $ROBOT_X y: $ROBOT_Y z: 0.0 }} orientation {{ x: 0 y: 0 z: $ROBOT_QZ w: $ROBOT_QW }}"
fi
"""
        rc, output = self._docker_exec(sim_gate_container, script)
        if rc != 0:
            raise RuntimeError(f"Failed to set robot pose: {output}")

    def _spawn_model(
        self,
        *,
        compose_project: str,
        world_name: str,
        model_sdf_host: Path,
        model_name: str,
        x: float,
        y: float,
        z: float,
        yaw: float,
        log_path: Path,
    ) -> dict[str, Any]:
        sim_gate_container = self._container_id(compose_project, "sim-gate")
        model_sdf = to_container_repo_path(model_sdf_host.resolve())
        half_yaw = 0.5 * yaw
        qz = math.sin(half_yaw)
        qw = math.cos(half_yaw)
        script = f"""
set -eo pipefail
set +u
source /opt/ros/${{CORE_ROS_DISTRO:-kilted}}/setup.bash
set -u
MODEL_FILE={json.dumps(model_sdf)}
MODEL_NAME={json.dumps(model_name)}
WORLD_NAME={json.dumps(world_name)}
TARGET_X={json.dumps(f"{x:.6f}")}
TARGET_Y={json.dumps(f"{y:.6f}")}
TARGET_Z={json.dumps(f"{z:.6f}")}
TARGET_QZ={json.dumps(f"{qz:.6f}")}
TARGET_QW={json.dumps(f"{qw:.6f}")}
if command -v gz >/dev/null 2>&1; then
  gz service -s "/world/$WORLD_NAME/remove/blocking" --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"$MODEL_NAME\\" type: 2" >/dev/null 2>&1 || true
fi
spawn_create() {{
  local include_world="$1"
  local -a cmd=(ros2 run ros_gz_sim create)
  if [[ "$include_world" == "true" ]]; then
    cmd+=(-world "$WORLD_NAME")
  fi
  cmd+=(-file "$MODEL_FILE" -name "$MODEL_NAME" -x "$TARGET_X" -y "$TARGET_Y" -z "$TARGET_Z")
  "${{cmd[@]}}"
}}
set +e
spawn_create true > /tmp/chasecar_gather_spawn.log 2>&1
rc=$?
if [[ "$rc" -ne 0 ]] && grep -Eq 'Waiting for service \\[/world/.*/create\\] to become available' /tmp/chasecar_gather_spawn.log 2>/dev/null; then
  spawn_create false >> /tmp/chasecar_gather_spawn.log 2>&1
  rc=$?
fi
if [[ "$rc" -eq 0 ]] && command -v gz >/dev/null 2>&1; then
  gz service -s "/world/$WORLD_NAME/set_pose/blocking" --reqtype gz.msgs.Pose --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"$MODEL_NAME\\" position {{ x: $TARGET_X y: $TARGET_Y z: $TARGET_Z }} orientation {{ x: 0 y: 0 z: $TARGET_QZ w: $TARGET_QW }}" >> /tmp/chasecar_gather_spawn.log 2>&1
  setpose_rc=$?
  if [[ "$setpose_rc" -ne 0 ]]; then
    rc="$setpose_rc"
  fi
fi
cat /tmp/chasecar_gather_spawn.log
exit "$rc"
"""
        rc, output = self._docker_exec(sim_gate_container, script)
        log_path.write_text(output + "\n", encoding="utf-8")
        payload = {
            "generated_utc": utc_now(),
            "compose_project": compose_project,
            "world_name": world_name,
            "model_name": model_name,
            "model_sdf": str(model_sdf_host.resolve()),
            "world_pose": {"x": x, "y": y, "z": z, "yaw": yaw},
            "spawn_rc": rc,
            "log_path": str(log_path),
            "output": output,
            "pass": rc == 0,
        }
        if rc != 0:
            raise RuntimeError(f"Failed to spawn model {model_name}: {output}")
        return payload

    def _remove_model(self, *, compose_project: str, world_name: str, model_name: str) -> None:
        sim_gate_container = self._container_id(compose_project, "sim-gate")
        script = f"""
set -eo pipefail
set +u
source /opt/ros/${{CORE_ROS_DISTRO:-kilted}}/setup.bash
set -u
WORLD_NAME={json.dumps(world_name)}
MODEL_NAME={json.dumps(model_name)}
if command -v gz >/dev/null 2>&1; then
  gz service -s "/world/$WORLD_NAME/remove/blocking" --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"$MODEL_NAME\\" type: 2" || true
fi
"""
        self._docker_exec(sim_gate_container, script)

    def _target_model_name(self, target: GatherTargetSpec) -> str:
        safe_id = "".join(ch if ch.isalnum() else "_" for ch in target.id.lower())
        return f"{self.args.target_model_name}_{safe_id}"

    def _target_world_pose(self, target: GatherTargetSpec) -> dict[str, float]:
        anchor_x = float(DEFAULT_MISSION_START_POSE["x"])
        anchor_y = float(DEFAULT_MISSION_START_POSE["y"])
        anchor_yaw = float(DEFAULT_MISSION_START_POSE["yaw"])
        world_x = anchor_x + (math.cos(anchor_yaw) * target.forward_m) - (math.sin(anchor_yaw) * target.lateral_m)
        world_y = anchor_y + (math.sin(anchor_yaw) * target.forward_m) + (math.cos(anchor_yaw) * target.lateral_m)
        return {"x": round(world_x, 6), "y": round(world_y, 6), "z": round(target.z_m, 6)}

    def _truth_state_path(self, session_id: str) -> Path:
        return REPO_ROOT / "artifacts" / "session" / session_id / "visual" / "truth_state.json"

    def _load_truth_state(self, session_id: str) -> dict[str, Any]:
        return read_json(self._truth_state_path(session_id))

    def _wait_for_truth_models(self, session_id: str, expected_names: set[str], timeout_s: float) -> dict[str, Any]:
        deadline = time.monotonic() + max(timeout_s, 0.1)
        last_state: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last_state = self._load_truth_state(session_id)
            target_poses = last_state.get("target_poses_by_name") if isinstance(last_state.get("target_poses_by_name"), dict) else {}
            names_seen = set(str(name) for name in target_poses.keys())
            if expected_names.issubset(names_seen):
                return last_state
            time.sleep(0.5)
        raise RuntimeError(f"Truth probe did not report expected gather models: {sorted(expected_names)}")

    def _ball_truth_pose(self, session_id: str, target: GatherTargetSpec) -> dict[str, float] | None:
        truth_state = self._load_truth_state(session_id)
        target_poses = truth_state.get("target_poses_by_name") if isinstance(truth_state.get("target_poses_by_name"), dict) else {}
        model_pose = target_poses.get(self._target_model_name(target))
        if not isinstance(model_pose, dict):
            return None
        return truth_world_xy(model_pose)

    def _release_sample(
        self,
        *,
        release_started_monotonic: float,
        now_monotonic: float,
        ball_pose: dict[str, Any] | None,
        zone_score: Any,
    ) -> dict[str, Any]:
        sample = {
            "elapsed_s": round(max(float(now_monotonic) - float(release_started_monotonic), 0.0), 6),
            "ball_pose": ball_pose or {},
            "zone_distance_m": 0.0,
            "inside_zone": False,
            "center_inside_zone": False,
        }
        if zone_score is not None:
            sample.update(zone_score.to_dict())
        return sample

    def _final_corral_audit_snapshot(
        self,
        *,
        session_id: str,
        previous_poses: dict[str, dict[str, float] | None] | None = None,
    ) -> dict[str, Any]:
        current_poses: dict[str, dict[str, float] | None] = {}
        final_corral_audit: dict[str, dict[str, Any]] = {}
        for target in self.targets:
            ball_pose = self._ball_truth_pose(session_id, target)
            current_poses[target.id] = dict(ball_pose) if isinstance(ball_pose, dict) else None
            zone_score = zone_snapshot(ball_pose or {}, self.zone) if ball_pose else None
            ball_motion_m = pose_delta_m((previous_poses or {}).get(target.id), ball_pose)
            entry: dict[str, Any] = {
                "distance_to_zone_center_m": (
                    round(float(zone_score.retrieval_distance_m), 6) if zone_score is not None else None
                ),
                "inside_retrieval_corral": bool(zone_score and zone_score.center_inside_retrieval_corral),
                "stopped_in_corral": bool(
                    zone_score
                    and zone_score.center_inside_retrieval_corral
                    and ball_motion_m is not None
                    and ball_motion_m <= DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M
                ),
            }
            if ball_motion_m is not None:
                entry["ball_motion_m"] = round(float(ball_motion_m), 6)
            final_corral_audit[target.id] = entry
        retrieved_count = sum(1 for entry in final_corral_audit.values() if bool(entry.get("inside_retrieval_corral", False)))
        final_all_targets_inside_retrieval_corral = bool(final_corral_audit) and retrieved_count == len(self.targets)
        latest_all_targets_stopped = bool(final_corral_audit) and all(
            bool(entry.get("inside_retrieval_corral", False)) and bool(entry.get("stopped_in_corral", False))
            for entry in final_corral_audit.values()
        )
        return {
            "final_corral_audit": final_corral_audit,
            "retrieved_count": retrieved_count,
            "final_all_targets_inside_retrieval_corral": final_all_targets_inside_retrieval_corral,
            "latest_all_targets_stopped": latest_all_targets_stopped,
            "current_poses": current_poses,
        }

    def _run_final_corral_audit(self, *, session_id: str, state_history_path: Path) -> dict[str, Any]:
        self._safe_stop()
        self._set_manual_drive(
            False,
            mode="final_corral_audit",
            rationale="Holding the robot still while auditing all placed balls in the retrieval corral.",
        )
        deadline = time.monotonic() + max(
            DEFAULT_RELEASE_SETTLE_MAX_WAIT_S,
            DEFAULT_RELEASE_SETTLE_STABLE_WINDOW_S + 1.0,
        )
        stable_started_monotonic: float | None = None
        previous_poses: dict[str, dict[str, float] | None] = {}
        latest_snapshot = self._final_corral_audit_snapshot(session_id=session_id, previous_poses=None)
        latest_snapshot["final_all_targets_stopped"] = False
        latest_snapshot["final_three_ball_corral_pass"] = False
        while time.monotonic() < deadline:
            now_monotonic = time.monotonic()
            snapshot = self._final_corral_audit_snapshot(
                session_id=session_id,
                previous_poses=previous_poses if previous_poses else None,
            )
            previous_poses = snapshot.pop("current_poses", {})
            all_inside = bool(snapshot.get("final_all_targets_inside_retrieval_corral", False))
            latest_all_targets_stopped = bool(snapshot.get("latest_all_targets_stopped", False))
            if all_inside and latest_all_targets_stopped:
                stable_started_monotonic = (
                    now_monotonic if stable_started_monotonic is None else stable_started_monotonic
                )
            else:
                stable_started_monotonic = None
            stable_window_complete = bool(
                stable_started_monotonic is not None
                and (now_monotonic - stable_started_monotonic) >= DEFAULT_RELEASE_SETTLE_STABLE_WINDOW_S
            )
            snapshot["final_all_targets_stopped"] = stable_window_complete
            snapshot["final_three_ball_corral_pass"] = stable_window_complete and all_inside
            latest_snapshot = snapshot
            append_jsonl(
                state_history_path,
                {
                    "generated_utc": utc_now(),
                    "phase": "final_corral_audit",
                    "targets": snapshot.get("final_corral_audit", {}),
                    "retrieved_count": int(snapshot.get("retrieved_count", 0) or 0),
                    "final_all_targets_inside_retrieval_corral": bool(snapshot.get("final_all_targets_inside_retrieval_corral", False)),
                    "latest_all_targets_stopped": latest_all_targets_stopped,
                    "stable_window_complete": stable_window_complete,
                },
            )
            self._update_gather_runtime_state(
                mission_phase="final_corral_audit",
                gather_phase="final_corral_audit",
                latest_feedback="Auditing all gathered balls inside the retrieval corral.",
                final_corral_audit=snapshot.get("final_corral_audit", {}),
            )
            if bool(snapshot.get("final_three_ball_corral_pass", False)):
                self._append_runtime_event(
                    "Final three-ball corral audit passed.",
                    category="mission",
                    key=f"final_corral_audit_pass:{session_id}",
                )
                return latest_snapshot
            time.sleep(self.args.poll_s)
        self._append_runtime_event(
            "Final three-ball corral audit timed out before all balls settled inside the retrieval corral.",
            category="warn",
            key=f"final_corral_audit_timeout:{session_id}",
        )
        latest_snapshot["final_all_targets_stopped"] = False
        latest_snapshot["final_three_ball_corral_pass"] = False
        return latest_snapshot

    def _start_motion_bridge(self, compose_project: str, mission_root: Path) -> None:
        gate_stack_container = self._container_id(compose_project, "gate-stack")
        runtime_container_path = to_container_repo_path(self.gather_runtime_state_path)
        log_path = mission_root / "gather_motion_bridge.log"
        script = f"""
set -euo pipefail
PID_FILE="/tmp/chasecar_gather_motion_bridge.pid"
LOG_FILE="/tmp/chasecar_gather_motion_bridge.log"
pkill -f "gather_motion_bridge.py" 2>/dev/null || true
rm -f "$PID_FILE" "$LOG_FILE"
nohup bash -lc 'source /opt/ros/${{CORE_ROS_DISTRO:-kilted}}/setup.bash && if [ -f /root/ros2_ws/install/setup.bash ]; then source /root/ros2_ws/install/setup.bash; fi && python3 /workspaces/chasecar/scripts/gather_motion_bridge.py --runtime-json {json.dumps(runtime_container_path)} --loop-rate-hz {json.dumps(str(self.args.motion_loop_hz))}' >"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
sleep 1
cat "$LOG_FILE" || true
"""
        rc, output = self._docker_exec(gate_stack_container, script)
        log_path.write_text(output + "\n", encoding="utf-8")
        if rc != 0:
            raise RuntimeError(f"Failed to start gather motion bridge: {output}")

    def _stop_motion_bridge(self, compose_project: str) -> None:
        try:
            gate_stack_container = self._container_id(compose_project, "gate-stack")
        except Exception:
            return
        script = """
set +e
if [ -f /tmp/chasecar_gather_motion_bridge.pid ]; then
  PID="$(cat /tmp/chasecar_gather_motion_bridge.pid 2>/dev/null || true)"
  [ -n "$PID" ] && kill "$PID" 2>/dev/null || true
fi
pkill -f "gather_motion_bridge.py" 2>/dev/null || true
"""
        self._docker_exec(gate_stack_container, script)

    def _set_manual_drive(self, enabled: bool, *, linear_x: float = 0.0, angular_z: float = 0.0, mode: str = "idle", rationale: str = "") -> None:
        manual_drive = dict(self.gather_runtime_state.get("manual_drive", {}) or {})
        self._gather_sequence += 1
        manual_drive.update(
            {
                "enabled": bool(enabled),
                "sequence": self._gather_sequence,
                "mode": str(mode),
                "updated_utc": utc_now(),
                "command": {
                    "linear_x": round(float(linear_x), 6),
                    "angular_z": round(float(angular_z), 6),
                },
                "rationale": str(rationale or ""),
            }
        )
        self._update_gather_runtime_state(manual_drive=manual_drive)

    def _record_target_position(self, target_id: str, *, x: float, y: float, z: float = 0.05) -> None:
        target_positions = dict(self.visit_runtime_state.get("target_positions", {}) or {})
        target_positions[str(target_id)] = {
            "x": round(float(x), 6),
            "y": round(float(y), 6),
            "z": round(float(z), 6),
        }
        self._update_visit_runtime_state(target_positions=target_positions)

    def _update_prior_from_ball_pose(self, target_id: str, ball_pose: dict[str, Any] | None) -> None:
        if not ball_pose:
            return
        x = clean_number(ball_pose.get("x"))
        y = clean_number(ball_pose.get("y"))
        z = clean_number(ball_pose.get("z"))
        if x is None or y is None:
            return
        self._update_visit_runtime_state(current_target_prior={"x": round(x, 6), "y": round(y, 6)})
        self._record_target_position(target_id, x=x, y=y, z=z or 0.05)

    def _init_runtime_state(self, *, session_id: str, mission_root: Path) -> None:
        target_positions = {
            target.id: self._target_world_pose(target)
            for target in self.targets
        }
        self.visit_runtime_state = {
            "running": True,
            "scenario_id": str(self.args.scenario_id),
            "session_id": session_id,
            "world_file": self.world_file,
            "surface_profile": self.surface_profile,
            "proof_state": "waiting",
            "mission_phase": "setup",
            "mission_status": "running",
            "current_target_id": "",
            "visit_index": 0,
            "visited_targets": [],
            "remaining_targets": [item.id for item in self.targets],
            "last_visit_result": {},
            "mission_verdict": {},
            "latest_operator_event": "",
            "recent_operator_events": [],
            "latest_feedback": "",
            "current_target_prior": {},
            "target_positions": target_positions,
            "artifact_dir": str(mission_root),
            "updated_utc": utc_now(),
        }
        self.gather_runtime_state = {
            "running": True,
            "scenario_id": str(self.args.scenario_id),
            "session_id": session_id,
            "world_file": self.world_file,
            "surface_profile": self.surface_profile,
            "mission_phase": "setup",
            "mission_status": "running",
            "gather_phase": "setup",
            "current_target_id": "",
            "visit_index": 0,
            "placed_targets": [],
            "remaining_targets": [item.id for item in self.targets],
            "route_order": [],
            "capture_state": {},
            "capture_loss_count": 0,
            "zone_pose": {
                "x": round(self.zone.world_x, 6),
                "y": round(self.zone.world_y, 6),
                "radius_m": round(self.zone.retrieval_radius_m, 6),
                "control_radius_m": round(self.zone.control_radius_m, 6),
                "dwell_s": round(self.zone.dwell_s, 6),
            },
            "zone_score": {},
            "final_corral_audit": {},
            "settle_metrics": {},
            "manual_drive": {
                "enabled": False,
                "sequence": 0,
                "mode": "idle",
                "updated_utc": utc_now(),
                "command": {"linear_x": 0.0, "angular_z": 0.0},
                "rationale": "",
            },
            "latest_control_command": {},
            "latest_feedback": "",
            "mission_verdict": {},
            "latest_operator_event": "",
            "recent_operator_events": [],
            "artifact_dir": str(mission_root),
            "updated_utc": utc_now(),
        }
        self._persist_visit_runtime_state()
        self._persist_gather_runtime_state()

    def _spawn_mission_models(self, ready_state: dict[str, Any], mission_root: Path) -> None:
        compose_project = clean_text(ready_state.get("compose_project"))
        world_name = clean_text(ready_state.get("world_name"), DEFAULT_WORLD_NAME)
        self._set_robot_pose(
            ready_state,
            x=float(DEFAULT_MISSION_START_POSE["x"]),
            y=float(DEFAULT_MISSION_START_POSE["y"]),
            yaw=float(DEFAULT_MISSION_START_POSE["yaw"]),
        )
        self._wait_for_robot_pose_near(
            x=float(DEFAULT_MISSION_START_POSE["x"]),
            y=float(DEFAULT_MISSION_START_POSE["y"]),
            yaw=float(DEFAULT_MISSION_START_POSE["yaw"]),
        )
        self._remove_model(compose_project=compose_project, world_name=world_name, model_name=self.args.zone_model_name)
        self._spawn_model(
            compose_project=compose_project,
            world_name=world_name,
            model_sdf_host=Path(self.args.zone_model_sdf).resolve(),
            model_name=self.args.zone_model_name,
            x=float(self.zone.world_x),
            y=float(self.zone.world_y),
            z=float(self.zone.z_m),
            yaw=0.0,
            log_path=mission_root / "zone_spawn.log",
        )
        for target in self.targets:
            world_pose = self._target_world_pose(target)
            self._spawn_model(
                compose_project=compose_project,
                world_name=world_name,
                model_sdf_host=Path(self.args.target_model_sdf).resolve(),
                model_name=self._target_model_name(target),
                x=float(world_pose["x"]),
                y=float(world_pose["y"]),
                z=float(world_pose["z"]),
                yaw=0.0,
                log_path=mission_root / f"{target.id}_spawn.log",
            )
            self._record_target_position(target.id, x=float(world_pose["x"]), y=float(world_pose["y"]), z=float(world_pose["z"]))

    def _clear_mission_models(self, state: dict[str, Any]) -> None:
        compose_project = clean_text(state.get("compose_project"))
        if not compose_project:
            return
        world_name = clean_text(state.get("world_name"), DEFAULT_WORLD_NAME)
        try:
            self._remove_model(compose_project=compose_project, world_name=world_name, model_name=self.args.zone_model_name)
        except Exception:
            pass
        for target in self.targets:
            try:
                self._remove_model(compose_project=compose_project, world_name=world_name, model_name=self._target_model_name(target))
            except Exception:
                pass

    def _nearest_remaining_route(self, remaining_ids: list[str], state: dict[str, Any]) -> list[str]:
        robot_pose = state.get("belief", {}).get("latest_robot_pose") if isinstance(state.get("belief"), dict) else {}
        robot_xyyaw = world_pose_xyyaw(robot_pose if isinstance(robot_pose, dict) else {})
        if robot_xyyaw is None:
            return list(remaining_ids)
        robot_x, robot_y, _robot_yaw = robot_xyyaw
        ordered = sorted(
            remaining_ids,
            key=lambda target_id: math.hypot(
                float(self._target_world_pose(self.targets_by_id[target_id])["x"]) - robot_x,
                float(self._target_world_pose(self.targets_by_id[target_id])["y"]) - robot_y,
            ),
        )
        return ordered

    def _plan_collection_route(self, remaining_ids: list[str], state: dict[str, Any]) -> list[str]:
        if len(remaining_ids) <= 1:
            return list(remaining_ids)

        enabled, disabled_reason = self.provider.is_enabled()
        if not enabled:
            self._append_runtime_event(
                f"Collection planner unavailable ({disabled_reason}); falling back to nearest target ordering.",
                category="warning",
                key="collection_planner_disabled",
            )
            return self._nearest_remaining_route(remaining_ids, state)

        target_details: list[dict[str, Any]] = []
        robot_pose = state.get("belief", {}).get("latest_robot_pose") if isinstance(state.get("belief"), dict) else {}
        robot_xyyaw = world_pose_xyyaw(robot_pose if isinstance(robot_pose, dict) else {})
        for target_id in remaining_ids:
            target = self.targets_by_id[target_id]
            world_pose = self._target_world_pose(target)
            zone_distance_m = math.hypot(float(world_pose["x"]) - self.zone.world_x, float(world_pose["y"]) - self.zone.world_y)
            entry = {
                "target_id": target.id,
                "label": target.label,
                "world": {"x": world_pose["x"], "y": world_pose["y"]},
                "zone_distance_m": round(zone_distance_m, 6),
                "start_visible": bool(target.start_visible),
            }
            if robot_xyyaw is not None:
                entry["robot_distance_m"] = round(
                    math.hypot(float(world_pose["x"]) - robot_xyyaw[0], float(world_pose["y"]) - robot_xyyaw[1]),
                    6,
                )
            target_details.append(entry)

        try:
            if hasattr(self.provider, "plan_collection_route"):
                ordered = self.provider.plan_collection_route(  # type: ignore[attr-defined]
                    remaining_target_ids=list(remaining_ids),
                    target_details=target_details,
                    zone_details={
                        "world_x": round(self.zone.world_x, 6),
                        "world_y": round(self.zone.world_y, 6),
                        "radius_m": round(self.zone.retrieval_radius_m, 6),
                        "control_radius_m": round(self.zone.control_radius_m, 6),
                    },
                    placed_targets=list(self.gather_runtime_state.get("placed_targets", [])),
                    mission_state={
                        "scenario_id": self.args.scenario_id,
                        "robot_pose": robot_pose if isinstance(robot_pose, dict) else {},
                    },
                    timeout_s=self.args.timeout_s,
                )
            else:
                ordered = self.provider.plan_route(  # type: ignore[attr-defined]
                    remaining_target_ids=list(remaining_ids),
                    target_details=target_details,
                    timeout_s=self.args.timeout_s,
                )
            ordered_ids = [target_id for target_id in ordered if target_id in remaining_ids]
            if set(ordered_ids) != set(remaining_ids):
                raise ProviderError(f"Collection route returned {ordered_ids}, expected exactly {remaining_ids}")
            return ordered_ids
        except Exception as exc:
            self._append_runtime_event(
                f"Collection planner failed ({exc}); falling back to nearest target ordering.",
                category="warning",
                key=f"collection_plan_fallback:{','.join(sorted(remaining_ids))}",
            )
            return self._nearest_remaining_route(remaining_ids, state)

    def _dispatch_visit_target(self, target_id: str) -> None:
        deadline = time.monotonic() + 12.0
        last_payload: dict[str, Any] = {}
        while time.monotonic() < deadline:
            status, payload = dispatch_intent(
                self.dashboard_url,
                "visit_target",
                {"target_id": target_id},
                timeout_s=self.args.timeout_s,
            )
            last_payload = payload
            if status == 202 and bool(payload.get("accepted", False)):
                return
            if "intent already in progress" not in clean_text(payload.get("error")).lower():
                break
            time.sleep(0.5)
        raise RuntimeError(f"visit_target dispatch rejected for {target_id}: {last_payload}")

    def _wait_for_visit_result(
        self,
        *,
        timeout_s: float,
        baseline_status: str,
        baseline_feedback: str,
        target_id: str,
    ) -> tuple[bool, dict[str, Any], str]:
        deadline = time.monotonic() + max(timeout_s, 0.1)
        last_state: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last_state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
            brain = last_state.get("brain", {}) if isinstance(last_state.get("brain"), dict) else {}
            status = clean_text(brain.get("last_feedback_status"))
            feedback = clean_text(brain.get("last_feedback_text") or last_state.get("last_feedback"))
            self._update_gather_runtime_state(latest_feedback=feedback)
            self._update_visit_runtime_state(latest_feedback=feedback)
            if status == baseline_status and feedback == baseline_feedback:
                time.sleep(self.args.poll_s)
                continue
            if status == "visit_target_reached" or feedback.lower() == f"visit_target: {target_id.lower()} reached":
                return True, last_state, status
            if status == "visit_target_failed" or (feedback.lower().startswith(f"visit_target: {target_id.lower()} failed")):
                return False, last_state, status
            time.sleep(self.args.poll_s)
        return False, last_state, "visit_target_timeout"

    def _control_loop_state(
        self,
        *,
        session_id: str,
        target: GatherTargetSpec,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, float] | None]:
        dashboard_state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
        robot_pose = dashboard_state.get("belief", {}).get("latest_robot_pose") if isinstance(dashboard_state.get("belief"), dict) else {}
        robot_world = robot_pose if isinstance(robot_pose, dict) else {}
        ball_pose = self._ball_truth_pose(session_id, target)
        return dashboard_state, robot_world, ball_pose

    def _capture_target(
        self,
        *,
        session_id: str,
        target: GatherTargetSpec,
        state_history_path: Path,
        mission_root: Path,
        prefer_zone_recovery: bool = False,
    ) -> tuple[bool, dict[str, Any]]:
        deadline = time.monotonic() + max(self.args.capture_timeout_s, 0.1)
        captured_started_monotonic: float | None = None
        zone_centered_started_monotonic: float | None = None
        previous_ball_pose: dict[str, Any] | None = None
        last_capture = None
        last_zone_score = None
        while time.monotonic() < deadline:
            now_monotonic = time.monotonic()
            _dashboard_state, robot_pose, ball_pose = self._control_loop_state(session_id=session_id, target=target)
            capture = capture_snapshot(robot_pose, ball_pose or {}, self.capture_envelope) if robot_pose and ball_pose else None
            zone_score = zone_snapshot(ball_pose or {}, self.zone) if ball_pose else None
            ball_motion_m = pose_delta_m(previous_ball_pose, ball_pose) if previous_ball_pose is not None else None
            last_capture = capture
            last_zone_score = zone_score
            if capture and capture.captured:
                captured_started_monotonic = now_monotonic if captured_started_monotonic is None else captured_started_monotonic
            else:
                captured_started_monotonic = None
            if zone_score and zone_score.center_inside_zone:
                zone_centered_started_monotonic = (
                    now_monotonic if zone_centered_started_monotonic is None else zone_centered_started_monotonic
                )
            else:
                zone_centered_started_monotonic = None
            self._update_gather_runtime_state(
                mission_phase="capture",
                gather_phase="capture",
                capture_state=capture.to_dict() if capture else {},
                zone_score=zone_score.to_dict() if zone_score else {},
                latest_feedback=f"Capturing {target.label}.",
            )
            self._update_visit_runtime_state(
                proof_state="capturing",
                mission_phase="capture",
                latest_feedback=f"Capturing {target.label}.",
            )
            if ball_pose:
                self._update_prior_from_ball_pose(target.id, ball_pose)
            append_jsonl(
                state_history_path,
                {
                    "generated_utc": utc_now(),
                    "phase": "capture",
                    "target_id": target.id,
                    "robot_pose": robot_pose,
                    "ball_pose": ball_pose,
                    "capture": capture.to_dict() if capture else {},
                    "zone_score": zone_score.to_dict() if zone_score else {},
                    "ball_motion_m": ball_motion_m,
                },
            )
            zone_entry_handoff_ready = bool(
                zone_score
                and zone_score.center_inside_zone
                and zone_centered_started_monotonic is not None
                and (now_monotonic - zone_centered_started_monotonic) >= 0.5
                and (
                    ball_motion_m is None
                    or ball_motion_m <= max(DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M * 2.0, 0.02)
                )
            )
            if zone_entry_handoff_ready:
                self._set_manual_drive(False, mode="capture_handoff", rationale="Ball reached zone during capture; handing off to place verification.")
                return True, {
                    "capture_state": capture.to_dict() if capture else {},
                    "zone_score": zone_score.to_dict(),
                    "entered_zone_during_capture": True,
                    "handoff_kind": "zone_entry",
                }
            if secure_capture(capture, self.capture_envelope):
                self._set_manual_drive(False, mode="captured", rationale="Ball captured.")
                return True, {
                    "capture_state": capture.to_dict(),
                    "zone_score": zone_score.to_dict() if zone_score else {},
                    "handoff_kind": "secure_capture",
                }
            soft_capture_handoff_ready = bool(
                capture
                and capture.captured
                and captured_started_monotonic is not None
                and (now_monotonic - captured_started_monotonic) >= 0.5
                and float(capture.ball_x_m) <= 0.35
            )
            if soft_capture_handoff_ready:
                self._set_manual_drive(False, mode="capture_handoff", rationale="Ball is stably inside the spur; handing off to place control.")
                return True, {
                    "capture_state": capture.to_dict(),
                    "zone_score": zone_score.to_dict() if zone_score else {},
                    "soft_capture_handoff": True,
                    "handoff_kind": "soft_capture",
                }
            handoff_near_zone_control = False
            if robot_pose and ball_pose:
                handoff_near_zone_control = bool(
                    not prefer_zone_recovery
                    and capture
                    and capture.ball_ahead
                    and zone_score is not None
                    and (
                        capture.within_recapture_window
                        or float(zone_score.zone_distance_m) <= (float(self.zone.control_radius_m) + 0.35)
                    )
                )
                if prefer_zone_recovery:
                    use_zone_recovery = bool(
                        capture
                        and capture.ball_ahead
                        and (
                            capture.within_recapture_window
                            or (
                                zone_score is not None
                                and float(zone_score.zone_distance_m) <= (float(self.zone.control_radius_m) + 0.35)
                            )
                        )
                    )
                    if use_zone_recovery:
                        command = compute_place_command(
                            robot_pose,
                            ball_pose or {},
                            zone=self.zone,
                            envelope=self.capture_envelope,
                        )
                    else:
                        command = compute_capture_command(robot_pose, ball_pose or {}, envelope=self.capture_envelope)
                elif handoff_near_zone_control:
                    command = compute_place_command(
                        robot_pose,
                        ball_pose or {},
                        zone=self.zone,
                        envelope=self.capture_envelope,
                    )
                else:
                    command = compute_capture_command(robot_pose, ball_pose or {}, envelope=self.capture_envelope)
            else:
                command = None
            if prefer_zone_recovery and command is not None:
                angular_limit = 0.50
                linear_limit = 0.055
                rationale = "Keep the ball local during post-place recapture instead of driving through it."
                if capture and not capture.ball_ahead:
                    linear_limit = 0.0
                    angular_limit = 0.90
                    rationale = "Ball slipped behind after place; turn in place quickly before it leaves local recovery range."
                elif capture and capture.within_recapture_window:
                    if float(capture.ball_x_m) > 0.40 or abs(float(capture.ball_y_m)) > 0.08:
                        linear_limit = 0.0
                        angular_limit = 0.35
                        rationale = "Ball is ahead but not seated; rotate under it before nudging forward again."
                    elif float(capture.ball_x_m) > 0.34:
                        linear_limit = 0.015
                        angular_limit = 0.40
                elif capture:
                    linear_limit = 0.02
                    angular_limit = 0.65
                    rationale = "Ball is still local but outside the spur mouth; bias toward turning before chasing forward."
                command = command.__class__(
                    mode="place_recapture_hold" if capture and capture.within_recapture_window else command.mode,
                    linear_x=min(float(command.linear_x), linear_limit),
                    angular_z=clamp(float(command.angular_z), -angular_limit, angular_limit),
                    target_speed_scale=min(float(command.target_speed_scale), 0.55 if linear_limit > 0.02 else 0.35),
                    rationale=rationale,
                )
            elif handoff_near_zone_control and command is not None:
                linear_limit = 0.03
                angular_limit = 0.35
                rationale = "Near the corral, switch to a gentle handoff instead of driving through the ball."
                if zone_score and zone_score.center_inside_zone:
                    linear_limit = 0.0
                    angular_limit = 0.25
                    rationale = "Ball is already centered in the corral; stop and let friction settle it."
                elif zone_score and zone_score.inside_zone:
                    linear_limit = 0.012
                    angular_limit = 0.30
                    rationale = "Ball is already inside the corral overlap; creep only if needed."
                elif capture and capture.within_recapture_window and (
                    float(capture.ball_x_m) > 0.36 or abs(float(capture.ball_y_m)) > 0.06
                ):
                    linear_limit = 0.0
                    angular_limit = 0.30
                    rationale = "Ball is near the corral but not seated; hold and yaw gently before the final settle."
                command = command.__class__(
                    mode="capture_handoff_hold" if capture and capture.within_recapture_window else command.mode,
                    linear_x=min(float(command.linear_x), linear_limit),
                    angular_z=clamp(float(command.angular_z), -angular_limit, angular_limit),
                    target_speed_scale=min(float(command.target_speed_scale), 0.45 if linear_limit > 0.015 else 0.30),
                    rationale=rationale,
                )
            if command is not None:
                self._set_manual_drive(
                    True,
                    linear_x=command.linear_x,
                    angular_z=command.angular_z,
                    mode=command.mode,
                    rationale=command.rationale,
                )
                self._update_gather_runtime_state(latest_control_command=command.to_dict())
            previous_ball_pose = dict(ball_pose or {}) if ball_pose else previous_ball_pose
            time.sleep(self.args.poll_s)

        self._set_manual_drive(False, mode="capture_timeout", rationale="Capture timed out.")
        last_capture_payload = last_capture.to_dict() if last_capture else {}
        last_zone_payload = last_zone_score.to_dict() if last_zone_score else {}
        correction_eligible = zone_edge_correction_eligible(
            capture=last_capture,
            zone_score=last_zone_score,
            zone=self.zone,
        )
        timeout_payload = {
            "failure_reason": "capture_timeout",
            "failure_stage": "capture",
            "capture_state": last_capture_payload,
            "zone_score": last_zone_payload,
            "zone_edge_correction_eligible": bool(correction_eligible),
            "allow_full_revisit": False,
        }
        write_json(mission_root / f"{target.id}_capture_timeout.json", timeout_payload)
        return False, timeout_payload

    def _place_target(
        self,
        *,
        session_id: str,
        target: GatherTargetSpec,
        state_history_path: Path,
    ) -> tuple[bool, dict[str, Any]]:
        deadline = time.monotonic() + max(self.args.place_timeout_s, 0.1)
        last_captured_monotonic: float | None = None
        local_recovery_attempted = False
        local_recovery_started_monotonic: float | None = None
        recaptured_settle_started_monotonic: float | None = None
        release_origin_monotonic: float | None = None
        release_monitoring_active = False
        release_samples: list[dict[str, Any]] = []
        release_prev_ball_pose: dict[str, Any] | None = None
        release_recontact_count = 0
        release_inside_seen = False
        marginal_capture_started_monotonic: float | None = None
        zone_edge_correction_started_monotonic: float | None = None
        escaped_zone_correction_started_monotonic: float | None = None
        stop_capture_state: dict[str, Any] = {}
        stopped_with_ball_captured = False
        release_capture_state: dict[str, Any] = {}
        release_started_with_capture = False
        zone_edge_correction_count = 0
        retrieval_centered_started_monotonic: float | None = None
        control_centered_started_monotonic: float | None = None
        pre_release_still_started_monotonic: float | None = None

        def _record_stop_capture(current_capture: Any) -> None:
            nonlocal stop_capture_state
            nonlocal stopped_with_ball_captured
            stop_capture_state = current_capture.to_dict() if current_capture else {}
            stopped_with_ball_captured = secure_capture(current_capture, self.capture_envelope)

        def _record_release_capture(current_capture: Any) -> None:
            nonlocal release_capture_state
            nonlocal release_started_with_capture
            release_capture_state = current_capture.to_dict() if current_capture else {}
            release_started_with_capture = secure_capture(current_capture, self.capture_envelope)

        def _retention_fields() -> dict[str, Any]:
            return {
                "stopped_with_ball_captured": bool(stopped_with_ball_captured),
                "release_started_with_capture": bool(release_started_with_capture),
                "stop_capture_state": dict(stop_capture_state),
                "release_capture_state": dict(release_capture_state),
            }

        def _place_diagnostics(
            *,
            current_capture: Any = None,
            current_zone_score: Any = None,
            allow_full_revisit: bool | None = None,
        ) -> dict[str, Any]:
            correction_eligible = zone_edge_correction_eligible(
                capture=current_capture,
                zone_score=current_zone_score,
                zone=self.zone,
            )
            return {
                "zone_edge_correction_count": int(zone_edge_correction_count),
                "zone_edge_correction_eligible": bool(correction_eligible),
                "allow_full_revisit": (
                    not bool(correction_eligible)
                    if allow_full_revisit is None
                    else bool(allow_full_revisit)
                ),
            }

        def _local_settle_correction_eligible(
            *,
            current_capture: Any = None,
            current_zone_score: Any = None,
        ) -> bool:
            if current_zone_score and bool(current_zone_score.inside_retrieval_corral):
                return True
            return bool(
                current_capture
                and current_capture.within_recapture_window
                and current_zone_score
                and float(current_zone_score.zone_distance_m)
                <= (float(self.zone.retrieval_radius_m) + 0.12)
            )

        def _settle_metrics() -> dict[str, Any]:
            return summarize_release_settle_trace(
                surface_profile=self.surface_profile,
                zone=self.zone,
                release_samples=release_samples,
                release_recontact_count=release_recontact_count,
            ).to_dict()

        def _settle_fields(metrics: dict[str, Any] | None = None) -> dict[str, Any]:
            active_metrics = metrics if isinstance(metrics, dict) else _settle_metrics()
            return {
                "final_inside_retrieval_corral": bool(active_metrics.get("final_inside_retrieval_corral", False)),
                "final_center_inside_zone": bool(active_metrics.get("final_center_inside_zone", False)),
                "ball_stopped_in_corral": bool(active_metrics.get("ball_stopped_in_corral", False)),
                "rolled_away_after_release": bool(active_metrics.get("rolled_away_after_release", False)),
                "settled_in_corral_pass": bool(active_metrics.get("settled_in_corral_pass", False)),
                "settle_exit_reason": clean_text(active_metrics.get("settle_exit_reason")),
            }

        def _settle_monitor_ready(
            *,
            current_capture: Any = None,
            current_zone_score: Any = None,
            ball_motion_m: float | None = None,
            now_monotonic: float,
        ) -> bool:
            if not current_zone_score or not bool(current_zone_score.center_inside_retrieval_corral):
                return False
            if bool(current_zone_score.center_inside_zone):
                corridor_ready = True
            else:
                corridor_ready = float(current_zone_score.zone_distance_m) <= max(
                    float(self.zone.control_radius_m) + 0.20,
                    float(self.zone.retrieval_radius_m) - 0.10,
                )
            if not corridor_ready:
                return False
            dwell_started = (
                control_centered_started_monotonic
                if bool(current_zone_score.center_inside_zone)
                else retrieval_centered_started_monotonic
            )
            if dwell_started is None or (now_monotonic - dwell_started) < 0.5:
                return False
            if current_capture and (current_capture.captured or current_capture.within_recapture_window):
                required_still_s = 0.5
            else:
                required_still_s = DEFAULT_RELEASE_SETTLE_STABLE_WINDOW_S
            if (
                pre_release_still_started_monotonic is None
                or (now_monotonic - pre_release_still_started_monotonic) < required_still_s
            ):
                return False
            if current_capture and (current_capture.captured or current_capture.within_recapture_window):
                return ball_motion_m is None or ball_motion_m <= max(DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M * 2.0, 0.02)
            return ball_motion_m is not None and ball_motion_m <= DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M

        def _reset_release_monitor(current_ball_pose: dict[str, Any] | None = None) -> None:
            nonlocal release_monitoring_active
            nonlocal release_origin_monotonic
            nonlocal release_samples
            nonlocal release_prev_ball_pose
            nonlocal release_inside_seen
            release_monitoring_active = False
            release_origin_monotonic = None
            release_samples = []
            release_prev_ball_pose = dict(current_ball_pose or {}) if current_ball_pose else None
            release_inside_seen = False

        def _begin_release_monitor(
            *,
            now_monotonic: float,
            current_capture: Any,
            current_ball_pose: dict[str, Any] | None,
            current_zone_score: Any,
            rationale: str,
            feedback: str,
        ) -> None:
            nonlocal release_monitoring_active
            nonlocal release_origin_monotonic
            nonlocal release_samples
            nonlocal release_prev_ball_pose
            nonlocal release_inside_seen
            _record_stop_capture(current_capture)
            _record_release_capture(current_capture)
            release_monitoring_active = True
            release_origin_monotonic = now_monotonic
            release_samples = [
                self._release_sample(
                    release_started_monotonic=now_monotonic,
                    now_monotonic=now_monotonic,
                    ball_pose=current_ball_pose,
                    zone_score=current_zone_score,
                )
            ]
            release_prev_ball_pose = dict(current_ball_pose or {}) if current_ball_pose else None
            release_inside_seen = bool(current_zone_score.center_inside_retrieval_corral) if current_zone_score else False
            self._set_manual_drive(False, mode="release_settle", rationale=rationale)
            self._update_gather_runtime_state(
                latest_feedback=feedback,
                settle_metrics=_settle_metrics(),
            )

        while time.monotonic() < deadline:
            now_monotonic = time.monotonic()
            _dashboard_state, robot_pose, ball_pose = self._control_loop_state(session_id=session_id, target=target)
            capture = capture_snapshot(robot_pose, ball_pose or {}, self.capture_envelope) if robot_pose and ball_pose else None
            zone_score = zone_snapshot(ball_pose or {}, self.zone) if ball_pose else None
            zone_edge_eligible = zone_edge_correction_eligible(
                capture=capture,
                zone_score=zone_score,
                zone=self.zone,
            )
            local_settle_correction_eligible = _local_settle_correction_eligible(
                current_capture=capture,
                current_zone_score=zone_score,
            )
            if ball_pose:
                self._update_prior_from_ball_pose(target.id, ball_pose)
            if capture and capture.captured:
                last_captured_monotonic = now_monotonic
                if local_recovery_started_monotonic is not None:
                    local_recovery_started_monotonic = None
                    recaptured_settle_started_monotonic = now_monotonic
            if zone_score and zone_score.center_inside_retrieval_corral:
                retrieval_centered_started_monotonic = (
                    now_monotonic
                    if retrieval_centered_started_monotonic is None
                    else retrieval_centered_started_monotonic
                )
            else:
                retrieval_centered_started_monotonic = None
            if zone_score and zone_score.center_inside_zone:
                control_centered_started_monotonic = (
                    now_monotonic
                    if control_centered_started_monotonic is None
                    else control_centered_started_monotonic
                )
            else:
                control_centered_started_monotonic = None
            self._update_gather_runtime_state(
                mission_phase="place",
                gather_phase="place",
                capture_state=capture.to_dict() if capture else {},
                zone_score=zone_score.to_dict() if zone_score else {},
                latest_feedback=f"Placing {target.label} into the zone.",
            )
            self._update_visit_runtime_state(
                proof_state="placing",
                mission_phase="place",
                latest_feedback=f"Placing {target.label} into the zone.",
            )
            ball_motion_m = pose_delta_m(release_prev_ball_pose, ball_pose) if release_prev_ball_pose is not None else None
            still_motion_threshold = (
                max(DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M * 2.0, 0.02)
                if capture and (capture.captured or capture.within_recapture_window)
                else DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M
            )
            if (
                zone_score
                and zone_score.center_inside_retrieval_corral
                and ball_motion_m is not None
                and ball_motion_m <= still_motion_threshold
            ):
                pre_release_still_started_monotonic = (
                    now_monotonic
                    if pre_release_still_started_monotonic is None
                    else pre_release_still_started_monotonic
                )
            else:
                pre_release_still_started_monotonic = None
            append_jsonl(
                state_history_path,
                {
                    "generated_utc": utc_now(),
                    "phase": "place",
                    "target_id": target.id,
                    "robot_pose": robot_pose,
                    "ball_pose": ball_pose,
                    "capture": capture.to_dict() if capture else {},
                    "zone_score": zone_score.to_dict() if zone_score else {},
                    "local_recovery_active": bool(local_recovery_started_monotonic is not None),
                    "local_recovery_attempted": bool(local_recovery_attempted),
                    "zone_edge_correction_eligible": bool(local_settle_correction_eligible),
                    "zone_edge_correction_count": int(zone_edge_correction_count),
                    "release_monitoring_active": bool(release_monitoring_active),
                    "release_recontact_count": int(release_recontact_count),
                    "ball_motion_m": ball_motion_m,
                },
            )
            if release_monitoring_active and release_origin_monotonic is not None:
                release_sample = self._release_sample(
                    release_started_monotonic=release_origin_monotonic,
                    now_monotonic=now_monotonic,
                    ball_pose=ball_pose,
                    zone_score=zone_score,
                )
                if ball_motion_m is not None:
                    release_sample["ball_motion_m"] = ball_motion_m
                release_samples.append(release_sample)
                release_prev_ball_pose = dict(ball_pose or {})
                if zone_score and zone_score.center_inside_retrieval_corral:
                    release_inside_seen = True
                settle_metrics = _settle_metrics()
                self._set_manual_drive(
                    False,
                    mode="release_settle",
                    rationale=f"Ball entered the release corridor; letting {self.surface_profile} friction settle it.",
                )
                self._update_gather_runtime_state(
                    latest_feedback=f"Letting {target.label} settle on {self.surface_profile}.",
                    settle_metrics=settle_metrics,
                )
                if bool(settle_metrics.get("settled_in_corral_pass", False)):
                    settle_exit_reason = default_settle_exit_reason(
                        settled_in_corral_pass=True,
                        corrected=bool(zone_edge_correction_count or release_recontact_count),
                    )
                    return True, {
                        "capture_state": capture.to_dict() if capture else {},
                        "zone_score": zone_score.to_dict() if zone_score else {},
                        "final_ball_pose": ball_pose,
                        "settle_metrics": {**settle_metrics, "settle_exit_reason": settle_exit_reason},
                        "release_recontact_count": release_recontact_count,
                        "settle_exit_reason": settle_exit_reason,
                        **_place_diagnostics(current_capture=capture, current_zone_score=zone_score, allow_full_revisit=False),
                        **_settle_fields({**settle_metrics, "settle_exit_reason": settle_exit_reason}),
                        **_retention_fields(),
                    }
                release_elapsed_s = now_monotonic - release_origin_monotonic
                within_zone_overlap = bool(zone_score and zone_score.inside_retrieval_corral)
                center_inside_now = bool(zone_score and zone_score.center_inside_retrieval_corral)
                if within_zone_overlap and (ball_motion_m is None or ball_motion_m > DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M):
                    self._update_gather_runtime_state(
                        latest_feedback=f"Letting {target.label} keep settling inside the corral overlap.",
                        settle_metrics=settle_metrics,
                    )
                    time.sleep(self.args.poll_s)
                    continue
                if (
                    not bool(settle_metrics.get("final_inside_retrieval_corral", False))
                    and not within_zone_overlap
                    and release_elapsed_s >= DEFAULT_RELEASE_SETTLE_STABLE_WINDOW_S
                    and capture
                    and capture.within_recapture_window
                    and local_settle_correction_eligible
                    and release_recontact_count < 1
                ):
                    release_recontact_count += 1
                    zone_edge_correction_count += 1
                    zone_edge_correction_started_monotonic = now_monotonic
                    _reset_release_monitor(ball_pose)
                    self._append_runtime_event(
                        f"{target.label}: gentle recontact after short release on {self.surface_profile}.",
                        key=f"release_recontact_short:{target.id}:{release_recontact_count}",
                    )
                    self._update_gather_runtime_state(
                        latest_feedback=f"Recontacting {target.label} after short release.",
                        settle_metrics=settle_metrics,
                    )
                elif bool(settle_metrics.get("rolled_away_after_release", False)):
                    if within_zone_overlap and (ball_motion_m is None or ball_motion_m > DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M):
                        self._update_gather_runtime_state(
                            latest_feedback=f"Watching {target.label} settle near the corral edge.",
                            settle_metrics=settle_metrics,
                        )
                    elif (
                        release_recontact_count < 1
                        and (
                            local_settle_correction_eligible
                            or within_zone_overlap
                        )
                    ):
                        release_recontact_count += 1
                        zone_edge_correction_count += 1
                        zone_edge_correction_started_monotonic = now_monotonic
                        _reset_release_monitor(ball_pose)
                        feedback = (
                            f"Recontacting {target.label} after an edge settle outside the retrieval corral."
                            if within_zone_overlap and not (capture and capture.within_recapture_window)
                            else f"Recontacting {target.label} after release roll-away."
                        )
                        self._append_runtime_event(
                            f"{target.label}: gentle recontact after release drift on {self.surface_profile}.",
                            key=f"release_recontact_overshoot:{target.id}:{release_recontact_count}",
                        )
                        self._update_gather_runtime_state(
                            latest_feedback=feedback,
                            settle_metrics=settle_metrics,
                        )
                    else:
                        self._set_manual_drive(False, mode="release_roll_away", rationale="Ball rolled away from the corral after release.")
                        settle_exit_reason = default_settle_exit_reason(
                            failure_reason="release_roll_away",
                            rolled_away_after_release=True,
                        )
                        return False, {
                            "failure_reason": "release_roll_away",
                            "failure_stage": "release",
                            "capture_state": capture.to_dict() if capture else {},
                            "zone_score": zone_score.to_dict() if zone_score else {},
                            "local_recovery_attempted": local_recovery_attempted,
                            "settle_metrics": {**settle_metrics, "settle_exit_reason": settle_exit_reason},
                            "release_recontact_count": release_recontact_count,
                            "settle_exit_reason": settle_exit_reason,
                            **_place_diagnostics(current_capture=capture, current_zone_score=zone_score, allow_full_revisit=False),
                            **_settle_fields({**settle_metrics, "settle_exit_reason": settle_exit_reason}),
                            **_retention_fields(),
                        }
                elif release_elapsed_s >= max(DEFAULT_RELEASE_SETTLE_MAX_WAIT_S, DEFAULT_RELEASE_SETTLE_STABLE_WINDOW_S + 3.0):
                    if within_zone_overlap and center_inside_now:
                        self._update_gather_runtime_state(
                            latest_feedback=f"Waiting for {target.label} to fully stop inside the corral.",
                            settle_metrics=settle_metrics,
                        )
                    elif (
                        within_zone_overlap
                        and not center_inside_now
                        and release_recontact_count < 1
                        and ball_motion_m is not None
                        and ball_motion_m <= DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M
                    ):
                        release_recontact_count += 1
                        zone_edge_correction_count += 1
                        zone_edge_correction_started_monotonic = now_monotonic
                        _reset_release_monitor(ball_pose)
                        self._append_runtime_event(
                            f"{target.label}: gentle recontact after stopping on the corral edge.",
                            key=f"release_recontact_edge:{target.id}:{release_recontact_count}",
                        )
                        self._update_gather_runtime_state(
                            latest_feedback=f"Nudging {target.label} back into the retrieval corral after it stopped on the edge.",
                            settle_metrics=settle_metrics,
                        )
                    elif (
                        release_recontact_count < 1
                        and (
                            (not within_zone_overlap and local_settle_correction_eligible)
                        )
                    ):
                        release_recontact_count += 1
                        zone_edge_correction_count += 1
                        zone_edge_correction_started_monotonic = now_monotonic
                        _reset_release_monitor(ball_pose)
                        self._append_runtime_event(
                            f"{target.label}: gentle recontact after long unsettled release on {self.surface_profile}.",
                            key=f"release_recontact_unsettled:{target.id}:{release_recontact_count}",
                        )
                        self._update_gather_runtime_state(
                            latest_feedback=f"Recontacting {target.label} after a long unsettled release.",
                            settle_metrics=settle_metrics,
                        )
                    else:
                        self._set_manual_drive(False, mode="release_unsettled", rationale="Ball did not finish retrieved and stopped in the corral.")
                        settle_exit_reason = default_settle_exit_reason(failure_reason="release_unsettled")
                        return False, {
                            "failure_reason": "release_unsettled",
                            "failure_stage": "release",
                            "capture_state": capture.to_dict() if capture else {},
                            "zone_score": zone_score.to_dict() if zone_score else {},
                            "local_recovery_attempted": local_recovery_attempted,
                            "settle_metrics": {**settle_metrics, "settle_exit_reason": settle_exit_reason},
                            "release_recontact_count": release_recontact_count,
                            "settle_exit_reason": settle_exit_reason,
                            **_place_diagnostics(current_capture=capture, current_zone_score=zone_score, allow_full_revisit=False),
                            **_settle_fields({**settle_metrics, "settle_exit_reason": settle_exit_reason}),
                            **_retention_fields(),
                        }
                time.sleep(self.args.poll_s)
                continue
            release_prev_ball_pose = dict(ball_pose or {}) if ball_pose else release_prev_ball_pose
            settle_monitor_ready = _settle_monitor_ready(
                current_capture=capture,
                current_zone_score=zone_score,
                ball_motion_m=ball_motion_m,
                now_monotonic=now_monotonic,
            )
            settle_shepherd_needed = bool(
                zone_score
                and zone_score.center_inside_retrieval_corral
                and capture
                and capture.ball_ahead
                and not capture.captured
                and not capture.within_recapture_window
                and not settle_monitor_ready
            )
            if (
                zone_score
                and zone_score.center_inside_retrieval_corral
                and settle_monitor_ready
            ):
                escaped_zone_correction_started_monotonic = None
                _begin_release_monitor(
                    now_monotonic=now_monotonic,
                    current_capture=capture,
                    current_ball_pose=ball_pose,
                    current_zone_score=zone_score,
                    rationale=f"Ball reached the practical retrieval corral; verifying settle on {self.surface_profile}.",
                    feedback=f"Letting {target.label} settle inside the retrieval corral.",
                )
                time.sleep(self.args.poll_s)
                continue
            if zone_score and zone_score.center_inside_zone and settle_monitor_ready:
                escaped_zone_correction_started_monotonic = None
                _begin_release_monitor(
                    now_monotonic=now_monotonic,
                    current_capture=capture,
                    current_ball_pose=ball_pose,
                    current_zone_score=zone_score,
                    rationale=f"Ball reached the corral center; verifying settle on {self.surface_profile}.",
                    feedback=f"Verifying that {target.label} settles in the corral.",
                )
                time.sleep(self.args.poll_s)
                continue
            if (
                release_ready(capture=capture, zone_score=zone_score, zone=self.zone)
                and capture
                and (capture.captured or capture.within_recapture_window)
            ):
                marginal_capture_started_monotonic = None
                escaped_zone_correction_started_monotonic = None
                _begin_release_monitor(
                    now_monotonic=now_monotonic,
                    current_capture=capture,
                    current_ball_pose=ball_pose,
                    current_zone_score=zone_score,
                    rationale=f"Ball reached the release corridor; letting {self.surface_profile} friction settle it.",
                    feedback=f"Letting {target.label} settle on {self.surface_profile}.",
                )
                time.sleep(self.args.poll_s)
                continue
            local_recovery_viable = bool(capture and capture.within_recapture_window)
            if local_settle_correction_eligible or local_recovery_viable:
                escaped_zone_correction_started_monotonic = None
            else:
                escaped_zone_correction_started_monotonic = (
                    now_monotonic
                    if escaped_zone_correction_started_monotonic is None
                    else escaped_zone_correction_started_monotonic
                )
            local_recovery_active = local_recovery_started_monotonic is not None
            if local_recovery_active:
                if recaptured_settle_started_monotonic is None and (not local_recovery_viable) and (not local_settle_correction_eligible):
                    escape_elapsed_s = (
                        now_monotonic - escaped_zone_correction_started_monotonic
                        if escaped_zone_correction_started_monotonic is not None
                        else 0.0
                    )
                    if escape_elapsed_s < DEFAULT_POST_VISIT_REVISIT_ESCAPE_TIMEOUT_S:
                        self._set_manual_drive(False, mode="zone_edge_wait", rationale="Waiting briefly to confirm the ball truly left local correction range.")
                        self._update_gather_runtime_state(
                            latest_feedback=f"Watching {target.label} before escalating outside local correction.",
                        )
                        time.sleep(self.args.poll_s)
                        continue
                    self._set_manual_drive(False, mode="release_roll_away", rationale="Ball left the corral correction window during place.")
                    return False, {
                        "failure_reason": "release_roll_away",
                        "failure_stage": "release",
                        "capture_state": capture.to_dict() if capture else {},
                        "zone_score": zone_score.to_dict() if zone_score else {},
                        "local_recovery_attempted": local_recovery_attempted,
                        "rolled_away_after_release": True,
                        "settle_exit_reason": "rolled_out",
                        **_place_diagnostics(current_capture=capture, current_zone_score=zone_score, allow_full_revisit=False),
                        **_settle_fields({"rolled_away_after_release": True, "settle_exit_reason": "rolled_out"}),
                        **_retention_fields(),
                    }
            elif capture and not capture.captured:
                marginal_capture_started_monotonic = None
                if local_recovery_viable or local_settle_correction_eligible:
                    if not local_recovery_attempted:
                        local_recovery_attempted = True
                        self._append_runtime_event(
                            f"{target.label}: short local recapture during place.",
                            key=f"place_local_recovery:{target.id}",
                        )
                    local_recovery_started_monotonic = now_monotonic
                    recaptured_settle_started_monotonic = None
                    if local_settle_correction_eligible and zone_edge_correction_started_monotonic is None:
                        zone_edge_correction_started_monotonic = now_monotonic
                        zone_edge_correction_count += 1
                    feedback = (
                        f"Gently correcting {target.label} near the corral edge."
                        if local_settle_correction_eligible
                        else f"Recovering {target.label} after brief capture loss."
                    )
                    self._update_gather_runtime_state(latest_feedback=feedback)
                else:
                    escape_elapsed_s = (
                        now_monotonic - escaped_zone_correction_started_monotonic
                        if escaped_zone_correction_started_monotonic is not None
                        else 0.0
                    )
                    if escape_elapsed_s < DEFAULT_POST_VISIT_REVISIT_ESCAPE_TIMEOUT_S:
                        self._set_manual_drive(False, mode="zone_edge_wait", rationale="Waiting briefly before leaving place control.")
                        self._update_gather_runtime_state(
                            latest_feedback=f"Watching {target.label} before escalating outside local correction.",
                        )
                        time.sleep(self.args.poll_s)
                        continue
                    self._set_manual_drive(False, mode="release_roll_away", rationale="Ball left the corral correction window during place.")
                    return False, {
                        "failure_reason": "release_roll_away",
                        "failure_stage": "release",
                        "capture_state": capture.to_dict(),
                        "zone_score": zone_score.to_dict() if zone_score else {},
                        "local_recovery_attempted": local_recovery_attempted,
                        "rolled_away_after_release": True,
                        "settle_exit_reason": "rolled_out",
                        **_place_diagnostics(current_capture=capture, current_zone_score=zone_score, allow_full_revisit=False),
                        **_settle_fields({"rolled_away_after_release": True, "settle_exit_reason": "rolled_out"}),
                        **_retention_fields(),
                    }
            elif capture_loss_detected(
                captured_now=False,
                last_captured_monotonic=last_captured_monotonic,
                now_monotonic=now_monotonic,
                loss_grace_s=self.capture_envelope.loss_grace_s,
            ):
                marginal_capture_started_monotonic = None
                escape_elapsed_s = (
                    now_monotonic - escaped_zone_correction_started_monotonic
                    if escaped_zone_correction_started_monotonic is not None
                    else DEFAULT_POST_VISIT_REVISIT_ESCAPE_TIMEOUT_S
                )
                if local_settle_correction_eligible or escape_elapsed_s < DEFAULT_POST_VISIT_REVISIT_ESCAPE_TIMEOUT_S:
                    self._set_manual_drive(False, mode="zone_edge_wait", rationale="Holding briefly while the ball pose recovers near the corral.")
                    self._update_gather_runtime_state(
                        latest_feedback=f"Holding for {target.label} to settle back into view near the corral.",
                    )
                    time.sleep(self.args.poll_s)
                    continue
                self._set_manual_drive(False, mode="release_roll_away", rationale="Ball left the corral correction window during place.")
                return False, {
                    "failure_reason": "release_roll_away",
                    "failure_stage": "release",
                    "capture_state": capture.to_dict() if capture else {},
                    "zone_score": zone_score.to_dict() if zone_score else {},
                    "local_recovery_attempted": local_recovery_attempted,
                    "rolled_away_after_release": True,
                    "settle_exit_reason": "rolled_out",
                    **_place_diagnostics(current_capture=capture, current_zone_score=zone_score, allow_full_revisit=False),
                    **_settle_fields({"rolled_away_after_release": True, "settle_exit_reason": "rolled_out"}),
                    **_retention_fields(),
                }
            if recaptured_settle_started_monotonic is not None:
                settle_elapsed_s = now_monotonic - recaptured_settle_started_monotonic
                if settle_elapsed_s < DEFAULT_PLACE_RECOVERY_SETTLE_S:
                    self._set_manual_drive(False, mode="capture_settle", rationale="Ball recaptured; settling before place.")
                    self._update_gather_runtime_state(latest_feedback=f"Stabilizing {target.label} after recapture.")
                    time.sleep(self.args.poll_s)
                    continue
                recaptured_settle_started_monotonic = None
            if capture and capture.captured:
                marginal_capture_now = abs(float(capture.ball_y_m)) > 0.04 or float(capture.ball_x_m) < 0.08
                if marginal_capture_now:
                    marginal_capture_started_monotonic = marginal_capture_started_monotonic or now_monotonic
                else:
                    marginal_capture_started_monotonic = None
                if marginal_capture_now and (now_monotonic - marginal_capture_started_monotonic) < DEFAULT_PLACE_MARGINAL_CAPTURE_SETTLE_S:
                    command = compute_place_command(robot_pose, ball_pose or {}, zone=self.zone, envelope=self.capture_envelope) if robot_pose and ball_pose else None
                    if command is not None:
                        self._set_manual_drive(
                            True,
                            linear_x=command.linear_x,
                            angular_z=command.angular_z,
                            mode=command.mode,
                            rationale=command.rationale,
                        )
                        self._update_gather_runtime_state(
                            latest_control_command=command.to_dict(),
                            latest_feedback=f"Settling {target.label} inside the spur before the final push.",
                        )
                    time.sleep(self.args.poll_s)
                    continue
            else:
                marginal_capture_started_monotonic = None
            if local_recovery_started_monotonic is not None:
                command = compute_place_command(robot_pose, ball_pose or {}, zone=self.zone, envelope=self.capture_envelope) if robot_pose and ball_pose else None
            else:
                command = compute_place_command(robot_pose, ball_pose or {}, zone=self.zone, envelope=self.capture_envelope) if robot_pose and ball_pose else None
            if command is not None:
                if (
                    local_settle_correction_eligible
                    and zone_score
                    and zone_score.inside_retrieval_corral
                    and ball_motion_m is not None
                    and ball_motion_m > DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M
                    and not settle_shepherd_needed
                ):
                    self._set_manual_drive(False, mode="zone_edge_wait", rationale="Ball is still moving inside the corral overlap; let it settle before nudging again.")
                    self._update_gather_runtime_state(
                        latest_feedback=f"Letting {target.label} settle near the corral edge before another correction.",
                        latest_control_command={
                            "mode": "zone_edge_wait",
                            "linear_x": 0.0,
                            "angular_z": 0.0,
                            "target_speed_scale": 0.0,
                            "rationale": "Ball is still moving inside the corral overlap; let it settle before nudging again.",
                        },
                    )
                    time.sleep(self.args.poll_s)
                    continue
                if local_recovery_started_monotonic is not None:
                    recovery_linear = min(float(command.linear_x), 0.05)
                    recovery_angular = clamp(float(command.angular_z), -0.45, 0.45)
                    recovery_scale = min(float(command.target_speed_scale), 0.55)
                    recovery_mode = "capture_recovery"
                    recovery_rationale = "Briefly recenter the ball under the catcher before resuming place."
                    if capture and not capture.ball_ahead:
                        recovery_linear = 0.0
                        recovery_angular = clamp(0.90 if float(capture.ball_y_m) >= 0.0 else -0.90, -0.90, 0.90)
                        recovery_scale = 0.0
                        recovery_mode = "capture_recovery_turn"
                        recovery_rationale = "Ball slipped behind inside the corral; turn in place quickly before it escapes."
                    elif capture and capture.within_recapture_window and (
                        float(capture.ball_x_m) > 0.40 or abs(float(capture.ball_y_m)) > 0.08
                    ):
                        recovery_linear = 0.0
                        recovery_angular = clamp((float(capture.ball_y_m) * 5.0), -0.35, 0.35)
                        recovery_scale = 0.30
                        recovery_mode = "capture_recovery_hold"
                        recovery_rationale = "Ball is ahead of the spur mouth; hold and yaw gently before pushing again."
                    command = command.__class__(
                        mode=recovery_mode,
                        linear_x=recovery_linear,
                        angular_z=recovery_angular,
                        target_speed_scale=recovery_scale,
                        rationale=recovery_rationale,
                    )
                elif settle_shepherd_needed and command.mode in {"retrieval_hold", "capture", "place_recapture", "place"}:
                    shepherd_linear = 0.02
                    if float(capture.ball_x_m) > 0.95:
                        shepherd_linear = 0.03
                    elif float(capture.ball_x_m) > 0.75:
                        shepherd_linear = 0.025
                    if abs(float(capture.ball_y_m)) > 0.12:
                        shepherd_linear = 0.0
                    command = command.__class__(
                        mode="retrieval_shepherd" if shepherd_linear > 0.0 else "retrieval_hold",
                        linear_x=round(shepherd_linear, 6),
                        angular_z=clamp(float(command.angular_z), -0.30, 0.30),
                        target_speed_scale=0.40 if shepherd_linear > 0.0 else 0.0,
                        rationale="Ball is inside the retrieval corral but still rolling away from the robot; keep a gentle shepherd until settle is credible.",
                    )
                elif local_settle_correction_eligible and command.mode in {"place_recapture", "capture", "place"}:
                    zone_edge_correction_started_monotonic = (
                        now_monotonic
                        if zone_edge_correction_started_monotonic is None
                        else zone_edge_correction_started_monotonic
                    )
                    zone_edge_correction_count = max(zone_edge_correction_count, 1)
                    command = command.__class__(
                        mode="zone_edge_correction",
                        linear_x=min(float(command.linear_x), 0.016),
                        angular_z=clamp(float(command.angular_z), -0.35, 0.35),
                        target_speed_scale=min(float(command.target_speed_scale), 0.45),
                        rationale="Ball is near the corral edge; use one gentle correction instead of escalating to revisit.",
                    )
                self._set_manual_drive(
                    True,
                    linear_x=command.linear_x,
                    angular_z=command.angular_z,
                    mode=command.mode,
                    rationale=command.rationale,
                )
                self._update_gather_runtime_state(latest_control_command=command.to_dict())
            time.sleep(self.args.poll_s)

        self._set_manual_drive(False, mode="place_timeout", rationale="Place timed out.")
        return False, {
            "failure_reason": "place_timeout",
            "failure_stage": "place",
            "local_recovery_attempted": local_recovery_attempted,
            "settle_metrics": _settle_metrics(),
            "release_recontact_count": release_recontact_count,
            "settle_exit_reason": "timeout",
            **_place_diagnostics(allow_full_revisit=False),
            **_settle_fields({"settle_exit_reason": "timeout"}),
            **_retention_fields(),
        }

    def _run_target(
        self,
        *,
        session_id: str,
        target: GatherTargetSpec,
        route_index: int,
        gather_sequence_path: Path,
        state_history_path: Path,
        mission_root: Path,
    ) -> dict[str, Any]:
        attempt = 0
        capture_loss_count = 0
        place_loss_recapture_count = 0
        place_loss_full_revisit_count = 0
        place_controller_reentry_count = 0
        post_visit_revisit_count = 0
        zone_edge_correction_count = 0
        local_recovery_attempted_any = False
        visit_completed_once = False
        active_handoff_kind = ""
        resume_with_capture = False
        resume_with_place_controller = False
        resume_with_place_loss_revisit = False
        target_start_monotonic = time.monotonic()

        def _retention_kwargs(payload: dict[str, Any] | None) -> dict[str, Any]:
            if not isinstance(payload, dict):
                return {}
            return {
                "stopped_with_ball_captured": bool(payload.get("stopped_with_ball_captured", False)),
                "release_started_with_capture": bool(payload.get("release_started_with_capture", False)),
                "stop_capture_state": payload.get("stop_capture_state", {}) if isinstance(payload.get("stop_capture_state"), dict) else {},
                "release_capture_state": payload.get("release_capture_state", {}) if isinstance(payload.get("release_capture_state"), dict) else {},
                "clean_retention_pass": (
                    bool(payload["clean_retention_pass"])
                    if "clean_retention_pass" in payload
                    else None
                ),
            }

        def _ownership_kwargs(payload: dict[str, Any] | None) -> dict[str, Any]:
            if not isinstance(payload, dict):
                return {}
            return {
                "handoff_kind": clean_text(payload.get("handoff_kind"), clean_text(active_handoff_kind, "unspecified")),
                "zone_edge_correction_count": int(payload.get("zone_edge_correction_count", 0) or 0),
                "place_controller_reentry_count": int(place_controller_reentry_count),
                "post_visit_revisit_count": int(post_visit_revisit_count),
            }

        def _settle_kwargs(payload: dict[str, Any] | None) -> dict[str, Any]:
            if not isinstance(payload, dict):
                return {}
            zone_payload = payload.get("zone_score", {}) if isinstance(payload.get("zone_score"), dict) else {}
            settle_metrics = payload.get("settle_metrics", {}) if isinstance(payload.get("settle_metrics"), dict) else {}
            final_inside_retrieval_corral = bool(
                settle_metrics.get("final_inside_retrieval_corral", zone_payload.get("center_inside_retrieval_corral", False))
            )
            final_center_inside_zone = bool(
                settle_metrics.get("final_center_inside_zone", zone_payload.get("center_inside_zone", False))
            )
            ball_stopped_in_corral = bool(settle_metrics.get("ball_stopped_in_corral", False))
            rolled_away_after_release = bool(settle_metrics.get("rolled_away_after_release", payload.get("rolled_away_after_release", False)))
            settled_pass = bool(settle_metrics.get("settled_in_corral_pass", payload.get("settled_in_corral_pass", False)))
            return {
                "final_inside_retrieval_corral": final_inside_retrieval_corral,
                "final_center_inside_zone": final_center_inside_zone,
                "ball_stopped_in_corral": ball_stopped_in_corral,
                "rolled_away_after_release": rolled_away_after_release,
                "settled_in_corral_pass": settled_pass,
                "settle_exit_reason": clean_text(
                    payload.get("settle_exit_reason"),
                    clean_text(
                        settle_metrics.get("settle_exit_reason") if isinstance(settle_metrics, dict) else "",
                        default_settle_exit_reason(
                            failure_reason=str(payload.get("failure_reason", "")),
                            settled_in_corral_pass=settled_pass,
                            corrected=bool(
                                int(payload.get("zone_edge_correction_count", 0) or 0)
                                or int(place_controller_reentry_count)
                                or int(settle_metrics.get("release_recontact_count", 0) or 0)
                            ),
                            rolled_away_after_release=rolled_away_after_release,
                        ),
                    ),
                ),
            }

        def _normalize_post_visit_capture_failure(payload: dict[str, Any]) -> dict[str, Any]:
            zone_payload = payload.get("zone_score", {}) if isinstance(payload.get("zone_score"), dict) else {}
            correction_eligible = bool(payload.get("zone_edge_correction_eligible", False))
            final_inside_retrieval_corral = bool(zone_payload.get("center_inside_retrieval_corral", False))
            final_center_inside_zone = bool(zone_payload.get("center_inside_zone", False))
            rolled_away_after_release = not correction_eligible and not final_inside_retrieval_corral
            failure_reason = "release_roll_away" if rolled_away_after_release else "release_unsettled"
            return {
                **payload,
                "failure_reason": failure_reason,
                "failure_stage": "release",
                "allow_full_revisit": False,
                "final_inside_retrieval_corral": final_inside_retrieval_corral,
                "final_center_inside_zone": final_center_inside_zone,
                "ball_stopped_in_corral": False,
                "rolled_away_after_release": rolled_away_after_release,
                "settled_in_corral_pass": False,
                "settle_exit_reason": default_settle_exit_reason(
                    failure_reason=failure_reason,
                    rolled_away_after_release=rolled_away_after_release,
                ),
            }

        while attempt <= self.args.max_retries_per_target:
            attempt += 1
            direct_recapture_attempt = resume_with_capture
            place_controller_reentry_attempt = resume_with_place_controller
            place_loss_revisit_attempt = resume_with_place_loss_revisit
            resume_with_capture = False
            resume_with_place_controller = False
            resume_with_place_loss_revisit = False

            if place_controller_reentry_attempt:
                attempt_kind = "place_controller_reentry"
            elif direct_recapture_attempt:
                attempt_kind = "place_loss_recapture"
            elif place_loss_revisit_attempt:
                attempt_kind = "place_loss_revisit"
            else:
                attempt_kind = "initial_visit" if not visit_completed_once else "retry_visit"

            if place_controller_reentry_attempt:
                place_controller_reentry_count += 1
                self._append_runtime_event(
                    f"{target.label}: place controller reentry {place_controller_reentry_count} near the corral edge.",
                    key=f"place_controller_reentry:{target.id}:{place_controller_reentry_count}",
                )
                self._update_visit_runtime_state(
                    proof_state="placing",
                    current_target_id=target.id,
                    visit_index=route_index,
                    remaining_targets=[item for item in self.gather_runtime_state.get("remaining_targets", []) if item != target.id],
                    mission_phase="place",
                    latest_feedback=f"Continuing local place correction for {target.label}.",
                )
                self._update_gather_runtime_state(
                    mission_phase="place",
                    gather_phase="place",
                    current_target_id=target.id,
                    visit_index=route_index,
                    latest_feedback=f"Continuing local place correction for {target.label}.",
                )
            elif direct_recapture_attempt:
                self._append_runtime_event(
                    f"{target.label}: direct recapture attempt {place_loss_recapture_count} after place-stage loss.",
                    key=f"place_loss_recapture:{target.id}:{place_loss_recapture_count}",
                )
                self._update_visit_runtime_state(
                    proof_state="capturing",
                    current_target_id=target.id,
                    visit_index=route_index,
                    remaining_targets=[item for item in self.gather_runtime_state.get("remaining_targets", []) if item != target.id],
                    mission_phase="capture",
                    latest_feedback=f"Reacquiring {target.label} after place-stage loss.",
                )
                self._update_gather_runtime_state(
                    mission_phase="capture",
                    gather_phase="capture",
                    current_target_id=target.id,
                    visit_index=route_index,
                    latest_feedback=f"Reacquiring {target.label} after place-stage loss.",
                )
                ball_pose = self._ball_truth_pose(session_id, target)
                if ball_pose:
                    self._update_prior_from_ball_pose(target.id, ball_pose)
            else:
                if place_loss_revisit_attempt:
                    if visit_completed_once:
                        post_visit_revisit_count += 1
                    self._append_runtime_event(
                        f"{target.label}: full revisit {post_visit_revisit_count or place_loss_full_revisit_count} after place-stage loss.",
                        key=f"place_loss_revisit:{target.id}:{post_visit_revisit_count or place_loss_full_revisit_count}",
                    )
                    visit_feedback = f"Revisiting {target.label} after place-stage loss."
                else:
                    self._append_runtime_event(f"{target.label}: visit attempt {attempt}.", key=f"visit_attempt:{target.id}:{attempt}")
                    visit_feedback = f"Visiting {target.label}."
                self._update_visit_runtime_state(
                    proof_state="visiting",
                    current_target_id=target.id,
                    visit_index=route_index,
                    remaining_targets=[item for item in self.gather_runtime_state.get("remaining_targets", []) if item != target.id],
                    mission_phase="visit",
                    latest_feedback=visit_feedback,
                )
                self._update_gather_runtime_state(
                    mission_phase="visit",
                    gather_phase="visit",
                    current_target_id=target.id,
                    visit_index=route_index,
                    latest_feedback=visit_feedback,
                )
                ball_pose = self._ball_truth_pose(session_id, target)
                if ball_pose:
                    self._update_prior_from_ball_pose(target.id, ball_pose)
                self._wait_for_nav2_ready(timeout_s=30.0)
                baseline_state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
                baseline_brain = baseline_state.get("brain", {}) if isinstance(baseline_state.get("brain"), dict) else {}
                baseline_status = clean_text(baseline_brain.get("last_feedback_status"))
                baseline_feedback = clean_text(baseline_brain.get("last_feedback_text") or baseline_state.get("last_feedback"))
                self._dispatch_visit_target(target.id)
                visit_pass, _last_state, visit_status = self._wait_for_visit_result(
                    timeout_s=self.args.visit_timeout_s,
                    baseline_status=baseline_status,
                    baseline_feedback=baseline_feedback,
                    target_id=target.id,
                )
                append_jsonl(
                    gather_sequence_path,
                    {
                        "generated_utc": utc_now(),
                        "event_type": "visit_result",
                        "target_id": target.id,
                        "attempt": attempt,
                        "status": visit_status,
                        "pass": visit_pass,
                    },
                )
                if not visit_pass:
                    if attempt > self.args.max_retries_per_target:
                        self._update_visit_runtime_state(proof_state="failed", mission_phase="failed", latest_feedback=f"{target.label} visit failed.")
                        return self._target_failure_result(
                            target=target,
                            failure_reason=visit_status,
                            failure_stage="visit",
                            attempts=attempt,
                            capture_loss_count=capture_loss_count,
                            route_index=route_index,
                            attempt_kind=attempt_kind,
                            local_recovery_attempted=local_recovery_attempted_any,
                            revisit_attempted=post_visit_revisit_count > 0,
                            handoff_kind=clean_text(active_handoff_kind, "unspecified"),
                            zone_edge_correction_count=zone_edge_correction_count,
                            place_controller_reentry_count=place_controller_reentry_count,
                            post_visit_revisit_count=post_visit_revisit_count,
                        )
                    self._safe_stop()
                    self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
                    continue
                visit_completed_once = True
                self._append_runtime_event(
                    f"{target.label}: visit leg complete; handing off to gather control.",
                    key=f"visit_handoff:{target.id}:{attempt}",
                )
                self._safe_stop()
                self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
            capture_payload: dict[str, Any] = {}
            capture_pass = True
            if not place_controller_reentry_attempt:
                capture_pass, capture_payload = self._capture_target(
                    session_id=session_id,
                    target=target,
                    state_history_path=state_history_path,
                    mission_root=mission_root,
                    prefer_zone_recovery=direct_recapture_attempt,
                )
                if not capture_pass:
                    capture_failure_reason = str(capture_payload.get("failure_reason", "capture_failed"))
                    capture_failure_stage = str(capture_payload.get("failure_stage", "capture"))
                    zone_edge_correction_count += int(capture_payload.get("zone_edge_correction_count", 0) or 0)
                    if direct_recapture_attempt and attempt <= self.args.max_retries_per_target:
                        place_loss_recapture_count += 1
                        self._append_runtime_event(
                            f"{target.label}: keeping place ownership after place-stage recapture timeout {place_loss_recapture_count}.",
                            key=f"place_controller_hold:{target.id}:{place_loss_recapture_count}:{capture_failure_reason}",
                        )
                        self._safe_stop()
                        self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
                        resume_with_place_controller = True
                        continue
                    if visit_completed_once and attempt <= self.args.max_retries_per_target:
                        place_loss_recapture_count += 1
                        self._append_runtime_event(
                            f"{target.label}: local gather recapture after post-visit capture timeout {place_loss_recapture_count}.",
                            key=f"post_visit_capture_recapture:{target.id}:{place_loss_recapture_count}",
                        )
                        self._safe_stop()
                        self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
                        resume_with_capture = True
                        continue
                    if visit_completed_once:
                        capture_failure_reason = str(
                            _normalize_post_visit_capture_failure(capture_payload).get("failure_reason", capture_failure_reason)
                        )
                        capture_failure_stage = str(
                            _normalize_post_visit_capture_failure(capture_payload).get("failure_stage", capture_failure_stage)
                        )
                    if attempt > self.args.max_retries_per_target or place_loss_full_revisit_count > 0 or visit_completed_once:
                        normalized_capture_failure = (
                            _normalize_post_visit_capture_failure(capture_payload)
                            if visit_completed_once
                            else capture_payload
                        )
                        self._update_visit_runtime_state(proof_state="failed", mission_phase="failed", latest_feedback=f"{target.label} capture failed.")
                        return self._target_failure_result(
                            target=target,
                            failure_reason=capture_failure_reason,
                            failure_stage=capture_failure_stage,
                            attempts=attempt,
                            capture_loss_count=capture_loss_count,
                            route_index=route_index,
                            attempt_kind=attempt_kind,
                            local_recovery_attempted=local_recovery_attempted_any,
                            revisit_attempted=post_visit_revisit_count > 0,
                            settle_metrics=normalized_capture_failure.get("settle_metrics") if isinstance(normalized_capture_failure.get("settle_metrics"), dict) else None,
                            handoff_kind=clean_text(active_handoff_kind, "unspecified"),
                            zone_edge_correction_count=zone_edge_correction_count,
                            place_controller_reentry_count=place_controller_reentry_count,
                            post_visit_revisit_count=post_visit_revisit_count,
                            **_retention_kwargs(normalized_capture_failure),
                            **_settle_kwargs(normalized_capture_failure),
                        )
                    self._safe_stop()
                    self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
                    continue
                active_handoff_kind = clean_text(
                    capture_payload.get("handoff_kind"),
                    "zone_entry"
                    if bool(capture_payload.get("entered_zone_during_capture"))
                    else "soft_capture"
                    if bool(capture_payload.get("soft_capture_handoff"))
                    else "secure_capture",
                )
                if direct_recapture_attempt:
                    place_controller_reentry_count += 1

            if isinstance(capture_payload.get("final_ball_pose"), dict):
                final_ball_pose = capture_payload.get("final_ball_pose", {})
                if final_ball_pose:
                    self._record_target_position(
                        target.id,
                        x=float(final_ball_pose.get("x", 0.0)),
                        y=float(final_ball_pose.get("y", 0.0)),
                        z=float(final_ball_pose.get("z", target.z_m) or target.z_m),
                    )
                placed_targets = list(self.gather_runtime_state.get("placed_targets", []))
                if target.id not in placed_targets:
                    placed_targets.append(target.id)
                visited_targets = list(self.visit_runtime_state.get("visited_targets", []))
                if target.id not in visited_targets:
                    visited_targets.append(target.id)
                remaining_targets = [item for item in self.gather_runtime_state.get("remaining_targets", []) if item != target.id]
                self._update_gather_runtime_state(
                    mission_phase="advance",
                    gather_phase="advance",
                    placed_targets=placed_targets,
                    remaining_targets=remaining_targets,
                    capture_loss_count=capture_loss_count,
                    latest_feedback=f"{target.label} placed in the zone.",
                )
                self._update_visit_runtime_state(
                    visited_targets=visited_targets,
                    remaining_targets=remaining_targets,
                    last_visit_result={"target_id": target.id, "pass": True},
                    current_target_prior={},
                    mission_phase="advance",
                    latest_feedback=f"{target.label} placed in the zone.",
                )
                self._append_runtime_event(f"{target.label} placed in the corral zone.", key=f"placed:{target.id}")
                settle_metrics = capture_payload.get("settle_metrics") if isinstance(capture_payload.get("settle_metrics"), dict) else None
                if settle_metrics is None and final_ball_pose:
                    zone_score = zone_snapshot(final_ball_pose, self.zone)
                    if zone_score is not None:
                        settle_metrics = summarize_release_settle_trace(
                            surface_profile=self.surface_profile,
                            zone=self.zone,
                            release_samples=[
                                self._release_sample(
                                    release_started_monotonic=target_start_monotonic,
                                    now_monotonic=time.monotonic(),
                                    ball_pose=final_ball_pose,
                                    zone_score=zone_score,
                                )
                            ],
                            release_recontact_count=0,
                        ).to_dict()
                return self._target_success_result(
                    target=target,
                    attempts=attempt,
                    capture_loss_count=capture_loss_count,
                    route_index=route_index,
                    final_ball_pose=final_ball_pose,
                    place_time_s=time.monotonic() - target_start_monotonic,
                    attempt_kind=attempt_kind,
                    revisit_attempted=post_visit_revisit_count > 0,
                    settle_metrics=settle_metrics,
                    handoff_kind=clean_text(active_handoff_kind, "unspecified"),
                    zone_edge_correction_count=zone_edge_correction_count,
                    place_controller_reentry_count=place_controller_reentry_count,
                    post_visit_revisit_count=post_visit_revisit_count,
                    **_retention_kwargs(capture_payload),
                    **_settle_kwargs(capture_payload),
                )

            place_pass, place_payload = self._place_target(
                session_id=session_id,
                target=target,
                state_history_path=state_history_path,
            )
            zone_edge_correction_count += int(place_payload.get("zone_edge_correction_count", 0) or 0)
            if place_pass:
                final_ball_pose = place_payload.get("final_ball_pose") if isinstance(place_payload.get("final_ball_pose"), dict) else {}
                if final_ball_pose:
                    self._record_target_position(
                        target.id,
                        x=float(final_ball_pose.get("x", 0.0)),
                        y=float(final_ball_pose.get("y", 0.0)),
                        z=float(final_ball_pose.get("z", target.z_m) or target.z_m),
                    )
                placed_targets = list(self.gather_runtime_state.get("placed_targets", []))
                if target.id not in placed_targets:
                    placed_targets.append(target.id)
                visited_targets = list(self.visit_runtime_state.get("visited_targets", []))
                if target.id not in visited_targets:
                    visited_targets.append(target.id)
                remaining_targets = [item for item in self.gather_runtime_state.get("remaining_targets", []) if item != target.id]
                self._update_gather_runtime_state(
                    mission_phase="advance",
                    gather_phase="advance",
                    placed_targets=placed_targets,
                    remaining_targets=remaining_targets,
                    capture_loss_count=capture_loss_count,
                    latest_feedback=f"{target.label} placed in the zone.",
                )
                self._update_visit_runtime_state(
                    visited_targets=visited_targets,
                    remaining_targets=remaining_targets,
                    last_visit_result={"target_id": target.id, "pass": True},
                    current_target_prior={},
                    mission_phase="advance",
                    latest_feedback=f"{target.label} placed in the zone.",
                )
                self._append_runtime_event(f"{target.label} placed in the corral zone.", key=f"placed:{target.id}")
                settle_metrics = place_payload.get("settle_metrics") if isinstance(place_payload.get("settle_metrics"), dict) else None
                return self._target_success_result(
                    target=target,
                    attempts=attempt,
                    capture_loss_count=capture_loss_count,
                    route_index=route_index,
                    final_ball_pose=final_ball_pose,
                    place_time_s=time.monotonic() - target_start_monotonic,
                    attempt_kind=attempt_kind,
                    local_recovery_attempted=local_recovery_attempted_any or bool(place_payload.get("local_recovery_attempted", False)),
                    revisit_attempted=post_visit_revisit_count > 0,
                    settle_metrics=settle_metrics,
                    handoff_kind=clean_text(active_handoff_kind, "unspecified"),
                    zone_edge_correction_count=zone_edge_correction_count,
                    place_controller_reentry_count=place_controller_reentry_count,
                    post_visit_revisit_count=post_visit_revisit_count,
                    **_retention_kwargs(place_payload),
                    **_settle_kwargs(place_payload),
                )

            failure_reason = str(place_payload.get("failure_reason", "place_failed"))
            failure_stage = str(place_payload.get("failure_stage", "place"))
            local_recovery_attempted = bool(place_payload.get("local_recovery_attempted", False))
            local_recovery_attempted_any = local_recovery_attempted_any or local_recovery_attempted
            place_recovery_failure = failure_reason in {"capture_lost", "release_unsettled", "release_roll_away"}
            if failure_reason == "capture_lost":
                capture_loss_count += 1
                self._update_gather_runtime_state(capture_loss_count=capture_loss_count)
            if place_recovery_failure:
                recovery_label = "place-stage correction" if failure_reason == "capture_lost" else "release-stage correction"
                if failure_reason != "release_roll_away" and attempt <= self.args.max_retries_per_target:
                    self._append_runtime_event(
                        f"{target.label}: keeping place ownership during {recovery_label}.",
                        key=f"place_correction_reentry:{target.id}:{attempt}:{failure_reason}",
                    )
                    self._safe_stop()
                    self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
                    resume_with_place_controller = True
                    continue
            if attempt > self.args.max_retries_per_target or place_recovery_failure:
                self._update_visit_runtime_state(proof_state="failed", mission_phase="failed", latest_feedback=f"{target.label} place failed.")
                return self._target_failure_result(
                    target=target,
                    failure_reason=failure_reason,
                    failure_stage=failure_stage,
                    attempts=attempt,
                    capture_loss_count=capture_loss_count,
                    route_index=route_index,
                    attempt_kind=attempt_kind,
                    local_recovery_attempted=local_recovery_attempted_any,
                    revisit_attempted=post_visit_revisit_count > 0,
                    settle_metrics=place_payload.get("settle_metrics") if isinstance(place_payload.get("settle_metrics"), dict) else None,
                    handoff_kind=clean_text(active_handoff_kind, "unspecified"),
                    zone_edge_correction_count=zone_edge_correction_count,
                    place_controller_reentry_count=place_controller_reentry_count,
                    post_visit_revisit_count=post_visit_revisit_count,
                    **_retention_kwargs(place_payload),
                    **_settle_kwargs(place_payload),
                )
            self._safe_stop()
            self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)

        return self._target_failure_result(
            target=target,
            failure_reason="unreachable_state",
            failure_stage="mission",
            attempts=attempt,
            capture_loss_count=capture_loss_count,
            route_index=route_index,
            attempt_kind="unreachable_state",
            revisit_attempted=post_visit_revisit_count > 0,
            settle_metrics={},
            clean_retention_pass=False,
            handoff_kind=clean_text(active_handoff_kind, "unspecified"),
            zone_edge_correction_count=zone_edge_correction_count,
            place_controller_reentry_count=place_controller_reentry_count,
            post_visit_revisit_count=post_visit_revisit_count,
        )

    def run(self) -> dict[str, Any]:
        ready_state, started_here = self._ensure_environment_ready()
        self._started_here = started_here
        ready_state = self._wait_for_robot_pose(timeout_s=self.args.environment_timeout_s)
        session_id = clean_text(ready_state.get("session_id"))
        if not session_id:
            raise RuntimeError("Dashboard did not provide a session id for gather mission.")

        mission_root = ensure_dir(REPO_ROOT / "artifacts" / "session" / session_id / self.args.artifact_kind / current_utc_stamp())
        gather_sequence_path = mission_root / "gather_sequence.jsonl"
        state_history_path = mission_root / "state_history.jsonl"
        target_results_path = mission_root / "target_results.json"

        self._init_runtime_state(session_id=session_id, mission_root=mission_root)
        self._append_runtime_event(f"{self.args.scenario_label} mission started.", category="scenario", key="mission_started")
        self._safe_stop()
        self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
        self._spawn_mission_models(ready_state, mission_root)
        expected_truth_models = {self._target_model_name(target) for target in self.targets}
        self._wait_for_truth_models(session_id, expected_truth_models, timeout_s=30.0)
        self._start_motion_bridge(clean_text(ready_state.get("compose_project")), mission_root)

        target_results: list[dict[str, Any]] = []
        mission_pass = True
        mission_error = ""
        mission_started_monotonic = time.monotonic()

        try:
            remaining_ids = [item.id for item in self.targets]
            route_decisions: list[dict[str, Any]] = []
            route_index = 0
            while remaining_ids:
                state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
                ordered_ids = self._plan_collection_route(remaining_ids, state)
                route_index += 1
                selected_id = ordered_ids[0]
                route_decisions.append({"step": route_index, "ordered_ids": ordered_ids, "selected_id": selected_id})
                self._update_gather_runtime_state(
                    route_order=[item["selected_id"] for item in route_decisions],
                    remaining_targets=list(remaining_ids),
                )
                append_jsonl(
                    gather_sequence_path,
                    {
                        "generated_utc": utc_now(),
                        "event_type": "route_planned",
                        "step": route_index,
                        "ordered_ids": ordered_ids,
                        "selected_id": selected_id,
                    },
                )
                target = self.targets_by_id[selected_id]
                target_result = self._run_target(
                    session_id=session_id,
                    target=target,
                    route_index=route_index,
                    gather_sequence_path=gather_sequence_path,
                    state_history_path=state_history_path,
                    mission_root=mission_root,
                )
                target_results.append(target_result)
                write_json(target_results_path, {"targets": target_results})
                remaining_ids = [item for item in remaining_ids if item != selected_id] if target_result.get("pass") else remaining_ids
                self._update_gather_runtime_state(
                    remaining_targets=remaining_ids,
                    mission_phase="advance" if target_result.get("pass") else "failed",
                    mission_status="running" if target_result.get("pass") else "failed",
                )
                self._update_visit_runtime_state(
                    remaining_targets=remaining_ids,
                    last_visit_result=target_result,
                    mission_status="running" if target_result.get("pass") else "failed",
                    mission_phase="advance" if target_result.get("pass") else "failed",
                    proof_state="placing" if target_result.get("pass") else "failed",
                )
                append_jsonl(
                    gather_sequence_path,
                    {
                        "generated_utc": utc_now(),
                        "event_type": "target_completed",
                        "target_id": selected_id,
                        "result": target_result,
                    },
                )
                if not target_result.get("pass"):
                    mission_pass = False
                    mission_error = str(target_result.get("failure_reason", "target_failed"))
                    self._append_runtime_event(
                        f"{target.label} failed: {mission_error}",
                        category="error",
                        key=f"target_failed:{target.id}",
                    )
                    break
                self._safe_stop()
                self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)

            mission_time_s = round(time.monotonic() - mission_started_monotonic, 6)
            placed_targets = list(self.gather_runtime_state.get("placed_targets", []))
            capture_loss_count = int(self.gather_runtime_state.get("capture_loss_count", 0) or 0)
            mission_completed_pass = mission_pass and len(placed_targets) == len(self.targets)
            final_result = next((item for item in reversed(target_results) if isinstance(item, dict)), {})
            stopped_with_ball_captured = bool(final_result.get("stopped_with_ball_captured", False))
            release_started_with_capture = bool(final_result.get("release_started_with_capture", False))
            stop_capture_state = final_result.get("stop_capture_state", {}) if isinstance(final_result.get("stop_capture_state"), dict) else {}
            release_capture_state = final_result.get("release_capture_state", {}) if isinstance(final_result.get("release_capture_state"), dict) else {}
            clean_retention_pass = (
                mission_completed_pass
                and capture_loss_count == 0
                and stopped_with_ball_captured
                and release_started_with_capture
            )
            handoff_kind = clean_text(final_result.get("handoff_kind"), "unspecified")
            zone_edge_correction_count = sum(int(item.get("zone_edge_correction_count", 0) or 0) for item in target_results)
            place_controller_reentry_count = sum(int(item.get("place_controller_reentry_count", 0) or 0) for item in target_results)
            post_visit_revisit_count = sum(int(item.get("post_visit_revisit_count", 0) or 0) for item in target_results)
            settle_exit_reason = clean_text(final_result.get("settle_exit_reason"))
            final_inside_retrieval_corral = bool(final_result.get("final_inside_retrieval_corral", False))
            final_center_inside_zone = bool(final_result.get("final_center_inside_zone", False))
            ball_stopped_in_corral = bool(final_result.get("ball_stopped_in_corral", False))
            rolled_away_after_release = bool(final_result.get("rolled_away_after_release", False))
            settled_in_corral_pass = (
                mission_completed_pass
                and final_inside_retrieval_corral
                and ball_stopped_in_corral
                and not rolled_away_after_release
                and post_visit_revisit_count == 0
            )
            final_settle_distance_m = float(final_result.get("final_settle_distance_m", 0.0) or 0.0)
            max_overshoot_distance_m = max(
                [float(item.get("max_overshoot_distance_m", 0.0) or 0.0) for item in target_results],
                default=0.0,
            )
            settle_time_s = float(final_result.get("settle_time_s", 0.0) or 0.0)
            release_recontact_count = sum(int(item.get("release_recontact_count", 0) or 0) for item in target_results)
            final_corral_audit: dict[str, Any] = {}
            final_all_targets_inside_retrieval_corral = False
            final_all_targets_stopped = False
            final_three_ball_corral_pass = False
            retrieved_count = 0
            if self.args.scenario_id == "gather_three_ball_zone":
                if mission_completed_pass:
                    final_corral_snapshot = self._run_final_corral_audit(
                        session_id=session_id,
                        state_history_path=state_history_path,
                    )
                else:
                    final_corral_snapshot = self._final_corral_audit_snapshot(
                        session_id=session_id,
                        previous_poses=None,
                    )
                    final_corral_snapshot["final_all_targets_stopped"] = False
                    final_corral_snapshot["final_three_ball_corral_pass"] = False
                final_corral_audit = (
                    final_corral_snapshot.get("final_corral_audit", {})
                    if isinstance(final_corral_snapshot.get("final_corral_audit"), dict)
                    else {}
                )
                final_all_targets_inside_retrieval_corral = bool(
                    final_corral_snapshot.get("final_all_targets_inside_retrieval_corral", False)
                )
                final_all_targets_stopped = bool(final_corral_snapshot.get("final_all_targets_stopped", False))
                retrieved_count = int(final_corral_snapshot.get("retrieved_count", 0) or 0)
                final_three_ball_corral_pass = (
                    mission_completed_pass
                    and final_all_targets_inside_retrieval_corral
                    and final_all_targets_stopped
                    and post_visit_revisit_count == 0
                )
            final_mission_error = mission_error
            if self.args.scenario_id == "gather_three_ball_zone":
                if mission_completed_pass and not final_three_ball_corral_pass and not final_mission_error:
                    final_mission_error = "final_corral_audit_failed"
            elif mission_completed_pass and not settled_in_corral_pass and not final_mission_error:
                final_mission_error = "settled_in_corral_failed"
            mission_verdict = {
                "generated_utc": utc_now(),
                "type": "gather_mission",
                "pass": final_three_ball_corral_pass if self.args.scenario_id == "gather_three_ball_zone" else settled_in_corral_pass,
                "mission_completed_pass": mission_completed_pass,
                "scenario_id": self.args.scenario_id,
                "scenario_label": self.args.scenario_label,
                "session_id": session_id,
                "world_file": self.world_file,
                "surface_profile": self.surface_profile,
                "route_order": [item["selected_id"] for item in route_decisions],
                "placed_targets": placed_targets,
                "placed_count": len(placed_targets),
                "total_targets": len(self.targets),
                "capture_loss_count": capture_loss_count,
                "handoff_kind": handoff_kind,
                "zone_edge_correction_count": zone_edge_correction_count,
                "place_controller_reentry_count": place_controller_reentry_count,
                "post_visit_revisit_count": post_visit_revisit_count,
                "settle_exit_reason": settle_exit_reason,
                "stopped_with_ball_captured": stopped_with_ball_captured,
                "release_started_with_capture": release_started_with_capture,
                "stop_capture_state": stop_capture_state,
                "release_capture_state": release_capture_state,
                "clean_retention_pass": clean_retention_pass,
                "final_inside_retrieval_corral": final_inside_retrieval_corral,
                "final_center_inside_zone": final_center_inside_zone,
                "ball_stopped_in_corral": ball_stopped_in_corral,
                "rolled_away_after_release": rolled_away_after_release,
                "settled_in_corral_pass": settled_in_corral_pass,
                "final_corral_audit": final_corral_audit,
                "final_all_targets_inside_retrieval_corral": final_all_targets_inside_retrieval_corral,
                "final_all_targets_stopped": final_all_targets_stopped,
                "final_three_ball_corral_pass": final_three_ball_corral_pass,
                "retrieved_count": retrieved_count,
                "final_settle_distance_m": round(final_settle_distance_m, 6),
                "max_overshoot_distance_m": round(max_overshoot_distance_m, 6),
                "settle_time_s": round(settle_time_s, 6),
                "release_recontact_count": release_recontact_count,
                "mission_time_s": mission_time_s,
                "zone_pose": {
                    "x": round(self.zone.world_x, 6),
                    "y": round(self.zone.world_y, 6),
                    "radius_m": round(self.zone.retrieval_radius_m, 6),
                    "control_radius_m": round(self.zone.control_radius_m, 6),
                    "dwell_s": round(self.zone.dwell_s, 6),
                },
                "mission_error": final_mission_error,
                "mission_root": str(mission_root),
            }
            mission_verdict["summary_path"] = str(mission_root / "summary.json")
            write_json(mission_root / "mission_verdict.json", mission_verdict)

            summary = {
                "generated_utc": utc_now(),
                "type": "gather_mission",
                "pass": bool(mission_verdict["pass"]),
                "scenario_id": self.args.scenario_id,
                "scenario_label": self.args.scenario_label,
                "session_id": session_id,
                "world_file": self.world_file,
                "surface_profile": self.surface_profile,
                "route_order": mission_verdict["route_order"],
                "placed_targets": placed_targets,
                "placed_count": mission_verdict["placed_count"],
                "mission_completed_pass": mission_completed_pass,
                "capture_loss_count": capture_loss_count,
                "handoff_kind": handoff_kind,
                "zone_edge_correction_count": zone_edge_correction_count,
                "place_controller_reentry_count": place_controller_reentry_count,
                "post_visit_revisit_count": post_visit_revisit_count,
                "settle_exit_reason": settle_exit_reason,
                "stopped_with_ball_captured": stopped_with_ball_captured,
                "release_started_with_capture": release_started_with_capture,
                "stop_capture_state": stop_capture_state,
                "release_capture_state": release_capture_state,
                "clean_retention_pass": clean_retention_pass,
                "final_inside_retrieval_corral": final_inside_retrieval_corral,
                "final_center_inside_zone": final_center_inside_zone,
                "ball_stopped_in_corral": ball_stopped_in_corral,
                "rolled_away_after_release": rolled_away_after_release,
                "settled_in_corral_pass": settled_in_corral_pass,
                "final_corral_audit": final_corral_audit,
                "final_all_targets_inside_retrieval_corral": final_all_targets_inside_retrieval_corral,
                "final_all_targets_stopped": final_all_targets_stopped,
                "final_three_ball_corral_pass": final_three_ball_corral_pass,
                "retrieved_count": retrieved_count,
                "final_settle_distance_m": mission_verdict["final_settle_distance_m"],
                "max_overshoot_distance_m": mission_verdict["max_overshoot_distance_m"],
                "settle_time_s": mission_verdict["settle_time_s"],
                "release_recontact_count": mission_verdict["release_recontact_count"],
                "mission_time_s": mission_time_s,
                "mission_verdict_path": str(mission_root / "mission_verdict.json"),
                "target_results_path": str(target_results_path),
                "scorecard_path": str(mission_root / "scorecard.md"),
            }
            write_json(mission_root / "summary.json", summary)
            scorecard_markdown = build_scorecard_markdown(
                scenario_label=self.args.scenario_label,
                summary={
                    "pass_count": 1 if summary["pass"] else 0,
                    "promotion_gate_pass": summary["pass"],
                    "settled_in_corral_pass_count": 1 if settled_in_corral_pass else 0,
                    "settled_in_corral_fail_count": 0 if settled_in_corral_pass else 1,
                    "final_inside_retrieval_corral_count": 1 if final_inside_retrieval_corral else 0,
                    "final_center_inside_zone_count": 1 if final_center_inside_zone else 0,
                    "ball_stopped_in_corral_count": 1 if ball_stopped_in_corral else 0,
                    "rolled_away_after_release_count": 1 if rolled_away_after_release else 0,
                    "clean_retention_pass_count": 1 if clean_retention_pass else 0,
                    "clean_retention_fail_count": 0 if clean_retention_pass else 1,
                    "mission_time_avg_s": summary["mission_time_s"],
                    "mission_time_min_s": summary["mission_time_s"],
                    "mission_time_max_s": summary["mission_time_s"],
                    "handoff_kinds": [handoff_kind],
                    "settle_exit_reasons": [settle_exit_reason] if settle_exit_reason else [],
                    "capture_loss_count_total": capture_loss_count,
                    "stopped_with_ball_captured_count": 1 if stopped_with_ball_captured else 0,
                    "release_started_with_capture_count": 1 if release_started_with_capture else 0,
                    "surface_profiles": [self.surface_profile],
                    "final_settle_distance_avg_m": summary["final_settle_distance_m"],
                    "final_settle_distance_max_m": summary["final_settle_distance_m"],
                    "max_overshoot_distance_max_m": summary["max_overshoot_distance_m"],
                    "settle_time_avg_s": summary["settle_time_s"],
                    "settle_time_max_s": summary["settle_time_s"],
                    "release_recontact_count_total": summary["release_recontact_count"],
                    "zone_edge_correction_count_total": zone_edge_correction_count,
                    "place_controller_reentry_count_total": place_controller_reentry_count,
                    "post_visit_revisit_count_total": post_visit_revisit_count,
                    "final_all_targets_inside_retrieval_corral_count": 1 if final_all_targets_inside_retrieval_corral else 0,
                    "final_all_targets_stopped_count": 1 if final_all_targets_stopped else 0,
                    "final_three_ball_corral_pass_count": 1 if final_three_ball_corral_pass else 0,
                    "final_three_ball_corral_fail_count": 0 if final_three_ball_corral_pass else 1,
                    "retrieved_count_avg": float(retrieved_count),
                    "retrieved_count_max": retrieved_count,
                },
                runs=[
                    {
                        "run_index": 1,
                        "pass": summary["pass"],
                        "surface_profile": self.surface_profile,
                        "handoff_kind": handoff_kind,
                        "settle_exit_reason": settle_exit_reason,
                        "placed_count": summary["placed_count"],
                        "capture_loss_count": capture_loss_count,
                        "zone_edge_correction_count": zone_edge_correction_count,
                        "place_controller_reentry_count": place_controller_reentry_count,
                        "post_visit_revisit_count": post_visit_revisit_count,
                        "stopped_with_ball_captured": stopped_with_ball_captured,
                        "release_started_with_capture": release_started_with_capture,
                        "clean_retention_pass": clean_retention_pass,
                        "final_inside_retrieval_corral": final_inside_retrieval_corral,
                        "final_center_inside_zone": final_center_inside_zone,
                        "ball_stopped_in_corral": ball_stopped_in_corral,
                        "rolled_away_after_release": rolled_away_after_release,
                        "settled_in_corral_pass": settled_in_corral_pass,
                        "final_corral_audit": final_corral_audit,
                        "final_all_targets_inside_retrieval_corral": final_all_targets_inside_retrieval_corral,
                        "final_all_targets_stopped": final_all_targets_stopped,
                        "final_three_ball_corral_pass": final_three_ball_corral_pass,
                        "retrieved_count": retrieved_count,
                        "final_settle_distance_m": summary["final_settle_distance_m"],
                        "max_overshoot_distance_m": summary["max_overshoot_distance_m"],
                        "settle_time_s": summary["settle_time_s"],
                        "release_recontact_count": summary["release_recontact_count"],
                        "mission_time_s": summary["mission_time_s"],
                    }
                ],
            )
            (mission_root / "scorecard.md").write_text(scorecard_markdown, encoding="utf-8")
            self._update_visit_runtime_state(
                running=False,
                proof_state="completed" if mission_verdict["pass"] else "failed",
                mission_verdict=mission_verdict,
                mission_phase="completed" if mission_verdict["pass"] else "failed",
                mission_status="completed" if mission_verdict["pass"] else "failed",
                current_target_id="",
                latest_feedback="Gather mission completed." if mission_verdict["pass"] else f"Gather mission failed: {final_mission_error or 'mission_failed'}.",
                surface_profile=self.surface_profile,
            )
            self._update_gather_runtime_state(
                running=False,
                mission_verdict=mission_verdict,
                mission_phase="completed" if mission_verdict["pass"] else "failed",
                mission_status="completed" if mission_verdict["pass"] else "failed",
                gather_phase="completed" if mission_verdict["pass"] else "failed",
                current_target_id="",
                latest_feedback="Gather mission completed." if mission_verdict["pass"] else f"Gather mission failed: {final_mission_error or 'mission_failed'}.",
                surface_profile=self.surface_profile,
                final_corral_audit=final_corral_audit,
            )
            return summary
        finally:
            self._set_manual_drive(False, mode="shutdown", rationale="Mission cleanup.")
            try:
                current_state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
                compose_project = clean_text(current_state.get("compose_project"))
                if compose_project:
                    self._stop_motion_bridge(compose_project)
                if bool(getattr(self.args, "cleanup_mission_models", False)):
                    self._clear_mission_models(current_state)
            except Exception:
                pass
            if self._started_here and not self.args.keep_environment:
                try:
                    self._stop_environment()
                except Exception:
                    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a deterministic gather mission through the dashboard control plane.")
    parser.add_argument("--dashboard-url", default=DEFAULT_DASHBOARD_URL)
    parser.add_argument("--provider", default=os.environ.get("CHASECAR_LLM_PROVIDER", "openai"))
    parser.add_argument("--model", default=os.environ.get("OPENAI_SUPERVISOR_MODEL") or DEFAULT_OPENAI_MODEL)
    parser.add_argument("--reasoning-effort", default=os.environ.get("OPENAI_SUPERVISOR_REASONING_EFFORT") or os.environ.get("OPENAI_REASONING_EFFORT") or DEFAULT_REASONING_EFFORT)
    parser.add_argument("--scenario-id", default="corral_single_ball_place")
    parser.add_argument("--scenario-label", default="Corral Single Ball Place")
    parser.add_argument("--world-file", default=os.environ.get("WORLD_FILE", ""))
    parser.add_argument("--surface-profile", default=os.environ.get("CHASECAR_SURFACE_PROFILE", "baseline"))
    parser.add_argument("--artifact-kind", default="gather_mission")
    parser.add_argument("--poll-s", type=float, default=0.5)
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--environment-timeout-s", type=float, default=360.0)
    parser.add_argument("--visit-timeout-s", type=float, default=120.0)
    parser.add_argument("--capture-timeout-s", type=float, default=20.0)
    parser.add_argument("--place-timeout-s", type=float, default=35.0)
    parser.add_argument("--pursuit-settle-timeout-s", type=float, default=8.0)
    parser.add_argument("--max-retries-per-target", type=int, default=2)
    parser.add_argument("--max-place-loss-revisits", type=int, default=1)
    parser.add_argument("--target-model-name", default=DEFAULT_TARGET_MODEL_NAME)
    parser.add_argument("--target-model-sdf", default=str(DEFAULT_TARGET_MODEL_SDF))
    parser.add_argument("--zone-model-name", default=DEFAULT_ZONE_MODEL_NAME)
    parser.add_argument("--zone-model-sdf", default=str(DEFAULT_ZONE_MODEL_SDF))
    parser.add_argument("--visit-runtime-json", default=str(DEFAULT_VISIT_RUNTIME_STATE_PATH))
    parser.add_argument("--gather-runtime-json", default=str(DEFAULT_GATHER_RUNTIME_STATE_PATH))
    parser.add_argument("--motion-loop-hz", type=float, default=10.0)
    parser.add_argument("--keep-environment", action="store_true")
    parser.add_argument("--cleanup-mission-models", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runner = GatherMissionRunner(args)
    summary = runner.run()
    print(f"GATHER_MISSION_SUMMARY={summary['mission_verdict_path']}")
    return 0 if summary["pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
