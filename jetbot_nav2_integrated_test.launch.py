#!/usr/bin/env python3
"""
Integrated Nav2 test launch file.
Launches robot, vision, and Nav2 with our fixes.
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, ExecuteProcess
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import time

def generate_launch_description():
    # Get package directories
    chasebot_pkg = get_package_share_directory('chasebot_description')
    nav2_bringup_pkg = get_package_share_directory('nav2_bringup')
    
    # Launch configuration variables
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    
    # Paths
    nav2_params_file = os.path.join(chasebot_pkg, 'config', 'nav2_params_simple.yaml')
    if not os.path.exists(nav2_params_file):
        nav2_params_file = os.path.join(os.getcwd(), 'nav2_params_simple.yaml')
    
    return LaunchDescription([
        # Declare launch arguments
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation time'
        ),
        
        # 1. Launch base robot with Gazebo (includes camera and movement)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(chasebot_pkg, 'launch', 'jetbot_autonomous_ball_following.launch.py')
            )
        ),
        
        # 2. Vision to laser scan converter
        Node(
            package='chasebot_description',
            executable='ros2_vision_to_laserscan_hsv.py',
            name='vision_to_laserscan',
            output='screen',
            parameters=[{'use_sim_time': use_sim_time}]
        ),
        
        # 3. Launch Nav2 stack
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(nav2_bringup_pkg, 'launch', 'navigation_launch.py')
            ),
            launch_arguments={
                'use_sim_time': 'true',
                'params_file': nav2_params_file,
                'autostart': 'true'
            }.items()
        ),
        
        # 4. Ball to Nav2 goal converter
        Node(
            package='chasebot_description',
            executable='ros2_ball_to_nav_goal.py',
            name='ball_to_nav_goal',
            output='screen',
            parameters=[{'use_sim_time': use_sim_time}]
        ),
        
        # 5. Optional: Manual test goal sender (comment out for autonomous operation)
        # Node(
        #     package='chasebot_description',
        #     executable='test_nav2_minimal.py',
        #     name='nav2_test',
        #     output='screen',
        #     parameters=[{'use_sim_time': use_sim_time}]
        # ),
    ])
