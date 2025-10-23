@echo off
echo Syncing Slice 4.8 Odometry Publisher Test files to WSL2...

:: Create directories if they don't exist
wsl -d Ubuntu-22.04 bash -c "mkdir -p ~/ros2_ws/src/chasebot_description/ros2_scripts"
wsl -d Ubuntu-22.04 bash -c "mkdir -p ~/ros2_ws/src/chasebot_description/ros2_config/launch"

:: Copy the odometry publisher script
echo Copying simple_odom_publisher.py...
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/simple_odom_publisher.py ~/ros2_ws/src/chasebot_description/ros2_scripts/ && chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/simple_odom_publisher.py"

:: Copy the test launch file
echo Copying test_odom_publisher.launch.py...
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/launch/test_odom_publisher.launch.py ~/ros2_ws/src/chasebot_description/ros2_config/launch/ && chmod +x ~/ros2_ws/src/chasebot_description/ros2_config/launch/test_odom_publisher.launch.py"

:: Copy the fixed debug script (already there but ensure it's up to date)
echo Copying debug_nav2_movement.py...
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/debug_nav2_movement.py ~/ros2_ws/src/chasebot_description/ros2_scripts/ && dos2unix ~/ros2_ws/src/chasebot_description/ros2_scripts/debug_nav2_movement.py && chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/debug_nav2_movement.py"

:: Update CMakeLists.txt to include the new script
echo Updating CMakeLists.txt...
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws/src/chasebot_description && if ! grep -q 'simple_odom_publisher.py' CMakeLists.txt; then sed -i '/debug_nav2_movement.py/a\    ros2_scripts/simple_odom_publisher.py' CMakeLists.txt; fi"

:: Rebuild the workspace
echo Building ROS 2 workspace...
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select chasebot_description"

echo.
echo Sync complete! You can now test the odometry publisher:
echo.
echo Launch command:
echo    wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=172.22.96.1:0.0 && ros2 launch chasebot_description test_odom_publisher.launch.py"
echo.
echo The diagnostic tool will launch automatically and show transform status!
echo.
pause
