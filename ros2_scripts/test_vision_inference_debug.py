#!/usr/bin/env python3
"""
Debug test to see why vision_inference won't start
"""
import subprocess
import time
import os
import sys

def run_command(cmd, capture=True):
    """Run command and return output"""
    if capture:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip(), result.stderr.strip()
    else:
        subprocess.run(cmd, shell=True)
        return None, None

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
    print("Vision Inference Debug Test")
    print("="*60)
    print("Goal: Find out why vision_inference won't start")
    print("="*60)
    
    cleanup_processes()
    
    # First, let's check if vision_inference package is built
    print("\nStep 1: Checking if vision_inference package is built...")
    stdout, stderr = run_command('powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash && ros2 pkg list | grep vision\'"')
    print("Vision packages:")
    print(stdout if stdout else "No vision packages found")
    
    # Check if the executable exists
    print("\nStep 2: Checking if vision_inference_node executable exists...")
    stdout, stderr = run_command('powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'find ~/ros2_ws/install -name vision_inference_node -type f 2>/dev/null\'"')
    print("Executable location:")
    print(stdout if stdout else "Executable not found")
    
    # Try to run vision_inference_node directly to see errors
    print("\nStep 3: Trying to run vision_inference_node directly...")
    print("(This will likely fail but show us the error)\n")
    
    cmd = '''powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 run ros2_vision_inference vision_inference_node 2>&1 | head -20'"'''
    stdout, stderr = run_command(cmd)
    print("Output:")
    print(stdout)
    if stderr:
        print("Errors:")
        print(stderr)
    
    # Check launch file existence
    print("\nStep 4: Checking if our launch file exists...")
    stdout, stderr = run_command('powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'ls -la ~/ros2_ws/install/chasebot_sim/share/chasebot_sim/ros2_config/launch/chasebot_vision_inference.launch.xml\'"')
    print(stdout if stdout else "Launch file not found")
    
    # Try running with the mono3d.launch.py that comes with the package
    print("\nStep 5: Trying the package's original launch file...")
    
    # First launch simulation
    print("\nLaunching simulation...")
    sim_cmd = '''powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=192.168.86.237:0.0 && ros2 launch chasebot_sim jetbot_gz_control_camera_test_v5.launch.py'"'''
    sim_proc = subprocess.Popen(sim_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    print("Waiting for simulation...")
    time.sleep(15)
    
    # Try the original launch file with parameters
    print("\nTrying mono3d.launch.py with our parameters...")
    vi_cmd = '''powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 launch ros2_vision_inference mono3d.launch.py camera_image_topic:=/d415/color/image_raw camera_info_topic:=/d415/color/camera_info 2>&1 | head -50'"'''
    
    stdout, stderr = run_command(vi_cmd)
    print("Launch output:")
    print(stdout)
    if stderr:
        print("Launch errors:")
        print(stderr)
    
    # Check if it's running now
    time.sleep(5)
    print("\nChecking if vision node is running...")
    stdout, stderr = run_command('powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && ros2 node list | grep -i vision\'"')
    print("Vision nodes:", stdout if stdout else "No vision nodes found")
    
    # Cleanup
    print("\nCleaning up...")
    if sim_proc:
        sim_proc.terminate()
    cleanup_processes()
    
    print("\nTest complete!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        cleanup_processes()
        sys.exit(0)
