#!/usr/bin/env python3

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # Get the current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # URDF file path - use standard RGB camera URDF
    urdf_file = os.path.join(get_package_share_directory('chasebot_description'), 'urdf', 'ros2_jetbot.urdf')
    
    # World file path
    world_file = os.path.join(get_package_share_directory('chasebot_description'), 'worlds', 'autonomous_golf_ball_world.world')
    
    # Read URDF file
    with open(urdf_file, 'r') as file:
        robot_description = file.read()
    
    # Gazebo launch
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(get_package_share_directory('gazebo_ros'), 'launch', 'gazebo.launch.py')
        ]),
        launch_arguments={'world': world_file}.items()
    )
    
    # Robot state publisher
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robot_description}]
    )
    
    # Spawn robot
    spawn_robot = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        name='spawn_entity',
        output='screen',
        arguments=['-entity', 'jetbot', '-topic', 'robot_description', '-x', '0', '-y', '0', '-z', '0.1']
    )
    
    # Vision to laserscan node (our custom node for IMX219)
    vision_to_laserscan = Node(
        package='chasebot_description',
        executable='ros2_vision_to_laserscan.py',
        name='vision_to_laserscan',
        output='screen',
        parameters=[{
            'scan_height_ratio': 0.5,      # Scan at middle of image
            'num_scan_samples': 180,        # 180 scan points (2 degree resolution)
            'scan_range_max': 3.0,          # Max 3 meters
            'scan_range_min': 0.2,          # Min 0.2 meters
            'obstacle_threshold': 80        # Dark pixels are obstacles
        }]
    )
    
    # Static transform for scan frame
    static_tf_scan = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_transform_publisher_scan',
        arguments=['0', '0', '0', '0', '0', '0', 'camera_optical_link', 'laser_frame']
    )
    
    # RViz for visualization (optional)
    rviz_config = os.path.join(current_dir, 'nav2_vision.rviz')
    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', rviz_config],
        condition=IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                os.path.join(get_package_share_directory('launch'), 'launch', 'if.launch.py')
            ]),
            launch_arguments={'arg': 'use_rviz', 'default': 'true'}.items()
        )
    )
    
    return LaunchDescription([
        # Launch arguments
        DeclareLaunchArgument(
            'use_rviz',
            default_value='false',
            description='Whether to start RViz'
        ),
        
        # Nodes
        gazebo,
        robot_state_publisher,
        spawn_robot,
        vision_to_laserscan,
        static_tf_scan
    ])
