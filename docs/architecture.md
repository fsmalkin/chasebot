# ChaseBot ROS 2 Architecture: Vision System Upgrade

## System Overview

ChaseBot is upgrading from a working HSV-based detection system to a professional YOLO-based detection pipeline using `ros2_vision_inference`. The upgrade will provide robust ball detection, standard ROS 2 messaging, and precise 3-inch approach distance for golf ball collection.

### Navigation Philosophy: Vision-Based, Map-Free

**CRITICAL ARCHITECTURAL DECISION**: ChaseBot uses **direct vision-based navigation** without relying on pre-built maps or SLAM. This is intentional and optimal for dynamic environments like golf driving ranges where:
- Balls constantly appear and disappear
- The environment is open and unstructured
- Mapping would provide no benefit
- Vision targets are the primary navigation goals

**Navigation Strategy**:
1. **No SLAM Required**: We do NOT use SLAM_toolbox or build persistent maps
2. **Direct Goal Publishing**: YOLO detections → Transform to odom frame → Nav2 goals
3. **Local Planning Only**: Nav2 handles obstacle avoidance via local costmaps
4. **Transform Chain**: Simple odom → base_link (with optional static map → odom if Nav2 requires it)

This approach is simpler, more robust, and perfectly suited for POC through production deployment.

## Current Status: Vision Upgrade Planned

### Working Baseline (HSV System)
- **Autonomous Navigation**: 2m+ detection and navigation working
- **Architecture**: Camera → HSV → Laser Scan → Nav2
- **Performance**: 100% success rate in controlled conditions
- **Limitation**: Lighting sensitive, imprecise final approach

### Target System (YOLO Upgrade)
- **Detection**: Neural network-based via ros2_vision_inference
- **Messages**: Standard vision_msgs/Detection3DArray
- **Approach**: Precise 3-inch (0.0762m) stopping distance
- **Robustness**: Lighting-independent professional detection

## Architecture Evolution

### Current HSV Architecture (Baseline)

```
Camera → HSV Detection → Pixel Counting → Laser Scan → Goal Bridge → Nav2
  |           |              |               |             |           |
  ↓           ↓              ↓               ↓             ↓           ↓
/camera/   Color-based   Distance from    /scan       Detection    Path
image_raw  thresholds    pixel count     topic       to goals    planning
```

### Target YOLO Architecture (Upgrade)

```
Camera → YOLO Detection → Detection3DArray → Goal Bridge → Nav2 → 3" Stop
  |           |                |                |           |        |
  ↓           ↓                ↓                ↓           ↓        ↓
/camera/   Neural net    3D positions    Closest ball   Path    0.0762m
image_raw  inference     & confidence    selection     planning  approach
```

## Implementation Tasks

### Task 1: Install ros2_vision_inference
- **Goal**: Set up YOLO-based detection package
- **Components**: 
  - ros2_vision_inference node
  - YOLO model for sports ball detection
  - GPU/CPU inference configuration
- **Output**: `/detection3d_array` topic with ball detections

### Task 2: Goal Bridge Development
- **Goal**: Convert detections to navigation goals
- **Components**:
  - Detection3DArray subscriber
  - Closest ball selection logic
  - NavigateToPose action client
- **Output**: Navigation goals sent to Nav2

### Task 3: Approach Distance Tuning
- **Goal**: Stop at 3 inches for pickup
- **Components**:
  - Goal calculation adjustment
  - Approach distance parameter
  - Validation testing
- **Output**: Consistent 0.0762m stopping distance

### Task 4: System Integration
- **Goal**: Unified launch and documentation
- **Components**:
  - Complete launch file
  - Parameter configuration
  - Updated documentation
- **Output**: Single-command system startup

## ROS 2 Topic Architecture

### Vision Topics (Current → Target)
- `/camera/image_raw` (sensor_msgs/Image) - Camera feed [unchanged]
- `/scan` (sensor_msgs/LaserScan) → `/detection3d_array` (vision_msgs/Detection3DArray)
- `/vision_to_laserscan/debug` → `/ros2_vision_inference/debug` (visualization)

### Navigation Topics (Unchanged)
- `/cmd_vel` (geometry_msgs/Twist) - Velocity commands
- `/odom` (nav_msgs/Odometry) - Robot odometry
- `/tf` - Transform tree
- `navigate_to_pose` action - Nav2 goal interface

## Key Improvements

### Detection Quality
| Aspect | Current (HSV) | Target (YOLO) |
|--------|---------------|---------------|
| Robustness | Lighting sensitive | Lighting independent |
| Accuracy | Pixel counting | Neural network |
| Standards | Custom messages | Detection3DArray |
| Performance | 2m+ range | Professional grade |

### System Integration
| Component | Current | Target |
|-----------|---------|---------|
| Detection | HSV thresholds | YOLO inference |
| Messages | LaserScan hack | Standard vision_msgs |
| Distance | Pixel estimation | 3D position |
| Approach | ~1.7m stop | 3-inch precision |

## Development Environment

### Platform Configuration (Unchanged)
- **OS**: Ubuntu 22.04 on WSL2
- **ROS**: ROS 2 Humble LTS
- **Simulation**: Gazebo Classic with GUI
- **Display**: VcXsrv for visualization

### New Components
- **Detection**: ros2_vision_inference package
- **Models**: YOLO weights for sports balls
- **Bridge**: Custom goal bridge node

## Design Principles

### Professional Standards
- Use existing solutions (ros2_vision_inference)
- Standard ROS 2 messages (Detection3DArray)
- Industry patterns (Nav2 integration)
- Clear interfaces and modularity

### Focused Scope
- Single ball detection only
- Simulation environment only
- 3-inch approach target
- No hardware dependencies

### Incremental Development
- Task 1: Detection working
- Task 2: Navigation connected
- Task 3: Approach tuned
- Task 4: System polished

## Performance Targets

### Detection System
- **Reliability**: Consistent ball detection
- **Latency**: <200ms detection time
- **Coverage**: Full camera FOV
- **Conditions**: Various lighting scenarios

### Navigation System
- **Approach**: 3 inches ± 0.5 inches
- **Success Rate**: >95% navigation completion
- **Smoothness**: Professional path execution
- **Safety**: Proper deceleration near target

## Testing Strategy

### Task 1 Validation
- Verify `/detection3d_array` publishes
- Confirm sports ball detection
- Check 3D position accuracy

### Task 2 Validation
- Detection triggers navigation
- Closest ball selected correctly
- Nav2 receives valid goals

### Task 3 Validation
- Measure final stop distance
- Verify 3-inch target achieved
- Test multiple approaches

### Task 4 Validation
- Single launch command works
- All components start correctly
- Complete autonomous demo

## Migration Path

### From HSV to YOLO
1. Keep HSV as fallback reference
2. Run YOLO in parallel initially
3. Compare detection quality
4. Switch goal bridge input
5. Remove HSV components

### Compatibility Maintenance
- Same Nav2 interface preserved
- Camera topics unchanged
- Robot control unmodified
- Only detection layer changes

## Future Extensibility

### Multi-Ball Support (Future)
- Detection3DArray already supports multiple
- Goal bridge can prioritize balls
- Sequential collection possible

### Hardware Deployment (Future)
- Same interfaces work on JetBot
- Model runs on Jetson Nano
- No simulation dependencies

### Advanced Features (Future)
- Different object types
- Obstacle detection
- Dynamic environments

## Summary

The ChaseBot architecture is evolving from a working HSV-based system to a professional YOLO-based detection pipeline. The upgrade maintains all proven navigation components while replacing the vision system with a robust, standard-compliant solution. The focused 4-task implementation plan ensures clear progress toward reliable 3-inch approach for golf ball pickup.

Key benefits:
- **Professional Detection**: YOLO-based neural network
- **Standard Compliance**: Detection3DArray messages
- **Precise Approach**: 3-inch stopping distance
- **Maintainability**: Clear, modular architecture

The architecture prioritizes professional standards, existing solutions, and focused scope to deliver a reliable autonomous golf ball collection system in simulation.
