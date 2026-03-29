#!/usr/bin/env python3
"""Headless proof harness for turn-then-go bounded LLM control."""

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

from brain_state_digest import build_state_digest
from brain_state_digest import state_digest_hash
from llm_provider_local import LocalModelProvider
from llm_provider_local import LocalStubProvider
from llm_provider_openai import OpenAIResponsesProvider
from llm_supervisor_core import DEFAULT_DASHBOARD_URL
from llm_supervisor_core import DEFAULT_OPENAI_MODEL
from llm_supervisor_core import DEFAULT_REASONING_EFFORT
from llm_supervisor_core import attempt_deterministic_recommendation
from llm_supervisor_core import append_jsonl
from llm_supervisor_core import blocked_decision
from llm_supervisor_core import blocked_from_preview
from llm_supervisor_core import decision_signature
from llm_supervisor_core import dispatch_intent
from llm_supervisor_core import fetch_dashboard_state
from llm_supervisor_core import http_json
from llm_supervisor_core import load_contract
from llm_supervisor_core import normalize_model_decision
from llm_supervisor_core import preview_intent
from llm_supervisor_core import preview_summary
from llm_supervisor_core import utc_now
from llm_supervisor_core import validate_decision_against_canonical_space
from llm_supervisor_core import validate_decision_against_contract
from llm_supervisor_core import write_json


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = REPO_ROOT / "runtime" / "dashboard"
PROOF_RUNTIME_STATE_PATH = RUNTIME_DIR / "llm_turn_then_go_runtime.json"
DOCKER_FALLBACK = Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe")
DEFAULT_WORLD_NAME = "yolo_test_world"
DEFAULT_TARGET_MODEL_NAME = "uat_nav2_target"
DEFAULT_TARGET_MODEL_SDF = REPO_ROOT / "ros2_config" / "frisbee_target_ball.sdf"
DEFAULT_TASK_TEXT = (
    "Use the bounded frozen robot controls to find the ball and go to it. "
    "If the ball is not visible, choose search_for_target(ball). "
    "Once the ball is visible and locked, choose plan_to_target(0.25) or track_target() as appropriate. "
    "Prefer safe_stop() if the state becomes unsafe or uncertain."
)


def normalize_angle(value: float) -> float:
    while value > math.pi:
        value -= 2.0 * math.pi
    while value < -math.pi:
        value += 2.0 * math.pi
    return value


def choose_docker_cli() -> str:
    found = shutil.which("docker")
    if found:
        return found
    if DOCKER_FALLBACK.exists():
        return str(DOCKER_FALLBACK)
    raise FileNotFoundError("Unable to locate docker CLI.")


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def to_container_repo_path(path: Path) -> str:
    resolved = path.resolve()
    relative = resolved.relative_to(REPO_ROOT.resolve())
    return "/workspaces/chasecar/" + str(relative).replace("\\", "/")


class ProofRunner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.dashboard_url = args.dashboard_url.rstrip("/")
        self.contract = load_contract(Path(args.contract).resolve())
        self.provider = self._build_provider(args)
        self.docker = choose_docker_cli()
        self.last_state_hash = ""
        self.last_decision_signature = ""
        self.last_dispatch_monotonic = 0.0
        self.pose_history: list[dict[str, float]] = []
        self.search_dispatched = False
        self.acquire_dispatched = False
        self.plan_or_track_dispatched = False
        self.target_locked_seen = False
        self.nav_activity_seen = False
        self.first_visible_distance_m: float | None = None
        self.best_visible_distance_m: float | None = None
        self.runtime_state: dict[str, Any] = {
            "running": False,
            "scenario_id": str(args.scenario_id),
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
        self._event_keys: set[str] = set()

    def _persist_runtime_state(self) -> None:
        write_json(PROOF_RUNTIME_STATE_PATH, self.runtime_state)

    def _update_runtime_state(self, **updates: Any) -> None:
        self.runtime_state.update(updates)
        self.runtime_state["updated_utc"] = utc_now()
        self._persist_runtime_state()

    def _append_runtime_event(self, message: str, *, category: str = "proof", key: str = "") -> None:
        event_key = key or message
        if event_key in self._event_keys:
            return
        self._event_keys.add(event_key)
        event = {
            "timestamp_utc": utc_now(),
            "message": str(message),
            "category": str(category),
            "source": "llm_proof",
        }
        events = list(self.runtime_state.get("recent_operator_events", []))
        events.append(event)
        self.runtime_state["recent_operator_events"] = events[-20:]
        self.runtime_state["latest_operator_event"] = event["message"]
        self.runtime_state["updated_utc"] = event["timestamp_utc"]
        self._persist_runtime_state()

    def _format_decision_label(self, decision: dict[str, Any]) -> str:
        intent = str(decision.get("intent", "") or "")
        args = dict(decision.get("args", {}))
        if intent == "search_for_target":
            return f"{intent}({args.get('target_class', 'ball')})"
        if intent == "acquire_target":
            return f"{intent}({args.get('target_class', 'ball')})"
        if intent == "plan_to_target":
            return f"{intent}({args.get('approach_distance_m', 0.25)})"
        if intent:
            return f"{intent}()"
        return "blocked"

    def _infer_proof_state(self, state: dict[str, Any]) -> str:
        brain = state.get("brain", {}) if isinstance(state.get("brain"), dict) else {}
        outcome = state.get("outcome", {}) if isinstance(state.get("outcome"), dict) else {}
        perception = state.get("perception", {}) if isinstance(state.get("perception"), dict) else {}
        if self._proof_pass():
            return "completed"
        if self.plan_or_track_dispatched and (
            bool(brain.get("goal_in_progress", False))
            or bool(outcome.get("nav_goal_recent", False))
            or bool(outcome.get("cmd_vel_recent", False))
        ):
            return "moving"
        if bool(brain.get("target_locked", False)) or bool(brain.get("target_visible_recent", False)) or bool(perception.get("target_visible_now", False)):
            return "target_locked"
        if self.search_dispatched or bool(brain.get("search_active", False)):
            return "searching"
        return "waiting"

    def _build_provider(self, args: argparse.Namespace):
        provider_name = str(args.provider).strip().lower()
        if provider_name == "openai":
            return OpenAIResponsesProvider(
                api_key=os.environ.get("OPENAI_API_KEY", ""),
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                base_url=os.environ.get("OPENAI_BASE_URL", ""),
                org_id=os.environ.get("OPENAI_ORG_ID", ""),
                project_id=os.environ.get("OPENAI_PROJECT_ID", ""),
            )
        if provider_name == "local_stub":
            return LocalStubProvider(model=args.model)
        if provider_name == "local_model":
            return LocalModelProvider(model=args.model)
        raise ValueError(f"Unsupported proof provider: {args.provider}")

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
            error_text="Environment did not become ready.",
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
            error_text="Robot pose did not become available after environment startup.",
        )

    def _stop_environment(self) -> None:
        self._request("POST", "/api/env/stop", timeout_s=10.0)
        self._wait_for_state(
            lambda current: current.get("environment_state") == "stopped",
            timeout_s=240.0,
            error_text="Environment did not stop cleanly.",
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
        container_id = proc.stdout.strip().splitlines()
        if not container_id:
            raise RuntimeError(f"No running container id found for {service_name}.")
        return container_id[0].strip()

    def _docker_exec(self, container_id: str, script: str) -> tuple[int, str]:
        proc = subprocess.run(
            [
                self.docker,
                "exec",
                "-i",
                container_id,
                "bash",
                "-lc",
                "cat >/tmp/chasecar_llm_proof.sh && chmod +x /tmp/chasecar_llm_proof.sh && /tmp/chasecar_llm_proof.sh",
            ],
            cwd=str(REPO_ROOT),
            input=script.encode("utf-8"),
            capture_output=True,
            check=False,
        )
        output = (proc.stdout or b"").decode("utf-8", errors="replace")
        output += ("\n" + (proc.stderr or b"").decode("utf-8", errors="replace")) if proc.stderr else ""
        return proc.returncode, output.strip()

    def _spawn_target_relative_to_robot(self, state: dict[str, Any], proof_root: Path) -> dict[str, Any]:
        robot_pose = state.get("belief", {}).get("latest_robot_pose", {}) if isinstance(state.get("belief"), dict) else {}
        if not isinstance(robot_pose, dict) or robot_pose.get("x") is None or robot_pose.get("y") is None or robot_pose.get("yaw") is None:
            raise RuntimeError("Robot pose unavailable for proof target spawn.")
        robot_x = float(robot_pose["x"])
        robot_y = float(robot_pose["y"])
        robot_yaw = float(robot_pose["yaw"])
        local_x = abs(self.args.target_behind_m)
        local_y = float(self.args.target_lateral_m)
        target_x = robot_x + (math.cos(robot_yaw) * local_x) - (math.sin(robot_yaw) * local_y)
        target_y = robot_y + (math.sin(robot_yaw) * local_x) + (math.cos(robot_yaw) * local_y)
        target_z = float(self.args.target_z_m)
        turned_robot_yaw = robot_yaw if self.args.start_visible else normalize_angle(robot_yaw + math.pi)
        half_yaw = 0.5 * turned_robot_yaw
        robot_qz = math.sin(half_yaw)
        robot_qw = math.cos(half_yaw)

        compose_project = str(state.get("compose_project", "") or "")
        if not compose_project:
            raise RuntimeError("Active compose project missing from dashboard state.")
        sim_gate_container = self._container_id(compose_project, "sim-gate")
        world_name = str(state.get("world_name", DEFAULT_WORLD_NAME) or DEFAULT_WORLD_NAME)
        model_sdf_host = Path(self.args.target_model_sdf).resolve()
        model_sdf = to_container_repo_path(model_sdf_host) if model_sdf_host.is_absolute() else self.args.target_model_sdf
        model_name = self.args.target_model_name
        log_path = proof_root / "spawn_target.log"
        script = f"""
set -eo pipefail
set +u
source /opt/ros/${{CORE_ROS_DISTRO:-kilted}}/setup.bash
set -u
MODEL_FILE={json.dumps(model_sdf)}
MODEL_NAME={json.dumps(model_name)}
WORLD_NAME={json.dumps(world_name)}
TARGET_X={json.dumps(f"{target_x:.6f}")}
TARGET_Y={json.dumps(f"{target_y:.6f}")}
TARGET_Z={json.dumps(f"{target_z:.6f}")}
ROBOT_X={json.dumps(f"{robot_x:.6f}")}
ROBOT_Y={json.dumps(f"{robot_y:.6f}")}
ROBOT_Z={json.dumps("0.000000")}
ROBOT_QZ={json.dumps(f"{robot_qz:.6f}")}
ROBOT_QW={json.dumps(f"{robot_qw:.6f}")}
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
spawn_create true > /tmp/chasecar_proof_spawn.log 2>&1
rc=$?
if [[ "$rc" -ne 0 ]] && grep -Eq 'Waiting for service \\[/world/.*/create\\] to become available' /tmp/chasecar_proof_spawn.log 2>/dev/null; then
  spawn_create false >> /tmp/chasecar_proof_spawn.log 2>&1
  rc=$?
fi
if [[ "$rc" -eq 0 ]] && command -v gz >/dev/null 2>&1; then
  gz service -s "/world/$WORLD_NAME/set_pose/blocking" --reqtype gz.msgs.Pose --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"$MODEL_NAME\\" position {{ x: $TARGET_X y: $TARGET_Y z: $TARGET_Z }} orientation {{ x: 0 y: 0 z: 0 w: 1 }}" >> /tmp/chasecar_proof_spawn.log 2>&1
  target_setpose_rc=$?
  if [[ "$target_setpose_rc" -ne 0 ]]; then
    rc="$target_setpose_rc"
  fi
fi
if [[ "$rc" -eq 0 ]] && command -v gz >/dev/null 2>&1; then
  gz service -s "/world/$WORLD_NAME/set_pose/blocking" --reqtype gz.msgs.Pose --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"jetbot\\" position {{ x: $ROBOT_X y: $ROBOT_Y z: $ROBOT_Z }} orientation {{ x: 0 y: 0 z: $ROBOT_QZ w: $ROBOT_QW }}" >> /tmp/chasecar_proof_spawn.log 2>&1
  setpose_rc=$?
  if [[ "$setpose_rc" -ne 0 ]]; then
    rc="$setpose_rc"
  fi
fi
cat /tmp/chasecar_proof_spawn.log
exit "$rc"
"""
        rc, output = self._docker_exec(sim_gate_container, script)
        log_path.write_text(output + "\n", encoding="utf-8")
        payload = {
            "generated_utc": utc_now(),
            "scenario_id": str(self.args.scenario_id),
            "start_visible": bool(self.args.start_visible),
            "robot_pose": {"x": robot_x, "y": robot_y, "yaw": robot_yaw},
            "robot_pose_after_turnaway": {"x": robot_x, "y": robot_y, "yaw": turned_robot_yaw},
            "target_world": {"x": target_x, "y": target_y, "z": target_z},
            "compose_project": compose_project,
            "sim_gate_container": sim_gate_container,
            "world_name": world_name,
            "model_name": model_name,
            "model_sdf": str(model_sdf_host),
            "model_sdf_container": model_sdf,
            "spawn_rc": rc,
            "log_path": str(log_path),
            "output": output,
            "pass": rc == 0,
        }
        write_json(proof_root / "spawn_target.json", payload)
        if rc != 0:
            raise RuntimeError(f"Failed to spawn proof target: {output}")
        return payload

    def _wait_for_robot_yaw(self, expected_yaw: float, timeout_s: float) -> dict[str, Any]:
        def yaw_ready(current: dict[str, Any]) -> bool:
            belief = current.get("belief", {}) if isinstance(current.get("belief"), dict) else {}
            pose = belief.get("latest_robot_pose")
            if not isinstance(pose, dict) or pose.get("yaw") is None:
                return False
            return abs(normalize_angle(float(pose["yaw"]) - expected_yaw)) <= 0.35

        return self._wait_for_state(
            yaw_ready,
            timeout_s=timeout_s,
            error_text="Robot yaw did not settle to the proof turn-away pose.",
        )

    def _record_pose(self, state: dict[str, Any]) -> None:
        belief = state.get("belief", {}) if isinstance(state.get("belief"), dict) else {}
        pose = belief.get("latest_robot_pose")
        if not isinstance(pose, dict):
            return
        x = pose.get("x")
        y = pose.get("y")
        yaw = pose.get("yaw")
        if x is None or y is None or yaw is None:
            return
        self.pose_history.append({"x": float(x), "y": float(y), "yaw": float(yaw)})

    def _cumulative_yaw_change_rad(self) -> float:
        if len(self.pose_history) < 2:
            return 0.0
        total = 0.0
        for index in range(1, len(self.pose_history)):
            prev = self.pose_history[index - 1]["yaw"]
            current = self.pose_history[index]["yaw"]
            total += abs(normalize_angle(current - prev))
        return total

    def _linear_displacement_m(self) -> float:
        if len(self.pose_history) < 2:
            return 0.0
        start = self.pose_history[0]
        end = self.pose_history[-1]
        return math.hypot(end["x"] - start["x"], end["y"] - start["y"])

    def _update_proof_observations(self, state: dict[str, Any]) -> None:
        self._record_pose(state)
        brain = state.get("brain", {}) if isinstance(state.get("brain"), dict) else {}
        outcome = state.get("outcome", {}) if isinstance(state.get("outcome"), dict) else {}
        belief = state.get("belief", {}) if isinstance(state.get("belief"), dict) else {}
        if bool(brain.get("target_locked", False)):
            self.target_locked_seen = True
        if bool(brain.get("goal_in_progress", False)) or bool(outcome.get("nav_goal_recent", False)):
            self.nav_activity_seen = True
        distance = belief.get("latest_target_distance_m")
        if distance is not None:
            distance_f = float(distance)
            if self.first_visible_distance_m is None and bool(state.get("perception", {}).get("target_visible_now", False)):
                self.first_visible_distance_m = distance_f
            if self.best_visible_distance_m is None or distance_f < self.best_visible_distance_m:
                self.best_visible_distance_m = distance_f

    def _proof_pass(self) -> bool:
        yaw_ok = self._cumulative_yaw_change_rad() >= 0.75
        displacement_ok = self._linear_displacement_m() >= 0.20
        distance_ok = False
        if self.first_visible_distance_m is not None and self.best_visible_distance_m is not None:
            distance_ok = self.best_visible_distance_m <= (self.first_visible_distance_m - 0.10)
        search_ok = self.search_dispatched or bool(self.args.skip_search_requirement)
        return bool(
            search_ok
            and self.plan_or_track_dispatched
            and self.target_locked_seen
            and self.nav_activity_seen
            and (yaw_ok or bool(self.args.skip_search_requirement))
            and (distance_ok or displacement_ok)
        )

    def run(self) -> dict[str, Any]:
        enabled, disabled_reason = self.provider.is_enabled()
        if not enabled:
            raise RuntimeError(disabled_reason or "LLM provider is disabled.")

        ready_state, started_here = self._ensure_environment_ready()
        ready_state = self._wait_for_robot_pose(timeout_s=self.args.environment_timeout_s)
        session_id = str(ready_state.get("session_id", "") or "")
        if not session_id:
            raise RuntimeError("Dashboard did not provide a session id.")

        proof_root = ensure_dir(REPO_ROOT / "artifacts" / "session" / session_id / self.args.artifact_kind / current_utc_stamp())
        decision_history_path = proof_root / "decision_history.jsonl"
        state_history_path = proof_root / "state_history.jsonl"
        self.runtime_state = {
            "running": True,
            "scenario_id": str(self.args.scenario_id),
            "session_id": session_id,
            "proof_state": "waiting",
            "latest_operator_event": "",
            "recent_operator_events": [],
            "latest_decision": {},
            "latest_feedback": "",
            "artifact_dir": str(proof_root),
            "proof_verdict": {},
            "updated_utc": utc_now(),
        }
        self._event_keys = set()
        self._persist_runtime_state()
        self._append_runtime_event(f"{self.args.scenario_label} scenario started.", category="scenario", key="scenario_started")

        try:
            spawn_info = self._spawn_target_relative_to_robot(ready_state, proof_root)
            spawn_message = "Proof target spawned in front of the robot." if self.args.start_visible else "Proof target spawned behind the robot."
            self._append_runtime_event(spawn_message, key="target_spawned")
            try:
                self._wait_for_robot_yaw(float(spawn_info["robot_pose_after_turnaway"]["yaw"]), timeout_s=20.0)
            except Exception as exc:
                append_jsonl(
                    decision_history_path,
                    {
                        "event_type": "proof_setup_warning",
                        "generated_utc": utc_now(),
                        "warning": str(exc),
                    },
                )
            status, payload = self._request("POST", "/api/intents/dispatch", {"intent": "safe_stop", "args": {}}, timeout_s=10.0)
            append_jsonl(
                decision_history_path,
                {
                    "event_type": "initial_stop",
                    "generated_utc": utc_now(),
                    "dispatch_status": status,
                    "dispatch_payload": payload,
                },
            )
            self._update_runtime_state(latest_feedback=str(payload.get("message", "") or ""))

            deadline = time.monotonic() + max(self.args.max_runtime_s, 5.0)
            while time.monotonic() < deadline:
                state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
                self._update_proof_observations(state)
                self._update_runtime_state(
                    proof_state=self._infer_proof_state(state),
                    latest_feedback=str(
                        (
                            (state.get("brain", {}) if isinstance(state.get("brain"), dict) else {}).get("last_feedback_text")
                            or state.get("last_feedback")
                            or self.runtime_state.get("latest_feedback", "")
                        )
                    ),
                )
                brain = state.get("brain", {}) if isinstance(state.get("brain"), dict) else {}
                outcome = state.get("outcome", {}) if isinstance(state.get("outcome"), dict) else {}
                perception = state.get("perception", {}) if isinstance(state.get("perception"), dict) else {}
                if bool(brain.get("search_active", False)):
                    self._append_runtime_event("Robot began search turn.", key="search_turn")
                if bool(brain.get("target_locked", False)) or bool(perception.get("target_visible_now", False)):
                    self._append_runtime_event("Target visible and locked.", key="target_locked")
                if self.plan_or_track_dispatched and (
                    bool(brain.get("goal_in_progress", False))
                    or bool(outcome.get("nav_goal_recent", False))
                    or bool(outcome.get("cmd_vel_recent", False))
                ):
                    self._append_runtime_event("Robot began move-to-target.", key="move_started")
                if self.best_visible_distance_m is not None and self.first_visible_distance_m is not None and self.best_visible_distance_m < self.first_visible_distance_m:
                    self._append_runtime_event("Motion progress observed.", key="motion_progress")
                append_jsonl(
                    state_history_path,
                    {
                        "generated_utc": utc_now(),
                        "environment_state": state.get("environment_state", ""),
                        "phase": state.get("phase", ""),
                        "target_id": state.get("target_id", ""),
                        "perception": state.get("perception", {}),
                        "belief": state.get("belief", {}),
                        "brain": state.get("brain", {}),
                        "outcome": state.get("outcome", {}),
                    },
                )
                if self._proof_pass():
                    break

                digest = build_state_digest(state, self.contract)
                state_hash = state_digest_hash(digest)
                if state_hash == self.last_state_hash and (time.monotonic() - self.last_dispatch_monotonic) < self.args.poll_s:
                    time.sleep(self.args.poll_s)
                    continue

                provider_name = self.provider.provider_name
                provider_model = self.provider.model_name
                evaluation_kind = "provider"
                preview_status = 0
                preview_payload: dict[str, Any] = {}
                dispatch_status = 0
                dispatch_payload: dict[str, Any] = {}

                deterministic = attempt_deterministic_recommendation(
                    task_text=self.args.task,
                    state=state,
                    contract=self.contract,
                    dashboard_url=self.dashboard_url,
                    timeout_s=self.args.timeout_s,
                    digest=digest,
                )
                if deterministic is not None:
                    decision = dict(deterministic.decision)
                    preview_status = deterministic.preview_status
                    preview_payload = dict(deterministic.preview_payload)
                    evaluation_kind = deterministic.evaluation_kind
                    provider_name = "deterministic_recommendation"
                    provider_model = self.provider.model_name
                else:
                    try:
                        provider_result = self.provider.recommend(
                            task_text=self.args.task,
                            digest=digest,
                            contract=self.contract,
                            timeout_s=self.args.timeout_s,
                        )
                        provider_name = provider_result.provider
                        provider_model = provider_result.model
                        decision = normalize_model_decision(provider_result.decision)
                        decision = validate_decision_against_contract(decision, self.contract)
                        decision = validate_decision_against_canonical_space(decision)
                    except Exception as exc:
                        decision = blocked_decision(
                            self.args.task,
                            "Provider output could not be validated.",
                            missing_prerequisites=["provider_output_invalid"],
                            expected_observations=[],
                            confidence=0.0,
                        )
                        decision["rationale_short"] = f"{decision['rationale_short']} {exc}"

                    if decision.get("status") == "recommendation":
                        preview_status, preview_payload = preview_intent(
                            self.dashboard_url,
                            str(decision.get("intent", "")),
                            dict(decision.get("args", {})),
                            timeout_s=self.args.timeout_s,
                        )
                        preview = preview_summary(preview_status, preview_payload)
                        if preview_status != 200 or not preview["contract_valid"] or not preview["ready_to_dispatch"]:
                            decision = blocked_from_preview(
                                task_text=self.args.task,
                                decision=decision,
                                preview_status=preview_status,
                                preview_payload=preview_payload,
                            )

                if decision.get("status") == "recommendation":
                    signature = decision_signature(decision)
                    if signature != self.last_decision_signature or (time.monotonic() - self.last_dispatch_monotonic) >= self.args.dispatch_cooldown_s:
                        dispatch_status, dispatch_payload = dispatch_intent(
                            self.dashboard_url,
                            str(decision.get("intent", "")),
                            dict(decision.get("args", {})),
                            timeout_s=self.args.timeout_s,
                        )
                        if dispatch_status == 202 and bool(dispatch_payload.get("accepted", False)):
                            self.last_decision_signature = signature
                            self.last_dispatch_monotonic = time.monotonic()
                            self._update_runtime_state(latest_decision=decision)
                            self._append_runtime_event(
                                f"LLM emitted {self._format_decision_label(decision)}.",
                                category="decision",
                                key=f"decision:{signature}",
                            )
                            if decision.get("intent") == "search_for_target":
                                self.search_dispatched = True
                            if decision.get("intent") == "acquire_target":
                                self.acquire_dispatched = True
                            if decision.get("intent") in {"plan_to_target", "track_target"}:
                                self.plan_or_track_dispatched = True

                append_jsonl(
                    decision_history_path,
                    {
                        "generated_utc": utc_now(),
                        "state_hash": state_hash,
                        "provider": provider_name,
                        "model": provider_model,
                        "decision": decision,
                        "preview": preview_summary(preview_status, preview_payload),
                        "evaluation_kind": evaluation_kind,
                        "dispatch_status": dispatch_status,
                        "dispatch_payload": dispatch_payload,
                    },
                )
                self.last_state_hash = state_hash
                time.sleep(self.args.poll_s)

            final_state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
            self._update_proof_observations(final_state)
            yaw_change_rad = self._cumulative_yaw_change_rad()
            displacement_m = self._linear_displacement_m()
            proof_verdict = {
                "generated_utc": utc_now(),
                "session_id": session_id,
                "scenario_id": str(self.args.scenario_id),
                "provider": self.provider.provider_name,
                "model": self.provider.model_name,
                "task_text": self.args.task,
                "spawn_target": spawn_info,
                "search_dispatched": self.search_dispatched,
                "acquire_dispatched": self.acquire_dispatched,
                "plan_or_track_dispatched": self.plan_or_track_dispatched,
                "target_locked_seen": self.target_locked_seen,
                "nav_activity_seen": self.nav_activity_seen,
                "cumulative_yaw_change_rad": round(yaw_change_rad, 6),
                "linear_displacement_m": round(displacement_m, 6),
                "first_visible_distance_m": self.first_visible_distance_m,
                "best_visible_distance_m": self.best_visible_distance_m,
                "pass": self._proof_pass(),
                "decision_history_path": str(decision_history_path),
                "state_history_path": str(state_history_path),
                "brain_feedback_history_path": str(REPO_ROOT / "artifacts" / "session" / session_id / "visual" / "brain_feedback.jsonl"),
            }
            write_json(proof_root / "proof_verdict.json", proof_verdict)
            self._update_runtime_state(
                running=False,
                proof_state="completed" if proof_verdict["pass"] else "failed",
                proof_verdict=proof_verdict,
            )
            self._append_runtime_event(
                "Proof completed successfully." if proof_verdict["pass"] else "Proof failed.",
                category="result",
                key="proof_verdict",
            )
            summary = {
                "generated_utc": utc_now(),
                "type": str(self.args.artifact_kind),
                "scenario_id": str(self.args.scenario_id),
                "session_id": session_id,
                "provider": self.provider.provider_name,
                "model": self.provider.model_name,
                "task_text": self.args.task,
                "proof_root": str(proof_root),
                "pass": bool(proof_verdict["pass"]),
                "proof_verdict_path": str(proof_root / "proof_verdict.json"),
            }
            write_json(proof_root / "summary.json", summary)
            try:
                self._request("POST", "/api/intents/dispatch", {"intent": "safe_stop", "args": {}}, timeout_s=10.0)
            except Exception:
                pass
            return summary
        finally:
            self._update_runtime_state(running=False)
            if started_here and not self.args.keep_environment:
                try:
                    self._stop_environment()
                except Exception:
                    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the headless turn-then-go LLM proof.")
    parser.add_argument("--dashboard-url", default=os.environ.get("CHASECAR_DASHBOARD_URL", DEFAULT_DASHBOARD_URL))
    parser.add_argument("--contract", default=str(REPO_ROOT / "runtime" / "contracts" / "llm_control_contract.yaml"))
    parser.add_argument("--provider", default=os.environ.get("CHASECAR_LLM_PROVIDER", "openai"))
    parser.add_argument("--model", default=os.environ.get("OPENAI_SUPERVISOR_MODEL") or "gpt-5-nano")
    parser.add_argument("--reasoning-effort", default=os.environ.get("OPENAI_SUPERVISOR_REASONING_EFFORT") or os.environ.get("OPENAI_REASONING_EFFORT") or DEFAULT_REASONING_EFFORT)
    parser.add_argument("--task", default=DEFAULT_TASK_TEXT)
    parser.add_argument("--scenario-id", default="llm_turn_then_go_proof")
    parser.add_argument("--scenario-label", default="LLM Turn + Go")
    parser.add_argument("--artifact-kind", default="llm_turn_then_go_proof")
    parser.add_argument("--poll-s", type=float, default=1.0)
    parser.add_argument("--timeout-s", type=float, default=45.0)
    parser.add_argument("--dispatch-cooldown-s", type=float, default=2.0)
    parser.add_argument("--environment-timeout-s", type=float, default=360.0)
    parser.add_argument("--max-runtime-s", type=float, default=180.0)
    parser.add_argument("--target-behind-m", type=float, default=1.10)
    parser.add_argument("--target-lateral-m", type=float, default=0.00)
    parser.add_argument("--target-z-m", type=float, default=0.05)
    parser.add_argument("--target-model-name", default=DEFAULT_TARGET_MODEL_NAME)
    parser.add_argument("--target-model-sdf", default=str(DEFAULT_TARGET_MODEL_SDF))
    parser.add_argument("--start-visible", action="store_true")
    parser.add_argument("--skip-search-requirement", action="store_true")
    parser.add_argument("--keep-environment", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runner = ProofRunner(args)
    summary = runner.run()
    print(f"LLM_BOUNDED_DEMO_SUMMARY={summary['proof_verdict_path']}")
    print(f"LLM_TURN_THEN_GO_PROOF_SUMMARY={summary['proof_verdict_path']}")
    print(f"LLM_TURN_THEN_GO_PROOF_PASS={summary['pass']}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
