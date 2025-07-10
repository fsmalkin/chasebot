#!/usr/bin/env python3
"""
Test what topics vision_inference is subscribing/publishing to
"""
import subprocess
import time
import signal
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
    print("Vision Inference Topics Test")
    print("="*60)
    print("Goal: See what topics vision_inference subscribes/publishes")
    print("="*60)
    
    cleanup_processes()
    
    # Detect display
    print("\nDetecting display IP...")
    display_ip = run_command('ipconfig | findstr /i "ipv4" | findstr /i "192.168" | head -1')
    if display_ip:
        display_ip = display_ip.split(':')[-1].strip()
        print(f"Detected display IP: {display_ip}")
        os.environ['DISPLAY'] = f"{display_ip}:0.0"
        print(f"Using DISPLAY={display_ip}:0.0")
    else:
        print("Could not detect display IP, using default")
        os.environ['DISPLAY'] = "172.25.128.1:0.0"
    print("="*60)
    
    # Launch simulation with camera
    print("\nStep 1: Launching simulation...")
    sim_cmd = f'''powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY={os.environ["DISPLAY"]} && ros2 launch chasebot_sim jetbot_gz_control_camera_test_v5.launch.py'"'''
    
    sim_proc = subprocess.Popen(sim_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    print("Waiting for simulation to stabilize...")
    time.sleep(15)
    
    # Launch vision inference
    print("\nStep 2: Launching vision_inference...")
    vi_cmd = f'''powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export ROS_DOMAIN_ID=0 && ros2 launch ros2_vision_inference mono3d.launch.py camera_image_topic:=/d415/color/image_raw camera_info_topic:=/d415/color/camera_info'"'''
    
    vi_proc = subprocess.Popen(vi_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    print("Waiting for vision_inference to initialize...")
    time.sleep(10)
    
    # Check all topics
    print("\nStep 3: Checking all topics...")
    print("\nAll available topics:")
    topics = run_command('powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && ros2 topic list | sort\'"')
    print(topics)
    
    # Check node info
    print("\nStep 4: Checking vision_inference node info...")
    node_info = run_command('powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && ros2 node info /VisionInferenceNode\'"')
    print(node_info)
    
    # Check specific topics
    print("\nStep 5: Checking specific topics...")
    print("\nCamera topics with data:")
    for topic in ['/d415/color/image_raw', '/d415/color/camera_info']:
        hz = run_command(f'powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && timeout 2 ros2 topic hz {topic} 2>&1 | grep -E \"average rate|no messages\" | head -1\'"')
        print(f"{topic}: {hz}")
    
    print("\nVision inference topics:")
    vi_topics = run_command('powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && ros2 topic list | grep vision\'"')
    print(vi_topics if vi_topics else "No vision inference topics found")
    
    # Keep running for a bit to see if detections appear
    print("\nMonitoring for 10 seconds...")
    time.sleep(10)
    
    print("\nFinal topic check:")
    vi_topics = run_command('powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && ros2 topic list | grep -E \"vision|detection|3d\"\'"')
    print(vi_topics if vi_topics else "No detection topics found")
    
    # Cleanup
    print("\nCleaning up...")
    if sim_proc:
        sim_proc.terminate()
    if vi_proc:
        vi_proc.terminate()
    time.sleep(2)
    cleanup_processes()
    
    print("\nTest complete!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        cleanup_processes()
        sys.exit(0)
