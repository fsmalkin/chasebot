@echo off
echo Syncing Slice 1 files to WSL2...

REM Create directories if they don't exist
wsl -d Ubuntu-22.04 bash -c "mkdir -p ~/ros2_ws/src/chasebot_description/ros2_config/launch"
wsl -d Ubuntu-22.04 bash -c "mkdir -p ~/ros2_ws/src/chasebot_description/ros2_scripts"
wsl -d Ubuntu-22.04 bash -c "mkdir -p ~/ros2_ws/src/chasebot_description/docs"

REM Copy launch file
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/launch/jetbot_basic_spawn.launch.py ~/ros2_ws/src/chasebot_description/ros2_config/launch/"

REM Copy shutdown manager
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/shutdown_manager.py ~/ros2_ws/src/chasebot_description/ros2_scripts/"

REM Copy UAT documentation
wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/docs/slice1_uat.md ~/ros2_ws/src/chasebot_description/docs/"

REM Make scripts executable
wsl -d Ubuntu-22.04 bash -c "chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/shutdown_manager.py"
wsl -d Ubuntu-22.04 bash -c "chmod +x ~/ros2_ws/src/chasebot_description/ros2_config/launch/jetbot_basic_spawn.launch.py"

REM Rebuild the package to register new files
echo.
echo Rebuilding package...
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select chasebot_description"

echo.
echo Sync complete! Files ready for Slice 1 UAT.
echo.
echo To run Slice 1 UAT:
echo   1. Make sure VcXsrv is running with "Disable access control" checked
echo   2. Run: wsl -d Ubuntu-22.04
echo   3. Then execute the launch command from slice1_uat.md
echo.
pause
