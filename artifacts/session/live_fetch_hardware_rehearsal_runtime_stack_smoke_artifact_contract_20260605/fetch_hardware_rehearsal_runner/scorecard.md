# Fetch Hardware Rehearsal Runner

- campaign_id: `live_fetch_hardware_rehearsal_runtime_stack_smoke_artifact_contract_20260605`
- mode: `execute`
- pass: `True`
- hardware_proven: `False`
- promotion_evidence: `False`
- interpretation: `planner_routed_fetch_hardware_rehearsal_step_executed`
- next_action: `review_execution_artifacts`
- issues: `[]`
- plan_summary: [artifact](/artifacts/session/analysis_fetch_hardware_rehearsal_plan_20260605/fetch_hardware_rehearsal_plan/hardware_rehearsal_plan_summary.json)

## Step Preflights

- `runtime_stack_smoke` pass=`True` issues=`[]`
  - command: `powershell -ExecutionPolicy Bypass -File scripts/run_first_uat.ps1 -ExecutionLane container_kilted -Distro Ubuntu-24.04 -RuntimeTarget robot_fidelity_orin -InferenceBackend tensorrt_int8 -IncludeVisual true`
  - required_artifacts: `['session:readiness_report.json', 'session:visual/operator_status.json', 'readiness_path:artifacts.coordinate_summary', 'readiness_path:artifacts.milestone_1_evidence_dir:screenshots/d415_color.png', 'readiness_path:artifacts.milestone_1_evidence_dir:screenshots/yolo_debug.png']`

## Execution

- step_id: `runtime_stack_smoke`
- pass: `True`
- returncode: `0`
- timed_out: `False`
- session_dir: `D:\dev\chasecar\artifacts\session\20260605T054242Z`

## Execution Artifacts

- pass: `True`
- issues: `[]`
- session_dir: [artifact](/artifacts/session/20260605T054242Z)
- readiness_report: [artifact](/artifacts/session/20260605T054242Z/readiness_report.json)
- `session:readiness_report.json` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T054242Z/readiness_report.json)
- `session:visual/operator_status.json` pass=`True` issues=`[]` [artifact](/artifacts/session/20260605T054242Z/visual/operator_status.json)
- `readiness_path:artifacts.coordinate_summary` pass=`True` issues=`[]` [artifact](/artifacts/uat/20260605T054321Z/summary.json)
- `readiness_path:artifacts.milestone_1_evidence_dir:screenshots/d415_color.png` pass=`True` issues=`[]` [artifact](/artifacts/demos/milestone_1_20260605T054242Z/screenshots/d415_color.png)
- `readiness_path:artifacts.milestone_1_evidence_dir:screenshots/yolo_debug.png` pass=`True` issues=`[]` [artifact](/artifacts/demos/milestone_1_20260605T054242Z/screenshots/yolo_debug.png)
