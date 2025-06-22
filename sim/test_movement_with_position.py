#!/usr/bin/env python3
"""
Movement Test with Position Tracking
Shows actual robot position to verify movement
"""

from controller import Robot, Motor, GPS
import time

def main():
    # Initialize robot
    robot = Robot()
    timestep = int(robot.getBasicTimeStep())
    print(f"Robot: {robot.getName()}")
    print(f"Timestep: {timestep}ms")
    
    # Get motors
    try:
        left_motor = robot.getDevice("left_wheel_hinge")
        right_motor = robot.getDevice("right_wheel_hinge")
        print("Motors found successfully")
    except:
        print("❌ Motors not found!")
        return
    
    # Configure motors for velocity control
    left_motor.setPosition(float('inf'))
    right_motor.setPosition(float('inf'))
    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)
    print("Motors configured for velocity control")
    
    # Try to get GPS for position tracking
    gps = None
    try:
        gps = robot.getDevice("gps")
        if gps:
            gps.enable(timestep)
            print("GPS sensor found and enabled")
        else:
            print("No GPS sensor found - will use supervisor functions")
    except:
        print("No GPS sensor found - will use supervisor functions")
    
    # Try supervisor functions for position
    supervisor_node = None
    try:
        from controller import Supervisor
        if hasattr(robot, 'getSelf'):
            supervisor_node = robot.getSelf()
            print("Supervisor mode available")
    except:
        print("Supervisor mode not available")
    
    def get_position():
        """Get robot position using available method"""
        if gps:
            try:
                pos = gps.getValues()
                return pos[0], pos[1], pos[2]
            except:
                pass
        
        if supervisor_node:
            try:
                translation_field = supervisor_node.getField("translation")
                pos = translation_field.getSFVec3f()
                return pos[0], pos[1], pos[2]
            except:
                pass
        
        return None, None, None
    
    def show_position(label):
        """Display current position"""
        x, y, z = get_position()
        if x is not None:
            print(f"{label}: Position = ({x:.4f}, {y:.4f}, {z:.4f})")
        else:
            print(f"{label}: Position tracking not available")
    
    def test_movement(name, left_vel, right_vel, duration):
        """Test movement with position tracking"""
        print(f"\n=== {name} ===")
        print(f"Left: {left_vel}, Right: {right_vel}")
        print(f"Duration: {duration}s")
        
        # Show starting position
        show_position("START")
        
        # Set velocities
        left_motor.setVelocity(left_vel)
        right_motor.setVelocity(right_vel)
        
        # Run for specified duration
        start_time = robot.getTime()
        last_pos_time = start_time
        
        while robot.step(timestep) != -1:
            current_time = robot.getTime()
            elapsed = current_time - start_time
            
            # Show position every 0.5 seconds
            if current_time - last_pos_time >= 0.5:
                show_position(f"Time: {elapsed:.1f}s")
                last_pos_time = current_time
            
            if elapsed >= duration:
                break
        
        # Show final position
        show_position("END")
        print(f"{name} completed\n")
    
    print("\nStarting movement test with position tracking...")
    show_position("INITIAL")
    
    # Test sequence
    test_movement("STOP", 0.0, 0.0, 2.0)
    test_movement("FORWARD", 1.0, 1.0, 3.0)
    test_movement("BACKWARD", -1.0, -1.0, 3.0)
    test_movement("TURN LEFT", -1.0, 1.0, 3.0)
    test_movement("TURN RIGHT", 1.0, -1.0, 3.0)
    test_movement("FINAL STOP", 0.0, 0.0, 1.0)
    
    print("=== MOVEMENT TEST COMPLETE ===")
    show_position("FINAL")

if __name__ == "__main__":
    main()
