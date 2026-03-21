# Stack Decisions 2026

## Decision Baseline

- Date baseline: 2026-02-26
- Branch baseline: `recovery/uat-full-robot-2026-02`
- Goal: full-stack rebuild before further high-confidence integration testing.

## Locked Decisions

1. Runtime substrate: Docker-first orchestration (`docker compose` profiles).
2. ROS runtime: `kilted` primary.
3. Parallel compatibility track: `lyrical` CI smoke + selected UAT subset.
4. Gate simulator lane: Gazebo Jetty (`jetty_gate`) authoritative for pass/fail.
5. High-fidelity lane: Isaac with Jazzy bridge sidecar (`isaac_fidelity`).
6. Robot-fidelity hardware contract: Jetson Orin Nano 8GB.
7. Inference backend: `tensorrt_int8` canonical runtime backend.
8. Migration policy: `chasecar_*` entrypoints preferred, `chasebot_*` compatibility wrappers retained for one transition cycle.

## Rationale

1. Docker-first removes cross-agent process collisions in shared WSL sessions.
2. Gate lane remains deterministic and reproducible for milestone promotion.
3. Isaac lane is explicitly bounded by bridge contracts to avoid integration drift.
4. Orin + TensorRT aligns development and deployment compute paths.
5. Parallel Lyrical validation prevents deferred migration risk after Kilted.

## Non-Goals In This Rebuild Cycle

1. Full package hard-rename from `chasebot_description` internals.
2. Field autonomy signoff.
3. New model training pipeline.
