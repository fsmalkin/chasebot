# ROS Development Standards

## Package Organization
- **chasebot_vision**: Computer vision and ball detection
- **chasebot_navigation**: Navigation and path planning integration
- **chasebot_behavior**: High-level behavior coordination and state machines
- **chasebot_bringup**: Launch files, configurations, and system coordination
- **chasebot_msgs**: Custom message and service definitions

## ROS Topic Conventions
- `/camera/image_raw` - Raw camera feed (sensor_msgs/Image)
- `/camera/camera_info` - Camera calibration (sensor_msgs/CameraInfo)
- `/ball_detections` - Detected golf balls (chasebot_msgs/BallDetectionArray)
- `/cmd_vel` - Motor control commands (geometry_msgs/Twist)
- `/odom` - Robot odometry (nav_msgs/Odometry)
- `/move_base_simple/goal` - Navigation goals (geometry_msgs/PoseStamped)

## Service Naming
- `/find_ball` - Initiate ball search behavior
- `/approach_ball` - Navigate to specific ball
- `/return_home` - Return to starting position
- `/emergency_stop` - Immediate stop command

## Parameter Organization
- **Global params**: `/chasebot/robot_name`, `/chasebot/simulation_mode`
- **Vision params**: `/chasebot/vision/detection_threshold`, `/chasebot/vision/min_ball_size`
- **Navigation params**: `/chasebot/navigation/max_velocity`, `/chasebot/navigation/goal_tolerance`

## Launch File Structure
- `chasebot_gazebo.launch` - Simulation environment
- `chasebot_hardware.launch` - Physical robot deployment
- `chasebot_vision.launch` - Vision processing nodes
- `chasebot_navigation.launch` - Navigation stack configuration

## Error Handling
- Use ROS logging (ROS_INFO, ROS_WARN, ROS_ERROR)
- Implement proper exception handling in Python nodes
- Add diagnostic publishers for system health monitoring
- Use actionlib for long-running operations with feedback

## Testing Standards
- Unit tests for individual node functionality
- Integration tests using rostest framework
- Simulation validation before hardware deployment
- **User Acceptance Testing (UAT)**: Final validation by user before marking anything complete
- Automated CI/CD pipeline for ROS package building

## UAT Requirements
- All ROS nodes must be tested by the user in their intended environment
- Navigation behaviors must be demonstrated and confirmed working
- Vision detection must be validated with real-world scenarios
- Emergency stop and safety systems must be user-tested
- **Nothing is considered complete without user confirmation that it works as expected**
