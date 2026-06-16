# Postfix Seed 20260651 Stop Decision Packet

Date: June 16, 2026

Branch: `spike/fetch-multiball-open-field-20260606`

Latest pushed checkpoint at packet creation: `159313d Align open-field owner docs with postfix stop evidence`

## Decision Needed

The Option A repair cleared the original seed `20260651` Nav2 setup-assist frame and corridor-safety defect. The next full postfix seed then exposed the next setup-owner gap: the robot delivered `10/12` balls, recorded two bounded give-ups, and stayed inside the visual/evidence guardrails.

This is a supervisor stop point. The current evidence supports repair planning. Additional breadth gates should wait for approval. The next executable lane needs Fred/supervisor approval because it either preserves the current v1 bar and chooses a repair strategy, or pulls part of the open-field setup owner forward into the current promotion lane.

## Current Evidence

### Option A repair evidence

- Phase 1 repair commit: `9c3f193 Fix Nav2 setup-assist frame math; add ball-clearance corridor gate`.
- Rotation-aware setup goal now records `frame_yaw_offset_rad` in `scripts/golf_ball_circle_delivery_demo_runner.py`.
- Nav2 setup-assist legs now run a pre-dispatch corridor gate and emit `nav2_setup_corridor_ball_conflict` when the straight chord crosses any ball clearance floor.

### Frozen-scene replay

- Campaign: `live_multiball_frozen_seed20260651_s01_replay_rerun3_20260615`
- Scorecard: `artifacts/session/live_multiball_frozen_seed20260651_s01_replay_rerun3_20260615/fetch_multiball_retrieval_gate/scorecard.md`
- Result: the frozen scene completed behaviorally with the original defect repaired. Step 2 corridor-rejected Nav2 and completed through the fallback ladder. Step 3 also corridor-rejected Nav2 and ended in the bounded give-up backstop.
- Visual package: `artifacts/session/live_multiball_frozen_seed20260651_s01_replay_rerun3_20260615_visual_package/fetch_visual_uat_package/package_summary.json`

### Full postfix seed

- Campaign: `live_multiball_route_diverse_seed20260651_4x3_postfix_20260615`
- Scorecard: `artifacts/session/live_multiball_route_diverse_seed20260651_4x3_postfix_20260615/fetch_multiball_retrieval_gate/scorecard.md`
- Delivery: `10/12`
- Bounded give-ups: `2`
- Bounded reason: `measured_setup_handoff_failed_before_contact`
- Live fetch failures: `0`
- Environment failures: `0`
- Route diversity: green across `nav2_reposition_first`, `local_setup_capture`, `recovery_or_reaim`, and `fetch_ready_local`
- Visual package: effective pass with multiball visual evidence green

The two bounded cases were:

| Scene | Step | Ball | Route | Closest approach | Mission verdict |
| --- | ---: | --- | --- | ---: | --- |
| `seed20260651_mb_route_diverse_s01_nav2` | 3 | `ball_3` | `local_setup_capture` | `0.656639` | `artifacts/session/20260616T004747521355Z/golf_ball_circle_delivery/20260616T005244709365Z/mission_verdict.json` |
| `seed20260651_mb_route_diverse_s04_ready` | 3 | `ball_2` | `local_setup_capture` | `0.774709` | `artifacts/session/20260616T011122561804Z/golf_ball_circle_delivery/20260616T011504578620Z/mission_verdict.json` |

### Rollup

- Rollup scorecard: `artifacts/session/analysis_multiball_seed20260651_postfix_stop_rollup_20260615/fetch_multiball_uat_rollup/scorecard.md`
- Interpretation: `multiball_llm_supervised_visual_uat_has_gaps`
- Issues: `live_gate_count_below_minimum`, `llm_supervised_gate_count_below_minimum`, `step_failures_remain`, `measured_push_ready_handoff_failures_remain`, `hidden_nav2_prefetch_in_local_setup`
- Next recommended rung: `repair_the_first_reported_gap_before_more_broadening`

## Browser Evidence

Dashboard base, when service `8895` is running: [dashboard](http://100.112.221.6:8895)

Primary full-seed visual proof:

| Scene session | Onboard | Topdown | World | Keyframes |
| --- | --- | --- | --- | --- |
| `20260616T004747521355Z` | [raw camera](http://100.112.221.6:8895/artifacts/session/20260616T004747521355Z/visual/raw_camera_browser.mp4) | [topdown](http://100.112.221.6:8895/artifacts/session/20260616T004747521355Z/visual/topdown_telemetry_browser.mp4) | [world](http://100.112.221.6:8895/artifacts/session/20260616T004747521355Z/visual/world_stream.mp4) | [keyframes](http://100.112.221.6:8895/artifacts/session/20260616T004747521355Z/visual/keyframe_review_contact_sheet.png) |
| `20260616T005753798483Z` | [raw camera](http://100.112.221.6:8895/artifacts/session/20260616T005753798483Z/visual/raw_camera_browser.mp4) | [topdown](http://100.112.221.6:8895/artifacts/session/20260616T005753798483Z/visual/topdown_telemetry_browser.mp4) | [world](http://100.112.221.6:8895/artifacts/session/20260616T005753798483Z/visual/world_stream.mp4) | [keyframes](http://100.112.221.6:8895/artifacts/session/20260616T005753798483Z/visual/keyframe_review_contact_sheet.png) |
| `20260616T010421234641Z` | [raw camera](http://100.112.221.6:8895/artifacts/session/20260616T010421234641Z/visual/raw_camera_browser.mp4) | [topdown](http://100.112.221.6:8895/artifacts/session/20260616T010421234641Z/visual/topdown_telemetry_browser.mp4) | [world](http://100.112.221.6:8895/artifacts/session/20260616T010421234641Z/visual/world_stream.mp4) | [keyframes](http://100.112.221.6:8895/artifacts/session/20260616T010421234641Z/visual/keyframe_review_contact_sheet.png) |
| `20260616T011122561804Z` | [raw camera](http://100.112.221.6:8895/artifacts/session/20260616T011122561804Z/visual/raw_camera_browser.mp4) | [topdown](http://100.112.221.6:8895/artifacts/session/20260616T011122561804Z/visual/topdown_telemetry_browser.mp4) | [world](http://100.112.221.6:8895/artifacts/session/20260616T011122561804Z/visual/world_stream.mp4) | [keyframes](http://100.112.221.6:8895/artifacts/session/20260616T011122561804Z/visual/keyframe_review_contact_sheet.png) |

## Promotion Impact

The current v1 bar requires five consecutive green route-diverse seeds, delivery rate `>= 90%`, every non-delivery bounded and diagnosed, and a green visual package per run.

Seed `20260651` stays outside the green set:

- Delivery is `10/12` (`83.3%`), below the numeric bar.
- The run includes two bounded give-ups in one seed, which hits the hard stop-and-report bound recorded in `docs/ACTIVE_WORKFLOW.md`.
- Visual evidence is usable and consistent with telemetry; the delivery bar remains controlling.

Seed `20260650` invariance remains queued. It should stay queued until the setup-owner decision is made, because another breadth gate would spend runtime against a known setup capability gap.

## Decision Lanes

### Lane A - Hold v1 to the current bar

Owner decision: preserve the current v1 promotion bar and select a repair path before more breadth execution.

Allowed immediate work after approval:

1. Keep the current evidence package as the stop record.
2. Pick the first repair target from the rollup's reported setup gap.
3. Run implementation and test work in a separate work order with explicit bounds.

Held work:

- Additional full-seed live gates.
- Seed `20260650` invariance.
- Any change to the bounded give-up predicate, planner gate, route labels, frozen seven-intent contract, ball-motion guard, or LLM authority.

### Lane B - Pull open-field setup owner Slice 1 into the current lane

Owner decision: authorize `OPEN_FIELD_SETUP_TRAJECTORY_OWNER_DESIGN.md` Slice 1 as the next repair slice before the streak restart.

Why this lane fits the evidence:

- Both postfix non-deliveries are setup/handoff failures before useful push control.
- The current owner design already judges `Boundary-Aware Wraparound Promotion` as the cheapest slice that can convert feasible bounded give-up geometry into executable setup.
- Slice 1 keeps the frozen route vocabulary intact: the row still uses `recovery_or_reaim`, while the evidence payload stamps the maneuver as `open_field_arc_setup`.

Implementation boundaries for the first work order:

- Implement `build_open_field_setup_waypoints` beside `build_wraparound_setup_waypoints` in `scripts/golf_ball_circle_delivery_demo_runner.py`.
- Reuse the existing wraparound executor path through `collect_wraparound_setup_samples`.
- Add a shared give-up predicate helper so gate planning and runner execution use the same feasibility conditions.
- Add persistent-field multiball clearance against all remaining undelivered balls.
- Serialize per-side candidate evaluation into both retained give-up detail and executed plan records.
- Add the measured staging gate before line-servo release: `|lateral| <= 0.12 m` and `|yaw error| <= 12 deg`.
- Add stage-indexed failure reasons such as `open_field_setup_stage_failed:W2:<reason>`.
- Keep downstream measured gates unchanged: behind-ready, contact-ready, measured push-ready handoff, guarded fetch dispatch, and `0.300 m` delivery radius.

Hard bounds for that work order:

- The work order keeps the ball-motion guard, bounded give-up predicate thresholds, `planner_gate`, route labels, frozen seven-intent contract, and LLM authority fixed.
- Live gates start only after implementation tests and supervisor diff review.
- Hardware claims remain out of scope until the pose-source gap is closed for `robot_fidelity_orin`.

## Lane B Work Order Draft

Phase B1: implementation plus tests only.

1. Add `build_open_field_setup_waypoints` and the shared predicate helper.
2. Route feasible bounded give-up cases to an executable `recovery_or_reaim` setup maneuver behind a CLI flag such as `--open-field-setup-maneuver`.
3. Preserve bounded give-up rows when both sides are infeasible, with per-side reject reasons.
4. Add tests:
   - Predicate-region property sweep.
   - Planner-stability replay from the measured post-step pose.
   - Synthetic corner-pinned infeasible case.
   - Persistent-field clearance against sibling balls.
   - Frozen `seed20260648` setup case flips from retained give-up to executable.
5. Run:

```powershell
python -m pytest tests/test_fetch_multiball_retrieval_gate.py -q
python C:\Users\afutu\.codex\skills\strong-drafting-style\scripts\check_drafting_style.py docs/OPEN_FIELD_SETUP_TRAJECTORY_OWNER_DESIGN.md docs/ACTIVE_WORKFLOW.md docs/ROADMAP_2026_H2.md
git diff --check
```

Phase B2: post-review regression and targeted live proof.

```powershell
python scripts\fetch_moonshot_regression_manifest.py --campaign-id analysis_open_field_owner_slice1_regression_20260616
```

Then follow the mandatory ladder in `docs/OPEN_FIELD_SETUP_TRAJECTORY_OWNER_DESIGN.md`:

1. Targeted live proof on `artifacts/session/live_multiball_route_diverse_seed20260648_4x3_bounded_giveup_20260608/fetch_multiball_retrieval_gate/target_layouts/seed20260648_mb_route_diverse_s02_setup_step03_ball_2.json`.
2. Persistent-field `seed20260648` scene `s02`, expected `3/3`.
3. Full seed `20260648` route-diverse gate, expected `12/12` and zero give-ups.
4. Seed `20260647` invariance gate, expected unchanged route labels.
5. Track planned-feasible/executed-infeasible flips and `measured_setup_handoff_failed_before_contact` rate.

## Lane C - Revise the milestone bar

Owner decision: change the milestone definition so the current class of bounded give-up is acceptable at higher frequency.

This is a product and promotion decision. It needs explicit Fred/supervisor approval before any agent execution because it changes the acceptance contract rather than repairing the setup capability.

## Recommended Next Approval

Approve Lane B Phase B1 as an implementation-only work order. It targets the observed setup gap while preserving the current v1 bar, route vocabulary, LLM authority limits, and visual evidence discipline.

The first stop after approval should be a green local diff with tests. Live proof starts as a separate reviewed phase.
