#!/usr/bin/env python3
"""
Test our existing working YOLO detector to confirm it still works
"""
import subprocess
import time
import os
import sys

def run_command(cmd):
    """Run command and return output"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip()

def cleanup_processes():
    """Clean up any existing processes"""
    print("Cleaning up existing processes...")
    commands = [
        'powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'pkill -9 -f gazebo\'"',
        'powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'pkill -9 -f ign\'"',
        'powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'pkill -9 -f ros2\'"',
        'powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'pkill -9 -f yolo\'"',
    ]
    for cmd in commands:
        subprocess.run(cmd, shell=True, capture_output=True)
    time.sleep(2)

def main():
    print("="*60)
    print("Testing Existing YOLO Detector")
    print("="*60)
    print("Goal: Verify our working YOLO detector still functions")
    print("="*60)
    
    cleanup_processes()
    
    # Detect display
    print("\nDetecting display IP...")
    display_ip = run_command('ipconfig | findstr /i "ipv4" | findstr /i "192.168" | head -1')
    if display_ip:
        display_ip = display_ip.split(':')[-1].strip()
        print(f"Detected display IP: {display_ip}")
        os.environ['DISPLAY'] = f"{display_ip}:0.0"
    else:
        os.environ['DISPLAY'] = "172.25.128.1:0.0"
    
    # Launch simulation
    print("\nStep 1: Launching simulation...")
    sim_cmd = f'''powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY={os.environ["DISPLAY"]} && ros2 launch chasebot_sim jetbot_gz_control_camera_test_v5.launch.py'"'''
    
    sim_proc = subprocess.Popen(sim_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    print("Waiting for simulation...")
    time.sleep(15)
    
    # Verify camera topics
    print("\nStep 2: Verifying camera topics...")
    camera_topics = run_command('powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && ros2 topic list | grep d415/color\'"')
    print("Camera topics:")
    print(camera_topics)
    
    # Launch our YOLO detector
    print("\nStep 3: Launching our YOLO detector (headless version)...")
    yolo_cmd = '''powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && python3 $(if [ -f ~/ros2_ws/src/chasecar/ros2_scripts/ros2_yolo_detector_headless.py ]; then echo ~/ros2_ws/src/chasecar/ros2_scripts/ros2_yolo_detector_headless.py; else echo ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_detector_headless.py; fi)'"'''
    
    yolo_proc = subprocess.Popen(yolo_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    print("Waiting for YOLO detector to initialize...")
    time.sleep(10)
    
    # Check YOLO topics
    print("\nStep 4: Checking YOLO topics...")
    yolo_topics = run_command('powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && ros2 topic list | grep yolo\'"')
    print("YOLO topics:")
    print(yolo_topics if yolo_topics else "No YOLO topics found")
    
    # Monitor detections
    print("\nStep 5: Monitoring YOLO detections for 20 seconds...")
    print("(Golf ball should be visible in camera view)")
    
    # Check for detections on the correct topic
    detection_cmd = '''powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'source /opt/ros/humble/setup.bash && timeout 10 ros2 topic echo /yolo/ball_position --once 2>&1'"'''
    
    detection_result = run_command(detection_cmd)
    print("\nBall position result:")
    print(detection_result[:500] + "..." if len(detection_result) > 500 else detection_result)
    
    # Also check confidence
    confidence_cmd = '''powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'source /opt/ros/humble/setup.bash && timeout 5 ros2 topic echo /yolo/confidence --once 2>&1'"'''
    
    confidence_result = run_command(confidence_cmd)
    print("\nConfidence result:")
    print(confidence_result[:200] + "..." if len(confidence_result) > 200 else confidence_result)
    
    # Check 3D position topics
    print("\nStep 6: Checking 3D position topics...")
    pos3d_topics = run_command('powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && ros2 topic list | grep position\'"')
    print("3D position topics:")
    print(pos3d_topics if pos3d_topics else "No 3D position topics found")
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    if camera_topics:
        print("✓ Camera topics are publishing")
    else:
        print("✗ Camera topics not found")
        
    if yolo_topics:
        print("✓ YOLO detector created topics")
    else:
        print("✗ YOLO topics not found")
        
    if "x:" in detection_result and "y:" in detection_result:
        print("✓ YOLO is detecting objects (ball position received)")
    elif "WARNING" in detection_result:
        print("✗ No YOLO detections received (no balls in view?)")
    else:
        print("✗ YOLO detection status unclear")
    
    print("\nNext steps:")
    print("1. If detection working, proceed with Nav2 bridge")
    print("2. If not detecting, check camera view and ball position")
    
    # Cleanup
    print("\nCleaning up...")
    if sim_proc:
        sim_proc.terminate()
    if yolo_proc:
        yolo_proc.terminate()
    time.sleep(2)
    cleanup_processes()
    
    print("\nDone!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        cleanup_processes()
        sys.exit(0)
