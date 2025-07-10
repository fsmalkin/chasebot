# ChaseBot Vision Architecture

## Overview
ChaseBot uses a modular vision pipeline built on ROS 2 that combines 2D object detection with depth sensing for 3D position estimation.

## Current Implementation (YOLO + Depth)

### Architecture
```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  D415 Camera    │────▶│  YOLO Detector   │────▶│ 3D Position         │
│  - RGB Image    │     │  (YOLOv8)        │     │ Extractor           │
│  - Depth Image  │     │                  │     │                     │
└─────────────────┘     └──────────────────┘     └─────────────────────┘
         │                       │                          │
         │                       ▼                          ▼
         │              2D Ball Position            3D World Position
         │              (pixel coords)              (x,y,z meters)
         │                                                 │
         └─────────────────────────────────────────────────┘
                                │
                                ▼
                        ┌──────────────┐
                        │ Nav2 Bridge  │
                        │              │
                        └──────────────┘
                                │
                                ▼
                        Navigation Goal
```

### Components

#### 1. YOLO Detector (`ros2_yolo_detector_headless.py`)
- **Model**: YOLOv8m (ultralytics)
- **Detection**: Golf balls detected as "frisbee" (class 29)
- **Confidence**: ~0.5 threshold
- **Output**: 2D pixel coordinates and confidence scores

#### 2. 3D Position Extractor (`yolo_3d_position_extractor.py`)
- **Input**: 2D detections + depth image
- **Method**: Projects 2D pixels to 3D using camera intrinsics
- **Output**: 3D position in camera frame (meters)
- **Accuracy**: Approaches within 15cm of target

#### 3. Nav2 Bridge (`ros2_yolo_to_nav_goal_v3.0.0.py`)
- **Input**: 3D positions in camera frame
- **Transform**: Camera frame → base_link → map frame
- **Output**: Navigation goals for Nav2 stack

### Topics
- `/d415/color/image_raw` - RGB camera feed
- `/d415/depth/image_raw` - Depth data
- `/yolo/ball_position` - 2D detection (normalized coords)
- `/yolo/confidence` - Detection confidence
- `/yolo/ball_position_3d` - 3D position in camera frame
- `/move_base_simple/goal` - Navigation goals

## Alternative: ros2_vision_inference (Future Enhancement)

### Status
- **Tested**: January 10, 2025
- **Result**: Model doesn't detect golf balls
- **Decision**: Keep as future enhancement option

### Findings
- Package processes images successfully (~0.12s per frame)
- Publishes empty MarkerArray to `/mono3d/bbox`
- No parameters exposed for threshold adjustment
- Would require model retraining for golf ball detection

### When to Reconsider
- When golf ball-specific models become available
- If 3D bounding box output is needed
- For multi-class object detection requirements

## Performance Metrics

### Current YOLO + Depth Pipeline
- **Detection Rate**: 100% (when ball in view)
- **Processing Time**: ~30 FPS
- **3D Accuracy**: ±5cm at 1m distance
- **Effective Range**: 0.5m - 5.0m (optimal at 3m)

## Future Improvements
1. Train custom YOLO model specifically on golf balls
2. Implement multi-ball tracking
3. Add ball trajectory prediction
4. Integrate ros2_vision_inference when suitable models available
