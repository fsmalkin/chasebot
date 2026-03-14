#!/usr/bin/env python3
"""Persistent local dashboard control service for the authoritative container lane."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

import yaml

from llm_supervisor_core import load_supervisor_runtime_state as load_shadow_runtime_state
from llm_supervisor_core import read_jsonl as read_jsonl_lines


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
RUNTIME_DIR = REPO_ROOT / "runtime" / "dashboard"
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
STATE_PATH = RUNTIME_DIR / "dashboard_service_state.json"
LOCK_PATH = RUNTIME_DIR / "dashboard_session.lock.json"

DEFAULT_RUNTIME_TARGET = "robot_fidelity_orin"
DEFAULT_CORE_ROS_DISTRO = "kilted"
DEFAULT_WORLD_FILE = "yolo_test_world_v6_clean_uat.world"
DEFAULT_WORLD_NAME = "yolo_test_world"
DEFAULT_INFERENCE_BACKEND = "tensorrt_int8"
DEFAULT_GATE_PROFILE = "compat"
DEFAULT_INFERENCE_DEVICE = "cuda:0"
DEFAULT_MULTI_TARGET_CONFIG = "ros2_config/config/multi_target_nav2_fidelity.yaml"
DEFAULT_NAV2_CONFIG = "ros2_config/config/nav2_readiness_fidelity.yaml"
TARGET_MODEL_SDF = "ros2_config/frisbee_target_ball.sdf"
TARGET_MODEL_NAME_NAV2 = "uat_nav2_target"
TARGET_MODEL_NAME_SNAPSHOT = "uat_snapshot_target"
TARGET_MODEL_NAME_PROOF = "llm_turn_then_go_target"
DEFAULT_CONTROL_MODE = "host_powershell"
DEFAULT_SIM_LANE = "jetty_gate"
DEFAULT_BRIDGE_ROS_DISTRO = "jazzy"
DEFAULT_WARM_SERVICES = ("dashboard-control", "dashboard-utility")
DEFAULT_DOCKER_SOCKET_PATH = Path("/var/run/docker.sock")
SESSION_PROJECT_PREFIX = "chasecar_dashboard_"

DOCKER_FALLBACK = Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe")
POWERSHELL_EXE = shutil.which("powershell.exe") or shutil.which("powershell") or "powershell.exe"


@dataclass(frozen=True)
class ScenarioDefinition:
    id: str
    phase: str
    target_id: str
    label: str
    description: str
    mode: str
    target_x: float = 1.10
    target_y: float = 0.00
    target_z: float = 0.05

    def to_api(self) -> Dict[str, Any]:
        return asdict(self)


SCENARIOS = [
    ScenarioDefinition(
        id="m2_single_target",
        phase="M2",
        target_id="single_target",
        label="M2 Single Target",
        description="Coordinate plus snapshot proof for a single target.",
        mode="m2",
    ),
    ScenarioDefinition(
        id="m3_single_target",
        phase="M3",
        target_id="single_target",
        label="M3 Single Target",
        description="Single-target motion proof on the canonical forward target.",
        mode="m3",
    ),
    ScenarioDefinition(
        id="m3_center",
        phase="M3",
        target_id="center",
        label="M3 Center",
        description="Single-target motion proof at the center preset.",
        mode="m3",
    ),
    ScenarioDefinition(
        id="m3_left",
        phase="M3",
        target_id="left",
        label="M3 Left",
        description="Single-target motion proof at the left preset.",
        mode="m3",
        target_y=0.12,
    ),
    ScenarioDefinition(
        id="m3_right",
        phase="M3",
        target_id="right",
        label="M3 Right",
        description="Single-target motion proof at the right preset.",
        mode="m3",
        target_y=-0.12,
    ),
    ScenarioDefinition(
        id="multi_target_rehearsal",
        phase="multi_target_rehearsal",
        target_id="multi_target",
        label="Multi-Target Rehearsal",
        description="Sequential multi-target rehearsal with explicit transition state.",
        mode="multi_target",
    ),
]
SCENARIOS_BY_ID = {item.id: item for item in SCENARIOS}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_session_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def slugify_session(session_id: str) -> str:
    return session_id.lower().replace(":", "").replace(" ", "")


def choose_docker_cli() -> str:
    found = shutil.which("docker")
    if found:
        return found
    if DOCKER_FALLBACK.exists():
        return str(DOCKER_FALLBACK)
    raise FileNotFoundError("Unable to locate docker CLI.")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def find_free_port(start: int, end: int) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError(f"No free localhost port in range {start}-{end}.")


def to_container_repo_path(path: Path) -> str:
    resolved = path.resolve()
    repo_root = REPO_ROOT.resolve()
    try:
        relative = resolved.relative_to(repo_root)
        if str(relative) == ".":
            return "/workspaces/chasecar"
        return "/workspaces/chasecar/" + relative.as_posix()
    except ValueError:
        drive = resolved.drive.rstrip(":").lower()
        tail = resolved.as_posix().split(":/", 1)[-1]
        if drive:
            return f"/mnt/{drive}/{tail}"
        return resolved.as_posix()


def parse_marker(text: str, prefix: str) -> str:
    matches = [line for line in text.splitlines() if line.startswith(prefix)]
    if not matches:
        return ""
    return matches[-1][len(prefix) :].strip()


def parse_step_marker(text: str, step_name: str) -> Dict[str, str]:
    pattern = re.compile(rf"^STEP_RESULT={re.escape(step_name)}:([^:]+):(.*)$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return {}
    return {"status": match.group(1).strip(), "artifact_dir": match.group(2).strip()}


class DashboardController:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.control_mode = (os.environ.get("CHASECAR_DASHBOARD_CONTROL_MODE", DEFAULT_CONTROL_MODE).strip() or DEFAULT_CONTROL_MODE)
        try:
            self.docker = choose_docker_cli()
        except FileNotFoundError:
            self.docker = ""
        warm_services_raw = os.environ.get("CHASECAR_DASHBOARD_WARM_SERVICES", ",".join(DEFAULT_WARM_SERVICES)).strip()
        self.warm_services = tuple(item.strip() for item in warm_services_raw.split(",") if item.strip()) or DEFAULT_WARM_SERVICES
        self.compose_file = REPO_ROOT / "docker-compose.yml"
        self.launcher_project = ""
        self.host_repo_mount_source = os.environ.get("HOST_REPO_MOUNT_SOURCE", "").strip()
        self._control_plane_checked_at = 0.0
        self.contract = self._load_contract()
        self.frozen_intents = {intent["name"]: intent for intent in self.contract.get("intents", [])}
        self.state_lock = threading.RLock()
        self.lifecycle_lock = threading.Lock()
        self.scenario_lock = threading.Lock()
        self.intent_lock = threading.Lock()
        self.lifecycle_cancel = threading.Event()
        self.scenario_cancel = threading.Event()

        self.lifecycle_thread: Optional[threading.Thread] = None
        self.scenario_thread: Optional[threading.Thread] = None
        self.intent_thread: Optional[threading.Thread] = None

        self.active_env_proc: Optional[subprocess.Popen[str]] = None
        self.active_scenario_proc: Optional[subprocess.Popen[str]] = None
        self.active_intent_proc: Optional[subprocess.Popen[str]] = None

        self.sim_gate_container_id = ""
        self.gate_stack_container_id = ""
        self.world_viewer_container_id = ""
        self.build_on_next_start = True

        ensure_dir(RUNTIME_DIR)
        with self.state_lock:
            self.state: Dict[str, Any] = {
                "service_started_utc": utc_now(),
                "service_mode": "api_backed",
                "control_mode": self.control_mode,
                "control_plane_ready": False,
                "control_plane_error": "",
                "warm_services_ready": False,
                "warm_services_status": "unknown",
                "warm_service_states": {},
                "launcher_project": "",
                "host_repo_mount_source": self.host_repo_mount_source,
                "environment_state": "stopped",
                "scenario_state": "idle",
                "session_id": "",
                "compose_project": "",
                "execution_lane": "container_kilted",
                "runtime_target": DEFAULT_RUNTIME_TARGET,
                "core_ros_distro": DEFAULT_CORE_ROS_DISTRO,
                "world_file": DEFAULT_WORLD_FILE,
                "world_name": DEFAULT_WORLD_NAME,
                "phase": "stopped",
                "target_id": "",
                "target_transition_active": False,
                "active_scenario": "",
                "environment_message": "stopped",
                "scenario_message": "",
                "last_intent": "",
                "last_feedback": "",
                "last_result": "",
                "last_intent_payload": {},
                "last_intent_timestamp_utc": "",
                "last_preview_payload": {},
                "last_preview_valid": False,
                "last_preview_error": "",
                "last_preview_timestamp_utc": "",
                "last_preview_session_id": "",
                "last_preview_readiness": {},
                "last_preview_expected_activity": [],
                "last_error": "",
                "status_text": "",
                "world_stream_url": "",
                "world_stream_port": 0,
                "validation_dir": "",
                "command_history_path": "",
                "multi_target_progress_path": "",
                "motion_evidence": False,
                "latest_artifacts": {},
                "operator_status_path": "",
                "lock_file": str(LOCK_PATH),
                "scenarios": [item.to_api() for item in SCENARIOS],
            }
            self._persist_state_locked()
        self._refresh_control_plane_state(force=True)

    def _load_contract(self) -> Dict[str, Any]:
        contract_path = REPO_ROOT / "runtime" / "contracts" / "llm_control_contract.yaml"
        with contract_path.open("r", encoding="utf-8") as fp:
            payload = yaml.safe_load(fp) or {}
        if not isinstance(payload, dict):
            raise ValueError("LLM control contract must be a mapping.")
        return payload

    def _intent_required_args(self, intent_name: str) -> list[str]:
        spec = self.frozen_intents.get(intent_name)
        if spec is None:
            raise KeyError(intent_name)
        return [str(value) for value in list(spec.get("required_args", []))]

    def _intent_transport(self) -> Dict[str, Any]:
        transport = self.contract.get("transport", {})
        return dict(transport) if isinstance(transport, dict) else {}

    def _normalize_intent_args(self, intent_name: str, args_payload: Dict[str, Any]) -> Dict[str, Any]:
        if intent_name not in self.frozen_intents:
            raise KeyError(intent_name)
        if not isinstance(args_payload, dict):
            raise ValueError("intent args must be an object")
        required_args = self._intent_required_args(intent_name)
        allowed_args = set(required_args)
        missing_args = [name for name in required_args if name not in args_payload]
        extra_args = sorted(name for name in args_payload.keys() if str(name) not in allowed_args)
        if missing_args:
            raise ValueError(f"Missing required args for {intent_name}: {', '.join(missing_args)}")
        if extra_args:
            raise ValueError(f"Unexpected args for {intent_name}: {', '.join(extra_args)}")

        normalized: Dict[str, Any] = {}
        for name in required_args:
            value = args_payload.get(name)
            if name == "target_class":
                value = str(value or "").strip()
                if not value:
                    raise ValueError("target_class must be a non-empty string")
            elif name == "approach_distance_m":
                value = float(value)
                if value <= 0.0:
                    raise ValueError("approach_distance_m must be greater than zero")
            normalized[name] = value
        return normalized

    def _build_intent_payload(
        self,
        intent_name: str,
        args_payload: Dict[str, Any],
        *,
        planner: str = "dashboard_service",
        seq: Optional[int] = None,
        timestamp_utc: str = "",
    ) -> Dict[str, Any]:
        return {
            "intent": intent_name,
            "seq": int(seq or int(time.time() * 1000)),
            "planner": planner,
            "timestamp_utc": timestamp_utc or utc_now(),
            "args": json.loads(json.dumps(args_payload)),
        }

    def _resolve_intent_request(self, body: Dict[str, Any], route_intent: str = "") -> tuple[str, Dict[str, Any]]:
        if route_intent:
            intent_name = route_intent.strip()
            args_payload = body.get("args")
            if isinstance(args_payload, dict) and set(body.keys()).issubset({"intent", "args"}):
                raw_args = dict(args_payload)
            else:
                raw_args = {key: value for key, value in body.items() if key != "intent"}
            return intent_name, raw_args

        intent_name = str(body.get("intent", "")).strip()
        if not intent_name:
            raise ValueError("intent is required")
        args_payload = body.get("args", {})
        if not isinstance(args_payload, dict):
            raise ValueError("args must be an object")
        return intent_name, dict(args_payload)

    def _persist_state_locked(self) -> None:
        write_json(STATE_PATH, self.state)

    def _update_state(self, **updates: Any) -> None:
        with self.state_lock:
            self.state.update(updates)
            self._persist_state_locked()

    def _lifecycle_busy(self) -> bool:
        thread = self.lifecycle_thread
        if thread is not None and not thread.is_alive():
            self.lifecycle_thread = None
        return self.lifecycle_lock.locked()

    def _wait_for_lifecycle_idle(self, timeout_s: float) -> bool:
        deadline = time.monotonic() + max(timeout_s, 0.0)
        while self._lifecycle_busy() and time.monotonic() < deadline:
            time.sleep(0.05)
        return not self._lifecycle_busy()

    def _current_session_dir(self) -> Optional[Path]:
        session_id = self.state.get("session_id", "")
        if not session_id:
            return None
        return ensure_dir(SESSION_ROOT / session_id)

    def _current_visual_dir(self) -> Optional[Path]:
        session_dir = self._current_session_dir()
        if session_dir is None:
            return None
        return ensure_dir(session_dir / "visual")

    def _current_validation_dir(self) -> Optional[Path]:
        session_dir = self._current_session_dir()
        if session_dir is None:
            return None
        return ensure_dir(session_dir / "dashboard_validation")

    def _command_history_path(self) -> Optional[Path]:
        validation_dir = self._current_validation_dir()
        if validation_dir is None:
            return None
        return validation_dir / "command_history.jsonl"

    def _timeline_events_path(self) -> Optional[Path]:
        visual_dir = self._current_visual_dir()
        if visual_dir is None:
            return None
        return visual_dir / "timeline_events.jsonl"

    def _scenarios_dir(self) -> Optional[Path]:
        validation_dir = self._current_validation_dir()
        if validation_dir is None:
            return None
        return ensure_dir(validation_dir / "scenarios")

    def _multi_target_progress_path(self) -> Optional[Path]:
        validation_dir = self._current_validation_dir()
        if validation_dir is None:
            return None
        return validation_dir / "multi_target_progress.json"

    def _is_docker_socket_mode(self) -> bool:
        return self.control_mode == "docker_socket"

    def _docker_enabled(self) -> bool:
        return bool(self.docker)

    def _docker_inspect(self, reference: str) -> Dict[str, Any]:
        proc = subprocess.run(
            [self.docker, "inspect", reference],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or f"docker inspect failed for {reference}").strip())
        payload = json.loads(proc.stdout or "[]")
        if not payload:
            raise RuntimeError(f"docker inspect returned no payload for {reference}")
        if not isinstance(payload[0], dict):
            raise RuntimeError(f"Unexpected docker inspect payload for {reference}")
        return payload[0]

    def _docker_find_container_ids(self, *, project_name: str, service_name: str, include_stopped: bool = False) -> list[str]:
        cmd = [self.docker, "ps"]
        if include_stopped:
            cmd.append("-a")
        cmd.extend(
            [
                "-q",
                "--filter",
                f"label=com.docker.compose.project={project_name}",
                "--filter",
                f"label=com.docker.compose.service={service_name}",
            ]
        )
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return []
        return [line.strip() for line in proc.stdout.splitlines() if line.strip()]

    def _docker_project_container_ids(self, project_name: str, *, include_stopped: bool = False) -> list[str]:
        cmd = [self.docker, "ps"]
        if include_stopped:
            cmd.append("-a")
        cmd.extend(["-q", "--filter", f"label=com.docker.compose.project={project_name}"])
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return []
        return [line.strip() for line in proc.stdout.splitlines() if line.strip()]

    def _docker_service_container_id(self, project_name: str, service_name: str) -> str:
        ids = self._docker_find_container_ids(project_name=project_name, service_name=service_name)
        return ids[0] if ids else ""

    def _docker_version_check(self) -> str:
        proc = subprocess.run(
            [self.docker, "version", "--format", "{{.Server.Version}}"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "docker version failed").strip())
        return (proc.stdout or "").strip()

    def _force_remove_project_resources(self, project_name: str) -> None:
        if not project_name or not self._docker_enabled():
            return
        container_ids = self._docker_project_container_ids(project_name, include_stopped=True)
        if container_ids:
            subprocess.run(
                [self.docker, "rm", "-f", *container_ids],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
        network_proc = subprocess.run(
            [self.docker, "network", "ls", "-q", "--filter", f"label=com.docker.compose.project={project_name}"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        network_ids = [line.strip() for line in network_proc.stdout.splitlines() if line.strip()]
        if network_ids:
            subprocess.run(
                [self.docker, "network", "rm", *network_ids],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=False,
            )

    def _discover_launcher_context(self) -> tuple[str, str]:
        env_host_source = os.environ.get("HOST_REPO_MOUNT_SOURCE", "").strip()
        container_ref = os.environ.get("HOSTNAME", "").strip()
        if not container_ref:
            if env_host_source:
                return "", env_host_source
            raise RuntimeError("dashboard container hostname unavailable for self-inspection")
        inspect_payload = self._docker_inspect(container_ref)
        labels = inspect_payload.get("Config", {}).get("Labels", {}) or {}
        mounts = inspect_payload.get("Mounts", []) or []
        launcher_project = str(labels.get("com.docker.compose.project", "") or "").strip()
        host_source = env_host_source
        if not host_source:
            for mount in mounts:
                if str(mount.get("Destination", "")).strip() == "/workspaces/chasecar":
                    host_source = str(mount.get("Source", "") or "").strip()
                    if host_source:
                        break
        if not host_source:
            raise RuntimeError("dashboard container is missing the /workspaces/chasecar bind mount source")
        return launcher_project, host_source

    def _warm_service_states(self, launcher_project: str) -> Dict[str, Dict[str, Any]]:
        if not launcher_project:
            return {}
        states: Dict[str, Dict[str, Any]] = {}
        for service_name in self.warm_services:
            container_ids = self._docker_find_container_ids(project_name=launcher_project, service_name=service_name, include_stopped=True)
            if not container_ids:
                states[service_name] = {"container_id": "", "running": False, "status": "missing"}
                continue
            inspect_payload = self._docker_inspect(container_ids[0])
            state_info = inspect_payload.get("State", {}) or {}
            health_info = state_info.get("Health", {}) or {}
            running = bool(state_info.get("Running", False))
            status = str(health_info.get("Status") or state_info.get("Status") or "unknown")
            states[service_name] = {
                "container_id": container_ids[0],
                "running": running,
                "status": status,
            }
        return states

    def _summarize_warm_services(self, warm_states: Dict[str, Dict[str, Any]]) -> tuple[bool, str]:
        if not self._is_docker_socket_mode():
            return False, "n/a"
        if not warm_states:
            return False, "missing"
        ready = True
        parts: list[str] = []
        for service_name in self.warm_services:
            state = warm_states.get(service_name, {})
            status = str(state.get("status", "missing") or "missing")
            running = bool(state.get("running", False))
            healthy = running and status in {"running", "healthy"}
            ready = ready and healthy
            parts.append(f"{service_name}:{status}")
        return ready, ", ".join(parts)

    def _refresh_control_plane_state(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._control_plane_checked_at < 2.0:
            return
        self._control_plane_checked_at = now

        ready = False
        error = ""
        warm_services_ready = False
        warm_services_status = "unknown"
        warm_service_states: Dict[str, Dict[str, Any]] = {}
        launcher_project = self.launcher_project
        host_repo_mount_source = self.host_repo_mount_source

        try:
            if not self._docker_enabled():
                raise RuntimeError("docker CLI is unavailable")
            self._docker_version_check()
            if self._is_docker_socket_mode():
                if not DEFAULT_DOCKER_SOCKET_PATH.exists():
                    raise RuntimeError(f"docker socket is not mounted at {DEFAULT_DOCKER_SOCKET_PATH}")
                launcher_project, host_repo_mount_source = self._discover_launcher_context()
                warm_service_states = self._warm_service_states(launcher_project)
                warm_services_ready, warm_services_status = self._summarize_warm_services(warm_service_states)
                ready = bool(host_repo_mount_source)
                if not ready:
                    raise RuntimeError("dashboard could not resolve the host repo bind source")
            else:
                warm_services_status = "host_managed"
                ready = True
        except Exception as exc:
            error = str(exc)

        self.launcher_project = launcher_project
        self.host_repo_mount_source = host_repo_mount_source
        status_text = ""
        with self.state_lock:
            current_env_state = str(self.state.get("environment_state", "stopped"))
            current_status = str(self.state.get("status_text", "") or "")
        if not ready:
            status_text = error or "control plane unavailable"
        elif self._is_docker_socket_mode() and not warm_services_ready:
            status_text = warm_services_status
        elif current_env_state == "stopped":
            status_text = ""
        else:
            status_text = current_status
        self._update_state(
            control_mode=self.control_mode,
            control_plane_ready=ready,
            control_plane_error=error,
            warm_services_ready=warm_services_ready,
            warm_services_status=warm_services_status,
            warm_service_states=warm_service_states,
            launcher_project=launcher_project,
            host_repo_mount_source=host_repo_mount_source,
            status_text=status_text,
        )

    def _control_plane_unavailable_response(self) -> tuple[int, Dict[str, Any]]:
        self._refresh_control_plane_state(force=True)
        state = self.get_state()
        return HTTPStatus.SERVICE_UNAVAILABLE, {
            "accepted": False,
            "error": state.get("control_plane_error") or "control plane unavailable",
            "state": state,
        }

    def get_state(self) -> Dict[str, Any]:
        self._refresh_control_plane_state()
        with self.state_lock:
            snapshot = json.loads(json.dumps(self.state))

        visual_dir = self._current_visual_dir()
        visual_state = read_json(visual_dir / "state.json") if visual_dir else {}
        brain_state = read_json(visual_dir / "brain_state.json") if visual_dir else {}
        operator_state = read_json(visual_dir / "operator_status.json") if visual_dir else {}
        world_state = read_json(visual_dir / "world_stream_state.json") if visual_dir else {}
        truth_state = read_json(visual_dir / "truth_state.json") if visual_dir else {}
        progress_state = read_json(Path(snapshot["multi_target_progress_path"])) if snapshot.get("multi_target_progress_path") else {}

        if operator_state:
            snapshot["phase"] = operator_state.get("phase") or snapshot.get("phase")
            snapshot["target_id"] = operator_state.get("target_id") or snapshot.get("target_id")
            snapshot["target_transition_active"] = bool(
                operator_state.get("target_transition_active", snapshot.get("target_transition_active", False))
            )
            snapshot["status_text"] = operator_state.get("status_text", "")
        if progress_state and snapshot.get("active_scenario") == "multi_target_rehearsal":
            snapshot["target_id"] = progress_state.get("current_scenario_id") or snapshot.get("target_id")
            snapshot["target_transition_active"] = bool(
                progress_state.get("target_transition_active", snapshot.get("target_transition_active", False))
            )

        snapshot["raw_frame_count"] = int(visual_state.get("raw_frame_count", 0))
        snapshot["debug_frame_count"] = int(visual_state.get("debug_frame_count", 0))
        snapshot["telemetry_frame_count"] = int(visual_state.get("telemetry_frame_count", 0))
        snapshot["truth_alignment_ok"] = bool(visual_state.get("truth_alignment_ok", False))
        snapshot["truth_failure_class"] = visual_state.get("truth_failure_class", "")
        snapshot["true_target_seen"] = bool(visual_state.get("true_target_seen", False))
        snapshot["target_visible_ratio"] = float(visual_state.get("target_visible_ratio", 0.0) or 0.0)
        snapshot["overlay_difference_ok"] = bool(visual_state.get("overlay_difference_ok", False))
        snapshot["world_stream_ready"] = bool(world_state.get("world_stream_ready", False))
        snapshot["scene_content_ok"] = bool(world_state.get("scene_content_ok", False))
        snapshot["robot_visible_ok"] = bool(world_state.get("robot_visible_ok", False))
        snapshot["target_visible_ok"] = bool(world_state.get("target_visible_ok", False))
        snapshot["same_session_partition"] = bool(world_state.get("same_session_partition", False))
        snapshot["world_stream_failure_class"] = world_state.get("failure_class", "")
        snapshot["world_stream_url"] = world_state.get("world_stream_url", snapshot.get("world_stream_url", ""))
        snapshot["world_stream_interactive"] = bool(world_state.get("world_stream_interactive", False))
        snapshot["robot_truth_seen"] = bool(truth_state.get("robot_truth_seen", False))
        snapshot["live_paths"] = {
            "raw_camera": "live/raw_camera.jpg",
            "yolo_debug": "live/yolo_debug.jpg",
            "topdown_telemetry": "live/topdown_telemetry.jpg",
            "world_stream": "live/world_stream.jpg",
        }

        perception = {
            "detection_topic_seen": bool(visual_state.get("detection_topic_seen", False)),
            "target_visible_now": bool(visual_state.get("target_visible_now", False)),
            "target_visible_ratio": float(visual_state.get("target_visible_ratio", 0.0) or 0.0),
            "latest_detection_world": visual_state.get("latest_detection_world"),
            "latest_truth_target_world": visual_state.get("latest_truth_target_world"),
            "truth_alignment_ok": bool(visual_state.get("truth_alignment_ok", False)),
            "truth_status": "aligned" if visual_state.get("truth_alignment_ok", False) else (visual_state.get("truth_failure_class") or "truth unavailable"),
        }
        belief = {
            "latest_robot_pose": visual_state.get("latest_robot_pose"),
            "robot_pose_available": bool(visual_state.get("latest_robot_pose")),
            "latest_goal_pose": visual_state.get("latest_goal_pose"),
            "latest_target_distance_m": visual_state.get("latest_target_distance_m"),
            "distance_trend": visual_state.get("distance_trend", "unknown"),
            "distance_progress_m": visual_state.get("distance_progress_m"),
            "capability_stage": visual_state.get("capability_stage", ""),
            "phase": snapshot.get("phase", ""),
            "target_id": snapshot.get("target_id", ""),
            "target_transition_active": bool(snapshot.get("target_transition_active", False)),
        }
        brain = {
            "search_active": bool(brain_state.get("search_active", False)),
            "search_state": str(brain_state.get("search_state", "idle") or "idle"),
            "search_rotation_accum_rad": float(brain_state.get("search_rotation_accum_rad", 0.0) or 0.0),
            "target_visible_recent": bool(brain_state.get("target_visible_recent", False)),
            "target_locked": bool(brain_state.get("target_locked", False)),
            "target_locked_class": str(brain_state.get("target_locked_class", "") or ""),
            "track_active": bool(brain_state.get("track_active", False)),
            "goal_in_progress": bool(brain_state.get("goal_in_progress", False)),
            "last_feedback_text": str(brain_state.get("last_feedback_text", "") or ""),
            "last_goal_dispatched_utc": str(brain_state.get("last_goal_dispatched_utc", "") or ""),
        }
        decision = {
            "available_intents": sorted(self.frozen_intents.keys()),
            "last_intent": snapshot.get("last_intent", ""),
            "last_intent_payload": snapshot.get("last_intent_payload", {}),
            "last_intent_timestamp_utc": snapshot.get("last_intent_timestamp_utc", ""),
            "last_preview_payload": snapshot.get("last_preview_payload", {}),
            "last_preview_valid": bool(snapshot.get("last_preview_valid", False)),
            "last_preview_error": snapshot.get("last_preview_error", ""),
            "last_preview_timestamp_utc": snapshot.get("last_preview_timestamp_utc", ""),
            "last_preview_readiness": snapshot.get("last_preview_readiness", {}),
            "last_preview_expected_activity": snapshot.get("last_preview_expected_activity", []),
        }
        outcome = {
            "last_feedback": snapshot.get("last_feedback", "") or visual_state.get("last_feedback_text", ""),
            "last_result": snapshot.get("last_result", ""),
            "feedback_recent": bool(visual_state.get("feedback_recent", False)),
            "nav_goal_recent": bool(visual_state.get("nav_goal_recent", False)),
            "cmd_vel_recent": bool(visual_state.get("cmd_vel_recent", False)),
            "boundary_activity_seen": bool(visual_state.get("boundary_activity_seen", False)),
            "motion_evidence": bool(snapshot.get("motion_evidence", False)),
        }
        active_scenario = snapshot.get("active_scenario", "")
        capability_stage = "WAIT"
        demo_label = "Warm Dashboard"
        demo_expectation = "Use Start to bring the authoritative session up, then run a capability demo."
        recommended_scenario_id = ""
        if active_scenario == "multi_target_rehearsal" or snapshot.get("phase") == "multi_target_rehearsal":
            capability_stage = "MULTI-STEP"
            demo_label = "Multi-Step"
            demo_expectation = "Watch the target sequence advance and the transition badge flip active at handoff."
            recommended_scenario_id = "multi_target_rehearsal"
        elif snapshot.get("last_intent") in {"abort", "safe_stop"} and snapshot.get("last_intent_timestamp_utc"):
            capability_stage = "INTERRUPT"
            demo_label = "Interrupt"
            demo_expectation = "Use abort or safe_stop during active motion and watch feedback plus motion drop-off."
            recommended_scenario_id = "m3_single_target"
        elif active_scenario.startswith("m3_") or active_scenario == "m3_single_target":
            capability_stage = "ACT" if outcome["cmd_vel_recent"] else "PLAN"
            demo_label = "Plan + Act"
            demo_expectation = "Watch the waypoint appear, then confirm the distance trend shrinks as motion continues."
            recommended_scenario_id = active_scenario or "m3_single_target"
        elif active_scenario == "m2_single_target":
            capability_stage = "SEE"
            demo_label = "See"
            demo_expectation = "Use the raw, debug, and topdown panes to compare detections against truth."
            recommended_scenario_id = "m2_single_target"
        elif snapshot.get("last_intent") == "track_target":
            capability_stage = "TRACK"
            demo_label = "Track"
            demo_expectation = "Watch continued boundary activity while the target remains visible and motion stays live."
        elif perception["detection_topic_seen"]:
            capability_stage = "SEE"
            demo_label = "See"
            demo_expectation = "Perception is live; the target cues should line up across the panes and the workbench."

        if capability_stage == "WAIT" and belief.get("capability_stage"):
            capability_stage = belief["capability_stage"]
        demo_story = {
            "capability_stage": capability_stage,
            "demo_label": demo_label,
            "demo_expectation": demo_expectation,
            "recommended_scenario_id": recommended_scenario_id,
        }

        snapshot["perception"] = perception
        snapshot["belief"] = belief
        snapshot["brain"] = brain
        snapshot["decision"] = decision
        snapshot["outcome"] = outcome
        snapshot["demo_story"] = demo_story
        snapshot["llm_supervisor"] = self._llm_supervisor_state()

        controls_enabled = bool(snapshot.get("control_plane_ready", False))
        snapshot["controls"] = {
            "can_start": controls_enabled and snapshot["environment_state"] in {"stopped", "error"},
            "can_stop": controls_enabled and snapshot["environment_state"] in {"starting", "environment_ready", "error"},
            "can_refresh": controls_enabled and snapshot["environment_state"] in {"environment_ready", "stopped", "error"},
            "can_reset_sim": controls_enabled and snapshot["environment_state"] == "environment_ready",
            "can_run_scenario": controls_enabled and snapshot["environment_state"] == "environment_ready" and snapshot["scenario_state"] != "running",
            "can_stop_scenario": controls_enabled and snapshot["scenario_state"] == "running",
            "can_issue_intent": controls_enabled and snapshot["environment_state"] == "environment_ready",
            "can_preview_intent": True,
            "can_dispatch_intent": controls_enabled and snapshot["environment_state"] == "environment_ready",
        }
        snapshot["available_intents"] = sorted(self.frozen_intents.keys())
        return snapshot

    def _llm_supervisor_state(self) -> Dict[str, Any]:
        runtime = load_shadow_runtime_state()
        history_path_raw = str(runtime.get("history_path", "") or "").strip()
        history_path = Path(history_path_raw) if history_path_raw else None
        recent_history = runtime.get("recent_history", [])
        if not isinstance(recent_history, list):
            recent_history = []
        if history_path and history_path.exists():
            recent_history = read_jsonl_lines(history_path, limit=5)
        return {
            "mode": str(runtime.get("mode", "shadow") or "shadow"),
            "provider": str(runtime.get("provider", "") or ""),
            "model": str(runtime.get("model", "") or ""),
            "running": bool(runtime.get("running", False)),
            "status": str(runtime.get("status", "disabled") or "disabled"),
            "latest_decision": runtime.get("latest_decision", {}) if isinstance(runtime.get("latest_decision"), dict) else {},
            "last_evaluated_utc": str(runtime.get("last_evaluated_utc", "") or ""),
            "last_polled_utc": str(runtime.get("last_polled_utc", "") or ""),
            "history_path": history_path_raw,
            "latest_path": str(runtime.get("latest_path", "") or ""),
            "state_hash": str(runtime.get("state_hash", "") or ""),
            "preview": runtime.get("preview", {}) if isinstance(runtime.get("preview"), dict) else {},
            "suppression_reason": str(runtime.get("suppression_reason", "") or ""),
            "recent_history": recent_history,
        }

    def list_llm_supervisor_history(self, limit: int) -> Dict[str, Any]:
        supervisor = self._llm_supervisor_state()
        history_path_raw = str(supervisor.get("history_path", "") or "").strip()
        history_path = Path(history_path_raw) if history_path_raw else None
        bounded_limit = max(1, min(limit, 100))
        history = read_jsonl_lines(history_path, limit=bounded_limit) if history_path and history_path.exists() else []
        return {"history": history, "latest": supervisor}

    def list_scenarios(self) -> Dict[str, Any]:
        return {"scenarios": [item.to_api() for item in SCENARIOS]}

    def read_live_file(self, name: str) -> Optional[Path]:
        visual_dir = self._current_visual_dir()
        if visual_dir is None:
            return None
        path = (visual_dir / name).resolve()
        if not str(path).startswith(str(visual_dir.resolve())):
            return None
        if not path.exists() or not path.is_file():
            return None
        return path

    def request_start(self) -> tuple[int, Dict[str, Any]]:
        with self.state_lock:
            env_state = self.state["environment_state"]
        if env_state == "environment_ready":
            return HTTPStatus.OK, {"accepted": False, "message": "environment already ready", "state": self.get_state()}
        if env_state == "starting":
            return HTTPStatus.OK, {"accepted": False, "message": "environment start already in progress", "state": self.get_state()}
        self._refresh_control_plane_state(force=True)
        with self.state_lock:
            if not self.state.get("control_plane_ready", False):
                return self._control_plane_unavailable_response()
        if self._lifecycle_busy():
            if env_state == "stopped" and self._wait_for_lifecycle_idle(2.0):
                pass
            else:
                return HTTPStatus.CONFLICT, {"accepted": False, "error": "lifecycle busy"}
        self.lifecycle_cancel.clear()
        self._update_state(
            environment_state="starting",
            scenario_state="idle",
            environment_message="environment start queued",
            scenario_message="",
            last_error="",
            phase="starting",
            target_id="",
            target_transition_active=False,
        )
        self.lifecycle_thread = threading.Thread(target=self._start_environment_worker, name="dashboard-start", daemon=True)
        self.lifecycle_thread.start()
        return HTTPStatus.ACCEPTED, {"accepted": True, "message": "environment start queued"}

    def request_stop(self) -> tuple[int, Dict[str, Any]]:
        with self.state_lock:
            env_state = self.state["environment_state"]
        if env_state == "stopped":
            return HTTPStatus.OK, {"accepted": False, "message": "environment already stopped", "state": self.get_state()}
        if env_state == "starting":
            self.lifecycle_cancel.set()
            self._terminate_process(self.active_env_proc)
            self._update_state(environment_message="stop requested during startup")
            return HTTPStatus.ACCEPTED, {"accepted": True, "message": "startup cancellation requested"}
        self._refresh_control_plane_state(force=True)
        with self.state_lock:
            if not self.state.get("control_plane_ready", False):
                return self._control_plane_unavailable_response()
        if self._lifecycle_busy():
            return HTTPStatus.CONFLICT, {"accepted": False, "error": "lifecycle busy"}
        self.lifecycle_thread = threading.Thread(target=self._stop_environment_worker, name="dashboard-stop", daemon=True)
        self.lifecycle_thread.start()
        return HTTPStatus.ACCEPTED, {"accepted": True, "message": "environment stop queued"}

    def request_refresh(self) -> tuple[int, Dict[str, Any]]:
        self._refresh_control_plane_state(force=True)
        with self.state_lock:
            if not self.state.get("control_plane_ready", False):
                return self._control_plane_unavailable_response()
        if self._lifecycle_busy():
            return HTTPStatus.CONFLICT, {"accepted": False, "error": "lifecycle busy"}
        self.lifecycle_thread = threading.Thread(target=self._refresh_environment_worker, name="dashboard-refresh", daemon=True)
        self.lifecycle_thread.start()
        return HTTPStatus.ACCEPTED, {"accepted": True, "message": "environment refresh queued"}

    def request_reset_sim(self) -> tuple[int, Dict[str, Any]]:
        with self.state_lock:
            env_state = self.state["environment_state"]
        if env_state not in {"environment_ready", "error"}:
            return HTTPStatus.CONFLICT, {"accepted": False, "error": "environment not ready for reset"}
        self._refresh_control_plane_state(force=True)
        with self.state_lock:
            if not self.state.get("control_plane_ready", False):
                return self._control_plane_unavailable_response()
        if self._lifecycle_busy():
            return HTTPStatus.CONFLICT, {"accepted": False, "error": "lifecycle busy"}
        self.lifecycle_thread = threading.Thread(target=self._reset_environment_worker, name="dashboard-reset", daemon=True)
        self.lifecycle_thread.start()
        return HTTPStatus.ACCEPTED, {"accepted": True, "message": "sim reset queued"}

    def request_scenario_run(self, scenario_id: str) -> tuple[int, Dict[str, Any]]:
        scenario = SCENARIOS_BY_ID.get(scenario_id)
        if scenario is None:
            return HTTPStatus.BAD_REQUEST, {"accepted": False, "error": f"unknown scenario: {scenario_id}"}
        with self.state_lock:
            env_state = self.state["environment_state"]
            scenario_state = self.state["scenario_state"]
        if env_state != "environment_ready":
            return HTTPStatus.CONFLICT, {"accepted": False, "error": "environment not ready"}
        self._refresh_control_plane_state(force=True)
        with self.state_lock:
            if not self.state.get("control_plane_ready", False):
                return self._control_plane_unavailable_response()
        if scenario_state == "running" or (self.scenario_thread and self.scenario_thread.is_alive()):
            return HTTPStatus.CONFLICT, {"accepted": False, "error": "scenario already running"}
        self.scenario_cancel.clear()
        self.scenario_thread = threading.Thread(
            target=self._scenario_worker,
            args=(scenario,),
            name=f"dashboard-scenario-{scenario_id}",
            daemon=True,
        )
        self.scenario_thread.start()
        return HTTPStatus.ACCEPTED, {"accepted": True, "message": f"scenario {scenario_id} queued"}

    def request_scenario_stop(self) -> tuple[int, Dict[str, Any]]:
        if not (self.scenario_thread and self.scenario_thread.is_alive()):
            return HTTPStatus.OK, {"accepted": False, "message": "no active scenario", "state": self.get_state()}
        self._refresh_control_plane_state(force=True)
        with self.state_lock:
            if not self.state.get("control_plane_ready", False):
                return self._control_plane_unavailable_response()
        self.scenario_cancel.set()
        self._terminate_process(self.active_scenario_proc)
        self._update_state(scenario_message="scenario stop requested")
        return HTTPStatus.ACCEPTED, {"accepted": True, "message": "scenario stop requested"}

    def request_intent_preview(self, body: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
        try:
            intent_name, args_payload = self._resolve_intent_request(body)
            preview = self._prepare_intent_preview(intent_name, args_payload)
        except KeyError:
            error = f"unknown frozen intent: {body.get('intent', '')}"
            self._remember_preview({}, error=error, valid=False)
            return HTTPStatus.NOT_FOUND, {"accepted": False, "error": error}
        except Exception as exc:
            self._remember_preview({}, error=str(exc), valid=False)
            return HTTPStatus.BAD_REQUEST, {"accepted": False, "error": str(exc)}

        self._remember_preview(preview, record_history=True)
        return HTTPStatus.OK, {"accepted": True, "preview": preview}

    def request_intent_dispatch(self, body: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
        try:
            intent_name, args_payload = self._resolve_intent_request(body)
        except Exception as exc:
            return HTTPStatus.BAD_REQUEST, {"accepted": False, "error": str(exc)}
        return self.request_intent(intent_name, args_payload)

    def request_intent(self, intent_name: str, args_payload: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
        if intent_name not in self.frozen_intents:
            return HTTPStatus.NOT_FOUND, {"accepted": False, "error": f"unknown frozen intent: {intent_name}"}
        try:
            preview = self._prepare_intent_preview(intent_name, args_payload)
        except Exception as exc:
            return HTTPStatus.BAD_REQUEST, {"accepted": False, "error": str(exc)}
        with self.state_lock:
            env_state = self.state["environment_state"]
        if env_state != "environment_ready":
            return HTTPStatus.CONFLICT, {"accepted": False, "error": "environment not ready"}
        self._refresh_control_plane_state(force=True)
        with self.state_lock:
            if not self.state.get("control_plane_ready", False):
                return self._control_plane_unavailable_response()
        if self.intent_thread and self.intent_thread.is_alive():
            return HTTPStatus.CONFLICT, {"accepted": False, "error": "intent already in progress"}
        self.intent_thread = threading.Thread(
            target=self._intent_worker,
            args=(preview,),
            name=f"dashboard-intent-{intent_name}",
            daemon=True,
        )
        self.intent_thread.start()
        return HTTPStatus.ACCEPTED, {"accepted": True, "message": f"intent {intent_name} queued", "preview": preview}

    def _write_lock_file(self) -> None:
        payload = {
            "session_id": self.state.get("session_id", ""),
            "compose_project": self.state.get("compose_project", ""),
            "owner_pid": os.getpid(),
            "updated_utc": utc_now(),
        }
        write_json(LOCK_PATH, payload)

    def _remove_lock_file(self) -> None:
        try:
            LOCK_PATH.unlink()
        except FileNotFoundError:
            pass

    def _write_operator_status(
        self,
        *,
        phase: str,
        target_id: str,
        target_transition_active: bool,
        status_text: str,
    ) -> None:
        visual_dir = self._current_visual_dir()
        if visual_dir is None:
            return
        payload = {
            "session_id": self.state.get("session_id", ""),
            "phase": phase,
            "target_id": target_id,
            "target_transition_active": bool(target_transition_active),
            "execution_lane": "container_kilted",
            "runtime_target": self.state.get("runtime_target", DEFAULT_RUNTIME_TARGET),
            "visual_surface": "browser_dashboard",
            "world_surface": "streamed_sim",
            "status_text": status_text,
            "updated_utc": utc_now(),
        }
        status_path = visual_dir / "operator_status.json"
        write_json(status_path, payload)
        self._update_state(
            operator_status_path=str(status_path),
            phase=phase,
            target_id=target_id,
            target_transition_active=bool(target_transition_active),
        )

    def _record_command_history(self, entry: Dict[str, Any]) -> None:
        path = self._command_history_path()
        if path is None:
            return
        ensure_dir(path.parent)
        with path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(entry, sort_keys=True) + "\n")
        self._update_state(command_history_path=str(path))

    def _record_visual_event(self, entry: Dict[str, Any]) -> None:
        path = self._timeline_events_path()
        if path is None:
            return
        payload = dict(entry)
        payload.setdefault("timestamp_utc", utc_now())
        ensure_dir(path.parent)
        with path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, sort_keys=True) + "\n")

    def _preview_matches_cached(self, intent_name: str, args_payload: Dict[str, Any]) -> bool:
        with self.state_lock:
            valid = bool(self.state.get("last_preview_valid", False))
            payload = self.state.get("last_preview_payload", {})
            preview_session_id = str(self.state.get("last_preview_session_id", ""))
            current_session_id = str(self.state.get("session_id", ""))
        if not valid or not isinstance(payload, dict):
            return False
        if not current_session_id or preview_session_id != current_session_id:
            return False
        return payload.get("intent") == intent_name and payload.get("args") == args_payload

    def _intent_expected_activity(self, intent_name: str) -> list[str]:
        if intent_name == "search_for_target":
            return ["turn-in-place cmd_vel activity", "feedback on /chasecar/brain/feedback"]
        if intent_name == "acquire_target":
            return ["feedback on /chasecar/brain/feedback", "fresh detection/odom boundary activity"]
        if intent_name == "plan_to_target":
            return ["nav goal activity on /chasecar/nav_goal_pose", "feedback on /chasecar/brain/feedback"]
        if intent_name == "track_target":
            return ["continued cmd_vel activity", "feedback on /chasecar/brain/feedback"]
        if intent_name == "abort":
            return ["cancel feedback", "behavior activity should stop"]
        if intent_name == "safe_stop":
            return ["stop feedback", "immediate low-level stop semantics"]
        return []

    def _intent_readiness_snapshot(self, intent_name: str, state: Dict[str, Any]) -> Dict[str, Any]:
        perception = state.get("perception", {}) if isinstance(state.get("perception"), dict) else {}
        belief = state.get("belief", {}) if isinstance(state.get("belief"), dict) else {}
        brain = state.get("brain", {}) if isinstance(state.get("brain"), dict) else {}
        outcome = state.get("outcome", {}) if isinstance(state.get("outcome"), dict) else {}

        readiness = {
            "control_plane_ready": bool(state.get("control_plane_ready", False)),
            "environment_ready": state.get("environment_state") == "environment_ready",
            "session_active": bool(state.get("session_id")),
            "sim_gate_ready": bool(self.sim_gate_container_id),
            "detection_seen": bool(perception.get("detection_topic_seen", False)),
            "target_visible_now": bool(perception.get("target_visible_now", False)),
            "robot_pose_available": bool(belief.get("robot_pose_available", False)),
            "target_locked": bool(brain.get("target_locked", False)),
            "nav_goal_recent": bool(outcome.get("nav_goal_recent", False)),
            "feedback_recent": bool(outcome.get("feedback_recent", False)),
            "cmd_vel_recent": bool(outcome.get("cmd_vel_recent", False)),
        }

        required_keys = ["control_plane_ready", "environment_ready", "session_active", "sim_gate_ready"]
        if intent_name == "search_for_target":
            required_keys.append("robot_pose_available")
        elif intent_name in {"acquire_target", "plan_to_target", "track_target"}:
            required_keys.extend(["detection_seen", "robot_pose_available"])
        missing = [name for name in required_keys if not readiness.get(name, False)]
        readiness["required_keys"] = required_keys
        readiness["missing_keys"] = missing
        readiness["ready_to_dispatch"] = not missing
        return readiness

    def _prepare_intent_preview(self, intent_name: str, args_payload: Dict[str, Any]) -> Dict[str, Any]:
        if intent_name not in self.frozen_intents:
            raise KeyError(intent_name)
        normalized_args = self._normalize_intent_args(intent_name, args_payload)
        payload = (
            json.loads(json.dumps(self.state.get("last_preview_payload", {})))
            if self._preview_matches_cached(intent_name, normalized_args)
            else self._build_intent_payload(intent_name, normalized_args)
        )
        state = self.get_state()
        readiness = self._intent_readiness_snapshot(intent_name, state)
        spec = self.frozen_intents[intent_name]
        transport = self._intent_transport()
        return {
            "generated_utc": utc_now(),
            "intent": intent_name,
            "description": str(spec.get("description", "")),
            "required_args": self._intent_required_args(intent_name),
            "args": normalized_args,
            "payload": payload,
            "command_topic": str(transport.get("command_topic", "/chasecar/brain/intent")),
            "feedback_topic": str(transport.get("feedback_topic", "/chasecar/brain/feedback")),
            "contract_status": str(self.contract.get("contract_status", "")),
            "contract_valid": True,
            "readiness": readiness,
            "ready_to_dispatch": bool(readiness.get("ready_to_dispatch", False)),
            "expected_boundary_activity": self._intent_expected_activity(intent_name),
        }

    def _remember_preview(self, preview: Dict[str, Any], *, error: str = "", valid: bool = True, record_history: bool = False) -> None:
        preview_payload = json.loads(json.dumps(preview.get("payload", {}))) if valid else {}
        readiness = json.loads(json.dumps(preview.get("readiness", {}))) if valid else {}
        expected_activity = list(preview.get("expected_boundary_activity", [])) if valid else []
        timestamp_utc = str(preview.get("generated_utc", utc_now()))
        self._update_state(
            last_preview_payload=preview_payload,
            last_preview_valid=bool(valid),
            last_preview_error=error,
            last_preview_timestamp_utc=timestamp_utc,
            last_preview_session_id=str(self.state.get("session_id", "")),
            last_preview_readiness=readiness,
            last_preview_expected_activity=expected_activity,
        )
        if not valid:
            return
        if record_history:
            history_entry = {
                "event_type": "preview",
                "timestamp_utc": timestamp_utc,
                "intent": preview.get("intent", ""),
                "args": preview.get("args", {}),
                "payload": preview_payload,
                "readiness": readiness,
                "ready_to_dispatch": bool(preview.get("ready_to_dispatch", False)),
                "expected_boundary_activity": expected_activity,
            }
            self._record_command_history(history_entry)
            self._record_visual_event(
                {
                    "event_type": "preview_created",
                    "intent": preview.get("intent", ""),
                    "payload": preview_payload,
                    "ready_to_dispatch": bool(preview.get("ready_to_dispatch", False)),
                }
            )

    def _powershell_command(self, script_name: str, *args: str) -> list[str]:
        return [POWERSHELL_EXE, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPTS_DIR / script_name), *args]

    def _run_powershell(self, script_name: str, *args: str, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess[str]:
        cmd = self._powershell_command(script_name, *args)
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        return proc

    def _popen_powershell(self, script_name: str, *args: str, env: Optional[Dict[str, str]] = None) -> subprocess.Popen[str]:
        cmd = self._powershell_command(script_name, *args)
        proc = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        return proc

    def _compose_env(self, base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        env = dict(base_env or os.environ.copy())
        env.setdefault("RUNTIME_TARGET", DEFAULT_RUNTIME_TARGET)
        env.setdefault("SIM_LANE", DEFAULT_SIM_LANE)
        env.setdefault("INFERENCE_BACKEND", DEFAULT_INFERENCE_BACKEND)
        env.setdefault("CORE_ROS_DISTRO", DEFAULT_CORE_ROS_DISTRO)
        env.setdefault("BRIDGE_ROS_DISTRO", DEFAULT_BRIDGE_ROS_DISTRO)
        env.setdefault("WORLD_FILE", DEFAULT_WORLD_FILE)
        env.setdefault("GATE_HEADLESS", "true")
        env.setdefault("GATE_DISPLAY_MODE", "none")
        env.setdefault("GATE_INCLUDE_NAV2_BRINGUP", "true")
        env.setdefault("GATE_INCLUDE_BRIDGE", "false")
        env.setdefault("GATE_INCLUDE_CMD_VEL_RELAY", "true")
        env.setdefault("GATE_INCLUDE_BRAIN_EXECUTOR", "true")
        env.setdefault("GATE_PERF_PROFILE", DEFAULT_GATE_PROFILE)
        env.setdefault("GATE_INFERENCE_DEVICE", DEFAULT_INFERENCE_DEVICE)
        if self.host_repo_mount_source:
            env["HOST_REPO_MOUNT_SOURCE"] = self.host_repo_mount_source
        return env

    def _docker_compose_command(self, project_name: str, *args: str) -> list[str]:
        return [self.docker, "compose", "-f", str(self.compose_file), "-p", project_name, *args]

    def _run_docker_compose(
        self,
        project_name: str,
        *args: str,
        env: Optional[Dict[str, str]] = None,
    ) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(
            self._docker_compose_command(project_name, *args),
            cwd=str(REPO_ROOT),
            env=self._compose_env(env),
            capture_output=True,
            text=True,
            check=False,
        )
        return proc

    def _popen_docker_compose(
        self,
        project_name: str,
        *args: str,
        env: Optional[Dict[str, str]] = None,
    ) -> subprocess.Popen[str]:
        return subprocess.Popen(
            self._docker_compose_command(project_name, *args),
            cwd=str(REPO_ROOT),
            env=self._compose_env(env),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def _docker_exec(self, container_id: str, script: str) -> subprocess.CompletedProcess[str]:
        normalized_script = script.replace("\r\n", "\n").encode("utf-8")
        proc = subprocess.run(
            [
                self.docker,
                "exec",
                "-i",
                container_id,
                "bash",
                "-lc",
                "cat >/tmp/chasecar_dashboard_cmd.sh && chmod +x /tmp/chasecar_dashboard_cmd.sh && /tmp/chasecar_dashboard_cmd.sh",
            ],
            cwd=str(REPO_ROOT),
            input=normalized_script,
            capture_output=True,
            check=False,
        )
        return subprocess.CompletedProcess(
            args=proc.args,
            returncode=proc.returncode,
            stdout=(proc.stdout or b"").decode("utf-8", errors="replace"),
            stderr=(proc.stderr or b"").decode("utf-8", errors="replace"),
        )

    def _docker_exec_popen(self, container_id: str, script: str, log_path: Path) -> subprocess.Popen[str]:
        normalized_script = script.replace("\r\n", "\n").encode("utf-8")
        ensure_dir(log_path.parent)
        log_file = log_path.open("wb")
        proc = subprocess.Popen(
            [
                self.docker,
                "exec",
                "-i",
                container_id,
                "bash",
                "-lc",
                "cat >/tmp/chasecar_dashboard_cmd.sh && chmod +x /tmp/chasecar_dashboard_cmd.sh && /tmp/chasecar_dashboard_cmd.sh",
            ],
            cwd=str(REPO_ROOT),
            stdin=subprocess.PIPE,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        assert proc.stdin is not None
        proc.stdin.write(normalized_script)
        proc.stdin.close()
        return proc

    def _terminate_process(self, proc: Optional[subprocess.Popen[str]]) -> None:
        if proc is None or proc.poll() is not None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _run_container_helper(self, container_id: str, script: str, prefix: str) -> Dict[str, Any]:
        proc = self._docker_exec(container_id, script)
        output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        return {
            "exit_code": proc.returncode,
            "output": output,
            "pid": parse_marker(output, f"{prefix}_PID="),
            "log": parse_marker(output, f"{prefix}_LOG="),
        }

    def _wait_for_visual_ready(self, timeout_s: float) -> bool:
        visual_dir = self._current_visual_dir()
        if visual_dir is None:
            return False
        deadline = time.monotonic() + max(timeout_s, 1.0)
        while time.monotonic() < deadline:
            state = read_json(visual_dir / "state.json")
            if int(state.get("raw_frame_count", 0)) >= 1 and int(state.get("debug_frame_count", 0)) >= 1:
                return True
            if self.lifecycle_cancel.is_set():
                return False
            time.sleep(0.5)
        return False

    def _wait_for_truth_ready(self, timeout_s: float) -> bool:
        visual_dir = self._current_visual_dir()
        if visual_dir is None:
            return False
        deadline = time.monotonic() + max(timeout_s, 1.0)
        while time.monotonic() < deadline:
            state = read_json(visual_dir / "truth_state.json")
            if state and bool(state.get("robot_truth_seen", False)):
                return True
            if self.lifecycle_cancel.is_set():
                return False
            time.sleep(0.5)
        return False

    def _wait_for_world_stream_ready(self, timeout_s: float) -> bool:
        visual_dir = self._current_visual_dir()
        if visual_dir is None:
            return False
        deadline = time.monotonic() + max(timeout_s, 1.0)
        while time.monotonic() < deadline:
            state = read_json(visual_dir / "world_stream_state.json")
            if (
                state
                and bool(state.get("world_stream_ready", False))
                and bool(state.get("scene_content_ok", False))
                and bool(state.get("robot_visible_ok", False))
                and bool(state.get("same_session_partition", False))
            ):
                return True
            if self.lifecycle_cancel.is_set():
                return False
            time.sleep(0.5)
        return False

    def _base_env(self, *, session_id: str, world_stream_port: int) -> Dict[str, str]:
        env = self._compose_env()
        env["GAZEBO_PARTITION"] = session_id
        env["WORLD_STREAM_PORT"] = str(world_stream_port)
        env["CHASECAR_SESSION_ID"] = session_id
        env["CHASECAR_BRAIN_STATE_PATH"] = to_container_repo_path(SESSION_ROOT / session_id / "visual" / "brain_state.json")
        env["CHASECAR_BRAIN_FEEDBACK_PATH"] = to_container_repo_path(SESSION_ROOT / session_id / "visual" / "brain_feedback.jsonl")
        return env

    def _refresh_session_container_ids(self, project_name: str) -> None:
        self.sim_gate_container_id = self._docker_service_container_id(project_name, "sim-gate")
        self.gate_stack_container_id = self._docker_service_container_id(project_name, "gate-stack")
        self.world_viewer_container_id = self._docker_service_container_id(project_name, "world-viewer")

    def _resolve_artifact_dir(self, artifact_dir: str) -> str:
        if not artifact_dir:
            return ""
        normalized = artifact_dir.strip()
        if normalized.startswith("/workspaces/chasecar/"):
            local_path = REPO_ROOT / normalized[len("/workspaces/chasecar/") :]
        else:
            local_path = Path(normalized)
            if not local_path.is_absolute():
                local_path = (REPO_ROOT / local_path).resolve()
        return str(local_path)

    def _start_environment_worker(self) -> None:
        if not self.lifecycle_lock.acquire(blocking=False):
            return
        try:
            session_id = make_session_id()
            project_name = f"chasecar_dashboard_{slugify_session(session_id)}"
            validation_dir = ensure_dir(SESSION_ROOT / session_id / "dashboard_validation")
            ensure_dir(SESSION_ROOT / session_id / "visual")
            world_stream_port = find_free_port(8891, 8921)
            env = self._base_env(session_id=session_id, world_stream_port=world_stream_port)
            self._update_state(
                environment_state="starting",
                scenario_state="idle",
                session_id=session_id,
                compose_project=project_name,
                environment_message="starting authoritative environment",
                scenario_message="",
                last_error="",
                world_stream_port=world_stream_port,
                validation_dir=str(validation_dir),
                command_history_path=str(validation_dir / "command_history.jsonl"),
                multi_target_progress_path=str(validation_dir / "multi_target_progress.json"),
                active_scenario="",
                phase="starting",
                target_id="",
                target_transition_active=False,
                latest_artifacts={},
                motion_evidence=False,
            )
            self._write_operator_status(
                phase="environment_starting",
                target_id="",
                target_transition_active=False,
                status_text="Starting authoritative environment",
            )
            if self.lifecycle_cancel.is_set():
                self._update_state(
                    environment_state="stopped",
                    scenario_state="idle",
                    environment_message="startup cancelled",
                )
                self._remove_lock_file()
                return

            if self._is_docker_socket_mode():
                self._run_docker_compose(project_name, "down", "--remove-orphans", env=env)
                args = ["up", "-d"]
                if self.build_on_next_start:
                    args.append("--build")
                args.extend(["sim-gate", "world-viewer", "gate-stack"])
                proc = self._popen_docker_compose(project_name, *args, env=env)
            else:
                self._run_powershell(
                    "run_compose_gate.ps1",
                    "-Action",
                    "down",
                    "-ProjectName",
                    project_name,
                    "-RuntimeTarget",
                    DEFAULT_RUNTIME_TARGET,
                    "-InferenceBackend",
                    DEFAULT_INFERENCE_BACKEND,
                    "-CoreRosDistro",
                    DEFAULT_CORE_ROS_DISTRO,
                    env=env,
                )
                self._run_powershell(
                    "run_compose_uat.ps1",
                    "-Action",
                    "down",
                    "-ProjectName",
                    project_name,
                    "-RuntimeTarget",
                    DEFAULT_RUNTIME_TARGET,
                    "-InferenceBackend",
                    DEFAULT_INFERENCE_BACKEND,
                    "-CoreRosDistro",
                    DEFAULT_CORE_ROS_DISTRO,
                    env=env,
                )

                args = [
                    "-Action",
                    "up",
                    "-ProjectName",
                    project_name,
                    "-RuntimeTarget",
                    DEFAULT_RUNTIME_TARGET,
                    "-InferenceBackend",
                    DEFAULT_INFERENCE_BACKEND,
                    "-CoreRosDistro",
                    DEFAULT_CORE_ROS_DISTRO,
                    "-GatePerfProfile",
                    DEFAULT_GATE_PROFILE,
                    "-InferenceDevice",
                    DEFAULT_INFERENCE_DEVICE,
                    "-WorldFile",
                    DEFAULT_WORLD_FILE,
                    "-IncludeNav2Bringup",
                    "true",
                    "-IncludeBridge",
                    "false",
                    "-IncludeCmdVelRelay",
                    "true",
                    "-Headless",
                    "true",
                    "-DisplayMode",
                    "none",
                ]
                if self.build_on_next_start:
                    args.append("-Build")
                proc = self._popen_powershell("run_compose_gate.ps1", *args, env=env)
            self.active_env_proc = proc
            output, _ = proc.communicate()
            self.active_env_proc = None
            if self.lifecycle_cancel.is_set():
                self._teardown_environment(env=env)
                self._update_state(
                    environment_state="stopped",
                    scenario_state="idle",
                    environment_message="startup cancelled",
                )
                self._remove_lock_file()
                return
            if proc.returncode != 0:
                raise RuntimeError(output.strip() or "gate bring-up failed")

            self._refresh_session_container_ids(project_name)
            if not self.sim_gate_container_id or not self.gate_stack_container_id or not self.world_viewer_container_id:
                raise RuntimeError("Missing required gate containers for dashboard environment.")

            visual_dir = self._current_visual_dir()
            assert visual_dir is not None
            visual_dir_container = to_container_repo_path(visual_dir)
            truth_script = f"""
set -euo pipefail
PID_FILE="/tmp/chasecar_truth_probe.pid"
LOG_FILE="/tmp/chasecar_truth_probe.log"
pkill -f "sim_truth_probe.py" 2>/dev/null || true
rm -f "$PID_FILE" "$LOG_FILE"
nohup bash -lc 'source /opt/ros/{DEFAULT_CORE_ROS_DISTRO}/setup.bash && if [ -f /root/ros2_ws/install/setup.bash ]; then source /root/ros2_ws/install/setup.bash; fi && python3 /workspaces/chasecar/scripts/sim_truth_probe.py --session-id "{session_id}" --output-dir "{visual_dir_container}" --world-name "{DEFAULT_WORLD_NAME}" --target-model-names "{TARGET_MODEL_NAME_NAV2},{TARGET_MODEL_NAME_SNAPSHOT}" --duration-s 7200' >"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
sleep 1
echo "TRUTH_PID=$(cat "$PID_FILE")"
echo "TRUTH_LOG=$LOG_FILE"
"""
            truth_info = self._run_container_helper(self.sim_gate_container_id, truth_script, "TRUTH")
            if not self._wait_for_truth_ready(20.0):
                raise RuntimeError(f"Truth probe did not report robot visibility. {truth_info['output']}".strip())

            truth_state_container = to_container_repo_path(visual_dir / "truth_state.json")
            operator_status_container = to_container_repo_path(visual_dir / "operator_status.json")
            world_script = f"""
set -euo pipefail
PID_FILE="/tmp/chasecar_world_stream.pid"
LOG_FILE="/tmp/chasecar_world_stream.log"
pkill -f "world_stream_controller.py" 2>/dev/null || true
rm -f "$PID_FILE" "$LOG_FILE"
nohup bash -lc 'source /opt/ros/{DEFAULT_CORE_ROS_DISTRO}/setup.bash && if [ -f /root/ros2_ws/install/setup.bash ]; then source /root/ros2_ws/install/setup.bash; fi && python3 /workspaces/chasecar/scripts/world_stream_controller.py --session-id "{session_id}" --output-dir "{visual_dir_container}" --public-url "http://127.0.0.1:{world_stream_port}/vnc.html?autoconnect=1&resize=scale&path=websockify" --world-name "{DEFAULT_WORLD_NAME}" --image-topic /observer_world/image_raw --camera-profile overview_fixed --truth-state-path "{truth_state_container}" --duration-s 7200' >"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
sleep 1
echo "WORLD_STREAM_PID=$(cat "$PID_FILE")"
echo "WORLD_STREAM_LOG=$LOG_FILE"
"""
            world_info = self._run_container_helper(self.world_viewer_container_id, world_script, "WORLD_STREAM")
            if not self._wait_for_world_stream_ready(40.0):
                raise RuntimeError(f"World stream did not become ready. {world_info['output']}".strip())

            visual_script = f"""
set -euo pipefail
PID_FILE="/tmp/chasecar_visual_observer.pid"
LOG_FILE="/tmp/chasecar_visual_observer.log"
pkill -f "visual_demo_observer.py" 2>/dev/null || true
rm -f "$PID_FILE" "$LOG_FILE"
nohup bash -lc 'source /opt/ros/{DEFAULT_CORE_ROS_DISTRO}/setup.bash && if [ -f /root/ros2_ws/install/setup.bash ]; then source /root/ros2_ws/install/setup.bash; fi && python3 /workspaces/chasecar/scripts/visual_demo_observer.py --session-id "{session_id}" --output-dir "{visual_dir_container}" --execution-lane "container_kilted" --runtime-target "{DEFAULT_RUNTIME_TARGET}" --visual-mode "browser_dashboard" --phase "environment_ready" --target-id "" --duration-s 7200 --target-visible-min-ratio 0.04 --motion-progress-min-m 0.20 --truth-state-path "{truth_state_container}" --operator-status-path "{operator_status_container}" --use-sim-time' >"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
sleep 1
echo "VISUAL_PID=$(cat "$PID_FILE")"
echo "VISUAL_LOG=$LOG_FILE"
"""
            visual_info = self._run_container_helper(self.gate_stack_container_id, visual_script, "VISUAL")
            if not self._wait_for_visual_ready(20.0):
                raise RuntimeError(f"Visual observer did not emit dashboard frames. {visual_info['output']}".strip())

            self._update_state(
                environment_state="environment_ready",
                scenario_state="ready",
                environment_message="environment ready",
                scenario_message="ready",
                world_stream_url=f"http://127.0.0.1:{world_stream_port}/vnc.html?autoconnect=1&resize=scale&path=websockify",
            )
            self._write_operator_status(
                phase="environment_ready",
                target_id="",
                target_transition_active=False,
                status_text="Environment ready",
            )
            self._write_lock_file()
            self.build_on_next_start = False
        except Exception as exc:
            self._teardown_environment(
                env=self._base_env(
                    session_id=self.state.get("session_id", ""),
                    world_stream_port=int(self.state.get("world_stream_port", 0) or 0),
                )
            )
            if self.lifecycle_cancel.is_set():
                self._update_state(
                    environment_state="stopped",
                    scenario_state="idle",
                    environment_message="startup cancelled",
                    scenario_message="",
                    last_error="",
                )
            else:
                self._update_state(
                    environment_state="error",
                    scenario_state="idle",
                    environment_message="environment start failed",
                    last_error=str(exc),
                )
            self._remove_lock_file()
        finally:
            self.lifecycle_cancel.clear()
            self.active_env_proc = None
            self.lifecycle_lock.release()

    def _stop_environment_worker(self) -> None:
        if not self.lifecycle_lock.acquire(blocking=False):
            return
        try:
            with self.state_lock:
                session_id = self.state.get("session_id", "")
                world_stream_port = int(self.state.get("world_stream_port", 0) or 0)
            env = self._base_env(session_id=session_id or make_session_id(), world_stream_port=world_stream_port or find_free_port(8891, 8921))
            self._update_state(environment_state="stopping", scenario_state="idle", environment_message="stopping environment")
            self._write_operator_status(
                phase="stopping",
                target_id="",
                target_transition_active=False,
                status_text="Stopping environment",
            )
            self.scenario_cancel.set()
            self._terminate_process(self.active_scenario_proc)
            self._cleanup_scenario_processes()
            self._teardown_environment(env=env)
            stale = self._list_chasecar_containers()
            self._remove_lock_file()
            self._update_state(
                environment_state="stopped",
                scenario_state="idle",
                environment_message="stopped",
                scenario_message="",
                active_scenario="",
                phase="stopped",
                target_id="",
                target_transition_active=False,
                stale_chasecar_containers=stale,
            )
        except Exception as exc:
            self._update_state(environment_state="error", last_error=str(exc), environment_message="stop failed")
        finally:
            self.lifecycle_lock.release()

    def _refresh_environment_worker(self) -> None:
        if not self.lifecycle_lock.acquire(blocking=False):
            return
        try:
            with self.state_lock:
                session_id = self.state.get("session_id", "") or make_session_id()
                project_name = self.state.get("compose_project", "") or f"chasecar_dashboard_{slugify_session(session_id)}"
                world_stream_port = int(self.state.get("world_stream_port", 0) or find_free_port(8891, 8921))
            self._update_state(environment_state="stopping", environment_message="refreshing environment")
            env = self._base_env(session_id=session_id, world_stream_port=world_stream_port)
            self._cleanup_scenario_processes()
            self._teardown_environment(env=env)
            self._update_state(
                environment_state="stopped",
                environment_message="refresh restart pending",
                compose_project=project_name,
                session_id=session_id,
            )
        finally:
            self.lifecycle_lock.release()
        self._start_environment_worker()

    def _reset_environment_worker(self) -> None:
        if not self.lifecycle_lock.acquire(blocking=False):
            return
        try:
            with self.state_lock:
                old_session = self.state.get("session_id", "")
                world_stream_port = int(self.state.get("world_stream_port", 0) or find_free_port(8891, 8921))
            env = self._base_env(session_id=old_session or make_session_id(), world_stream_port=world_stream_port)
            self._update_state(environment_state="stopping", environment_message="resetting sim", scenario_message="reset pending")
            self.scenario_cancel.set()
            self._terminate_process(self.active_scenario_proc)
            self._cleanup_scenario_processes()
            self._teardown_environment(env=env)
            self._remove_lock_file()
        finally:
            self.lifecycle_lock.release()
        self._start_environment_worker()

    def _teardown_environment(self, env: Dict[str, str]) -> None:
        if self.gate_stack_container_id:
            self._docker_exec(
                self.gate_stack_container_id,
                """
set +e
if [ -f /tmp/chasecar_visual_observer.pid ]; then
  PID="$(cat /tmp/chasecar_visual_observer.pid 2>/dev/null || true)"
  [ -n "$PID" ] && kill "$PID" 2>/dev/null || true
fi
pkill -f "visual_demo_observer.py" 2>/dev/null || true
""",
            )
        if self.sim_gate_container_id:
            self._docker_exec(
                self.sim_gate_container_id,
                """
set +e
if [ -f /tmp/chasecar_truth_probe.pid ]; then
  PID="$(cat /tmp/chasecar_truth_probe.pid 2>/dev/null || true)"
  [ -n "$PID" ] && kill "$PID" 2>/dev/null || true
fi
pkill -f "sim_truth_probe.py" 2>/dev/null || true
""",
            )
        if self.world_viewer_container_id:
            self._docker_exec(
                self.world_viewer_container_id,
                """
set +e
if [ -f /tmp/chasecar_world_stream.pid ]; then
  PID="$(cat /tmp/chasecar_world_stream.pid 2>/dev/null || true)"
  [ -n "$PID" ] && kill "$PID" 2>/dev/null || true
fi
pkill -f "world_stream_controller.py" 2>/dev/null || true
pkill -f "websockify .* 6080" 2>/dev/null || true
pkill -f "x11vnc .*5900" 2>/dev/null || true
pkill -f "Xvfb :99" 2>/dev/null || true
pkill -f "fluxbox" 2>/dev/null || true
pkill -f "gz gui" 2>/dev/null || true
""",
            )

        project_name = self.state.get("compose_project", "")
        if project_name:
            if self._is_docker_socket_mode():
                self._run_docker_compose(project_name, "down", "--remove-orphans", env=env)
                self._force_remove_project_resources(project_name)
            else:
                self._run_powershell(
                    "run_compose_gate.ps1",
                    "-Action",
                    "down",
                    "-ProjectName",
                    project_name,
                    "-RuntimeTarget",
                    DEFAULT_RUNTIME_TARGET,
                    "-InferenceBackend",
                    DEFAULT_INFERENCE_BACKEND,
                    "-CoreRosDistro",
                    DEFAULT_CORE_ROS_DISTRO,
                    env=env,
                )
                self._run_powershell(
                    "run_compose_uat.ps1",
                    "-Action",
                    "down",
                    "-ProjectName",
                    project_name,
                    "-RuntimeTarget",
                    DEFAULT_RUNTIME_TARGET,
                    "-InferenceBackend",
                    DEFAULT_INFERENCE_BACKEND,
                    "-CoreRosDistro",
                    DEFAULT_CORE_ROS_DISTRO,
                    env=env,
                )
        self.sim_gate_container_id = ""
        self.gate_stack_container_id = ""
        self.world_viewer_container_id = ""

    def _list_chasecar_containers(self) -> list[str]:
        proc = subprocess.run(
            [self.docker, "ps", "--format", "{{.Names}}"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        names = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        return [name for name in names if name.startswith(SESSION_PROJECT_PREFIX)]

    def _scenario_worker(self, scenario: ScenarioDefinition) -> None:
        if not self.scenario_lock.acquire(blocking=False):
            return
        try:
            self._update_state(
                scenario_state="running",
                active_scenario=scenario.id,
                scenario_message=f"running {scenario.id}",
                latest_artifacts={},
                motion_evidence=False,
            )
            self._write_operator_status(
                phase=scenario.phase,
                target_id=scenario.target_id,
                target_transition_active=False,
                status_text=f"Running {scenario.label}",
            )
            if scenario.mode == "m2":
                result = self._run_m2_scenario(scenario)
            elif scenario.mode == "m3":
                result = self._run_m3_scenario(scenario)
            else:
                result = self._run_multi_target_scenario(scenario)
            artifacts = result.get("artifacts", {})
            self._update_state(
                scenario_state="ready" if result.get("pass") else "error",
                scenario_message=result.get("message", ""),
                latest_artifacts=artifacts,
                motion_evidence=bool(result.get("motion_evidence", False)),
                last_result=result.get("message", ""),
            )
            self._write_operator_status(
                phase="environment_ready",
                target_id="",
                target_transition_active=False,
                status_text="Environment ready",
            )
        except RuntimeError as exc:
            if str(exc) != "scenario cancelled":
                raise
            self._cleanup_scenario_processes()
            with self.state_lock:
                environment_state = self.state.get("environment_state", "stopped")
            if environment_state == "environment_ready":
                self._update_state(
                    scenario_state="ready",
                    scenario_message="ready",
                    latest_artifacts={},
                    motion_evidence=False,
                    last_error="",
                    last_result="scenario cancelled",
                )
            else:
                self._update_state(
                    scenario_state="idle",
                    scenario_message="",
                    latest_artifacts={},
                    motion_evidence=False,
                    last_error="",
                    last_result="scenario cancelled",
                )
        except Exception as exc:
            self._update_state(scenario_state="error", scenario_message=f"scenario failed: {exc}", last_error=str(exc))
        finally:
            self.active_scenario_proc = None
            self.scenario_cancel.clear()
            self._update_state(active_scenario="")
            self.scenario_lock.release()

    def _scenario_env(self, scenario: ScenarioDefinition) -> Dict[str, str]:
        session_id = self.state.get("session_id", "")
        world_stream_port = int(self.state.get("world_stream_port", 0) or find_free_port(8891, 8921))
        env = self._base_env(session_id=session_id, world_stream_port=world_stream_port)
        env.update(
            {
                "CHASECAR_NAV2_TARGET_X": f"{scenario.target_x:.3f}",
                "CHASECAR_NAV2_TARGET_Y": f"{scenario.target_y:.3f}",
                "CHASECAR_NAV2_TARGET_Z": f"{scenario.target_z:.3f}",
                "CHASECAR_NAV2_WORLD_NAME": DEFAULT_WORLD_NAME,
                "CHASECAR_NAV2_MODEL_SDF": TARGET_MODEL_SDF,
                "CHASECAR_NAV2_MODEL_NAME": TARGET_MODEL_NAME_NAV2,
                "CHASECAR_SNAPSHOT_TARGET_X": f"{scenario.target_x:.3f}",
                "CHASECAR_SNAPSHOT_TARGET_Y": f"{scenario.target_y:.3f}",
                "CHASECAR_SNAPSHOT_TARGET_Z": f"{scenario.target_z:.3f}",
                "CHASECAR_SNAPSHOT_WORLD_NAME": DEFAULT_WORLD_NAME,
                "CHASECAR_SNAPSHOT_MODEL_SDF": TARGET_MODEL_SDF,
                "CHASECAR_SNAPSHOT_MODEL_NAME": TARGET_MODEL_NAME_SNAPSHOT,
            }
        )
        return env

    def _run_uat_stage(self, mode: str, scenario: ScenarioDefinition) -> Dict[str, Any]:
        env = self._scenario_env(scenario)
        if self._is_docker_socket_mode():
            log_dir = self._scenarios_dir() or ensure_dir(self._current_validation_dir() or (SESSION_ROOT / self.state["session_id"] / "dashboard_validation"))
            log_path = ensure_dir(log_dir) / f"{scenario.id}_{mode}.log"
            script = f"""
set -euo pipefail
export CHASECAR_UAT_MODE="{mode}"
export CHASECAR_RUNTIME_TARGET="{DEFAULT_RUNTIME_TARGET}"
export CHASECAR_SIM_LANE="{DEFAULT_SIM_LANE}"
export CHASECAR_INFERENCE_BACKEND="{DEFAULT_INFERENCE_BACKEND}"
export CHASECAR_STEP_TIMEOUT_S="900"
export CHASECAR_NAV2_DURATION_S="120"
export CHASECAR_MULTI_TARGET_GOAL_TIMEOUT_S="55"
export CHASECAR_SNAPSHOT_TIMEOUT_S="12"
export CHASECAR_SNAPSHOT_MIN_MEAN_ABS_DIFF="1"
export CHASECAR_SNAPSHOT_MIN_CHANGED_PIXEL_RATIO="0.001"
export CHASECAR_SNAPSHOT_MIN_FRAMES="1"
export CHASECAR_SNAPSHOT_RGB_TOPIC="/d415/color/image_raw"
export CHASECAR_SNAPSHOT_DEBUG_TOPIC="/yolo/debug_image"
export CHASECAR_NAV2_BRIDGE_MAX_GOALS="1"
export CHASECAR_NAV2_CONFIG="{DEFAULT_NAV2_CONFIG}"
export CHASECAR_MULTI_TARGET_CONFIG="{DEFAULT_MULTI_TARGET_CONFIG}"
export CHASECAR_UAT_PROFILE="{DEFAULT_GATE_PROFILE}"
export CHASECAR_UAT_INFERENCE_DEVICE="{DEFAULT_INFERENCE_DEVICE}"
export CHASECAR_NAV2_TARGET_X="{env['CHASECAR_NAV2_TARGET_X']}"
export CHASECAR_NAV2_TARGET_Y="{env['CHASECAR_NAV2_TARGET_Y']}"
export CHASECAR_NAV2_TARGET_Z="{env['CHASECAR_NAV2_TARGET_Z']}"
export CHASECAR_NAV2_WORLD_NAME="{env['CHASECAR_NAV2_WORLD_NAME']}"
export CHASECAR_NAV2_MODEL_SDF="{env['CHASECAR_NAV2_MODEL_SDF']}"
export CHASECAR_NAV2_MODEL_NAME="{env['CHASECAR_NAV2_MODEL_NAME']}"
export CHASECAR_SNAPSHOT_TARGET_X="{env['CHASECAR_SNAPSHOT_TARGET_X']}"
export CHASECAR_SNAPSHOT_TARGET_Y="{env['CHASECAR_SNAPSHOT_TARGET_Y']}"
export CHASECAR_SNAPSHOT_TARGET_Z="{env['CHASECAR_SNAPSHOT_TARGET_Z']}"
export CHASECAR_SNAPSHOT_WORLD_NAME="{env['CHASECAR_SNAPSHOT_WORLD_NAME']}"
export CHASECAR_SNAPSHOT_MODEL_SDF="{env['CHASECAR_SNAPSHOT_MODEL_SDF']}"
export CHASECAR_SNAPSHOT_MODEL_NAME="{env['CHASECAR_SNAPSHOT_MODEL_NAME']}"
export REPO_ROOT="/workspaces/chasecar"
bash /workspaces/chasecar/uat/orchestrator/run_uat_orchestrator.sh
"""
            proc = self._docker_exec_popen(self.sim_gate_container_id, script, log_path)
            self.active_scenario_proc = proc
            proc.wait()
            output = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
        else:
            args = [
                "-Action",
                "run",
                "-ProjectName",
                self.state["compose_project"],
                "-RuntimeTarget",
                DEFAULT_RUNTIME_TARGET,
                "-InferenceBackend",
                DEFAULT_INFERENCE_BACKEND,
                "-CoreRosDistro",
                DEFAULT_CORE_ROS_DISTRO,
                "-UatMode",
                mode,
                "-UatExecutionContext",
                "sim_gate",
                "-UatProfile",
                DEFAULT_GATE_PROFILE,
                "-UatInferenceDevice",
                DEFAULT_INFERENCE_DEVICE,
            ]
            if mode == "nav2":
                args += ["-Nav2DurationSeconds", "120", "-Nav2Config", DEFAULT_NAV2_CONFIG]
            proc = self._popen_powershell("run_compose_uat.ps1", *args, env=env)
            self.active_scenario_proc = proc
            output, _ = proc.communicate()
        if self.scenario_cancel.is_set():
            raise RuntimeError("scenario cancelled")
        step_marker = parse_step_marker(output, mode)
        artifact_dir = step_marker.get("artifact_dir") or parse_marker(output, "ARTIFACT_DIR=")
        readiness_report = parse_marker(output, "READINESS_REPORT=")
        artifact_path = self._resolve_artifact_dir(artifact_dir) if artifact_dir else ""
        if proc.returncode != 0:
            raise RuntimeError(f"{mode} stage failed: {output.strip()}")
        return {
            "output": output,
            "artifact_dir": artifact_path,
            "readiness_report": readiness_report,
        }

    def _load_summary(self, artifact_dir: str, summary_name: str) -> Dict[str, Any]:
        if not artifact_dir:
            return {}
        path = Path(artifact_dir) / summary_name
        return read_json(path)

    def _write_scenario_result(self, scenario_id: str, payload: Dict[str, Any]) -> None:
        scenario_dir = self._scenarios_dir()
        if scenario_dir is None:
            return
        write_json(scenario_dir / f"{scenario_id}.json", payload)

    def _run_m2_scenario(self, scenario: ScenarioDefinition) -> Dict[str, Any]:
        coordinate = self._run_uat_stage("coordinate", scenario)
        snapshot = self._run_uat_stage("snapshot", scenario)
        coordinate_summary = self._load_summary(coordinate["artifact_dir"], "summary.json")
        snapshot_summary = self._load_summary(snapshot["artifact_dir"], "snapshot_summary.json")
        passed = bool(coordinate_summary.get("pass")) and bool(snapshot_summary.get("pass"))
        payload = {
            "scenario_id": scenario.id,
            "phase": scenario.phase,
            "pass": passed,
            "artifacts": {
                "coordinate": coordinate["artifact_dir"],
                "snapshot": snapshot["artifact_dir"],
            },
            "coordinate_summary": coordinate_summary,
            "snapshot_summary": snapshot_summary,
            "message": "m2 scenario passed" if passed else "m2 scenario failed",
            "motion_evidence": False,
        }
        self._write_scenario_result(scenario.id, payload)
        return payload

    def _run_m3_scenario(self, scenario: ScenarioDefinition) -> Dict[str, Any]:
        snapshot = self._run_uat_stage("snapshot", scenario)
        nav2 = self._run_uat_stage("nav2", scenario)
        snapshot_summary = self._load_summary(snapshot["artifact_dir"], "snapshot_summary.json")
        nav_summary = self._load_summary(nav2["artifact_dir"], "nav_summary.json")
        motion_evidence = bool(nav_summary.get("target_progress", {}).get("pass")) or bool(nav_summary.get("pass"))
        passed = bool(snapshot_summary.get("pass")) and bool(nav_summary.get("pass"))
        payload = {
            "scenario_id": scenario.id,
            "phase": scenario.phase,
            "pass": passed,
            "artifacts": {
                "snapshot": snapshot["artifact_dir"],
                "nav2": nav2["artifact_dir"],
            },
            "snapshot_summary": snapshot_summary,
            "nav_summary": nav_summary,
            "message": "m3 scenario passed" if passed else "m3 scenario failed",
            "motion_evidence": motion_evidence,
        }
        self._write_scenario_result(scenario.id, payload)
        return payload

    def _run_multi_target_scenario(self, scenario: ScenarioDefinition) -> Dict[str, Any]:
        progress_path = self._multi_target_progress_path()
        assert progress_path is not None
        try:
            progress_path.unlink()
        except FileNotFoundError:
            pass

        progress_container_path = to_container_repo_path(progress_path)
        log_path = progress_path.with_suffix(".log")
        cfg_container = to_container_repo_path(REPO_ROOT / DEFAULT_MULTI_TARGET_CONFIG)
        script = f"""
set -euo pipefail
export AMENT_TRACE_SETUP_FILES="${{AMENT_TRACE_SETUP_FILES-}}"
set +u
source /opt/ros/{DEFAULT_CORE_ROS_DISTRO}/setup.bash
if [ -f /root/ros2_ws/install/setup.bash ]; then
  source /root/ros2_ws/install/setup.bash
fi
set -u
cd /workspaces/chasecar
python3 scripts/multi_target_nav2_runner.py --runtime-target "{DEFAULT_RUNTIME_TARGET}" --profile "{DEFAULT_GATE_PROFILE}" --inference-device "{DEFAULT_INFERENCE_DEVICE}" --config "{cfg_container}" --goal-timeout-s "55" --progress-json "{progress_container_path}" --transition-hold-s "1.5" --use-sim-time
"""
        proc = self._docker_exec_popen(self.sim_gate_container_id, script, log_path)
        self.active_scenario_proc = proc
        last_transition = False
        while proc.poll() is None:
            if self.scenario_cancel.is_set():
                self._terminate_process(proc)
                self._cleanup_scenario_processes()
                raise RuntimeError("scenario cancelled")
            progress = read_json(progress_path)
            if progress:
                transition_active = bool(progress.get("target_transition_active", False))
                current_target = progress.get("current_scenario_id", scenario.target_id)
                phase = scenario.phase if progress.get("phase") not in {"completed", "failed"} else progress.get("phase", scenario.phase)
                self._write_operator_status(
                    phase=phase,
                    target_id=current_target,
                    target_transition_active=transition_active,
                    status_text="Target transition active" if transition_active else f"Running {current_target}",
                )
                last_transition = last_transition or transition_active
            time.sleep(1.0)
        if proc.returncode != 0:
            output = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
            raise RuntimeError(output.strip() or "multi_target runner failed")

        summary_dir = self._find_latest_artifact_dir(REPO_ROOT / "artifacts" / "nav2_multi", "multi_target_summary.json")
        summary = self._load_summary(str(summary_dir) if summary_dir else "", "multi_target_summary.json")
        payload = {
            "scenario_id": scenario.id,
            "phase": scenario.phase,
            "pass": bool(summary.get("pass")),
            "artifacts": {
                "multi_target": str(summary_dir) if summary_dir else "",
                "progress": str(progress_path),
                "log": str(log_path),
            },
            "multi_target_summary": summary,
            "message": "multi-target rehearsal passed" if summary.get("pass") else "multi-target rehearsal failed",
            "motion_evidence": bool(summary.get("pass")),
            "target_transition_seen": last_transition or bool(read_json(progress_path).get("target_transition_active", False)),
        }
        self._write_scenario_result(scenario.id, payload)
        return payload

    def _find_latest_artifact_dir(self, root: Path, file_name: str) -> Optional[Path]:
        if not root.exists():
            return None
        candidates = [item for item in root.glob(f"*/{file_name}") if item.is_file()]
        if not candidates:
            return None
        latest = max(candidates, key=lambda item: item.stat().st_mtime)
        return latest.parent

    def _cleanup_scenario_processes(self) -> None:
        if self.sim_gate_container_id:
            self._docker_exec(
                self.sim_gate_container_id,
                f"""
set +e
pkill -f "run_uat_orchestrator.sh" 2>/dev/null || true
pkill -f "coordinate_uat_runner.py" 2>/dev/null || true
pkill -f "nav2_readiness_runner.py" 2>/dev/null || true
pkill -f "multi_target_nav2_runner.py" 2>/dev/null || true
pkill -f "capture_topic_image.py" 2>/dev/null || true
pkill -f "image_diff_metrics.py" 2>/dev/null || true
pkill -f "yolo_3d_to_nav2_bridge.py" 2>/dev/null || true
if command -v gz >/dev/null 2>&1; then
  gz service -s "/world/{DEFAULT_WORLD_NAME}/remove/blocking" --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"{TARGET_MODEL_NAME_NAV2}\\" type: 2" >/dev/null 2>&1 || true
  gz service -s "/world/{DEFAULT_WORLD_NAME}/remove/blocking" --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"{TARGET_MODEL_NAME_SNAPSHOT}\\" type: 2" >/dev/null 2>&1 || true
fi
""",
            )
        if self.state.get("environment_state") == "environment_ready":
            try:
                self._run_intent_sync(self._prepare_intent_preview("abort", {}))
            except Exception:
                pass
        self._write_operator_status(
            phase="environment_ready",
            target_id="",
            target_transition_active=False,
            status_text="Environment ready",
        )
        self._update_state(scenario_state="ready", scenario_message="ready", active_scenario="")

    def _intent_worker(self, preview: Dict[str, Any]) -> None:
        if not self.intent_lock.acquire(blocking=False):
            return
        intent_name = str(preview.get("intent", ""))
        try:
            result = self._run_intent_sync(preview)
            self._update_state(
                last_intent=intent_name,
                last_intent_payload=preview.get("payload", {}),
                last_intent_timestamp_utc=preview.get("payload", {}).get("timestamp_utc", ""),
                last_feedback=result.get("feedback_samples", [""])[-1] if result.get("feedback_samples") else "",
                last_result=f"{intent_name}: {'pass' if result.get('pass') else 'fail'}",
            )
        except Exception as exc:
            self._update_state(
                last_intent=intent_name,
                last_intent_payload=preview.get("payload", {}),
                last_intent_timestamp_utc=preview.get("payload", {}).get("timestamp_utc", ""),
                last_result=f"{intent_name}: fail",
                last_error=str(exc),
            )
        finally:
            self.active_intent_proc = None
            self.intent_lock.release()

    def _run_intent_sync(self, preview: Dict[str, Any]) -> Dict[str, Any]:
        intent_name = str(preview.get("intent", ""))
        args_payload = dict(preview.get("args", {}))
        payload = dict(preview.get("payload", {}))
        readiness = dict(preview.get("readiness", {}))
        if intent_name not in self.frozen_intents:
            raise ValueError(f"Unsupported frozen intent: {intent_name}")
        output_path = ensure_dir(self._current_validation_dir()) / f"intent_{intent_name}_{int(time.time())}.json"
        args_json = json.dumps(args_payload, separators=(",", ":"))
        output_path_container = shlex.quote(to_container_repo_path(output_path))
        planner = shlex.quote(str(payload.get("planner", "dashboard_service")))
        timestamp_utc = shlex.quote(str(payload.get("timestamp_utc", "")))
        script = f"""
set -euo pipefail
export AMENT_TRACE_SETUP_FILES="${{AMENT_TRACE_SETUP_FILES-}}"
set +u
source /opt/ros/{DEFAULT_CORE_ROS_DISTRO}/setup.bash
if [ -f /root/ros2_ws/install/setup.bash ]; then
  source /root/ros2_ws/install/setup.bash
fi
set -u
cd /workspaces/chasecar
python3 scripts/dashboard_intent_runner.py --intent {shlex.quote(intent_name)} --args-json {shlex.quote(args_json)} --output {output_path_container} --seq {int(payload.get("seq", 0) or 0)} --planner {planner} --timestamp-utc {timestamp_utc} --wait-timeout-s 12 --observe-time-s 3 --use-sim-time
"""
        log_path = output_path.with_suffix(".log")
        proc = self._docker_exec_popen(self.sim_gate_container_id, script, log_path)
        self.active_intent_proc = proc
        proc.wait()
        if proc.returncode != 0 and not output_path.exists():
            output = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
            raise RuntimeError(output.strip() or "intent runner failed")
        result = read_json(output_path)
        history_entry = {
            "event_type": "execute",
            "timestamp_utc": utc_now(),
            "intent": intent_name,
            "args": args_payload,
            "payload": payload,
            "readiness": readiness,
            "summary_path": str(output_path),
            "pass": bool(result.get("pass")),
            "feedback_seen": bool(result.get("feedback_seen")),
            "feedback_samples": result.get("feedback_samples", []),
            "boundary_activity_seen": bool(result.get("boundary_activity_seen", False)),
        }
        self._record_command_history(history_entry)
        self._record_visual_event(
            {
                "event_type": "intent_executed",
                "intent": intent_name,
                "payload": payload,
                "pass": bool(result.get("pass")),
                "summary_path": str(output_path),
            }
        )
        return result


class DashboardRequestHandler(BaseHTTPRequestHandler):
    server: "DashboardHttpServer"

    def _json_response(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path: Path, content_type: str) -> None:
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        if not raw.strip():
            return {}
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("JSON body must decode to an object.")
        return payload

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or "/"
        query = parse_qs(parsed.query or "")
        controller = self.server.controller
        if path in {"/", "/dashboard.html"}:
            return self._serve_file(REPO_ROOT / "runtime" / "dashboard" / "browser_dashboard.html", "text/html; charset=utf-8")
        if path == "/api/state":
            return self._json_response(HTTPStatus.OK, controller.get_state())
        if path == "/api/llm/supervisor/history":
            try:
                limit = int((query.get("limit") or ["20"])[0])
            except (TypeError, ValueError):
                return self._json_response(HTTPStatus.BAD_REQUEST, {"error": "limit must be an integer"})
            return self._json_response(HTTPStatus.OK, controller.list_llm_supervisor_history(limit))
        if path == "/api/scenarios":
            return self._json_response(HTTPStatus.OK, controller.list_scenarios())
        if path.startswith("/live/"):
            live_name = path[len("/") :]
            live_path = controller.read_live_file(live_name)
            if live_path is None:
                return self._json_response(HTTPStatus.NOT_FOUND, {"error": f"missing live asset: {live_name}"})
            content_type = "image/jpeg"
            if live_path.suffix.lower() == ".png":
                content_type = "image/png"
            return self._serve_file(live_path, content_type)
        return self._json_response(HTTPStatus.NOT_FOUND, {"error": f"unknown route: {path}"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or "/"
        controller = self.server.controller
        try:
            body = self._read_json_body()
        except Exception as exc:
            return self._json_response(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        if path == "/api/env/start":
            status, payload = controller.request_start()
            return self._json_response(status, payload)
        if path == "/api/env/stop":
            status, payload = controller.request_stop()
            return self._json_response(status, payload)
        if path == "/api/env/refresh":
            status, payload = controller.request_refresh()
            return self._json_response(status, payload)
        if path == "/api/sim/reset":
            status, payload = controller.request_reset_sim()
            return self._json_response(status, payload)
        if path == "/api/scenario/run":
            scenario_id = str(body.get("scenario_id", "")).strip()
            status, payload = controller.request_scenario_run(scenario_id)
            return self._json_response(status, payload)
        if path == "/api/scenario/stop":
            status, payload = controller.request_scenario_stop()
            return self._json_response(status, payload)
        if path == "/api/intents/preview":
            status, payload = controller.request_intent_preview(body)
            return self._json_response(status, payload)
        if path == "/api/intents/dispatch":
            status, payload = controller.request_intent_dispatch(body)
            return self._json_response(status, payload)
        if path.startswith("/api/intents/"):
            intent_name = path.rsplit("/", 1)[-1]
            try:
                _, args_payload = controller._resolve_intent_request(body, route_intent=intent_name)
            except Exception as exc:
                return self._json_response(HTTPStatus.BAD_REQUEST, {"accepted": False, "error": str(exc)})
            status, payload = controller.request_intent(intent_name, args_payload)
            return self._json_response(status, payload)
        return self._json_response(HTTPStatus.NOT_FOUND, {"error": f"unknown route: {path}"})

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


class DashboardHttpServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], controller: DashboardController) -> None:
        super().__init__(server_address, DashboardRequestHandler)
        self.controller = controller


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the Chasecar operator dashboard control plane.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8860)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    controller = DashboardController(host=args.host, port=args.port)
    controller._update_state(dashboard_url=f"http://{args.host}:{args.port}/")
    server = DashboardHttpServer((args.host, args.port), controller)
    print(f"DASHBOARD_URL=http://{args.host}:{args.port}/")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
