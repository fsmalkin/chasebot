#!/usr/bin/env python3
"""
ChaseBot Slice 1: Basic Gazebo + Robot Spawn
Minimal launch file to verify robot spawning with camera
Includes auto-shutdown after UAT verification
"""

import os
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, 
    ExecuteProcess, 
    IncludeLaunchDescription,
    LogInfo, 
    TimerAction
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # Get package directories
    pkg_gazebo_ros = get_package_share_directory('gazebo_ros')
    pkg_description = get_package_share_directory('chasebot_description')
    
    # Launch configuration variables
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    
    # Paths
    world_path = os.path.join(pkg_description, 'ros2_config', 'worlds', 'single_ball_test.world')
    urdf_path = os.path.join(pkg_description, 'ros2_config', 'urdf', 'ros2_jetbot.urdf')
    
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
        
        # Initial message
        LogInfo(msg='\n' + '='*60),
        LogInfo(msg='=== SLICE 1: Basic Gazebo + Robot Spawn ==='),
        LogInfo(msg='='*60),
        LogInfo(msg='Starting Gazebo simulation...'),
        
        # Step 1: Launch Gazebo with world
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_gazebo_ros, 'launch', 'gazebo.launch.py')
            ),
            launch_arguments={
                'world': world_path,
                'verbose': 'false'  # Less verbose for cleaner output
            }.items()
        ),
        
        # Step 2: Spawn robot (with delay for Gazebo to initialize)
        TimerAction(
            period=5.0,
            actions=[
                LogInfo(msg='Spawning JetBot robot at origin...'),
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
        
        # Step 3: Robot State Publisher (minimal for camera to work)
        TimerAction(
            period=7.0,
            actions=[
                LogInfo(msg='Starting robot state publisher for transforms...'),
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
        
        # Step 4: Joint State Publisher (needed for moving parts)
        TimerAction(
            period=8.0,
            actions=[
                LogInfo(msg='Starting joint state publisher...'),
                Node(
                    package='joint_state_publisher',
                    executable='joint_state_publisher',
                    name='joint_state_publisher',
                    parameters=[{'use_sim_time': use_sim_time}],
                    output='screen'
                )
            ]
        ),
        
        # Step 5: UAT Instructions
        TimerAction(
            period=10.0,
            actions=[
                LogInfo(msg='\n' + '='*60),
                LogInfo(msg='SYSTEM READY FOR UAT VERIFICATION'),
                LogInfo(msg='='*60),
                LogInfo(msg='Check the following:'),
                LogInfo(msg='1. Gazebo window shows JetBot at origin (0,0)'),
                LogInfo(msg='2. Robot has visible camera on front'),
                LogInfo(msg='3. No RED error messages in terminal'),
                LogInfo(msg=''),
                LogInfo(msg='To verify camera is publishing:'),
                LogInfo(msg='  ros2 topic echo /camera/image_raw --once'),
                LogInfo(msg='='*60 + '\n')
            ]
        ),
        
        # Step 6: Launch shutdown manager
        TimerAction(
            period=12.0,
            actions=[
                Node(
                    package='chasebot_description',
                    executable='shutdown_manager.py',
                    name='shutdown_manager',
                    parameters=[{
                        'timeout_minutes': 5.0,
                        'slice_name': 'SLICE 1: Basic Gazebo + Robot Spawn',
                        'uat_checklist': [
                            'Robot appears in Gazebo at origin (0,0)',
                            'Camera sensor visible on robot front',
                            'No transform errors in terminal',
                            'Camera topic /camera/image_raw is publishing'
                        ]
                    }],
                    output='screen'
                )
            ]
        )
    ])
