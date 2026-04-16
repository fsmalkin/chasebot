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
| Ball-ground rolling friction (`short_turf`) | Short soccer-practice turf | Approximated and actively calibrating | Explicit ODE + torsional friction in `yolo_test_world_v6_clean_uat_short_turf.world`; current 5-foot retrieval-corral live gate is still failing, so this surface remains the active calibration target rather than a closed proof. |
| Ball-ground rolling friction (`short_grass`) | Short soccer-practice grass | Approximated and partly calibrated | Explicit ODE + torsional friction in `yolo_test_world_v6_clean_uat_short_grass.world`; useful as a secondary comparison surface, but not the current operator gate. |
| Ball-catcher contact response | Front U-catcher controlling a rolling ball | Approximated and actively calibrating | Explicit contact tuning in `frisbee_target_ball.sdf`; latest work is focused on release-to-settle behavior inside the 5-foot retrieval corral rather than spur-perfect retention. |
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
- Canonical corral-placement surface is now `short_turf` (`yolo_test_world_v6_clean_uat_short_turf.world`).
- Fresh protected regression evidence after the latest corral/contact tuning:
  - `artifacts/session/20260416T023747Z/visit_mission_repeatability/campaign_run_summary.json`
- Historical surface-calibration passes under the earlier tighter settle bar:
  - `artifacts/session/20260413T135949Z/gather_mission_repeatability/campaign_run_summary.json`
  - `artifacts/session/20260413T140714Z/gather_mission_repeatability/campaign_run_summary.json`
- Current 5-foot retrieval-corral checkpoint is still open:
  - `artifacts/session/20260416T023444Z/gather_mission_repeatability/campaign_run_summary.json`
  - `artifacts/session/20260416T023035Z/gather_mission_repeatability/campaign_run_summary.json`
