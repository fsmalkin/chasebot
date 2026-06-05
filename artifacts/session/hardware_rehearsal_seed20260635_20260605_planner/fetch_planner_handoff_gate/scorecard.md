# Fetch Planner Handoff Gate

- campaign_id: `hardware_rehearsal_seed20260635_20260605_planner`
- scene_set: `mixed_fetch_planner_v1`
- scene_source: `generated`
- planner_mode: `llm_supervised_guarded`
- seed: `20260635`
- pass: `True`
- route pass/fail: `30/0`
- fetch dispatch count: `9`
- wrong fetch-ready dispatches: `0`
- guard agreement: `30/30`
- provider status counts: `{'skipped_missing_openai_api_key': 30}`
- effective planner modes: `{'deterministic_fallback': 30}`
- llm_shadow_ready: `False`
- llm_supervised accepted/vetoed: `0/30`
- llm_supervised_ready: `False`

## Routes

- `fetch_ready_local` expected=`9` chosen=`9`
- `nav2_reposition_first` expected=`8` chosen=`8`
- `scan_or_perceive_first` expected=`4` chosen=`4`
- `recovery_or_reaim` expected=`7` chosen=`7`
- `ambiguous_or_unsafe_no_go` expected=`2` chosen=`2`

## Cases

- `seed20260635_scene01_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene02_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene03_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene04_ambiguous_or_unsafe_no_go` expected=`ambiguous_or_unsafe_no_go` route=`ambiguous_or_unsafe_no_go` correct=`True` dispatch_fetch=`False` guard=`ambiguous_or_unsafe_no_go` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene05_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene06_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene07_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene08_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene09_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene10_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene11_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene12_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene13_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene14_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene15_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene16_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene17_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene18_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene19_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene20_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene21_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene22_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene23_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene24_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene25_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene26_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene27_ambiguous_or_unsafe_no_go` expected=`ambiguous_or_unsafe_no_go` route=`ambiguous_or_unsafe_no_go` correct=`True` dispatch_fetch=`False` guard=`ambiguous_or_unsafe_no_go` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene28_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene29_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260635_scene30_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
