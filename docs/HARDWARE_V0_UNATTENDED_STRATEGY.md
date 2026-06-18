# Hardware V0 Unattended Strategy

## Decision

The hardware lane optimizes for unattended operation. The robot must start,
diagnose its sensing path, run bounded control, and fail locked without a human
recovering camera state, moving cables, or swapping ad hoc viewers during a run.

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

The preferred camera is the onboard camera path because it can run without an
operator. A fallback camera is acceptable only when it is fixed to the robot or
bench, powered with the robot, auto-started by the run command, and covered by
the same readiness gate.

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

The current blocker is camera bring-up stability. The robot reports the bridge
healthy and locked, while camera health remains unloaded with zero cached
frames. Robot-side logs showed NVIDIA Argus / IMX219 camera-provider failures.
The next workstream is readiness recovery for unattended autonomy before
additional policy tuning.

Reference artifact:

```text
artifacts/session/live_factory_blue_bottle_camera_gate_block_20260618/goal_summary.json
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

Run a one-target offboard Chasecar policy proof through the factory bridge after
camera readiness is green.

Success criteria:

- Bridge starts locked and reports fresh camera frames.
- Target perception produces a stable target observation.
- Policy produces bounded `linear_x` / `angular_z` commands.
- The robot turns toward the target and performs a short bounded approach.
- The run restores the locked bridge.
- The artifact bundle includes health, command log, frame sequence, contact
  sheet, and pass/fail summary.
