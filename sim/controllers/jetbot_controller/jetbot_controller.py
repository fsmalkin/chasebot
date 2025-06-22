#!/usr/bin/env python3
"""
ChaseBot JetBot Controller
Phase 1: Basic vision and navigation
"""

from controller import Robot, Camera, Motor
import cv2
import numpy as np
import time

class JetBotController:
    def __init__(self):
        # Initialize robot
        self.robot = Robot()
        self.timestep = int(self.robot.getBasicTimeStep())
        
        print(f"Robot initialized: {self.robot.getName()}")
        print(f"Number of devices: {self.robot.getNumberOfDevices()}")
        
        # Discover and initialize devices
        self.discover_devices()
        
        # Control parameters
        self.max_speed = 2.0  # rad/s
        self.target_found = False
        self.target_position = None
        
        print("ChaseBot controller initialized")
    
    def discover_devices(self):
        """Discover all available devices and initialize them"""
        print("=== Device Discovery ===")
        
        # Try to find camera
        camera_names = ['camera', 'Camera', 'cam']
        self.camera = None
        for name in camera_names:
            device = self.robot.getDevice(name)
            if device is not None:
                self.camera = device
                self.camera.enable(self.timestep)
                print(f"✅ Camera found: '{name}'")
                break
        
        if self.camera is None:
            print("❌ No camera found")
        
        # Try to find motors
        motor_pairs = [
            ('left_wheel_hinge', 'right_wheel_hinge'),
            ('left wheel', 'right wheel'),
            ('left wheel motor', 'right wheel motor'),
            ('left_wheel', 'right_wheel'),
            ('left_wheel_motor', 'right_wheel_motor'),
            ('left motor', 'right motor'),
            ('left_motor', 'right_motor'),
            ('wheel1', 'wheel2'),
            ('motor1', 'motor2')
        ]
        
        self.left_motor = None
        self.right_motor = None
        
        for left_name, right_name in motor_pairs:
            left_device = self.robot.getDevice(left_name)
            right_device = self.robot.getDevice(right_name)
            
            if left_device is not None and right_device is not None:
                self.left_motor = left_device
                self.right_motor = right_device
                print(f"✅ Motors found: '{left_name}', '{right_name}'")
                
                # Set motors to velocity control
                try:
                    self.left_motor.setPosition(float('inf'))
                    self.right_motor.setPosition(float('inf'))
                    self.left_motor.setVelocity(0.0)
                    self.right_motor.setVelocity(0.0)
                    print("✅ Motors configured for velocity control")
                except Exception as e:
                    print(f"⚠️ Motor configuration error: {e}")
                break
        
        if self.left_motor is None or self.right_motor is None:
            print("❌ Motors not found")
            
        # List all devices for debugging
        print("\n=== All Devices ===")
        device_count = self.robot.getNumberOfDevices()
        for i in range(device_count):
            try:
                device = self.robot.getDeviceByIndex(i)
                if device is not None:
                    name = device.getName() if hasattr(device, 'getName') else 'Unknown'
                    device_type = type(device).__name__
                    print(f"Device {i}: '{name}' (Type: {device_type})")
            except:
                print(f"Device {i}: Failed to access")
    
    def get_camera_image(self):
        """Get current camera image as OpenCV array"""
        # Get image from camera
        raw_image = self.camera.getImage()
        if raw_image is None:
            return None
            
        # Convert to OpenCV format
        width = self.camera.getWidth()
        height = self.camera.getHeight()
        
        # Convert from Webots BGRA to OpenCV BGR
        image = np.frombuffer(raw_image, np.uint8).reshape((height, width, 4))
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        
        return image
    
    def detect_golf_balls(self, image):
        """Detect golf balls in camera image using simple color/shape detection"""
        if image is None:
            return []
        
        # Convert to HSV for better color detection
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # Define white color range for golf balls
        # Golf balls appear white/light colored
        lower_white = np.array([0, 0, 200])
        upper_white = np.array([180, 30, 255])
        
        # Create mask for white objects
        mask = cv2.inRange(hsv, lower_white, upper_white)
        
        # Apply morphological operations to clean up mask
        kernel = np.ones((5,5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        golf_balls = []
        for contour in contours:
            # Filter by area (golf balls should be reasonably sized)
            area = cv2.contourArea(contour)
            if area > 100 and area < 5000:  # Adjust based on testing
                # Get bounding rectangle
                x, y, w, h = cv2.boundingRect(contour)
                
                # Check if shape is roughly circular (aspect ratio close to 1)
                aspect_ratio = float(w) / h
                if 0.7 <= aspect_ratio <= 1.3:
                    center_x = x + w // 2
                    center_y = y + h // 2
                    golf_balls.append({
                        'center': (center_x, center_y),
                        'area': area,
                        'bbox': (x, y, w, h)
                    })
        
        return golf_balls
    
    def calculate_movement(self, target_center, image_width):
        """Calculate motor speeds based on target position"""
        if target_center is None:
            return 0.0, 0.0
        
        # Calculate error from center of image
        center_x = target_center[0]
        image_center = image_width // 2
        error = center_x - image_center
        
        # Normalize error (-1 to 1)
        normalized_error = error / (image_width // 2)
        
        # Simple proportional control
        turn_speed = normalized_error * 0.5  # Adjust gain as needed
        forward_speed = 0.3  # Base forward speed
        
        # Calculate individual motor speeds (differential drive)
        left_speed = forward_speed - turn_speed
        right_speed = forward_speed + turn_speed
        
        # Clamp speeds to max values
        left_speed = max(-self.max_speed, min(self.max_speed, left_speed))
        right_speed = max(-self.max_speed, min(self.max_speed, right_speed))
        
        return left_speed, right_speed
    
    def set_motor_speeds(self, left_speed, right_speed):
        """Set motor velocities"""
        self.left_motor.setVelocity(left_speed)
        self.right_motor.setVelocity(right_speed)
    
    def stop_robot(self):
        """Stop the robot"""
        self.set_motor_speeds(0.0, 0.0)
    
    def run(self):
        """Main control loop"""
        print("Starting ChaseBot control loop...")
        
        while self.robot.step(self.timestep) != -1:
            # Get camera image
            image = self.get_camera_image()
            
            if image is not None:
                # Detect golf balls
                golf_balls = self.detect_golf_balls(image)
                
                if golf_balls:
                    # Target the closest/largest golf ball
                    target = max(golf_balls, key=lambda x: x['area'])
                    self.target_found = True
                    self.target_position = target['center']
                    
                    # Calculate and apply movement
                    left_speed, right_speed = self.calculate_movement(
                        self.target_position, image.shape[1]
                    )
                    self.set_motor_speeds(left_speed, right_speed)
                    
                    print(f"Target found at {self.target_position}, speeds: L={left_speed:.2f}, R={right_speed:.2f}")
                    
                else:
                    # No target found, search behavior
                    self.target_found = False
                    self.set_motor_speeds(0.2, -0.2)  # Slow turn to search
                    print("No target found, searching...")
            
            # Small delay to avoid overwhelming output
            time.sleep(0.1)

# Main execution
if __name__ == "__main__":
    controller = JetBotController()
    controller.run()
