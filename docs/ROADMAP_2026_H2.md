# Roadmap 2026 H2

## Near-Term (First UAT to Full Visual UAT)

Current status as of February 27, 2026:

1. First-UAT promotion gate is green (`session 20260227T230314Z`).
2. Full headless replay gate is green (`session 20260227T231443Z`).
3. Visual milestone evidence runs are green for M1/M2/M3 (latest M2 `20260227T232250Z`, M3 `20260227T232745Z`).
4. Next promotion focus is repeatability and soak cycles for the same gates.

1. Keep `scripts/run_first_uat.ps1` as the default operator entrypoint on `ExecutionLane=container_kilted`.
2. Keep gate-critical first-UAT steps container-native (no host `/opt/ros/kilted` dependency).
3. Achieve first-UAT green on canonical target:
   - coordinate summary `pass=true`
   - milestone 1 evidence bundle present
4. Run headless replay gates in sequence:
   - coordinate
   - snapshot verification
   - orientation
   - Nav2 readiness
   - multi-target Nav2
5. Run visual milestone progression:
   - milestone 1 (perception)
   - milestone 2 (3D estimate coherence)
   - milestone 3 (autonomous approach)
6. Freeze operator docs only after one green first-UAT cycle and one green full headless replay cycle.
7. Keep `scripts/run_headless_pre_llm.ps1` as the default developer push path with `Lane=dual` until LLM integration starts.

Status update as of February 28, 2026:

1. Pre-LLM dual-lane campaign achieved `3/3` green:
   - `artifacts/session/20260228T155850Z/pre_llm_headless_summary.json`
   - `artifacts/session/20260228T160643Z/pre_llm_headless_summary.json`
   - `artifacts/session/20260228T161425Z/pre_llm_headless_summary.json`
2. Fidelity soak gate is green:
   - `artifacts/session/20260228T162201Z/pre_llm_headless_summary.json`
   - includes Nav2 duration `1200s` and 12-goal multi-target sequence.
3. Campaign trend report and RC package generated:
   - `artifacts/session/20260228T164623Z/pre_llm_campaign_trend.json`
   - `artifacts/session/20260228T164654Z/readiness_report.json` (`pass=true`)
4. Pre-LLM contract freeze applied:
   - `runtime/contracts/llm_control_contract.yaml` (`contract_status: frozen_pre_llm`)

## Mid-Term (Dual-Lane Regression Hardening)

1. Keep Jetty gate lane as authoritative release lane.
2. Maintain Isaac lane as parity/cross-validation lane behind bridge contract.
3. Add weekly dual-lane regression policy:
   - Jetty full headless gate replay weekly
   - Isaac subset parity replay weekly
4. Enforce per-session isolation:
   - unique compose project naming
   - stale project cleanup before each run
   - explicit ROS domain strategy per session

## Pre-LLM Integration Gate Checklist

1. Acquire/plan/track low-level interfaces are frozen and documented.
2. Safety contracts are frozen:
   - stale detection timeout
   - navigation timeout
   - safe stop behavior
3. Required artifact set is green in one release candidate cycle:
   - coordinate summary
   - orientation summary
   - nav readiness summary
   - milestone evidence bundle(s)
4. Unresolved failure signatures are tracked in session readiness reports.
5. Final GUI rehearsal aligns with headless gate outcomes before LLM handoff.

## Post-Freeze Bounded LLM Promotion Path

Once the frozen pre-LLM boundary is in place, the next roadmap step is not open-ended autonomy. It is a bounded promotion ladder:

1. headless LLM proof over the frozen intent contract ✓
2. repeatability gate on the authoritative `container_kilted` lane ✓
3. simple browser UAT demo for the same proof path ✓
4. bounded supervisor reuse across the visible-ball M3 scenario family ✓
   - `visit_m3_positions` scenario validates center, left, right targets using the same policy
5. target prior contract for multi-target scenarios ✓
   - executor receives expected target position from the mission layer, not from sim ground truth
   - prior-based lock gating and prior-based track approach implemented and tested
   - `visit_single_ball_proof` and `visit_three_ball_sequence` passing
   - sim truth probe is a validation oracle (test-time only), not an executor runtime dependency
   - this makes the executor's target discrimination portable to hardware
6. provider benchmarking infrastructure for a future on-machine model path on Orin Nano ✓
   - provider abstraction (`DecisionProvider` protocol) and replay comparison tool exist
   - `LocalModelProvider` placeholder ready for Orin Nano integration
   - benchmarking is not a prerequisite for the current promotion ladder

Status update as of April 3, 2026:

1. All six promotion ladder steps are complete.
2. Target prior contract validated: `visit_three_ball_sequence` 3/3, `visit_m3_positions` 3/3.
3. Escalation rules formalized with table and 19 policy tests.
4. Browser UAT surface meets acceptance criteria (Watch/Drive/Inspect tabs).
5. Provider benchmarking infrastructure in place (replay comparison tool, local provider placeholder).

Status update as of April 4, 2026:

1. Direct intent dispatch implemented: file-based inbox replaces docker-exec-per-intent.
2. Intent dispatch latency reduced from ~13s to <1s.
3. Zombie dashboard prevention: startup kills stale processes, `allow_reuse_address` enabled.
4. Dashboard URL fix: client-facing URL uses `127.0.0.1` when binding `0.0.0.0` (Windows).

### Intended Outcomes

1. prove that the LLM can supervise high-level bounded decisions without owning low-level loops
2. keep deterministic policy/gating as the safety and contract layer
3. give operators a browser demo that is simple enough to trust and understand
4. keep the control architecture compatible with both:
   - Wi-Fi/cloud inference
   - smaller local-model inference later
5. ensure multi-target discrimination is solved in sim before hardware POC:
   - executor target verification uses mission-provided priors, not sim-only ground truth
   - the same mechanism works on hardware with operator-provided or observation-derived priors

### Explicit Non-Goals For This Roadmap Slice

1. freeform browser prompt control
2. open-ended task decomposition
3. end-to-end VLA action generation
4. autonomous environment lifecycle management by the LLM
5. pivoting the roadmap slice to end-to-end VLA control
6. replacing deterministic perception, planning, or execution loops with model-generated low-level action

## Next Roadmap Slice: LLM Route Planning and Model Evaluation

The bounded single-target supervisor is complete and UAT-ready. The next slice
promotes the LLM from reactive supervisor to route planner — giving it real
planning authority over multi-target sequencing — then evaluates whether a
lightweight model can replace the cloud provider.

### Step 1: LLM-Planned Multi-Target Route

Goal: the LLM decides which target to visit next based on visibility, proximity,
and progress — not a predetermined sequence.

This is the sim analogue of the end-state use case: a robot on a grass or turf
field retrieving scattered sports balls (e.g., soccer balls after practice). The
LLM plans which ball to collect next based on what it can see and where it is.
Sim proves the planning logic; the same decision shape transfers to outdoor
hardware with real perception.

Scenario:

- 3 balls spawned at known positions (same positions as `visit_three_ball_sequence`)
- the LLM sees the multi-target digest: which targets remain, which are visible, robot pose
- the LLM emits `visit_target(id)` to select the next target, then the existing search/acquire/plan/track policy handles execution
- success = all 3 targets visited; quality = total distance traveled, time to complete

What changes:

1. extend the frozen intent contract with `visit_target(target_id)` — a high-level planning intent that selects the next target
2. extend the state digest with multi-target awareness: remaining targets, visited targets, per-target visibility and estimated distance
3. add a route planning policy stage above the existing search/acquire/plan/track stages
4. add a `visit_route_planning` scenario to the dashboard
5. prove the LLM picks a reasonable visit order (e.g., nearest-visible-first) and completes all targets

Acceptance:

1. LLM-planned route completes all 3 targets
2. visit order is demonstrably non-random (nearest-visible or similar heuristic)
3. same frozen contract, same deterministic lower layers, same safety guarantees
4. proof passes 3+ consecutive times

Current status as of April 12, 2026:

1. fresh-session route planning is now green with object avoidance working against already-visited balls
2. validated fresh-session proofs:
   - `artifacts/session/20260412T021011Z/visit_mission/20260412T021044Z/mission_verdict.json`
   - `artifacts/session/20260412T022002Z/visit_mission/20260412T022019Z/mission_verdict.json`
3. the previous "drive through the visited center ball" failure mode improved from roughly `0.05 m` center clearance to roughly `0.26-0.27 m` on the `ball_b -> ball_a` transition
4. the remaining blocker before Step 1 can be treated as fully repeatable is same-session rerun stability: reusing the scenario without a fresh environment restart can reuse the previous mission anchor and respawn the route-planning targets around the wrong origin

### Step 2: Stabilize on Current Provider (GPT)

Goal: soak the route planning scenario on the current GPT model until it is
repeatable and the decision quality is measurable.

Work:

1. run 5+ consecutive route planning proofs on `container_kilted`
2. record decision traces for replay: state digest → LLM decision at each step
3. define quality metrics: total path length, visit order optimality, time to complete, number of wasted intents
4. establish a baseline scorecard for the GPT provider
5. eliminate the same-session mission-anchor reset bug so the 5-run soak is measuring route-planning quality, not scenario reset drift

Acceptance:

1. 5/5 consecutive green route planning runs
2. baseline scorecard with quality metrics for GPT

### Step 3: Model Evaluation for On-Robot Inference

Goal: determine whether a lightweight model can make comparable route planning
decisions on the Orin Nano GPU.

Work:

1. replay the recorded GPT decision traces through candidate providers using the existing `llm_provider_replay_compare.py` tool
2. candidate models: small open-weight models that fit Orin Nano 8GB (e.g., Phi-3-mini, Llama-3.2-3B, Qwen-2.5-3B)
3. compare: decision agreement rate, intent validity rate, visit order quality, inference latency
4. for the top candidate: run the live route planning scenario end-to-end with `LocalModelProvider`
5. if no candidate meets quality threshold, document the gap and keep cloud inference as the primary path

Acceptance:

1. replay comparison report for at least 3 candidate models
2. live end-to-end proof with the top candidate (or documented gap analysis)
3. decision on whether to proceed with local inference or stay on cloud for the hardware POC
