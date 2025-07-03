#!/usr/bin/env python3
"""
Slice 4.5: Fixed Nav2 Integration Launch File
Extends Slice 3.5 (Clean YOLO) with Nav2 and corrected bridge script
"""

import os
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import ExecuteProcess, TimerAction, RegisterEventHandler, LogInfo
from launch.event_handlers import OnProcessExit
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # Package directories
    pkg_share = get_package_share_directory('chasebot_description')
    world_path = os.path.join(pkg_share, 'worlds', 'yolo_test_world.world')
    urdf_path = os.path.join(pkg_share, 'urdf', 'ros2_jetbot.urdf')
    
    # Nav2 configuration
    nav2_params_path = os.path.join(pkg_share, 'params', 'nav2_params_minimal_fixed.yaml')
    
    return LaunchDescription([
        # 1. Gazebo server (headless)
        ExecuteProcess(
            cmd=['gzserver', '--verbose', '-s', 'libgazebo_ros_init.so', 
                 '-s', 'libgazebo_ros_factory.so', world_path],
            output='screen',
            additional_env={'GAZEBO_MODEL_PATH': pkg_share}
        ),
        
        # 2. Gazebo client (GUI) - 3 seconds after server
        TimerAction(
            period=3.0,
            actions=[
                ExecuteProcess(
                    cmd=['gzclient'],
                    output='screen'
                ),
                LogInfo(msg='Launched Gazebo GUI')
            ]
        ),
        
        # 3. Spawn JetBot - 5 seconds after start
        TimerAction(
            period=5.0,
            actions=[
                Node(
                    package='gazebo_ros',
                    executable='spawn_entity.py',
                    arguments=[
                        '-entity', 'jetbot',
                        '-file', urdf_path,
                        '-x', '0.0',
                        '-y', '0.0',
                        '-z', '0.05',
                        '-Y', '0.0'
                    ],
                    output='screen'
                ),
                LogInfo(msg='Spawning JetBot in Gazebo')
            ]
        ),
        
        # 4. Robot State Publisher - 8 seconds after start
        TimerAction(
            period=8.0,
            actions=[
                Node(
                    package='robot_state_publisher',
                    executable='robot_state_publisher',
                    name='robot_state_publisher',
                    output='screen',
                    parameters=[{
                        'use_sim_time': True,
                        'robot_description': open(urdf_path, 'r').read()
                    }]
                ),
                LogInfo(msg='Started Robot State Publisher')
            ]
        ),
        
        # 5. Static transform publishers - 9 seconds after start
        TimerAction(
            period=9.0,
            actions=[
                # Transform: map -> odom (required for Nav2)
                Node(
                    package='tf2_ros',
                    executable='static_transform_publisher',
                    name='map_to_odom_tf',
                    arguments=['0', '0', '0', '0', '0', '0', 'map', 'odom'],
                    parameters=[{'use_sim_time': True}],
                    output='screen'
                ),
                
                # Transform: base_link -> camera_link
                Node(
                    package='tf2_ros',
                    executable='static_transform_publisher',
                    name='base_to_camera_tf',
                    arguments=['0.07', '0', '0.12', '0', '0', '0', 'base_link', 'camera_link'],
                    parameters=[{'use_sim_time': True}],
                    output='screen'
                ),
                
                # Transform: camera_link -> camera_optical_link
                Node(
                    package='tf2_ros',
                    executable='static_transform_publisher',
                    name='camera_to_optical_tf',
                    arguments=['0', '0', '0', '-1.57', '0', '-1.57', 'camera_link', 'camera_optical_link'],
                    parameters=[{'use_sim_time': True}],
                    output='screen'
                ),
                
                LogInfo(msg='Started static transform publishers')
            ]
        ),
        
        # 6. YOLO detector (silent version) - 12 seconds after start
        TimerAction(
            period=12.0,
            actions=[
                Node(
                    package='chasebot_description',
                    executable='ros2_yolo_detector_silent.py',
                    name='yolo_detector',
                    output='screen',
                    parameters=[{'use_sim_time': True}]
                ),
                LogInfo(msg='Started YOLO detector (silent mode)')
            ]
        ),
        
        # 7. Nav2 Components - 15 seconds after start
        TimerAction(
            period=15.0,
            actions=[
                # Controller Server
                Node(
                    package='nav2_controller',
                    executable='controller_server',
                    name='controller_server',
                    output='screen',
                    parameters=[nav2_params_path, {'use_sim_time': True}],
                    remappings=[('/cmd_vel', '/cmd_vel')]
                ),
                
                # Planner Server
                Node(
                    package='nav2_planner',
                    executable='planner_server',
                    name='planner_server',
                    output='screen',
                    parameters=[nav2_params_path, {'use_sim_time': True}]
                ),
                
                # Behavior Server
                Node(
                    package='nav2_behaviors',
                    executable='behavior_server',
                    name='behavior_server',
                    output='screen',
                    parameters=[nav2_params_path, {'use_sim_time': True}]
                ),
                
                # BT Navigator
                Node(
                    package='nav2_bt_navigator',
                    executable='bt_navigator',
                    name='bt_navigator',
                    output='screen',
                    parameters=[nav2_params_path, {'use_sim_time': True}]
                ),
                
                LogInfo(msg='Started Nav2 components')
            ]
        ),
        
        # 8. Lifecycle Manager - 16 seconds after start
        TimerAction(
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
                        'node_names': [
                            'controller_server',
                            'planner_server',
                            'behavior_server',
                            'bt_navigator'
                        ]
                    }]
                ),
                LogInfo(msg='Started Nav2 lifecycle manager')
            ]
        ),
        
        # 9. YOLO to Nav2 Bridge (FIXED version) - 20 seconds after start
        TimerAction(
            period=20.0,
            actions=[
                Node(
                    package='chasebot_description',
                    executable='ros2_yolo_to_nav_goal_fixed.py',
                    name='yolo_to_nav_goal',
                    output='screen',
                    parameters=[{'use_sim_time': True}]
                ),
                LogInfo(msg='Started YOLO to Nav2 bridge (fixed version)')
            ]
        ),
        
        # 10. Shutdown manager - 5 seconds after bridge
        TimerAction(
            period=25.0,
            actions=[
                Node(
                    package='chasebot_description',
                    executable='shutdown_manager.py',
                    name='shutdown_manager',
                    output='screen',
                    parameters=[{
                        'timeout_minutes': 5.0,
                        'warn_before_shutdown': True
                    }]
                ),
                LogInfo(msg='Shutdown manager started - 5 minute timeout')
            ]
        ),
    ])
