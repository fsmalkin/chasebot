# Sync v2.0.0 coordinate fix to WSL2
# This script syncs the new properly versioned bridge files

Write-Host "Syncing v2.0.0 coordinate fix to WSL2..." -ForegroundColor Cyan

# Sync the new v2.0.0 bridge
Write-Host "Syncing v2.0.0 bridge..." -ForegroundColor Yellow
wsl -d Ubuntu-22.04 -- bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/ros2_yolo_to_nav_goal_v2.0.0.py ~/ros2_ws/src/chasebot_description/ros2_scripts/"

# Sync all versioned bridges for comparison
Write-Host "Syncing all versioned bridges..." -ForegroundColor Yellow
wsl -d Ubuntu-22.04 -- bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/ros2_yolo_to_nav_goal_v*.py ~/ros2_ws/src/chasebot_description/ros2_scripts/"

# Sync updated launch file
Write-Host "Syncing updated launch file..." -ForegroundColor Yellow
wsl -d Ubuntu-22.04 -- bash -c "cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_config/launch/jetbot_nav2_integration_complete.launch.py ~/ros2_ws/src/chasebot_description/ros2_config/launch/"

# Make all scripts executable
Write-Host "Making scripts executable..." -ForegroundColor Yellow
wsl -d Ubuntu-22.04 -- bash -c "chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_to_nav_goal_v*.py"

# Verify files were copied
Write-Host "`nVerifying files..." -ForegroundColor Green
wsl -d Ubuntu-22.04 -- bash -c "ls -la ~/ros2_ws/src/chasebot_description/ros2_scripts/ros2_yolo_to_nav_goal_v*.py"

# Build workspace
Write-Host "`nBuilding workspace..." -ForegroundColor Yellow
wsl -d Ubuntu-22.04 -- bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select chasebot_description"

Write-Host "`nSync complete! You can now launch with:" -ForegroundColor Green
Write-Host "ros2 launch chasebot_description jetbot_nav2_integration_complete.launch.py bridge_version:=2.0.0" -ForegroundColor White
Write-Host "Or test the old broken version with:" -ForegroundColor Yellow
Write-Host "ros2 launch chasebot_description jetbot_nav2_integration_complete.launch.py bridge_version:=1.2.0" -ForegroundColor White
