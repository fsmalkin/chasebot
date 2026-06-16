# Open-Field Setup Owner Slice 1 Work Order Draft

Date: June 16, 2026

Status: approval-gated draft. Execution starts only after Fred/supervisor approval of Lane B in `docs/handoffs/2026-06-16-postfix-stop-decision-packet.md`.

Branch: `spike/fetch-multiball-open-field-20260606`

## Purpose

Implement Slice 1 of `docs/OPEN_FIELD_SETUP_TRAJECTORY_OWNER_DESIGN.md`: Boundary-Aware Wraparound Promotion behind an explicit CLI flag. The slice targets the setup-owner gap exposed by the postfix seed `20260651` run, where two balls ended as bounded give-ups with `measured_setup_handoff_failed_before_contact`.

The repair keeps the current v1 bar intact and gives the system one controlled way to convert feasible edge-of-field setup geometry into an executable `recovery_or_reaim` setup maneuver.

## Source Evidence

- Decision packet: `docs/handoffs/2026-06-16-postfix-stop-decision-packet.md`
- Owner design: `docs/OPEN_FIELD_SETUP_TRAJECTORY_OWNER_DESIGN.md`
- Stop evidence: `artifacts/session/live_multiball_route_diverse_seed20260651_4x3_postfix_20260615/fetch_multiball_retrieval_gate/scorecard.md`
- Rollup: `artifacts/session/analysis_multiball_seed20260651_postfix_stop_rollup_20260615/fetch_multiball_uat_rollup/scorecard.md`
- Earlier frozen owner gap: `artifacts/session/live_multiball_route_diverse_seed20260648_4x3_bounded_giveup_20260608/fetch_multiball_retrieval_gate/target_layouts/seed20260648_mb_route_diverse_s02_setup_step03_ball_2.json`

## Scope

Phase B1 is implementation plus tests only. Live replay, broad seeds, dashboard HTTP, and commits beyond this reviewed implementation slice wait for a separate Phase B2 work order.

Allowed production files:

- `scripts/golf_ball_circle_delivery_demo_runner.py`
- `scripts/fetch_multiball_retrieval_gate.py`

Allowed test files:

- `tests/test_golf_ball_circle_delivery_demo_runner.py`
- `tests/test_fetch_multiball_retrieval_gate.py`

Documentation updates should stay limited to implementation notes needed for reviewer clarity.

## Fixed Contracts

The work preserves these contracts:

- Ball-motion guard threshold and terminal semantics.
- Bounded give-up predicate thresholds.
- `planner_gate` route labels and route taxonomy.
- Frozen seven-intent planner contract.
- LLM authority limits.
- Delivery radius contract at `0.300 m`.
- Existing measured gates after setup: behind-ready, contact-ready, measured push-ready handoff, guarded fetch dispatch, and mission-level contact-quality proof.

## Implementation Requirements

### 1. Shared bounded-open-field predicate

Extract the existing predicate inside `bounded_give_up_decision` into a shared helper. The helper returns the current boolean result plus the geometry payload already used in the bounded give-up detail.

Acceptance requirements:

- Existing planned bounded give-up behavior stays identical when the open-field setup maneuver flag is disabled.
- Predicate thresholds remain unchanged.
- Tests cover the current seed `20260648` frozen setup gap and a synthetic out-of-region case.

### 2. `build_open_field_setup_waypoints`

Add a runner-side planner beside `build_wraparound_setup_waypoints`.

Planner behavior:

- Evaluate both side signs.
- Build W1 side-entry, W2 behind-side, and W3 final-behind waypoints from the design doc constants.
- Clamp W1/W2 into field bounds shrunk by `OPEN_FIELD_SETUP_WALL_MARGIN_M = 0.10`.
- Keep W3 unclamped and reject the candidate if W3 violates the field bounds.
- Check every chord against all relevant ball poses using `point_segment_distance`.
- Enforce the `0.30 m` clearance floor.
- Add a W0 radial back-out when the entry chord is below the `0.42 m` trigger and the back-out improves clearance.
- Rank candidates by feasibility, minimum chord clearance, and path length.
- Serialize all candidate decisions, reject reasons, clearance values, and selected side.

Acceptance requirements:

- Feasible plans include `maneuver_plan.executor_identity = "open_field_arc_setup"`.
- Infeasible plans preserve a named reject reason and full per-side diagnostics.
- Waypoints carry stable names, tolerances, target yaw, and field-bound provenance.

### 3. Gate integration

After the shared predicate matches, call the open-field setup planner when the new CLI flag is enabled.

Gate behavior:

- Feasible plan keeps the row executable as `recovery_or_reaim`.
- The generated layout stores the advisory `maneuver_plan`.
- Both-sides-infeasible cases retain the existing bounded give-up path and reason payload.
- Route label and route executor vocabulary stay unchanged.

Acceptance requirements:

- The seed `20260648` setup case flips from planned bounded give-up to executable when the flag is enabled.
- The same case remains a bounded give-up when the flag is disabled.
- Dry-run route counts remain understandable and preserve route diversity surfaces.

### 4. Runner execution

Add `--open-field-setup-maneuver` and execute the new setup maneuver only when the runner receives that flag and the route remains eligible.

Runner behavior:

- Re-derive the maneuver from the current measured pose at execution time; treat the layout plan as advisory evidence.
- Reuse `collect_wraparound_setup_samples` for command execution.
- Preserve the `0.020 m` ball-motion abort.
- Treat waypoints within about `0.05 m` as reached for degenerate-entry cases.
- Use the boundary-tightened waypoint tolerance of `0.060 m` near walls.
- Run the staging gate before line-servo release using `_route_geometry_from_poses`: `|lateral| <= 0.12 m` and `|yaw error| <= 12 deg`.
- Emit stage-indexed failure reasons such as `open_field_setup_stage_failed:W2:<reason>`.
- Record the measured replan payload, executed waypoints, per-waypoint samples, final geometry, and executor identity in `wraparound_setup.json` and the mission verdict.

Acceptance requirements:

- Existing wraparound behavior remains unchanged unless the new flag is active.
- Ball motion during the maneuver terminates the setup path immediately with the current guard semantics.
- A non-ball-motion stage failure may attempt at most one bounded replan from measured state.

### 5. Dead-code cleanup

If `build_step_command` is edited, remove the confirmed dead inner conditional that compares `route_label` to `ROUTE_LOCAL_SETUP_CAPTURE` inside the `ROUTE_NAV2_REPOSITION` branch. This is local cleanup attached to the same edit surface.

## Tests

Run these focused tests after implementation:

```powershell
python -m pytest tests/test_golf_ball_circle_delivery_demo_runner.py -q
python -m pytest tests/test_fetch_multiball_retrieval_gate.py -q
```

Required new or updated tests:

- Predicate helper preserves current bounded give-up classification with the flag disabled.
- Seed `20260648` frozen setup geometry becomes executable with the flag enabled.
- Synthetic infeasible corner geometry remains a bounded give-up with per-side reject reasons.
- Predicate-region property sweep covers angle `145-180 deg`, bounded standoff `0.60-0.65 m`, target-side `0.35-0.70 m`, and lateral `0.10-0.24 m`.
- Planner stability holds when replanning from the measured post-step pose.
- Persistent-field clearance checks sibling balls, target ball, and all remaining undelivered balls.
- Degenerate-entry waypoint skip works for approximately `0.05 m`.
- Boundary-tightened waypoint tolerance is applied near walls.
- Stage-indexed failure reasons reach the mission summary.
- `build_step_command` appends the open-field flag only for eligible executable rows.

## Static Checks

Run:

```powershell
python -m py_compile scripts/golf_ball_circle_delivery_demo_runner.py scripts/fetch_multiball_retrieval_gate.py
python C:\Users\afutu\.codex\skills\strong-drafting-style\scripts\check_drafting_style.py docs/OPEN_FIELD_SETUP_TRAJECTORY_OWNER_DESIGN.md docs/ACTIVE_WORKFLOW.md docs/ROADMAP_2026_H2.md
git diff --check
```

Use forward slashes for `pytest --basetemp` or cache paths in bash contexts.

## Stop Conditions

Stop and report before further work if any of these conditions occur:

- The implementation requires a route-label, planner-gate, frozen-intent, bounded-predicate, ball-motion-guard, or LLM-authority change.
- The maneuver needs Nav2 ownership for ball-relative legs.
- The pose-source gap requires hardware-lane work.
- Tests reveal the open-field flag changes existing behavior while disabled.
- Making the seed `20260648` frozen case executable requires a change to the fixed contracts above.

## Phase B2 Preview

Phase B2 begins only after B1 implementation tests are green and the supervisor reviews the diff.

Planned ladder:

1. `python scripts\fetch_moonshot_regression_manifest.py --campaign-id analysis_open_field_owner_slice1_regression_<YYYYMMDD>`
2. Targeted live proof on `artifacts/session/live_multiball_route_diverse_seed20260648_4x3_bounded_giveup_20260608/fetch_multiball_retrieval_gate/target_layouts/seed20260648_mb_route_diverse_s02_setup_step03_ball_2.json`
3. Persistent-field `seed20260648` scene `s02`, expected `3/3`
4. Full seed `20260648` 4x3 route-diverse gate, expected `12/12` and zero give-ups
5. Seed `20260647` invariance gate with unchanged route labels
6. Streak restart plan after supervisory review of the targeted evidence
