#!/usr/bin/env python3
"""
ChaseBot ROS 2 Launch File - JetBot with Vision + FOV Visualization
Phase 3, Step 3.2 - Enhanced with field of view visualization
Launches JetBot simulation + vision detection + 3D FOV display
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    
    # Package and file paths
    pkg_share = FindPackageShare('chasebot_description').find('chasebot_description')
    urdf_file = os.path.join(pkg_share, 'urdf', 'ros2_jetbot.urdf')
    
    # Launch arguments
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation time if true'
    )
    
    world_file_arg = DeclareLaunchArgument(
        'world_file',
        default_value='empty.world',
        description='Gazebo world file to load'
    )
    
    # Read URDF file
    robot_description = Command(['cat ', urdf_file])
    
    return LaunchDescription([
        use_sim_time_arg,
        world_file_arg,
        
        # Launch Gazebo with specified world
        ExecuteProcess(
            cmd=['gazebo', '--verbose', '-s', 'libgazebo_ros_factory.so', 
                 LaunchConfiguration('world_file')],
            output='screen'
        ),
        
        # Robot state publisher
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{
                'robot_description': robot_description,
                'use_sim_time': LaunchConfiguration('use_sim_time')
            }]
        ),
        
        # Joint state publisher
        Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            name='joint_state_publisher',
            output='screen',
            parameters=[{
                'use_sim_time': LaunchConfiguration('use_sim_time')
            }]
        ),
        
        # Spawn robot in Gazebo
        Node(
            package='gazebo_ros',
            executable='spawn_entity.py',
            name='spawn_jetbot',
            output='screen',
            arguments=[
                '-entity', 'jetbot',
                '-topic', '/robot_description',
                '-x', '0.0',
                '-y', '0.0',
                '-z', '0.1'
            ]
        ),
        
        # Vision with Display
        ExecuteProcess(
            cmd=['python3', os.path.join(pkg_share, 'scripts', 'ros2_vision_with_display.py')],
            output='screen'
        ),
        
        # Field of View Visualization
        ExecuteProcess(
            cmd=['python3', os.path.join(pkg_share, 'scripts', 'ros2_fov_visualization.py')],
            output='screen'
        ),
        
        # RViz for visualization
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen',
            arguments=['-d', os.path.join(pkg_share, 'rviz', 'jetbot_fov.rviz')],
            parameters=[{
                'use_sim_time': LaunchConfiguration('use_sim_time')
            }],
            condition=None  # Always launch RViz
        )
    ])
