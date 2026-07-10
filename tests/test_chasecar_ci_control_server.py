import ast
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

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


def _aruco_scene(markers):
    """Build a 320x240 RGB scene from (marker_id, x, y, size_px) tuples."""
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    scene = np.full((240, 320), 255, dtype=np.uint8)
    for marker_id, x, y, size_px in markers:
        marker = cv2.aruco.generateImageMarker(dictionary, marker_id, size_px)
        scene[y:y + size_px, x:x + size_px] = marker
    return np.repeat(scene[:, :, None], 3, axis=2)


def test_aruco_target_detector_recovers_centered_metric_pose():
    detector = control_server.ArucoTargetDetector(
        cv2_module=cv2,
        np_module=np,
        dictionary_name="DICT_4X4_50",
        marker_id=0,
        marker_size_m=0.10,
        focal_px=225.317,
    )

    target = detector.detect(_aruco_scene([(0, 80, 40, 160)]))

    assert target["id"] == 0
    assert target["dictionary"] == "DICT_4X4_50"
    assert target["pose_status"] == "metric"
    assert target["pose_method"] == "aruco_ippe_square_empirical_intrinsics"
    assert abs(target["center_error"]) < 0.01
    assert abs(target["bearing_rad"]) < 0.01
    assert 0.13 < target["z_m"] < 0.16
    assert target["distance_m"] >= target["z_m"]
    assert target["calibration"]["source"] == "mono_distance_calibration_bench01"
    assert target["limits"]
    assert json.loads(json.dumps(target))["pose_status"] == "metric"


def test_aruco_target_detector_selects_configured_id_and_preserves_bearing_sign():
    detector = control_server.ArucoTargetDetector(
        cv2_module=cv2,
        np_module=np,
        marker_id=0,
        marker_size_m=0.10,
        focal_px=225.317,
    )

    target = detector.detect(_aruco_scene([(7, 20, 70, 90), (0, 210, 70, 90)]))

    assert target["id"] == 0
    assert target["center_px"][0] > 160.0
    assert target["center_error"] > 0.0
    assert target["bearing_rad"] > 0.0
    assert detector.detect(_aruco_scene([(7, 115, 75, 90)])) is None


def test_status_payload_serves_target_with_its_own_freshness(monkeypatch):
    target = {"id": 0, "bearing_rad": 0.25, "pose_status": "metric"}
    with control_server.cam_lock:
        original_cam = dict(control_server.cam)
        control_server.cam.update({
            "det": {"confidence": 0.9},
            "ts": 123.0,
            "err": "",
            "target": target,
            "target_ts": 122.5,
            "target_err": "",
        })
    monkeypatch.setattr(
        control_server,
        "bridge_get",
        lambda path, timeout=5: (200, json.dumps({"motion_enabled": False}).encode(), "application/json"),
    )

    try:
        payload = control_server.build_status_payload()
    finally:
        with control_server.cam_lock:
            control_server.cam.clear()
            control_server.cam.update(original_cam)

    assert payload["target"] == target
    assert payload["target_ts"] == 122.5
    assert payload["target_err"] == ""
    assert payload["det_ts"] == 123.0
    assert payload["motion_enabled"] is False


def test_dashboard_exposes_live_center_error_for_operator_setup():
    assert "s.det.center_error" in control_server.DASH
    assert "err=" in control_server.DASH


def test_acquire_only_command_preserves_arc_gains_and_disables_push():
    command = control_server.build_approach_command("arc", push_steps=0)

    assert command[command.index("--push-steps") + 1] == "0"
    assert command[command.index("--steering") + 1] == "arc"
    assert command[command.index("--turn-gate") + 1] == "0.55"
    assert command[command.index("--detector") + 1] == "trt"


def test_dashboard_fetch_command_keeps_bounded_push_default():
    command = control_server.build_approach_command("pulse")

    assert command[command.index("--push-steps") + 1] == "10"
    assert "--steering" not in command
