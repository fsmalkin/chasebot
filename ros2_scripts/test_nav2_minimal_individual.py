#!/usr/bin/env python3
"""
Nav2 Minimal Individual Component Test
Goal: Launch Nav2 components individually to isolate lifecycle_manager issues
UAT: Identify which specific Nav2 component is failing
Version: 1.0.0
Based on: test_nav2_lifecycle_debug.py
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
    print("🧩 Nav2 Individual Component Test")
    print("=" * 80)
    print("\n📋 Test Objective:")
    print("  - Launch minimal simulation")
    print("  - Start required transforms and map")
    print("  - Launch Nav2 components INDIVIDUALLY")
    print("  - Test just controller_server first")
    print("  - Manually manage lifecycle transitions")
    print("\n🔍 Debug Focus:")
    print("  - Which specific Nav2 component fails?")
    print("  - Can we manually transition nodes?")
    print("  - Is it a parameter or dependency issue?")
    print("  - Test without full Nav2 stack complexity")
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
        
        # Step 4: First check robot_description (Nav2 needs URDF)
        print("\n🔍 Step 4: Checking robot_description parameter...")
        check_robot_desc_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 param get /robot_state_publisher robot_description | head -10'
        ]
        result = subprocess.run(check_robot_desc_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Robot description found!")
        else:
            print("⚠️  Robot description missing - Nav2 needs this!")
        
        # Step 5: Launch Nav2 components INDIVIDUALLY
        print("\n🧩 Step 5: Launching Nav2 components INDIVIDUALLY...")
        
        # Step 5a: First launch just the controller_server
        print("\n🎮 Step 5a: Launching ONLY controller_server...")
        controller_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 run nav2_controller controller_server --ros-args '
            '-p use_sim_time:=True '
            '--log-level debug'
        ]
        controller_proc = run_command(controller_cmd, "Controller Server")
        processes.append((controller_proc, "Controller Server"))
        
        print("⏳ Waiting for controller_server to start...")
        time.sleep(5)
        
        # Check if controller_server started
        print("\n🔍 Checking controller_server status...")
        check_controller_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 lifecycle get /controller_server'
        ]
        result = subprocess.run(check_controller_cmd, capture_output=True, text=True)
        print(f"Controller state: {result.stdout}")
        
        # Step 5b: Manually transition controller_server to active
        print("\n🔧 Step 5b: Manually transitioning controller_server to active...")
        configure_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 lifecycle set /controller_server configure'
        ]
        subprocess.run(configure_cmd)
        time.sleep(2)
        
        activate_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 lifecycle set /controller_server activate'
        ]
        subprocess.run(activate_cmd)
        time.sleep(2)
        
        # Check final state
        result = subprocess.run(check_controller_cmd, capture_output=True, text=True)
        print(f"Controller state after activation: {result.stdout}")
        
        print("⏳ Waiting for Nav2 to initialize...")
        time.sleep(10)
        
        # Debug Step 1: Check if lifecycle_manager is running
        print("\n🔍 Debug Step 1: Checking if lifecycle_manager is running...")
        check_lifecycle_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 node list | grep lifecycle'
        ]
        result = subprocess.run(check_lifecycle_cmd, capture_output=True, text=True)
        if 'lifecycle_manager' in result.stdout:
            print("✅ lifecycle_manager is running!")
            print(f"Nodes found: {result.stdout.strip()}")
        else:
            print("❌ lifecycle_manager NOT FOUND!")
            print("All nodes:")
            all_nodes_cmd = [
                'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
                'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
                'ros2 node list'
            ]
            subprocess.run(all_nodes_cmd)
        
        # Debug Step 2: Check Nav2 node states
        print("\n🔍 Debug Step 2: Checking Nav2 node lifecycle states...")
        nav2_nodes = ['controller_server', 'planner_server', 'recoveries_server', 'bt_navigator']
        for node in nav2_nodes:
            check_state_cmd = [
                'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
                'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
                f'timeout 2 ros2 lifecycle get /{node} 2>&1'
            ]
            result = subprocess.run(check_state_cmd, capture_output=True, text=True)
            print(f"/{node}: {result.stdout.strip() if result.stdout else 'Not found'}")
        
        # Debug Step 3: Check lifecycle_manager parameters
        print("\n🔍 Debug Step 3: Checking lifecycle_manager parameters...")
        check_params_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 2 ros2 param list /lifecycle_manager 2>&1'
        ]
        result = subprocess.run(check_params_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("Lifecycle manager parameters found:")
            print(result.stdout)
        else:
            print("❌ Cannot access lifecycle_manager parameters")
            print(result.stdout + result.stderr)
        
        # Debug Step 4: Check for action servers
        print("\n🔍 Debug Step 4: Checking available action servers...")
        action_list_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 action list'
        ]
        result = subprocess.run(action_list_cmd, capture_output=True, text=True)
        print("Available actions:")
        print(result.stdout if result.stdout else "No actions found")
        
        # Debug Step 5: Check cmd_vel publisher count
        print("\n🔍 Debug Step 5: Checking /cmd_vel publishers...")
        check_pub_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 topic info /cmd_vel'
        ]
        subprocess.run(check_pub_cmd)
        
        print("\n⏳ Waiting additional time for Nav2 to fully initialize...")
        time.sleep(10)
        
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
