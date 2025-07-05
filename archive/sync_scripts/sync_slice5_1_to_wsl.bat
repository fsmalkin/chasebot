@echo off
echo Syncing Slice 5.1 Static Ball Refiner files to WSL2...

:: Copy the enhanced static ball refiner script
echo Copying ros2_static_ball_refiner.py...
wsl -d Ubuntu-22.04 cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/ros2_static_ball_refiner.py ~/ros2_ws/src/chasebot_description/ros2_scripts/

:: Copy the new launch file
echo Copying jetbot_nav2_refined_approach.launch.py...
wsl -d Ubuntu-22.04 cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/launch/jetbot_nav2_refined_approach.launch.py ~/ros2_ws/src/chasebot_description/ros2_config/launch/

:: Fix line endings for Python scripts
echo Fixing line endings...
wsl -d Ubuntu-22.04 sed -i 's/\r$//' ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_static_ball_refiner.py

:: Make Python scripts executable
echo Making scripts executable...
wsl -d Ubuntu-22.04 chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_static_ball_refiner.py

:: Build the workspace
echo Building workspace...
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select chasebot_description"

echo.
echo Slice 5.1 files synchronized successfully!
echo.
echo Ready to test enhanced static ball refiner:
echo Launch command: ros2 launch chasebot_description jetbot_nav2_refined_approach.launch.py
echo.
echo Key enhancements:
echo - Approach distance reduced from 0.3m to 0.25m
echo - Periodic goal refinement every 3 seconds
echo - Smart position change threshold (5cm)
echo - Refinement stops within 0.5m of goal
echo.
pause
