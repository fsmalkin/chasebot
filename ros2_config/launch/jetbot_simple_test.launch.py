#!/usr/bin/env python3
"""
Simple test to verify Gazebo display works
"""

import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, LogInfo
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    pkg_gazebo_ros = get_package_share_directory('gazebo_ros')
    pkg_description = get_package_share_directory('chasebot_description')
    
    world_path = os.path.join(pkg_description, 'ros2_config', 'worlds', 'single_ball_test.world')
    
    return LaunchDescription([
        LogInfo(msg='Testing Gazebo display...'),
        LogInfo(msg='If Gazebo window appears, display is working!'),
        
        # Just launch Gazebo
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_gazebo_ros, 'launch', 'gazebo.launch.py')
            ),
            launch_arguments={
                'world': world_path,
                'verbose': 'false'
            }.items()
        ),
    ])
