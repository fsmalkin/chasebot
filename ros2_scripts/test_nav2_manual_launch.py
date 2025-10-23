#!/usr/bin/env python3
"""
Manual Nav2 Component Launch Script
Launches Nav2 components individually without lifecycle_manager
Allows debugging which component is causing issues
"""

import subprocess
import time
import sys
import signal

class Nav2ManualLauncher:
    def __init__(self):
        self.processes = []
        signal.signal(signal.SIGINT, self.signal_handler)
        
    def signal_handler(self, sig, frame):
        print("\n[INFO] Shutting down all processes...")
        self.cleanup()
        sys.exit(0)
        
    def cleanup(self):
        """Kill all spawned processes"""
        for process in self.processes:
            if process.poll() is None:
                print(f"[INFO] Terminating process {process.pid}")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    
    def run_command(self, cmd, name):
        """Run a command in WSL and track the process"""
        print(f"\n[INFO] Starting {name}...")
        full_cmd = [
            "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
            f"cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && {cmd}"
        ]
        process = subprocess.Popen(full_cmd)
        self.processes.append(process)
        print(f"[INFO] {name} started with PID {process.pid}")
        return process
        
    def wait_for_input(self, prompt="Press Enter to continue..."):
        """Wait for user input"""
        input(prompt)
        
    def launch_sequence(self):
        """Launch Nav2 components in sequence"""
        print("=== Nav2 Manual Launch Sequence ===")
        print("This will launch Nav2 components one by one.")
        print("Watch for errors after each component starts.\n")
        
        # Copy params file first
        print("[INFO] Copying parameters file to WSL...")
        subprocess.run([
            "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
            "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/nav2_complete_params.yaml ~/ros2_ws/src/chasebot_description/ros2_scripts/"
        ])
        
        # Step 1: Launch controller_server only
        print("\n[STEP 1] Launching controller_server ONLY...")
        controller_cmd = (
            "ros2 run nav2_controller controller_server "
            "--ros-args -p use_sim_time:=True "
            "--params-file ~/ros2_ws/src/chasebot_description/ros2_scripts/nav2_complete_params.yaml"
        )
        self.run_command(controller_cmd, "controller_server")
        
        time.sleep(3)
        print("\n[CHECK] Controller server should be in 'unconfigured' state")
        print("If it crashes, check the terminal output above for errors.")
        self.wait_for_input("\nPress Enter to check lifecycle state...")
        
        # Check lifecycle state
        subprocess.run([
            "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
            "source /opt/ros/humble/setup.bash && ros2 lifecycle get /controller_server"
        ])
        
        self.wait_for_input("\nPress Enter to manually configure controller_server...")
        
        # Manually configure
        print("\n[ACTION] Manually configuring controller_server...")
        subprocess.run([
            "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
            "source /opt/ros/humble/setup.bash && ros2 lifecycle set /controller_server configure"
        ])
        
        time.sleep(2)
        subprocess.run([
            "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
            "source /opt/ros/humble/setup.bash && ros2 lifecycle get /controller_server"
        ])
        
        self.wait_for_input("\nPress Enter to activate controller_server...")
        
        # Manually activate
        print("\n[ACTION] Manually activating controller_server...")
        subprocess.run([
            "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
            "source /opt/ros/humble/setup.bash && ros2 lifecycle set /controller_server activate"
        ])
        
        time.sleep(2)
        subprocess.run([
            "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
            "source /opt/ros/humble/setup.bash && ros2 lifecycle get /controller_server"
        ])
        
        # Step 2: Add planner_server
        self.wait_for_input("\nPress Enter to launch planner_server...")
        
        print("\n[STEP 2] Launching planner_server...")
        planner_cmd = (
            "ros2 run nav2_planner planner_server "
            "--ros-args -p use_sim_time:=True "
            "--params-file ~/ros2_ws/src/chasebot_description/ros2_scripts/nav2_complete_params.yaml"
        )
        self.run_command(planner_cmd, "planner_server")
        
        time.sleep(3)
        self.wait_for_input("\nPress Enter to configure and activate planner_server...")
        
        # Configure and activate planner
        subprocess.run([
            "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
            "source /opt/ros/humble/setup.bash && ros2 lifecycle set /planner_server configure"
        ])
        time.sleep(2)
        subprocess.run([
            "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
            "source /opt/ros/humble/setup.bash && ros2 lifecycle set /planner_server activate"
        ])
        
        # Check final states
        print("\n[FINAL CHECK] Current lifecycle states:")
        subprocess.run([
            "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
            "source /opt/ros/humble/setup.bash && echo 'Controller:' && ros2 lifecycle get /controller_server && echo 'Planner:' && ros2 lifecycle get /planner_server"
        ])
        
        # Test navigation
        self.wait_for_input("\nPress Enter to test navigation goal...")
        
        print("\n[TEST] Sending navigation goal...")
        test_cmd = """
import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node

rclpy.init()
node = Node('test_nav_goal')
pub = node.create_publisher(PoseStamped, '/goal_pose', 10)
goal = PoseStamped()
goal.header.frame_id = 'map'
goal.header.stamp = node.get_clock().now().to_msg()
goal.pose.position.x = 1.0
goal.pose.position.y = 0.0
goal.pose.orientation.w = 1.0

# Wait for publisher to be ready
import time
time.sleep(1)
pub.publish(goal)
print('Goal published to /goal_pose')
time.sleep(1)
node.destroy_node()
rclpy.shutdown()
"""
        
        subprocess.run([
            "wsl", "-d", "Ubuntu-22.04", "--", "bash", "-c",
            f"cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && python3 -c '{test_cmd}'"
        ])
        
        print("\n[INFO] Components are running. Press Ctrl+C to shut down all processes.")
        
        # Keep running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
            
if __name__ == "__main__":
    launcher = Nav2ManualLauncher()
    try:
        launcher.launch_sequence()
    finally:
        launcher.cleanup()
