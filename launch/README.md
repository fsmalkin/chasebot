# Canonical Launch Surface

These launch files define the rebuilt canonical surface.

## Files

1. `sim_gate.launch.py`
   - Authoritative gate simulator lane (`jetty_gate`)
2. `perception_stack.launch.py`
   - TensorRT detector + 3D extractor
3. `nav_acquire_plan_track.launch.py`
   - Low-level acquire/plan/track chain
4. `sim_isaac_bridge.launch.py`
   - Isaac sidecar bridge launcher using allowlist contract

## Contract Inputs

1. Runtime profile contract:
   - `runtime/profiles/runtime_targets.yaml`
2. Bridge allowlist contract:
   - `runtime/contracts/isaac_bridge_allowlist.yaml`
