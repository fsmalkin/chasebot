# Fetch Planner Provider Rerun Readiness

- campaign_id: `provider_rerun_readiness_seed20260648_20260605`
- pass: `False`
- provider_rerun_ready: `False`
- provider_backed_authority_proven: `False`
- openai_api_key_present: `False`
- readiness_level: `provider_rerun_blocked`
- promotion_evidence: `False`
- interpretation: `provider_backed_planner_rerun_waiting_on_prerequisites`

## Current Fallback Evidence

- latest_fallback_seed pass=`True` issues=`[]` [artifact](/artifacts/session/live_planner_seeded_generalization_gate_seed20260648_breadth_100x3_20260605_planner/fetch_planner_handoff_gate/gate_summary.json)
- seed: `20260648`
- random_cases: `100`
- route_counts: `{'ambiguous_or_unsafe_no_go': 19, 'fetch_ready_local': 19, 'nav2_reposition_first': 21, 'recovery_or_reaim': 16, 'scan_or_perceive_first': 25}`
- provider_status_counts: `{'skipped_missing_openai_api_key': 100}`

## Dashboard Evidence

- dashboard pass=`True` issues=`[]` [artifact](/runtime/dashboard/fetch_plan_data.json)
- status_label: `Seed 20260648 green; provider rerun preflight is waiting on OPENAI_API_KEY`
- uat_sample_count: `15`

## Blockers

- `missing_openai_api_key`

## Rerun Commands

### planner_gate

```powershell
python scripts\fetch_planner_seeded_generalization_gate.py --campaign-id provider_planner_seed20260648_breadth_100x3_20260605 --seed 20260648 --random-cases 100 --planner-mode llm_supervised_guarded --quality-order roughest --max-per-route 3 --dashboard-url http://127.0.0.1:8883 --fresh-dashboard-session-per-run --allow-operator-view-degraded --stop-on-fail
```

### explicit_all_routes_replay

```powershell
python scripts\fetch_planner_route_replay_batch.py --campaign-id provider_planner_seed20260648_mixed_all_routes_3x_20260605 --gate-summary artifacts\session\provider_planner_seed20260648_breadth_100x3_20260605_planner\fetch_planner_handoff_gate\gate_summary.json --route fetch_ready_local --route nav2_reposition_first --route recovery_or_reaim --route scan_or_perceive_first --route ambiguous_or_unsafe_no_go --quality-order roughest --max-per-route 3 --dashboard-url http://127.0.0.1:8883 --fresh-dashboard-session-per-run --allow-operator-view-degraded --stop-on-fail
```

### analysis

```powershell
python scripts\fetch_planner_route_uat_analyzer.py --campaign-id provider_planner_seed20260648_mixed_all_routes_analysis_20260605 --planner-summary artifacts\session\provider_planner_seed20260648_breadth_100x3_20260605_planner\fetch_planner_handoff_gate\gate_summary.json --mission-summary <each batch row mission_summary_path> --visual-package-summary <each batch row visual_package_summary_path>
```
