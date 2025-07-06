#!/usr/bin/env python3

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, TimerAction
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
    
    # Start Gazebo with GUI (using working display configuration)
    start_gazebo_cmd = ExecuteProcess(
        cmd=['ign', 'gazebo', '-v', '4', world_path],
        output='screen',
        additional_env={
            'DISPLAY': '172.25.128.1:0.0',
            'QT_X11_NO_MITSHM': '1',
            'LIBGL_ALWAYS_SOFTWARE': '1',
            'IGN_GAZEBO_SYSTEM_PLUGIN_PATH': '/opt/ros/humble/lib'
        }
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
    
    # Minimal URDF with ros2_control tags for robot_state_publisher
    minimal_urdf = '''<?xml version="1.0"?>
    <robot name="jetbot">
        <link name="base_link"/>
        <link name="left_wheel"/>
        <link name="right_wheel"/>
        <joint name="left_wheel_joint" type="continuous">
            <parent link="base_link"/>
            <child link="left_wheel"/>
            <origin xyz="0 0.08 0.032"/>
            <axis xyz="0 1 0"/>
        </joint>
        <joint name="right_wheel_joint" type="continuous">
            <parent link="base_link"/>
            <child link="right_wheel"/>
            <origin xyz="0 -0.08 0.032"/>
            <axis xyz="0 1 0"/>
        </joint>
        
        <ros2_control name="GazeboSimSystem" type="system">
            <hardware>
                <plugin>gz_ros2_control/GazeboSimSystem</plugin>
            </hardware>
            <joint name="left_wheel_joint">
                <command_interface name="velocity">
                    <param name="min">-10</param>
                    <param name="max">10</param>
                </command_interface>
                <state_interface name="position"/>
                <state_interface name="velocity"/>
            </joint>
            <joint name="right_wheel_joint">
                <command_interface name="velocity">
                    <param name="min">-10</param>
                    <param name="max">10</param>
                </command_interface>
                <state_interface name="position"/>
                <state_interface name="velocity"/>
            </joint>
        </ros2_control>
    </robot>'''
    
    # Robot state publisher
    robot_state_publisher_cmd = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{
            'use_sim_time': use_sim_time,
            'robot_description': minimal_urdf
        }],
        output='screen'
    )
    
    # Spawn controllers using the Gazebo-internal controller manager
    # Wait longer to ensure gz_ros2_control is fully initialized
    spawn_joint_state_broadcaster_cmd = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster', '--controller-manager', '/controller_manager'],
        output='screen'
    )
    
    spawn_diff_drive_controller_cmd = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['jetbot_base_controller', '--controller-manager', '/controller_manager'],
        output='screen'
    )
    
    # Create the launch description and populate
    ld = LaunchDescription()
    
    # Declare the launch options
    ld.add_action(declare_use_sim_time_cmd)
    ld.add_action(declare_world_file_cmd)
    
    # Add the actions to launch
    ld.add_action(start_gazebo_cmd)
    ld.add_action(robot_state_publisher_cmd)
    ld.add_action(ros_gz_bridge_cmd)
    
    # Add delays for proper startup sequence
    ld.add_action(TimerAction(
        period=5.0,
        actions=[spawn_robot_cmd]
    ))
    
    # Wait for gz_ros2_control to be fully initialized
    ld.add_action(TimerAction(
        period=10.0,
        actions=[spawn_joint_state_broadcaster_cmd]
    ))
    
    ld.add_action(TimerAction(
        period=12.0,
        actions=[spawn_diff_drive_controller_cmd]
    ))
    
    return ld
