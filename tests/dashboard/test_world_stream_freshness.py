from __future__ import annotations

import json
import socket
import sys
import threading
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
        node_mod = ModuleType("rclpy.node")

        class _Node:
            def __init__(self, *_args, **_kwargs) -> None:
                return None

            def create_subscription(self, *_args, **_kwargs):
                return None

            def destroy_node(self) -> None:
                return None

        node_mod.Node = _Node
        qos_mod = ModuleType("rclpy.qos")

        class _Preset:
            SENSOR_DATA = SimpleNamespace(value=None)

        qos_mod.QoSPresetProfiles = _Preset
        sys.modules["rclpy"] = rclpy_stub
        sys.modules["rclpy.node"] = node_mod
        sys.modules["rclpy.qos"] = qos_mod

    if "sensor_msgs" not in sys.modules:
        sensor_msgs_mod = ModuleType("sensor_msgs")
        msg_mod = ModuleType("sensor_msgs.msg")

        class _Image:
            pass

        msg_mod.Image = _Image
        sensor_msgs_mod.msg = msg_mod
        sys.modules["sensor_msgs"] = sensor_msgs_mod
        sys.modules["sensor_msgs.msg"] = msg_mod


try:
    import world_stream_controller  # noqa: E402
except ModuleNotFoundError:
    _install_world_stream_stubs()
    import world_stream_controller  # noqa: E402


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _make_controller(tmp_path: Path) -> dashboard_service.DashboardController:
    controller = dashboard_service.DashboardController.__new__(dashboard_service.DashboardController)
    controller.host = "127.0.0.1"
    controller.port = 8860
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
    controller.sim_gate_container_id = "sim-gate"
    controller.world_viewer_container_id = "world-viewer"
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
        "latest_operator_event": "",
        "recent_operator_events": [],
        "world_stream_url": "http://127.0.0.1:8891/vnc.html?autoconnect=1&resize=scale&path=websockify",
        "world_stream_port": 8891,
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
    return controller


def _write_world_state(tmp_path: Path, payload: dict[str, object]) -> Path:
    visual_dir = tmp_path / "visual"
    visual_dir.mkdir(parents=True, exist_ok=True)
    _write_json(visual_dir / "state.json", {"raw_frame_count": 0, "debug_frame_count": 0, "telemetry_frame_count": 0})
    _write_json(visual_dir / "world_stream_state.json", payload)
    return visual_dir


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
            "image_topic": "/observer/image_raw",
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
            "image_topic": "/observer/image_raw",
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
            "image_topic": "/observer/image_raw",
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
    )
    controller._run_container_helper = lambda *_args, **_kwargs: {"output": "ok"}
    controller._wait_for_truth_ready = lambda timeout_s: True
    controller._wait_for_world_stream_ready = lambda timeout_s: True
    controller._wait_for_visual_ready = lambda timeout_s: True

    cleanup_calls: list[str] = []
    cleanup_batches = iter([["chasecar_dashboard_stale0"], ["chasecar_dashboard_stale1"]])
    controller._cleanup_stale_dashboard_projects = lambda current_project="": cleanup_calls.append(current_project) or list(next(cleanup_batches))

    removed_projects: list[str] = []
    controller._force_remove_project_resources = lambda project_name: removed_projects.append(project_name)

    ports = iter([8891, 8892])
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
    assert controller.state["startup_retry_count"] == 1
    assert controller.state["startup_cleanup_count"] == 2
    assert controller.state["startup_last_cleanup_projects"] == [
        "chasecar_dashboard_stale0",
        "chasecar_dashboard_stale1",
    ]
    messages = [message for message, _category in events]
    assert "Cleaned stale dashboard projects before startup: chasecar_dashboard_stale0." in messages
    assert "Cleaned stale dashboard projects after port bind failure: chasecar_dashboard_stale1." in messages
    assert "Retrying startup after world-view port 8891 bind failure." in messages


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
        image_topic="/observer/image_raw",
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
    monkeypatch.setattr(world_stream_controller.cv2, "imwrite", lambda *_args, **_kwargs: True)
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
        if i < 2:
            assert state["world_stream_ready"] is False
        else:
            assert state["world_stream_ready"] is True

    state2 = observer.update()
    assert state2["frame_count"] == 3
    assert state2["received_frame_count"] == 3
    assert state2["rendered_frame_count"] == 3
    assert state2["world_stream_ready"] is True

    wall["value"] = 103.1
    state3 = observer.update()
    assert state3["frame_count"] == 3
    assert state3["received_frame_count"] == 3
    assert state3["rendered_frame_count"] == 3
    assert state3["frames_stale"] is True
    assert state3["world_stream_ready"] is False
    assert state3["failure_class"] == "world_stream_stale"


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
    monkeypatch.setattr(world_stream_controller.cv2, "imwrite", lambda *_args, **_kwargs: True)
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
    monkeypatch.setattr(world_stream_controller.cv2, "imwrite", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(world_stream_controller.time, "time", lambda: wall["value"])
    monkeypatch.setattr(world_stream_controller.time, "monotonic", lambda: mono["value"])
    monkeypatch.setenv("GZ_PARTITION", observer.args.session_id)

    observer._on_image(SimpleNamespace())
    first = observer.update()
    assert first["frames_stale"] is False
    assert first["failure_class"] == "world_stream_client_crash"

    wall["value"] = 103.5
    stale = observer.update()
    assert stale["frames_stale"] is True
    assert stale["failure_class"] == "world_stream_stale"
