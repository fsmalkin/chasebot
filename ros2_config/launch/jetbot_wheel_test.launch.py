#!/usr/bin/env python3
"""
Minimal launch file to demonstrate wheel axis fix
Spawns robot in Ignition Gazebo without control system
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    pkg_path = get_package_share_directory('chasebot_sim')
    sdf_path = os.path.join(pkg_path, 'ros2_config', 'urdf', 'jetbot_core_ignition.sdf')
    world_path = os.path.join(pkg_path, 'ros2_config', 'worlds', 'yolo_test_world.world')
    
    # Launch Ignition Gazebo
    ignition_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')
        ]),
        launch_arguments={
            'gz_args': f'-r -v 4 {world_path}',
            'use_sim_time': 'true'
        }.items()
    )
    
    # Bridge for cmd_vel
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/cmd_vel@geometry_msgs/msg/Twist@gz.msgs.Twist',
            '/model/jetbot/odometry@nav_msgs/msg/Odometry@gz.msgs.Odometry'
        ],
        output='screen'
    )
    
    # Spawn the robot
    spawner = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-name', 'jetbot',
            '-file', sdf_path,
            '-x', '0',
            '-y', '0',
            '-z', '0.1'
        ],
        output='screen'
    )
    
    return LaunchDescription([
        ignition_launch,
        bridge,
        spawner
    ])
