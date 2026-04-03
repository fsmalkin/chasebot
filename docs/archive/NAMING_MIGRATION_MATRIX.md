# Naming Migration Matrix

## Scope

Phased transition from `chasebot_*` entrypoints to `chasecar_*` canonical entrypoints.

## Matrix

| Legacy | Canonical | Status |
|---|---|---|
| `scripts/run_canonical_stack.ps1 -RuntimeTarget robot_fidelity` | `scripts/run_chasecar_stack.ps1 -RuntimeTarget robot_fidelity_orin` | Active compatibility alias |
| `scripts/run_coordinate_uat.ps1 -RuntimeTarget robot_fidelity` | `scripts/run_chasecar_coordinate_uat.ps1 -RuntimeTarget robot_fidelity_orin` | Active compatibility alias |
| `scripts/run_chasebot_stack_compat.ps1` | `scripts/run_chasecar_stack.ps1` | Legacy wrapper |
| `scripts/run_chasebot_coordinate_uat_compat.ps1` | `scripts/run_chasecar_coordinate_uat.ps1` | Legacy wrapper |
| `robot_fidelity` runtime target | `robot_fidelity_orin` runtime target | Legacy alias retained |

## Decommission Policy

1. Keep wrappers for one transition cycle.
2. Remove wrappers after two consecutive green release candidate cycles under canonical names.
