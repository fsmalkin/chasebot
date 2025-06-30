#!/usr/bin/env python3

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # Get package directory
    pkg_dir = get_package_share_directory('chasebot_description')
    
    # Paths
    urdf_file = os.path.join(pkg_dir, 'urdf', 'ros2_jetbot.urdf')
    nav2_params_file = os.path.join(pkg_dir, 'nav2_params_simple.yaml')
    
    # Launch configuration
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    
    # Read URDF
    with open(urdf_file, 'r') as file:
        robot_description = file.read()
    
    # Core nodes only - minimal setup
    nodes = [
        # Robot state publisher
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{
                'robot_description': robot_description,
                'use_sim_time': use_sim_time
            }]
        ),
        
        # Static transform for scan frame
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='static_transform_publisher_scan',
            arguments=['0', '0', '0', '0', '0', '0', 'camera_optical_link', 'base_scan']
        ),
        
        # Just controller server for now - minimal Nav2
        Node(
            package='nav2_controller',
            executable='controller_server',
            name='controller_server',
            output='screen',
            parameters=[nav2_params_file],
            remappings=[
                ('/cmd_vel', '/cmd_vel'),
                ('/odom', '/odom')
            ]
        ),
        
        # Lifecycle manager for controller
        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            name='lifecycle_manager',
            output='screen',
            parameters=[{
                'use_sim_time': use_sim_time,
                'autostart': True,
                'node_names': ['controller_server']
            }]
        )
    ]
    
    return LaunchDescription([
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation time'
        ),
        *nodes
    ])
