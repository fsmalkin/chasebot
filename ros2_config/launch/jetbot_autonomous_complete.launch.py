#!/usr/bin/env python3
"""
ChaseBot Autonomous Complete Launch File
Addresses transform tree fragmentation and timing issues
Provides single-command launch for entire system
"""

import os
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, 
    ExecuteProcess, 
    IncludeLaunchDescription,
    LogInfo, 
    TimerAction,
    RegisterEventHandler
)
from launch.event_handlers import OnProcessStart, OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # Get package directories
    pkg_gazebo_ros = get_package_share_directory('gazebo_ros')
    pkg_description = get_package_share_directory('chasebot_description')
    
    # Launch configuration variables
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    world = LaunchConfiguration('world', default='single_ball_test.world')
    
    # Paths
    world_path = os.path.join(pkg_description, 'ros2_config', 'worlds', 'single_ball_test.world')
    urdf_path = os.path.join(pkg_description, 'ros2_config', 'urdf', 'ros2_jetbot.urdf')
    nav2_params_path = os.path.join(pkg_description, 'ros2_config', 'params', 'nav2_params_simple.yaml')
    
    # Read URDF
    with open(urdf_path, 'r') as infp:
        robot_desc = infp.read()
    
    return LaunchDescription([
        # Declare arguments
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation time'
        ),
        
        DeclareLaunchArgument(
            'world',
            default_value=world_path,
            description='Path to world file'
        ),
        
        # Step 1: Launch Gazebo with world
        LogInfo(msg='Step 1: Launching Gazebo with world...'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_gazebo_ros, 'launch', 'gazebo.launch.py')
            ),
            launch_arguments={
                'world': world_path,
                'verbose': 'true'
            }.items()
        ),
        
        # Step 2: Spawn robot (with delay for Gazebo to initialize)
        TimerAction(
            period=5.0,
            actions=[
                LogInfo(msg='Step 2: Spawning JetBot robot...'),
                Node(
                    package='gazebo_ros',
                    executable='spawn_entity.py',
                    arguments=[
                        '-file', urdf_path,
                        '-entity', 'jetbot',
                        '-x', '0',
                        '-y', '0',
                        '-z', '0.05'
                    ],
                    output='screen'
                )
            ]
        ),
        
        # Step 3: Robot State Publisher (with delay)
        TimerAction(
            period=7.0,
            actions=[
                LogInfo(msg='Step 3: Starting robot state publisher...'),
                Node(
                    package='robot_state_publisher',
                    executable='robot_state_publisher',
                    name='robot_state_publisher',
                    parameters=[{
                        'use_sim_time': use_sim_time,
                        'robot_description': robot_desc
                    }],
                    output='screen'
                )
            ]
        ),
        
        # Step 4: Critical Static Transforms (MUST be before Nav2!)
        TimerAction(
            period=8.0,
            actions=[
                LogInfo(msg='Step 4: Publishing critical static transforms...'),
                # Map to odom (required by Nav2)
                Node(
                    package='tf2_ros',
                    executable='static_transform_publisher',
                    name='map_to_odom_publisher',
                    arguments=['0', '0', '0', '0', '0', '0', 'map', 'odom'],
                    parameters=[{'use_sim_time': use_sim_time}],
                    output='screen'
                ),
                # Base to camera (often missing from Gazebo!)
                Node(
                    package='tf2_ros',
                    executable='static_transform_publisher',
                    name='base_to_camera_publisher',
                    arguments=['0.07', '0', '0.12', '0', '0', '0', 'base_link', 'camera_link'],
                    parameters=[{'use_sim_time': use_sim_time}],
                    output='screen'
                ),
                # Camera to optical frame (ROS convention)
                Node(
                    package='tf2_ros',
                    executable='static_transform_publisher',
                    name='camera_to_optical_publisher',
                    arguments=['0', '0', '0', '-1.5708', '0', '-1.5708', 'camera_link', 'camera_optical_link'],
                    parameters=[{'use_sim_time': use_sim_time}],
                    output='screen'
                )
            ]
        ),
        
        # Step 5: Joint State Publisher (for moving parts)
        TimerAction(
            period=9.0,
            actions=[
                LogInfo(msg='Step 5: Starting joint state publisher...'),
                Node(
                    package='joint_state_publisher',
                    executable='joint_state_publisher',
                    name='joint_state_publisher',
                    parameters=[{'use_sim_time': use_sim_time}],
                    output='screen'
                )
            ]
        ),
        
        # Step 6: Nav2 Stack (after transforms are established)
        TimerAction(
            period=10.0,
            actions=[
                LogInfo(msg='Step 6: Launching Nav2 navigation stack...'),
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(get_package_share_directory('nav2_bringup'), 'launch', 'navigation_launch.py')
                    ),
                    launch_arguments={
                        'use_sim_time': 'true',
                        'params_file': nav2_params_path
                    }.items()
                )
            ]
        ),
        
        # Step 7: YOLO Detection (with simulation time!)
        TimerAction(
            period=15.0,
            actions=[
                LogInfo(msg='Step 7: Starting YOLO detection system...'),
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(get_package_share_directory('yolov8_bringup'), 'launch', 'yolov8.launch.py')
                    ),
                    launch_arguments={
                        'model': 'yolov8m.pt',
                        'input_image_topic': '/camera/image_raw',
                        'device': 'cpu',
                        'use_sim_time': 'true'  # CRITICAL!
                    }.items()
                )
            ]
        ),
        
        # Step 8: Camera Debug Viewer (helps verify detection)
        TimerAction(
            period=17.0,
            actions=[
                LogInfo(msg='Step 8: Opening camera debug viewer...'),
                Node(
                    package='rqt_image_view',
                    executable='rqt_image_view',
                    name='yolo_debug_viewer',
                    arguments=['/yolo/dbg_image'],
                    parameters=[{'use_sim_time': use_sim_time}],
                    output='screen'
                )
            ]
        ),
        
        # Step 9: YOLO to Nav2 Bridge (with proper timing parameters)
        TimerAction(
            period=20.0,
            actions=[
                LogInfo(msg='Step 9: Starting YOLO to Nav2 goal bridge...'),
                Node(
                    package='chasebot_description',
                    executable='ros2_yolo_to_nav_goal_fixed.py',
                    name='yolo_to_nav_goal',
                    parameters=[{
                        'use_sim_time': True,  # CRITICAL!
                        'approach_distance': 0.3,
                        'goal_tolerance': 0.1
                    }],
                    output='screen'
                )
            ]
        ),
        
        # Step 10: User instructions
        TimerAction(
            period=22.0,
            actions=[
                LogInfo(msg='\n' + '='*60),
                LogInfo(msg='SYSTEM READY! ChaseBot autonomous system initialized.'),
                LogInfo(msg='='*60),
                LogInfo(msg='To begin testing:'),
                LogInfo(msg='1. Verify robot appears in Gazebo'),
                LogInfo(msg='2. Check debug viewer shows camera feed'),
                LogInfo(msg='3. Open new terminal and spawn golf ball:'),
                LogInfo(msg='   cd ~/ros2_ws && source install/setup.bash'),
                LogInfo(msg='   ros2 run chasebot_description spawn_golf_ball.py'),
                LogInfo(msg=''),
                LogInfo(msg='The robot will automatically detect and navigate to the ball!'),
                LogInfo(msg='='*60 + '\n')
            ]
        )
    ])
