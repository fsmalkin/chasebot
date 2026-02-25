#!/usr/bin/env python3
"""
Launch file for JetBot + gz_ros2_control + D415 sensors (v5 baseline).

Canonical runtime arguments:
- inference_device: auto|cuda:0|cpu
- perf_profile: compat|balanced|max
- headless: true|false
"""

from ament_index_python.packages import PackageNotFoundError
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import ExecuteProcess
from launch.actions import LogInfo
from launch.actions import SetEnvironmentVariable
from launch.actions import TimerAction
from launch.conditions import IfCondition
from launch.conditions import UnlessCondition
from launch.substitutions import LaunchConfiguration
from launch.substitutions import PathJoinSubstitution
from launch.substitutions import PythonExpression
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def _resolve_sim_package():
    """
    Resolve package share for mixed historical package names.

    Preferred package is chasebot_sim. Fallback is chasebot_description.
    """
    for candidate in ('chasebot_sim', 'chasebot_description'):
        try:
            get_package_share_directory(candidate)
            return candidate
        except PackageNotFoundError:
            continue
    raise RuntimeError(
        'Unable to resolve package share for chasebot_sim or chasebot_description.'
    )


def generate_launch_description():
    sim_package = _resolve_sim_package()

    headless = LaunchConfiguration('headless')
    perf_profile = LaunchConfiguration('perf_profile')
    inference_device = LaunchConfiguration('inference_device')
    enable_test_movement = LaunchConfiguration('enable_test_movement')

    world_path = PathJoinSubstitution(
        [FindPackageShare(sim_package), 'ros2_config', 'worlds', 'yolo_test_world_v5_no_sensors_plugin.world']
    )
    sdf_path = PathJoinSubstitution(
        [FindPackageShare(sim_package), 'ros2_config', 'urdf', 'jetbot_core_ignition_v1.6.0.sdf']
    )
    controller_config = PathJoinSubstitution(
        [FindPackageShare(sim_package), 'ros2_config', 'config', 'jetbot_diff_drive_v1.0.0.yaml']
    )

    set_ign_plugin_path = SetEnvironmentVariable(
        name='IGN_GAZEBO_SYSTEM_PLUGIN_PATH',
        value='/opt/ros/humble/lib',
    )
    set_qt_mitshm = SetEnvironmentVariable(
        name='QT_X11_NO_MITSHM',
        value='1',
    )
    set_software_gl_for_compat = SetEnvironmentVariable(
        name='LIBGL_ALWAYS_SOFTWARE',
        value='1',
        condition=IfCondition(PythonExpression(["'", perf_profile, "' == 'compat'"])),
    )

    ignition_spawn_gui = ExecuteProcess(
        cmd=['ign', 'gazebo', '-v', '4', '-r', world_path],
        output='screen',
        additional_env={'IGN_GAZEBO_SYSTEM_PLUGIN_PATH': '/opt/ros/humble/lib'},
        condition=UnlessCondition(headless),
    )
    ignition_spawn_headless = ExecuteProcess(
        cmd=['ign', 'gazebo', '-v', '4', '-r', '--headless-rendering', world_path],
        output='screen',
        additional_env={'IGN_GAZEBO_SYSTEM_PLUGIN_PATH': '/opt/ros/humble/lib'},
        condition=IfCondition(headless),
    )

    # Minimal URDF required by controller_manager/robot_state_publisher.
    minimal_urdf = """<?xml version="1.0"?>
    <robot name="jetbot">
        <link name="base_link"/>
        <link name="left_wheel"/>
        <link name="right_wheel"/>
        <joint name="left_wheel_joint" type="continuous">
            <parent link="base_link"/>
            <child link="left_wheel"/>
            <origin xyz="0 0.08 0.032"/>
            <axis xyz="0 0 1"/>
        </joint>
        <joint name="right_wheel_joint" type="continuous">
            <parent link="base_link"/>
            <child link="right_wheel"/>
            <origin xyz="0 -0.08 0.032"/>
            <axis xyz="0 0 1"/>
        </joint>
        <ros2_control name="GazeboSimSystem" type="system">
            <hardware>
                <plugin>gz_ros2_control/GazeboSimSystem</plugin>
            </hardware>
            <joint name="left_wheel_joint">
                <command_interface name="velocity">
                    <param name="min">-10</param>
                    <param name="max">10</param>
                </command_interface>
                <state_interface name="position"/>
                <state_interface name="velocity"/>
            </joint>
            <joint name="right_wheel_joint">
                <command_interface name="velocity">
                    <param name="min">-10</param>
                    <param name="max">10</param>
                </command_interface>
                <state_interface name="position"/>
                <state_interface name="velocity"/>
            </joint>
        </ros2_control>
    </robot>"""

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'use_sim_time': True, 'robot_description': minimal_urdf}],
        output='screen',
    )

    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock',
            '/model/jetbot/cmd_vel@geometry_msgs/msg/Twist]ignition.msgs.Twist',
            '/model/jetbot/odometry@nav_msgs/msg/Odometry[ignition.msgs.Odometry',
            '/model/jetbot/tf@tf2_msgs/msg/TFMessage[ignition.msgs.Pose_V',
            '/world/yolo_test_world/model/jetbot/joint_state@sensor_msgs/msg/JointState[ignition.msgs.Model',
            '/d415/color/image_raw@sensor_msgs/msg/Image[ignition.msgs.Image',
            '/d415/color/camera_info@sensor_msgs/msg/CameraInfo[ignition.msgs.CameraInfo',
            '/d415/depth/image_raw@sensor_msgs/msg/Image[ignition.msgs.Image',
            '/d415/depth/camera_info@sensor_msgs/msg/CameraInfo[ignition.msgs.CameraInfo',
        ],
        output='screen',
    )

    spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=['-file', sdf_path, '-name', 'jetbot'],
        output='screen',
    )

    spawn_joint_state_broadcaster = Node(
        package='controller_manager',
        executable='spawner',
        arguments=[
            'joint_state_broadcaster',
            '--controller-manager',
            '/controller_manager',
            '--controller-manager-timeout',
            '30',
            '--switch-timeout',
            '20',
            '--param-file',
            controller_config,
        ],
        output='screen',
    )

    spawn_diff_drive_controller = Node(
        package='controller_manager',
        executable='spawner',
        arguments=[
            'jetbot_base_controller',
            '--controller-manager',
            '/controller_manager',
            '--controller-manager-timeout',
            '30',
            '--switch-timeout',
            '20',
            '--param-file',
            controller_config,
        ],
        output='screen',
    )

    test_movement = TimerAction(
        period=15.0,
        condition=IfCondition(enable_test_movement),
        actions=[
            ExecuteProcess(
                cmd=[
                    'ros2',
                    'topic',
                    'pub',
                    '--once',
                    '/jetbot_base_controller/cmd_vel',
                    'geometry_msgs/msg/TwistStamped',
                    '{twist: {linear: {x: 0.2}, angular: {z: 0.0}}}',
                ],
                output='screen',
            )
        ],
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                'inference_device',
                default_value='auto',
                description='Hint passed through canonical stack: auto|cuda:0|cpu',
            ),
            DeclareLaunchArgument(
                'perf_profile',
                default_value='balanced',
                description='Runtime profile: compat|balanced|max',
            ),
            DeclareLaunchArgument(
                'headless',
                default_value='false',
                description='Run Gazebo without GUI when true',
            ),
            DeclareLaunchArgument(
                'enable_test_movement',
                default_value='false',
                description='Publish one test cmd_vel after startup',
            ),
            LogInfo(msg=['Launching package: ', sim_package]),
            LogInfo(msg=['headless=', headless, ', perf_profile=', perf_profile, ', inference_device=', inference_device]),
            set_ign_plugin_path,
            set_qt_mitshm,
            set_software_gl_for_compat,
            ignition_spawn_gui,
            ignition_spawn_headless,
            robot_state_publisher,
            bridge,
            TimerAction(period=2.0, actions=[spawn_entity]),
            TimerAction(period=7.0, actions=[spawn_joint_state_broadcaster]),
            TimerAction(period=9.0, actions=[spawn_diff_drive_controller]),
            test_movement,
        ]
    )
