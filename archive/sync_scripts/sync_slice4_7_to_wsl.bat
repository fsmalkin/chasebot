@echo off
echo Syncing Slice 4.7 files to WSL2 ROS 2 workspace...

:: Create directories if they don't exist
wsl -d Ubuntu-22.04 bash -c "mkdir -p ~/ros2_ws/src/chasebot_description/ros2_scripts"

:: Copy the debug script
echo Copying debug_nav2_movement.py...
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/debug_nav2_movement.py ~/ros2_ws/src/chasebot_description/ros2_scripts/ && chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/debug_nav2_movement.py"

:: Update CMakeLists.txt to include the new script
echo Updating CMakeLists.txt...
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws/src/chasebot_description && if ! grep -q 'debug_nav2_movement.py' CMakeLists.txt; then sed -i '/ros2_yolo_to_nav_goal_fixed.py/a\    ros2_scripts/debug_nav2_movement.py' CMakeLists.txt; fi"

:: Rebuild the workspace
echo Building ROS 2 workspace...
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select chasebot_description"

echo.
echo Sync complete! You can now run the debugger alongside your Nav2 launch:
echo.
echo 1. First launch Nav2 integration:
echo    wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.22.96.1:0.0 && ros2 launch chasebot_description jetbot_nav2_integration.launch.py"
echo.
echo 2. In another terminal, run the debugger:
echo    wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 run chasebot_description debug_nav2_movement.py"
echo.
pause
