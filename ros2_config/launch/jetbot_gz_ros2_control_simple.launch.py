#!/usr/bin/env python3

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    
    # Launch configuration variables
    use_sim_time = LaunchConfiguration('use_sim_time')
    world_file = LaunchConfiguration('world_file')
    
    # Declare the launch arguments
    declare_use_sim_time_cmd = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation (Gazebo) clock if true'
    )
    
    declare_world_file_cmd = DeclareLaunchArgument(
        'world_file',
        default_value='yolo_test_world.world',
        description='World file to load'
    )
    
    # Paths
    world_path = PathJoinSubstitution([
        FindPackageShare('chasebot_description'),
        'ros2_config', 'worlds', world_file
    ])
    
    sdf_path = PathJoinSubstitution([
        FindPackageShare('chasebot_description'),
        'ros2_config', 'urdf', 'jetbot_core_ignition.sdf'
    ])
    
    controller_config = PathJoinSubstitution([
        FindPackageShare('chasebot_description'),
        'ros2_config', 'config', 'jetbot_controllers.yaml'
    ])
    
    # Start Gazebo server (headless)
    start_gazebo_server_cmd = ExecuteProcess(
        cmd=['gz', 'sim', world_path, '-s', '--verbose'],
        output='screen'
    )
    
    # Spawn the robot
    spawn_robot_cmd = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=['-file', sdf_path, '-name', 'jetbot'],
        output='screen'
    )
    
    # ROS-Gazebo bridge for basic topics
    ros_gz_bridge_cmd = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock',
            '--ros-args', '--log-level', 'warn'
        ],
        output='screen'
    )
    
    # Start controller manager
    controller_manager_cmd = Node(
        package='controller_manager',
        executable='ros2_control_node',
        parameters=[controller_config],
        output='screen',
        remappings=[
            ('~/robot_description', '/robot_description'),
        ]
    )
    
    # Spawn joint state broadcaster
    spawn_joint_state_broadcaster_cmd = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster'],
        output='screen'
    )
    
    # Spawn differential drive controller
    spawn_diff_drive_controller_cmd = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['jetbot_base_controller'],
        output='screen'
    )
    
    # Robot state publisher
    robot_state_publisher_cmd = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen'
    )
    
    # Create the launch description and populate
    ld = LaunchDescription()
    
    # Declare the launch options
    ld.add_action(declare_use_sim_time_cmd)
    ld.add_action(declare_world_file_cmd)
    
    # Add the actions to launch
    ld.add_action(start_gazebo_server_cmd)
    ld.add_action(spawn_robot_cmd)
    ld.add_action(ros_gz_bridge_cmd)
    ld.add_action(controller_manager_cmd)
    ld.add_action(spawn_joint_state_broadcaster_cmd)
    ld.add_action(spawn_diff_drive_controller_cmd)
    ld.add_action(robot_state_publisher_cmd)
    
    return ld
