from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
ROS2_SCRIPTS_DIR = REPO_ROOT / "ros2_scripts"
if str(ROS2_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(ROS2_SCRIPTS_DIR))


def _install_ros_stubs() -> None:
    if "rclpy" not in sys.modules:
        rclpy_mod = ModuleType("rclpy")
        rclpy_mod.init = lambda *_args, **_kwargs: None
        rclpy_mod.spin = lambda *_args, **_kwargs: None
        rclpy_mod.shutdown = lambda: None
        rclpy_mod.ok = lambda: False
        node_mod = ModuleType("rclpy.node")
        executors_mod = ModuleType("rclpy.executors")

        class _Node:
            def __init__(self, *_args, **_kwargs) -> None:
                return None

        class _ExternalShutdownException(Exception):
            pass

        node_mod.Node = _Node
        executors_mod.ExternalShutdownException = _ExternalShutdownException
        sys.modules["rclpy"] = rclpy_mod
        sys.modules["rclpy.node"] = node_mod
        sys.modules["rclpy.executors"] = executors_mod

    if "geometry_msgs" not in sys.modules:
        geometry_mod = ModuleType("geometry_msgs")
        msg_mod = ModuleType("geometry_msgs.msg")

        class _TwistStamped:
            def __init__(self) -> None:
                self.header = SimpleNamespace(stamp=None, frame_id="")
                self.twist = SimpleNamespace(
                    linear=SimpleNamespace(x=0.0, y=0.0, z=0.0),
                    angular=SimpleNamespace(x=0.0, y=0.0, z=0.0),
                )

        msg_mod.TwistStamped = _TwistStamped
        geometry_mod.msg = msg_mod
        sys.modules["geometry_msgs"] = geometry_mod
        sys.modules["geometry_msgs.msg"] = msg_mod

    if "sensor_msgs" not in sys.modules:
        sys.modules["sensor_msgs"] = ModuleType("sensor_msgs")
    sensor_mod = sys.modules["sensor_msgs"]
    if "sensor_msgs.msg" not in sys.modules:
        sys.modules["sensor_msgs.msg"] = ModuleType("sensor_msgs.msg")
    msg_mod = sys.modules["sensor_msgs.msg"]

    if not hasattr(msg_mod, "Image"):
        class _Image:
            pass

        msg_mod.Image = _Image

    if not hasattr(msg_mod, "CameraInfo"):
        class _CameraInfo:
            pass

        msg_mod.CameraInfo = _CameraInfo
    sensor_mod.msg = msg_mod


_install_ros_stubs()

import chasecar_mono_fetch_node as mono_node  # noqa: E402


def _calibration() -> dict:
    return {
        "k_px_m": 10.0,
        "sigma_s_px": 1.0,
        "object_size_m": 0.0427,
        "max_reliable_range_m": 2.0,
        "size_key": "equiv_diameter_px",
    }


def _cfg(**overrides):
    payload = {
        "standoff_m": 0.40,
        "center_deadband": 0.16,
        "forward_budget": 10,
        "lost_limit": 4,
        "min_confidence": 0.25,
        "max_steps": 100,
        "turn_angular_z": 0.7,
        "approach_linear_x": 0.04,
    }
    payload.update(overrides)
    return mono_node.build_fetch_config(_calibration(), **payload)


def _state(**overrides):
    payload = {"step": 0, "forward_steps": 0, "lost_count": 0}
    payload.update(overrides)
    return payload


def _detection(**overrides):
    payload = {
        "confidence": 0.90,
        "equiv_diameter_px": 10.0,
        "bbox_height_px": 10.0,
        "center_error": 0.0,
    }
    payload.update(overrides)
    return payload


def test_centered_far_detection_drives_forward():
    obs, pose, action = mono_node.decide_mono_fetch(
        _detection(equiv_diameter_px=10.0, center_error=0.0),
        state=_state(),
        cfg=_cfg(),
        calibration=_calibration(),
        horizontal_fov_deg=60.0,
    )

    assert obs["equiv_diameter_px"] == 10.0
    assert pose["z_m_forward"] == 1.0
    assert action["action"] == "forward"
    assert action["linear_x"] == 0.04


def test_off_center_right_detection_turns_negative_angular_z():
    _obs, _pose, action = mono_node.decide_mono_fetch(
        _detection(center_error=0.30),
        state=_state(),
        cfg=_cfg(),
        calibration=_calibration(),
        horizontal_fov_deg=60.0,
    )

    assert action["action"] == "turn"
    assert action["angular_z"] < 0.0


def test_within_standoff_stops():
    _obs, pose, action = mono_node.decide_mono_fetch(
        _detection(equiv_diameter_px=40.0),
        state=_state(),
        cfg=_cfg(),
        calibration=_calibration(),
        horizontal_fov_deg=60.0,
    )

    assert pose["z_m_forward"] == 0.25
    assert action == {"action": "stop", "reason": "standoff_reached", "z_m": 0.25}


def test_lost_target_stops_after_lost_limit():
    _obs, pose, action = mono_node.decide_mono_fetch(
        None,
        state=_state(lost_count=4),
        cfg=_cfg(),
        calibration=_calibration(),
        horizontal_fov_deg=60.0,
    )

    assert pose is None
    assert action["action"] == "stop"
    assert action["reason"] == "lost_target"


def test_pose_status_gate_blocks_forward_when_bearing_only():
    action = {"action": "forward", "reason": "approach", "linear_x": 0.04}
    gated = mono_node.apply_pose_status_motion_gate(
        action,
        {"pose_status": "bearing_only"},
        require_metric_pose_for_forward=True,
    )

    assert gated["action"] == "hold"
    assert gated["reason"] == "pose_not_metric"
    assert gated["gated_action"] == "forward"


def test_contact_push_steps_zero_keeps_standoff_only_terminal_stop():
    decision, phase_state, transition = mono_node.contact_push_phase_step(
        {"phase": "approach"},
        {"action": "stop", "reason": "standoff_reached", "z_m": 0.39},
        push_steps=0,
        push_linear_x=0.05,
        push_max_distance_m=0.25,
        publish_hz=20.0,
    )

    assert decision == {"action": "stop", "reason": "standoff_reached", "z_m": 0.39}
    assert phase_state["phase"] == "hold"
    assert transition == {"from": "approach", "to": "hold", "reason": "standoff_reached"}


def test_contact_push_steps_positive_enters_push_then_stops():
    decision, phase_state, transition = mono_node.contact_push_phase_step(
        {"phase": "approach"},
        {"action": "stop", "reason": "standoff_reached", "z_m": 0.39},
        push_steps=1,
        push_linear_x=0.05,
        push_max_distance_m=0.25,
        publish_hz=20.0,
    )

    assert decision["reason"] == "standoff_reached"
    assert phase_state["phase"] == "push"
    assert transition == {"from": "approach", "to": "push", "reason": "standoff_reached"}

    push_decision, phase_state, transition = mono_node.contact_push_phase_step(
        phase_state,
        {"action": "stop", "reason": "terminal_phase"},
        push_steps=1,
        push_linear_x=0.05,
        push_max_distance_m=0.25,
        publish_hz=20.0,
    )

    assert push_decision["action"] == "forward"
    assert push_decision["reason"] == "contact_push"
    assert push_decision["push_tick"] == 1
    assert phase_state["phase"] == "push"
    assert transition is None

    stop_decision, phase_state, transition = mono_node.contact_push_phase_step(
        phase_state,
        {"action": "stop", "reason": "terminal_phase"},
        push_steps=1,
        push_linear_x=0.05,
        push_max_distance_m=0.25,
        publish_hz=20.0,
    )

    assert stop_decision == {"action": "stop", "reason": "push_steps_completed"}
    assert phase_state["phase"] == "hold"
    assert transition == {"from": "push", "to": "hold", "reason": "push_steps_completed"}
