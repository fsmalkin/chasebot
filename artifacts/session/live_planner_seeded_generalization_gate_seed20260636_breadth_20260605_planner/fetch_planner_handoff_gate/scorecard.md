# Fetch Planner Handoff Gate

- campaign_id: `live_planner_seeded_generalization_gate_seed20260636_breadth_20260605_planner`
- scene_set: `mixed_fetch_planner_v1`
- scene_source: `generated`
- planner_mode: `llm_supervised_guarded`
- seed: `20260636`
- pass: `True`
- route pass/fail: `30/0`
- fetch dispatch count: `4`
- wrong fetch-ready dispatches: `0`
- guard agreement: `30/30`
- provider status counts: `{'skipped_missing_openai_api_key': 30}`
- effective planner modes: `{'deterministic_fallback': 30}`
- llm_shadow_ready: `False`
- llm_supervised accepted/vetoed: `0/30`
- llm_supervised_ready: `False`

## Routes

- `fetch_ready_local` expected=`4` chosen=`4`
- `nav2_reposition_first` expected=`6` chosen=`6`
- `scan_or_perceive_first` expected=`6` chosen=`6`
- `recovery_or_reaim` expected=`9` chosen=`9`
- `ambiguous_or_unsafe_no_go` expected=`5` chosen=`5`

## Cases

- `seed20260636_scene01_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene02_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene03_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene04_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene05_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene06_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene07_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene08_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene09_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene10_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene11_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene12_ambiguous_or_unsafe_no_go` expected=`ambiguous_or_unsafe_no_go` route=`ambiguous_or_unsafe_no_go` correct=`True` dispatch_fetch=`False` guard=`ambiguous_or_unsafe_no_go` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene13_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene14_ambiguous_or_unsafe_no_go` expected=`ambiguous_or_unsafe_no_go` route=`ambiguous_or_unsafe_no_go` correct=`True` dispatch_fetch=`False` guard=`ambiguous_or_unsafe_no_go` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene15_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene16_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene17_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene18_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene19_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene20_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene21_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene22_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene23_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene24_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene25_ambiguous_or_unsafe_no_go` expected=`ambiguous_or_unsafe_no_go` route=`ambiguous_or_unsafe_no_go` correct=`True` dispatch_fetch=`False` guard=`ambiguous_or_unsafe_no_go` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene26_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene27_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene28_ambiguous_or_unsafe_no_go` expected=`ambiguous_or_unsafe_no_go` route=`ambiguous_or_unsafe_no_go` correct=`True` dispatch_fetch=`False` guard=`ambiguous_or_unsafe_no_go` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene29_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260636_scene30_ambiguous_or_unsafe_no_go` expected=`ambiguous_or_unsafe_no_go` route=`ambiguous_or_unsafe_no_go` correct=`True` dispatch_fetch=`False` guard=`ambiguous_or_unsafe_no_go` provider=`skipped_missing_openai_api_key`
