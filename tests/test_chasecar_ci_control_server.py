import ast
import subprocess
from pathlib import Path

import chasecar_bridge_control_server as control_server


ROOT = Path(__file__).resolve().parents[1]
CONTROL_SERVER = ROOT / "tools" / "robot_factory_bridge" / "chasecar_bridge_control_server.py"


def _literal_number(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    raise AssertionError("timeout must be a numeric literal for CI auditability")


def test_remote_pkill_uses_self_excluding_pattern(monkeypatch):
    captured = {}

    def fake_run(cmd, cwd=None, capture_output=False, timeout=None):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["capture_output"] = capture_output
        captured["timeout"] = timeout
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(control_server.subprocess, "run", fake_run)

    result = control_server.remote_pkill_fetch("ci-test", timeout=3.0)

    assert result["ok"] is True
    assert captured["cmd"][0] == "ssh"
    assert "ConnectTimeout=5" in captured["cmd"]
    assert captured["timeout"] == 3.0
    remote_command = captured["cmd"][-1]
    assert "chasecar_onboard_fetc[h]" in remote_command
    assert "chasecar_onboard_fetch.py" not in remote_command


def test_remote_pkill_timeout_call_sites_are_bounded_for_ssh_cleanup():
    tree = ast.parse(CONTROL_SERVER.read_text(encoding="utf-8"))
    default_timeout = None
    call_timeouts = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "remote_pkill_fetch":
            defaults = dict(zip([arg.arg for arg in node.args.args[-len(node.args.defaults):]], node.args.defaults))
            default_timeout = _literal_number(defaults["timeout"])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "remote_pkill_fetch":
            timeout_kw = [kw.value for kw in node.keywords if kw.arg == "timeout"]
            assert timeout_kw, "remote_pkill_fetch call on line %d must pass timeout=" % node.lineno
            call_timeouts.append((node.lineno, _literal_number(timeout_kw[0])))

    assert default_timeout is not None
    assert default_timeout >= 3.0
    assert call_timeouts
    too_short = [(line, value) for line, value in call_timeouts if value < 3.0]
    assert not too_short


def test_bridge_post_returns_failure_tuple_for_unreachable_bridge(monkeypatch):
    def fail_urlopen(_req, timeout=None):
        raise OSError("unroutable test URL")

    monkeypatch.setattr(control_server, "BRIDGE", "http://192.0.2.1:9")
    monkeypatch.setattr(control_server.urllib.request, "urlopen", fail_urlopen)

    ok, body = control_server.bridge_post("/motion", {"enabled": False}, timeout=0.05)

    assert ok is False
    assert isinstance(body, bytes)
    assert b"unroutable test URL" in body
