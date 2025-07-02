#!/usr/bin/env python3
"""
Automated test runner for single ball YOLO-to-Nav2 testing.
Ensures proper sequencing and clear visual indicators.
"""

import subprocess
import time
import sys
import os

class SingleBallTestRunner:
    def __init__(self):
        self.processes = []
        
    def run_command(self, cmd, name, wait_time=0):
        """Run a command and track the process."""
        print(f"\n🚀 {name}...")
        print(f"   Command: {cmd[:100]}...")
        
        process = subprocess.Popen(cmd, shell=True)
        self.processes.append((process, name))
        
        if wait_time > 0:
            print(f"   Waiting {wait_time} seconds for {name} to initialize...")
            time.sleep(wait_time)
            
        return process
        
    def check_vcxsrv(self):
        """Check if VcXsrv is running."""
        print("\n🔍 Checking VcXsrv...")
        result = subprocess.run("tasklist | findstr -i vcxsrv", shell=True, capture_output=True, text=True)
        
        if "vcxsrv" in result.stdout.lower():
            print("   ✅ VcXsrv is running")
            return True
        else:
            print("   ❌ VcXsrv is NOT running!")
            print("   Please start VcXsrv with 'Disable access control' checked")
            return False
            
    def kill_existing_processes(self):
        """Kill any existing ChaseBot processes."""
        print("\n🧹 Cleaning existing processes...")
        subprocess.run("wsl -d Ubuntu-22.04 bash -c 'cd ~/ros2_ws/src/chasebot_description && python3 ros2_scripts/kill_chasebot_processes.py'", shell=True)
        time.sleep(2)
        
    def spawn_golf_ball(self):
        """Spawn a single golf ball at a known location."""
        print("\n⛳ SPAWNING GOLF BALL - TESTING SHOULD BEGIN NOW!")
        print("=" * 60)
        
        # Create SDF content for the golf ball
        golf_ball_sdf = '''<?xml version="1.0" ?>
<sdf version="1.6">
  <model name="golf_ball">
    <pose>2.0 0.5 0.021 0 0 0</pose>
    <link name="link">
      <inertial>
        <mass>0.045</mass>
        <inertia>
          <ixx>1.5e-05</ixx>
          <iyy>1.5e-05</iyy>
          <izz>1.5e-05</izz>
        </inertia>
      </inertial>
      <collision name="collision">
        <geometry>
          <sphere>
            <radius>0.021</radius>
          </sphere>
        </geometry>
      </collision>
      <visual name="visual">
        <geometry>
          <sphere>
            <radius>0.021</radius>
          </sphere>
        </geometry>
        <material>
          <ambient>0.9 0.9 0.9 1</ambient>
          <diffuse>0.9 0.9 0.9 1</diffuse>
        </material>
      </visual>
    </link>
  </model>
</sdf>'''
        
        # Save SDF to temp file and spawn
        spawn_cmd = f"""cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && \\
export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{{print $2}}'):0.0 && \\
echo '{golf_ball_sdf}' > /tmp/golf_ball.sdf && \\
ros2 run gazebo_ros spawn_entity.py -file /tmp/golf_ball.sdf -entity golf_ball -x 2.0 -y 0.5 -z 0.021"""
        
        self.run_command(f"wsl -d Ubuntu-22.04 bash -c \"{spawn_cmd}\"", "Golf Ball Spawn", wait_time=3)
        
        print("\n✅ Golf ball spawned at position (2.0, 0.5)")
        print("   The robot should now detect and navigate to the ball")
        
    def run_test(self):
        """Run the complete test sequence."""
        print("=" * 60)
        print("ChaseBot Single Ball Test Runner")
        print("=" * 60)
        
        # Check prerequisites
        if not self.check_vcxsrv():
            return False
            
        # Kill existing processes
        self.kill_existing_processes()
        
        # Launch sequence with proper timing
        print("\n📋 Test Sequence Starting...")
        print("   Watch for the golf ball to appear - that's when detection begins!")
        
        # 1. Launch Gazebo with empty world
        gazebo_cmd = """cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && \\
export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{{print $2}}'):0.0 && \\
ros2 launch gazebo_ros gazebo.launch.py world:=~/ros2_ws/src/chasebot_description/ros2_config/worlds/single_ball_test.world"""
        
        self.run_command(f"wsl -d Ubuntu-22.04 bash -c \"{gazebo_cmd}\"", "Gazebo (empty world)", wait_time=5)
        
        # 2. Spawn robot
        robot_cmd = """cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && \\
export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{{print $2}}'):0.0 && \\
ros2 run gazebo_ros spawn_entity.py -file ~/ros2_ws/src/chasebot_description/ros2_config/urdf/ros2_jetbot.urdf -entity jetbot -x 0 -y 0 -z 0.05"""
        
        self.run_command(f"wsl -d Ubuntu-22.04 bash -c \"{robot_cmd}\"", "JetBot Robot", wait_time=3)
        
        # 3. Launch Nav2
        nav2_cmd = """cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && \\
export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{{print $2}}'):0.0 && \\
ros2 launch nav2_bringup navigation_launch.py use_sim_time:=true"""
        
        self.run_command(f"wsl -d Ubuntu-22.04 bash -c \"{nav2_cmd}\"", "Nav2 Stack", wait_time=8)
        
        # 4. Start YOLO detection
        yolo_cmd = """cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && \\
export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{{print $2}}'):0.0 && \\
ros2 launch yolov8_bringup yolov8.launch.py model:=yolov8m.pt input_image_topic:=/camera/image_raw device:=cpu"""
        
        self.run_command(f"wsl -d Ubuntu-22.04 bash -c \"{yolo_cmd}\"", "YOLO Detection", wait_time=5)
        
        # 5. NOW SPAWN THE BALL - Visual indicator for tester
        self.spawn_golf_ball()
        
        # 6. Start the bridge node (with fixes)
        bridge_cmd = """cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && \\
export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{{print $2}}'):0.0 && \\
python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_to_nav_goal.py"""
        
        self.run_command(f"wsl -d Ubuntu-22.04 bash -c \"{bridge_cmd}\"", "YOLO-to-Nav2 Bridge", wait_time=2)
        
        # Summary
        print("\n" + "=" * 60)
        print("🎯 TEST SYSTEM READY!")
        print("=" * 60)
        print("\nExpected behavior:")
        print("1. Robot should detect the golf ball (check terminal for 'Ball detected' message)")
        print("2. Robot should send navigation goal (check for 'Sending navigation goal' message)")
        print("3. Robot should move toward the ball")
        print("4. Robot should stop ~0.3m from the ball")
        print("5. SUCCESS: 'Navigation succeeded! Reached the ball.' message")
        print("\n⚠️  Watch for transform errors in the YOLO-to-Nav2 Bridge output")
        print("\nPress Ctrl+C to stop the test")
        
        # Keep running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping test...")
            self.cleanup()
            
    def cleanup(self):
        """Clean up all processes."""
        print("\n🧹 Cleaning up processes...")
        for process, name in self.processes:
            if process.poll() is None:  # Still running
                print(f"   Terminating {name}...")
                process.terminate()
                time.sleep(0.5)
                if process.poll() is None:
                    process.kill()
                    
        # Final cleanup with kill script
        self.kill_existing_processes()
        print("\n✅ Test complete and cleaned up")


def main():
    runner = SingleBallTestRunner()
    try:
        runner.run_test()
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        runner.cleanup()
        sys.exit(1)


if __name__ == '__main__':
    main()
