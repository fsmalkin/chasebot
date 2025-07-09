#!/usr/bin/env python3
"""
UAT Test Script for Slice 2.1: Detection Format Discovery
Launches simulation, YOLO detector, and discovery node
"""

import subprocess
import time
import os
import signal

def run_command(cmd, name, env=None):
    """Run a command and return the process"""
    print(f"Starting {name}...")
    if env:
        process_env = os.environ.copy()
        process_env.update(env)
        return subprocess.Popen(cmd, shell=True, env=process_env)
    return subprocess.Popen(cmd, shell=True)

def main():
    print("="*60)
    print("UAT Test for Slice 2.1: YOLO Detection Format Discovery")
    print("="*60)
    print()
    
    processes = []
    
    try:
        # Set up environment
        env_setup = "source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash"
        display_env = {"DISPLAY": "172.25.128.1:0.0"}
        
        # 1. Launch simulation with camera
        print("Step 1: Launching simulation with camera...")
        sim_cmd = f'wsl -d Ubuntu-22.04 -- bash -c "cd ~/ros2_ws && {env_setup} && export DISPLAY=172.25.128.1:0.0 && ros2 launch chasebot_sim jetbot_gz_control_camera_test_v3.launch.py"'
        sim_proc = run_command(sim_cmd, "Simulation")
        processes.append(sim_proc)
        
        print("Waiting 10 seconds for simulation to start...")
        time.sleep(10)
        
        # 2. Start YOLO detector (frisbee version)
        print("\nStep 2: Starting YOLO detector (frisbee class)...")
        yolo_cmd = f'wsl -d Ubuntu-22.04 -- bash -c "cd ~/ros2_ws && {env_setup} && export DISPLAY=172.25.128.1:0.0 && python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_detector_frisbee.py"'
        yolo_proc = run_command(yolo_cmd, "YOLO Detector")
        processes.append(yolo_proc)
        
        print("Waiting 5 seconds for YOLO to initialize...")
        time.sleep(5)
        
        # 3. Run discovery node
        print("\nStep 3: Running format discovery node...")
        discovery_cmd = f'wsl -d Ubuntu-22.04 -- bash -c "cd ~/ros2_ws && {env_setup} && python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/discover_yolo_format.py"'
        discovery_proc = run_command(discovery_cmd, "Discovery Node")
        processes.append(discovery_proc)
        
        print("\n" + "="*60)
        print("All components launched!")
        print("="*60)
        print()
        print("INSTRUCTIONS:")
        print("1. Check the Gazebo window - you should see the robot and a ball")
        print("2. Check the YOLO detector window - you should see detection visualization")
        print("3. Watch the discovery node output in this terminal")
        print()
        print("The discovery node will report:")
        print("  - What topics YOLO is publishing to")
        print("  - The message types and formats")
        print("  - The actual detection data")
        print()
        print("UAT SUCCESS CRITERIA:")
        print("  ✅ Discovery node receives and logs YOLO detection messages")
        print("  ✅ Message format is clearly displayed")
        print("  ✅ Normalized coordinates (0-1) are shown")
        print()
        print("Press Ctrl+C when you're done reviewing the output...")
        
        # Wait for user to stop
        discovery_proc.wait()
        
    except KeyboardInterrupt:
        print("\n\nShutting down all processes...")
        
    finally:
        # Clean up all processes
        for proc in processes:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except:
                proc.kill()
        
        print("All processes terminated.")
        print("\nUAT COMPLETE!")
        print("\nNEXT STEPS:")
        print("  - If discovery successful: Move to Slice 2.2 (Multi-class filter)")
        print("  - If no detections: Check simulation has ball in view")

if __name__ == "__main__":
    main()
