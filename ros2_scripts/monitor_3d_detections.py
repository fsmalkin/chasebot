#!/usr/bin/env python3
"""
Monitor 3D detections from vision_inference node
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
        'powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'pkill -9 -f vision_inference\'"',
    ]
    for cmd in commands:
        subprocess.run(cmd, shell=True, capture_output=True)
    time.sleep(2)

def main():
    print("="*60)
    print("3D Detection Monitor")
    print("="*60)
    print("Goal: See what detections we get from vision_inference")
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
    
    # Launch vision inference
    print("\nStep 2: Launching vision_inference...")
    vi_cmd = f'''powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 launch ros2_vision_inference detect_seg_depth.launch.xml mono3d_flag:=true mono3d_ckpt_file:=~/ros2_ws/models/mono3d_yolox_576_768.onnx seg_flag:=false monodepth_flag:=false camera_topic:=/d415/color/image_raw camera_param:=/d415/color/camera_info'"'''
    
    vi_proc = subprocess.Popen(vi_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    print("Waiting for vision_inference to initialize...")
    time.sleep(15)
    
    # Check topic type
    print("\nStep 3: Checking detection topic type...")
    topic_type = run_command('powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && ros2 topic type /mono3d/bbox 2>&1\'"')
    print(f"Topic type: {topic_type}")
    
    # Monitor detections
    print("\nStep 4: Monitoring detections for 30 seconds...")
    print("(Golf ball should be visible in camera view)\n")
    
    # Start echo in background
    echo_cmd = '''powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'source /opt/ros/humble/setup.bash && timeout 30 ros2 topic echo /mono3d/bbox 2>&1'"'''
    
    echo_result = run_command(echo_cmd)
    print("Detection output:")
    print(echo_result if echo_result else "No detections received")
    
    # Check topic frequency
    print("\nStep 5: Checking detection frequency...")
    hz_cmd = '''powershell -Command "wsl -d Ubuntu-22.04 -- bash -c 'source /opt/ros/humble/setup.bash && timeout 5 ros2 topic hz /mono3d/bbox 2>&1 | tail -5'"'''
    hz_result = run_command(hz_cmd)
    print(hz_result)
    
    # Also check camera feed
    print("\nStep 6: Verifying camera is working...")
    cam_hz = run_command('powershell -Command "wsl -d Ubuntu-22.04 -- bash -c \'source /opt/ros/humble/setup.bash && timeout 3 ros2 topic hz /d415/color/image_raw 2>&1 | grep \"average rate\" | tail -1\'"')
    print(f"Camera rate: {cam_hz if cam_hz else 'No camera data'}")
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    if topic_type and "vision_msgs" in topic_type:
        print("✓ Detection topic has correct message type")
    else:
        print("✗ Detection topic type not as expected")
        
    if echo_result and "detections:" in echo_result.lower():
        print("✓ Receiving detection messages")
    else:
        print("✗ No detection messages received")
        
    print("\nNote: If no detections, ensure:")
    print("  1. Golf ball is visible in camera view")
    print("  2. Ball is within detection range (3-5m)")
    print("  3. Lighting is adequate")
    
    # Cleanup
    print("\nCleaning up...")
    if sim_proc:
        sim_proc.terminate()
    if vi_proc:
        vi_proc.terminate()
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
