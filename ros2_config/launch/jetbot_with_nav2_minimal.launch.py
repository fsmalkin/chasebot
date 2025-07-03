#!/usr/bin/env python3
"""
Slice 4: Nav2 Minimal Integration
Builds on Slice 3.5, adds Nav2 navigation stack for autonomous ball following
"""

import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, ExecuteProcess, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # Package directories
    pkg_share = get_package_share_directory('chasebot_description')
    
    # World file path - includes a golf ball
    world_file = os.path.join(pkg_share, 'ros2_config', 'worlds', 'yolo_test_world.world')
    
    # Check if world file exists, fall back if needed
    if not os.path.exists(world_file):
        print(f"World file not found at {world_file}, using default")
        world_file = os.path.join(pkg_share, 'ros2_config', 'worlds', 'simple_uat_world.world')
    
    # URDF file path
    urdf_file = os.path.join(pkg_share, 'ros2_config', 'urdf', 'ros2_jetbot.urdf')
    
    # Nav2 params file path
    nav2_params_file = os.path.join(pkg_share, 'ros2_config', 'params', 'nav2_params_simple.yaml')
    
    # Read URDF
    with open(urdf_file, 'r') as file:
        robot_description = file.read()
    
    # Launch Gazebo with specified world
    gazebo = ExecuteProcess(
        cmd=['gazebo', '--verbose', world_file, '-s', 'libgazebo_ros_factory.so'],
        output='screen',
        additional_env={'GAZEBO_MODEL_PATH': os.path.dirname(world_file)}
    )
    
    # Spawn robot with delay (5 seconds after Gazebo starts)
    spawn_robot = TimerAction(
        period=5.0,
        actions=[
            Node(
                package='gazebo_ros',
                executable='spawn_entity.py',
                name='spawn_jetbot',
                arguments=[
                    '-entity', 'jetbot',
                    '-file', urdf_file,
                    '-x', '0.0',
                    '-y', '0.0',
                    '-z', '0.05'
                ],
                output='screen',
                parameters=[{'use_sim_time': True}]
            )
        ]
    )
    
    # Robot State Publisher (added at 8 seconds for Nav2)
    robot_state_publisher = TimerAction(
        period=8.0,
        actions=[
            Node(
                package='robot_state_publisher',
                executable='robot_state_publisher',
                name='robot_state_publisher',
                output='screen',
                parameters=[{
                    'robot_description': robot_description,
                    'use_sim_time': True
                }]
            )
        ]
    )
    
    # Static transform publishers (added at 9 seconds)
    # 1. Map to odom transform (required for Nav2)
    map_to_odom_tf = TimerAction(
        period=9.0,
        actions=[
            Node(
                package='tf2_ros',
                executable='static_transform_publisher',
                name='map_to_odom_tf_publisher',
                arguments=['0', '0', '0', '0', '0', '0', 'map', 'odom'],
                output='screen',
                parameters=[{'use_sim_time': True}]
            )
        ]
    )
    
    # 2. Base_link to camera_link transform
    base_to_camera_tf = TimerAction(
        period=9.0,
        actions=[
            Node(
                package='tf2_ros',
                executable='static_transform_publisher',
                name='base_to_camera_tf_publisher',
                arguments=['0.07', '0', '0.12', '0', '0', '0', 'base_link', 'camera_link'],
                output='screen',
                parameters=[{'use_sim_time': True}]
            )
        ]
    )
    
    # 3. Camera_link to camera_optical_link transform (optical frame convention)
    camera_to_optical_tf = TimerAction(
        period=9.0,
        actions=[
            Node(
                package='tf2_ros',
                executable='static_transform_publisher',
                name='camera_to_optical_tf_publisher',
                arguments=['0', '0', '0', '-1.5708', '0', '-1.5708', 'camera_link', 'camera_optical_link'],
                output='screen',
                parameters=[{'use_sim_time': True}]
            )
        ]
    )
    
    # 4. Base_link to base_scan transform (for Nav2 obstacle detection)
    base_to_scan_tf = TimerAction(
        period=9.0,
        actions=[
            Node(
                package='tf2_ros',
                executable='static_transform_publisher',
                name='base_to_scan_tf_publisher',
                arguments=['0.0', '0', '0.1', '0', '0', '0', 'base_link', 'base_scan'],
                output='screen',
                parameters=[{'use_sim_time': True}]
            )
        ]
    )
    
    # YOLO Detection Node - Silent Version (added at 12 seconds)
    yolo_detector = TimerAction(
        period=12.0,
        actions=[
            Node(
                package='chasebot_description',
                executable='ros2_yolo_detector_silent.py',
                name='yolo_detector',
                output='screen',
                parameters=[{'use_sim_time': True}]
            )
        ]
    )
    
    # Nav2 Controller Server (added at 15 seconds)
    controller_server = TimerAction(
        period=15.0,
        actions=[
            Node(
                package='nav2_controller',
                executable='controller_server',
                name='controller_server',
                output='screen',
                parameters=[nav2_params_file],
                remappings=[('/cmd_vel', '/cmd_vel')]
            )
        ]
    )
    
    # Nav2 Planner Server (added at 15 seconds)
    planner_server = TimerAction(
        period=15.0,
        actions=[
            Node(
                package='nav2_planner',
                executable='planner_server',
                name='planner_server',
                output='screen',
                parameters=[nav2_params_file]
            )
        ]
    )
    
    # Nav2 Behavior Server (added at 15 seconds)
    behavior_server = TimerAction(
        period=15.0,
        actions=[
            Node(
                package='nav2_behaviors',
                executable='behavior_server',
                name='behavior_server',
                output='screen',
                parameters=[nav2_params_file]
            )
        ]
    )
    
    # Nav2 BT Navigator (added at 15 seconds)
    bt_navigator = TimerAction(
        period=15.0,
        actions=[
            Node(
                package='nav2_bt_navigator',
                executable='bt_navigator',
                name='bt_navigator',
                output='screen',
                parameters=[nav2_params_file]
            )
        ]
    )
    
    # Nav2 Lifecycle Manager (added at 16 seconds to start Nav2 nodes)
    lifecycle_manager = TimerAction(
        period=16.0,
        actions=[
            Node(
                package='nav2_lifecycle_manager',
                executable='lifecycle_manager',
                name='lifecycle_manager',
                output='screen',
                parameters=[{
                    'use_sim_time': True,
                    'autostart': True,
                    'node_names': ['controller_server', 'planner_server', 'behavior_server', 'bt_navigator']
                }]
            )
        ]
    )
    
    # YOLO to Nav2 Bridge (added at 20 seconds after Nav2 is ready)
    yolo_to_nav_bridge = TimerAction(
        period=20.0,
        actions=[
            Node(
                package='chasebot_description',
                executable='ros2_yolo_to_nav_goal.py',
                name='yolo_to_nav_goal',
                output='screen',
                parameters=[{'use_sim_time': True}]
            )
        ]
    )
    
    # Shutdown manager with 5-minute timer
    shutdown_manager = Node(
        package='chasebot_description',
        executable='shutdown_manager.py',
        name='shutdown_manager',
        output='screen'
    )
    
    # Status message
    status_msg = ExecuteProcess(
        cmd=['echo', '=== Launching Slice 4: Nav2 Minimal Integration ==='],
        output='screen'
    )
    
    return LaunchDescription([
        # Status
        status_msg,
        
        # Core simulation
        gazebo,
        spawn_robot,
        
        # Robot description for Nav2
        robot_state_publisher,
        
        # Transform publishers
        map_to_odom_tf,
        base_to_camera_tf,
        camera_to_optical_tf,
        base_to_scan_tf,
        
        # YOLO detection (silent mode)
        yolo_detector,
        
        # Nav2 stack
        controller_server,
        planner_server,
        behavior_server,
        bt_navigator,
        lifecycle_manager,
        
        # Bridge script for autonomous behavior
        yolo_to_nav_bridge,
        
        # Auto-shutdown
        shutdown_manager
    ])
