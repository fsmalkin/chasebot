#!/usr/bin/env python3
"""Canonical Jetty gate lane launch wrapper."""

import os

from ament_index_python.packages import PackageNotFoundError
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription
from launch.actions import LogInfo
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def _resolve_gate_launch_path() -> str:
    source_hint = os.environ.get("CHASECAR_SOURCE_PATH", "").strip()
    if source_hint:
        candidate = os.path.join(
            source_hint,
            "ros2_config",
            "launch",
            "jetbot_gz_control_camera_test_v5.launch.py",
        )
        if os.path.isfile(candidate):
            return candidate

    for pkg in ("chasecar_description", "chasebot_description", "chasebot_sim"):
        try:
            share_dir = get_package_share_directory(pkg)
        except PackageNotFoundError:
            continue
        candidate = os.path.join(
            share_dir,
            "ros2_config",
            "launch",
            "jetbot_gz_control_camera_test_v5.launch.py",
        )
        if os.path.isfile(candidate):
            return candidate

    raise RuntimeError("Unable to resolve canonical gate launch: jetbot_gz_control_camera_test_v5.launch.py")


def generate_launch_description() -> LaunchDescription:
    world = LaunchConfiguration("world")
    headless = LaunchConfiguration("headless")
    perf_profile = LaunchConfiguration("perf_profile")
    inference_device = LaunchConfiguration("inference_device")

    source_launch = _resolve_gate_launch_path()

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "world",
                default_value="yolo_test_world_v6_clean_uat.world",
                description="World file used in authoritative gate lane.",
            ),
            DeclareLaunchArgument("headless", default_value="true"),
            DeclareLaunchArgument("perf_profile", default_value="compat"),
            DeclareLaunchArgument("inference_device", default_value="cuda:0"),
            LogInfo(msg=["[sim_gate] source launch: ", source_launch]),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(source_launch),
                launch_arguments={
                    "world": world,
                    "headless": headless,
                    "perf_profile": perf_profile,
                    "inference_device": inference_device,
                }.items(),
            ),
        ]
    )
