from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import route_planning_parallel_soak_runner as soak_runner  # noqa: E402


def test_build_worker_configs_assigns_unique_ros_domains_and_runtime_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(soak_runner, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(soak_runner, "reserve_dashboard_ports", lambda count, start, end: [8870, 8871][:count])
    args = SimpleNamespace(
        workers=2,
        dashboard_port_start=8870,
        dashboard_port_end=8909,
        ros_domain_id_start=180,
        runtime_root="runtime/dashboard_parallel",
    )

    configs = soak_runner.build_worker_configs(args, campaign_id="20260412T000000Z", campaign_root=tmp_path / "artifacts")

    assert [config.dashboard_port for config in configs] == [8870, 8871]
    assert [config.ros_domain_id for config in configs] == [180, 181]
    assert configs[0].runtime_dir == tmp_path / "runtime" / "dashboard_parallel" / "20260412T000000Z" / "worker_01"
    assert configs[1].runtime_dir == tmp_path / "runtime" / "dashboard_parallel" / "20260412T000000Z" / "worker_02"


def test_build_repeatability_command_uses_worker_runtime_state_path(tmp_path, monkeypatch):
    monkeypatch.setattr(soak_runner, "REPO_ROOT", tmp_path)
    config = soak_runner.WorkerConfig(
        index=1,
        name="worker_01",
        ros_domain_id=180,
        dashboard_port=8870,
        dashboard_url="http://127.0.0.1:8870",
        runtime_dir=tmp_path / "runtime" / "dashboard_parallel" / "campaign" / "worker_01",
        dashboard_log_path=tmp_path / "artifacts" / "dashboard.log",
        repeatability_log_path=tmp_path / "artifacts" / "repeatability.log",
        worker_campaign_id="campaign_worker_01",
    )
    args = SimpleNamespace(
        scenario_id="visit_route_planning",
        scenario_label="LLM Route Planning",
        runs_per_worker=1,
        hidden_start_settle_s=3.0,
        max_target_runtime_s=240.0,
        search_timeouts_s=45.0,
        search_timeout_s=45.0,
        approach_timeout_s=120.0,
        keep_visited_targets=True,
    )

    command = soak_runner.build_repeatability_command(config, args)

    assert "--visit-runtime-json" in command
    path_index = command.index("--visit-runtime-json") + 1
    assert Path(command[path_index]) == config.runtime_dir / "visit_mission_runtime.json"
    gate_mode_index = command.index("--promotion-gate-mode") + 1
    assert command[gate_mode_index] == "pass_only"
