# ChaseBot Repository Cleanup Plan

## Overview
With the pivot to Intel RealSense D415 3D camera, many files related to 2D coordinate transformations are now obsolete. This document tracks the cleanup process.

## Files to Archive

### Obsolete Coordinate Transform Scripts
These attempted to solve the pixel-to-world conversion problem:
- `ros2_scripts/ros2_yolo_to_nav_goal.py` - Original broken implementation
- `ros2_scripts/ros2_yolo_to_nav_goal_fixed.py` - Failed fix attempt  
- `ros2_scripts/ros2_yolo_to_nav_goal_corrected.py` - Still broken (treats pixels as meters)
- `ros2_scripts/ros2_yolo_to_nav_goal_v1.0.0.py` - Version 1.0.0
- `ros2_scripts/ros2_yolo_to_nav_goal_v1.1.0.py` - Version 1.1.0
- `ros2_scripts/ros2_yolo_to_nav_goal_v1.2.0.py` - Version 1.2.0
- `ros2_scripts/ros2_yolo_to_nav_goal_v2.0.0.py` - Version 2.0.0

### Debug/Diagnostic Scripts  
These were created to debug the 2D coordinate issues:
- `ros2_scripts/coordinate_transformation_debug.py` - Transform debugger
- `ros2_scripts/position_diagnostics.py` - Position analyzer
- `ros2_scripts/coordinate_fix_uat.py` - UAT test script
- `ros2_scripts/visual_detection_overlay.py` - Debug overlay (may keep for 3D)

### Telemetry Scripts
Recent additions that may still be useful:
- `ros2_scripts/navigation_telemetry.py` - Keep (useful for any system)
- `ros2_scripts/direct_ball_follower_with_telemetry.py` - Archive (2D based)
- `ros2_scripts/direct_follower_with_3d_viz.py` - Archive (misleading name, still 2D)
- `ros2_scripts/simple_direct_approach.py` - Archive (2D workaround)

### Test Scripts
- `test_direct_follower.sh` - Archive
- `test_direct_follower_clean.sh` - Archive  
- `test_direct_follower_simple.sh` - Archive
- `test_3d_follower.sh` - Archive (misleading name, actually 2D)

### Documentation to Update
- `docs/CRITICAL_COORDINATE_BUG_FOUND.md` - Add note about 3D solution
- `docs/CURRENT_STATE_ANALYSIS_2025_07_04.md` - Add deprecation notice
- `docs/yolo_nav_bridge_versions.md` - Mark all as obsolete
- `docs/telemetry_*.md` - Review for 2D-specific content

## New Directory Structure

```
chasebot/
├── archive/
│   └── old_2d_vision/           # All 2D coordinate transform attempts
│       ├── bridges/             # Various nav goal bridges
│       ├── debug_scripts/       # Coordinate debugging tools
│       ├── telemetry/          # 2D-specific telemetry
│       └── docs/               # Outdated documentation
├── ros2_scripts/
│   ├── ros2_yolo_detector_3d.py         # NEW: 3D detector
│   ├── ros2_3d_ball_to_nav_goal.py      # NEW: Simple 3D bridge
│   └── navigation_telemetry.py          # KEEP: General purpose
└── docs/
    ├── architecture.md                   # UPDATED: 3D vision
    ├── d415_implementation_plan.md       # NEW: Implementation guide
    └── cleanup_plan.md                   # This file
```

## Cleanup Commands

```bash
# Create archive directory
mkdir -p archive/old_2d_vision/bridges
mkdir -p archive/old_2d_vision/debug_scripts
mkdir -p archive/old_2d_vision/telemetry
mkdir -p archive/old_2d_vision/docs

# Move bridge scripts
mv ros2_scripts/ros2_yolo_to_nav_goal*.py archive/old_2d_vision/bridges/

# Move debug scripts
mv ros2_scripts/coordinate_*.py archive/old_2d_vision/debug_scripts/
mv ros2_scripts/position_diagnostics.py archive/old_2d_vision/debug_scripts/

# Move 2D telemetry
mv ros2_scripts/direct_*_follower*.py archive/old_2d_vision/telemetry/
mv ros2_scripts/simple_direct_approach.py archive/old_2d_vision/telemetry/

# Move test scripts
mv test_*_follower*.sh archive/old_2d_vision/

# Keep useful scripts
# - navigation_telemetry.py (general purpose)
# - ros2_yolo_detector.py (base for 3D version)
```

## Files to Keep (But Modify)

1. **ros2_yolo_detector.py** - Base for 3D version
2. **navigation_telemetry.py** - Useful for any system
3. **Launch files** - Update for D415 camera

## Documentation Updates Needed

1. Add deprecation notices to old coordinate transform docs
2. Update README with 3D camera focus
3. Create migration guide from 2D to 3D
4. Update memory bank files (✓ DONE)

## Validation After Cleanup

- [ ] No broken imports in remaining scripts
- [ ] Launch files reference only valid scripts
- [ ] Documentation reflects current architecture
- [ ] Archive preserves history for reference
- [ ] Repository is clean and focused on 3D vision

## Benefits of Cleanup

1. **Clarity**: Clear separation between old 2D and new 3D approaches
2. **Maintainability**: Fewer confusing files to navigate
3. **Focus**: Repository clearly shows current direction
4. **History**: Archive preserves learning journey
5. **Simplicity**: Dramatically reduced codebase complexity
