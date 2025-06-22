#!/usr/bin/env python3
"""
Device Discovery Script for JetBot
Helps identify correct device names in Webots
"""

from controller import Robot

def discover_devices():
    """Discover all available devices on the robot"""
    robot = Robot()
    timestep = int(robot.getBasicTimeStep())
    
    print("=== JetBot Device Discovery ===")
    print(f"Robot name: {robot.getName()}")
    print(f"Basic timestep: {timestep}")
    
    # Try to get the number of devices
    device_count = robot.getNumberOfDevices()
    print(f"Number of devices: {device_count}")
    
    print("\nDiscovering devices:")
    
    # Common device names to try
    device_names = [
        # Motor variations
        'left wheel', 'right wheel',
        'left wheel motor', 'right wheel motor', 
        'left_wheel', 'right_wheel',
        'left_wheel_motor', 'right_wheel_motor',
        'left motor', 'right motor',
        'left_motor', 'right_motor',
        'wheel1', 'wheel2',
        'motor1', 'motor2',
        
        # Camera variations
        'camera', 'Camera', 'cam',
        
        # Other common devices
        'accelerometer', 'gyro', 'compass',
        'gps', 'lidar', 'distance sensor'
    ]
    
    found_devices = []
    
    for name in device_names:
        device = robot.getDevice(name)
        if device is not None:
            device_type = type(device).__name__
            print(f"✅ Found: '{name}' (Type: {device_type})")
            found_devices.append((name, device_type))
        else:
            print(f"❌ Not found: '{name}'")
    
    print(f"\n=== Summary ===")
    print(f"Found {len(found_devices)} devices:")
    for name, device_type in found_devices:
        print(f"  - {name}: {device_type}")
    
    # Try to discover devices by index
    print(f"\n=== Device by Index ===")
    for i in range(device_count):
        try:
            device = robot.getDeviceByIndex(i)
            if device is not None:
                name = device.getName() if hasattr(device, 'getName') else 'Unknown'
                device_type = type(device).__name__
                print(f"Index {i}: '{name}' (Type: {device_type})")
        except:
            print(f"Index {i}: Failed to get device")
    
    # Keep robot running for a moment
    robot.step(timestep)
    
    return found_devices

if __name__ == "__main__":
    discover_devices()
