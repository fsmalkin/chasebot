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
    
    # URDF file path
    urdf_file = os.path.join(current_dir, 'ros2_jetbot_depth.urdf')
    
    # World file path
    world_file = os.path.join(current_dir, 'autonomous_golf_ball_world.world')
    
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
    
    # Depthimage to laserscan node
    depthimage_to_laserscan = Node(
        package='depthimage_to_laserscan',
        executable='depthimage_to_laserscan_node',
        name='depthimage_to_laserscan',
        remappings=[
            ('depth', '/camera/depth/image_raw'),
            ('depth_camera_info', '/camera/depth/camera_info'),
            ('scan', '/scan')
        ],
        parameters=[{
            'scan_height': 10,
            'output_frame_id': 'camera_optical_link',
            'range_min': 0.1,
            'range_max': 10.0
        }]
    )
    
    # Static transform for laser scan frame
    static_tf_laser = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_transform_publisher_laser',
        arguments=['0', '0', '0', '0', '0', '0', 'base_link', 'laser_frame']
    )
    
    return LaunchDescription([
        gazebo,
        robot_state_publisher,
        spawn_robot,
        depthimage_to_laserscan,
        static_tf_laser
    ])
