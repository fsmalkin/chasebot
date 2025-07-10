#!/usr/bin/env python3
"""
Check all topics from vision_inference node
"""
import subprocess
import time
import os
import sys

def run_command(cmd):
    """Run command and return output"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip()

def cleanup_processes():
    """Clean up any existing processes"""
    print("Cleaning up existing processes...")
    commands = [
        'powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'pkill -9 -f gazebo\'"',
        'powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'pkill -9 -f ign\'"',
        'powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'pkill -9 -f ros2\'"',
        'powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'pkill -9 -f vision_inference\'"',
    ]
    for cmd in commands:
        subprocess.run(cmd, shell=True, capture_output=True)
    time.sleep(2)

def main():
    print("="*60)
    print("Vision Inference Topic Check")
    print("="*60)
    
    cleanup_processes()
    
    # Launch simulation
    print("\nLaunching simulation...")
    sim_cmd = '''powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=192.168.86.237:0.0 && ros2 launch chasebot_sim jetbot_gz_control_camera_test_v5.launch.py'"'''
    
    sim_proc = subprocess.Popen(sim_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    print("Waiting for simulation...")
    time.sleep(15)
    
    # Launch vision inference
    print("\nLaunching vision_inference...")
    vi_cmd = '''powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 launch ros2_vision_inference detect_seg_depth.launch.xml mono3d_flag:=true mono3d_ckpt_file:=/home/macro2/ros2_ws/models/mono3d_yolox_576_768.onnx seg_flag:=false monodepth_flag:=false camera_topic:=/d415/color/image_raw camera_param:=/d415/color/camera_info output_bbox_topic:=/detections'"'''
    
    vi_proc = subprocess.Popen(vi_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    print("Waiting for vision_inference...")
    time.sleep(15)
    
    # Check all topics
    print("\nAll topics:")
    topics = run_command('powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && ros2 topic list | sort\'"')
    print(topics)
    
    # Check node info
    print("\nVision inference node info:")
    node_info = run_command('powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && ros2 node info /vision_inference 2>&1\'"')
    print(node_info)
    
    # Check specific detection-related topics
    print("\nChecking detection-related topics...")
    for topic in ['/detections', '/bboxes', '/mono3d/bbox', '/point_cloud']:
        topic_type = run_command(f'powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && ros2 topic type {topic} 2>&1\'"')
        if "Unknown topic" not in topic_type:
            print(f"\n{topic}: {topic_type}")
            # Try to echo it
            echo = run_command(f'powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && timeout 3 ros2 topic echo {topic} --once 2>&1\'"')
            print(f"Sample: {echo[:200]}...")
    
    # Check camera data
    print("\nChecking camera data flow...")
    cam_echo = run_command('powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && ros2 topic hz /d415/color/image_raw 2>&1 | head -5\'"')
    print(f"Camera status:\n{cam_echo}")
    
    # Try to save a camera frame
    print("\nTrying to save camera image...")
    save_cmd = '''powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && python3 -c \"import rclpy; from sensor_msgs.msg import Image; import cv2; from cv_bridge import CvBridge; import numpy as np; rclpy.init(); node = rclpy.create_node(\'img_saver\'); bridge = CvBridge(); img_msg = None; def cb(msg): global img_msg; img_msg = msg; node.create_subscription(Image, \'/d415/color/image_raw\', cb, 1); rclpy.spin_once(node, timeout_sec=5.0); print(\'Got image\' if img_msg else \'No image\'); rclpy.shutdown()\" 2>&1'"'''
    save_result = run_command(save_cmd)
    print(save_result)
    
    # Cleanup
    print("\nCleaning up...")
    if sim_proc:
        sim_proc.terminate()
    if vi_proc:
        vi_proc.terminate()
    time.sleep(2)
    cleanup_processes()
    
    print("\nDone!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        cleanup_processes()
        sys.exit(0)
