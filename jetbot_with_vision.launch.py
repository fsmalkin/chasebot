#!/usr/bin/env python3
"""
ChaseBot ROS 2 Launch File - JetBot with Vision Detection
Phase 3, Step 3.2 - Basic Vision Integration
Launches JetBot simulation + simple vision detector
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    
    # Package and file paths
    pkg_share = FindPackageShare('chasebot_description').find('chasebot_description')
    urdf_file = os.path.join(pkg_share, 'urdf', 'ros2_jetbot.urdf')
    
    # Launch arguments
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation time if true'
    )
    
    # Read URDF file
    robot_description = Command(['cat ', urdf_file])
    
    return LaunchDescription([
        use_sim_time_arg,
        
        # Launch Gazebo with empty world
        ExecuteProcess(
            cmd=['gazebo', '--verbose', '-s', 'libgazebo_ros_factory.so'],
            output='screen'
        ),
        
        # Robot state publisher
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{
                'robot_description': robot_description,
                'use_sim_time': LaunchConfiguration('use_sim_time')
            }]
        ),
        
        # Joint state publisher
        Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            name='joint_state_publisher',
            output='screen',
            parameters=[{
                'use_sim_time': LaunchConfiguration('use_sim_time')
            }]
        ),
        
        # Spawn robot in Gazebo
        Node(
            package='gazebo_ros',
            executable='spawn_entity.py',
            name='spawn_jetbot',
            output='screen',
            arguments=[
                '-entity', 'jetbot',
                '-topic', '/robot_description',
                '-x', '0.0',
                '-y', '0.0',
                '-z', '0.1'
            ]
        ),
        
        # Simple Vision Detector
        ExecuteProcess(
            cmd=['python3', os.path.join(pkg_share, 'scripts', 'ros2_simple_vision_detector.py')],
            output='screen'
        )
    ])
