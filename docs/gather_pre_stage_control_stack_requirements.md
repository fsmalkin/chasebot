# Gather Pre-Stage Control Stack Requirements

## Context

The blocked gather-control candidates now share the same first-attempt blocker: fresh `zero` and `plus45` live matrix attempts do not reliably reach behind-ball pre-stage handoff. The latest `pre_stage_path_tracker_v1` smoke failed safely: it recorded no pre-stage ball motion/contact, but both primary cases stayed on the `escape` waypoint until timeout.

The next step is an assumption peel-back, not another gather-control family. The evidence can still mean "bad geometry," but it may also mean command authority, timing, frame interpretation, manual-drive realization, or gate threshold mismatch. New runtime architecture work should wait until those possibilities are separated.

## Next Audit Steps

- Add a pre-stage command-authority analyzer (`scripts/gather_pre_stage_command_authority_audit.py`) that compares selected `linear_x` / `angular_z` commands against realized world-motion deltas during `pre_stage`.
- Split blocked evidence into geometry failure, command-realization failure, timeout despite progress, ball-safety failure, and handoff-threshold mismatch.
- Run a minimal live motion probe on the same `zero` and `plus45` setup that commands small controlled turns/arcs away from the ball and records measured response.
- Keep the current `zero` / `plus45` pre-stage handoff gate, but add intermediate diagnostics for goal-side cleared, escape waypoint reached, lateral error reduced, yaw reduced, and ball remained still.
- Use `docs/gather_pre_stage_architecture_options_review.md` to compare the remaining broader options before selecting the next runtime branch, including at least one pass that looks for architectures outside the current overlay/local-planner/Nav2/MPPI set.

## Requirements

- Own the full pre-stage motion from measured robot pose to measured handoff readiness, instead of layering another reactive overlay around the current pre-stage loop.
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
- Do not name or implement the next runtime branch until command authority and motion-realization evidence are available.
- Do not refresh portfolio or stress evidence for blocked branches.
