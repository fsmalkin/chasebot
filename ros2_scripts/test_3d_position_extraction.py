#!/usr/bin/env python3
"""
Test script for 3D position extraction
Launches simulation, YOLO detector, and 3D position extractor
Updated to use correct topics for v5 configuration
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
    print("3D Position Extraction Test - v5 Configuration")
    print("=" * 60)
    print("\nIMPORTANT: Using separated RGB/Depth topics:")
    print("- RGB: /d415/color/image_raw")
    print("- Depth: /d415/depth/image_raw")
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
            'export DISPLAY=172.25.128.1:0.0 && '
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
        
        # Step 2: Launch YOLO detector (frisbee version with correct topic)
        print("\nStep 2: Launching YOLO detector (frisbee detector - proven to work)...")
        yolo_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_detector_frisbee.py '
            '--ros-args -p use_sim_time:=true -p confidence_threshold:=0.3 '
            '-p input_topic:=/d415/color/image_raw'  # CRITICAL: Use correct topic!
        ]
        yolo_proc = run_command(yolo_cmd, "YOLO Detector")
        processes.append((yolo_proc, "YOLO Detector"))
        
        print("Waiting for YOLO to initialize...")
        time.sleep(5)
        
        # Verify YOLO is publishing
        print("\nVerifying YOLO detection output...")
        verify_yolo_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 2 ros2 topic echo /yolo/ball_position --once'
        ]
        subprocess.run(verify_yolo_cmd)
        
        # Step 3: Launch 3D position extractor
        print("\nStep 3: Launching 3D position extractor...")
        extractor_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/yolo_3d_position_extractor.py '
            '--ros-args -p use_sim_time:=true -p confidence_threshold:=0.3'
        ]
        extractor_proc = run_command(extractor_cmd, "3D Position Extractor")
        processes.append((extractor_proc, "3D Position Extractor"))
        
        print("\nWaiting for 3D extraction to start...")
        time.sleep(5)
        
        # Step 4: Launch debug viewer
        print("\nStep 4: Launching debug viewer (shows RGB + Depth)...")
        viewer_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'export DISPLAY=172.25.128.1:0.0 && '
            'python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/d415_3d_debug_viewer.py '
            '--ros-args -p use_sim_time:=true'
        ]
        viewer_proc = run_command(viewer_cmd, "Debug Viewer")
        processes.append((viewer_proc, "Debug Viewer"))
        
        print("\nWaiting for viewer to start...")
        time.sleep(3)
        
        # Step 5: Monitor 3D position output
        print("\nStep 5: Monitoring 3D position output...")
        print("Watch the terminal for 3D position messages...")
        print("Expected output: 3D Position: [x, y, z]m")
        print("\nRunning for 20 seconds...")
        
        # Also echo the 3D position topic
        echo_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 20 ros2 topic echo /yolo/ball_position_3d'
        ]
        subprocess.run(echo_cmd)
        
        print("\n" + "=" * 60)
        print("TEST COMPLETE!")
        print("=" * 60)
        print("\nExpected Results:")
        print("✓ YOLO detector should report ball detections (as 'frisbee' ~0.5 confidence)")
        print("✓ 3D position extractor should publish [x, y, z] coordinates")
        print("✓ z value should be approximately 3.0m (distance to ball)")
        print("✓ x and y values depend on ball position relative to camera center")
        print("\nTroubleshooting:")
        print("- If no detections: Check that YOLO is using /d415/color/image_raw topic")
        print("- If no depth data: Verify /d415/depth/image_raw is publishing")
        print("- If viewer is blank: Check DISPLAY environment variable")
        
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
