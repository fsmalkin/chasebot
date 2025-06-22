# ChaseBot Vision Architecture

## Overview
ChaseBot's vision system follows a modular pipeline approach: **Detection → Tracking → Navigation**, designed to leverage standard robotics patterns while maintaining flexibility for future LLM-based object classification.

## Architecture Diagram
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Camera Node   │───▶│ Object Detector │───▶│ Object Tracker  │
│ /camera/image_* │    │ OpenCV Contours │    │ Kalman Filter   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Goal Selection  │◀───│ Vision-Nav      │◀───│ Tracked Objects │
│ (Closest Ball)  │    │ Bridge Node     │    │ /tracked_objects│
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│  move_base      │    │ Behavior State  │
│ (Path Planning) │    │ Machine (SMACH) │
└─────────────────┘    └─────────────────┘
```

## Current Implementation Status

### ✅ Phase 1: Basic Object Detection (COMPLETE)
**File**: `scripts/super_simple_detector.py`
- **Input**: `/camera/image_raw` (sensor_msgs/Image)
- **Processing**: OpenCV contour analysis with binary thresholding
- **Output**: `/object_detection` (geometry_msgs/Point)
- **Status**: UAT passed - 400+ detections in 17 seconds

### 🔄 Phase 2: Enhanced Detection & Tracking (NEXT)
**Target**: Proper ROS package with object persistence

#### 2.1: Enhanced Object Detection Node
**Package**: `chasebot_vision`
**Node**: `object_detector_node.py`
- **Enhanced Detection**:
  - Bounding box calculation (cv2.boundingRect)
  - Object area and centroid calculation
  - Detection confidence scoring (geometry-based: circularity, size consistency)
  - Multiple object detection handling
  - **NO CLASSIFICATION** - treats all detected objects as "generic_object"
- **Structured Output**:
  - Custom message: `chasebot_msgs/DetectedObject`
  - Fields: id, center_x, center_y, bounding_box, area, detection_confidence
  - object_type: Always "generic_object" (classification reserved for future LLM)
  - Topic: `/detected_objects`

#### 2.2: Object Tracking Node
**Node**: `object_tracker_node.py`
**Method**: OpenCV KCF Tracker or Simple Kalman Filter
- **Features**:
  - Object persistence across frames
  - Unique ID assignment and maintenance
  - Track state (active, lost, recovered)
  - Motion prediction and smoothing
- **Output**:
  - Topic: `/tracked_objects` (chasebot_msgs/TrackedObjectArray)
  - Fields: id, position, velocity, track_age, confidence

### 🔄 Phase 3: Vision-Guided Navigation
**Package**: `chasebot_behavior`

#### 3.1: Vision-to-Navigation Bridge
**Node**: `vision_nav_bridge.py`
- **Goal Selection Logic**:
  - Priority scoring (distance, confidence, track stability)
  - Closest ball selection for simplified world
  - Future: LLM integration for semantic classification
- **Navigation Integration**:
  - Convert pixel coordinates to world coordinates
  - Publish goals to `/move_base_simple/goal`
  - Handle goal updates and cancellation

#### 3.2: Behavior Coordination
**Node**: `chase_behavior_node.py` (SMACH State Machine)
- **States**:
  - `SEARCH`: Rotate to find objects
  - `APPROACH`: Navigate to selected target
  - `CONTACT`: Final approach and contact verification
  - `RETURN`: Return to home position
- **Transitions**:
  - Object detected → APPROACH
  - Goal reached → CONTACT
  - Contact confirmed → RETURN
  - Object lost → SEARCH

## Object Classification Strategy

### Current Approach: Generic Object Detection
- **Philosophy**: Detect ANY round objects, treat as potential targets
- **Classification**: Stubbed as "generic_object" type
- **Selection**: Based on geometric properties (size, shape, position)

### Future LLM Integration
- **Detection Pipeline**: Unchanged (OpenCV contours)
- **Classification Layer**: LLM analysis of cropped object images
- **Semantic Understanding**: "golf ball", "tennis ball", "obstacle", etc.
- **Decision Making**: LLM-guided goal prioritization and task planning

## ROS Topic Architecture

### Data Flow
```
/camera/image_raw (sensor_msgs/Image)
    ↓
/detected_objects (chasebot_msgs/DetectedObjectArray)
    ↓
/tracked_objects (chasebot_msgs/TrackedObjectArray)
    ↓
/move_base_simple/goal (geometry_msgs/PoseStamped)
    ↓
/cmd_vel (geometry_msgs/Twist)
```

### Custom Messages
**chasebot_msgs/DetectedObject.msg**:
```
uint32 id
float32 center_x
float32 center_y
float32 area
float32 detection_confidence  # Geometry-based detection confidence (NOT classification)
geometry_msgs/Polygon bounding_box
string object_type           # Always "generic_object" until LLM integration
```

**chasebot_msgs/TrackedObject.msg**:
```
uint32 id
geometry_msgs/Point position
geometry_msgs/Vector3 velocity
float32 track_age
float32 confidence
string track_state  # "active", "lost", "recovered"
```

## Technical Implementation Details

### Detection Parameters
- **Minimum Area**: 100 pixels (configurable via ROS param)
- **Maximum Area**: 10,000 pixels
- **Circularity Threshold**: 0.4 (for round objects)
- **Aspect Ratio Range**: 0.7 - 1.3 (nearly square bounding boxes)

### Tracking Configuration
- **Tracker Type**: OpenCV KCF or cv2.TrackerKCF_create()
- **Update Rate**: 10 Hz (synchronized with camera)
- **Track Timeout**: 2.0 seconds without detection
- **ID Reuse**: After 5.0 seconds of track deletion

### Navigation Integration
- **Coordinate Transform**: Camera frame → base_link → map
- **Goal Distance**: 0.5m from detected object (configurable)
- **Goal Tolerance**: 0.1m position, 0.1 rad orientation
- **Safety**: Collision avoidance via move_base local planner

## Development Roadmap

### Immediate Next Steps (Phase 2.1)
1. **Package Structure Setup**:
   ```
   catkin_ws/src/chasebot_vision/
   ├── CMakeLists.txt
   ├── package.xml
   ├── nodes/
   │   └── object_detector_node.py
   ├── msg/
   │   ├── DetectedObject.msg
   │   └── DetectedObjectArray.msg
   └── launch/
       └── object_detection.launch
   ```

2. **Enhanced Detector Implementation**:
   - Convert super_simple_detector.py to proper ROS node
   - Add bounding box and confidence calculation
   - Implement structured message publishing
   - Add dynamic reconfigure for runtime tuning

3. **Integration Testing**:
   - Launch file for complete vision pipeline
   - RViz configuration for visualization
   - UAT validation with structured detection output

### Mid-term Goals (Phase 2.2 & 3)
1. **Object Tracking Integration**
2. **ROS Navigation Stack Configuration**
3. **Behavior State Machine Implementation**
4. **Multi-ball scenarios and goal prioritization**

### Long-term Vision
1. **LLM Classification Integration**
2. **Advanced behavior trees**
3. **Dynamic world mapping and navigation**
4. **Hardware deployment and real-world testing**

## Success Criteria

### Phase 2.1 Complete When:
- ✅ Enhanced detector publishes structured messages
- ✅ Multiple objects detected simultaneously
- ✅ Bounding boxes and confidence scores working
- ✅ ROS package structure follows conventions
- ✅ Dynamic reconfigure functional
- ✅ UAT passed with improved detection quality

### Phase 2.2 Complete When:
- ✅ Object tracking maintains IDs across frames
- ✅ Track state (active/lost/recovered) working
- ✅ Motion prediction smooths position estimates
- ✅ Integration with enhanced detector seamless

### Phase 3 Complete When:
- ✅ Vision-guided navigation replaces time-based approach
- ✅ Robot successfully navigates to detected balls
- ✅ Behavior state machine handles full task cycle
- ✅ Goal selection logic working for multiple targets
- ✅ Professional ROS architecture fully implemented
