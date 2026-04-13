#!/usr/bin/env python3
"""
Launch file for JetBot + gz_ros2_control + D415 sensors (v5 baseline).

Canonical runtime arguments:
- inference_device: auto|cuda:0|cpu
- perf_profile: compat|balanced|max
- headless: true|false
"""

import os
import re
import shutil
import tempfile

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
    source_path = os.environ.get('CHASECAR_SOURCE_PATH', '').strip()
    if source_path and os.path.isdir(os.path.join(source_path, 'ros2_config')):
        return None, source_path

    for candidate in ('chasebot_sim', 'chasebot_description'):
        try:
            share_dir = get_package_share_directory(candidate)
            return candidate, share_dir
        except PackageNotFoundError:
            continue
    raise RuntimeError(
        'Unable to resolve package share for chasebot_sim/chasebot_description '
        'and CHASECAR_SOURCE_PATH is not set to a valid source tree.'
    )


def _prepare_runtime_sdf(sim_share_dir: str, controller_config_path: str) -> str:
    """
    Create a runtime SDF copy with an explicit gz_ros2_control parameter file path.

    Jazzy's GazeboSimROS2ControlPlugin fails to initialize if parameters are empty.
    """
    source_sdf_name = os.environ.get('CHASECAR_ROBOT_SDF_NAME', 'jetbot_core_ignition_v1.7.0.sdf').strip() or 'jetbot_core_ignition_v1.7.0.sdf'
    source_sdf = os.path.join(sim_share_dir, 'ros2_config', 'urdf', source_sdf_name)
    if not os.path.isfile(source_sdf):
        raise RuntimeError(f'Unable to locate requested robot SDF: {source_sdf}')

    with open(source_sdf, 'r', encoding='utf-8') as fp:
        sdf_text = fp.read()

    plugin_marker = '<plugin filename="libgz_ros2_control-system.so" name="gz_ros2_control::GazeboSimROS2ControlPlugin">'
    plugin_start = sdf_text.find(plugin_marker)
    if plugin_start < 0:
        raise RuntimeError('Unable to find GazeboSimROS2ControlPlugin block in SDF template.')

    plugin_end = sdf_text.find('</plugin>', plugin_start)
    if plugin_end < 0:
        raise RuntimeError('Unable to find end of GazeboSimROS2ControlPlugin block in SDF template.')
    plugin_end += len('</plugin>')

    plugin_block = sdf_text[plugin_start:plugin_end]
    parameters_tag = f'<parameters>{controller_config_path}</parameters>'
    if '<parameters>' in plugin_block:
        plugin_block = re.sub(
            r'<parameters>.*?</parameters>',
            parameters_tag,
            plugin_block,
            count=1,
            flags=re.DOTALL,
        )
    else:
        plugin_block = plugin_block.replace(
            plugin_marker,
            f'{plugin_marker}\n      {parameters_tag}',
            1,
        )

    runtime_sdf_text = sdf_text[:plugin_start] + plugin_block + sdf_text[plugin_end:]
    runtime_dir = os.path.join(tempfile.gettempdir(), 'chasecar_runtime')
    os.makedirs(runtime_dir, exist_ok=True)
    runtime_stub = os.path.splitext(os.path.basename(source_sdf_name))[0]
    runtime_sdf = os.path.join(runtime_dir, f'{runtime_stub}.{os.getpid()}.sdf')
    with open(runtime_sdf, 'w', encoding='utf-8') as fp:
        fp.write(runtime_sdf_text)
    return runtime_sdf


def generate_launch_description():
    sim_package, sim_share_dir = _resolve_sim_package()
    ros_distro = os.environ.get('ROS_DISTRO', 'jazzy')
    ros_lib_dir = f'/opt/ros/{ros_distro}/lib'
    sim_source_label = sim_package if sim_package is not None else sim_share_dir

    world = LaunchConfiguration('world')
    headless = LaunchConfiguration('headless')
    perf_profile = LaunchConfiguration('perf_profile')
    inference_device = LaunchConfiguration('inference_device')
    enable_test_movement = LaunchConfiguration('enable_test_movement')

    controller_config_path = os.path.join(
        sim_share_dir,
        'ros2_config',
        'config',
        'jetbot_diff_drive_v1.0.0.yaml',
    )
    runtime_sdf_path = _prepare_runtime_sdf(sim_share_dir, controller_config_path)

    if sim_package is not None:
        world_path = PathJoinSubstitution([FindPackageShare(sim_package), 'ros2_config', 'worlds', world])
    else:
        world_path = PathJoinSubstitution([sim_share_dir, 'ros2_config', 'worlds', world])
    sdf_path = runtime_sdf_path

    sim_exec = 'ign' if shutil.which('ign') else 'gz'
    if sim_exec == 'ign':
        sim_cmd_gui = ['ign', 'gazebo', '-v', '4', '-r', world_path]
        sim_cmd_headless = ['ign', 'gazebo', '-s', '-v', '4', '-r', '--headless-rendering', world_path]
    else:
        sim_cmd_gui = ['gz', 'sim', '-v', '4', '-r', world_path]
        sim_cmd_headless = ['gz', 'sim', '-s', '-v', '4', '-r', '--headless-rendering', world_path]

    set_ign_plugin_path = SetEnvironmentVariable(
        name='IGN_GAZEBO_SYSTEM_PLUGIN_PATH',
        value=ros_lib_dir,
    )
    set_gz_plugin_path = SetEnvironmentVariable(
        name='GZ_SIM_SYSTEM_PLUGIN_PATH',
        value=ros_lib_dir,
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
        cmd=sim_cmd_gui,
        output='screen',
        additional_env={
            'IGN_GAZEBO_SYSTEM_PLUGIN_PATH': ros_lib_dir,
            'GZ_SIM_SYSTEM_PLUGIN_PATH': ros_lib_dir,
        },
        condition=UnlessCondition(headless),
    )
    ignition_spawn_headless = ExecuteProcess(
        cmd=sim_cmd_headless,
        output='screen',
        additional_env={
            'IGN_GAZEBO_SYSTEM_PLUGIN_PATH': ros_lib_dir,
            'GZ_SIM_SYSTEM_PLUGIN_PATH': ros_lib_dir,
        },
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
            '/observer/image_raw@sensor_msgs/msg/Image[ignition.msgs.Image',
            '/observer/camera_info@sensor_msgs/msg/CameraInfo[ignition.msgs.CameraInfo',
            '/observer_world/image_raw@sensor_msgs/msg/Image[ignition.msgs.Image',
            '/observer_world/camera_info@sensor_msgs/msg/CameraInfo[ignition.msgs.CameraInfo',
        ],
        remappings=[
            ('/model/jetbot/odometry', '/odom'),
            ('/model/jetbot/tf', '/tf'),
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
            controller_config_path,
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
            controller_config_path,
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
                'world',
                default_value='yolo_test_world_v6_clean_uat.world',
                description='World file under ros2_config/worlds',
            ),
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
            LogInfo(msg=['Launching source: ', sim_source_label]),
            LogInfo(msg=['ROS distro=', ros_distro, ', sim_exec=', sim_exec]),
            LogInfo(msg=['world=', world]),
            LogInfo(msg=['headless=', headless, ', perf_profile=', perf_profile, ', inference_device=', inference_device]),
            set_ign_plugin_path,
            set_gz_plugin_path,
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
