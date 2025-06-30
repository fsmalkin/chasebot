#!/usr/bin/env python3

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    """
    Minimal Nav2 demo for ChaseBot - clean UAT demonstration
    Goal: Robot navigates to a golf ball using Nav2 professional path planning
    """
    
    # Get package directories
    pkg_dir = get_package_share_directory('chasebot_description')
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')
    
    # File paths
    urdf_file = os.path.join(pkg_dir, 'urdf', 'ros2_jetbot.urdf')
    world_file = os.path.join(pkg_dir, 'worlds', 'simple_golf_ball_world.world')
    nav2_params_file = os.path.join(pkg_dir, 'nav2_params_simple.yaml')
    
    # Launch configuration
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    autostart = LaunchConfiguration('autostart', default='true')
    
    # Read URDF
    with open(urdf_file, 'r') as file:
        robot_description = file.read()
    
    # Gazebo launch with GUI
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(get_package_share_directory('gazebo_ros'), 'launch', 'gazebo.launch.py')
        ]),
        launch_arguments={
            'world': world_file,
            'verbose': 'true'
        }.items()
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
    
    # Spawn robot in Gazebo
    spawn_robot = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        name='spawn_entity',
        output='screen',
        arguments=['-entity', 'jetbot', '-topic', 'robot_description', '-x', '0', '-y', '0', '-z', '0.1']
    )
    
    # Static transform: map -> odom (for mapless navigation)
    static_tf_map_odom = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_tf_map_odom',
        arguments=['0', '0', '0', '0', '0', '0', 'map', 'odom']
    )
    
    # Create fake laser scan for Nav2 (simple obstacle detection)
    fake_laser_scan = Node(
        executable='python3',
        name='fake_laser_scan',
        output='screen',
        arguments=[os.path.join(pkg_dir, 'scripts', 'ros2_vision_to_laserscan.py')],
        parameters=[{
            'use_sim_time': use_sim_time,
            'scan_height_ratio': 0.5,
            'num_scan_samples': 180,
            'scan_range_max': 3.0,
            'scan_range_min': 0.2
        }]
    )
    
    # Nav2 bringup with simplified parameters
    nav2_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_dir, 'launch', 'navigation_launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'autostart': autostart,
            'params_file': nav2_params_file,
            'map_subscribe_transient_local': 'true'
        }.items()
    )
    
    return LaunchDescription([
        # Launch arguments
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation time'
        ),
        DeclareLaunchArgument(
            'autostart',
            default_value='true',
            description='Automatically startup the nav2 stack'
        ),
        
        # Core components
        gazebo,
        robot_state_publisher,
        spawn_robot,
        
        # Navigation infrastructure
        static_tf_map_odom,
        fake_laser_scan,
        nav2_bringup,
    ])
