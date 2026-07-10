# Handoff: chasebot hw-v0 → Codex gpt-5.6-sol spine (2026-07-04)

Audience: the Codex spine thread (`019ee82b-6b01-7a50-aafe-019f4775956e`), now
running **gpt-5.6-sol at xhigh** (owner switch), and any supervisor session
resuming this lane. Self-contained: read this plus
`docs/HARDWARE_V0_STACK_THROUGH_BRIDGE_PLAN.md` (governing plan, current) and
you have the whole state. The June sim lane is PAUSED at its June-11 state
(`docs/ACTIVE_WORKFLOW.md`); hardware-v0 IRL is the active workstream.

## What this lane is

JetBot Mini ("Chasecar") golf-ball fetch robot, real hardware. Mission ladder:
fetch (find→approach→push) → deliver-to-target → multi-surface robustness.
Current rung: reliable fetch with fully-onboard perception; delivery target
(fiducials) is next.

## Hardware truth (do not re-litigate; all bench-measured)

- ONE compute board: factory **Jetson Nano 4GB** (JetPack 4.4, **Python
  3.6.9**, TensorRT 7.1.3, no pycuda). NO Orin. NO encoders (no odometry).
  NO depth camera. Camera 320x240@15fps gstreamer/ISP (never
  `-CameraBackend v4l2_bayer`).
- Motor chain: bridge `cmd_vel_to_motors` (chasecar_factory_bridge.py:1130)
  scales linear_x*0.583 → motor. **Static stiction ~0.30 motor** (forward,
  from rest); rolling lower (~0.18). Bench floors: linear_x ≥ 0.5143 for
  motion from rest; turn_angular_z 2.3 with bridge `-TurnGain 1.0`.
- **Surface matters**: in-place pivot works briskly on hard floor at
  angular 2.3; STALLS on carpet (wheels scrub through fibers). Forward
  rolls fine on both. Never conclude "chassis can't X" from a carpet run.
- Wi-Fi: robot hosts AP `jetbot-mini`; laptop joins via
  `netsh wlan connect name="jetbot-mini"`. Requests arrive / responses get
  lost under flap; ssh wrapper timeouts must exceed ConnectTimeout (≥6s).
- Robot boot: bridge does NOT autostart —
  `scripts/deploy_robot_factory_bridge.ps1 -RobotHost 192.168.1.11
  -RobotUser jetson -Start -Camera -TurnGain 1.0` (boots LOCKED).

## Stack as deployed (all pushed, branch codex/hw-irl-v0-bringup)

- **Perception (SOLVED)**: v3 fine-tune (yolov8n, 4 surfaces + night) runs
  ONBOARD via TensorRT at 640px, 46ms ≈ 21 FPS (`--detector trt`, engine
  `/home/jetson/chasecar_onboard/golfball_finetune_fp16.engine`). Laptop
  dashboard runs a fine-tune→YOLO-World ensemble as spectator feed + labeler.
  Data flywheel: every GO auto-banks outcome-tagged frames to
  `artifacts/finetune_dataset/inbox/`; crank = `finetune/flywheel_prepare.py`
  (label + montage for owner audit) → owner "ship it" →
  `scripts/flywheel_ship.ps1` (train→gate→install→640 ONNX→engine build on
  robot→smoke). Acceptance gate `finetune/acceptance_gate.py` (append-only
  anchor registry + zero-FP sweep; anchors must live in labeled_* dirs, not
  session dirs). Trainer self-tunes compute (auto-batch, disk cache,
  commit-aware workers; never cache="ram" with workers on Windows).
- **Control (ACTIVE WORK)**: onboard brain `chasecar_onboard_fetch.py`
  (py3.6-clean, self-contained). Two steering modes, dashboard-selectable:
  - `pulse` (default): bang-bang scan/turn/forward. PROVEN: basement fetch
    3.5s standoff+push. Wobbles (limit cycle: 11° min pulse vs 3.6° deadband).
  - `arc` (opt-in): BallTracker (alpha-beta) + two-regime servo
    (turn-in-place when |err|>turn_gate 0.55; forward ≥ stiction floor with
    bounded trim otherwise). Gains via dashboard ARC_GAINS: kp 0.30 kd 0.10
    slew 1.00 turn-gate 0.55. Status: forward regime PROVEN on hard floor
    (standoff+push, onboard_1652153224); turn regime stalled on CARPET only
    (surface artifact, retracted as code bug); **hard-floor off-center test
    NOT yet run** — that is the next bench experiment. Mid-band
    (0.12<|err|<0.55) also untested.
- **Ops**: laptop control server `chasecar_bridge_control_server.py` :8791
  (GO/RESET/STOP + 2D jog pad + PULSE/ARC toggle + verified-STOP with
  health read-back; jog idle-watchdog relocks). Tailscale
  https://chasebox.tail3b1bce.ts.net/ for phone. RESET = dead-reckoned
  reverse-replay of the episode motion tape. Every episode start
  synchronously pkills remote orphans (**pattern must be self-excluding:
  `pkill -f 'chasecar_onboard_fetc[h]'`** — plain pattern kills its own ssh
  shell, rc -1, silent).
- **Planner port (READY, unwired)**: `onboard_route_policy.py` — py3.6 port
  of the sim route classifier + plan compiler, 510-scene parity-proven vs
  `scripts/fetch_planner_handoff_gate.py`. Wiring gaps documented in
  `docs/notes/route-policy-port.md`: needs target pose (fiducial slice) +
  lateral/yaw vs ball-target line; corridor/clearance has no sensor.
- **Sim harness**: `sim_arc_tuning.py` — kinematic model with per-wheel
  stiction applied AFTER the bridge motor mapping (mirror verified against
  chasecar_factory_bridge.py:1130). Reproduces the real forward stall.
  Rotational scrub (carpet) NOT modeled; rotation model unvalidated.
- **CI**: `.github/workflows/ci.yml` — py3.6 vermin gate on both onboard
  files, onboard --selftest, STOP-helper regression tests, ast/PS parse.
  CD stays supervised by policy (motion-capable robot: CI proves
  eligibility, a human deploys).

## History Codex must know about its own past deliverables

1. Servoing+STOP slices (2026-07-03): landed, BUT the fail-closed prestart
   pkill guard exposed that every remote pkill had been silently
   self-matching its own ssh shell — supervisor fixed pattern + raised
   sub-second ssh timeouts (0.5–1.2s → 4–8s). Lesson: wrapper timeout >
   ssh ConnectTimeout; pkill patterns self-excluding.
2. Arc v1 (2026-07-04 00:08): STALLED on bench — sim had blessed it because
   stiction was checked in linear_x units pre-scaling. Fixed by your
   stiction-model + two-regime slices (2d1f950, 4541199) with the
   reproduce-the-real-stall pytest gate. That gate discipline is now
   mandatory: a sim only earns tuning authority by reproducing an observed
   hardware failure.
3. Arc v2 turn-regime "failure" (2026-07-04 10:09): commanded correct
   in-place turn, robot didn't rotate — later RETRACTED as carpet artifact
   (owner confirmed brisk pivot on hard floor via jog). Do not "fix" the
   turn regime without a hard-floor failure in evidence.

## Work queue (priority order)

1. **(bench, operator-gated)** Hard-floor off-center arc A/B: ball at
   |err|>0.6 on hardwood, dashboard ARC, GO. If it pivots-centers-fetches:
   arc validated, close the saga. If it stalls on HARD floor: real bug —
   pull trace `/home/jetson/chasecar_onboard/runs/onboard_*.jsonl` first,
   suspect regime transition or tracker, not physics.
2. **Fiducial slice (software, no robot)**: laptop-side ArUco detection in
   the control server (laptop cv2 5.0 has aruco; robot cv2 4.1.1 does NOT —
   never install onboard), served like the ball det (`target` field in
   /status). Sim world marker optional. Owner prints a ~10cm marker.
   Unlocks: delivery mission + the descriptor fields onboard_route_policy
   needs.
3. **Wire the ported planner** once target pose exists: scene-descriptor
   builder from BallTracker + target det + staleness; route the onboard
   loop through deterministic_route_label for scan/approach/deliver
   sequencing. Parity test stays green.
4. **Carpet mode (deferred, owner call)**: pivot-on-carpet needs either
   rolling arc-turns, kickstart bursts, or higher motor cap — measure
   carpet pivot threshold first via jog; do NOT tune blind.
5. **Maintenance window (post-demo, owner-scheduled)**: JetPack 4.4→4.6
   (TRT 8.2) on a bigger SD (disk 88% full); encoder-motor retrofit (~$30
   Yahboom drop-ins) = real odometry, owner spend decision pending.

## Protocols (binding)

- Safety: bridge boots LOCKED; never enable motion/cmd_vel/GO/RESET/jog in
  an automated turn — the operator drives. Deploy = scp + no-motion smokes
  (--selftest, --dry-run). Every episode must end final_safe.
- py3.6 discipline for anything scp'd to the robot; CI vermin-gates it.
- QUESTIONS: block at end of every turn for anything outside bounds;
  supervisor triages (code-level answered directly, whiteboard/design/spend
  → Fred with options + default).
- Evidence rules: bench conclusions cite a trace/run id; sims cite a
  reproduction gate; never benchmark perception on annotated/overlay frames;
  label audits are eyeball-mandatory before training (frame-diff labeling is
  known-poison on this bench).
- Commit per slice, no push (supervisor reviews + pushes). CI must pass.

## Environment quickstart (supervisor shell, Windows)

- Bench up: join AP → deploy bridge (cmd above) → scp onboard files →
  dashboard `Start-Process python tools\robot_factory_bridge\
  chasecar_bridge_control_server.py` (WorkingDirectory repo root).
- Resume this spine (desktop-born: MCP codex-reply does NOT work; app may
  ARCHIVE it — run `codex unarchive <id>` first if resume errors):

```powershell
$codex = (gci 'C:\Users\afutu\AppData\Local\OpenAI\Codex\bin\*\codex.exe' |
          Sort-Object LastWriteTime -Descending)[0].FullName
Get-Content prompt.txt -Raw | & $codex exec resume 019ee82b-6b01-7a50-aafe-019f4775956e `
  -c sandbox_mode="workspace-write" -c approval_policy="never" `
  -m gpt-5.6-sol -c model_reasoning_effort="xhigh" --output-last-message out.txt -
```

Sandbox blocks network (pip/ssh); robot-touching turns need
`--dangerously-bypass-approvals-and-sandbox` plus the no-motion bounds
stated explicitly in the prompt.
