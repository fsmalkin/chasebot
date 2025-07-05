#!/usr/bin/env python3
"""
Coordinate Transformation Debugger
Shows step-by-step how pixel coordinates are transformed to world coordinates
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Point, TransformStamped
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import Float32
from tf2_ros import Buffer, TransformListener
import numpy as np
import math

class CoordinateDebugger(Node):
    def __init__(self):
        super().__init__('coordinate_debugger')
        
        # TF2 setup
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        
        # Camera parameters
        self.camera_info = None
        self.image_dimensions = None
        
        # Detection data
        self.last_ball_position = None
        self.last_confidence = 0.0
        
        # Subscriptions
        self.camera_info_sub = self.create_subscription(
            CameraInfo, '/camera/camera_info', self.camera_info_callback, 10)
        
        self.image_sub = self.create_subscription(
            Image, '/camera/image_raw', self.image_callback, 10)
        
        self.ball_pos_sub = self.create_subscription(
            Point, '/yolo/ball_position', self.ball_position_callback, 10)
        
        self.confidence_sub = self.create_subscription(
            Float32, '/yolo/confidence', self.confidence_callback, 10)
        
        # Timer for debug output
        self.timer = self.create_timer(1.0, self.debug_transformation)
        
        self.get_logger().info("Coordinate Transformation Debugger Started")
        self.get_logger().info("Monitoring pixel to world coordinate transformations...")

    def camera_info_callback(self, msg):
        """Store camera calibration info"""
        self.camera_info = msg

    def image_callback(self, msg):
        """Store image dimensions"""
        self.image_dimensions = (msg.width, msg.height)

    def ball_position_callback(self, msg):
        """Store ball detection position"""
        self.last_ball_position = msg

    def confidence_callback(self, msg):
        """Store detection confidence"""
        self.last_confidence = msg.data

    def debug_transformation(self):
        """Debug the coordinate transformation process"""
        if not self.last_ball_position or self.last_confidence < 0.6:
            return
            
        if not self.camera_info or not self.image_dimensions:
            self.get_logger().warn("Waiting for camera info...")
            return
        
        print("\n" + "="*80)
        print("COORDINATE TRANSFORMATION DEBUG")
        print("="*80)
        
        # Step 1: Normalized to Pixel Coordinates
        print("\n1. NORMALIZED → PIXEL COORDINATES:")
        print(f"   Input (normalized): ({self.last_ball_position.x:.4f}, {self.last_ball_position.y:.4f})")
        print(f"   Image dimensions: {self.image_dimensions[0]} x {self.image_dimensions[1]}")
        
        pixel_x = self.last_ball_position.x * self.image_dimensions[0]
        pixel_y = self.last_ball_position.y * self.image_dimensions[1]
        print(f"   Output (pixels): ({pixel_x:.1f}, {pixel_y:.1f})")
        
        # Step 2: Camera Intrinsics
        print("\n2. CAMERA INTRINSICS:")
        K = np.array(self.camera_info.k).reshape(3, 3)
        fx, fy = K[0, 0], K[1, 1]
        cx, cy = K[0, 2], K[1, 2]
        print(f"   Focal length: fx={fx:.1f}, fy={fy:.1f}")
        print(f"   Principal point: cx={cx:.1f}, cy={cy:.1f}")
        
        # Step 3: Pixel to Camera Ray
        print("\n3. PIXEL → CAMERA RAY:")
        ray_x = (pixel_x - cx) / fx
        ray_y = (pixel_y - cy) / fy
        ray_z = 1.0
        print(f"   Unnormalized ray: ({ray_x:.4f}, {ray_y:.4f}, {ray_z:.4f})")
        
        ray_length = math.sqrt(ray_x**2 + ray_y**2 + ray_z**2)
        ray_x_norm = ray_x / ray_length
        ray_y_norm = ray_y / ray_length
        ray_z_norm = ray_z / ray_length
        print(f"   Normalized ray: ({ray_x_norm:.4f}, {ray_y_norm:.4f}, {ray_z_norm:.4f})")
        
        # Step 4: TF Lookup
        print("\n4. TRANSFORM LOOKUP:")
        try:
            transform = self.tf_buffer.lookup_transform(
                'odom', 'camera_link', rclpy.time.Time())
            
            cam_x = transform.transform.translation.x
            cam_y = transform.transform.translation.y
            cam_z = transform.transform.translation.z
            print(f"   Camera position in world: ({cam_x:.3f}, {cam_y:.3f}, {cam_z:.3f})")
            
            # Simplified quaternion to euler (assuming mostly level camera)
            q = transform.transform.rotation
            # Approximate camera pitch (assuming no roll)
            pitch = math.asin(2 * (q.w * q.y - q.z * q.x))
            yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
            print(f"   Camera rotation: pitch={math.degrees(pitch):.1f}°, yaw={math.degrees(yaw):.1f}°")
            
        except Exception as e:
            print(f"   Transform lookup failed: {e}")
            return
        
        # Step 5: Ground Intersection
        print("\n5. GROUND PLANE INTERSECTION:")
        ground_height = 0.02  # Ball radius
        print(f"   Ground height: {ground_height:.3f}m")
        print(f"   Camera height: {cam_z:.3f}m")
        
        # Simplified calculation assuming level camera
        if ray_y_norm <= 0:
            print("   ERROR: Ray points upward, cannot intersect ground!")
            return
            
        t = (cam_z - ground_height) / ray_y_norm
        print(f"   Ray parameter t: {t:.3f}m")
        
        # Step 6: World Position
        print("\n6. WORLD POSITION CALCULATION:")
        world_x = cam_x + t * ray_z_norm
        world_y = cam_y - t * ray_x_norm  # Negative because camera X is robot -Y
        world_z = ground_height
        print(f"   Ball world position: ({world_x:.3f}, {world_y:.3f}, {world_z:.3f})")
        
        # Step 7: Distance Calculation
        print("\n7. DISTANCE CALCULATIONS:")
        try:
            robot_tf = self.tf_buffer.lookup_transform(
                'odom', 'base_link', rclpy.time.Time())
            robot_x = robot_tf.transform.translation.x
            robot_y = robot_tf.transform.translation.y
            
            distance = math.sqrt((world_x - robot_x)**2 + (world_y - robot_y)**2)
            print(f"   Robot position: ({robot_x:.3f}, {robot_y:.3f})")
            print(f"   Distance to ball: {distance:.3f}m")
            
            # Navigation goal calculation
            approach_distance = 0.15
            if distance > approach_distance:
                scale = (distance - approach_distance) / distance
                goal_x = robot_x + (world_x - robot_x) * scale
                goal_y = robot_y + (world_y - robot_y) * scale
                print(f"\n8. NAVIGATION GOAL:")
                print(f"   Approach distance: {approach_distance:.3f}m")
                print(f"   Goal position: ({goal_x:.3f}, {goal_y:.3f})")
                print(f"   Expected final distance: {approach_distance:.3f}m")
            
        except Exception as e:
            print(f"   Robot transform lookup failed: {e}")
        
        print("\n" + "="*80)

def main(args=None):
    rclpy.init(args=args)
    node = CoordinateDebugger()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
