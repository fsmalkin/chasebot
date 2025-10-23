# ROS2 Scripts Cleanup Inventory

## Purpose
This document provides a comprehensive inventory of all scripts in ros2_scripts/ to identify what's needed, what's redundant, and what should be archived or deleted.

## Categories
- **ACTIVE**: Currently working and needed for the project
- **ARCHIVE**: Old/broken but may have historical value
- **DELETE**: True duplicates or obsolete with no value
- **UNKNOWN**: Needs testing to determine status

## YOLO Detector Scripts (7 versions!)

### 1. `ros2_yolo_detector.py`
- **Status**: ARCHIVE
- **Issue**: Subscribes to wrong topic `/camera/image_raw`
- **Replaced by**: `ros2_yolo_detector_fixed.py` and `ros2_yolo_detector_frisbee.py`
- **Action**: Move to archive/

### 2. `ros2_yolo_detector_fixed.py`
- **Status**: ARCHIVE
- **Purpose**: Fixed topic subscription to `/d415/image_raw`
- **Issue**: Superseded by frisbee version which handles the actual detection class
- **Action**: Move to archive/

### 3. `ros2_yolo_detector_frisbee.py` ⭐
- **Status**: ACTIVE - PRIMARY DETECTOR (VERBOSE)
- **Purpose**: Detects balls as frisbee (class 29) with verbose logging
- **Working**: YES - Used in test_3d_position_extraction.py
- **Required Param**: `-p input_topic:=/d415/color/image_raw`
- **Action**: KEEP for debugging

### 3b. `ros2_yolo_detector_frisbee_quiet.py` ⭐ NEW
- **Status**: ACTIVE - PRODUCTION DETECTOR
- **Purpose**: Same as frisbee.py but with reduced logging (5s summaries)
- **Working**: YES - Best for production/demos to avoid terminal flooding
- **Required Param**: `-p input_topic:=/d415/color/image_raw`
- **Action**: KEEP for production use

### 4. `ros2_yolo_detector_quiet.py`
- **Status**: ARCHIVE
- **Purpose**: Reduced logging (summaries every 5 seconds)
- **Issue**: Uses old topic `/camera/image_raw` + only looks for sports ball (class 32)
- **Action**: Move to archive/

### 5. `ros2_yolo_detector_silent.py`
- **Status**: ARCHIVE
- **Purpose**: Same as quiet but suppresses YOLO stdout output
- **Issue**: Uses old topic `/camera/image_raw` + only looks for sports ball (class 32)
- **Action**: Move to archive/ (redundant with quiet)

### 6. `ros2_yolo_detector_sports_ball.py`
- **Status**: ARCHIVE
- **Purpose**: Looks for sports ball class (32)
- **Issue**: Doesn't work because sim balls appear as frisbees
- **Action**: Move to archive/

### 7. `ros2_yolo_detector_debug.py`
- **Status**: POTENTIALLY USEFUL
- **Purpose**: Comprehensive debug output, multi-class detection (frisbee, sports ball, tennis ball)
- **Features**: Shows all detections, adjustable threshold, parameterized topic
- **Action**: Could be updated to use `/d415/color/image_raw` and kept as debug tool

## 3D Vision Scripts

### 8. `yolo_3d_position_extractor.py` ⭐
- **Status**: ACTIVE
- **Purpose**: Extracts 3D positions from YOLO detections + depth
- **Working**: YES - Core component of 3D pipeline
- **Action**: KEEP

### 9. `d415_3d_debug_viewer.py` ⭐
- **Status**: ACTIVE
- **Purpose**: GUI viewer for RGB + depth + detections
- **Working**: YES (with display bugs noted)
- **Action**: KEEP

### 10. `d415_vision_display.py`
- **Status**: UNKNOWN
- **Purpose**: Display D415 camera feed
- **Action**: Test if redundant with debug viewer

## Test Scripts

### 11. `test_3d_position_extraction.py` ⭐
- **Status**: ACTIVE
- **Purpose**: End-to-end test of 3D vision pipeline
- **Working**: YES - Just successfully tested
- **Action**: KEEP

### 12. `test_sports_ball_detection_uat.py` ⭐
- **Status**: ACTIVE
- **Purpose**: Complete working demo mentioned in docs
- **Action**: KEEP

### 13. `test_camera_topic.py` ⭐
- **Status**: ACTIVE
- **Purpose**: Essential debugging tool for camera topics
- **Action**: KEEP

### 14-22. Various test_*.py files
- **Status**: UNKNOWN
- **Files**: 
  - test_gz_controller_movement.py
  - test_gz_movement_simple.py
  - test_gz_movement.py
  - test_gz_ros2_control.py
  - test_jetbot_ignition_core.py
  - test_minimal_gz_control.py
  - test_slice_2_1_discovery.py
  - test_wheel_axis_fix.py
- **Action**: Review each for current relevance

## Monitoring/Analysis Scripts

### 23. `monitor_yolo_detections.py`
- **Status**: LIKELY ACTIVE
- **Purpose**: Monitor YOLO output
- **Action**: Test and keep if useful

### 24. `analyze_yolo_raw_detections.py`
- **Status**: LIKELY ACTIVE
- **Purpose**: Detailed analysis of detections
- **Action**: Test and keep if useful

### 25. `discover_yolo_format.py`
- **Status**: LIKELY ARCHIVE
- **Purpose**: One-time discovery tool
- **Action**: Move to archive/

### 26. `check_depth_topics.py`
- **Status**: LIKELY ACTIVE
- **Purpose**: Verify depth data availability
- **Action**: Keep if still useful for debugging

## Utility Scripts

### 27. `kill_chasebot_processes.py` ⭐
- **Status**: ACTIVE
- **Purpose**: Emergency cleanup tool
- **Action**: KEEP

### 28. `cleanup_before_launch.py` ⭐
- **Status**: ACTIVE
- **Purpose**: Pre-launch cleanup
- **Action**: KEEP

### 29. `shutdown_manager.py`
- **Status**: LIKELY ACTIVE
- **Purpose**: Auto-shutdown after timeout
- **Action**: Keep if used in launch files

## Navigation Scripts

### 30. `nav2_minimal_test.py`
- **Status**: UNKNOWN
- **Purpose**: Nav2 testing
- **Action**: Check if still relevant

### 31. `navigation_telemetry.py`
- **Status**: UNKNOWN
- **Purpose**: Navigation monitoring
- **Action**: Check if superseded

### 32. `complete_nav2_uat_demo.py`
- **Status**: UNKNOWN
- **Purpose**: Full Nav2 demo
- **Action**: Check current state

## Other Scripts

### 33-45. Remaining scripts
- Various vision, movement, and utility scripts
- Need individual assessment

## Recommended Actions

### 1. Immediate Archives (move to archive/old_detectors/)
- ros2_yolo_detector.py (broken)
- ros2_yolo_detector_fixed.py (superseded)
- ros2_yolo_detector_sports_ball.py (wrong class)
- discover_yolo_format.py (one-time use)

### 2. Create Unified Detector
Consider creating `ros2_yolo_detector_v2.0.0.py` that:
- Has configurable logging levels (verbose/quiet/silent)
- Accepts both frisbee and sports ball classes
- Uses correct topic by default
- Follows semantic versioning

### 3. Keep These Active Files
- ros2_yolo_detector_frisbee.py (verbose - for debugging)
- ros2_yolo_detector_frisbee_quiet.py (quiet - for production)
- yolo_3d_position_extractor.py
- d415_3d_debug_viewer.py
- test_3d_position_extraction.py
- test_sports_ball_detection_uat.py
- test_camera_topic.py
- kill_chasebot_processes.py
- cleanup_before_launch.py

### 4. Test These for Relevance
- All quiet/silent/debug variants
- All test_gz_* movement tests
- Navigation scripts
- Monitoring tools

## Next Steps
1. Move identified files to archive/
2. Test uncertain files
3. Update README.md with clear inventory
4. Create migration guide
5. Consider unified detector implementation
