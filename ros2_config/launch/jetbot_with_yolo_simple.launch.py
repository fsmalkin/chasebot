#!/usr/bin/env python3
"""
Slice 3 Simple: Basic Gazebo + Robot Spawn + Static Transforms + YOLO Detection (without cleanup)
"""

import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, ExecuteProcess, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # Package directories
    pkg_share = get_package_share_directory('chasebot_description')
    
    # World file path - now includes a golf ball
    world_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..',
        'worlds',
        'yolo_test_world.world'
    )
    
    # Launch Gazebo with specified world
    gazebo = ExecuteProcess(
        cmd=['gazebo', '--verbose', world_file, '-s', 'libgazebo_ros_factory.so'],
        output='screen',
        additional_env={'GAZEBO_MODEL_PATH': os.path.dirname(world_file)}
    )
    
    # Spawn robot with delay (5 seconds after Gazebo starts)
    spawn_robot = TimerAction(
        period=5.0,
        actions=[
            Node(
                package='gazebo_ros',
                executable='spawn_entity.py',
                name='spawn_jetbot',
                arguments=[
                    '-entity', 'jetbot',
                    '-file', os.path.join(pkg_share, 'urdf', 'ros2_jetbot.urdf'),
                    '-x', '0.0',
                    '-y', '0.0',
                    '-z', '0.05'
                ],
                output='screen',
                parameters=[{'use_sim_time': True}]
            )
        ]
    )
    
    # Static transform publishers (added at 9 seconds)
    # 1. Map to odom transform (required for Nav2)
    map_to_odom_tf = TimerAction(
        period=9.0,
        actions=[
            Node(
                package='tf2_ros',
                executable='static_transform_publisher',
                name='map_to_odom_tf_publisher',
                arguments=['0', '0', '0', '0', '0', '0', 'map', 'odom'],
                output='screen',
                parameters=[{'use_sim_time': True}]
            )
        ]
    )
    
    # 2. Base_link to camera_link transform (often missing from Gazebo)
    base_to_camera_tf = TimerAction(
        period=9.0,
        actions=[
            Node(
                package='tf2_ros',
                executable='static_transform_publisher',
                name='base_to_camera_tf_publisher',
                arguments=['0.07', '0', '0.12', '0', '0', '0', 'base_link', 'camera_link'],
                output='screen',
                parameters=[{'use_sim_time': True}]
            )
        ]
    )
    
    # 3. Camera_link to camera_optical_link transform (optical frame convention)
    camera_to_optical_tf = TimerAction(
        period=9.0,
        actions=[
            Node(
                package='tf2_ros',
                executable='static_transform_publisher',
                name='camera_to_optical_tf_publisher',
                arguments=['0', '0', '0', '-1.5708', '0', '-1.5708', 'camera_link', 'camera_optical_link'],
                output='screen',
                parameters=[{'use_sim_time': True}]
            )
        ]
    )
    
    # YOLO Detection Node (added at 12 seconds, after transforms are established)
    yolo_detector = TimerAction(
        period=12.0,
        actions=[
            Node(
                package='chasebot_description',
                executable='ros2_yolo_detector.py',
                name='yolo_detector',
                output='screen',
                parameters=[{'use_sim_time': True}]
            )
        ]
    )
    
    return LaunchDescription([
        # Core simulation
        gazebo,
        spawn_robot,
        
        # Transform publishers
        map_to_odom_tf,
        base_to_camera_tf,
        camera_to_optical_tf,
        
        # YOLO detection
        yolo_detector
    ])
