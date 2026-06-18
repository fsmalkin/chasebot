from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
ROS2_SCRIPTS_DIR = REPO_ROOT / "ros2_scripts"
if str(ROS2_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(ROS2_SCRIPTS_DIR))


def _install_ros_stubs() -> None:
    if "rclpy" not in sys.modules:
        rclpy_mod = ModuleType("rclpy")
        rclpy_mod.init = lambda *_args, **_kwargs: None
        rclpy_mod.spin = lambda *_args, **_kwargs: None
        rclpy_mod.shutdown = lambda *_args, **_kwargs: None
        rclpy_mod.ok = lambda: False
        node_mod = ModuleType("rclpy.node")

        class _Node:
            def __init__(self, *_args, **_kwargs) -> None:
                return None

            def create_subscription(self, *_args, **_kwargs):
                return object()

            def create_timer(self, *_args, **_kwargs):
                return object()

            def destroy_node(self) -> None:
                return None

            def get_logger(self):
                return SimpleNamespace(info=lambda *_args, **_kwargs: None, warn=lambda *_args, **_kwargs: None)

        node_mod.Node = _Node
        sys.modules["rclpy"] = rclpy_mod
        sys.modules["rclpy.node"] = node_mod

    if "geometry_msgs" not in sys.modules:
        geometry_mod = ModuleType("geometry_msgs")
        msg_mod = ModuleType("geometry_msgs.msg")

        class _Twist:
            def __init__(self) -> None:
                self.linear = SimpleNamespace(x=0.0, y=0.0, z=0.0)
                self.angular = SimpleNamespace(x=0.0, y=0.0, z=0.0)

        class _TwistStamped:
            def __init__(self) -> None:
                self.header = SimpleNamespace(stamp=None, frame_id="")
                self.twist = _Twist()

        msg_mod.Twist = _Twist
        msg_mod.TwistStamped = _TwistStamped
        geometry_mod.msg = msg_mod
        sys.modules["geometry_msgs"] = geometry_mod
        sys.modules["geometry_msgs.msg"] = msg_mod


_install_ros_stubs()

import factory_bridge_cmd_vel_relay as relay  # noqa: E402


def test_relay_core_scales_and_clamps_stack_command():
    core = relay.RelayCore(
        relay.RelayConfig(
            linear_scale=3.0,
            angular_scale=3.0,
            max_bridge_linear_x=0.36,
            max_bridge_angular_z=1.0,
            post_rate_hz=5.0,
        )
    )

    latest = core.update_command(
        topic="/cmd_vel",
        message_type="geometry_msgs/msg/Twist",
        linear_x=0.20,
        angular_z=-0.50,
        now_monotonic_s=10.0,
    )
    action = core.next_action(now_monotonic_s=10.25)

    assert latest.bridge_linear_x == 0.36
    assert latest.bridge_angular_z == -1.0
    assert action is not None
    assert action.action == "cmd_vel"
    assert action.payload["linear_x"] == 0.36
    assert action.payload["angular_z"] == -1.0
    assert action.payload["raw"]["linear_x"] == 0.20
    assert action.payload["source"] == "factory_bridge_cmd_vel_relay:/cmd_vel"


def test_relay_core_sends_single_stale_stop_after_active_command():
    core = relay.RelayCore(relay.RelayConfig(post_rate_hz=5.0, stale_stop_s=0.45))
    core.update_command(
        topic="/jetbot_base_controller/cmd_vel",
        message_type="geometry_msgs/msg/TwistStamped",
        linear_x=0.12,
        angular_z=0.0,
        now_monotonic_s=20.0,
    )
    command = core.next_action(now_monotonic_s=20.25)
    assert command is not None

    core.record_action_result(command, now_monotonic_s=20.25, http_status=200, response={"ok": True})
    stale_stop = core.next_action(now_monotonic_s=20.60)

    assert stale_stop is not None
    assert stale_stop.action == "stop"
    assert stale_stop.payload["source"] == "factory_bridge_cmd_vel_relay:stale_stop"

    core.record_action_result(stale_stop, now_monotonic_s=20.60, http_status=200, response={"ok": True})
    assert core.next_action(now_monotonic_s=21.20) is None
    assert core.summary()["counters"]["stop_posts"] == 1


def test_parse_args_keeps_relay_defaults_beginner_safe():
    args = relay.parse_args([])

    assert args.base_url == "http://192.168.1.11:8765"
    assert args.linear_scale == 3.0
    assert args.max_bridge_linear_x == 0.36
    assert args.max_bridge_angular_z == 1.0
    assert args.require_motion_enabled is False
