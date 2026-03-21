#!/usr/bin/env python3
"""Canonical perception stack launch using TensorRT backend."""

import os
import shlex

from ament_index_python.packages import PackageNotFoundError
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import ExecuteProcess
from launch.actions import OpaqueFunction
from launch.actions import LogInfo
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
    raise RuntimeError("Unable to resolve source root for perception launch.")


def _build_actions(context):
    source_root = _resolve_source_root()
    detector_path = os.path.join(source_root, "ros2_scripts", "chasecar_tensorrt_detector.py")
    extractor_path = os.path.join(source_root, "ros2_scripts", "yolo_3d_position_extractor.py")

    input_topic = LaunchConfiguration("input_topic").perform(context)
    use_sim_time = LaunchConfiguration("use_sim_time").perform(context)
    headless = LaunchConfiguration("headless").perform(context)
    perf_profile = LaunchConfiguration("perf_profile").perform(context)
    runtime_target = LaunchConfiguration("runtime_target").perform(context)
    inference_device = LaunchConfiguration("inference_device").perform(context)
    inference_backend = LaunchConfiguration("inference_backend").perform(context)
    engine_path = LaunchConfiguration("engine_path").perform(context)

    detector_cmd = (
        f"python3 {shlex.quote(detector_path)} --ros-args "
        f"-p use_sim_time:={use_sim_time} "
        f"-p input_topic:={input_topic} "
        f"-p headless:={headless} "
        f"-p perf_profile:={perf_profile} "
        f"-p runtime_target:={runtime_target} "
        f"-p inference_device:={inference_device} "
        f"-p inference_backend:={inference_backend} "
        f"-p engine_path:={engine_path}"
    )
    extractor_cmd = (
        f"python3 {shlex.quote(extractor_path)} --ros-args "
        f"-p use_sim_time:={use_sim_time}"
    )

    return [
        LogInfo(msg=["[perception_stack] detector: ", detector_path]),
        ExecuteProcess(cmd=["bash", "-lc", detector_cmd], output="screen"),
        ExecuteProcess(cmd=["bash", "-lc", extractor_cmd], output="screen"),
    ]


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription(
        [
            DeclareLaunchArgument("input_topic", default_value="/d415/color/image_raw"),
            DeclareLaunchArgument("use_sim_time", default_value="true"),
            DeclareLaunchArgument("headless", default_value="true"),
            DeclareLaunchArgument("perf_profile", default_value="compat"),
            DeclareLaunchArgument("runtime_target", default_value="robot_fidelity_orin"),
            DeclareLaunchArgument("inference_device", default_value="cuda:0"),
            DeclareLaunchArgument("inference_backend", default_value="tensorrt_int8"),
            DeclareLaunchArgument(
                "engine_path",
                default_value="runtime/tensorrt/engines/ball_detector_int8.engine",
            ),
            OpaqueFunction(function=_build_actions),
        ]
    )
