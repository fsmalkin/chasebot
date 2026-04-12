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
    vision_scan_path = os.path.join(source_root, "ros2_scripts", "ros2_vision_to_laserscan_hsv.py")
    visited_target_obstacles_path = os.path.join(source_root, "ros2_scripts", "visited_target_obstacle_cloud.py")

    input_topic = LaunchConfiguration("input_topic").perform(context)
    use_sim_time = LaunchConfiguration("use_sim_time").perform(context)
    headless = LaunchConfiguration("headless").perform(context)
    perf_profile = LaunchConfiguration("perf_profile").perform(context)
    runtime_target = LaunchConfiguration("runtime_target").perform(context)
    inference_device = LaunchConfiguration("inference_device").perform(context)
    inference_backend = LaunchConfiguration("inference_backend").perform(context)
    engine_path = LaunchConfiguration("engine_path").perform(context)
    enable_obstacle_scan = LaunchConfiguration("enable_obstacle_scan").perform(context)
    enable_visited_target_obstacles = LaunchConfiguration("enable_visited_target_obstacles").perform(context)
    obstacle_depth_topic = LaunchConfiguration("obstacle_depth_topic").perform(context)
    obstacle_camera_info_topic = LaunchConfiguration("obstacle_camera_info_topic").perform(context)

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

    actions = [
        LogInfo(msg=["[perception_stack] detector: ", detector_path]),
        ExecuteProcess(cmd=["bash", "-lc", detector_cmd], output="screen"),
        ExecuteProcess(cmd=["bash", "-lc", extractor_cmd], output="screen"),
    ]

    if enable_obstacle_scan.lower() == "true":
        # Depth-backed HSV obstacle scan for the red target balls.
        vision_scan_cmd = (
            f"python3 {shlex.quote(vision_scan_path)} --ros-args "
            f"-p use_sim_time:={use_sim_time} "
            f"-p image_topic:={input_topic} "
            f"-p depth_topic:={obstacle_depth_topic} "
            f"-p camera_info_topic:={obstacle_camera_info_topic} "
            f"-p hsv_lower_h:=0 "
            f"-p hsv_upper_h:=10 "
            f"-p hsv_lower_s:=100 "
            f"-p hsv_upper_s:=255 "
            f"-p hsv_lower_v:=100 "
            f"-p hsv_upper_v:=255"
        )
        actions.append(LogInfo(msg=["[perception_stack] vision_to_laserscan: ", vision_scan_path]))
        actions.append(ExecuteProcess(cmd=["bash", "-lc", vision_scan_cmd], output="screen"))

    if enable_visited_target_obstacles.lower() == "true":
        visited_target_obstacles_cmd = f"python3 {shlex.quote(visited_target_obstacles_path)} --ros-args -p use_sim_time:={use_sim_time}"
        actions.append(
            LogInfo(msg=["[perception_stack] visited_target_obstacles: ", visited_target_obstacles_path])
        )
        actions.append(ExecuteProcess(cmd=["bash", "-lc", visited_target_obstacles_cmd], output="screen"))

    return actions


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
            DeclareLaunchArgument("enable_obstacle_scan", default_value="true"),
            DeclareLaunchArgument("enable_visited_target_obstacles", default_value="true"),
            DeclareLaunchArgument("obstacle_depth_topic", default_value="/d415/depth/image_raw"),
            DeclareLaunchArgument("obstacle_camera_info_topic", default_value="/d415/depth/camera_info"),
            OpaqueFunction(function=_build_actions),
        ]
    )
