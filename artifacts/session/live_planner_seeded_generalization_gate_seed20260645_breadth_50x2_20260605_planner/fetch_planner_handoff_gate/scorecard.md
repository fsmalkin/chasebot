# Fetch Planner Handoff Gate

- campaign_id: `live_planner_seeded_generalization_gate_seed20260645_breadth_50x2_20260605_planner`
- scene_set: `mixed_fetch_planner_v1`
- scene_source: `generated`
- planner_mode: `llm_supervised_guarded`
- seed: `20260645`
- pass: `True`
- route pass/fail: `50/0`
- fetch dispatch count: `11`
- wrong fetch-ready dispatches: `0`
- guard agreement: `50/50`
- provider status counts: `{'skipped_missing_openai_api_key': 50}`
- effective planner modes: `{'deterministic_fallback': 50}`
- llm_shadow_ready: `False`
- llm_supervised accepted/vetoed: `0/50`
- llm_supervised_ready: `False`

## Routes

- `fetch_ready_local` expected=`11` chosen=`11`
- `nav2_reposition_first` expected=`9` chosen=`9`
- `scan_or_perceive_first` expected=`11` chosen=`11`
- `recovery_or_reaim` expected=`14` chosen=`14`
- `ambiguous_or_unsafe_no_go` expected=`5` chosen=`5`

## Cases

- `seed20260645_scene01_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene02_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene03_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene04_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene05_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene06_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene07_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene08_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene09_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene10_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene11_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene12_ambiguous_or_unsafe_no_go` expected=`ambiguous_or_unsafe_no_go` route=`ambiguous_or_unsafe_no_go` correct=`True` dispatch_fetch=`False` guard=`ambiguous_or_unsafe_no_go` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene13_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene14_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene15_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene16_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene17_ambiguous_or_unsafe_no_go` expected=`ambiguous_or_unsafe_no_go` route=`ambiguous_or_unsafe_no_go` correct=`True` dispatch_fetch=`False` guard=`ambiguous_or_unsafe_no_go` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene18_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene19_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene20_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene21_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene22_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene23_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene24_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene25_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene26_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene27_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene28_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene29_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene30_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene31_ambiguous_or_unsafe_no_go` expected=`ambiguous_or_unsafe_no_go` route=`ambiguous_or_unsafe_no_go` correct=`True` dispatch_fetch=`False` guard=`ambiguous_or_unsafe_no_go` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene32_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene33_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene34_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene35_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene36_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene37_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene38_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene39_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene40_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene41_ambiguous_or_unsafe_no_go` expected=`ambiguous_or_unsafe_no_go` route=`ambiguous_or_unsafe_no_go` correct=`True` dispatch_fetch=`False` guard=`ambiguous_or_unsafe_no_go` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene42_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene43_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene44_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene45_nav2_reposition_first` expected=`nav2_reposition_first` route=`nav2_reposition_first` correct=`True` dispatch_fetch=`False` guard=`nav2_reposition_first` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene46_recovery_or_reaim` expected=`recovery_or_reaim` route=`recovery_or_reaim` correct=`True` dispatch_fetch=`False` guard=`recovery_or_reaim` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene47_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene48_ambiguous_or_unsafe_no_go` expected=`ambiguous_or_unsafe_no_go` route=`ambiguous_or_unsafe_no_go` correct=`True` dispatch_fetch=`False` guard=`ambiguous_or_unsafe_no_go` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene49_fetch_ready_local` expected=`fetch_ready_local` route=`fetch_ready_local` correct=`True` dispatch_fetch=`True` guard=`fetch_ready_local` provider=`skipped_missing_openai_api_key`
- `seed20260645_scene50_scan_or_perceive_first` expected=`scan_or_perceive_first` route=`scan_or_perceive_first` correct=`True` dispatch_fetch=`False` guard=`scan_or_perceive_first` provider=`skipped_missing_openai_api_key`
