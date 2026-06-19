# Robot Factory Bridge

This bridge lets Chasecar talk to the factory Yahboom/JetBot Mini runtime while the robot image stays intact.

The bridge runs as one Python process on the robot. It exposes HTTP endpoints for health, stop, camera snapshot, direct motor pulses, and Chasecar-style `cmd_vel` commands. Motion starts only when the process is launched with `--enable-motion`.

The default motor backend uses the same Yahboom I2C command format as the factory web app: direction and speed bytes for the left and right motors in one write.

Camera mode serves a cached `320x240` JPEG from a background encoder by default. The current JetBot Mini hardware uses the onboard CSI camera through the GStreamer/Argus backend, which avoids the crashing `jetbotmini`/`cv2` Python camera imports observed during bring-up. The legacy `jetbotmini` camera backend remains available with `-CameraBackend jetbotmini` when the factory Python camera package is healthy. The dashboard requests one image at a time and follows the configured camera FPS so a slow Wi-Fi link stays focused on the newest frame. Tune `-CameraWidth`, `-CameraHeight`, `-CameraFps`, `-CameraJpegQuality`, and `-CameraBackend` in the deploy wrapper when the operator needs a different balance between clarity and responsiveness.

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
   python tools/robot_factory_bridge/chasecar_bridge_stack_path_gate.py --pretty --artifact-dir artifacts/session/manual_factory_bridge_stack_path_locked --command-linear-x 0 --command-angular-z 0.2
   ```

   The gate writes a Chasecar-style runtime command, publishes it through ROS `/cmd_vel`, forwards it through the factory bridge relay, and requires the locked bridge to refuse motion with HTTP `423`. A passing run proves the workstation stack path reaches the robot bridge without moving the robot.

10. Run one bounded live stack-path motion proof after the locked gate passes:

   ```powershell
   python tools/robot_factory_bridge/chasecar_bridge_stack_path_gate.py --pretty --artifact-dir artifacts/session/manual_factory_bridge_stack_path_live --execute-motion --confirm-operator-ready --command-linear-x 0 --command-angular-z 0.2 --max-bridge-linear-x 0 --max-bridge-angular-z 0.8 --max-motor-speed 0.7
   ```

   The live gate uses the same runtime JSON, ROS `/cmd_vel`, relay, and bridge path. It enables motion only for the bounded turn-only slice, records before/after camera evidence, and restores locked bridge health before returning success.

11. Restart with motion enabled for lifted-wheel tests:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/deploy_robot_factory_bridge.ps1 -RobotHost 192.168.1.11 -RobotUser jetson -Start -EnableMotion
   ```

12. Run the lifted-wheel test only while the operator holds the robot clear of the floor:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/test_robot_factory_bridge_lifted_wheels.ps1 -RobotHost 192.168.1.11 -ConfirmHeldInAir
   ```

13. Run the bounded camera-gated turn behavior after the operator confirms the setup:

   ```powershell
   python tools/robot_factory_bridge/chasecar_bridge_behavior_runner.py --pretty --mode tiny-turn --execute-motion --confirm-operator-ready --artifact-dir artifacts/session/manual_factory_bridge_tiny_turn
   ```

   The runner captures camera evidence, sends the bounded `linear_x` / `angular_z` command plan, sends a final stop, and writes `behavior_summary.json`.

14. Run a floor-clear 90-degree camera proof:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/run_robot_factory_bridge_motion_rehearsal.ps1 -RobotHost 192.168.1.11 -Turn90Proof -ExecuteMotion -ConfirmFloorClear -MaxMotorSpeed 0.20
   ```

   The rehearsal runs the safe preflight, proves the turn plan is refused while motion is locked, restarts with motion enabled, runs the bounded multi-pulse turn plan, writes before/after camera evidence, and returns the bridge to health mode. Floor-turn proof also requires saved frames to show visual movement; static before/after frames fail with `visual_motion_not_confirmed` even when the bridge accepted motor commands.

15. Stop the bridge:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/stop_robot_factory_bridge.ps1 -RobotHost 192.168.1.11 -RobotUser jetson
   ```

Rollback is delete-only: stop the process and remove `/home/jetson/chasecar_factory_bridge`.
