#!/usr/bin/env python3
"""
Device Discovery Script
Find all available devices on the JetBot
"""

from controller import Robot # type: ignore

def main():
    # Initialize robot
    robot = Robot()
    timestep = int(robot.getBasicTimeStep())
    
    print(f"Robot: {robot.getName()}")
    print(f"Timestep: {timestep}ms")
    print("=" * 50)
    print("DISCOVERING ALL DEVICES...")
    print("=" * 50)
    
    # Get number of devices
    device_count = robot.getNumberOfDevices()
    print(f"Total devices found: {device_count}")
    print()
    
    # List all devices
    for i in range(device_count):
        device = robot.getDeviceByIndex(i)
        device_name = device.getName()
        device_type = device.getNodeType()
        print(f"Device {i:2d}: '{device_name}' (Type: {device_type})")
    
    print("=" * 50)
    print("TESTING COMMON MOTOR NAMES...")
    print("=" * 50)
    
    # Test common motor names
    motor_names_to_test = [
        "left wheel motor",
        "right wheel motor", 
        "left_wheel_motor",
        "right_wheel_motor",
        "left motor",
        "right motor",
        "left_motor", 
        "right_motor",
        "wheel1",
        "wheel2",
        "motor1",
        "motor2",
        "left",
        "right"
    ]
    
    for name in motor_names_to_test:
        try:
            device = robot.getDevice(name)
            if device:
                print(f"✅ FOUND: '{name}'")
            else:
                print(f"❌ NOT FOUND: '{name}'")
        except:
            print(f"❌ ERROR: '{name}'")
    
    print("=" * 50)
    print("Device discovery complete!")

if __name__ == "__main__":
    main()
