#!/usr/bin/env python3
"""
Test script for YOLO + Depth + Nav2 integration (Headless Version)
Based on test_3d_position_extraction_v2_with_nav2.py
Modified to use headless components for WSL2 compatibility
Version: 1.0.0
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
    print("🤖 ChaseBot YOLO + Depth + Nav2 Integration Test (Headless)")
    print("=" * 80)
    print("\n📋 Features:")
    print("✓ D415 camera with RGB/Depth topics")
    print("✓ YOLO detection (headless - no display required)")
    print("✓ 3D position extraction from depth")
    print("✓ Nav2 navigation stack")
    print("✓ Autonomous ball following (15cm approach)")
    print("\n⚡ Optimized for WSL2 - No GUI required!")
    print("=" * 80)
    
    processes = []
    
    try:
        # Kill any existing processes
        print("\n🧹 Cleaning up existing processes...")
        subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'gazebo'], stderr=subprocess.DEVNULL)
        subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'ros2'], stderr=subprocess.DEVNULL)
        subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'yolo'], stderr=subprocess.DEVNULL)
        subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'nav2'], stderr=subprocess.DEVNULL)
        time.sleep(3)
        
        # Step 1: Launch simulation with D415 camera (headless mode)
        print("\n📦 Step 1: Launching Gazebo simulation (headless)...")
        sim_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 launch chasebot_sim jetbot_gz_control_camera_test_v5.launch.py headless:=true'
        ]
        sim_proc = run_command(sim_cmd, "Simulation")
        processes.append((sim_proc, "Simulation"))
        
        print("⏳ Waiting for simulation to start...")
        time.sleep(10)
        
        # Verify topics are available
        print("\n🔍 Verifying camera topics...")
        verify_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 topic list | grep d415'
        ]
        result = subprocess.run(verify_cmd, capture_output=True, text=True)
        print("Available D415 topics:")
        print(result.stdout)
        
        # Step 2: Launch YOLO detector (HEADLESS version)
        print("\n🎯 Step 2: Launching YOLO detector (headless version)...")
        yolo_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_detector_headless.py '
            '--ros-args -p use_sim_time:=true -p confidence_threshold:=0.3 '
            '-p input_topic:=/d415/color/image_raw'
        ]
        yolo_proc = run_command(yolo_cmd, "YOLO Detector (Headless)")
        processes.append((yolo_proc, "YOLO Detector"))
        
        print("⏳ Waiting for YOLO to initialize...")
        time.sleep(5)
        
        # Verify YOLO is publishing
        print("\n✅ Verifying YOLO detection output...")
        verify_yolo_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 2 ros2 topic echo /yolo/ball_position --once'
        ]
        subprocess.run(verify_yolo_cmd)
        
        # Step 3: Launch 3D position extractor
        print("\n📐 Step 3: Launching 3D position extractor...")
        extractor_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/yolo_3d_position_extractor.py '
            '--ros-args -p use_sim_time:=true -p confidence_threshold:=0.3'
        ]
        extractor_proc = run_command(extractor_cmd, "3D Position Extractor")
        processes.append((extractor_proc, "3D Position Extractor"))
        
        print("⏳ Waiting for 3D extraction to start...")
        time.sleep(5)
        
        # Step 4: Launch Nav2 stack
        print("\n🗺️ Step 4: Launching Nav2 navigation stack...")
        nav2_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 launch nav2_bringup navigation_launch.py use_sim_time:=True'
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
            print("⚠️  Nav2 action server not detected, but continuing...")
        
        # Step 5: Launch YOLO 3D to Nav2 bridge
        print("\n🌉 Step 5: Launching YOLO 3D to Nav2 bridge...")
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
        
        print("⏳ Waiting for bridge to initialize...")
        time.sleep(3)
        
        # Step 6: Monitor system
        print("\n" + "=" * 60)
        print("🎉 ALL COMPONENTS LAUNCHED!")
        print("=" * 60)
        print("\n📊 Expected Behavior:")
        print("  1. YOLO detects ball (as 'frisbee' class 29)")
        print("  2. 3D extractor calculates [x,y,z] position using depth")
        print("  3. Bridge converts to Nav2 goal 15cm before ball")
        print("  4. Robot autonomously navigates to ball")
        print("  5. Robot stops 15cm from ball")
        print("\n🔍 Monitoring Topics:")
        print("  - /yolo/ball_position (2D normalized coordinates)")
        print("  - /yolo/confidence (detection confidence)")
        print("  - /yolo/ball_position_3d (3D world coordinates)")
        print("  - /navigate_to_pose/_action/status (Nav2 status)")
        
        print("\n⏱️ Running for 60 seconds... Press Ctrl+C to stop early")
        
        # Monitor multiple topics in sequence
        print("\n📡 Monitoring 3D positions:")
        echo_3d_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 20 ros2 topic echo /yolo/ball_position_3d'
        ]
        subprocess.run(echo_3d_cmd)
        
        print("\n📡 Monitoring Nav2 action status:")
        echo_nav_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 20 ros2 action list -t'
        ]
        subprocess.run(echo_nav_cmd)
        
        print("\n📡 Checking robot velocity commands:")
        echo_vel_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 20 ros2 topic echo /cmd_vel'
        ]
        subprocess.run(echo_vel_cmd)
        
        print("\n" + "=" * 60)
        print("✅ TEST COMPLETE!")
        print("=" * 60)
        print("\n📝 Summary:")
        print("  - All components launched in headless mode")
        print("  - No display required - perfect for WSL2")
        print("  - Monitor Gazebo GUI separately if needed")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
    finally:
        print("\n\n🧹 Cleaning up...")
        for proc, name in reversed(processes):
            terminate_process_group(proc, name)
        
        # Final cleanup
        subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'gazebo'], stderr=subprocess.DEVNULL)
        subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'ros2'], stderr=subprocess.DEVNULL)
        subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'yolo'], stderr=subprocess.DEVNULL)
        subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'nav2'], stderr=subprocess.DEVNULL)
        
        print("✅ Cleanup complete!")


if __name__ == '__main__':
    main()
