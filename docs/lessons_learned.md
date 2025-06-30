# ChaseBot Lessons Learned

This document consolidates key technical insights, solutions, and lessons from the ChaseBot development journey.

## Vision System Insights

### HSV Detection Threshold Discovery
- **Breakthrough**: Reducing pixel threshold from 10 to 3 pixels per column enabled 2x detection range
- **Impact**: Extended golf ball detection from 1m to 2m+ distances
- **Lesson**: Simple parameter tuning can unlock significant capability improvements

### Camera Field of View Limitations
- **Issue**: Robot loses ball tracking when turning due to limited camera FOV
- **Solution**: Implement predictive movement to continue toward last known position
- **Lesson**: Consider sensor limitations in movement planning algorithms

### Vision to LaserScan Conversion
- **Challenge**: IMX219 is monocular RGB camera without depth
- **Solution**: HSV-based obstacle detection converted to laser scan format
- **Success**: Enabled Nav2 integration without depth camera hardware

## ROS 2 Migration Insights

### Python Compatibility
- **Critical**: ROS Melodic requires Python 2.7 syntax (no f-strings)
- **Solution**: Always use `.format()` method instead of f-strings
- **Validation**: Test all Python scripts for compatibility before deployment

### Process Management
- **Issue**: Generic pkill commands unreliable for ROS processes
- **Solution**: Always use PID-based termination: `ps aux | grep [process] → kill -9 [specific PIDs]`
- **Reason**: Prevents "Address already in use" errors and ensures clean shutdown

### WSL2 Environment Management
- **Challenge**: Dual ROS 1/ROS 2 environments in separate WSL2 instances
- **Solution**: Systematic environment validation at session start
- **Key Commands**:
  - Check status: `wsl --list --verbose`
  - ROS 1: `wsl -d Ubuntu-18.04`
  - ROS 2: `wsl -d Ubuntu-22.04`
- **Session Initialization Checklist**:
  1. Check WSL2 status
  2. Start WSL2 if stopped
  3. Kill existing ROS processes: `pkill -f ros; pkill -f gazebo`
  4. Copy updated files from Windows to WSL2
  5. Source ROS environment
  6. Launch fresh simulation

## Navigation System Insights

### Nav2 Resource Requirements
- **Discovery**: Full Nav2 stack is very resource-intensive
- **Impact**: Can cause system overheating on limited hardware
- **Solution**: Direct cmd_vel control sufficient for basic ball following
- **Future**: Nav2 ready when more powerful hardware available

### Transform Timing Issues
- **Problem**: "Lookup would require extrapolation into the future"
- **Root Cause**: Small timing mismatches between transform timestamps
- **Solution**: Increase transform_tolerance to 0.5 seconds in Nav2 config

### Costmap Configuration
- **Issue**: "Robot is out of bounds of the costmap!"
- **Solution**: Proper costmap sizing and centering:
  - Local: 5x5 meters
  - Global: 20x20 meters with origin_x: -10.0, origin_y: -10.0

## Hardware Integration

### JetBot Physics Configuration
- **Problem**: Robot wouldn't move in simulation despite correct commands
- **Root Cause**: Missing physics parameters in URDF
- **Solution**: Added mass (1kg) and inertia matrix to base_link
- **Lesson**: Always validate physics properties for simulation

### Differential Drive Parameters
- **Working Configuration**:
  - Wheel separation: 0.1 meters
  - Wheel radius: 0.03 meters
  - Max velocity: 0.15 m/s
  - Command timeout: 2.0 seconds

## Development Workflow

### Thin Slice Development Success
- **Pattern**: Break complex problems into very small, testable pieces
- **Example**: Test package installation → Test basic launch → Test with camera → Test detection
- **Benefit**: Each slice independently demonstrable and valuable

### GUI Environment Setup
- **Challenge**: Headless WSL2 requires display configuration for Gazebo GUI
- **Solution**: VcXsrv Windows X Server with proper DISPLAY export
- **Success**: Enabled vision-based testing with visual feedback

### File Synchronization
- **Issue**: Editing in Windows, executing in WSL2
- **Solution**: Manual copy commands between environments
- **Pattern**: Always rebuild workspace after file changes

## Architecture Decisions

### Search Existing Solutions First
- **Success Story**: Found darknet_ros for YOLO detection instead of custom implementation
- **Strategic Pivot**: Discovered ros2_vision_inference for 3D multi-object detection
  - Changed approach from custom multi-ball detection to professional solution
  - Enabled focus on LLM strategic planning instead of low-level detection
- **Benefit**: Professional-grade detection with minimal integration effort
- **Lesson**: 80% solution from existing package better than custom 100% solution

### Modular Architecture
- **Design**: Separate nodes for detection, position calculation, movement control
- **Benefit**: Easy to swap components (e.g., YOLO vs HSV detection)
- **Success**: Enabled rapid experimentation and debugging

## Testing Insights

### UAT-Driven Development
- **Pattern**: Nothing considered complete without user acceptance testing
- **Benefit**: Catches integration issues early
- **Example**: Discovered joystick dependency in simple_follower package through UAT

### Simulation-First Testing
- **Approach**: Always validate in Gazebo before hardware deployment
- **Benefit**: Rapid iteration without hardware wear
- **Success**: Complete autonomous system proven in simulation

## Critical Configuration Parameters

### PID Control (Proven Values)
```yaml
P: [2.0, 0.8]  # Angular, Linear gains
I: [0.0, 0.0]  # No integral action
D: [0.2, 0.1]  # Derivative damping
```

### Vision Detection
```yaml
HSV Range: [35,50,50] to [85,255,255]  # Green golf balls
Min Pixel Threshold: 3  # Enables 2m+ detection
Camera Resolution: 640x480
Detection FPS: ~22Hz
```

### Robot Safety
```yaml
Max Speed: 0.15 m/s
Target Distance: 0.6 m
Command Timeout: 2.0 seconds
Emergency Stop: Implemented
```

## Future Considerations

### Advanced Vision Research
- **MonoDepth2**: Deep learning depth estimation for better distance accuracy
- **DepthImage to LaserScan**: Professional ROS package for depth cameras
- **ros2_vision_inference**: Professional 3D multi-object detection
  - Repository: https://github.com/Owen-Liuyuxuan/ros2_vision_inference
  - Features: ONNX models, GPU acceleration, 3D positioning
  - Benefit: Replace custom HSV with professional detection
- **Benefit**: Could extend detection range to 10m+ with 3D accuracy

### Hardware Deployment
- **Consideration**: Jetson Nano GPU capabilities for advanced vision
- **Planning**: Test resource usage before deploying Nav2 on hardware
- **Safety**: Implement hardware emergency stop before deployment

## Key Success Factors

1. **Professional Standards**: Following ROS conventions enabled smooth integration
2. **Incremental Progress**: Thin slices prevented getting stuck on complex problems
3. **Existing Solutions**: Leveraging proven packages accelerated development
4. **Documentation**: Maintaining clear docs enabled effective handoffs
5. **User Validation**: UAT caught issues automated testing missed

## Conclusion

The ChaseBot project successfully demonstrated that professional robotics development can be achieved through:
- Systematic problem decomposition
- Leveraging existing solutions
- Maintaining high engineering standards
- Continuous user validation
- Careful resource management

These lessons provide a solid foundation for future robotics projects and ongoing ChaseBot enhancements.
