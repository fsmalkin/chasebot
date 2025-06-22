#!/usr/bin/env python3
"""
ChaseBot Simulation Setup Script
Creates JetBot world with golf balls for Phase 1 testing
"""

import os
import sys

def create_world_file():
    """Create the basic world file for JetBot golf ball collection simulation"""
    world_content = '''#VRML_SIM R2023b utf8

EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2023b/projects/objects/backgrounds/protos/TexturedBackground.proto"
EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2023b/projects/objects/backgrounds/protos/TexturedBackgroundLight.proto"
EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2023b/projects/objects/floors/protos/RectangleArena.proto"
EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2023b/projects/robots/nvidia/jetbot/protos/JetBot.proto"

WorldInfo {
  info [
    "ChaseBot Golf Ball Collection Simulation"
    "Phase 1: Basic vision and navigation testing"
  ]
  title "ChaseBot Simulation World"
  basicTimeStep 16
  contactProperties [
    ContactProperties {
      coulombFriction [
        8
      ]
      bounce 0.1
    }
  ]
}

Viewpoint {
  orientation -0.5773502691896258 0.5773502691896258 0.5773502691896258 2.0944
  position 0 0 3
  follow "JetBot"
  followSmoothness 0.01
}

TexturedBackground {
}

TexturedBackgroundLight {
}

RectangleArena {
  translation 0 0 0
  floorSize 4 4
  wallHeight 0.1
}

JetBot {
  translation 0 0 0.02
  rotation 0 0 1 0
  controller "jetbot_controller"
  supervisor TRUE
  camera_width 224
  camera_height 224
  name "ChaseBot"
}

# Golf Ball 1
Solid {
  translation 1.5 0.5 0.02
  children [
    Shape {
      appearance PBRAppearance {
        baseColor 1 1 1
        roughness 0.2
        metalness 0
      }
      geometry Sphere {
        radius 0.021
        subdivision 2
      }
    }
  ]
  name "golf_ball_1"
  boundingObject Sphere {
    radius 0.021
  }
  physics Physics {
    density -1
    mass 0.046
  }
}

# Golf Ball 2
Solid {
  translation -0.8 1.2 0.02
  children [
    Shape {
      appearance PBRAppearance {
        baseColor 1 1 1
        roughness 0.2
        metalness 0
      }
      geometry Sphere {
        radius 0.021
        subdivision 2
      }
    }
  ]
  name "golf_ball_2"
  boundingObject Sphere {
    radius 0.021
  }
  physics Physics {
    density -1
    mass 0.046
  }
}

# Golf Ball 3
Solid {
  translation -1.0 -1.0 0.02
  children [
    Shape {
      appearance PBRAppearance {
        baseColor 1 1 1
        roughness 0.2
        metalness 0
      }
      geometry Sphere {
        radius 0.021
        subdivision 2
      }
    }
  ]
  name "golf_ball_3"
  boundingObject Sphere {
    radius 0.021
  }
  physics Physics {
    density -1
    mass 0.046
  }
}

# Golf Ball 4
Solid {
  translation 0.7 -1.3 0.02
  children [
    Shape {
      appearance PBRAppearance {
        baseColor 1 1 1
        roughness 0.2
        metalness 0
      }
      geometry Sphere {
        radius 0.021
        subdivision 2
      }
    }
  ]
  name "golf_ball_4"
  boundingObject Sphere {
    radius 0.021
  }
  physics Physics {
    density -1
    mass 0.046
  }
}
'''
    
    # Create worlds directory
    worlds_dir = "worlds"
    if not os.path.exists(worlds_dir):
        os.makedirs(worlds_dir)
    
    # Write world file
    world_path = os.path.join(worlds_dir, "chasebot_world.wbt")
    with open(world_path, 'w') as f:
        f.write(world_content)
    
    print(f"✓ Created world file: {world_path}")
    return world_path

def create_controller_template():
    """Create the basic controller template for JetBot"""
    controller_content = '''#!/usr/bin/env python3
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
        
        # Initialize camera
        self.camera = self.robot.getDevice('camera')
        self.camera.enable(self.timestep)
        
        # Initialize motors
        self.left_motor = self.robot.getDevice('left wheel motor')
        self.right_motor = self.robot.getDevice('right wheel motor')
        
        # Set motors to velocity control
        self.left_motor.setPosition(float('inf'))
        self.right_motor.setPosition(float('inf'))
        self.left_motor.setVelocity(0.0)
        self.right_motor.setVelocity(0.0)
        
        # Control parameters
        self.max_speed = 2.0  # rad/s
        self.target_found = False
        self.target_position = None
        
        print("ChaseBot controller initialized")
    
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
'''
    
    # Create controllers directory
    controllers_dir = "controllers"
    if not os.path.exists(controllers_dir):
        os.makedirs(controllers_dir)
    
    # Create jetbot_controller subdirectory
    controller_dir = os.path.join(controllers_dir, "jetbot_controller")
    if not os.path.exists(controller_dir):
        os.makedirs(controller_dir)
    
    # Write controller file
    controller_path = os.path.join(controller_dir, "jetbot_controller.py")
    with open(controller_path, 'w') as f:
        f.write(controller_content)
    
    print(f"✓ Created controller: {controller_path}")
    return controller_path

def check_dependencies():
    """Check if required Python packages are available"""
    required_packages = ['opencv-python', 'numpy']
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'opencv-python':
                import cv2
            elif package == 'numpy':
                import numpy
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"⚠️  Missing required packages: {', '.join(missing_packages)}")
        print("Install with: pip install " + " ".join(missing_packages))
        return False
    else:
        print("✓ All required packages are available")
        return True

def main():
    """Main setup function"""
    print("ChaseBot Simulation Setup")
    print("=" * 40)
    
    # Check dependencies
    deps_ok = check_dependencies()
    
    # Create world file
    world_path = create_world_file()
    
    # Create controller
    controller_path = create_controller_template()
    
    print("\nSetup complete!")
    print("=" * 40)
    print(f"World file: {world_path}")
    print(f"Controller: {controller_path}")
    
    if not deps_ok:
        print("\n⚠️  Install missing packages before running simulation")
    
    print("\nTo run simulation:")
    print("1. Open Webots")
    print("2. File > Open World...")
    print(f"3. Select: {os.path.abspath(world_path)}")
    print("4. Click Play button to start simulation")

if __name__ == "__main__":
    main()
