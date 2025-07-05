@echo off
echo ================================================
echo SLICE 5.2: Coordinate Fix Deployment File Sync
echo ================================================
echo.
echo CRITICAL: This script must be run from Command Prompt (cmd.exe)
echo NOT from Git Bash due to WSL path mapping issues!
echo.
echo Copying corrected bridge and diagnostic files...
echo.

REM Copy corrected YOLO to Nav2 bridge
echo Copying corrected bridge...
wsl -d Ubuntu-22.04 cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/ros2_yolo_to_nav_goal_corrected.py ~/ros2_ws/src/chasebot_description/ros2_scripts/
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to copy corrected bridge file
    echo Make sure you're running from Command Prompt, not Git Bash
    pause
    exit /b 1
)

REM Copy position diagnostics tool
echo Copying position diagnostics...
wsl -d Ubuntu-22.04 cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/position_diagnostics.py ~/ros2_ws/src/chasebot_description/ros2_scripts/
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to copy position diagnostics file
    pause
    exit /b 1
)

REM Fix line endings
echo Fixing line endings...
wsl -d Ubuntu-22.04 sed -i 's/\r$//' ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_to_nav_goal_corrected.py
wsl -d Ubuntu-22.04 sed -i 's/\r$//' ~/ros2_ws/src/chasebot_description/ros2_scripts/position_diagnostics.py

REM Set permissions
echo Setting permissions...
wsl -d Ubuntu-22.04 chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_to_nav_goal_corrected.py
wsl -d Ubuntu-22.04 chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/position_diagnostics.py

REM Build workspace
echo Building workspace...
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select chasebot_description"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to build workspace
    pause
    exit /b 1
)

echo.
echo ================================================
echo SUCCESS: Slice 5.2 files synchronized!
echo ================================================
echo.
echo Files deployed:
echo - ros2_yolo_to_nav_goal_corrected.py (corrected coordinate bridge)
echo - position_diagnostics.py (position validation tool)
echo.
echo Ready for UAT testing!
echo Follow the test procedures in docs/slice5_2_coordinate_fix_deployment_uat.md
echo.
pause
