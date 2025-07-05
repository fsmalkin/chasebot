#!/bin/bash
# Test direct follower with 3D visualization

echo "=== Direct Follower with 3D Visualization Test ==="
echo ""

# Kill ALL existing ROS processes
echo "Killing all ROS processes..."
wsl -d Ubuntu-22.04 bash -c "pkill -9 -f ros2; pkill -9 -f gazebo; pkill -9 -f rviz; pkill -9 -f navigation_telemetry; pkill -9 -f yolo"
sleep 3

# Copy files
echo "Copying scripts..."
wsl -d Ubuntu-22.04 -- bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/direct_follower_with_3d_viz.py ~/ros2_ws/src/chasebot_description/ros2_scripts/"
wsl -d Ubuntu-22.04 -- bash -c "chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/direct_follower_with_3d_viz.py"
wsl -d Ubuntu-22.04 -- bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/yolov8m.pt ~/ros2_ws/"

echo ""
echo "Starting basic robot spawn..."
# Just spawn robot with camera, no navigation stack
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.17.112.1:0.0 && ros2 launch chasebot_description jetbot_basic_spawn.launch.py" &
SIM_PID=$!

echo "Waiting 15 seconds for robot to spawn..."
sleep 15

# Spawn ball manually
echo ""
echo "Spawning ball at 3m in front of robot..."
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && ros2 run gazebo_ros spawn_entity.py -entity golf_ball -database golf_ball -x 3.0 -y 0.0 -z 0.05" &

sleep 3

# Check topics
echo ""
echo "Available topics:"
wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 topic list | grep -E '(camera|cmd_vel)'"

echo ""
echo "Starting Direct Follower with 3D Viz..."
echo "========================================="
echo "This will show:"
echo "1. Terminal telemetry here"
echo "2. Annotated camera view on /debug/image_with_overlay"
echo "3. 3D markers on /visualization_markers"
echo ""
echo "To view the debug image in another terminal:"
echo "ros2 run rqt_image_view rqt_image_view"
echo ""

# Run the 3D follower
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && python3 ~/ros2_ws/src/chasebot_description/ros2_scripts/direct_follower_with_3d_viz.py"

# Cleanup
echo ""
echo "Cleaning up..."
kill $SIM_PID 2>/dev/null
wsl -d Ubuntu-22.04 bash -c "pkill -9 -f ros2; pkill -9 -f gazebo"
echo "Test complete!"
