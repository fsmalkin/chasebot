# Probe Odom/World Sign Chain Closeout (2026-04-21)

## Summary

- Refreshed closeout artifact: `artifacts/session/live_plus45_probe_odom_world_sign_chain_20260421_provenance_rerun/probe_odom_world_sign_chain/odom_world_sign_chain_summary.json`
- Preserved runtime verdict: `runtime_classification.diagnosis=sign_chain_aligned`
- Preserved source-side verdict: `source_alignment_assessment.diagnosis=source_fixture_command_sign_mismatch`
- Preserved next action: `inspect_source_fixture_alignment`

The narrow runtime-check branch is closed. The refreshed April 21, 2026 provenance rerun shows that the fresh runtime sign chain is internally aligned, while the remaining disagreement is in how the preserved source fixtures map onto the fresh fixture-local command windows.

## Artifact Chain

1. `helper_turn_authority_contract_audit` stopped the helper-turn-authority promotion path with `blocking_reason=sign_parity`.
2. `manual_drive_sign_parity_audit` escalated to `probe_odom_world_sign_chain` for one concrete runtime follow-up.
3. The refreshed April 21, 2026 probe bundle preserved a live runtime result of `sign_chain_aligned` while reconstructing source and fresh fixture-local command provenance inside the analyzer output.

## Fixture Interpretation

The rows below come from the refreshed fixture-local comparison surfaces in `scorecard.md` and the per-fixture payloads. These values are the bounded windows we should use for interpretation, not older attempt-level summaries.

| Fixture | Source window | Fresh window | Source sign | Fresh sign | Relation | Interpretation |
| --- | --- | --- | --- | --- | --- | --- |
| `early_stall` | `18.668..29.88599` | `21.471..32.628529` | `+1` | `-1` | `mismatch` | Fresh runtime and fresh world truth stay aligned; the disagreement is source command provenance versus the fresh fixture-local request. |
| `mid_stall` | `25.052..36.259906` | `27.266..38.576887` | `+1` | `-1` | `mismatch` | Same pattern as `early_stall`: the source command sign disagrees with the fresh fixture-local command sign while the fresh runtime chain remains internally aligned. |
| `late_stall` | `31.39..37.801761` | `33.731..40.013532` | `-1` | `+1` | `mismatch` | The source command sign still disagrees with the fresh fixture-local command sign; this remains a source fixture/window interpretation issue, not a reproduced live odom/world sign break. |
| `terminal_stall` | `37.679..37.679` | `39.998..39.998` | `+1` | `+1` | `match` | Control match. This label anchors the refreshed comparison and shows the analyzer can recover a homologous source/fresh fixture-local relation when the preserved signs agree. |

## Findings

- `early_stall`, `mid_stall`, and `late_stall` remain source-command mismatches after the fresh command window is reconstructed.
- `terminal_stall` remains the control match.
- The refreshed runtime probe keeps `requested_command`, controller-side odom, and fresh world truth aligned on the fresh run.
- This branch therefore does not justify a runtime sign-chain patch or a public `/odom` contract change.

## Decision

- Treat `/jetbot_base_controller/odom` as a probe-only witness for this branch.
- Keep the helper turn-authority lane as a comparison baseline, not the next promotion path.
- Move the next work to source-artifact interpretation plus end-to-end gather-control comparison, using the known mismatch fixtures as stress tests rather than as proof that the final architecture needs a named recovery strategy.
- Reopen runtime-focused work only if a future fresh rerun materially changes the mismatch set above.
