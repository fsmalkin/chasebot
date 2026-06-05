# Fetch Planner Seeded Generalization Gate

- campaign_id: `live_planner_seeded_generalization_gate_seed20260641_rough_breadth_timeout_capture_20260605`
- dry_run: `False`
- seed: `20260641`
- random_cases: `30`
- max_per_route: `3`
- expected_executable_count: `9`
- pass: `False`
- promotion_evidence: `False`
- planner_authority_ready: `False`
- interpretation: `planner_routed_seeded_generalization_incomplete`

## Child Evidence

- planner_gate pass=`True` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260641_rough_breadth_timeout_capture_20260605_planner/fetch_planner_handoff_gate/scorecard.md)
- replay_batch pass=`False` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260641_rough_breadth_timeout_capture_20260605_replay/fetch_planner_route_replay_batch/scorecard.md)
- route_analyzer pass=`False` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260641_rough_breadth_timeout_capture_20260605_analysis/fetch_planner_route_uat_analyzer/scorecard.md)

## Summary

- planner: `{'pass_count': 30, 'fail_count': 0, 'wrong_fetch_dispatch_count': 0, 'route_counts': {'fetch_ready_local': 3, 'nav2_reposition_first': 6, 'scan_or_perceive_first': 9, 'recovery_or_reaim': 10, 'ambiguous_or_unsafe_no_go': 2}, 'provider_status_counts': {'skipped_missing_openai_api_key': 30}, 'planner_mode_effective_counts': {'deterministic_fallback': 30}, 'llm_shadow_ready': False, 'llm_shadow_provider_ok_count': 0, 'llm_supervised_ready': False, 'llm_supervised_accept_count': 0, 'llm_supervised_veto_count': 30, 'llm_supervised_veto_reason_counts': {'provider_not_ok': 30, 'missing_llm_route': 30, 'confidence_below_threshold': 30}, 'strict_planner_authority_ready': False, 'guarded_fallback_authority_ready': False}`
- replay: `{'selected_count': 1, 'mission_pass_count': 0, 'mission_fail_count': 0, 'visual_package_pass_count': 0, 'requested_route_count': {'fetch_ready_local': 0, 'nav2_reposition_first': 0, 'recovery_or_reaim': 1}}`
- analyzer: `{'milestone_interpretation': 'randomized_route_owner_visual_uat_incomplete', 'execution_quality_status': 'clean', 'setup_quality_status': 'clean', 'contact_quality_status': 'clean', 'first_contact_blocker_count': 0}`

## First Replay Failure

- `{'scene_id': 'seed20260641_scene21_recovery_or_reaim', 'route_label': 'recovery_or_reaim', 'returncode': -1, 'failure_reason': 'fresh_dashboard_session_start_failed; environment_state=error; phase=environment_starting; last_error=World stream did not become ready. WORLD_STREAM_PID=43\nWORLD_STREAM_LOG=/tmp/chasecar_world_stream.log', 'expected_session_id': '20260605T110823960749Z'}`
