#!/usr/bin/env python3

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, ExecuteProcess
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # Get package directory
    pkg_dir = get_package_share_directory('chasebot_description')
    
    # Paths
    urdf_file = os.path.join(pkg_dir, 'urdf', 'ros2_jetbot.urdf')
    world_file = os.path.join(pkg_dir, 'worlds', 'autonomous_golf_ball_world.world')
    nav2_params_file = os.path.join(pkg_dir, 'nav2_params_simple.yaml')
    
    # Launch configuration
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    
    # Read URDF
    with open(urdf_file, 'r') as file:
        robot_description = file.read()
    
    # Launch Gazebo headless
    gazebo = ExecuteProcess(
        cmd=['gazebo', '--verbose', '-s', 'libgazebo_ros_factory.so', 
             '-s', 'libgazebo_ros_init.so', world_file],
        output='screen'
    )
    
    # Robot state publisher
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': use_sim_time
        }]
    )
    
    # Spawn robot
    spawn_robot = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        name='spawn_entity',
        output='screen',
        arguments=['-entity', 'jetbot', '-topic', 'robot_description', 
                   '-x', '0', '-y', '0', '-z', '0.1']
    )
    
    # Vision to laserscan node
    vision_to_laserscan = Node(
        package='chasebot_description',
        executable='ros2_vision_to_laserscan_hsv.py',
        name='vision_to_laserscan_hsv',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'scan_height_ratio': 0.5,
            'num_scan_samples': 180,
            'scan_range_max': 3.0,
            'scan_range_min': 0.2,
            'min_obstacle_width': 5,
            'hsv_lower_h': 35,
            'hsv_upper_h': 85,
            'hsv_lower_s': 50,
            'hsv_upper_s': 255,
            'hsv_lower_v': 50,
            'hsv_upper_v': 255
        }]
    )
    
    # Test node that sends Nav2 goals
    test_nav_goal = Node(
        package='chasebot_description',
        executable='test_nav2_goal.py',
        name='test_nav_goal',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}]
    )
    
    # Simple direct control test (no Nav2 yet)
    simple_movement = Node(
        package='chasebot_description',
        executable='ros2_simple_movement_test.py',
        name='simple_movement_test',
        output='screen'
    )
    
    return LaunchDescription([
        # Declare launch arguments
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation time'
        ),
        
        # Launch everything
        gazebo,
        robot_state_publisher,
        spawn_robot,
        vision_to_laserscan,
        # For now, just test simple movement
        simple_movement
    ])
