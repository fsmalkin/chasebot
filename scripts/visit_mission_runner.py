#!/usr/bin/env python3
"""Deterministic visible-ball visit mission runner over the dashboard control plane."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from brain_state_digest import CANONICAL_ARGS_BY_INTENT
from brain_supervisor_policy import build_policy_snapshot
from llm_supervisor_core import DEFAULT_DASHBOARD_URL
from llm_supervisor_core import append_jsonl
from llm_supervisor_core import blocked_decision
from llm_supervisor_core import decision_signature
from llm_supervisor_core import dispatch_intent
from llm_supervisor_core import fetch_dashboard_state
from llm_supervisor_core import http_json
from llm_supervisor_core import load_contract
from llm_supervisor_core import preview_intent
from llm_supervisor_core import preview_summary
from llm_supervisor_core import utc_now
from llm_supervisor_core import validate_decision_against_canonical_space
from llm_supervisor_core import validate_decision_against_contract
from llm_supervisor_core import write_json


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = REPO_ROOT / "runtime" / "dashboard"
MISSION_RUNTIME_STATE_PATH = RUNTIME_DIR / "visit_mission_runtime.json"
DOCKER_FALLBACK = Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe")
DEFAULT_WORLD_NAME = "yolo_test_world"
DEFAULT_TARGET_MODEL_NAME = "visit_mission_target"
DEFAULT_TARGET_MODEL_SDF = REPO_ROOT / "ros2_config" / "frisbee_target_ball.sdf"
DEFAULT_VISIT_TOLERANCE_M = 0.35
DEFAULT_MIN_TARGET_DWELL_S = 1.0
DEFAULT_POST_GOAL_TRUTH_GRACE_S = 2.5
DEFAULT_ACTIVE_TARGET_LOCK_TOLERANCE_M = 0.50
DEFAULT_TASK_TEXT = (
    "Run the deterministic ball-visit mission through the bounded frozen controls. "
    "Search when the ball is not visible, acquire when visible, plan when locked, track while pursuit is active, "
    "and fail closed with safe_stop if the target cannot be visited."
)
INTENT_OWNERSHIP_GRACE_S = 2.0
SEARCH_INTENT_OWNERSHIP_GRACE_S = 5.0
OWNED_BOUNDED_INTENTS = {"search_for_target", "acquire_target", "plan_to_target", "track_target"}


@dataclass(frozen=True)
class VisitTargetSpec:
    id: str
    label: str
    start_visible: bool
    forward_m: float
    lateral_m: float
    z_m: float = 0.05
    visit_tolerance_m: float = DEFAULT_VISIT_TOLERANCE_M
    min_dwell_s: float = DEFAULT_MIN_TARGET_DWELL_S


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


def _clean_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _clean_number(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def build_visit_targets(scenario_id: str) -> list[VisitTargetSpec]:
    if scenario_id == "visit_single_ball_proof":
        return [
            VisitTargetSpec(
                id="ball_1",
                label="Ball 1",
                start_visible=False,
                forward_m=1.10,
                lateral_m=0.00,
            )
        ]
    if scenario_id == "visit_three_ball_sequence":
        return [
            VisitTargetSpec(
                id="ball_1",
                label="Ball 1",
                start_visible=False,
                forward_m=1.10,
                lateral_m=0.00,
            ),
            VisitTargetSpec(
                id="ball_2",
                label="Ball 2",
                start_visible=True,
                forward_m=1.75,
                lateral_m=0.60,
            ),
            VisitTargetSpec(
                id="ball_3",
                label="Ball 3",
                start_visible=True,
                forward_m=1.75,
                lateral_m=-0.60,
            ),
        ]
    raise ValueError(f"Unsupported visit mission scenario: {scenario_id}")


def mission_truth_distance_m(state: dict[str, Any]) -> float | None:
    belief = state.get("belief", {}) if isinstance(state.get("belief"), dict) else {}
    perception = state.get("perception", {}) if isinstance(state.get("perception"), dict) else {}
    robot_pose = belief.get("latest_robot_pose") if isinstance(belief.get("latest_robot_pose"), dict) else {}
    truth_target = perception.get("latest_truth_target_world") if isinstance(perception.get("latest_truth_target_world"), dict) else {}
    robot_x = _clean_number(robot_pose.get("x"))
    robot_y = _clean_number(robot_pose.get("y"))
    truth_x = _clean_number(truth_target.get("x"))
    truth_y = _clean_number(truth_target.get("y"))
    if robot_x is not None and robot_y is not None and truth_x is not None and truth_y is not None:
        return round(math.hypot(truth_x - robot_x, truth_y - robot_y), 6)
    return None


def mission_belief_distance_m(state: dict[str, Any]) -> float | None:
    belief = state.get("belief", {}) if isinstance(state.get("belief"), dict) else {}
    return _clean_number(belief.get("latest_target_distance_m"))


def mission_vision_truth_delta_m(state: dict[str, Any]) -> float | None:
    perception = state.get("perception", {}) if isinstance(state.get("perception"), dict) else {}
    detection_world = perception.get("latest_detection_world") if isinstance(perception.get("latest_detection_world"), dict) else {}
    truth_target = perception.get("latest_truth_target_world") if isinstance(perception.get("latest_truth_target_world"), dict) else {}
    detection_x = _clean_number(detection_world.get("x"))
    detection_y = _clean_number(detection_world.get("y"))
    truth_x = _clean_number(truth_target.get("x"))
    truth_y = _clean_number(truth_target.get("y"))
    if detection_x is None or detection_y is None or truth_x is None or truth_y is None:
        return None
    return round(math.hypot(truth_x - detection_x, truth_y - detection_y), 6)


def detection_matches_active_truth(
    state: dict[str, Any],
    *,
    tolerance_m: float = DEFAULT_ACTIVE_TARGET_LOCK_TOLERANCE_M,
) -> bool:
    delta_m = mission_vision_truth_delta_m(state)
    if delta_m is None:
        return False
    # Match the observer's alignment contract so a partially-close distractor
    # cannot slip through with a looser mission-only threshold.
    alignment_tolerance_m = max(min(tolerance_m, DEFAULT_ACTIVE_TARGET_LOCK_TOLERANCE_M), 0.05)
    return delta_m <= alignment_tolerance_m


def off_truth_centering_during_search(state: dict[str, Any]) -> bool:
    brain = state.get("brain", {}) if isinstance(state.get("brain"), dict) else {}
    perception = state.get("perception", {}) if isinstance(state.get("perception"), dict) else {}
    if not bool(brain.get("search_active", False)):
        return False
    if not bool(perception.get("target_visible_now", False)):
        return False
    if bool(brain.get("target_locked", False)):
        return False
    return mission_vision_truth_delta_m(state) is not None and not detection_matches_active_truth(state)


def search_bias_release_ready(
    *,
    target_locked_seen: bool,
    search_active: bool,
    search_rotation_accum_rad: float,
    search_rotation_baseline_rad: float,
    hold_until_monotonic: float,
    now_monotonic: float | None = None,
) -> bool:
    now_value = time.monotonic() if now_monotonic is None else float(now_monotonic)
    return bool(
        target_locked_seen
        or search_active
        or (search_rotation_accum_rad - search_rotation_baseline_rad) >= 0.15
        or now_value >= hold_until_monotonic
    )


def feedback_indicates_goal_success(state: dict[str, Any]) -> bool:
    brain = state.get("brain", {}) if isinstance(state.get("brain"), dict) else {}
    feedback_text = _clean_text(brain.get("last_feedback_text") or state.get("last_feedback")).lower()
    return "nav goal reached successfully" in feedback_text


def truth_missing_after_goal_failure(
    state: dict[str, Any],
    *,
    target_locked_seen: bool,
    nav_activity_seen: bool,
    goal_success_seen_monotonic: float | None,
    visit_tolerance_m: float,
    post_goal_truth_grace_s: float,
    now_monotonic: float | None = None,
) -> bool:
    if not target_locked_seen or not nav_activity_seen or goal_success_seen_monotonic is None:
        return False
    now_value = time.monotonic() if now_monotonic is None else float(now_monotonic)
    if (now_value - float(goal_success_seen_monotonic)) < max(post_goal_truth_grace_s, 0.0):
        return False
    if mission_truth_distance_m(state) is not None:
        return False
    distance_m = mission_belief_distance_m(state)
    if distance_m is None:
        return False
    return distance_m <= max(visit_tolerance_m, 0.05)


def visit_success(
    state: dict[str, Any],
    *,
    target_locked_seen: bool,
    nav_activity_seen: bool,
    visit_tolerance_m: float,
    elapsed_since_spawn_s: float,
    min_dwell_s: float,
) -> bool:
    if not target_locked_seen or not nav_activity_seen:
        return False
    if elapsed_since_spawn_s < max(min_dwell_s, 0.0):
        return False
    distance_m = mission_truth_distance_m(state)
    if distance_m is None:
        return False
    return distance_m <= max(visit_tolerance_m, 0.05)


def deterministic_visit_decision(state: dict[str, Any], task_text: str, contract: dict[str, Any]) -> dict[str, Any]:
    policy = build_policy_snapshot(state, sim_gate_ready=bool(state.get("sim_gate_ready", False)))
    preferred_intent = _clean_text(policy.get("preferred_intent"))
    active_truth_delta_m = mission_vision_truth_delta_m(state)
    if preferred_intent == "acquire_target" and active_truth_delta_m is not None and not detection_matches_active_truth(state):
        preferred_intent = "search_for_target"
        policy = {
            **policy,
            "preferred_intent": preferred_intent,
            "reason": f"Visible detection diverges from active truth by {active_truth_delta_m:.2f}m, so search remains preferred.",
        }
    if not preferred_intent:
        return blocked_decision(
            task_text,
            _clean_text(policy.get("reason"), "The deterministic visit mission is waiting for an actionable state."),
            missing_prerequisites=list(policy.get("common_missing_keys", [])),
            expected_observations=[],
            confidence=0.0,
        )
    decision = {
        "status": "recommendation",
        "task_text": task_text,
        "intent": preferred_intent,
        "args": dict(CANONICAL_ARGS_BY_INTENT.get(preferred_intent, {})),
        "rationale_short": _clean_text(policy.get("reason")),
        "missing_prerequisites": [],
        "expected_observations": [],
        "confidence": 1.0,
    }
    decision = validate_decision_against_contract(decision, contract)
    return validate_decision_against_canonical_space(decision)


class VisitMissionRunner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.dashboard_url = args.dashboard_url.rstrip("/")
        self.contract = load_contract(Path(args.contract).resolve())
        self.targets = build_visit_targets(str(args.scenario_id))
        self.docker = choose_docker_cli()
        self.last_state_hash = ""
        self.last_decision_signature = ""
        self.last_dispatch_monotonic = 0.0
        self._mission_anchor_pose: dict[str, float] | None = None
        self.runtime_state: dict[str, Any] = {
            "running": False,
            "scenario_id": str(args.scenario_id),
            "session_id": "",
            "proof_state": "waiting",
            "mission_phase": "setup",
            "mission_status": "waiting",
            "search_bias_active": False,
            "current_target_id": "",
            "visit_index": 0,
            "visited_targets": [],
            "remaining_targets": [item.id for item in self.targets],
            "last_visit_result": {},
            "mission_verdict": {},
            "latest_operator_event": "",
            "recent_operator_events": [],
            "latest_decision": {},
            "latest_feedback": "",
            "artifact_dir": "",
            "updated_utc": utc_now(),
        }
        self._event_keys: set[str] = set()

    def _persist_runtime_state(self) -> None:
        write_json(MISSION_RUNTIME_STATE_PATH, self.runtime_state)

    def _update_runtime_state(self, **updates: Any) -> None:
        self.runtime_state.update(updates)
        self.runtime_state["updated_utc"] = utc_now()
        self._persist_runtime_state()

    def _append_runtime_event(self, message: str, *, category: str = "mission", key: str = "") -> None:
        event_key = key or message
        if event_key in self._event_keys:
            return
        self._event_keys.add(event_key)
        event = {
            "timestamp_utc": utc_now(),
            "message": str(message),
            "category": str(category),
            "source": "visit_mission",
        }
        events = list(self.runtime_state.get("recent_operator_events", []))
        events.append(event)
        self.runtime_state["recent_operator_events"] = events[-30:]
        self.runtime_state["latest_operator_event"] = event["message"]
        self.runtime_state["updated_utc"] = event["timestamp_utc"]
        self._persist_runtime_state()

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

    def _wait_for_hidden_start_settle(self, timeout_s: float) -> dict[str, Any]:
        deadline = time.monotonic() + max(timeout_s, 0.1)
        last_state: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last_state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
            perception = last_state.get("perception", {}) if isinstance(last_state.get("perception"), dict) else {}
            brain = last_state.get("brain", {}) if isinstance(last_state.get("brain"), dict) else {}
            if not bool(perception.get("target_visible_now", False)) or bool(brain.get("search_active", False)) or bool(brain.get("target_locked", False)):
                return last_state
            time.sleep(0.25)
        return last_state

    def _stop_environment(self) -> None:
        self._request("POST", "/api/env/stop", timeout_s=10.0)
        self._wait_for_state(
            lambda current: current.get("environment_state") == "stopped",
            timeout_s=240.0,
            error_text="Environment did not stop cleanly.",
        )

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
                "cat >/tmp/chasecar_visit_mission.sh && chmod +x /tmp/chasecar_visit_mission.sh && /tmp/chasecar_visit_mission.sh",
            ],
            cwd=str(REPO_ROOT),
            input=script.encode("utf-8"),
            capture_output=True,
            check=False,
        )
        output = (proc.stdout or b"").decode("utf-8", errors="replace")
        output += ("\n" + (proc.stderr or b"").decode("utf-8", errors="replace")) if proc.stderr else ""
        return proc.returncode, output.strip()

    def _target_model_name(self, target: VisitTargetSpec) -> str:
        safe_id = "".join(ch if ch.isalnum() else "_" for ch in target.id.lower())
        return f"{self.args.target_model_name}_{safe_id}"

    def _remove_target_model(
        self,
        *,
        compose_project: str,
        world_name: str,
        model_name: str,
        mission_root: Path,
        log_stem: str,
    ) -> dict[str, Any]:
        sim_gate_container = self._container_id(compose_project, "sim-gate")
        log_path = mission_root / f"{log_stem}_remove.log"
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
        rc, output = self._docker_exec(sim_gate_container, script)
        log_path.write_text(output + "\n", encoding="utf-8")
        payload = {
            "generated_utc": utc_now(),
            "compose_project": compose_project,
            "sim_gate_container": sim_gate_container,
            "world_name": world_name,
            "model_name": model_name,
            "remove_rc": rc,
            "log_path": str(log_path),
            "output": output,
            "pass": True,
        }
        write_json(mission_root / f"{log_stem}_remove.json", payload)
        return payload

    def _clear_mission_targets(self, state: dict[str, Any], mission_root: Path, *, keep: set[str] | None = None) -> None:
        compose_project = _clean_text(state.get("compose_project"))
        if not compose_project:
            return
        world_name = _clean_text(state.get("world_name"), DEFAULT_WORLD_NAME)
        keep_names = set(keep or set())
        for target in self.targets:
            model_name = self._target_model_name(target)
            if model_name in keep_names:
                continue
            self._remove_target_model(
                compose_project=compose_project,
                world_name=world_name,
                model_name=model_name,
                mission_root=mission_root,
                log_stem=f"{target.id}_cleanup",
            )

    def _robot_pose_components(self, state: dict[str, Any]) -> tuple[float, float, float]:
        belief = state.get("belief", {}) if isinstance(state.get("belief"), dict) else {}
        robot_pose = belief.get("latest_robot_pose", {}) if isinstance(belief.get("latest_robot_pose"), dict) else {}
        robot_x = _clean_number(robot_pose.get("x"))
        robot_y = _clean_number(robot_pose.get("y"))
        robot_yaw = _clean_number(robot_pose.get("yaw"))
        if robot_x is None or robot_y is None or robot_yaw is None:
            raise RuntimeError("Robot pose unavailable for mission target spawn.")
        return robot_x, robot_y, robot_yaw

    def _capture_mission_anchor_pose(self, state: dict[str, Any]) -> None:
        if self._mission_anchor_pose is not None:
            return
        robot_x, robot_y, robot_yaw = self._robot_pose_components(state)
        self._mission_anchor_pose = {
            "x": robot_x,
            "y": robot_y,
            "yaw": robot_yaw,
        }

    def _spawn_target_from_mission_anchor(self, state: dict[str, Any], target: VisitTargetSpec, mission_root: Path) -> dict[str, Any]:
        robot_x, robot_y, robot_yaw = self._robot_pose_components(state)
        self._capture_mission_anchor_pose(state)
        anchor_pose = dict(self._mission_anchor_pose or {})
        anchor_x = float(anchor_pose.get("x", robot_x))
        anchor_y = float(anchor_pose.get("y", robot_y))
        anchor_yaw = float(anchor_pose.get("yaw", robot_yaw))

        target_x = anchor_x + (math.cos(anchor_yaw) * target.forward_m) - (math.sin(anchor_yaw) * target.lateral_m)
        target_y = anchor_y + (math.sin(anchor_yaw) * target.forward_m) + (math.cos(anchor_yaw) * target.lateral_m)
        target_bearing = math.atan2(target_y - robot_y, target_x - robot_x)
        turned_robot_yaw = target_bearing if target.start_visible else normalize_angle(target_bearing + math.pi)
        half_yaw = 0.5 * turned_robot_yaw
        robot_qz = math.sin(half_yaw)
        robot_qw = math.cos(half_yaw)

        compose_project = _clean_text(state.get("compose_project"))
        if not compose_project:
            raise RuntimeError("Active compose project missing from dashboard state.")
        sim_gate_container = self._container_id(compose_project, "sim-gate")
        world_name = _clean_text(state.get("world_name"), DEFAULT_WORLD_NAME)
        model_sdf_host = Path(self.args.target_model_sdf).resolve()
        model_sdf = to_container_repo_path(model_sdf_host)
        model_name = self._target_model_name(target)
        log_path = mission_root / f"{target.id}_spawn.log"
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
TARGET_Z={json.dumps(f"{target.z_m:.6f}")}
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
spawn_create true > /tmp/chasecar_visit_mission_spawn.log 2>&1
rc=$?
if [[ "$rc" -ne 0 ]] && grep -Eq 'Waiting for service \\[/world/.*/create\\] to become available' /tmp/chasecar_visit_mission_spawn.log 2>/dev/null; then
  spawn_create false >> /tmp/chasecar_visit_mission_spawn.log 2>&1
  rc=$?
fi
if [[ "$rc" -eq 0 ]] && command -v gz >/dev/null 2>&1; then
  gz service -s "/world/$WORLD_NAME/set_pose/blocking" --reqtype gz.msgs.Pose --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"$MODEL_NAME\\" position {{ x: $TARGET_X y: $TARGET_Y z: $TARGET_Z }} orientation {{ x: 0 y: 0 z: 0 w: 1 }}" >> /tmp/chasecar_visit_mission_spawn.log 2>&1
  target_setpose_rc=$?
  if [[ "$target_setpose_rc" -ne 0 ]]; then
    rc="$target_setpose_rc"
  fi
fi
if [[ "$rc" -eq 0 ]] && command -v gz >/dev/null 2>&1; then
  gz service -s "/world/$WORLD_NAME/set_pose/blocking" --reqtype gz.msgs.Pose --reptype gz.msgs.Boolean --timeout 2000 --req "name: \\"jetbot\\" position {{ x: $ROBOT_X y: $ROBOT_Y z: $ROBOT_Z }} orientation {{ x: 0 y: 0 z: $ROBOT_QZ w: $ROBOT_QW }}" >> /tmp/chasecar_visit_mission_spawn.log 2>&1
  setpose_rc=$?
  if [[ "$setpose_rc" -ne 0 ]]; then
    rc="$setpose_rc"
  fi
fi
cat /tmp/chasecar_visit_mission_spawn.log
exit "$rc"
"""
        rc, output = self._docker_exec(sim_gate_container, script)
        log_path.write_text(output + "\n", encoding="utf-8")
        payload = {
            "generated_utc": utc_now(),
            "target": asdict(target),
            "compose_project": compose_project,
            "sim_gate_container": sim_gate_container,
            "world_name": world_name,
            "model_name": model_name,
            "model_sdf": str(model_sdf_host),
            "target_world": {"x": target_x, "y": target_y, "z": target.z_m},
            "anchor_pose": {"x": anchor_x, "y": anchor_y, "yaw": anchor_yaw},
            "robot_pose_after_spawn": {"x": robot_x, "y": robot_y, "yaw": turned_robot_yaw},
            "spawn_rc": rc,
            "log_path": str(log_path),
            "output": output,
            "pass": rc == 0,
        }
        write_json(mission_root / f"{target.id}_spawn.json", payload)
        if rc != 0:
            raise RuntimeError(f"Failed to spawn visit target {target.id}: {output}")
        return payload

    def _issue_safe_stop(self) -> None:
        try:
            self._request("POST", "/api/intents/dispatch", {"intent": "safe_stop", "args": {}}, timeout_s=10.0)
        except Exception:
            pass

    def _owned_intent_name(self, decision: dict[str, Any]) -> str:
        intent = _clean_text(decision.get("intent"))
        return intent if intent in OWNED_BOUNDED_INTENTS else ""

    def _intent_feedback_text(self, state: dict[str, Any]) -> str:
        brain = state.get("brain", {}) if isinstance(state.get("brain"), dict) else {}
        return _clean_text(brain.get("last_feedback_text") or state.get("last_feedback")).lower()

    def _intent_terminal_feedback_reason(self, state: dict[str, Any], intent_name: str) -> str:
        feedback = self._intent_feedback_text(state)
        if not feedback.startswith(f"{intent_name}:"):
            return ""
        if "blocked because" in feedback:
            return "blocked"
        if intent_name == "search_for_target" and "full scan completed without lock" in feedback:
            return "search_exhausted"
        if intent_name == "plan_to_target" and "already within approach distance" in feedback:
            return "noop"
        return ""

    def _owned_intent_status(
        self,
        *,
        state: dict[str, Any],
        intent_name: str,
        owned_since_monotonic: float,
    ) -> tuple[bool, bool, str]:
        if not intent_name:
            return False, False, ""
        brain = state.get("brain", {}) if isinstance(state.get("brain"), dict) else {}
        outcome = state.get("outcome", {}) if isinstance(state.get("outcome"), dict) else {}
        perception = state.get("perception", {}) if isinstance(state.get("perception"), dict) else {}
        elapsed_s = max(time.monotonic() - owned_since_monotonic, 0.0)
        target_visible_recent = bool(brain.get("target_visible_recent", False)) or bool(perception.get("target_visible_now", False))
        last_intent = _clean_text(brain.get("last_intent"))
        terminal_reason = self._intent_terminal_feedback_reason(state, intent_name)

        if intent_name == "search_for_target":
            if bool(brain.get("target_locked", False)):
                return False, True, ""
            if bool(brain.get("search_active", False)):
                return True, False, ""
            if last_intent == intent_name and not terminal_reason:
                return True, False, ""
            search_grace_s = max(
                float(getattr(self.args, "search_timeout_s", SEARCH_INTENT_OWNERSHIP_GRACE_S)),
                SEARCH_INTENT_OWNERSHIP_GRACE_S,
            )
            if elapsed_s <= search_grace_s:
                return True, False, ""
            return False, False, terminal_reason

        if intent_name == "acquire_target":
            if bool(brain.get("target_locked", False)):
                return False, True, ""
            if last_intent == intent_name and target_visible_recent and not terminal_reason:
                return True, False, ""
            if elapsed_s <= INTENT_OWNERSHIP_GRACE_S and target_visible_recent:
                return True, False, ""
            return False, False, terminal_reason

        if intent_name == "plan_to_target":
            if bool(brain.get("goal_in_progress", False)) or bool(outcome.get("nav_goal_recent", False)):
                return False, True, ""
            if last_intent == intent_name and not terminal_reason:
                return True, False, ""
            if elapsed_s <= INTENT_OWNERSHIP_GRACE_S:
                return True, False, ""
            return False, False, terminal_reason

        if intent_name == "track_target":
            if bool(brain.get("track_active", False)):
                return True, False, ""
            if last_intent == intent_name and not terminal_reason:
                return True, False, ""
            if elapsed_s <= INTENT_OWNERSHIP_GRACE_S:
                return True, False, ""
            return False, False, terminal_reason

        return False, False, terminal_reason

    def _search_dispatch_in_flight(self, state: dict[str, Any], decision: dict[str, Any]) -> bool:
        if _clean_text(decision.get("intent")) != "search_for_target":
            return False
        brain = state.get("brain", {}) if isinstance(state.get("brain"), dict) else {}
        return bool(brain.get("search_active", False))

    def _should_dispatch_decision(self, *, decision: dict[str, Any], state_hash: str, state: dict[str, Any]) -> bool:
        signature = decision_signature(decision)
        if self._search_dispatch_in_flight(state, decision) and signature == self.last_decision_signature:
            return False
        return (
            signature != self.last_decision_signature
            or state_hash != self.last_state_hash
            or (time.monotonic() - self.last_dispatch_monotonic) >= self.args.dispatch_cooldown_s
        )

    def _owned_in_flight_decision(self, intent_name: str, args_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "owned_in_flight",
            "intent": intent_name,
            "args": dict(args_payload),
            "task_text": self.args.task,
            "rationale_short": f"{intent_name} is still in flight; waiting for executor progress before choosing the next step.",
            "missing_prerequisites": [],
            "expected_observations": [],
            "confidence": 1.0,
        }

    def _own_intent(
        self,
        *,
        target: VisitTargetSpec,
        attempt: int,
        decision: dict[str, Any],
        state_hash: str,
        first_dispatched_intent: str,
        announce: bool,
    ) -> tuple[str, str, dict[str, Any], float]:
        signature = decision_signature(decision)
        intent_name = self._owned_intent_name(decision)
        if not first_dispatched_intent and intent_name:
            first_dispatched_intent = intent_name
        self.last_decision_signature = signature
        self.last_state_hash = state_hash
        owned_since_monotonic = time.monotonic()
        self.last_dispatch_monotonic = owned_since_monotonic
        if announce and intent_name:
            message = {
                "search_for_target": "Search already in progress; waiting for executor progress.",
                "acquire_target": "Acquire already in progress; waiting for lock confirmation.",
                "plan_to_target": "Plan already in progress; waiting for goal activity.",
                "track_target": "Track already in progress; waiting for pursuit progress.",
            }.get(intent_name, f"{intent_name} already in progress; waiting for executor progress.")
            self._append_runtime_event(
                message,
                key=f"{intent_name}_inflight:{target.id}:{attempt}:{signature}",
            )
        return first_dispatched_intent, intent_name, dict(decision.get("args", {})), owned_since_monotonic

    def _format_decision_label(self, decision: dict[str, Any]) -> str:
        intent = _clean_text(decision.get("intent"))
        args = decision.get("args", {}) if isinstance(decision.get("args"), dict) else {}
        if intent == "search_for_target":
            return f"{intent}({args.get('target_class', 'ball')})"
        if intent == "acquire_target":
            return f"{intent}({args.get('target_class', 'ball')})"
        if intent == "plan_to_target":
            return f"{intent}({args.get('approach_distance_m', 0.25)})"
        if intent:
            return f"{intent}()"
        return "blocked"

    def _proof_state_for_state(self, state: dict[str, Any]) -> str:
        brain = state.get("brain", {}) if isinstance(state.get("brain"), dict) else {}
        outcome = state.get("outcome", {}) if isinstance(state.get("outcome"), dict) else {}
        perception = state.get("perception", {}) if isinstance(state.get("perception"), dict) else {}
        if self.runtime_state.get("mission_status") == "completed":
            return "completed"
        if self.runtime_state.get("mission_status") == "failed":
            return "failed"
        if bool(brain.get("goal_in_progress", False)) or bool(outcome.get("nav_goal_recent", False)) or bool(outcome.get("cmd_vel_recent", False)):
            return "moving"
        if bool(brain.get("target_locked", False)) or bool(perception.get("target_visible_now", False)):
            return "target_locked"
        if bool(brain.get("search_active", False)):
            return "searching"
        return "waiting"

    def _mission_phase_for_decision(self, decision: dict[str, Any], state: dict[str, Any]) -> str:
        if self.runtime_state.get("mission_status") in {"completed", "failed"}:
            return str(self.runtime_state.get("mission_status"))
        intent = _clean_text(decision.get("intent"))
        if intent == "search_for_target":
            return "search"
        if intent == "acquire_target":
            return "acquire"
        if intent == "plan_to_target":
            return "plan"
        if intent == "track_target":
            return "track"
        if intent in {"abort", "safe_stop"}:
            return "safe_stop"
        return _clean_text(build_policy_snapshot(state, sim_gate_ready=bool(state.get("sim_gate_ready", False))).get("stage"), "setup")

    def run(self) -> dict[str, Any]:
        ready_state, started_here = self._ensure_environment_ready()
        ready_state = self._wait_for_robot_pose(timeout_s=self.args.environment_timeout_s)
        session_id = _clean_text(ready_state.get("session_id"))
        if not session_id:
            raise RuntimeError("Dashboard did not provide a session id.")

        mission_root = ensure_dir(REPO_ROOT / "artifacts" / "session" / session_id / self.args.artifact_kind / current_utc_stamp())
        visit_sequence_path = mission_root / "visit_sequence.jsonl"
        state_history_path = mission_root / "state_history.jsonl"
        target_results_path = mission_root / "target_results.json"

        self.runtime_state = {
            "running": True,
            "scenario_id": str(self.args.scenario_id),
            "session_id": session_id,
            "proof_state": "waiting",
            "mission_phase": "setup",
            "mission_status": "running",
            "search_bias_active": False,
            "current_target_id": "",
            "visit_index": 0,
            "visited_targets": [],
            "remaining_targets": [item.id for item in self.targets],
            "last_visit_result": {},
            "mission_verdict": {},
            "latest_operator_event": "",
            "recent_operator_events": [],
            "latest_decision": {},
            "latest_feedback": "",
            "artifact_dir": str(mission_root),
            "updated_utc": utc_now(),
        }
        self._event_keys = set()
        self._persist_runtime_state()
        self._append_runtime_event(f"{self.args.scenario_label} mission started.", category="scenario", key="mission_started")

        target_results: list[dict[str, Any]] = []
        mission_pass = True
        mission_error = ""

        try:
            self._issue_safe_stop()
            ready_state = self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
            self._clear_mission_targets(ready_state, mission_root)
            self._capture_mission_anchor_pose(ready_state)
            for index, target in enumerate(self.targets, start=1):
                attempt = 0
                target_pass = False
                while attempt <= self.args.max_retries_per_target and not target_pass:
                    target_locked_seen = False
                    nav_activity_seen = False
                    move_started = False
                    first_dispatched_intent = ""
                    owned_intent = ""
                    owned_intent_args: dict[str, Any] = {}
                    owned_intent_started_monotonic = 0.0
                    search_rotation_bias_baseline = 0.0
                    target_visit_started_monotonic = time.monotonic()
                    search_bias_hold_until_monotonic = target_visit_started_monotonic
                    lock_seen_monotonic: float | None = None
                    goal_success_seen_monotonic: float | None = None
                    self.last_state_hash = ""
                    self.last_decision_signature = ""
                    self.last_dispatch_monotonic = 0.0

                    current_state = self._wait_for_robot_pose(timeout_s=self.args.environment_timeout_s)
                    spawn_info = self._spawn_target_from_mission_anchor(current_state, target, mission_root)
                    target_spawned_monotonic = time.monotonic()
                    remaining_targets = [item.id for item in self.targets[index:]]
                    self._update_runtime_state(
                        current_target_id=target.id,
                        visit_index=index,
                        mission_phase="setup",
                        mission_status="running",
                        search_bias_active=not target.start_visible,
                        visited_targets=[item["target_id"] for item in target_results if item.get("pass")],
                        remaining_targets=[target.id] + remaining_targets,
                        last_visit_result={},
                    )
                    self._append_runtime_event(f"{target.label} selected.", key=f"target_selected:{target.id}:{attempt}")
                    self._append_runtime_event(
                        f"{target.label} spawned {'in view' if target.start_visible else 'out of view'}.",
                        key=f"target_spawned:{target.id}:{attempt}",
                    )
                    append_jsonl(
                        visit_sequence_path,
                        {
                            "generated_utc": utc_now(),
                            "event_type": "target_spawned",
                            "target_id": target.id,
                            "attempt": attempt,
                            "spawn_info": spawn_info,
                        },
                    )
                    if not target.start_visible:
                        self._append_runtime_event("Waiting for hidden-start view to settle.", key=f"hidden_settle:{target.id}:{attempt}")
                        settled_state = self._wait_for_hidden_start_settle(self.args.hidden_start_settle_s)
                        settled_brain = settled_state.get("brain", {}) if isinstance(settled_state.get("brain"), dict) else {}
                        search_rotation_bias_baseline = _clean_number(settled_brain.get("search_rotation_accum_rad")) or 0.0
                        target_visit_started_monotonic = time.monotonic()
                        search_bias_hold_until_monotonic = target_visit_started_monotonic + self.args.hidden_start_settle_s

                    failure_reason = ""
                    while time.monotonic() < (target_visit_started_monotonic + self.args.max_target_runtime_s):
                        state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
                        brain = state.get("brain", {}) if isinstance(state.get("brain"), dict) else {}
                        outcome = state.get("outcome", {}) if isinstance(state.get("outcome"), dict) else {}
                        perception = state.get("perception", {}) if isinstance(state.get("perception"), dict) else {}
                        attempt_phase = "approach_phase" if target_locked_seen else "search_phase"
                        target_lock_active = bool(brain.get("target_locked", False))
                        active_truth_delta_m = mission_vision_truth_delta_m(state)
                        aligned_target_lock = target_lock_active and detection_matches_active_truth(state)

                        if off_truth_centering_during_search(state):
                            self._append_runtime_event(
                                f"Ignoring visible off-target blob ({active_truth_delta_m:.2f}m from active truth); resuming search.",
                                category="mission",
                                key=f"off_truth_visible:{target.id}:{attempt}:{round(active_truth_delta_m or 0.0, 2)}",
                            )
                            append_jsonl(
                                visit_sequence_path,
                                {
                                    "generated_utc": utc_now(),
                                    "event_type": "off_truth_visible_rejected",
                                    "target_id": target.id,
                                    "attempt": attempt,
                                    "vision_truth_delta_m": active_truth_delta_m,
                                    "attempt_phase": attempt_phase,
                                },
                            )
                            self._issue_safe_stop()
                            self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
                            owned_intent = ""
                            owned_intent_args = {}
                            owned_intent_started_monotonic = 0.0
                            search_rotation_bias_baseline = _clean_number(brain.get("search_rotation_accum_rad")) or search_rotation_bias_baseline
                            search_bias_hold_until_monotonic = time.monotonic() + self.args.hidden_start_settle_s
                            nav_activity_seen = False
                            move_started = False
                            goal_success_seen_monotonic = None
                            lock_seen_monotonic = None
                            self._update_runtime_state(
                                search_bias_active=True,
                                mission_phase="search",
                                proof_state=self._proof_state_for_state(state),
                                latest_feedback=_clean_text(brain.get("last_feedback_text") or state.get("last_feedback")),
                                current_target_id=target.id,
                            )
                            time.sleep(self.args.poll_s)
                            continue

                        if target_lock_active and active_truth_delta_m is not None and not aligned_target_lock:
                            self._append_runtime_event(
                                f"Rejected off-target lock ({active_truth_delta_m:.2f}m from active truth); resuming search.",
                                category="mission",
                                key=f"off_target_lock:{target.id}:{attempt}:{round(active_truth_delta_m, 2)}",
                            )
                            append_jsonl(
                                visit_sequence_path,
                                {
                                    "generated_utc": utc_now(),
                                    "event_type": "off_target_lock_rejected",
                                    "target_id": target.id,
                                    "attempt": attempt,
                                    "vision_truth_delta_m": active_truth_delta_m,
                                    "attempt_phase": attempt_phase,
                                },
                            )
                            self._issue_safe_stop()
                            self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
                            owned_intent = ""
                            owned_intent_args = {}
                            owned_intent_started_monotonic = 0.0
                            search_rotation_bias_baseline = search_rotation
                            search_bias_hold_until_monotonic = time.monotonic() + self.args.hidden_start_settle_s
                            nav_activity_seen = False
                            move_started = False
                            goal_success_seen_monotonic = None
                            lock_seen_monotonic = None
                            self._update_runtime_state(
                                search_bias_active=True,
                                mission_phase="search",
                                proof_state=self._proof_state_for_state(state),
                                latest_feedback=_clean_text(brain.get("last_feedback_text") or state.get("last_feedback")),
                                current_target_id=target.id,
                            )
                            time.sleep(self.args.poll_s)
                            continue

                        if aligned_target_lock:
                            target_locked_seen = True
                            lock_seen_monotonic = lock_seen_monotonic or time.monotonic()
                            attempt_phase = "approach_phase"
                            self._append_runtime_event("Target visible and locked.", key=f"target_locked:{target.id}:{attempt}")
                        search_rotation = _clean_number(brain.get("search_rotation_accum_rad")) or 0.0
                        if bool(self.runtime_state.get("search_bias_active", False)) and search_bias_release_ready(
                            target_locked_seen=target_locked_seen,
                            search_active=bool(brain.get("search_active", False)),
                            search_rotation_accum_rad=search_rotation,
                            search_rotation_baseline_rad=search_rotation_bias_baseline,
                            hold_until_monotonic=search_bias_hold_until_monotonic,
                        ):
                            self._update_runtime_state(search_bias_active=False)
                        if bool(brain.get("goal_in_progress", False)) or bool(outcome.get("nav_goal_recent", False)):
                            nav_activity_seen = True
                        if nav_activity_seen and not move_started and (
                            bool(outcome.get("cmd_vel_recent", False))
                            or bool(brain.get("goal_in_progress", False))
                            or bool(outcome.get("nav_goal_recent", False))
                        ):
                            move_started = True
                            self._append_runtime_event("Robot began move-to-target.", key=f"move_started:{target.id}:{attempt}")
                        if feedback_indicates_goal_success(state) and goal_success_seen_monotonic is None:
                            goal_success_seen_monotonic = time.monotonic()
                            self._append_runtime_event(
                                "Nav goal succeeded; waiting briefly for active-target truth confirmation.",
                                key=f"goal_success:{target.id}:{attempt}",
                            )

                        self._update_runtime_state(
                            mission_phase=self._mission_phase_for_decision(self.runtime_state.get("latest_decision", {}), state),
                            proof_state=self._proof_state_for_state(state),
                            latest_feedback=_clean_text(brain.get("last_feedback_text") or state.get("last_feedback")),
                            current_target_id=target.id,
                        )
                        append_jsonl(
                            state_history_path,
                            {
                                "generated_utc": utc_now(),
                                "target_id": target.id,
                                "attempt": attempt,
                                "attempt_phase": attempt_phase,
                                "owned_intent": owned_intent,
                                "mission_phase": self.runtime_state.get("mission_phase"),
                                "proof_state": self.runtime_state.get("proof_state"),
                                "perception": state.get("perception", {}),
                                "belief": state.get("belief", {}),
                                "brain": brain,
                                "outcome": outcome,
                            },
                        )

                        if visit_success(
                            state,
                            target_locked_seen=target_locked_seen,
                            nav_activity_seen=nav_activity_seen,
                            visit_tolerance_m=target.visit_tolerance_m,
                            elapsed_since_spawn_s=(time.monotonic() - target_spawned_monotonic),
                            min_dwell_s=target.min_dwell_s,
                        ):
                            target_pass = True
                            distance_m = mission_truth_distance_m(state)
                            result = {
                                "target_id": target.id,
                                "label": target.label,
                                "attempt": attempt,
                                "pass": True,
                                "model_name": self._target_model_name(target),
                                "first_dispatched_intent": first_dispatched_intent,
                                "visit_distance_m": distance_m,
                                "target_locked_seen": target_locked_seen,
                                "nav_activity_seen": nav_activity_seen,
                                "started_visible": target.start_visible,
                            }
                            target_results.append(result)
                            write_json(target_results_path, {"targets": target_results})
                            self._update_runtime_state(
                                mission_phase="advance",
                                visited_targets=[item["target_id"] for item in target_results if item.get("pass")],
                                remaining_targets=[item.id for item in self.targets[index:]],
                                last_visit_result=result,
                            )
                            self._append_runtime_event(f"{target.label} visited.", key=f"visited:{target.id}")
                            append_jsonl(
                                visit_sequence_path,
                                {
                                    "generated_utc": utc_now(),
                                    "event_type": "target_visited",
                                    "target_id": target.id,
                                    "attempt": attempt,
                                    "result": result,
                                },
                            )
                            if self.args.remove_visited_targets:
                                self._remove_target_model(
                                    compose_project=_clean_text(state.get("compose_project")),
                                    world_name=_clean_text(state.get("world_name"), DEFAULT_WORLD_NAME),
                                    model_name=self._target_model_name(target),
                                    mission_root=mission_root,
                                    log_stem=f"{target.id}_visited",
                                )
                            break

                        search_elapsed = time.monotonic() - target_visit_started_monotonic
                        if not target_locked_seen and search_elapsed >= self.args.search_timeout_s:
                            failure_reason = "search_timeout"
                            break
                        if truth_missing_after_goal_failure(
                            state,
                            target_locked_seen=target_locked_seen,
                            nav_activity_seen=nav_activity_seen,
                            goal_success_seen_monotonic=goal_success_seen_monotonic,
                            visit_tolerance_m=target.visit_tolerance_m,
                            post_goal_truth_grace_s=self.args.post_goal_truth_grace_s,
                        ):
                            failure_reason = "truth_missing_for_active_target"
                            break
                        if lock_seen_monotonic is not None and (time.monotonic() - lock_seen_monotonic) >= self.args.approach_timeout_s:
                            failure_reason = "approach_timeout"
                            break

                        if owned_intent:
                            owned_in_flight, owned_transitioned, terminal_reason = self._owned_intent_status(
                                state=state,
                                intent_name=owned_intent,
                                owned_since_monotonic=owned_intent_started_monotonic,
                            )
                            if owned_in_flight:
                                decision = self._owned_in_flight_decision(owned_intent, owned_intent_args)
                                self._update_runtime_state(
                                    latest_decision=decision,
                                    mission_phase=self._mission_phase_for_decision(decision, state),
                                    proof_state=self._proof_state_for_state(state),
                                )
                                append_jsonl(
                                    visit_sequence_path,
                                    {
                                        "generated_utc": utc_now(),
                                        "event_type": "decision_tick",
                                        "target_id": target.id,
                                        "attempt": attempt,
                                        "attempt_phase": attempt_phase,
                                        "decision": decision,
                                        "owned_intent": owned_intent,
                                        "preview": preview_summary(0, {}),
                                        "dispatch_status": 0,
                                        "dispatch_payload": {},
                                    },
                                )
                                time.sleep(self.args.poll_s)
                                continue
                            if terminal_reason == "blocked" and owned_intent == "plan_to_target" and target_locked_seen and not nav_activity_seen:
                                failure_reason = "plan_blocked"
                                break
                            owned_intent = ""
                            owned_intent_args = {}
                            owned_intent_started_monotonic = 0.0

                        policy = build_policy_snapshot(state, sim_gate_ready=bool(state.get("sim_gate_ready", False)))
                        decision = deterministic_visit_decision(state, self.args.task, self.contract)
                        preview_status = 0
                        preview_payload: dict[str, Any] = {}
                        dispatch_status = 0
                        dispatch_payload: dict[str, Any] = {}

                        if decision.get("status") == "recommendation":
                            state_hash = json.dumps(
                                {
                                    "policy_stage": policy.get("stage"),
                                    "preferred_intent": policy.get("preferred_intent"),
                                    "search_bias_active": self.runtime_state.get("search_bias_active", False),
                                    "target_visible_now": perception.get("target_visible_now"),
                                    "target_locked": brain.get("target_locked"),
                                    "goal_in_progress": brain.get("goal_in_progress"),
                                    "track_active": brain.get("track_active"),
                                },
                                sort_keys=True,
                            )
                            preview_status, preview_payload = preview_intent(
                                self.dashboard_url,
                                _clean_text(decision.get("intent")),
                                dict(decision.get("args", {})),
                                timeout_s=self.args.timeout_s,
                            )
                            preview = preview_summary(preview_status, preview_payload)
                            if preview_status == 200 and preview["contract_valid"] and preview["ready_to_dispatch"]:
                                signature = decision_signature(decision)
                                if self._should_dispatch_decision(decision=decision, state_hash=state_hash, state=state):
                                    dispatch_status, dispatch_payload = dispatch_intent(
                                        self.dashboard_url,
                                        _clean_text(decision.get("intent")),
                                        dict(decision.get("args", {})),
                                        timeout_s=self.args.timeout_s,
                                    )
                                    if dispatch_status == 202 and bool(dispatch_payload.get("accepted", False)):
                                        (
                                            first_dispatched_intent,
                                            owned_intent,
                                            owned_intent_args,
                                            owned_intent_started_monotonic,
                                        ) = self._own_intent(
                                            target=target,
                                            attempt=attempt,
                                            decision=decision,
                                            state_hash=state_hash,
                                            first_dispatched_intent=first_dispatched_intent,
                                            announce=False,
                                        )
                                        self._update_runtime_state(
                                            latest_decision=decision,
                                            mission_phase=self._mission_phase_for_decision(decision, state),
                                            proof_state=self._proof_state_for_state(state),
                                        )
                                        append_jsonl(
                                            visit_sequence_path,
                                            {
                                                "generated_utc": utc_now(),
                                                "event_type": "decision_dispatched",
                                                "target_id": target.id,
                                                "attempt": attempt,
                                                "decision": decision,
                                            },
                                        )
                                        self._append_runtime_event(
                                            f"Mission issued {self._format_decision_label(decision)}.",
                                            category="decision",
                                            key=f"decision:{target.id}:{signature}",
                                        )
                                    elif (
                                        dispatch_status == 409
                                        and self._owned_intent_name(decision)
                                        and "intent already in progress" in _clean_text(dispatch_payload.get("error")).lower()
                                    ):
                                        (
                                            first_dispatched_intent,
                                            owned_intent,
                                            owned_intent_args,
                                            owned_intent_started_monotonic,
                                        ) = self._own_intent(
                                            target=target,
                                            attempt=attempt,
                                            decision=decision,
                                            state_hash=state_hash,
                                            first_dispatched_intent=first_dispatched_intent,
                                            announce=True,
                                        )
                            else:
                                decision = blocked_decision(
                                    self.args.task,
                                    _clean_text(preview.get("status_text"), "Preview rejected the deterministic decision."),
                                    missing_prerequisites=list(preview.get("missing_prerequisites", [])),
                                    expected_observations=list(preview.get("expected_activity", [])),
                                    confidence=0.0,
                                )

                        append_jsonl(
                            visit_sequence_path,
                            {
                                "generated_utc": utc_now(),
                                "event_type": "decision_tick",
                                "target_id": target.id,
                                "attempt": attempt,
                                "attempt_phase": attempt_phase,
                                "decision": decision,
                                "owned_intent": owned_intent,
                                "preview": preview_summary(preview_status, preview_payload),
                                "dispatch_status": dispatch_status,
                                "dispatch_payload": dispatch_payload,
                            },
                        )
                        time.sleep(self.args.poll_s)

                    if target_pass:
                        if index < len(self.targets):
                            self._issue_safe_stop()
                            self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
                        break

                    self._issue_safe_stop()
                    self._wait_for_pursuit_quiet(self.args.pursuit_settle_timeout_s)
                    if attempt < self.args.max_retries_per_target:
                        attempt += 1
                        self._append_runtime_event(
                            f"{target.label} retrying after {failure_reason or 'visit timeout'}.",
                            category="mission",
                            key=f"retry:{target.id}:{attempt}",
                        )
                        append_jsonl(
                            visit_sequence_path,
                            {
                                "generated_utc": utc_now(),
                                "event_type": "target_retry",
                                "target_id": target.id,
                                "attempt": attempt,
                                "failure_reason": failure_reason or "visit_timeout",
                            },
                        )
                        continue

                    result = {
                        "target_id": target.id,
                        "label": target.label,
                        "attempt": attempt,
                        "pass": False,
                        "model_name": self._target_model_name(target),
                        "first_dispatched_intent": first_dispatched_intent,
                        "failure_reason": failure_reason or "visit_timeout",
                        "failure_phase": "approach_phase" if target_locked_seen else "search_phase",
                        "target_locked_seen": target_locked_seen,
                        "nav_activity_seen": nav_activity_seen,
                        "started_visible": target.start_visible,
                    }
                    target_results.append(result)
                    write_json(target_results_path, {"targets": target_results})
                    self._update_runtime_state(last_visit_result=result, current_target_id="")
                    mission_pass = False
                    mission_error = f"{target.label} failed: {result['failure_reason']}"
                    self._append_runtime_event(mission_error, category="error", key=f"failed:{target.id}")
                    append_jsonl(
                        visit_sequence_path,
                        {
                            "generated_utc": utc_now(),
                            "event_type": "target_failed",
                            "target_id": target.id,
                            "attempt": attempt,
                            "result": result,
                        },
                    )
                    break

                if not target_pass:
                    break
                if index < len(self.targets):
                    self._append_runtime_event("Advancing to the next target.", key=f"advance:{target.id}")

            self._issue_safe_stop()
            mission_verdict = {
                "generated_utc": utc_now(),
                "session_id": session_id,
                "scenario_id": str(self.args.scenario_id),
                "task_text": self.args.task,
                "target_count": len(self.targets),
                "visited_count": len([item for item in target_results if item.get("pass")]),
                "retry_count": sum(max(int(item.get("attempt", 0)), 0) for item in target_results),
                "pass": mission_pass and len([item for item in target_results if item.get("pass")]) == len(self.targets),
                "mission_error": mission_error,
                "target_results_path": str(target_results_path),
                "visit_sequence_path": str(visit_sequence_path),
                "state_history_path": str(state_history_path),
            }
            write_json(mission_root / "mission_verdict.json", mission_verdict)
            summary = {
                "generated_utc": utc_now(),
                "type": str(self.args.artifact_kind),
                "scenario_id": str(self.args.scenario_id),
                "session_id": session_id,
                "pass": bool(mission_verdict["pass"]),
                "mission_root": str(mission_root),
                "mission_verdict_path": str(mission_root / "mission_verdict.json"),
            }
            write_json(mission_root / "summary.json", summary)
            self._update_runtime_state(
                running=False,
                proof_state="completed" if mission_verdict["pass"] else "failed",
                mission_phase="completed" if mission_verdict["pass"] else "failed",
                mission_status="completed" if mission_verdict["pass"] else "failed",
                search_bias_active=False,
                visited_targets=[item["target_id"] for item in target_results if item.get("pass")],
                remaining_targets=[item.id for item in self.targets if item.id not in {entry["target_id"] for entry in target_results if entry.get("pass")}],
                mission_verdict=mission_verdict,
                current_target_id="",
            )
            self._append_runtime_event(
                "Visit mission completed." if mission_verdict["pass"] else "Visit mission failed.",
                category="result",
                key="mission_verdict",
            )
            return summary
        finally:
            try:
                final_state = fetch_dashboard_state(self.dashboard_url, timeout_s=self.args.timeout_s)
                self._clear_mission_targets(final_state, mission_root)
            except Exception:
                pass
            self._update_runtime_state(running=False, search_bias_active=False, current_target_id="")
            if started_here and not self.args.keep_environment:
                try:
                    self._stop_environment()
                except Exception:
                    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a deterministic visible-ball visit mission.")
    parser.add_argument("--dashboard-url", default=DEFAULT_DASHBOARD_URL)
    parser.add_argument("--contract", default=str(REPO_ROOT / "runtime" / "contracts" / "llm_control_contract.yaml"))
    parser.add_argument("--task", default=DEFAULT_TASK_TEXT)
    parser.add_argument("--scenario-id", default="visit_single_ball_proof")
    parser.add_argument("--scenario-label", default="Visit Single Ball Proof")
    parser.add_argument("--artifact-kind", default="visit_mission")
    parser.add_argument("--poll-s", type=float, default=1.0)
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--dispatch-cooldown-s", type=float, default=2.0)
    parser.add_argument("--environment-timeout-s", type=float, default=360.0)
    parser.add_argument("--max-target-runtime-s", type=float, default=120.0)
    parser.add_argument("--search-timeout-s", type=float, default=35.0)
    parser.add_argument("--approach-timeout-s", type=float, default=70.0)
    parser.add_argument("--post-goal-truth-grace-s", type=float, default=DEFAULT_POST_GOAL_TRUTH_GRACE_S)
    parser.add_argument("--hidden-start-settle-s", type=float, default=3.0)
    parser.add_argument("--pursuit-settle-timeout-s", type=float, default=8.0)
    parser.add_argument("--max-retries-per-target", type=int, default=1)
    parser.add_argument("--target-model-name", default=DEFAULT_TARGET_MODEL_NAME)
    parser.add_argument("--target-model-sdf", default=str(DEFAULT_TARGET_MODEL_SDF))
    parser.add_argument("--keep-visited-targets", dest="remove_visited_targets", action="store_false")
    parser.set_defaults(remove_visited_targets=True)
    parser.add_argument("--keep-environment", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runner = VisitMissionRunner(args)
    summary = runner.run()
    print(f"VISIT_MISSION_SUMMARY={summary['mission_verdict_path']}")
    return 0 if summary["pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
