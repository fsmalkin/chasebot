#!/usr/bin/env python3
"""
Slice 4: Full Vision + Nav2 Integration Test
Goal: Integrate YOLO + Depth pipeline with Nav2 for autonomous ball following
UAT: Robot detects a ball and autonomously approaches within 15cm
Version: 1.0.0
Based on: test_nav2_slice1_5_with_map.py
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
    print("🎯 Slice 4: Full Vision + Nav2 Integration Test")
    print("=" * 80)
    print("\n📋 Test Objective:")
    print("  - Launch simulation with GUI and golf ball")
    print("  - Start blank map publisher and transforms")
    print("  - Start Nav2 navigation stack")
    print("  - Start YOLO detector (headless)")
    print("  - Start 3D position extractor")
    print("  - Start YOLO to Nav2 bridge")
    print("  - Robot autonomously approaches ball")
    print("\n✅ Success Criteria:")
    print("  - YOLO detects golf ball (as 'frisbee')")
    print("  - 3D position is extracted from depth data")
    print("  - Nav2 receives and executes approach goal")
    print("  - Robot stops within 15cm of ball")
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
        
        # Step 2: Start blank map publisher
        print("\n🗺️ Step 2: Starting blank map publisher...")
        map_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/blank_map_publisher.py'
        ]
        map_proc = run_command(map_cmd, "Blank Map Publisher")
        processes.append((map_proc, "Blank Map Publisher"))
        
        # Step 3: Add static transform from map to odom
        print("\n🔗 Step 3: Publishing map->odom transform...")
        tf_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 run tf2_ros static_transform_publisher 0 0 0 0 0 0 map odom'
        ]
        tf_proc = run_command(tf_cmd, "Map->Odom Transform")
        processes.append((tf_proc, "Map->Odom Transform"))
        
        # Verify transforms
        print("\n🔍 Verifying transforms...")
        verify_tf_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 2 ros2 run tf2_ros tf2_echo map odom'
        ]
        subprocess.run(verify_tf_cmd)
        
        # Step 4: Launch Nav2 stack with topic remapping
        print("\n🗺️ Step 4: Launching Nav2 navigation stack with topic remapping...")
        nav2_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 launch nav2_bringup navigation_launch.py use_sim_time:=True '
            '--ros-args -r /cmd_vel:=/jetbot_base_controller/cmd_vel'
        ]
        nav2_proc = run_command(nav2_cmd, "Nav2 Stack")
        processes.append((nav2_proc, "Nav2 Stack"))
        
        print("⏳ Waiting for Nav2 to initialize (this takes time)...")
        time.sleep(15)
        
        # Verify Nav2 is running
        print("\n🔍 Verifying Nav2 action server...")
        verify_nav2_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 2 ros2 action list | grep navigate_to_pose'
        ]
        result = subprocess.run(verify_nav2_cmd, capture_output=True, text=True)
        if 'navigate_to_pose' in result.stdout:
            print("✅ Nav2 action server is ready!")
        else:
            print("⚠️  Nav2 action server not detected yet...")
        
        # Step 5: Start YOLO detector (headless version)
        print("\n👁️ Step 5: Starting YOLO detector (headless)...")
        yolo_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_detector_headless.py'
        ]
        yolo_proc = run_command(yolo_cmd, "YOLO Detector")
        processes.append((yolo_proc, "YOLO Detector"))
        
        # Step 6: Start 3D position extractor
        print("\n📍 Step 6: Starting 3D position extractor...")
        pos3d_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/yolo_3d_position_extractor.py'
        ]
        pos3d_proc = run_command(pos3d_cmd, "3D Position Extractor")
        processes.append((pos3d_proc, "3D Position Extractor"))
        
        # Step 7: Start YOLO to Nav2 bridge
        print("\n🌉 Step 7: Starting YOLO to Nav2 bridge...")
        bridge_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/yolo_3d_to_nav2_bridge.py'
        ]
        bridge_proc = run_command(bridge_cmd, "YOLO to Nav2 Bridge")
        processes.append((bridge_proc, "YOLO to Nav2 Bridge"))
        
        print("\n" + "=" * 60)
        print("🤖 AUTONOMOUS BALL FOLLOWING ACTIVE")
        print("=" * 60)
        print("\n🎾 Place a golf ball in front of the robot in Gazebo")
        print("📏 Optimal detection distance: 1-3 meters")
        print("⏳ The robot will automatically approach when ball is detected")
        print("\n📊 Monitoring system status...")
        
        # Monitor YOLO detections
        print("\n👁️ Step 8: Monitoring YOLO detections...")
        monitor_yolo_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 10 ros2 topic echo /yolo/ball_position --once'
        ]
        subprocess.run(monitor_yolo_cmd)
        
        # Monitor 3D positions
        print("\n📍 Step 9: Monitoring 3D positions...")
        monitor_3d_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 10 ros2 topic echo /yolo/ball_position_3d --once'
        ]
        subprocess.run(monitor_3d_cmd)
        
        # Let the system run for a while
        print("\n⏱️ Running autonomous ball following for 30 seconds...")
        print("Watch the robot in Gazebo GUI - it should approach any detected balls")
        time.sleep(30)
        
        # Monitor robot movement
        print("\n📊 Step 10: Checking robot movement...")
        monitor_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 5 ros2 topic echo /jetbot_base_controller/cmd_vel'
        ]
        subprocess.run(monitor_cmd)
        
        # Check final robot position
        print("\n📍 Step 11: Checking robot position...")
        odom_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 2 ros2 topic echo /odom --once'
        ]
        subprocess.run(odom_cmd)
        
        print("\n" + "=" * 80)
        print("✅ SLICE 4 VISION + NAV2 INTEGRATION TEST COMPLETE!")
        print("=" * 80)
        print("\n📊 Expected Results:")
        print("✓ YOLO detector should find golf balls (as 'frisbee' class)")
        print("✓ 3D positions should be extracted from depth data")
        print("✓ Nav2 should receive approach goals from vision bridge")
        print("✓ Robot should autonomously approach detected balls")
        print("✓ Robot should stop within 15cm of the ball")
        print("\n🎯 Vision Pipeline:")
        print("✓ Camera → YOLO Detector → 3D Position → Nav2 Bridge → Navigation")
        print("✓ Topics: /d415/color/image_raw → /yolo/ball_position → /yolo/ball_position_3d")
        print("\n🔍 Troubleshooting:")
        print("- No detection: Check ball placement (1-3m in front)")
        print("- No movement: Verify Nav2 action server is ready")
        print("- Wrong direction: Check transform from camera to base_link")
        print("\n⏭️ Next Steps:")
        print("- If successful: Create unified launch file")
        print("- Tune approach distance and navigation parameters")
        print("- Add multiple ball handling logic")
        
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
