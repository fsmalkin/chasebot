# ChaseBot Environment Management Rules

## 🚀 QUICK START - FINDING ROS 2
**Current Development Environment**: ROS 2 Humble on Ubuntu-22.04 WSL2
- **Quick Check**: `wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 --help"`
- **Workspace Location**: `~/ros2_ws/`
- **Core Foundation Validated**: `ros2 launch ~/ros2_ws/src/chasebot_description/launch/jetbot_autonomous_headless.launch.py`
- **✅ UAT SUCCESS**: Non-Nav2 demo proven operational - robot movement and control validated
- **🎯 NEXT PRIORITY**: GUI environment setup for vision-based autonomous behavior

## Current Status: Core Foundation Complete, GUI Environment Required

### ✅ What Works (UAT Validated - 2025-06-28):
- **ROS 2 Humble + Gazebo** - Complete simulation environment operational
- **Robot Spawning** - JetBot successfully spawned in headless simulation  
- **Movement Control** - Robot responds perfectly to `/cmd_vel` commands
- **Physics Simulation** - Validated movement from (0,0) to (0.76m, 0.71m) with rotation
- **Professional ROS Topics** - All communication channels operational

### 🎯 Current Priority: GUI Environment for Vision
- **Issue**: Camera sensor requires GUI ("Unable to create CameraSensor. Rendering is disabled")
- **Impact**: Vision-based ball following cannot operate in headless mode
- **Solution**: Configure WSL2 display/X11 forwarding for Gazebo GUI
- **Goal**: Enable complete autonomous ball following with visual feedback

## New Session Checklist
**Start every session with this validation:**
1. **Verify Core Foundation**: Confirm ROS 2 + Gazebo headless simulation working
2. **Check WSL2 Status**: `wsl --list --verbose`
3. **Quick ROS 2 Test**: `wsl -d Ubuntu-22.04 bash -c "ros2 --help"`
4. **Priority Assessment**: Focus on GUI environment setup for vision capabilities

## DUAL WSL2 + ROS Development Environment

### CRITICAL: Two Separate ROS Environments
**We maintain BOTH ROS 1 and ROS 2 environments for different purposes:**

#### **ROS 1 Environment (Legacy/Reference)**
- **WSL2 Instance**: `Ubuntu-18.04`
- **ROS Version**: ROS Melodic
- **Purpose**: Baseline autonomous ball following system (reference implementation)
- **Status**: Complete autonomous system validated
- **Launch Check**: `wsl -d Ubuntu-18.04 bash -c "source /opt/ros/melodic/setup.bash && which roscore"`

#### **ROS 2 Environment (Current Development) ✅ VALIDATED**
- **WSL2 Instance**: `Ubuntu-22.04` 
- **ROS Version**: ROS 2 Humble LTS
- **Purpose**: Modern robotics platform with Nav2 integration
- **Status**: Core foundation UAT complete, GUI environment next priority
- **Launch Check**: `wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 --help"`

### Session Initialization Protocol
**ALWAYS start each session with environment validation:**

1. **Check WSL2 Status**: `wsl --list --verbose`
   - **ROS 1**: If Ubuntu-18.04 stopped, restart with: `wsl -d Ubuntu-18.04`
   - **ROS 2**: If Ubuntu-22.04 stopped, restart with: `wsl -d Ubuntu-22.04`

2. **Choose and Validate Target Environment**:

   **FOR ROS 1 WORK (Legacy Reference)**:
   - Kill existing processes: `wsl -d Ubuntu-18.04 bash -c "pkill -f ros; pkill -f gazebo"`
   - Check ROS availability: `wsl -d Ubuntu-18.04 bash -c "source /opt/ros/melodic/setup.bash && which roscore"`
   - Source catkin workspace: `wsl -d Ubuntu-18.04 bash -c "source ~/catkin_ws/devel/setup.bash"`

   **FOR ROS 2 WORK (Current Development) ✅ VALIDATED**:
   - Kill existing processes: `wsl -d Ubuntu-22.04 bash -c "pkill -f ros; pkill -f gazebo"`
   - Check ROS 2 availability: `wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 --help"`
   - Source workspace: `wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source install/setup.bash"`

3. **File Synchronization**:
   - **Windows edits**: `c:/workspaces/chasebot/`
   - **ROS 1 execution**: `~/catkin_ws/src/chasebot_description/` (Ubuntu-18.04)
   - **ROS 2 execution**: `~/ros2_ws/src/chasebot_description/` (Ubuntu-22.04)
   - **Copy commands**: 
     - ROS 1: `wsl -d Ubuntu-18.04 bash -c "cp /mnt/c/workspaces/chasebot/file.ext ~/catkin_ws/src/target/"`
     - ROS 2: `wsl -d Ubuntu-22.04 bash -c "cp /mnt/c/workspaces/chasebot/file.ext ~/ros2_ws/src/target/"`

## GUI Environment Setup (Next Priority)

### Current Limitation
- **Headless Success**: Core robotics foundation validated in headless mode
- **Vision Barrier**: Camera sensor requires GUI for autonomous ball following
- **GUI Required**: WSL2 display configuration needed for Gazebo visual interface

### GUI Setup Options
1. **WSL2 + X11 Forwarding**: Configure display forwarding to Windows
2. **VcXsrv Windows X Server**: Native Windows X server for WSL2 GUI
3. **Native Windows ROS 2**: Direct Windows installation for GUI access

### GUI Validation Commands
```bash
# Test GUI environment
wsl -d Ubuntu-22.04 bash -c "echo $DISPLAY"

# Launch Gazebo with GUI (target command)
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && gazebo"

# Complete autonomous demo (goal)
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 launch ~/ros2_ws/src/chasebot_description/launch/jetbot_autonomous_direct.launch.py"
```

### Code Compatibility Requirements

#### Python Compatibility (ROS Melodic)
- **FORBIDDEN**: f-string syntax `f"text {variable}"`
- **REQUIRED**: `.format()` method `"text {}".format(variable)`
- **REASON**: ROS Melodic uses older Python version

#### ROS Process Management
- **ALWAYS**: Check for existing ROS processes before launching
- **PATTERN**: Kill → Wait → Restart for clean state
- **DETECTION**: "Unable to communicate with master!" = ROS master not running

### User Interaction Best Practices

#### Automated vs Manual Workflows
- **PREFERRED**: Single automated commands that launch GUI applications
- **EFFECTIVE**: `ros2 launch package_name launch_file.launch.py` followed by automated test
- **AVOID**: Multi-step manual instructions requiring user terminal input
- **PATTERN**: Launch → Wait → Test → Visual Confirmation

#### UAT Testing Approach
- **LAUNCH**: Automated simulation startup with GUI
- **EXECUTE**: Automated movement/behavior test
- **OBSERVE**: User visual confirmation in Gazebo GUI
- **VALIDATE**: Clear success/failure criteria

### Environment Troubleshooting

#### Common Issues & Solutions
- **"Unable to create CameraSensor"** → GUI environment required
- **"Can't open display"** → Configure WSL2 X11 forwarding
- **"SyntaxError" on f-strings** → Use `.format()` syntax for ROS Melodic
- **Robot not moving** → Check physics configuration and topic availability
- **Gazebo won't start** → Verify WSL2 status and display configuration
- **File not found** → Verify file sync between Windows and WSL2

#### Session Recovery Pattern - CRITICAL: ALWAYS USE PIDs
1. **Terminate all existing processes using PIDs**: 
   - First: `ps aux | grep -E '(gazebo|gzserver|gzclient|ros2|nav2)' | grep -v grep`
   - Then: `kill -9 [PID1] [PID2] [PID3]` (use specific PIDs, never generic pkill)
   - Verify: Check that all processes are actually terminated
2. Verify WSL2 is running
3. Copy latest files to WSL2
4. Source ROS environment
5. Launch fresh simulation
6. Execute automated tests

#### MANDATORY: PID-Based Process Management
- **ALWAYS use PIDs for process termination** - Generic pkill commands are unreliable
- **NEVER use pkill -f** or similar generic commands for critical processes
- **PATTERN**: `ps aux | grep [process] → kill -9 [specific PIDs] → verify termination`
- **REASON**: Ensures complete cleanup and prevents "Address already in use" errors

#### CRITICAL: WSL Path Mapping Issues
**DISCOVERED 2025-01-03**: Git Bash fails with WSL file operations due to path mapping issues.

**SYMPTOMS**:
- Error: "cannot stat 'C:/Program Files/Git/mnt/c/..." 
- Error: "No such file or directory"
- Git Bash incorrectly prefixes WSL paths with Git installation directory

**SOLUTION**: Never use Git Bash for WSL file operations. Use these alternatives:

**Method 1: Command Prompt (RECOMMENDED)**
```cmd
# Open Command Prompt (cmd.exe) and run:
wsl -d Ubuntu-22.04 cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/file.py ~/ros2_ws/src/target/
```

**Method 2: Direct WSL Terminal**
```bash
# Open WSL terminal directly and run:
cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/file.py ~/ros2_ws/src/target/
```

**File Sync Pattern**:
```bash
# 1. Use Command Prompt for file operations
wsl -d Ubuntu-22.04 cp /mnt/c/Users/arsen_j7sbcbk/Desktop/chasebot/ros2_scripts/new_file.py ~/ros2_ws/src/chasebot_description/ros2_scripts/

# 2. Fix line endings
wsl -d Ubuntu-22.04 sed -i 's/\r$//' ~/ros2_ws/src/chasebot_description/ros2_scripts/new_file.py

# 3. Make executable
wsl -d Ubuntu-22.04 chmod +x ~/ros2_ws/src/chasebot_description/ros2_scripts/new_file.py

# 4. Build workspace
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select chasebot_description"
```

**NEVER**: Use Git Bash for WSL commands
**ALWAYS**: Use Command Prompt or direct WSL terminal for file sync operations

### Development Workflow Standards

#### File Management
- **Edit**: Windows VS Code for development
- **Execute**: WSL2 environment for ROS operations
- **Sync**: Manual copy commands between environments
- **Build**: Always rebuild workspace after file changes

#### Testing Execution
- **Simulation First**: Always test in Gazebo before hardware
- **Clean Environment**: Fresh ROS processes for each test session
- **Visual Validation**: User confirmation of expected behavior in GUI
- **Automated Scripts**: Minimize manual user interaction

#### Session Continuity
- **Document State**: What's running and what needs restart
- **Environment Setup**: Script common initialization sequences
- **File Status**: Track which files are synced between environments
- **Process Management**: Clean shutdown/startup procedures

### Validated Working Commands (ROS 2)

#### Core Foundation (✅ PROVEN)
```bash
# Headless simulation with robot control
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 launch ~/ros2_ws/src/chasebot_description/launch/jetbot_autonomous_headless.launch.py"

# Movement test
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.1}, angular: {z: 0.2}}'"

# Odometry verification
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 topic echo /odom --once"
```

#### Next Target (GUI Required)
```bash
# Full autonomous ball following (requires GUI)
wsl -d Ubuntu-22.04 bash -c "cd ~/ros2_ws && source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 launch ~/ros2_ws/src/chasebot_description/launch/jetbot_autonomous_direct.launch.py"
```

### Critical Success Factors
1. **Environment Validation**: Always verify WSL2 and ROS status first
2. **GUI Priority**: Configure display environment for vision capabilities
3. **Process Hygiene**: Clean process startup/shutdown procedures
4. **File Synchronization**: Maintain sync between Windows and WSL2
5. **Visual Confirmation**: Enable GUI for complete UAT validation

**Current Achievement**: Core robotics foundation validated. GUI environment setup is the only barrier to complete autonomous ball following demonstration.
