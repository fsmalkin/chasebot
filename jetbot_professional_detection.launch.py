#!/usr/bin/env python3

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
import os

def generate_launch_description():
    # Get the path to our downloaded model
    model_path = os.path.expanduser('~/ros2_ws/models/mono3d_yolox_576_768.onnx')
    
    return LaunchDescription([
        # Launch arguments for configuration
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation (Gazebo) clock if true'
        ),
        
        # Launch our JetBot with camera
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                PathJoinSubstitution([
                    FindPackageShare('chasebot_description'),
                    'launch',
                    'jetbot_autonomous_ball_following.launch.py'
                ])
            ]),
            launch_arguments={'use_sim_time': LaunchConfiguration('use_sim_time')}.items()
        ),
        
        # Launch ros2_vision_inference node for professional 3D ball detection
        Node(
            package='ros2_vision_inference',
            executable='vision_inference_node',
            name='professional_ball_detector',
            parameters=[{
                'use_sim_time': LaunchConfiguration('use_sim_time'),
                
                # Enable only mono3d detection for sports balls
                'mono3d_flag': True,
                'mono3d_ckpt_file': model_path,
                'mono3d_gpu_index': 0,
                
                # Disable other features for this test
                'seg_flag': False,
                'monodepth_flag': False,
                
                # Map to our camera topics
                'camera_topic': '/camera/image_raw',
                'camera_param': '/camera/camera_info',
                
                # Output topics for detected balls
                'output_bbox_topic': '/professional_ball_detections',
                'output_seg_pointcloud_topic': '/ball_pointcloud'
            }],
            remappings=[
                ('/image_raw', '/camera/image_raw'),
                ('/camera_info', '/camera/camera_info'),
            ],
            output='screen'
        ),
        
        # Node to visualize professional detections alongside our HSV detection
        Node(
            package='chasebot_description', 
            executable='ros2_vision_comparison.py',
            name='vision_comparison_display',
            parameters=[{
                'use_sim_time': LaunchConfiguration('use_sim_time')
            }],
            output='screen'
        )
    ])

if __name__ == '__main__':
    generate_launch_description()
