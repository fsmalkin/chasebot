# Sync Direct Follower Files to WSL2
Write-Host "Syncing Direct Follower files to WSL2..." -ForegroundColor Green

# Sync the direct follower implementation
Write-Host "Copying yolo_3d_direct_follower.py..."
wsl -d Ubuntu-22.04 -- bash -c 'cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/yolo_3d_direct_follower.py ~/ros2_ws/src/chasebot_description/ros2_scripts/'

# Sync the test scripts
Write-Host "Copying test_direct_follower.py..."
wsl -d Ubuntu-22.04 -- bash -c 'cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/test_direct_follower.py ~/ros2_ws/src/chasebot_description/ros2_scripts/'

Write-Host "Copying Nav2 debug tests..."
wsl -d Ubuntu-22.04 -- bash -c 'cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/test_nav2_lifecycle_debug.py ~/ros2_ws/src/chasebot_description/ros2_scripts/'
wsl -d Ubuntu-22.04 -- bash -c 'cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/test_nav2_minimal_individual.py ~/ros2_ws/src/chasebot_description/ros2_scripts/'

# Make scripts executable
Write-Host "Making scripts executable..."
wsl -d Ubuntu-22.04 -- bash -c 'chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/yolo_3d_direct_follower.py'
wsl -d Ubuntu-22.04 -- bash -c 'chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/test_direct_follower.py'
wsl -d Ubuntu-22.04 -- bash -c 'chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/test_nav2_lifecycle_debug.py'
wsl -d Ubuntu-22.04 -- bash -c 'chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/test_nav2_minimal_individual.py'

# Verify files exist
Write-Host "`nVerifying files in WSL2..." -ForegroundColor Yellow
wsl -d Ubuntu-22.04 -- bash -c 'ls -la ~/ros2_ws/src/chasebot_description/ros2_scripts/ | grep -E "(direct_follower|nav2_lifecycle|nav2_minimal)"'

Write-Host "`nSync complete!" -ForegroundColor Green
Write-Host "You can now run: python3 ros2_scripts/test_direct_follower.py" -ForegroundColor Cyan
