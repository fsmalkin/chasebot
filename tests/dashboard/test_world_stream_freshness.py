from __future__ import annotations

import json
import io
import math
import os
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


def test_bounded_golf_fetch_random_draw_profiles_are_seeded_and_bounded():
    corridor_a = dashboard_service.bounded_golf_fetch_random_draw(seed=123)
    corridor_b = dashboard_service.bounded_golf_fetch_random_draw(seed=123)

    assert corridor_a == corridor_b
    assert corridor_a["random_profile"] == dashboard_service.GOLF_BALL_RANDOM_PROFILE_CORRIDOR_CONTACT
    corridor_bounds = corridor_a["bounds"]
    assert corridor_bounds["forward_min_m"] <= corridor_a["ball_pose"]["x"] <= corridor_bounds["forward_max_m"]
    assert corridor_bounds["lateral_min_m"] <= corridor_a["ball_pose"]["y"] <= corridor_bounds["lateral_max_m"]
    assert corridor_a["robot_lateral_offset_m"] == pytest.approx(0.0)
    assert corridor_a["robot_yaw_error_deg"] == pytest.approx(0.0)

    visual = dashboard_service.bounded_golf_fetch_random_draw(
        seed=123,
        profile=dashboard_service.GOLF_BALL_RANDOM_PROFILE_LOCAL_VISUAL,
    )
    visual_bounds = visual["bounds"]
    assert visual["random_profile"] == dashboard_service.GOLF_BALL_RANDOM_PROFILE_LOCAL_VISUAL
    assert visual_bounds["distance_min_m"] <= visual["ball_target_distance_m"] <= visual_bounds["distance_max_m"]
    assert visual_bounds["angle_min_deg"] <= visual["ball_target_angle_deg"] <= visual_bounds["angle_max_deg"]
    assert visual_bounds["robot_standoff_min_m"] <= visual["robot_standoff_m"] <= visual_bounds["robot_standoff_max_m"]
    assert visual_bounds["robot_lateral_min_m"] <= visual["robot_lateral_offset_m"] <= visual_bounds["robot_lateral_max_m"]
    assert visual_bounds["robot_yaw_error_min_deg"] <= visual["robot_yaw_error_deg"] <= visual_bounds["robot_yaw_error_max_deg"]
    assert visual["robot_ball_separation_m"] >= visual_bounds["min_robot_ball_separation_m"]
    for pose_key in ("ball_pose", "robot_pose"):
        pose = visual[pose_key]
        assert visual_bounds["world_x_min_m"] <= pose["x"] <= visual_bounds["world_x_max_m"]
        assert visual_bounds["world_y_min_m"] <= pose["y"] <= visual_bounds["world_y_max_m"]


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
        np_stub.isscalar = lambda value: isinstance(value, (int, float, complex, bool, str, bytes))
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
    controller.operator_view_required = True
    controller.visual_evidence_required = True
    controller.docker = "docker"
    controller.compose_file = REPO_ROOT / "docker-compose.yml"
    controller.host_repo_mount_source = ""
    controller.launcher_project = ""
    controller.build_on_next_start = False
    controller.state_lock = threading.RLock()
    controller.lifecycle_lock = threading.Lock()
    controller.lifecycle_thread = None
    controller.lifecycle_cancel = threading.Event()
    controller.idle_shutdown_enabled = True
    controller.idle_shutdown_after_s = dashboard_service.DEFAULT_IDLE_SHUTDOWN_AFTER_S
    controller.idle_shutdown_poll_s = dashboard_service.IDLE_SHUTDOWN_WATCHDOG_POLL_S
    controller.idle_shutdown_thread = None
    controller.idle_shutdown_cancel = threading.Event()
    controller.world_stream_restart_lock = threading.Lock()
    controller._world_stream_stale_since_monotonic = 0.0
    controller._world_stream_last_restart_monotonic = 0.0
    controller.active_env_proc = None
    controller.active_scenario_proc = None
    controller.active_intent_proc = None
    controller.scenario_thread = None
    controller.intent_thread = None
    controller.sim_gate_container_id = "sim-gate"
    controller.gate_stack_container_id = "gate-stack"
    controller.world_viewer_container_id = "world-viewer"
    controller.operator_view_container_id = "operator-view"
    controller.pending_scenario_id = ""
    controller.pending_scenario_overrides = {}
    controller.active_scenario_overrides = {}
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
        "planner_handoff": {},
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
        "operator_view_required": True,
        "visual_evidence_required": True,
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
        "idle_shutdown_enabled": True,
        "idle_shutdown_after_s": dashboard_service.DEFAULT_IDLE_SHUTDOWN_AFTER_S,
        "idle_shutdown_poll_s": dashboard_service.IDLE_SHUTDOWN_WATCHDOG_POLL_S,
        "idle_shutdown_state": "watching",
        "idle_shutdown_blocker": "",
        "idle_shutdown_idle_since_utc": "",
        "idle_shutdown_deadline_utc": "",
        "idle_shutdown_remaining_s": None,
        "idle_shutdown_triggered_utc": "",
        "idle_shutdown_last_checked_utc": "",
        "idle_shutdown_last_error": "",
        "last_operator_activity_utc": "2026-03-18T00:00:00Z",
        "last_operator_activity_reason": "test_setup",
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


def test_fetch_plan_routes_serve_static_page_and_data(tmp_path):
    page = _serve_dashboard_path("/fetch-plan", tmp_path)
    assert page == [
        (
            dashboard_service.STATIC_DASHBOARD_DIR / "fetch_plan.html",
            "text/html; charset=utf-8",
            False,
        )
    ]

    data = _serve_dashboard_path("/fetch_plan_data.json", tmp_path)
    assert data == [
        (
            dashboard_service.STATIC_DASHBOARD_DIR / "fetch_plan_data.json",
            "application/json; charset=utf-8",
            True,
        )
    ]

    payload = json.loads((dashboard_service.STATIC_DASHBOARD_DIR / "fetch_plan_data.json").read_text(encoding="utf-8"))
    assert payload["status_label"] == "Fresh rough seed 20260642 is green"
    evidence_by_title = {item["title"]: item for item in payload["latest_evidence"]}
    assert "Seed 20260642 rough UAT is green" in evidence_by_title
    assert "Seed 20260641 startup-retry rough UAT is green" in evidence_by_title
    assert "Seed 20260640 preflight repair rough UAT is green" in evidence_by_title
    assert "Seed 20260639 rough breadth UAT is green" in evidence_by_title
    assert "Seed 20260638 rough breadth UAT is green" in evidence_by_title
    assert "Seed 20260637 breadth UAT is green" in evidence_by_title
    assert "Seed 20260636 breadth UAT is green" in evidence_by_title
    assert "Fresh rehearsal ladder is green" in evidence_by_title
    assert "Robot-side rehearsal preflight is ready" in evidence_by_title
    assert "Seed 20260635 hardware rehearsal is green" in evidence_by_title
    assert "Saved-anchor fetch rehearsal is green" in evidence_by_title
    assert "Runtime stack smoke executed with artifact contract" in evidence_by_title
    assert "Hardware rehearsal runner preflight is green" in evidence_by_title
    assert "Hardware rehearsal run plan is ready" in evidence_by_title
    assert "Hardware-transfer rehearsal package is ready" in evidence_by_title
    assert "Supervised seeded promotion refresh is green" in evidence_by_title
    assert evidence_by_title["Seed 20260642 rough UAT is green"]["links"][0]["url"].endswith(
        "/fetch_planner_seeded_generalization_gate/scorecard.md"
    )
    assert any(
        link["url"].endswith("/visual/raw_camera_browser.mp4")
        for link in evidence_by_title["Seed 20260642 rough UAT is green"]["links"]
    )
    assert any(
        link["url"].endswith("/visual/keyframe_review_contact_sheet.png")
        for link in evidence_by_title["Seed 20260642 rough UAT is green"]["links"]
    )
    assert evidence_by_title["Seed 20260641 startup-retry rough UAT is green"]["links"][0]["url"].endswith(
        "/fetch_planner_seeded_generalization_gate/scorecard.md"
    )
    assert any(
        link["url"].endswith("/visual/raw_camera_browser.mp4")
        for link in evidence_by_title["Seed 20260641 startup-retry rough UAT is green"]["links"]
    )
    assert any(
        "timeout_capture" in link["url"]
        for link in evidence_by_title["Seed 20260641 startup-retry rough UAT is green"]["links"]
    )
    assert evidence_by_title["Seed 20260640 preflight repair rough UAT is green"]["links"][0]["url"].endswith(
        "/fetch_planner_seeded_generalization_gate/scorecard.md"
    )
    assert any(
        link["url"].endswith("/visual/raw_camera_browser.mp4")
        for link in evidence_by_title["Seed 20260640 preflight repair rough UAT is green"]["links"]
    )
    assert any(
        "control_preflight.json" in link["url"]
        for link in evidence_by_title["Seed 20260640 preflight repair rough UAT is green"]["links"]
    )
    assert evidence_by_title["Seed 20260639 rough breadth UAT is green"]["links"][0]["url"].endswith(
        "/fetch_planner_seeded_generalization_gate/scorecard.md"
    )
    assert any(
        link["url"].endswith("/visual/raw_camera_browser.mp4")
        for link in evidence_by_title["Seed 20260639 rough breadth UAT is green"]["links"]
    )
    assert evidence_by_title["Seed 20260638 rough breadth UAT is green"]["links"][0]["url"].endswith(
        "/fetch_planner_seeded_generalization_gate/scorecard.md"
    )
    assert any(
        link["url"].endswith("/visual/raw_camera_browser.mp4")
        for link in evidence_by_title["Seed 20260638 rough breadth UAT is green"]["links"]
    )
    assert evidence_by_title["Seed 20260637 breadth UAT is green"]["links"][0]["url"].endswith(
        "/fetch_planner_seeded_generalization_gate/scorecard.md"
    )
    assert any(
        link["url"].endswith("/visual/raw_camera_browser.mp4")
        for link in evidence_by_title["Seed 20260637 breadth UAT is green"]["links"]
    )
    assert evidence_by_title["Seed 20260636 breadth UAT is green"]["links"][0]["url"].endswith(
        "/fetch_planner_seeded_generalization_gate/scorecard.md"
    )
    assert any(
        link["url"].endswith("/visual/raw_camera_browser.mp4")
        for link in evidence_by_title["Seed 20260636 breadth UAT is green"]["links"]
    )
    assert evidence_by_title["Saved-anchor fetch rehearsal is green"]["links"][0]["url"].endswith(
        "/fetch_hardware_rehearsal_runner/scorecard.md"
    )
    assert evidence_by_title["Fresh rehearsal ladder is green"]["links"][0]["url"].endswith(
        "/fetch_hardware_rehearsal_runner/scorecard.md"
    )
    assert evidence_by_title["Robot-side rehearsal preflight is ready"]["links"][0]["url"].endswith(
        "/fetch_robot_side_rehearsal_preflight/scorecard.md"
    )
    assert evidence_by_title["Seed 20260635 hardware rehearsal is green"]["links"][0]["url"].endswith(
        "/fetch_hardware_rehearsal_runner/scorecard.md"
    )
    assert evidence_by_title["Runtime stack smoke executed with artifact contract"]["links"][0]["url"].endswith(
        "/fetch_hardware_rehearsal_runner/scorecard.md"
    )
    assert evidence_by_title["Hardware rehearsal runner preflight is green"]["links"][0]["url"].endswith(
        "/fetch_hardware_rehearsal_runner/scorecard.md"
    )
    assert evidence_by_title["Hardware rehearsal run plan is ready"]["links"][0]["url"].endswith(
        "/fetch_hardware_rehearsal_plan/scorecard.md"
    )
    assert evidence_by_title["Hardware-transfer rehearsal package is ready"]["links"][0]["url"].endswith(
        "/fetch_hardware_transfer_readiness/scorecard.md"
    )
    assert evidence_by_title["Supervised seeded promotion refresh is green"]["links"][0]["url"].endswith(
        "/fetch_planner_seeded_generalization_gate/scorecard.md"
    )
    route_samples = payload["uat_review_bundle"]["route_samples"]
    assert len(route_samples) == 8
    assert {sample["route"] for sample in route_samples} == {
        "fetch_ready_local",
        "nav2_reposition_first",
        "recovery_or_reaim",
    }
    assert payload["uat_review_bundle"]["route_samples"][0]["video_url"].startswith("/artifacts/session/")
    assert payload["latest_evidence"][0]["links"][0]["url"].startswith("/artifacts/session/")
    html = (dashboard_service.STATIC_DASHBOARD_DIR / "fetch_plan.html").read_text(encoding="utf-8")
    assert "UAT Review Bundle" in html
    assert "uat_review_bundle" in html
    assert "renderUatBundle" in html
    assert "Running / Recent Video Proof" in html
    assert "runningProof" in html
    assert "running_proof" in html
    assert "recent_video_proof" in html
    assert "primary_video" in html


def test_artifact_media_route_serves_mp4_ranges(monkeypatch, tmp_path):
    session_root = tmp_path / "artifacts" / "session"
    monkeypatch.setattr(dashboard_service, "SESSION_ROOT", session_root)
    video_path = session_root / "uat" / "visual" / "world_stream.mp4"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_bytes(b"0123456789")

    handler = dashboard_service.DashboardRequestHandler.__new__(dashboard_service.DashboardRequestHandler)
    handler.headers = {"Range": "bytes=2-5"}
    handler.wfile = io.BytesIO()
    responses: list[int] = []
    headers: list[tuple[str, str]] = []
    handler.send_response = lambda status: responses.append(int(status))
    handler.send_header = lambda key, value: headers.append((str(key), str(value)))
    handler.end_headers = lambda: None

    handler._serve_artifact_file(video_path)

    assert responses == [206]
    assert ("Content-Range", "bytes 2-5/10") in headers
    assert ("Accept-Ranges", "bytes") in headers
    assert handler.wfile.getvalue() == b"2345"


def test_artifact_media_route_rejects_path_traversal(monkeypatch, tmp_path):
    session_root = tmp_path / "artifacts" / "session"
    monkeypatch.setattr(dashboard_service, "SESSION_ROOT", session_root)
    controller = _make_controller(tmp_path)

    assert controller.resolve_session_artifact_path("../outside.mp4") is None


def test_get_state_includes_latest_visual_uat_package(monkeypatch, tmp_path):
    session_root = tmp_path / "artifacts" / "session"
    monkeypatch.setattr(dashboard_service, "SESSION_ROOT", session_root)
    controller = _make_controller(tmp_path)
    _write_json(
        session_root / "uat" / "fetch_visual_uat_package" / "package_summary.json",
        {
            "type": "fetch_visual_uat_package",
            "campaign_id": "uat",
            "pass": True,
            "mobile_watchable": True,
            "planner_gate_green": True,
            "local_fetch_pass_seen": True,
            "raw_local_fetch_pass_seen": True,
            "fetch_model_provenance_invalid_seen": False,
            "videos": [
                {
                    "name": "world_stream.mp4",
                    "path": "artifacts/session/uat/visual/world_stream.mp4",
                    "url": "/artifacts/session/uat/visual/world_stream.mp4",
                    "browser_compatible": True,
                    "browser_playable": True,
                },
                {
                    "name": "raw_camera.mp4",
                    "path": "artifacts/session/uat/visual/raw_camera.mp4",
                    "url": "",
                    "browser_compatible": False,
                    "browser_playable": False,
                    "validation_error": "moov_atom_not_found",
                }
            ],
        },
    )

    state = controller.get_state()

    assert state["visual_uat_package"]["campaign_id"] == "uat"
    assert state["visual_uat_package"]["pass"] is True
    assert state["visual_uat_package"]["fetch_model_provenance_invalid_seen"] is False
    assert state["visual_uat_package"]["videos"][0]["url"] == "/artifacts/session/uat/visual/world_stream.mp4"
    assert state["visual_uat_package"]["videos"][1]["url"] == ""


def test_idle_shutdown_operator_activity_resets_idle_timer(monkeypatch, tmp_path):
    controller = _make_controller(tmp_path)
    controller.state["idle_shutdown_idle_since_utc"] = "2026-05-22T12:00:00+00:00"
    controller.state["idle_shutdown_deadline_utc"] = "2026-05-22T12:30:00+00:00"
    controller.state["idle_shutdown_remaining_s"] = 1200.0
    monkeypatch.setattr(dashboard_service, "utc_now", lambda: "2026-05-22T12:10:00+00:00")

    controller._mark_operator_activity("intent_preview")

    assert controller.state["last_operator_activity_utc"] == "2026-05-22T12:10:00+00:00"
    assert controller.state["last_operator_activity_reason"] == "intent_preview"
    assert controller.state["idle_shutdown_idle_since_utc"] == ""
    assert controller.state["idle_shutdown_deadline_utc"] == ""
    assert controller.state["idle_shutdown_remaining_s"] is None


def test_idle_shutdown_queues_environment_stop_after_ready_idle_timeout(monkeypatch, tmp_path):
    controller = _make_controller(tmp_path)
    controller.idle_shutdown_after_s = 10.0
    controller.state["idle_shutdown_after_s"] = 10.0
    controller.state["idle_shutdown_idle_since_utc"] = "2026-05-22T12:00:00+00:00"
    monkeypatch.setattr(dashboard_service, "utc_now", lambda: "2026-05-22T12:00:11+00:00")
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

    controller._evaluate_idle_shutdown()

    assert started
    assert started[0].target == controller._stop_environment_worker
    assert started[0].name == "dashboard-idle-stop"
    assert controller.state["idle_shutdown_state"] == "queued"
    assert controller.state["idle_shutdown_triggered_utc"] == "2026-05-22T12:00:11+00:00"
    assert controller.state["environment_message"] == "idle shutdown queued"


def test_idle_shutdown_does_not_stop_while_scenario_running(monkeypatch, tmp_path):
    controller = _make_controller(tmp_path)
    controller.idle_shutdown_after_s = 10.0
    controller.state["idle_shutdown_idle_since_utc"] = "2026-05-22T12:00:00+00:00"
    controller.state["scenario_state"] = "running"
    monkeypatch.setattr(dashboard_service, "utc_now", lambda: "2026-05-22T12:00:30+00:00")
    started: list[object] = []

    class _FakeThread:
        def __init__(self, target, name, daemon):
            started.append(self)

        def start(self) -> None:
            return None

        def is_alive(self) -> bool:
            return False

    monkeypatch.setattr(dashboard_service.threading, "Thread", _FakeThread)

    controller._evaluate_idle_shutdown()

    assert started == []
    assert controller.state["idle_shutdown_state"] == "busy"
    assert controller.state["idle_shutdown_blocker"] == "scenario_running"
    assert controller.state["idle_shutdown_idle_since_utc"] == ""


def test_idle_shutdown_does_not_stop_while_mission_runtime_running(monkeypatch, tmp_path):
    controller = _make_controller(tmp_path)
    controller.idle_shutdown_after_s = 10.0
    controller.state["idle_shutdown_idle_since_utc"] = "2026-05-22T12:00:00+00:00"
    controller._visit_mission_runtime_state = lambda: {"running": True}
    monkeypatch.setattr(dashboard_service, "utc_now", lambda: "2026-05-22T12:00:30+00:00")
    started: list[object] = []

    class _FakeThread:
        def __init__(self, target, name, daemon):
            started.append(self)

        def start(self) -> None:
            return None

        def is_alive(self) -> bool:
            return False

    monkeypatch.setattr(dashboard_service.threading, "Thread", _FakeThread)

    controller._evaluate_idle_shutdown()

    assert started == []
    assert controller.state["idle_shutdown_state"] == "busy"
    assert controller.state["idle_shutdown_blocker"] == "visit_runtime_running"


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
    controller.pending_scenario_overrides = {"random_layout": True, "random_seed": 456}
    controller._launch_scenario_thread = lambda scenario: launched.append(scenario.id)

    controller._start_pending_scenario_if_any()

    assert launched == ["visit_route_planning"]
    assert controller.pending_scenario_id == ""
    assert controller.pending_scenario_overrides == {}
    assert controller.active_scenario_overrides == {"random_layout": True, "random_seed": 456}


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


def test_truth_probe_samples_pose_info_when_dynamic_pose_is_empty(monkeypatch):
    dynamic_topic = "/world/yolo_test_world/dynamic_pose/info"
    pose_topic = "/world/yolo_test_world/pose/info"
    pose_payload = '''
pose {
  name: "jetbot"
  position {
    x: 0.1
  }
  orientation {
    w: 1
  }
}
'''

    def fake_sample(topic):
        if topic == dynamic_topic:
            return True, ""
        if topic == pose_topic:
            return True, pose_payload
        return False, "unexpected topic"

    monkeypatch.setattr(sim_truth_probe, "sample_pose_topic", fake_sample)

    ok, payload, sampled_topic, errors = sim_truth_probe.sample_first_pose_payload([dynamic_topic, pose_topic])

    assert ok is True
    assert payload == pose_payload
    assert sampled_topic == pose_topic
    assert errors == {dynamic_topic: ""}
    assert sim_truth_probe.parse_pose_message(payload)[0]["name"] == "jetbot"


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
    monkeypatch.setattr(dashboard_service, "find_free_port", lambda start, end, *, exclude_ports=None: start)
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


def test_beta_dashboard_includes_primary_golf_fetch_cta_and_stage_mapping():
    html_path = REPO_ROOT / "runtime/dashboard/beta_dashboard.html"
    html = html_path.read_text(encoding="utf-8")

    assert "pickScenario('corral_single_ball_place')" in html
    assert "pickScenario('gather_three_ball_zone')" in html
    assert "pickScenario('golf_ball_circle_delivery_uat')" in html
    assert "runLatestGolfFetch()" in html
    assert "Run Random Golf-Ball Delivery" in html
    assert "Start + Run Random Golf-Ball Delivery" in html
    assert "random_layout: true" in html
    assert "random_profile: 'local_visual_v1'" in html
    assert "Run Golf-Ball Circle Delivery" not in html
    assert '<link rel="icon" href="data:,">' in html
    assert 'onload="if (window.operatorFrameLoaded)' in html
    assert "window.__operatorFrameLoadedPending = true" in html
    assert "const LATEST_GOLF_FETCH_SCENARIO_ID = 'golf_ball_circle_delivery_uat';" in html
    assert "const OBJECT_CENTRIC_ZERO_SCENARIO_ID = 'object_centric_zero_saved_layout';" in html
    assert "const CORRAL_STAGE_LABELS = ['Init','Visit','Capture','Place','Done'];" in html
    assert "const FETCH_STAGE_LABELS = ['Init','Visit','Capture','Deliver','Done'];" in html
    assert "Acquiring the ball" in html
    assert "Controlling the ball" in html
    assert "Placing ball into the zone" in html
    assert "Fetch v1 Progress" in html
    assert 'id="fp-status"' in html
    assert 'id="fp-planner"' in html
    assert 'id="fp-stage"' in html
    assert "Planner-Gated Random" in html
    assert "Mobile UAT Package" in html
    assert 'id="uat-stage"' in html
    assert 'id="uat-model"' in html
    assert 'id="uat-video-list"' in html
    assert "playsinline" in html
    assert "renderVisualUatPackage()" in html
    assert "ai_push_coast_mode: 'guarded_live'" in html
    assert "renderFetchProgress()" in html
    assert "routeOrderText" in html
    assert "final_three_ball_corral_pass" in html


def test_dashboard_state_includes_latest_fetch_progress_from_artifacts(tmp_path, monkeypatch):
    session_root = tmp_path / "session"
    monkeypatch.setattr(dashboard_service, "SESSION_ROOT", session_root)
    controller = _make_controller(tmp_path)
    controller._fetch_progress_cache = {}
    controller._fetch_progress_cache_at = 0.0

    evidence_dir = session_root / "fetch_evidence" / "fetch_seeded_gate_evidence_analyzer"
    _write_json(
        evidence_dir / "evidence_summary.json",
        {
            "type": "fetch_seeded_gate_evidence_analyzer",
            "campaign_id": "fetch_evidence",
            "recommended_next_action": "rerun_watchlist_before_guarded_live",
            "milestone_interpretation": "non_repro_watchlist_before_promotion",
            "promotion_evidence": False,
            "saved_anchor_context": {
                "campaign_id": "saved_anchor_campaign",
                "candidate_rows": [
                    {
                        "family": "ai_push_coast_servo_v1",
                        "layout_id": "zero",
                        "pass": True,
                        "model_provenance_valid": True,
                        "model_provenance_reason": "calibrated_fetch_models",
                        "target_model_classification": "calibrated_golf_ball",
                        "worst_closest_approach_distance_m": 0.21,
                    },
                    {
                        "family": "ai_push_coast_servo_v1",
                        "layout_id": "left05",
                        "pass": True,
                        "model_provenance_valid": True,
                        "model_provenance_reason": "calibrated_fetch_models",
                        "target_model_classification": "calibrated_golf_ball",
                        "worst_closest_approach_distance_m": 0.18,
                    },
                    {
                        "family": "ai_push_coast_servo_v1",
                        "layout_id": "right05",
                        "pass": True,
                        "model_provenance_valid": True,
                        "model_provenance_reason": "calibrated_fetch_models",
                        "target_model_classification": "calibrated_golf_ball",
                        "worst_closest_approach_distance_m": 0.19,
                    },
                ],
            },
            "seeded_shadow_gate": {
                "campaign_id": "seeded_gate",
                "mode": "shadow",
                "seed": 20260529,
                "pass_count": 5,
                "fail_count": 1,
                "non_repro_failure_count": 1,
                "reproduced_failure_count": 0,
                "guarded_live_candidate_count": 1,
                "model_provenance_valid": True,
                "model_provenance_invalid_count": 0,
                "interpretation": "non_repro_watchlist_before_promotion",
            },
        },
    )
    _write_json(
        session_root / "guarded_probe" / "gather_mission_repeatability" / "campaign_run_summary.json",
        {
            "campaign_id": "guarded_probe",
            "mission_objective": "fetch_to_pose",
            "ai_push_coast_mode": "guarded_live",
            "fetch_to_pose_pass_count": 1,
            "fetch_to_pose_fail_count": 0,
            "model_provenance_valid": True,
            "model_provenance_reason": "calibrated_fetch_models",
            "target_model_classification": "calibrated_golf_ball",
            "target_model_sdf": "ros2_config/calibrated_golf_ball.sdf",
            "zone_model_sdf": "ros2_config/golf_ball_delivery_zone_marker.sdf",
            "first_contact_push_alignment_max_deg": 18.2,
            "fetch_to_pose_time_max_s": 8.7,
        },
    )
    _write_json(
        session_root / "planner_gate" / "fetch_planner_handoff_gate" / "gate_summary.json",
        {
            "type": "fetch_planner_handoff_gate",
            "campaign_id": "planner_gate",
            "scene_set": "mixed_fetch_planner_v1",
            "scene_source": "frozen",
            "planner_mode": "deterministic",
            "pass": True,
            "pass_count": 20,
            "fail_count": 0,
            "random_cases": 20,
            "fetch_dispatch_count": 5,
            "wrong_fetch_dispatch_count": 0,
            "route_counts": {
                "fetch_ready_local": 5,
                "nav2_reposition_first": 4,
                "scan_or_perceive_first": 4,
                "recovery_or_reaim": 4,
                "ambiguous_or_unsafe_no_go": 3,
            },
        },
    )
    _write_json(
        session_root / "stage_audit" / "fetch_saved_anchor_setup_contact_audit" / "audit_summary.json",
        {
            "type": "fetch_saved_anchor_setup_contact_audit",
            "campaign_id": "stage_audit",
            "overall_interpretation": "repair_setup_contact_before_guarded_live",
            "stage_quality_green": False,
            "saved_anchor_count": 3,
            "stage_quality_pass_count": 2,
            "setup_contact_blocker_count": 1,
            "setup_capture_blocker_count": 1,
            "first_contact_blocker_count": 0,
            "invalid_geometry_count": 0,
            "invalid_model_provenance_count": 0,
            "saved_anchor_pass_with_contact_watch_count": 2,
            "saved_anchors": [
                {"layout": "zero", "pass": True, "delivery_pass": True, "quality_classification": "pass_with_capture_quality_watch"},
                {"layout": "left05", "pass": True, "delivery_pass": True, "quality_classification": "pass_with_capture_quality_watch"},
                {"layout": "right05", "pass": False, "delivery_pass": False, "quality_classification": "setup_capture_blocker"},
            ],
        },
    )

    state = controller.get_state()
    progress = state["fetch_progress"]
    assert progress["milestone"] == dashboard_service.FETCH_PROGRESS_MILESTONE
    assert progress["status"] == "bad"
    assert progress["saved_anchor"]["green"] is False
    assert progress["saved_anchor"]["pass_count"] == 2
    assert progress["seeded_shadow_gate"]["pass_count"] == 5
    assert progress["seeded_shadow_gate"]["non_repro_failure_count"] == 1
    assert progress["planner_handoff_gate"]["pass"] is True
    assert progress["planner_handoff_gate"]["scene_source"] == "frozen"
    assert progress["planner_handoff_gate"]["wrong_fetch_dispatch_count"] == 0
    assert progress["stage_quality_audit"]["green"] is False
    assert progress["stage_quality_audit"]["pass_count"] == 2
    assert progress["stage_quality_audit"]["setup_capture_blocker_count"] == 1
    assert progress["stage_quality_audit"]["push_coast_blocker_count"] == 0
    assert progress["stage_quality_audit"]["watch_count"] == 2
    assert progress["latest_guarded_live_probe"]["pass"] is True
    assert progress["latest_guarded_live_probe"]["model_provenance_valid"] is True
    assert progress["recommended_next_action"] == "repair_setup_contact_before_guarded_live"


def test_dashboard_fetch_progress_blocks_stale_model_provenance(tmp_path, monkeypatch):
    session_root = tmp_path / "session"
    monkeypatch.setattr(dashboard_service, "SESSION_ROOT", session_root)
    controller = _make_controller(tmp_path)
    controller._fetch_progress_cache = {}
    controller._fetch_progress_cache_at = 0.0

    evidence_dir = session_root / "fetch_evidence" / "fetch_seeded_gate_evidence_analyzer"
    _write_json(
        evidence_dir / "evidence_summary.json",
        {
            "type": "fetch_seeded_gate_evidence_analyzer",
            "campaign_id": "stale_fetch_evidence",
            "recommended_next_action": "rerun_watchlist_before_guarded_live",
            "saved_anchor_context": {
                "campaign_id": "saved_anchor_campaign",
                "candidate_rows": [
                    {
                        "family": "ai_push_coast_servo_v1",
                        "layout_id": "zero",
                        "pass": True,
                        "worst_closest_approach_distance_m": 0.21,
                    },
                ],
            },
            "seeded_shadow_gate": {
                "campaign_id": "seeded_gate",
                "mode": "shadow",
                "pass_count": 1,
                "fail_count": 0,
            },
        },
    )

    progress = controller.get_state()["fetch_progress"]

    assert progress["status"] == "bad"
    assert "lacks calibrated model provenance" in progress["headline"]
    assert progress["saved_anchor"]["green"] is False
    assert progress["saved_anchor"]["invalid_model_provenance_count"] == 1
    assert progress["seeded_shadow_gate"]["model_provenance_valid"] is False
    assert progress["seeded_shadow_gate"]["model_provenance_invalid_count"] == 1


def test_dashboard_fetch_progress_marks_older_seeded_model_gap_pending_after_fresh_stage_audit(tmp_path, monkeypatch):
    session_root = tmp_path / "session"
    monkeypatch.setattr(dashboard_service, "SESSION_ROOT", session_root)
    controller = _make_controller(tmp_path)
    controller._fetch_progress_cache = {}
    controller._fetch_progress_cache_at = 0.0

    evidence_path = session_root / "fetch_evidence" / "fetch_seeded_gate_evidence_analyzer" / "evidence_summary.json"
    _write_json(
        evidence_path,
        {
            "type": "fetch_seeded_gate_evidence_analyzer",
            "campaign_id": "stale_fetch_evidence",
            "recommended_next_action": "rerun_watchlist_before_guarded_live",
            "saved_anchor_context": {
                "campaign_id": "stale_saved_anchor_campaign",
                "candidate_rows": [{"layout_id": "zero", "pass": True}],
            },
            "seeded_shadow_gate": {
                "campaign_id": "stale_seeded_gate",
                "mode": "shadow",
                "pass_count": 5,
                "fail_count": 1,
                "model_provenance_valid": False,
                "model_provenance_invalid_count": 6,
            },
        },
    )
    stage_path = session_root / "stage_audit" / "fetch_saved_anchor_setup_contact_audit" / "audit_summary.json"
    _write_json(
        stage_path,
        {
            "type": "fetch_saved_anchor_setup_contact_audit",
            "campaign_id": "fresh_stage_audit",
            "overall_interpretation": "saved_anchor_repeatability_ready_with_contact_watch",
            "stage_quality_green": True,
            "saved_anchor_count": 3,
            "stage_quality_pass_count": 3,
            "setup_contact_blocker_count": 0,
            "setup_capture_blocker_count": 0,
            "first_contact_blocker_count": 0,
            "push_coast_blocker_count": 0,
            "invalid_geometry_count": 0,
            "invalid_model_provenance_count": 0,
            "saved_anchor_pass_with_contact_watch_count": 1,
            "saved_anchors": [
                {"layout": "zero", "pass": True, "delivery_pass": True, "model_provenance_valid": True, "quality_classification": "clean_pass"},
                {"layout": "left05", "pass": True, "delivery_pass": True, "model_provenance_valid": True, "quality_classification": "pass_with_capture_quality_watch"},
                {"layout": "right05", "pass": True, "delivery_pass": True, "model_provenance_valid": True, "quality_classification": "clean_pass"},
            ],
        },
    )
    os.utime(evidence_path, (100.0, 100.0))
    os.utime(stage_path, (200.0, 200.0))

    progress = controller.get_state()["fetch_progress"]

    assert progress["status"] == "warn"
    assert "Saved anchors stage-quality pass 3/3" in progress["headline"]
    assert progress["recommended_next_action"] == "run_seeded_generalization_gate"
    assert progress["saved_anchor"]["green"] is True
    assert progress["seeded_shadow_gate"]["stale_after_stage_quality_audit"] is True
    assert progress["seeded_shadow_gate"]["current_blocking"] is False
    assert progress["seeded_shadow_gate"]["model_provenance_invalid_count"] == 6


def test_dashboard_fetch_progress_prioritizes_fresh_seeded_reproduced_failures(tmp_path, monkeypatch):
    session_root = tmp_path / "session"
    monkeypatch.setattr(dashboard_service, "SESSION_ROOT", session_root)
    controller = _make_controller(tmp_path)
    controller._fetch_progress_cache = {}
    controller._fetch_progress_cache_at = 0.0

    stage_path = session_root / "stage_audit" / "fetch_saved_anchor_setup_contact_audit" / "audit_summary.json"
    _write_json(
        stage_path,
        {
            "type": "fetch_saved_anchor_setup_contact_audit",
            "campaign_id": "fresh_stage_audit",
            "overall_interpretation": "saved_anchor_repeatability_ready_with_contact_watch",
            "stage_quality_green": True,
            "saved_anchor_count": 3,
            "stage_quality_pass_count": 3,
            "setup_contact_blocker_count": 0,
            "setup_capture_blocker_count": 0,
            "first_contact_blocker_count": 0,
            "push_coast_blocker_count": 0,
            "invalid_geometry_count": 0,
            "invalid_model_provenance_count": 0,
            "saved_anchor_pass_with_contact_watch_count": 1,
            "saved_anchors": [
                {"layout": "zero", "pass": True, "delivery_pass": True, "model_provenance_valid": True, "quality_classification": "clean_pass"},
                {"layout": "left05", "pass": True, "delivery_pass": True, "model_provenance_valid": True, "quality_classification": "pass_with_capture_quality_watch"},
                {"layout": "right05", "pass": True, "delivery_pass": True, "model_provenance_valid": True, "quality_classification": "clean_pass"},
            ],
        },
    )
    evidence_path = session_root / "fetch_evidence" / "fetch_seeded_gate_evidence_analyzer" / "evidence_summary.json"
    _write_json(
        evidence_path,
        {
            "type": "fetch_seeded_gate_evidence_analyzer",
            "campaign_id": "fresh_seeded_evidence",
            "recommended_next_action": "freeze_reproduced_failures_before_tuning",
            "milestone_interpretation": "promotion_blocker_freeze_reproduced_failures",
            "promotion_evidence": False,
            "seeded_shadow_gate": {
                "campaign_id": "seeded_gate",
                "mode": "shadow",
                "pass_count": 4,
                "fail_count": 2,
                "non_repro_failure_count": 0,
                "reproduced_failure_count": 2,
                "model_provenance_valid": True,
                "model_provenance_invalid_count": 0,
            },
        },
    )
    os.utime(stage_path, (100.0, 100.0))
    os.utime(evidence_path, (200.0, 200.0))

    progress = controller.get_state()["fetch_progress"]

    assert progress["status"] == "bad"
    assert "Seeded random gate has 2 reproduced failures" in progress["headline"]
    assert progress["recommended_next_action"] == "freeze_reproduced_failures_before_tuning"
    assert progress["stage_quality_audit"]["green"] is True
    assert progress["seeded_shadow_gate"]["current_blocking"] is True
    assert progress["seeded_shadow_gate"]["reproduced_failure_count"] == 2


def test_dashboard_fetch_progress_promotion_evidence_overrides_stage_quality_watch(tmp_path, monkeypatch):
    session_root = tmp_path / "session"
    monkeypatch.setattr(dashboard_service, "SESSION_ROOT", session_root)
    controller = _make_controller(tmp_path)
    controller._fetch_progress_cache = {}
    controller._fetch_progress_cache_at = 0.0

    _write_json(
        session_root / "stage_audit" / "fetch_saved_anchor_setup_contact_audit" / "audit_summary.json",
        {
            "type": "fetch_saved_anchor_setup_contact_audit",
            "campaign_id": "stage_audit",
            "overall_interpretation": "saved_anchor_repeatability_ready_with_contact_watch",
            "stage_quality_green": True,
            "saved_anchor_count": 3,
            "stage_quality_pass_count": 3,
            "setup_contact_blocker_count": 0,
            "setup_capture_blocker_count": 0,
            "first_contact_blocker_count": 0,
            "push_coast_blocker_count": 0,
            "invalid_geometry_count": 0,
            "invalid_model_provenance_count": 0,
            "saved_anchor_pass_with_contact_watch_count": 1,
            "saved_anchors": [
                {"layout": "zero", "pass": True, "delivery_pass": True, "model_provenance_valid": True, "quality_classification": "clean_pass"},
                {"layout": "left05", "pass": True, "delivery_pass": True, "model_provenance_valid": True, "quality_classification": "pass_with_capture_quality_watch"},
                {"layout": "right05", "pass": True, "delivery_pass": True, "model_provenance_valid": True, "quality_classification": "clean_pass"},
            ],
        },
    )
    _write_json(
        session_root / "fetch_evidence" / "fetch_seeded_gate_evidence_analyzer" / "evidence_summary.json",
        {
            "type": "fetch_seeded_gate_evidence_analyzer",
            "campaign_id": "guarded_live_evidence",
            "recommended_next_action": "package_mobile_visual_uat",
            "milestone_interpretation": "guarded_live_seeded_gate_promotion_ready",
            "promotion_evidence": True,
            "seeded_shadow_gate": {
                "campaign_id": "guarded_seeded_gate",
                "mode": "guarded_live",
                "pass_count": 6,
                "fail_count": 0,
                "non_repro_failure_count": 0,
                "reproduced_failure_count": 0,
                "model_provenance_valid": True,
                "model_provenance_invalid_count": 0,
                "interpretation": "guarded_live_seeded_gate_clean",
            },
        },
    )

    progress = controller.get_state()["fetch_progress"]

    assert progress["status"] == "ok"
    assert progress["promotion_evidence"] is True
    assert "promotion-grade" in progress["headline"]
    assert progress["recommended_next_action"] == "package_mobile_visual_uat"


def test_dashboard_fetch_progress_fresh_planner_seeded_gate_blocks_stale_promotion(tmp_path, monkeypatch):
    session_root = tmp_path / "session"
    monkeypatch.setattr(dashboard_service, "SESSION_ROOT", session_root)
    controller = _make_controller(tmp_path)
    controller._fetch_progress_cache = {}
    controller._fetch_progress_cache_at = 0.0

    _write_json(
        session_root / "stage_audit" / "fetch_saved_anchor_setup_contact_audit" / "audit_summary.json",
        {
            "type": "fetch_saved_anchor_setup_contact_audit",
            "campaign_id": "stage_audit",
            "stage_quality_green": True,
            "saved_anchor_count": 3,
            "stage_quality_pass_count": 3,
            "setup_contact_blocker_count": 0,
            "setup_capture_blocker_count": 0,
            "first_contact_blocker_count": 0,
            "push_coast_blocker_count": 0,
            "invalid_model_provenance_count": 0,
        },
    )
    _write_json(
        session_root / "fetch_evidence" / "fetch_seeded_gate_evidence_analyzer" / "evidence_summary.json",
        {
            "type": "fetch_seeded_gate_evidence_analyzer",
            "campaign_id": "old_guarded_live_evidence",
            "recommended_next_action": "package_mobile_visual_uat",
            "milestone_interpretation": "guarded_live_seeded_gate_promotion_ready",
            "promotion_evidence": True,
            "seeded_shadow_gate": {
                "campaign_id": "old_guarded_seeded_gate",
                "mode": "guarded_live",
                "pass_count": 6,
                "fail_count": 0,
                "model_provenance_valid": True,
                "model_provenance_invalid_count": 0,
            },
        },
    )
    _write_json(
        session_root / "broad_gate" / "fetch_planner_seeded_generalization_gate" / "gate_summary.json",
        {
            "type": "fetch_planner_seeded_generalization_gate",
            "campaign_id": "broad_gate",
            "dry_run": False,
            "seed": 20260627,
            "random_cases": 30,
            "expected_executable_count": 6,
            "pass": False,
            "promotion_evidence": False,
            "planner_gate_pass": True,
            "replay_pass": False,
            "analyzer_pass": False,
            "milestone_interpretation": "planner_routed_seeded_generalization_incomplete",
            "replay_first_failure": {
                "scene_id": "seed20260627_scene04_recovery_or_reaim",
                "route_label": "recovery_or_reaim",
                "returncode": 2,
            },
            "replay_summary": {"mission_pass_count": 0, "mission_fail_count": 1},
            "analyzer_summary": {"execution_quality_status": "blocker"},
        },
    )

    progress = controller.get_state()["fetch_progress"]

    assert progress["status"] == "bad"
    assert progress["promotion_evidence"] is False
    assert "Broad planner-routed UAT is incomplete" in progress["headline"]
    assert progress["recommended_next_action"] == "repair_planner_routed_recovery_reaim_executor"
    assert progress["planner_seeded_gate"]["current_blocking"] is True
    assert progress["planner_seeded_gate"]["first_failure"]["route_label"] == "recovery_or_reaim"


def test_dashboard_fetch_progress_targeted_replay_repairs_latest_seeded_failure(tmp_path, monkeypatch):
    session_root = tmp_path / "session"
    monkeypatch.setattr(dashboard_service, "SESSION_ROOT", session_root)
    controller = _make_controller(tmp_path)
    controller._fetch_progress_cache = {}
    controller._fetch_progress_cache_at = 0.0

    _write_json(
        session_root / "fetch_evidence" / "fetch_seeded_gate_evidence_analyzer" / "evidence_summary.json",
        {
            "type": "fetch_seeded_gate_evidence_analyzer",
            "campaign_id": "old_guarded_live_evidence",
            "recommended_next_action": "package_mobile_visual_uat",
            "promotion_evidence": True,
            "seeded_shadow_gate": {
                "campaign_id": "old_guarded_seeded_gate",
                "pass_count": 6,
                "fail_count": 0,
                "model_provenance_valid": True,
                "model_provenance_invalid_count": 0,
            },
        },
    )
    _write_json(
        session_root / "broad_gate" / "fetch_planner_seeded_generalization_gate" / "gate_summary.json",
        {
            "type": "fetch_planner_seeded_generalization_gate",
            "campaign_id": "broad_gate",
            "dry_run": False,
            "pass": False,
            "promotion_evidence": False,
            "replay_first_failure": {
                "scene_id": "seed20260627_scene04_recovery_or_reaim",
                "route_label": "recovery_or_reaim",
                "returncode": 2,
            },
            "replay_summary": {"mission_pass_count": 0, "mission_fail_count": 1},
        },
    )
    _write_json(
        session_root / "targeted_repair" / "fetch_planner_route_replay_batch" / "batch_summary.json",
        {
            "type": "fetch_planner_route_replay_batch",
            "campaign_id": "targeted_repair",
            "dry_run": False,
            "pass": True,
            "selected_count": 1,
            "mission_pass_count": 1,
            "visual_package_pass_count": 1,
            "rows": [
                {
                    "scene_id": "seed20260627_scene04_recovery_or_reaim",
                    "route_label": "recovery_or_reaim",
                    "route_executor": "bounded_recovery_reaim",
                    "returncode": 0,
                    "mission": {"pass": True},
                    "visual_package": {"pass": True},
                }
            ],
        },
    )

    progress = controller.get_state()["fetch_progress"]

    assert progress["status"] == "warn"
    assert progress["promotion_evidence"] is False
    assert "Targeted recovery_or_reaim repair passed" in progress["headline"]
    assert progress["recommended_next_action"] == "rerun_full_planner_routed_seeded_gate"
    assert progress["planner_seeded_gate"]["current_blocking"] is False
    assert progress["planner_route_replay_batch"]["repairs_latest_seeded_failure"] is True


def test_dashboard_fetch_progress_latest_route_replay_keeps_seeded_gate_pending_after_dry_run(tmp_path, monkeypatch):
    session_root = tmp_path / "session"
    monkeypatch.setattr(dashboard_service, "SESSION_ROOT", session_root)
    controller = _make_controller(tmp_path)
    controller._fetch_progress_cache = {}
    controller._fetch_progress_cache_at = 0.0

    _write_json(
        session_root / "fetch_evidence" / "fetch_seeded_gate_evidence_analyzer" / "evidence_summary.json",
        {
            "type": "fetch_seeded_gate_evidence_analyzer",
            "campaign_id": "old_guarded_live_evidence",
            "recommended_next_action": "package_mobile_visual_uat",
            "promotion_evidence": True,
            "seeded_shadow_gate": {
                "campaign_id": "old_guarded_seeded_gate",
                "pass_count": 6,
                "fail_count": 0,
                "model_provenance_valid": True,
                "model_provenance_invalid_count": 0,
            },
        },
    )
    _write_json(
        session_root / "dry_parent" / "fetch_planner_seeded_generalization_gate" / "gate_summary.json",
        {
            "type": "fetch_planner_seeded_generalization_gate",
            "campaign_id": "dry_parent",
            "dry_run": True,
            "pass": True,
            "promotion_evidence": False,
        },
    )
    _write_json(
        session_root / "latest_route_replay" / "fetch_planner_route_replay_batch" / "batch_summary.json",
        {
            "type": "fetch_planner_route_replay_batch",
            "campaign_id": "latest_route_replay",
            "dry_run": False,
            "pass": True,
            "selected_count": 1,
            "mission_pass_count": 1,
            "visual_package_pass_count": 1,
            "rows": [
                {
                    "scene_id": "seed20260627_scene04_recovery_or_reaim",
                    "route_label": "recovery_or_reaim",
                    "route_executor": "bounded_recovery_reaim",
                    "returncode": 0,
                    "mission": {"pass": True},
                    "visual_package": {"pass": True},
                }
            ],
        },
    )

    progress = controller.get_state()["fetch_progress"]

    assert progress["status"] == "warn"
    assert progress["promotion_evidence"] is False
    assert "Latest planner-route replay batch passed 1/1" in progress["headline"]
    assert progress["recommended_next_action"] == "rerun_full_planner_routed_seeded_gate"
    assert progress["planner_route_replay_batch"]["current_pending_seeded_gate"] is True


def test_dashboard_fetch_progress_green_visual_replay_supersedes_incomplete_seeded_parent(tmp_path, monkeypatch):
    session_root = tmp_path / "session"
    monkeypatch.setattr(dashboard_service, "SESSION_ROOT", session_root)
    controller = _make_controller(tmp_path)
    controller._fetch_progress_cache = {}
    controller._fetch_progress_cache_at = 0.0

    _write_json(
        session_root / "fetch_evidence" / "fetch_seeded_gate_evidence_analyzer" / "evidence_summary.json",
        {
            "type": "fetch_seeded_gate_evidence_analyzer",
            "campaign_id": "old_guarded_live_evidence",
            "recommended_next_action": "package_mobile_visual_uat",
            "promotion_evidence": True,
            "seeded_shadow_gate": {
                "campaign_id": "old_guarded_seeded_gate",
                "pass_count": 6,
                "fail_count": 0,
                "model_provenance_valid": True,
                "model_provenance_invalid_count": 0,
            },
        },
    )
    _write_json(
        session_root / "mission_only_parent" / "fetch_planner_seeded_generalization_gate" / "gate_summary.json",
        {
            "type": "fetch_planner_seeded_generalization_gate",
            "campaign_id": "mission_only_parent",
            "dry_run": False,
            "pass": False,
            "promotion_evidence": False,
            "planner_gate_pass": True,
            "replay_pass": False,
            "replay_first_failure": {},
            "replay_summary": {
                "selected_count": 4,
                "mission_pass_count": 4,
                "mission_fail_count": 0,
                "visual_package_pass_count": 0,
            },
        },
    )
    _write_json(
        session_root / "visual_recheck" / "fetch_planner_route_replay_batch" / "batch_summary.json",
        {
            "type": "fetch_planner_route_replay_batch",
            "campaign_id": "visual_recheck",
            "dry_run": False,
            "pass": True,
            "selected_count": 4,
            "mission_pass_count": 4,
            "visual_package_pass_count": 4,
            "rows": [
                {
                    "scene_id": "seed20260627_scene04_recovery_or_reaim",
                    "route_label": "recovery_or_reaim",
                    "route_executor": "bounded_recovery_reaim",
                    "returncode": 0,
                    "mission": {"pass": True},
                    "visual_package": {"pass": True},
                },
                {
                    "scene_id": "seed20260627_scene09_fetch_ready_local",
                    "route_label": "fetch_ready_local",
                    "route_executor": "local_fetch_to_pose",
                    "returncode": 0,
                    "mission": {"pass": True},
                    "visual_package": {"pass": True},
                },
            ],
        },
    )

    progress = controller.get_state()["fetch_progress"]

    assert progress["status"] == "warn"
    assert progress["promotion_evidence"] is False
    assert "Latest planner-route replay batch passed 4/4" in progress["headline"]
    assert progress["recommended_next_action"] == "rerun_full_planner_routed_seeded_gate"
    assert progress["planner_seeded_gate"]["current_blocking"] is False
    assert progress["planner_route_replay_batch"]["current_pending_seeded_gate"] is True
    assert progress["planner_route_replay_batch"]["supersedes_incomplete_seeded_gate"] is True


def test_dashboard_fetch_progress_prefers_terminal_stage_audit_over_stale_seeded_context(tmp_path, monkeypatch):
    session_root = tmp_path / "session"
    monkeypatch.setattr(dashboard_service, "SESSION_ROOT", session_root)
    controller = _make_controller(tmp_path)
    controller._fetch_progress_cache = {}
    controller._fetch_progress_cache_at = 0.0

    _write_json(
        session_root / "fetch_evidence" / "fetch_seeded_gate_evidence_analyzer" / "evidence_summary.json",
        {
            "type": "fetch_seeded_gate_evidence_analyzer",
            "campaign_id": "stale_fetch_evidence",
            "saved_anchor_context": {
                "campaign_id": "saved_anchor_campaign",
                "candidate_rows": [{"layout_id": "zero", "pass": True}],
            },
            "seeded_shadow_gate": {"campaign_id": "seeded_gate", "pass_count": 1, "fail_count": 0},
        },
    )
    _write_json(
        session_root / "stage_audit" / "fetch_saved_anchor_setup_contact_audit" / "audit_summary.json",
        {
            "type": "fetch_saved_anchor_setup_contact_audit",
            "campaign_id": "fresh_stage_audit",
            "overall_interpretation": "guarded_live_terminal_probe_ready",
            "stage_quality_green": False,
            "saved_anchor_count": 3,
            "stage_quality_pass_count": 2,
            "setup_contact_blocker_count": 0,
            "setup_capture_blocker_count": 0,
            "first_contact_blocker_count": 0,
            "push_coast_blocker_count": 0,
            "invalid_model_provenance_count": 0,
            "saved_anchor_pass_with_contact_watch_count": 1,
            "saved_anchors": [
                {"layout": "zero", "pass": True, "delivery_pass": True, "quality_classification": "clean_pass"},
                {"layout": "left05", "pass": True, "delivery_pass": True, "quality_classification": "pass_with_capture_quality_watch"},
                {"layout": "right05", "pass": False, "delivery_pass": False, "quality_classification": "terminal_arrival_candidate"},
            ],
        },
    )

    progress = controller.get_state()["fetch_progress"]

    assert progress["status"] == "warn"
    assert "terminal-arrival candidate" in progress["headline"]
    assert progress["stage_quality_audit"]["terminal_arrival_candidate_count"] == 1
    assert progress["stage_quality_audit"]["invalid_model_provenance_count"] == 0


def test_browser_dashboard_promotes_golf_fetch_as_featured_demo():
    js_path = REPO_ROOT / "runtime/dashboard/browser_dashboard.js"
    js = js_path.read_text(encoding="utf-8")

    golf_demo = "{ id: 'golf_ball_circle_delivery_uat', label: 'Random Golf-Ball Delivery', randomLayout: true, randomProfile: 'local_visual_v1' }"
    corral_demo = "{ id: 'corral_single_ball_place', label: 'Single-Ball Corral' }"
    gather_demo = "{ id: 'gather_three_ball_zone', label: 'Gather 3 Ball Zone' }"
    route_demo = "{ id: 'visit_route_planning', label: 'LLM Route Planning' }"

    assert golf_demo in js
    assert "{ id: 'corral_single_ball_place', label: 'Single-Ball Corral' }" in js
    assert "{ id: 'gather_three_ball_zone', label: 'Gather 3 Ball Zone' }" in js
    assert "{ id: 'visit_route_planning', label: 'LLM Route Planning' }" in js
    assert js.index(golf_demo) < js.index(corral_demo)
    assert js.index(corral_demo) < js.index(gather_demo)
    assert js.index(gather_demo) < js.index(route_demo)
    assert "renderMissionSnapshot(state);" in js
    assert "final_three_ball_corral_pass" in js
    assert "data-demo-random-layout" in js
    assert "data-demo-random-profile" in js
    assert "random_layout: true" in js
    assert "random_profile: randomProfile || 'corridor_contact_v1'" in js


def test_browser_dashboard_includes_multi_ball_mission_snapshot_panel():
    html_path = REPO_ROOT / "runtime/dashboard/browser_dashboard.html"
    html = html_path.read_text(encoding="utf-8")

    assert 'id="mission-summary"' in html
    assert 'id="retrieved-count-detail"' in html
    assert 'id="corral-audit-list"' in html
    assert "Gather 3 Ball Zone" in html


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


def test_find_free_port_skips_excluded_ports(monkeypatch):
    monkeypatch.setattr(dashboard_service, "can_bind_localhost_port", lambda _port: True)

    chosen = dashboard_service.find_free_port(14500, 14502, exclude_ports={14500, 14501})

    assert chosen == 14502


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


def test_request_scenario_run_three_ball_gather_queues_after_sim_reset(monkeypatch, tmp_path):
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

    status, payload = controller.request_scenario_run("gather_three_ball_zone")

    assert status == 202
    assert payload["accepted"] is True
    assert "queued after sim reset" in payload["message"]
    assert controller.pending_scenario_id == "gather_three_ball_zone"
    assert started
    assert started[0].target == controller._reset_environment_worker


def test_request_object_centric_zero_from_stopped_starts_environment_and_queues_scenario(monkeypatch, tmp_path):
    controller = _make_controller(tmp_path)
    controller.state["environment_state"] = "stopped"
    controller.state["scenario_state"] = "idle"
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

    status, payload = controller.request_scenario_run(dashboard_service.OBJECT_CENTRIC_ZERO_SCENARIO_ID)

    assert status == 202
    assert payload["accepted"] is True
    assert "queued after environment start" in payload["message"]
    assert controller.pending_scenario_id == dashboard_service.OBJECT_CENTRIC_ZERO_SCENARIO_ID
    assert controller.state["environment_state"] == "starting"
    assert controller.state["world_file"] == dashboard_service.SHORT_TURF_WORLD_FILE
    assert controller.state["surface_profile"] == "short_turf"
    assert controller.state["robot_sdf_name"] == dashboard_service.CORRAL_ROBOT_SDF_NAME
    assert started
    assert started[0].target == controller._start_environment_worker


def test_request_golf_fetch_random_cta_from_stopped_preserves_random_override(monkeypatch, tmp_path):
    controller = _make_controller(tmp_path)
    controller.state["environment_state"] = "stopped"
    controller.state["scenario_state"] = "idle"
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

    status, payload = controller.request_scenario_run(
        dashboard_service.GOLF_BALL_CIRCLE_DELIVERY_SCENARIO_ID,
        {"random_layout": True, "random_seed": "456"},
    )

    assert status == 202
    assert payload["accepted"] is True
    assert "queued after environment start" in payload["message"]
    assert controller.pending_scenario_id == dashboard_service.GOLF_BALL_CIRCLE_DELIVERY_SCENARIO_ID
    assert controller.pending_scenario_overrides["random_layout"] is True
    assert controller.pending_scenario_overrides["random_seed"] == 456
    assert controller.pending_scenario_overrides["random_profile"] == dashboard_service.GOLF_BALL_RANDOM_PROFILE_CORRIDOR_CONTACT
    assert controller.pending_scenario_overrides["world_file"] == dashboard_service.CALIBRATED_GOLF_TURF_WORLD_FILE
    assert controller.pending_scenario_overrides["surface_profile"] == "calibrated_golf_turf"
    assert started
    assert started[0].target == controller._start_environment_worker


def test_request_golf_fetch_random_cta_accepts_local_visual_profile(monkeypatch, tmp_path):
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
        dashboard_service.GOLF_BALL_CIRCLE_DELIVERY_SCENARIO_ID,
        {
            "random_layout": True,
            "random_profile": dashboard_service.GOLF_BALL_RANDOM_PROFILE_LOCAL_VISUAL,
        },
    )

    assert status == 202
    assert payload["accepted"] is True
    assert controller.pending_scenario_overrides["random_profile"] == dashboard_service.GOLF_BALL_RANDOM_PROFILE_LOCAL_VISUAL
    assert started
    assert started[0].target == controller._reset_environment_worker


def test_request_golf_fetch_random_cta_rejects_unknown_profile(tmp_path):
    controller = _make_controller(tmp_path)

    status, payload = controller.request_scenario_run(
        dashboard_service.GOLF_BALL_CIRCLE_DELIVERY_SCENARIO_ID,
        {"random_layout": True, "random_profile": "wide_open_v0"},
    )

    assert status == 400
    assert payload["accepted"] is False
    assert payload["error"] == "unknown random_profile: wide_open_v0"


def test_request_golf_fetch_planner_gated_random_accepts_mode(monkeypatch, tmp_path):
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
        dashboard_service.GOLF_BALL_CIRCLE_DELIVERY_SCENARIO_ID,
        {
            "planner_gated_random": True,
            "planner_mode": dashboard_service.fetch_planner_gate.PLANNER_MODE_LLM_SHADOW,
            "random_seed": "456",
        },
    )

    assert status == 202
    assert payload["accepted"] is True
    assert controller.pending_scenario_overrides["planner_gated_random"] is True
    assert controller.pending_scenario_overrides["planner_mode"] == dashboard_service.fetch_planner_gate.PLANNER_MODE_LLM_SHADOW
    assert controller.pending_scenario_overrides["random_seed"] == 456
    assert started


def test_request_golf_fetch_planner_gated_random_accepts_supervised_mode(monkeypatch, tmp_path):
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
        dashboard_service.GOLF_BALL_CIRCLE_DELIVERY_SCENARIO_ID,
        {
            "planner_gated_random": True,
            "planner_mode": dashboard_service.fetch_planner_gate.PLANNER_MODE_LLM_SUPERVISED_GUARDED,
            "random_seed": "456",
        },
    )

    assert status == 202
    assert payload["accepted"] is True
    assert controller.pending_scenario_overrides["planner_mode"] == (
        dashboard_service.fetch_planner_gate.PLANNER_MODE_LLM_SUPERVISED_GUARDED
    )
    assert started


def test_request_golf_fetch_accepts_guarded_live_overrides(monkeypatch, tmp_path):
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
        dashboard_service.GOLF_BALL_CIRCLE_DELIVERY_SCENARIO_ID,
        {
            "planner_gated_random": True,
            "planner_scene_json": "ros2_config/fetch_planner_scene_sets/mixed_fetch_planner_v1.json",
            "planner_scene_id": "frozen_fetch_ready_local_01",
            "target_layout_json": "ros2_config/target_layouts/golf_ball_circle_delivery_zero.json",
            "gather_control_family": "ai_push_coast_servo_v1",
            "ai_push_coast_mode": "guarded_live",
        },
    )

    assert status == 202
    assert payload["accepted"] is True
    assert controller.pending_scenario_overrides["planner_scene_id"] == "frozen_fetch_ready_local_01"
    assert (
        controller.pending_scenario_overrides["target_layout_json"].replace("\\", "/")
        == "ros2_config/target_layouts/golf_ball_circle_delivery_zero.json"
    )
    assert controller.pending_scenario_overrides["gather_control_family"] == "ai_push_coast_servo_v1"
    assert controller.pending_scenario_overrides["ai_push_coast_mode"] == "guarded_live"
    assert started


def test_request_golf_fetch_rejects_unknown_ai_mode(tmp_path):
    controller = _make_controller(tmp_path)

    status, payload = controller.request_scenario_run(
        dashboard_service.GOLF_BALL_CIRCLE_DELIVERY_SCENARIO_ID,
        {"ai_push_coast_mode": "free_drive"},
    )

    assert status == 400
    assert payload["accepted"] is False
    assert payload["error"] == "unknown ai_push_coast_mode: free_drive"


def test_dashboard_planner_handoff_replays_requested_frozen_scene(monkeypatch, tmp_path):
    monkeypatch.setattr(dashboard_service, "SESSION_ROOT", tmp_path / "session")
    controller = _make_controller(tmp_path)

    result = controller._run_dashboard_planner_handoff(
        overrides={
            "planner_scene_json": "ros2_config/fetch_planner_scene_sets/mixed_fetch_planner_v1.json",
            "planner_scene_id": "frozen_fetch_ready_local_01",
            "planner_scene_set": "mixed_fetch_planner_v1",
            "planner_mode": dashboard_service.fetch_planner_gate.PLANNER_MODE_DETERMINISTIC,
        }
    )

    assert result["scene"]["scene_id"] == "frozen_fetch_ready_local_01"
    assert result["decision"]["route_label"] == dashboard_service.fetch_planner_gate.ROUTE_FETCH_READY
    assert result["decision"]["should_dispatch_fetch_to_pose"] is True


def test_request_golf_fetch_planner_gated_random_rejects_unknown_mode(tmp_path):
    controller = _make_controller(tmp_path)

    status, payload = controller.request_scenario_run(
        dashboard_service.GOLF_BALL_CIRCLE_DELIVERY_SCENARIO_ID,
        {"planner_gated_random": True, "planner_mode": "free_drive"},
    )

    assert status == 400
    assert payload["accepted"] is False
    assert payload["error"] == "unknown planner_mode: free_drive"


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


def test_robot_sdf_name_for_startup_uses_pending_three_ball_gather_scenario(tmp_path):
    controller = _make_controller(tmp_path)
    controller.pending_scenario_id = "gather_three_ball_zone"

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


def test_request_start_accepts_environment_profile_overrides(monkeypatch, tmp_path):
    controller = _make_controller(tmp_path)
    controller.state["environment_state"] = "stopped"
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

    status, payload = controller.request_start(
        {
            "scenario_id": "corral_single_ball_place",
            "world_file": "yolo_test_world_v6_clean_uat_short_grass.world",
            "surface_profile": "short_grass",
        }
    )

    assert status == 202
    assert payload["accepted"] is True
    assert controller.state["world_file"] == "yolo_test_world_v6_clean_uat_short_grass.world"
    assert controller.state["surface_profile"] == "short_grass"
    assert controller.state["robot_sdf_name"] == dashboard_service.CORRAL_ROBOT_SDF_NAME
    assert started


def test_request_reset_sim_accepts_environment_profile_overrides(monkeypatch, tmp_path):
    controller = _make_controller(tmp_path)
    controller.state["environment_state"] = "environment_ready"
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

    status, payload = controller.request_reset_sim(
        {
            "scenario_id": "gather_three_ball_zone",
            "world_file": "yolo_test_world_v6_clean_uat_short_turf.world",
            "surface_profile": "short_turf",
        }
    )

    assert status == 202
    assert payload["accepted"] is True
    assert controller.state["world_file"] == "yolo_test_world_v6_clean_uat_short_turf.world"
    assert controller.state["surface_profile"] == "short_turf"
    assert controller.state["robot_sdf_name"] == dashboard_service.CORRAL_ROBOT_SDF_NAME
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


def test_run_object_centric_zero_dashboard_scenario_uses_saved_layout_and_policy(tmp_path, monkeypatch):
    controller = _make_controller(tmp_path)
    controller.state["dashboard_url"] = "http://127.0.0.1:8860/"
    controller._scenarios_dir = lambda: tmp_path / "scenarios"
    controller._current_validation_dir = lambda: tmp_path / "validation"
    controller._visit_mission_runtime_state = lambda: {"proof_state": "completed"}
    controller._gather_mission_runtime_state = lambda: {
        "mission_phase": "completed",
        "mission_status": "completed",
        "gather_phase": "completed",
        "surface_profile": "short_turf",
    }
    controller._scenario_env = lambda _scenario: {
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

    monkeypatch.setattr(dashboard_service.subprocess, "Popen", lambda command, **kwargs: _FakeProc(command, kwargs["stdout"]))

    scenario = dashboard_service.SCENARIOS_BY_ID[dashboard_service.OBJECT_CENTRIC_ZERO_SCENARIO_ID]
    result = controller._run_gather_mission_scenario(scenario)

    command = captured["cmd"]
    assert command[command.index("--scenario-id") + 1] == "corral_single_ball_place"
    assert command[command.index("--gather-control-family") + 1] == "object_centric_gather_policy_v1"
    assert command[command.index("--target-layout-json") + 1] == dashboard_service.OBJECT_CENTRIC_ZERO_TARGET_LAYOUT_JSON
    assert command[command.index("--max-retries-per-target") + 1] == "2"
    assert result["scenario_id"] == dashboard_service.OBJECT_CENTRIC_ZERO_SCENARIO_ID
    assert result["runner_scenario_id"] == "corral_single_ball_place"
    assert result["gather_control_family"] == "object_centric_gather_policy_v1"


def test_run_golf_fetch_cta_random_layout_uses_bounded_generated_layout(tmp_path, monkeypatch):
    controller = _make_controller(tmp_path)
    controller.state["dashboard_url"] = "http://127.0.0.1:8860/"
    controller._scenarios_dir = lambda: tmp_path / "scenarios"
    controller._current_validation_dir = lambda: tmp_path / "validation"
    controller.active_scenario_overrides = {
        "random_layout": True,
        "random_profile": dashboard_service.GOLF_BALL_RANDOM_PROFILE_LOCAL_VISUAL,
        "random_seed": 123,
    }
    controller._visit_mission_runtime_state = lambda: {"proof_state": "completed"}
    controller._gather_mission_runtime_state = lambda: {
        "mission_phase": "completed",
        "mission_status": "completed",
        "gather_phase": "completed",
        "surface_profile": "calibrated_golf_turf",
    }
    controller._scenario_env = lambda _scenario: {
        "WORLD_FILE": "yolo_test_world_v6_calibrated_golf_turf.world",
        "CHASECAR_SURFACE_PROFILE": "calibrated_golf_turf",
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

    monkeypatch.setattr(dashboard_service.subprocess, "Popen", lambda command, **kwargs: _FakeProc(command, kwargs["stdout"]))

    scenario = dashboard_service.SCENARIOS_BY_ID[dashboard_service.GOLF_BALL_CIRCLE_DELIVERY_SCENARIO_ID]
    result = controller._run_gather_mission_scenario(scenario)

    command = captured["cmd"]
    assert str(command[1]).endswith("golf_ball_circle_delivery_demo_runner.py")
    assert "--target-layout-json" in command
    layout_path = Path(command[command.index("--target-layout-json") + 1])
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    target = layout["targets"][0]
    bounds = layout["random_draw"]["bounds"]
    assert layout["random_profile"] == dashboard_service.GOLF_BALL_RANDOM_PROFILE_LOCAL_VISUAL
    assert layout["random_draw"]["random_profile"] == dashboard_service.GOLF_BALL_RANDOM_PROFILE_LOCAL_VISUAL
    assert layout["random_draw"]["seed"] == 123
    target_pose = layout["random_draw"]["target_pose"]
    robot_pose = layout["random_draw"]["robot_pose"]
    initial_distance = math.hypot(target_pose["x"] - target["forward_m"], target_pose["y"] - target["lateral_m"])
    assert initial_distance >= target_pose["radius_m"] + bounds["min_initial_delivery_margin_m"]
    assert bounds["distance_min_m"] <= initial_distance <= bounds["distance_max_m"]
    assert bounds["angle_min_deg"] <= layout["random_draw"]["ball_target_angle_deg"] <= bounds["angle_max_deg"]
    assert bounds["robot_standoff_min_m"] <= layout["random_draw"]["robot_standoff_m"] <= bounds["robot_standoff_max_m"]
    assert bounds["robot_lateral_min_m"] <= layout["random_draw"]["robot_lateral_offset_m"] <= bounds["robot_lateral_max_m"]
    assert bounds["robot_yaw_error_min_deg"] <= layout["random_draw"]["robot_yaw_error_deg"] <= bounds["robot_yaw_error_max_deg"]
    assert bounds["world_x_min_m"] <= target["forward_m"] <= bounds["world_x_max_m"]
    assert bounds["world_y_min_m"] <= target["lateral_m"] <= bounds["world_y_max_m"]
    assert bounds["world_x_min_m"] <= robot_pose["x"] <= bounds["world_x_max_m"]
    assert bounds["world_y_min_m"] <= robot_pose["y"] <= bounds["world_y_max_m"]
    assert "--robot-x" in command
    assert "--robot-y" in command
    assert "--robot-yaw" in command
    assert command[command.index("--artifact-kind") + 1] == dashboard_service.GOLF_BALL_CIRCLE_DELIVERY_RANDOM_ARTIFACT_KIND
    assert result["random_layout"] is True
    assert result["random_profile"] == dashboard_service.GOLF_BALL_RANDOM_PROFILE_LOCAL_VISUAL
    assert result["random_draw"]["seed"] == 123
    assert result["random_draw"]["robot_ball_separation_m"] >= bounds["min_robot_ball_separation_m"]
    assert result["target_layout_json"] == str(layout_path)


def test_run_golf_fetch_planner_gated_non_fetch_route_does_not_dispatch_local_fetch(tmp_path, monkeypatch):
    controller = _make_controller(tmp_path)
    controller.state["dashboard_url"] = "http://127.0.0.1:8860/"
    controller._scenarios_dir = lambda: tmp_path / "scenarios"
    controller._current_validation_dir = lambda: tmp_path / "validation"
    controller.active_scenario_overrides = {
        "planner_gated_random": True,
        "planner_mode": dashboard_service.fetch_planner_gate.PLANNER_MODE_DETERMINISTIC,
        "random_seed": 123,
    }
    controller._visit_mission_runtime_state = lambda: {"proof_state": "completed"}
    controller._gather_mission_runtime_state = lambda: {"surface_profile": "calibrated_golf_turf"}
    controller._scenario_env = lambda _scenario: {
        "WORLD_FILE": "yolo_test_world_v6_calibrated_golf_turf.world",
        "CHASECAR_SURFACE_PROFILE": "calibrated_golf_turf",
    }
    scene = next(
        item for item in dashboard_service.fetch_planner_gate.generate_random_scenes(seed=123, random_cases=10)
        if item["expected_route_label"] == dashboard_service.fetch_planner_gate.ROUTE_NO_GO
    )
    monkeypatch.setattr(dashboard_service.fetch_planner_gate, "generate_dashboard_scene", lambda **_kwargs: scene)

    def _unexpected_popen(*_args, **_kwargs):
        raise AssertionError("local fetch runner should not start for non-fetch planner routes")

    monkeypatch.setattr(dashboard_service.subprocess, "Popen", _unexpected_popen)

    scenario = dashboard_service.SCENARIOS_BY_ID[dashboard_service.GOLF_BALL_CIRCLE_DELIVERY_SCENARIO_ID]
    result = controller._run_gather_mission_scenario(scenario)

    decision = result["planner_handoff"]["decision"]
    assert result["pass"] is True
    assert result["planner_gated_random"] is True
    assert result["local_fetch_dispatched"] is False
    assert decision["route_label"] == dashboard_service.fetch_planner_gate.ROUTE_NO_GO
    assert result["route_label"] == dashboard_service.fetch_planner_gate.ROUTE_NO_GO
    assert result["route_executor"] == dashboard_service.fetch_planner_gate.ROUTE_EXECUTOR_NO_GO
    assert result["planner_route_executed"] is True
    assert result["planner_route_execution"]["outcome"] == "safe_no_go_selected"
    assert result["forward_only_pre_contact_required"] is False
    assert result["artifacts"]["planner_decision"]
    assert Path(result["artifacts"]["planner_decision"]).exists()


def test_run_golf_fetch_planner_gated_scan_route_executes_without_local_fetch(tmp_path, monkeypatch):
    controller = _make_controller(tmp_path)
    controller.state["dashboard_url"] = "http://127.0.0.1:8860/"
    controller._scenarios_dir = lambda: tmp_path / "scenarios"
    controller._current_validation_dir = lambda: tmp_path / "validation"
    controller.active_scenario_overrides = {
        "planner_gated_random": True,
        "planner_mode": dashboard_service.fetch_planner_gate.PLANNER_MODE_DETERMINISTIC,
        "random_seed": 123,
    }
    controller._visit_mission_runtime_state = lambda: {"proof_state": "completed"}
    controller._gather_mission_runtime_state = lambda: {"surface_profile": "calibrated_golf_turf"}
    controller._scenario_env = lambda _scenario: {
        "WORLD_FILE": "yolo_test_world_v6_calibrated_golf_turf.world",
        "CHASECAR_SURFACE_PROFILE": "calibrated_golf_turf",
    }
    scene = next(
        item for item in dashboard_service.fetch_planner_gate.generate_random_scenes(seed=20260603, random_cases=20)
        if item["expected_route_label"] == dashboard_service.fetch_planner_gate.ROUTE_SCAN_OR_PERCEIVE
    )
    monkeypatch.setattr(dashboard_service.fetch_planner_gate, "generate_dashboard_scene", lambda **_kwargs: scene)

    def _unexpected_popen(*_args, **_kwargs):
        raise AssertionError("local fetch runner should not start for scan/perceive planner routes")

    monkeypatch.setattr(dashboard_service.subprocess, "Popen", _unexpected_popen)

    scenario = dashboard_service.SCENARIOS_BY_ID[dashboard_service.GOLF_BALL_CIRCLE_DELIVERY_SCENARIO_ID]
    result = controller._run_gather_mission_scenario(scenario)

    decision = result["planner_handoff"]["decision"]
    assert result["pass"] is True
    assert result["planner_gated_random"] is True
    assert result["local_fetch_dispatched"] is False
    assert decision["route_label"] == dashboard_service.fetch_planner_gate.ROUTE_SCAN_OR_PERCEIVE
    assert result["route_label"] == dashboard_service.fetch_planner_gate.ROUTE_SCAN_OR_PERCEIVE
    assert result["route_executor"] == dashboard_service.fetch_planner_gate.ROUTE_EXECUTOR_SCAN
    assert result["planner_route_executed"] is True
    assert result["planner_route_execution"]["outcome"] == "scan_or_perception_refresh_selected"
    assert result["forward_only_pre_contact_required"] is False
    assert result["target_layout_json"] == ""
    assert result["artifacts"]["planner_decision"]
    assert Path(result["artifacts"]["planner_decision"]).exists()


def test_run_golf_fetch_planner_gated_fetch_ready_route_dispatches_layout(tmp_path, monkeypatch):
    controller = _make_controller(tmp_path)
    controller.state["dashboard_url"] = "http://127.0.0.1:8860/"
    controller._scenarios_dir = lambda: tmp_path / "scenarios"
    controller._current_validation_dir = lambda: tmp_path / "validation"
    controller.active_scenario_overrides = {
        "planner_gated_random": True,
        "planner_mode": dashboard_service.fetch_planner_gate.PLANNER_MODE_DETERMINISTIC,
        "random_seed": 456,
    }
    controller._visit_mission_runtime_state = lambda: {"proof_state": "completed"}
    controller._gather_mission_runtime_state = lambda: {
        "mission_phase": "completed",
        "mission_status": "completed",
        "gather_phase": "completed",
        "surface_profile": "calibrated_golf_turf",
    }
    controller._scenario_env = lambda _scenario: {
        "WORLD_FILE": "yolo_test_world_v6_calibrated_golf_turf.world",
        "CHASECAR_SURFACE_PROFILE": "calibrated_golf_turf",
    }
    scene = next(
        item for item in dashboard_service.fetch_planner_gate.generate_random_scenes(seed=456, random_cases=10)
        if item["expected_route_label"] == dashboard_service.fetch_planner_gate.ROUTE_FETCH_READY
    )
    monkeypatch.setattr(dashboard_service.fetch_planner_gate, "generate_dashboard_scene", lambda **_kwargs: scene)

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

    monkeypatch.setattr(dashboard_service.subprocess, "Popen", lambda command, **kwargs: _FakeProc(command, kwargs["stdout"]))

    scenario = dashboard_service.SCENARIOS_BY_ID[dashboard_service.GOLF_BALL_CIRCLE_DELIVERY_SCENARIO_ID]
    result = controller._run_gather_mission_scenario(scenario)

    command = captured["cmd"]
    layout_path = Path(command[command.index("--target-layout-json") + 1])
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    assert result["pass"] is True
    assert result["planner_gated_random"] is True
    assert result["local_fetch_dispatched"] is True
    assert result["route_label"] == dashboard_service.fetch_planner_gate.ROUTE_FETCH_READY
    assert result["route_executor"] == dashboard_service.fetch_planner_gate.ROUTE_EXECUTOR_LOCAL_FETCH
    assert result["planner_route_executed"] is True
    assert result["forward_only_pre_contact_required"] is True
    assert result["forward_only_pre_contact"] is True
    assert result["random_profile"] == dashboard_service.fetch_planner_gate.PLANNER_MIXED_PROFILE
    assert layout["layout_family"] == "planner_gated_fetch_ready"
    assert layout["planner_route_label"] == dashboard_service.fetch_planner_gate.ROUTE_FETCH_READY
    assert layout["route_executor"] == dashboard_service.fetch_planner_gate.ROUTE_EXECUTOR_LOCAL_FETCH
    assert layout["planner_scene"]["scene_id"] == scene["scene_id"]
    assert "--robot-x" in command
    assert "--planner-route-label" in command
    assert command[command.index("--planner-route-label") + 1] == dashboard_service.fetch_planner_gate.ROUTE_FETCH_READY
    assert "--route-executor" in command
    assert command[command.index("--route-executor") + 1] == dashboard_service.fetch_planner_gate.ROUTE_EXECUTOR_LOCAL_FETCH
    assert "--forward-only-pre-contact-required" in command
    assert "--drive-mode" in command
    assert command[command.index("--drive-mode") + 1] == "line_servo"
    assert "--stop-on-delivery" in command
    assert command[command.index("--delivery-stop-radius-m") + 1] == "0.200000"
    assert command[command.index("--artifact-kind") + 1] == dashboard_service.GOLF_BALL_CIRCLE_DELIVERY_RANDOM_ARTIFACT_KIND


def test_run_golf_fetch_planner_gated_recovery_route_dispatches_forward_layout(tmp_path, monkeypatch):
    controller = _make_controller(tmp_path)
    controller.state["dashboard_url"] = "http://127.0.0.1:8860/"
    controller._scenarios_dir = lambda: tmp_path / "scenarios"
    controller._current_validation_dir = lambda: tmp_path / "validation"
    controller.active_scenario_overrides = {
        "planner_gated_random": True,
        "planner_mode": dashboard_service.fetch_planner_gate.PLANNER_MODE_DETERMINISTIC,
        "random_seed": 20260603,
    }
    controller._visit_mission_runtime_state = lambda: {"proof_state": "completed"}
    controller._gather_mission_runtime_state = lambda: {
        "mission_phase": "completed",
        "mission_status": "completed",
        "gather_phase": "completed",
        "surface_profile": "calibrated_golf_turf",
    }
    controller._scenario_env = lambda _scenario: {
        "WORLD_FILE": "yolo_test_world_v6_calibrated_golf_turf.world",
        "CHASECAR_SURFACE_PROFILE": "calibrated_golf_turf",
    }
    scene = next(
        item for item in dashboard_service.fetch_planner_gate.generate_random_scenes(seed=20260603, random_cases=20)
        if item["expected_route_label"] == dashboard_service.fetch_planner_gate.ROUTE_RECOVERY_OR_REAIM
    )
    monkeypatch.setattr(dashboard_service.fetch_planner_gate, "generate_dashboard_scene", lambda **_kwargs: scene)

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

    monkeypatch.setattr(dashboard_service.subprocess, "Popen", lambda command, **kwargs: _FakeProc(command, kwargs["stdout"]))

    scenario = dashboard_service.SCENARIOS_BY_ID[dashboard_service.GOLF_BALL_CIRCLE_DELIVERY_SCENARIO_ID]
    result = controller._run_gather_mission_scenario(scenario)

    command = captured["cmd"]
    layout_path = Path(command[command.index("--target-layout-json") + 1])
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    assert result["pass"] is True
    assert result["planner_gated_random"] is True
    assert result["local_fetch_dispatched"] is True
    assert result["route_label"] == dashboard_service.fetch_planner_gate.ROUTE_RECOVERY_OR_REAIM
    assert result["route_executor"] == dashboard_service.fetch_planner_gate.ROUTE_EXECUTOR_RECOVERY
    assert result["planner_route_executed"] is True
    assert result["planner_route_execution"]["outcome"] == "forward_only_fetch_runner_dispatched"
    assert result["planner_route_execution"]["reason"] == "planner route permitted bounded local re-aim execution"
    assert result["forward_only_pre_contact_required"] is True
    assert result["forward_only_pre_contact"] is True
    assert layout["layout_family"] == "planner_gated_recovery_or_reaim"
    assert layout["planner_route_label"] == dashboard_service.fetch_planner_gate.ROUTE_RECOVERY_OR_REAIM
    assert layout["route_executor"] == dashboard_service.fetch_planner_gate.ROUTE_EXECUTOR_RECOVERY
    assert layout["planner_scene"]["scene_id"] == scene["scene_id"]
    assert "--planner-route-label" in command
    assert command[command.index("--planner-route-label") + 1] == dashboard_service.fetch_planner_gate.ROUTE_RECOVERY_OR_REAIM
    assert "--route-executor" in command
    assert command[command.index("--route-executor") + 1] == dashboard_service.fetch_planner_gate.ROUTE_EXECUTOR_RECOVERY
    assert "--forward-only-pre-contact-required" in command
    assert command[command.index("--robot-x") + 1] == f"{float(scene['robot_pose']['x']):.6f}"
    assert command[command.index("--robot-y") + 1] == f"{float(scene['robot_pose']['y']):.6f}"
    assert command[command.index("--robot-yaw") + 1] == f"{float(scene['robot_pose']['yaw']):.6f}"
    assert "--drive-mode" in command
    assert command[command.index("--drive-mode") + 1] == "line_servo"
    assert "--nav2-reposition-before-fetch" not in command
    assert "--nav2-reposition-transform-layout-to-current-robot" not in command
    assert "--stop-on-delivery" in command
    assert command[command.index("--delivery-stop-radius-m") + 1] == "0.200000"
    assert command[command.index("--artifact-kind") + 1] == dashboard_service.GOLF_BALL_CIRCLE_DELIVERY_RANDOM_ARTIFACT_KIND


def test_run_golf_fetch_planner_gated_nav2_reposition_route_dispatches_forward_layout(tmp_path, monkeypatch):
    controller = _make_controller(tmp_path)
    controller.state["dashboard_url"] = "http://127.0.0.1:8860/"
    controller._scenarios_dir = lambda: tmp_path / "scenarios"
    controller._current_validation_dir = lambda: tmp_path / "validation"
    controller.active_scenario_overrides = {
        "planner_gated_random": True,
        "planner_mode": dashboard_service.fetch_planner_gate.PLANNER_MODE_DETERMINISTIC,
        "random_seed": 456,
    }
    controller._visit_mission_runtime_state = lambda: {"proof_state": "completed"}
    controller._gather_mission_runtime_state = lambda: {
        "mission_phase": "completed",
        "mission_status": "completed",
        "gather_phase": "completed",
        "surface_profile": "calibrated_golf_turf",
    }
    controller._scenario_env = lambda _scenario: {
        "WORLD_FILE": "yolo_test_world_v6_calibrated_golf_turf.world",
        "CHASECAR_SURFACE_PROFILE": "calibrated_golf_turf",
    }
    scene = next(
        item for item in dashboard_service.fetch_planner_gate.generate_random_scenes(seed=456, random_cases=10)
        if item["expected_route_label"] == dashboard_service.fetch_planner_gate.ROUTE_NAV2_REPOSITION
    )
    monkeypatch.setattr(dashboard_service.fetch_planner_gate, "generate_dashboard_scene", lambda **_kwargs: scene)

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

    monkeypatch.setattr(dashboard_service.subprocess, "Popen", lambda command, **kwargs: _FakeProc(command, kwargs["stdout"]))

    scenario = dashboard_service.SCENARIOS_BY_ID[dashboard_service.GOLF_BALL_CIRCLE_DELIVERY_SCENARIO_ID]
    result = controller._run_gather_mission_scenario(scenario)

    command = captured["cmd"]
    layout_path = Path(command[command.index("--target-layout-json") + 1])
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    assert result["pass"] is True
    assert result["planner_gated_random"] is True
    assert result["local_fetch_dispatched"] is True
    assert result["route_label"] == dashboard_service.fetch_planner_gate.ROUTE_NAV2_REPOSITION
    assert result["route_executor"] == dashboard_service.fetch_planner_gate.ROUTE_EXECUTOR_NAV2_REPOSITION_FETCH
    assert result["planner_route_executed"] is True
    assert result["forward_only_pre_contact_required"] is True
    assert result["forward_only_pre_contact"] is True
    assert layout["layout_family"] == "planner_gated_nav2_reposition_first"
    assert layout["planner_route_label"] == dashboard_service.fetch_planner_gate.ROUTE_NAV2_REPOSITION
    assert layout["route_executor"] == dashboard_service.fetch_planner_gate.ROUTE_EXECUTOR_NAV2_REPOSITION_FETCH
    assert "--planner-route-label" in command
    assert command[command.index("--planner-route-label") + 1] == dashboard_service.fetch_planner_gate.ROUTE_NAV2_REPOSITION
    assert "--route-executor" in command
    assert command[command.index("--route-executor") + 1] == dashboard_service.fetch_planner_gate.ROUTE_EXECUTOR_NAV2_REPOSITION_FETCH
    assert command[command.index("--robot-x") + 1] == "0.000000"
    assert command[command.index("--robot-y") + 1] == "0.000000"
    assert command[command.index("--robot-yaw") + 1] == "0.000000"
    assert "--forward-only-pre-contact-required" in command
    assert "--drive-mode" in command
    assert command[command.index("--drive-mode") + 1] == "line_servo"
    assert "--drive-linear-x-mps" in command
    assert command[command.index("--drive-linear-x-mps") + 1] == "0.100000"
    assert "--drive-duration-s" in command
    assert command[command.index("--drive-duration-s") + 1] == "36.000000"
    assert "--sample-duration-s" in command
    assert command[command.index("--sample-duration-s") + 1] == "40.000000"
    assert "--line-servo-push-linear-x-mps" in command
    assert command[command.index("--line-servo-push-linear-x-mps") + 1] == "0.055000"
    assert "--line-servo-max-angular-z-rps" in command
    assert command[command.index("--line-servo-max-angular-z-rps") + 1] == "0.180000"
    assert "--line-servo-yaw-gain" in command
    assert command[command.index("--line-servo-yaw-gain") + 1] == "1.200000"
    assert "--nav2-reposition-before-fetch" in command
    assert command[command.index("--nav2-reposition-frame-id") + 1] == "odom"
    assert command[command.index("--nav2-reposition-goal-frame-mode") + 1] == "nav2_relative"
    assert "--nav2-reposition-transform-layout-to-current-robot" in command
    assert command[command.index("--nav2-reposition-setup-standoff-m") + 1] == "0.380000"
    assert command[command.index("--nav2-reposition-timeout-s") + 1] == "24.000000"
    assert command[command.index("--nav2-reposition-server-wait-s") + 1] == "8.000000"
    assert command[command.index("--nav2-reposition-pose-wait-s") + 1] == "3.000000"
    assert "--stop-on-delivery" in command
    assert "--delivery-stop-radius-m" in command
    assert command[command.index("--delivery-stop-radius-m") + 1] == "0.200000"
    assert "--post-delivery-sample-s" in command
    assert command[command.index("--post-delivery-sample-s") + 1] == "4.000000"


def test_run_three_ball_gather_scenario_returns_aggregate_corral_fields(tmp_path, monkeypatch):
    controller = _make_controller(tmp_path)
    controller.state["dashboard_url"] = "http://127.0.0.1:8860/"
    controller._scenarios_dir = lambda: tmp_path / "scenarios"
    controller._current_validation_dir = lambda: tmp_path / "validation"
    controller._visit_mission_runtime_state = lambda: {
        "proof_state": "completed",
        "visited_targets": ["ball_a", "ball_b", "ball_c"],
        "last_visit_result": {"target_id": "ball_c", "pass": True},
    }
    controller._gather_mission_runtime_state = lambda: {
        "mission_phase": "completed",
        "mission_status": "completed",
        "gather_phase": "completed",
        "surface_profile": "short_turf",
        "placed_targets": ["ball_a", "ball_b", "ball_c"],
        "capture_loss_count": 0,
        "route_order": ["ball_b", "ball_a", "ball_c"],
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
    _write_json(
        mission_verdict_path,
        {
            "pass": True,
            "type": "gather_mission",
            "final_corral_audit": {
                "ball_a": {"distance_to_zone_center_m": 0.2, "inside_retrieval_corral": True, "stopped_in_corral": True},
                "ball_b": {"distance_to_zone_center_m": 0.2, "inside_retrieval_corral": True, "stopped_in_corral": True},
                "ball_c": {"distance_to_zone_center_m": 0.2, "inside_retrieval_corral": True, "stopped_in_corral": True},
            },
            "final_all_targets_inside_retrieval_corral": True,
            "final_all_targets_stopped": True,
            "final_three_ball_corral_pass": True,
            "retrieved_count": 3,
        },
    )
    _write_json(mission_root / "summary.json", {"pass": True})
    _write_json(mission_root / "target_results.json", {"targets": []})

    class _FakeProc:
        def __init__(self, cmd, stdout_handle) -> None:
            stdout_handle.write(f"GATHER_MISSION_SUMMARY={mission_verdict_path}\n")
            stdout_handle.flush()
            self.returncode = 0

        def poll(self):
            return 0

    monkeypatch.setattr(dashboard_service.subprocess, "Popen", lambda command, **kwargs: _FakeProc(command, kwargs["stdout"]))

    result = controller._run_gather_mission_scenario(dashboard_service.SCENARIOS_BY_ID["gather_three_ball_zone"])

    assert result["pass"] is True
    assert set(result["final_corral_audit"].keys()) == {"ball_a", "ball_b", "ball_c"}
    assert result["mission_verdict"]["final_three_ball_corral_pass"] is True
    assert result["mission_verdict"]["retrieved_count"] == 3


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
        "zone_pose": {"x": 2.4, "y": 0.0, "radius_m": 0.762, "control_radius_m": 0.2},
        "zone_score": {"inside_zone": False},
        "final_corral_audit": {
            "ball_1": {"distance_to_zone_center_m": 0.18, "inside_retrieval_corral": True, "stopped_in_corral": False},
        },
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
    assert state["zone_pose"]["radius_m"] == 0.762
    assert state["zone_pose"]["control_radius_m"] == 0.2
    assert state["route_order"] == ["ball_1"]
    assert state["surface_profile"] == "short_turf"
    assert state["final_corral_audit"]["ball_1"]["inside_retrieval_corral"] is True
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

    allocation_requests: list[tuple[int, int, tuple[int, ...]]] = []

    def fake_find_free_port(start, end, *, exclude_ports=None):
        excluded = tuple(sorted(exclude_ports or set()))
        allocation_requests.append((start, end, excluded))
        for port in range(start, end + 1):
            if port not in set(excluded):
                return port
        raise RuntimeError("no free port")

    monkeypatch.setattr(dashboard_service, "find_free_port", fake_find_free_port)
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
    assert allocation_requests == [
        (8891, 8921, ()),
        (dashboard_service.OPERATOR_VIEW_PORT_START, dashboard_service.OPERATOR_VIEW_PORT_END, ()),
        (8891, 8921, (8891,)),
        (dashboard_service.OPERATOR_VIEW_PORT_START, dashboard_service.OPERATOR_VIEW_PORT_END, ()),
    ]
    assert removed_projects == ["chasecar_dashboard_20260320t200000z"]
    assert controller.state["environment_state"] == "environment_ready"
    assert controller.state["world_stream_port"] == 8892
    assert controller.state["operator_view_port"] == dashboard_service.OPERATOR_VIEW_PORT_START
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


def test_start_environment_worker_can_degrade_optional_operator_view(tmp_path, monkeypatch):
    controller = _make_controller(tmp_path)
    controller.operator_view_required = False
    controller.visual_evidence_required = True
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
    controller._run_environment_compose_up = lambda *_args, **_kwargs: (0, "ok")
    helper_prefixes: list[str] = []
    controller._run_container_helper = lambda _container_id, _script, prefix: helper_prefixes.append(prefix) or {"output": "ok"}
    controller._wait_for_truth_ready = lambda timeout_s: True
    controller._wait_for_world_stream_ready = lambda timeout_s: True
    controller._wait_for_operator_view_ready = lambda timeout_s: False
    controller._wait_for_visual_ready = lambda timeout_s: True
    controller._wait_for_required_gate_services = lambda *_args, **_kwargs: {
        "sim-gate": {"service": "sim-gate", "status": "running", "container_id": "sim-gate-1"},
        "world-viewer": {"service": "world-viewer", "status": "running", "container_id": "world-viewer-1"},
        "gate-stack": {"service": "gate-stack", "status": "running", "container_id": "gate-stack-1"},
        "operator-view": {"service": "operator-view", "status": "running", "container_id": "operator-view-1"},
    }
    controller._operator_view_snapshot = lambda *_args, **_kwargs: {
        "ready": False,
        "status": "error",
        "failure_class": "xpra_http_unavailable",
    }
    monkeypatch.setattr(dashboard_service, "find_free_port", lambda start, end, *, exclude_ports=None: start)
    monkeypatch.setattr(dashboard_service, "make_session_id", lambda: "20260320T201500Z")

    events: list[tuple[str, str]] = []
    controller._record_operator_event = lambda message, category="info", source="dashboard": events.append((message, category))

    controller._start_environment_worker()

    assert controller.state["environment_state"] == "environment_ready"
    assert controller.state["operator_view_required"] is False
    assert controller.state["visual_evidence_required"] is True
    assert controller.state["operator_view_ready"] is False
    assert controller.state["operator_view_status"] == "degraded_optional"
    assert controller.state["operator_view_failure_class"] == ""
    assert helper_prefixes == ["TRUTH", "WORLD_STREAM", "VISUAL"]
    assert any("Recorded visual evidence starting with optional Xpra" in message for message, _category in events)


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

        def communicate(self, timeout=None):
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

        def communicate(self, timeout=None):
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


def test_run_environment_compose_up_keeps_world_stream_for_visual_evidence_without_operator_view(tmp_path):
    controller = _make_controller(tmp_path)
    controller.control_mode = "docker_socket"
    controller.build_on_next_start = False
    controller.operator_view_required = False
    controller.visual_evidence_required = True

    popen_calls: list[tuple[str, ...]] = []
    controller._run_docker_compose = lambda *_args, **_kwargs: None

    class _Proc:
        returncode = 0

        def communicate(self, timeout=None):
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
        )
    ]


def test_run_environment_compose_up_recovers_timeout_when_services_are_running(tmp_path):
    controller = _make_controller(tmp_path)
    controller.control_mode = "docker_socket"
    controller.build_on_next_start = False
    controller._run_docker_compose = lambda *_args, **_kwargs: None
    controller._docker_image_exists = lambda _image_ref: True
    controller._wait_for_required_gate_services = lambda *_args, **_kwargs: {
        "sim-gate": {"service": "sim-gate", "status": "running", "container_id": "sim-gate-1"},
        "world-viewer": {"service": "world-viewer", "status": "running", "container_id": "world-viewer-1"},
        "gate-stack": {"service": "gate-stack", "status": "running", "container_id": "gate-stack-1"},
        "operator-view": {"service": "operator-view", "status": "running", "container_id": "operator-view-1"},
    }
    terminated = []
    controller._terminate_process = lambda proc: terminated.append(proc)

    class _Proc:
        returncode = None

        def communicate(self, timeout=None):
            raise subprocess.TimeoutExpired(cmd=["docker", "compose"], timeout=timeout, output="still waiting")

    proc = _Proc()
    controller._popen_docker_compose = lambda *_args, **_kwargs: proc

    rc, output = controller._run_environment_compose_up("chasecar_dashboard_test", {"WORLD_STREAM_PORT": "8891"})

    assert rc == 0
    assert "compose_up_timeout_recovered_required_services_running" in output
    assert terminated == [proc]


def test_run_environment_compose_up_reports_timeout_when_services_are_not_ready(tmp_path):
    controller = _make_controller(tmp_path)
    controller.control_mode = "docker_socket"
    controller.build_on_next_start = False
    controller._run_docker_compose = lambda *_args, **_kwargs: None
    controller._docker_image_exists = lambda _image_ref: True
    controller._wait_for_required_gate_services = lambda *_args, **_kwargs: {
        "sim-gate": {"service": "sim-gate", "status": "running", "container_id": "sim-gate-1"},
        "world-viewer": {"service": "world-viewer", "status": "created", "container_id": "world-viewer-1"},
        "gate-stack": {"service": "gate-stack", "status": "running", "container_id": "gate-stack-1"},
        "operator-view": {"service": "operator-view", "status": "running", "container_id": "operator-view-1"},
    }
    controller._terminate_process = lambda _proc: None

    class _Proc:
        returncode = None

        def communicate(self, timeout=None):
            raise subprocess.TimeoutExpired(cmd=["docker", "compose"], timeout=timeout, output="")

    controller._popen_docker_compose = lambda *_args, **_kwargs: _Proc()

    rc, output = controller._run_environment_compose_up("chasecar_dashboard_test", {"WORLD_STREAM_PORT": "8891"})

    assert rc == 124
    assert "compose_up_timeout" in output
    assert "world-viewer=created" in output


def test_run_environment_compose_up_uses_build_when_requested(tmp_path):
    controller = _make_controller(tmp_path)
    controller.control_mode = "docker_socket"
    controller.build_on_next_start = True
    controller._docker_image_exists = lambda _image_ref: False

    popen_calls: list[tuple[str, ...]] = []
    controller._run_docker_compose = lambda *_args, **_kwargs: None

    class _Proc:
        returncode = 0

        def communicate(self, timeout=None):
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

        def communicate(self, timeout=None):
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
    observer.frame_spool_dir = observer.output_dir / "world_stream_frames"
    observer.frame_spool_dir.mkdir(parents=True, exist_ok=True)
    observer.screenshot_path = observer.live_dir / "world_stream.jpg"
    observer.video_path = observer.output_dir / "world_stream.mp4"
    observer.state_path = observer.output_dir / "world_stream_state.json"
    observer.summary_path = observer.output_dir / "world_stream_summary.json"
    observer.placeholder = SimpleNamespace(copy=lambda: observer.placeholder)
    observer.writer = SimpleNamespace(write=lambda _frame: None, release=lambda: None)
    observer.writer_size = None
    observer.video_writer_open = True
    observer.video_writer_error = ""
    observer.spool_frame_count = 0
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


def test_world_stream_finalize_rebuilds_tiny_opencv_video_from_spool(tmp_path, monkeypatch):
    observer = _make_world_stream_observer(tmp_path)
    observer.video_path.write_bytes(b"tiny")
    observer.spool_frame_count = 2
    (observer.frame_spool_dir / "000001.jpg").write_bytes(b"frame1")
    (observer.frame_spool_dir / "000002.jpg").write_bytes(b"frame2")

    def _fake_run(command, **_kwargs):
        assert command[0] == "ffmpeg"
        assert str(observer.frame_spool_dir / "%06d.jpg") in command
        Path(command[-1]).write_bytes(b"x" * world_stream_controller.WORLD_STREAM_VIDEO_MIN_BYTES)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(world_stream_controller.subprocess, "run", _fake_run)

    observer.finalize({"world_stream_ready": True})

    summary = json.loads(observer.summary_path.read_text(encoding="utf-8"))
    assert summary["pass"] is True
    assert summary["video_ok"] is True
    assert summary["opencv_video_ok"] is False
    assert summary["ffmpeg_fallback_attempted"] is True
    assert summary["ffmpeg_fallback_ok"] is True
    assert summary["world_stream_spool_frame_count"] == 2


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
