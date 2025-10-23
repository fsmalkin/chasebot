#!/usr/bin/env python3
"""
UAT Test Script for Sports Ball Detection
Tests YOLO detection with visual feedback
"""

import subprocess
import time
import sys

def run_test():
    print("="*60)
    print("SPORTS BALL DETECTION UAT")
    print("="*60)
    print("\nThis test will:")
    print("1. Launch the robot simulation with camera")
    print("2. Start the sports ball detector")
    print("3. Show a window with the camera view and detections")
    print("\nYou should see:")
    print("- Green boxes around detected sports balls")
    print("- Confidence scores above 0.5")
    print("- Red dots at ball centers")
    print("\nControls in detection window:")
    print("- Press '+' to increase confidence threshold")
    print("- Press '-' to decrease confidence threshold")
    print("- Press 'q' to quit")
    print("="*60)
    
    print("\nPress Enter to start the test...")
    input()
    
    # Kill any existing processes
    print("\nCleaning up existing processes...")
    subprocess.run([
        'powershell', '-Command',
        'wsl -d Ubuntu-22.04 -- bash -c "pkill -f gazebo; pkill -f ros2; pkill -f yolo; sleep 2"'
    ])
    
    # Step 1: Launch simulation
    print("\nStep 1: Launching simulation with camera...")
    sim_cmd = [
        'powershell', '-Command',
        'wsl -d Ubuntu-22.04 -- bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.25.128.1:0.0 && ros2 launch chasebot_sim jetbot_gz_control_camera_test_v3.launch.py"'
    ]
    sim_process = subprocess.Popen(sim_cmd)
    
    print("Waiting for simulation to start (15 seconds)...")
    time.sleep(15)
    
    # Step 2: Start sports ball detector
    print("\nStep 2: Starting sports ball detector...")
    print("A window should appear showing the camera view")
    print("Look for green boxes around any detected sports balls")
    
    detector_cmd = [
        'powershell', '-Command',
        'wsl -d Ubuntu-22.04 -- bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.25.128.1:0.0 && python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_detector_sports_ball.py"'
    ]
    
    detector_process = subprocess.Popen(detector_cmd)
    
    print("\n" + "="*60)
    print("UAT TEST RUNNING")
    print("="*60)
    print("\nThe detection window should now be visible.")
    print("If you see sports balls detected with green boxes, the test passes!")
    print("If no detections appear, the simulated balls may not register as 'sports balls'")
    print("\nPress Ctrl+C to stop the test")
    
    try:
        # Wait for user to stop
        detector_process.wait()
    except KeyboardInterrupt:
        print("\n\nStopping test...")
        detector_process.terminate()
        sim_process.terminate()
        time.sleep(2)
        
        # Final cleanup
        subprocess.run([
            'powershell', '-Command',
            'wsl -d Ubuntu-22.04 -- bash -c "pkill -f gazebo; pkill -f ros2; pkill -f yolo"'
        ])
        
        print("\nTest completed!")

if __name__ == "__main__":
    try:
        run_test()
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
