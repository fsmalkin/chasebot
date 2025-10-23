#!/usr/bin/env python3

"""
Launch file for JetBot golf ball detection test
Spawns JetBot with camera in golf ball world and runs detection test
"""

import os
from launch import LaunchDescription
from launch.actions import ExecuteProcess, DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # Get file paths
    pkg_share = get_package_share_directory('chasebot_description')
    urdf_file = os.path.join(pkg_share, 'urdf', 'ros2_jetbot.urdf')
    world_file = os.path.join(pkg_share, 'worlds', 'autonomous_golf_ball_world.world')
    
    return LaunchDescription([
        # Launch arguments
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation time'
        ),
        
        # Start Gazebo with golf ball world
        ExecuteProcess(
            cmd=['gazebo', '--verbose', '-s', 'libgazebo_ros_factory.so', world_file],
            output='screen'
        ),
        
        # Spawn JetBot robot
        Node(
            package='gazebo_ros',
            executable='spawn_entity.py',
            name='spawn_jetbot',
            arguments=[
                '-entity', 'jetbot',
                '-file', urdf_file,
                '-x', '0', '-y', '0', '-z', '0.1'
            ],
            output='screen'
        ),
        
        # Robot state publisher
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            parameters=[{
                'robot_description': open(urdf_file).read(),
                'use_sim_time': LaunchConfiguration('use_sim_time')
            }],
            output='screen'
        ),
        
        # Joint state publisher
        Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            name='joint_state_publisher',
            parameters=[{'use_sim_time': LaunchConfiguration('use_sim_time')}],
            output='screen'
        ),
        
        # Detection Test Script
        ExecuteProcess(
            cmd=['python3', os.path.join(pkg_share, 'scripts', 'ros2_detection_test.py')],
            output='screen'
        ),
    ])
