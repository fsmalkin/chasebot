@echo off
echo === Syncing Slice 4 files to WSL2 Ubuntu-22.04 ===
echo.

REM Create necessary directories
wsl -d Ubuntu-22.04 bash -c "mkdir -p ~/ros2_ws/src/chasebot_description/ros2_config/launch"
wsl -d Ubuntu-22.04 bash -c "mkdir -p ~/ros2_ws/src/chasebot_description/ros2_config/params"
wsl -d Ubuntu-22.04 bash -c "mkdir -p ~/ros2_ws/src/chasebot_description/ros2_scripts"

REM Copy launch file
echo Copying launch file...
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/launch/jetbot_with_nav2_minimal.launch.py ~/ros2_ws/src/chasebot_description/ros2_config/launch/"

REM Copy updated CMakeLists.txt
echo Copying CMakeLists.txt...
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/CMakeLists.txt ~/ros2_ws/src/chasebot_description/"

REM Copy bridge script (already exists, but ensure it's there)
echo Copying bridge script...
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/ros2_yolo_to_nav_goal.py ~/ros2_ws/src/chasebot_description/ros2_scripts/"

REM Copy Nav2 params files (ensure they exist)
echo Copying Nav2 params...
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/params/*.yaml ~/ros2_ws/src/chasebot_description/ros2_config/params/ 2>/dev/null || true"

REM Make scripts executable
echo Making scripts executable...
wsl -d Ubuntu-22.04 bash -c "chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/*.py"
wsl -d Ubuntu-22.04 bash -c "chmod +x ~/ros2_ws/src/chasebot_description/ros2_config/launch/*.py"

REM Build the package
echo Building package...
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select chasebot_description"

echo.
echo === Sync complete! ===
echo.
echo To run the Slice 4 UAT:
echo wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0 && ros2 launch chasebot_description jetbot_with_nav2_minimal.launch.py"
echo.
pause
