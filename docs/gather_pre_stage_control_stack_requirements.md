# Gather Pre-Stage Control Stack Requirements

## Context

The blocked gather-control candidates now share the same first-attempt blocker: fresh `zero` and `plus45` live matrix attempts do not reliably reach behind-ball pre-stage handoff. The latest helper-layer owners failed safely with no pre-stage ball motion/contact. The first lower-stack DWB FollowPath probe accepted `/follow_path` goals but aborted immediately before measured robot progress, while the MPPI FollowPath probe accepted goals and moved the robot without moving the ball but still timed out before measured handoff.

The assumption peel-back is complete enough to keep work below the helper layer. The command-authority audit and MPPI evidence indicate that selected commands can be realized and geometry can improve, but the measured handoff gate still times out. The next work is controller-stack repair/tuning for the `nav2_mppi_follow_path_reacquire_v1` evidence path or an equivalent controller-plugin design, not another manual-drive overlay.

## Next Branch Steps

- Treat `nav2_mppi_follow_path_reacquire_v1` as blocked evidence and repair/tune controller convergence before any promotion work.
- Keep the current `zero` / `plus45` pre-stage handoff gate, while recording intermediate diagnostics for goal-side cleared, trajectory milestone progress, lateral error reduced, yaw reduced, and ball remained still.
- Inspect controller-server feedback/logs and MPPI realization metrics before retuning blocked overlays.

## Requirements

- Own the full pre-stage motion from measured robot pose to measured handoff readiness through Nav2 controller-server ownership, instead of layering another reactive overlay around the current pre-stage loop.
- Separate planned geometry progress from realized controller authority, so the evidence can distinguish "bad waypoint/path" from "commanded motion did not realize enough escape progress."
- Emit explicit commanded-vs-realized progress evidence for projection, lateral error, distance, yaw, waypoint/path progress, command mode, and manual-drive authority.
- Stop or hold on ball motion, predicted clearance violation, or measured clearance violation before handoff.
- Release to baseline only when measured pre-stage handoff is ready or a strict baseline-safe envelope is met.
- Stay out of portfolio/stress ingestion until a fresh one-run goal-side matrix shows `zero` and `plus45` both pass pre-stage handoff without pre-stage ball drift/contact.

## Architecture Options To Revisit

- Authority-owning local trajectory controller: default next candidate if the audit shows commanded motion is not being realized reliably.
- True local trajectory tracker: continuous SE(2) path tracking with measured progress, not waypoint overlays.
- MPC/MPPI-style local planner: short-horizon command optimization against ball clearance, goal-side escape, and handoff geometry.
- Nav2 controller-plugin path: use controller-server/local-planner machinery rather than black-box `NavigateToPose`.
- Contact-aware manipulation planner: later option if non-contact pre-stage remains too brittle.
- Learned or Google/RT-style model path: shadow-mode proposer or critic only; no direct motor control in this phase.
- Other architecture families: explicitly search for and evaluate alternatives not already represented here before committing to the next branch.

## Non-Goals

- Do not retune `region_funnel_v1`, `nav2_reacquire_v1`, `constrained_local_planner_v1`, `docking_reacquire_v1`, `handoff_yaw_servo_v1`, `pre_stage_reacquire_fsm_v1`, or `pre_stage_path_tracker_v1`.
- Do not name or implement another helper/manual-drive runtime branch while the MPPI/controller-stack blocker is under repair.
- Do not refresh portfolio or stress evidence for blocked branches.
