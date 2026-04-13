from __future__ import annotations

import json
import re
import socket
import sys
import threading
import subprocess
from collections import deque
from types import ModuleType, SimpleNamespace
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import dashboard_service  # noqa: E402


def _install_world_stream_stubs() -> None:
    if "cv2" not in sys.modules:
        cv2_stub = ModuleType("cv2")
        cv2_stub.imwrite = lambda *_args, **_kwargs: True
        cv2_stub.VideoWriter_fourcc = lambda *_args, **_kwargs: 0

        class _Writer:
            def __init__(self, *_args, **_kwargs) -> None:
                self.frames = []

            def write(self, frame) -> None:
                self.frames.append(frame)

            def release(self) -> None:
                return None

        cv2_stub.VideoWriter = _Writer
        cv2_stub.FONT_HERSHEY_SIMPLEX = 0
        cv2_stub.LINE_AA = 0
        cv2_stub.COLOR_BGR2GRAY = 0
        cv2_stub.COLOR_BGR2HSV = 0
        cv2_stub.COLOR_RGB2BGR = 0
        cv2_stub.COLOR_RGBA2BGR = 0
        cv2_stub.COLOR_BGRA2BGR = 0
        cv2_stub.COLOR_GRAY2BGR = 0
        cv2_stub.cvtColor = lambda frame, *_args, **_kwargs: frame
        cv2_stub.putText = lambda frame, *_args, **_kwargs: frame
        cv2_stub.inRange = lambda frame, *_args, **_kwargs: frame
        cv2_stub.bitwise_or = lambda a, b: a
        cv2_stub.morphologyEx = lambda frame, *_args, **_kwargs: frame
        cv2_stub.findContours = lambda *_args, **_kwargs: ([], None)
        cv2_stub.contourArea = lambda contour: 0.0
        sys.modules["cv2"] = cv2_stub

    if "numpy" not in sys.modules:
        np_stub = ModuleType("numpy")
        np_stub.uint8 = int
        np_stub.full = lambda *args, **kwargs: None
        np_stub.zeros = lambda *args, **kwargs: None
        np_stub.frombuffer = lambda *_args, **_kwargs: b""
        np_stub.mean = lambda *_args, **_kwargs: 0.0
        np_stub.std = lambda *_args, **_kwargs: 0.0
        np_stub.bitwise_or = lambda a, b: a
        np_stub.ones = lambda *args, **kwargs: None
        sys.modules["numpy"] = np_stub

    if "rclpy" not in sys.modules:
        rclpy_stub = ModuleType("rclpy")
        rclpy_stub.init = lambda *_args, **_kwargs: None
        rclpy_stub.shutdown = lambda *_args, **_kwargs: None
        rclpy_stub.spin_once = lambda *_args, **_kwargs: None
        parameter_mod = ModuleType("rclpy.parameter")

        class _Parameter:
            class Type:
                BOOL = "bool"

            def __init__(self, *_args, **_kwargs) -> None:
                return None

        parameter_mod.Parameter = _Parameter
        rclpy_stub.parameter = parameter_mod
        node_mod = ModuleType("rclpy.node")

        class _Node:
            def __init__(self, *_args, **_kwargs) -> None:
                return None

            def create_subscription(self, *_args, **_kwargs):
                return None

            def create_timer(self, *_args, **_kwargs):
                return None

            def set_parameters(self, *_args, **_kwargs):
                return None

            def destroy_node(self) -> None:
                return None

        node_mod.Node = _Node
        qos_mod = ModuleType("rclpy.qos")

        class _Preset:
            SENSOR_DATA = SimpleNamespace(value=None)
            SYSTEM_DEFAULT = SimpleNamespace(value=None)

        class _QoSProfile:
            def __init__(self, *_args, **_kwargs) -> None:
                return None

        class _HistoryPolicy:
            KEEP_LAST = "keep_last"

        class _ReliabilityPolicy:
            RELIABLE = "reliable"

        qos_mod.QoSPresetProfiles = _Preset
        qos_mod.QoSProfile = _QoSProfile
        qos_mod.HistoryPolicy = _HistoryPolicy
        qos_mod.ReliabilityPolicy = _ReliabilityPolicy
        action_mod = ModuleType("rclpy.action")

        class _ActionClient:
            def __init__(self, *_args, **_kwargs) -> None:
                return None

        action_mod.ActionClient = _ActionClient
        sys.modules["rclpy"] = rclpy_stub
        sys.modules["rclpy.parameter"] = parameter_mod
        sys.modules["rclpy.node"] = node_mod
        sys.modules["rclpy.qos"] = qos_mod
        sys.modules["rclpy.action"] = action_mod

    if "sensor_msgs" not in sys.modules:
        sensor_msgs_mod = ModuleType("sensor_msgs")
        msg_mod = ModuleType("sensor_msgs.msg")

        class _Image:
            pass

        msg_mod.Image = _Image
        sensor_msgs_mod.msg = msg_mod
        sys.modules["sensor_msgs"] = sensor_msgs_mod
        sys.modules["sensor_msgs.msg"] = msg_mod

    if "geometry_msgs" not in sys.modules:
        geometry_msgs_mod = ModuleType("geometry_msgs")
        msg_mod = ModuleType("geometry_msgs.msg")

        class _Pose:
            def __init__(self) -> None:
                self.position = SimpleNamespace(x=0.0, y=0.0, z=0.0)
                self.orientation = SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0)

        class _PointStamped:
            def __init__(self) -> None:
                self.point = SimpleNamespace(x=0.0, y=0.0, z=0.0)

        class _PoseStamped:
            def __init__(self) -> None:
                self.header = SimpleNamespace(frame_id="", stamp=None)
                self.pose = _Pose()

        class _Twist:
            def __init__(self) -> None:
                self.linear = SimpleNamespace(x=0.0, y=0.0, z=0.0)
                self.angular = SimpleNamespace(x=0.0, y=0.0, z=0.0)

        class _TwistStamped:
            def __init__(self) -> None:
                self.header = SimpleNamespace(stamp=None, frame_id="")
                self.twist = _Twist()

        msg_mod.Pose = _Pose
        msg_mod.PointStamped = _PointStamped
        msg_mod.PoseStamped = _PoseStamped
        msg_mod.Twist = _Twist
        msg_mod.TwistStamped = _TwistStamped
        geometry_msgs_mod.msg = msg_mod
        sys.modules["geometry_msgs"] = geometry_msgs_mod
        sys.modules["geometry_msgs.msg"] = msg_mod

    if "nav_msgs" not in sys.modules:
        nav_msgs_mod = ModuleType("nav_msgs")
        msg_mod = ModuleType("nav_msgs.msg")

        class _Odometry:
            def __init__(self) -> None:
                self.pose = SimpleNamespace(pose=None)

        msg_mod.Odometry = _Odometry
        nav_msgs_mod.msg = msg_mod
        sys.modules["nav_msgs"] = nav_msgs_mod
        sys.modules["nav_msgs.msg"] = msg_mod

    if "std_msgs" not in sys.modules:
        std_msgs_mod = ModuleType("std_msgs")
        msg_mod = ModuleType("std_msgs.msg")

        class _String:
            pass

        msg_mod.String = _String
        std_msgs_mod.msg = msg_mod
        sys.modules["std_msgs"] = std_msgs_mod
        sys.modules["std_msgs.msg"] = msg_mod


try:
    import world_stream_controller  # noqa: E402
except ModuleNotFoundError:
    _install_world_stream_stubs()
    import world_stream_controller  # noqa: E402

try:
    import visual_demo_observer  # noqa: E402
except ModuleNotFoundError:
    _install_world_stream_stubs()
    import visual_demo_observer  # noqa: E402

import sim_truth_probe  # noqa: E402


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _make_controller(tmp_path: Path) -> dashboard_service.DashboardController:
    controller = dashboard_service.DashboardController.__new__(dashboard_service.DashboardController)
    controller.host = "127.0.0.1"
    controller.port = 8860
    controller.runtime_dir = tmp_path / "runtime"
    controller.state_path = controller.runtime_dir / "dashboard_service_state.json"
    controller.lock_path = controller.runtime_dir / "dashboard_session.lock.json"
    controller.llm_proof_runtime_path = controller.runtime_dir / "llm_turn_then_go_runtime.json"
    controller.visit_mission_runtime_path = controller.runtime_dir / "visit_mission_runtime.json"
    controller.gather_mission_runtime_path = controller.runtime_dir / "gather_mission_runtime.json"
    controller.intent_inbox_path = controller.runtime_dir / "intent_inbox.json"
    controller.intent_ack_path = controller.runtime_dir / "intent_ack.json"
    controller.peer_project_cleanup = "exclusive"
    controller.headless_worker_mode = False
    controller.docker = "docker"
    controller.compose_file = REPO_ROOT / "docker-compose.yml"
    controller.host_repo_mount_source = ""
    controller.launcher_project = ""
    controller.build_on_next_start = False
    controller.state_lock = threading.RLock()
    controller.lifecycle_lock = threading.Lock()
    controller.lifecycle_thread = None
    controller.lifecycle_cancel = threading.Event()
    controller.world_stream_restart_lock = threading.Lock()
    controller._world_stream_stale_since_monotonic = 0.0
    controller._world_stream_last_restart_monotonic = 0.0
    controller.active_env_proc = None
    controller.active_scenario_proc = None
    controller.scenario_thread = None
    controller.intent_thread = None
    controller.sim_gate_container_id = "sim-gate"
    controller.gate_stack_container_id = "gate-stack"
    controller.world_viewer_container_id = "world-viewer"
    controller.operator_view_container_id = "operator-view"
    controller.pending_scenario_id = ""
    controller.scenario_lock = threading.Lock()
    controller.scenario_cancel = threading.Event()
    controller.frozen_intents = {
        "search_for_target": {},
        "plan_to_target": {},
        "track_target": {},
        "safe_stop": {},
    }
    controller.state = {
        "service_started_utc": "2026-03-18T00:00:00Z",
        "service_mode": "api_backed",
        "control_mode": "host_powershell",
        "control_plane_ready": True,
        "control_plane_error": "",
        "warm_services_ready": True,
        "warm_services_status": "ready",
        "warm_service_states": {},
        "launcher_project": "",
        "host_repo_mount_source": "",
        "environment_state": "environment_ready",
        "scenario_state": "ready",
        "session_id": "20260318T000000Z",
        "compose_project": "chasecar_dashboard_20260318T000000Z",
        "execution_lane": "container_kilted",
        "runtime_target": "robot_fidelity_orin",
        "core_ros_distro": "kilted",
        "world_file": "yolo_test_world_v6_clean_uat.world",
        "world_name": "yolo_test_world",
        "phase": "M3",
        "target_id": "single_target",
        "target_transition_active": False,
        "active_scenario": "llm_turn_then_go_proof",
        "environment_message": "ready",
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
        "placed_targets": [],
        "capture_loss_count": 0,
        "route_order": [],
        "latest_operator_event": "",
        "recent_operator_events": [],
        "world_stream_url": "http://127.0.0.1:8891/vnc.html?autoconnect=1&resize=scale&path=websockify",
        "world_stream_port": 8891,
        "operator_view_backend": "xpra",
        "operator_view_url": "http://127.0.0.1:14500/",
        "operator_view_port": 14500,
        "operator_view_ready": True,
        "operator_view_status": "ready",
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
        "world_stream_restart_cooldown_s": dashboard_service.WORLD_STREAM_RESTART_COOLDOWN_S,
        "world_stream_restart_max_attempts": dashboard_service.WORLD_STREAM_RESTART_MAX_ATTEMPTS,
        "startup_retry_count": 0,
        "startup_cleanup_count": 0,
        "startup_last_cleanup_projects": [],
        "lock_file": "",
        "scenarios": [],
    }
    controller._refresh_control_plane_state = lambda force=False: None
    controller._current_visual_dir = lambda: tmp_path / "visual"
    controller._llm_supervisor_state = lambda: {}
    controller._visit_mission_runtime_state = lambda: {}
    controller._gather_mission_runtime_state = lambda: {}
    return controller


def _write_world_state(tmp_path: Path, payload: dict[str, object]) -> Path:
    visual_dir = tmp_path / "visual"
    visual_dir.mkdir(parents=True, exist_ok=True)
    _write_json(visual_dir / "state.json", {"raw_frame_count": 0, "debug_frame_count": 0, "telemetry_frame_count": 0})
    _write_json(visual_dir / "world_stream_state.json", payload)
    screenshot_path = str(payload.get("screenshot_path", "") or "")
    if screenshot_path:
        screenshot_file = Path(screenshot_path)
        screenshot_file.parent.mkdir(parents=True, exist_ok=True)
        screenshot_file.write_bytes(b"frame")
    return visual_dir


def _write_operator_view_state(tmp_path: Path, payload: dict[str, object]) -> Path:
    visual_dir = tmp_path / "visual"
    visual_dir.mkdir(parents=True, exist_ok=True)
    _write_json(visual_dir / "state.json", {"raw_frame_count": 0, "debug_frame_count": 0, "telemetry_frame_count": 0})
    _write_json(visual_dir / "operator_view_state.json", payload)
    return visual_dir


def _serve_dashboard_path(path: str, tmp_path: Path) -> list[tuple[Path, str, bool]]:
    served: list[tuple[Path, str, bool]] = []
    handler = dashboard_service.DashboardRequestHandler.__new__(dashboard_service.DashboardRequestHandler)
    handler.path = path
    handler.server = SimpleNamespace(controller=_make_controller(tmp_path))
    handler._serve_file = lambda file_path, content_type, no_cache=False: served.append((Path(file_path), content_type, no_cache))
    handler._json_response = lambda status, payload: (_ for _ in ()).throw(AssertionError(f"unexpected json response: {status} {payload}"))
    dashboard_service.DashboardRequestHandler.do_GET(handler)
    return served


def test_make_session_id_uses_subsecond_precision():
    session_id = dashboard_service.make_session_id()
    assert re.fullmatch(r"\d{8}T\d{12}Z", session_id)


def _beta_dashboard_world_snapshots(*states: dict[str, object]) -> list[dict[str, object]]:
    html_path = REPO_ROOT / "runtime/dashboard/beta_dashboard.html"
    script = html_path.read_text(encoding="utf-8")
    script = script.split("<script>", 1)[1].rsplit("</script>", 1)[0]
    script = re.sub(r"\npoll\(\);\s*setInterval\(poll, 1000\);\s*$", "\n", script)
    payload = json.dumps(list(states))
    node_script = f"""
const states = {payload};
const elements = new Map();
function makeElement(id) {{
  const classes = new Set();
  const el = {{
    id,
    style: {{ display: '' }},
    disabled: false,
    title: '',
    textContent: '',
    innerHTML: '',
    _classes: classes,
    classList: {{
      add(...names) {{ names.forEach((name) => classes.add(name)); }},
      remove(...names) {{ names.forEach((name) => classes.delete(name)); }},
      toggle(name, force) {{
        const shouldAdd = force === undefined ? !classes.has(name) : !!force;
        if (shouldAdd) classes.add(name);
        else classes.delete(name);
        return shouldAdd;
      }},
    }},
    removeAttribute(name) {{ if (name === 'src') this.src = ''; }},
  }};
  let srcValue = '';
  Object.defineProperty(el, 'src', {{
    get() {{ return srcValue; }},
    set(value) {{
      srcValue = String(value);
      if (typeof el.onload === 'function') el.onload();
    }},
  }});
  el.onload = null;
  el.onerror = null;
  if (id === 'img-world') {{
    el.onload = () => imgOk('world');
    el.onerror = () => imgFail('world');
  }}
  if (id === 'img-yolo') {{
    el.onload = () => imgOk('yolo');
    el.onerror = () => imgFail('yolo');
  }}
  el.setAttribute = (name, value) => {{ if (name === 'src') el.src = String(value); }};
  Object.defineProperty(el, 'className', {{
    get() {{ return Array.from(classes).join(' '); }},
    set(value) {{
      classes.clear();
      String(value).split(/\\s+/).filter(Boolean).forEach((name) => classes.add(name));
    }},
  }});
  return el;
}}
function getElementById(id) {{
  if (!elements.has(id)) elements.set(id, makeElement(id));
  return elements.get(id);
}}
globalThis.document = {{
  getElementById,
  querySelectorAll: () => [],
  addEventListener: () => {{}},
}};
globalThis.window = {{ open: () => {{}} }};
globalThis.fetch = async () => ({{ ok: true, json: async () => ({{}}) }});
globalThis.setInterval = () => 0;
globalThis.clearInterval = () => {{}};
globalThis.Image = class {{
  constructor() {{ this.onload = null; this.onerror = null; this._src = ''; }}
  set src(value) {{
    this._src = String(value);
    if (!globalThis.__deferImageLoad && this.onload) this.onload();
  }}
  get src() {{ return this._src; }}
}};
{script}
function snapshot() {{
  const ids = ['label-world','badge-world','ph-world','ph-world-text','note-world','img-world','frame-operator','btn-open-live','btn-embed-live','btn-legacy-world','ph-operator','ph-operator-text'];
  const pick = (id) => elements.get(id);
  return {{
    label: pick('label-world').textContent,
    badgeText: pick('badge-world').textContent,
    badgeClass: pick('badge-world').className,
    badgeTitle: pick('badge-world').title,
    worldDisplay: pick('img-world').style.display,
    worldPlaceholderDisplay: pick('ph-world').style.display,
    worldPlaceholderText: pick('ph-world-text').textContent,
    noteText: pick('note-world').textContent,
    noteDisplay: pick('note-world').style.display,
    operatorFrameDisplay: pick('frame-operator').style.display,
    operatorPlaceholderDisplay: pick('ph-operator').style.display,
    operatorPlaceholderText: pick('ph-operator-text').textContent,
    openHidden: pick('btn-open-live').className.includes('hidden'),
    embedHidden: pick('btn-embed-live').className.includes('hidden'),
    legacyHidden: pick('btn-legacy-world').className.includes('hidden'),
  }};
}}
const snapshots = [];
for (const state of states) {{
  globalThis.__deferImageLoad = Boolean(state.__defer_image_load);
  S = state;
  renderImages();
  snapshots.push(snapshot());
}}
process.stdout.write(JSON.stringify(snapshots));
"""
    completed = subprocess.run(["node", "-"], input=node_script, capture_output=True, check=True, text=True)
    return json.loads(completed.stdout)


def test_get_state_exposes_world_stream_freshness_fields(tmp_path):
    controller = _make_controller(tmp_path)
    _write_world_state(
        tmp_path,
        {
            "session_id": controller.state["session_id"],
            "partition": controller.state["session_id"],
            "world_surface": "streamed_sim",
            "world_stream_url": controller.state["world_stream_url"],
            "world_stream_ready": False,
            "world_stream_nonblank": True,
            "world_stream_interactive": False,
            "same_session_partition": True,
            "viewer_process_healthy": False,
            "viewer_client_mode": "gazebo_sensor_camera",
            "camera_profile": "robot_follow",
            "render_backend": "gazebo_sensor_camera:ogre2",
            "software_render_only": False,
            "display_server": "none",
            "gpu_available": True,
            "scene_content_ok": True,
            "robot_visible_ok": True,
            "target_visible_ok": True,
            "failure_class": "world_stream_stale",
            "image_topic": "/observer_world/image_raw",
            "frame_count": 42,
            "elapsed_s": 9.5,
            "frame_coverage_ratio": 0.81,
            "nonblank_ratio": 0.93,
            "scene_content_ratio": 0.88,
            "robot_visible_ratio": 0.77,
            "target_visible_ratio": 0.66,
            "robot_max_area_px": 151.0,
            "target_max_area_px": 91.0,
            "latest_robot_area_px": 151.0,
            "latest_target_area_px": 91.0,
            "latest_frame_error": "",
            "truth_target_seen": True,
            "screenshot_path": str(tmp_path / "visual" / "live" / "world_stream.jpg"),
            "video_path": str(tmp_path / "visual" / "world_stream.mp4"),
            "latest_frame_wall_s": 123.4,
            "latest_frame_utc": "2026-03-18T12:00:00Z",
            "latest_frame_age_s": 3.2,
            "frames_stale": True,
            "healthy_stale_seconds": 2.5,
        },
    )

    state = controller.get_state()

    assert state["world_stream_ready"] is False
    assert state["world_stream_failure_class"] == "world_stream_stale"
    assert state["world_stream_frame_count"] == 42
    assert state["world_stream_latest_frame_utc"] == "2026-03-18T12:00:00Z"
    assert state["world_stream_frame_age_s"] == 3.2
    assert state["world_stream_frames_stale"] is True
    assert state["world_stream_viewer_process_healthy"] is False
    assert state["world_stream_renderable"] is True
    assert state["world_stream_transport_healthy"] is False
    assert state["world_stream_degraded"] is True


def test_get_state_surfaces_latest_truth_target_model_name(tmp_path):
    controller = _make_controller(tmp_path)
    visual_dir = tmp_path / "visual"
    visual_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        visual_dir / "state.json",
        {
            "raw_frame_count": 1,
            "debug_frame_count": 1,
            "telemetry_frame_count": 1,
            "truth_alignment_ok": True,
            "truth_failure_class": "",
            "true_target_seen": True,
            "latest_truth_target_world": {"x": 1.0, "y": 0.1},
            "latest_truth_target_model_name": "visit_mission_target_ball_2",
        },
    )
    _write_json(
        visual_dir / "world_stream_state.json",
        {
            "session_id": controller.state["session_id"],
            "partition": controller.state["session_id"],
            "world_stream_ready": False,
            "same_session_partition": True,
            "frames_stale": False,
        },
    )
    _write_json(
        visual_dir / "truth_state.json",
        {
            "session_id": controller.state["session_id"],
            "robot_truth_seen": True,
            "target_model_candidates": list(dashboard_service.TRUTH_TARGET_MODEL_NAMES),
        },
    )

    state = controller.get_state()

    assert state["latest_truth_target_model_name"] == "visit_mission_target_ball_2"
    assert state["perception"]["latest_truth_target_model_name"] == "visit_mission_target_ball_2"


def test_get_state_surfaces_nav2_server_ready_from_brain_state(tmp_path):
    controller = _make_controller(tmp_path)
    visual_dir = tmp_path / "visual"
    visual_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        visual_dir / "state.json",
        {
            "raw_frame_count": 1,
            "debug_frame_count": 1,
            "telemetry_frame_count": 1,
            "latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
        },
    )
    _write_json(
        visual_dir / "brain_state.json",
        {
            "nav2_server_ready": True,
            "goal_in_progress": False,
            "search_active": False,
        },
    )
    _write_json(
        visual_dir / "world_stream_state.json",
        {
            "session_id": controller.state["session_id"],
            "partition": controller.state["session_id"],
            "world_stream_ready": True,
            "same_session_partition": True,
            "frames_stale": False,
        },
    )

    state = controller.get_state()

    assert state["brain"]["nav2_server_ready"] is True


def test_get_state_surfaces_last_feedback_status_from_brain_state(tmp_path):
    controller = _make_controller(tmp_path)
    visual_dir = tmp_path / "visual"
    visual_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        visual_dir / "state.json",
        {
            "raw_frame_count": 1,
            "debug_frame_count": 1,
            "telemetry_frame_count": 1,
            "latest_robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
        },
    )
    _write_json(
        visual_dir / "brain_state.json",
        {
            "last_feedback_status": "visit_target_reached",
            "last_feedback_text": "visit_target: ball_b reached",
        },
    )
    _write_json(
        visual_dir / "world_stream_state.json",
        {
            "session_id": controller.state["session_id"],
            "partition": controller.state["session_id"],
            "world_stream_ready": True,
            "same_session_partition": True,
            "frames_stale": False,
        },
    )

    state = controller.get_state()

    assert state["brain"]["last_feedback_status"] == "visit_target_reached"


def test_get_state_derives_healthy_world_renderability_from_current_session_artifact(tmp_path):
    controller = _make_controller(tmp_path)
    _write_world_state(
        tmp_path,
        {
            "session_id": controller.state["session_id"],
            "partition": controller.state["session_id"],
            "world_surface": "streamed_sim",
            "world_stream_url": "",
            "world_stream_ready": True,
            "world_stream_nonblank": True,
            "world_stream_interactive": False,
            "same_session_partition": True,
            "viewer_process_healthy": True,
            "camera_profile": "robot_follow",
            "scene_content_ok": True,
            "robot_visible_ok": True,
            "target_visible_ok": True,
            "failure_class": "",
            "frame_count": 12,
            "received_frame_count": 12,
            "rendered_frame_count": 12,
            "latest_frame_utc": "2026-03-18T12:00:05Z",
            "latest_frame_age_s": 0.4,
            "frames_stale": False,
            "latest_frame_error": "",
            "screenshot_path": str(tmp_path / "visual" / "live" / "world_stream.jpg"),
            "video_path": str(tmp_path / "visual" / "world_stream.mp4"),
        },
    )

    state = controller.get_state()

    assert state["world_stream_ready"] is True
    assert state["world_stream_renderable"] is True
    assert state["world_stream_transport_healthy"] is True
    assert state["world_stream_degraded"] is False


def test_request_scenario_run_route_planning_queues_after_sim_reset(monkeypatch, tmp_path):
    controller = _make_controller(tmp_path)
    started: list[threading.Thread] = []

    class _FakeThread:
        def __init__(self, *, target=None, name=None, daemon=None, args=()):
            self.target = target
            self.name = name
            self.daemon = daemon
            self.args = args
            self._alive = False
            started.append(self)

        def start(self) -> None:
            self._alive = True

        def is_alive(self) -> bool:
            return self._alive

    monkeypatch.setattr(dashboard_service.threading, "Thread", _FakeThread)

    status, payload = controller.request_scenario_run("visit_route_planning")

    assert status == 202
    assert payload["accepted"] is True
    assert "queued after sim reset" in payload["message"]
    assert controller.pending_scenario_id == "visit_route_planning"
    assert started
    assert started[0].target == controller._reset_environment_worker


def test_start_pending_scenario_if_any_launches_queued_scenario(monkeypatch, tmp_path):
    controller = _make_controller(tmp_path)
    launched: list[str] = []
    controller.pending_scenario_id = "visit_route_planning"
    controller._launch_scenario_thread = lambda scenario: launched.append(scenario.id)

    controller._start_pending_scenario_if_any()

    assert launched == ["visit_route_planning"]
    assert controller.pending_scenario_id == ""


def test_get_state_clears_completed_visit_current_target_id(tmp_path):
    controller = _make_controller(tmp_path)
    controller.state["active_scenario"] = "visit_three_ball_sequence"
    controller._visit_mission_runtime_state = lambda: {
        "proof_state": "completed",
        "mission_phase": "completed",
        "mission_status": "completed",
        "current_target_id": "ball_3",
        "visit_index": 3,
        "visited_targets": ["ball_1", "ball_2", "ball_3"],
        "remaining_targets": [],
        "mission_verdict": {"pass": True},
    }

    state = controller.get_state()

    assert state["mission_status"] == "completed"
    assert state["current_target_id"] == ""


def test_truth_probe_defaults_include_visit_prefix(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sim_truth_probe.py",
            "--session-id",
            "20260327T060000Z",
            "--output-dir",
            "artifacts/session/20260327T060000Z/visual",
            "--world-name",
            "yolo_test_world",
        ],
    )

    args = sim_truth_probe.parse_args()
    assert args.target_model_prefix == "visit_mission_target_"


def test_truth_probe_select_target_poses_reports_all_matching_candidates():
    poses = [
        {"name": "jetbot", "position": {"x": 0.0, "y": 0.0}},
        {"name": "visit_mission_target_ball_2", "position": {"x": 1.2, "y": 0.4}},
        {"name": "visit_mission_target_ball_3", "position": {"x": 1.5, "y": -0.3}},
    ]

    poses_by_name, names_seen, first_pose, first_name = sim_truth_probe.select_target_poses(
        poses,
        ["visit_mission_target_ball_1", "visit_mission_target_ball_2", "visit_mission_target_ball_3"],
    )

    assert names_seen == ["visit_mission_target_ball_2", "visit_mission_target_ball_3"]
    assert first_name == "visit_mission_target_ball_2"
    assert first_pose == poses[1]
    assert poses_by_name == {
        "visit_mission_target_ball_2": poses[1],
        "visit_mission_target_ball_3": poses[2],
    }


def test_truth_probe_prefix_discovers_visit_models():
    poses = [
        {"name": "jetbot", "position": {"x": 0.0, "y": 0.0}},
        {"name": "visit_mission_target_ball_a", "position": {"x": 1.0, "y": 0.5}},
        {"name": "visit_mission_target_ball_c", "position": {"x": 2.0, "y": -0.5}},
        {"name": "uat_nav2_target", "position": {"x": 3.0, "y": 0.0}},
    ]

    poses_by_name, names_seen, first_pose, first_name = sim_truth_probe.select_target_poses(
        poses,
        ["uat_nav2_target"],
        ["visit_mission_target_"],
    )

    assert "uat_nav2_target" in poses_by_name
    assert "visit_mission_target_ball_a" in poses_by_name
    assert "visit_mission_target_ball_c" in poses_by_name
    assert "jetbot" not in poses_by_name
    assert first_name == "uat_nav2_target"


def test_select_active_truth_target_prefers_active_visit_target_and_fails_closed_when_missing():
    truth_state = {
        "target_poses_by_name": {
            "visit_mission_target_ball_1": {"position": {"x": 1.0, "y": 0.1}},
            "visit_mission_target_ball_2": {"position": {"x": 2.0, "y": 0.2}},
        },
        "true_target_pose": {"position": {"x": 1.0, "y": 0.1}},
        "target_model_name": "visit_mission_target_ball_1",
        "target_model_candidates": [
            "visit_mission_target_ball_1",
            "visit_mission_target_ball_2",
            "visit_mission_target_ball_3",
        ],
    }

    truth_target, model_name = visual_demo_observer.select_active_truth_target(truth_state, "ball_2")
    assert truth_target == (2.0, 0.2)
    assert model_name == "visit_mission_target_ball_2"

    missing_target, missing_model_name = visual_demo_observer.select_active_truth_target(truth_state, "ball_3")
    assert missing_target is None
    assert missing_model_name == ""


def test_visual_observer_operator_state_uses_visit_runtime_current_target(tmp_path, monkeypatch):
    operator_status_path = tmp_path / "visual" / "operator_status.json"
    operator_status_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(
        operator_status_path,
        {
            "phase": "visit_three_ball_sequence",
            "target_id": "ball_sequence",
            "target_transition_active": False,
            "status_text": "Running Visit Three Ball Sequence",
        },
    )
    runtime_path = tmp_path / "visit_mission_runtime.json"
    _write_json(runtime_path, {"current_target_id": "ball_2"})
    monkeypatch.setattr(visual_demo_observer, "VISIT_MISSION_RUNTIME_PATH", runtime_path)

    observer = visual_demo_observer.VisualDemoObserver.__new__(visual_demo_observer.VisualDemoObserver)
    observer.args = SimpleNamespace(phase="", target_id="", target_transition_active=False)
    observer.operator_status_path = operator_status_path

    state = observer._operator_state()

    assert state["target_id"] == "ball_2"


def test_wait_for_truth_ready_requires_full_candidate_set(tmp_path, monkeypatch):
    controller = _make_controller(tmp_path)
    visual_dir = tmp_path / "visual"
    visual_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        visual_dir / "truth_state.json",
        {
            "session_id": controller.state["session_id"],
            "robot_truth_seen": True,
            "target_model_candidates": list(dashboard_service.TRUTH_TARGET_MODEL_NAMES),
        },
    )

    monkeypatch.setattr(dashboard_service.time, "sleep", lambda *_args, **_kwargs: None)
    assert controller._wait_for_truth_ready(0.01) is True


def test_wait_for_truth_ready_rejects_incomplete_candidate_set(tmp_path, monkeypatch):
    controller = _make_controller(tmp_path)
    visual_dir = tmp_path / "visual"
    visual_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        visual_dir / "truth_state.json",
        {
            "session_id": controller.state["session_id"],
            "robot_truth_seen": True,
            "target_model_candidates": ["uat_nav2_target", "uat_snapshot_target"],
        },
    )

    monkeypatch.setattr(dashboard_service.time, "sleep", lambda *_args, **_kwargs: None)
    assert controller._wait_for_truth_ready(0.01) is False


def test_get_state_world_not_renderable_without_current_session_frame(tmp_path):
    controller = _make_controller(tmp_path)
    _write_world_state(
        tmp_path,
        {
            "session_id": controller.state["session_id"],
            "partition": controller.state["session_id"],
            "world_surface": "streamed_sim",
            "world_stream_url": "",
            "world_stream_ready": False,
            "world_stream_nonblank": False,
            "world_stream_interactive": False,
            "same_session_partition": True,
            "viewer_process_healthy": False,
            "camera_profile": "robot_follow",
            "scene_content_ok": False,
            "robot_visible_ok": False,
            "target_visible_ok": False,
            "failure_class": "world_stream_no_recent_frames",
            "frame_count": 0,
            "received_frame_count": 0,
            "rendered_frame_count": 0,
            "latest_frame_utc": "",
            "latest_frame_age_s": None,
            "frames_stale": False,
            "latest_frame_error": "",
            "screenshot_path": str(tmp_path / "visual" / "live" / "world_stream.jpg.missing"),
            "video_path": str(tmp_path / "visual" / "world_stream.mp4"),
        },
    )

    state = controller.get_state()

    assert state["world_stream_ready"] is False
    assert state["world_stream_renderable"] is False
    assert state["world_stream_transport_healthy"] is False
    assert state["world_stream_degraded"] is False


def test_get_state_exposes_operator_view_fields(tmp_path):
    controller = _make_controller(tmp_path)
    _write_operator_view_state(
        tmp_path,
        {
            "session_id": controller.state["session_id"],
            "backend": "xpra",
            "url": "http://127.0.0.1:14512/",
            "port": 14512,
            "ready": True,
            "status": "ready",
            "failure_class": "",
            "latest_heartbeat_utc": dashboard_service.utc_now(),
            "apps": {
                "gz_gui": {"pid": 1001, "alive": True},
                "raw_viewer": {"pid": 1002, "alive": True},
                "debug_viewer": {"pid": 1003, "alive": True},
            },
        },
    )

    state = controller.get_state()

    assert state["operator_view_backend"] == "xpra"
    assert state["operator_view_url"] == "http://127.0.0.1:14512/"
    assert state["operator_view_port"] == 14512
    assert state["operator_view_ready"] is True
    assert state["operator_view_status"] == "ready"
    assert state["operator_view_failure_class"] == ""


def test_get_state_blanks_operator_view_url_until_ready(tmp_path):
    controller = _make_controller(tmp_path)
    _write_operator_view_state(
        tmp_path,
        {
            "session_id": controller.state["session_id"],
            "backend": "xpra",
            "url": "http://127.0.0.1:14512/",
            "port": 14512,
            "ready": False,
            "status": "starting",
            "failure_class": "",
            "latest_heartbeat_utc": dashboard_service.utc_now(),
            "apps": {
                "gz_gui": {"pid": 1001, "alive": True},
                "raw_viewer": {"pid": 1002, "alive": True},
                "debug_viewer": {"pid": 1003, "alive": True},
            },
        },
    )

    not_ready = controller.get_state()
    assert not_ready["operator_view_ready"] is False
    assert not_ready["operator_view_url"] == ""

    _write_operator_view_state(
        tmp_path,
        {
            "session_id": controller.state["session_id"],
            "backend": "xpra",
            "url": "http://127.0.0.1:14512/",
            "port": 14512,
            "ready": True,
            "status": "ready",
            "failure_class": "",
            "latest_heartbeat_utc": dashboard_service.utc_now(),
            "apps": {
                "gz_gui": {"pid": 1001, "alive": True},
                "raw_viewer": {"pid": 1002, "alive": True},
                "debug_viewer": {"pid": 1003, "alive": True},
            },
        },
    )

    ready = controller.get_state()
    assert ready["operator_view_ready"] is True
    assert ready["operator_view_url"] == "http://127.0.0.1:14512/"


def test_get_state_marks_operator_view_stale_when_heartbeat_old(tmp_path):
    controller = _make_controller(tmp_path)
    _write_operator_view_state(
        tmp_path,
        {
            "session_id": controller.state["session_id"],
            "backend": "xpra",
            "url": "http://127.0.0.1:14512/",
            "port": 14512,
            "ready": True,
            "status": "ready",
            "failure_class": "",
            "latest_heartbeat_utc": "2000-01-01T00:00:00Z",
            "apps": {
                "gz_gui": {"pid": 1001, "alive": True},
                "raw_viewer": {"pid": 1002, "alive": True},
                "debug_viewer": {"pid": 1003, "alive": True},
            },
        },
    )

    state = controller.get_state()

    assert state["operator_view_ready"] is False
    assert state["operator_view_status"] == "stale"
    assert state["operator_view_failure_class"] == "operator_view_stale"


def test_required_gate_service_states_cover_running_created_exited_and_missing(tmp_path):
    controller = _make_controller(tmp_path)
    service_states = {
        "sim-gate": {"service": "sim-gate", "status": "running", "container_id": "sim-gate-1"},
        "world-viewer": {"service": "world-viewer", "status": "created", "container_id": "world-viewer-1"},
        "gate-stack": {"service": "gate-stack", "status": "exited", "container_id": "gate-stack-1"},
        "operator-view": {"service": "operator-view", "status": "missing", "container_id": ""},
    }
    controller._docker_service_state = lambda _project_name, service_name: dict(service_states[service_name])

    resolved = controller._required_gate_service_states("chasecar_dashboard_test")

    assert resolved == service_states
    assert controller._gate_services_ready(resolved) is False
    failure_class, failure_message = controller._classify_gate_service_states(resolved)
    assert failure_class == "gate_services_missing"
    assert "operator-view" in failure_message


def test_classify_gate_service_states_reports_not_running_when_services_exist(tmp_path):
    controller = _make_controller(tmp_path)
    gate_service_states = {
        "sim-gate": {"service": "sim-gate", "status": "running", "container_id": "sim-gate-1"},
        "world-viewer": {"service": "world-viewer", "status": "created", "container_id": "world-viewer-1"},
        "gate-stack": {"service": "gate-stack", "status": "exited", "container_id": "gate-stack-1"},
        "operator-view": {"service": "operator-view", "status": "running", "container_id": "operator-view-1"},
    }

    failure_class, failure_message = controller._classify_gate_service_states(gate_service_states)

    assert failure_class == "gate_services_not_running"
    assert "world-viewer=created" in failure_message
    assert "gate-stack=exited" in failure_message


def test_start_environment_worker_records_gate_service_failure_class_and_states(tmp_path, monkeypatch):
    controller = _make_controller(tmp_path)
    controller._clear_llm_proof_runtime_state = lambda: None
    controller._clear_visit_mission_runtime_state = lambda: None
    controller._write_operator_status = lambda **_kwargs: None
    controller._write_lock_file = lambda: None
    controller._remove_lock_file = lambda: None
    controller._record_operator_event = lambda *_args, **_kwargs: None
    controller._teardown_environment = lambda env=None: None
    controller._run_environment_compose_up = lambda *_args, **_kwargs: (0, "ok")
    controller._refresh_session_container_ids = lambda *_args, **_kwargs: None
    controller._wait_for_required_gate_services = lambda _project_name, _timeout_s: {
        "sim-gate": {"service": "sim-gate", "status": "running", "container_id": "sim-gate-1"},
        "world-viewer": {"service": "world-viewer", "status": "created", "container_id": "world-viewer-1"},
        "gate-stack": {"service": "gate-stack", "status": "exited", "container_id": "gate-stack-1"},
        "operator-view": {"service": "operator-view", "status": "running", "container_id": "operator-view-1"},
    }
    monkeypatch.setattr(dashboard_service, "find_free_port", lambda start, end: start)
    monkeypatch.setattr(dashboard_service, "make_session_id", lambda: "20260320T200000Z")

    controller._start_environment_worker()

    assert controller.state["environment_state"] == "error"
    assert controller.state["environment_failure_class"] == "gate_services_not_running"
    assert controller.state["gate_service_states"]["world-viewer"]["status"] == "created"
    assert controller.state["gate_service_states"]["gate-stack"]["status"] == "exited"
    assert controller.state["operator_view_ready"] is False
    assert controller.state["operator_view_url"] == ""
    assert controller.state["operator_view_status"] == "error"


def test_dashboard_routes_promote_beta_and_keep_classic_alias(tmp_path):
    root_served = _serve_dashboard_path("/", tmp_path)
    classic_served = _serve_dashboard_path("/browser_dashboard.html", tmp_path)

    assert root_served[0][0].name == "beta_dashboard.html"
    assert classic_served[0][0].name == "browser_dashboard.html"


def test_beta_dashboard_default_route_stays_inert_before_viewer_ready(tmp_path):
    root_served = _serve_dashboard_path("/", tmp_path)
    assert root_served[0][0].name == "beta_dashboard.html"

    controller = _make_controller(tmp_path)
    _write_operator_view_state(
        tmp_path,
        {
            "session_id": controller.state["session_id"],
            "backend": "xpra",
            "url": "http://127.0.0.1:14512/",
            "port": 14512,
            "ready": False,
            "status": "starting",
            "failure_class": "",
            "latest_heartbeat_utc": dashboard_service.utc_now(),
            "apps": {
                "gz_gui": {"pid": 1001, "alive": True},
                "raw_viewer": {"pid": 1002, "alive": True},
                "debug_viewer": {"pid": 1003, "alive": True},
            },
        },
    )

    state = controller.get_state()
    assert state["operator_view_ready"] is False
    assert state["operator_view_url"] == ""


def test_beta_dashboard_includes_corral_menu_and_stage_mapping():
    html_path = REPO_ROOT / "runtime/dashboard/beta_dashboard.html"
    html = html_path.read_text(encoding="utf-8")

    assert "pickScenario('corral_single_ball_place')" in html
    assert "runScenario('corral_single_ball_place')" in html
    assert "Run Single-Ball Corral" in html
    assert "const CORRAL_STAGE_LABELS = ['Init','Visit','Capture','Place','Done'];" in html
    assert "Acquiring the ball" in html
    assert "Controlling the ball" in html
    assert "Placing ball into the zone" in html


def test_browser_dashboard_promotes_single_ball_corral_as_featured_demo():
    js_path = REPO_ROOT / "runtime/dashboard/browser_dashboard.js"
    js = js_path.read_text(encoding="utf-8")

    assert "{ id: 'corral_single_ball_place', label: 'Single-Ball Corral' }" in js
    assert "{ id: 'visit_route_planning', label: 'LLM Route Planning' }" in js
    assert js.index("{ id: 'corral_single_ball_place', label: 'Single-Ball Corral' }") < js.index(
        "{ id: 'visit_route_planning', label: 'LLM Route Planning' }"
    )


def test_beta_dashboard_world_surface_prefers_world_feed_when_renderable():
    snapshots = _beta_dashboard_world_snapshots(
        {
            "session_id": "20260327T043932Z",
            "environment_state": "environment_ready",
            "world_stream_ready": True,
            "world_stream_renderable": True,
            "world_stream_transport_healthy": True,
            "world_stream_degraded": False,
            "world_stream_frame_age_s": 0.2,
            "live_paths": {"world_stream": "live/world_stream.jpg"},
            "operator_view_ready": True,
            "operator_view_url": "http://127.0.0.1:14500/",
            "operator_view_status": "ready",
            "operator_view_failure_class": "",
            "world_stream_failure_class": "",
            "recent_operator_events": [],
        }
    )

    snap = snapshots[0]

    assert snap["label"] == "World surface"
    assert snap["badgeText"] == "sim live"
    assert snap["worldDisplay"] == "block"
    assert snap["worldPlaceholderDisplay"] == "none"
    assert snap["openHidden"] is False
    assert snap["embedHidden"] is False
    assert snap["legacyHidden"] is True


def test_beta_dashboard_keeps_last_good_world_frame_during_degradation():
    snapshots = _beta_dashboard_world_snapshots(
        {
            "session_id": "20260327T043932Z",
            "environment_state": "environment_ready",
            "world_stream_ready": True,
            "world_stream_renderable": True,
            "world_stream_transport_healthy": True,
            "world_stream_degraded": False,
            "world_stream_frame_age_s": 0.2,
            "live_paths": {"world_stream": "live/world_stream.jpg"},
            "operator_view_ready": True,
            "operator_view_url": "http://127.0.0.1:14500/",
            "operator_view_status": "ready",
            "operator_view_failure_class": "",
            "world_stream_failure_class": "",
            "recent_operator_events": [],
        },
        {
            "session_id": "20260327T043932Z",
            "environment_state": "environment_ready",
            "world_stream_ready": False,
            "world_stream_renderable": False,
            "world_stream_transport_healthy": False,
            "world_stream_degraded": True,
            "world_stream_frame_age_s": 3.8,
            "live_paths": {"world_stream": "live/world_stream.jpg"},
            "operator_view_ready": True,
            "operator_view_url": "http://127.0.0.1:14500/",
            "operator_view_status": "ready",
            "operator_view_failure_class": "",
            "world_stream_failure_class": "world_stream_no_recent_frames",
            "recent_operator_events": [],
        },
    )

    healthy, degraded = snapshots

    assert healthy["worldDisplay"] == "block"
    assert degraded["worldDisplay"] == "block"
    assert degraded["badgeText"] == "stale"
    assert degraded["noteText"] == "Holding last good world frame while stream recovers..."
    assert degraded["worldPlaceholderDisplay"] == "none"


def test_beta_dashboard_waits_for_first_world_frame():
    snapshots = _beta_dashboard_world_snapshots(
        {
            "session_id": "20260327T043932Z",
            "environment_state": "environment_ready",
            "world_stream_ready": False,
            "world_stream_renderable": True,
            "world_stream_transport_healthy": False,
            "world_stream_degraded": True,
            "world_stream_frame_age_s": 0.0,
            "live_paths": {"world_stream": "live/world_stream.jpg"},
            "__defer_image_load": True,
            "operator_view_ready": True,
            "operator_view_url": "http://127.0.0.1:14500/",
            "operator_view_status": "ready",
            "operator_view_failure_class": "",
            "world_stream_failure_class": "",
            "recent_operator_events": [],
        }
    )

    snap = snapshots[0]

    assert snap["worldDisplay"] == "none"
    assert snap["worldPlaceholderDisplay"] == ""
    assert snap["worldPlaceholderText"] == "Waiting for first world frame..."
    assert snap["badgeText"] == "degraded"


def test_beta_dashboard_session_rollover_clears_stale_world_frame():
    snapshots = _beta_dashboard_world_snapshots(
        {
            "session_id": "20260327T043932Z",
            "environment_state": "environment_ready",
            "world_stream_ready": True,
            "world_stream_renderable": True,
            "world_stream_transport_healthy": True,
            "world_stream_degraded": False,
            "world_stream_frame_age_s": 0.2,
            "live_paths": {"world_stream": "live/world_stream.jpg"},
            "operator_view_ready": True,
            "operator_view_url": "http://127.0.0.1:14500/",
            "operator_view_status": "ready",
            "operator_view_failure_class": "",
            "world_stream_failure_class": "",
            "recent_operator_events": [],
        },
        {
            "session_id": "20260327T044500Z",
            "environment_state": "environment_ready",
            "world_stream_ready": False,
            "world_stream_renderable": False,
            "world_stream_transport_healthy": False,
            "world_stream_degraded": False,
            "world_stream_frame_age_s": None,
            "live_paths": {},
            "operator_view_ready": True,
            "operator_view_url": "http://127.0.0.1:14500/",
            "operator_view_status": "ready",
            "operator_view_failure_class": "",
            "world_stream_failure_class": "world_stream_no_recent_frames",
            "recent_operator_events": [],
        },
    )

    rollover = snapshots[1]

    assert rollover["worldDisplay"] == "none"
    assert rollover["worldPlaceholderText"] == "World feed unavailable for this session."
    assert rollover["badgeText"] == "unavailable"
    assert rollover["label"] == "World surface"


def test_find_free_port_skips_bound_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        occupied = sock.getsockname()[1]
        chosen = dashboard_service.find_free_port(occupied, occupied + 32)
        assert chosen != occupied


def test_list_dashboard_projects_filters_to_session_prefix(tmp_path, monkeypatch):
    controller = _make_controller(tmp_path)

    def _fake_run(*_args, **_kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout="\n".join(
                [
                    "chasecar_dashboard_olda",
                    "chasecar_local",
                    "schoology-prod",
                    "chasecar_dashboard_oldb",
                    "chasecar_dashboard_olda",
                    "",
                ]
            ),
        )

    monkeypatch.setattr(dashboard_service.subprocess, "run", _fake_run)
    assert controller._list_dashboard_projects() == ["chasecar_dashboard_olda", "chasecar_dashboard_oldb"]


def test_cleanup_stale_dashboard_projects_excludes_current(tmp_path):
    controller = _make_controller(tmp_path)
    removed: list[str] = []
    controller._list_dashboard_projects = lambda include_stopped=True: [
        "chasecar_dashboard_keepme",
        "chasecar_dashboard_olda",
        "chasecar_dashboard_oldb",
    ]
    controller._force_remove_project_resources = lambda project_name: removed.append(project_name)

    cleaned = controller._cleanup_stale_dashboard_projects(current_project="chasecar_dashboard_keepme")

    assert cleaned == ["chasecar_dashboard_olda", "chasecar_dashboard_oldb"]
    assert removed == cleaned


def test_cleanup_stale_dashboard_projects_can_leave_peer_projects_running(tmp_path):
    controller = _make_controller(tmp_path)
    controller.peer_project_cleanup = "none"
    removed: list[str] = []
    controller._list_dashboard_projects = lambda include_stopped=True: [
        "chasecar_dashboard_keepme",
        "chasecar_dashboard_peer",
    ]
    controller._force_remove_project_resources = lambda project_name: removed.append(project_name)

    cleaned = controller._cleanup_stale_dashboard_projects(current_project="chasecar_dashboard_keepme")

    assert cleaned == []
    assert removed == []


def test_base_env_uses_instance_runtime_files(tmp_path):
    controller = _make_controller(tmp_path)
    env = controller._base_env(session_id="20260412T120000Z", world_stream_port=8891, operator_view_port=14500)

    assert env["CHASECAR_VISIT_RUNTIME_PATH"].endswith("/runtime/visit_mission_runtime.json")
    assert env["CHASECAR_GATHER_RUNTIME_PATH"].endswith("/runtime/gather_mission_runtime.json")
    assert env["CHASECAR_INTENT_INBOX_PATH"].endswith("/runtime/intent_inbox.json")
    assert env["CHASECAR_INTENT_ACK_PATH"].endswith("/runtime/intent_ack.json")


def test_run_visit_mission_scenario_uses_host_visit_runtime_path(tmp_path, monkeypatch):
    controller = _make_controller(tmp_path)
    controller.state["dashboard_url"] = "http://127.0.0.1:8860/"
    controller._scenarios_dir = lambda: tmp_path / "scenarios"
    controller._current_validation_dir = lambda: tmp_path / "validation"
    controller._visit_mission_runtime_state = lambda: {}
    controller._scenario_env = lambda _scenario: {
        "CHASECAR_VISIT_RUNTIME_PATH": "/workspaces/chasecar/runtime/dashboard/visit_mission_runtime.json"
    }

    mission_root = tmp_path / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    mission_verdict_path = mission_root / "mission_verdict.json"
    _write_json(mission_verdict_path, {"pass": True})
    _write_json(mission_root / "summary.json", {"pass": True})
    _write_json(mission_root / "target_results.json", {"targets": []})

    captured: dict[str, object] = {}

    class _FakeProc:
        def __init__(self, cmd, stdout_handle) -> None:
            captured["cmd"] = list(cmd)
            stdout_handle.write(f"VISIT_MISSION_SUMMARY={mission_verdict_path}\n")
            stdout_handle.flush()
            self.returncode = 0

        def poll(self):
            return 0

    def _fake_popen(command, **kwargs):
        return _FakeProc(command, kwargs["stdout"])

    monkeypatch.setattr(dashboard_service.subprocess, "Popen", _fake_popen)

    result = controller._run_visit_mission_scenario(dashboard_service.SCENARIOS_BY_ID["visit_route_planning"])

    command = captured["cmd"]
    assert "--visit-runtime-json" in command
    path_index = command.index("--visit-runtime-json") + 1
    assert command[path_index] == str(controller.visit_mission_runtime_path)
    assert result["pass"] is True


def test_request_scenario_run_corral_queues_after_sim_reset(monkeypatch, tmp_path):
    controller = _make_controller(tmp_path)
    controller.state["environment_state"] = "environment_ready"
    controller.state["scenario_state"] = "ready"
    controller._refresh_control_plane_state = lambda force=False: None
    started: list[object] = []

    class _FakeThread:
        def __init__(self, target, name, daemon):
            self.target = target
            self.name = name
            self.daemon = daemon
            self._alive = False
            started.append(self)

        def start(self) -> None:
            self._alive = True

        def is_alive(self) -> bool:
            return self._alive

    monkeypatch.setattr(dashboard_service.threading, "Thread", _FakeThread)

    status, payload = controller.request_scenario_run("corral_single_ball_place")

    assert status == 202
    assert payload["accepted"] is True
    assert "queued after sim reset" in payload["message"]
    assert controller.pending_scenario_id == "corral_single_ball_place"
    assert started
    assert started[0].target == controller._reset_environment_worker


def test_robot_sdf_name_for_startup_defaults_to_baseline(tmp_path):
    controller = _make_controller(tmp_path)

    assert controller._robot_sdf_name_for_startup() == dashboard_service.BASELINE_ROBOT_SDF_NAME
    assert controller._world_file_for_startup() == dashboard_service.DEFAULT_WORLD_FILE
    assert controller._surface_profile_for_startup() == dashboard_service.DEFAULT_SURFACE_PROFILE


def test_robot_sdf_name_for_startup_uses_pending_corral_scenario(tmp_path):
    controller = _make_controller(tmp_path)
    controller.pending_scenario_id = "corral_single_ball_place"

    assert controller._robot_sdf_name_for_startup() == dashboard_service.CORRAL_ROBOT_SDF_NAME
    assert controller._world_file_for_startup() == dashboard_service.SHORT_TURF_WORLD_FILE
    assert controller._surface_profile_for_startup() == "short_turf"


def test_request_scenario_run_accepts_world_and_surface_overrides(monkeypatch, tmp_path):
    controller = _make_controller(tmp_path)
    controller.state["environment_state"] = "environment_ready"
    controller.state["scenario_state"] = "ready"
    controller._refresh_control_plane_state = lambda force=False: None
    started: list[object] = []

    class _FakeThread:
        def __init__(self, target, name, daemon):
            self.target = target
            self.name = name
            self.daemon = daemon
            started.append(self)

        def start(self) -> None:
            return None

        def is_alive(self) -> bool:
            return False

    monkeypatch.setattr(dashboard_service.threading, "Thread", _FakeThread)

    status, payload = controller.request_scenario_run(
        "corral_single_ball_place",
        {"world_file": "yolo_test_world_v6_clean_uat_short_grass.world", "surface_profile": "short_grass"},
    )

    assert status == 202
    assert payload["world_file"] == "yolo_test_world_v6_clean_uat_short_grass.world"
    assert payload["surface_profile"] == "short_grass"
    assert controller.pending_scenario_overrides["world_file"] == "yolo_test_world_v6_clean_uat_short_grass.world"
    assert controller.pending_scenario_overrides["surface_profile"] == "short_grass"
    assert started


def test_run_gather_mission_scenario_uses_host_runtime_paths(tmp_path, monkeypatch):
    controller = _make_controller(tmp_path)
    controller.state["dashboard_url"] = "http://127.0.0.1:8860/"
    controller._scenarios_dir = lambda: tmp_path / "scenarios"
    controller._current_validation_dir = lambda: tmp_path / "validation"
    controller._visit_mission_runtime_state = lambda: {
        "proof_state": "completed",
        "visited_targets": ["ball_1"],
        "last_visit_result": {"target_id": "ball_1", "pass": True},
    }
    controller._gather_mission_runtime_state = lambda: {
        "mission_phase": "completed",
        "mission_status": "completed",
        "gather_phase": "completed",
        "surface_profile": "short_turf",
        "placed_targets": ["ball_1"],
        "capture_loss_count": 0,
        "route_order": ["ball_1"],
        "artifact_dir": str(tmp_path / "mission"),
    }
    controller._scenario_env = lambda _scenario: {
        "CHASECAR_VISIT_RUNTIME_PATH": "/workspaces/chasecar/runtime/dashboard/visit_mission_runtime.json",
        "CHASECAR_GATHER_RUNTIME_PATH": "/workspaces/chasecar/runtime/dashboard/gather_mission_runtime.json",
        "WORLD_FILE": "yolo_test_world_v6_clean_uat_short_turf.world",
        "CHASECAR_SURFACE_PROFILE": "short_turf",
    }

    mission_root = tmp_path / "mission"
    mission_root.mkdir(parents=True, exist_ok=True)
    mission_verdict_path = mission_root / "mission_verdict.json"
    _write_json(mission_verdict_path, {"pass": True, "type": "gather_mission"})
    _write_json(mission_root / "summary.json", {"pass": True})
    _write_json(mission_root / "target_results.json", {"targets": []})

    captured: dict[str, object] = {}

    class _FakeProc:
        def __init__(self, cmd, stdout_handle) -> None:
            captured["cmd"] = list(cmd)
            stdout_handle.write(f"GATHER_MISSION_SUMMARY={mission_verdict_path}\n")
            stdout_handle.flush()
            self.returncode = 0

        def poll(self):
            return 0

    def _fake_popen(command, **kwargs):
        return _FakeProc(command, kwargs["stdout"])

    monkeypatch.setattr(dashboard_service.subprocess, "Popen", _fake_popen)

    result = controller._run_gather_mission_scenario(dashboard_service.SCENARIOS_BY_ID["corral_single_ball_place"])

    command = captured["cmd"]
    assert "--world-file" in command
    assert "--surface-profile" in command
    assert "--visit-runtime-json" in command
    assert "--gather-runtime-json" in command
    world_index = command.index("--world-file") + 1
    surface_index = command.index("--surface-profile") + 1
    visit_index = command.index("--visit-runtime-json") + 1
    gather_index = command.index("--gather-runtime-json") + 1
    assert command[world_index] == "yolo_test_world_v6_clean_uat_short_turf.world"
    assert command[surface_index] == "short_turf"
    assert command[visit_index] == str(controller.visit_mission_runtime_path)
    assert command[gather_index] == str(controller.gather_mission_runtime_path)
    assert result["pass"] is True
    assert result["artifacts"]["gather_mission"] == str(mission_root)
    assert result["surface_profile"] == "short_turf"


def test_get_state_merges_gather_runtime_fields(tmp_path):
    controller = _make_controller(tmp_path)
    controller.state["active_scenario"] = "corral_single_ball_place"
    controller._visit_mission_runtime_state = lambda: {
        "proof_state": "placing",
        "mission_phase": "place",
        "mission_status": "running",
        "current_target_id": "ball_1",
        "visit_index": 1,
        "visited_targets": [],
        "remaining_targets": [],
        "last_visit_result": {},
        "latest_feedback": "Placing Ball 1 into the zone.",
        "recent_operator_events": [
            {
                "timestamp_utc": "2026-04-12T23:00:00Z",
                "message": "Ball 1: visit attempt 1.",
                "category": "mission",
                "source": "gather_mission",
            }
        ],
    }
    controller._gather_mission_runtime_state = lambda: {
        "mission_phase": "place",
        "mission_status": "running",
        "gather_phase": "place",
        "surface_profile": "short_turf",
        "current_target_id": "ball_1",
        "visit_index": 1,
        "placed_targets": [],
        "remaining_targets": [],
        "route_order": ["ball_1"],
        "capture_state": {"captured": True},
        "capture_loss_count": 0,
        "zone_pose": {"x": 2.4, "y": 0.0, "radius_m": 0.2},
        "zone_score": {"inside_zone": False},
        "latest_feedback": "Placing Ball 1 into the zone.",
        "artifact_dir": str(tmp_path / "mission"),
        "mission_verdict": {"type": "gather_mission"},
        "recent_operator_events": [
            {
                "timestamp_utc": "2026-04-12T23:00:00Z",
                "message": "Ball 1: visit attempt 1.",
                "category": "mission",
                "source": "gather_mission",
            }
        ],
    }

    state = controller.get_state()

    assert state["proof_state"] == "placing"
    assert state["mission_phase"] == "place"
    assert state["gather_phase"] == "place"
    assert state["capture_state"]["captured"] is True
    assert state["zone_pose"]["radius_m"] == 0.2
    assert state["route_order"] == ["ball_1"]
    assert state["surface_profile"] == "short_turf"
    assert state["proof_artifact_dir"] == str(tmp_path / "mission")
    assert state["latest_proof_feedback"] == "Placing Ball 1 into the zone."
    assert [item["message"] for item in state["recent_operator_events"]] == ["Ball 1: visit attempt 1."]


def test_wait_for_world_stream_ready_accepts_fresh_stream(tmp_path, monkeypatch):
    controller = _make_controller(tmp_path)
    _write_world_state(
        tmp_path,
        {
            "session_id": controller.state["session_id"],
            "partition": controller.state["session_id"],
            "world_surface": "streamed_sim",
            "world_stream_url": controller.state["world_stream_url"],
            "world_stream_ready": True,
            "world_stream_nonblank": True,
            "world_stream_interactive": False,
            "same_session_partition": True,
            "viewer_process_healthy": True,
            "viewer_client_mode": "gazebo_sensor_camera",
            "camera_profile": "robot_follow",
            "render_backend": "gazebo_sensor_camera:ogre2",
            "software_render_only": False,
            "display_server": "none",
            "gpu_available": True,
            "scene_content_ok": True,
            "robot_visible_ok": True,
            "target_visible_ok": True,
            "failure_class": "",
            "image_topic": "/observer_world/image_raw",
            "frame_count": 84,
            "elapsed_s": 17.0,
            "frame_coverage_ratio": 0.91,
            "nonblank_ratio": 0.98,
            "scene_content_ratio": 0.96,
            "robot_visible_ratio": 0.89,
            "target_visible_ratio": 0.74,
            "robot_max_area_px": 200.0,
            "target_max_area_px": 110.0,
            "latest_robot_area_px": 190.0,
            "latest_target_area_px": 105.0,
            "latest_frame_error": "",
            "truth_target_seen": True,
            "screenshot_path": str(tmp_path / "visual" / "live" / "world_stream.jpg"),
            "video_path": str(tmp_path / "visual" / "world_stream.mp4"),
            "latest_frame_wall_s": 123.4,
            "latest_frame_utc": "2026-03-18T12:00:05Z",
            "latest_frame_age_s": 0.3,
            "frames_stale": False,
            "healthy_stale_seconds": 2.5,
        },
    )

    monkeypatch.setattr(dashboard_service.time, "sleep", lambda *_args, **_kwargs: None)
    assert controller._wait_for_world_stream_ready(0.01) is True


def test_wait_for_world_stream_ready_accepts_fresh_renderable_stream_before_strict_promotion(tmp_path, monkeypatch):
    controller = _make_controller(tmp_path)
    _write_world_state(
        tmp_path,
        {
            "session_id": controller.state["session_id"],
            "partition": controller.state["session_id"],
            "world_surface": "streamed_sim",
            "world_stream_url": "",
            "world_stream_ready": False,
            "world_stream_renderable": True,
            "world_stream_transport_healthy": False,
            "world_stream_degraded": True,
            "world_stream_nonblank": True,
            "world_stream_interactive": False,
            "same_session_partition": True,
            "viewer_process_healthy": True,
            "viewer_client_mode": "gazebo_sensor_camera",
            "camera_profile": "robot_follow",
            "render_backend": "gazebo_sensor_camera:ogre2",
            "software_render_only": False,
            "display_server": "none",
            "gpu_available": True,
            "scene_content_ok": False,
            "robot_visible_ok": False,
            "target_visible_ok": True,
            "failure_class": "world_stream_no_recent_frames",
            "image_topic": "/observer_world/image_raw",
            "frame_count": 1,
            "received_frame_count": 1,
            "rendered_frame_count": 1,
            "elapsed_s": 1.0,
            "frame_coverage_ratio": 0.0,
            "nonblank_ratio": 1.0,
            "scene_content_ratio": 1.0,
            "robot_visible_ratio": 1.0,
            "target_visible_ratio": 0.0,
            "robot_max_area_px": 812.0,
            "target_max_area_px": 0.0,
            "latest_robot_area_px": 812.0,
            "latest_target_area_px": 0.0,
            "latest_frame_error": "",
            "truth_target_seen": False,
            "screenshot_path": str(tmp_path / "visual" / "live" / "world_stream.jpg"),
            "video_path": str(tmp_path / "visual" / "world_stream.mp4"),
            "latest_frame_wall_s": 123.4,
            "latest_frame_utc": "2026-04-02T22:28:10Z",
            "latest_frame_age_s": 0.6,
            "frames_stale": False,
            "healthy_stale_seconds": 2.5,
        },
    )

    monkeypatch.setattr(dashboard_service.time, "sleep", lambda *_args, **_kwargs: None)
    assert controller._wait_for_world_stream_ready(0.01) is True


def test_wait_for_world_stream_ready_rejects_stale_stream(tmp_path, monkeypatch):
    controller = _make_controller(tmp_path)
    _write_world_state(
        tmp_path,
        {
            "session_id": controller.state["session_id"],
            "partition": controller.state["session_id"],
            "world_surface": "streamed_sim",
            "world_stream_url": controller.state["world_stream_url"],
            "world_stream_ready": True,
            "world_stream_nonblank": True,
            "world_stream_interactive": False,
            "same_session_partition": True,
            "viewer_process_healthy": True,
            "viewer_client_mode": "gazebo_sensor_camera",
            "camera_profile": "robot_follow",
            "render_backend": "gazebo_sensor_camera:ogre2",
            "software_render_only": False,
            "display_server": "none",
            "gpu_available": True,
            "scene_content_ok": True,
            "robot_visible_ok": True,
            "target_visible_ok": True,
            "failure_class": "world_stream_stale",
            "image_topic": "/observer_world/image_raw",
            "frame_count": 84,
            "elapsed_s": 17.0,
            "frame_coverage_ratio": 0.91,
            "nonblank_ratio": 0.98,
            "scene_content_ratio": 0.96,
            "robot_visible_ratio": 0.89,
            "target_visible_ratio": 0.74,
            "robot_max_area_px": 200.0,
            "target_max_area_px": 110.0,
            "latest_robot_area_px": 190.0,
            "latest_target_area_px": 105.0,
            "latest_frame_error": "",
            "truth_target_seen": True,
            "screenshot_path": str(tmp_path / "visual" / "live" / "world_stream.jpg"),
            "video_path": str(tmp_path / "visual" / "world_stream.mp4"),
            "latest_frame_wall_s": 123.4,
            "latest_frame_utc": "2026-03-18T12:00:05Z",
            "latest_frame_age_s": 3.7,
            "frames_stale": True,
            "healthy_stale_seconds": 2.5,
        },
    )

    monkeypatch.setattr(dashboard_service.time, "sleep", lambda *_args, **_kwargs: None)
    assert controller._wait_for_world_stream_ready(0.01) is False


def test_start_environment_worker_retries_once_after_host_port_bind_failure(tmp_path, monkeypatch):
    controller = _make_controller(tmp_path)
    controller._clear_llm_proof_runtime_state = lambda: None
    controller._clear_visit_mission_runtime_state = lambda: None
    controller._write_operator_status = lambda **_kwargs: None
    controller._write_lock_file = lambda: None
    controller._remove_lock_file = lambda: None
    controller._teardown_environment = lambda env=None: None
    controller._refresh_session_container_ids = lambda project_name: (
        setattr(controller, "sim_gate_container_id", "sim-gate"),
        setattr(controller, "gate_stack_container_id", "gate-stack"),
        setattr(controller, "world_viewer_container_id", "world-viewer"),
        setattr(controller, "operator_view_container_id", "operator-view"),
    )
    controller._run_container_helper = lambda *_args, **_kwargs: {"output": "ok"}
    controller._wait_for_truth_ready = lambda timeout_s: True
    controller._wait_for_world_stream_ready = lambda timeout_s: True
    controller._wait_for_operator_view_ready = lambda timeout_s: True
    controller._wait_for_visual_ready = lambda timeout_s: True
    controller._wait_for_required_gate_services = lambda *_args, **_kwargs: {
        "sim-gate": {"service": "sim-gate", "status": "running", "container_id": "sim-gate-1"},
        "world-viewer": {"service": "world-viewer", "status": "running", "container_id": "world-viewer-1"},
        "gate-stack": {"service": "gate-stack", "status": "running", "container_id": "gate-stack-1"},
        "operator-view": {"service": "operator-view", "status": "running", "container_id": "operator-view-1"},
    }

    cleanup_calls: list[str] = []
    cleanup_batches = iter([["chasecar_dashboard_stale0"], ["chasecar_dashboard_stale1"]])
    controller._cleanup_stale_dashboard_projects = lambda current_project="": cleanup_calls.append(current_project) or list(next(cleanup_batches))

    removed_projects: list[str] = []
    controller._force_remove_project_resources = lambda project_name: removed_projects.append(project_name)

    ports = iter([8891, 14500, 8892, 14501])
    monkeypatch.setattr(dashboard_service, "find_free_port", lambda start, end: next(ports))
    monkeypatch.setattr(dashboard_service, "make_session_id", lambda: "20260320T200000Z")

    events: list[tuple[str, str]] = []
    controller._record_operator_event = lambda message, category="info", source="dashboard": events.append((message, category))

    compose_calls: list[int] = []

    def _run_environment_compose_up(project_name, env):
        compose_calls.append(int(env["WORLD_STREAM_PORT"]))
        if len(compose_calls) == 1:
            return 1, "Bind for 127.0.0.1:8891 failed: port is already allocated"
        return 0, "ok"

    controller._run_environment_compose_up = _run_environment_compose_up

    controller._start_environment_worker()

    assert compose_calls == [8891, 8892]
    assert removed_projects == ["chasecar_dashboard_20260320t200000z"]
    assert controller.state["environment_state"] == "environment_ready"
    assert controller.state["world_stream_port"] == 8892
    assert controller.state["operator_view_port"] == 14501
    assert controller.state["operator_view_ready"] is True
    assert controller.state["startup_retry_count"] == 1
    assert controller.state["startup_cleanup_count"] == 2
    assert controller.state["startup_last_cleanup_projects"] == [
        "chasecar_dashboard_stale0",
        "chasecar_dashboard_stale1",
    ]
    messages = [message for message, _category in events]
    assert "Cleaned stale dashboard projects before startup: chasecar_dashboard_stale0." in messages
    assert "Cleaned stale dashboard projects after port bind failure: chasecar_dashboard_stale1." in messages
    assert "Retrying startup after host port 8891 bind failure." in messages


def test_world_stream_restart_ready_uses_live_world_state_not_snapshot(tmp_path):
    controller = _make_controller(tmp_path)
    _write_world_state(
        tmp_path,
        {
            "session_id": controller.state["session_id"],
            "partition": controller.state["session_id"],
            "world_stream_ready": False,
            "same_session_partition": True,
            "frames_stale": True,
        },
    )

    assert "world_stream_frames_stale" not in controller.state
    assert controller._world_stream_restart_ready() is True


def test_run_environment_compose_up_uses_no_build_when_reusing_local_images(tmp_path):
    controller = _make_controller(tmp_path)
    controller.control_mode = "docker_socket"
    controller.build_on_next_start = False

    down_calls: list[tuple[str, ...]] = []
    popen_calls: list[tuple[str, ...]] = []

    controller._run_docker_compose = lambda project_name, *args, env=None: down_calls.append((project_name, *args))

    class _Proc:
        returncode = 0

        def communicate(self):
            return ("ok", "")

    controller._popen_docker_compose = lambda project_name, *args, env=None: popen_calls.append((project_name, *args)) or _Proc()

    rc, output = controller._run_environment_compose_up("chasecar_dashboard_test", {"WORLD_STREAM_PORT": "8891"})

    assert rc == 0
    assert output == "ok"
    assert down_calls == [("chasecar_dashboard_test", "down", "--remove-orphans")]
    assert popen_calls == [
        (
            "chasecar_dashboard_test",
            "up",
            "-d",
            "--no-build",
            "sim-gate",
            "world-viewer",
            "gate-stack",
            "dashboard-utility",
            "operator-view",
        )
    ]


def test_run_environment_compose_up_headless_worker_skips_visual_services(tmp_path):
    controller = _make_controller(tmp_path)
    controller.control_mode = "docker_socket"
    controller.build_on_next_start = False
    controller.headless_worker_mode = True

    popen_calls: list[tuple[str, ...]] = []
    controller._run_docker_compose = lambda *_args, **_kwargs: None

    class _Proc:
        returncode = 0

        def communicate(self):
            return ("ok", "")

    controller._popen_docker_compose = lambda project_name, *args, env=None: popen_calls.append((project_name, *args)) or _Proc()

    rc, output = controller._run_environment_compose_up("chasecar_dashboard_test", {"WORLD_STREAM_PORT": "8891"})

    assert rc == 0
    assert output == "ok"
    assert popen_calls == [
        (
            "chasecar_dashboard_test",
            "up",
            "-d",
            "--no-build",
            "sim-gate",
            "gate-stack",
        )
    ]


def test_run_environment_compose_up_uses_build_when_requested(tmp_path):
    controller = _make_controller(tmp_path)
    controller.control_mode = "docker_socket"
    controller.build_on_next_start = True
    controller._docker_image_exists = lambda _image_ref: False

    popen_calls: list[tuple[str, ...]] = []
    controller._run_docker_compose = lambda *_args, **_kwargs: None

    class _Proc:
        returncode = 0

        def communicate(self):
            return ("ok", "")

    controller._popen_docker_compose = lambda project_name, *args, env=None: popen_calls.append((project_name, *args)) or _Proc()

    rc, output = controller._run_environment_compose_up("chasecar_dashboard_test", {"WORLD_STREAM_PORT": "8891"})

    assert rc == 0
    assert output == "ok"
    assert popen_calls == [
        (
            "chasecar_dashboard_test",
            "up",
            "-d",
            "--build",
            "sim-gate",
            "world-viewer",
            "gate-stack",
            "dashboard-utility",
            "operator-view",
        )
    ]


def test_run_environment_compose_up_skips_build_when_local_gate_images_exist(tmp_path):
    controller = _make_controller(tmp_path)
    controller.control_mode = "docker_socket"
    controller.build_on_next_start = True
    controller._docker_image_exists = lambda _image_ref: True

    popen_calls: list[tuple[str, ...]] = []
    controller._run_docker_compose = lambda *_args, **_kwargs: None

    class _Proc:
        returncode = 0

        def communicate(self):
            return ("ok", "")

    controller._popen_docker_compose = lambda project_name, *args, env=None: popen_calls.append((project_name, *args)) or _Proc()

    rc, output = controller._run_environment_compose_up("chasecar_dashboard_test", {"WORLD_STREAM_PORT": "8891"})

    assert rc == 0
    assert output == "ok"
    assert popen_calls == [
        (
            "chasecar_dashboard_test",
            "up",
            "-d",
            "--no-build",
            "sim-gate",
            "world-viewer",
            "gate-stack",
            "dashboard-utility",
            "operator-view",
        )
    ]


def test_restart_world_stream_controller_recovers_and_records_event(tmp_path, monkeypatch):
    controller = _make_controller(tmp_path)
    _write_world_state(
        tmp_path,
        {
            "session_id": controller.state["session_id"],
            "partition": controller.state["session_id"],
            "world_stream_ready": False,
            "same_session_partition": True,
            "frames_stale": True,
        },
    )

    events: list[tuple[str, str]] = []
    helper_calls: list[tuple[str, str, str]] = []

    controller._record_operator_event = lambda message, category="info", source="dashboard": events.append((message, category))
    controller._run_container_helper = lambda container_id, script, prefix: helper_calls.append((container_id, script, prefix)) or {"output": "ok"}
    controller._wait_for_world_stream_ready = lambda timeout_s: True

    monotonic_values = iter([100.0, 100.0])
    monkeypatch.setattr(dashboard_service.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(dashboard_service, "utc_now", lambda: "2026-03-18T12:05:00Z")

    assert controller._restart_world_stream_controller() is True
    assert helper_calls
    assert helper_calls[0][0] == "world-viewer"
    assert "world_stream_controller.py" in helper_calls[0][1]
    assert controller.state["world_stream_recovery_state"] == "healthy"
    assert controller.state["world_stream_restart_attempts"] == 1
    assert controller.state["world_stream_last_restart_utc"] == "2026-03-18T12:05:00Z"
    assert controller.state["world_stream_restart_in_progress"] is False
    assert controller._world_stream_stale_since_monotonic == 0.0
    assert [message for message, _category in events] == [
        "World surface stale; restarting world stream controller.",
        "World surface recovered after stale stream.",
    ]


def _make_world_stream_observer(tmp_path: Path) -> world_stream_controller.WorldStreamObserver:
    args = SimpleNamespace(
        session_id="20260318T000000Z",
        output_dir=str(tmp_path / "visual"),
        world_name="yolo_test_world",
        image_topic="/observer_world/image_raw",
        truth_state_path="",
        public_url="",
        camera_profile="robot_follow",
        duration_s=10.0,
        fps=5.0,
        require_target_visible=False,
        robot_min_area_px=140.0,
        target_min_area_px=90.0,
        scene_std_min=12.0,
        scene_sat_min=30.0,
        healthy_stale_seconds=2.5,
    )
    observer = world_stream_controller.WorldStreamObserver.__new__(world_stream_controller.WorldStreamObserver)
    observer.args = args
    observer.latest_frame = None
    observer.last_frame_wall_s = 0.0
    observer.image_error = ""
    observer.received_frame_count = 0
    observer.rendered_frame_count = 0
    observer.nonblank_count = 0
    observer.scene_content_count = 0
    observer.robot_visible_count = 0
    observer.target_visible_count = 0
    observer.robot_max_area = 0.0
    observer.target_max_area = 0.0
    observer.started_monotonic_s = 0.0
    observer.latest_received_frame_seq = 0
    observer.last_rendered_frame_seq = 0
    observer.recent_frame_wall_times = deque()
    observer.output_dir = tmp_path / "visual"
    observer.output_dir.mkdir(parents=True, exist_ok=True)
    observer.live_dir = observer.output_dir / "live"
    observer.live_dir.mkdir(parents=True, exist_ok=True)
    observer.logs_dir = observer.output_dir / "logs"
    observer.logs_dir.mkdir(parents=True, exist_ok=True)
    observer.screenshot_path = observer.live_dir / "world_stream.jpg"
    observer.video_path = observer.output_dir / "world_stream.mp4"
    observer.state_path = observer.output_dir / "world_stream_state.json"
    observer.summary_path = observer.output_dir / "world_stream_summary.json"
    observer.placeholder = SimpleNamespace(copy=lambda: observer.placeholder)
    observer.writer = SimpleNamespace(write=lambda _frame: None, release=lambda: None)
    observer.writer_size = None
    observer._ensure_writer = lambda _frame: None
    return observer


class _FakeFrame:
    def copy(self) -> "_FakeFrame":
        return self


def _fake_imwrite_factory(tmp_path: Path):
    def _fake_imwrite(path: str, *_args, **_kwargs) -> bool:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"frame")
        return True

    return _fake_imwrite


def test_world_stream_observer_counts_only_fresh_callbacks(tmp_path, monkeypatch):
    observer = _make_world_stream_observer(tmp_path)
    frame = _FakeFrame()
    wall = {"value": 100.0}
    mono = {"value": 0.6}

    monkeypatch.setattr(world_stream_controller, "image_msg_to_bgr", lambda _msg: frame)
    monkeypatch.setattr(world_stream_controller, "image_is_nonblank", lambda _frame: True)
    monkeypatch.setattr(world_stream_controller, "scene_has_content", lambda _frame, *_args: True)
    monkeypatch.setattr(world_stream_controller, "robot_blue_area", lambda _frame: 180.0)
    monkeypatch.setattr(world_stream_controller, "target_red_area", lambda _frame: 100.0)
    monkeypatch.setattr(world_stream_controller.cv2, "imwrite", _fake_imwrite_factory(tmp_path))
    monkeypatch.setattr(world_stream_controller.time, "time", lambda: wall["value"])
    monkeypatch.setattr(world_stream_controller.time, "monotonic", lambda: mono["value"])
    monkeypatch.setenv("GZ_PARTITION", observer.args.session_id)

    for i in range(3):
        wall["value"] = 100.0 + (i * 0.1)
        observer._on_image(SimpleNamespace())
        state = observer.update()
        assert state["frame_count"] == i + 1
        assert state["received_frame_count"] == i + 1
        assert state["rendered_frame_count"] == i + 1
        assert state["world_stream_renderable"] is True
        if i < 2:
            assert state["world_stream_ready"] is False
            assert state["world_stream_transport_healthy"] is False
            assert state["world_stream_degraded"] is True
        else:
            assert state["world_stream_ready"] is True
            assert state["world_stream_transport_healthy"] is True
            assert state["world_stream_degraded"] is False

    state2 = observer.update()
    assert state2["frame_count"] == 3
    assert state2["received_frame_count"] == 3
    assert state2["rendered_frame_count"] == 3
    assert state2["world_stream_ready"] is True
    assert state2["world_stream_renderable"] is True
    assert state2["world_stream_transport_healthy"] is True

    wall["value"] = 104.3
    state3 = observer.update()
    assert state3["frame_count"] == 3
    assert state3["received_frame_count"] == 3
    assert state3["rendered_frame_count"] == 3
    assert state3["frames_stale"] is True
    assert state3["world_stream_ready"] is False
    assert state3["world_stream_renderable"] is True
    assert state3["world_stream_transport_healthy"] is False
    assert state3["world_stream_degraded"] is True
    assert state3["failure_class"] == "world_stream_receive_rate_low"


def test_world_stream_observer_marks_rendered_and_received_separately(tmp_path, monkeypatch):
    observer = _make_world_stream_observer(tmp_path)
    frame = _FakeFrame()
    wall = {"value": 100.0}
    mono = {"value": 0.6}

    monkeypatch.setattr(world_stream_controller, "image_msg_to_bgr", lambda _msg: frame)
    monkeypatch.setattr(world_stream_controller, "image_is_nonblank", lambda _frame: True)
    monkeypatch.setattr(world_stream_controller, "scene_has_content", lambda _frame, *_args: True)
    monkeypatch.setattr(world_stream_controller, "robot_blue_area", lambda _frame: 180.0)
    monkeypatch.setattr(world_stream_controller, "target_red_area", lambda _frame: 100.0)
    monkeypatch.setattr(world_stream_controller.cv2, "imwrite", _fake_imwrite_factory(tmp_path))
    monkeypatch.setattr(world_stream_controller.time, "time", lambda: wall["value"])
    monkeypatch.setattr(world_stream_controller.time, "monotonic", lambda: mono["value"])
    monkeypatch.setenv("GZ_PARTITION", observer.args.session_id)

    for i in range(3):
        wall["value"] = 100.0 + (i * 0.1)
        observer._on_image(SimpleNamespace())
        observer.update()

    observer.update()

    assert observer.received_frame_count == 3
    assert observer.rendered_frame_count == 3
    assert observer.state_path.exists()
    state = json.loads(observer.state_path.read_text(encoding="utf-8"))
    assert state["received_frame_count"] == 3
    assert state["rendered_frame_count"] == 3
    assert state["frame_count"] == 3


def test_world_stream_observer_marks_stale_after_any_received_frame(tmp_path, monkeypatch):
    observer = _make_world_stream_observer(tmp_path)
    frame = _FakeFrame()
    wall = {"value": 100.0}
    mono = {"value": 0.1}

    monkeypatch.setattr(world_stream_controller, "image_msg_to_bgr", lambda _msg: frame)
    monkeypatch.setattr(world_stream_controller, "image_is_nonblank", lambda _frame: True)
    monkeypatch.setattr(world_stream_controller, "scene_has_content", lambda _frame, *_args: True)
    monkeypatch.setattr(world_stream_controller, "robot_blue_area", lambda _frame: 180.0)
    monkeypatch.setattr(world_stream_controller, "target_red_area", lambda _frame: 0.0)
    monkeypatch.setattr(world_stream_controller.cv2, "imwrite", _fake_imwrite_factory(tmp_path))
    monkeypatch.setattr(world_stream_controller.time, "time", lambda: wall["value"])
    monkeypatch.setattr(world_stream_controller.time, "monotonic", lambda: mono["value"])
    monkeypatch.setenv("GZ_PARTITION", observer.args.session_id)

    observer._on_image(SimpleNamespace())
    first = observer.update()
    assert first["frames_stale"] is False
    assert first["world_stream_renderable"] is True
    assert first["world_stream_transport_healthy"] is False
    assert first["failure_class"] == "world_stream_receive_rate_low"

    wall["value"] = 103.5
    stale = observer.update()
    assert stale["frames_stale"] is True
    assert stale["world_stream_renderable"] is True
    assert stale["world_stream_degraded"] is True
    assert stale["failure_class"] == "world_stream_receive_rate_low"


def test_world_stream_observer_renderability_expires_after_grace_window(tmp_path, monkeypatch):
    observer = _make_world_stream_observer(tmp_path)
    frame = _FakeFrame()
    wall = {"value": 100.0}
    mono = {"value": 0.6}

    monkeypatch.setattr(world_stream_controller, "image_msg_to_bgr", lambda _msg: frame)
    monkeypatch.setattr(world_stream_controller, "image_is_nonblank", lambda _frame: True)
    monkeypatch.setattr(world_stream_controller, "scene_has_content", lambda _frame, *_args: True)
    monkeypatch.setattr(world_stream_controller, "robot_blue_area", lambda _frame: 180.0)
    monkeypatch.setattr(world_stream_controller, "target_red_area", lambda _frame: 100.0)
    monkeypatch.setattr(world_stream_controller.cv2, "imwrite", _fake_imwrite_factory(tmp_path))
    monkeypatch.setattr(world_stream_controller.time, "time", lambda: wall["value"])
    monkeypatch.setattr(world_stream_controller.time, "monotonic", lambda: mono["value"])
    monkeypatch.setenv("GZ_PARTITION", observer.args.session_id)

    for i in range(3):
        wall["value"] = 100.0 + (i * 0.1)
        observer._on_image(SimpleNamespace())
        observer.update()

    wall["value"] = 111.0
    expired = observer.update()

    assert expired["world_stream_ready"] is False
    assert expired["world_stream_renderable"] is False
    assert expired["world_stream_transport_healthy"] is False
    assert expired["world_stream_degraded"] is False
    assert expired["failure_class"] == "world_stream_no_recent_frames"
