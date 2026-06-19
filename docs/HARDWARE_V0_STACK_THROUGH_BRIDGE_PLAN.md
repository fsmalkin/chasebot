# Hardware V0 Stack-Through-Bridge Plan

## Decision

The next hardware milestone loads the Chasecar stack offboard and uses the
factory bridge as the reversible adapter to the JetBot Mini. The bridge owns the
physical safety contract: locked default state, motion enablement, deadman
timeout, motor caps, camera snapshots, stop, health, and relock evidence.
Chasecar owns perception, policy, command selection, and artifact
interpretation from the workstation/runtime workspace first.

This sequence gives the project real hardware feedback while preserving the
factory robot image. A full onboard install comes after the offboard path proves
that the stack can produce bounded commands and recover to a locked robot state.

## Current Evidence

The bridge lane is ready to act as an adapter:

- `scripts/deploy_robot_factory_bridge.ps1` can start the bridge locked with the
  onboard CSI camera served through the GStreamer backend.
- The bridge refuses motion commands while locked.
- The bridge accepts bounded live `cmd_vel` commands when motion is explicitly
  enabled.
- A strong turn-only proof moved the robot visibly with no forward command.
- The final health check after the motion proof reported `motion_enabled=false`,
  left and right motors at `0.0`, and live camera frames.

Reference artifact:

```text
artifacts/session/factory_bridge_ipad_motion_campaign_20260619T1612Z/campaign_summary.json
```

## Stack Path

The offboard path uses the same velocity contract the simulation stack already
understands:

1. Chasecar stack or stack adapter produces a bounded command decision.
2. `scripts/gather_motion_bridge.py` publishes that decision to ROS `cmd_vel`
   surfaces from the runtime JSON handoff.
3. `ros2_scripts/factory_bridge_cmd_vel_relay.py` subscribes to those ROS
   topics and posts clamped `linear_x` / `angular_z` commands to the factory
   bridge.
4. The bridge either refuses the command while locked or executes it while
   motion is explicitly enabled.
5. Every run restores the bridge to locked mode and records final health.

The stack path gate now defaults to `chasecar_stack_fetch_adapter_v0`. It
captures a bridge camera frame, runs the Chasecar visual target analyzer, builds
the current supervisor policy state, records the stack policy decision, emits a
bounded yaw or tiny fetch-approach command, and sends that command through the
same runtime JSON, ROS `cmd_vel`, relay, bridge, and relock path.

The adapter records its claim boundary in every artifact. The current bridge
path uses the deterministic/planner Chasecar policy contract and the available
detector asset; it records a learned low-level fetch checkpoint only when one is
explicitly supplied. `jetbot_visual_target_turn_v0` and `fixed_command_v0`
remain diagnostic fallbacks.

## Gate 1: Locked Stack-To-Bridge Command Path

Claim: the offboard stack path can produce bounded velocity commands and route
them to the robot bridge while the bridge remains locked.

Representative command:

```powershell
python tools/robot_factory_bridge/chasecar_bridge_stack_path_gate.py --artifact-dir artifacts/session/<id>/locked_policy_path --policy-entrypoint chasecar_stack_fetch_adapter_v0 --target-profile blue --max-bridge-linear-x 0.08 --max-bridge-angular-z 0.8
```

Pass criteria:

- Bridge health is reachable and locked.
- Camera readiness passes before relay starts.
- `chasecar_stack_fetch_adapter_v0` records observation, stack policy state,
  decision, command bounds, lineage, claim boundary, and stop reason.
- The ROS relay sees the command.
- The bridge refuses nonzero commands with HTTP `423` while locked.
- Final bridge health is locked, motors are zero, and camera frames are live.

## Gate 2: Bounded Live Stack Motion

Claim: the same path can execute one bounded live motion slice and recover to a
locked state.

Live execution requires the Gate 1 artifact from the same session family.

Pass criteria:

- Motion starts only after camera readiness and bounded command evidence.
- Command caps are explicit in the artifact.
- The robot executes a small, turn-dominant command.
- Visual evidence and bridge telemetry show the robot changed orientation.
- The bridge relocks after the run.
- Final health reports `motion_enabled=false`, both motors `0.0`, and fresh
  camera frames.

## Gate 3: Stack-Owned Policy Slice

Claim: Chasecar policy, rather than the color-target command-path probe,
produces the command that reaches the bridge.

Pass criteria:

- The artifact names `chasecar_stack_fetch_adapter_v0` and its config.
- The policy records the bridge observation, Chasecar supervisor snapshot,
  chosen command, command bounds, stack lineage, checkpoint status, and stop
  reason.
- The same relay and relock evidence from Gate 1 and Gate 2 is present.
- The run stays within the bridge safety contract.

## Stop Conditions

Stop and report when the bridge is unreachable, camera frames are stale, command
caps are missing, the relay produces unbounded commands, motion occurs while the
bridge is locked, final health is unlocked, either motor remains nonzero, or
the visual evidence conflicts with bridge telemetry.
