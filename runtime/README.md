# Runtime Contracts

## Purpose

This directory contains canonical runtime contracts for the rebuilt stack.

## Files

1. `profiles/runtime_targets.yaml`
   - Runtime targets (`robot_fidelity_orin`, `workstation_balanced`, `workstation_max`)
2. `contracts/isaac_bridge_allowlist.yaml`
   - Topic/action/service boundary for Isaac bridge sidecar
3. `contracts/message_schema_manifest.yaml`
   - Topic/action/service schema manifest for CI drift checks
4. `contracts/llm_control_contract.yaml`
   - Pre-LLM integration command and safety contract
5. `tensorrt/`
   - TensorRT engine/calibration assets and pipeline metadata
