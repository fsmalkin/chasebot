# Gather Pre-Stage Architecture Options Review

## Current Test Signal

The seven blocked gather-control branches prove that isolated overlays are not enough for the current fresh `zero` / `plus45` pre-stage blocker. The tests and matrix artifacts are still useful, but they mostly prove wiring, branch activation, safety guards, and artifact truthfulness. They do not by themselves prove that selected manual-drive commands have enough authority in the live plant, that the realized motion matches the helper's projected geometry, or that the handoff gate exactly matches the measured state the controller is optimizing.

The command-authority audit now separates the next blocker enough to name the next runtime branch: selected manual-drive commands are usually realized and geometry often improves, but fresh `zero` / `plus45` still time out before measured handoff. The next active branch is `pre_stage_trajectory_owner_v1`, an in-process owner for the full measured pre-stage trajectory to handoff. If that branch cannot converge, the next fallback family should move ownership lower in the stack, starting with a Nav2 controller plugin or MPPI/MPC-style local recovery.

## Assumptions To Peel Back

- Command authority: selected `linear_x` / `angular_z` may be too weak, clipped, delayed, or poorly realized even when helper projections look plausible.
- Geometry progress: realized motion may be real but may not reduce projection, lateral error, distance, yaw, or waypoint progress enough for handoff.
- Gate alignment: a controller may reach a state that looks handoff-ready in debug fields while repeatability summaries still count the case as failed.
- Test shape: fresh `zero` and `plus45` are the right promotion gate, but intermediate diagnostics should distinguish goal-side clearance, waypoint reach, lateral reduction, yaw reduction, and ball-still safety.
- Evidence completeness: missing state history or missing branch debug fields should trigger more instrumentation, not a pass/fail interpretation.

## Architecture Families To Compare

- Authority-owning local trajectory controller: selected for `pre_stage_trajectory_owner_v1`; it owns the full pre-stage motion and command limits from measured pose to measured handoff readiness.
- True local trajectory tracker: represented inside the selected branch as measured milestone tracking through a bounded SE(2) trajectory rather than reactive overlays or loose waypoints.
- Nav2 controller plugin: first fallback if the in-process owner cannot converge, using controller-server/local-planner machinery directly instead of black-box `NavigateToPose` while keeping the scope to pre-stage.
- MPC/MPPI local planner: second fallback if deterministic tracking still cannot handle the geometry, optimizing bounded short-horizon commands against ball clearance, goal-side escape, and handoff geometry.
- Contact-aware manipulation planner: consider deliberate contact only if non-contact pre-stage remains too brittle and safety gates can be made explicit.
- Behavior-tree or action-server pre-stage owner: move pre-stage ownership out of the mission loop so progress, holds, aborts, and release conditions are first-class runtime states.
- Learned or Google/RT-style model path: use only as a shadow-mode maneuver proposer, critic, or switch/abstain sidecar. Direct real-time motor control is out of scope for this phase.
- Other architecture families: explicitly search for approaches not represented above before committing to the next runtime branch.

## Next Decision Gate

Implement `pre_stage_trajectory_owner_v1` behind the existing gather-control family seam and verify it offline first. Run the one-run goal-side matrix only after the implementation checkpoint is committed. Continue only if fresh `zero` and `plus45` both reach measured pre-stage handoff with no pre-stage ball drift/contact; otherwise stop promotion work and plan the lower-stack fallback rather than retuning blocked overlays.
