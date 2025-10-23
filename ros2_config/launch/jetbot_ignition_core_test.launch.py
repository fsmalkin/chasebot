#!/usr/bin/env python3

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, ExecuteProcess
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # Get paths
    chasebot_description_share = FindPackageShare('chasebot_description')
    
    # World with golf ball
    world_file = PathJoinSubstitution([
        chasebot_description_share,
        'ros2_config', 'worlds', 'yolo_test_world.world'
    ])
    
    # JetBot SDF model
    jetbot_sdf = PathJoinSubstitution([
        chasebot_description_share,
        'ros2_config', 'urdf', 'jetbot_core_ignition.sdf'
    ])
    
    # Launch arguments
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation time'
    )
    
    world_arg = DeclareLaunchArgument(
        'world',
        default_value=world_file,
        description='Path to world file'
    )
    
    # Launch Ignition Gazebo with our world
    ignition_gazebo = ExecuteProcess(
        cmd=['ign', 'gazebo', '-v', '4', LaunchConfiguration('world')],
        output='screen'
    )
    
    # Spawn the JetBot robot
    spawn_jetbot = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-file', jetbot_sdf,
            '-name', 'jetbot',
            '-x', '0.0',
            '-y', '0.0',
            '-z', '0.1'
        ],
        output='screen'
    )
    
    # Bridge cmd_vel topic (ROS2 -> Ignition)
    cmd_vel_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            'cmd_vel@geometry_msgs/msg/Twist@ignition.msgs.Twist'
        ],
        output='screen'
    )
    
    # Bridge odometry topic (Ignition -> ROS2)
    odom_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            'odom@nav_msgs/msg/Odometry@ignition.msgs.Odometry'
        ],
        output='screen'
    )
    
    # Bridge TF (Ignition -> ROS2)
    tf_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/tf@tf2_msgs/msg/TFMessage@ignition.msgs.Pose_V'
        ],
        output='screen'
    )
    
    return LaunchDescription([
        use_sim_time_arg,
        world_arg,
        ignition_gazebo,
        spawn_jetbot,
        cmd_vel_bridge,
        odom_bridge,
        tf_bridge
    ])
