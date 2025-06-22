#!/usr/bin/env python3
"""
Simple Movement Test Launcher
Run movement test in minimal world
"""

import subprocess
import os
import time
import sys

def run_webots_with_world(world_file):
    """Start Webots with the specified world file"""
    webots_path = r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe"
    world_path = os.path.abspath(world_file)
    
    print("🚀 Starting Webots...")
    print(f"World file: {world_path}")
    
    try:
        webots_process = subprocess.Popen([webots_path, world_path], 
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
    print("ChaseBot Simple Movement Test")
    print("=" * 60)
    print("Testing basic movement in minimal world")
    print("=" * 60)
    
    # Start Webots with simple world
    webots_process = run_webots_with_world("worlds/simple_test_world.wbt")
    if webots_process is None:
        return
    
    # Wait for Webots to initialize
    print("⏳ Waiting for Webots to initialize...")
    time.sleep(5)
    
    # Start movement test controller
    controller_process = run_controller("test_movement_with_position.py")
    if controller_process is None:
        webots_process.terminate()
        return
    
    print("✅ Both processes started!")
    print("📺 Controller output with position tracking:")
    print("-" * 60)
    
    try:
        # Stream controller output in real-time
        stream_output(controller_process, "MOVEMENT_TEST")
        controller_process.wait()
        
    except KeyboardInterrupt:
        print("\n🛑 Stopping simulation...")
        
    finally:
        # Clean up processes
        if controller_process and controller_process.poll() is None:
            controller_process.terminate()
        if webots_process and webots_process.poll() is None:
            webots_process.terminate()
        
        print("🏁 Simple movement test stopped.")

if __name__ == "__main__":
    main()
