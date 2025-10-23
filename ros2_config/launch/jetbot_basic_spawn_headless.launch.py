#!/usr/bin/env python3
"""
ChaseBot Slice 1: Basic Gazebo + Robot Spawn (Headless Audio)
Modified for WSL2 to avoid audio issues
"""

import os
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, 
    ExecuteProcess, 
    LogInfo, 
    TimerAction
)
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # Get package directories
    pkg_description = get_package_share_directory('chasebot_description')
    
    # Paths
    world_path = os.path.join(pkg_description, 'ros2_config', 'worlds', 'single_ball_test.world')
    urdf_path = os.path.join(pkg_description, 'ros2_config', 'urdf', 'ros2_jetbot.urdf')
    
    # Read URDF
    with open(urdf_path, 'r') as infp:
        robot_desc = infp.read()
    
    return LaunchDescription([
        # Pre-launch cleanup
        ExecuteProcess(
            cmd=['python3', os.path.join(pkg_description, 'ros2_scripts', 'cleanup_before_launch.py')],
            output='screen',
            shell=False
        ),
        
        # Initial message
        LogInfo(msg='\n' + '='*60),
        LogInfo(msg='=== SLICE 1: Basic Gazebo + Robot Spawn (WSL2) ==='),
        LogInfo(msg='='*60),
        LogInfo(msg='Starting Gazebo simulation (audio disabled for WSL2)...'),
        
        # Step 1: Launch Gazebo with audio disabled
        ExecuteProcess(
            cmd=['gzserver', 
                 '--verbose', 
                 world_path,
                 '-s', 'libgazebo_ros_init.so',
                 '-s', 'libgazebo_ros_factory.so',
                 '-s', 'libgazebo_ros_force_system.so'],
            output='screen',
            # Disable audio to prevent crashes in WSL2
            additional_env={'LIBGL_ALWAYS_SOFTWARE': '1', 
                          'GAZEBO_AUDIO_DEVICE': 'null'}
        ),
        
        # Launch GUI client separately
        ExecuteProcess(
            cmd=['gzclient', '--verbose', '--gui-client-plugin', 'libgazebo_ros_eol_gui.so'],
            output='screen',
            additional_env={'LIBGL_ALWAYS_SOFTWARE': '1'}
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
                        'use_sim_time': True,
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
                    parameters=[{'use_sim_time': True}],
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
                LogInfo(msg=''),
                LogInfo(msg='Press Ctrl+C to shutdown when UAT complete'),
                LogInfo(msg='='*60 + '\n')
            ]
        ),
    ])
