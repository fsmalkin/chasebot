# Robot Factory Bridge

This bridge lets Chasecar talk to the factory Yahboom/JetBot Mini runtime while the robot image stays intact.

The bridge runs as one Python process on the robot. It exposes HTTP endpoints for health, stop, camera snapshot, direct motor pulses, and Chasecar-style `cmd_vel` commands. Motion starts only when the process is launched with `--enable-motion`.

The default motor backend uses the same Yahboom I2C command format as the factory web app: direction and speed bytes for the left and right motors in one write.

Camera mode serves a cached `320x240` JPEG from a background encoder by default. The current JetBot Mini hardware uses the onboard CSI camera through the GStreamer/Argus backend, which avoids the crashing `jetbotmini`/`cv2` Python camera imports observed during bring-up. When Argus crashes but `/dev/video0` still exposes the fixed IMX219 sensor as raw `RG10`, use `-CameraBackend v4l2_bayer` to capture one raw Bayer frame through V4L2 and convert it to JPEG in the bridge process. The legacy `jetbotmini` camera backend remains available with `-CameraBackend jetbotmini` when the factory Python camera package is healthy. The dashboard requests one image at a time and follows the configured camera FPS so a slow Wi-Fi link stays focused on the newest frame. Tune `-CameraWidth`, `-CameraHeight`, `-CameraFps`, `-CameraJpegQuality`, and `-CameraBackend` in the deploy wrapper when the operator needs a different balance between clarity and responsiveness.

Current direction:

The bridge is the safety and transport layer for the offboard Chasecar
sim-stack policy. The primary behavior route is
`chasecar_stack_fetch_adapter_v0` to runtime handoff, ROS relay, factory bridge
HTTP command, and final relock. Bright/color bbox handling is calibration and
safety-stop fallback for lighting, centering, stiction, and conservative
terminal-stop probes.

The latest bridge-visual terminal pass is
`artifacts/session/manual_sim_stack_irl_back_up_live_bright_bbox_terminal_approach_20260625_002/closed_loop_summary.json`.
It proves bridge access, camera freshness, lock/relock, motor direction,
acquire-turn stiction floor, visual acquisition, bounded forward approach, and
a bridge-visual terminal stop. It is outside full 3D/object-pose fetch-to-pose
scope.

Safety defaults:

- `--enable-motion` is required before `/motors` or `/cmd_vel` can move wheels.
- `--deadman-timeout-s 0.5` stops the motors if commands stop arriving.
- `--max-command-duration-s 1.0` bounds each command.
- `--max-motor-speed 0.35` clamps wheel power during early bring-up.

Basic flow:

1. Deploy and start health mode:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/deploy_robot_factory_bridge.ps1 -RobotHost 192.168.1.11 -RobotUser jetson -Start -Camera
   ```

   Use the fixed raw-camera fallback when `nvargus-daemon` is failed and `/dev/video0` still lists `Pixel Format: 'RG10'`:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/deploy_robot_factory_bridge.ps1 -RobotHost 192.168.1.11 -RobotUser jetson -Start -Camera -CameraBackend v4l2_bayer
   ```

   Open `http://192.168.1.11:8765/dashboard` for bridge health, camera, recent commands, and operator notes.

2. Check direct access from the laptop:

   ```powershell
   python tools/robot_factory_bridge/chasecar_bridge_preflight.py --pretty --artifact-dir artifacts/session/manual_factory_bridge_safe_preflight
   ```

   The safe preflight checks bridge health, camera readiness, a snapshot, a short camera video, and the motion lock. The command-refusal check sends zero velocity while motion is locked, so a passing run proves the command path is reachable and still guarded.

3. Run individual checks when you want smaller pieces:

   ```powershell
   python tools/robot_factory_bridge/chasecar_bridge_client.py --pretty health
   python tools/robot_factory_bridge/chasecar_bridge_client.py --pretty camera-diagnostics --frames 8 --interval-s 0.2
   python tools/robot_factory_bridge/chasecar_bridge_client.py --pretty snapshot --output artifacts/session/manual_factory_bridge_camera/camera.jpg
   python tools/robot_factory_bridge/chasecar_bridge_client.py --pretty record-video --seconds 3 --fps 5 --output-dir artifacts/session/manual_factory_bridge_camera_video
   ```

   These checks read bridge state, score camera readiness, save a camera frame, and record a short camera clip while the robot stays still. The video command writes `camera.gif`, `camera.mp4` when ffmpeg is available, and the source JPEG frames.
   The bridge also exposes `/camera.json`, which returns the latest cached JPEG
   as base64 for links where direct `/camera.jpg` reads hang.
   Stack gate and endurance runners also support `--camera-fetch-mode ssh` for
   the same transport failure. That mode runs `curl` on the robot against
   `127.0.0.1:8765/camera.jpg`, copies the JPEG back with `scp`, and records the
   selected fetch path in the snapshot artifact. Use it only after SSH access is
   reachable and the bridge health endpoint proves a locked state.

4. Confirm that motion is still locked while the bridge is in health mode:

   ```powershell
   python tools/robot_factory_bridge/chasecar_bridge_client.py --pretty cmd-vel --linear-x 0.05 --angular-z 0 --duration-s 0.1 --expect-refusal
   ```

   A successful refusal returns `http_status: 423` with `error: "expected_refusal"`.

5. Run the camera-gated no-motion behavior runner:

   ```powershell
   python tools/robot_factory_bridge/chasecar_bridge_behavior_runner.py --pretty --mode no-motion-command --artifact-dir artifacts/session/manual_factory_bridge_no_motion
   ```

   This runner performs the camera readiness gate and then proves the bridge refuses a Chasecar-style `cmd_vel` while motion is locked.

6. Prove a Chasecar-style command plan reaches the bridge while motion stays locked:

   ```powershell
   python tools/robot_factory_bridge/chasecar_bridge_behavior_runner.py --pretty --mode plan-refusal --artifact-dir artifacts/session/manual_factory_bridge_plan_refusal
   ```

   The runner loads the bounded `linear_x` / `angular_z` plan, checks the camera gate, requires `motion_enabled=false`, and expects every planned command to return `http_status: 423`.

7. Run the target scan while motion stays locked:

   ```powershell
   python tools/robot_factory_bridge/chasecar_bridge_behavior_runner.py --pretty --mode visual-scan --artifact-dir artifacts/session/manual_factory_bridge_visual_scan
   ```

   The scan captures one camera frame, tries the supported target color profiles, writes annotated images, and ranks the best safe target candidate. Broad color casts or missing targets become a safe no-op.

8. Run the camera-guided advisor while motion stays locked:

   ```powershell
   python tools/robot_factory_bridge/chasecar_bridge_behavior_runner.py --pretty --mode visual-advisor --target-profile yellow --artifact-dir artifacts/session/manual_factory_bridge_visual_advisor
   ```

   The advisor captures one camera frame, marks a target candidate when one is visible, and writes the bounded `linear_x` / `angular_z` recommendation without sending a motion command. Broad color casts or missing targets become a safe no-op.

9. Prove the offboard stack-through-bridge command path while motion stays locked:

   ```powershell
   python tools/robot_factory_bridge/chasecar_bridge_stack_path_gate.py --pretty --artifact-dir artifacts/session/manual_factory_bridge_stack_path_locked --policy-entrypoint chasecar_stack_fetch_adapter_v0 --target-profile blue --max-bridge-linear-x 0.08 --max-bridge-angular-z 0.8
   ```

   The gate captures a bridge camera frame, runs the `chasecar_stack_fetch_adapter_v0` policy entry point, writes the policy command to the Chasecar runtime handoff, publishes it through ROS `/cmd_vel`, forwards it through the factory bridge relay, and requires the locked bridge to refuse motion with HTTP `423`. A passing run proves the workstation policy path reaches the robot bridge while the robot stays physically locked. The artifact records the Chasecar supervisor snapshot, command provenance, and whether a learned low-level fetch checkpoint was loaded.

10. Run one bounded live stack-path motion proof after the locked gate passes:

    ```powershell
    python tools/robot_factory_bridge/chasecar_bridge_stack_path_gate.py --pretty --artifact-dir artifacts/session/manual_factory_bridge_stack_path_live --policy-entrypoint chasecar_stack_fetch_adapter_v0 --target-profile blue --execute-motion --confirm-operator-ready --live-motion-require-turn-only --max-bridge-linear-x 0.08 --max-bridge-angular-z 0.8 --max-motor-speed 0.7
    ```

   The live gate uses the same runtime JSON, ROS `/cmd_vel`, relay, and bridge path. The first physical proof should include the turn-only guard so a forward stack command fails closed before live motion. A passing run enables motion only for the bounded stack-adapter slice, records before/after camera evidence, and restores locked bridge health before returning success.

11. Run the bounded closed-loop stack adapter while motion stays locked:

    ```powershell
    python tools/robot_factory_bridge/chasecar_bridge_stack_closed_loop_runner.py --pretty --artifact-dir artifacts/session/manual_factory_bridge_stack_closed_loop_locked --steps 2
    ```

    The loop repeats fresh observation, stack policy decision, relay handoff, bridge refusal, and final relock checks for each step. It stops on target-too-close, stale camera, command mismatch, unsafe bridge state, or conflicting visual evidence.

12. Run the bounded live closed-loop proof after the locked loop passes:

    ```powershell
    python tools/robot_factory_bridge/chasecar_bridge_stack_closed_loop_runner.py --pretty --artifact-dir artifacts/session/manual_factory_bridge_stack_closed_loop_live --steps 2 --execute-motion --confirm-operator-ready
    ```

    Defaults for the current blue target setup are `--target-profile blue`, `--max-bridge-linear-x 0.08`, `--max-bridge-angular-z 0.8`, `--max-motor-speed 0.7`, and `--stack-forward-stop-area-ratio 0.20`.

13. Run the progress-scorecard live loop before contact tests:

    ```powershell
    python tools/robot_factory_bridge/chasecar_bridge_stack_closed_loop_runner.py --pretty --artifact-dir artifacts/session/manual_factory_bridge_stack_progress_live --steps 3 --step-settle-s 1.0 --target-min-area-ratio 0.008 --execute-motion --confirm-operator-ready
    ```

    The runner writes `real_stack_boot_report.json`,
    `real_stack_boot_report.md`, `progress_scorecard.json`, and
    `progress_scorecard.md`. The boot report names the active Chasecar stack
    slice, runs a deterministic supervisor-policy smoke, and lists the
    ROS/Nav2/object-pose adapters still required for full stack onboarding. The
    scorecard compares target area and centering across live steps, includes a
    final post-loop target observation for the last pulse, and fails the run
    when target loss, meaningful regression, stale camera, visual contradiction,
    command mismatch, or unsafe final health appears.

Current basement bottle-target shakedown:

The basement setup currently uses the `v4l2_bayer` camera fallback and
PC-side YOLO ONNX inference as detector input for the intended bottle target.
The wrapper preset `basement_green_v0` still carries the current scene
thresholds, YOLO fallback area threshold, and lower camera FPS gate used by
this hardware setup. Run the locked wrapper proof first. It exercises scan,
closed-loop policy, relay refusal, inverse-reset no-op, motor-budget
accounting, and final relock while motion stays disabled:

```powershell
$env:PYTHONPATH=(Resolve-Path .codex_yolo_deps).Path
python tools/robot_factory_bridge/chasecar_bridge_overnight_endurance_loop.py --base-url http://192.168.1.11:8765 --artifact-dir artifacts/session/manual_sim_stack_irl_basement_locked_overnight_wrapper_budget_smoke --target-preset basement_green_v0 --max-cycles 1 --cycle-sleep-s 0 --steps 2 --min-completed-steps 1 --step-retries 0 --detector-backend yolo_onnx_or_color --camera-fetch-mode ssh --no-require-nav-target-success --max-accepted-motor-events-per-cycle 1 --max-accepted-motor-duration-s-per-cycle 0.30 --pretty
```

After the operator confirms the floor is flat, clear, and watched, run one
bounded live pulse through the same wrapper. Keep an operator stop file path in
the command; creating that file terminates the loop, stops the bridge, relocks,
and writes final health:

```powershell
$env:PYTHONPATH=(Resolve-Path .codex_yolo_deps).Path
python tools/robot_factory_bridge/chasecar_bridge_overnight_endurance_loop.py --base-url http://192.168.1.11:8765 --artifact-dir artifacts/session/manual_sim_stack_irl_basement_live_first_pulse --operator-stop-file artifacts/session/manual_sim_stack_irl_basement_live_first_pulse.stop --target-preset basement_green_v0 --max-cycles 1 --cycle-sleep-s 0 --steps 1 --min-completed-steps 1 --step-retries 0 --detector-backend yolo_onnx_or_color --camera-fetch-mode ssh --no-require-nav-target-success --max-accepted-motor-events-per-cycle 1 --max-accepted-motor-duration-s-per-cycle 0.30 --command-duration-s 0.20 --max-bridge-linear-x 0.04 --max-bridge-angular-z 0.8 --max-motor-speed 0.35 --execute-motion --confirm-operator-ready --pretty
```

The live shakedown passes only when the bridge finishes locked, both motors
return to zero, the intended bottle target remains visible through YOLO,
accepted motor count stays within budget, and inverse reset succeeds or records
a clean no-op.

Serial gate ladder:

Use the gate ladder report before selecting the next live slice. The report
records bridge health plus saved artifact summaries. Treat access, camera,
lock/relock, motor direction, stiction floor, visual acquisition, bounded
approach, and bridge-visual terminal stop as foundation evidence.

The behavior ladder is now:

```text
sim_stack_offboard_policy_routing -> yolo_object_pose_observation_adapter ->
terminal_fetch_to_pose_proof -> endurance_loop
```

```powershell
python tools/robot_factory_bridge/chasecar_bridge_gate_ladder_report.py --base-url http://192.168.1.11:8765 --artifact-dir artifacts/session/manual_factory_bridge_gate_ladder --evidence artifacts/session/<locked_run>/overnight_loop_summary.json --evidence artifacts/session/<policy_routing_run>/closed_loop_summary.json --evidence artifacts/session/<observation_adapter_run>/observation_adapter_summary.json --evidence artifacts/session/<terminal_fetch_to_pose_run>/closed_loop_summary.json --pretty
```

Color-only and bright-bbox evidence helps diagnose scene geometry, lighting,
frame exposure, stiction floors, and conservative terminal stops. The current
next gate is sim-stack offboard policy routing through
`chasecar_stack_fetch_adapter_v0`. The observation adapter, terminal
fetch-to-pose proof, and endurance gates follow in that order.

Current observation and calibration notes:

The active upstairs/Prime-bottle v0 detector path is PC-side
`runtime/yolo/yolov5s.onnx` over direct HTTP camera fetch. The bridge is using
the `v4l2_bayer` camera fallback at about `1.2` cached FPS. Fresh evidence on
June 25, 2026 showed `yolov5s.onnx` detecting the visible bottle at low
confidence and producing stable centered target observations across a locked
two-step stack loop. Use that detector output as input to the object-pose
observation adapter.

Use these parameters for the current Prime-bottle stack gates:

```powershell
--camera-fetch-mode http --camera-min-fps 1.0 --camera-max-frame-age-s 2.0 --yolo-onnx-model runtime/yolo/yolov5s.onnx --yolo-onnx-confidence-threshold 0.001 --yolo-target-min-area-ratio 0.001 --relay-start-timeout-s 60 --relay-finish-timeout-s 20
```

For calibration and fallback terminal-stop probes, use the bright color profile
with the acquire-turn floor and bbox-height stop:

```powershell
--target-profile bright --detector-backend color --target-min-luma 75 --target-min-area-ratio 0.0005 --target-max-area-ratio 0.08 --target-max-bbox-width-ratio 0.25 --target-max-bbox-height-ratio 0.65 --target-max-bbox-aspect-ratio 1.20 --target-max-centroid-y-ratio 0.72 --visual-angular-gain 0.75 --max-policy-angular-z 0.16 --stack-acquire-min-angular-z 0.16 --stack-acquire-max-angular-z 0.16 --stack-forward-stop-bbox-height-ratio 0.30 --command-duration-s 0.12 --max-bridge-linear-x 0.04 --max-bridge-angular-z 0.8 --max-motor-speed 0.35 --motion-control-mode http
```

Direct HTTP camera fetch is the preferred observation path when `/camera.jpg`
responds. SSH camera fetch remains a diagnostic fallback for Windows transfer
stalls; visually similar SSH frames showed lower detector scores in this setup.
Use `chasecar_bridge_yolo_onnx_probe.py --all-classes` as a diagnostic for
misclassified objects. Observation-adapter promotion requires the intended
`bottle` class or selected target class plus the distance or pose fields needed
by fetch-to-pose.

Current pass artifacts:

```text
artifacts/session/manual_sim_stack_irl_back_up_yolo5s_live_repeat_20260625_001/yolo_detection_summary.json
artifacts/session/manual_sim_stack_irl_back_up_locked_stack_path_gate_yolo5s_http_20260625_001/gate_summary.json
artifacts/session/manual_sim_stack_irl_back_up_locked_closed_loop_yolo5s_http_lowconf_20260625_001/closed_loop_summary.json
artifacts/session/manual_sim_stack_irl_back_up_live_bright_bbox_terminal_approach_20260625_002/closed_loop_summary.json
```

The bright-bbox terminal artifact passed with
`terminal_reason=target_inside_stack_forward_stop_bbox_height`,
`target_bbox_height_ratio=0.300`, target center error about `-0.111`, final
`motion_enabled=false`, and left/right motors at `0.0`. Treat it as
access/safety/control evidence while the object-pose observation adapter is
pending.

14. Run the nav-to-target success gate only as a bridge-visual safety-stop
    calibration proof while the object-pose adapter is pending:

    ```powershell
    python tools/robot_factory_bridge/chasecar_bridge_stack_closed_loop_runner.py --pretty --artifact-dir artifacts/session/manual_factory_bridge_nav_target_success --steps 14 --step-settle-s 1.0 --target-min-area-ratio 0.008 --max-bridge-linear-x 0.14 --max-bridge-angular-z 0.8 --max-motor-speed 1.0 --stack-search-angular-z 0.25 --stack-acquire-max-angular-z 0.12 --command-duration-s 0.35 --require-nav-target-success --execute-motion --confirm-operator-ready
    ```

    The runner writes `nav_target_success.json` and
    `nav_target_success.md`. With `--require-nav-target-success`, completing the
    motion budget is insufficient; the run must end with a centered target at
    the configured success area, the configured bbox-height threshold, or a safe
    terminal stop. The deploy step aligns the bridge's linear and angular caps
    with the relay caps, `--stack-acquire-min-angular-z` lifts acquire turns
    above low-speed stiction, and `--stack-acquire-max-angular-z` keeps
    target-centering turns smaller than broad search turns. This gate promotes
    bridge-visual safety only until object trajectory and delivery-radius
    evidence exist.

15. Restart with motion enabled for lifted-wheel tests:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/deploy_robot_factory_bridge.ps1 -RobotHost 192.168.1.11 -RobotUser jetson -Start -EnableMotion
   ```

16. Run the lifted-wheel test only while the operator holds the robot clear of the floor:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/test_robot_factory_bridge_lifted_wheels.ps1 -RobotHost 192.168.1.11 -ConfirmHeldInAir
   ```

17. Run the bounded camera-gated turn behavior after the operator confirms the setup:

   ```powershell
   python tools/robot_factory_bridge/chasecar_bridge_behavior_runner.py --pretty --mode tiny-turn --execute-motion --confirm-operator-ready --artifact-dir artifacts/session/manual_factory_bridge_tiny_turn
   ```

   The runner captures camera evidence, sends the bounded `linear_x` / `angular_z` command plan, sends a final stop, and writes `behavior_summary.json`.

18. Run a floor-clear 90-degree camera proof:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/run_robot_factory_bridge_motion_rehearsal.ps1 -RobotHost 192.168.1.11 -Turn90Proof -ExecuteMotion -ConfirmFloorClear -MaxMotorSpeed 0.20
   ```

   The rehearsal runs the safe preflight, proves the turn plan is refused while motion is locked, restarts with motion enabled, runs the bounded multi-pulse turn plan, writes before/after camera evidence, and returns the bridge to health mode. Floor-turn proof also requires saved frames to show visual movement; static before/after frames fail with `visual_motion_not_confirmed` even when the bridge accepted motor commands.

19. Stop the bridge:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/stop_robot_factory_bridge.ps1 -RobotHost 192.168.1.11 -RobotUser jetson
   ```

Rollback is delete-only: stop the process and remove `/home/jetson/chasecar_factory_bridge`.
