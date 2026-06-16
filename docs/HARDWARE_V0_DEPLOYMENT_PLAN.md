# Hardware V0 Deployment Plan

This plan gets a new operator from a clean Windows worktree to direct,
safe Codex access to the Chasecar hardware. The first target is SSH-level
command access that lets Codex inspect the robot, update code, sync runtime
files, and run no-motion probes. Motion authority comes later, after the robot
has proven power, sensors, command timeout, and lifted-wheel behavior.

## Current Workspace

Use the hardware worktree for this effort:

```powershell
cd D:\dev\chasecar-hw-v0
git status -sb
```

Expected branch:

```text
codex/hw-irl-v0-bringup
```

This worktree shares the same Git repository and remotes as `D:\dev\chasecar`.
Committed changes can be merged, rebased, or cherry-picked between branches.
Uncommitted files stay inside the folder where they were edited.

## Operating Model

The human operator owns physical safety, power, cables, robot placement, and
the emergency stop. Codex owns repo inspection, command preparation, artifact
review, checklist updates, and commits after the operator confirms each rung.

Each rung has one job and one evidence package. Advance only when the evidence
proves the claim for that rung. If the robot moves unexpectedly, loses command
timeout behavior, overheats, drops camera frames, or publishes confusing odom,
stop the run and write the failure down before changing code.

## Fast Track: Codex Direct Hardware Access

Fastest useful milestone: Codex can run no-motion commands on the robot through
SSH, produce a preflight artifact, and identify the repo/runtime path to update.
That gives us direct hardware visibility while physical motion remains locked.

Bench wiring and login setup are handled in
`docs/HARDWARE_BENCH_CONNECTION_RUNBOOK.md`. Start there when the question is
physical power, network cabling, D415 cabling, SSH, or Tailscale.

Operator provides:

- Robot hostname, LAN IP, or Tailscale IP.
- Robot username.
- SSH key or password path the operator is comfortable using.
- Expected robot repo path, if one already exists.
- Confirmation that Codex may run no-motion commands such as `hostname`,
  `uname`, `git`, `python3`, `ros2` discovery, and directory checks.

Codex first command from this worktree:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_robot_direct_access.ps1 -RobotHost <robot-host-or-ip> -RobotUser <robot-user>
```

Add `-RobotRepoPath <path-on-robot>` when the operator already knows where the
repo lives on the Jetson.

Use this form for the first password-based login:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_robot_direct_access.ps1 -RobotHost <robot-host-or-ip> -RobotUser <robot-user> -AllowPasswordPrompt
```

Evidence:

- `artifacts/session/<campaign>/robot_direct_access_preflight/preflight_summary.json`
- `artifacts/session/<campaign>/robot_direct_access_preflight/scorecard.md`
- `direct_access_ready=true`
- `motion_commands_sent=false`

Direct-access levels:

1. `direct_access_ready=true`: Codex can reach the robot and run safe shell
   commands.
2. `ros_command_ready=true`: Codex can also see a ROS command surface on the
   robot.
3. `runtime_update_ready=true`: Codex has an agreed repo/runtime path and can
   sync or pull code there.
4. `motion_command_ready=true`: lifted-wheel controller and deadman checks have
   passed, so Codex can issue tiny operator-approved movement commands.

Fastest next branch outcome:

- Commit this plan and preflight script.
- Ask the operator for robot host and username.
- Run `check_robot_direct_access.ps1`.
- If SSH succeeds, use that channel to inspect OS, ROS, repo path, camera USB,
  and deployment gaps.
- Add a robot-side sync command only after the preflight names the correct path.

## Shared Baseline

The physical target is the Chasecar JetBot-derived differential-drive robot:

- Compute: Jetson Orin Nano 8GB.
- Camera: Intel RealSense D415.
- Runtime target: `robot_fidelity_orin`.
- Inference backend: `tensorrt_int8`.
- Command topic: `/jetbot_base_controller/cmd_vel` with `TwistStamped`.
- Command timeout: `0.5 s`.
- Deadman timeout: `0.5 s`.
- Controller update rate: `100 Hz`.

Authoritative references:

- `docs/ROBOT_HARDWARE_CONTRACT_ORIN_NANO.md`
- `docs/ROBOT_HARDWARE_CONSTRAINTS.md`
- `runtime/tensorrt/README.md`
- `docs/ACTIVE_WORKFLOW.md`

## Rung 0: Confirm The Active Folder And Branch

Claim: the operator and Codex know which folder and branch are active.

Commands:

```powershell
cd D:\dev\chasecar-hw-v0
git status -sb
git remote -v
git branch --show-current
```

Evidence:

- Worktree path is `D:\dev\chasecar-hw-v0`.
- Branch is `codex/hw-irl-v0-bringup`.
- Remote is the Chasecar GitHub repo.
- Working tree is clean before the next rung starts.

Pulling newer code:

```powershell
git fetch origin
git merge origin/main
```

If the active integration branch is something other than `main`, replace
`origin/main` with the branch Codex names after inspecting the repo. Local
uncommitted edits in `D:\dev\chasecar` need a commit, stash, patch, or explicit
copy before this worktree can use them.

## Rung 1: Prove The Windows Host Can Run The Toolchain

Claim: the Windows host can run Docker, WSL, PowerShell wrappers, Git, and the
repo scripts needed for sim and deployment prep.

Commands:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_docker_host.ps1 -ExpectedDistro Ubuntu-24.04
docker ps --format "table {{.Names}}\t{{.Status}}"
```

Evidence:

- Docker CLI and Docker Compose respond.
- WSL lists `Ubuntu-24.04`.
- NVIDIA tooling status is known.
- Any running Chasecar compose stack is identified before starting another one.

Stop condition:

- Docker, WSL, or GPU tooling is missing or ambiguous. Capture the output and
  fix the host before touching robot hardware.

## Rung 2: Sync The Latest Source Into The Runtime Workspace

Claim: the code in this worktree has been copied into the ROS runtime workspace
that the wrappers use.

Command:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/sync_runtime_workspace.ps1 -Distro Ubuntu-24.04 -WorkspacePath '~/ros2_ws' -SkipBuild -RosDistro kilted
```

Evidence:

- The command prints `RUNTIME_SYNC_OK=1`.
- The runtime source path resolves to `~/ros2_ws/src/chasecar_runtime`.
- `git status --short` in `D:\dev\chasecar-hw-v0` is still understood after
  the sync because artifacts are excluded from the mirror.

Next sync with build:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/sync_runtime_workspace.ps1 -Distro Ubuntu-24.04 -WorkspacePath '~/ros2_ws' -RosDistro kilted
```

Use the build form after host preflight is green and before sim or robot-side
execution depends on compiled ROS package changes.

## Rung 3: Prove The Sim Gate Before Robot Deployment

Claim: the latest code still passes the first containerized robot-fidelity gate.

Commands:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_compose_gate.ps1 -Action up -Build
powershell -ExecutionPolicy Bypass -File scripts/run_first_uat.ps1 -ExecutionLane container_kilted -Distro Ubuntu-24.04 -RuntimeTarget robot_fidelity_orin
```

Evidence:

- `readiness_report.json` exists under `artifacts/session/<timestamp>/`.
- The report has `runtime_target=robot_fidelity_orin`.
- The report identifies the coordinate UAT summary.
- Visual evidence exists when the run includes visuals.

Stop condition:

- Sim gate fails. Fix or document the sim failure before connecting the robot,
  because hardware debugging should start from a known software baseline.

## Rung 4: Robot Bench Inventory With Motors Inactive

Claim: the robot can be powered, reached, observed, and logged while motion is
physically disabled.

Operator setup:

- Put the robot on a stable bench.
- Keep wheels lifted or motor power disconnected.
- Confirm the emergency stop or power disconnect is within reach.
- Connect the D415 and any required power/network cables.

Evidence to collect:

- Robot power source and battery or bench-supply notes.
- Jetson Orin Nano model and OS version.
- Network address and login method.
- `tegrastats` sample for thermals and power mode.
- Camera connection evidence from the OS.
- Photo of the wiring and bench setup.

Suggested robot-side probes:

```bash
hostname
uname -a
lsb_release -a
nvpmodel -q
tegrastats
lsusb
```

Stop condition:

- Power, thermals, login, camera enumeration, or physical wiring looks unstable.

## Rung 5: Sensor-Only ROS Bring-Up

Claim: the D415 publishes usable RGB and depth data with motors inactive.

Evidence:

- ROS topic list includes D415 color and depth topics.
- Color and depth rates are near `640x480 @ 30 Hz`.
- One raw color frame and one depth-derived frame are captured.
- Camera orientation is documented from the robot's forward direction.

Suggested checks:

```bash
ros2 topic list
ros2 topic hz /d415/color/image_raw
ros2 topic hz /d415/depth/image_rect_raw
ros2 topic echo /d415/color/camera_info --once
```

Stop condition:

- Camera topics are missing, stale, low-rate, incorrectly oriented, or unstable
  under the current cable and power setup.

## Rung 6: Controller And Deadman Proof With Wheels Lifted

Claim: commands reach the controller, odom publishes, and command timeout stops
motion while the wheels are off the ground.

Evidence:

- Controller manager shows the diff-drive controller active.
- `/jetbot_base_controller/cmd_vel` accepts `TwistStamped`.
- `/jetbot_base_controller/odom` or the expected odom witness publishes.
- A short forward command turns wheels in the expected direction.
- Command release stops wheel motion within the configured timeout.

Suggested checks:

```bash
ros2 control list_controllers
ros2 topic info -v /jetbot_base_controller/cmd_vel
ros2 topic echo /jetbot_base_controller/odom --once
```

Tiny lifted-wheel command:

```bash
timeout 0.5 ros2 topic pub -r 20 /jetbot_base_controller/cmd_vel geometry_msgs/msg/TwistStamped "{twist: {linear: {x: 0.03}, angular: {z: 0.0}}}"
```

Stop condition:

- Wrong wheel direction, missing odom, wrong message type, missing timeout, or
  any command path ambiguity.

## Rung 7: Lifted-Wheel Sign Chain

Claim: requested forward and yaw signs agree with wheel direction and odom sign.

Tests:

- Forward only: tiny positive `linear.x`.
- Reverse only: tiny negative `linear.x`.
- Left yaw only: tiny positive `angular.z`.
- Right yaw only: tiny negative `angular.z`.

Evidence:

- Command payloads are saved.
- Wheel direction is described or recorded.
- Odom sign is captured for each command.
- Operator notes confirm the physical direction matches the command intent.

Stop condition:

- Any sign mismatch. Compare `ros2_config/config/jetbot_diff_drive_v1.0.0.yaml`,
  `ros2_config/config/jetbot_controllers.yaml`, controller wiring, and odom
  before running on the floor.

## Rung 8: Ground Crawl With No Ball

Claim: the robot can crawl safely on the floor under low-speed manual or
scripted control.

Operator setup:

- Clear a small floor area.
- Keep one person next to the robot with a hard power stop.
- Start with no ball and no autonomy.
- Use low speed caps below the hardware maximums.

Evidence:

- Forward crawl video.
- Left and right turn video.
- Stop/deadman release video.
- Odom trace and command log.
- Operator note on traction, drift, cable snag, and thermal status.

Stop condition:

- Unexpected acceleration, delayed stop, traction loss, cable risk, thermal
  issue, or odom disagreement.

## Rung 9: Perception While Moving, No Contact

Claim: perception remains usable while the robot moves near a static ball with
contact authority withheld.

Evidence:

- Ball appears in onboard camera video.
- Detection timestamps stay fresh.
- Depth alignment remains plausible while the robot creeps.
- Robot pose, ball pose, and camera frames can be reviewed together.

Stop condition:

- Camera drops, stale detections, vibration blur, poor depth, or target pose
  instability.

## Rung 10: Low-Energy Contact Sandbox

Claim: the robot can make a bounded, low-speed contact with a golf ball while
recording enough evidence to understand the result.

Operator setup:

- One ball.
- Visible delivery circle.
- Short distance.
- Human deadman active.
- Low speed caps.

Evidence:

- Onboard camera video first.
- Top-down or external context video.
- Command log.
- Robot pose/yaw trace.
- Ball trajectory and closest approach to the delivery circle.
- Operator notes for first contact, mid-push, terminal arrival, and final rest.

Stop condition:

- Lateral knock-away, over-rotation, unsafe acceleration, stale perception, or
  confusing video/telemetry alignment.

## Rung 11: Robot-Side Rehearsal Package

Claim: the repo's existing hardware rehearsal tools can now run against a
physical evidence bundle without claiming more than the artifacts prove.

Preflight:

```powershell
python scripts/fetch_hardware_transfer_readiness.py --campaign-id hardware_transfer_readiness_hw_v0
python scripts/fetch_hardware_rehearsal_plan.py --campaign-id hardware_rehearsal_plan_hw_v0
python scripts/fetch_robot_side_rehearsal_preflight.py --campaign-id robot_side_rehearsal_preflight_hw_v0
```

Step runner, preflight only:

```powershell
python scripts/fetch_hardware_rehearsal_runner.py --campaign-id hardware_rehearsal_runner_hw_v0 --step-id runtime_stack_smoke
```

Execution comes after the operator confirms the physical setup:

```powershell
python scripts/fetch_hardware_rehearsal_runner.py --campaign-id robot_side_runtime_stack_smoke_hw_v0 --step-id runtime_stack_smoke --execute --timeout-s 1800
```

Evidence:

- `control_preflight.json`.
- `mission_verdict.json`.
- `visual/raw_camera_browser.mp4`.
- `visual/topdown_telemetry_browser.mp4`.
- `visual/world_stream.mp4`.
- `visual/keyframe_review_contact_sheet.png`.
- Operator visual review covering setup, pre-contact, first contact, mid-push,
  terminal arrival, and final rest.

Formal claim boundary:

- `hardware_transfer_ready=true` means the software package is ready for a
  robot-side rehearsal attempt.
- `hardware_proven=true` requires a physical claim summary with real robot,
  onboard TensorRT, physical camera, field physics, and reviewed visual evidence.

Physical claim command after a real robot run:

```powershell
python scripts/fetch_physical_claim_from_run.py --campaign-id physical_claim_hw_v0 --batch-summary <path-to-physical-batch-summary.json> --confirm-physical-robot --confirm-onboard-tensorrt --confirm-physical-camera --confirm-field-physics
python scripts/fetch_physical_onboard_proof_gap.py --campaign-id physical_gap_hw_v0 --physical-claim-summary artifacts/session/physical_claim_hw_v0/fetch_physical_claim_from_run/physical_claim_summary.json
```

## Branch And Commit Cadence

Use `codex/hw-irl-v0-bringup` as the umbrella branch for the beginner hardware
ladder. Keep commits small and evidence-based:

1. Planning and checklist docs.
2. Host/runtime preflight evidence.
3. Bench inventory evidence.
4. Sensor-only evidence.
5. Controller/deadman evidence.
6. Lifted-wheel sign-chain evidence.
7. Ground crawl evidence.
8. Perception no-contact evidence.
9. Contact sandbox evidence.
10. Robot-side rehearsal evidence.

When a rung needs code changes, make a short-lived branch from the hardware
worktree, merge it back after the rung passes, then return to
`codex/hw-irl-v0-bringup` for the next rung.

## Beginner Handoff Template

Use this template at the end of each hardware session:

```text
Rung:
Claim:
Pass/fail:
Commands run:
Artifact paths:
Videos reviewed:
Physical setup notes:
What surprised us:
Next safe rung:
Stop conditions still open:
```

## Next Safe Action

Start with Rung 0 and Rung 1 from this worktree. After host preflight is green,
sync the runtime workspace in Rung 2. Connect the robot only after the sim gate
or a deliberate operator decision says the software baseline is clear enough for
bench-only inventory.
