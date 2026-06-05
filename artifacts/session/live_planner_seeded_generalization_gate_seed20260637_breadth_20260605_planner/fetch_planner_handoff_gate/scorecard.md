# Fetch Planner Handoff Gate

- campaign_id: `live_planner_seeded_generalization_gate_seed20260637_breadth_20260605_planner`
- scene_set: `mixed_fetch_planner_v1`
- scene_source: `generated`
- planner_mode: `llm_supervised_guarded`
- seed: `20260637`
- pass: `True`
- route pass/fail: `30/0`
- fetch dispatch count: `6`
- wrong fetch-ready dispatches: `0`
- guard agreement: `30/30`
- provider status counts: `{'skipped_missing_openai_api_key': 30}`
- effective planner modes: `{'deterministic_fallback': 30}`
- llm_shadow_ready: `False`
- llm_supervised accepted/vetoed: `0/30`
- llm_supervised_ready: `False`

## Routes

- `fetch_ready_local` expected=`6` chosen=`6`
- `nav2_reposition_first` expected=`6` chosen=`6`
- `scan_or_perceive_first` expected=`7` chosen=`7`
- `recovery_or_reaim` expected=`7` chosen=`7`
- `ambiguous_or_unsafe_no_go` expected=`4` chosen=`4`

## Cases

- `seed20260637_scene01_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene02_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene03_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene04_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene05_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene06_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene07_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene08_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene09_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene10_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene11_ambiguous_or_unsafe_no_go` expected=`ambiguous_or_unsafe_no_go` route=`ambiguous_or_unsafe_no_go` correct=`True` dispatch_fetch=`False` guard=`ambiguous_or_unsafe_no_go` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene12_ambiguous_or_unsafe_no_go` expected=`ambiguous_or_unsafe_no_go` route=`ambiguous_or_unsafe_no_go` correct=`True` dispatch_fetch=`False` guard=`ambiguous_or_unsafe_no_go` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene13_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene14_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene15_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene16_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene17_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene18_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene19_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene20_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene21_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene22_ambiguous_or_unsafe_no_go` expected=`ambiguous_or_unsafe_no_go` route=`ambiguous_or_unsafe_no_go` correct=`True` dispatch_fetch=`False` guard=`ambiguous_or_unsafe_no_go` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene23_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene24_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene25_ambiguous_or_unsafe_no_go` expected=`ambiguous_or_unsafe_no_go` route=`ambiguous_or_unsafe_no_go` correct=`True` dispatch_fetch=`False` guard=`ambiguous_or_unsafe_no_go` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene26_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene27_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene28_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene29_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260637_scene30_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
