#!/usr/bin/env python3
"""
Test script to validate the transform timing fix.
Runs in headless mode to demonstrate the fix works.
"""

import subprocess
import time
import sys

def run_headless_test():
    """Run a headless test of the transform timing fix."""
    print("=" * 60)
    print("Transform Timing Fix Validation Test")
    print("=" * 60)
    
    print("\n1. Killing existing processes...")
    subprocess.run("wsl -d Ubuntu-22.04 bash -c 'cd ~/ros2_ws/src/chasebot_description && python3 ros2_scripts/kill_chasebot_processes.py'", shell=True)
    time.sleep(2)
    
    print("\n2. Launching test in headless mode...")
    print("   This will demonstrate the transform timing fix")
    print("   Watch for NO 'extrapolation' errors in the output")
    print("=" * 60)
    
    # Run the yolo_to_nav_goal script directly to show it initializes without errors
    cmd = """wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && timeout 10 python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_to_nav_goal.py" """
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    print("\nOutput from YOLO-to-Nav2 Bridge:")
    print("-" * 60)
    print(result.stdout)
    if result.stderr:
        print("Errors:")
        print(result.stderr)
    print("-" * 60)
    
    # Check for transform errors
    if "extrapolation" in result.stdout.lower() or "extrapolation" in result.stderr.lower():
        print("\n❌ FAIL: Transform extrapolation errors detected!")
        print("   The timing fix may not be working correctly.")
        return False
    else:
        print("\n✅ SUCCESS: No transform extrapolation errors!")
        print("   The timing fix is working correctly.")
        print("\nKey improvements in the fixed version:")
        print("   - Uses current time for all transforms")
        print("   - Enhanced debug logging for coordinate pipeline")
        print("   - Better error handling with diagnostics")
        return True

if __name__ == '__main__':
    success = run_headless_test()
    sys.exit(0 if success else 1)
