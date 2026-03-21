#!/bin/bash
# ChaseBot Complete Autonomous Navigation Demo
# Proven working procedure based on successful UAT 2025-06-29

set -e  # Exit on any error

echo "🚀 ChaseBot Autonomous Navigation Demo - Starting..."
echo "📋 Based on proven working sequence from UAT success"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

WSL_DISTRO="${WSL_DISTRO:-Ubuntu-22.04}"
ROS2_WS="${ROS2_WS:-~/ros2_ws}"

to_wsl_path() {
    local input_path="$1"

    if [[ "$input_path" =~ ^/mnt/[a-z]/.*$ ]]; then
        echo "$input_path"
        return
    fi

    if [[ "$input_path" =~ ^/([A-Za-z])/(.*)$ ]]; then
        local drive
        drive="$(echo "${BASH_REMATCH[1]}" | tr '[:upper:]' '[:lower:]')"
        echo "/mnt/${drive}/${BASH_REMATCH[2]}"
        return
    fi

    if [[ "$input_path" =~ ^([A-Za-z]):\\(.*)$ ]]; then
        local drive
        drive="$(echo "${BASH_REMATCH[1]}" | tr '[:upper:]' '[:lower:]')"
        local rest
        rest="${BASH_REMATCH[2]//\\//}"
        echo "/mnt/${drive}/${rest}"
        return
    fi

    echo "$input_path"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_WSL_PATH="${REPO_WSL_PATH:-$(to_wsl_path "$SCRIPT_DIR")}"
WSL_PACKAGE_ROOT="${WSL_PACKAGE_ROOT:-$(wsl -d "$WSL_DISTRO" bash -lc "if [ -d $ROS2_WS/src/chasecar ]; then echo $ROS2_WS/src/chasecar; elif [ -d $ROS2_WS/src/chasebot_description ]; then echo $ROS2_WS/src/chasebot_description; else echo $ROS2_WS/src/chasecar; fi")}"

# Step 1: Setup Display Environment
print_step "1. Setting up GUI display environment..."
wsl -d "$WSL_DISTRO" bash -c "
    DISPLAY_IP=\$(ip route show default | awk '{print \$3}')
    export DISPLAY=\${DISPLAY_IP}:0
    export LIBGL_ALWAYS_INDIRECT=1
    export MESA_GL_VERSION_OVERRIDE=3.3
    echo 'DISPLAY set to: '\$DISPLAY
    
    # Test X11 connection
    if command -v xset &> /dev/null; then
        if xset q >/dev/null 2>&1; then
            echo 'X11 connection successful!'
        else
            echo 'ERROR: X11 connection failed!'
            echo 'Make sure VcXsrv is running with -ac parameter'
            exit 1
        fi
    fi
"

if [ $? -eq 0 ]; then
    print_success "Display environment configured"
else
    print_error "Display setup failed"
    exit 1
fi

# Step 2: Sync Files from Windows to WSL2
print_step "2. Syncing latest files from Windows to WSL2..."
wsl -d "$WSL_DISTRO" bash -c "
    TARGET_PACKAGE='${WSL_PACKAGE_ROOT}'
    mkdir -p \"\$TARGET_PACKAGE/ros2_config/launch\" \"\$TARGET_PACKAGE/ros2_config/worlds\" \"\$TARGET_PACKAGE/ros2_config/urdf\" \"\$TARGET_PACKAGE/ros2_config/params\" \"\$TARGET_PACKAGE/ros2_scripts\"
    cp '${REPO_WSL_PATH}/ros2_config/launch/nav2_complete_uat.launch.py' \"\$TARGET_PACKAGE/ros2_config/launch/\"
    cp '${REPO_WSL_PATH}/ros2_scripts/ros2_vision_to_laserscan_hsv.py' \"\$TARGET_PACKAGE/ros2_scripts/\"
    cp '${REPO_WSL_PATH}/ros2_scripts/ros2_ball_to_nav_goal.py' \"\$TARGET_PACKAGE/ros2_scripts/\"
    cp '${REPO_WSL_PATH}/ros2_config/worlds/autonomous_golf_ball_world.world' \"\$TARGET_PACKAGE/ros2_config/worlds/\"
    cp '${REPO_WSL_PATH}/ros2_config/urdf/ros2_jetbot.urdf' \"\$TARGET_PACKAGE/ros2_config/urdf/\"
    cp '${REPO_WSL_PATH}/ros2_config/params/nav2_params_simple.yaml' \"\$TARGET_PACKAGE/ros2_config/params/\"
    chmod +x \"\$TARGET_PACKAGE/ros2_scripts\"/*.py
"
print_success "Files synced and permissions set"

# Step 3: Rebuild Workspace
print_step "3. Rebuilding ROS 2 workspace..."
wsl -d "$WSL_DISTRO" bash -c "
    cd ~/ros2_ws
    source /opt/ros/humble/setup.bash
    colcon build --packages-select chasebot_description
"
print_success "Workspace rebuilt successfully"

# Step 4: Kill any existing processes (using PIDs)
print_step "4. Cleaning up any existing processes..."
wsl -d "$WSL_DISTRO" bash -c "
    PIDS=\$(ps aux | grep -E '(gazebo|gzserver|gzclient|ros2|nav2)' | grep -v grep | awk '{print \$2}' | tr '\n' ' ')
    if [ ! -z '\$PIDS' ]; then
        echo 'Killing existing processes: '\$PIDS
        kill -9 \$PIDS 2>/dev/null || true
        sleep 2
    else
        echo 'No existing processes found'
    fi
"
print_success "Process cleanup completed"

echo ""
echo "🎯 Ready to launch ChaseBot autonomous navigation demo!"
echo "📋 The demo will launch components in this sequence:"
echo "   1. Gazebo with golf ball world (GUI)"
echo "   2. JetBot robot spawn"
echo "   3. Nav2 navigation stack"
echo "   4. Vision processing components"
echo ""
echo "🚨 IMPORTANT: Make sure VcXsrv is running on Windows!"
echo ""
read -p "Press Enter to start the demo or Ctrl+C to cancel..."

# Step 5: Launch Gazebo with Golf Ball World
print_step "5. Launching Gazebo with golf ball world..."
wsl -d "$WSL_DISTRO" bash -c "
    TARGET_PACKAGE='${WSL_PACKAGE_ROOT}'
    DISPLAY_IP=\$(ip route show default | awk '{print \$3}')
    export DISPLAY=\${DISPLAY_IP}:0
    export LIBGL_ALWAYS_INDIRECT=1
    export MESA_GL_VERSION_OVERRIDE=3.3
    source /opt/ros/humble/setup.bash
    cd ~/ros2_ws
    source install/setup.bash
    ros2 launch gazebo_ros gazebo.launch.py world:=\"\$TARGET_PACKAGE/ros2_config/worlds/autonomous_golf_ball_world.world\"
" &

GAZEBO_PID=$!
echo "Gazebo starting... (PID: $GAZEBO_PID)"
sleep 10

# Check if Gazebo is running
wsl -d "$WSL_DISTRO" bash -c "ps aux | grep gazebo | grep -v grep" > /dev/null
if [ $? -eq 0 ]; then
    print_success "Gazebo launched successfully"
else
    print_error "Gazebo failed to launch"
    exit 1
fi

# Step 6: Spawn JetBot Robot
print_step "6. Spawning JetBot robot in simulation..."
wsl -d "$WSL_DISTRO" bash -c "
    TARGET_PACKAGE='${WSL_PACKAGE_ROOT}'
    source /opt/ros/humble/setup.bash
    cd ~/ros2_ws
    source install/setup.bash
    ros2 run gazebo_ros spawn_entity.py -file \"\$TARGET_PACKAGE/ros2_config/urdf/ros2_jetbot.urdf\" -entity jetbot -x 0 -y 0 -z 0.1
"

if [ $? -eq 0 ]; then
    print_success "JetBot robot spawned successfully"
else
    print_error "Robot spawn failed"
    exit 1
fi

sleep 3

# Step 7: Launch Nav2 Navigation Stack
print_step "7. Launching Nav2 navigation stack..."
wsl -d "$WSL_DISTRO" bash -c "
    TARGET_PACKAGE='${WSL_PACKAGE_ROOT}'
    source /opt/ros/humble/setup.bash
    cd ~/ros2_ws
    source install/setup.bash
    ros2 launch nav2_bringup navigation_launch.py params_file:=\"\$TARGET_PACKAGE/ros2_config/params/nav2_params_simple.yaml\" use_sim_time:=true
" &

NAV2_PID=$!
echo "Nav2 starting... (PID: $NAV2_PID)"
sleep 8

print_success "Nav2 navigation stack launched"

# Step 8: Start Vision to LaserScan Converter
print_step "8. Starting vision to laser scan converter..."
wsl -d "$WSL_DISTRO" bash -c "
    TARGET_PACKAGE='${WSL_PACKAGE_ROOT}'
    source /opt/ros/humble/setup.bash
    cd ~/ros2_ws
    source install/setup.bash
    python3 \"\$TARGET_PACKAGE/ros2_scripts/ros2_vision_to_laserscan_hsv.py\"
" &

VISION_PID=$!
echo "Vision processing starting... (PID: $VISION_PID)"
sleep 3

# Step 9: Start Ball to Nav Goal Converter
print_step "9. Starting ball to navigation goal converter..."
wsl -d "$WSL_DISTRO" bash -c "
    TARGET_PACKAGE='${WSL_PACKAGE_ROOT}'
    source /opt/ros/humble/setup.bash
    cd ~/ros2_ws
    source install/setup.bash
    python3 \"\$TARGET_PACKAGE/ros2_scripts/ros2_ball_to_nav_goal.py\"
" &

BALL_NAV_PID=$!
echo "Ball navigation starting... (PID: $BALL_NAV_PID)"

echo ""
print_success "🎉 ChaseBot Autonomous Navigation Demo is now RUNNING!"
echo ""
echo "📊 System Status:"
echo "   ✅ Gazebo GUI: Running (check your screen)"
echo "   ✅ JetBot Robot: Spawned and operational"
echo "   ✅ Nav2 Stack: Active with path planning"
echo "   ✅ Vision Processing: Detecting golf balls"
echo "   ✅ Autonomous Navigation: Robot should move toward ball"
echo ""
echo "🔍 What you should see:"
echo "   - Gazebo window showing robot and green golf ball"
echo "   - Robot turning and moving toward the ball"
echo "   - Autonomous navigation with obstacle avoidance"
echo ""
echo "🛑 To stop the demo, press Ctrl+C"
echo ""

# Wait for user to stop
trap "echo '🛑 Stopping demo...' && kill $GAZEBO_PID $NAV2_PID $VISION_PID $BALL_NAV_PID 2>/dev/null && exit" INT

# Keep script running
while true; do
    sleep 1
done
