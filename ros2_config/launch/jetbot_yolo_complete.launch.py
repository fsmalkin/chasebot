#!/usr/bin/env python3

import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    package_share = get_package_share_directory('chasebot_description')
    world_file = os.path.join(
        package_share,
        'ros2_config',
        'worlds',
        'simple_golf_ball_world.world',
    )
    urdf_file = os.path.join(
        package_share,
        'ros2_config',
        'urdf',
        'ros2_jetbot.urdf',
    )

    # Include the gazebo_ros package's gazebo.launch.py
    # This ensures all ROS plugins are loaded properly
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(get_package_share_directory('gazebo_ros'), 'launch', 'gazebo.launch.py')
        ]),
        launch_arguments={
            'world': world_file,
            'verbose': 'true'
        }.items()
    )
    
    # Robot state publisher
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        arguments=[urdf_file]
    )
    
    # Spawn robot with delay to ensure Gazebo is ready
    spawn_robot = TimerAction(
        period=5.0,  # Wait 5 seconds for Gazebo to fully load
        actions=[
            Node(
                package='gazebo_ros',
                executable='spawn_entity.py',
                arguments=[
                    '-file', urdf_file,
                    '-entity', 'jetbot',
                    '-x', '0',
                    '-y', '0',
                    '-z', '0.05'
                ],
                output='screen'
            )
        ]
    )
    
    # YOLO detection node
    yolo_detector = Node(
        package='yolo_ros',
        executable='yolo_node',
        name='yolo_node',
        remappings=[
            ('image_raw', '/camera/image_raw'),
            ('detections', '/yolo/detections')
        ],
        parameters=[{
            'model': 'yolov8m',
            'threshold': 0.5,
            'device': 'cpu'
        }],
        output='screen'
    )
    
    # YOLO tracking node
    yolo_tracker = Node(
        package='yolo_ros',
        executable='tracking_node',
        name='tracking_node',
        remappings=[
            ('image_raw', '/camera/image_raw'),
            ('detections', '/yolo/detections'),
            ('tracking', '/yolo/tracking')
        ],
        output='screen'
    )
    
    # YOLO debug node for visualization
    yolo_debug = Node(
        package='yolo_ros',
        executable='debug_node',
        name='debug_node',
        remappings=[
            ('image_raw', '/camera/image_raw'),
            ('detections', '/yolo/detections'),
            ('dbg_image', '/yolo/debug_image')
        ],
        output='screen'
    )
    
    return LaunchDescription([
        gazebo,
        robot_state_publisher,
        spawn_robot,
        yolo_detector,
        yolo_tracker,
        yolo_debug
    ])
