# ChaseBot Environment Management Rules

## 🚀 QUICK START - FINDING ROS 2
**Current Development Environment**: ROS 2 Humble on Ubuntu-22.04 WSL2
- **Quick Check**: `wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 --help"`
- **Workspace Location**: `~/ros2_ws/`
- **Launch Robot**: `ros2 launch chasebot_description jetbot_gazebo.launch.py`
- **⚠️ CURRENT ISSUE**: gzserver crashes prevent robot spawning - fresh rebuild required
- **⚠️ NO GPU REQUIRED** - ROS 2 works perfectly without GPU

## GPU Requirements - CLARIFICATION
### ✅ What DOESN'T need GPU (Current Development):
- **ROS 2 Humble** - Works perfectly without GPU
- **Gazebo Classic** - Works with ROS 2 without GPU  
- **All our current robot development** - No GPU needed
- **Keyboard/programmatic robot control** - No GPU needed

### ❌ What DOES need GPU (Future Upgrades):
- **Modern Gazebo (Ignition/Fortress)** - OpenGL errors without GPU
- **Isaac Sim** - Requires NVIDIA RTX GPU
- **GPU-accelerated Isaac ROS perception** - Optional performance boost

### 📝 Bottom Line:
**Continue ROS 2 development now, upgrade simulators when GPU available**

## New Session Checklist
**Start every session with this validation:**
1. **Check which ROS you need:**
   - ROS 1 (Ubuntu-18.04): Legacy reference system
   - **ROS 2 (Ubuntu-22.04): Current development** ⭐
2. **Verify WSL2 running**: `wsl --list --verbose`
3. **Quick ROS 2 test**: `wsl -d Ubuntu-22.04 bash -c "ros2 --help"`
4. **If ROS 2 not found**: Check Ubuntu-22.04 is running, source environment

## DUAL WSL2 + ROS Development Environment

### CRITICAL: Two Separate ROS Environments
**We maintain BOTH ROS 1 and ROS 2 environments for different purposes:**

#### **ROS 1 Environment (Legacy/Reference)**
- **WSL2 Instance**: `Ubuntu-18.04`
- **ROS Version**: ROS Melodic
- **Purpose**: Baseline autonomous ball following system (reference implementation)
- **Launch Check**: `wsl -d Ubuntu-18.04 bash -c "source /opt/ros/melodic/setup.bash && which roscore"`

#### **ROS 2 Environment (Current Development)**
- **WSL2 Instance**: `Ubuntu-22.04` 
- **ROS Version**: ROS 2 Humble LTS
- **Purpose**: Modern migration target with Isaac ROS integration
- **Launch Check**: `wsl -d Ubuntu-22.04 bash -c "source /opt/ros/humble/setup.bash && ros2 --help"`

### Session Initialization Protocol
**ALWAYS start each session with environment validation:**

1. **Check WSL2 Status**: `wsl --list --verbose`
   - **ROS 1**: If Ubuntu-18.04 stopped, restart with: `wsl -d Ubuntu-18.04`
   - **ROS 2**: If Ubuntu-22.04 stopped, restart with: `wsl -d Ubuntu-22.04`

2. **Choose and Validate Target Environment**:

   **FOR ROS 1 WORK (Legacy System)**:
   - Kill existing processes: `wsl -d Ubuntu-18.04 bash -c "pkill -f ros; pkill -f gazebo"`
   - Check ROS availability: `wsl -d Ubuntu-18.04 bash -c "source /opt/ros/melodic/setup.bash && which roscore"`
   - Source catkin workspace: `wsl -d Ubuntu-18.04 bash -c "source ~/catkin_ws/devel/setup.bash"`

   **FOR ROS 2 WORK (Current Development)**:
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
- **EFFECTIVE**: `roslaunch package_name launch_file.launch` followed by automated test
- **AVOID**: Multi-step manual instructions requiring user terminal input
- **PATTERN**: Launch → Wait → Test → Visual Confirmation

#### UAT Testing Approach
- **LAUNCH**: Automated simulation startup
- **EXECUTE**: Automated movement/behavior test
- **OBSERVE**: User visual confirmation in GUI
- **VALIDATE**: Clear success/failure criteria

### Environment Troubleshooting

#### Common Issues & Solutions
- **"Unable to communicate with master"** → Restart ROS master
- **"SyntaxError" on f-strings** → Use `.format()` syntax
- **Robot not moving** → Check physics configuration and topic availability
- **Gazebo won't start** → Verify WSL2 status and display configuration
- **File not found** → Verify file sync between Windows and WSL2

#### Session Recovery Pattern
1. Terminate all existing processes
2. Verify WSL2 is running
3. Copy latest files to WSL2
4. Source ROS environment
5. Launch fresh simulation
6. Execute automated tests

### Development Workflow Standards

#### File Management
- **Edit**: Windows VS Code for development
- **Execute**: WSL2 environment for ROS operations
- **Sync**: Manual copy commands between environments
- **Build**: Always rebuild catkin workspace after file changes

#### Testing Execution
- **Simulation First**: Always test in Gazebo before hardware
- **Clean Environment**: Fresh ROS processes for each test session
- **Visual Validation**: User confirmation of expected behavior
- **Automated Scripts**: Minimize manual user interaction

#### Session Continuity
- **Document State**: What's running and what needs restart
- **Environment Setup**: Script common initialization sequences
- **File Status**: Track which files are synced between environments
- **Process Management**: Clean shutdown/startup procedures

### Critical Success Factors
1. **Environment Validation**: Always verify WSL2 and ROS status first
2. **Process Hygiene**: Clean process startup/shutdown procedures
3. **File Synchronization**: Maintain sync between Windows and WSL2
4. **Automated Testing**: Minimize manual user interaction
5. **Visual Confirmation**: Provide clear validation in simulation GUI

These practices ensure reliable, repeatable ChaseBot development sessions across the Windows/WSL2/ROS environment stack.
