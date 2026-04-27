# Gather Pre-Stage Architecture Options Review

## Current Test Signal

The seven blocked gather-control branches prove that isolated overlays are not enough for the current fresh `zero` / `plus45` pre-stage blocker. The tests and matrix artifacts are still useful, but they mostly prove wiring, branch activation, safety guards, and artifact truthfulness. They do not by themselves prove that selected manual-drive commands have enough authority in the live plant, that the realized motion matches the helper's projected geometry, or that the handoff gate exactly matches the measured state the controller is optimizing.

The next diagnostic layer is `scripts/gather_pre_stage_command_authority_audit.py`. It should run before another runtime branch is named. If the audit cannot separate command realization from geometry failure, the next live work should be a minimal motion-realization probe rather than another gather controller.

## Assumptions To Peel Back

- Command authority: selected `linear_x` / `angular_z` may be too weak, clipped, delayed, or poorly realized even when helper projections look plausible.
- Geometry progress: realized motion may be real but may not reduce projection, lateral error, distance, yaw, or waypoint progress enough for handoff.
- Gate alignment: a controller may reach a state that looks handoff-ready in debug fields while repeatability summaries still count the case as failed.
- Test shape: fresh `zero` and `plus45` are the right promotion gate, but intermediate diagnostics should distinguish goal-side clearance, waypoint reach, lateral reduction, yaw reduction, and ball-still safety.
- Evidence completeness: missing state history or missing branch debug fields should trigger more instrumentation, not a pass/fail interpretation.

## Architecture Families To Compare

- Authority-owning local trajectory controller: own the full pre-stage motion and command limits from measured pose to handoff. This is the default next architecture if command authority is the blocker.
- True local trajectory tracker: track a continuous SE(2) path with measured progress rather than cycling through reactive overlays or loose waypoints.
- Nav2 controller plugin: use controller-server/local-planner machinery directly instead of black-box `NavigateToPose`, while keeping the scope to pre-stage.
- MPC/MPPI local planner: optimize bounded short-horizon commands against ball clearance, goal-side escape, and handoff geometry.
- Contact-aware manipulation planner: consider deliberate contact only if non-contact pre-stage remains too brittle and safety gates can be made explicit.
- Behavior-tree or action-server pre-stage owner: move pre-stage ownership out of the mission loop so progress, holds, aborts, and release conditions are first-class runtime states.
- Learned or Google/RT-style model path: use only as a shadow-mode maneuver proposer, critic, or switch/abstain sidecar. Direct real-time motor control is out of scope for this phase.
- Other architecture families: explicitly search for approaches not represented above before committing to the next runtime branch.

## Next Decision Gate

Do not implement another gather-control family until the command-authority audit classifies the primary `zero` and `plus45` blocker. If the audit reports weak or missing realized motion, run the minimal live motion-realization probe. If command realization is adequate but geometry still fails, choose the next architecture from this review and document why the selected family addresses the measured blocker.
