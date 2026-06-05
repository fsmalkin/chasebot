# Fetch Hardware Rehearsal Runner

- campaign_id: `live_hardware_rehearsal_seed20260648_mixed_all_routes_20260605`
- mode: `execute`
- pass: `True`
- hardware_proven: `False`
- promotion_evidence: `False`
- interpretation: `planner_routed_fetch_hardware_rehearsal_step_executed`
- next_action: `review_execution_artifacts`
- issues: `[]`
- plan_summary: [artifact](/artifacts/session/analysis_fetch_hardware_rehearsal_plan_seed20260648_20260605/fetch_hardware_rehearsal_plan/hardware_rehearsal_plan_summary.json)

## Step Preflights

- `seed20260648_mixed_all_routes_rehearsal` pass=`True` issues=`[]`
  - command: `python scripts/fetch_planner_route_replay_batch.py --campaign-id hardware_rehearsal_seed20260648_mixed_all_routes_20260605 --gate-summary artifacts/session/live_planner_seeded_generalization_gate_seed20260648_breadth_100x3_20260605_planner/fetch_planner_handoff_gate/gate_summary.json --route fetch_ready_local --route nav2_reposition_first --route recovery_or_reaim --route scan_or_perceive_first --route ambiguous_or_unsafe_no_go --quality-order roughest --max-per-route 3 --dashboard-url http://127.0.0.1:8883 --fresh-dashboard-session-per-run --allow-operator-view-degraded --stop-on-fail`
  - required_artifacts: `['fetch_planner_handoff_gate/gate_summary.json', 'fetch_planner_route_replay_batch/batch_summary.json', 'fetch_planner_route_uat_analyzer/route_uat_summary.json', 'visual/raw_camera_browser.mp4', 'visual/topdown_telemetry_browser.mp4', 'visual/keyframe_review_contact_sheet.png']`

## Execution

- step_id: `seed20260648_mixed_all_routes_rehearsal`
- pass: `True`
- returncode: `0`
- timed_out: `False`
- session_dir: ``
- batch_summary_path: `D:\dev\chasecar\artifacts\session\hardware_rehearsal_seed20260648_mixed_all_routes_20260605\fetch_planner_route_replay_batch\batch_summary.json`
- seeded_gate_summary_path: ``

## Execution Artifacts

- pass: `True`
- issues: `[]`
- session_dir: ` `
- readiness_report: ` `
- seeded_gate_summary: ` `
- batch_summary: [artifact](/artifacts/session/hardware_rehearsal_seed20260648_mixed_all_routes_20260605/fetch_planner_route_replay_batch/batch_summary.json)
- `batch_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260648_mixed_all_routes_20260605/fetch_planner_route_replay_batch/batch_summary.json)
- `seed20260648_scene01_ambiguous_or_unsafe_no_go:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T195229932524Z/golf_ball_circle_delivery/20260605T195255557096Z/mission_verdict.json)
- `seed20260648_scene01_ambiguous_or_unsafe_no_go:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260648_mixed_all_routes_20260605_seed20260648_scene01_ambiguous_or_unsafe_no_go/fetch_visual_uat_package/package_summary.json)
- `seed20260648_scene02_ambiguous_or_unsafe_no_go:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T195335910854Z/golf_ball_circle_delivery/20260605T195401760132Z/mission_verdict.json)
- `seed20260648_scene02_ambiguous_or_unsafe_no_go:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260648_mixed_all_routes_20260605_seed20260648_scene02_ambiguous_or_unsafe_no_go/fetch_visual_uat_package/package_summary.json)
- `seed20260648_scene08_scan_or_perceive_first:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T195442437457Z/golf_ball_circle_delivery/20260605T195514628950Z/mission_verdict.json)
- `seed20260648_scene08_scan_or_perceive_first:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260648_mixed_all_routes_20260605_seed20260648_scene08_scan_or_perceive_first/fetch_visual_uat_package/package_summary.json)
- `seed20260648_scene100_scan_or_perceive_first:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T195601494948Z/golf_ball_circle_delivery/20260605T195627306371Z/mission_verdict.json)
- `seed20260648_scene100_scan_or_perceive_first:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260648_mixed_all_routes_20260605_seed20260648_scene100_scan_or_perceive_first/fetch_visual_uat_package/package_summary.json)
- `seed20260648_scene11_scan_or_perceive_first:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T195715549838Z/golf_ball_circle_delivery/20260605T195743155810Z/mission_verdict.json)
- `seed20260648_scene11_scan_or_perceive_first:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260648_mixed_all_routes_20260605_seed20260648_scene11_scan_or_perceive_first/fetch_visual_uat_package/package_summary.json)
- `seed20260648_scene12_ambiguous_or_unsafe_no_go:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T195825011688Z/golf_ball_circle_delivery/20260605T195857747603Z/mission_verdict.json)
- `seed20260648_scene12_ambiguous_or_unsafe_no_go:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260648_mixed_all_routes_20260605_seed20260648_scene12_ambiguous_or_unsafe_no_go/fetch_visual_uat_package/package_summary.json)
- `seed20260648_scene87_recovery_or_reaim:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T195939864983Z/golf_ball_circle_delivery/20260605T200012067446Z/mission_verdict.json)
- `seed20260648_scene87_recovery_or_reaim:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260648_mixed_all_routes_20260605_seed20260648_scene87_recovery_or_reaim/fetch_visual_uat_package/package_summary.json)
- `seed20260648_scene51_recovery_or_reaim:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T200211722524Z/golf_ball_circle_delivery/20260605T200250350812Z/mission_verdict.json)
- `seed20260648_scene51_recovery_or_reaim:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260648_mixed_all_routes_20260605_seed20260648_scene51_recovery_or_reaim/fetch_visual_uat_package/package_summary.json)
- `seed20260648_scene23_recovery_or_reaim:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T200448596339Z/golf_ball_circle_delivery/20260605T200520324136Z/mission_verdict.json)
- `seed20260648_scene23_recovery_or_reaim:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260648_mixed_all_routes_20260605_seed20260648_scene23_recovery_or_reaim/fetch_visual_uat_package/package_summary.json)
- `seed20260648_scene79_nav2_reposition_first:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T200634381925Z/golf_ball_circle_delivery/20260605T200700368761Z/mission_verdict.json)
- `seed20260648_scene79_nav2_reposition_first:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260648_mixed_all_routes_20260605_seed20260648_scene79_nav2_reposition_first/fetch_visual_uat_package/package_summary.json)
- `seed20260648_scene36_nav2_reposition_first:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T200840990591Z/golf_ball_circle_delivery/20260605T200907062504Z/mission_verdict.json)
- `seed20260648_scene36_nav2_reposition_first:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260648_mixed_all_routes_20260605_seed20260648_scene36_nav2_reposition_first/fetch_visual_uat_package/package_summary.json)
- `seed20260648_scene54_nav2_reposition_first:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T201102280260Z/golf_ball_circle_delivery/20260605T201140626920Z/mission_verdict.json)
- `seed20260648_scene54_nav2_reposition_first:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260648_mixed_all_routes_20260605_seed20260648_scene54_nav2_reposition_first/fetch_visual_uat_package/package_summary.json)
- `seed20260648_scene42_fetch_ready_local:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T201311556325Z/golf_ball_circle_delivery/20260605T201337323401Z/mission_verdict.json)
- `seed20260648_scene42_fetch_ready_local:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260648_mixed_all_routes_20260605_seed20260648_scene42_fetch_ready_local/fetch_visual_uat_package/package_summary.json)
- `seed20260648_scene86_fetch_ready_local:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T201505275081Z/golf_ball_circle_delivery/20260605T201530717782Z/mission_verdict.json)
- `seed20260648_scene86_fetch_ready_local:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260648_mixed_all_routes_20260605_seed20260648_scene86_fetch_ready_local/fetch_visual_uat_package/package_summary.json)
- `seed20260648_scene10_fetch_ready_local:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T201626735139Z/golf_ball_circle_delivery/20260605T201652430029Z/mission_verdict.json)
- `seed20260648_scene10_fetch_ready_local:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260648_mixed_all_routes_20260605_seed20260648_scene10_fetch_ready_local/fetch_visual_uat_package/package_summary.json)
