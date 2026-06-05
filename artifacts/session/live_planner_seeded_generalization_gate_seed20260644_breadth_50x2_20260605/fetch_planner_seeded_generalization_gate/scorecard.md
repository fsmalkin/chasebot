# Fetch Planner Seeded Generalization Gate

- campaign_id: `live_planner_seeded_generalization_gate_seed20260644_breadth_50x2_20260605`
- dry_run: `False`
- seed: `20260644`
- random_cases: `50`
- max_per_route: `2`
- expected_executable_count: `6`
- pass: `True`
- promotion_evidence: `False`
- planner_authority_ready: `False`
- interpretation: `planner_routed_seeded_generalization_visual_uat_green`

## Child Evidence

- planner_gate pass=`True` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260644_breadth_50x2_20260605_planner/fetch_planner_handoff_gate/scorecard.md)
- replay_batch pass=`True` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260644_breadth_50x2_20260605_replay/fetch_planner_route_replay_batch/scorecard.md)
- route_analyzer pass=`True` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260644_breadth_50x2_20260605_analysis/fetch_planner_route_uat_analyzer/scorecard.md)

## Summary

- planner: `{'pass_count': 50, 'fail_count': 0, 'wrong_fetch_dispatch_count': 0, 'route_counts': {'fetch_ready_local': 10, 'nav2_reposition_first': 9, 'scan_or_perceive_first': 14, 'recovery_or_reaim': 7, 'ambiguous_or_unsafe_no_go': 10}, 'provider_status_counts': {'skipped_missing_openai_api_key': 50}, 'planner_mode_effective_counts': {'deterministic_fallback': 50}, 'llm_shadow_ready': False, 'llm_shadow_provider_ok_count': 0, 'llm_supervised_ready': False, 'llm_supervised_accept_count': 0, 'llm_supervised_veto_count': 50, 'llm_supervised_veto_reason_counts': {'provider_not_ok': 50, 'missing_llm_route': 50, 'confidence_below_threshold': 50}, 'strict_planner_authority_ready': False, 'guarded_fallback_authority_ready': False}`
- replay: `{'selected_count': 6, 'mission_pass_count': 6, 'mission_fail_count': 0, 'visual_package_pass_count': 6, 'requested_route_count': {'fetch_ready_local': 2, 'nav2_reposition_first': 2, 'recovery_or_reaim': 2}}`
- analyzer: `{'milestone_interpretation': 'randomized_route_owner_visual_uat_green', 'execution_quality_status': 'clean', 'setup_quality_status': 'clean', 'contact_quality_status': 'clean', 'first_contact_blocker_count': 0}`
