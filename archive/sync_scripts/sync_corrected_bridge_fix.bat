@echo off
echo ===================================================
echo ChaseBot: Deploying Corrected Bridge Fix
echo ===================================================
echo.
echo This script deploys the CORRECTED bridge that uses direct
echo calculation for accurate ball approach (15cm instead of 30cm).
echo.

REM Kill existing processes first
echo Step 1: Terminating existing ROS processes...
wsl -d Ubuntu-22.04 bash -c "ps aux | grep -E '(gazebo|gzserver|gzclient|ros2|nav2)' | grep -v grep | awk '{print $2}' | xargs -r kill -9 2>/dev/null"
timeout /t 2

echo.
echo Step 2: Copying corrected bridge to WSL2...
REM Copy the corrected bridge
wsl -d Ubuntu-22.04 cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/ros2_yolo_to_nav_goal_corrected.py ~/ros2_ws/src/chasebot_description/ros2_scripts/

echo.
echo Step 3: Copying updated launch file...
REM Copy the updated launch file
wsl -d Ubuntu-22.04 cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/launch/jetbot_nav2_integration_complete.launch.py ~/ros2_ws/src/chasebot_description/ros2_config/launch/

echo.
echo Step 4: Fixing line endings...
wsl -d Ubuntu-22.04 sed -i 's/\r$//' ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_to_nav_goal_corrected.py
wsl -d Ubuntu-22.04 sed -i 's/\r$//' ~/ros2_ws/src/chasebot_description/ros2_config/launch/jetbot_nav2_integration_complete.launch.py

echo.
echo Step 5: Making scripts executable...
wsl -d Ubuntu-22.04 chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_to_nav_goal_corrected.py

echo.
echo Step 6: Rebuilding workspace...
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select chasebot_description"

echo.
echo ===================================================
echo DEPLOYMENT COMPLETE!
echo ===================================================
echo.
echo The corrected bridge is now deployed with:
echo - Direct position calculation (no complex transforms)
echo - 15cm approach distance (was 30cm)
echo - Simple, accurate goal calculation
echo.
echo To test:
echo 1. Launch: wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.17.112.1:0.0 && ros2 launch chasebot_description jetbot_nav2_integration_complete.launch.py"
echo 2. Watch for: "Started CORRECTED YOLO to Nav2 bridge"
echo 3. Robot should now approach balls within 15cm!
echo.
pause
