# Generalized Fetch-To-Pose Autonomous Execution Plan

This plan is the default execution path for `spike/fetch-arch-ai-push-coast-servo-20260529`.
It exists so agents can keep moving without asking for clarification when the
next safe step is covered here.

## Milestone

Deliver **Planner-Gated Generalized Fetch-To-Pose v1**: a no-shoot,
robot-owned fetch behavior where an LLM/world-state planner selects the route
class, Nav2 owns as much real-time robot motion as corrected evidence supports,
and a thin fetch adapter monitors corrected delivery geometry, object progress,
escape, stale state, and replanning triggers.

The default control sequence is deliberately simple: classify the route, compute
the intended ball path, compute the capture pose behind the ball, reach and gate
that setup, let Nav2 push through the ball-target corridor, then let the monitor
classify success or the next bounded recovery.

The broader product path is **Planner-Gated Generalized Fetch**. Mixed or
surprising random scenes must pass planner routing before local fetch is judged.
Custom contact routines and AI push-coast proposals remain fallback lanes that
earn live authority only from corrected, reproducible stage-gap evidence.

June 2, 2026 execution pivot: the LLM/world-state planner is integrated as a
route-classification and shadow-evidence surface. The non-local route labels
still need executable route owners. The opposite-side direct run proved
corrected fetch geometry and delivery, then exposed a forward-motion gap because
local fetch used legacy reverse pre-stage commands to reach setup. Future broad
UAT should classify that scene as `nav2_reposition_first` and execute a
forward-driving setup/reposition path before local fetch starts.

The next preferred execution lane is
`spike/fetch-arch-planner-routed-forward-only-moonshot-20260602`. Use cheap
simulation to test broad route ownership quickly: executable reposition, scan,
recovery/re-aim, no-go, and direct local fetch. Treat discarded branch work as a
low-cost search mechanism while preserving canonical 1.0x evidence for
promotion decisions.

June 2, 2026 moonshot implementation target: the branch routes mixed planner
scenes into v0 executable outcomes. `fetch_ready_local` and
`nav2_reposition_first` dispatch the forward-only golf delivery runner with
route metadata and a pre-contact forward-motion guard. `ambiguous_or_unsafe_no_go`
records an executed safe no-go. `scan_or_perceive_first` and
`recovery_or_reaim` remain classified placeholders until their scan/refresh and
bounded re-aim executors are wired. The v0 forward runner is a proof surface for
the route contract; real Nav2 reposition is the next executor swap after the
operator-visible route demo is green.

June 3, 2026 moonshot evidence update: planner-routed `fetch_ready_local` and
`nav2_reposition_first` now share the stage-aware `line_servo` proof executor.
The executor drives forward-only setup, aligns behind the ball-target line,
pushes at bounded speed, and stops when the ball reaches the tighter `0.200m`
delivery-stop radius while the formal `fetch_to_pose` contract remains `0.300m`.
The mixed planner gate passed `12/12` with no wrong fetch dispatches:
`artifacts/session/live_planner_routed_line_servo_wide_batch_seed_scan_20260603/fetch_planner_handoff_gate/gate_summary.json`.
Representative live mobile UAT packages are green:
`artifacts/session/uat_planner_routed_line_servo_generated_scene09_20260603/fetch_visual_uat_package/scorecard.md`
for direct local fetch, `artifacts/session/uat_planner_routed_line_servo_generated_scene04_20260603/fetch_visual_uat_package/scorecard.md`
for a `1.24m` robot-ball Nav2-reposition start, and
`artifacts/session/uat_planner_routed_line_servo_generated_scene05_20260603/fetch_visual_uat_package/scorecard.md`
for an angled `-23deg` corridor. Treat this as route-execution UAT evidence.
Promotion still waits for canonical saved-layout and seeded-random gates after
real Nav2 reposition and the remaining scan/recovery route owners are wired.

Later June 3 route-owner update: `recovery_or_reaim` now dispatches the same
bounded forward-only proof executor with a contact-ready re-aim gate, while
`scan_or_perceive_first` records an executed planner-owned refresh/abstain
outcome. Post-change live UAT passed the same frozen recovery scene
(`20260603T014849625586Z`, closest `0.197571m`), a Nav2-reposition scene
(`20260603T015429081277Z`, closest `0.194266m`), and a fetch-ready local scene
(`20260603T015619379922Z`, closest `0.197331m`). Nav2-reposition and
fetch-ready local were clean at first contact. Recovery delivered with improved
trajectory angle and a remaining first-contact lateral/yaw watch, so the next
route-owner work is planner-owned setup/reposition before recovery fetch rather
than another narrow terminal-distance tweak. Mobile visual packages:
`artifacts/session/uat_contact_ready_patch_recovery_scene01_20260603/fetch_visual_uat_package/scorecard.md`,
`artifacts/session/uat_contact_ready_patch_nav2_scene02_20260603/fetch_visual_uat_package/scorecard.md`,
and
`artifacts/session/uat_contact_ready_patch_fetch_scene09_20260603/fetch_visual_uat_package/scorecard.md`.

Later June 3 setup-quality update: the recovery route now uses route-specific
setup geometry before the shared `line_servo` proof executor. For
`recovery_or_reaim`, the runner sets a deeper setup standoff (`0.34m`), keeps
the tighter lateral contact gate (`0.030m`), and raises bounded turn authority
to `0.45rad/s`; ordinary `fetch_ready_local` and `nav2_reposition_first`
routes keep their existing local-fetch settings. The current-code recovery
rerun passed with clean first contact (`20260603T025500649447Z`, closest
`0.195938m`, first-contact lateral `0.029732m`, yaw `-1.397719deg`, trajectory
angle `0.043748deg`, delivery stop triggered). Non-recovery smoke remains green
on Nav2 scene02 (`20260603T023349145784Z`, closest `0.196889m`) and
fetch-ready scene09 (`20260603T023748259579Z`, closest `0.196443m`). Mobile
visual packages:
`artifacts/session/uat_recovery_route_setup_quality_scene01_20260603/fetch_visual_uat_package/scorecard.md`,
`artifacts/session/uat_recovery_route_setup_quality_nav2_scene02_20260603/fetch_visual_uat_package/scorecard.md`,
and
`artifacts/session/uat_recovery_route_setup_quality_fetch_scene09_20260603/fetch_visual_uat_package/scorecard.md`.
The rejected micro-tuning evidence is also useful: a global tighter lateral gate
regressed Nav2 scene02 (`20260603T023025633192Z`, closest `0.300912m`), and
extra recovery creep/nudge preserved delivery while worsening first-contact
quality. Keep route-specific setup changes; use broader route-owner tests before
another narrow contact tweak.

Late June 3 Nav2 setup-first recovery update: the recovery route now combines
real Nav2 setup, the shared bounded `line_servo` executor, and a
`recovery_line_acquire` transition once the robot reaches the setup pocket. The
exact recovery layout that previously stalled without first contact
(`20260603T040615017369Z`, closest `0.739814m`) now passes
(`20260603T042159429741Z`, closest `0.196169m`). The contact trace shows the
expected sequence: `setup_converge`, `recovery_line_acquire`, then `push_coast`;
first ball motion occurs at `6.026817s`. Sequence-based visual review confirms
the robot advances into contact and pushes the ball into the delivery circle.
Browser-watchable package:
`artifacts/session/uat_recovery_line_acquire_fix_seed20260606_20260603/fetch_visual_uat_package/scorecard.md`.
The remaining watch is contact quality (`pre_contact_lateral_error`,
`pre_contact_yaw_error`, and `first_contact_lateral_error`), so the next broad
test is a planner-routed multi-scene rerun before another local-contact tweak.

Broad frozen route rerun, late June 3: the planner-routed branch now has a
green mixed-route UAT package across all five route classes. The handoff gate
passed `5/5` with zero wrong fetch dispatches:
`artifacts/session/live_broad_frozen_planner_routed_gate_20260603/fetch_planner_handoff_gate/gate_summary.json`.
Executable route runs passed under same-session sequence review:
`fetch_ready_local` (`20260603T043331724833Z`, closest `0.196023m`),
`nav2_reposition_first` (`20260603T043525704923Z`, closest `0.193737m`), and
`recovery_or_reaim` (`20260603T043728550735Z`, closest `0.197799m`). The
planner-owned non-fetch routes also executed correctly:
`scan_or_perceive_first` selected perception refresh, and
`ambiguous_or_unsafe_no_go` selected safe no-go. Browser-watchable package:
`artifacts/session/uat_broad_frozen_planner_routes_20260603/fetch_visual_uat_package/scorecard.md`.
Treat this as mobile visual UAT for route ownership and video review. Promotion
still waits for canonical saved-layout and seeded-random gates.

Random planner-routed route-owner batch, later June 3: the generated planner
gate passed `15/15` with zero wrong fetch dispatches and route spread across
all five labels:
`artifacts/session/live_random_planner_routed_gate_seed20260607_15case_20260603/fetch_planner_handoff_gate/gate_summary.json`.
Six executable route replays passed with sequence-based visual review, two per
executable route class:
`fetch_ready_local` (`20260603T110734954675Z`, closest `0.197448m`;
`20260603T114148765004Z`, closest `0.197425m`),
`nav2_reposition_first` (`20260603T111354017138Z`, closest `0.195932m`;
`20260603T114321822659Z`, closest `0.196426m`), and
`recovery_or_reaim` (`20260603T111751279374Z`, closest `0.247356m`;
`20260603T114506043298Z`, closest `0.193687m`). The browser-watchable package
is
`artifacts/session/uat_random_planner_routes_seed20260607_exec6_20260603/fetch_visual_uat_package/scorecard.md`,
and the route UAT analyzer is
`artifacts/session/route_uat_random_seed20260607_exec6_analyzer_20260603/fetch_planner_route_uat_analyzer/scorecard.md`.
This is randomized route-owner visual UAT on the moonshot branch. The remaining
contact-quality watch is pre-contact lateral/yaw error across all six
executable runs; first-contact flags were clean in the six-run batch.

Replay-path fix, later June 3: fresh-seed `seed20260608_scene24_fetch_ready_local`
exposed a frozen-layout replay mismatch. The manual target-layout path used the
old constant-push defaults and default robot pose, then missed at `0.416135m`.
`golf_ball_circle_delivery_demo_runner.py` now applies planner route execution
defaults from frozen layouts: route metadata, planned robot pose for
`fetch_ready_local`, current-robot pose normalization for setup-first route
replays, long-horizon line servo, delivery stop, and forward-only
contact guard. The patched replay passed at `0.196327m` with sequence review and
browser-watchable evidence:
`artifacts/session/uat_planner_route_replay_fix_seed20260608_scene24_20260603/fetch_visual_uat_package/scorecard.md`.
This is a replay-harness fix and diagnostic UAT evidence; promotion still
requires the canonical saved-layout and seeded-random gates.

Frozen executable-route replay set, later June 3: seed `20260608` now covers
all three executable route owners with one browser-watchable replay each:
`fetch_ready_local`, `nav2_reposition_first`, and `recovery_or_reaim`. The
combined analyzer is green for visual UAT and keeps promotion evidence false:
`artifacts/session/route_uat_frozen_seed20260608_three_route_replays_20260603/fetch_planner_route_uat_analyzer/scorecard.md`.
Contact quality is a watch item rather than a blocker because delivery and ball
trajectory are coherent, first-contact blockers are `0`, and pre-contact
lateral/yaw posture still needs smoothing.

June 4 saved-anchor planner-routed proof: the canonical `zero`, `left05`, and
`right05` anchors now run through the planner-routed route owner, replacing the
legacy architecture-revisit wrapper. The handoff gate passed `3/3` after fixing
exact `0.0` geometry handling, so `zero` remains `fetch_ready_local` and the
off-axis anchors route to `recovery_or_reaim`:
`artifacts/session/dev_planner_saved_anchor_handoff_gate_zero_numeric_fix_20260604/fetch_planner_handoff_gate/scorecard.md`.
The live one-run replay passed `3/3` with visual packages:
`artifacts/session/live_planner_saved_anchor_replay_zero_numeric_fix_8881_20260604/fetch_planner_route_replay_batch/scorecard.md`.
Closest approaches were `0.195m` for `left05`, `0.190m` for `right05`, and
`0.193m` for `zero`. Sequence review of the onboard/topdown sheets confirmed
visible delivery into the circle for all three anchors. This is saved-anchor
visual UAT.

June 4 saved-anchor repeatability proof: the planner-routed stack passed the
saved-anchor `3/3` rung with nine fresh-dashboard runs and browser-watchable
packages:
`artifacts/session/analysis_planner_saved_anchor_repeat3x_20260604/fetch_planner_route_uat_analyzer/scorecard.md`.
Counts are `saved_anchor_left05=3/3`, `saved_anchor_right05=3/3`, and
`saved_anchor_zero=3/3`. Execution, setup, and contact quality were clean;
first-contact blockers were `0`; closest approaches ranged from `0.194m` to
`0.198m`. The contact-sheet montage is
`artifacts/session/analysis_planner_saved_anchor_repeat3x_20260604/fetch_planner_route_uat_analyzer/saved_anchor_repeat3x_contact_sheet_montage.png`.
The seeded random gate is now the remaining promotion-grade proof before
claiming generalized fetch-to-pose readiness.

June 4 planner-routed random slice after repeatability: seed `20260627` passed
the fresh mixed planner gate with `30/30` route decisions and `0` wrong
fetch-ready dispatches:
`artifacts/session/dev_route_quality_gate_seed20260627_post_repeatability_30case_20260604/fetch_planner_handoff_gate/scorecard.md`.
The live executable slice passed `6/6` across two `fetch_ready_local`, two
`nav2_reposition_first`, and two `recovery_or_reaim` rows:
`artifacts/session/analysis_route_quality_seed20260627_exec6_post_repeatability_20260604/fetch_planner_route_uat_analyzer/scorecard.md`.
Execution, setup, and contact quality were clean; first-contact blockers were
`0`; closest approaches ranged from `0.194m` to `0.196m`. The visual montage is
`artifacts/session/analysis_route_quality_seed20260627_exec6_post_repeatability_20260604/fetch_planner_route_uat_analyzer/seed20260627_exec6_keyframe_montage.png`.
This is green randomized route-owner visual UAT. The next implementation step
is a formal planner-routed seeded generalization gate surface that can carry the
canonical promotion semantics.

June 4 planner-routed seeded gate surface: `scripts/fetch_planner_seeded_generalization_gate.py`
now composes the planner handoff gate, executable route replay batch, and route
UAT analyzer under one parent artifact. Dry-run
`dev_planner_seeded_generalization_gate_dry_run_20260604` passed with a
`30/30` planner gate and six selected executable replay rows:
`artifacts/session/dev_planner_seeded_generalization_gate_dry_run_20260604/fetch_planner_seeded_generalization_gate/scorecard.md`.
The live run of this wrapper is the next promotion-grade gate candidate; it
must use fresh dashboard sessions, browser-watchable visual packages, clean
execution/setup/contact quality, and zero first-contact blockers before
`promotion_evidence=true`.

The first live wrapper attempt,
`live_planner_seeded_generalization_gate_seed20260627_20260604`, validated the
planner child and exposed an infrastructure blocker before mission execution:
the fresh dashboard session stayed in `environment_starting` on the first replay
row. The scorecard is
`artifacts/session/live_planner_seeded_generalization_gate_seed20260627_20260604/fetch_planner_seeded_generalization_gate/scorecard.md`.
Classify this as dashboard/compose startup evidence; fetch-control scoring
remains unattempted. The next autonomous step is repairing or bypassing that
startup path, then rerunning the same parent gate.

The fixed live wrapper run,
`live_planner_seeded_generalization_gate_full_visual_fix_20260604`, clears that
promotion surface:
`artifacts/session/live_planner_seeded_generalization_gate_full_visual_fix_20260604/fetch_planner_seeded_generalization_gate/scorecard.md`.
The dashboard now separates optional Xpra operator-view health from required
recorded visual evidence, so visual packages start `world_stream_controller.py`
and `visual_demo_observer.py` even when Xpra is optional. The parent gate passed
with `promotion_evidence=true`: `30/30` planner decisions, `6/6` live missions,
`6/6` browser-watchable visual packages, clean execution/setup/contact quality,
and `0` first-contact blockers. The next autonomous step is seed breadth under
the same evidence contract, followed by hardware-transfer planning.

June 4 recovery/re-aim ownership correction: the latest seed `20260627`
failure clarified the stage boundary. `nav2_reposition_first` owns real Nav2
setup before local fetch; `recovery_or_reaim` now stays local and runs the
bounded forward-only re-aim routine from the generated robot pose. The exact
previously failing `seed20260627_scene04_recovery_or_reaim` row passed after
this change:
`artifacts/session/live_recovery_reaim_local_setup_scene04_20260604/fetch_planner_route_replay_batch/scorecard.md`.
The mission delivered with closest approach `0.193732m`, clean first-contact
quality, stable contact approach, and `nav2_reposition_before_fetch=false`.
The browser-watchable visual package is
`artifacts/session/live_recovery_reaim_local_setup_scene04_20260604_seed20260627_scene04_recovery_or_reaim/fetch_visual_uat_package/scorecard.md`.
This is targeted UAT evidence for the corrected recovery route, while the full
planner-routed seeded gate remains the next promotion-grade proof.

June 4 planner-routed readyfix evidence: the repaired gate path now has live
mission evidence plus representative visual UAT. The planner child
`live_planner_seeded_generalization_gate_mission_only_readyfix_20260604_planner`
passed `30/30` with `0` wrong fetch-ready dispatches. The mission-only replay
`live_planner_seeded_generalization_gate_mission_only_readyfix_20260604_replay`
passed `6/6` executable rows across `recovery_or_reaim`, `fetch_ready_local`,
and `nav2_reposition_first`; the most important Nav2 row aborted before
contact, moved the ball `0.0m`, fell back to bounded local recovery, and still
delivered at `0.197m`. The representative browser-visual replay
`live_planner_seeded_generalization_gate_visual_recheck_20260604` passed `4/4`
with browser-watchable packages and frame-sequence review across recovery,
fetch-ready, and Nav2-first rows. Treat this as green route-owner UAT and
Nav2-fallback boundary evidence. The promotion-grade task remains a canonical
parent seeded gate run that carries visual packaging through the wrapper and
sets `promotion_evidence=true`.

June 4 second-seed breadth proof: seed `20260628` repeated the parent
planner-routed seeded gate as a fresh breadth check:
`artifacts/session/live_planner_seeded_generalization_gate_seed20260628_full_visual_rerun_20260604/fetch_planner_seeded_generalization_gate/scorecard.md`.
The planner child passed `30/30` with `0` wrong fetch-ready dispatches. The
live replay passed `6/6` executable rows and `6/6` browser-watchable visual
packages across two local fetch, two Nav2-first, and two recovery/re-aim cases:
`artifacts/session/live_planner_seeded_generalization_gate_seed20260628_full_visual_rerun_20260604_replay/fetch_planner_route_replay_batch/scorecard.md`.
The analyzer reports clean execution, setup, and contact quality with `0`
first-contact blockers:
`artifacts/session/live_planner_seeded_generalization_gate_seed20260628_full_visual_rerun_20260604_analysis/fetch_planner_route_uat_analyzer/scorecard.md`.
This gives the sim milestone two independent promotion-green randomized seeds
after saved-anchor repeatability. Next execution work is UAT packaging,
regression preservation, and hardware-transfer planning for the planner-routed
route-owner split.

June 4 seed `20260629` boundary repairs and third green gate: seed `20260629`
exposed two useful setup/execution boundaries after the first two green seeds.
The planner child still passed `30/30` with `0` wrong fetch-ready dispatches,
but the first live row `seed20260629_scene01_nav2_reposition_first` aborted
before fetch, moved the ball `0.0m`, and produced no first-contact trace:
`artifacts/session/live_planner_seeded_generalization_gate_seed20260629_full_visual_20260604/fetch_planner_seeded_generalization_gate/scorecard.md`.
The failing geometry was otherwise clean: robot-ball distance `1.222382m`,
ball-target distance `0.47132m`, lateral setup debt about `0.052m`, and yaw
debt under `1deg`. The clean-abort fallback envelope now admits otherwise-safe
Nav2-first rows out to `1.300m` robot-ball separation while preserving the ball
motion, lateral, yaw, and ball-target gates. The exact scene then passed in
`live_seed20260629_scene01_nav2_abort_fallback_repro_20260604`, with closest
approach `0.195562m`, clean first-contact flags, stable contact approach, and
browser-watchable onboard/topdown/world proof:
`artifacts/session/live_seed20260629_scene01_nav2_abort_fallback_repro_20260604/fetch_planner_route_replay_batch/scorecard.md`.
The resumed parent gate then found a second boundary at
`seed20260629_scene05_recovery_or_reaim`: high setup debt consumed about a
minute before first contact, leaving too little push time under the old recovery
window. Extending only the bounded recovery route window repaired that row while
preserving delivery-stop behavior. The final resumed parent gate is now green:
`artifacts/session/live_planner_seeded_generalization_gate_seed20260629_boundary_repair_full_visual_20260604/fetch_planner_seeded_generalization_gate/scorecard.md`.
It reports `promotion_evidence=true`, `30/30` planner routing, `6/6` live
missions, `6/6` browser-watchable packages, clean execution/setup/contact
quality, and `0` first-contact blockers. This gives the sim milestone three
independent randomized promotion-green seeds: `20260627`, `20260628`, and
`20260629`.

Harness hardening from the same run: Gazebo stale-model removal is now
timeout-safe, returning `rc=124` and preserving runner control flow instead of
crashing before mission dispatch.

June 4 harness hardening: route replay now returns immediately when dashboard
startup reports `environment_state=error`, preserving truth-probe failures as
infrastructure evidence before mission launch. Dashboard startup now allows a
longer cold Gazebo truth-probe window, which recovered the saved-anchor live
proof on a fresh service port. Keep this distinction explicit: truth/visual
startup failure blocks evidence collection and belongs to
infrastructure triage before fetch-control interpretation.

June 4 moonshot regression manifest: the current planner-routed stack now has
a compact regression set for future moonshot changes:
`artifacts/session/analysis_planner_moonshot_regression_set_20260604/fetch_moonshot_regression_manifest/scorecard.md`.
The analyzer reads the current saved-anchor repeatability summary, the
setup/contact audit, the three promotion-green seeded gates (`20260627`,
`20260628`, and `20260629`), and the two seed `20260629` boundary rows that
forced the latest repairs. The result is
`planner_routed_moonshot_regression_set_green`, with `9/9` saved-anchor
repeatability preserved and `18/18` seeded live missions plus `18/18` visual
packages preserved. Run this analyzer before broadening the route-owner stack,
swapping executors, changing timeouts, or claiming hardware-transfer readiness.

June 4 broad-UAT recovery repair: the breadth queue now selects rougher seeded
route-owner rows behind the regression manifest:
`artifacts/session/analysis_planner_moonshot_breadth_queue_20260604/fetch_moonshot_breadth_queue/scorecard.md`.
Seed `20260630` exposed the first broad recovery stage gap on
`seed20260630_scene28_recovery_or_reaim`: the initial live replay failed at
`0.557m`, first contact was missing, and visual review confirmed zero ball
motion. The diagnosis is a setup/first-contact recovery yaw-hold stall. The
bounded repair adds recovery line-acquire yaw crawl only while the robot is in
the guarded line-acquire pocket, still far enough from contact, near the
recovery lateral boundary, below the existing close-acquire yaw cap, and before
ball motion. The targeted replay passed with browser-watchable proof, clean
first-contact flags, and `0.198m` closest approach:
`artifacts/session/live_seed20260630_scene28_recovery_crawl_repair_20260604/fetch_planner_route_replay_batch/scorecard.md`.
The full seed `20260630` breadth rerun then passed at
`artifacts/session/live_planner_seeded_generalization_gate_seed20260630_recovery_crawl_full_20260604/fetch_planner_seeded_generalization_gate/scorecard.md`:
planner routing was `30/30`, `wrong_fetch=0`, executable missions were `6/6`,
visual packages were `6/6`, the analyzer was clean, and live closest approach
stayed within `0.194m..0.198m`. Treat this as broad randomized route-owner UAT
evidence behind the regression manifest.

June 4 second rough-seed breadth proof: seed `20260631` passed the same broad
route-owner gate after the recovery yaw-crawl repair:
`artifacts/session/live_planner_seeded_generalization_gate_seed20260631_breadth_20260604/fetch_planner_seeded_generalization_gate/scorecard.md`.
The planner routed `30/30` mixed scenes with `wrong_fetch=0`; the live replay
passed `6/6` executable rows across two `recovery_or_reaim`, two
`nav2_reposition_first`, and two `fetch_ready_local` cases; visual packages were
`6/6`; the analyzer was clean with first-contact blockers `0`; and closest
approach stayed within `0.194m..0.197m`.

June 4 five-seed regression manifest: the manifest now preserves seeds
`20260627` through `20260631`:
`artifacts/session/analysis_planner_moonshot_regression_set_five_seed_20260604/fetch_moonshot_regression_manifest/scorecard.md`.
The result is green with seeded gates `5/5`, live seeded missions `30/30`, and
visual packages `30/30`. Use this manifest as the preservation bar before the
next controller, route-owner, visual-packaging, or hardware-transfer change.

June 4 six-seed breadth checkpoint: seed `20260632` passed the third rough
post-repair route-owner gate:
`artifacts/session/live_planner_seeded_generalization_gate_seed20260632_breadth_20260604/fetch_planner_seeded_generalization_gate/scorecard.md`.
Planner routing was `30/30` with `wrong_fetch=0`; live executable rows were
`6/6`; visual packages were `6/6`; and closest approach stayed within
`0.194m..0.198m`. Sequence review checked both recovery rows, both Nav2-first
rows, and both fetch-ready rows through raw-camera plus topdown contact sheets.
The regression manifest now preserves seeds `20260627` through `20260632`:
`artifacts/session/analysis_planner_moonshot_regression_set_six_seed_20260604/fetch_moonshot_regression_manifest/scorecard.md`.
The result is green with seeded gates `6/6`, live seeded missions `36/36`, and
visual packages `36/36`. Continue on the planner-routed route-owner path and
keep pure Nav2, learned local control, and larger VLA/world-model control as
fallback lanes until this six-seed preservation bar exposes a reproducible
stage gap.

June 4 seven-seed breadth checkpoint: seed `20260633` passed the fourth rough
post-repair route-owner gate:
`artifacts/session/live_planner_seeded_generalization_gate_seed20260633_breadth_20260604/fetch_planner_seeded_generalization_gate/scorecard.md`.
Planner routing was `30/30` with `wrong_fetch=0`; the route mix included
`10` no-go classifications and `4` scan/perception classifications; live
executable rows were `6/6`; visual packages were `6/6`; and closest approach
stayed within `0.193m..0.196m`. All six executable rows were predicted as
contact-quality watches, then analyzed clean after live execution and visual
review. The regression manifest now preserves seeds `20260627` through
`20260633`:
`artifacts/session/analysis_planner_moonshot_regression_set_seven_seed_20260604/fetch_moonshot_regression_manifest/scorecard.md`.
The result is green with seeded gates `7/7`, live seeded missions `42/42`, and
visual packages `42/42`. Keep the planner-routed stack as the primary path; the
next broadening target is larger mixed route-family coverage while the local
contact path remains under the seven-seed preservation bar.

June 5 seed20260635/preflight manifest refresh: the regression manifest now
preserves the current supervised promotion proof and controller guard:
`artifacts/session/analysis_planner_moonshot_regression_set_seed20260635_preflight_20260605/fetch_moonshot_regression_manifest/scorecard.md`.
It is green with seeded gates `8/8`, live seeded missions `48/48`, visual
packages `48/48`, the two seed `20260629` boundary repairs, and one required
base-controller preflight for seed `20260635` scene03. This is the active
preservation bar before route-owner, contact-servo, visual-packaging, or
hardware-transfer moonshots.

June 5 hardware-transfer readiness package: the planner-routed stack now has a
rehearsal contract for the Jetbot/Orin path:
`artifacts/session/analysis_fetch_hardware_transfer_readiness_20260605/fetch_hardware_transfer_readiness/scorecard.md`.
The analyzer passes with `hardware_transfer_ready=true`,
`hardware_proven=false`, and `promotion_evidence=false`. It verifies the active
seed20260635/preflight regression bar, browser-watchable UAT dashboard samples,
`robot_fidelity_orin` runtime documentation, `tensorrt_int8` documentation, and
controller-preflight evidence. The next rung is robot-side rehearsal evidence:
base-controller preflight, mission verdict, onboard raw-camera video,
topdown/world context, keyframe sequence review, and explicit TensorRT/runtime
provenance.

June 5 hardware rehearsal plan: the readiness contract is now converted into a
three-step robot-side rehearsal plan:
`artifacts/session/analysis_fetch_hardware_rehearsal_plan_20260605/fetch_hardware_rehearsal_plan/scorecard.md`.
The plan starts with `run_first_uat.ps1` under `robot_fidelity_orin` and
`tensorrt_int8`, then runs the saved anchors through the planner-routed fetch
stack, then repeats the seed20260635 mixed-route sample. It requires
base-controller preflight, mission verdicts, onboard raw-camera video,
topdown/world context, and keyframe sequence review before the hardware claim
advances beyond rehearsal-ready.

June 5 hardware rehearsal runner preflight: the three-step plan now has a
runner preflight artifact:
`artifacts/session/analysis_fetch_hardware_rehearsal_runner_preflight_20260605/fetch_hardware_rehearsal_runner/scorecard.md`.
It verifies that the `runtime_stack_smoke`, saved-anchor rehearsal, and
seed20260635 mixed-route rehearsal commands resolve locally, then names
`execute_runtime_stack_smoke` as the next action. This is launch readiness; the
hardware proof boundary remains open until the stack smoke produces visual and
runtime artifacts.

June 5 runtime stack smoke execution: the first hardware-rehearsal step now
passes with artifact-contract validation:
`artifacts/session/live_fetch_hardware_rehearsal_runtime_stack_smoke_artifact_contract_20260605/fetch_hardware_rehearsal_runner/scorecard.md`.
The run used `robot_fidelity_orin`, `tensorrt_int8`, and `container_kilted`,
then validated session `20260605T054242Z`, coordinate UAT summary, operator
status, and milestone screenshots. Visual review confirmed the raw camera target
and YOLO debug overlay. The first attempt exposed CRLF in
`uat/orchestrator/run_uat_orchestrator.sh`; the script is now LF-normalized and
covered by a line-ending regression test. The next step is saved-anchor fetch
rehearsal with raw-camera/topdown/world video evidence.

June 5 saved-anchor fetch rehearsal: the second hardware-rehearsal step is
green:
`artifacts/session/live_fetch_hardware_rehearsal_saved_anchors_batch_contract_20260605/fetch_hardware_rehearsal_runner/scorecard.md`.
The replay batch scorecard is
`artifacts/session/hardware_rehearsal_saved_anchors_20260605/fetch_planner_route_replay_batch/scorecard.md`.
Saved-anchor `left05`, `right05`, and `zero` passed `3/3` with browser-playable
raw-camera/topdown/world videos, keyframe contact sheets, control preflight, and
mission verdict artifacts. Visual review matched telemetry for setup, first
contact, push, and delivery-circle arrival. The remaining rehearsal step is
seed20260635 mixed-route execution across fetch-ready, Nav2-first, and
recovery/re-aim owners.

June 5 seed20260635 mixed-route hardware rehearsal: the third
hardware-rehearsal step is green:
`artifacts/session/live_fetch_hardware_rehearsal_seed20260635_mixed_route_contract_20260605/fetch_hardware_rehearsal_runner/scorecard.md`.
The seeded parent gate is
`artifacts/session/hardware_rehearsal_seed20260635_20260605/fetch_planner_seeded_generalization_gate/scorecard.md`.
The replay batch scorecard is
`artifacts/session/hardware_rehearsal_seed20260635_20260605_replay/fetch_planner_route_replay_batch/scorecard.md`.
The planner gate classified `30/30` generated scenes with zero wrong fetch
dispatches. The executable replay selected six rows across fetch-ready,
Nav2-first, and recovery/re-aim route owners, delivered `6/6` inside the
`0.300m` contract, produced `6/6` browser-playable visual packages, and the
analyzer reports clean execution, setup, and contact quality. Visual review
inspected all six raw/topdown keyframe sheets and found the same story in the
camera and telemetry: setup, first contact, push, and terminal delivery. This
clears the current rehearsal ladder in simulation while keeping
`hardware_proven=false`; the next milestone step is robot-side execution with
onboard camera proof under the same artifact contract.

June 5 robot-side rehearsal preflight: the hardware-transfer bridge now has a
local runbook artifact:
`artifacts/session/analysis_fetch_robot_side_rehearsal_preflight_20260605/fetch_robot_side_rehearsal_preflight/scorecard.md`.
The refreshed hardware-transfer readiness scorecard is
`artifacts/session/analysis_fetch_hardware_transfer_readiness_post_seed_rehearsal_20260605_fixed/fetch_hardware_transfer_readiness/scorecard.md`.
The preflight verifies the readiness summary, rehearsal plan, dashboard service,
runtime sync, stack-smoke script, saved-anchor runner, seed20260635 runner, and
required local commands. It reports `local_preflight_ready=true` while keeping
`hardware_connected=false`, `hardware_proven=false`, and
`promotion_evidence=false`. The next execution step is robot-side stack smoke,
followed by saved anchors and seed20260635 mixed-route rehearsal only after
onboard raw-camera/context artifacts are available for sequence review.

June 5 fresh rehearsal ladder: the full runner sequence now passes on the
`robot_fidelity_orin` / `tensorrt_int8` sim-gate runtime target:
`artifacts/session/robot_side_fetch_rehearsal_runtime_stack_smoke_20260605/fetch_hardware_rehearsal_runner/scorecard.md`,
`artifacts/session/robot_side_fetch_rehearsal_saved_anchors_20260605/fetch_hardware_rehearsal_runner/scorecard.md`,
and
`artifacts/session/robot_side_fetch_rehearsal_seed20260635_20260605/fetch_hardware_rehearsal_runner/scorecard.md`.
The stack smoke captured raw D415 and YOLO debug screenshots, saved anchors
passed `3/3`, and seed20260635 mixed-route replay passed `6/6` with clean
route-analyzer status. Visual review covered the stack-smoke screenshots, three
saved-anchor keyframe sheets, and six seed keyframe sheets. Treat this as the
current browser-watchable rehearsal proof while preserving the hardware claim
boundary: physical robot execution, onboard TensorRT on the robot, physical
camera behavior, and field physics remain open.

June 5 seed20260636 breadth UAT: the current route-owner stack now has a
second fresh broad seeded pass at
`artifacts/session/live_planner_seeded_generalization_gate_seed20260636_breadth_20260605/fetch_planner_seeded_generalization_gate/scorecard.md`.
The planner classified `30` generated scenes with `wrong_fetch_dispatch_count=0`.
The executable replay at
`artifacts/session/live_planner_seeded_generalization_gate_seed20260636_breadth_20260605_replay/fetch_planner_route_replay_batch/scorecard.md`
selected two `fetch_ready_local`, two `nav2_reposition_first`, and two
`recovery_or_reaim` rows; all six delivered with visual packages and closest
approaches from `0.193m` to `0.197m`. The analyzer at
`artifacts/session/live_planner_seeded_generalization_gate_seed20260636_breadth_20260605_analysis/fetch_planner_route_uat_analyzer/scorecard.md`
reports clean execution, setup, and contact with first-contact blockers `0`.
Frame-sequence review of all six raw-camera/topdown sheets matched the delivery
geometry. This broadens sim-gate UAT evidence while preserving two claim
boundaries: provider-backed LLM routing needs a rerun after `OPENAI_API_KEY` is
available, and physical/onboard proof still gates `hardware_proven=true`.

June 5 seed20260637 breadth UAT: a third fresh seeded pass is green at
`artifacts/session/live_planner_seeded_generalization_gate_seed20260637_breadth_20260605/fetch_planner_seeded_generalization_gate/scorecard.md`.
The planner classified `30` generated scenes with `wrong_fetch_dispatch_count=0`.
The executable replay at
`artifacts/session/live_planner_seeded_generalization_gate_seed20260637_breadth_20260605_replay/fetch_planner_route_replay_batch/scorecard.md`
selected two `fetch_ready_local`, two `nav2_reposition_first`, and two
`recovery_or_reaim` rows; all six delivered with visual packages. The analyzer
at
`artifacts/session/live_planner_seeded_generalization_gate_seed20260637_breadth_20260605_analysis/fetch_planner_route_uat_analyzer/scorecard.md`
reports clean execution, setup, and contact with first-contact blockers `0`.
Frame-sequence review of all six raw-camera/topdown sheets matched the delivery
geometry, including two high-risk recovery rows. This strengthens the broad
sim-gate UAT floor while leaving provider-backed LLM routing and physical
hardware-transfer proof as the active gates.

June 5 seed20260639 rough breadth UAT: the current route-owner stack now has a
cleaner roughest-row seeded pass at
`artifacts/session/live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605/fetch_planner_seeded_generalization_gate/scorecard.md`.
The planner classified `30` generated scenes with `wrong_fetch_dispatch_count=0`.
The replay at
`artifacts/session/live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_replay/fetch_planner_route_replay_batch/scorecard.md`
selected nine executable rows: three `recovery_or_reaim`, three
`nav2_reposition_first`, and three `fetch_ready_local`. All nine delivered with
visual packages; closest approaches stayed in `0.194m..0.198m`. The analyzer at
`artifacts/session/live_planner_seeded_generalization_gate_seed20260639_rough_breadth_20260605_analysis/fetch_planner_route_uat_analyzer/scorecard.md`
reports clean execution, setup, and contact with first-contact blockers `0`.
Frame-sequence review of all nine raw-camera/topdown sheets matched the
delivery geometry. The command omitted `--env-ready-timeout-s`, so the pass also
proves the new `600s` rough-gate startup default. This remains sim-gate UAT:
`OPENAI_API_KEY` was unavailable, provider-backed LLM routing stayed open, and
hardware proof is still pending.

June 5 seed20260638 rough breadth UAT: the route-owner stack added an earlier
roughest-row seeded pass at
`artifacts/session/live_planner_seeded_generalization_gate_seed20260638_rough_breadth_20260605/fetch_planner_seeded_generalization_gate/scorecard.md`.
The planner classified `30` generated scenes with `wrong_fetch_dispatch_count=0`.
The replay at
`artifacts/session/live_planner_seeded_generalization_gate_seed20260638_rough_breadth_20260605_replay/fetch_planner_route_replay_batch/scorecard.md`
selected eight executable rows: three `recovery_or_reaim`, three
`nav2_reposition_first`, and two `fetch_ready_local`. All eight delivered with
visual packages; closest approaches stayed in `0.194m..0.198m`. The analyzer at
`artifacts/session/live_planner_seeded_generalization_gate_seed20260638_rough_breadth_20260605_analysis/fetch_planner_route_uat_analyzer/scorecard.md`
reports clean execution, setup, and contact with first-contact blockers `0`.
Frame-sequence review of all eight raw-camera/topdown sheets matched the
delivery geometry. The first attempt exposed a fresh-dashboard startup timeout
on scene15; the row passed on resume with `--env-ready-timeout-s 600`, so the
evidence class is startup-health watch rather than control failure.

June 4 mixed route-family UAT proof: seed `20260633` now has one live row per
route family at
`artifacts/session/analysis_mixed_route_family_uat_seed20260633_20260604/fetch_planner_route_uat_analyzer/scorecard.md`.
The batch passed route contracts `5/5`, visual packages `5/5`, executable
deliveries `3/3`, route-only proofs `2/2`, clean analyzer status, and
first-contact blockers `0`. This covers the live scan/defer and safe no-go
families by contract.

June 4 two-per-route mixed-family proof: the scaled seed `20260633` replay is
green at
`artifacts/session/analysis_mixed_route_family_2per_route_seed20260633_20260604/fetch_planner_route_uat_analyzer/scorecard.md`.
It passed route contracts `10/10`, visual packages `10/10`, executable
deliveries `6/6`, route-only proofs `4/4`, clean analyzer status, and
first-contact blockers `0`.

June 4 second rough mixed-family proof: seed `20260632` repeated the same
two-per-route mixed-family UAT at
`artifacts/session/analysis_mixed_route_family_2per_route_seed20260632_20260604/fetch_planner_route_uat_analyzer/scorecard.md`.
It selected `10` fresh rows and passed route contracts `10/10`, visual packages
`10/10`, executable deliveries `6/6`, route-only proofs `4/4`, clean analyzer
status, and first-contact blockers `0`. Sequence review across all ten
raw-camera/topdown sheets matched the route contract: executable rows delivered
into the visible circle, while planner-only rows withheld local fetch. The next
autonomous step is a harder mixed-scenario UAT matrix with opposite-side starts,
larger setup angles, and forward-only setup pressure, plus hardware-transfer
packaging in parallel. Hold contact-control changes until that matrix exposes
a reproduced route-family stage gap.

June 4 hard mixed-scenario proof: `hard_mixed_fetch_planner_v1` is now the
named pressure matrix for planner-routed UAT. The analyzer scorecard is
`artifacts/session/analysis_hard_mixed_route_family_20260604/fetch_planner_route_uat_analyzer/scorecard.md`.
The matrix covers wide-angle direct local fetch, opposite-side Nav2-first
setup, large-angle recovery/re-aim, scan/defer, and safe no-go with two rows
per route family. The live replay passed route contracts `10/10`, visual
packages `10/10`, executable deliveries `6/6`, route-only proofs `4/4`, clean
setup/contact/execution analysis, and first-contact blockers `0`; executable
closest approaches ranged from `0.194m` to `0.197m`. Raw-camera and topdown
sequence review matched the telemetry.

June 4 LLM-shadow hard-matrix proof: the real provider now matches deterministic
route classification on the same hard matrix at
`artifacts/session/shadow_llm_hard_mixed_fetch_planner_v1_20260604/fetch_planner_handoff_gate/scorecard.md`.
The dry classification gate passed `10/10`, provider status was `ok` on every
row, guard agreement was `10/10`, wrong fetch-ready dispatches were `0`, and
`llm_shadow_ready=True`. Treat this as high-level route-selection evidence.
Live execution remains deterministic and guarded until shadow scoring also
covers the rough mixed-family seeds and seven-seed manifest. Continue
hardware-transfer packaging in parallel, and use reproduced hard-matrix failures
as the trigger for local contact-control changes.

The first LLM-shadow rollup now covers the hard matrix plus rough mixed seeds
`20260632` and `20260633`:
`artifacts/session/analysis_llm_shadow_hard_plus_rough_mixed_20260604/fetch_planner_llm_shadow_evidence/scorecard.md`.
It passed `70/70` route classifications, provider status was `ok` on every row,
guard agreement was `70/70`, and wrong fetch-ready dispatches stayed at `0`.
The full hard-plus-seven-seed manifest is also green:
`artifacts/session/analysis_llm_shadow_hard_plus_seven_seed_manifest_20260604/fetch_planner_llm_shadow_evidence/scorecard.md`.
It passed `220/220` route classifications, provider status was `ok` on the
clean manifest inputs, guard agreement was `220/220`, and wrong fetch-ready
dispatches stayed at `0`. Seed `20260630` had one transient provider timeout on
the first pass and cleared on the longer-timeout rerun. The next autonomous step
is defining supervised-live route-selection thresholds and fallback policy.

The supervised route guard now has a first hard-matrix proof:
`artifacts/session/supervised_llm_hard_mixed_fetch_planner_v1_20260604/fetch_planner_handoff_gate/scorecard.md`.
In `llm_supervised_guarded` mode, the provider returned `ok` for all ten hard
scenes, accepted proposals `10/10`, vetoed `0`, matched the deterministic guard
`10/10`, and produced wrong fetch-ready dispatches `0`. Run the same supervised
dry mode over the seven-seed manifest before live route-selection authority.

The supervised hard-plus-seven-seed rollup now completes that dry mode:
`artifacts/session/analysis_supervised_llm_hard_plus_seven_seed_manifest_20260604/fetch_planner_llm_supervised_evidence/scorecard.md`.
The rollup is green as guarded-fallback evidence across `220` provider-backed
cases: route pass/fail `220/0`, provider `ok` `220/220`, guard agreement
`220/220`, wrong fetch-ready dispatches `0`, and accept/veto `217/3`. The three
vetoes were confidence-only and fell back to the deterministic route. The next
autonomous execution step is live route-owner visual UAT, with LLM route output
still gated by deterministic guards.

The supervised hard route-owner replay now provides that first live visual UAT:
`artifacts/session/analysis_supervised_hard_mixed_route_family_20260604/fetch_planner_route_uat_analyzer/scorecard.md`.
It used the supervised hard planner gate and passed route contracts `10/10`,
visual packages `10/10`, executable deliveries `6/6`, and route-only proofs
`4/4`. Visual frame-sequence review matched telemetry across representative
fetch-ready, Nav2, recovery, and no-go cases. Continue with broader supervised
route-owner live batches before canonical saved-layout promotion.

## Evidence Reset

May 31, 2026 reset: a local fetch result counts as UAT or architecture evidence
only when `geometry_consistency.pass=true`, the visible delivery marker matches
`fetch_pose_world`, and same-session browser-watchable onboard plus context
video exists. Pre-fix or marker-mismatched fetch passes are diagnostic
implementation evidence.

June 3, 2026 visual-review rule: operator-facing UAT needs a sequence review
across start/setup, approach, first contact, mid-push or handoff,
terminal/stop, and final frames from top-down plus onboard/world views when
present. `fetch_visual_uat_package.py` may accept an explicit same-session
keyframe recovery confirmation when continuous visual summaries are incomplete,
and the package records
`visual_confirmation_keyframe_recovery` so the evidence stays labeled.
The package builder also recovers browser-safe onboard, top-down, and
world-stream videos from saved keyframes or world frames when recorder MP4s are
missing, empty, or invalid; recovered clips are listed in the scorecard under
`Video Recovery`.

June 1, 2026 provenance reset: direct `fetch_to_pose` evidence also needs
`model_provenance_valid=true`, target model `calibrated_golf_ball`, target
radius `0.021336m`, and marker model `golf_ball_delivery_zone_marker`. Commit
`680e393 Use calibrated ball for fetch direct runs` is the boundary for direct
fetch reruns. Older direct artifacts with missing or legacy model provenance
are diagnostic and should be rebuilt through the saved-layout ladder.

Corrected reference artifacts:

- mission:
  `artifacts/session/20260531T204154158382Z/gather_mission/20260531T204255Z/mission_verdict.json`
- visual package:
  `artifacts/session/uat_fetch_visual_package_postfix_20260531/fetch_visual_uat_package/scorecard.md`
- geometry audit:
  `artifacts/session/fetch_geometry_evidence_audit_postfix_20260531/fetch_geometry_evidence_audit/scorecard.md`

June 1, 2026 contact-buffer handoff validation: commit
`02a4c12 Fix Nav2 contact-buffer fetch handoff` fixes the stop-short behavior
seen in operator video review. Nav2 now uses the tight
`corridor_push_goal_checker`, the readiness launch publishes the missing depth
scan TF, and the fetch adapter treats a close/aligned no-object-motion Nav2 stop
as `monitor_contact_buffer_handoff`. The bounded deterministic contact servo
then confirms first contact before the corridor push continues.

Reference proof:

- campaign:
  `artifacts/session/live_contact_buffer_monitor_servo_zero_probe_20260601/gather_mission_repeatability/campaign_run_summary.json`
- visual package:
  `artifacts/session/uat_contact_buffer_monitor_servo_zero_probe_20260601/fetch_visual_uat_package/scorecard.md`
- result:
  `fetch_to_pose_pass=true`, closest delivery distance `0.179959m`, Nav2
  handoff at `robot_ball_distance_m=0.195671`, first-contact servo motion
  `0.046811m`

Saved-anchor requalification, later June 1:

- planner gate:
  `artifacts/session/live_planner_handoff_mixed_fetch_20260601/fetch_planner_handoff_gate/gate_summary.json`
  passed `5/5`
- `zero`:
  `artifacts/session/live_contact_buffer_saved_anchor_zero_one_run_20260601/gather_mission_repeatability/campaign_run_summary.json`
  passed, closest `0.152567m`
- `left05`:
  `artifacts/session/live_contact_buffer_saved_anchor_left05_one_run_20260601/gather_mission_repeatability/campaign_run_summary.json`
  passed, closest `0.266102m`, contact-quality watch
- `right05`:
  `artifacts/session/live_contact_buffer_saved_anchor_right05_one_run_20260601/gather_mission_repeatability/campaign_run_summary.json`
  failed at `capture_entry_timeout`
- audit:
  `artifacts/session/audit_contact_buffer_right05_one_run_20260601/fetch_saved_anchor_setup_contact_audit/scorecard.md`
  classifies the blocker as setup/capture

Stage-owner comparison, later June 1:

- analyzer:
  `scripts/fetch_stage_owner_comparison.py`
- artifact:
  `artifacts/session/live_fetch_stage_owner_comparison_20260601/fetch_stage_owner_comparison/scorecard.md`
- recommended action:
  `run_setup_capture_gap_fill_or_port_prior_behavior`
- interpretation:
  the planner handoff is green; current staged Nav2/contact-buffer is red on
  `right05` setup/capture; Nav2 corridor-push and the corrected direct
  `right05` reference show reusable setup/capture behavior; current staged
  first-contact and push/coast are yellow because `right05` stopped before
  those stages; May 27 object-centric fetch remains the best terminal-delivery
  comparison, with yellow margin flags near the delivery-radius boundary.

Setup/capture gap-fill probe, later June 1:

- analyzer:
  `scripts/fetch_setup_capture_gap_fill_probe.py`
- gap-fill artifact:
  `artifacts/session/live_fetch_setup_capture_gap_fill_20260601/fetch_setup_capture_gap_fill_probe/scorecard.md`
- saved-anchor one-run rebuild:
  `artifacts/session/live_ai_push_coast_saved_anchor_gapfill_one_run_20260601/calibrated_fetch_architecture_revisit/scorecard.md`
- stage-quality audit:
  `artifacts/session/audit_ai_push_coast_gapfill_saved_anchor_one_run_20260601/fetch_saved_anchor_setup_contact_audit/scorecard.md`
- capture-entry diagnostic:
  `artifacts/session/audit_ai_push_coast_gapfill_saved_anchor_one_run_20260601/fetch_capture_entry_diagnostic_analyzer/scorecard.md`
- interpretation:
  setup/capture is requalified on the corrected staged path. The latest
  saved-anchor one-run set is `2/3`: `zero` passed cleanly, `left05` passed
  with a first-contact alignment watch, and `right05` reached capture-entry but
  missed the delivery radius at `0.520765m` after a Nav2 corridor-push action
  abort. This initially pointed at terminal-arrival correction. The later
  clip-review reframe below supersedes that sequence.

Clip-review reframe, later June 1:

- audit:
  `artifacts/session/audit_ai_push_coast_capture_yaw_saved_layout_one_run_20260601/fetch_saved_anchor_setup_contact_audit/scorecard.md`
- visual package:
  `artifacts/session/uat_ai_push_coast_capture_yaw_saved_layout_one_run_20260601/fetch_visual_uat_package/scorecard.md`
- interpretation:
  the latest operator-visible clips supersede the terminal-correction priority.
  `zero` is the desired behavior, but `left05` and `right05` show off-axis
  setup/capture/handoff instability. `left05` pushes the ball laterally out of
  the corridor; `right05` under-moves the ball after unstable capture. The next
  implementation work is a first-class capture-geometry setup stage before
  another terminal correction probe.

## Default Execution Order

1. Keep `spike/fetch-arch-ai-push-coast-servo-20260529` as the active lane for
   corrected requalification, analyzers, guards, and fallback AI/contact work.
2. Keep shared docs/harness changes propagated to `physics-calibrated-golf-fetch-v1`
   and `main` after the spike has clean verification.
3. Run planner-handoff evidence before broad random UAT:
   - deterministic frozen scene gate:
     `python scripts/fetch_planner_handoff_gate.py --campaign-id <id> --scene-descriptor-json ros2_config/fetch_planner_scene_sets/mixed_fetch_planner_v1.json --dry-run`
   - optional LLM shadow comparison:
     `python scripts/fetch_planner_handoff_gate.py --campaign-id <id> --scene-descriptor-json ros2_config/fetch_planner_scene_sets/mixed_fetch_planner_v1.json --dry-run --planner-mode llm_shadow`
4. Run the moonshot planner-routed executor ladder before treating broad random
   scenes as UAT:
   - `fetch_ready_local` dispatches the forward-only local fetch proof runner
     with route metadata
   - `nav2_reposition_first` dispatches the same forward-only proof runner as
     v0 executable evidence, then graduates to real Nav2 reposition plus local
     fetch
   - `scan_or_perceive_first` records an executed planner-owned
     scan/perception-refresh abstention until a live refresh executor exists
   - `recovery_or_reaim` dispatches the bounded forward-only re-aim proof
     executor and reports contact-quality watches separately from delivery
     success
   - `ambiguous_or_unsafe_no_go` records an executed safe no-go outcome with
     rationale
5. Run local fetch evidence only for planner-approved `fetch_ready_local` scenes
   or after an executable `nav2_reposition_first` route has produced a
   forward-only setup handoff.
6. Rerun corrected saved-layout local fetch evidence before expanding custom
   control:
   - `zero`, `left05`, `right05`
   - no retries
   - `0.300m` delivery radius
   - `model_provenance_valid=true`
   - same-session visual package
7. Use the staged local fetch sequence as the current implementation baseline:
   planner-approved local case -> ball-target delivery line -> capture pose ->
   setup motion -> geometry gate -> Nav2 corridor push -> delivery monitor.
8. Treat the June 1 clip-reviewed saved-anchor rebuild as superseded by the
   June 2 fetch-ready handoff repair and one-run matrix.
9. Use the fetch-ready capture-entry handoff as the current setup stage:
   - compute the robot's standoff, lateral error, and yaw error against the
     ball-target line
   - hold when the fetch push-readiness gate is green under the tighter
     capture-entry `0.58m` standoff cap
   - hand off to `fetch_to_pose` corridor push with `handoff_kind =
     fetch_push_ready`
   - preserve gate decisions in mission verdicts, saved-anchor summaries, and
     visual UAT packages
10. Treat the June 2 saved-anchor one-run result as the current UAT screen:
   `artifacts/session/live_fetch_push_ready_handoff_saved_anchor_one_run_20260602/calibrated_fetch_architecture_revisit/scorecard.md`.
   The matrix is `3/3` at one run each with a green mobile visual package:
   `artifacts/session/uat_fetch_push_ready_handoff_saved_anchor_one_run_20260602/fetch_visual_uat_package/scorecard.md`.
11. Use the June 2 corrected saved-layout repeatability result as the current
    saved-anchor baseline:
    `artifacts/session/live_fetch_setup_contact_repair_saved_anchor_3x_20260602/calibrated_fetch_architecture_revisit/scorecard.md`.
    `zero`, `left05`, and `right05` passed promotion `3/3` with worst closest
    approaches `0.201194m`, `0.169541m`, and `0.136046m`.
12. Use the setup/contact audit as the stage-quality baseline:
    `artifacts/session/audit_fetch_setup_contact_repair_saved_anchor_3x_20260602/fetch_saved_anchor_setup_contact_audit/scorecard.md`.
    The audit is `stage_quality_green=true` with one `left05`
    `capture_entry_time_watch`.
13. Use the initial June 2 seeded shadow/evidence gate as the setup/capture
    blocker that drove the bounded recenter repair:
    `artifacts/session/live_fetch_setup_contact_repair_seeded_gate_20260602/fetch_generalization_gate/gate_summary.json`.
    The analyzer is
    `artifacts/session/evidence_fetch_setup_contact_repair_seeded_gate_20260602/fetch_seeded_gate_evidence_analyzer/scorecard.md`.
    The gate passed `4/6`; `case01` and `case06` reproduced
    `capture_entry_timeout` before corridor-push handoff.
14. Treat the frozen setup/capture layouts as repaired for one-run evidence:
    `artifacts/session/live_fetch_setup_contact_repair_seeded_gate_20260602/fetch_generalization_gate/frozen_failure_layouts`.
    Targeted one-run gates passed for both frozen cases:
    `artifacts/session/live_fetch_frozen_case01_setup_capture_bounded_setup_v2_20260602/gather_mission_repeatability/campaign_run_summary.json`
    and
    `artifacts/session/live_fetch_frozen_case06_setup_capture_bounded_setup_v2_20260602/gather_mission_repeatability/campaign_run_summary.json`.
15. Use the clean seeded rerun as the current random-evidence baseline:
    `artifacts/session/live_fetch_setup_capture_bounded_setup_v2_seeded_gate_clean_20260602/fetch_generalization_gate/gate_summary.json`.
    The analyzer is
    `artifacts/session/evidence_fetch_setup_capture_bounded_setup_v2_seeded_gate_20260602/fetch_seeded_gate_evidence_analyzer/scorecard.md`.
    The gate passed `5/6` initially with `0` reproduced failures; `case01`
    failed once after `fetch_push_ready`, then passed repro.
16. Use the near-margin repair as the case01 closeout:
    `ball_already_at_delivery_margin` is a readiness note when setup geometry is
    otherwise ready, and contact-buffer re-push readiness accepts `0.10m`
    standoff.
17. Treat the `case01` `3x` repeatability proof as green:
    `artifacts/session/live_fetch_case01_near_margin_gate_v1_repeat_3x_20260602/gather_mission_repeatability/campaign_run_summary.json`.
    The result is `3/3` with `handoff_kind=fetch_push_ready`.
18. Treat the earlier `case01` `3x` probe as superseded evidence:
    `artifacts/session/live_fetch_case01_bounded_setup_v2_repeat_3x_20260602/gather_mission_repeatability/campaign_run_summary.json`.
    The earlier `2/3` result drove the near-margin repair.
19. Use the latest seeded gate as the active watchlist:
    `artifacts/session/live_fetch_relaxed_standoff_v1_seeded_gate_20260602/fetch_generalization_gate/gate_summary.json`.
    The analyzer is
    `artifacts/session/evidence_fetch_relaxed_standoff_v1_seeded_gate_20260602/fetch_seeded_gate_evidence_analyzer/scorecard.md`.
    The gate passed `5/6` initially with `1` non-repro failure and `0`
    reproduced failures. `case04` failed once with
    `missed_delivery_radius_after_push_readiness_gate_failed` and
    `missing_first_contact_alignment`, then passed repro.
20. Treat case04 targeted repeatability as delivery-green and contact-quality
    flagged:
    `artifacts/session/live_fetch_case04_relaxed_standoff_v1_repeat_3x_20260602/gather_mission_repeatability/campaign_run_summary.json`.
    Delivery passed `3/3`; `missing_first_contact_alignment` appeared in `2/3`.
21. Treat the clean shadow seeded gate as the handoff to guarded live:
    `artifacts/session/live_fetch_near_margin_case04_repeat_seeded_gate_20260602/fetch_generalization_gate/gate_summary.json`
    and
    `artifacts/session/evidence_fetch_near_margin_case04_repeat_seeded_gate_20260602/fetch_seeded_gate_evidence_analyzer/scorecard.md`.
    The result is `6/6`, with `0` reproduced failures.
22. Treat guarded-live saved-anchor repeatability as green:
    `artifacts/session/live_fetch_guarded_live_saved_anchor_3x_20260602/calibrated_fetch_architecture_revisit/scorecard.md`.
    `zero`, `left05`, and `right05` passed promotion `3/3`.
23. Treat guarded-live seeded random as promotion-ready contract evidence:
    `artifacts/session/live_fetch_guarded_live_seeded_gate_20260602/fetch_generalization_gate/gate_summary.json`
    and
    `artifacts/session/evidence_fetch_guarded_live_seeded_gate_20260602/fetch_seeded_gate_evidence_analyzer/scorecard.md`.
    The result is `6/6`, `0` reproduced failures, and
    `promotion_evidence=True`.
24. Keep guarded-live AI/contact execution terminal-only until a later contact
    quality slice proves broader deterministic routines are needed and useful.
25. Build a mobile visual UAT package before asking for operator signoff:
    `python scripts/fetch_visual_uat_package.py --campaign-id <id> --planner-summary <gate_summary.json> --seeded-evidence-summary <evidence_summary.json> --mission-summary <campaign_run_summary.json> --visual-dir <session>/visual`
    Current package:
    `artifacts/session/uat_fetch_guarded_live_seeded_case04_20260602/fetch_visual_uat_package/scorecard.md`.
    The package passes with browser-safe onboard, debug, topdown, and world
    videos for guarded-live seeded case04.
26. Freeze reproduced seeded/random failures into named layouts before tuning.

June 5 roughest-seed breadth and authority update: seed `20260634` adds a
roughest-order breadth pass for the planner-routed stack:
`artifacts/session/live_supervised_planner_seeded_generalization_gate_seed20260634_roughest_provider_reuse_20260605/fetch_planner_seeded_generalization_gate/scorecard.md`.
The replay delivered `6/6` executable rows with `6/6` browser-watchable visual
packages across `recovery_or_reaim`, `nav2_reposition_first`, and
`fetch_ready_local`. The two recovery rows and two Nav2 rows were clean. The
two fetch-ready rows delivered inside the `0.300m` contract and carried
`ball_lateral_knock_away` plus `contact_trajectory_angle_error` watches, which
keeps direct local-fetch contact smoothness active.

The provider-backed reuse pass resolved the earlier evidence-authority gap:
`artifacts/session/live_supervised_planner_seeded_generalization_gate_seed20260634_roughest_provider_reuse_20260605/fetch_planner_seeded_generalization_gate/scorecard.md`.
The provider returned `ok` for all `30` planner rows, guard agreement stayed
`30/30`, wrong fetch dispatches stayed `0`, and the parent seeded gate now
reports `planner_authority_ready=true`. Strict all-accepted authority remains
false because one `scan_or_perceive_first` row used deterministic fallback for
`confidence_below_threshold`; the repo treats that as guarded fallback
authority, consistent with the LLM-supervised evidence rollup. The next control
work is direct local-fetch contact smoothness, while hardware-transfer planning
can start from the provider-backed guarded route-owner stack.

The targeted contact-smoothing recheck is now clean:
`artifacts/session/live_fetch_ready_contact_smoothing_recheck_seed20260634_20260605/fetch_planner_route_uat_analyzer/scorecard.md`.
Planner-route defaults apply `line_servo_contact_lateral_ready_m=0.024` only to
`fetch_ready_local` layouts whose route-quality metadata requests
`pre_contact_smoothing`; clean fetch-ready layouts keep `0.028m`. The two rough
fetch-ready watch rows reran as `2/2` deliveries with clean execution, setup,
contact, and first-contact metrics. Scene04 max ball lateral error improved
from `0.049686m` to `0.000224m`; scene28 improved from `0.058755m` to
`0.000273m`. Contact-angle error dropped from roughly `-7deg` to near `0deg`
on both rows.

The full rough executable route-family preservation rerun also passed:
`artifacts/session/live_fetch_ready_contact_smoothing_full_rough_analysis_seed20260634_20260605/fetch_planner_route_uat_analyzer/scorecard.md`.
It delivered `6/6` missions and `6/6` browser-watchable visual packages across
two recovery/re-aim, two Nav2-first, and two fetch-ready rows. The analyzer
reports clean execution, setup, and contact quality with `0` contact watches and
`0` first-contact blockers. Treat this as rough route-owner UAT preservation
evidence with `promotion_evidence=false`; the next canonical seeded/saved-layout
promotion refresh should include the smoothing default.

June 5 supervised seeded promotion refresh: seed `20260635` is the current
canonical supervised promotion proof for the planner-routed stack:
`artifacts/session/live_supervised_planner_seeded_generalization_gate_seed20260635_smoothing_20260605/fetch_planner_seeded_generalization_gate/scorecard.md`.
The provider-backed planner child routed `30/30` generated scenes with provider
`ok=30/30`, guard agreement `30/30`, wrong fetch dispatches `0`, and one
confidence-only deterministic fallback. The live replay selected two
`nav2_reposition_first`, two `recovery_or_reaim`, and two `fetch_ready_local`
rows, delivered `6/6`, produced `6/6` browser-watchable packages, and the
analyzer reports clean execution, setup, contact, and `0` first-contact
blockers. Closest approach stayed inside `0.194m..0.197m`.

Scene03 turned the prior no-motion ambiguity into a runtime guard. The failed
attempt showed commands published while the robot and ball stayed fixed because
the base diff-drive controller was unavailable. Executable fetch now runs a
service-call preflight through `/controller_manager/list_controllers`, records
`control_preflight.json`, and fails before mission scoring unless
`jetbot_base_controller` is active. The repaired scene03 session
`20260605T045353381785Z` confirmed controller readiness, observed first contact
at `27.631s`, moved the ball from `(0.293, -0.118)` to `(0.756, -0.035)`, and
delivered at `0.197m`. Hardware-transfer packaging should treat this preflight
as a required executor guard.

## Gates

- Planner handoff gate passes only when no out-of-envelope scene dispatches
  local fetch.
- Fetch UAT evidence passes only when corrected marker geometry, calibrated model
  provenance, and same-session video are present.
- Mobile visual UAT passes only when the package has planner-green evidence, a
  local fetch pass, and playable `world_stream.mp4` plus `topdown_telemetry.mp4`.
- Operator-review videos are useful UAT evidence only when they are
  browser-watchable and traceable to the same session. Rebuilt videos can support
  review, but a green package should also carry healthy observer confirmation.
- Saved-layout gate requires `zero`, `left05`, and `right05` one-run, then `3/3`.
- Seeded gate uses `scripts/fetch_generalization_gate.py` and
  `scripts/fetch_seeded_gate_evidence_analyzer.py`.
- Promotion evidence must be canonical `real_time_factor=1.0`; accelerated runs
  are rejection/training evidence only.

## Stop Conditions

Continue autonomously through reversible edits, tests, docs, commits, pushes,
and evidence runs. Stop for destructive operations, paid credentials, hardware
safety risk, or a repeated blocker outside the current gates.
