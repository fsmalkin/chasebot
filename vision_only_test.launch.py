#!/usr/bin/env python3

import os
from launch import LaunchDescription
from launch.actions import ExecuteProcess, TimerAction
from launch_ros.actions import Node
from launch.substitutions import Command
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # Get the urdf file path
    urdf_path = os.path.expanduser('~/ros2_ws/src/chasebot_description/urdf/ros2_jetbot.urdf')
    
    # Read URDF content
    with open(urdf_path, 'r') as file:
        robot_description_content = file.read()
    
    # SDF file for golf ball
    sdf_path = os.path.expanduser('~/ros2_ws/green_golf_ball.sdf')
    
    return LaunchDescription([
        # Launch Gazebo
        ExecuteProcess(
            cmd=['gazebo', '--verbose', '-s', 'libgazebo_ros_factory.so'],
            output='screen'
        ),
        
        # Wait a bit then spawn golf ball
        TimerAction(
            period=5.0,
            actions=[
                ExecuteProcess(
                    cmd=['ros2', 'run', 'gazebo_ros', 'spawn_entity.py',
                         '-file', sdf_path,
                         '-entity', 'golf_ball',
                         '-x', '1.0', '-y', '0.0', '-z', '0.025'],
                    output='screen'
                )
            ]
        ),
        
        # Wait then spawn robot
        TimerAction(
            period=7.0,
            actions=[
                Node(
                    package='gazebo_ros',
                    executable='spawn_entity.py',
                    arguments=['-entity', 'jetbot',
                              '-x', '0', '-y', '0', '-z', '0.1',
                              '-topic', 'robot_description'],
                    output='screen'
                ),
            ]
        ),
        
        # Robot state publisher
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_description_content}]
        ),
        
        # Vision to laserscan node
        TimerAction(
            period=10.0,
            actions=[
                Node(
                    package='chasebot_description',
                    executable='ros2_vision_to_laserscan_hsv.py',
                    name='vision_to_laserscan',
                    output='screen'
                )
            ]
        ),
    ])
