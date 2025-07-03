@echo off
echo ========================================
echo Syncing Slice 4.5 files to WSL2 ROS2 workspace...
echo ========================================

REM Set the source directory (current directory)
set SOURCE_DIR=%CD%

REM Copy the fixed bridge script
echo Copying fixed bridge script...
wsl -d Ubuntu-22.04 cp "/mnt/c%SOURCE_DIR:\=/%/ros2_scripts/ros2_yolo_to_nav_goal_fixed.py" ~/ros2_ws/src/chasebot_description/ros2_scripts/
if %errorlevel% neq 0 (
    echo ERROR: Failed to copy ros2_yolo_to_nav_goal_fixed.py
    pause
    exit /b 1
)

REM Copy the fixed launch file
echo Copying fixed launch file...
wsl -d Ubuntu-22.04 cp "/mnt/c%SOURCE_DIR:\=/%/ros2_config/launch/jetbot_with_nav2_fixed.launch.py" ~/ros2_ws/src/chasebot_description/ros2_config/launch/
if %errorlevel% neq 0 (
    echo ERROR: Failed to copy jetbot_with_nav2_fixed.launch.py
    pause
    exit /b 1
)

REM Copy the updated CMakeLists.txt
echo Copying updated CMakeLists.txt...
wsl -d Ubuntu-22.04 cp "/mnt/c%SOURCE_DIR:\=/%/CMakeLists.txt" ~/ros2_ws/src/chasebot_description/
if %errorlevel% neq 0 (
    echo ERROR: Failed to copy CMakeLists.txt
    pause
    exit /b 1
)

REM Make Python scripts executable
echo Setting executable permissions...
wsl -d Ubuntu-22.04 chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_to_nav_goal_fixed.py
wsl -d Ubuntu-22.04 chmod +x ~/ros2_ws/src/chasebot_description/ros2_config/launch/jetbot_with_nav2_fixed.launch.py

REM Build the workspace
echo Building ROS2 workspace...
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select chasebot_description"
if %errorlevel% neq 0 (
    echo ERROR: Failed to build workspace
    pause
    exit /b 1
)

echo ========================================
echo Slice 4.5 sync complete!
echo ========================================
echo.
echo Key files updated:
echo - Fixed bridge script: ros2_yolo_to_nav_goal_fixed.py
echo - Fixed launch file: jetbot_with_nav2_fixed.launch.py
echo - Updated CMakeLists.txt
echo.
echo To test the fixed autonomous system:
echo 1. Make sure VcXsrv is running
echo 2. Run: wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0 && ros2 launch chasebot_description jetbot_with_nav2_fixed.launch.py"
echo.
echo Expected behavior:
echo - Bridge script subscribes to correct topics
echo - "Ball detected" messages appear
echo - Robot autonomously navigates to ball
echo - Robot stops ~0.3m from ball
echo.
pause
