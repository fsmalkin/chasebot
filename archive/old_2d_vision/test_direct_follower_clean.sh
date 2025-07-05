#!/bin/bash
# Clean test script for direct ball follower with telemetry

echo "=== Direct Ball Follower Test (Clean) ==="
echo "This will test direct ball following with telemetry"
echo ""

# Kill any existing ROS processes
echo "Cleaning up existing processes..."
wsl -d Ubuntu-22.04 bash -c "ps aux | grep -E '(ros2|gazebo|rviz|yolo|navigation)' | grep -v grep | awk '{print \$2}' | xargs -r kill -9 2>/dev/null"
sleep 2

# Copy the direct follower script
echo "Copying direct follower script to WSL..."
wsl -d Ubuntu-22.04 -- bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/direct_ball_follower_with_telemetry.py ~/ros2_ws/src/chasebot_description/ros2_scripts/"
wsl -d Ubuntu-22.04 -- bash -c "chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/direct_ball_follower_with_telemetry.py"

# Copy YOLO model if needed
echo "Ensuring YOLO model is in place..."
wsl -d Ubuntu-22.04 -- bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/yolov8m.pt ~/ros2_ws/"

echo ""
echo "Starting simulation with single ball..."
echo ""

# Terminal 1: Launch simple simulation with ball
echo "Launching simulation (this will run in background)..."
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.17.112.1:0.0 && ros2 launch chasebot_description jetbot_golf_ball_test.launch.py" &
SIM_PID=$!

# Wait for simulation to fully start
echo "Waiting for simulation to initialize..."
sleep 15

# Terminal 2: Run ONLY the direct follower
echo ""
echo "Starting direct ball follower with integrated telemetry..."
echo "Watch for the telemetry display!"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Run the direct follower in foreground so we can see the telemetry
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/direct_ball_follower_with_telemetry.py"

# Cleanup on exit
echo ""
echo "Cleaning up..."
kill $SIM_PID 2>/dev/null
wsl -d Ubuntu-22.04 bash -c "ps aux | grep -E '(ros2|gazebo|rviz)' | grep -v grep | awk '{print \$2}' | xargs -r kill -9 2>/dev/null"
echo "Test complete!"
