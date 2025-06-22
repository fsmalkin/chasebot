#!/usr/bin/env python3
"""
Movement Test with Supervisor Position Tracking
Uses supervisor functionality to track robot position
"""

from controller import Supervisor # type: ignore

def main():
    # Initialize robot as supervisor
    robot = Supervisor()
    timestep = int(robot.getBasicTimeStep())
    print(f"Robot: {robot.getName()}")
    print(f"Timestep: {timestep}ms")
    
    # Get motors
    try:
        left_motor = robot.getDevice("left_wheel_hinge")
        right_motor = robot.getDevice("right_wheel_hinge")
        print("Motors found successfully")
    except:
        print("ERROR: Motors not found!")
        return
    
    # Configure motors for velocity control
    left_motor.setPosition(float('inf'))
    right_motor.setPosition(float('inf'))
    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)
    print("Motors configured for velocity control")
    
    # Get robot node for position tracking
    robot_node = robot.getSelf()
    if not robot_node:
        print("ERROR: Cannot get robot node")
        return
    
    translation_field = robot_node.getField("translation")
    if not translation_field:
        print("ERROR: Cannot get translation field")
        return
    
    print("Position tracking ready")
    
    def get_position():
        """Get robot position using supervisor"""
        try:
            pos = translation_field.getSFVec3f()
            return pos[0], pos[1], pos[2]
        except:
            return None, None, None
    
    def show_position(label):
        """Display current position"""
        x, y, z = get_position()
        if x is not None:
            print(f"{label}: Position = ({x:.4f}, {y:.4f}, {z:.4f})")
        else:
            print(f"{label}: Position read failed")
    
    def test_movement(name, left_vel, right_vel, duration):
        """Test movement with position tracking"""
        print(f"\n=== {name} ===")
        print(f"Left: {left_vel}, Right: {right_vel}, Duration: {duration}s")
        
        # Show starting position
        show_position("START")
        
        # Set velocities
        left_motor.setVelocity(left_vel)
        right_motor.setVelocity(right_vel)
        
        # Run for specified duration with position tracking
        start_time = robot.getTime()
        last_pos_time = start_time
        
        while robot.step(timestep) != -1:
            current_time = robot.getTime()
            elapsed = current_time - start_time
            
            # Show position every 1 second
            if current_time - last_pos_time >= 1.0:
                show_position(f"T+{elapsed:.1f}s")
                last_pos_time = current_time
            
            if elapsed >= duration:
                break
        
        # Show final position
        show_position("END")
        print(f"{name} completed")
    
    print("\nStarting movement test with supervisor position tracking...")
    show_position("INITIAL")
    
    # Test sequence with shorter durations for debugging
    test_movement("STOP", 0.0, 0.0, 1.0)
    test_movement("FORWARD", 1.0, 1.0, 3.0)
    test_movement("STOP", 0.0, 0.0, 1.0)
    test_movement("BACKWARD", -1.0, -1.0, 3.0)
    test_movement("STOP", 0.0, 0.0, 1.0)
    test_movement("TURN LEFT", -1.0, 1.0, 2.0)
    test_movement("STOP", 0.0, 0.0, 1.0)
    test_movement("TURN RIGHT", 1.0, -1.0, 2.0)
    test_movement("FINAL STOP", 0.0, 0.0, 1.0)
    
    print("\n=== MOVEMENT TEST COMPLETE ===")
    show_position("FINAL")

if __name__ == "__main__":
    main()
