# TensorRT Runtime Assets

This directory contains TensorRT runtime artifacts for the canonical `tensorrt_int8` inference backend.

## Layout

- `calibration/calibration_config.yaml`: canonical INT8 calibration/build settings.
- `calibration/images/`: calibration image dataset root (not tracked in git).
- `calibration/calibration.cache`: TensorRT calibration cache.
- `engines/`: serialized TensorRT engines (not tracked in git by default).

## Workflow

1. Export ONNX:
   - `python scripts/export_yolo_onnx.py --model yolov8m.pt --output runtime/tensorrt/onnx/ball_detector.onnx`
2. Build INT8 engine:
   - `python scripts/build_tensorrt_engine.py --config runtime/tensorrt/calibration/calibration_config.yaml --onnx runtime/tensorrt/onnx/ball_detector.onnx`
3. Run canonical stack with TensorRT backend:
   - `scripts/run_canonical_stack.ps1 -RuntimeTarget robot_fidelity_orin -InferenceBackend tensorrt_int8`
