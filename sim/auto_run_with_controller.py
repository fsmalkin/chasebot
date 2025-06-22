#!/usr/bin/env python3
"""
Flexible Auto-Connect Simulation Script
Run any controller with console output
Usage: python auto_run_with_controller.py [controller_script]
"""

import subprocess
import os
import time
import sys

def run_webots():
    """Start Webots with the world file"""
    webots_path = r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe"
    world_file = os.path.abspath("worlds/chasebot_world.wbt")
    
    print("🚀 Starting Webots...")
    print(f"World file: {world_file}")
    
    try:
        webots_process = subprocess.Popen([webots_path, world_file], 
                                        stdout=subprocess.PIPE, 
                                        stderr=subprocess.PIPE, 
                                        text=True)
        time.sleep(3)
        return webots_process
    except Exception as e:
        print(f"❌ Failed to start Webots: {e}")
        return None

def run_controller(controller_script):
    """Start the specified controller with proper environment"""
    print(f"🤖 Starting controller: {controller_script}")
    
    # Set up Webots environment
    env = os.environ.copy()
    env['WEBOTS_HOME'] = r"C:\Program Files\Webots"
    env['PYTHONPATH'] = r"C:\Program Files\Webots\lib\controller\python"
    
    controller_path = os.path.abspath(controller_script)
    
    try:
        controller_process = subprocess.Popen([sys.executable, controller_path],
                                            cwd=os.path.dirname(controller_path),
                                            env=env,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT,
                                            text=True,
                                            bufsize=1,
                                            universal_newlines=True)
        return controller_process
    except Exception as e:
        print(f"❌ Failed to start controller: {e}")
        return None

def stream_output(process, name):
    """Stream process output to console"""
    try:
        for line in process.stdout:
            print(f"[{name}] {line.rstrip()}")
    except:
        pass

def main():
    """Main execution function"""
    # Get controller script from command line args
    if len(sys.argv) > 1:
        controller_script = sys.argv[1]
    else:
        controller_script = "test_manual_movement.py"
    
    print("ChaseBot Flexible Auto-Connect Simulation")
    print("=" * 60)
    print(f"Controller: {controller_script}")
    print("=" * 60)
    
    # Start Webots
    webots_process = run_webots()
    if webots_process is None:
        return
    
    # Wait for Webots to initialize
    print("⏳ Waiting for Webots to initialize...")
    time.sleep(5)
    
    # Start controller
    controller_process = run_controller(controller_script)
    if controller_process is None:
        webots_process.terminate()
        return
    
    print("✅ Both processes started!")
    print("📺 Controller output will appear below:")
    print("-" * 60)
    
    try:
        # Stream controller output in real-time
        stream_output(controller_process, "CONTROLLER")
        controller_process.wait()
        
    except KeyboardInterrupt:
        print("\n🛑 Stopping simulation...")
        
    finally:
        # Clean up processes
        if controller_process and controller_process.poll() is None:
            controller_process.terminate()
        if webots_process and webots_process.poll() is None:
            webots_process.terminate()
        
        print("🏁 Simulation stopped.")

if __name__ == "__main__":
    main()
