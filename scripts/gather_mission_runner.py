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
from gather_mission_helpers import DEFAULT_ZONE_DWELL_S
from gather_mission_helpers import DEFAULT_RELEASE_SETTLE_MOTION_TOLERANCE_M
from gather_mission_helpers import DEFAULT_RELEASE_SETTLE_STABLE_WINDOW_S
from gather_mission_helpers import CaptureEnvelope
from gather_mission_helpers import GatherTargetSpec
from gather_mission_helpers import build_gather_targets
from gather_mission_helpers import build_scorecard_markdown
from gather_mission_helpers import build_zone_spec
from gather_mission_helpers import capture_loss_detected
from gather_mission_helpers import capture_snapshot
from gather_mission_helpers import compute_capture_command
from gather_mission_helpers import compute_place_command
from gather_mission_helpers import normalize_angle
from gather_mission_helpers import pose_delta_m
from gather_mission_helpers import release_ready
from gather_mission_helpers import summarize_release_settle_trace
from gather_mission_helpers import world_pose_xyyaw
from gather_mission_helpers import zone_dwell_complete
from gather_mission_helpers import zone_snapshot


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
DEFAULT_PLACE_LOCAL_RECOVERY_WINDOW_S = 1.25
DEFAULT_PLACE_RECOVERY_SETTLE_S = 0.20

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
    ) -> dict[str, Any]:
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
        }
        if isinstance(settle_metrics, dict):
            payload.update(settle_metrics)
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
    ) -> dict[str, Any]:
        payload = {
            "target_id": target.id,
            "label": target.label,
            "pass": True,
            "attempts": int(attempts),
            "attempt_kind": str(attempt_kind),
            "capture_loss_count": int(capture_loss_count),
            "route_index": int(route_index),
            "placed": True,
            "final_ball_pose": final_ball_pose,
            "place_time_s": round(float(place_time_s), 6),
            "local_recovery_attempted": bool(local_recovery_attempted),
            "revisit_attempted": bool(revisit_attempted),
            "surface_profile": self.surface_profile,
        }
        if isinstance(settle_metrics, dict):
            payload.update(settle_metrics)
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
                "radius_m": round(self.zone.radius_m, 6),
                "dwell_s": round(self.zone.dwell_s, 6),
            },
            "zone_score": {},
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
                        "radius_m": round(self.zone.radius_m, 6),
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
        zone_entry_monotonic: float | None = None
        while time.monotonic() < deadline:
            now_monotonic = time.monotonic()
            _dashboard_state, robot_pose, ball_pose = self._control_loop_state(session_id=session_id, target=target)
            capture = capture_snapshot(robot_pose, ball_pose or {}, self.capture_envelope) if robot_pose and ball_pose else None
            zone_score = zone_snapshot(ball_pose or {}, self.zone) if ball_pose else None
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
                },
            )
            if zone_score and zone_score.inside_zone:
                zone_entry_monotonic = zone_entry_monotonic or now_monotonic
            else:
                zone_entry_monotonic = None
            if zone_score and zone_dwell_complete(
                inside_zone=zone_score.inside_zone,
                zone_entry_monotonic=zone_entry_monotonic,
                now_monotonic=now_monotonic,
                dwell_s=max(self.zone.dwell_s, DEFAULT_ZONE_DWELL_S),
            ):
                self._set_manual_drive(False, mode="placed", rationale="Ball is dwelling inside the zone.")
                return True, {
                    "capture_state": capture.to_dict() if capture else {},
                    "zone_score": zone_score.to_dict(),
                    "final_ball_pose": ball_pose,
                }
            if prefer_zone_recovery and zone_score and zone_score.inside_zone:
                self._set_manual_drive(False, mode="zone_dwell", rationale="Ball entered the zone during recapture; holding for dwell.")
                time.sleep(self.args.poll_s)
                continue
            if capture and capture.captured:
                self._set_manual_drive(False, mode="captured", rationale="Ball captured.")
                return True, {
                    "capture_state": capture.to_dict(),
                    "zone_score": zone_score.to_dict() if zone_score else {},
                }
            if robot_pose and ball_pose:
                if prefer_zone_recovery:
                    use_zone_recovery = bool(
                        capture
                        and (
                            capture.within_recapture_window
                            or (
                                zone_score is not None
                                and float(zone_score.zone_distance_m) <= (float(self.zone.radius_m) + 0.35)
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
                else:
                    command = compute_capture_command(robot_pose, ball_pose or {}, envelope=self.capture_envelope)
            else:
                command = None
            if command is not None:
                self._set_manual_drive(
                    True,
                    linear_x=command.linear_x,
                    angular_z=command.angular_z,
                    mode=command.mode,
                    rationale=command.rationale,
                )
                self._update_gather_runtime_state(latest_control_command=command.to_dict())
            time.sleep(self.args.poll_s)

        self._set_manual_drive(False, mode="capture_timeout", rationale="Capture timed out.")
        timeout_payload = {"failure_reason": "capture_timeout", "failure_stage": "capture"}
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
        zone_entry_monotonic: float | None = None
        last_captured_monotonic: float | None = None
        local_recovery_attempted = False
        local_recovery_deadline_monotonic: float | None = None
        local_recovery_started_monotonic: float | None = None
        recaptured_settle_started_monotonic: float | None = None
        release_origin_monotonic: float | None = None
        release_monitoring_active = False
        release_samples: list[dict[str, Any]] = []
        release_prev_ball_pose: dict[str, Any] | None = None
        release_recontact_count = 0
        release_inside_seen = False

        while time.monotonic() < deadline:
            now_monotonic = time.monotonic()
            _dashboard_state, robot_pose, ball_pose = self._control_loop_state(session_id=session_id, target=target)
            capture = capture_snapshot(robot_pose, ball_pose or {}, self.capture_envelope) if robot_pose and ball_pose else None
            zone_score = zone_snapshot(ball_pose or {}, self.zone) if ball_pose else None
            if ball_pose:
                self._update_prior_from_ball_pose(target.id, ball_pose)
            if capture and capture.captured:
                last_captured_monotonic = now_monotonic
                if local_recovery_started_monotonic is not None:
                    local_recovery_started_monotonic = None
                    recaptured_settle_started_monotonic = now_monotonic
            inside_zone = bool(zone_score.inside_zone) if zone_score else False
            if inside_zone:
                zone_entry_monotonic = zone_entry_monotonic or now_monotonic
            else:
                zone_entry_monotonic = None
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
                if inside_zone:
                    release_inside_seen = True
                settle_metrics = summarize_release_settle_trace(
                    surface_profile=self.surface_profile,
                    zone=self.zone,
                    release_samples=release_samples,
                    release_recontact_count=release_recontact_count,
                ).to_dict()
                self._set_manual_drive(
                    False,
                    mode="release_settle",
                    rationale=f"Ball entered the release corridor; letting {self.surface_profile} friction settle it.",
                )
                self._update_gather_runtime_state(
                    latest_feedback=f"Letting {target.label} settle on {self.surface_profile}.",
                    settle_metrics=settle_metrics,
                )
                if zone_score and zone_dwell_complete(
                    inside_zone=zone_score.inside_zone,
                    zone_entry_monotonic=zone_entry_monotonic,
                    now_monotonic=now_monotonic,
                    dwell_s=max(self.zone.dwell_s, DEFAULT_ZONE_DWELL_S),
                ):
                    return True, {
                        "capture_state": capture.to_dict() if capture else {},
                        "zone_score": zone_score.to_dict(),
                        "final_ball_pose": ball_pose,
                        "settle_metrics": settle_metrics,
                        "release_recontact_count": release_recontact_count,
                    }
                release_elapsed_s = now_monotonic - release_origin_monotonic
                if (
                    not release_inside_seen
                    and release_elapsed_s >= DEFAULT_RELEASE_SETTLE_STABLE_WINDOW_S
                    and capture
                    and capture.within_recapture_window
                    and release_recontact_count < 1
                ):
                    release_recontact_count += 1
                    release_monitoring_active = False
                    self._append_runtime_event(
                        f"{target.label}: gentle recontact after short release on {self.surface_profile}.",
                        key=f"release_recontact_short:{target.id}:{release_recontact_count}",
                    )
                    self._update_gather_runtime_state(
                        latest_feedback=f"Recontacting {target.label} after short release.",
                        settle_metrics=settle_metrics,
                    )
                elif release_inside_seen and zone_score and float(zone_score.zone_distance_m) > float(self.zone.radius_m) + 0.05:
                    if capture and capture.within_recapture_window and release_recontact_count < 1:
                        release_recontact_count += 1
                        release_monitoring_active = False
                        self._append_runtime_event(
                            f"{target.label}: gentle recontact after release overshoot on {self.surface_profile}.",
                            key=f"release_recontact_overshoot:{target.id}:{release_recontact_count}",
                        )
                        self._update_gather_runtime_state(
                            latest_feedback=f"Recontacting {target.label} after release overshoot.",
                            settle_metrics=settle_metrics,
                        )
                    else:
                        self._set_manual_drive(False, mode="release_overshoot", rationale="Ball overshot beyond the zone after release.")
                        return False, {
                            "failure_reason": "release_overshoot",
                            "failure_stage": "release",
                            "capture_state": capture.to_dict() if capture else {},
                            "zone_score": zone_score.to_dict() if zone_score else {},
                            "local_recovery_attempted": local_recovery_attempted,
                            "settle_metrics": settle_metrics,
                            "release_recontact_count": release_recontact_count,
                        }
                elif (
                    not release_inside_seen
                    and release_elapsed_s >= 2.0
                ):
                    self._set_manual_drive(False, mode="release_stalled", rationale="Ball did not settle into the zone after release.")
                    return False, {
                        "failure_reason": "release_stalled",
                        "failure_stage": "release",
                        "capture_state": capture.to_dict() if capture else {},
                        "zone_score": zone_score.to_dict() if zone_score else {},
                        "local_recovery_attempted": local_recovery_attempted,
                        "settle_metrics": settle_metrics,
                        "release_recontact_count": release_recontact_count,
                    }
                time.sleep(self.args.poll_s)
                continue
            release_prev_ball_pose = dict(ball_pose or {}) if ball_pose else release_prev_ball_pose
            if release_ready(capture=capture, zone_score=zone_score, zone=self.zone):
                release_origin_monotonic = release_origin_monotonic or now_monotonic
                release_monitoring_active = True
                release_inside_seen = release_inside_seen or inside_zone
                initial_sample = self._release_sample(
                    release_started_monotonic=release_origin_monotonic,
                    now_monotonic=now_monotonic,
                    ball_pose=ball_pose,
                    zone_score=zone_score,
                )
                if not release_samples or release_samples[-1] != initial_sample:
                    release_samples.append(initial_sample)
                self._set_manual_drive(
                    False,
                    mode="release_settle",
                    rationale=f"Ball reached the release corridor; letting {self.surface_profile} friction settle it.",
                )
                self._update_gather_runtime_state(
                    latest_feedback=f"Letting {target.label} settle on {self.surface_profile}.",
                    settle_metrics=summarize_release_settle_trace(
                        surface_profile=self.surface_profile,
                        zone=self.zone,
                        release_samples=release_samples,
                        release_recontact_count=release_recontact_count,
                    ).to_dict(),
                )
                time.sleep(self.args.poll_s)
                continue
            if zone_score and zone_dwell_complete(
                inside_zone=zone_score.inside_zone,
                zone_entry_monotonic=zone_entry_monotonic,
                now_monotonic=now_monotonic,
                dwell_s=max(self.zone.dwell_s, DEFAULT_ZONE_DWELL_S),
            ):
                settle_metrics = summarize_release_settle_trace(
                    surface_profile=self.surface_profile,
                    zone=self.zone,
                    release_samples=[
                        self._release_sample(
                            release_started_monotonic=now_monotonic,
                            now_monotonic=now_monotonic,
                            ball_pose=ball_pose,
                            zone_score=zone_score,
                        )
                    ],
                    release_recontact_count=release_recontact_count,
                ).to_dict()
                self._set_manual_drive(False, mode="placed", rationale="Ball is dwelling inside the zone.")
                return True, {
                    "capture_state": capture.to_dict() if capture else {},
                    "zone_score": zone_score.to_dict(),
                    "final_ball_pose": ball_pose,
                    "settle_metrics": settle_metrics,
                    "release_recontact_count": release_recontact_count,
                }
            if zone_score and zone_score.inside_zone:
                self._set_manual_drive(False, mode="zone_dwell", rationale="Ball is inside the zone; holding for dwell.")
                time.sleep(self.args.poll_s)
                continue
            local_recovery_viable = bool(capture and capture.within_recapture_window)
            local_recovery_active = local_recovery_started_monotonic is not None
            if local_recovery_active:
                if (
                    recaptured_settle_started_monotonic is None
                    and (
                        (not local_recovery_viable)
                        or (
                            local_recovery_deadline_monotonic is not None
                            and now_monotonic >= local_recovery_deadline_monotonic
                        )
                    )
                ):
                    self._set_manual_drive(False, mode="capture_lost", rationale="Capture recovery expired during place.")
                    return False, {
                        "failure_reason": "capture_lost",
                        "failure_stage": "place",
                        "capture_state": capture.to_dict() if capture else {},
                        "zone_score": zone_score.to_dict() if zone_score else {},
                        "local_recovery_attempted": local_recovery_attempted,
                    }
            elif capture and not capture.captured:
                if local_recovery_viable:
                    if not local_recovery_attempted:
                        local_recovery_attempted = True
                        local_recovery_deadline_monotonic = now_monotonic + DEFAULT_PLACE_LOCAL_RECOVERY_WINDOW_S
                        self._append_runtime_event(
                            f"{target.label}: short local recapture during place.",
                            key=f"place_local_recovery:{target.id}",
                        )
                    elif local_recovery_deadline_monotonic is not None and now_monotonic >= local_recovery_deadline_monotonic:
                        self._set_manual_drive(False, mode="capture_lost", rationale="Capture recovery budget exhausted during place.")
                        return False, {
                            "failure_reason": "capture_lost",
                            "failure_stage": "place",
                            "capture_state": capture.to_dict() if capture else {},
                            "zone_score": zone_score.to_dict() if zone_score else {},
                            "local_recovery_attempted": local_recovery_attempted,
                        }
                    local_recovery_started_monotonic = now_monotonic
                    recaptured_settle_started_monotonic = None
                    self._update_gather_runtime_state(latest_feedback=f"Recovering {target.label} after brief capture loss.")
                else:
                    self._set_manual_drive(False, mode="capture_lost", rationale="Capture lost during place.")
                    return False, {
                        "failure_reason": "capture_lost",
                        "failure_stage": "place",
                        "capture_state": capture.to_dict(),
                        "zone_score": zone_score.to_dict() if zone_score else {},
                        "local_recovery_attempted": local_recovery_attempted,
                    }
            elif capture_loss_detected(
                captured_now=False,
                last_captured_monotonic=last_captured_monotonic,
                now_monotonic=now_monotonic,
                loss_grace_s=self.capture_envelope.loss_grace_s,
            ):
                self._set_manual_drive(False, mode="capture_lost", rationale="Ball pose disappeared during place.")
                return False, {
                    "failure_reason": "capture_lost",
                    "failure_stage": "place",
                    "capture_state": capture.to_dict() if capture else {},
                    "zone_score": zone_score.to_dict() if zone_score else {},
                    "local_recovery_attempted": local_recovery_attempted,
                }
            if recaptured_settle_started_monotonic is not None:
                settle_elapsed_s = now_monotonic - recaptured_settle_started_monotonic
                if settle_elapsed_s < DEFAULT_PLACE_RECOVERY_SETTLE_S:
                    self._set_manual_drive(False, mode="capture_settle", rationale="Ball recaptured; settling before place.")
                    self._update_gather_runtime_state(latest_feedback=f"Stabilizing {target.label} after recapture.")
                    time.sleep(self.args.poll_s)
                    continue
                recaptured_settle_started_monotonic = None
            if local_recovery_started_monotonic is not None:
                command = compute_place_command(robot_pose, ball_pose or {}, zone=self.zone, envelope=self.capture_envelope) if robot_pose and ball_pose else None
            else:
                command = compute_place_command(robot_pose, ball_pose or {}, zone=self.zone, envelope=self.capture_envelope) if robot_pose and ball_pose else None
            if command is not None:
                if local_recovery_started_monotonic is not None:
                    command = command.__class__(
                        mode="capture_recovery",
                        linear_x=min(float(command.linear_x), 0.12),
                        angular_z=float(command.angular_z),
                        target_speed_scale=min(float(command.target_speed_scale), 0.7),
                        rationale="Briefly recenter the ball under the catcher before resuming place.",
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
            "settle_metrics": summarize_release_settle_trace(
                surface_profile=self.surface_profile,
                zone=self.zone,
                release_samples=release_samples,
                release_recontact_count=release_recontact_count,
            ).to_dict(),
            "release_recontact_count": release_recontact_count,
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
        local_recovery_attempted_any = False
        resume_with_capture = False
        resume_with_place_loss_revisit = False
        target_start_monotonic = time.monotonic()
        while attempt <= self.args.max_retries_per_target:
            attempt += 1
            direct_recapture_attempt = resume_with_capture
            place_loss_revisit_attempt = resume_with_place_loss_revisit
            if direct_recapture_attempt:
                attempt_kind = "place_loss_recapture"
            elif place_loss_revisit_attempt:
                attempt_kind = "place_loss_revisit"
            else:
                attempt_kind = "initial_visit" if attempt == 1 else "retry_visit"
            if direct_recapture_attempt:
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
                resume_with_capture = False
            else:
                if place_loss_revisit_attempt:
                    self._append_runtime_event(
                        f"{target.label}: full revisit {place_loss_full_revisit_count} after place-stage loss.",
                        key=f"place_loss_revisit:{target.id}:{place_loss_full_revisit_count}",
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
                resume_with_place_loss_revisit = False
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
                            revisit_attempted=place_loss_full_revisit_count > 0,
                        )
                    self._safe_stop()
                    self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
                    continue

                self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
            capture_pass, capture_payload = self._capture_target(
                session_id=session_id,
                target=target,
                state_history_path=state_history_path,
                mission_root=mission_root,
                prefer_zone_recovery=(attempt_kind == "place_loss_recapture"),
            )
            if not capture_pass:
                capture_failure_reason = str(capture_payload.get("failure_reason", "capture_failed"))
                capture_failure_stage = str(capture_payload.get("failure_stage", "capture"))
                if (
                    attempt_kind == "place_loss_recapture"
                    and place_loss_full_revisit_count < 1
                    and attempt <= self.args.max_retries_per_target
                ):
                    place_loss_full_revisit_count += 1
                    self._append_runtime_event(
                        f"{target.label}: full revisit after unsuccessful place-loss recapture.",
                        key=f"place_loss_revisit_dispatch:{target.id}:{place_loss_full_revisit_count}",
                    )
                    self._safe_stop()
                    self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
                    resume_with_place_loss_revisit = True
                    continue
                if attempt > self.args.max_retries_per_target:
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
                        revisit_attempted=place_loss_full_revisit_count > 0,
                        settle_metrics=capture_payload.get("settle_metrics") if isinstance(capture_payload.get("settle_metrics"), dict) else None,
                    )
                if place_loss_full_revisit_count > 0:
                    self._update_visit_runtime_state(proof_state="failed", mission_phase="failed", latest_feedback=f"{target.label} capture failed after revisit.")
                    return self._target_failure_result(
                        target=target,
                        failure_reason=capture_failure_reason,
                        failure_stage=capture_failure_stage,
                        attempts=attempt,
                        capture_loss_count=capture_loss_count,
                        route_index=route_index,
                        attempt_kind=attempt_kind,
                        local_recovery_attempted=local_recovery_attempted_any,
                        revisit_attempted=True,
                        settle_metrics=capture_payload.get("settle_metrics") if isinstance(capture_payload.get("settle_metrics"), dict) else None,
                    )
                self._safe_stop()
                self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
                continue

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
                    revisit_attempted=place_loss_full_revisit_count > 0,
                    settle_metrics=settle_metrics,
                )

            place_pass, place_payload = self._place_target(
                session_id=session_id,
                target=target,
                state_history_path=state_history_path,
            )
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
                    revisit_attempted=place_loss_full_revisit_count > 0,
                    settle_metrics=settle_metrics,
                )

            failure_reason = str(place_payload.get("failure_reason", "place_failed"))
            failure_stage = str(place_payload.get("failure_stage", "place"))
            local_recovery_attempted = bool(place_payload.get("local_recovery_attempted", False))
            local_recovery_attempted_any = local_recovery_attempted_any or local_recovery_attempted
            if failure_reason == "capture_lost":
                capture_loss_count += 1
                self._update_gather_runtime_state(capture_loss_count=capture_loss_count)
                if place_loss_full_revisit_count == 0 and place_loss_recapture_count < max(int(self.args.max_place_loss_revisits), 0):
                    place_loss_recapture_count += 1
                    self._append_runtime_event(
                        f"{target.label}: direct recapture after place-stage capture loss {place_loss_recapture_count}.",
                        key=f"place_loss_recovery:{target.id}:{place_loss_recapture_count}",
                    )
                    self._safe_stop()
                    self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
                    resume_with_capture = True
                    continue
                if place_loss_full_revisit_count < 1 and attempt <= self.args.max_retries_per_target:
                    place_loss_full_revisit_count += 1
                    self._append_runtime_event(
                        f"{target.label}: full revisit after place-stage capture loss.",
                        key=f"place_loss_revisit_dispatch:{target.id}:{place_loss_full_revisit_count}",
                    )
                    self._safe_stop()
                    self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
                    resume_with_place_loss_revisit = True
                    continue
            if attempt > self.args.max_retries_per_target or (failure_reason == "capture_lost" and place_loss_full_revisit_count >= 1 and place_loss_recapture_count >= max(int(self.args.max_place_loss_revisits), 0)):
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
                    revisit_attempted=place_loss_full_revisit_count > 0,
                    settle_metrics=place_payload.get("settle_metrics") if isinstance(place_payload.get("settle_metrics"), dict) else None,
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
            revisit_attempted=place_loss_full_revisit_count > 0,
            settle_metrics={},
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
            final_settle_distance_m = max(
                [float(item.get("final_settle_distance_m", 0.0) or 0.0) for item in target_results if item.get("pass")],
                default=0.0,
            )
            max_overshoot_distance_m = max(
                [float(item.get("max_overshoot_distance_m", 0.0) or 0.0) for item in target_results],
                default=0.0,
            )
            settle_time_s = max(
                [float(item.get("settle_time_s", 0.0) or 0.0) for item in target_results if item.get("pass")],
                default=0.0,
            )
            release_recontact_count = sum(int(item.get("release_recontact_count", 0) or 0) for item in target_results)
            mission_verdict = {
                "generated_utc": utc_now(),
                "type": "gather_mission",
                "pass": mission_pass and len(placed_targets) == len(self.targets),
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
                "final_settle_distance_m": round(final_settle_distance_m, 6),
                "max_overshoot_distance_m": round(max_overshoot_distance_m, 6),
                "settle_time_s": round(settle_time_s, 6),
                "release_recontact_count": release_recontact_count,
                "mission_time_s": mission_time_s,
                "zone_pose": {
                    "x": round(self.zone.world_x, 6),
                    "y": round(self.zone.world_y, 6),
                    "radius_m": round(self.zone.radius_m, 6),
                    "dwell_s": round(self.zone.dwell_s, 6),
                },
                "mission_error": mission_error,
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
                "capture_loss_count": capture_loss_count,
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
                    "mission_time_avg_s": summary["mission_time_s"],
                    "mission_time_min_s": summary["mission_time_s"],
                    "mission_time_max_s": summary["mission_time_s"],
                    "capture_loss_count_total": capture_loss_count,
                    "surface_profiles": [self.surface_profile],
                    "final_settle_distance_avg_m": summary["final_settle_distance_m"],
                    "final_settle_distance_max_m": summary["final_settle_distance_m"],
                    "max_overshoot_distance_max_m": summary["max_overshoot_distance_m"],
                    "settle_time_avg_s": summary["settle_time_s"],
                    "settle_time_max_s": summary["settle_time_s"],
                    "release_recontact_count_total": summary["release_recontact_count"],
                },
                runs=[
                    {
                        "run_index": 1,
                        "pass": summary["pass"],
                        "surface_profile": self.surface_profile,
                        "placed_count": summary["placed_count"],
                        "capture_loss_count": capture_loss_count,
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
                latest_feedback="Gather mission completed." if mission_verdict["pass"] else f"Gather mission failed: {mission_error or 'mission_failed'}.",
                surface_profile=self.surface_profile,
            )
            self._update_gather_runtime_state(
                running=False,
                mission_verdict=mission_verdict,
                mission_phase="completed" if mission_verdict["pass"] else "failed",
                mission_status="completed" if mission_verdict["pass"] else "failed",
                gather_phase="completed" if mission_verdict["pass"] else "failed",
                current_target_id="",
                latest_feedback="Gather mission completed." if mission_verdict["pass"] else f"Gather mission failed: {mission_error or 'mission_failed'}.",
                surface_profile=self.surface_profile,
            )
            return summary
        finally:
            self._set_manual_drive(False, mode="shutdown", rationale="Mission cleanup.")
            try:
                current_state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
                compose_project = clean_text(current_state.get("compose_project"))
                if compose_project:
                    self._stop_motion_bridge(compose_project)
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runner = GatherMissionRunner(args)
    summary = runner.run()
    print(f"GATHER_MISSION_SUMMARY={summary['mission_verdict_path']}")
    return 0 if summary["pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
