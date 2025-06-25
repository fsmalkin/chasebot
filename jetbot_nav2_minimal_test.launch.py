#!/usr/bin/env python3
"""
Minimal Nav2 test launch file.
Tests Nav2 with simplified configuration.
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    # Launch configuration variables
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    
    # Paths to config files
    nav2_params_file = os.path.join(os.getcwd(), 'nav2_params_simple.yaml')
    
    # Nodes to launch
    return LaunchDescription([
        # Declare launch arguments
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation time'
        ),
        
        # Launch Gazebo with JetBot and world
        Node(
            package='ros2launch',
            executable='launch',
            arguments=['jetbot_autonomous_ball_following.launch.py'],
            output='screen'
        ),
        
        # Vision to laser scan converter
        Node(
            package='ros2launch',
            executable='launch',
            arguments=['ros2_vision_to_laserscan_hsv.py'],
            output='screen'
        ),
        
        # Ball to Nav2 goal converter
        Node(
            package='ros2launch',
            executable='launch',
            arguments=['ros2_ball_to_nav_goal.py'],
            output='screen'
        ),
        
        # Nav2 bringup - simplified
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(get_package_share_directory('nav2_bringup'), 'launch', 'navigation_launch.py')
            ),
            launch_arguments={
                'use_sim_time': use_sim_time,
                'params_file': nav2_params_file,
                'autostart': 'true'
            }.items()
        ),
        
        # Minimal test node
        Node(
            package='ros2launch',
            executable='launch',
            arguments=['test_nav2_minimal.py'],
            output='screen'
        )
    ])
