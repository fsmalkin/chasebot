#!/usr/bin/env python3
"""
Direct Follower V2 Test - Fixed Coordinate Transformation
Goal: Test YOLO + Depth pipeline with corrected coordinate transformation
UAT: Robot detects a ball and approaches it directly without spiraling
Version: 2.0.0
Based on: test_direct_follower.py
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
    print("🎯 Direct Follower V2 Test - Fixed Coordinate Transformation")
    print("=" * 80)
    print("\n📋 Test Objective:")
    print("  - Launch simulation with GUI and golf ball")
    print("  - Start YOLO detector (headless)")
    print("  - Start 3D position extractor")
    print("  - Start Direct Follower V2 (with coordinate transformation)")
    print("  - Robot approaches ball directly without spiraling")
    print("\n✅ Success Criteria:")
    print("  - YOLO detects golf ball (as 'frisbee')")
    print("  - 3D position is extracted from depth data")
    print("  - Direct follower V2 properly transforms coordinates")
    print("  - Robot approaches ball directly (no spiraling)")
    print("  - Robot stops within 15cm of ball")
    print("\n🔧 Key Fix:")
    print("  - Camera frame (X-right, Y-down, Z-forward)")
    print("  - Robot frame (X-forward, Y-left, Z-up)")
    print("  - Transform: robot_x=camera_z, robot_y=-camera_x")
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
        
        # Verify robot control topics
        print("\nVerifying robot control topics...")
        verify_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 topic list | grep -E "(cmd_vel|odom)"'
        ]
        result = subprocess.run(verify_cmd, capture_output=True, text=True)
        print("Available control topics:")
        print(result.stdout)
        
        # Step 2: Start YOLO detector (frisbee quiet version)
        print("\n🎯️ Step 2: Starting YOLO detector (frisbee quiet)...")
        yolo_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_detector_frisbee_quiet.py '
            '--ros-args -p use_sim_time:=true -p confidence_threshold:=0.3'
        ]
        yolo_proc = run_command(yolo_cmd, "YOLO Detector")
        processes.append((yolo_proc, "YOLO Detector"))
        
        # Step 3: Start 3D position extractor
        print("\n📐 Step 3: Starting 3D position extractor...")
        pos3d_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/yolo_3d_position_extractor.py'
        ]
        pos3d_proc = run_command(pos3d_cmd, "3D Position Extractor")
        processes.append((pos3d_proc, "3D Position Extractor"))
        
        # Step 4: Start Direct Follower V2 (with coordinate transformation)
        print("\n🎯 Step 4: Starting Direct Follower V2 (Fixed Coordinates)...")
        follower_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/yolo_3d_direct_follower_v2.py'
        ]
        follower_proc = run_command(follower_cmd, "Direct Follower V2")
        processes.append((follower_proc, "Direct Follower V2"))
        
        print("\n" + "=" * 60)
        print("🤖 AUTONOMOUS BALL FOLLOWING ACTIVE (V2)")
        print("=" * 60)
        print("\n🎾 Place a golf ball in front of the robot in Gazebo")
        print("📏 Optimal detection distance: 1-3 meters")
        print("⏳ The robot should approach directly without spiraling")
        print("\n📊 Monitoring system status...")
        
        # Monitor YOLO detections
        print("\n🔍 Step 5: Monitoring YOLO detections...")
        monitor_yolo_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 10 ros2 topic echo /yolo/ball_position --once'
        ]
        subprocess.run(monitor_yolo_cmd)
        
        # Monitor 3D positions
        print("\n📐 Step 6: Monitoring 3D positions...")
        monitor_3d_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 10 ros2 topic echo /yolo/ball_position_3d --once'
        ]
        subprocess.run(monitor_3d_cmd)
        
        # Let the system run for a while
        print("\n⏱️ Running autonomous ball following for 30 seconds...")
        print("Watch the robot in Gazebo GUI - it should approach the ball directly!")
        time.sleep(30)
        
        # Monitor robot movement
        print("\n🚗 Step 7: Checking robot movement...")
        monitor_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 5 ros2 topic echo /jetbot_base_controller/cmd_vel'
        ]
        subprocess.run(monitor_cmd)
        
        # Check final robot position
        print("\n📍 Step 8: Checking robot position...")
        odom_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 2 ros2 topic echo /odom --once'
        ]
        subprocess.run(odom_cmd)
        
        print("\n" + "=" * 80)
        print("✅ DIRECT FOLLOWER V2 TEST COMPLETE!")
        print("=" * 80)
        print("\n📊 Expected Results:")
        print("✓ YOLO detector finds golf balls (as 'frisbee' class)")
        print("✓ 3D positions extracted from depth data")
        print("✓ Direct follower V2 transforms coordinates correctly")
        print("✓ Robot approaches ball directly (no spiraling)")
        print("✓ Robot stops within 15cm of the ball")
        print("\n🔧 If Still Spiraling:")
        print("- Check coordinate transform in follower logs")
        print("- May need to adjust angular gain (currently 2.0)")
        print("- Consider reducing max angular speed (currently 0.5 rad/s)")
        print("\n🎯 Parameter Tuning:")
        print("- linear_gain: Controls forward speed response")
        print("- angular_gain: Controls turning response")
        print("- Lower gains = smoother but slower")
        print("- Higher gains = faster but may oscillate")
        
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
        subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'nav2'], stderr=subprocess.DEVNULL)
        
        print("\nCleanup complete!")


if __name__ == '__main__':
    main()
