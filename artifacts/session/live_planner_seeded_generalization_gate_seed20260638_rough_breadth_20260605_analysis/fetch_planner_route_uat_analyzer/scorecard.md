# Fetch Planner Route UAT Scorecard

- Campaign: `live_planner_seeded_generalization_gate_seed20260638_rough_breadth_20260605_analysis`
- Evidence scope: `route_owner_visual_uat`
- Pass: `True`
- Interpretation: `randomized_route_owner_visual_uat_green`
- Promotion evidence: `False`
- Mission green: `True`
- Visual package green: `True`
- Execution quality: `clean`
- Execution watches: `0`
- Setup quality: `clean`
- Setup watches: `0`
- Contact quality: `clean`
- Contact watches: `0`
- First-contact blockers: `0`
- Predicted contact quality: `{'watch': 8}`
- Predicted first-contact risk: `{'high': 3, 'medium': 3, 'low': 2}`

## Route Coverage
- route=`fetch_ready_local` planner=`2` live=`2` pass=`2` fetch_pass=`2` route_only_pass=`0` clean=`2` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`2` pred_blocker=`0` blocker=`0` status=`live_executable_passed`
- route=`nav2_reposition_first` planner=`6` live=`3` pass=`3` fetch_pass=`3` route_only_pass=`0` clean=`3` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`3` pred_blocker=`0` blocker=`0` status=`live_executable_passed`
- route=`scan_or_perceive_first` planner=`9` live=`0` pass=`0` fetch_pass=`0` route_only_pass=`0` clean=`0` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`0` pred_blocker=`0` blocker=`0` status=`planner_only_classified`
- route=`recovery_or_reaim` planner=`7` live=`3` pass=`3` fetch_pass=`3` route_only_pass=`0` clean=`3` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`3` pred_blocker=`0` blocker=`0` status=`live_executable_passed`
- route=`ambiguous_or_unsafe_no_go` planner=`6` live=`0` pass=`0` fetch_pass=`0` route_only_pass=`0` clean=`0` watch=`0` setup_watch=`0` exec_watch=`0` pred_watch=`0` pred_blocker=`0` blocker=`0` status=`planner_only_classified`

## Planner Gates
- `live_planner_seeded_generalization_gate_seed20260638_rough_breadth_20260605_planner` pass=`True` routes=`30/30` wrong_fetch=`0` guard_agree=`30/30` provider=`{'skipped_missing_openai_api_key': 30}` llm_shadow_ready=`False` source=`generated` seed=`20260638` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260638_rough_breadth_20260605_planner/fetch_planner_handoff_gate/gate_summary.json)

## Live Missions
- route=`recovery_or_reaim` session=`20260605T082051238429Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.197m` predicted=`watch` risk=`high` score=`41.032` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T082051238429Z/golf_ball_circle_delivery/20260605T082358318264Z/mission_verdict.json)
- route=`recovery_or_reaim` session=`20260605T082636242942Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.195m` predicted=`watch` risk=`high` score=`42.686` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T082636242942Z/golf_ball_circle_delivery/20260605T082753629458Z/mission_verdict.json)
- route=`recovery_or_reaim` session=`20260605T082935422917Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.198m` predicted=`watch` risk=`high` score=`43.27` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T082935422917Z/golf_ball_circle_delivery/20260605T083205722403Z/mission_verdict.json)
- route=`nav2_reposition_first` session=`20260605T085830212640Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.197m` predicted=`watch` risk=`medium` score=`62.224` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T085830212640Z/golf_ball_circle_delivery/20260605T090151238492Z/mission_verdict.json)
- route=`nav2_reposition_first` session=`20260605T090418004362Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.194m` predicted=`watch` risk=`medium` score=`62.388` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T090418004362Z/golf_ball_circle_delivery/20260605T090507735139Z/mission_verdict.json)
- route=`nav2_reposition_first` session=`20260605T090640781973Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.198m` predicted=`watch` risk=`medium` score=`66.104` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T090640781973Z/golf_ball_circle_delivery/20260605T090807345090Z/mission_verdict.json)
- route=`fetch_ready_local` session=`20260605T090951695110Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.195m` predicted=`watch` risk=`low` score=`82.266` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T090951695110Z/golf_ball_circle_delivery/20260605T091029720533Z/mission_verdict.json)
- route=`fetch_ready_local` session=`20260605T091204007488Z` contract_pass=`True` fetch_pass=`True` route_only_pass=`False` local_fetch=`True` closest=`0.198m` predicted=`watch` risk=`low` score=`92.537` exec=`clean` setup=`clean` contact=`clean` flags=`` setup_flags=`` contact_flags=`` first_flags=`` [summary](/artifacts/session/20260605T091204007488Z/golf_ball_circle_delivery/20260605T091241562525Z/mission_verdict.json)

## Visual Packages
- `live_planner_seeded_generalization_gate_seed20260638_rough_breadth_20260605_replay_seed20260638_scene09_recovery_or_reaim` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260638_rough_breadth_20260605_replay_seed20260638_scene09_recovery_or_reaim/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260638_rough_breadth_20260605_replay_seed20260638_scene16_recovery_or_reaim` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260638_rough_breadth_20260605_replay_seed20260638_scene16_recovery_or_reaim/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260638_rough_breadth_20260605_replay_seed20260638_scene24_recovery_or_reaim` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260638_rough_breadth_20260605_replay_seed20260638_scene24_recovery_or_reaim/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260638_rough_breadth_20260605_replay_seed20260638_scene15_nav2_reposition_first` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260638_rough_breadth_20260605_replay_seed20260638_scene15_nav2_reposition_first/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260638_rough_breadth_20260605_replay_seed20260638_scene03_nav2_reposition_first` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260638_rough_breadth_20260605_replay_seed20260638_scene03_nav2_reposition_first/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260638_rough_breadth_20260605_replay_seed20260638_scene08_nav2_reposition_first` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260638_rough_breadth_20260605_replay_seed20260638_scene08_nav2_reposition_first/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260638_rough_breadth_20260605_replay_seed20260638_scene23_fetch_ready_local` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260638_rough_breadth_20260605_replay_seed20260638_scene23_fetch_ready_local/fetch_visual_uat_package/scorecard.md)
- `live_planner_seeded_generalization_gate_seed20260638_rough_breadth_20260605_replay_seed20260638_scene10_fetch_ready_local` pass=`True` mobile=`True` onboard=`True` recoveries=`2/2` warnings=`visual_confirmation_keyframe_recovery` [summary](/artifacts/session/live_planner_seeded_generalization_gate_seed20260638_rough_breadth_20260605_replay_seed20260638_scene10_fetch_ready_local/fetch_visual_uat_package/scorecard.md)
