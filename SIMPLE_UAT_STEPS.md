# JetBot Physics Fix - Simple UAT Steps

**Follow these exact steps to test if the robot moves:**

## Step 1: Open WSL2 Terminal
1. Press `Ctrl + Shift + ` ` (backtick) to open VS Code terminal
2. Type: `wsl -d Ubuntu-18.04`
3. Press Enter

## Step 2: Start the Simulation
In the WSL terminal, run these commands one by one:

```bash
cd ~/catkin_ws
source /opt/ros/melodic/setup.bash
source devel/setup.bash
roslaunch chasebot_description jetbot_gazebo.launch
```

**What you should see:**
- Gazebo GUI window will open (may take 10-20 seconds)
- Blue robot (JetBot) should appear in the middle of an empty gray world
- Terminal will show "spawning model" messages

## Step 3: Test Robot Movement
**Open a NEW terminal** (keep the first one running) and type:

```bash
wsl -d Ubuntu-18.04
cd ~/catkin_ws
source /opt/ros/melodic/setup.bash
source devel/setup.bash
python /mnt/c/workspaces/chasebot/simple_movement_test.py
```

**What you should see:**
- In the terminal: "Testing JetBot Physics Fixes..." messages
- **In Gazebo GUI: The blue robot should MOVE FORWARD then ROTATE**
- This is the visual proof the physics fix worked!

## Step 4: UAT Success Criteria
✅ **PASS**: Robot moves forward and rotates in Gazebo  
❌ **FAIL**: Robot stays at same position (0,0,0)

## If Something Goes Wrong:
- Make sure both terminals are running
- Gazebo might be slow to start - wait 20-30 seconds
- If robot doesn't appear, close Gazebo and try Step 2 again

## Expected Results:
- Robot should move forward about 0.6 meters
- Robot should then rotate in place
- No "nan" values in terminal output
- Smooth movement without jerking

**This test proves the physics configuration is fixed and the robot can move properly!**
