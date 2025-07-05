#!/bin/bash
# Test script for direct ball follower with telemetry

echo "=== Direct Ball Follower Test ==="
echo "This will test basic ball following with real-time telemetry"
echo ""

# Make script executable
chmod +x ros2_scripts/direct_ball_follower_with_telemetry.py

# Copy to WSL
echo "Copying script to WSL..."
wsl -d Ubuntu-22.04 -- bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/direct_ball_follower_with_telemetry.py ~/ros2_ws/src/chasebot_description/ros2_scripts/"

echo ""
echo "Starting simulation with ball at 3m..."
echo ""

# Terminal 1: Launch simulation with ball
echo "Terminal 1: Launching simulation with ball..."
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.17.112.1:0.0 && ros2 launch chasebot_description jetbot_golf_ball_test.launch.py" &

# Wait for simulation to start
echo "Waiting for simulation to start..."
sleep 15

# Terminal 2: Run direct follower
echo ""
echo "Terminal 2: Starting direct ball follower with telemetry..."
echo "Watch the telemetry display for real-time status!"
echo ""
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/direct_ball_follower_with_telemetry.py"
