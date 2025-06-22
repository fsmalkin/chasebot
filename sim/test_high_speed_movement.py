#!/usr/bin/env python3
"""
High Speed Movement Test
Test with much higher velocities to get visible movement
"""

from controller import Supervisor

def main():
    # Initialize robot as supervisor
    robot = Supervisor()
    timestep = int(robot.getBasicTimeStep())
    print(f"Robot: {robot.getName()}")
    print(f"Timestep: {timestep}ms")
    
    # Get motors
    left_motor = robot.getDevice("left_wheel_hinge")
    right_motor = robot.getDevice("right_wheel_hinge")
    print("Motors found successfully")
    
    # Configure motors for velocity control
    left_motor.setPosition(float('inf'))
    right_motor.setPosition(float('inf'))
    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)
    print("Motors configured for velocity control")
    
    # Get robot node for position tracking
    robot_node = robot.getSelf()
    translation_field = robot_node.getField("translation")
    print("Position tracking ready")
    
    def get_position():
        """Get robot position using supervisor"""
        pos = translation_field.getSFVec3f()
        return pos[0], pos[1], pos[2]
    
    def show_position(label):
        """Display current position"""
        x, y, z = get_position()
        print(f"{label}: Position = ({x:.4f}, {y:.4f}, {z:.4f})")
    
    def test_movement(name, left_vel, right_vel, duration):
        """Test movement with position tracking"""
        print(f"\n=== {name} ===")
        print(f"Left: {left_vel}, Right: {right_vel}, Duration: {duration}s")
        
        # Show starting position
        show_position("START")
        
        # Set velocities
        left_motor.setVelocity(left_vel)
        right_motor.setVelocity(right_vel)
        
        # Run for specified duration with frequent position updates
        start_time = robot.getTime()
        last_pos_time = start_time
        
        while robot.step(timestep) != -1:
            current_time = robot.getTime()
            elapsed = current_time - start_time
            
            # Show position every 0.5 seconds for better tracking
            if current_time - last_pos_time >= 0.5:
                show_position(f"T+{elapsed:.1f}s")
                last_pos_time = current_time
            
            if elapsed >= duration:
                break
        
        # Show final position
        show_position("END")
        print(f"{name} completed")
    
    print("\nStarting HIGH SPEED movement test...")
    show_position("INITIAL")
    
    # Test with much higher velocities (10x, 50x, 100x)
    test_movement("STOP", 0.0, 0.0, 1.0)
    test_movement("FORWARD 10x", 10.0, 10.0, 2.0)
    test_movement("STOP", 0.0, 0.0, 1.0)
    test_movement("FORWARD 50x", 50.0, 50.0, 2.0) 
    test_movement("STOP", 0.0, 0.0, 1.0)
    test_movement("TURN LEFT 50x", -50.0, 50.0, 1.0)
    test_movement("STOP", 0.0, 0.0, 1.0)
    
    print("\n=== HIGH SPEED TEST COMPLETE ===")
    show_position("FINAL")

if __name__ == "__main__":
    main()
