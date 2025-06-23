#!/usr/bin/env python3
"""
ChaseBot ROS 2 Field of View Visualization
Shows camera field of view as lines in the 3D simulation world
"""

import rclpy
from rclpy.node import Node
import math
import tf2_ros
from geometry_msgs.msg import TransformStamped
from visualization_msgs.msg import Marker, MarkerArray
from std_msgs.msg import ColorRGBA
from geometry_msgs.msg import Point, Quaternion, Vector3
import tf_transformations

class FOVVisualization(Node):
    def __init__(self):
        super().__init__('fov_visualization')
        
        # TF2 buffer and listener for robot pose
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        
        # Publishers
        self.marker_pub = self.create_publisher(MarkerArray, '/fov_markers', 10)
        
        # Camera parameters (from JetBot URDF)
        self.camera_fov = math.radians(80.0)  # 80 degrees FOV
        self.camera_range = 3.0  # 3 meter visualization range
        self.camera_height = 0.12  # Camera height above base_link
        
        # Marker parameters
        self.marker_id = 0
        self.fov_line_count = 9  # Number of FOV boundary lines (center + 4 each side)
        
        # Timer to update FOV visualization
        self.timer = self.create_timer(0.1, self.update_fov_visualization)  # 10 Hz
        
        self.get_logger().info("FOV Visualization initialized - publishing to /fov_markers")
        self.get_logger().info("Camera FOV: {:.1f} degrees, Range: {:.1f}m".format(
            math.degrees(self.camera_fov), self.camera_range))
    
    def create_fov_markers(self, camera_transform):
        """Create visualization markers for camera field of view"""
        marker_array = MarkerArray()
        
        # Get camera position and orientation
        camera_pos = camera_transform.transform.translation
        camera_rot = camera_transform.transform.rotation
        
        # Convert quaternion to Euler angles
        euler = tf_transformations.euler_from_quaternion([
            camera_rot.x, camera_rot.y, camera_rot.z, camera_rot.w
        ])
        camera_yaw = euler[2]  # Rotation around Z-axis
        
        # Create center line marker (forward direction)
        center_marker = self.create_line_marker(
            self.marker_id,
            camera_pos,
            camera_yaw,
            0.0,  # No angle offset for center
            ColorRGBA(r=0.0, g=1.0, b=0.0, a=0.8),  # Green for center
            0.02  # Thicker line for center
        )
        marker_array.markers.append(center_marker)
        self.marker_id += 1
        
        # Create FOV boundary lines
        half_fov = self.camera_fov / 2.0
        
        # Left and right boundary lines
        for side in [-1, 1]:  # -1 for left, +1 for right
            boundary_marker = self.create_line_marker(
                self.marker_id,
                camera_pos,
                camera_yaw,
                side * half_fov,
                ColorRGBA(r=1.0, g=1.0, b=0.0, a=0.6),  # Yellow for boundaries
                0.015
            )
            marker_array.markers.append(boundary_marker)
            self.marker_id += 1
        
        # Create additional FOV grid lines
        grid_angles = [-half_fov/2, half_fov/2]  # Quarter positions
        for angle in grid_angles:
            grid_marker = self.create_line_marker(
                self.marker_id,
                camera_pos,
                camera_yaw,
                angle,
                ColorRGBA(r=0.0, g=0.8, b=1.0, a=0.4),  # Light blue for grid
                0.01
            )
            marker_array.markers.append(grid_marker)
            self.marker_id += 1
        
        # Create FOV arc at the end
        arc_marker = self.create_fov_arc(
            self.marker_id,
            camera_pos,
            camera_yaw,
            half_fov
        )
        marker_array.markers.append(arc_marker)
        self.marker_id += 1
        
        return marker_array
    
    def create_line_marker(self, marker_id, camera_pos, camera_yaw, angle_offset, color, width):
        """Create a single line marker for FOV visualization"""
        marker = Marker()
        marker.header.frame_id = "base_link"
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = "fov_lines"
        marker.id = marker_id
        marker.type = Marker.LINE_STRIP
        marker.action = Marker.ADD
        
        # Line properties
        marker.scale = Vector3(x=width, y=0.0, z=0.0)
        marker.color = color
        
        # Calculate line direction
        line_yaw = camera_yaw + angle_offset
        end_x = camera_pos.x + self.camera_range * math.cos(line_yaw)
        end_y = camera_pos.y + self.camera_range * math.sin(line_yaw)
        end_z = camera_pos.z
        
        # Create line points (start at camera, end at calculated position)
        start_point = Point(x=camera_pos.x, y=camera_pos.y, z=camera_pos.z)
        end_point = Point(x=end_x, y=end_y, z=end_z)
        
        marker.points = [start_point, end_point]
        
        return marker
    
    def create_fov_arc(self, marker_id, camera_pos, camera_yaw, half_fov):
        """Create an arc marker showing the FOV boundary"""
        marker = Marker()
        marker.header.frame_id = "base_link"
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = "fov_arc"
        marker.id = marker_id
        marker.type = Marker.LINE_STRIP
        marker.action = Marker.ADD
        
        # Arc properties
        marker.scale = Vector3(x=0.02, y=0.0, z=0.0)
        marker.color = ColorRGBA(r=1.0, g=0.5, b=0.0, a=0.7)  # Orange for arc
        
        # Create arc points
        arc_points = []
        arc_segments = 20
        for i in range(arc_segments + 1):
            # Interpolate angle from -half_fov to +half_fov
            t = i / arc_segments
            angle = camera_yaw + (-half_fov + t * 2 * half_fov)
            
            # Arc point at FOV range
            arc_x = camera_pos.x + self.camera_range * math.cos(angle)
            arc_y = camera_pos.y + self.camera_range * math.sin(angle)
            arc_z = camera_pos.z
            
            arc_points.append(Point(x=arc_x, y=arc_y, z=arc_z))
        
        marker.points = arc_points
        
        return marker
    
    def update_fov_visualization(self):
        """Update FOV visualization based on current robot pose"""
        try:
            # Get camera transform
            camera_transform = self.tf_buffer.lookup_transform(
                'base_link',
                'camera_link',
                rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=1.0)
            )
            
            # Create and publish FOV markers
            self.marker_id = 0  # Reset marker ID counter
            marker_array = self.create_fov_markers(camera_transform)
            
            self.marker_pub.publish(marker_array)
            
        except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException) as e:
            # Only log errors occasionally to avoid spam
            if hasattr(self, '_error_count'):
                self._error_count += 1
                if self._error_count % 50 == 0:  # Log every 5 seconds at 10 Hz
                    self.get_logger().warn("Could not get camera transform: {}".format(str(e)))
            else:
                self._error_count = 1
                self.get_logger().warn("Could not get camera transform: {}".format(str(e)))
    
    def destroy_markers(self):
        """Clear all FOV markers"""
        marker_array = MarkerArray()
        
        # Create delete markers
        for i in range(20):  # Clear up to 20 markers
            delete_marker = Marker()
            delete_marker.header.frame_id = "base_link"
            delete_marker.header.stamp = self.get_clock().now().to_msg()
            delete_marker.ns = "fov_lines"
            delete_marker.id = i
            delete_marker.action = Marker.DELETE
            marker_array.markers.append(delete_marker)
            
            # Also clear arc markers
            delete_arc = Marker()
            delete_arc.header.frame_id = "base_link"
            delete_arc.header.stamp = self.get_clock().now().to_msg()
            delete_arc.ns = "fov_arc"
            delete_arc.id = i
            delete_arc.action = Marker.DELETE
            marker_array.markers.append(delete_arc)
        
        self.marker_pub.publish(marker_array)

def main(args=None):
    rclpy.init(args=args)
    
    fov_viz = FOVVisualization()
    
    try:
        rclpy.spin(fov_viz)
    except KeyboardInterrupt:
        fov_viz.get_logger().info("FOV Visualization shutting down...")
    finally:
        fov_viz.destroy_markers()
        fov_viz.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
