#!/usr/bin/env python3
"""
Test script comparing YOLO detector vs ros2_vision_inference
Launches simulation, both detection methods side-by-side
Shows why YOLO works but vision_inference doesn't detect balls
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
    print("=" * 60)
    print("YOLO vs Vision Inference Comparison Test")
    print("=" * 60)
    print("\nThis test runs both detection methods side-by-side:")
    print("1. Our working YOLO detector (detects as 'frisbee')")
    print("2. ros2_vision_inference package (currently not detecting)")
    print("\nCamera topics:")
    print("- RGB: /d415/color/image_raw")
    print("- Depth: /d415/depth/image_raw")
    print("=" * 60)
    
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
        subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'yolo'], stderr=subprocess.DEVNULL)
        time.sleep(2)
        
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
        
        # Verify topics are available
        print("\nVerifying camera topics...")
        verify_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 topic list | grep d415'
        ]
        result = subprocess.run(verify_cmd, capture_output=True, text=True)
        print("Available D415 topics:")
        print(result.stdout)
        
        # Step 2: Launch YOLO detector (frisbee version with correct topic)
        print("\nStep 2: Launching YOLO detector (quiet version to reduce terminal flooding)...")
        yolo_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            f'export DISPLAY={display_var} && '
            'python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_detector_frisbee_quiet.py '
            '--ros-args -p use_sim_time:=true -p confidence_threshold:=0.3 '
            '-p input_topic:=/d415/color/image_raw'  # CRITICAL: Use correct topic!
        ]
        yolo_proc = run_command(yolo_cmd, "YOLO Detector")
        processes.append((yolo_proc, "YOLO Detector"))
        
        print("Waiting for YOLO to initialize...")
        time.sleep(5)
        
        # Verify YOLO is publishing
        print("\nVerifying YOLO detection output...")
        verify_yolo_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 2 ros2 topic echo /yolo/ball_position --once'
        ]
        subprocess.run(verify_yolo_cmd)
        
        # NEW Step 3: Launch ros2_vision_inference for comparison
        print("\n" + "=" * 60)
        print("Step 3: Launching ros2_vision_inference (for comparison)")
        print("=" * 60)
        vision_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 launch ros2_vision_inference detect_seg_depth.launch.xml '
            'mono3d_flag:=true '
            'mono3d_ckpt_file:=~/ros2_ws/models/mono3d_yolox_576_768.onnx '
            'seg_flag:=false '
            'monodepth_flag:=false '
            'camera_topic:=/d415/color/image_raw '
            'camera_param:=/d415/color/camera_info'
        ]
        vision_proc = run_command(vision_cmd, "Vision Inference")
        processes.append((vision_proc, "Vision Inference"))
        
        print("Waiting for vision_inference to initialize...")
        time.sleep(10)
        
        # Verify vision_inference is running
        print("\nVerifying vision_inference output...")
        verify_vision_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 2 ros2 topic echo /mono3d/bbox --once'
        ]
        subprocess.run(verify_vision_cmd)
        
        # NEW: Parameter Introspection for vision_inference
        print("\n" + "=" * 60)
        print("VISION INFERENCE PARAMETER INTROSPECTION")
        print("=" * 60)
        
        # List all parameters
        print("\nListing all vision_inference parameters...")
        param_list_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 param list /vision_inference'
        ]
        result = subprocess.run(param_list_cmd, capture_output=True, text=True)
        params = result.stdout.strip().split('\n') if result.stdout else []
        
        if params:
            print(f"Found {len(params)} parameters:")
            # Get value for each parameter
            for param in params[:20]:  # Limit to first 20 to avoid flooding
                if param.strip():
                    get_param_cmd = [
                        'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
                        'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
                        f'ros2 param get /vision_inference {param.strip()}'
                    ]
                    value_result = subprocess.run(get_param_cmd, capture_output=True, text=True)
                    if value_result.stdout:
                        print(f"  {param.strip()}: {value_result.stdout.strip()}")
        
        # Check for specific important parameters
        print("\nChecking for key parameters...")
        key_params = ['confidence_threshold', 'score_threshold', 'nms_threshold', 
                      'detection_threshold', 'model_path', 'input_size']
        for param in key_params:
            check_cmd = [
                'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
                'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
                f'ros2 param get /vision_inference {param} 2>&1'
            ]
            result = subprocess.run(check_cmd, capture_output=True, text=True)
            if "Parameter not set" not in result.stdout:
                print(f"  {param}: {result.stdout.strip()}")
        
        # Check node info for more details
        print("\nGetting detailed node info...")
        node_info_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 node info /vision_inference'
        ]
        result = subprocess.run(node_info_cmd, capture_output=True, text=True)
        if result.stdout:
            print("Node connections:")
            lines = result.stdout.split('\n')
            for line in lines:
                if 'Subscribers:' in line or 'Publishers:' in line or '/d415' in line or 'bbox' in line:
                    print(f"  {line.strip()}")
        
        # NEW: Pipeline Analysis
        print("\n" + "=" * 60)
        print("VISION INFERENCE PIPELINE ANALYSIS")
        print("=" * 60)
        
        # Stage 1: Input verification
        print("\n1. INPUT STAGE - Camera Subscription Check")
        # Check if vision_inference is actually receiving images
        print("Checking camera subscription status...")
        sub_check_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 topic info /d415/color/image_raw | grep -A 5 "Subscription count"'
        ]
        result = subprocess.run(sub_check_cmd, capture_output=True, text=True)
        print(f"Camera topic info: {result.stdout.strip()}")
        
        # Check message frequency to vision_inference
        print("\nChecking if vision_inference is processing images...")
        log_check_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 3 ros2 topic hz /d415/color/image_raw'
        ]
        subprocess.run(log_check_cmd)
        
        # Stage 2: Check all output topics
        print("\n2. OUTPUT STAGE - All Vision Inference Topics")
        all_topics_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 node info /vision_inference | grep -A 20 "Publishers:"'
        ]
        result = subprocess.run(all_topics_cmd, capture_output=True, text=True)
        print("All published topics from vision_inference:")
        print(result.stdout)
        
        # Check other output topics that might have data
        print("\n3. INTERMEDIATE OUTPUTS - Checking all vision topics")
        vision_topics = ['/depth_image', '/seg_image', '/point_cloud']
        for topic in vision_topics:
            echo_cmd = [
                'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
                'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
                f'timeout 1 ros2 topic hz {topic} 2>&1'
            ]
            result = subprocess.run(echo_cmd, capture_output=True, text=True)
            if "average rate" in result.stdout:
                print(f"  {topic}: Publishing data")
            else:
                print(f"  {topic}: No data")
        
        # Stage 4: Try to get any log output
        print("\n4. LOG ANALYSIS - Checking for processing logs")
        print("Attempting to get vision_inference logs...")
        # This would need the node to be launched with debug logging enabled
        
        # Stage 5: Service availability check
        print("\n5. SERVICE CHECK - Available services")
        service_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 service list | grep vision'
        ]
        result = subprocess.run(service_cmd, capture_output=True, text=True)
        if result.stdout:
            print(f"Vision services: {result.stdout.strip()}")
        else:
            print("No vision-specific services found")
        
        print("\n" + "=" * 60)
        
        # Step 4: Launch 3D position extractor
        print("\nStep 3: Launching 3D position extractor...")
        extractor_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/yolo_3d_position_extractor.py '
            '--ros-args -p use_sim_time:=true -p confidence_threshold:=0.3'
        ]
        extractor_proc = run_command(extractor_cmd, "3D Position Extractor")
        processes.append((extractor_proc, "3D Position Extractor"))
        
        print("\nWaiting for 3D extraction to start...")
        time.sleep(5)
        
        # Step 4: Launch debug viewer
        print("\nStep 4: Launching debug viewer (shows RGB + Depth)...")
        viewer_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            f'export DISPLAY={display_var} && '
            'python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/d415_3d_debug_viewer.py '
            '--ros-args -p use_sim_time:=true'
        ]
        viewer_proc = run_command(viewer_cmd, "Debug Viewer")
        processes.append((viewer_proc, "Debug Viewer"))
        
        print("\nWaiting for viewer to start...")
        time.sleep(3)
        
        # Step 5: Compare YOLO vs Vision Inference outputs
        print("\n" + "=" * 60)
        print("Step 5: Comparing Detection Methods")
        print("=" * 60)
        
        # Check what topics each system is publishing
        print("\nChecking available topics from both systems...")
        topic_cmd = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'ros2 topic list | grep -E "(yolo|mono3d|bbox|detection)"'
        ]
        result = subprocess.run(topic_cmd, capture_output=True, text=True)
        print("Detection-related topics:")
        print(result.stdout)
        
        print("\n--- YOLO Output (Working) ---")
        yolo_echo = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 5 ros2 topic echo /yolo/ball_position'
        ]
        subprocess.run(yolo_echo)
        
        print("\n--- Vision Inference Output (Not detecting) ---")
        vision_echo = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 5 ros2 topic echo /mono3d/bbox'
        ]
        subprocess.run(vision_echo)
        
        print("\n--- 3D Position Output (from YOLO) ---")
        position_echo = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 5 ros2 topic echo /yolo/ball_position_3d'
        ]
        subprocess.run(position_echo)
        
        # Check camera data rates to ensure both systems get same input
        print("\n--- Camera Data Rates ---")
        camera_hz = [
            'wsl', '-d', 'Ubuntu-22.04', '--', 'bash', '-c',
            'cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && '
            'timeout 3 ros2 topic hz /d415/color/image_raw'
        ]
        subprocess.run(camera_hz)
        
        print("\n" + "=" * 60)
        print("ANALYSIS: Why YOLO Works but Vision Inference Doesn't")
        print("=" * 60)
        print("\nObservations:")
        print("1. YOLO detector:")
        print("   - Detects golf balls as 'frisbee' (class 29)")
        print("   - Confidence typically ~0.5")
        print("   - Publishes to /yolo/ball_position")
        print("\n2. ros2_vision_inference:")
        print("   - Publishes only empty MarkerArray to /mono3d/bbox")
        print("   - No Detection3DArray messages found")
        print("   - Model likely not trained on golf balls")
        print("\nPossible reasons for vision_inference failure:")
        print("1. Model not trained on golf balls/sports balls")
        print("2. Confidence threshold too high (no parameter exposed)")
        print("3. Input preprocessing mismatch")
        print("4. Model expects different image dimensions")
        print("\nRecommendations:")
        print("1. Use our working YOLO + 3D extractor pipeline")
        print("2. Find YOLO models specifically trained on golf balls")
        print("3. Train custom model if needed")
        print("4. Check ros2_vision_inference docs for supported objects")
        
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
        subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '--', 'pkill', '-f', 'yolo'], stderr=subprocess.DEVNULL)
        
        print("\nCleanup complete!")


if __name__ == '__main__':
    main()
