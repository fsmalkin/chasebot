# Architecture vs State of the Art — Review and Recommendations (June 9, 2026)

Requested by Fred: step back, re-inspect the fundamental architecture choices,
survey the 2024–2026 state of the art, and recommend. Method: (1) internal
grounding pass over the repo's decision docs (what was chosen, why, what was
already rejected and on what evidence); (2) adversarially verified external
research (multi-agent web sweep; every claim below survived 3-vote
verification against primary sources unless noted). Hardware filter applied
throughout: Jetson Orin Nano 8 GB shared CPU/GPU, 25 W, TensorRT INT8, single
D415 RGB-D, diff-drive 0.6 m/s / 2.5 rad/s.

## Verdict

**Keep the layered deterministic architecture.** No 2024–2026 learned or
foundation-model alternative is production-ready as a replacement for this
task class (reliability-gated, push-based retrieval on embedded compute). The
external evidence actively confirms the two load-bearing choices: deterministic
guarded contact control, and LLM planning constrained to frozen contracts.
The recommendations below are bounded complements, not replacements, in
priority order.

## Findings by area (verified)

### 1. VLA / robot foundation models — infeasible on our hardware, no-go now

- GR00T N1.7 requires a 16 GB+ VRAM GPU; the official TensorRT export offers
  only bf16/fp16/fp32 (no INT8 path; repo-wide grep confirms); even on AGX
  Orin (~4–7x an Orin Nano) only the diffusion head TRT-accelerates, at
  216.5 ms/action chunk (~4.6 Hz). Sources: NVIDIA Isaac-GR00T repo +
  deployment README (primary, code-inspected).
- OpenVLA 7B with 4-bit quantization: 374.7 ms/step (~2.7 Hz), 4.0 GB weights,
  measured on AGX Orin 64GB (arXiv 2505.15304 Table 9, corroborated by
  2412.01034). On 8 GB shared RAM that footprint barely fits before
  perception.
- Sub-billion edge VLAs (LiteVLA-Edge, SmolVLM-256M, ~6.6 Hz on AGX Orin)
  publish latency only — zero task-success evidence (arXiv 2603.03380,
  unreviewed preprint).
- Quantization is not free: naive INT4 PTQ dropped real-robot success 79%→67%;
  recovery requires quantization-aware retraining (SQIL, ICCV 2025). Any
  future learned policy on our INT8 path needs a QAT loop, not a conversion.

Judgment: confirms the repo's standing no-go on end-to-end VLA control. Shelf
life ~6–12 months (JetPack/TRT releases and the fast-moving edge-VLA lineage
could shift the arithmetic); keep the existing "revisit when" marker.

### 2. Learned push policies — below the UAT bar; direction is real

- Strongest reliability evidence: constrained-RL pushing on ANYmal at
  80–92.9% per-object real success — but with external motion capture for all
  6D poses, onboard perception explicitly deferred (ICRA 2025,
  arXiv 2502.01546).
- Best world-model push result: PIN-WM (RSS 2025) 97% sim / 75% real over 20
  trials. (A sibling claim about its margin over baselines was REFUTED in
  verification — treat only the headline as solid.)
- Diffusion-policy cotraining (MIT/Tedrake, IROS 2025; 1000+ real trials,
  50,000+ sim trials on canonical planar pushing): sim cotraining improves
  real performance 2–7x, and **reducing physical domain gaps
  (friction/contact) matters more than visual fidelity** for contact-rich
  sim-to-real (arXiv 2503.22634).

Judgment: 65–92% real-world success is below what our gates demand of the
deterministic primitive, and every credible deployment leans on pose
infrastructure we don't have. Keep learned policies shadow-only behind the
existing ladder. The cotraining physics finding is actionable today — see
recommendation R2.

### 3. Contact-implicit MPC — the credible eventual upgrade, research-grade today

- C3+ / "Push Anything" (UPenn DAIR, ICRA 2026): 98% pooled success across 33
  objects over 928 real trials at ≤2 cm / ≤0.1 rad tolerance — the first
  learned-adjacent result in UAT-gate reliability territory. As deployed:
  three desktop machines (32-thread i9 for the controller alone, RTX 4090 for
  perception), 8.6–15.2 Hz, fixed-base arm (arXiv 2510.19974).
- IDTO (Toyota, T-RO 2024): contact-implicit MPC at >100 Hz for a 20-DoF task
  on 4 CPU threads, complexity cubic in DoFs — a ~3-DoF planar ball-push
  plausibly fits Orin Nano's 6-core CPU. Acknowledged limitations:
  force-at-a-distance artifacts, ad-hoc contact tuning, zero embedded
  deployments anywhere (arXiv 2309.01813).

Judgment: this matches the repo's own #1 "external SOTA could flip" candidate
(receding-horizon contact MPC, deferred on priority, never spiked — and its
documented trigger, "a reproducible stage gap", arguably fired with seed
20260607). Still research-grade; nobody has run it embedded. See R3.

### 4. Nav2 ecosystem — the docking server pattern is directly relevant (partial coverage)

Verified against primary sources (docs.nav2.org, ROSCon 2024):

- opennav_docking is explicitly designed for non-charging docking targets via
  plugin docks; its core is a 50 Hz vision-control loop that continuously
  re-detects and filters the target pose during approach (graceful-controller
  law, detection smoothing, staleness timeout, staging-pose offsets, retry
  budget) — i.e., **object-relative servoing, not map-frame goal seeking**.
- Configured (not field-measured) default tolerances: 0.05 m position,
  0.05 rad (~2.9°) yaw.
- `rotate_to_dock` implements approach-facing-forward → detect → rotate →
  dead-reckon final motion — directly applicable to a ball-relative setup
  where the camera loses the ball during the final yaw-align.

Judgment: a strong candidate **execution substrate for the v1.1 slice-2 named
route owner** (or hardening for slice 1's staging gate). This does NOT
reverse the standing no-go on Nav2 ball-relative legs: that rule targets the
NavigateToPose/FollowPath replanning BT whose executed path is unconstrained
near an uncostmapped ball; the docking loop is a different mechanism
(continuous target-relative servoing). Any adoption still enters behind the
existing measured gates and the 0.020 m ball-motion guard. Coverage caveat:
MPPI-vs-other-controller precision claims and release-by-release Nav2 history
did not survive verification (session limits), so the docking pattern is the
only Nav2 finding this review endorses.

### 5. LLM/VLM planners in production — area remains open

Two research passes produced no surviving verified claims on what authority
production deployments give LLM planners versus frozen vocabularies. Absence
of evidence here is a pipeline artifact, not evidence of absence. Default
stands: keep the frozen 7-intent contract and fail-closed conversion;
nothing found argues for more LLM authority.

### 6. Sim pipeline — highest-leverage near-term investment

- Isaac Lab: 0.9–1.6M FPS GPU-parallel training throughput and first-class
  domain randomization (verified in code) — orders of magnitude beyond
  Gazebo for *policy training*; not a replacement for the Gazebo gate, which
  remains the right UAT/evidence authority (real-time factor 1.0, watchable
  video, seeded scenes).
- Combined with the IROS 2025 physics-gap finding (area 2), the message for
  our pipeline is concrete: **ball–pusher contact and rolling-friction
  calibration is worth more than any visual-fidelity work** — and the
  SIM_FIDELITY_MATRIX already lists rolling friction as approximated and
  uncalibrated with no locked canonical_surface_profile.

## Recommendations

- **R1 — Keep the stack; close v1.** No architecture change. The breadth lane
  to the approved promotion bar, then v1.1 slice 1 per
  `docs/OPEN_FIELD_SETUP_TRAJECTORY_OWNER_DESIGN.md`, remains the plan of
  record.
- **R2 — Name sim physics calibration as the next sim investment (post-v1).**
  Calibrate ball–pusher contact and rolling friction against measured passive
  rolls; lock a canonical_surface_profile. Direct evidence says this buys more
  transfer than visuals. Cheap, fully inside current architecture.
- **R3 — Contact-MPC paper spike (design-note only, post-v1).** The repo's own
  trigger has arguably fired. First gate per the existing plan: fast screen on
  the zero layout, then the canonical one-run matrix — desk-feasibility of an
  IDTO-class ~3-DoF planar formulation on Orin-class CPU, behind shadow
  scoring. No live authority. Proposal to Fred before any implementation.
- **R4 — Evaluate opennav_docking as slice-2 substrate (design-note only).**
  When v1.1 slice 2 (named route owner) comes up, spike the docking server's
  pose-refinement pattern against the orbit-arc executor on the frozen
  layouts, behind the same measured gates and ball-motion guard. If it wins,
  we inherit a maintained upstream component instead of bespoke executor code.
- **R5 — Hardware-in-the-loop entry right after v1 promotion.** Unchanged from
  the roadmap decision: qualify the one-ball `fetch_to_pose` primitive on the
  Orin with onboard TensorRT INT8 and the physical camera before any v1.1
  capability work meets hardware. Every learned/MPC option above presumes
  pose sources we have not proven on hardware; this is the single biggest
  unvalidated bet in the whole architecture.
- **R6 — Re-run the VLA feasibility check in ~2 quarters.** The "infeasible on
  Orin Nano" judgments are time-stamped (TRT 10.3 / JetPack 6.x era). Calendar
  marker, not a workstream.

## Sources (surviving verified claims)

NVIDIA Isaac-GR00T repo + deployment README; arXiv 2505.15304 (SQIL, ICCV
2025) + 2412.01034; arXiv 2603.03380 (LiteVLA-Edge, preprint); arXiv
2503.22634 (IROS 2025 cotraining) + sim-and-real-cotraining.github.io; arXiv
2502.01546 (ICRA 2025 ANYmal pushing); arXiv 2504.16693 (PIN-WM, RSS 2025);
arXiv 2510.19974 (C3+/Push Anything, ICRA 2026); arXiv 2309.01813 (IDTO,
T-RO 2024); arXiv 2605.30778 (object-informed MPPI, preprint); arXiv
2511.04831 + Isaac Lab docs/code; docs.nav2.org docking-server configuration;
ROSCon 2024 "On Use of Nav2 Docking".

One claim refuted in verification (PIN-WM baseline-margin comparison) is
excluded above. Unverified areas are labeled as open, not silently filled.
