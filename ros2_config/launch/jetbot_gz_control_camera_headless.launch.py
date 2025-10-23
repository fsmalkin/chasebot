#!/usr/bin/env python3
"""
Launch file for JetBot with gz_ros2_control - Camera Headless Version
Runs simulation in server-only mode without GUI, but still publishes camera topics
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, RegisterEventHandler, SetEnvironmentVariable, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    # Get package directories
    pkg_chasebot_sim = get_package_share_directory('chasebot_sim')
    
    # Set paths
    world_path = PathJoinSubstitution([
        FindPackageShare('chasebot_sim'),
        'ros2_config', 'worlds', 'yolo_test_world.world'
    ])

    # Using v1.2.0 model with RGB camera sensor
    sdf_path = PathJoinSubstitution([
        FindPackageShare('chasebot_sim'),
        'ros2_config', 'urdf', 'jetbot_core_ignition_v1.2.0.sdf'
    ])

    # Set environment variable for plugin path
    set_ign_plugin_path = SetEnvironmentVariable(
        name='IGN_GAZEBO_SYSTEM_PLUGIN_PATH',
        value='/opt/ros/humble/lib'
    )
    
    # Start Ignition Gazebo in headless mode (server only, no GUI)
    ignition_spawn = ExecuteProcess(
        cmd=['ign', 'gazebo', '-s', '-v', '4', '-r', world_path],  # -s flag for server-only mode
        output='screen'
    )

    # Bridge between Ignition and ROS2
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock',
            '/model/jetbot/cmd_vel@geometry_msgs/msg/Twist]ignition.msgs.Twist',
            '/model/jetbot/odometry@nav_msgs/msg/Odometry[ignition.msgs.Odometry',
            '/model/jetbot/tf@tf2_msgs/msg/TFMessage[ignition.msgs.Pose_V',
            '/world/yolo_test_world/model/jetbot/joint_state@sensor_msgs/msg/JointState[ignition.msgs.Model',
            # Camera topic bridge
            '/d415/image_raw@sensor_msgs/msg/Image[ignition.msgs.Image',
            '/d415/camera_info@sensor_msgs/msg/CameraInfo[ignition.msgs.CameraInfo'
        ],
        output='screen'
    )

    # Spawn the robot
    spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=['-file', sdf_path, '-name', 'jetbot'],
        output='screen'
    )

    # Load controllers after robot spawn
    load_joint_state_broadcaster = ExecuteProcess(
        cmd=['ros2', 'control', 'load_controller', '--set-state', 'active',
             'joint_state_broadcaster'],
        output='screen'
    )

    load_diff_drive_controller = ExecuteProcess(
        cmd=['ros2', 'control', 'load_controller', '--set-state', 'active',
             'jetbot_base_controller'],
        output='screen'
    )

    # Test movement after 10 seconds
    test_movement = TimerAction(
        period=10.0,
        actions=[
            ExecuteProcess(
                cmd=['ros2', 'topic', 'pub', '--once',
                     '/jetbot_base_controller/cmd_vel',
                     'geometry_msgs/msg/TwistStamped',
                     '{twist: {linear: {x: 0.2}, angular: {z: 0.0}}}'],
                output='screen'
            )
        ]
    )

    return LaunchDescription([
        set_ign_plugin_path,
        ignition_spawn,
        bridge,
        TimerAction(
            period=2.0,
            actions=[spawn_entity]
        ),
        TimerAction(
            period=5.0,
            actions=[load_joint_state_broadcaster]
        ),
        TimerAction(
            period=6.0,
            actions=[load_diff_drive_controller]
        ),
        test_movement
    ])
