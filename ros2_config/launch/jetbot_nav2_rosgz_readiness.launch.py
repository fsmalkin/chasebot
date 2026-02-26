#!/usr/bin/env python3
"""
Nav2 readiness launch for ROS-Gz simulation workflows.

This launch intentionally avoids gazebo_ros/classic Gazebo dependencies and
only brings up Nav2 against the existing ROS-Gz topics provided by the
canonical simulation stack.
"""

import os

from ament_index_python.packages import PackageNotFoundError
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def _resolve_default_params_file() -> str:
    source_path = os.environ.get('CHASECAR_SOURCE_PATH', '').strip()
    if source_path:
        candidate = os.path.join(source_path, 'ros2_config', 'params', 'nav2_params_simple.yaml')
        if os.path.isfile(candidate):
            return candidate

    try:
        share_dir = get_package_share_directory('chasebot_description')
    except PackageNotFoundError as exc:
        raise RuntimeError(
            'Unable to resolve nav2 params from package share and CHASECAR_SOURCE_PATH '
            'is not set to a valid source tree.'
        ) from exc

    return os.path.join(share_dir, 'ros2_config', 'params', 'nav2_params_simple.yaml')


def generate_launch_description() -> LaunchDescription:
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')

    use_sim_time = LaunchConfiguration('use_sim_time')
    autostart = LaunchConfiguration('autostart')
    params_file = LaunchConfiguration('params_file')

    default_params = _resolve_default_params_file()

    nav2_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            [
                nav2_bringup_dir,
                '/launch/navigation_launch.py',
            ]
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'autostart': autostart,
            'params_file': params_file,
            'use_composition': 'False',
        }.items(),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                'use_sim_time',
                default_value='true',
                description='Use simulation time',
            ),
            DeclareLaunchArgument(
                'autostart',
                default_value='true',
                description='Autostart Nav2 lifecycle nodes',
            ),
            DeclareLaunchArgument(
                'params_file',
                default_value=default_params,
                description='Nav2 params file',
            ),
            nav2_bringup,
        ]
    )
