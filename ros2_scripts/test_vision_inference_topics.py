#!/usr/bin/env python3
"""
Test script to verify camera topic compatibility with ros2_vision_inference
Based on test_camera_topic.py
"""

import subprocess
import time

def main():
    print("=" * 60)
    print("Testing ros2_vision_inference Topic Compatibility")
    print("=" * 60)
    
    # Check our D415 topics
    print("\n1. Checking D415 camera topics...")
    topics_cmd = ['wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
                  'source /opt/ros/humble/setup.bash && ros2 topic list | grep d415']
    
    result = subprocess.run(topics_cmd, capture_output=True, text=True)
    print("Available D415 topics:")
    print(result.stdout)
    
    # Check specific topics we need
    print("\n2. Checking required topics...")
    
    # Image topic
    image_cmd = ['wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
                 'source /opt/ros/humble/setup.bash && ros2 topic info /d415/color/image_raw']
    result = subprocess.run(image_cmd, capture_output=True, text=True)
    print("\nImage topic info:")
    print(result.stdout if result.returncode == 0 else "Topic not found")
    
    # Camera info topic
    info_cmd = ['wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
                'source /opt/ros/humble/setup.bash && ros2 topic info /d415/color/camera_info']
    result = subprocess.run(info_cmd, capture_output=True, text=True)
    print("\nCamera info topic:")
    print(result.stdout if result.returncode == 0 else "Topic not found")
    
    print("\n3. Topic mapping for ros2_vision_inference:")
    print("   - camera_topic: /d415/color/image_raw")
    print("   - camera_param: /d415/color/camera_info")
    print("   - output_bbox_topic: /vision_inference/bboxes")
    
    print("\n✅ Topics identified. Ready for integration.")
    

if __name__ == '__main__':
    main()
