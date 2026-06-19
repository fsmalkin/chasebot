# Hardware V0 Unattended Strategy

## Decision

The hardware lane optimizes for unattended operation. The robot must start,
diagnose its sensing path, run bounded control, and fail locked without a human
recovering camera state, moving cables, or swapping ad hoc viewers during a run.

Current hardware v0 is the Yahboom/JetBot Mini factory bridge lane. The next
milestone loads the Chasecar stack offboard and routes its bounded velocity
commands through the HTTP factory bridge. The bridge remains the reversible
hardware adapter for the robot's onboard CSI camera, motion enablement, motor
limits, deadman timeout, health, and locked default state.

The Orin Nano plus RealSense D415 depth-camera lane remains the later
hardware-transfer target. D415-specific depth/ROS/TensorRT proof starts after
the JetBot lane proves that the Chasecar stack can perceive, choose bounded
commands, and recover to a locked state through the bridge.

## Operating Model

The factory bridge remains the safety and actuator layer. It owns motion
enablement, deadman timeout, motor limits, health, and the locked default state.
Chasecar policy code runs outside that layer first, using the bridge as an
adapter rather than a replacement runtime.

The first deployable stack loop runs offboard control through the bridge:

1. Start the bridge locked with camera enabled.
2. Require fresh nonempty camera frames before relay or motion starts.
3. Run Chasecar perception, policy, or a named stack adapter on the host.
4. Route the stack's `linear_x` / `angular_z` output through the existing ROS
   `cmd_vel` relay.
5. Send bounded commands through the bridge only after the locked no-motion gate
   proves the command path.
6. Stop and restore the locked bridge after every proof run.
7. Save health, command, frame, and contact-sheet evidence for audit.

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
- The onboard CSI camera serves fresh bridge frames through the GStreamer
  backend.
- Bounded live turn commands can move the robot.
- Cleanup restores `motion_enabled=false` with both motors at `0.0`.
- The reusable color-target runner stops before relay or motion when the camera
  readiness gate is red.
- A stronger turn-only proof moved the robot visibly through the bridge while
  preserving final relock and live camera health.

Reference artifact:

```text
artifacts/session/live_factory_blue_bottle_camera_gate_block_20260618/goal_summary.json
artifacts/session/jetbot_reconnect_20260619T1505Z/camera_probe.jpg
artifacts/session/factory_bridge_ipad_motion_campaign_20260619T1612Z/campaign_summary.json
```

## Acceleration Path

Advance in three layers:

1. Safety layer: keep the factory bridge small, locked by default, and
   artifact-heavy.
2. Readiness layer: make camera, command, and health gates explicit and
   machine-checkable before motion.
3. Stack layer: connect Chasecar perception/control to the bridge command
   contract, first with no-motion relay evidence and then with bounded motion.

This lets the project test trained Chasecar behavior on the real robot without
turning camera setup into an operator ritual.

## Next Milestone

Load the Chasecar stack slice through the factory bridge, prove the no-motion
command path, then run bounded live policy motion until the nav-target success
gate passes. Each closed-loop run must also emit the real-stack boot report so
unattended proof can distinguish the routed supervisor-policy path from the
remaining ROS/Nav2 executor and object-pose adapter work.

Success criteria:

- Bridge starts locked and reports fresh onboard CSI frames through the
  GStreamer backend.
- The offboard Chasecar runtime workspace can publish a bounded command through
  the existing ROS `cmd_vel` surface.
- The bridge relay observes the command while locked and records expected HTTP
  refusals, proving transport without motion.
- A live motion attempt starts only after the no-motion gate produces bounded
  commands, usable camera evidence, and final locked health.
- The live nav-to-target run records `nav_target_success.pass=true` from either
  a centered target at the configured success area or the safe target-too-close
  terminal stop.
- The artifact bundle includes health, command log, frame sequence, contact
  sheet, relock evidence, real-stack boot report, progress scorecard, and
  pass/fail summary.
