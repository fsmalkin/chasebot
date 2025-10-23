#!/usr/bin/env python3
"""
Test script to verify the corrected bridge is achieving 15cm approach distance
Run this after launching the system to monitor approach accuracy
"""

import subprocess
import time
import re

def run_command(cmd):
    """Run a WSL command and return output"""
    full_cmd = f'wsl -d Ubuntu-22.04 bash -c "{cmd}"'
    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
    return result.stdout

def check_bridge_type():
    """Check which bridge is running"""
    print("Checking which bridge is active...")
    nodes = run_command("source /opt/ros/humble/setup.bash && ros2 node list")
    
    # Check logs for bridge type
    print("\nLooking for bridge initialization message...")
    time.sleep(2)
    
    # The corrected bridge should log "CORRECTED YOLO to Nav Goal bridge initialized"
    return "yolo_to_nav_goal" in nodes

def monitor_approach_distance():
    """Monitor the approach distance calculations"""
    print("\nMonitoring approach calculations...")
    print("Watch for these key messages:")
    print("- 'Approach distance: 0.15m' (should be 0.15, not 0.3)")
    print("- 'Expected final distance to ball: 0.150m'")
    print("- 'Approach goal: (x, y)' coordinates")
    print("\nPress Ctrl+C to stop monitoring\n")
    
    try:
        # Echo the topic to see navigation goals
        cmd = "source /opt/ros/humble/setup.bash && source ~/ros2_ws/install/setup.bash && ros2 topic echo /navigate_to_pose/goal --once"
        while True:
            output = run_command(cmd)
            if output:
                print("Navigation Goal Sent:")
                print(output)
                print("-" * 50)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped monitoring")

def main():
    print("=" * 60)
    print("ChaseBot Corrected Bridge Verification")
    print("=" * 60)
    
    # Check if system is running
    nodes = run_command("source /opt/ros/humble/setup.bash && ros2 node list")
    if not nodes or "yolo" not in nodes.lower():
        print("ERROR: ChaseBot system doesn't appear to be running!")
        print("Please launch the system first with:")
        print('wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.17.112.1:0.0 && ros2 launch chasebot_description jetbot_nav2_integration_complete.launch.py"')
        return
    
    # Check bridge type
    if check_bridge_type():
        print("\n✓ YOLO to Nav2 bridge is running")
        print("\nIMPORTANT: Check the launch terminal for this message:")
        print('"Started CORRECTED YOLO to Nav2 bridge - Direct calculation for accurate approach!"')
        print("\nIf you see this instead:")
        print('"Started YOLO to Nav2 bridge - ChaseBot is now fully autonomous!"')
        print("Then the OLD bridge is still running!\n")
    else:
        print("\n✗ YOLO to Nav2 bridge not found!")
        return
    
    # Monitor approach distance
    monitor_approach_distance()

if __name__ == "__main__":
    main()
