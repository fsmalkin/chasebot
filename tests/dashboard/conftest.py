from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_URL = "http://127.0.0.1:8860"
STATE_PATH = REPO_ROOT / "runtime" / "dashboard" / "dashboard_service_state.json"
PYTEST_RESULTS: list[dict[str, Any]] = []


def port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


def read_dashboard_state_file() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    text = STATE_PATH.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        try:
            payload, _end = json.JSONDecoder().raw_decode(text.lstrip())
        except json.JSONDecodeError:
            return {}
    return payload if isinstance(payload, dict) else {}


@dataclass
class DashboardClient:
    base_url: str

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                body = response.read().decode("utf-8")
                return response.getcode(), json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            return exc.code, json.loads(body) if body else {}

    def state(self) -> dict[str, Any]:
        status, payload = self.request("GET", "/api/state")
        assert status == 200
        return payload

    def wait_for(self, predicate: Callable[[dict[str, Any]], bool], timeout_s: float, message: str) -> dict[str, Any]:
        deadline = time.time() + timeout_s
        last_state: dict[str, Any] = {}
        while time.time() < deadline:
            last_state = self.state()
            if predicate(last_state):
                return last_state
            time.sleep(1.0)
        raise AssertionError(f"{message}\nLast state: {json.dumps(last_state, indent=2, sort_keys=True)}")


@pytest.fixture(scope="session")
def dashboard_service():
    proc = None
    if not port_open("127.0.0.1", 8860):
        env = dict(os.environ)
        env.setdefault("CHASECAR_DASHBOARD_CONTROL_MODE", "host_powershell")
        proc = subprocess.Popen(
            ["python", "scripts/dashboard_service.py", "--host", "127.0.0.1", "--port", "8860"],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 60
        while time.time() < deadline:
            if port_open("127.0.0.1", 8860):
                break
            time.sleep(1.0)
        else:
            raise RuntimeError("dashboard service did not start")
    yield
    if proc is not None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="session")
def dashboard_client(dashboard_service) -> DashboardClient:
    return DashboardClient(base_url=BASE_URL)


def pytest_addoption(parser):  # type: ignore[no-untyped-def]
    parser.addoption("--run-live", action="store_true", default=False, help="Run live sim integration tests")


def pytest_runtest_makereport(item, call):  # type: ignore[no-untyped-def]
    if call.when != "call":
        return
    PYTEST_RESULTS.append(
        {
            "nodeid": item.nodeid,
            "outcome": call.excinfo.typename if call.excinfo else "passed",
            "passed": call.excinfo is None,
        }
    )


def pytest_sessionfinish(session, exitstatus):  # type: ignore[no-untyped-def]
    state = {}
    try:
        with urllib.request.urlopen(f"{BASE_URL}/api/state", timeout=10) as response:
            state = json.loads(response.read().decode("utf-8"))
    except Exception:
        state = read_dashboard_state_file()

    session_id = str(state.get("session_id", "")).strip()
    if not session_id:
        return
    summary_path = REPO_ROOT / "artifacts" / "session" / session_id / "dashboard_validation" / "pytest_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "exitstatus": exitstatus,
        "pass": exitstatus == 0,
        "session_id": session_id,
        "compose_project": state.get("compose_project", ""),
        "results": PYTEST_RESULTS,
    }
    summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
