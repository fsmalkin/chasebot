#!/usr/bin/env python3
"""
ROS 2 YOLO Frisbee Detection Node - Quiet Version
Accepts frisbee detections (class 29) with reduced logging
Only logs summaries every 5 seconds instead of every detection
"""

import os
import time

import cv2
import rclpy
import torch
from cv_bridge import CvBridge
from geometry_msgs.msg import Point
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Float32
from ultralytics import YOLO

class YOLOFrisbeeDetectorNode(Node):
    def __init__(self):
        super().__init__('yolo_frisbee_detector')
        
        # Declare parameters
        self.declare_parameter('input_topic', '/d415/color/image_raw')
        self.declare_parameter('confidence_threshold', 0.5)
        self.declare_parameter('log_interval', 5.0)  # Log summary interval in seconds
        self.declare_parameter('inference_device', 'auto')
        self.declare_parameter('require_gpu', False)
        self.declare_parameter('show_window', True)
        self.declare_parameter('headless', False)
        self.declare_parameter('perf_profile', 'balanced')
        self.declare_parameter('performance_profile', 'balanced')
        self.declare_parameter('target_classes', [29, 32])
        self.declare_parameter('compat_include_stop_sign_class', False)
        self.declare_parameter('bbox_vertical_anchor', 0.85)
        self.declare_parameter('model_path', '')
        self.declare_parameter('imgsz', 0)
        self.declare_parameter('image_queue_depth', 10)
        self.declare_parameter('cpu_num_threads', 0)
        self.declare_parameter('cpu_num_interop_threads', 0)
        self.declare_parameter('enable_sim_red_fallback', False)
        self.declare_parameter('red_fallback_min_area_px', 8)
        self.declare_parameter('red_fallback_confidence', 0.35)
        
        # Get parameters
        input_topic = self.get_parameter('input_topic').value
        self.CONFIDENCE_THRESHOLD = self.get_parameter('confidence_threshold').value
        self.log_interval = self.get_parameter('log_interval').value
        requested_device = self.get_parameter('inference_device').value
        require_gpu = self.get_parameter('require_gpu').value
        self.show_window = self.get_parameter('show_window').value
        headless = self.get_parameter('headless').value
        self.perf_profile = self.get_parameter('perf_profile').value
        legacy_perf_profile = self.get_parameter('performance_profile').value
        target_classes_raw = self.get_parameter('target_classes').value
        compat_include_stop_sign = bool(
            self.get_parameter('compat_include_stop_sign_class').value
        )
        self.bbox_vertical_anchor = float(self.get_parameter('bbox_vertical_anchor').value)
        model_path_override = str(self.get_parameter('model_path').value).strip()
        requested_imgsz = int(self.get_parameter('imgsz').value)
        queue_depth = int(self.get_parameter('image_queue_depth').value)
        cpu_num_threads = int(self.get_parameter('cpu_num_threads').value)
        cpu_num_interop_threads = int(self.get_parameter('cpu_num_interop_threads').value)
        self.enable_sim_red_fallback = bool(
            self.get_parameter('enable_sim_red_fallback').value
        )
        self.red_fallback_min_area_px = max(
            1,
            int(self.get_parameter('red_fallback_min_area_px').value),
        )
        self.red_fallback_confidence = max(
            0.0,
            min(1.0, float(self.get_parameter('red_fallback_confidence').value)),
        )
        self.bbox_vertical_anchor = max(0.0, min(self.bbox_vertical_anchor, 1.0))
        if not self.perf_profile:
            self.perf_profile = legacy_perf_profile
        if self.perf_profile not in ('compat', 'balanced', 'max'):
            self.get_logger().warn(
                f'Unsupported perf_profile "{self.perf_profile}". Falling back to "balanced".'
            )
            self.perf_profile = 'balanced'
        if headless:
            self.show_window = False

        cuda_available = torch.cuda.is_available()
        if requested_device == 'auto':
            self.inference_device = 'cuda:0' if cuda_available else 'cpu'
        elif requested_device.startswith('cuda') and not cuda_available:
            if require_gpu:
                raise RuntimeError('CUDA requested but not available and require_gpu=true')
            self.get_logger().warn('CUDA requested but unavailable. Falling back to CPU.')
            self.inference_device = 'cpu'
        else:
            self.inference_device = requested_device

        if requested_imgsz > 0:
            self.inference_imgsz = requested_imgsz
        elif self.perf_profile == 'compat':
            self.inference_imgsz = 416
        else:
            self.inference_imgsz = 0

        queue_depth = max(1, queue_depth)
        if self.perf_profile == 'compat':
            queue_depth = 1
        self.image_queue_depth = queue_depth

        if self.inference_device == 'cpu' and self.perf_profile == 'compat':
            cpu_count = os.cpu_count() or 4
            if cpu_num_threads <= 0:
                cpu_num_threads = min(4, max(1, cpu_count // 2))
            if cpu_num_interop_threads <= 0:
                cpu_num_interop_threads = 1
            try:
                torch.set_num_threads(cpu_num_threads)
            except Exception:
                pass
            try:
                torch.set_num_interop_threads(cpu_num_interop_threads)
            except Exception:
                pass
            self.get_logger().info(
                f'Compat CPU threading: num_threads={cpu_num_threads}, '
                f'num_interop_threads={cpu_num_interop_threads}'
            )
        
        # Initialize CV Bridge
        self.bridge = CvBridge()
        
        # Load YOLO model
        model_candidates = ['yolov8m.pt']
        if self.perf_profile == 'compat':
            model_candidates = ['yolov8m.pt', 'yolov8n.pt']

        if model_path_override:
            model_path = os.path.expanduser(model_path_override)
        else:
            model_path = ''
            for model_name in model_candidates:
                for candidate in (
                    os.path.expanduser(f'~/ros2_ws/{model_name}'),
                    os.path.expanduser(f'~/ros2_ws/src/chasecar_runtime/{model_name}'),
                    os.path.expanduser(f'~/ros2_ws/src/chasecar/{model_name}'),
                    os.path.expanduser(f'~/ros2_ws/src/chasebot_description/{model_name}'),
                    model_name,
                ):
                    if os.path.exists(candidate):
                        model_path = candidate
                        break
                if model_path:
                    break
            if not model_path:
                model_path = model_candidates[0]
            
        self.get_logger().info(f'Loading YOLO model from: {model_path}')
        try:
            self.model = YOLO(model_path)
            self.get_logger().info('YOLO model loaded successfully')
        except Exception as e:
            self.get_logger().error(f'Failed to load YOLO model: {e}')
            return
        
        # COCO class for frisbee (our simulated balls appear as frisbees)
        if isinstance(target_classes_raw, list):
            classes = [int(c) for c in target_classes_raw]
        else:
            classes = [int(target_classes_raw)]
        if not classes:
            classes = [29, 32]
        if self.perf_profile == 'compat':
            # Optional compat override for occasional close-range class drift.
            if compat_include_stop_sign and 11 not in classes:
                classes.append(11)
            if self.CONFIDENCE_THRESHOLD > 0.10:
                self.get_logger().info(
                    f'Compat profile lowering confidence threshold '
                    f'from {self.CONFIDENCE_THRESHOLD:.2f} to 0.10'
                )
                self.CONFIDENCE_THRESHOLD = 0.10
        self.target_classes = set(classes)
        
        # Publishers
        self.debug_image_pub = self.create_publisher(Image, '/yolo/debug_image', 10)
        self.detection_pub = self.create_publisher(Point, '/yolo/ball_position', 10)
        self.confidence_pub = self.create_publisher(Float32, '/yolo/confidence', 10)
        self.inference_ms_pub = self.create_publisher(Float32, '/yolo/inference_ms', 10)
        self.camera_to_debug_ms_pub = self.create_publisher(Float32, '/yolo/camera_to_debug_ms', 10)
        
        # Subscriber
        self.image_sub = self.create_subscription(
            Image,
            input_topic,
            self.image_callback,
            self.image_queue_depth
        )
        
        # Debug window
        self.window_name = 'YOLO Ball Detection (Frisbee) - Quiet'
        
        # Logging control variables
        self.last_log_time = time.time()
        self.frame_count = 0
        self.detection_count = 0
        self.frames_with_detection = 0
        self.estimated_dropped_frames = 0
        self.last_frame_time = None
        self.last_confidence = 0.0
        self.confidence_change_threshold = 0.1  # Log if confidence changes by 10%
        self.max_confidence_seen = 0.0
        self.min_confidence_seen = 1.0
        self.total_inference_ms = 0.0
        self.max_inference_ms = 0.0
        
        self.get_logger().info('='*50)
        self.get_logger().info('YOLO Ball Detection Node Started (Quiet Mode)')
        self.get_logger().info(f'Subscribing to: {input_topic}')
        self.get_logger().info(f'Confidence threshold: {self.CONFIDENCE_THRESHOLD}')
        self.get_logger().info(f'Looking for classes: {sorted(self.target_classes)}')
        self.get_logger().info(f'Summaries every {self.log_interval} seconds')
        self.get_logger().info(f'Inference device: {self.inference_device} (requested: {requested_device})')
        self.get_logger().info(f'Performance profile: {self.perf_profile}')
        self.get_logger().info(f'Inference image size: {self.inference_imgsz if self.inference_imgsz > 0 else "default"}')
        self.get_logger().info(f'Image queue depth: {self.image_queue_depth}')
        self.get_logger().info(f'Sim red fallback: {self.enable_sim_red_fallback}')
        self.get_logger().info(f'Headless mode: {headless}')
        self.get_logger().info(f'Debug window enabled: {self.show_window}')
        self.get_logger().info('='*50)

    def detect_red_blob(self, cv_image):
        hsv = cv2.cvtColor(cv_image, cv2.COLOR_BGR2HSV)
        lower_red_1 = (0, 80, 60)
        upper_red_1 = (12, 255, 255)
        lower_red_2 = (170, 80, 60)
        upper_red_2 = (180, 255, 255)
        mask1 = cv2.inRange(hsv, lower_red_1, upper_red_1)
        mask2 = cv2.inRange(hsv, lower_red_2, upper_red_2)
        mask = cv2.bitwise_or(mask1, mask2)
        mask = cv2.GaussianBlur(mask, (5, 5), 0)
        _, mask = cv2.threshold(mask, 80, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        best = max(contours, key=cv2.contourArea)
        area = float(cv2.contourArea(best))
        if area < float(self.red_fallback_min_area_px):
            return None

        x, y, w, h = cv2.boundingRect(best)
        center_x = float(x + (w / 2.0))
        center_y = float(y + (h * self.bbox_vertical_anchor))
        return {
            'bbox': (int(x), int(y), int(x + w), int(y + h)),
            'center': (center_x, center_y),
            'confidence': float(self.red_fallback_confidence),
            'class_id': -1,
            'class_name': 'sim_red_blob',
        }
        
    def image_callback(self, msg):
        try:
            self.frame_count += 1
            now_sec = self.get_clock().now().nanoseconds / 1e9
            if self.last_frame_time is not None:
                delta = now_sec - self.last_frame_time
                expected = 1.0 / 30.0
                if delta > expected * 1.5:
                    self.estimated_dropped_frames += max(0, int(round(delta / expected) - 1))
            self.last_frame_time = now_sec
            
            # Convert ROS image to OpenCV
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            
            # Run YOLO detection
            inference_start = time.perf_counter()
            predict_kwargs = {
                'source': cv_image,
                'verbose': False,
                'device': self.inference_device,
            }
            if self.inference_imgsz > 0:
                predict_kwargs['imgsz'] = self.inference_imgsz
            results = self.model.predict(**predict_kwargs)
            inference_ms = (time.perf_counter() - inference_start) * 1000.0
            self.total_inference_ms += inference_ms
            self.max_inference_ms = max(self.max_inference_ms, inference_ms)
            inference_ms_msg = Float32()
            inference_ms_msg.data = float(inference_ms)
            self.inference_ms_pub.publish(inference_ms_msg)
            
            # Process detections
            detected_balls = []
            
            for r in results:
                boxes = r.boxes
                if boxes is not None:
                    for box in boxes:
                        # Get detection info
                        class_id = int(box.cls)
                        confidence = float(box.conf)
                        
                        # Keep detections for configured target classes.
                        if class_id in self.target_classes and confidence >= self.CONFIDENCE_THRESHOLD:
                            # Get bounding box coordinates
                            x1, y1, x2, y2 = box.xyxy[0].tolist()
                            
                            # Use bottom-biased anchor for depth sampling robustness.
                            center_x = (x1 + x2) / 2
                            center_y = y1 + ((y2 - y1) * self.bbox_vertical_anchor)
                            
                            detected_balls.append({
                                'bbox': (int(x1), int(y1), int(x2), int(y2)),
                                'center': (center_x, center_y),
                                'confidence': confidence,
                                'class_id': class_id,
                            })
                            
                            self.detection_count += 1
                            
                            # Update confidence statistics
                            self.max_confidence_seen = max(self.max_confidence_seen, confidence)
                            self.min_confidence_seen = min(self.min_confidence_seen, confidence)

            if not detected_balls and self.enable_sim_red_fallback:
                fallback_ball = self.detect_red_blob(cv_image)
                if fallback_ball is not None:
                    detected_balls.append(fallback_ball)
                    self.detection_count += 1
                    confidence = float(fallback_ball['confidence'])
                    self.max_confidence_seen = max(self.max_confidence_seen, confidence)
                    self.min_confidence_seen = min(self.min_confidence_seen, confidence)
            
            # Track frames with detections
            if detected_balls:
                self.frames_with_detection += 1
            
            # Draw debug image
            debug_image = cv_image.copy()
            
            # Draw detected balls
            for ball in detected_balls:
                x1, y1, x2, y2 = ball['bbox']
                confidence = ball['confidence']
                class_id = ball['class_id']
                if class_id >= 0:
                    class_name = self.model.names.get(class_id, str(class_id))
                else:
                    class_name = ball.get('class_name', str(class_id))
                
                # Draw green rectangle with thicker lines
                cv2.rectangle(debug_image, (x1, y1), (x2, y2), (0, 255, 0), 3)
                
                # Draw center point
                center = (int(ball['center'][0]), int(ball['center'][1]))
                cv2.circle(debug_image, center, 5, (0, 0, 255), -1)
                
                # Add confidence text with background
                label = f'Ball ({class_name}): {confidence:.2f}'
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                cv2.rectangle(debug_image, 
                             (x1, y1 - label_size[1] - 10),
                             (x1 + label_size[0], y1),
                             (0, 255, 0), -1)
                cv2.putText(debug_image, label, (x1, y1 - 5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
            
            # Add status info
            status_color = (0, 255, 0) if detected_balls else (0, 0, 255)
            cv2.putText(debug_image, f'Frame: {self.frame_count}', (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(debug_image, f'Balls Detected: {len(detected_balls)}', (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
            cv2.putText(debug_image, f'Threshold: {self.CONFIDENCE_THRESHOLD}', (10, 90), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(debug_image, 'Quiet mode - reduced logging', (10, 120), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            
            # Publish debug image
            debug_msg = self.bridge.cv2_to_imgmsg(debug_image, encoding='bgr8')
            debug_msg.header = msg.header
            self.debug_image_pub.publish(debug_msg)
            
            # Publish detection data for highest confidence ball
            if detected_balls:
                # Get highest confidence ball
                best_ball = max(detected_balls, key=lambda x: x['confidence'])
                
                # Publish normalized position (0-1 range)
                position_msg = Point()
                position_msg.x = best_ball['center'][0] / cv_image.shape[1]
                position_msg.y = best_ball['center'][1] / cv_image.shape[0]
                position_msg.z = 0.0
                self.detection_pub.publish(position_msg)
                
                # Publish confidence
                confidence_msg = Float32()
                confidence_msg.data = best_ball['confidence']
                self.confidence_pub.publish(confidence_msg)
                
                # Log significant confidence changes only
                current_confidence = best_ball['confidence']
                if abs(current_confidence - self.last_confidence) > self.confidence_change_threshold:
                    self.get_logger().info(
                        f'Confidence changed significantly: {current_confidence:.3f} '
                        f'(was {self.last_confidence:.3f})'
                    )
                    self.last_confidence = current_confidence
            else:
                # Explicitly clear confidence when no detection is present.
                confidence_msg = Float32()
                confidence_msg.data = 0.0
                self.confidence_pub.publish(confidence_msg)
            
            header_time_sec = msg.header.stamp.sec + (msg.header.stamp.nanosec / 1e9)
            camera_to_debug_ms = (now_sec - header_time_sec) * 1000.0
            delay_msg = Float32()
            delay_msg.data = float(camera_to_debug_ms)
            self.camera_to_debug_ms_pub.publish(delay_msg)

            # Show debug window
            if self.show_window:
                cv2.imshow(self.window_name, debug_image)
                key = cv2.waitKey(1)
                
                # Allow threshold adjustment with keys
                if key == ord('+') or key == ord('='):
                    self.CONFIDENCE_THRESHOLD = min(0.9, self.CONFIDENCE_THRESHOLD + 0.05)
                    self.get_logger().info(f'Increased threshold to: {self.CONFIDENCE_THRESHOLD:.2f}')
                elif key == ord('-'):
                    self.CONFIDENCE_THRESHOLD = max(0.1, self.CONFIDENCE_THRESHOLD - 0.05)
                    self.get_logger().info(f'Decreased threshold to: {self.CONFIDENCE_THRESHOLD:.2f}')
                elif key == ord('q'):
                    self.get_logger().info('User requested quit')
                    rclpy.shutdown()
            
            # Periodic summary logging
            current_time = time.time()
            if current_time - self.last_log_time >= self.log_interval:
                if self.frame_count > 0:
                    detection_rate = (self.frames_with_detection / self.frame_count) * 100
                    avg_detections_per_frame = self.detection_count / self.frame_count
                    
                    self.get_logger().info('='*50)
                    self.get_logger().info(
                        f'Detection Summary ({self.log_interval}s interval):'
                    )
                    self.get_logger().info(
                        f'   Frames processed: {self.frame_count}'
                    )
                    self.get_logger().info(
                        f'   Total detections: {self.detection_count} '
                        f'({avg_detections_per_frame:.1f} per frame)'
                    )
                    self.get_logger().info(
                        f'   Detection rate: {detection_rate:.1f}% of frames had detections'
                    )
                    if self.frame_count > 0:
                        avg_inference_ms = self.total_inference_ms / self.frame_count
                        self.get_logger().info(
                            f'   Inference: avg={avg_inference_ms:.1f}ms max={self.max_inference_ms:.1f}ms'
                        )
                    self.get_logger().info(
                        f'   Estimated dropped camera frames: {self.estimated_dropped_frames}'
                    )
                    if self.detection_count > 0:
                        self.get_logger().info(
                            f'   Confidence range: {self.min_confidence_seen:.3f} - {self.max_confidence_seen:.3f}'
                        )
                    self.get_logger().info('='*50)
                
                # Reset counters
                self.last_log_time = current_time
                self.frame_count = 0
                self.detection_count = 0
                self.frames_with_detection = 0
                self.max_confidence_seen = 0.0
                self.min_confidence_seen = 1.0
                self.total_inference_ms = 0.0
                self.max_inference_ms = 0.0
                self.estimated_dropped_frames = 0
                
        except Exception as e:
            self.get_logger().error(f'Error in image callback: {e}')
            import traceback
            self.get_logger().error(traceback.format_exc())

def main(args=None):
    rclpy.init(args=args)
    
    try:
        node = YOLOFrisbeeDetectorNode()
        node.get_logger().info('Press +/- to adjust confidence threshold, Q to quit (window mode only)')
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
