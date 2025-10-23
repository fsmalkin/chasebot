#!/usr/bin/env python3

"""
Camera Orientation Test Launch File
Uses colored balls in each direction to diagnose camera orientation
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, Command
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    pkg_share = get_package_share_directory('chasebot_sim')
    
    # Set IGN_GAZEBO_SYSTEM_PLUGIN_PATH for gz_ros2_control
    set_ign_plugin_path = SetEnvironmentVariable(
        'IGN_GAZEBO_SYSTEM_PLUGIN_PATH',
        '/opt/ros/humble/lib'
    )
    
    # Declare arguments
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    
    # Robot description
    robot_description_path = os.path.join(pkg_share, 'ros2_config', 'urdf', 'jetbot_core_ignition_v1.3.0.sdf')
    with open(robot_description_path, 'r') as file:
        robot_description = file.read()
    
    # Start Ignition Gazebo with camera orientation test world
    ignition_spawn = ExecuteProcess(
        cmd=['ign', 'gazebo', 
             os.path.join(pkg_share, 'ros2_config', 'worlds', 'camera_orientation_test_world.world'),
             '-r', '-v', '3'],
        output='screen'
    )
    
    # Spawn robot entity
    spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-name', 'jetbot',
            '-x', '0.0',
            '-y', '0.0',
            '-z', '0.05',
            '-R', '0.0',
            '-P', '0.0',
            '-Y', '0.0',
            '-file', robot_description_path
        ],
        output='screen'
    )
    
    # Robot state publisher
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        parameters=[{
            'use_sim_time': use_sim_time,
            'robot_description': robot_description,
        }],
        output='screen'
    )
    
    # Bridge for camera topics
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock',
            '/d415/image_raw@sensor_msgs/msg/Image@ignition.msgs.Image',
            '/d415/camera_info@sensor_msgs/msg/CameraInfo@ignition.msgs.CameraInfo',
            '/jetbot_base_controller/cmd_vel@geometry_msgs/msg/TwistStamped@ignition.msgs.Twist',
            '/model/jetbot/pose@geometry_msgs/msg/PoseArray@ignition.msgs.Pose_V',
            '/world/camera_orientation_test_world/model/jetbot/joint_state@sensor_msgs/msg/JointState[ignition.msgs.Model'
        ],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen'
    )
    
    # Controller manager
    controller_manager = Node(
        package='controller_manager',
        executable='ros2_control_node',
        parameters=[
            {'use_sim_time': use_sim_time},
            {'robot_description': robot_description},
            os.path.join(pkg_share, 'ros2_config', 'config', 'jetbot_controllers.yaml')
        ],
        output='screen'
    )
    
    # Spawn controllers
    joint_state_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster', '--controller-manager', '/controller_manager'],
        output='screen'
    )
    
    jetbot_base_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['jetbot_base_controller', '--controller-manager', '/controller_manager'],
        output='screen'
    )
    
    return LaunchDescription([
        set_ign_plugin_path,
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation (Gazebo) clock if true'
        ),
        ignition_spawn,
        spawn_entity,
        robot_state_publisher,
        bridge,
        controller_manager,
        joint_state_broadcaster_spawner,
        jetbot_base_controller_spawner
    ])
