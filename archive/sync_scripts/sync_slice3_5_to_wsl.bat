@echo off
echo.
echo ===== Syncing Slice 3.5 Files to WSL2 =====
echo.

REM Kill any existing processes
echo Killing existing ROS/Gazebo processes...
wsl -d Ubuntu-22.04 bash -c "pkill -f ros2; pkill -f gazebo; pkill -f gzserver; pkill -f gzclient; pkill -f yolo"
timeout /t 2 /nobreak > nul

REM Create target directories if they don't exist
echo Creating directories...
wsl -d Ubuntu-22.04 bash -c "mkdir -p ~/ros2_ws/src/chasebot_description/ros2_config/launch"
wsl -d Ubuntu-22.04 bash -c "mkdir -p ~/ros2_ws/src/chasebot_description/ros2_scripts"
wsl -d Ubuntu-22.04 bash -c "mkdir -p ~/ros2_ws/src/chasebot_description/docs"

REM Copy the new quiet YOLO detector
echo.
echo Copying quiet YOLO detector...
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/ros2_yolo_detector_quiet.py ~/ros2_ws/src/chasebot_description/ros2_scripts/"
wsl -d Ubuntu-22.04 bash -c "chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_detector_quiet.py"

REM Copy the clean launch file
echo Copying clean launch file...
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/launch/jetbot_with_yolo_clean.launch.py ~/ros2_ws/src/chasebot_description/ros2_config/launch/"
wsl -d Ubuntu-22.04 bash -c "chmod +x ~/ros2_ws/src/chasebot_description/ros2_config/launch/jetbot_with_yolo_clean.launch.py"

REM Copy updated CMakeLists.txt
echo Copying updated CMakeLists.txt...
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/CMakeLists.txt ~/ros2_ws/src/chasebot_description/"

REM Copy slice 3.5 UAT documentation
echo Copying UAT documentation...
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/docs/slice3_5_uat.md ~/ros2_ws/src/chasebot_description/docs/"

REM Also sync supporting files from previous slices
echo.
echo Syncing supporting files...
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/cleanup_before_launch.py ~/ros2_ws/src/chasebot_description/ros2_scripts/"
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/shutdown_manager.py ~/ros2_ws/src/chasebot_description/ros2_scripts/"
wsl -d Ubuntu-22.04 bash -c "chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/*.py"

REM Copy world file if needed
echo Copying world files...
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/worlds/yolo_test_world.world ~/ros2_ws/src/chasebot_description/ros2_config/worlds/ 2>/dev/null || echo 'World file already exists'"

REM Copy URDF files
echo Copying URDF files...
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/urdf/ros2_jetbot.urdf ~/ros2_ws/src/chasebot_description/ros2_config/urdf/ 2>/dev/null || echo 'URDF already exists'"

REM Ensure YOLO model is in place
echo.
echo Checking YOLO model...
wsl -d Ubuntu-22.04 bash -c "if [ ! -f ~/ros2_ws/yolov8m.pt ]; then echo 'Copying YOLO model...'; cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/yolov8m.pt ~/ros2_ws/; fi"

REM Build the workspace
echo.
echo Building ROS2 workspace...
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select chasebot_description"

echo.
echo ===== Sync Complete! =====
echo.
echo To test Slice 3.5, run:
echo wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0 && ros2 launch chasebot_description jetbot_with_yolo_clean.launch.py"
echo.
pause
