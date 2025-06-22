#!/usr/bin/env python3
"""
Physics Diagnostic Script
Check robot physics configuration and ground contact
"""

from controller import Robot, Supervisor

def main():
    # Initialize robot as supervisor to access physics info
    robot = Supervisor()
    timestep = int(robot.getBasicTimeStep())
    
    print("Physics Diagnostic for ChaseBot")
    print("=" * 50)
    
    # Get robot node
    robot_node = robot.getSelf()
    if robot_node:
        print("OK: Robot node found")
        
        # Get translation
        translation_field = robot_node.getField("translation")
        pos = translation_field.getSFVec3f()
        print(f"Robot position: ({pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.4f})")
        
        # Check if robot has physics
        try:
            physics_field = robot_node.getField("physics")
            if physics_field:
                print("OK: Robot has physics field")
            else:
                print("ERROR: Robot missing physics field")
        except:
            print("ERROR: Error checking robot physics")
    
    # Get ground/floor information
    floor_node = robot.getFromDef("RectangleArena")
    if not floor_node:
        # Try alternative floor names
        floor_node = robot.getFromDef("FLOOR")
    if floor_node:
        print("OK: Floor node found")
    else:
        print("ERROR: Floor node not found")
    
    # Get motors and check their physics
    print("\nChecking motor physics...")
    left_motor = robot.getDevice("left_wheel_hinge")
    right_motor = robot.getDevice("right_wheel_hinge")
    
    if left_motor and right_motor:
        print("OK: Motors found")
        
        # Configure for testing
        left_motor.setPosition(float('inf'))
        right_motor.setPosition(float('inf'))
        
        print("\nTesting motor response...")
        # Set a small velocity and check motor feedback
        left_motor.setVelocity(0.1)
        right_motor.setVelocity(0.1)
        
        # Step simulation and check motor velocity
        for i in range(10):
            robot.step(timestep)
            try:
                left_vel = left_motor.getVelocity()
                right_vel = right_motor.getVelocity()
                print(f"Step {i}: Left vel: {left_vel:.3f}, Right vel: {right_vel:.3f}")
            except:
                print(f"Step {i}: Cannot read motor velocities")
        
        # Stop motors
        left_motor.setVelocity(0.0)
        right_motor.setVelocity(0.0)
    else:
        print("ERROR: Motors not found")
    
    print("\n" + "=" * 50)
    print("PHYSICS DIAGNOSTIC SUGGESTIONS:")
    print("=" * 50)
    
    if pos[2] > 0.01:
        print("WARNING: Robot is floating above ground (Z > 0.01)")
        print("   Suggestion: Lower robot or adjust wheel radius")
    
    print("Check JetBot PROTO file for:")
    print("   - Wheel contact properties")
    print("   - Robot mass and physics")
    print("   - Friction coefficients")
    print("   - Wheel-ground contact geometry")

if __name__ == "__main__":
    main()
