# Launch Directory Guide

## Canonical Launch
- `jetbot_gz_control_camera_test_v5.launch.py`

This is the active baseline for simulation + D415 camera + control.

Supported canonical launch args:
1. `inference_device` (`auto|cuda:0|cpu`)
2. `perf_profile` (`compat|balanced|max`)
3. `headless` (`true|false`)

Example:
```bash
ros2 launch chasebot_sim jetbot_gz_control_camera_test_v5.launch.py \
  inference_device:=auto perf_profile:=balanced headless:=false
```

## Canonical Runtime Stack (outside launch file)
1. Launch v5 simulation.
2. Start `ros2_yolo_detector_frisbee_quiet.py`.
3. Start `yolo_3d_position_extractor.py`.
4. Optional nav: `yolo_3d_to_nav2_bridge.py`.

## Non-Canonical Files
Many launch files in this folder are historical or experimental and remain for reference.
Use `docs/ACTIVE_WORKFLOW.md` for what is currently supported.
