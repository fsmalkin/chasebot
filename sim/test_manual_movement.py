#!/usr/bin/env python3
"""
Manual Robot Movement Test
Simple test to verify motor control works
"""

from controller import Robot, Motor # type: ignore
import time

def test_movement():
    # Initialize robot
    robot = Robot()
    timestep = int(robot.getBasicTimeStep())
    
    print("Starting manual movement test...")
    print(f"Robot: {robot.getName()}")
    print(f"Timestep: {timestep}ms")
    
    # Get motors
    left_motor = robot.getDevice('left_wheel_hinge')
    right_motor = robot.getDevice('right_wheel_hinge')
    
    if left_motor is None or right_motor is None:
        print("ERROR: Motors not found!")
        return
    
    print("Motors found successfully")
    
    # Set motors to velocity control
    left_motor.setPosition(float('inf'))
    right_motor.setPosition(float('inf'))
    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)
    
    print("Motors configured for velocity control")
    
    # Test sequence
    tests = [
        ("STOP", 0.0, 0.0, 2.0),
        ("FORWARD", 1.0, 1.0, 3.0),
        ("STOP", 0.0, 0.0, 1.0),
        ("BACKWARD", -1.0, -1.0, 3.0),
        ("STOP", 0.0, 0.0, 1.0),
        ("TURN LEFT", -0.5, 0.5, 3.0),
        ("STOP", 0.0, 0.0, 1.0),
        ("TURN RIGHT", 0.5, -0.5, 3.0),
        ("STOP", 0.0, 0.0, 1.0),
    ]
    
    for test_name, left_speed, right_speed, duration in tests:
        print(f"\n=== {test_name} ===")
        print(f"Left: {left_speed}, Right: {right_speed}")
        print(f"Duration: {duration}s")
        
        # Set motor speeds
        left_motor.setVelocity(left_speed)
        right_motor.setVelocity(right_speed)
        
        # Run for specified duration
        start_time = robot.getTime()
        while robot.step(timestep) != -1:
            current_time = robot.getTime()
            if current_time - start_time >= duration:
                break
            print(f"Time: {current_time - start_time:.2f}s", end="\r")
        
        print(f"\n{test_name} completed")
    
    print("\n=== FINAL STOP ===")
    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)
    
    print("Manual movement test complete!")

if __name__ == "__main__":
    test_movement()
