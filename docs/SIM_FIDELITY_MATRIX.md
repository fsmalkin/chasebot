# Simulation Fidelity Matrix

## Goal
Track which physical constraints are simulated exactly, approximated, or not simulated.

## Matrix
| Constraint | Physical Target | Simulation Status | Notes |
|---|---|---|---|
| Wheel separation | 0.16 m | Simulated exactly | In controller config and SDF geometry. |
| Wheel radius | 0.032 m | Simulated exactly | In controller config and wheel geometry. |
| Max linear velocity | 0.5 m/s | Simulated exactly | Enforced in diff drive controller limits. |
| Max angular velocity | 2.0 rad/s | Simulated exactly | Enforced in diff drive controller limits. |
| Controller rate | 100 Hz | Simulated exactly | `controller_manager` update rate. |
| D415 RGB stream | 640x480 @ 30 Hz | Simulated exactly | v1.6.0 SDF camera sensor config. |
| D415 depth stream | 640x480 @ 30 Hz | Simulated exactly | v1.6.0 SDF depth sensor config. |
| D415 depth range | 0.165-10.0 m | Simulated exactly | Depth clip near/far in SDF. |
| Ball-ground rolling friction (`short_turf`) | Short soccer-practice turf | Approximated and intended default, calibration still open | Explicit ODE + torsional friction in `yolo_test_world_v6_clean_uat_short_turf.world`; this remains the intended operator-default comparison surface, but the new surface-calibration harness has not yet locked it as the canonical calibrated lane. |
| Ball-ground rolling friction (`short_grass`) | Short soccer-practice grass | Approximated and active fallback candidate | Explicit ODE + torsional friction in `yolo_test_world_v6_clean_uat_short_grass.world`; the comparison harness keeps this as the stronger-stop fallback candidate while the canonical lane decision remains open. |
| Ball-catcher contact response | Front U-catcher controlling a rolling ball | Approximated and baseline-stable | Explicit contact tuning in `frisbee_target_ball.sdf`; the committed shorter spur geometry is the current baseline, and the next work is surface/ball realism rather than reopening spur geometry. |
| Orin Nano compute envelope | 8GB + Ampere GPU | Approximated | Emulated via `robot_fidelity_orin` runtime profile and conservative defaults. |
| Real-world lighting noise | Dynamic outdoor lighting | Not simulated | UAT thresholds account for sim-only bias. |
| Sensor calibration drift | Hardware aging/misalignment | Not simulated | Requires hardware calibration test plan. |

## Runtime Policy
1. `robot_fidelity_orin`: enforce physical limits and conservative compute behavior.
2. `workstation_balanced`: optimized for iteration speed.
3. `workstation_max`: optimized for throughput and GPU-only operation.
4. `jetty_gate` lane is authoritative for pass/fail promotion.
5. `isaac_fidelity` lane is used for cross-lane reproducibility and perception confidence expansion.

## Validation
- Coordinate UAT and navigation UAT reports are authoritative only when run in `robot_fidelity_orin` on `jetty_gate`.
- Active operator-default corral surface remains `short_turf` (`yolo_test_world_v6_clean_uat_short_turf.world`), but the canonical calibrated lane is still unresolved.
- Fresh protected regression evidence after the latest corral/contact tuning:
  - `artifacts/session/20260416T023747Z/visit_mission_repeatability/campaign_run_summary.json`
- Operator review on April 16, 2026 accepted the current one-ball 5-foot retrieval behavior as good enough to keep moving, while still treating exact surface fidelity as open.
- The three-lane calibration harness now exists:
  - `artifacts/session/pre_tune_surface_calibration/corral_surface_calibration/campaign_summary.json`
  - `artifacts/session/halfstep_probe_surface_calibration/corral_surface_calibration/campaign_summary.json`
- Current calibration truth:
  - the harness compares `baseline`, `short_turf`, and `short_grass`
  - no current comparison run has produced a locked `canonical_surface_profile`
  - `short_grass` remains the strongest fallback candidate from the comparison runs, but it is not promoted yet
- Current roadmap policy:
  - unresolved exact surface fidelity is a known realism gap, not the blocking milestone
  - the team is moving forward with multi-ball gather under the same 5-foot diameter practical retrieval bar
  - `short_turf` remains the active operator-default lane until later evidence justifies a change
- Current multi-ball engineering truth:
  - `gather_three_ball_zone` is now exposed in the dashboard as a secondary scenario on `short_turf`
  - final multi-ball scoring now records `final_corral_audit`, `final_all_targets_inside_retrieval_corral`, `final_all_targets_stopped`, `final_three_ball_corral_pass`, and `retrieved_count`
  - the first fresh three-ball sanity run emitted those fields at `artifacts/session/20260416T184739Z/gather_mission_repeatability/campaign_run_summary.json`
  - that run still failed on the same release/settle behavior that also showed up in the fresh one-ball rerun at `artifacts/session/20260416T184447Z/gather_mission_repeatability/campaign_run_summary.json`
- Historical surface-calibration passes under the earlier tighter settle bar:
  - `artifacts/session/20260413T135949Z/gather_mission_repeatability/campaign_run_summary.json`
  - `artifacts/session/20260413T140714Z/gather_mission_repeatability/campaign_run_summary.json`
- Current strict sim-only 5-foot retrieval evidence remains mixed:
  - `artifacts/session/20260416T023444Z/gather_mission_repeatability/campaign_run_summary.json`
  - `artifacts/session/20260416T023035Z/gather_mission_repeatability/campaign_run_summary.json`
- Current engineering inference: real soccer balls on grass or turf likely have more rolling resistance than the simulated red target ball, so the present lane may be pessimistic. Treat that as an inference to calibrate, not a verified hardware claim.
