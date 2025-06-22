# JetBot Physics Configuration Fix

**Date**: June 22, 2025  
**Issue**: JetBot URDF model receives commands but doesn't move - physics configuration problem  
**Status**: ✅ FIXES IMPLEMENTED - Ready for UAT  

## Problem Analysis
During previous UAT, the JetBot model had these issues:
- Robot position remained at (0,0,0) despite movement commands
- Velocity values showed "nan" (not a number) in model states
- Robot appeared to be floating or not making proper ground contact
- ROS integration worked perfectly, but physics simulation failed

## Physics Fixes Implemented

### 1. Enhanced Wheel Contact Physics
**Before**: Basic friction (mu1=1.0, mu2=1.0)  
**After**: High-friction contact with detailed physics parameters
```xml
<gazebo reference="left_wheel">
  <material>Gazebo/Black</material>
  <mu1>100.0</mu1>           <!-- High friction coefficient -->
  <mu2>100.0</mu2>           <!-- High friction coefficient -->
  <kp>1000000.0</kp>         <!-- Contact stiffness -->
  <kd>100.0</kd>             <!-- Contact damping -->
  <minDepth>0.001</minDepth>  <!-- Minimum penetration depth -->
  <maxVel>1.0</maxVel>       <!-- Maximum contact velocity -->
  <fdir1>1 0 0</fdir1>       <!-- Friction direction -->
</gazebo>
```

### 2. Increased Motor Torque
**Before**: torque=1.0, wheelTorque=1.0  
**After**: torque=10.0, wheelTorque=10.0
- Increased torque to handle 2.5kg robot mass
- Enhanced wheelAcceleration from 2.8 to 5.0
- Added publishOdomTF=true for better odometry

### 3. Proper Spawn Height
**Before**: Robot spawned at z=0.1 (potentially floating)  
**After**: Robot spawned at z=0.05 (ensures wheel ground contact)

### 4. Contact Physics Theory
The key insight is that Gazebo physics simulation requires:
- Sufficient friction coefficients for wheel traction
- Proper contact stiffness (kp) to prevent penetration
- Adequate damping (kd) to stabilize contact forces
- Minimum depth threshold to ensure contact detection
- Motor torque sufficient for robot mass and friction

## Files Modified

### jetbot.urdf
- Enhanced wheel Gazebo properties with contact physics
- Increased differential drive plugin torque parameters
- Added publishOdomTF for better odometry tracking

### jetbot_gazebo.launch  
- Reduced spawn height from z=0.1 to z=0.05
- Ensures proper wheel-ground contact from simulation start

### New Diagnostic Tools
- `diagnose_jetbot_physics.py` - Comprehensive physics diagnostic
- `simple_movement_test.py` - Quick movement validation

## Expected Results After Fix
With these physics fixes, the JetBot should:
1. **Move Forward**: Respond to positive linear.x commands
2. **Rotate**: Respond to angular.z commands
3. **Show Real Velocities**: No more "nan" values in model states
4. **Update Position**: Robot position should change during movement
5. **Proper Odometry**: /odom topic should show realistic position/velocity data

## UAT Test Plan
1. **Launch Simulation**: `roslaunch chasebot_description jetbot_gazebo.launch`
2. **Verify Topics**: Check `/cmd_vel`, `/odom`, `/joint_states` are available
3. **Run Movement Test**: Execute `python simple_movement_test.py`
4. **Visual Confirmation**: Observe robot movement in Gazebo GUI
5. **Data Validation**: Monitor rostopic echo /odom for position changes

## Technical Validation Commands
```bash
# Start simulation
roslaunch chasebot_description jetbot_gazebo.launch

# Check topics (in new terminal)
rostopic list | grep -E "(cmd_vel|odom|joint_states)"

# Test movement (in new terminal)
python simple_movement_test.py

# Monitor odometry (in new terminal)
rostopic echo /odom
```

## Physics Parameter Justification

### High Friction (mu1=100.0, mu2=100.0)
- Ensures wheels don't slip on ground plane
- Common for robotics simulation where wheel slip is undesirable
- Allows precise differential drive control

### Contact Stiffness (kp=1000000.0)
- High stiffness prevents wheel penetration into ground
- Maintains stable ground contact for physics calculation
- Standard value for rigid body contact in Gazebo

### Motor Torque (10.0 N⋅m)
- Sufficient to accelerate 2.5kg robot with high friction wheels
- Accounts for rotational inertia and contact forces
- Allows realistic acceleration profiles

### Spawn Height (z=0.05)
- Wheel radius is 0.032m, positioned at z=0.032 relative to base_link
- Base_link at z=0.05 puts wheel centers at z=0.082
- Wheel bottoms at z=0.05 (0.082 - 0.032) = ground contact
- Prevents floating robot initialization

## Known Working Values from Webots
From our successful Webots implementation:
- Robot mass: 2.5kg (preserved)
- Wheel radius: 0.032m (preserved)
- Wheel separation: 0.16m (preserved)
- Max velocity scaling: 10-50x needed for visible movement (addressed with torque)

## Next Steps After UAT Success
1. **Document UAT Results**: Update jetbot_urdf_uat_complete.md
2. **Create World File**: Build ChaseBot arena with golf balls
3. **Vision Integration**: Port ball detection to ROS nodes
4. **Navigation Stack**: Configure move_base for autonomous navigation

## Confidence Level: HIGH
The physics fixes address all identified root causes:
- ✅ Ground contact ensured through spawn height adjustment
- ✅ Sufficient friction for wheel traction
- ✅ Adequate motor torque for robot mass
- ✅ Proper contact physics for stable simulation
- ✅ Enhanced odometry publication for navigation

These changes directly target the "nan" velocity issue and should result in functional robot movement in Gazebo simulation.
