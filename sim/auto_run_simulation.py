#!/usr/bin/env python3
"""
ChaseBot Auto-Connect Simulation Script
Automatically starts Webots and connects the external controller
"""

import subprocess
import os
import time
import threading
import sys

def run_webots():
    """Start Webots with the world file"""
    webots_path = r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe"
    world_file = os.path.abspath("worlds/chasebot_world.wbt")
    
    print("🚀 Starting Webots...")
    print(f"World file: {world_file}")
    
    try:
        # Start Webots (this will wait for external controller connection)
        webots_process = subprocess.Popen([webots_path, world_file], 
                                        stdout=subprocess.PIPE, 
                                        stderr=subprocess.PIPE, 
                                        text=True)
        
        # Give Webots time to start and load the world
        time.sleep(3)
        
        return webots_process
    except Exception as e:
        print(f"❌ Failed to start Webots: {e}")
        return None

def run_controller():
    """Start the JetBot controller with proper environment"""
    print("🤖 Starting JetBot controller...")
    
    # Set up Webots environment
    env = os.environ.copy()
    env['WEBOTS_HOME'] = r"C:\Program Files\Webots"
    env['PYTHONPATH'] = r"C:\Program Files\Webots\lib\controller\python"
    
    controller_script = os.path.abspath("controllers/jetbot_controller/jetbot_controller.py")
    
    try:
        # Start controller
        controller_process = subprocess.Popen([sys.executable, controller_script],
                                            cwd=os.path.dirname(controller_script),
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
    print("ChaseBot Auto-Connect Simulation")
    print("=" * 50)
    
    # Start Webots
    webots_process = run_webots()
    if webots_process is None:
        return
    
    # Wait a moment for Webots to fully initialize
    print("⏳ Waiting for Webots to initialize...")
    time.sleep(5)
    
    # Start controller
    controller_process = run_controller()
    if controller_process is None:
        webots_process.terminate()
        return
    
    print("✅ Both processes started!")
    print("📺 Controller output will appear below:")
    print("-" * 50)
    
    try:
        # Stream controller output in real-time
        stream_output(controller_process, "CONTROLLER")
        
        # Wait for controller to finish
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
