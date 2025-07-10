# ROS2 Scripts Directory
*Auto-generated on 2025-07-09 21:13 from FILE_REGISTRY.yaml*

## 📊 Summary
- **Total Files**: 52
- **Active**: 16
- **Deprecated**: 8
- **Experimental**: 9
- **Unknown/Needs Review**: 19

## 🚀 Quick Reference

### Working YOLO Detectors
- `ros2_yolo_detector_frisbee.py (verbose)`
- `ros2_yolo_detector_frisbee_quiet.py (production)`

### Working Test Scripts
- `test_sports_ball_detection_uat.py (full demo)`
- `test_3d_position_extraction.py (3D vision)`
- `test_camera_topic.py (diagnostics)`

### Essential Tools
- `kill_chasebot_processes.py`
- `cleanup_before_launch.py`
- `yolo_3d_position_extractor.py`
- `d415_3d_debug_viewer.py`

## 📁 File Status Overview

### ✅ ACTIVE FILES

| File | Purpose | Version | Last Updated | Working Status |
|------|---------|---------|--------------|----------------|
| analyze_yolo_raw_detections.py | Detailed analysis of YOLO raw data | 1.0.0 | 2025-01-06 | N/A |
| check_depth_topics.py | Verify depth data availability | 1.0.0 | 2025-01-06 | N/A |
| cleanup_before_launch.py | Pre-launch cleanup of stale processes | 1.0.0 | 2025-01-06 | VERIFIED |
| d415_3d_debug_viewer.py | GUI viewer for RGB + depth + detections + 3D posit... | 1.0.0 | 2025-01-09 | VERIFIED |
| kill_chasebot_processes.py | Emergency cleanup of all ChaseBot processes | 1.0.0 | 2025-01-06 | VERIFIED |
| monitor_yolo_detections.py | Real-time monitoring of YOLO output | 1.0.0 | 2025-01-06 | N/A |
| ros2_simple_movement_test.py | Test basic robot movement commands | 1.0.0 | 2025-01-06 | N/A |
| ros2_yolo_detector_frisbee.py | YOLO detector accepting frisbee class (29) for sim... | 1.0.0 | 2025-01-07 | VERIFIED |
| ros2_yolo_detector_frisbee_quiet.py | Same as frisbee.py but with reduced logging (5s su... | 1.0.0 | 2025-01-09 | VERIFIED |
| shutdown_manager.py | Auto-shutdown after timeout | 1.0.0 | 2025-01-06 | N/A |
| simple_odom_publisher.py | Publish odometry data for testing | 1.0.0 | 2025-01-06 | N/A |
| test_3d_position_extraction.py | End-to-end test of 3D vision pipeline | 1.1.0 | 2025-01-09 | VERIFIED |
| test_camera_topic.py | Diagnostic tool for camera topics | 1.0.0 | 2025-01-07 | VERIFIED |
| test_sports_ball_detection_uat.py | Complete working demo for YOLO detection | 1.0.0 | 2025-01-07 | VERIFIED |
| yolo_3d_position_extractor.py | Extracts 3D positions from YOLO detections + depth... | 1.0.0 | 2025-01-09 | VERIFIED |

### ❌ DEPRECATED FILES

| File | Purpose | Replaced By | Issue |
|------|---------|-------------|-------|
| discover_yolo_format.py | One-time discovery of YOLO output format | N/A | One-time use tool |
| ros2_yolo_detector.py | Original YOLO detector | ros2_yolo_detector_frisbee.py | Subscribes to wrong topic /camera/image_... |
| ros2_yolo_detector_fixed.py | Fixed topic subscription to /d415/image_... | ros2_yolo_detector_frisbee.py | Only looks for sports ball class, not fr... |
| ros2_yolo_detector_quiet.py | Reduced logging version | ros2_yolo_detector_frisbee_quiet.py | Wrong topic + wrong class |
| ros2_yolo_detector_silent.py | Even quieter logging | ros2_yolo_detector_frisbee_quiet.py | Wrong topic + wrong class |
| ros2_yolo_detector_sports_ball.py | Looks for sports ball class (32) | N/A | Simulated balls appear as frisbees, not ... |

### 🧪 EXPERIMENTAL FILES

| File | Purpose | Version |
|------|---------|---------|
| camera_orientation_viewer.py | Debug camera orientation issues | 0.5.0 |
| complete_nav2_uat_demo.py | Full Nav2 demo | 0.5.0 |
| d415_vision_display.py | Simple D415 camera feed display | 0.5.0 |
| headless_vision_analyzer.py | Analyze vision without GUI | 0.5.0 |
| nav2_minimal_test.py | Minimal Nav2 stack testing | 0.5.0 |
| navigation_telemetry.py | Navigation monitoring and telemetry | 0.5.0 |
| ros2_fov_visualization.py | Visualize camera field of view | 0.5.0 |
| ros2_yolo_detector_debug.py | Comprehensive debug output, multi-class detection | 0.5.0 |

## 📡 Topic Reference

### Publishers
- **/cmd_vel**: ros2_simple_movement_test.py
- **/odom**: simple_odom_publisher.py
- **/yolo/ball_position**: ros2_yolo_detector_frisbee.py, ros2_yolo_detector_frisbee_quiet.py
- **/yolo/ball_position_3d**: yolo_3d_position_extractor.py
- **/yolo/confidence**: ros2_yolo_detector_frisbee.py, ros2_yolo_detector_frisbee_quiet.py
- **/yolo/debug_image**: ros2_yolo_detector_frisbee.py, ros2_yolo_detector_frisbee_quiet.py

### Subscribers
- **/d415/color/image_raw**: ros2_yolo_detector_frisbee.py, ros2_yolo_detector_frisbee_quiet.py
- **/d415/depth/camera_info**: yolo_3d_position_extractor.py
- **/d415/depth/image_raw**: yolo_3d_position_extractor.py
- **/yolo/ball_position**: yolo_3d_position_extractor.py, monitor_yolo_detections.py
- **/yolo/confidence**: yolo_3d_position_extractor.py
- **/yolo/detections**: monitor_yolo_detections.py

## 🔧 How to Use

### Running YOLO Detection
```bash
# For verbose output (debugging)
python3 ros2_yolo_detector_frisbee.py --ros-args -p use_sim_time:=true

# For quiet output (production)
python3 ros2_yolo_detector_frisbee_quiet.py --ros-args -p use_sim_time:=true
```

### Running Tests
```bash
# Full system demo
python ros2_scripts/test_sports_ball_detection_uat.py

# 3D vision test (run from Windows)
python ros2_scripts/test_3d_position_extraction.py
```

### Diagnostics
```bash
# Check camera topics
python3 test_camera_topic.py

# Monitor YOLO output
python3 monitor_yolo_detections.py
```

---
*To update this documentation, modify FILE_REGISTRY.yaml and run:*
```bash
python3 generate_documentation.py
```