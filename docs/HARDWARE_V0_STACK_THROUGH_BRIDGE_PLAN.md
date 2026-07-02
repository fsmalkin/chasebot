# Hardware V0 Stack-Through-Bridge Plan

## Direction Pivot (2026-06-30)

This branch proves the **mono perception+control stack in simulation as a digital
twin**, then deploys it onboard the robot. The north star is **the JetBot Mini
working a fetch with the hardware we actually have** — one mono RGB camera, no
depth, no wheel odometry. The sim is scaffolding, not the deliverable: it gives us
the one thing the bench cannot — **ground truth** to measure the mono stack's
error against — so we tune it where the error is visible, then redeploy to the
robot.

**Why not the world-frame stack.** The sim's object-centric `fetch_to_pose`
policy consumes **world-frame metric state** — robot pose (x, y, yaw), ball world
position, delivery-zone geometry — which needs depth + odometry the hardware
lacks. An earlier sim run of that world-frame stack passed (closest approach
0.19 m inside the 0.30 m delivery radius, calibrated golf physics engaged) — but
it read the ball pose from **Gazebo ground truth**, not from any camera. So it
validated the *rich* stack, not the mono one. We do **not** wait to close the
sensing gap; we prove the stack that runs on the sensors we already have.

**The mono stack (what we are proving — "Option B").** A native ROS2 node drives
the sim robot using **only the mono RGB camera**, robot-relative control, no world
frame: `/d415/color/image_raw` → YOLOv5m → apparent-size distance
(`z = K / size_px`, range + bearing) → `decide_fetch_action()` →
`TwistStamped` on `/jetbot_base_controller/cmd_vel`. Gazebo ground truth is read
**only by an external scorer**, never by the node — the "blinding" that keeps the
sim honest to mono-only sensing. This is the literal robot-relative control core
already demonstrated on the real robot; the sim swaps the perception inputs, not
the brain. The world-frame gather policy (`decide_object_centric_gather_command`)
is explicitly **excluded** — it needs odometry the hardware does not have.

**What was proven IRL (retained as evidence below).** Offboard supervisor-policy
routing through the locked factory bridge; monocular distance calibration;
closed-loop visual approach to a calibrated standoff; and contact — the
minimum-viable IRL fetch on degraded sensors, with the bridge safety contract
(lock + 0.5 s deadman + bounded commands, final relock) holding throughout.

**Confirmed sim facts (2026-06-30).** Gate lane up (sim-gate + gate-stack);
gate-stack has onnxruntime + the committed `runtime/yolo/yolov5m.onnx`; live D415
RGB intrinsics `fx = fy = 462.27`, 640×480, zero distortion → sim apparent-size
constant `K = f·H ≈ 19.7 px·m` (vs the real bench's 9.62 — the mono K **must be
re-fit** for the sim camera before closed-loop drive); drive seam confirmed
(`/jetbot_base_controller/cmd_vel`, `TwistStamped`, publish ≥20 Hz); ground truth
read via `gz topic /world/yolo_test_world/dynamic_pose/info` for scoring only.

**Onboard horizon.** Once the mono stack is green in sim against ground truth, it
deploys onboard the Jetson (perception backend swappable: onnxruntime in sim →
TensorRT on the Orin). The hardware bring-up content below is kept as the IRL
evidence record.

**Validation result (2026-06-30) — mono fetch-to-contact PROVEN in sim.** A
closed-loop run scored against Gazebo ground truth: robot started at the world
origin, ball at x=0.7 m. Using **only the mono RGB camera**, the node detected the
ball every frame through the approach (color detector, confidence 0.89–0.92,
`lost_count=0` — zero flicker), drove a calibrated closed-loop approach (mono `z`
0.617 m → 0.391 m, straight to the 0.40 m standoff), then a bounded open-loop push
**contacted the ball — ground truth shows it displaced from x=0.7 m to x=0.945 m
(≈0.25 m), y≈0**. This validates the full mono perception → calibrated-distance →
approach → contact pipeline against ground truth — the part the bench could not
measure. A static ground-truth range sweep quantifies the calibrated distance
(`z = K/size`, K=19.73): mono estimate accurate to **~2% (±0.008–0.015 m) across
0.4–1.0 m** vs Gazebo truth.

**Perception note (sim-to-real gap).** yolov5m has a domain gap on the synthetic
ball: it localizes correctly but its "sports ball" confidence is starved
(~0.04–0.13, flickering to 0.0), even with realistic golf / high-contrast soccer
textures — far below the ~0.76 it scores on the real white golf ball. So the sim
uses a **color detector** front-end: the sim ball is white (emissive, so it reads
bright in the sim's flat lighting — matching the real golf ball), segmented by
low-saturation/high-value with the more-saturated sky excluded; equiv-diameter
matches the geometry, so `K` is unchanged. The real
robot keeps YOLO (bench-proven); the geometry/control being validated is identical
either way — detection-confidence stays validated on the real bench, the sim
validates the calibrated geometry + control.

**Artifacts:** `ros2_scripts/chasecar_mono_fetch_node.py` (+ `chasecar_mono_yolo_detect.py`,
`chasecar_mono_color_detect.py`), `scripts/chasecar_mono_fetch_scorer.py`,
`scripts/chasecar_mono_fetch_harness.py`, `tools/robot_factory_bridge/chasecar_bridge_sim_distance_calibration.py`;
reproducible run via the harness with `--detector color`.

**IRL validation (2026-07-01/02) — repeatable autonomous fetch on the real robot.**
Offboard loop (laptop YOLO + calibrated mono distance driving the factory bridge):
**6 completed fetch-push episodes across two days, 3 safe empty-scan give-ups, 0
unsafe end-states**, including self-play (fetch → self-reset with randomized turn →
scan re-acquire → fetch) with no human touches. Best approach: 1.14 m → 0.34 m of
continuous closed-loop servoing in warm dim lamplight, then a 10-burst contact
push. Hardware constants and failure modes recorded in memory + commit 809fa4b
(motor stiction ~0.3, TurnGain 1.0, Wi-Fi response-loss signature + ride-through).
Perception boundary measured: YOLO 0.7–0.9 conf in daylight, ~0.14 at 1 m in dim
lamplight (acquire floor 0.12), useless in the dark; classical CV (HSV color,
tophat local-contrast) is measurably defeated by warm light on glossy wood — the
white ball reads S≈178 vs floor S≈152. Onboard brain (`chasecar_onboard_fetch.py`)
validated on the Jetson in dry-run (py3.6, ~4–5 Hz loop, floor-zone gate rejecting
a dark-room LED false positive); onboard perception awaits a TensorRT YOLO engine
(`trtexec` confirmed present). Recurring mission-level failure: every successful
push eventually exiles the ball (under furniture / out of the room) — the passive
scoop/corral attachment (see `docs-hub chasebot/docs/scoop-attachment-brief`) is
the unlock for capture-and-carry.

**Detector correction + hybrid feed validation (2026-07-02 PM).** On the repaired
gstreamer/ISP camera path (15 fps, auto-exposure), a three-way bake-off on real
bench frames showed **YOLO-World v2 zero-shot prompted with "ball"** beats the
yolov5m-ONNX "sports ball" stack decisively: 0.38–0.56 vs 0.09 on the easy
near-ball case, only detector to find the far-ball-on-glossy-mat case, and **zero
false positives across ~20 archived ball-less bench frames at conf 0.05**
(9 ms/frame on the RTX 5060). The earlier in-session dismissal of YOLO-World was
traced to a contaminated test frame (`irl_overlay.jpg`: dark v4l2_bayer capture
with a burned-in annotation overlay). Frame-diff auto-labels (labeled_diff_v1 /
walk02_v1) were audited and found poisoned (boxes on background flicker, ball in
the median background) — quarantined; the corpus was relabeled zero-shot
(2791 clean labels from 4025 frames, review-sampled) and a yolov8n single-class
fine-tune targets `runtime/yolo/golfball_finetune.pt`, which the control server
auto-prefers over the World backend. Pipeline: `tools/robot_factory_bridge/finetune/`.
The control server (`chasecar_bridge_control_server.py`, :8791) now serves
`det_ts` + keepalive-on-/status, and the **onboard hybrid loop was dry-run
validated end-to-end**: Jetson `--detector remote` consumed the laptop
YOLO-World feed (conf 0.42–0.66, z≈0.26 m stable, ~3 Hz onboard, rate-aware
no_new_data holds, final_safe) with the bridge locked throughout. **The
fine-tune landed the same day**: yolov8n on 2791 zero-shot labels (mAP50 0.995,
2373/418 split), acceptance-gated on held-out frames — **0.97/0.97/0.93 conf on
the three real-ball frames including both glossy-mat hard cases, 0 false
positives across 19 ball-less frames**, and it recovered a ball that both
YOLO-World and the ONNX stack had missed (`try_now.jpg`). Known limit: it is
scene-specialized (misses the dark wood-floor-room captures from the old camera
path); YOLO-World stays in the fallback chain for new scenes. Installed as
`runtime/yolo/golfball_finetune.pt`; the control server picks it up on start
(`detector backend: finetune`). Remaining for a live hybrid episode:
power the robot on (bridge deploy after boot) + operator-supervised GO.

**Onboard GPU proven (2026-07-02 evening).** Hardware identity settled by photo +
purchase trail + `/proc/device-tree/model`: the robot has exactly ONE compute
board, the kit's Jetson Nano 4GB (no Orin — the earlier inventory claim was a
mis-recollection; the "attached GPU with the big black fan" is the kit Nano and
its heatsink fan). The fine-tune was exported to ONNX (opset 11, imgsz 320,
simplified) and built into a TensorRT 7.1 FP16 engine ON the Nano
(`/home/jetson/chasecar_onboard/golfball_finetune_fp16.engine`, 8.4 MB):
**13.5 ms/frame GPU compute, ~73 FPS throughput** — ~15× the current CPU color
loop and ~40× the Wi-Fi feed rate. Live-camera validation of the laptop
fine-tune feed same evening: 0.92 conf, z=0.35 m on the dashboard. Next slice:
a py3.6 TRT inference wrapper (tensorrt 7.1 bindings present; NO pycuda — use
ctypes/libcudart for buffers) plumbed into `chasecar_onboard_fetch.py` as
`--detector trt` → fully self-contained robot eyes, Wi-Fi out of the loop.

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
| `yolo_object_pose_observation_adapter` | In progress (2026-06-28) | Convert bridge camera observations into the object state the sim stack needs: target class, freshness, 2D bbox, distance or pose estimate, and delivery-target geometry with explicit confidence and limitation fields. Detector + calibrated distance/pose + uncertainty built and offline-validated; remaining: delivery geometry (D3), base_link frame (D4), policy wiring. See Evidence Boundary. |
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

### Object-pose observation adapter (in progress, 2026-06-28)

YOLO is the hardware detector of record: it cleanly isolates the golf ball
(`sports ball`, conf ~0.7) where color/bright segmentation fails in the dim,
reflective bench scene; color stays a safety fallback. Monocular distance uses
the calibrated apparent-size law `z = K / size_px` — the modern, calibrated form
of the legacy `ros2_scripts/ros2_ball_to_nav_goal.py` estimator (the D415 depth
path is unavailable on the mono CSI hardware). A 3-point bench calibration (golf
ball at 12/22/36 in) fit `K = 9.62 px·m` on the YOLO bbox equivalent diameter
(implied focal ~225 px, effective HFOV ~71 deg), `sigma_s = 1.72 px`, usable
range ~0.25-0.9 m (6 in clips the frame bottom; >36 in the ball is <9 px and
detection drops). The adapter emits class, bbox, confidence, freshness, `z`,
bearing, `sigma_d`, and a `pose_status` (`metric` / `bearing_only` /
`unavailable`) limitation field. Offline validation on the saved 12 in frame
estimated `0.294 m` vs `0.305 m` true (1.1 cm error). Remaining before promotion:
delivery-target geometry (D3), base_link frame transform (D4), and wiring the
observation into the sim-stack policy state. Tools (16 offline unit tests):
`tools/robot_factory_bridge/chasecar_bridge_mono_distance_calibration.py`,
`chasecar_bridge_object_pose_observation.py`,
`chasecar_bridge_object_pose_adapter.py`. Calibration artifact (on disk;
`artifacts/` gitignored): `artifacts/session/mono_distance_calibration_bench01/`.
Workstation `onnxruntime` now installed via pip wheel (the vendored copy in
`.codex_yolo_deps/` failed to load — DLL/VC++ runtime).

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
