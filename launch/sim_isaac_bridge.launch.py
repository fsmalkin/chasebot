#!/usr/bin/env python3
"""Bridge launcher for Isaac sidecar contract boundaries."""

import os
from typing import List

import yaml
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import LogInfo
from launch.actions import OpaqueFunction
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration


def _build_parameter_bridge_args(allowlist_path: str) -> List[str]:
    if not os.path.isfile(allowlist_path):
        return []

    with open(allowlist_path, "r", encoding="utf-8") as fp:
        data = yaml.safe_load(fp) or {}

    bridge_args: List[str] = []
    for item in data.get("topics", []):
        topic = item.get("ros_topic", "").strip()
        ros_type = item.get("ros_type", "").strip()
        sim_type = item.get("sim_type", "").strip()
        direction = item.get("direction", "").strip()
        if not (topic and ros_type and sim_type and direction):
            continue
        if direction == "sim_to_ros":
            bridge_args.append(f"{topic}@{ros_type}[{sim_type}")
        elif direction == "ros_to_sim":
            bridge_args.append(f"{topic}@{ros_type}]{sim_type}")
    return bridge_args


def _build_launch(context):
    allowlist_path = LaunchConfiguration("allowlist_path").perform(context)
    bridge_args = _build_parameter_bridge_args(allowlist_path)

    actions = [
        LogInfo(msg=["[sim_isaac_bridge] allowlist: ", allowlist_path]),
        LogInfo(msg=["[sim_isaac_bridge] bridge topic count: ", str(len(bridge_args))]),
    ]

    if bridge_args:
        actions.append(
            Node(
                package="ros_gz_bridge",
                executable="parameter_bridge",
                arguments=bridge_args,
                output="screen",
            )
        )
    else:
        actions.append(LogInfo(msg="[sim_isaac_bridge] No bridge topics configured; lane is idle."))

    return actions


def generate_launch_description() -> LaunchDescription:
    default_allowlist = os.path.join(
        os.getcwd(),
        "runtime",
        "contracts",
        "isaac_bridge_allowlist.yaml",
    )
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "allowlist_path",
                default_value=default_allowlist,
                description="Path to ROS/Isaac bridge allowlist YAML.",
            ),
            OpaqueFunction(function=_build_launch),
        ]
    )
