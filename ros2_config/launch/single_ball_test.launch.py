#!/usr/bin/env python3
"""
Minimal launch file for single ball testing.
Components are launched separately by the test runner for better control.
This file is for reference and can be used for manual testing.
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, TimerAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # Package directory
    pkg_dir = get_package_share_directory('chasebot_description')
    
    # World file
    world_file = os.path.join(pkg_dir, 'ros2_config', 'worlds', 'single_ball_test.world')
    
    # URDF file
    urdf_file = os.path.join(pkg_dir, 'ros2_config', 'urdf', 'ros2_jetbot.urdf')
    
    # Launch arguments
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    
    return LaunchDescription([
        # Declare launch arguments
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation (Gazebo) clock if true'
        ),
        
        # Launch Gazebo with empty world first
        ExecuteProcess(
            cmd=['gazebo', '--verbose', world_file, '-s', 'libgazebo_ros_init.so', '-s', 'libgazebo_ros_factory.so'],
            output='screen'
        ),
        
        # Robot state publisher (needed for transforms)
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{'use_sim_time': use_sim_time}],
            arguments=[urdf_file]
        ),
        
        # Spawn robot after Gazebo starts
        TimerAction(
            period=5.0,
            actions=[
                ExecuteProcess(
                    cmd=['ros2', 'run', 'gazebo_ros', 'spawn_entity.py',
                         '-file', urdf_file,
                         '-entity', 'jetbot',
                         '-x', '0', '-y', '0', '-z', '0.05'],
                    output='screen'
                )
            ]
        ),
        
        # Note: Nav2, YOLO, and ball spawning are handled by the test runner
        # for better timing control and visual feedback
    ])
