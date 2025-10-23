#!/usr/bin/env python3

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, ExecuteProcess
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    # Get package directory
    pkg_dir = get_package_share_directory('chasebot_description')
    
    # Include the basic robot spawn (from Slice 1)
    basic_spawn_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_dir, 'ros2_config/launch/jetbot_basic_spawn.launch.py')
        )
    )
    
    # Add the simple odometry publisher
    odom_publisher = Node(
        package='chasebot_description',
        executable='simple_odom_publisher.py',
        name='simple_odom_publisher',
        output='screen',
        prefix=['stdbuf', '-o', 'L']
    )
    
    # Launch the diagnostic tool automatically for easy testing
    diagnostic_tool = ExecuteProcess(
        cmd=[
            'ros2', 'run', 'chasebot_description', 'debug_nav2_movement.py'
        ],
        output='screen',
        shell=True
    )
    
    return LaunchDescription([
        basic_spawn_launch,
        odom_publisher,
        diagnostic_tool
    ])
