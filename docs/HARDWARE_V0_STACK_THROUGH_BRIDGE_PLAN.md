# Hardware V0 Stack-Through-Bridge Plan

## Decision

The current hardware v0 path gets the sim stack working IRL through the JetBot
factory bridge before any onboard runtime expansion. The factory bridge at
`http://192.168.1.11:8765` owns the live hardware boundary: locked defaults,
explicit motion enablement, command caps, deadman behavior, camera frames,
health, stop, and relock evidence. Between tests, the required safe state is
`motion_enabled=false` with both motors at `0.0`.

The primary hardware path routes the Chasecar sim-stack policy offboard through
`chasecar_stack_fetch_adapter_v0` and the factory bridge. The bridge provides
the reversible actuator and camera boundary; the workstation owns policy
routing, observation adapters, command selection, artifact capture, and claim
interpretation.

Bright/color bbox handling is calibration and safety fallback. It helps tune
lighting, centering, stiction floors, and terminal visual stops. Behavior
promotion comes from the sim-stack policy route, then object-pose observations,
then fetch-to-pose evidence.

## Current Bridge Path

The active proof path is:

1. Query bridge health at `http://192.168.1.11:8765`.
2. Confirm the bridge is locked, camera frames are fresh, and motors are zero.
3. Capture bridge frames on the Windows workstation. Use direct HTTP first; use
   `--camera-fetch-mode ssh` when `/health` is reachable and `/camera.jpg`
   stalls during Windows-side body transfer.
4. Build the bridge observation for `chasecar_stack_fetch_adapter_v0`. Use the
   YOLO/object-pose adapter as the promotion path when available; keep
   color/bright bbox as a calibration and safety-stop fallback.
5. Send only bounded bridge commands selected by the routed policy after the
   relevant locked transport and motion gates pass.
6. Relock after each test slice and record final bridge health.

Bridge defaults stay locked. Test code may enable motion only for the bounded
slice under test, then must return the bridge to `motion_enabled=false`. This is
the safety contract for every gate below.

## Serial Gate Ladder

The ladder now separates foundation evidence from behavior promotion. The June
25 bright-bbox terminal run is a foundation pass for hardware access, safety,
and bounded control. Its proof scope excludes 3D/object-pose fetch-to-pose.

Foundation evidence:

| Check | Current live status | Evidence claim |
| --- | --- | --- |
| `access_safety` | Current live pass | The bridge is reachable at `http://192.168.1.11:8765`, SSH works as `jetson`, and final health is locked with both motors at `0.0`. |
| `camera_freshness` | Current live pass | The `v4l2_bayer` camera path is loaded, fresh, and running near `1.2` cached FPS under the lowered hardware gate. |
| `lock_relock` | Current live pass | Locked transport returns HTTP `423` refusals, live slices relock, and final health returns `motion_enabled=false`. |
| `motor_direction_and_stiction` | Current live pass | Bounded motion proved motor direction and an acquire-turn stiction floor while preserving the bridge stop path. |
| `visual_acquisition_and_approach` | Current live pass | The visible target stayed centered through a bounded forward approach slice. |
| `bridge_visual_terminal_stop` | Current live pass | The latest bright target run stopped at bbox height `0.300` with centered target error about `-0.111`, final bridge locked, and motors zero. |

Next serial gates:

| Gate | Current status | Promotion requirement |
| --- | --- | --- |
| `sim_stack_offboard_policy_routing` | Passed (live 2026-06-25) | Met: the Chasecar sim-stack policy loaded and routed offboard through `chasecar_stack_fetch_adapter_v0` into the locked bridge, recording stack state, supervisor policy snapshot, command provenance, relay/bridge response, a real-stack boot report, and final relock. See Evidence Boundary. |
| `yolo_object_pose_observation_adapter` | Active next gate | Convert bridge camera observations into the object state the sim stack needs: target class, freshness, 2D bbox, distance or pose estimate, and delivery-target geometry with explicit confidence and limitation fields. |
| `terminal_fetch_to_pose_proof` | Pending | Prove fetch-to-pose with object trajectory, delivery radius, bounded command evidence, contact or no-contact classification, and final locked bridge health. |
| `endurance_loop` | Pending | Repeat the terminal fetch-to-pose loop across cycles while preserving bridge lock, camera readiness, observation confidence, motor budget, reset safety, and final relock. |

Latest ladder report:

```text
artifacts/session/manual_sim_stack_irl_gate_ladder_current_20260625_003/gate_ladder_report.md
```

The latest saved ladder report is stale relative to the current live run. The
current bridge session has recovered access, camera readiness, lock/relock,
motor direction, acquire-turn stiction floor, visual acquisition, bounded
forward approach, and a bridge-visual bbox-height terminal stop.

## Evidence Boundary

`sim_stack_offboard_policy_routing` passed live on 2026-06-25 through two
complementary runs. Both selected `chasecar_stack_fetch_adapter_v0`, recorded the
supervisor policy snapshot and a real-stack boot report, used the `v4l2_bayer`
camera path with fresh frames, and ended locked with both motors at `0.0`:

```text
artifacts/session/manual_sim_stack_irl_offboard_policy_route_locked_20260625_002/closed_loop_summary.json
artifacts/session/manual_sim_stack_irl_offboard_policy_route_live_turn_20260625_001/closed_loop_summary.json
```

The locked run routed the full policy path with `execute_motion=false`: 11
expected HTTP-`423` locked refusals, zero live motor events, and final
`motion_enabled=false` with motors at `0.0`. The live-turn run executed one
bounded turn-only step (`left/right` about `0.28/-0.28` for `0.04s`), passed the
required progress scorecard (target area increased, centering improved), then
relocked to `motion_enabled=false` with motors at `0.0`. The boot report records
the remaining gaps that define the next gate: a `bridge_adapter_placeholder_pose`
for robot pose and color-target bbox-only perception, with no calibrated object
pose or delivery geometry yet. (These artifacts live on disk only; `artifacts/`
is gitignored.)

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

The latest bridge-visual terminal run passed with
`terminal_reason=target_inside_stack_forward_stop_bbox_height`,
`target_bbox_height_ratio=0.300`, centered target error about `-0.111`, final
`motion_enabled=false`, and left/right motors at `0.0`. It selected
`chasecar_stack_fetch_adapter_v0` and recorded a real-stack boot report, so it
supports bridge access, safety, command routing, bounded forward control, and
terminal safety-stop behavior. Its observation was bright bbox geometry, so the
artifact does not prove 3D/object-pose fetch-to-pose.

The earlier YOLO ONNX runs support detector visibility and the next observation
adapter. The current Prime-bottle setup uses direct HTTP camera fetch with
`runtime/yolo/yolov5s.onnx`, confidence threshold `0.001`, YOLO target area
floor `0.001`, camera FPS floor `1.0`, and a 60-second relay-start budget for
WSL/ROS cold starts. Promotion now requires that detector output to feed the
object-pose state contract for the sim-stack policy.

The turn-response probe proves a strong bounded turn primitive and a reverse
reset are available for later observation-adapter framing tests. Those
primitives are safe to use when the test starts from a verified locked bridge
state and ends with relock evidence.

Bright/color bbox evidence is diagnostic and remains useful as a safety
fallback. It can explain scene lighting, geometry, frame exposure, target
placement, stiction floors, and conservative terminal stops. Promotion evidence
must name the routed sim-stack policy, the observation contract, and the
fetch-to-pose success metric it satisfies.

## Next Serial Goal

`sim_stack_offboard_policy_routing` is now a live pass (2026-06-25; see Evidence
Boundary). The next serial goal is the YOLO/object-pose observation adapter.

Build the YOLO/object-pose observation adapter. The adapter must state the
target class, bbox, confidence, freshness, estimated
distance or pose, delivery target geometry, and any limits on the estimate. The
terminal fetch-to-pose proof follows only after that observation state is
available. Endurance follows only after terminal fetch-to-pose passes.

## Stop Conditions

Stop and report when bridge health is unreachable, camera frames are stale,
command caps are missing, motion occurs while locked, final health remains
unlocked, either motor remains nonzero, object-pose evidence is absent for a
fetch-to-pose claim, bbox-only evidence is used as the behavior proof, or visual
evidence conflicts with bridge telemetry.
