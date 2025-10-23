#!/usr/bin/env python3
"""
ChaseBot Slice 2: Basic Gazebo + Robot Spawn + Static Transforms
Adds explicit static transform publishers to fix transform tree fragmentation
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
        LogInfo(msg='=== SLICE 2: Basic Gazebo + Robot Spawn + Static Transforms ==='),
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
        
        # Step 5: CRITICAL - Static Transform Publishers
        TimerAction(
            period=9.0,
            actions=[
                LogInfo(msg='\n' + '='*50),
                LogInfo(msg='ADDING STATIC TRANSFORMS (SLICE 2 ADDITION)'),
                LogInfo(msg='='*50),
                LogInfo(msg='Publishing map → odom transform...'),
                Node(
                    package='tf2_ros',
                    executable='static_transform_publisher',
                    arguments=['0', '0', '0', '0', '0', '0', 'map', 'odom'],
                    parameters=[{'use_sim_time': use_sim_time}],
                    output='screen'
                ),
                LogInfo(msg='Publishing base_link → camera_link transform...'),
                Node(
                    package='tf2_ros',
                    executable='static_transform_publisher',
                    arguments=['0.07', '0', '0.12', '0', '0', '0', 'base_link', 'camera_link'],
                    parameters=[{'use_sim_time': use_sim_time}],
                    output='screen'
                ),
                LogInfo(msg='Publishing camera_link → camera_optical_link transform...'),
                Node(
                    package='tf2_ros',
                    executable='static_transform_publisher',
                    arguments=['0', '0', '0', '-1.5708', '0', '-1.5708', 'camera_link', 'camera_optical_link'],
                    parameters=[{'use_sim_time': use_sim_time}],
                    output='screen'
                ),
                LogInfo(msg='Static transforms published successfully!\n')
            ]
        ),
        
        # Step 6: UAT Instructions with Transform Verification
        TimerAction(
            period=12.0,
            actions=[
                LogInfo(msg='\n' + '='*60),
                LogInfo(msg='SYSTEM READY FOR SLICE 2 UAT VERIFICATION'),
                LogInfo(msg='='*60),
                LogInfo(msg='Check the following:'),
                LogInfo(msg='1. Gazebo window shows JetBot at origin (0,0)'),
                LogInfo(msg='2. Robot has visible camera on front'),
                LogInfo(msg='3. No RED error messages in terminal'),
                LogInfo(msg='4. No "extrapolation into future" warnings'),
                LogInfo(msg=''),
                LogInfo(msg='SLICE 2 SPECIFIC - Verify Transform Tree:'),
                LogInfo(msg='  In a new terminal, run:'),
                LogInfo(msg='  ros2 run tf2_tools view_frames'),
                LogInfo(msg='  (This creates a PDF showing the transform tree)'),
                LogInfo(msg=''),
                LogInfo(msg='Expected Result:'),
                LogInfo(msg='  Complete chain: map → odom → base_link → camera_link → camera_optical_link'),
                LogInfo(msg=''),
                LogInfo(msg='Also verify specific transform:'),
                LogInfo(msg='  ros2 run tf2_ros tf2_echo map camera_optical_link'),
                LogInfo(msg='  (Should show valid transform data)'),
                LogInfo(msg='='*60 + '\n')
            ]
        ),
        
        # Step 7: Launch shutdown manager
        TimerAction(
            period=15.0,
            actions=[
                Node(
                    package='chasebot_description',
                    executable='shutdown_manager.py',
                    name='shutdown_manager',
                    parameters=[{
                        'timeout_minutes': 5.0,
                        'slice_name': 'SLICE 2: Basic Gazebo + Robot Spawn + Static Transforms',
                        'uat_checklist': [
                            'Robot appears in Gazebo at origin (0,0)',
                            'Camera sensor visible on robot front',
                            'No transform errors in terminal',
                            'No "extrapolation into future" warnings',
                            'TF tree shows complete chain: map → odom → base_link → camera_link → camera_optical_link',
                            'tf2_echo map camera_optical_link returns valid data'
                        ]
                    }],
                    output='screen'
                )
            ]
        )
    ])
