# ChaseBot Environment Management Rules

## WSL2 + ROS Development Environment

### Session Initialization Protocol
**ALWAYS start each session with environment validation:**

1. **Check WSL2 Status**: `wsl --list --verbose`
   - If stopped, restart with: `wsl -d Ubuntu-18.04`
   - WSL2 Ubuntu must be running for ROS functionality

2. **Validate ROS Environment**:
   - Kill existing processes: `wsl -d Ubuntu-18.04 bash -c "pkill -f ros; pkill -f gazebo"`
   - Check ROS availability: `source /opt/ros/melodic/setup.bash && which roscore`
   - Source catkin workspace: `source ~/catkin_ws/devel/setup.bash`

3. **File Synchronization**:
   - Windows edits at: `c:/workspaces/chasebot/`
   - WSL2 execution from: `~/catkin_ws/src/chasebot_description/`
   - Copy command: `cp /mnt/c/workspaces/chasebot/file.ext ~/catkin_ws/src/target/`

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
