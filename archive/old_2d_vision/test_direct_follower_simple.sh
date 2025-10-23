#!/bin/bash
# Simple test for direct ball follower

echo "=== Simple Direct Ball Follower Test ==="
echo ""

# Kill existing processes
echo "Cleaning up..."
wsl -d Ubuntu-22.04 bash -c "pkill -f ros2; pkill -f gazebo; pkill -f rviz; pkill -f yolo; sleep 2"

# Copy necessary files
echo "Copying files to WSL..."
wsl -d Ubuntu-22.04 -- bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/direct_ball_follower_with_telemetry.py ~/ros2_ws/src/chasebot_description/ros2_scripts/"
wsl -d Ubuntu-22.04 -- bash -c "chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/direct_ball_follower_with_telemetry.py"
wsl -d Ubuntu-22.04 -- bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/yolov8m.pt ~/ros2_ws/"

# Launch basic simulation
echo ""
echo "Terminal 1: Launching basic simulation with ball..."
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.17.112.1:0.0 && ros2 launch chasebot_description jetbot_simple_test.launch.py" &
SIM_PID=$!

# Wait for sim
echo "Waiting 20 seconds for simulation..."
sleep 20

# Place a ball in front of robot
echo ""
echo "Terminal 2: Spawning golf ball in front of robot..."
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && ros2 run gazebo_ros spawn_entity.py -entity golf_ball -database golf_ball -x 3.0 -y 0.0 -z 0.05" &

sleep 5

# Run direct follower
echo ""
echo "Terminal 3: Starting direct ball follower..."
echo "====================================="
echo "TELEMETRY SHOULD APPEAR BELOW:"
echo "====================================="
echo ""

wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/direct_ball_follower_with_telemetry.py"

# Cleanup
echo ""
echo "Cleaning up..."
kill $SIM_PID 2>/dev/null
wsl -d Ubuntu-22.04 bash -c "pkill -f ros2; pkill -f gazebo"
echo "Test complete!"
