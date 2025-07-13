#!/usr/bin/env python3
"""
Slice 1.5: Nav2 with Map Frame Test
Goal: Add blank map publisher and map->odom transform to fix frame issues
UAT: Robot moves forward 1 meter when given a simple goal (with proper frames)
Version: 1.0.0
Based on: test_nav2_slice1_basic_connectivity.py
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
    print("🎯 Slice 1.5: Nav2 with Map Frame Test")
    print("=" * 80)
    print("\n📋 Test Objective:")
    print("  - Launch simulation with GUI")
    print("  - Start blank map publisher")
    print("  - Add map->odom transform")
    print("  - Start Nav2 navigation stack")
    print("  - Send a simple goal 1 meter forward")
    print("  - Verify robot moves to the goal")
    print("\n✅ Success Criteria:")
    print("  - No map frame errors")
    print("  - Robot moves forward approximately 1 meter")
    print("  - Nav2 reports goal success")
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
        
        # Step 4: Launch Nav2 stack (without remapping)
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
            print("⚠️  Nav2 action server not detected yet...")
        
        # Step 5: Start cmd_vel relay
        print("\n🔗 Step 5: Starting cmd_vel relay (Nav2 -> Robot)...")
        relay_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/cmd_vel_relay.py'
        ]
        relay_proc = run_command(relay_cmd, "CMD_VEL Relay")
        processes.append((relay_proc, "CMD_VEL Relay"))
        
        # Step 6: Send a simple navigation goal
        print("\n🎯 Step 6: Sending navigation goal (1 meter forward)...")
        print("📍 Goal: Move robot from (0,0) to (1,0)")
        
        # Create and send navigation goal
        nav_goal_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose '
            '"{pose: {header: {frame_id: \\"map\\"}, pose: {position: {x: 1.0, y: 0.0, z: 0.0}, '
            'orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}}}}"'
        ]
        subprocess.run(nav_goal_cmd)
        
        print("\n⏳ Waiting for robot to reach goal...")
        time.sleep(10)
        
        # Monitor robot movement on the correct topic
        print("\n📊 Step 7: Monitoring robot movement...")
        print("Checking /jetbot_base_controller/cmd_vel for movement commands...")
        
        monitor_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 10 ros2 topic echo /jetbot_base_controller/cmd_vel'
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
        print("✅ SLICE 1.5 TEST COMPLETE!")
        print("=" * 80)
        print("\n📊 Expected Results:")
        print("✓ Map frame should be available (no transform errors)")
        print("✓ Nav2 action server should be available")
        print("✓ Robot should have moved approximately 1 meter forward")
        print("✓ /jetbot_base_controller/cmd_vel should show movement commands")
        print("✓ Final odometry should show position near (1.0, 0.0)")
        print("\n🔍 Key Fixes Applied:")
        print("✓ Blank map publisher provides /map topic")
        print("✓ Static transform provides map->odom connection")
        print("✓ CMD_VEL relay bridges Nav2 output to robot controller")
        print("\n⏭️ Next Steps:")
        print("- If successful: Proceed to integrate vision pipeline")
        print("- If robot doesn't move: Check Nav2 logs for planning issues")
        
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
