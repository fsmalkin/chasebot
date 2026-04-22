# Chasecar Documentation

## Current Docs (2026 Stack)

### Operations
- [ACTIVE_WORKFLOW.md](ACTIVE_WORKFLOW.md) — Canonical bring-up, UAT execution, and GUI rehearsal sequencing
- [FIRST_UAT_RUNBOOK.md](FIRST_UAT_RUNBOOK.md) — First operator UAT procedure and triage
- [DASHBOARD_OPERATOR_GUIDE.md](DASHBOARD_OPERATOR_GUIDE.md) — Browser dashboard and Xpra operator view
- [QUICK_REFERENCE_ROBOT_CONTROL.md](QUICK_REFERENCE_ROBOT_CONTROL.md) — Quick reference for robot control
- [TELEGRAM_MCP.md](TELEGRAM_MCP.md) — Repo-local Telegram wait bridge and Codex MCP setup

### Architecture and Design
- [LLM_CONTROL_ARCHITECTURE.md](LLM_CONTROL_ARCHITECTURE.md) — Layered LLM supervisor design (bounded intent, deterministic gating)
- [STACK_DECISIONS_2026.md](STACK_DECISIONS_2026.md) — Locked decisions for the 2026 rebuild
- [ROBOT_HARDWARE_CONTRACT_ORIN_NANO.md](ROBOT_HARDWARE_CONTRACT_ORIN_NANO.md) — Jetson Orin Nano 8GB hardware contract
- [ROBOT_HARDWARE_CONSTRAINTS.md](ROBOT_HARDWARE_CONSTRAINTS.md) — Hardware constraints and profiles
- [SIM_FIDELITY_MATRIX.md](SIM_FIDELITY_MATRIX.md) — Simulation fidelity levels (gate vs. Isaac)

### Planning and Research
- [ROADMAP_2026_H2.md](ROADMAP_2026_H2.md) — H2 2026 roadmap
- [LLM_BROWSER_UAT_PLAN.md](LLM_BROWSER_UAT_PLAN.md) — LLM integration UAT planning
- [LLM_RESEARCH_NOTES.md](LLM_RESEARCH_NOTES.md) — Research notes on LLM integration
- [CURRENT_EXPERIMENTS_REFERENCE.md](CURRENT_EXPERIMENTS_REFERENCE.md) — Active experiments reference

- [PROBE_ODOM_WORLD_SIGN_CHAIN_CLOSEOUT_2026-04-21.md](PROBE_ODOM_WORLD_SIGN_CHAIN_CLOSEOUT_2026-04-21.md) - Runtime probe closeout and source-vs-fresh fixture interpretation

### Runtime Contracts
- [../runtime/contracts/llm_control_contract.yaml](../runtime/contracts/llm_control_contract.yaml) — Pre-LLM control contract (frozen)
- [../runtime/contracts/isaac_bridge_allowlist.yaml](../runtime/contracts/isaac_bridge_allowlist.yaml) — Isaac bridge topic/action/service boundaries
- [../runtime/contracts/message_schema_manifest.yaml](../runtime/contracts/message_schema_manifest.yaml) — Message schema manifest

## Archive

Historical docs from the 2025 development cycle are in [archive/](archive/). These cover the original ROS Humble stack, pre-Docker workflows, and early vision/nav integration work. They are preserved for reference but do not reflect the current system.
