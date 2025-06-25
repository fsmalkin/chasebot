#!/bin/bash
# Nav2 Integration UAT Test Script

echo "=== NAV2 INTEGRATION UAT TEST ==="
echo "This will launch ChaseBot with Nav2 navigation to golf balls"
echo ""

# Kill any existing processes
echo "1. Cleaning up existing processes..."
pkill -f ros2
pkill -f gazebo
sleep 2

# Source ROS 2
echo "2. Setting up ROS 2 environment..."
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash

echo ""
echo "3. Starting test in 3 terminals:"
echo ""
echo "TERMINAL 1 - Robot with camera and ball detection:"
echo "---------------------------------------------------"
echo "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 launch chasebot_description jetbot_autonomous_ball_following.launch.py"
echo ""
echo "TERMINAL 2 - Vision to LaserScan + Nav2:"
echo "----------------------------------------"
echo "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 run chasebot_description ros2_vision_to_laserscan_hsv.py & sleep 5 && ros2 launch nav2_bringup navigation_launch.py params_file:=~/ros2_ws/src/chasebot_description/config/nav2_params_simple.yaml use_sim_time:=true"
echo ""
echo "TERMINAL 3 - Ball to Nav2 Goal Converter:"
echo "-----------------------------------------"
echo "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && sleep 10 && ros2 run chasebot_description ros2_ball_to_nav_goal.py"
echo ""
echo "Expected Results:"
echo "1. Robot spawns in Gazebo with green golf ball"
echo "2. Vision system detects ball and converts to laser scan"
echo "3. Nav2 stack launches successfully"
echo "4. Ball detection triggers Nav2 navigation goal"
echo "5. Robot navigates to ball using path planning (not direct control)"
echo ""
echo "Visual Indicators of Success:"
echo "- 'Nav2 action server is ready!' message"
echo "- 'Goal accepted by Nav2' message"
echo "- Robot moves smoothly to ball with planning"
echo "- No transform or costmap errors"
