# Calibrated Fetch Architecture Test Plan

This plan exists so architecture exploration does not collapse into tuning the
same control loop under different names. The active UAT baseline remains
`object_centric_fetch_policy_v1` on the calibrated golf-ball/turf lane, but the
research portfolio should deliberately test wider designs that may generalize
better, reduce telemetry fragility, or simplify eventual hardware transfer.

## Coverage Rule

Treat these as different levels of evidence:

1. Control-family screen:
   - same mission shell and fetch objective, different `--gather-control-family`
     implementation
   - useful for cheap regression checks and branch resurrection decisions
   - not sufficient to claim broad architecture coverage
2. Architecture spike:
   - changes who owns the last-meter behavior, the state machine boundary, the
     prediction model, or the actuation/contact strategy
   - must keep the same calibrated ball, turf, delivery radius, saved layouts,
     no-retry rule, and approach telemetry
3. Promotion candidate:
   - passes canonical fidelity gates and shows a generalization or product
     benefit beyond matching the current baseline

Accelerated time is allowed only for screening. Any green or surprising
accelerated result must be rerun in the canonical
`yolo_test_world_v6_calibrated_golf_turf.world` lane before it counts as UAT or
branch-promotion evidence.

## Architecture Portfolio

| Family | Why test it | First evidence gate | Promotion question |
| --- | --- | --- | --- |
| Current object-centric fetch baseline | Known green UAT lane and reference telemetry | Existing May 27 `3/3` saved-layout gate | Does any new design beat its margin, stability, or simplicity? |
| Runnable legacy control-family screen | Checks whether old branches become viable under calibrated physics | `scripts/calibrated_fetch_architecture_revisit.py --screen-scope runnable_control_family_screen --fast-screen --short-circuit-on-failure` | Did any old implementation clear `zero` cheaply enough to justify canonical rerun? |
| Contact-aware geometric shooter | Plans a measured launch/release trajectory instead of pushing until close | Offline shot-model replay, then `zero` one-run canonical probe | Does it improve closest-approach margin or reduce contact duration? |
| Receding-horizon contact MPC/object servo | Owns robot-ball-target state and optimizes bounded commands directly | Fast screen on `zero`, then canonical `zero`/`left05`/`right05` one-run | Does it avoid lateral knock-away while recovering from small offsets? |
| ROS action-server or behavior-tree last-meter owner | Moves setup, contact, re-aim, abort, and telemetry out of ad hoc mission-loop phases | Dry-run/action-contract test, then canonical one-run `zero` | Does explicit ownership make failures easier to classify and recover? |
| Nav2 reposition plus object-centric last meter | Uses Nav2 for long-range approach only, with a clean handoff to object-centric contact | Pre-contact approach telemetry and handoff dwell on varied starts | Does it generalize to farther starts without contaminating contact control? |
| Passive mechanical guide/funnel | Tests whether a wider physical interaction envelope is simpler than software-only precision | Sim model smoke plus calibrated `zero`/off-axis one-run | Does it improve robustness without hiding unstable approach telemetry? |
| Learned residual or maneuver proposer | Learns residual corrections or proposes re-aim/shot parameters behind deterministic gates | Offline replay/shadow evaluation before live control | Does it add measurable margin while abstaining on out-of-distribution states? |
| Portfolio supervisor/switcher | Chooses push, shoot, re-aim, or give-up from measured uncertainty | Offline counterfactual replay, then live A/B on hard layouts | Does switching reduce tail failures without adding opaque behavior? |
| Perception-first target-pose fetch | Replaces truth-state assumptions with sensed ball/target pose once pose delivery is stable | Shadow perception parity against truth-state UAT traces | Does it preserve success when truth-state shortcuts are removed? |

## Gate Ladder

1. Desk check:
   - define the ownership boundary and why this is not merely parameter tuning
   - state expected benefit: margin, speed, robustness, simplicity, hardware
     transfer, data collection, or diagnosability
   - list new failure modes and safety guards
2. Offline or accelerated screen:
   - use recorded traces, dry-run contract tests, or the 2.0x calibrated fast
     world for cheap negatives
   - accept accelerated failures as screening evidence
   - never accept accelerated passes as UAT evidence
3. Canonical one-run probe:
   - `zero`, no retries, `0.300m` delivery radius, canonical calibrated world
   - require `mission_completed_pass=true`, `fetch_to_pose_pass=true`, and
     `shot_outcome.closest_approach_distance_m <= 0.300`
4. Canonical saved-layout matrix:
   - `zero`, `left05`, `right05`, one run each, no retries
   - compare closest-approach margin, first-contact alignment, yaw sign changes,
     lateral knock-away, and runtime/failure clarity against the May 27 baseline
5. Repeatability promotion:
   - `zero`, `left05`, and `right05` `3/3` each
   - every run must pass mission and fetch gates
   - any candidate with only equal pass rate must still justify itself through
     better margin, simpler architecture, lower latency, cleaner telemetry, or
     better transfer path
6. Generalization suite:
   - wider lateral offsets, farther starts, start yaw variation, target-distance
     variation, and at least one secondary surface check
   - include hard-case layouts only after the candidate clears the saved-layout
     gate, so hard cases do not distract from primary repeatability

## Branching

- Keep `physics-calibrated-golf-fetch-v1` as the UAT integration branch.
- Put shared harnesses, analyzers, and docs there after review.
- Use `spike/fetch-arch-<family>-YYYYMMDD` for a single architecture hypothesis.
- Promote to `candidate/fetch-arch-<family>` only after the canonical saved-layout
  matrix is green and the benefit is written down.
- Do not resurrect blocked gather-control branches in place. If an old idea is
  worth retesting, wrap it as a new architecture spike with a fresh hypothesis.

## Current Evidence Notes

- MPPI FollowPath calibrated revisit:
  `artifacts/session/live_calibrated_fetch_architecture_revisit_nav2_mppi_20260527/calibrated_fetch_architecture_revisit/architecture_revisit_summary.json`.
  It failed `zero`, `left05`, and `right05` before contact and remains
  evidence-only.
- A partial accelerated control-family screen on May 27, 2026 produced
  `artifacts/session/live_calibrated_fetch_architecture_revisit_legacy_fast_short_screen_20260527_region-funnel_zero_one_run/gather_mission_repeatability/campaign_run_summary.json`.
  `region_funnel_v1` failed `zero` after pre-stage handoff because the ball
  stopped short of the delivery radius. Treat this as screening-only context,
  not a completed architecture matrix.
