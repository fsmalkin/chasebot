#!/usr/bin/env python3
"""Persistent local dashboard control service for the authoritative container lane."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
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

from brain_supervisor_policy import build_policy_snapshot
from brain_supervisor_policy import intent_readiness_snapshot
from llm_supervisor_core import load_supervisor_runtime_state as load_shadow_runtime_state
from llm_supervisor_core import read_jsonl as read_jsonl_lines


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Load .env from repo root so API keys are available regardless of how
# the dashboard is launched (CLI, IDE, background process, etc.).
_dotenv_path = REPO_ROOT / ".env"
if _dotenv_path.is_file():
    with _dotenv_path.open(encoding="utf-8", errors="ignore") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _key, _, _val = _line.partition("=")
            _key = _key.strip()
            _val = _val.strip().strip("'\"")
            if _key and _key not in os.environ:
                os.environ[_key] = _val
STATIC_DASHBOARD_DIR = REPO_ROOT / "runtime" / "dashboard"
SESSION_ROOT = REPO_ROOT / "artifacts" / "session"
DEFAULT_RUNTIME_DIR = STATIC_DASHBOARD_DIR

DEFAULT_RUNTIME_TARGET = "robot_fidelity_orin"
DEFAULT_CORE_ROS_DISTRO = "kilted"
DEFAULT_WORLD_FILE = "yolo_test_world_v6_clean_uat.world"
DEFAULT_SURFACE_PROFILE = "baseline"
SHORT_TURF_WORLD_FILE = "yolo_test_world_v6_clean_uat_short_turf.world"
SHORT_GRASS_WORLD_FILE = "yolo_test_world_v6_clean_uat_short_grass.world"
DEFAULT_WORLD_NAME = "yolo_test_world"
DEFAULT_INFERENCE_BACKEND = "tensorrt_int8"
DEFAULT_GATE_PROFILE = "compat"
DEFAULT_INFERENCE_DEVICE = "cuda:0"
DEFAULT_MULTI_TARGET_CONFIG = "ros2_config/config/multi_target_nav2_fidelity.yaml"
DEFAULT_NAV2_CONFIG = "ros2_config/config/nav2_readiness_fidelity.yaml"
TARGET_MODEL_SDF = "ros2_config/frisbee_target_ball.sdf"
BASELINE_ROBOT_SDF_NAME = "jetbot_core_ignition_v1.6.0.sdf"
CORRAL_ROBOT_SDF_NAME = "jetbot_core_ignition_v1.7.0.sdf"
TARGET_MODEL_NAME_NAV2 = "uat_nav2_target"
TARGET_MODEL_NAME_SNAPSHOT = "uat_snapshot_target"
TARGET_MODEL_NAME_PROOF = "llm_turn_then_go_target"
DEFAULT_VISIT_MISSION_POLL_S = 0.25
TRUTH_TARGET_MODEL_NAMES = (
    TARGET_MODEL_NAME_NAV2,
    TARGET_MODEL_NAME_SNAPSHOT,
    TARGET_MODEL_NAME_PROOF,
)
TRUTH_TARGET_MODEL_PREFIX = "visit_mission_target_"
WORLD_STREAM_RESTART_COOLDOWN_S = 20.0
WORLD_STREAM_RESTART_MAX_ATTEMPTS = 3
WORLD_STREAM_STALE_DEBOUNCE_S = 3.0
WORLD_STREAM_WATCHDOG_POLL_S = 1.0
WORLD_STREAM_TRANSPORT_WINDOW_S = 5.0
WORLD_STREAM_TRANSPORT_MIN_FRAMES = 3
WORLD_STREAM_TRANSPORT_MAX_AGE_S = 4.0
WORLD_STREAM_RENDERABLE_GRACE_S = 10.0
GATE_SERVICE_READY_TIMEOUT_S = 25.0
GATE_SERVICE_POLL_S = 0.5
DEFAULT_CONTROL_MODE = "host_powershell"
DEFAULT_SIM_LANE = "jetty_gate"
DEFAULT_BRIDGE_ROS_DISTRO = "jazzy"
DEFAULT_WARM_SERVICES = ("dashboard-control", "dashboard-utility")
DEFAULT_DOCKER_SOCKET_PATH = Path("/var/run/docker.sock")
SESSION_PROJECT_PREFIX = "chasecar_dashboard_"
HOST_PORT_BIND_FAILURE_RE = re.compile(r"Bind for (?:127\.0\.0\.1|0\.0\.0\.0):(\d+) failed: port is already allocated")
OPERATOR_VIEW_PORT_START = 14500
OPERATOR_VIEW_PORT_END = 14520
OPERATOR_VIEW_HEARTBEAT_STALE_S = 5.0
REQUIRED_GATE_SERVICES = ("sim-gate", "world-viewer", "gate-stack", "operator-view")
HEADLESS_SOAK_GATE_SERVICES = ("sim-gate", "gate-stack")
SELF_CONTAINED_SCENARIO_IDS = {"visit_route_planning", "corral_single_ball_place", "gather_three_ball_zone"}

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
    browser_default: bool = False
    featured: bool = False
    robot_sdf_name: str = BASELINE_ROBOT_SDF_NAME
    world_file: str = DEFAULT_WORLD_FILE
    surface_profile: str = DEFAULT_SURFACE_PROFILE
    target_x: float = 1.10
    target_y: float = 0.00
    target_z: float = 0.05

    def to_api(self) -> Dict[str, Any]:
        return asdict(self)


class EnvironmentStartupError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        environment_failure_class: str = "",
        operator_view_failure_class: str = "",
        gate_service_states: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        super().__init__(message)
        self.environment_failure_class = str(environment_failure_class or "")
        self.operator_view_failure_class = str(operator_view_failure_class or "")
        self.gate_service_states = json.loads(json.dumps(gate_service_states or {}))


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
        id="llm_turn_then_go_proof",
        phase="llm_turn_then_go_proof",
        target_id="ball",
        label="LLM Turn + Go",
        description="LLM proof demo: turn until the ball is seen, then move to it.",
        mode="llm_proof",
        browser_default=True,
        featured=True,
    ),
    ScenarioDefinition(
        id="m3_single_target",
        phase="M3",
        target_id="single_target",
        label="M3 Single Target",
        description="Single-target motion proof on the canonical forward target.",
        mode="m3",
        browser_default=True,
    ),
    ScenarioDefinition(
        id="m3_center",
        phase="M3",
        target_id="center",
        label="M3 Center",
        description="Single-target motion proof at the center preset.",
        mode="m3",
        browser_default=True,
    ),
    ScenarioDefinition(
        id="m3_left",
        phase="M3",
        target_id="left",
        label="M3 Left",
        description="Single-target motion proof at the left preset.",
        mode="m3",
        browser_default=True,
        target_y=0.12,
    ),
    ScenarioDefinition(
        id="m3_right",
        phase="M3",
        target_id="right",
        label="M3 Right",
        description="Single-target motion proof at the right preset.",
        mode="m3",
        browser_default=True,
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
    ScenarioDefinition(
        id="visit_single_ball_proof",
        phase="visit_single_ball_proof",
        target_id="ball_1",
        label="Visit Single Ball",
        description="Deterministic single-ball visit mission with search, lock, and approach.",
        mode="visit_mission",
    ),
    ScenarioDefinition(
        id="visit_three_ball_sequence",
        phase="visit_three_ball_sequence",
        target_id="ball_sequence",
        label="Visit Three Ball Sequence",
        description="Deterministic three-ball visit mission with ordered target progression.",
        mode="visit_mission",
    ),
    ScenarioDefinition(
        id="visit_m3_positions",
        phase="visit_m3_positions",
        target_id="m3_positions",
        label="Visit M3 Positions",
        description="Bounded supervisor visit across M3 target positions (center, left, right).",
        mode="visit_mission",
    ),
    ScenarioDefinition(
        id="visit_route_planning",
        phase="visit_route_planning",
        target_id="route_plan",
        label="LLM Route Planning",
        description="LLM-planned multi-target visit: the LLM chooses which target to visit next.",
        mode="visit_mission",
        featured=True,
    ),
    ScenarioDefinition(
        id="corral_single_ball_place",
        phase="corral_single_ball_place",
        target_id="ball_1",
        label="Corral Single Ball Place",
        description="Single-ball corral mission: visit, capture, and place the ball into the zone.",
        mode="gather_mission",
        robot_sdf_name=CORRAL_ROBOT_SDF_NAME,
        world_file=SHORT_TURF_WORLD_FILE,
        surface_profile="short_turf",
    ),
    ScenarioDefinition(
        id="gather_three_ball_zone",
        phase="gather_three_ball_zone",
        target_id="ball_sequence",
        label="Gather Three Ball Zone",
        description="Three-ball gather mission: visit, capture, and retrieve all balls into the shared corral.",
        mode="gather_mission",
        robot_sdf_name=CORRAL_ROBOT_SDF_NAME,
        world_file=SHORT_TURF_WORLD_FILE,
        surface_profile="short_turf",
    ),
]
SCENARIOS_BY_ID = {item.id: item for item in SCENARIOS}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_session_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def slugify_session(session_id: str) -> str:
    return session_id.lower().replace(":", "").replace(" ", "")


def parse_utc_timestamp(value: str) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _truth_world_xy(pose: Dict[str, Any]) -> Optional[Dict[str, float]]:
    if not isinstance(pose, dict):
        return None
    position = pose.get("position")
    if not isinstance(position, dict):
        return None
    try:
        return {
            "x": float(position.get("x", 0.0)),
            "y": float(position.get("y", 0.0)),
        }
    except Exception:
        return None


def _truth_robot_pose(pose: Dict[str, Any]) -> Optional[Dict[str, float]]:
    if not isinstance(pose, dict):
        return None
    position = pose.get("position")
    orientation = pose.get("orientation")
    if not isinstance(position, dict) or not isinstance(orientation, dict):
        return None
    try:
        x = float(position.get("x", 0.0))
        y = float(position.get("y", 0.0))
        ox = float(orientation.get("x", 0.0))
        oy = float(orientation.get("y", 0.0))
        oz = float(orientation.get("z", 0.0))
        ow = float(orientation.get("w", 1.0))
    except Exception:
        return None
    yaw = math.atan2(2.0 * (ow * oz + ox * oy), 1.0 - 2.0 * (oy * oy + oz * oz))
    return {"x": x, "y": y, "yaw": yaw}


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


def can_bind_localhost_port(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def find_free_port(start: int, end: int, *, exclude_ports: Optional[set[int]] = None) -> int:
    excluded = exclude_ports or set()
    for port in range(start, end + 1):
        if port in excluded:
            continue
        if can_bind_localhost_port(port):
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


def resolve_runtime_dir(path_hint: str) -> Path:
    cleaned = str(path_hint or "").strip()
    if not cleaned:
        return DEFAULT_RUNTIME_DIR
    candidate = Path(cleaned)
    if not candidate.is_absolute():
        candidate = (REPO_ROOT / candidate).resolve()
    return candidate


class DashboardController:
    def __init__(
        self,
        host: str,
        port: int,
        *,
        runtime_dir: Path | None = None,
        peer_project_cleanup: str = "exclusive",
        headless_worker_mode: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.runtime_dir = (runtime_dir or DEFAULT_RUNTIME_DIR).resolve()
        self.state_path = self.runtime_dir / "dashboard_service_state.json"
        self.lock_path = self.runtime_dir / "dashboard_session.lock.json"
        self.llm_proof_runtime_path = self.runtime_dir / "llm_turn_then_go_runtime.json"
        self.visit_mission_runtime_path = self.runtime_dir / "visit_mission_runtime.json"
        self.gather_mission_runtime_path = self.runtime_dir / "gather_mission_runtime.json"
        self.intent_inbox_path = self.runtime_dir / "intent_inbox.json"
        self.intent_ack_path = self.runtime_dir / "intent_ack.json"
        self.peer_project_cleanup = peer_project_cleanup if peer_project_cleanup in {"exclusive", "none"} else "exclusive"
        self.headless_worker_mode = bool(headless_worker_mode)
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
        self.world_stream_watchdog_cancel = threading.Event()

        self.lifecycle_thread: Optional[threading.Thread] = None
        self.scenario_thread: Optional[threading.Thread] = None
        self.intent_thread: Optional[threading.Thread] = None
        self.world_stream_watchdog_thread: Optional[threading.Thread] = None

        self.active_env_proc: Optional[subprocess.Popen[str]] = None
        self.active_scenario_proc: Optional[subprocess.Popen[str]] = None
        self.active_intent_proc: Optional[subprocess.Popen[str]] = None

        self.sim_gate_container_id = ""
        self.gate_stack_container_id = ""
        self.world_viewer_container_id = ""
        self.operator_view_container_id = ""
        self.pending_scenario_id = ""
        self.pending_scenario_overrides: Dict[str, str] = {}
        self.build_on_next_start = True
        self.world_stream_restart_lock = threading.Lock()
        self._world_stream_stale_since_monotonic = 0.0
        self._world_stream_last_restart_monotonic = 0.0

        ensure_dir(self.runtime_dir)
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
                "surface_profile": DEFAULT_SURFACE_PROFILE,
                "robot_sdf_name": BASELINE_ROBOT_SDF_NAME,
                "world_name": DEFAULT_WORLD_NAME,
                "phase": "stopped",
                "target_id": "",
                "target_transition_active": False,
                "active_scenario": "",
                "environment_message": "stopped",
                "environment_failure_class": "",
                "gate_service_states": {},
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
                "proof_state": "waiting",
                "proof_verdict": {},
                "mission_phase": "idle",
                "mission_status": "idle",
                "search_bias_active": False,
                "current_target_id": "",
                "visit_index": 0,
                "visited_targets": [],
                "remaining_targets": [],
                "last_visit_result": {},
                "mission_verdict": {},
                "gather_phase": "idle",
                "capture_state": {},
                "zone_pose": {},
                "zone_score": {},
                "final_corral_audit": {},
                "placed_targets": [],
                "capture_loss_count": 0,
                "route_order": [],
                "latest_operator_event": "",
                "recent_operator_events": [],
                "world_stream_url": "",
                "world_stream_port": 0,
                "world_stream_renderable": False,
                "world_stream_transport_healthy": False,
                "world_stream_degraded": False,
                "operator_view_backend": "xpra",
                "operator_view_url": "",
                "operator_view_port": 0,
                "operator_view_ready": False,
                "operator_view_status": "disabled",
                "operator_view_failure_class": "",
                "validation_dir": "",
                "command_history_path": "",
                "multi_target_progress_path": "",
                "motion_evidence": False,
                "latest_artifacts": {},
                "operator_status_path": "",
                "world_stream_restart_attempts": 0,
                "world_stream_last_restart_utc": "",
                "world_stream_last_restart_error": "",
                "world_stream_recovery_state": "idle",
                "world_stream_restart_in_progress": False,
                "world_stream_restart_cooldown_s": WORLD_STREAM_RESTART_COOLDOWN_S,
                "world_stream_restart_max_attempts": WORLD_STREAM_RESTART_MAX_ATTEMPTS,
                "startup_retry_count": 0,
                "startup_cleanup_count": 0,
                "startup_last_cleanup_projects": [],
                "lock_file": str(self.lock_path),
                "runtime_dir": str(self.runtime_dir),
                "headless_worker_mode": self.headless_worker_mode,
                "scenarios": [item.to_api() for item in SCENARIOS],
            }
        self._persist_state_locked()
        self._clear_llm_proof_runtime_state()
        self._clear_visit_mission_runtime_state()
        self._clear_gather_mission_runtime_state()
        self._refresh_control_plane_state(force=True)
        self.world_stream_watchdog_thread = threading.Thread(
            target=self._world_stream_watchdog_loop,
            name="dashboard-world-stream-watchdog",
            daemon=True,
        )
        self.world_stream_watchdog_thread.start()

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
        write_json(self.state_path, self.state)

    def _update_state(self, **updates: Any) -> None:
        with self.state_lock:
            self.state.update(updates)
            self._persist_state_locked()

    def _lifecycle_busy(self) -> bool:
        thread = self.lifecycle_thread
        if thread is not None and not thread.is_alive():
            self.lifecycle_thread = None
        return self.lifecycle_lock.locked()

    def _scenario_requires_clean_reset(self, scenario: ScenarioDefinition) -> bool:
        return scenario.id in SELF_CONTAINED_SCENARIO_IDS

    def _normalize_world_file(self, raw_value: str, *, default_value: str) -> str:
        candidate = str(raw_value or "").strip() or str(default_value or "").strip() or DEFAULT_WORLD_FILE
        candidate_path = Path(candidate)
        if not candidate_path.is_absolute():
            candidate_path = (REPO_ROOT / "ros2_config" / "worlds" / candidate).resolve()
        if not candidate_path.exists():
            raise ValueError(f"unknown world_file: {candidate}")
        return candidate_path.name

    def _normalize_surface_profile(self, raw_value: str, *, default_value: str) -> str:
        candidate = str(raw_value or "").strip() or str(default_value or "").strip() or DEFAULT_SURFACE_PROFILE
        return candidate.replace(" ", "_")

    def _scenario_pending_world_file(self) -> str:
        pending_scenario = SCENARIOS_BY_ID.get(str(self.pending_scenario_id or "").strip())
        default_world = pending_scenario.world_file if pending_scenario is not None else DEFAULT_WORLD_FILE
        pending_overrides = getattr(self, "pending_scenario_overrides", {}) or {}
        return self._normalize_world_file(str(pending_overrides.get("world_file", "") or ""), default_value=default_world)

    def _scenario_pending_surface_profile(self) -> str:
        pending_scenario = SCENARIOS_BY_ID.get(str(self.pending_scenario_id or "").strip())
        default_surface = pending_scenario.surface_profile if pending_scenario is not None else DEFAULT_SURFACE_PROFILE
        pending_overrides = getattr(self, "pending_scenario_overrides", {}) or {}
        return self._normalize_surface_profile(str(pending_overrides.get("surface_profile", "") or ""), default_value=default_surface)

    def _launch_scenario_thread(self, scenario: ScenarioDefinition) -> None:
        self.scenario_cancel.clear()
        self.scenario_thread = threading.Thread(
            target=self._scenario_worker,
            args=(scenario,),
            name=f"dashboard-scenario-{scenario.id}",
            daemon=True,
        )
        self.scenario_thread.start()

    def _start_pending_scenario_if_any(self) -> None:
        pending_scenario_id = str(self.pending_scenario_id or "").strip()
        if not pending_scenario_id:
            return
        self.pending_scenario_id = ""
        self.pending_scenario_overrides = {}
        scenario = SCENARIOS_BY_ID.get(pending_scenario_id)
        if scenario is None:
            return
        self._record_operator_event(f"{scenario.label} auto-starting after sim reset.", category="scenario")
        self._launch_scenario_thread(scenario)

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

    def _current_operator_view_state_path(self) -> Optional[Path]:
        visual_dir = self._current_visual_dir()
        if visual_dir is None:
            return None
        return visual_dir / "operator_view_state.json"

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

    def _llm_proof_runtime_state(self) -> Dict[str, Any]:
        payload = read_json(self.llm_proof_runtime_path)
        return payload if isinstance(payload, dict) else {}

    def _write_llm_proof_runtime_state(self, payload: Dict[str, Any]) -> None:
        write_json(self.llm_proof_runtime_path, payload)

    def _clear_llm_proof_runtime_state(self) -> None:
        self._write_llm_proof_runtime_state(
            {
                "running": False,
                "scenario_id": "",
                "session_id": "",
                "proof_state": "waiting",
                "latest_operator_event": "",
                "recent_operator_events": [],
                "latest_decision": {},
                "latest_feedback": "",
                "artifact_dir": "",
                "proof_verdict": {},
                "updated_utc": utc_now(),
            }
        )

    def _visit_mission_runtime_state(self) -> Dict[str, Any]:
        payload = read_json(self.visit_mission_runtime_path)
        return payload if isinstance(payload, dict) else {}

    def _write_visit_mission_runtime_state(self, payload: Dict[str, Any]) -> None:
        write_json(self.visit_mission_runtime_path, payload)

    def _clear_visit_mission_runtime_state(self) -> None:
        self._write_visit_mission_runtime_state(
            {
                "running": False,
                "scenario_id": "",
                "session_id": "",
                "proof_state": "waiting",
                "mission_phase": "idle",
                "mission_status": "idle",
                "search_bias_active": False,
                "current_target_id": "",
                "visit_index": 0,
                "visited_targets": [],
                "remaining_targets": [],
                "last_visit_result": {},
                "mission_verdict": {},
                "latest_operator_event": "",
                "recent_operator_events": [],
                "latest_decision": {},
                "latest_feedback": "",
                "artifact_dir": "",
                "updated_utc": utc_now(),
            }
        )

    def _gather_mission_runtime_state(self) -> Dict[str, Any]:
        payload = read_json(self.gather_mission_runtime_path)
        return payload if isinstance(payload, dict) else {}

    def _write_gather_mission_runtime_state(self, payload: Dict[str, Any]) -> None:
        write_json(self.gather_mission_runtime_path, payload)

    def _clear_gather_mission_runtime_state(self) -> None:
        self._write_gather_mission_runtime_state(
            {
                "running": False,
                "scenario_id": "",
                "session_id": "",
                "mission_phase": "idle",
                "mission_status": "idle",
                "gather_phase": "idle",
                "current_target_id": "",
                "visit_index": 0,
                "placed_targets": [],
                "remaining_targets": [],
                "route_order": [],
                "capture_state": {},
                "capture_loss_count": 0,
                "zone_pose": {},
                "zone_score": {},
                "final_corral_audit": {},
                "latest_control_command": {},
                "latest_feedback": "",
                "mission_verdict": {},
                "latest_operator_event": "",
                "recent_operator_events": [],
                "artifact_dir": "",
                "updated_utc": utc_now(),
            }
        )

    def _record_operator_event(self, message: str, *, category: str = "info", source: str = "dashboard") -> None:
        event = {
            "timestamp_utc": utc_now(),
            "message": str(message),
            "category": str(category),
            "source": str(source),
        }
        with self.state_lock:
            events = list(self.state.get("recent_operator_events", []))
            if events and str(events[-1].get("message", "")) == event["message"]:
                return
            events.append(event)
            self.state["recent_operator_events"] = events[-20:]
            self.state["latest_operator_event"] = event["message"]
            self._persist_state_locked()

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

    def _docker_service_state(self, project_name: str, service_name: str) -> Dict[str, Any]:
        ids = self._docker_find_container_ids(project_name=project_name, service_name=service_name, include_stopped=True)
        if not ids:
            return {"service": service_name, "status": "missing", "container_id": ""}
        container_id = ids[0]
        status = "unknown"
        try:
            inspect_payload = self._docker_inspect(container_id)
            state_payload = inspect_payload.get("State", {})
            if isinstance(state_payload, dict):
                status = str(state_payload.get("Status", "") or "").strip().lower() or "unknown"
        except Exception:
            status = "unknown"
        return {"service": service_name, "status": status, "container_id": container_id}

    def _required_gate_service_states(self, project_name: str) -> Dict[str, Dict[str, Any]]:
        required_services = self._required_gate_services()
        return {
            service_name: self._docker_service_state(project_name, service_name)
            for service_name in required_services
        }

    def _gate_services_ready(self, gate_service_states: Dict[str, Dict[str, Any]]) -> bool:
        if not gate_service_states:
            return False
        required_services = self._required_gate_services()
        return all(
            str(gate_service_states.get(service_name, {}).get("status", "missing") or "missing") == "running"
            for service_name in required_services
        )

    def _classify_gate_service_states(self, gate_service_states: Dict[str, Dict[str, Any]]) -> tuple[str, str]:
        required_services = self._required_gate_services()
        missing = [
            service_name
            for service_name in required_services
            if str(gate_service_states.get(service_name, {}).get("status", "missing") or "missing") == "missing"
        ]
        if missing:
            return "gate_services_missing", f"Required gate services missing: {', '.join(missing)}."
        not_running = [
            f"{service_name}={str(gate_service_states.get(service_name, {}).get('status', 'unknown') or 'unknown')}"
            for service_name in required_services
            if str(gate_service_states.get(service_name, {}).get("status", "missing") or "missing") != "running"
        ]
        if not_running:
            return "gate_services_not_running", f"Required gate services not running: {', '.join(not_running)}."
        return "", ""

    def _wait_for_required_gate_services(self, project_name: str, timeout_s: float) -> Dict[str, Dict[str, Any]]:
        deadline = time.monotonic() + max(timeout_s, 1.0)
        latest_states: Dict[str, Dict[str, Any]] = {}
        while time.monotonic() < deadline:
            latest_states = self._required_gate_service_states(project_name)
            self._update_state(gate_service_states=latest_states)
            if self._gate_services_ready(latest_states):
                return latest_states
            if self.lifecycle_cancel.is_set():
                return latest_states
            time.sleep(GATE_SERVICE_POLL_S)
        latest_states = self._required_gate_service_states(project_name)
        self._update_state(gate_service_states=latest_states)
        return latest_states

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
        state = self._docker_service_state(project_name, service_name)
        return str(state.get("container_id", "") or "")

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

    def _list_dashboard_projects(self, *, include_stopped: bool = True) -> list[str]:
        if not self._docker_enabled():
            return []
        cmd = [self.docker, "ps"]
        if include_stopped:
            cmd.append("-a")
        cmd.extend(["--format", '{{.Label "com.docker.compose.project"}}'])
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return []
        projects: list[str] = []
        seen: set[str] = set()
        for raw in proc.stdout.splitlines():
            project_name = raw.strip()
            if not project_name or not project_name.startswith(SESSION_PROJECT_PREFIX) or project_name in seen:
                continue
            seen.add(project_name)
            projects.append(project_name)
        return projects

    def _cleanup_stale_dashboard_projects(self, *, current_project: str = "") -> list[str]:
        if self.peer_project_cleanup == "none":
            return []
        projects = self._list_dashboard_projects(include_stopped=True)
        stale_projects = [name for name in projects if name != current_project]
        for project_name in stale_projects:
            self._force_remove_project_resources(project_name)
        return stale_projects

    def _required_gate_services(self) -> tuple[str, ...]:
        return HEADLESS_SOAK_GATE_SERVICES if self.headless_worker_mode else REQUIRED_GATE_SERVICES

    def _extract_host_port_bind_failure_port(self, output: str) -> Optional[int]:
        match = HOST_PORT_BIND_FAILURE_RE.search(output or "")
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

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

    def _operator_view_snapshot(self, visual_dir: Optional[Path], fallback: Dict[str, Any]) -> Dict[str, Any]:
        operator_view_state = read_json(visual_dir / "operator_view_state.json") if visual_dir else {}
        snapshot = {
            "backend": str(operator_view_state.get("backend", fallback.get("operator_view_backend", "xpra")) or "xpra"),
            "url": str(operator_view_state.get("url", fallback.get("operator_view_url", "")) or ""),
            "port": int(operator_view_state.get("port", fallback.get("operator_view_port", 0)) or 0),
            "ready": bool(operator_view_state.get("ready", fallback.get("operator_view_ready", False))),
            "status": str(operator_view_state.get("status", fallback.get("operator_view_status", "disabled")) or "disabled"),
            "failure_class": str(
                operator_view_state.get("failure_class", fallback.get("operator_view_failure_class", "")) or ""
            ),
            "latest_heartbeat_utc": str(operator_view_state.get("latest_heartbeat_utc", "") or ""),
            "apps": operator_view_state.get("apps", {}),
        }
        heartbeat = parse_utc_timestamp(snapshot["latest_heartbeat_utc"])
        if snapshot["ready"] and heartbeat is not None:
            age_s = (datetime.now(timezone.utc) - heartbeat.astimezone(timezone.utc)).total_seconds()
            if age_s > OPERATOR_VIEW_HEARTBEAT_STALE_S:
                snapshot["ready"] = False
                snapshot["status"] = "stale"
                if not snapshot["failure_class"]:
                    snapshot["failure_class"] = "operator_view_stale"
        if not snapshot["ready"]:
            snapshot["url"] = ""
        return snapshot

    def _world_stream_path(self, visual_dir: Optional[Path], world_state: Dict[str, Any]) -> Optional[Path]:
        if visual_dir is None:
            return None
        screenshot_path = str(world_state.get("screenshot_path", "") or "").strip()
        if screenshot_path:
            try:
                return Path(screenshot_path)
            except Exception:
                pass
        return visual_dir / "live" / "world_stream.jpg"

    def _world_stream_snapshot(self, visual_dir: Optional[Path], world_state: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        latest_frame_age = world_state.get("latest_frame_age_s")
        latest_frame_age_s = float(latest_frame_age) if latest_frame_age not in {None, ""} else None
        received_frame_count = int(world_state.get("received_frame_count", world_state.get("frame_count", 0)) or 0)
        session_matches = str(world_state.get("session_id", "") or "") == str(session_id or "")
        same_session_partition = bool(world_state.get("same_session_partition", False)) and session_matches
        latest_frame_error = str(world_state.get("latest_frame_error", "") or "")
        frames_stale = bool(world_state.get("frames_stale", False))

        world_stream_ready = bool(world_state.get("world_stream_ready", False))

        world_stream_transport_healthy = world_state.get("world_stream_transport_healthy")
        if world_stream_transport_healthy is None:
            world_stream_transport_healthy = bool(
                same_session_partition
                and received_frame_count >= WORLD_STREAM_TRANSPORT_MIN_FRAMES
                and latest_frame_age_s is not None
                and latest_frame_age_s <= max(WORLD_STREAM_TRANSPORT_MAX_AGE_S, 0.1)
                and not latest_frame_error
                and not frames_stale
            )
        else:
            world_stream_transport_healthy = bool(world_stream_transport_healthy)

        world_stream_renderable = world_state.get("world_stream_renderable")
        if world_stream_renderable is None:
            frame_path = self._world_stream_path(visual_dir, world_state)
            world_stream_renderable = bool(
                same_session_partition
                and received_frame_count >= 1
                and latest_frame_age_s is not None
                and latest_frame_age_s <= max(WORLD_STREAM_RENDERABLE_GRACE_S, 0.1)
                and frame_path is not None
                and frame_path.exists()
            )
        else:
            world_stream_renderable = bool(world_stream_renderable)

        world_stream_degraded = world_state.get("world_stream_degraded")
        if world_stream_degraded is None:
            world_stream_degraded = bool(
                world_stream_renderable and (not world_stream_transport_healthy or not world_stream_ready)
            )
        else:
            world_stream_degraded = bool(world_stream_degraded)

        return {
            "world_stream_ready": world_stream_ready,
            "world_stream_renderable": world_stream_renderable,
            "world_stream_transport_healthy": world_stream_transport_healthy,
            "world_stream_degraded": world_stream_degraded,
            "world_stream_frame_count": received_frame_count,
            "world_stream_latest_frame_utc": str(world_state.get("latest_frame_utc", "") or ""),
            "world_stream_frame_age_s": latest_frame_age_s,
            "world_stream_frames_stale": frames_stale,
            "world_stream_viewer_process_healthy": bool(world_state.get("viewer_process_healthy", False)),
            "world_stream_failure_class": str(world_state.get("failure_class", "") or ""),
            "world_stream_url": str(world_state.get("world_stream_url", "") or ""),
            "scene_content_ok": bool(world_state.get("scene_content_ok", False)),
            "robot_visible_ok": bool(world_state.get("robot_visible_ok", False)),
            "target_visible_ok": bool(world_state.get("target_visible_ok", False)),
            "same_session_partition": same_session_partition,
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
        operator_view = self._operator_view_snapshot(visual_dir, snapshot)

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
        snapshot["latest_truth_target_model_name"] = str(visual_state.get("latest_truth_target_model_name", "") or "")
        snapshot["target_visible_ratio"] = float(visual_state.get("target_visible_ratio", 0.0) or 0.0)
        snapshot["overlay_difference_ok"] = bool(visual_state.get("overlay_difference_ok", False))
        world_snapshot = self._world_stream_snapshot(visual_dir, world_state, str(snapshot.get("session_id", "") or ""))
        snapshot["world_stream_ready"] = world_snapshot["world_stream_ready"]
        snapshot["world_stream_renderable"] = world_snapshot["world_stream_renderable"]
        snapshot["world_stream_transport_healthy"] = world_snapshot["world_stream_transport_healthy"]
        snapshot["world_stream_degraded"] = world_snapshot["world_stream_degraded"]
        snapshot["scene_content_ok"] = world_snapshot["scene_content_ok"]
        snapshot["robot_visible_ok"] = world_snapshot["robot_visible_ok"]
        snapshot["target_visible_ok"] = world_snapshot["target_visible_ok"]
        snapshot["same_session_partition"] = world_snapshot["same_session_partition"]
        snapshot["world_stream_frame_count"] = world_snapshot["world_stream_frame_count"]
        snapshot["world_stream_latest_frame_utc"] = world_snapshot["world_stream_latest_frame_utc"]
        snapshot["world_stream_frame_age_s"] = world_snapshot["world_stream_frame_age_s"]
        snapshot["world_stream_frames_stale"] = world_snapshot["world_stream_frames_stale"]
        snapshot["world_stream_viewer_process_healthy"] = world_snapshot["world_stream_viewer_process_healthy"]
        snapshot["world_stream_failure_class"] = world_snapshot["world_stream_failure_class"]
        snapshot["world_stream_url"] = world_snapshot["world_stream_url"] or snapshot.get("world_stream_url", "")
        snapshot["world_stream_interactive"] = bool(world_state.get("world_stream_interactive", False))
        snapshot["operator_view_backend"] = operator_view["backend"]
        snapshot["operator_view_url"] = operator_view["url"]
        snapshot["operator_view_port"] = operator_view["port"]
        snapshot["operator_view_ready"] = operator_view["ready"]
        snapshot["operator_view_status"] = operator_view["status"]
        snapshot["operator_view_failure_class"] = operator_view["failure_class"]
        snapshot["robot_truth_seen"] = bool(truth_state.get("robot_truth_seen", False))
        snapshot["live_paths"] = {
            "raw_camera": "live/raw_camera.jpg",
            "yolo_debug": "live/yolo_debug.jpg",
            "topdown_telemetry": "live/topdown_telemetry.jpg",
            "world_stream": "live/world_stream.jpg",
        }

        latest_detection_world = (
            visual_state.get("latest_detection_world")
            if isinstance(visual_state.get("latest_detection_world"), dict)
            else brain_state.get("latest_detection_world")
        )
        latest_truth_target_world = (
            visual_state.get("latest_truth_target_world")
            if isinstance(visual_state.get("latest_truth_target_world"), dict)
            else _truth_world_xy(truth_state.get("true_target_pose") if isinstance(truth_state.get("true_target_pose"), dict) else {})
        )
        latest_truth_target_model_name = str(
            visual_state.get("latest_truth_target_model_name", "")
            or truth_state.get("target_model_name", "")
            or ""
        )
        latest_robot_pose = (
            visual_state.get("latest_robot_pose")
            if isinstance(visual_state.get("latest_robot_pose"), dict)
            else brain_state.get("latest_robot_pose")
        )
        if not isinstance(latest_robot_pose, dict):
            latest_robot_pose = _truth_robot_pose(
                truth_state.get("robot_truth_pose") if isinstance(truth_state.get("robot_truth_pose"), dict) else {}
            )

        perception = {
            "detection_topic_seen": bool(visual_state.get("detection_topic_seen", False)),
            "target_visible_now": bool(visual_state.get("target_visible_now", False)),
            "target_visible_ratio": float(visual_state.get("target_visible_ratio", 0.0) or 0.0),
            "latest_detection_world": latest_detection_world,
            "latest_truth_target_world": latest_truth_target_world,
            "latest_truth_target_model_name": latest_truth_target_model_name,
            "truth_alignment_ok": bool(visual_state.get("truth_alignment_ok", False)),
            "truth_status": "aligned" if visual_state.get("truth_alignment_ok", False) else (visual_state.get("truth_failure_class") or "truth unavailable"),
        }
        belief = {
            "latest_robot_pose": latest_robot_pose,
            "robot_pose_available": isinstance(latest_robot_pose, dict) and bool(latest_robot_pose),
            "latest_goal_pose": visual_state.get("latest_goal_pose"),
            "latest_target_distance_m": visual_state.get("latest_target_distance_m", brain_state.get("latest_target_distance_m")),
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
            "nav2_server_ready": bool(brain_state.get("nav2_server_ready", False)),
            "last_feedback_status": str(brain_state.get("last_feedback_status", "") or ""),
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
        snapshot["sim_gate_ready"] = bool(self.sim_gate_container_id)
        snapshot["policy"] = build_policy_snapshot(snapshot, sim_gate_ready=bool(self.sim_gate_container_id))
        snapshot["demo_story"] = demo_story
        snapshot["llm_supervisor"] = self._llm_supervisor_state()

        proof_runtime = self._llm_proof_runtime_state()
        visit_runtime = self._visit_mission_runtime_state()
        gather_runtime = self._gather_mission_runtime_state()
        proof_verdict = proof_runtime.get("proof_verdict", {}) if isinstance(proof_runtime.get("proof_verdict"), dict) else {}
        proof_state = str(proof_runtime.get("proof_state", "") or "").strip()
        visit_verdict = visit_runtime.get("mission_verdict", {}) if isinstance(visit_runtime.get("mission_verdict"), dict) else {}
        gather_verdict = gather_runtime.get("mission_verdict", {}) if isinstance(gather_runtime.get("mission_verdict"), dict) else {}
        active_scenario_id = str(snapshot.get("active_scenario", "") or "")
        active_scenario = SCENARIOS_BY_ID.get(active_scenario_id)
        active_mode = active_scenario.mode if active_scenario else ""
        snapshot["active_scenario_label"] = active_scenario.label if active_scenario else ""
        if not active_mode:
            mission_verdict_type = ""
            if isinstance(snapshot.get("mission_verdict"), dict):
                mission_verdict_type = str(snapshot.get("mission_verdict", {}).get("type", "") or "")
            if mission_verdict_type == "gather_mission":
                active_mode = "gather_mission"
            elif mission_verdict_type == "visit_mission":
                active_mode = "visit_mission"
        if not proof_state:
            if snapshot.get("active_scenario") == "llm_turn_then_go_proof" and snapshot.get("scenario_state") == "running":
                proof_state = "searching" if brain.get("search_active") else "waiting"
            elif proof_verdict:
                proof_state = "completed" if proof_verdict.get("pass") else "failed"
            else:
                proof_state = "waiting"
        if active_mode == "visit_mission":
            proof_state = str(visit_runtime.get("proof_state", "") or "").strip() or proof_state
            if visit_verdict:
                proof_verdict = visit_verdict
        elif active_mode == "gather_mission":
            proof_state = str(visit_runtime.get("proof_state", "") or gather_runtime.get("proof_state", "") or "").strip() or proof_state
            if gather_verdict:
                proof_verdict = gather_verdict

        operator_events = snapshot.get("recent_operator_events", [])
        if not isinstance(operator_events, list):
            operator_events = []
        proof_events = proof_runtime.get("recent_operator_events", [])
        if not isinstance(proof_events, list):
            proof_events = []
        visit_events = visit_runtime.get("recent_operator_events", [])
        if not isinstance(visit_events, list):
            visit_events = []
        gather_events = gather_runtime.get("recent_operator_events", [])
        if not isinstance(gather_events, list):
            gather_events = []
        merged_events = []
        seen_event_keys = set()
        for item in operator_events + proof_events + visit_events + gather_events:
            if isinstance(item, dict) and item.get("message"):
                event_key = (
                    str(item.get("timestamp_utc", "") or ""),
                    str(item.get("source", "") or ""),
                    str(item.get("category", "") or ""),
                    str(item.get("message", "") or ""),
                )
                if event_key in seen_event_keys:
                    continue
                seen_event_keys.add(event_key)
                merged_events.append(item)
        if merged_events:
            merged_events = sorted(merged_events, key=lambda item: str(item.get("timestamp_utc", "")))[-20:]
        operator_events = merged_events
        latest_operator_event = str(snapshot.get("latest_operator_event", "") or "")
        if operator_events:
            latest_payload = operator_events[-1] if isinstance(operator_events[-1], dict) else {}
            latest_operator_event = str(latest_payload.get("message", latest_operator_event) or latest_operator_event)

        snapshot["proof_state"] = proof_state
        snapshot["proof_verdict"] = proof_verdict
        snapshot["latest_operator_event"] = latest_operator_event
        snapshot["recent_operator_events"] = operator_events
        if active_mode == "visit_mission":
            snapshot["latest_proof_decision"] = visit_runtime.get("latest_decision", {}) if isinstance(visit_runtime.get("latest_decision"), dict) else {}
            snapshot["latest_proof_feedback"] = str(visit_runtime.get("latest_feedback", "") or "")
            snapshot["proof_artifact_dir"] = str(visit_runtime.get("artifact_dir", "") or "")
        elif active_mode == "gather_mission":
            snapshot["latest_proof_decision"] = visit_runtime.get("latest_decision", {}) if isinstance(visit_runtime.get("latest_decision"), dict) else {}
            snapshot["latest_proof_feedback"] = str(gather_runtime.get("latest_feedback", "") or visit_runtime.get("latest_feedback", "") or "")
            snapshot["proof_artifact_dir"] = str(gather_runtime.get("artifact_dir", "") or visit_runtime.get("artifact_dir", "") or "")
        else:
            snapshot["latest_proof_decision"] = proof_runtime.get("latest_decision", {}) if isinstance(proof_runtime.get("latest_decision"), dict) else {}
            snapshot["latest_proof_feedback"] = str(proof_runtime.get("latest_feedback", "") or "")
            snapshot["proof_artifact_dir"] = str(proof_runtime.get("artifact_dir", "") or "")

        mission_runtime = gather_runtime if active_mode == "gather_mission" else visit_runtime
        snapshot["mission_phase"] = str(mission_runtime.get("mission_phase", snapshot.get("mission_phase", "idle")) or "idle")
        snapshot["mission_status"] = str(mission_runtime.get("mission_status", snapshot.get("mission_status", "idle")) or "idle")
        snapshot["search_bias_active"] = bool(visit_runtime.get("search_bias_active", snapshot.get("search_bias_active", False)))
        current_target_id = str(mission_runtime.get("current_target_id", visit_runtime.get("current_target_id", snapshot.get("current_target_id", ""))) or "")
        if active_mode in {"visit_mission", "gather_mission"} and snapshot["mission_status"] != "running":
            current_target_id = ""
        snapshot["current_target_id"] = current_target_id
        snapshot["visit_index"] = int(mission_runtime.get("visit_index", visit_runtime.get("visit_index", snapshot.get("visit_index", 0))) or 0)
        snapshot["visited_targets"] = list(visit_runtime.get("visited_targets", snapshot.get("visited_targets", [])) or [])
        snapshot["remaining_targets"] = list(mission_runtime.get("remaining_targets", visit_runtime.get("remaining_targets", snapshot.get("remaining_targets", []))) or [])
        snapshot["last_visit_result"] = visit_runtime.get("last_visit_result", snapshot.get("last_visit_result", {})) if isinstance(visit_runtime.get("last_visit_result", snapshot.get("last_visit_result", {})), dict) else {}
        snapshot["mission_verdict"] = gather_verdict if active_mode == "gather_mission" and gather_verdict else visit_verdict
        snapshot["route_planning_active"] = bool(visit_runtime.get("route_planning_active", False))
        snapshot["route_target_specs"] = list(visit_runtime.get("route_target_specs", [])) if isinstance(visit_runtime.get("route_target_specs"), list) else []
        snapshot["gather_phase"] = str(gather_runtime.get("gather_phase", snapshot.get("gather_phase", "idle")) or "idle")
        snapshot["capture_state"] = gather_runtime.get("capture_state", snapshot.get("capture_state", {})) if isinstance(gather_runtime.get("capture_state", snapshot.get("capture_state", {})), dict) else {}
        snapshot["zone_pose"] = gather_runtime.get("zone_pose", snapshot.get("zone_pose", {})) if isinstance(gather_runtime.get("zone_pose", snapshot.get("zone_pose", {})), dict) else {}
        snapshot["zone_score"] = gather_runtime.get("zone_score", snapshot.get("zone_score", {})) if isinstance(gather_runtime.get("zone_score", snapshot.get("zone_score", {})), dict) else {}
        snapshot["final_corral_audit"] = gather_runtime.get(
            "final_corral_audit",
            gather_verdict.get("final_corral_audit", snapshot.get("final_corral_audit", {})),
        ) if isinstance(
            gather_runtime.get("final_corral_audit", gather_verdict.get("final_corral_audit", snapshot.get("final_corral_audit", {}))),
            dict,
        ) else {}
        snapshot["placed_targets"] = list(gather_runtime.get("placed_targets", snapshot.get("placed_targets", [])) or [])
        snapshot["capture_loss_count"] = int(gather_runtime.get("capture_loss_count", snapshot.get("capture_loss_count", 0)) or 0)
        snapshot["route_order"] = list(gather_runtime.get("route_order", snapshot.get("route_order", [])) or [])
        snapshot["surface_profile"] = str(gather_runtime.get("surface_profile", snapshot.get("surface_profile", DEFAULT_SURFACE_PROFILE)) or DEFAULT_SURFACE_PROFILE)
        if active_mode in {"visit_mission", "gather_mission"} and snapshot["current_target_id"]:
            snapshot["target_id"] = snapshot["current_target_id"]
        snapshot["policy"] = build_policy_snapshot(snapshot, sim_gate_ready=bool(self.sim_gate_container_id))

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

    def _normalize_robot_sdf_name(self, raw_value: str, *, default_value: str) -> str:
        candidate = str(raw_value or "").strip() or str(default_value or "").strip() or BASELINE_ROBOT_SDF_NAME
        candidate_path = REPO_ROOT / "ros2_config" / "urdf" / candidate
        if not candidate_path.exists():
            raise ValueError(f"unknown robot_sdf_name: {candidate}")
        return candidate_path.name

    def _resolve_environment_profile(self, overrides: Optional[Dict[str, Any]] = None) -> tuple[str, str, str]:
        payload = dict(overrides or {})
        scenario_id = str(payload.get("scenario_id", "") or "").strip()
        scenario = SCENARIOS_BY_ID.get(scenario_id) if scenario_id else None
        with self.state_lock:
            state_world = str(self.state.get("world_file", "") or DEFAULT_WORLD_FILE)
            state_surface = str(self.state.get("surface_profile", "") or DEFAULT_SURFACE_PROFILE)
            state_robot = str(self.state.get("robot_sdf_name", "") or BASELINE_ROBOT_SDF_NAME)
        default_world = scenario.world_file if scenario is not None else state_world
        default_surface = scenario.surface_profile if scenario is not None else state_surface
        default_robot = scenario.robot_sdf_name if scenario is not None else state_robot
        world_file = self._normalize_world_file(str(payload.get("world_file", "") or ""), default_value=default_world)
        surface_profile = self._normalize_surface_profile(str(payload.get("surface_profile", "") or ""), default_value=default_surface)
        robot_sdf_name = self._normalize_robot_sdf_name(str(payload.get("robot_sdf_name", "") or ""), default_value=default_robot)
        return world_file, surface_profile, robot_sdf_name

    def request_start(self, overrides: Optional[Dict[str, Any]] = None) -> tuple[int, Dict[str, Any]]:
        with self.state_lock:
            env_state = self.state["environment_state"]
        if env_state == "environment_ready":
            return HTTPStatus.OK, {"accepted": False, "message": "environment already ready", "state": self.get_state()}
        if env_state == "starting":
            return HTTPStatus.OK, {"accepted": False, "message": "environment start already in progress", "state": self.get_state()}
        try:
            world_file, surface_profile, robot_sdf_name = self._resolve_environment_profile(overrides)
        except ValueError as exc:
            return HTTPStatus.BAD_REQUEST, {"accepted": False, "error": str(exc)}
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
            environment_failure_class="",
            gate_service_states={},
            scenario_message="",
            last_error="",
            phase="starting",
            world_file=world_file,
            surface_profile=surface_profile,
            robot_sdf_name=robot_sdf_name,
            target_id="",
            target_transition_active=False,
            world_stream_recovery_state="idle",
            world_stream_restart_in_progress=False,
        )
        self._record_operator_event("Environment starting.", category="environment")
        self.lifecycle_thread = threading.Thread(target=self._start_environment_worker, name="dashboard-start", daemon=True)
        self.lifecycle_thread.start()
        return HTTPStatus.ACCEPTED, {"accepted": True, "message": "environment start queued"}

    def request_stop(self) -> tuple[int, Dict[str, Any]]:
        with self.state_lock:
            env_state = self.state["environment_state"]
        if env_state == "stopped":
            return HTTPStatus.OK, {"accepted": False, "message": "environment already stopped", "state": self.get_state()}
        if env_state == "starting":
            self.pending_scenario_id = ""
            self.lifecycle_cancel.set()
            self._terminate_process(self.active_env_proc)
            self._update_state(environment_message="stop requested during startup")
            self._record_operator_event("Environment stop requested during startup.", category="environment")
            return HTTPStatus.ACCEPTED, {"accepted": True, "message": "startup cancellation requested"}
        self._refresh_control_plane_state(force=True)
        with self.state_lock:
            if not self.state.get("control_plane_ready", False):
                return self._control_plane_unavailable_response()
        if self._lifecycle_busy():
            return HTTPStatus.CONFLICT, {"accepted": False, "error": "lifecycle busy"}
        self.pending_scenario_id = ""
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

    def request_reset_sim(self, overrides: Optional[Dict[str, Any]] = None) -> tuple[int, Dict[str, Any]]:
        with self.state_lock:
            env_state = self.state["environment_state"]
        if env_state not in {"environment_ready", "error"}:
            return HTTPStatus.CONFLICT, {"accepted": False, "error": "environment not ready for reset"}
        try:
            world_file, surface_profile, robot_sdf_name = self._resolve_environment_profile(overrides)
        except ValueError as exc:
            return HTTPStatus.BAD_REQUEST, {"accepted": False, "error": str(exc)}
        self._refresh_control_plane_state(force=True)
        with self.state_lock:
            if not self.state.get("control_plane_ready", False):
                return self._control_plane_unavailable_response()
        if self._lifecycle_busy():
            return HTTPStatus.CONFLICT, {"accepted": False, "error": "lifecycle busy"}
        self.pending_scenario_id = ""
        self.pending_scenario_overrides = {}
        self._update_state(
            world_file=world_file,
            surface_profile=surface_profile,
            robot_sdf_name=robot_sdf_name,
        )
        self.lifecycle_thread = threading.Thread(target=self._reset_environment_worker, name="dashboard-reset", daemon=True)
        self.lifecycle_thread.start()
        return HTTPStatus.ACCEPTED, {"accepted": True, "message": "sim reset queued"}

    def request_scenario_run(self, scenario_id: str, overrides: Optional[Dict[str, Any]] = None) -> tuple[int, Dict[str, Any]]:
        scenario = SCENARIOS_BY_ID.get(scenario_id)
        if scenario is None:
            return HTTPStatus.BAD_REQUEST, {"accepted": False, "error": f"unknown scenario: {scenario_id}"}
        overrides = dict(overrides or {})
        try:
            world_file = self._normalize_world_file(str(overrides.get("world_file", "") or ""), default_value=scenario.world_file)
            surface_profile = self._normalize_surface_profile(str(overrides.get("surface_profile", "") or ""), default_value=scenario.surface_profile)
        except ValueError as exc:
            return HTTPStatus.BAD_REQUEST, {"accepted": False, "error": str(exc)}
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
        if self._scenario_requires_clean_reset(scenario):
            if self._lifecycle_busy():
                return HTTPStatus.CONFLICT, {"accepted": False, "error": "lifecycle busy"}
            self.pending_scenario_id = scenario_id
            self.pending_scenario_overrides = {
                "world_file": world_file,
                "surface_profile": surface_profile,
            }
            self._record_operator_event(f"{scenario.label} queued after sim reset.", category="scenario")
            self._update_state(
                scenario_message=f"{scenario.label} queued after sim reset",
                world_file=world_file,
                surface_profile=surface_profile,
            )
            self.lifecycle_thread = threading.Thread(target=self._reset_environment_worker, name="dashboard-reset", daemon=True)
            self.lifecycle_thread.start()
            return HTTPStatus.ACCEPTED, {
                "accepted": True,
                "message": f"scenario {scenario_id} queued after sim reset",
                "world_file": world_file,
                "surface_profile": surface_profile,
            }
        if world_file != scenario.world_file or surface_profile != scenario.surface_profile:
            return HTTPStatus.CONFLICT, {
                "accepted": False,
                "error": "scenario world override requires a clean-reset scenario",
            }
        self._launch_scenario_thread(scenario)
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
        self._record_operator_event("Scenario stop requested.", category="scenario")
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
        write_json(self.lock_path, payload)

    def _remove_lock_file(self) -> None:
        try:
            self.lock_path.unlink()
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
        return intent_readiness_snapshot(intent_name, state, sim_gate_ready=bool(self.sim_gate_container_id))

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

    def _docker_image_exists(self, image_ref: str) -> bool:
        proc = subprocess.run(
            [self.docker, "image", "inspect", image_ref],
            cwd=str(REPO_ROOT),
            env=self._compose_env(),
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.returncode == 0

    def _required_gate_image_refs(self, env: Optional[Dict[str, str]] = None) -> tuple[str, ...]:
        compose_env = self._compose_env(env)
        ros_distro = str(compose_env.get("CORE_ROS_DISTRO", DEFAULT_CORE_ROS_DISTRO) or DEFAULT_CORE_ROS_DISTRO)
        return (
            f"chasecar/sim-gate:{ros_distro}",
            f"chasecar/core-kilted:{ros_distro}",
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

    def _expected_truth_target_candidates(self) -> set[str]:
        return {str(item).strip() for item in TRUTH_TARGET_MODEL_NAMES if str(item).strip()}

    def _truth_state_target_candidates(self, state: Dict[str, Any]) -> set[str]:
        raw_candidates = state.get("target_model_candidates", [])
        if not isinstance(raw_candidates, (list, tuple)):
            return set()
        return {str(item).strip() for item in raw_candidates if str(item).strip()}

    def _truth_probe_state_ready(self, state: Dict[str, Any]) -> bool:
        if not state:
            return False
        current_session_id = str(self.state.get("session_id", "") or "")
        if current_session_id and str(state.get("session_id", "") or "") != current_session_id:
            return False
        if not bool(state.get("robot_truth_seen", False)):
            return False
        expected_candidates = self._expected_truth_target_candidates()
        return expected_candidates.issubset(self._truth_state_target_candidates(state))

    def _truth_probe_startup_failure_text(self) -> str:
        visual_dir = self._current_visual_dir()
        if visual_dir is None:
            return "Missing visual directory for truth probe diagnostics."
        state = read_json(visual_dir / "truth_state.json")
        if not state:
            return "truth_state.json missing or unreadable."
        current_session_id = str(self.state.get("session_id", "") or "")
        truth_session_id = str(state.get("session_id", "") or "")
        if current_session_id and truth_session_id != current_session_id:
            return f"Truth probe session mismatch: expected {current_session_id}, got {truth_session_id or 'none'}."
        if not bool(state.get("robot_truth_seen", False)):
            return "Truth probe did not report robot visibility."
        expected_candidates = self._expected_truth_target_candidates()
        actual_candidates = self._truth_state_target_candidates(state)
        missing_candidates = sorted(expected_candidates - actual_candidates)
        if missing_candidates:
            reported = sorted(actual_candidates)
            return (
                "Truth probe candidate set mismatch: missing "
                f"{', '.join(missing_candidates)}; reported {', '.join(reported) or 'none'}."
            )
        return "Truth probe did not reach a ready state."

    def _wait_for_truth_ready(self, timeout_s: float) -> bool:
        visual_dir = self._current_visual_dir()
        if visual_dir is None:
            return False
        deadline = time.monotonic() + max(timeout_s, 1.0)
        while time.monotonic() < deadline:
            state = read_json(visual_dir / "truth_state.json")
            if self._truth_probe_state_ready(state):
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
            world_snapshot = self._world_stream_snapshot(visual_dir, state, str(self.state.get("session_id", "") or "")) if state else {}
            if (
                state
                and (
                    (
                        bool(state.get("world_stream_ready", False))
                        and bool(state.get("scene_content_ok", False))
                        and bool(state.get("robot_visible_ok", False))
                        and bool(state.get("same_session_partition", False))
                        and not bool(state.get("frames_stale", False))
                    )
                    or (
                        bool(world_snapshot.get("world_stream_renderable", False))
                        and bool(world_snapshot.get("same_session_partition", False))
                        and not bool(state.get("frames_stale", False))
                    )
                )
            ):
                return True
            if self.lifecycle_cancel.is_set():
                return False
            time.sleep(0.5)
        return False

    def _wait_for_operator_view_ready(self, timeout_s: float) -> bool:
        visual_dir = self._current_visual_dir()
        if visual_dir is None:
            return False
        deadline = time.monotonic() + max(timeout_s, 1.0)
        while time.monotonic() < deadline:
            state = self._operator_view_snapshot(visual_dir, self.state)
            if state["ready"]:
                return True
            if state["failure_class"]:
                return False
            if self.lifecycle_cancel.is_set():
                return False
            time.sleep(0.5)
        return False

    def _world_stream_launch_script(self, *, session_id: str, visual_dir_container: str, truth_state_container: str) -> str:
        world_stream_port = int(self.state.get("world_stream_port", 0) or 0)
        return f"""
set -euo pipefail
PID_FILE="/tmp/chasecar_world_stream.pid"
LOG_FILE="/tmp/chasecar_world_stream.log"
pkill -f "world_stream_controller.py" 2>/dev/null || true
rm -f "$PID_FILE" "$LOG_FILE"
nohup bash -lc 'source /opt/ros/{DEFAULT_CORE_ROS_DISTRO}/setup.bash && if [ -f /root/ros2_ws/install/setup.bash ]; then source /root/ros2_ws/install/setup.bash; fi && python3 /workspaces/chasecar/scripts/world_stream_controller.py --session-id "{session_id}" --output-dir "{visual_dir_container}" --public-url "http://127.0.0.1:{world_stream_port}/vnc.html?autoconnect=1&resize=scale&path=websockify" --world-name "{DEFAULT_WORLD_NAME}" --image-topic /observer_world/image_raw --camera-profile robot_follow --truth-state-path "{truth_state_container}" --duration-s 7200' >"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
sleep 1
echo "WORLD_STREAM_PID=$(cat "$PID_FILE")"
echo "WORLD_STREAM_LOG=$LOG_FILE"
"""

    def _operator_view_launch_script(self, *, session_id: str, visual_dir_container: str, dashboard_url: str) -> str:
        operator_view_port = int(self.state.get("operator_view_port", 0) or 0)
        return f"""
set -euo pipefail
PID_FILE="/tmp/chasecar_operator_view.pid"
LOG_FILE="/tmp/chasecar_operator_view.log"
pkill -f "operator_view_controller.py start" 2>/dev/null || true
rm -f "$PID_FILE" "$LOG_FILE"
nohup bash -lc 'source /opt/ros/{DEFAULT_CORE_ROS_DISTRO}/setup.bash && if [ -f /root/ros2_ws/install/setup.bash ]; then source /root/ros2_ws/install/setup.bash; fi && python3 /workspaces/chasecar/scripts/operator_view_controller.py start --session-id "{session_id}" --output-dir "{visual_dir_container}" --port "{operator_view_port}" --dashboard-url "{dashboard_url}"' >"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
sleep 1
echo "OPERATOR_VIEW_PID=$(cat "$PID_FILE")"
echo "OPERATOR_VIEW_LOG=$LOG_FILE"
"""

    def _world_stream_restart_ready(self) -> bool:
        if self.headless_worker_mode:
            return False
        with self.state_lock:
            if self.state.get("environment_state") != "environment_ready":
                return False
            if self.state.get("world_stream_restart_in_progress", False):
                return False
            if not self.world_viewer_container_id:
                return False
            attempts = int(self.state.get("world_stream_restart_attempts", 0) or 0)
            max_attempts = int(self.state.get("world_stream_restart_max_attempts", WORLD_STREAM_RESTART_MAX_ATTEMPTS) or WORLD_STREAM_RESTART_MAX_ATTEMPTS)
            if attempts >= max_attempts:
                return False
        visual_dir = self._current_visual_dir()
        if visual_dir is None:
            return False
        state_path = visual_dir / "world_stream_state.json"
        state = read_json(state_path)
        if not state:
            return False
        current_session_id = str(self.state.get("session_id", "") or "")
        if current_session_id and str(state.get("session_id", "") or "") != current_session_id:
            return False
        if not bool(state.get("frames_stale", False)):
            return False
        if self._lifecycle_busy():
            return False
        return True

    def _restart_world_stream_controller(self, *, reason: str = "world_stream_stale") -> bool:
        if not self.world_stream_restart_lock.acquire(blocking=False):
            return False
        try:
            if not self._world_stream_restart_ready():
                with self.state_lock:
                    if self.state.get("world_stream_restart_in_progress", False):
                        return False
                return False
            now_monotonic = time.monotonic()
            with self.state_lock:
                attempts = int(self.state.get("world_stream_restart_attempts", 0) or 0)
                cooldown_s = float(self.state.get("world_stream_restart_cooldown_s", WORLD_STREAM_RESTART_COOLDOWN_S) or WORLD_STREAM_RESTART_COOLDOWN_S)
                max_attempts = int(self.state.get("world_stream_restart_max_attempts", WORLD_STREAM_RESTART_MAX_ATTEMPTS) or WORLD_STREAM_RESTART_MAX_ATTEMPTS)
                since_last = now_monotonic - float(self._world_stream_last_restart_monotonic or 0.0)
                if attempts >= max_attempts:
                    self._update_state(world_stream_recovery_state="exhausted")
                    return False
                if self._world_stream_last_restart_monotonic and since_last < cooldown_s:
                    self._update_state(world_stream_recovery_state="cooldown")
                    return False
                self._update_state(
                    world_stream_restart_in_progress=True,
                    world_stream_recovery_state="restarting",
                    world_stream_last_restart_error="",
                )
                attempts += 1
                self._update_state(world_stream_restart_attempts=attempts)
            self._record_operator_event("World surface stale; restarting world stream controller.", category="environment")
            visual_dir = self._current_visual_dir()
            if visual_dir is None:
                raise RuntimeError("missing visual directory for world stream restart")
            truth_state_container = to_container_repo_path(visual_dir / "truth_state.json")
            world_script = self._world_stream_launch_script(
                session_id=str(self.state.get("session_id", "") or ""),
                visual_dir_container=to_container_repo_path(visual_dir),
                truth_state_container=truth_state_container,
            )
            world_info = self._run_container_helper(self.world_viewer_container_id, world_script, "WORLD_STREAM")
            ready = self._wait_for_world_stream_ready(40.0)
            restart_utc = utc_now()
            self._world_stream_last_restart_monotonic = now_monotonic
            if ready:
                self._world_stream_stale_since_monotonic = 0.0
                self._update_state(
                    world_stream_restart_in_progress=False,
                    world_stream_recovery_state="healthy",
                    world_stream_last_restart_utc=restart_utc,
                    world_stream_last_restart_error="",
                )
                self._record_operator_event("World surface recovered after stale stream.", category="environment")
                return True

            error_text = (world_info.get("output", "") or "").strip() or "world stream did not become ready after restart"
            self._update_state(
                world_stream_restart_in_progress=False,
                world_stream_recovery_state="stale",
                world_stream_last_restart_utc=restart_utc,
                world_stream_last_restart_error=error_text,
            )
            self._record_operator_event("World surface restart did not recover fresh frames.", category="warn")
            return False
        except Exception as exc:
            self._world_stream_last_restart_monotonic = time.monotonic()
            self._update_state(
                world_stream_restart_in_progress=False,
                world_stream_recovery_state="error",
                world_stream_last_restart_utc=utc_now(),
                world_stream_last_restart_error=str(exc),
            )
            self._record_operator_event(f"World surface restart failed: {exc}", category="error")
            return False
        finally:
            self.world_stream_restart_lock.release()

    def _world_stream_watchdog_loop(self) -> None:
        while not self.world_stream_watchdog_cancel.wait(WORLD_STREAM_WATCHDOG_POLL_S):
            try:
                stale = self._world_stream_restart_ready()
                if stale:
                    if not self._world_stream_stale_since_monotonic:
                        self._world_stream_stale_since_monotonic = time.monotonic()
                    elif time.monotonic() - self._world_stream_stale_since_monotonic >= WORLD_STREAM_STALE_DEBOUNCE_S:
                        self._restart_world_stream_controller()
                else:
                    self._world_stream_stale_since_monotonic = 0.0
                    with self.state_lock:
                        if self.state.get("world_stream_recovery_state") in {"stale", "cooldown", "restarting"} and not self.state.get("world_stream_restart_in_progress", False):
                            self.state["world_stream_recovery_state"] = "idle"
                            self.state["world_stream_last_restart_error"] = ""
                            self._persist_state_locked()
            except Exception as exc:
                self._update_state(
                    world_stream_recovery_state="error",
                    world_stream_last_restart_error=str(exc),
                )

    def _base_env(self, *, session_id: str, world_stream_port: int, operator_view_port: int) -> Dict[str, str]:
        env = self._compose_env()
        env["GAZEBO_PARTITION"] = session_id
        env["WORLD_STREAM_PORT"] = str(world_stream_port)
        env["OPERATOR_VIEW_PORT"] = str(operator_view_port)
        env["CHASECAR_SESSION_ID"] = session_id
        env["CHASECAR_BRAIN_STATE_PATH"] = to_container_repo_path(SESSION_ROOT / session_id / "visual" / "brain_state.json")
        env["CHASECAR_BRAIN_FEEDBACK_PATH"] = to_container_repo_path(SESSION_ROOT / session_id / "visual" / "brain_feedback.jsonl")
        env["CHASECAR_VISIT_RUNTIME_PATH"] = to_container_repo_path(self.visit_mission_runtime_path)
        env["CHASECAR_GATHER_RUNTIME_PATH"] = to_container_repo_path(self.gather_mission_runtime_path)
        env["CHASECAR_INTENT_INBOX_PATH"] = to_container_repo_path(self.intent_inbox_path)
        env["CHASECAR_INTENT_ACK_PATH"] = to_container_repo_path(self.intent_ack_path)
        return env

    def _robot_sdf_name_for_startup(self) -> str:
        pending_scenario = SCENARIOS_BY_ID.get(str(self.pending_scenario_id or "").strip())
        if pending_scenario is not None:
            return pending_scenario.robot_sdf_name
        with self.state_lock:
            current_robot = str(self.state.get("robot_sdf_name", "") or BASELINE_ROBOT_SDF_NAME)
        return self._normalize_robot_sdf_name(current_robot, default_value=BASELINE_ROBOT_SDF_NAME)

    def _world_file_for_startup(self) -> str:
        if str(self.pending_scenario_id or "").strip():
            return self._scenario_pending_world_file()
        with self.state_lock:
            current_world = str(self.state.get("world_file", "") or DEFAULT_WORLD_FILE)
        return self._normalize_world_file(current_world, default_value=DEFAULT_WORLD_FILE)

    def _surface_profile_for_startup(self) -> str:
        if str(self.pending_scenario_id or "").strip():
            return self._scenario_pending_surface_profile()
        with self.state_lock:
            current_surface = str(self.state.get("surface_profile", "") or DEFAULT_SURFACE_PROFILE)
        return self._normalize_surface_profile(current_surface, default_value=DEFAULT_SURFACE_PROFILE)

    def _refresh_session_container_ids(self, project_name: str) -> None:
        service_states = self._required_gate_service_states(project_name)
        self.sim_gate_container_id = str(service_states.get("sim-gate", {}).get("container_id", "") or "")
        self.gate_stack_container_id = str(service_states.get("gate-stack", {}).get("container_id", "") or "")
        self.world_viewer_container_id = str(service_states.get("world-viewer", {}).get("container_id", "") or "")
        self.operator_view_container_id = str(service_states.get("operator-view", {}).get("container_id", "") or "")

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

    def _run_environment_compose_up(self, project_name: str, env: Dict[str, str]) -> tuple[int, str]:
        self._run_docker_compose(project_name, "down", "--remove-orphans", env=env)
        args: list[str] = ["up", "-d"]
        if self.build_on_next_start:
            required_images = self._required_gate_image_refs(env)
            missing_images = [image_ref for image_ref in required_images if not self._docker_image_exists(image_ref)]
            if missing_images:
                args.append("--build")
            else:
                args.append("--no-build")
        else:
            args.append("--no-build")
        # Only bring up sim/gate services. In host_powershell mode the
        # dashboard-control and brain-supervisor-shadow run on the host, so
        # starting them inside compose would cause a port conflict on 8860.
        compose_services = ["sim-gate", "world-viewer", "gate-stack", "dashboard-utility", "operator-view"]
        if self.headless_worker_mode:
            compose_services = ["sim-gate", "gate-stack"]
        args.extend(compose_services)
        proc = self._popen_docker_compose(project_name, *args, env=env)
        self.active_env_proc = proc
        output, _ = proc.communicate()
        self.active_env_proc = None
        if returncode := proc.returncode:
            return returncode, output
        return proc.returncode, output

    def _start_environment_worker(self) -> None:
        pending_scenario_ready_to_launch = False
        if not self.lifecycle_lock.acquire(blocking=False):
            return
        try:
            self._clear_llm_proof_runtime_state()
            self._clear_visit_mission_runtime_state()
            self._clear_gather_mission_runtime_state()
            session_id = make_session_id()
            project_name = f"chasecar_dashboard_{slugify_session(session_id)}"
            validation_dir = ensure_dir(SESSION_ROOT / session_id / "dashboard_validation")
            ensure_dir(SESSION_ROOT / session_id / "visual")
            startup_cleanup_projects = self._cleanup_stale_dashboard_projects(current_project=project_name)
            startup_cleanup_count = len(startup_cleanup_projects)
            startup_retry_count = 0
            if startup_cleanup_projects:
                self._record_operator_event(
                    f"Cleaned stale dashboard projects before startup: {', '.join(startup_cleanup_projects)}.",
                    category="environment",
                )
            operator_view_status = "disabled" if self.headless_worker_mode else "starting"
            self._update_state(
                environment_state="starting",
                scenario_state="idle",
                session_id=session_id,
                compose_project=project_name,
                world_file=self._world_file_for_startup(),
                surface_profile=self._surface_profile_for_startup(),
                environment_message="starting authoritative environment",
                environment_failure_class="",
                gate_service_states={},
                scenario_message="",
                last_error="",
                world_stream_port=0,
                operator_view_port=0,
                operator_view_url="",
                operator_view_ready=False,
                operator_view_status=operator_view_status,
                operator_view_failure_class="",
                validation_dir=str(validation_dir),
                command_history_path=str(validation_dir / "command_history.jsonl"),
                multi_target_progress_path=str(validation_dir / "multi_target_progress.json"),
                active_scenario="",
                phase="starting",
                target_id="",
                target_transition_active=False,
                latest_artifacts={},
                motion_evidence=False,
                world_stream_restart_attempts=0,
                world_stream_last_restart_utc="",
                world_stream_last_restart_error="",
                world_stream_recovery_state="idle",
                world_stream_restart_in_progress=False,
                startup_retry_count=startup_retry_count,
                startup_cleanup_count=startup_cleanup_count,
                startup_last_cleanup_projects=startup_cleanup_projects,
            )
            self._world_stream_stale_since_monotonic = 0.0
            self._world_stream_last_restart_monotonic = 0.0
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
                    environment_failure_class="",
                    gate_service_states={},
                    world_stream_recovery_state="idle",
                    world_stream_restart_in_progress=False,
                )
                self._remove_lock_file()
                return

            output = ""
            env: Dict[str, str] = {}
            world_stream_port = 0
            operator_view_port = 0
            gate_service_states: Dict[str, Dict[str, Any]] = {}
            failed_world_stream_ports: set[int] = set()
            failed_operator_view_ports: set[int] = set()
            for attempt in range(2):
                world_stream_port = (
                    0
                    if self.headless_worker_mode
                    else find_free_port(8891, 8921, exclude_ports=failed_world_stream_ports)
                )
                operator_view_port = (
                    0
                    if self.headless_worker_mode
                    else find_free_port(
                        OPERATOR_VIEW_PORT_START,
                        OPERATOR_VIEW_PORT_END,
                        exclude_ports=failed_operator_view_ports,
                    )
                )
                env = self._base_env(
                    session_id=session_id,
                    world_stream_port=world_stream_port,
                    operator_view_port=operator_view_port,
                )
                env["WORLD_FILE"] = self._world_file_for_startup()
                env["CHASECAR_SURFACE_PROFILE"] = self._surface_profile_for_startup()
                env["CHASECAR_ROBOT_SDF_NAME"] = self._robot_sdf_name_for_startup()
                self._update_state(
                    world_file=env["WORLD_FILE"],
                    surface_profile=env["CHASECAR_SURFACE_PROFILE"],
                    world_stream_port=world_stream_port,
                    operator_view_port=operator_view_port,
                    operator_view_url="",
                    operator_view_ready=False,
                    operator_view_status=operator_view_status,
                    operator_view_failure_class="",
                    environment_message="starting authoritative environment",
                    environment_failure_class="",
                    gate_service_states={},
                    startup_retry_count=startup_retry_count,
                    startup_cleanup_count=startup_cleanup_count,
                    startup_last_cleanup_projects=startup_cleanup_projects,
                )
                returncode, output = self._run_environment_compose_up(project_name, env)
                if self.lifecycle_cancel.is_set():
                    self._teardown_environment(env=env)
                    self._update_state(
                        environment_state="stopped",
                        scenario_state="idle",
                        environment_message="startup cancelled",
                        environment_failure_class="",
                        gate_service_states={},
                        world_stream_recovery_state="idle",
                        world_stream_restart_in_progress=False,
                    )
                    self._record_operator_event("Environment startup cancelled.", category="environment")
                    self._remove_lock_file()
                    return
                if returncode == 0:
                    break
                bind_port = self._extract_host_port_bind_failure_port(output)
                if bind_port is None or attempt >= 1:
                    raise RuntimeError(output.strip() or "gate bring-up failed")
                if 8891 <= bind_port <= 8921:
                    failed_world_stream_ports.add(bind_port)
                elif OPERATOR_VIEW_PORT_START <= bind_port <= OPERATOR_VIEW_PORT_END:
                    failed_operator_view_ports.add(bind_port)
                retry_cleanup_projects = self._cleanup_stale_dashboard_projects(current_project=project_name)
                if retry_cleanup_projects:
                    for retry_project in retry_cleanup_projects:
                        if retry_project not in startup_cleanup_projects:
                            startup_cleanup_projects.append(retry_project)
                    startup_cleanup_count = len(startup_cleanup_projects)
                    self._record_operator_event(
                        f"Cleaned stale dashboard projects after port bind failure: {', '.join(retry_cleanup_projects)}.",
                        category="environment",
                    )
                self._force_remove_project_resources(project_name)
                startup_retry_count += 1
                self._update_state(
                    environment_message=f"retrying startup after host port {bind_port} bind failure",
                    startup_retry_count=startup_retry_count,
                    startup_cleanup_count=startup_cleanup_count,
                    startup_last_cleanup_projects=startup_cleanup_projects,
                )
                self._record_operator_event(
                    f"Retrying startup after host port {bind_port} bind failure.",
                    category="environment",
                )
            else:
                raise RuntimeError(output.strip() or "gate bring-up failed")

            gate_service_states = self._wait_for_required_gate_services(project_name, GATE_SERVICE_READY_TIMEOUT_S)
            self._refresh_session_container_ids(project_name)
            if not self._gate_services_ready(gate_service_states):
                failure_class, failure_message = self._classify_gate_service_states(gate_service_states)
                raise EnvironmentStartupError(
                    failure_message or "Required gate services failed to reach running state.",
                    environment_failure_class=failure_class or "gate_services_not_running",
                    gate_service_states=gate_service_states,
                )

            visual_dir = self._current_visual_dir()
            assert visual_dir is not None
            visual_dir_container = to_container_repo_path(visual_dir)
            truth_script = f"""
set -euo pipefail
PID_FILE="/tmp/chasecar_truth_probe.pid"
LOG_FILE="/tmp/chasecar_truth_probe.log"
pkill -f "sim_truth_probe.py" 2>/dev/null || true
rm -f "$PID_FILE" "$LOG_FILE"
nohup bash -lc 'source /opt/ros/{DEFAULT_CORE_ROS_DISTRO}/setup.bash && if [ -f /root/ros2_ws/install/setup.bash ]; then source /root/ros2_ws/install/setup.bash; fi && python3 /workspaces/chasecar/scripts/sim_truth_probe.py --session-id "{session_id}" --output-dir "{visual_dir_container}" --world-name "{DEFAULT_WORLD_NAME}" --target-model-names "{",".join(TRUTH_TARGET_MODEL_NAMES)}" --target-model-prefix "{TRUTH_TARGET_MODEL_PREFIX}" --duration-s 7200' >"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
sleep 1
echo "TRUTH_PID=$(cat "$PID_FILE")"
echo "TRUTH_LOG=$LOG_FILE"
"""
            truth_info = self._run_container_helper(self.sim_gate_container_id, truth_script, "TRUTH")
            if int(truth_info.get("exit_code", 0) or 0) != 0:
                raise EnvironmentStartupError(
                    f"Truth probe helper failed. {truth_info['output']}".strip(),
                    environment_failure_class="truth_probe_start_failed",
                    gate_service_states=gate_service_states,
                )
            if not self._wait_for_truth_ready(20.0):
                truth_failure_text = self._truth_probe_startup_failure_text()
                raise EnvironmentStartupError(
                    f"Truth probe did not report ready state. {truth_failure_text} {truth_info['output']}".strip(),
                    environment_failure_class="truth_probe_start_failed",
                    gate_service_states=gate_service_states,
                )

            if self.headless_worker_mode:
                self._update_state(
                    environment_state="environment_ready",
                    scenario_state="ready",
                    environment_message="environment ready",
                    environment_failure_class="",
                    world_file=env.get("WORLD_FILE", DEFAULT_WORLD_FILE),
                    surface_profile=env.get("CHASECAR_SURFACE_PROFILE", DEFAULT_SURFACE_PROFILE),
                    gate_service_states=gate_service_states,
                    scenario_message="ready",
                    world_stream_url="",
                    operator_view_backend="disabled",
                    operator_view_url="",
                    operator_view_ready=False,
                    operator_view_status="disabled",
                    operator_view_failure_class="",
                    world_stream_recovery_state="idle",
                    world_stream_restart_in_progress=False,
                    world_stream_last_restart_error="",
                )
                self._record_operator_event("Environment ready (headless soak mode).", category="environment")
                self._write_operator_status(
                    phase="environment_ready",
                    target_id="",
                    target_transition_active=False,
                    status_text="Environment ready",
                )
                self._write_lock_file()
                self.build_on_next_start = False
                pending_scenario_ready_to_launch = True
                return

            truth_state_container = to_container_repo_path(visual_dir / "truth_state.json")
            operator_status_container = to_container_repo_path(visual_dir / "operator_status.json")
            world_script = self._world_stream_launch_script(
                session_id=session_id,
                visual_dir_container=visual_dir_container,
                truth_state_container=truth_state_container,
            )
            world_info = self._run_container_helper(self.world_viewer_container_id, world_script, "WORLD_STREAM")
            if int(world_info.get("exit_code", 0) or 0) != 0:
                raise EnvironmentStartupError(
                    f"World stream helper failed. {world_info['output']}".strip(),
                    environment_failure_class="world_stream_start_failed",
                    gate_service_states=gate_service_states,
                )
            if not self._wait_for_world_stream_ready(40.0):
                raise EnvironmentStartupError(
                    f"World stream did not become ready. {world_info['output']}".strip(),
                    environment_failure_class="world_stream_start_failed",
                    gate_service_states=gate_service_states,
                )

            dashboard_url = f"http://127.0.0.1:{self.port}/dashboard.html"
            operator_view_script = self._operator_view_launch_script(
                session_id=session_id,
                visual_dir_container=visual_dir_container,
                dashboard_url=dashboard_url,
            )
            operator_view_info = self._run_container_helper(self.operator_view_container_id, operator_view_script, "OPERATOR_VIEW")
            if int(operator_view_info.get("exit_code", 0) or 0) != 0:
                raise EnvironmentStartupError(
                    f"Operator view helper failed. {operator_view_info['output']}".strip(),
                    environment_failure_class="operator_view_start_failed",
                    operator_view_failure_class="operator_view_start_failed",
                    gate_service_states=gate_service_states,
                )
            if not self._wait_for_operator_view_ready(30.0):
                operator_view_state = self._operator_view_snapshot(visual_dir, self.state)
                raise EnvironmentStartupError(
                    f"Operator view did not become ready. {operator_view_info['output']}".strip(),
                    environment_failure_class="operator_view_start_failed",
                    operator_view_failure_class=str(
                        operator_view_state.get("failure_class", "") or "operator_view_start_failed"
                    ),
                    gate_service_states=gate_service_states,
                )

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
            if int(visual_info.get("exit_code", 0) or 0) != 0:
                raise EnvironmentStartupError(
                    f"Visual observer helper failed. {visual_info['output']}".strip(),
                    environment_failure_class="visual_observer_start_failed",
                    gate_service_states=gate_service_states,
                )
            if not self._wait_for_visual_ready(20.0):
                raise EnvironmentStartupError(
                    f"Visual observer did not emit dashboard frames. {visual_info['output']}".strip(),
                    environment_failure_class="visual_observer_start_failed",
                    gate_service_states=gate_service_states,
                )

            self._update_state(
                environment_state="environment_ready",
                scenario_state="ready",
                environment_message="environment ready",
                environment_failure_class="",
                gate_service_states=gate_service_states,
                scenario_message="ready",
                world_stream_url=f"http://127.0.0.1:{world_stream_port}/vnc.html?autoconnect=1&resize=scale&path=websockify",
                operator_view_backend="xpra",
                operator_view_url=f"http://127.0.0.1:{operator_view_port}/",
                operator_view_ready=True,
                operator_view_status="ready",
                operator_view_failure_class="",
                world_stream_recovery_state="idle",
                world_stream_restart_in_progress=False,
                world_stream_last_restart_error="",
            )
            self._record_operator_event("Environment ready.", category="environment")
            self._write_operator_status(
                phase="environment_ready",
                target_id="",
                target_transition_active=False,
                status_text="Environment ready",
            )
            self._write_lock_file()
            self.build_on_next_start = False
            pending_scenario_ready_to_launch = bool(str(self.pending_scenario_id or "").strip())
        except Exception as exc:
            self.pending_scenario_id = ""
            self.pending_scenario_overrides = {}
            self._teardown_environment(
                env=self._base_env(
                    session_id=self.state.get("session_id", ""),
                    world_stream_port=int(self.state.get("world_stream_port", 0) or 0),
                    operator_view_port=int(self.state.get("operator_view_port", 0) or 0),
                )
            )
            if self.lifecycle_cancel.is_set():
                self._update_state(
                    environment_state="stopped",
                    scenario_state="idle",
                    environment_message="startup cancelled",
                    environment_failure_class="",
                    gate_service_states={},
                    scenario_message="",
                    last_error="",
                    operator_view_url="",
                    operator_view_ready=False,
                    operator_view_status="cancelled",
                    operator_view_failure_class="",
                    world_stream_recovery_state="idle",
                    world_stream_restart_in_progress=False,
                )
                self._record_operator_event("Environment startup cancelled.", category="environment")
            else:
                environment_failure_class = ""
                operator_view_failure_class = ""
                failed_gate_service_states: Dict[str, Dict[str, Any]] = gate_service_states
                if isinstance(exc, EnvironmentStartupError):
                    environment_failure_class = exc.environment_failure_class
                    operator_view_failure_class = exc.operator_view_failure_class
                    failed_gate_service_states = exc.gate_service_states or gate_service_states
                self._update_state(
                    environment_state="error",
                    scenario_state="idle",
                    environment_message="environment start failed",
                    environment_failure_class=environment_failure_class,
                    gate_service_states=failed_gate_service_states,
                    last_error=str(exc),
                    operator_view_url="",
                    operator_view_ready=False,
                    operator_view_status="error",
                    operator_view_failure_class=operator_view_failure_class,
                    world_stream_recovery_state="error",
                    world_stream_last_restart_error=str(exc),
                    world_stream_restart_in_progress=False,
                )
                self._record_operator_event(f"Environment start failed: {exc}", category="error")
            self._remove_lock_file()
        finally:
            self.lifecycle_cancel.clear()
            self.active_env_proc = None
            self.lifecycle_lock.release()
        if pending_scenario_ready_to_launch:
            self._start_pending_scenario_if_any()

    def _stop_environment_worker(self) -> None:
        if not self.lifecycle_lock.acquire(blocking=False):
            return
        try:
            self.pending_scenario_id = ""
            self.pending_scenario_overrides = {}
            with self.state_lock:
                session_id = self.state.get("session_id", "")
                world_stream_port = int(self.state.get("world_stream_port", 0) or 0)
                operator_view_port = int(self.state.get("operator_view_port", 0) or 0)
            env = self._base_env(
                session_id=session_id or make_session_id(),
                world_stream_port=world_stream_port or find_free_port(8891, 8921),
                operator_view_port=operator_view_port or find_free_port(OPERATOR_VIEW_PORT_START, OPERATOR_VIEW_PORT_END),
            )
            self._update_state(
                environment_state="stopping",
                scenario_state="idle",
                environment_message="stopping environment",
                environment_failure_class="",
                operator_view_ready=False,
                operator_view_url="",
                operator_view_status="stopping",
                operator_view_failure_class="",
                gate_service_states={},
                world_stream_recovery_state="idle",
                world_stream_restart_in_progress=False,
            )
            self._world_stream_stale_since_monotonic = 0.0
            self._record_operator_event("Environment stopping.", category="environment")
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
                environment_failure_class="",
                scenario_message="",
                active_scenario="",
                phase="stopped",
                target_id="",
                target_transition_active=False,
                stale_chasecar_containers=stale,
                operator_view_url="",
                operator_view_port=0,
                operator_view_ready=False,
                operator_view_status="disabled",
                operator_view_failure_class="",
                gate_service_states={},
                world_stream_recovery_state="idle",
                world_stream_restart_in_progress=False,
            )
            self._clear_llm_proof_runtime_state()
            self._clear_visit_mission_runtime_state()
            self._clear_gather_mission_runtime_state()
            self._record_operator_event("Environment stopped.", category="environment")
        except Exception as exc:
            self._update_state(
                environment_state="error",
                last_error=str(exc),
                environment_message="stop failed",
                environment_failure_class="environment_stop_failed",
                operator_view_ready=False,
                operator_view_url="",
                operator_view_status="error",
                operator_view_failure_class="operator_view_stop_failed",
                gate_service_states={},
                world_stream_recovery_state="error",
                world_stream_restart_in_progress=False,
            )
            self._record_operator_event(f"Environment stop failed: {exc}", category="error")
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
                operator_view_port = int(self.state.get("operator_view_port", 0) or find_free_port(OPERATOR_VIEW_PORT_START, OPERATOR_VIEW_PORT_END))
            self._update_state(
                environment_state="stopping",
                environment_message="refreshing environment",
                environment_failure_class="",
                operator_view_ready=False,
                operator_view_url="",
                operator_view_status="refreshing",
                operator_view_failure_class="",
                gate_service_states={},
                world_stream_recovery_state="idle",
                world_stream_restart_in_progress=False,
            )
            self._world_stream_stale_since_monotonic = 0.0
            env = self._base_env(session_id=session_id, world_stream_port=world_stream_port, operator_view_port=operator_view_port)
            env["WORLD_FILE"] = self._world_file_for_startup()
            env["CHASECAR_SURFACE_PROFILE"] = self._surface_profile_for_startup()
            env["CHASECAR_ROBOT_SDF_NAME"] = self._robot_sdf_name_for_startup()
            self._cleanup_scenario_processes()
            self._teardown_environment(env=env)
            self._update_state(
                environment_state="stopped",
                environment_message="refresh restart pending",
                environment_failure_class="",
                compose_project=project_name,
                session_id=session_id,
                operator_view_url="",
                operator_view_ready=False,
                operator_view_status="starting",
                operator_view_failure_class="",
                gate_service_states={},
                world_stream_recovery_state="idle",
                world_stream_restart_in_progress=False,
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
                operator_view_port = int(self.state.get("operator_view_port", 0) or find_free_port(OPERATOR_VIEW_PORT_START, OPERATOR_VIEW_PORT_END))
            env = self._base_env(
                session_id=old_session or make_session_id(),
                world_stream_port=world_stream_port,
                operator_view_port=operator_view_port,
            )
            env["WORLD_FILE"] = self._world_file_for_startup()
            env["CHASECAR_SURFACE_PROFILE"] = self._surface_profile_for_startup()
            env["CHASECAR_ROBOT_SDF_NAME"] = self._robot_sdf_name_for_startup()
            self._update_state(
                environment_state="stopping",
                environment_message="resetting sim",
                environment_failure_class="",
                scenario_message="reset pending",
                operator_view_ready=False,
                operator_view_url="",
                operator_view_status="resetting",
                operator_view_failure_class="",
                gate_service_states={},
                world_stream_recovery_state="idle",
                world_stream_restart_in_progress=False,
            )
            self._world_stream_stale_since_monotonic = 0.0
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
        if self.operator_view_container_id:
            visual_dir = self._current_visual_dir()
            output_dir = to_container_repo_path(visual_dir) if visual_dir else ""
            stop_command = (
                f'python3 /workspaces/chasecar/scripts/operator_view_controller.py stop --output-dir "{output_dir}"'
                if output_dir
                else 'pkill -f "operator_view_controller.py start" 2>/dev/null || true'
            )
            self._docker_exec(
                self.operator_view_container_id,
                f"""
set +e
{stop_command}
if [ -f /tmp/chasecar_operator_view.pid ]; then
  PID="$(cat /tmp/chasecar_operator_view.pid 2>/dev/null || true)"
  [ -n "$PID" ] && kill "$PID" 2>/dev/null || true
fi
pkill -f "operator_view_controller.py start" 2>/dev/null || true
pkill -f "xpra .*14500" 2>/dev/null || true
pkill -f "rqt_image_view" 2>/dev/null || true
pkill -f "image_view" 2>/dev/null || true
pkill -f "gz gui" 2>/dev/null || true
pkill -f "fluxbox" 2>/dev/null || true
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
                if self.docker:
                    self._run_docker_compose(project_name, "down", "--remove-orphans", env=env)
        self.sim_gate_container_id = ""
        self.gate_stack_container_id = ""
        self.world_viewer_container_id = ""
        self.operator_view_container_id = ""
        self._world_stream_stale_since_monotonic = 0.0

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
            if scenario.mode == "llm_proof":
                self._clear_llm_proof_runtime_state()
            if scenario.mode in {"visit_mission", "gather_mission"}:
                self._clear_visit_mission_runtime_state()
            if scenario.mode == "gather_mission":
                self._clear_gather_mission_runtime_state()
            self._update_state(
                scenario_state="running",
                active_scenario=scenario.id,
                scenario_message=f"running {scenario.id}",
                latest_artifacts={},
                motion_evidence=False,
                proof_state="waiting" if scenario.mode in {"llm_proof", "visit_mission", "gather_mission"} else self.state.get("proof_state", "waiting"),
                proof_verdict={},
                mission_phase="setup" if scenario.mode in {"visit_mission", "gather_mission"} else self.state.get("mission_phase", "idle"),
                mission_status="running" if scenario.mode in {"visit_mission", "gather_mission"} else self.state.get("mission_status", "idle"),
                search_bias_active=False,
                current_target_id="",
                visit_index=0,
                visited_targets=[],
                remaining_targets=[],
                last_visit_result={},
                mission_verdict={},
                gather_phase="setup" if scenario.mode == "gather_mission" else "idle",
                capture_state={},
                zone_pose={},
                zone_score={},
                placed_targets=[],
                capture_loss_count=0,
                route_order=[],
            )
            self._record_operator_event(f"{scenario.label} scenario started.", category="scenario")
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
            elif scenario.mode == "llm_proof":
                result = self._run_llm_proof_scenario(scenario)
            elif scenario.mode == "visit_mission":
                result = self._run_visit_mission_scenario(scenario)
            elif scenario.mode == "gather_mission":
                result = self._run_gather_mission_scenario(scenario)
            else:
                result = self._run_multi_target_scenario(scenario)
            artifacts = result.get("artifacts", {})
            self._update_state(
                scenario_state="ready" if result.get("pass") else "error",
                scenario_message=result.get("message", ""),
                latest_artifacts=artifacts,
                motion_evidence=bool(result.get("motion_evidence", False)),
                last_result=result.get("message", ""),
                proof_state=result.get("proof_state", self.state.get("proof_state", "waiting")),
                proof_verdict=result.get("proof_verdict", {}),
                mission_phase=result.get("mission_phase", self.state.get("mission_phase", "idle")),
                mission_status=result.get("mission_status", self.state.get("mission_status", "idle")),
                search_bias_active=bool(result.get("search_bias_active", False)),
                current_target_id=result.get("current_target_id", ""),
                visit_index=int(result.get("visit_index", 0) or 0),
                visited_targets=result.get("visited_targets", []),
                remaining_targets=result.get("remaining_targets", []),
                last_visit_result=result.get("last_visit_result", {}),
                mission_verdict=result.get("mission_verdict", {}),
                gather_phase=result.get("gather_phase", self.state.get("gather_phase", "idle")),
                capture_state=result.get("capture_state", self.state.get("capture_state", {})),
                zone_pose=result.get("zone_pose", self.state.get("zone_pose", {})),
                zone_score=result.get("zone_score", self.state.get("zone_score", {})),
                placed_targets=result.get("placed_targets", self.state.get("placed_targets", [])),
                capture_loss_count=int(result.get("capture_loss_count", self.state.get("capture_loss_count", 0)) or 0),
                route_order=result.get("route_order", self.state.get("route_order", [])),
            )
            self._record_operator_event(result.get("message", f"{scenario.label} complete"), category="scenario")
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
            if scenario.mode == "llm_proof":
                self._clear_llm_proof_runtime_state()
            if scenario.mode in {"visit_mission", "gather_mission"}:
                self._clear_visit_mission_runtime_state()
            if scenario.mode == "gather_mission":
                self._clear_gather_mission_runtime_state()
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
                    proof_state="failed" if scenario.mode in {"llm_proof", "visit_mission", "gather_mission"} else self.state.get("proof_state", "waiting"),
                    mission_phase="failed" if scenario.mode in {"visit_mission", "gather_mission"} else self.state.get("mission_phase", "idle"),
                    mission_status="failed" if scenario.mode in {"visit_mission", "gather_mission"} else self.state.get("mission_status", "idle"),
                    search_bias_active=False,
                    gather_phase="failed" if scenario.mode == "gather_mission" else "idle",
                    capture_state={},
                    zone_pose={},
                    zone_score={},
                    placed_targets=[],
                    capture_loss_count=0,
                    route_order=[],
                )
            else:
                self._update_state(
                    scenario_state="idle",
                    scenario_message="",
                    latest_artifacts={},
                    motion_evidence=False,
                    last_error="",
                    last_result="scenario cancelled",
                    proof_state="waiting",
                    mission_phase="idle",
                    mission_status="idle",
                    search_bias_active=False,
                    gather_phase="idle",
                    capture_state={},
                    zone_pose={},
                    zone_score={},
                    placed_targets=[],
                    capture_loss_count=0,
                    route_order=[],
                )
            self._record_operator_event(f"{scenario.label} scenario cancelled.", category="scenario")
        except Exception as exc:
            self._update_state(scenario_state="error", scenario_message=f"scenario failed: {exc}", last_error=str(exc))
            self._record_operator_event(f"{scenario.label} scenario failed: {exc}", category="error")
        finally:
            self.active_scenario_proc = None
            self.scenario_cancel.clear()
            self._update_state(active_scenario="")
            self.scenario_lock.release()

    def _scenario_env(self, scenario: ScenarioDefinition) -> Dict[str, str]:
        session_id = self.state.get("session_id", "")
        world_stream_port = int(self.state.get("world_stream_port", 0) or find_free_port(8891, 8921))
        operator_view_port = int(self.state.get("operator_view_port", 0) or find_free_port(OPERATOR_VIEW_PORT_START, OPERATOR_VIEW_PORT_END))
        env = self._base_env(
            session_id=session_id,
            world_stream_port=world_stream_port,
            operator_view_port=operator_view_port,
        )
        env["WORLD_FILE"] = self._normalize_world_file(str(self.state.get("world_file", "") or ""), default_value=scenario.world_file)
        env["CHASECAR_SURFACE_PROFILE"] = self._normalize_surface_profile(
            str(self.state.get("surface_profile", "") or ""),
            default_value=scenario.surface_profile,
        )
        env.update(
            {
                "CHASECAR_ROBOT_SDF_NAME": scenario.robot_sdf_name,
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

    def _run_llm_proof_scenario(self, scenario: ScenarioDefinition) -> Dict[str, Any]:
        scenario_dir = self._scenarios_dir() or ensure_dir(self._current_validation_dir() or (SESSION_ROOT / self.state["session_id"] / "dashboard_validation"))
        log_path = ensure_dir(scenario_dir) / f"{scenario.id}.log"
        env = self._scenario_env(scenario)
        command = [
            sys.executable,
            str(SCRIPTS_DIR / "llm_turn_then_go_proof_runner.py"),
            "--dashboard-url",
            str(self.state.get("dashboard_url", f"http://127.0.0.1:{self.port}") or f"http://127.0.0.1:{self.port}"),
            "--contract",
            str(REPO_ROOT / "runtime" / "contracts" / "llm_control_contract.yaml"),
            "--keep-environment",
        ]

        with log_path.open("w", encoding="utf-8") as handle:
            proc = subprocess.Popen(
                command,
                cwd=str(REPO_ROOT),
                env=env,
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.active_scenario_proc = proc
            while proc.poll() is None:
                if self.scenario_cancel.is_set():
                    self._terminate_process(proc)
                    raise RuntimeError("scenario cancelled")
                time.sleep(1.0)

        output = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
        summary_path_raw = parse_marker(output, "LLM_TURN_THEN_GO_PROOF_SUMMARY=")
        summary_path = Path(summary_path_raw) if summary_path_raw else None
        summary = read_json(summary_path.with_name("summary.json")) if summary_path and summary_path.exists() else {}
        verdict = read_json(summary_path) if summary_path and summary_path.exists() else {}
        pass_flag = bool(verdict.get("pass")) if verdict else bool(summary.get("pass"))
        artifacts = {
            "llm_turn_then_go_proof": str(summary_path.parent) if summary_path and summary_path.exists() else "",
            "proof_verdict": str(summary_path) if summary_path and summary_path.exists() else "",
            "log": str(log_path),
        }
        if proc.returncode not in {0, 2} and not verdict:
            raise RuntimeError(output.strip() or "llm proof scenario failed")

        payload = {
            "scenario_id": scenario.id,
            "phase": scenario.phase,
            "pass": pass_flag,
            "artifacts": artifacts,
            "summary": summary,
            "proof_verdict": verdict,
            "message": "LLM turn-and-go proof passed" if pass_flag else "LLM turn-and-go proof failed",
            "motion_evidence": bool(verdict.get("linear_displacement_m", 0.0) or pass_flag),
            "proof_state": "completed" if pass_flag else "failed",
        }
        self._write_scenario_result(scenario.id, payload)
        return payload

    def _run_visit_mission_scenario(self, scenario: ScenarioDefinition) -> Dict[str, Any]:
        scenario_dir = self._scenarios_dir() or ensure_dir(self._current_validation_dir() or (SESSION_ROOT / self.state["session_id"] / "dashboard_validation"))
        log_path = ensure_dir(scenario_dir) / f"{scenario.id}.log"
        env = self._scenario_env(scenario)
        command = [
            sys.executable,
            str(SCRIPTS_DIR / "visit_mission_runner.py"),
            "--dashboard-url",
            str(self.state.get("dashboard_url", f"http://127.0.0.1:{self.port}") or f"http://127.0.0.1:{self.port}"),
            "--contract",
            str(REPO_ROOT / "runtime" / "contracts" / "llm_control_contract.yaml"),
            "--scenario-id",
            scenario.id,
            "--scenario-label",
            scenario.label,
            "--visit-runtime-json",
            str(self.visit_mission_runtime_path),
            "--poll-s",
            str(DEFAULT_VISIT_MISSION_POLL_S),
            "--keep-environment",
        ]

        with log_path.open("w", encoding="utf-8") as handle:
            proc = subprocess.Popen(
                command,
                cwd=str(REPO_ROOT),
                env=env,
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.active_scenario_proc = proc
            while proc.poll() is None:
                if self.scenario_cancel.is_set():
                    self._terminate_process(proc)
                    raise RuntimeError("scenario cancelled")
                time.sleep(1.0)

        output = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
        summary_path_raw = parse_marker(output, "VISIT_MISSION_SUMMARY=")
        summary_path = Path(summary_path_raw) if summary_path_raw else None
        summary = read_json(summary_path.with_name("summary.json")) if summary_path and summary_path.exists() else {}
        verdict = read_json(summary_path) if summary_path and summary_path.exists() else {}
        pass_flag = bool(verdict.get("pass")) if verdict else bool(summary.get("pass"))
        mission_root = summary_path.parent if summary_path and summary_path.exists() else None
        target_results = read_json(mission_root / "target_results.json") if mission_root is not None else {}
        runtime = self._visit_mission_runtime_state()
        artifacts = {
            "visit_mission": str(mission_root) if mission_root is not None else "",
            "mission_verdict": str(summary_path) if summary_path and summary_path.exists() else "",
            "target_results": str(mission_root / "target_results.json") if mission_root is not None else "",
            "log": str(log_path),
        }
        if proc.returncode not in {0, 2} and not verdict:
            raise RuntimeError(output.strip() or "visit mission scenario failed")

        payload = {
            "scenario_id": scenario.id,
            "phase": scenario.phase,
            "pass": pass_flag,
            "artifacts": artifacts,
            "summary": summary,
            "mission_verdict": verdict,
            "proof_verdict": verdict,
            "target_results": target_results,
            "message": "Visit mission passed" if pass_flag else "Visit mission failed",
            "motion_evidence": bool(pass_flag),
            "proof_state": "completed" if pass_flag else "failed",
            "mission_phase": str(runtime.get("mission_phase", "completed" if pass_flag else "failed") or ("completed" if pass_flag else "failed")),
            "mission_status": "completed" if pass_flag else "failed",
            "search_bias_active": bool(runtime.get("search_bias_active", False)),
            "current_target_id": str(runtime.get("current_target_id", "") or ""),
            "visit_index": int(runtime.get("visit_index", 0) or 0),
            "visited_targets": list(runtime.get("visited_targets", [])) if isinstance(runtime.get("visited_targets"), list) else [],
            "remaining_targets": list(runtime.get("remaining_targets", [])) if isinstance(runtime.get("remaining_targets"), list) else [],
            "last_visit_result": runtime.get("last_visit_result", {}) if isinstance(runtime.get("last_visit_result"), dict) else {},
        }
        self._write_scenario_result(scenario.id, payload)
        return payload

    def _run_gather_mission_scenario(self, scenario: ScenarioDefinition) -> Dict[str, Any]:
        scenario_dir = self._scenarios_dir() or ensure_dir(self._current_validation_dir() or (SESSION_ROOT / self.state["session_id"] / "dashboard_validation"))
        log_path = ensure_dir(scenario_dir) / f"{scenario.id}.log"
        env = self._scenario_env(scenario)
        command = [
            sys.executable,
            str(SCRIPTS_DIR / "gather_mission_runner.py"),
            "--dashboard-url",
            str(self.state.get("dashboard_url", f"http://127.0.0.1:{self.port}") or f"http://127.0.0.1:{self.port}"),
            "--scenario-id",
            scenario.id,
            "--scenario-label",
            scenario.label,
            "--world-file",
            str(env.get("WORLD_FILE", scenario.world_file)),
            "--surface-profile",
            str(env.get("CHASECAR_SURFACE_PROFILE", scenario.surface_profile)),
            "--visit-runtime-json",
            str(self.visit_mission_runtime_path),
            "--gather-runtime-json",
            str(self.gather_mission_runtime_path),
            "--keep-environment",
        ]

        with log_path.open("w", encoding="utf-8") as handle:
            proc = subprocess.Popen(
                command,
                cwd=str(REPO_ROOT),
                env=env,
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.active_scenario_proc = proc
            while proc.poll() is None:
                if self.scenario_cancel.is_set():
                    self._terminate_process(proc)
                    raise RuntimeError("scenario cancelled")
                time.sleep(1.0)

        output = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
        summary_path_raw = parse_marker(output, "GATHER_MISSION_SUMMARY=")
        summary_path = Path(summary_path_raw) if summary_path_raw else None
        summary = read_json(summary_path.with_name("summary.json")) if summary_path and summary_path.exists() else {}
        verdict = read_json(summary_path) if summary_path and summary_path.exists() else {}
        pass_flag = bool(verdict.get("pass")) if verdict else bool(summary.get("pass"))
        mission_root = summary_path.parent if summary_path and summary_path.exists() else None
        target_results = read_json(mission_root / "target_results.json") if mission_root is not None else {}
        visit_runtime = self._visit_mission_runtime_state()
        gather_runtime = self._gather_mission_runtime_state()
        artifacts = {
            "gather_mission": str(mission_root) if mission_root is not None else "",
            "mission_verdict": str(summary_path) if summary_path and summary_path.exists() else "",
            "target_results": str(mission_root / "target_results.json") if mission_root is not None else "",
            "scorecard": str(mission_root / "scorecard.md") if mission_root is not None else "",
            "log": str(log_path),
        }
        if proc.returncode not in {0, 2} and not verdict:
            raise RuntimeError(output.strip() or "gather mission scenario failed")

        payload = {
            "scenario_id": scenario.id,
            "phase": scenario.phase,
            "pass": pass_flag,
            "artifacts": artifacts,
            "summary": summary,
            "mission_verdict": verdict,
            "proof_verdict": verdict,
            "target_results": target_results,
            "message": "Gather mission passed" if pass_flag else "Gather mission failed",
            "motion_evidence": bool(pass_flag or gather_runtime.get("latest_control_command")),
            "proof_state": str(visit_runtime.get("proof_state", "completed" if pass_flag else "failed") or ("completed" if pass_flag else "failed")),
            "mission_phase": str(gather_runtime.get("mission_phase", "completed" if pass_flag else "failed") or ("completed" if pass_flag else "failed")),
            "mission_status": str(gather_runtime.get("mission_status", "completed" if pass_flag else "failed") or ("completed" if pass_flag else "failed")),
            "search_bias_active": bool(visit_runtime.get("search_bias_active", False)),
            "current_target_id": str(gather_runtime.get("current_target_id", visit_runtime.get("current_target_id", "")) or ""),
            "visit_index": int(gather_runtime.get("visit_index", visit_runtime.get("visit_index", 0)) or 0),
            "visited_targets": list(visit_runtime.get("visited_targets", [])) if isinstance(visit_runtime.get("visited_targets"), list) else [],
            "remaining_targets": list(gather_runtime.get("remaining_targets", [])) if isinstance(gather_runtime.get("remaining_targets"), list) else [],
            "last_visit_result": visit_runtime.get("last_visit_result", {}) if isinstance(visit_runtime.get("last_visit_result"), dict) else {},
            "gather_phase": str(gather_runtime.get("gather_phase", "completed" if pass_flag else "failed") or ("completed" if pass_flag else "failed")),
            "capture_state": gather_runtime.get("capture_state", {}) if isinstance(gather_runtime.get("capture_state"), dict) else {},
            "zone_pose": gather_runtime.get("zone_pose", {}) if isinstance(gather_runtime.get("zone_pose"), dict) else {},
            "zone_score": gather_runtime.get("zone_score", {}) if isinstance(gather_runtime.get("zone_score"), dict) else {},
            "final_corral_audit": gather_runtime.get(
                "final_corral_audit",
                verdict.get("final_corral_audit", {}),
            ) if isinstance(gather_runtime.get("final_corral_audit", verdict.get("final_corral_audit", {})), dict) else {},
            "placed_targets": list(gather_runtime.get("placed_targets", [])) if isinstance(gather_runtime.get("placed_targets"), list) else [],
            "capture_loss_count": int(gather_runtime.get("capture_loss_count", 0) or 0),
            "route_order": list(gather_runtime.get("route_order", [])) if isinstance(gather_runtime.get("route_order"), list) else [],
            "surface_profile": str(gather_runtime.get("surface_profile", env.get("CHASECAR_SURFACE_PROFILE", scenario.surface_profile)) or ""),
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
  gz service -s "/world/{DEFAULT_WORLD_NAME}/remove/blocking" --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"{TARGET_MODEL_NAME_PROOF}\\" type: 2" >/dev/null 2>&1 || true
  gz service -s "/world/{DEFAULT_WORLD_NAME}/remove/blocking" --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"visit_mission_target_ball_1\\" type: 2" >/dev/null 2>&1 || true
  gz service -s "/world/{DEFAULT_WORLD_NAME}/remove/blocking" --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"visit_mission_target_ball_2\\" type: 2" >/dev/null 2>&1 || true
  gz service -s "/world/{DEFAULT_WORLD_NAME}/remove/blocking" --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"visit_mission_target_ball_3\\" type: 2" >/dev/null 2>&1 || true
  gz service -s "/world/{DEFAULT_WORLD_NAME}/remove/blocking" --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"visit_mission_target\\" type: 2" >/dev/null 2>&1 || true
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

    def _dispatch_intent_via_inbox(self, preview: Dict[str, Any]) -> Dict[str, Any]:
        """Write intent to file inbox; the executor picks it up in <100ms."""
        intent_name = str(preview.get("intent", ""))
        args_payload = dict(preview.get("args", {}))
        payload = dict(preview.get("payload", {}))
        inbox_payload = {
            "intent": intent_name,
            "seq": int(payload.get("seq", 0) or int(time.time() * 1000)),
            "planner": str(payload.get("planner", "dashboard_service")),
            "timestamp_utc": str(payload.get("timestamp_utc", "") or utc_now()),
            "args": args_payload,
        }
        # Clear stale ack before writing inbox.
        try:
            self.intent_ack_path.unlink()
        except FileNotFoundError:
            pass
        ensure_dir(self.runtime_dir)
        self.intent_inbox_path.write_text(
            json.dumps(inbox_payload, separators=(",", ":")) + "\n", encoding="utf-8",
        )
        # Poll for ack from the executor (up to 2s).
        deadline = time.monotonic() + 2.0
        ack: Dict[str, Any] = {}
        while time.monotonic() < deadline:
            if self.intent_ack_path.exists():
                try:
                    ack = json.loads(self.intent_ack_path.read_text(encoding="utf-8"))
                    break
                except (json.JSONDecodeError, OSError):
                    pass
            time.sleep(0.05)
        accepted = bool(ack.get("accepted", False))
        return {
            "pass": accepted,
            "feedback_seen": accepted,
            "feedback_samples": [f"{intent_name}: dispatched via direct inbox"] if accepted else [],
            "boundary_activity_seen": False,
            "dispatch_method": "direct_inbox",
            "ack": ack,
        }

    def _run_intent_sync_docker(self, preview: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy path: dispatch intent via docker exec subprocess."""
        intent_name = str(preview.get("intent", ""))
        args_payload = dict(preview.get("args", {}))
        payload = dict(preview.get("payload", {}))
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
        return read_json(output_path)

    def _run_intent_sync(self, preview: Dict[str, Any]) -> Dict[str, Any]:
        intent_name = str(preview.get("intent", ""))
        args_payload = dict(preview.get("args", {}))
        payload = dict(preview.get("payload", {}))
        readiness = dict(preview.get("readiness", {}))
        if intent_name not in self.frozen_intents:
            raise ValueError(f"Unsupported frozen intent: {intent_name}")
        # Use direct file inbox when the executor is running (gate-stack up).
        use_direct = bool(self.sim_gate_container_id)
        if use_direct:
            result = self._dispatch_intent_via_inbox(preview)
        else:
            result = self._run_intent_sync_docker(preview)
        history_entry = {
            "event_type": "execute",
            "timestamp_utc": utc_now(),
            "intent": intent_name,
            "args": args_payload,
            "payload": payload,
            "readiness": readiness,
            "pass": bool(result.get("pass")),
            "feedback_seen": bool(result.get("feedback_seen")),
            "feedback_samples": result.get("feedback_samples", []),
            "boundary_activity_seen": bool(result.get("boundary_activity_seen", False)),
            "dispatch_method": str(result.get("dispatch_method", "docker_exec")),
        }
        self._record_command_history(history_entry)
        self._record_visual_event(
            {
                "event_type": "intent_executed",
                "intent": intent_name,
                "payload": payload,
                "pass": bool(result.get("pass")),
                "dispatch_method": str(result.get("dispatch_method", "docker_exec")),
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

    def _serve_file(self, path: Path, content_type: str, *, no_cache: bool = False) -> None:
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if no_cache:
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
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
        if path in {"/", "/dashboard.html", "/beta", "/beta/", "/beta_dashboard.html"}:
            return self._serve_file(STATIC_DASHBOARD_DIR / "beta_dashboard.html", "text/html; charset=utf-8")
        if path in {"/classic", "/classic/", "/browser_dashboard.html"}:
            return self._serve_file(STATIC_DASHBOARD_DIR / "browser_dashboard.html", "text/html; charset=utf-8")
        if path == "/browser_dashboard.js":
            return self._serve_file(STATIC_DASHBOARD_DIR / "browser_dashboard.js", "text/javascript; charset=utf-8")
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
            return self._serve_file(live_path, content_type, no_cache=True)
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
            status, payload = controller.request_start(body)
            return self._json_response(status, payload)
        if path == "/api/env/stop":
            status, payload = controller.request_stop()
            return self._json_response(status, payload)
        if path == "/api/env/refresh":
            status, payload = controller.request_refresh()
            return self._json_response(status, payload)
        if path == "/api/sim/reset":
            status, payload = controller.request_reset_sim(body)
            return self._json_response(status, payload)
        if path == "/api/scenario/run":
            scenario_id = str(body.get("scenario_id", "")).strip()
            status, payload = controller.request_scenario_run(scenario_id, body)
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
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], controller: DashboardController) -> None:
        super().__init__(server_address, DashboardRequestHandler)
        self.controller = controller


def _kill_stale_dashboard_on_port(port: int) -> None:
    """Find and kill any existing processes listening on *port*.

    This prevents zombie dashboard instances from accumulating when the
    service is restarted (e.g. after a code fix) without first killing
    the old process.  Works on both Windows and Linux.
    """
    my_pid = os.getpid()
    pids_to_kill: list[int] = []

    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                ["netstat", "-ano"], text=True, stderr=subprocess.DEVNULL,
            )
        except Exception:
            return
        for line in out.splitlines():
            if "LISTENING" not in line:
                continue
            parts = line.split()
            # Format: proto  local_addr  foreign_addr  state  pid
            if len(parts) < 5:
                continue
            local_addr = parts[1]
            if local_addr.endswith(f":{port}"):
                try:
                    pid = int(parts[-1])
                except ValueError:
                    continue
                if pid != my_pid and pid > 0:
                    pids_to_kill.append(pid)
        for pid in pids_to_kill:
            print(f"[dashboard] killing stale process {pid} on port {port}")
            subprocess.call(
                ["taskkill", "/PID", str(pid), "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    else:
        # Linux / macOS
        try:
            out = subprocess.check_output(
                ["ss", "-tlnp", f"sport = :{port}"],
                text=True, stderr=subprocess.DEVNULL,
            )
        except Exception:
            return
        for line in out.splitlines():
            # Extract pid from pid=<N> token
            m = re.search(r"pid=(\d+)", line)
            if m:
                pid = int(m.group(1))
                if pid != my_pid and pid > 0:
                    pids_to_kill.append(pid)
        for pid in pids_to_kill:
            print(f"[dashboard] killing stale process {pid} on port {port}")
            try:
                os.kill(pid, 9)
            except OSError:
                pass

    if pids_to_kill:
        # Brief pause for the OS to release the socket.
        time.sleep(0.5)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the Chasecar operator dashboard control plane.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8860)
    parser.add_argument(
        "--runtime-dir",
        default="",
        help="Optional repo-local runtime state directory for this dashboard instance.",
    )
    parser.add_argument(
        "--peer-project-cleanup",
        choices=("exclusive", "none"),
        default="exclusive",
        help="Whether startup should remove peer dashboard compose projects.",
    )
    parser.add_argument(
        "--headless-worker",
        action="store_true",
        help="Start only the sim and gate stack needed for non-interactive soak workers.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _kill_stale_dashboard_on_port(args.port)
    # Use 127.0.0.1 for client-facing URL when binding to all interfaces;
    # 0.0.0.0 is not a valid connect target on Windows.
    client_host = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    controller = DashboardController(
        host=args.host,
        port=args.port,
        runtime_dir=resolve_runtime_dir(args.runtime_dir),
        peer_project_cleanup=args.peer_project_cleanup,
        headless_worker_mode=args.headless_worker,
    )
    controller._update_state(dashboard_url=f"http://{client_host}:{args.port}/")
    server = DashboardHttpServer((args.host, args.port), controller)
    print(f"DASHBOARD_URL=http://{client_host}:{args.port}/")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
