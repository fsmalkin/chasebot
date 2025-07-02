#!/usr/bin/env python3
"""
Shutdown Manager for ChaseBot Launch Files
Provides user interaction and automatic cleanup
"""

import rclpy
from rclpy.node import Node
import threading
import time
import subprocess
import signal
import sys
import select
import os

class ShutdownManager(Node):
    def __init__(self):
        super().__init__('shutdown_manager')
        
        # Parameters
        self.declare_parameter('timeout_minutes', 5.0)
        self.declare_parameter('slice_name', 'Test Slice')
        self.declare_parameter('uat_checklist', ['Check robot spawned', 'Check camera active'])
        
        self.timeout_minutes = self.get_parameter('timeout_minutes').value
        self.slice_name = self.get_parameter('slice_name').value
        self.uat_checklist = self.get_parameter('uat_checklist').value
        
        # Timer tracking
        self.start_time = time.time()
        self.timeout_seconds = self.timeout_minutes * 60
        self.extended = False
        
        # Display initial UAT instructions
        self.display_uat_instructions()
        
        # Start timer thread
        self.timer_thread = threading.Thread(target=self.run_timer)
        self.timer_thread.daemon = True
        self.timer_thread.start()
        
        # Start input thread
        self.input_thread = threading.Thread(target=self.handle_user_input)
        self.input_thread.daemon = True
        self.input_thread.start()

    def display_uat_instructions(self):
        """Display UAT checklist and instructions"""
        print("\n" + "="*60)
        print(f"=== {self.slice_name} UAT VERIFICATION ===")
        print("="*60)
        
        for item in self.uat_checklist:
            print(f"✓ Check: {item}")
        
        print("\n" + "-"*60)
        print("Press:")
        print("  [Enter]     - Confirm UAT success and shutdown now")
        print("  [e] + Enter - Extend timer by 5 minutes")
        print("  [q] + Enter - Quit immediately")
        print("-"*60 + "\n")

    def run_timer(self):
        """Timer countdown with display updates"""
        while True:
            elapsed = time.time() - self.start_time
            remaining = self.timeout_seconds - elapsed
            
            if remaining <= 0:
                print("\n⏰ Timer expired! Initiating shutdown...")
                self.shutdown_system()
                break
            
            # Update display every second
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            print(f"\rAuto-shutdown in: {minutes:02d}:{seconds:02d} remaining  ", end='', flush=True)
            
            time.sleep(1)

    def handle_user_input(self):
        """Handle user keyboard input"""
        try:
            while True:
                # Use select for non-blocking input with timeout
                if sys.platform == 'win32':
                    # Windows doesn't support select on stdin
                    user_input = input().strip().lower()
                else:
                    # Unix-like systems
                    rlist, _, _ = select.select([sys.stdin], [], [], 1)
                    if rlist:
                        user_input = sys.stdin.readline().strip().lower()
                    else:
                        continue
                
                if user_input == '':
                    # Enter pressed - confirm UAT success
                    print("\n✅ UAT confirmed! Shutting down gracefully...")
                    self.shutdown_system()
                    break
                elif user_input == 'e':
                    # Extend timer
                    if not self.extended:
                        self.timeout_seconds += 300  # Add 5 minutes
                        self.extended = True
                        print("\n⏳ Timer extended by 5 minutes!")
                    else:
                        print("\n❌ Timer already extended once!")
                elif user_input == 'q':
                    # Quit immediately
                    print("\n⚡ Immediate shutdown requested...")
                    self.shutdown_system()
                    break
                    
        except Exception as e:
            self.get_logger().error(f"Input handling error: {e}")

    def shutdown_system(self):
        """Clean shutdown of all ROS and Gazebo processes"""
        print("\n" + "="*60)
        print("Shutting down ChaseBot test system...")
        print("="*60)
        
        try:
            # Kill Gazebo processes
            print("Stopping Gazebo...")
            subprocess.run(['pkill', '-f', 'gazebo'], capture_output=True)
            subprocess.run(['pkill', '-f', 'gzserver'], capture_output=True)
            subprocess.run(['pkill', '-f', 'gzclient'], capture_output=True)
            
            # Kill ROS 2 processes
            print("Stopping ROS 2 nodes...")
            subprocess.run(['pkill', '-f', 'ros2'], capture_output=True)
            
            # Kill any robot state publishers
            subprocess.run(['pkill', '-f', 'robot_state_publisher'], capture_output=True)
            subprocess.run(['pkill', '-f', 'joint_state_publisher'], capture_output=True)
            
            print("✅ All processes terminated successfully!")
            print("="*60 + "\n")
            
        except Exception as e:
            print(f"❌ Error during shutdown: {e}")
        
        # Signal ROS to shutdown
        rclpy.shutdown()
        
        # Exit the process
        os._exit(0)

def main(args=None):
    rclpy.init(args=args)
    
    try:
        manager = ShutdownManager()
        rclpy.spin(manager)
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received, shutting down...")
    finally:
        rclpy.shutdown()

if __name__ == '__main__':
    main()
