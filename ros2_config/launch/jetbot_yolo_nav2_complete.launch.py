#!/usr/bin/env python3

import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction, ExecuteProcess
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from launch.substitutions import LaunchConfiguration
from launch.actions import DeclareLaunchArgument

def generate_launch_description():
    # Declare launch arguments
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    
    # Include the gazebo_ros package's gazebo.launch.py
    # This ensures all ROS plugins are loaded properly
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(get_package_share_directory('gazebo_ros'), 'launch', 'gazebo.launch.py')
        ]),
        launch_arguments={
            'world': '/mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/worlds/simple_golf_ball_world.world',
            'verbose': 'true'
        }.items()
    )
    
    # Robot state publisher
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        arguments=['/mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/urdf/ros2_jetbot.urdf'],
        parameters=[{'use_sim_time': use_sim_time}]
    )
    
    # Spawn robot with delay to ensure Gazebo is ready
    spawn_robot = TimerAction(
        period=5.0,  # Wait 5 seconds for Gazebo to fully load
        actions=[
            Node(
                package='gazebo_ros',
                executable='spawn_entity.py',
                arguments=[
                    '-file', '/mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/urdf/ros2_jetbot.urdf',
                    '-entity', 'jetbot',
                    '-x', '0',
                    '-y', '0',
                    '-z', '0.05'
                ],
                output='screen'
            )
        ]
    )
    
    # YOLO detection node
    yolo_detector = Node(
        package='yolo_ros',
        executable='yolo_node',
        name='yolo_node',
        remappings=[
            ('image_raw', '/camera/image_raw'),
            ('detections', '/yolo/detections')
        ],
        parameters=[{
            'model': 'yolov8m',
            'threshold': 0.5,
            'device': 'cpu',
            'use_sim_time': use_sim_time
        }],
        output='screen'
    )
    
    # YOLO tracking node
    yolo_tracker = Node(
        package='yolo_ros',
        executable='tracking_node',
        name='tracking_node',
        remappings=[
            ('image_raw', '/camera/image_raw'),
            ('detections', '/yolo/detections'),
            ('tracking', '/yolo/tracking')
        ],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen'
    )
    
    # YOLO debug node for visualization
    yolo_debug = Node(
        package='yolo_ros',
        executable='debug_node',
        name='debug_node',
        remappings=[
            ('image_raw', '/camera/image_raw'),
            ('detections', '/yolo/detections'),
            ('dbg_image', '/yolo/debug_image')
        ],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen'
    )
    
    # Nav2 navigation stack with delay
    nav2_bringup = TimerAction(
        period=8.0,  # Wait for robot to be spawned
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource([
                    os.path.join(get_package_share_directory('nav2_bringup'), 'launch', 'navigation_launch.py')
                ]),
                launch_arguments={
                    'use_sim_time': 'true',
                    'params_file': '/mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/params/nav2_params_simple.yaml'
                }.items()
            )
        ]
    )
    
    # YOLO to Nav2 bridge with delay
    yolo_to_nav_bridge = TimerAction(
        period=12.0,  # Wait for Nav2 to be ready
        actions=[
            ExecuteProcess(
                cmd=[
                    'python3',
                    '/mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/ros2_yolo_to_nav_goal.py'
                ],
                output='screen'
            )
        ]
    )
    
    # Joint state publisher for robot model
    joint_state_publisher = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        parameters=[{
            'use_sim_time': use_sim_time,
            'source_list': ['/joint_states']
        }]
    )
    
    return LaunchDescription([
        # Declare launch arguments
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation time'
        ),
        
        # Launch components in order
        gazebo,
        robot_state_publisher,
        joint_state_publisher,
        spawn_robot,
        yolo_detector,
        yolo_tracker,
        yolo_debug,
        nav2_bringup,
        yolo_to_nav_bridge
    ])
