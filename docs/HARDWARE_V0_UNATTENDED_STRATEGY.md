# Hardware V0 Unattended Strategy

## Decision

The hardware v0 unattended lane advances through one serial behavior gate at a
time after bridge safety is proven. The active robot path is the JetBot factory
bridge at `http://192.168.1.11:8765`; the bridge stays locked by default and
must return to `motion_enabled=false` with both motors at `0.0` between tests.

The current direction routes the Chasecar sim-stack policy offboard through
`chasecar_stack_fetch_adapter_v0` and the factory bridge. PC-side YOLO,
object-pose estimation, and bridge camera frames provide observations for that
policy route. Bright/color bbox handling remains calibration and safety-stop
fallback.

## Operating Model

The factory bridge remains the safety and actuator layer. It owns motion
enablement, deadman timeout, motor limits, health, camera serving, and locked
default state. PC-side tools own detector execution, gate evaluation, command
selection, artifact capture, and promotion decisions.

Each unattended or semi-unattended run follows the same sequence:

1. Start from bridge health at `http://192.168.1.11:8765`.
2. Confirm locked state, zero motors, and fresh camera frames.
3. Run the next unpassed behavior gate only.
4. Enable motion only for the bounded primitive or policy slice under test.
5. Relock after the slice and write final health evidence.
6. Promote exactly the gate whose pass criteria were tested.

This sequence keeps the robot safe while making the evidence ladder easy to
resume after a reboot, lighting change, or operator reset.

## Current Gate State

Current foundation evidence has passed:

```text
access_safety -> camera_freshness -> lock_relock ->
motor_direction_and_stiction -> visual_acquisition_and_approach ->
bridge_visual_terminal_stop
```

The behavior ladder now runs in this order:

```text
sim_stack_offboard_policy_routing -> yolo_object_pose_observation_adapter ->
terminal_fetch_to_pose_proof -> endurance_loop
```

The latest saved gate report is stale relative to the current live bridge
session. Current live evidence has recovered bridge access, camera freshness,
lock/relock, motor direction, acquire-turn stiction floor, visual acquisition,
bounded forward approach, and a bridge-visual bbox-height terminal stop. The
next operator-gated behavior proof is `sim_stack_offboard_policy_routing`.

Latest report:

```text
artifacts/session/manual_sim_stack_irl_gate_ladder_current_20260625_003/gate_ladder_report.md
```

## Evidence Boundary

Representative evidence:

```text
artifacts/session/manual_sim_stack_irl_basement_live_five_step_20260625_002/overnight_loop_summary.json
artifacts/session/manual_sim_stack_irl_basement_live_yolo_only_slow_scan_20260625_001/overnight_loop_summary.json
artifacts/session/manual_sim_stack_irl_basement_turn_response_probe_20260625_001/turn_response_summary.json
artifacts/session/manual_sim_stack_irl_upstairs_yolo_snapshot_20260625_002/yolo_detection_summary.json
artifacts/session/manual_sim_stack_irl_upstairs_yolo_snapshot_low_conf_20260625_001/yolo_detection_summary.json
artifacts/session/manual_sim_stack_irl_upstairs_yolo5m_probe_20260625_001/yolo_detection_summary.json
artifacts/session/manual_sim_stack_irl_upstairs_yolo_reacquire_scan_20260625_002/overnight_loop_summary.json
artifacts/session/manual_sim_stack_irl_gate_ladder_current_20260625_003/gate_ladder_report.md
artifacts/session/manual_sim_stack_irl_back_up_yolo5s_live_repeat_20260625_001/yolo_detection_summary.json
artifacts/session/manual_sim_stack_irl_back_up_locked_stack_path_gate_yolo5s_http_20260625_001/gate_summary.json
artifacts/session/manual_sim_stack_irl_back_up_locked_closed_loop_yolo5s_http_lowconf_20260625_001/closed_loop_summary.json
artifacts/session/manual_sim_stack_irl_back_up_live_bright_bbox_terminal_approach_20260625_002/closed_loop_summary.json
```

The latest bridge-visual terminal run supports access, safety, command routing,
bounded forward approach, and terminal safety-stop behavior. It passed with
`terminal_reason=target_inside_stack_forward_stop_bbox_height`,
`target_bbox_height_ratio=0.300`, centered target error about `-0.111`, final
`motion_enabled=false`, and left/right motors at `0.0`. Its observation was
bright bbox geometry, so it remains outside full 3D/object-pose fetch-to-pose
scope.

The earlier YOLO ONNX evidence supports the next observation adapter. The
current Prime-bottle setup uses direct HTTP camera fetch with
`runtime/yolo/yolov5s.onnx`, confidence threshold `0.001`, YOLO target area
floor `0.001`, camera FPS floor `1.0`, and a 60-second relay-start budget for
WSL/ROS cold starts. The next promotion artifact must connect that detector
output to the object state consumed by the sim-stack policy.

The turn-response probe proves the strong bounded turn primitive and reverse
reset are available for later observation-adapter framing tests. Use them as
bounded setup and recovery primitives after the policy-routing gate passes.

Bright/color bbox evidence remains diagnostic. It can explain lighting, target
placement, geometry, stiction floors, and conservative terminal stops. Behavior
promotion requires the routed sim-stack policy, an explicit observation
contract, and a fetch-to-pose success metric.

## Promotion Rule

Promote one gate at a time. A later gate may run only after the current gate has
passed in the latest ladder report or in a clearly cited replacement artifact.
The next serial goals are:

1. Promote `sim_stack_offboard_policy_routing` with
   `chasecar_stack_fetch_adapter_v0`, command provenance, relay/bridge response,
   policy state, and final locked health.
2. Promote `yolo_object_pose_observation_adapter` with target class, bbox,
   confidence, freshness, distance or pose estimate, delivery target geometry,
   and explicit estimate limits.
3. Promote `terminal_fetch_to_pose_proof` with object trajectory, delivery
   radius, bounded command evidence, and final locked health.
4. Promote `endurance_loop` only after terminal fetch-to-pose passes.

Each promoted artifact must show bridge health reachable, camera readiness,
bounded command caps, final `motion_enabled=false`, and both motors at `0.0`.

## Camera And Deployment Policy

The active camera source is the JetBot bridge camera served by the factory
bridge. The current evidence uses the `v4l2_bayer` path with fresh frames.
PC-side YOLO ONNX and any object-pose estimator feed the observation adapter for
the routed sim-stack policy. Onboard camera setup, onboard YOLO, TensorRT
conversion, and Jetson runtime packaging belong to a later deploy/setup slice.

Manual scene inspection, color-only target scans, and one-off frame checks can
diagnose lighting, placement, and conservative stop thresholds. Promotion
artifacts require the observation state needed by fetch-to-pose.

## Stop Conditions

Stop and report when bridge health is unreachable, camera frames are stale,
motion occurs while locked, final health is unlocked, either motor remains
nonzero, object-pose evidence is absent for a fetch-to-pose claim, bbox-only
evidence is used as the behavior proof, or the only positive target evidence is
color-only.
