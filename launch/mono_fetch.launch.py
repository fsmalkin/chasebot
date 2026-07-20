#!/usr/bin/env python3
"""Launch the mono fetch node inside the gate-stack runtime."""

import os
import shlex

from ament_index_python.packages import PackageNotFoundError
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import ExecuteProcess
from launch.actions import LogInfo
from launch.actions import OpaqueFunction
from launch.substitutions import LaunchConfiguration


def _resolve_source_root() -> str:
    source_hint = os.environ.get("CHASECAR_SOURCE_PATH", "").strip()
    if source_hint and os.path.isdir(source_hint):
        return source_hint
    for pkg in ("chasecar_description", "chasebot_description", "chasebot_sim"):
        try:
            share_dir = get_package_share_directory(pkg)
        except PackageNotFoundError:
            continue
        src_hint = os.path.normpath(os.path.join(share_dir, "..", "..", "..", "src", pkg))
        if os.path.isdir(src_hint):
            return src_hint
    cwd = os.getcwd()
    if os.path.isdir(os.path.join(cwd, "ros2_scripts")):
        return cwd
    raise RuntimeError("Unable to resolve source root for mono fetch launch.")


def _build_actions(context):
    source_root = _resolve_source_root()
    node_path = os.path.join(source_root, "ros2_scripts", "chasecar_mono_fetch_node.py")
    calibration = LaunchConfiguration("calibration").perform(context)
    artifact_dir = LaunchConfiguration("artifact_dir").perform(context)
    model_path = LaunchConfiguration("model_path").perform(context)
    use_sim_time = LaunchConfiguration("use_sim_time").perform(context)
    image_topic = LaunchConfiguration("image_topic").perform(context)
    camera_info_topic = LaunchConfiguration("camera_info_topic").perform(context)
    cmd_vel_topic = LaunchConfiguration("cmd_vel_topic").perform(context)
    publish_hz = LaunchConfiguration("publish_hz").perform(context)
    confidence_threshold = LaunchConfiguration("confidence_threshold").perform(context)
    min_confidence = LaunchConfiguration("min_confidence").perform(context)
    standoff_m = LaunchConfiguration("standoff_m").perform(context)

    cmd = (
        f"python3 {shlex.quote(node_path)} "
        f"--calibration {shlex.quote(calibration)} "
        f"--artifact-dir {shlex.quote(artifact_dir)} "
        f"--model {shlex.quote(model_path)} "
        "--ros-args "
        f"-p use_sim_time:={use_sim_time} "
        f"-p image_topic:={shlex.quote(image_topic)} "
        f"-p camera_info_topic:={shlex.quote(camera_info_topic)} "
        f"-p cmd_vel_topic:={shlex.quote(cmd_vel_topic)} "
        f"-p publish_hz:={publish_hz} "
        f"-p confidence_threshold:={confidence_threshold} "
        f"-p min_confidence:={min_confidence} "
        f"-p standoff_m:={standoff_m}"
    )
    return [
        LogInfo(msg=["[mono_fetch] node: ", node_path]),
        ExecuteProcess(cmd=["bash", "-lc", cmd], output="screen"),
    ]


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription(
        [
            DeclareLaunchArgument("calibration", default_value="artifacts/session/sim_mono_calibration/calibration_summary.json"),
            DeclareLaunchArgument("artifact_dir", default_value="artifacts/session/mono_fetch_node"),
            DeclareLaunchArgument("model_path", default_value="runtime/yolo/yolov5m.onnx"),
            DeclareLaunchArgument("use_sim_time", default_value="true"),
            DeclareLaunchArgument("image_topic", default_value="/d415/color/image_raw"),
            DeclareLaunchArgument("camera_info_topic", default_value="/d415/color/camera_info"),
            DeclareLaunchArgument("cmd_vel_topic", default_value="/jetbot_base_controller/cmd_vel"),
            DeclareLaunchArgument("publish_hz", default_value="20.0"),
            DeclareLaunchArgument("confidence_threshold", default_value="0.25"),
            DeclareLaunchArgument("min_confidence", default_value="0.25"),
            DeclareLaunchArgument("standoff_m", default_value="0.40"),
            OpaqueFunction(function=_build_actions),
        ]
    )
