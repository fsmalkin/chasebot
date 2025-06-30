#!/usr/bin/env python3
"""
Complete Nav2 UAT launch file - all components in one
"""

import os
from launch import LaunchDescription
from launch.actions import ExecuteProcess, DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # Get package directories
    pkg_share = get_package_share_directory('chasebot_description')
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')
    
    # File paths
    urdf_file = os.path.join(pkg_share, 'urdf', 'ros2_jetbot.urdf')
    world_file = os.path.join(pkg_share, 'worlds', 'autonomous_golf_ball_world.world')
    nav2_params_file = os.path.join(pkg_share, 'nav2_params_simple.yaml')
    
    # Launch configuration
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    
    return LaunchDescription([
        # Launch arguments
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation time'
        ),
        
        # 1. Start Gazebo with golf ball world
        ExecuteProcess(
            cmd=['gazebo', '--verbose', world_file],
            output='screen'
        ),
        
        # 2. Spawn JetBot robot (with delay)
        TimerAction(
            period=3.0,
            actions=[
                Node(
                    package='gazebo_ros',
                    executable='spawn_entity.py',
                    name='spawn_jetbot',
                    arguments=[
                        '-entity', 'jetbot',
                        '-file', urdf_file,
                        '-x', '0', '-y', '0', '-z', '0.1'
                    ],
                    output='screen'
                )
            ]
        ),
        
        # 3. Robot state publisher
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            parameters=[{
                'robot_description': open(urdf_file).read(),
                'use_sim_time': use_sim_time
            }],
            output='screen'
        ),
        
        # 4. Joint state publisher
        Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            name='joint_state_publisher',
            parameters=[{'use_sim_time': use_sim_time}],
            output='screen'
        ),
        
        # 5. Vision to LaserScan converter (starts immediately)
        Node(
            package='chasebot_description',
            executable='ros2_vision_to_laserscan_hsv.py',
            name='vision_to_laserscan',
            parameters=[{'use_sim_time': use_sim_time}],
            output='screen'
        ),
        
        # 6. Launch Nav2 stack (with delay)
        TimerAction(
            period=5.0,
            actions=[
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(nav2_bringup_dir, 'launch', 'navigation_launch.py')
                    ),
                    launch_arguments={
                        'use_sim_time': 'true',
                        'params_file': nav2_params_file,
                        'autostart': 'true'
                    }.items()
                )
            ]
        ),
        
        # 7. Ball to Nav2 goal converter (with longer delay)
        TimerAction(
            period=10.0,
            actions=[
                Node(
                    package='chasebot_description',
                    executable='ros2_ball_to_nav_goal.py',
                    name='ball_to_nav_goal',
                    parameters=[{'use_sim_time': use_sim_time}],
                    output='screen'
                )
            ]
        ),
        
        # Optional: Direct ball follower (comment out to test Nav2-only)
        # Node(
        #     package='chasebot_description',
        #     executable='ros2_golf_ball_follower.py',
        #     name='golf_ball_follower',
        #     parameters=[{'use_sim_time': use_sim_time}],
        #     output='screen'
        # ),
    ])
