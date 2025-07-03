#!/usr/bin/env python3
"""
Complete Nav2 Integration with YOLO Detection and Odometry Publisher
Final integration of all proven components for autonomous ball following
"""

import os
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import IncludeLaunchDescription, TimerAction, LogInfo
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # Package directory
    pkg_share = get_package_share_directory('chasebot_description')
    
    # Nav2 configuration
    nav2_params_path = os.path.join(pkg_share, 'ros2_config', 'params', 'nav2_params_minimal_fixed.yaml')
    
    return LaunchDescription([
        # 1. Include the ENTIRE working Slice 3.5 launch file
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_share, 'ros2_config', 'launch', 'jetbot_with_yolo_clean_fixed.launch.py')
            )
        ),
        LogInfo(msg='Launched working Slice 3.5 foundation'),
        
        # 2. Robot State Publisher - 8 seconds after start
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
                        'robot_description': open(os.path.join(pkg_share, 'ros2_config', 'urdf', 'ros2_jetbot.urdf'), 'r').read()
                    }]
                ),
                LogInfo(msg='Started Robot State Publisher')
            ]
        ),
        
        # 3. Blank Map Publisher - 10 seconds after start
        TimerAction(
            period=10.0,
            actions=[
                Node(
                    package='chasebot_description',
                    executable='blank_map_publisher.py',
                    name='blank_map_publisher',
                    output='screen',
                    parameters=[{'use_sim_time': True}]
                ),
                LogInfo(msg='Started Blank Map Publisher for Nav2')
            ]
        ),
        
        # 4. Add Nav2 Components - 15 seconds after start
        # Note: Gazebo's differential_drive_controller already publishes odom->base_link transform
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
                    parameters=[nav2_params_path, {
                        'use_sim_time': True,
                        'default_nav_to_pose_bt_xml': os.path.join(pkg_share, 'ros2_config', 'behavior_trees', 'navigate_to_pose_w_replanning.xml')
                    }]
                ),
                
                LogInfo(msg='Started Nav2 components')
            ]
        ),
        
        # 5. Lifecycle Manager - 16 seconds after start
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
        
        # 6. YOLO to Nav2 Bridge (FIXED version) - 20 seconds after start
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
                LogInfo(msg='Started YOLO to Nav2 bridge - ChaseBot is now fully autonomous!')
            ]
        ),
    ])
