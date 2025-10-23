#!/usr/bin/env python3

"""
Simple Camera Orientation Test Launch File
Just spawns the world and robot, no control system
"""

import os
from launch import LaunchDescription
from launch.actions import ExecuteProcess, SetEnvironmentVariable
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    pkg_share = get_package_share_directory('chasebot_sim')
    
    # Set IGN_GAZEBO_SYSTEM_PLUGIN_PATH for camera sensors
    set_ign_plugin_path = SetEnvironmentVariable(
        'IGN_GAZEBO_SYSTEM_PLUGIN_PATH',
        '/opt/ros/humble/lib'
    )
    
    # Robot description (SDF file path)
    robot_description_path = os.path.join(pkg_share, 'ros2_config', 'urdf', 'jetbot_core_ignition_v1.3.0.sdf')
    
    # Start Ignition Gazebo with camera orientation test world
    ignition_spawn = ExecuteProcess(
        cmd=['ign', 'gazebo', 
             os.path.join(pkg_share, 'ros2_config', 'worlds', 'camera_orientation_test_world.world'),
             '-r', '-v', '3'],
        output='screen'
    )
    
    # Spawn robot entity
    spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-name', 'jetbot',
            '-x', '0.0',
            '-y', '0.0',
            '-z', '0.05',
            '-R', '0.0',
            '-P', '0.0',
            '-Y', '0.0',
            '-file', robot_description_path
        ],
        output='screen'
    )
    
    # Bridge for camera topics only
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock',
            '/d415/image_raw@sensor_msgs/msg/Image@ignition.msgs.Image',
            '/d415/camera_info@sensor_msgs/msg/CameraInfo@ignition.msgs.CameraInfo',
        ],
        output='screen'
    )
    
    return LaunchDescription([
        set_ign_plugin_path,
        ignition_spawn,
        spawn_entity,
        bridge
    ])
