#!/usr/bin/env python3
"""
Quick script to check available depth topics from D415 camera
"""

import subprocess
import time

def main():
    print("=" * 60)
    print("Checking D415 Depth Topics")
    print("=" * 60)
    
    # Kill any existing processes
    print("\nCleaning up existing processes...")
    subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'gazebo'], stderr=subprocess.DEVNULL)
    subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'ros2'], stderr=subprocess.DEVNULL)
    time.sleep(2)
    
    # Launch simulation
    print("\nLaunching simulation with D415 camera...")
    sim_cmd = [
        'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
        'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
        'export DISPLAY=172.25.128.1:0.0 && '
        'ros2 launch chasebot_sim jetbot_gz_control_camera_test_v3.launch.py &'
    ]
    subprocess.Popen(sim_cmd, shell=False)
    
    print("Waiting for simulation to start...")
    time.sleep(15)
    
    # List all topics
    print("\nListing all available topics...")
    list_cmd = [
        'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
        'source /opt/ros/humble/setup.bash && ros2 topic list'
    ]
    result = subprocess.run(list_cmd, capture_output=True, text=True)
    print(result.stdout)
    
    # Filter for depth topics
    print("\nFiltering for depth-related topics...")
    topics = result.stdout.split('\n')
    depth_topics = [t for t in topics if 'depth' in t.lower() or 'd415' in t.lower()]
    
    if depth_topics:
        print("Found depth topics:")
        for topic in depth_topics:
            if topic.strip():
                print(f"  - {topic}")
                
                # Get topic info
                info_cmd = [
                    'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
                    f'source /opt/ros/humble/setup.bash && ros2 topic info {topic} -v'
                ]
                info_result = subprocess.run(info_cmd, capture_output=True, text=True)
                if info_result.stdout:
                    print(f"    Type: {info_result.stdout.strip()}")
    else:
        print("No depth topics found!")
    
    # Check camera info
    print("\nChecking camera info topic...")
    info_cmd = [
        'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
        'source /opt/ros/humble/setup.bash && ros2 topic echo /d415/camera_info --once'
    ]
    subprocess.run(info_cmd)
    
    # Cleanup
    print("\nCleaning up...")
    subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'gazebo'])
    subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'ros2'])
    
    print("\nDone!")

if __name__ == '__main__':
    main()
