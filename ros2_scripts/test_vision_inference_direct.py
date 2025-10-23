#!/usr/bin/env python3
"""
Direct test of vision_inference using our launch file
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
    print("Vision Inference Direct Test")
    print("="*60)
    print("Goal: Launch vision_inference with our custom launch file")
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
    
    # Check camera topics are available
    print("\nStep 2: Verifying camera topics...")
    camera_topics = run_command('powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && ros2 topic list | grep d415\'"')
    print("Camera topics:")
    print(camera_topics)
    
    # Launch vision inference with our launch file
    print("\nStep 3: Launching vision_inference with our launch file...")
    vi_cmd = f'''powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export ROS_DOMAIN_ID=0 && ros2 launch chasebot_sim chasebot_vision_inference.launch.xml'"'''
    
    vi_proc = subprocess.Popen(vi_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    print("Waiting for vision_inference to initialize...")
    time.sleep(10)
    
    # Check for nodes
    print("\nStep 4: Checking ROS nodes...")
    nodes = run_command('powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && ros2 node list\'"')
    print("Active nodes:")
    print(nodes)
    
    # Check for vision topics
    print("\nStep 5: Checking for vision inference topics...")
    topics = run_command('powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && ros2 topic list | grep -E \"vision|detection\"\'"')
    print("Vision-related topics:")
    print(topics if topics else "No vision topics found")
    
    # Try to echo the detection topic
    print("\nStep 6: Trying to echo detection topic...")
    echo_cmd = 'powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && timeout 5 ros2 topic echo /vision_inference/detections --once 2>&1\'"'
    echo_result = run_command(echo_cmd)
    print("Echo result:")
    print(echo_result)
    
    # Check if vision inference process is still running
    print("\nStep 7: Checking if vision_inference is still running...")
    ps_result = run_command('powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'ps aux | grep vision_inference | grep -v grep\'"')
    print("Vision inference processes:")
    print(ps_result if ps_result else "No vision_inference process found")
    
    # Keep running for a bit
    print("\nMonitoring for 10 seconds...")
    time.sleep(10)
    
    # Final check
    print("\nFinal status check:")
    final_nodes = run_command('powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && ros2 node list | grep -i vision\'"')
    print("Vision nodes:", final_nodes if final_nodes else "No vision nodes found")
    
    final_topics = run_command('powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && ros2 topic list | grep -E \"vision|detection|bbox\"\'"')
    print("Detection topics:", final_topics if final_topics else "No detection topics found")
    
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
