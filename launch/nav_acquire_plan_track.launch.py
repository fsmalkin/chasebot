#!/usr/bin/env python3
"""Canonical low-level autonomy lane: acquire + plan + track."""

import os
import shlex

from ament_index_python.packages import PackageNotFoundError
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription
from launch.actions import ExecuteProcess
from launch.actions import OpaqueFunction
from launch.actions import LogInfo
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def _resolve_source_root() -> str:
    source_hint = os.environ.get("CHASECAR_SOURCE_PATH", "").strip()
    if source_hint and os.path.isdir(source_hint):
        return source_hint
    cwd = os.getcwd()
    if os.path.isdir(os.path.join(cwd, "ros2_scripts")):
        return cwd
    for pkg in ("chasecar_description", "chasebot_description", "chasebot_sim"):
        try:
            share_dir = get_package_share_directory(pkg)
        except PackageNotFoundError:
            continue
        src_hint = os.path.normpath(os.path.join(share_dir, "..", "..", "..", "src", pkg))
        if os.path.isdir(src_hint):
            return src_hint
    raise RuntimeError("Unable to resolve source root for nav lane launch.")


def _resolve_nav_launch(source_root: str) -> str:
    for launch_name in (
        "jetbot_nav2_rosgz_readiness.launch.py",
        "nav2_complete_uat.launch.py",
    ):
        source_candidate = os.path.join(source_root, "ros2_config", "launch", launch_name)
        if os.path.isfile(source_candidate):
            return source_candidate
    for pkg in ("chasecar_description", "chasebot_description"):
        try:
            share_dir = get_package_share_directory(pkg)
        except PackageNotFoundError:
            continue
        for launch_name in (
            "jetbot_nav2_rosgz_readiness.launch.py",
            "nav2_complete_uat.launch.py",
        ):
            candidate = os.path.join(share_dir, "ros2_config", "launch", launch_name)
            if os.path.isfile(candidate):
                return candidate
    return ""


def _as_bool(value: str) -> bool:
    return value.lower() in ("1", "true", "yes", "on")


def _build_actions(context):
    source_root = _resolve_source_root()
    nav_bridge_path = os.path.join(source_root, "ros2_scripts", "yolo_3d_to_nav2_bridge.py")
    cmd_vel_relay_path = os.path.join(source_root, "ros2_scripts", "cmd_vel_relay.py")
    brain_executor_path = os.path.join(source_root, "scripts", "brain_intent_executor.py")
    brain_state_path = os.environ.get("CHASECAR_BRAIN_STATE_PATH", "").strip()
    brain_feedback_path = os.environ.get("CHASECAR_BRAIN_FEEDBACK_PATH", "").strip()

    use_sim_time = LaunchConfiguration("use_sim_time").perform(context)
    include_bridge = _as_bool(LaunchConfiguration("include_bridge").perform(context))
    include_nav2_bringup = _as_bool(LaunchConfiguration("include_nav2_bringup").perform(context))
    include_cmd_vel_relay = _as_bool(LaunchConfiguration("include_cmd_vel_relay").perform(context))
    include_brain_executor = _as_bool(LaunchConfiguration("include_brain_executor").perform(context))

    actions = [
        LogInfo(msg=["[nav_lane] source root: ", source_root]),
    ]

    if include_bridge:
        bridge_cmd = (
            f"python3 {shlex.quote(nav_bridge_path)} --ros-args "
            f"-p use_sim_time:={use_sim_time}"
        )
        actions.append(ExecuteProcess(cmd=["bash", "-lc", bridge_cmd], output="screen"))

    if include_nav2_bringup and include_cmd_vel_relay:
        relay_cmd = (
            f"python3 {shlex.quote(cmd_vel_relay_path)} --ros-args "
            f"-p use_sim_time:={use_sim_time}"
        )
        actions.append(ExecuteProcess(cmd=["bash", "-lc", relay_cmd], output="screen"))

    if include_brain_executor:
        brain_cmd = [f"python3 {shlex.quote(brain_executor_path)}"]
        if brain_state_path:
            brain_cmd.append(f"--state-json {shlex.quote(brain_state_path)}")
        if brain_feedback_path:
            brain_cmd.append(f"--feedback-jsonl {shlex.quote(brain_feedback_path)}")
        visit_runtime_path = os.environ.get("CHASECAR_VISIT_RUNTIME_PATH", "").strip()
        if visit_runtime_path:
            brain_cmd.append(f"--visit-runtime-json {shlex.quote(visit_runtime_path)}")
        brain_cmd.append("--use-sim-time" if _as_bool(use_sim_time) else "--no-use-sim-time")
        actions.append(ExecuteProcess(cmd=["bash", "-lc", " ".join(brain_cmd)], output="screen"))

    if include_nav2_bringup:
        nav_launch = _resolve_nav_launch(source_root)
        if nav_launch:
            actions.append(
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(nav_launch),
                    launch_arguments={"use_sim_time": use_sim_time}.items(),
                )
            )
        else:
            actions.append(LogInfo(msg="[nav_lane] Nav2 bringup launch not found; skipping Nav2 bringup."))

    return actions


def generate_launch_description() -> LaunchDescription:
    perception_launch = os.path.join(os.path.dirname(__file__), "perception_stack.launch.py")

    return LaunchDescription(
        [
            DeclareLaunchArgument("use_sim_time", default_value="true"),
            DeclareLaunchArgument("include_bridge", default_value="true"),
            DeclareLaunchArgument("include_nav2_bringup", default_value="false"),
            DeclareLaunchArgument("include_cmd_vel_relay", default_value="true"),
            DeclareLaunchArgument("include_brain_executor", default_value="false"),
            IncludeLaunchDescription(PythonLaunchDescriptionSource(perception_launch)),
            OpaqueFunction(function=_build_actions),
        ]
    )
