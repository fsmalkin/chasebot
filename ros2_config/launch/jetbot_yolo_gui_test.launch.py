#!/usr/bin/env python3

import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument, ExecuteProcess
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # Launch Gazebo with golf ball world
    gazebo = ExecuteProcess(
        cmd=['gazebo', '--verbose', '-s', 'libgazebo_ros_factory.so', '/mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/worlds/simple_golf_ball_world.world'],
        output='screen'
    )
    
    # Robot state publisher
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        arguments=['/mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/urdf/ros2_jetbot.urdf']
    )
    
    # Spawn robot
    spawn_robot = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        arguments=[
            '-file', '/mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/urdf/ros2_jetbot.urdf',
            '-entity', 'jetbot',
            '-x', '0',
            '-y', '0',
            '-z', '0.05'
        ],
        output='screen'
    )
    
    # YOLO detection node
    yolo_detector = Node(
        package='yolo_ros',
        executable='yolo_node',
        name='yolo_node',
        parameters=[{
            'image_topic': '/camera/image_raw',
            'detection_topic': '/yolo/detections',
            'model': 'yolov8m',
            'threshold': 0.5,
            'device': 'cpu'
        }],
        output='screen'
    )
    
    # YOLO tracking node (optional)
    yolo_tracker = Node(
        package='yolo_ros',
        executable='tracking_node',
        name='tracking_node',
        parameters=[{
            'image_topic': '/camera/image_raw',
            'detection_topic': '/yolo/detections',
            'tracking_topic': '/yolo/tracking'
        }],
        output='screen'
    )
    
    # YOLO debug node for visualization
    yolo_debug = Node(
        package='yolo_ros',
        executable='debug_node',
        name='debug_node',
        parameters=[{
            'image_topic': '/camera/image_raw',
            'detection_topic': '/yolo/detections',
            'output_topic': '/yolo/debug_image'
        }],
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
