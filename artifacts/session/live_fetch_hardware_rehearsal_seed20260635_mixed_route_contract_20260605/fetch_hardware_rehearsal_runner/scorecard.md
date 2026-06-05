# Fetch Hardware Rehearsal Runner

- campaign_id: `live_fetch_hardware_rehearsal_seed20260635_mixed_route_contract_20260605`
- mode: `execute`
- pass: `True`
- hardware_proven: `False`
- promotion_evidence: `False`
- interpretation: `planner_routed_fetch_hardware_rehearsal_step_executed`
- next_action: `review_execution_artifacts`
- issues: `[]`
- plan_summary: [artifact](/artifacts/session/analysis_fetch_hardware_rehearsal_plan_20260605/fetch_hardware_rehearsal_plan/hardware_rehearsal_plan_summary.json)

## Step Preflights

- `seed20260635_mixed_route_fetch_rehearsal` pass=`True` issues=`[]`
  - command: `python scripts/fetch_planner_seeded_generalization_gate.py --campaign-id hardware_rehearsal_seed20260635_20260605 --seed 20260635 --random-cases 30 --planner-mode llm_supervised_guarded --max-per-route 2 --dashboard-url http://127.0.0.1:8883 --fresh-dashboard-session-per-run --allow-operator-view-degraded --stop-on-fail`
  - required_artifacts: `['fetch_planner_handoff_gate/gate_summary.json', 'fetch_planner_route_replay_batch/batch_summary.json', 'fetch_planner_route_uat_analyzer/route_uat_summary.json', 'visual/raw_camera_browser.mp4', 'visual/topdown_telemetry_browser.mp4', 'visual/keyframe_review_contact_sheet.png']`

## Execution

- step_id: `seed20260635_mixed_route_fetch_rehearsal`
- pass: `True`
- returncode: `0`
- timed_out: `False`
- session_dir: ``
- batch_summary_path: ``
- seeded_gate_summary_path: `D:\dev\chasecar\artifacts\session\hardware_rehearsal_seed20260635_20260605\fetch_planner_seeded_generalization_gate\gate_summary.json`

## Execution Artifacts

- pass: `True`
- issues: `[]`
- session_dir:
- readiness_report:
- seeded_gate_summary: [artifact](/artifacts/session/hardware_rehearsal_seed20260635_20260605/fetch_planner_seeded_generalization_gate/gate_summary.json)
- batch_summary: [artifact](/artifacts/session/hardware_rehearsal_seed20260635_20260605_replay/fetch_planner_route_replay_batch/batch_summary.json)
- `seeded_gate_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260635_20260605/fetch_planner_seeded_generalization_gate/gate_summary.json)
- `planner_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260635_20260605_planner/fetch_planner_handoff_gate/gate_summary.json)
- `replay_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260635_20260605_replay/fetch_planner_route_replay_batch/batch_summary.json)
- `analyzer_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260635_20260605_analysis/fetch_planner_route_uat_analyzer/route_uat_summary.json)
- `seeded_gate_replay_batch_validation` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260635_20260605_replay/fetch_planner_route_replay_batch/batch_summary.json)
- `batch_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260635_20260605_replay/fetch_planner_route_replay_batch/batch_summary.json)
- `seed20260635_scene02_nav2_reposition_first:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T062655532643Z/golf_ball_circle_delivery/20260605T062733105356Z/mission_verdict.json)
- `seed20260635_scene02_nav2_reposition_first:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260635_20260605_replay_seed20260635_scene02_nav2_reposition_first/fetch_visual_uat_package/package_summary.json)
- `seed20260635_scene03_recovery_or_reaim:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T062848905204Z/golf_ball_circle_delivery/20260605T062920127412Z/mission_verdict.json)
- `seed20260635_scene03_recovery_or_reaim:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260635_20260605_replay_seed20260635_scene03_recovery_or_reaim/fetch_visual_uat_package/package_summary.json)
- `seed20260635_scene05_nav2_reposition_first:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T063036140143Z/golf_ball_circle_delivery/20260605T063108236202Z/mission_verdict.json)
- `seed20260635_scene05_nav2_reposition_first:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260635_20260605_replay_seed20260635_scene05_nav2_reposition_first/fetch_visual_uat_package/package_summary.json)
- `seed20260635_scene07_fetch_ready_local:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T063225158607Z/golf_ball_circle_delivery/20260605T063257224629Z/mission_verdict.json)
- `seed20260635_scene07_fetch_ready_local:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260635_20260605_replay_seed20260635_scene07_fetch_ready_local/fetch_visual_uat_package/package_summary.json)
- `seed20260635_scene08_fetch_ready_local:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T063400908945Z/golf_ball_circle_delivery/20260605T063432723094Z/mission_verdict.json)
- `seed20260635_scene08_fetch_ready_local:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260635_20260605_replay_seed20260635_scene08_fetch_ready_local/fetch_visual_uat_package/package_summary.json)
- `seed20260635_scene09_recovery_or_reaim:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T063530711030Z/golf_ball_circle_delivery/20260605T063608675589Z/mission_verdict.json)
- `seed20260635_scene09_recovery_or_reaim:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_seed20260635_20260605_replay_seed20260635_scene09_recovery_or_reaim/fetch_visual_uat_package/package_summary.json)
