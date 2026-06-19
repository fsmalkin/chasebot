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

The closed-loop runner repeats the same stack path for a small fixed number of
steps. Each step captures a fresh observation, computes the Chasecar stack
adapter decision, routes the bounded command through the relay, and records a
post-step relock and health check. The loop exits on target-too-close, stale
camera, command mismatch, unsafe bridge state, or visual evidence that conflicts
with the bridge telemetry.

Live closed-loop runs also emit a progress scorecard. The scorecard compares
the target observation after each bounded pulse with the previous observation.
It passes when the target area increases, the centering error improves, or the
target remains centered without meaningful area loss. It fails on target loss,
stale camera, meaningful area regression, centering regression, unsafe bridge
state, or command evidence that contradicts the bridge telemetry.

Every closed-loop run now writes a real-stack boot report beside the scorecard.
`real_stack_boot_report.json` and `real_stack_boot_report.md` name the selected
entrypoint, run a deterministic policy smoke through
`scripts/brain_supervisor_policy.py:build_policy_snapshot`, and classify the
current stack components by bridge status. The report keeps the current claim
precise: the v0 hardware lane runs the shared supervisor policy through the
factory-bridge adapter, while the ROS/Nav2 executor loop and object-centric
fetch-to-pose contact policy still require bridge-backed object pose, dashboard
state, and executor shims before full stack onboarding.

The nav-target success gate is stricter than the progress scorecard. The
scorecard proves each bounded pulse remains visually coherent. The nav gate
requires the target to reach the configured area threshold while centered, or
requires the stack adapter to produce the safe target-too-close terminal stop.
Use this gate for hardware claims that say the robot navigated to the target.

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

Claim: Chasecar policy produces the command that reaches the bridge through the
same adapter path.

Pass criteria:

- The artifact names `chasecar_stack_fetch_adapter_v0` and its config.
- The policy records the bridge observation, Chasecar supervisor snapshot,
  chosen command, command bounds, stack lineage, checkpoint status, and stop
  reason.
- The same relay and relock evidence from Gate 1 and Gate 2 is present.
- The run stays within the bridge safety contract.

## Gate 4: Bounded Closed-Loop Stack Adapter

Claim: the workstation can run repeated observe-policy-command-relock steps
through the same Chasecar stack adapter while preserving the bridge safety
contract.

Representative locked command:

```powershell
python tools/robot_factory_bridge/chasecar_bridge_stack_closed_loop_runner.py --pretty --artifact-dir artifacts/session/<id>/closed_loop_locked --steps 2
```

Representative live command:

```powershell
python tools/robot_factory_bridge/chasecar_bridge_stack_closed_loop_runner.py --pretty --artifact-dir artifacts/session/<id>/closed_loop_live --steps 2 --execute-motion --confirm-operator-ready
```

Defaults for the current blue target setup are `--target-profile blue`,
`--max-bridge-linear-x 0.08`, `--max-bridge-angular-z 0.8`,
`--max-motor-speed 0.7`, and `--stack-forward-stop-area-ratio 0.20`.

Pass criteria:

- Each step records observation, stack supervisor snapshot, command,
  locked-refusal proof, live motion proof when enabled, and final relock health.
- The loop writes one source summary per step plus a top-level
  `closed_loop_summary.json`.
- Command mismatch, stale camera, unsafe final health, visual contradiction, or
  unexpected bridge motion fails the loop.
- Target-too-close becomes a safe terminal stop only after the required minimum
  completed step count.

## Gate 5: Physical Progress Scorecard

Claim: a bounded live loop can prove visual approach progress before the project
allows contact-rich fetch tests.

Representative live command:

```powershell
python tools/robot_factory_bridge/chasecar_bridge_stack_closed_loop_runner.py --pretty --artifact-dir artifacts/session/<id>/closed_loop_progress --steps 3 --step-settle-s 1.0 --target-min-area-ratio 0.008 --execute-motion --confirm-operator-ready
```

Pass criteria:

- `progress_scorecard.json` and `progress_scorecard.md` exist beside
  `closed_loop_summary.json`.
- Every scored live transition names area-ratio delta, absolute center-error
  delta, evidence labels, and any issues.
- The final post-loop observation scores the last live pulse.
- The live run fails when the scorecard reports target loss, stale camera,
  meaningful area regression, centering regression, visual contradiction, or an
  unsafe final bridge state.
- Final independent bridge health is locked, both motors are zero, and camera
  frames are fresh.

## Gate 6: Real Stack Boot Boundary

Claim: the hardware lane can boot the closest current Chasecar stack path
through the bridge and produce code-referenced evidence for the remaining
sim-to-hardware gaps.

Representative dry-run command:

```powershell
python tools/robot_factory_bridge/chasecar_bridge_stack_closed_loop_runner.py --pretty --artifact-dir artifacts/session/<id>/real_stack_boot_boundary --dry-run
```

Pass criteria:

- `real_stack_boot_report.json` and `real_stack_boot_report.md` exist beside
  `closed_loop_summary.json`.
- The report names `chasecar_stack_fetch_adapter_v0` as the selected bridge
  entrypoint.
- The policy smoke produces `preferred_intent=plan_to_target` and a bounded
  nonzero command through the same `stack_command_from_policy` mapping used by
  live runs.
- The component table marks `brain_supervisor_policy` and the factory-bridge
  stack adapter as routed.
- The component table marks `brain_supervisor_loop`,
  `brain_intent_executor`, and `gather_object_centric_policy_helpers.py` as
  source-present bridge gaps, with a code path or missing adapter named for each.
- The sim-to-hardware section lists perception, state, execution, and success
  evidence differences before any run claims full stack onboarding.

## Gate 7: Nav-To-Target Success

Claim: the robot reached the visible target through the Chasecar stack bridge
path, rather than only completing a safe motion budget.

Representative live command:

```powershell
python tools/robot_factory_bridge/chasecar_bridge_stack_closed_loop_runner.py --pretty --artifact-dir artifacts/session/<id>/nav_target_success --steps 14 --step-settle-s 1.0 --target-min-area-ratio 0.008 --max-bridge-linear-x 0.14 --max-bridge-angular-z 0.8 --max-motor-speed 1.0 --stack-search-angular-z 0.25 --stack-acquire-max-angular-z 0.12 --command-duration-s 0.35 --require-nav-target-success --execute-motion --confirm-operator-ready
```

Pass criteria:

- `nav_target_success.json` and `nav_target_success.md` exist beside the
  progress scorecard and real-stack boot report.
- The run keeps the same bridge safety contract: camera readiness before
  command, locked refusal proof, bounded live motion, relock after each slice,
  final locked health, and motors at zero.
- The progress scorecard passes.
- The nav gate passes through either `target_too_close_terminal_stop` or
  `target_area_success_threshold_met` with `target_centered_for_success`.
- The deployed bridge uses the same linear and angular caps as the relay, so
  the factory bridge normalizes commands against the intended hardware limits.
- Search can use a stronger bounded turn while acquire uses
  `--stack-acquire-max-angular-z` for gentle centering after target reacquire.
- A run that only completes `--steps` while the target remains below the success
  threshold fails when `--require-nav-target-success` is set.

## Stop Conditions

Stop and report when the bridge is unreachable, camera frames are stale, command
caps are missing, the relay produces unbounded commands, motion occurs while the
bridge is locked, final health is unlocked, either motor remains nonzero, or
the visual evidence or progress scorecard conflicts with bridge telemetry.
