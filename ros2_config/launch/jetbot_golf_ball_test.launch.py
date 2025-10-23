#!/usr/bin/env python3
"""
ChaseBot Golf Ball Detection Test Launch File
Phase 3, Step 3.2 - Thin Slice 3: Golf Ball Detection Testing

Minimal validation test before Isaac ROS transition.
Validates: Camera → OpenCV Detection → Topic Publishing → Movement Capability

UAT Success Criteria:
- JetBot spawns in golf ball world
- Camera feed shows golf balls
- Vision system detects and displays golf balls with bounding boxes
- /ball_detections topic publishes coordinates
- System remains stable
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
    world_file = os.path.join(pkg_share, 'worlds', 'simple_golf_ball_world.world')
    
    # Launch arguments
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation time if true'
    )
    
    # Read URDF file
    robot_description = Command(['cat ', urdf_file])
    
    return LaunchDescription([
        use_sim_time_arg,
        
        # Launch Gazebo with golf ball world
        ExecuteProcess(
            cmd=['gazebo', '--verbose', '-s', 'libgazebo_ros_factory.so', world_file],
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
        
        # Spawn robot in Gazebo - positioned to see golf balls
        Node(
            package='gazebo_ros',
            executable='spawn_entity.py',
            name='spawn_jetbot',
            output='screen',
            arguments=[
                '-entity', 'jetbot',
                '-topic', '/robot_description',
                '-x', '0.0',      # Start at origin facing golf balls
                '-y', '0.0',      # Center position
                '-z', '0.1'       # Slightly elevated
            ]
        ),
        
        # Vision with Display - using working ExecuteProcess pattern
        ExecuteProcess(
            cmd=['python3', os.path.join(pkg_share, 'scripts', 'ros2_vision_with_display.py')],
            output='screen'
        )
    ])
