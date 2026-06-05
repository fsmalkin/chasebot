# Fetch Planner Handoff Gate

- campaign_id: `live_planner_seeded_generalization_gate_seed20260641_rough_breadth_startup_retry_20260605_planner`
- scene_set: `mixed_fetch_planner_v1`
- scene_source: `generated`
- planner_mode: `llm_supervised_guarded`
- seed: `20260641`
- pass: `True`
- route pass/fail: `30/0`
- fetch dispatch count: `3`
- wrong fetch-ready dispatches: `0`
- guard agreement: `30/30`
- provider status counts: `{'skipped_missing_openai_api_key': 30}`
- effective planner modes: `{'deterministic_fallback': 30}`
- llm_shadow_ready: `False`
- llm_supervised accepted/vetoed: `0/30`
- llm_supervised_ready: `False`

## Routes

- `fetch_ready_local` expected=`3` chosen=`3`
- `nav2_reposition_first` expected=`6` chosen=`6`
- `scan_or_perceive_first` expected=`9` chosen=`9`
- `recovery_or_reaim` expected=`10` chosen=`10`
- `ambiguous_or_unsafe_no_go` expected=`2` chosen=`2`

## Cases

- `seed20260641_scene01_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene02_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene03_ambiguous_or_unsafe_no_go` expected=`ambiguous_or_unsafe_no_go` route=`ambiguous_or_unsafe_no_go` correct=`True` dispatch_fetch=`False` guard=`ambiguous_or_unsafe_no_go` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene04_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene05_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene06_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene07_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene08_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene09_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene10_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene11_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene12_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene13_ambiguous_or_unsafe_no_go` expected=`ambiguous_or_unsafe_no_go` route=`ambiguous_or_unsafe_no_go` correct=`True` dispatch_fetch=`False` guard=`ambiguous_or_unsafe_no_go` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene14_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene15_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene16_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene17_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene18_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene19_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene20_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene21_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene22_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene23_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene24_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene25_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene26_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene27_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene28_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene29_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260641_scene30_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
