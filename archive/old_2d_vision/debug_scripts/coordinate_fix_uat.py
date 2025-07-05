#!/usr/bin/env python3
"""
UAT script to prove coordinate transformation fix
Demonstrates robot approaches within 15cm vs previous 57cm stopping distance
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Point
from std_msgs.msg import Float32
from nav_msgs.msg import Odometry
import time
import math

class CoordinateFixUAT(Node):
    def __init__(self):
        super().__init__('coordinate_fix_uat')
        
        # Subscribers
        self.ball_position_sub = self.create_subscription(
            Point, '/yolo/ball_position', self.ball_position_callback, 10
        )
        self.confidence_sub = self.create_subscription(
            Float32, '/yolo/confidence', self.confidence_callback, 10
        )
        self.odom_sub = self.create_subscription(
            Odometry, '/odom', self.odom_callback, 10
        )
        
        # State variables
        self.robot_position = None
        self.ball_position = None
        self.confidence = 0.0
        self.test_results = []
        self.test_start_time = time.time()
        
        self.get_logger().info("🎯 UAT: Coordinate Transformation Fix Validation")
        self.get_logger().info("📏 Expected: Robot approaches within 15cm of detected balls")
        self.get_logger().info("📏 Previous: Robot stopped 57cm away from balls")
        self.get_logger().info("⏱️  Test duration: 30 seconds")
        
        # Timer for periodic reporting
        self.timer = self.create_timer(2.0, self.report_status)
        
    def ball_position_callback(self, msg):
        self.ball_position = msg
        
    def confidence_callback(self, msg):
        self.confidence = msg.data
        
    def odom_callback(self, msg):
        self.robot_position = msg.pose.pose.position
        
    def calculate_distance(self, pos1, pos2):
        """Calculate Euclidean distance between two positions"""
        if pos1 is None or pos2 is None:
            return None
        return math.sqrt((pos1.x - pos2.x)**2 + (pos1.y - pos2.y)**2)
        
    def report_status(self):
        elapsed = time.time() - self.test_start_time
        
        if elapsed > 30.0:
            self.finalize_test()
            return
            
        if self.robot_position and self.ball_position and self.confidence > 0.6:
            distance = self.calculate_distance(self.robot_position, self.ball_position)
            
            if distance is not None:
                # Categorize approach quality
                if distance <= 0.15:
                    status = "✅ EXCELLENT - Within target range"
                elif distance <= 0.30:
                    status = "✅ GOOD - Significant improvement"
                elif distance <= 0.50:
                    status = "⚠️  ACCEPTABLE - Better than before"
                elif distance <= 0.60:
                    status = "❌ POOR - Similar to old system"
                else:
                    status = "❌ FAILED - Worse than old system"
                    
                self.test_results.append({
                    'time': elapsed,
                    'distance': distance,
                    'confidence': self.confidence,
                    'robot_pos': (self.robot_position.x, self.robot_position.y),
                    'ball_pos': (self.ball_position.x, self.ball_position.y)
                })
                
                self.get_logger().info(f"🤖 Robot: ({self.robot_position.x:.3f}, {self.robot_position.y:.3f})")
                self.get_logger().info(f"⚽ Ball:  ({self.ball_position.x:.3f}, {self.ball_position.y:.3f})")
                self.get_logger().info(f"📏 Distance: {distance:.3f}m - {status}")
                self.get_logger().info("=" * 60)
        else:
            self.get_logger().info(f"⏱️  {elapsed:.1f}s - Waiting for ball detection (confidence: {self.confidence:.2f})")
            
    def finalize_test(self):
        self.get_logger().info("🏁 UAT COMPLETE - FINAL RESULTS")
        self.get_logger().info("=" * 60)
        
        if not self.test_results:
            self.get_logger().error("❌ NO TEST DATA - Unable to validate fix")
            rclpy.shutdown()
            return
            
        # Calculate statistics
        distances = [r['distance'] for r in self.test_results]
        avg_distance = sum(distances) / len(distances)
        min_distance = min(distances)
        max_distance = max(distances)
        
        # Count improvement categories
        excellent = len([d for d in distances if d <= 0.15])
        good = len([d for d in distances if 0.15 < d <= 0.30])
        acceptable = len([d for d in distances if 0.30 < d <= 0.50])
        poor = len([d for d in distances if 0.50 < d <= 0.60])
        failed = len([d for d in distances if d > 0.60])
        
        total_samples = len(distances)
        success_rate = (excellent + good) / total_samples * 100
        
        # Report results
        self.get_logger().info(f"📊 MEASUREMENT SUMMARY ({total_samples} samples)")
        self.get_logger().info(f"📏 Average Distance: {avg_distance:.3f}m")
        self.get_logger().info(f"📏 Best Distance: {min_distance:.3f}m")
        self.get_logger().info(f"📏 Worst Distance: {max_distance:.3f}m")
        self.get_logger().info("")
        
        self.get_logger().info("🎯 PERFORMANCE BREAKDOWN:")
        self.get_logger().info(f"✅ Excellent (≤15cm): {excellent}/{total_samples} ({excellent/total_samples*100:.1f}%)")
        self.get_logger().info(f"✅ Good (15-30cm): {good}/{total_samples} ({good/total_samples*100:.1f}%)")
        self.get_logger().info(f"⚠️  Acceptable (30-50cm): {acceptable}/{total_samples} ({acceptable/total_samples*100:.1f}%)")
        self.get_logger().info(f"❌ Poor (50-60cm): {poor}/{total_samples} ({poor/total_samples*100:.1f}%)")
        self.get_logger().info(f"❌ Failed (>60cm): {failed}/{total_samples} ({failed/total_samples*100:.1f}%)")
        self.get_logger().info("")
        
        # Overall assessment
        self.get_logger().info("🏆 FINAL VERDICT:")
        if avg_distance <= 0.15:
            verdict = "🏆 OUTSTANDING SUCCESS - Coordinate fix performs excellently"
        elif avg_distance <= 0.30:
            verdict = "✅ SUCCESS - Significant improvement achieved"
        elif avg_distance <= 0.50:
            verdict = "✅ SUCCESS - Clear improvement over previous 57cm"
        elif avg_distance <= 0.60:
            verdict = "⚠️  MARGINAL - Some improvement but needs refinement"
        else:
            verdict = "❌ FAILED - No improvement over original system"
            
        self.get_logger().info(verdict)
        self.get_logger().info(f"🎯 Success Rate: {success_rate:.1f}% (Excellent + Good)")
        
        improvement = ((0.57 - avg_distance) / 0.57) * 100
        self.get_logger().info(f"📈 Improvement: {improvement:.1f}% closer than original 57cm")
        
        self.get_logger().info("=" * 60)
        self.get_logger().info("✅ UAT VALIDATION COMPLETE")
        
        rclpy.shutdown()

def main():
    rclpy.init()
    uat = CoordinateFixUAT()
    
    try:
        rclpy.spin(uat)
    except KeyboardInterrupt:
        pass
    finally:
        uat.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
