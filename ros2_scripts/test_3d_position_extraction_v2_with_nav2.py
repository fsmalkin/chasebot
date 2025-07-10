#!/usr/bin/env python3
"""
Test script for 3D position extraction with Nav2 integration
Launches simulation, YOLO detector, 3D position extractor, and Nav2 autonomous navigation
Version 2: Adds Nav2 and autonomous ball following
Based on working v1 test_3d_position_extraction.py
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
    print("=" * 80)
    print("3D Position Extraction + Nav2 Autonomous Following - v2")
    print("=" * 80)
    print("\nFeatures:")
    print("✓ D415 camera with separated RGB/Depth topics")
    print("✓ YOLO detection (as frisbee)")
    print("✓ 3D position extraction")
    print("✓ Nav2 navigation stack")
    print("✓ Autonomous ball following (15cm approach)")
    print("=" * 80)
    
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
        subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'nav2'], stderr=subprocess.DEVNULL)
        time.sleep(3)
        
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
        
        # Step 2: Launch YOLO detector (frisbee version with correct topic)
        print("\nStep 2: Launching YOLO detector (quiet version to reduce terminal flooding)...")
        yolo_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            f'export DISPLAY={display_var} && '
            'python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_detector_frisbee_quiet.py '
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
            f'export DISPLAY={display_var} && '
            'python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/d415_3d_debug_viewer.py '
            '--ros-args -p use_sim_time:=true'
        ]
        viewer_proc = run_command(viewer_cmd, "Debug Viewer")
        processes.append((viewer_proc, "Debug Viewer"))
        
        print("\nWaiting for viewer to start...")
        time.sleep(3)
        
        # Step 5: Launch Nav2 stack
        print("\nStep 5: Launching Nav2 navigation stack...")
        nav2_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 launch nav2_bringup navigation_launch.py use_sim_time:=True'
        ]
        nav2_proc = run_command(nav2_cmd, "Nav2 Stack")
        processes.append((nav2_proc, "Nav2 Stack"))
        
        print("Waiting for Nav2 to initialize (this takes time)...")
        time.sleep(15)
        
        # Verify Nav2 is running
        print("\nVerifying Nav2 action server...")
        verify_nav2_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 2 ros2 action list | grep navigate_to_pose'
        ]
        result = subprocess.run(verify_nav2_cmd, capture_output=True, text=True)
        if 'navigate_to_pose' in result.stdout:
            print("✅ Nav2 action server is ready!")
        else:
            print("⚠️  Nav2 action server not detected, but continuing...")
        
        # Step 6: Launch YOLO 3D to Nav2 bridge
        print("\nStep 6: Launching YOLO 3D to Nav2 bridge...")
        print("  📏 Approach distance: 15cm")
        print("  ⏱️  Goal cooldown: 5 seconds")
        bridge_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_to_nav_goal_v3.0.0.py '
            '--ros-args -p use_sim_time:=true -p approach_distance:=0.15 -p cooldown_time:=5.0'
        ]
        bridge_proc = run_command(bridge_cmd, "YOLO to Nav2 Bridge")
        processes.append((bridge_proc, "YOLO to Nav2 Bridge"))
        
        print("\nWaiting for bridge to initialize...")
        time.sleep(3)
        
        # Step 7: Monitor system
        print("\nStep 7: System Running - Monitoring output...")
        print("\n" + "=" * 60)
        print("🎉 ALL COMPONENTS LAUNCHED!")
        print("=" * 60)
        print("\n📊 Expected Behavior:")
        print("  1. YOLO detects ball (as frisbee)")
        print("  2. 3D extractor calculates [x,y,z] position")
        print("  3. Bridge sends Nav2 goal 15cm before ball")
        print("  4. Robot autonomously navigates to ball")
        print("  5. Robot stops 15cm from ball")
        print("\n👀 Watch for:")
        print("  - Ball detection messages")
        print("  - 3D position calculations")
        print("  - Nav2 goal acceptance")
        print("  - Robot movement in Gazebo")
        
        print("\nRunning for 60 seconds... Press Ctrl+C to stop early")
        
        # Monitor 3D position topic
        echo_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 60 ros2 topic echo /yolo/ball_position_3d'
        ]
        subprocess.run(echo_cmd)
        
        print("\n" + "=" * 60)
        print("✅ TEST COMPLETE!")
        print("=" * 60)
        
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
        subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'nav2'], stderr=subprocess.DEVNULL)
        
        print("\nCleanup complete!")


if __name__ == '__main__':
    main()
