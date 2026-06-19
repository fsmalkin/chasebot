# Hardware V0 Unattended Strategy

## Decision

The hardware lane optimizes for unattended operation. The robot must start,
diagnose its sensing path, run bounded control, and fail locked without a human
recovering camera state, moving cables, or swapping ad hoc viewers during a run.

Current hardware v0 is the Yahboom/JetBot Mini factory bridge lane. It uses the
robot's onboard CSI camera through the factory Jetson image and the HTTP factory
bridge. The Orin Nano plus RealSense D415 depth-camera lane remains the later
hardware-transfer target. D415-specific depth/ROS/TensorRT proof starts after
the current bridge lane proves locked camera readiness and bounded command
transport.

## Operating Model

The factory bridge remains the safety and actuator layer. It owns motion
enablement, deadman timeout, motor limits, health, and the locked default state.
Chasecar policy code stays outside that layer until the safety contract and
camera readiness contract are repeatable.

The first deployable loop runs offboard control through the bridge:

1. Start the bridge locked with camera enabled.
2. Require fresh nonempty camera frames before relay or motion starts.
3. Run perception and control on the host through a single `linear_x` /
   `angular_z` interface.
4. Send bounded commands through the bridge.
5. Stop and restore the locked bridge after every proof run.
6. Save health, command, frame, and contact-sheet evidence for audit.

## Camera Policy

The current preferred camera is the onboard CSI camera because it is already
mounted, powered with the robot, and available to the Jetson camera stack. The
bridge camera backend should serve fresh JPEG frames without importing the
crashing `jetbotmini`/`cv2` Python camera path. GStreamer/Argus is the current
recovery path because a robot-side still-frame probe produced a valid image from
the sensor.

A fallback camera is acceptable only when it is fixed to the robot or bench,
powered with the robot, auto-started by the run command, and covered by the same
readiness gate.

Manual camera recovery, phone repositioning, laptop webcam aiming, and
interactive viewer setup are debugging tools. They can explain a failure.
Qualification requires a fixed, powered, auto-starting camera path.

## Current Evidence

The bridge has proven the useful safety surface:

- Motion stays locked by default.
- Commands are refused while locked.
- Bounded live turn commands can move the robot.
- Cleanup restores `motion_enabled=false` with both motors at `0.0`.
- The reusable color-target runner now stops before relay or motion when the
  camera readiness gate is red.

The bridge camera backend is the current blocker. The robot reports the bridge
healthy and locked, while the Python camera backend can leave camera health
unloaded with zero cached frames or crash while importing `jetbotmini`/`cv2`. A
direct GStreamer/Argus still-frame probe produced a valid JPEG from the onboard
sensor, so the next workstream is a bridge-served GStreamer camera backend with
the existing readiness gate.

Reference artifact:

```text
artifacts/session/live_factory_blue_bottle_camera_gate_block_20260618/goal_summary.json
artifacts/session/jetbot_reconnect_20260619T1505Z/camera_probe.jpg
```

## Acceleration Path

Advance in three layers:

1. Safety layer: keep the factory bridge small, locked by default, and
   artifact-heavy.
2. Readiness layer: make camera, command, and health gates explicit and
   machine-checkable before motion.
3. Policy layer: connect Chasecar perception/control to the same bridge command
   contract once the readiness layer is green.

This lets the project test trained Chasecar behavior on the real robot without
turning camera setup into an operator ritual.

## Next Milestone

Recover locked bridge camera readiness, then run a one-target offboard Chasecar
policy proof through the factory bridge.

Success criteria:

- Bridge starts locked and reports fresh camera frames from the onboard CSI
  camera through the GStreamer backend.
- Target perception produces a stable target observation.
- Policy produces bounded `linear_x` / `angular_z` commands.
- The robot turns toward the target and performs a short bounded approach.
- The run restores the locked bridge.
- The artifact bundle includes health, command log, frame sequence, contact
  sheet, and pass/fail summary.
