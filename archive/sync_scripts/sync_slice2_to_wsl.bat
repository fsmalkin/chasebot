@echo off
REM Sync Slice 2 files to WSL2 Ubuntu-22.04
echo ======================================
echo Syncing Slice 2 files to WSL2...
echo ======================================

REM Copy launch file
echo Copying jetbot_with_transforms.launch.py...
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/launch/jetbot_with_transforms.launch.py ~/ros2_ws/src/chasebot_description/ros2_config/launch/"

REM Copy UAT documentation
echo Copying slice2_uat.md...
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/docs/slice2_uat.md ~/ros2_ws/src/chasebot_description/docs/"

REM Make launch file executable
echo Making launch file executable...
wsl -d Ubuntu-22.04 bash -c "chmod +x ~/ros2_ws/src/chasebot_description/ros2_config/launch/jetbot_with_transforms.launch.py"

REM Rebuild workspace
echo Rebuilding workspace...
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && colcon build --packages-select chasebot_description"

echo ======================================
echo Sync complete!
echo ======================================
echo.
echo Ready to launch with:
echo wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0 && ros2 launch chasebot_description jetbot_with_transforms.launch.py"
echo.
pause
