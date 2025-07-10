#!/usr/bin/env python3
"""
Test script for ros2_vision_inference basic operation (Slice 3)
Based on test_3d_position_extraction.py
Launches simulation and vision inference, tests if it runs without crashes
"""

import subprocess
import time
import sys
import signal
import os

def run_command(cmd, name, shell=False):
    """Run a command and return the process"""
    print(f"Starting {name}...")
    proc = subprocess.Popen(cmd)
    time.sleep(2)
    return proc

def terminate_process_group(proc, name):
    """Terminate a process and all its children"""
    try:
        print(f"Terminating {name}...")
        if proc.poll() is None:
            proc.terminate()
            time.sleep(1)
            # If still running, force kill
            if proc.poll() is None:
                proc.kill()
    except Exception as e:
        print(f"Error terminating {name}: {e}")

def main():
    print("=" * 60)
    print("ROS2 Vision Inference Basic Test (Slice 3)")
    print("=" * 60)
    print("\nGoal: Launch vision_inference with our camera, see if it runs")
    print("=" * 60)
    
    # Get display IP dynamically
    print("\nDetecting display IP...")
    get_ip_cmd = [
        'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
        'cat /etc/resolv.conf | grep nameserver | awk \'{print $2}\''
    ]
    result = subprocess.run(get_ip_cmd, capture_output=True, text=True)
    # Extract just the IP address
    output = result.stdout.strip()
    if output:
        # Handle case where output might be "nameserver X.X.X.X" or just "X.X.X.X"
        parts = output.split()
        display_ip = parts[-1] if parts else ""
    else:
        display_ip = ""
    
    # Default fallback if detection fails
    if not display_ip:
        display_ip = "192.168.96.1"
        print(f"Could not detect display IP, using default: {display_ip}")
    else:
        print(f"Detected display IP: {display_ip}")
    
    display_var = f"{display_ip}:0.0"
    print(f"Using DISPLAY={display_var}")
    print("=" * 60)
    
    processes = []
    
    try:
        # Kill any existing processes
        print("\nCleaning up existing processes...")
        subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'gazebo'], stderr=subprocess.DEVNULL)
        subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'ros2'], stderr=subprocess.DEVNULL)
        subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'yolo'], stderr=subprocess.DEVNULL)
        time.sleep(2)
        
        # Step 1: Launch simulation with D415 camera (v5 with depth support)
        print("\nStep 1: Launching simulation with D415 camera (v5 with depth)...")
        sim_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            f'export DISPLAY={display_var} && '
            'ros2 launch chasebot_sim jetbot_gz_control_camera_test_v5.launch.py'
        ]
        sim_proc = run_command(sim_cmd, "Simulation")
        processes.append((sim_proc, "Simulation"))
        
        print("Waiting for simulation to start...")
        time.sleep(10)
        
        # Verify topics are available
        print("\nVerifying camera topics...")
        verify_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 topic list | grep d415'
        ]
        result = subprocess.run(verify_cmd, capture_output=True, text=True)
        print("Available D415 topics:")
        print(result.stdout)
        
        # Step 2: Launch vision inference directly
        print("\nStep 2: Launching ros2_vision_inference...")
        # Run the vision inference node directly with our parameters
        vision_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            f'export DISPLAY={display_var} && '
            'ros2 run ros2_vision_inference vision_inference_node --ros-args '
            '-p MONO3D_FLAG:=true '
            '-p MONO3D_CKPT_FILE:=/home/macro2/ros2_ws/models/mono3d_yolox_576_768.onnx '
            '-p MONO3D_GPU_INDEX:=0 '
            '-p SEG_FLAG:=false '
            '-p MONODEPTH_FLAG:=false '
            '-p CAMERA_TOPIC:=/d415/color/image_raw '
            '-p CAMERA_PARAM:=/d415/color/camera_info '
            '-p OUTPUT_BBOX_TOPIC:=/vision_inference/detections'
        ]
        vision_proc = run_command(vision_cmd, "Vision Inference")
        processes.append((vision_proc, "Vision Inference"))
        
        print("Waiting for vision inference to initialize...")
        time.sleep(10)
        
        # Verify it's running
        print("\nVerifying vision inference is running...")
        verify_node_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 node list | grep vision_inference'
        ]
        result = subprocess.run(verify_node_cmd, capture_output=True, text=True)
        print("Vision inference node:")
        print(result.stdout)
        
        # Check output topics
        print("\nChecking vision inference output topics...")
        verify_topics_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 topic list | grep vision_inference'
        ]
        result = subprocess.run(verify_topics_cmd, capture_output=True, text=True)
        print("Vision inference topics:")
        print(result.stdout)
        
        # Step 3: Monitor detection output
        print("\nStep 3: Monitoring detection output...")
        print("Checking if vision inference produces detections...")
        print("\nRunning for 10 seconds...")
        
        # Echo the detection topic
        echo_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 10 ros2 topic echo /vision_inference/detections'
        ]
        subprocess.run(echo_cmd)
        
        print("\n" + "=" * 60)
        print("TEST COMPLETE!")
        print("=" * 60)
        print("\nExpected Results:")
        print("✓ Vision inference node should be running without crashes")
        print("✓ /vision_inference/detections topic should exist")
        print("✓ May see Detection3DArray messages if ball is detected")
        print("\nTroubleshooting:")
        print("- If node crashes: Check ONNX model path in launch file")
        print("- If no node: Check package was built correctly")
        print("- If no detections: Normal - model may not detect our specific ball")
        print(f"- If display issues: Current DISPLAY={display_var}")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\nError during test: {e}")
    finally:
        print("\n\nCleaning up...")
        for proc, name in reversed(processes):
            terminate_process_group(proc, name)
        
        # Final cleanup
        subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'gazebo'], stderr=subprocess.DEVNULL)
        subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'ros2'], stderr=subprocess.DEVNULL)
        subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'yolo'], stderr=subprocess.DEVNULL)
        
        print("\nCleanup complete!")


if __name__ == '__main__':
    main()
