#!/usr/bin/env python3
"""Run isolated route-planning soak workers in parallel without sharing dashboard state."""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_supervisor_core import REPO_ROOT
from llm_supervisor_core import ensure_dir
from llm_supervisor_core import http_json
from llm_supervisor_core import read_json
from llm_supervisor_core import utc_now
from llm_supervisor_core import write_json
from visit_mission_campaign_helpers import parse_marker


DEFAULT_SCENARIO_ID = "visit_route_planning"
DEFAULT_SCENARIO_LABEL = "LLM Route Planning"
STOP_REQUESTED = threading.Event()


@dataclass(frozen=True)
class WorkerConfig:
    index: int
    name: str
    ros_domain_id: int
    dashboard_port: int
    dashboard_url: str
    runtime_dir: Path
    dashboard_log_path: Path
    repeatability_log_path: Path
    worker_campaign_id: str


def current_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def request_stop(_signum: int, _frame: Any) -> None:
    STOP_REQUESTED.set()


def install_signal_handlers() -> None:
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, request_stop)
        except Exception:
            continue


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run isolated route-planning soak workers in parallel.")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--runs-per-worker", type=int, default=1)
    parser.add_argument("--campaign-id", default="")
    parser.add_argument("--scenario-id", default=DEFAULT_SCENARIO_ID)
    parser.add_argument("--scenario-label", default=DEFAULT_SCENARIO_LABEL)
    parser.add_argument("--dashboard-port-start", type=int, default=8870)
    parser.add_argument("--dashboard-port-end", type=int, default=8909)
    parser.add_argument("--ros-domain-id-start", type=int, default=180)
    parser.add_argument("--runtime-root", default="runtime/dashboard_parallel")
    parser.add_argument("--runtime-target", default="workstation_max")
    parser.add_argument("--world-file", default="yolo_test_world_v6_clean_uat_fast.world")
    parser.add_argument("--gate-perf-profile", default="max")
    parser.add_argument("--dashboard-ready-timeout-s", type=float, default=90.0)
    parser.add_argument("--environment-stop-timeout-s", type=float, default=180.0)
    parser.add_argument("--hidden-start-settle-s", type=float, default=3.0)
    parser.add_argument("--max-target-runtime-s", type=float, default=240.0)
    parser.add_argument("--search-timeout-s", type=float, default=45.0)
    parser.add_argument("--approach-timeout-s", type=float, default=120.0)
    parser.add_argument("--keep-visited-targets", action="store_true", default=True)
    parser.add_argument("--no-keep-visited-targets", dest="keep_visited_targets", action="store_false")
    return parser.parse_args()


def port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def reserve_dashboard_ports(count: int, *, start: int, end: int) -> list[int]:
    ports: list[int] = []
    for port in range(start, end + 1):
        if port_open("127.0.0.1", port):
            continue
        ports.append(port)
        if len(ports) >= count:
            return ports
    raise RuntimeError(f"Unable to reserve {count} dashboard ports in range {start}-{end}.")


def wait_for_dashboard(dashboard_url: str, timeout_s: float) -> None:
    deadline = time.monotonic() + max(timeout_s, 5.0)
    while time.monotonic() < deadline:
        if STOP_REQUESTED.is_set():
            raise RuntimeError("Interrupted while waiting for dashboard readiness.")
        try:
            status, _ = http_json(f"{dashboard_url.rstrip('/')}/api/state", timeout_s=5.0)
            if status == 200:
                return
        except Exception:
            pass
        time.sleep(1.0)
    raise RuntimeError(f"Dashboard API at {dashboard_url} did not become ready before timeout.")


def wait_for_environment_stop(dashboard_url: str, timeout_s: float) -> None:
    deadline = time.monotonic() + max(timeout_s, 5.0)
    while time.monotonic() < deadline:
        try:
            status, payload = http_json(f"{dashboard_url.rstrip('/')}/api/state", timeout_s=5.0)
        except Exception:
            return
        if status != 200:
            return
        if str(payload.get("environment_state", "")) == "stopped":
            return
        time.sleep(1.0)


def terminate_process(proc: subprocess.Popen[str] | None, *, timeout_s: float = 20.0) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=max(timeout_s, 1.0))
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10.0)


def build_worker_configs(args: argparse.Namespace, *, campaign_id: str, campaign_root: Path) -> list[WorkerConfig]:
    runtime_base = ensure_dir(REPO_ROOT / args.runtime_root / campaign_id)
    workers_root = ensure_dir(campaign_root / "workers")
    ports = reserve_dashboard_ports(max(args.workers, 1), start=args.dashboard_port_start, end=args.dashboard_port_end)
    configs: list[WorkerConfig] = []
    for index, port in enumerate(ports, start=1):
        ros_domain_id = int(args.ros_domain_id_start) + index - 1
        if ros_domain_id < 0 or ros_domain_id > 232:
            raise RuntimeError(f"ROS_DOMAIN_ID {ros_domain_id} is outside the supported 0-232 range.")
        worker_name = f"worker_{index:02d}"
        worker_root = ensure_dir(workers_root / worker_name)
        runtime_dir = ensure_dir(runtime_base / worker_name)
        configs.append(
            WorkerConfig(
                index=index,
                name=worker_name,
                ros_domain_id=ros_domain_id,
                dashboard_port=port,
                dashboard_url=f"http://127.0.0.1:{port}",
                runtime_dir=runtime_dir,
                dashboard_log_path=worker_root / "dashboard_service.log",
                repeatability_log_path=worker_root / "repeatability.log",
                worker_campaign_id=f"{campaign_id}_{worker_name}",
            )
        )
    return configs


def build_repeatability_command(config: WorkerConfig, args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "visit_mission_repeatability_runner.py"),
        "--dashboard-url",
        config.dashboard_url,
        "--scenario-id",
        args.scenario_id,
        "--scenario-label",
        args.scenario_label,
        "--runs",
        str(max(args.runs_per_worker, 1)),
        "--campaign-id",
        config.worker_campaign_id,
        "--hidden-start-settle-s",
        str(args.hidden_start_settle_s),
        "--max-target-runtime-s",
        str(args.max_target_runtime_s),
        "--search-timeout-s",
        str(args.search_timeout_s),
        "--approach-timeout-s",
        str(args.approach_timeout_s),
        "--visit-runtime-json",
        str(config.runtime_dir / "visit_mission_runtime.json"),
        "--promotion-gate-mode",
        "pass_only",
    ]
    if args.keep_visited_targets:
        command.append("--keep-visited-targets")
    return command


def run_worker(config: WorkerConfig, args: argparse.Namespace) -> dict[str, Any]:
    dashboard_proc: subprocess.Popen[str] | None = None
    dashboard_command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "dashboard_service.py"),
        "--host",
        "127.0.0.1",
        "--port",
        str(config.dashboard_port),
        "--runtime-dir",
        str(config.runtime_dir),
        "--peer-project-cleanup",
        "none",
        "--headless-worker",
    ]
    repeatability_command = build_repeatability_command(config, args)

    result: dict[str, Any] = {
        "worker_index": config.index,
        "worker_name": config.name,
        "dashboard_port": config.dashboard_port,
        "dashboard_url": config.dashboard_url,
        "ros_domain_id": config.ros_domain_id,
        "runtime_dir": str(config.runtime_dir),
        "dashboard_log_path": str(config.dashboard_log_path),
        "repeatability_log_path": str(config.repeatability_log_path),
        "worker_campaign_id": config.worker_campaign_id,
        "generated_utc": utc_now(),
        "pass": False,
        "interrupted": False,
        "error": "",
        "repeatability_return_code": None,
        "worker_summary_path": "",
        "worker_summary": {},
    }

    dashboard_env = dict(os.environ)
    dashboard_env.setdefault("CHASECAR_DASHBOARD_CONTROL_MODE", "host_powershell")
    dashboard_env["PYTHONUNBUFFERED"] = "1"
    dashboard_env["ROS_DOMAIN_ID"] = str(config.ros_domain_id)
    dashboard_env["RUNTIME_TARGET"] = str(args.runtime_target)
    dashboard_env["WORLD_FILE"] = str(args.world_file)
    dashboard_env["GATE_PERF_PROFILE"] = str(args.gate_perf_profile)

    try:
        with config.dashboard_log_path.open("w", encoding="utf-8") as dashboard_log:
            dashboard_proc = subprocess.Popen(
                dashboard_command,
                cwd=str(REPO_ROOT),
                env=dashboard_env,
                stdout=dashboard_log,
                stderr=subprocess.STDOUT,
                text=True,
            )
        wait_for_dashboard(config.dashboard_url, timeout_s=args.dashboard_ready_timeout_s)
        if STOP_REQUESTED.is_set():
            raise RuntimeError("Interrupted before repeatability run started.")

        repeatability_proc = subprocess.run(
            repeatability_command,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        repeatability_output = (repeatability_proc.stdout or "") + ("\n" + repeatability_proc.stderr if repeatability_proc.stderr else "")
        config.repeatability_log_path.write_text(repeatability_output, encoding="utf-8")
        worker_summary_path = parse_marker(repeatability_output, "VISIT_MISSION_REPEATABILITY_SUMMARY=")
        worker_summary = read_json(Path(worker_summary_path)) if worker_summary_path else {}
        result.update(
            repeatability_return_code=repeatability_proc.returncode,
            worker_summary_path=worker_summary_path,
            worker_summary=worker_summary,
        )
        result["pass"] = bool(worker_summary.get("promotion_gate_pass")) if isinstance(worker_summary, dict) else False
        if repeatability_proc.returncode not in {0, 2} and not result["pass"]:
            result["error"] = f"repeatability runner failed with exit code {repeatability_proc.returncode}"
    except Exception as exc:
        result["error"] = str(exc)
        result["interrupted"] = STOP_REQUESTED.is_set()
    finally:
        try:
            http_json(f"{config.dashboard_url}/api/env/stop", method="POST", timeout_s=10.0)
        except Exception:
            pass
        wait_for_environment_stop(config.dashboard_url, timeout_s=args.environment_stop_timeout_s)
        terminate_process(dashboard_proc)

    return result


def main() -> int:
    install_signal_handlers()
    args = parse_args()
    campaign_id = args.campaign_id.strip() or current_utc_stamp()
    campaign_root = ensure_dir(REPO_ROOT / "artifacts" / "session" / campaign_id / "route_planning_parallel_soak")
    worker_configs = build_worker_configs(args, campaign_id=campaign_id, campaign_root=campaign_root)

    worker_results: list[dict[str, Any]] = []
    max_workers = min(len(worker_configs), max(args.workers, 1))
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="route-soak") as executor:
        future_map = {executor.submit(run_worker, config, args): config for config in worker_configs}
        for future in as_completed(future_map):
            worker_results.append(future.result())

    worker_results.sort(key=lambda item: int(item.get("worker_index", 0) or 0))
    total_runs = max(args.runs_per_worker, 1) * len(worker_results)
    passed_workers = sum(1 for item in worker_results if bool(item.get("pass")))
    summary = {
        "generated_utc": utc_now(),
        "type": "route_planning_parallel_soak",
        "campaign_id": campaign_id,
        "scenario_id": args.scenario_id,
        "scenario_label": args.scenario_label,
        "workers_requested": max(args.workers, 1),
        "workers_started": len(worker_results),
        "runs_per_worker": max(args.runs_per_worker, 1),
        "total_runs_requested": total_runs,
        "passed_workers": passed_workers,
        "failed_workers": len(worker_results) - passed_workers,
        "promotion_gate_pass": passed_workers == len(worker_results) and len(worker_results) > 0,
        "worker_results": worker_results,
    }
    summary_path = campaign_root / "campaign_summary.json"
    write_json(summary_path, summary)
    print(f"ROUTE_PLANNING_PARALLEL_SOAK_SUMMARY={summary_path}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    if STOP_REQUESTED.is_set():
        return 130
    return 0 if summary["promotion_gate_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
