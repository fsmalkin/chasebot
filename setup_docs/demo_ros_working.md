# ChaseBot ROS Environment - Live Demonstration

## Step-by-Step Proof of Functionality

### Demo 1: Basic ROS System Check
```bash
# Open WSL Ubuntu 18.04
wsl -d "Ubuntu-18.04"

# Check ROS installation
echo "ROS Distribution: $(rosversion -d)"
echo "ROS Package Path: $ROS_PACKAGE_PATH"

# List available ROS packages (should show hundreds)
rospack list | wc -l
echo "packages installed"
```

### Demo 2: ROS Master and Node Communication
```bash
# Terminal 1: Start ROS Master
roscore

# Terminal 2: Start a test publisher node
rostopic pub /chatter std_msgs/String "data: 'Hello ChaseBot!'" -r 1

# Terminal 3: Listen to the messages
rostopic echo /chatter

# Terminal 4: See active nodes and topics
rosnode list
rostopic list
```

### Demo 3: Gazebo Simulation Launch
```bash
# Launch Gazebo with a simple world
roslaunch gazebo_ros empty_world.launch

# In another terminal, spawn a simple robot
rosservice call /gazebo/spawn_urdf_model '{model_name: test_robot, model_xml: "<?xml version=\"1.0\"?><robot name=\"test_robot\"><link name=\"base_link\"><visual><geometry><box size=\"1 1 1\"/></geometry></visual></link></robot>", robot_namespace: test, initial_pose: {position: {x: 0, y: 0, z: 1}}}'
```

### Demo 4: ROS-Gazebo Integration Test
```bash
# Check Gazebo services are available
rosservice list | grep gazebo

# Check if we can control physics
rosservice call /gazebo/pause_physics
rosservice call /gazebo/unpause_physics
```

### Demo 5: Catkin Workspace Test
```bash
# Create a simple test package
cd ~/catkin_ws/src
catkin_create_pkg chasebot_test std_msgs rospy

# Build the workspace
cd ~/catkin_ws
catkin_make

# Verify package was built
rospack find chasebot_test
