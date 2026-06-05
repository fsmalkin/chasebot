# Fetch Hardware Rehearsal Runner

- campaign_id: `robot_side_fetch_rehearsal_saved_anchors_seed20260643_20260605`
- mode: `execute`
- pass: `True`
- hardware_proven: `False`
- promotion_evidence: `False`
- interpretation: `planner_routed_fetch_hardware_rehearsal_step_executed`
- next_action: `review_execution_artifacts`
- issues: `[]`
- plan_summary: [artifact](/artifacts/session/analysis_fetch_hardware_rehearsal_plan_seed20260643_20260605/fetch_hardware_rehearsal_plan/hardware_rehearsal_plan_summary.json)

## Step Preflights

- `saved_anchor_one_run_fetch_rehearsal` pass=`True` issues=`[]`
  - command: `python scripts/fetch_planner_route_replay_batch.py --campaign-id hardware_rehearsal_saved_anchors_20260605 --gate-summary artifacts/session/dev_planner_saved_anchor_handoff_gate_zero_numeric_fix_20260604/fetch_planner_handoff_gate/gate_summary.json --max-per-route 3 --dashboard-url http://127.0.0.1:8883 --fresh-dashboard-session-per-run --allow-operator-view-degraded --stop-on-fail`
  - required_artifacts: `['control_preflight.json', 'mission_verdict.json', 'visual/raw_camera_browser.mp4', 'visual/topdown_telemetry_browser.mp4', 'visual/world_stream.mp4', 'visual/keyframe_review_contact_sheet.png']`

## Execution

- step_id: `saved_anchor_one_run_fetch_rehearsal`
- pass: `True`
- returncode: `0`
- timed_out: `False`
- session_dir: ``
- batch_summary_path: `D:\dev\chasecar\artifacts\session\hardware_rehearsal_saved_anchors_20260605\fetch_planner_route_replay_batch\batch_summary.json`
- seeded_gate_summary_path: ``

## Execution Artifacts

- pass: `True`
- issues: `[]`
- session_dir: ` `
- readiness_report: ` `
- seeded_gate_summary: ` `
- batch_summary: [artifact](/artifacts/session/hardware_rehearsal_saved_anchors_20260605/fetch_planner_route_replay_batch/batch_summary.json)
- `batch_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_saved_anchors_20260605/fetch_planner_route_replay_batch/batch_summary.json)
- `saved_anchor_left05:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T133832843100Z/golf_ball_circle_delivery/20260605T134202920806Z/mission_verdict.json)
- `saved_anchor_left05:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_saved_anchors_20260605_saved_anchor_left05/fetch_visual_uat_package/package_summary.json)
- `saved_anchor_right05:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T134446173266Z/golf_ball_circle_delivery/20260605T134529579483Z/mission_verdict.json)
- `saved_anchor_right05:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_saved_anchors_20260605_saved_anchor_right05/fetch_visual_uat_package/package_summary.json)
- `saved_anchor_zero:mission_summary` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T134708780783Z/golf_ball_circle_delivery/20260605T134816172036Z/mission_verdict.json)
- `saved_anchor_zero:visual_package` pass=`True` issues=`[]` [artifact](/artifacts/session/hardware_rehearsal_saved_anchors_20260605_saved_anchor_zero/fetch_visual_uat_package/package_summary.json)
