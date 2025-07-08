#!/usr/bin/env python3
"""
Launch file for JetBot with D415 camera and YOLO v8 detection
Slice 2: Connect yolo_ros to D415 camera (2D only)
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, TimerAction, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, FindExecutable, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    # Get package directories
    pkg_chasebot_sim = get_package_share_directory('chasebot_description')
    pkg_yolo_bringup = get_package_share_directory('yolo_bringup')
    
    # Set paths
    world_path = PathJoinSubstitution([
        FindPackageShare('chasebot_description'),
        'ros2_config', 'worlds', 'yolo_test_world.world'
    ])

    # Using v1.3.0 model with camera sensor plugin
    sdf_path = PathJoinSubstitution([
        FindPackageShare('chasebot_description'),
        'ros2_config', 'urdf', 'jetbot_core_ignition_v1.3.0.sdf'
    ])
    
    # Controller configuration file
    controller_config = PathJoinSubstitution([
        FindPackageShare('chasebot_description'),
        'ros2_config', 'config', 'jetbot_diff_drive_v1.0.0.yaml'
    ])

    # Set environment variable for plugin path
    set_ign_plugin_path = SetEnvironmentVariable(
        name='IGN_GAZEBO_SYSTEM_PLUGIN_PATH',
        value='/opt/ros/humble/lib'
    )
    
    # Start Ignition Gazebo
    ignition_spawn = ExecuteProcess(
        cmd=['ign', 'gazebo', '-v', '4', '-r', world_path],
        output='screen',
        additional_env={
            'DISPLAY': os.environ.get('DISPLAY', ':0'),
            'QT_X11_NO_MITSHM': '1',
            'LIBGL_ALWAYS_SOFTWARE': '1',
            'IGN_GAZEBO_SYSTEM_PLUGIN_PATH': '/opt/ros/humble/lib'
        }
    )

    # Minimal URDF with ros2_control tags
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
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{
            'use_sim_time': True,
            'robot_description': minimal_urdf
        }],
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

    # Spawn controllers
    spawn_joint_state_broadcaster = Node(
        package='controller_manager',
        executable='spawner',
        arguments=[
            'joint_state_broadcaster',
            '--controller-manager', '/controller_manager',
            '--controller-manager-timeout', '30',
            '--switch-timeout', '20',
            '--param-file', controller_config
        ],
        output='screen'
    )

    spawn_diff_drive_controller = Node(
        package='controller_manager',
        executable='spawner',
        arguments=[
            'jetbot_base_controller',
            '--controller-manager', '/controller_manager',
            '--controller-manager-timeout', '30',
            '--switch-timeout', '20',
            '--param-file', controller_config
        ],
        output='screen'
    )

    # YOLO v8 launch with D415 camera configuration
    yolo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            pkg_yolo_bringup, '/launch/yolov8.launch.py'
        ]),
        launch_arguments={
            'model': 'yolov8m.pt',
            'tracker': 'bytetrack.yaml',
            'device': 'cuda:0',  # Use CPU if no GPU: 'cpu'
            'enable': 'True',
            'threshold': '0.5',
            'input_image_topic': '/d415/image_raw',  # Connect to D415 camera
            'image_reliability': '1',
            'namespace': 'yolo',
        }.items()
    )

    # Monitor detections (for debugging)
    detection_monitor = Node(
        package='chasebot_description',
        executable='monitor_yolo_detections.py',
        name='detection_monitor',
        output='screen',
        parameters=[{'use_sim_time': True}]
    )

    return LaunchDescription([
        set_ign_plugin_path,
        ignition_spawn,
        robot_state_publisher,
        bridge,
        TimerAction(
            period=2.0,
            actions=[spawn_entity]
        ),
        TimerAction(
            period=7.0,
            actions=[spawn_joint_state_broadcaster]
        ),
        TimerAction(
            period=9.0,
            actions=[spawn_diff_drive_controller]
        ),
        TimerAction(
            period=12.0,
            actions=[yolo_launch]
        ),
        TimerAction(
            period=15.0,
            actions=[detection_monitor]
        )
    ])
