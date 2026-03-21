# Legacy Surface Marker

This directory marks the rebuild transition boundary.

## Current Legacy Areas (non-canonical)

1. `archive/`
2. `ros/`
3. `sim/`
4. Historical launch and script variants under `ros2_config/launch` and `ros2_scripts`

## Policy

1. Do not remove legacy assets during the rebuild unless explicitly approved.
2. New workflow changes must land in canonical surfaces:
   - `docker-compose.yml`
   - `containers/`
   - `launch/`
   - `runtime/`
   - `scripts/run_compose_*.ps1`
   - `docs/ACTIVE_WORKFLOW.md`
