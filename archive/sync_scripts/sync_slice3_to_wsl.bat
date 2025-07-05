@echo off
echo ========================================
echo Syncing Slice 3 Files to WSL2
echo ========================================

REM Core launch file
echo Copying launch file...
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/launch/jetbot_with_yolo.launch.py ~/ros2_ws/src/chasebot_description/launch/"

REM YOLO detection script
echo Copying YOLO detection node...
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/ros2_yolo_detector.py ~/ros2_ws/src/chasebot_description/scripts/"
wsl -d Ubuntu-22.04 bash -c "chmod +x ~/ros2_ws/src/chasebot_description/scripts/ros2_yolo_detector.py"

REM World file with golf ball
echo Copying world file...
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/worlds/yolo_test_world.world ~/ros2_ws/src/chasebot_description/worlds/"

REM Supporting scripts from previous slices
echo Copying supporting scripts...
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/cleanup_before_launch.py ~/ros2_ws/src/chasebot_description/scripts/"
wsl -d Ubuntu-22.04 bash -c "chmod +x ~/ros2_ws/src/chasebot_description/scripts/cleanup_before_launch.py"
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/shutdown_manager.py ~/ros2_ws/src/chasebot_description/scripts/"
wsl -d Ubuntu-22.04 bash -c "chmod +x ~/ros2_ws/src/chasebot_description/scripts/shutdown_manager.py"

REM URDF file
echo Copying URDF file...
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/urdf/ros2_jetbot.urdf ~/ros2_ws/src/chasebot_description/urdf/"

REM YOLO model file
echo Copying YOLO model (if not already present)...
wsl -d Ubuntu-22.04 bash -c "if [ ! -f ~/ros2_ws/yolov8m.pt ]; then cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/yolov8m.pt ~/ros2_ws/; fi"

REM Build the package
echo Building workspace...
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select chasebot_description"

echo.
echo ========================================
echo Sync Complete!
echo ========================================
echo.
echo Launch with:
echo wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0 && ros2 launch chasebot_description jetbot_with_yolo.launch.py"
echo.
pause
