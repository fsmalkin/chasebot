#!/usr/bin/env python3

import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, ExecuteProcess
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from launch.substitutions import LaunchConfiguration
from launch.actions import DeclareLaunchArgument

def generate_launch_description():
    # Get package directories
    chasebot_dir = get_package_share_directory('chasebot_description')
    yolo_dir = get_package_share_directory('yolo_bringup')
    
    # Launch arguments
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    
    # Include the basic JetBot simulation with camera
    jetbot_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(chasebot_dir, 'launch', 'jetbot_with_vision.launch.py')
        ),
        launch_arguments={'use_sim_time': use_sim_time}.items()
    )
    
    # Include YOLO detection - configured for sports ball detection
    yolo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(yolo_dir, 'launch', 'yolov8.launch.py')
        ),
        launch_arguments={
            'model': 'yolov8m.pt',  # Medium model for good accuracy
            'tracker': 'bytetrack.yaml',
            'device': 'cpu',  # Use CPU for WSL2 compatibility
            'enable': 'True',
            'threshold': '0.5',  # Detection confidence threshold
            'input_image_topic': '/camera/image_raw',
            'namespace': 'yolo',
            'image_reliability': '1'
        }.items()
    )
    
    # Simple detection viewer node (we'll create this next)
    detection_viewer = Node(
        package='chasebot_description',
        executable='yolo_detection_viewer.py',
        name='yolo_detection_viewer',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}]
    )
    
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        jetbot_launch,
        yolo_launch,
        # detection_viewer  # Commented out for now until we create it
    ])
