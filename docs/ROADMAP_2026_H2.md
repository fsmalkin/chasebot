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

1. headless LLM proof over the frozen intent contract
2. repeatability gate on the authoritative `container_kilted` lane
3. simple browser UAT demo for the same proof path
4. bounded supervisor reuse across the visible-ball M3 scenario family
5. target prior contract for multi-target scenarios — **complete**
   - executor receives expected target position from the mission layer, not from sim ground truth ✓
   - prior-based lock gating implemented and tested ✓
   - prior-based track approach closes depth-estimation gap ✓
   - visit runtime path plumbed through compose env → launch → executor ✓
   - `visit_single_ball_proof` passing (0.33m visit distance, within 0.35m tolerance) ✓
   - `visit_three_ball_sequence` passing: 3/3 balls visited on attempt 0 (0.34m, 0.33m, 0.34m) ✓
   - sim truth probe is a validation oracle (test-time only), not an executor runtime dependency ✓
   - this makes the executor's target discrimination portable to hardware, where no sim oracle exists
6. provider benchmarking for a future on-machine model path on Orin Nano
   - benchmark only providers that can map cleanly to the frozen bounded intent contract while preserving deterministic lower layers
   - optional research lane: evaluate alternate embodied-reasoning providers, including Gemini Robotics-ER-class models, only as supervisory reasoning providers
   - this benchmarking is not a prerequisite for the current promotion ladder

Status update as of April 3, 2026:

1. Target prior contract is complete:
   - executor prior-based lock gating and prior-based track approach are implemented
   - visit runtime path plumbed end-to-end: dashboard env → compose → launch file → executor CLI
   - `visit_single_ball_proof` scenario passes with 0.33m visit distance
   - `visit_three_ball_sequence` passes: 3/3 balls visited on attempt 0 (session `20260403T130519Z`)
   - bugs found and fixed during live testing:
     - port 8860 conflict in host_powershell compose startup
     - 409 intent ownership guard for search/acquire transitions
     - approach_timeout: depth estimation error caused detection-based goals to fall short; prior-based track approach closes the gap
     - mission runner's sim-truth lock rejection bypassed in visit missions — executor's prior gate is authoritative for target discrimination

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
