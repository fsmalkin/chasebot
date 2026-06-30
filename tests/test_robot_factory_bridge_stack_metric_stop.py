from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_TOOLS_DIR = REPO_ROOT / "tools" / "robot_factory_bridge"
if str(BRIDGE_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_TOOLS_DIR))

import chasecar_bridge_stack_path_gate as gate  # noqa: E402

PLAN = {"preferred_intent": "plan_to_target", "stage": "plan"}


def _args(stop_distance=0.0):
    a = gate.build_parser().parse_args([])
    a.stack_forward_stop_distance_m = stop_distance
    return a


def _analysis(z=None, status="metric", area=0.0):
    a = {
        "detected": True,
        "centered": True,
        "center_error": 0.0,
        "area_ratio": area,
        "bbox_height_ratio": 0.0,
        "recommendation": {"linear_x": 0.0, "angular_z": 0.0},
    }
    if z is not None:
        a["object_pose"] = {"z_m_forward": z, "pose_status": status}
    return a


def test_metric_stop_fires_within_distance():
    cmd, _issues, reason = gate.stack_command_from_policy(_analysis(z=0.35), PLAN, _args(stop_distance=0.40))
    assert reason == "target_inside_stack_forward_stop_distance"
    assert cmd == {"linear_x": 0.0, "angular_z": 0.0}
    assert gate.safe_terminal_zero_stop(reason, cmd) is True


def test_metric_stop_keeps_approaching_when_beyond_distance():
    cmd, _issues, reason = gate.stack_command_from_policy(_analysis(z=0.60, area=0.0), PLAN, _args(stop_distance=0.40))
    assert reason == "fetch_to_pose_approach_command"
    assert cmd["linear_x"] > 0.0


def test_disabled_by_default_preserves_legacy_path():
    # stop_distance 0.0 (default) -> metric stop never engages, even with a close pose
    cmd, _issues, reason = gate.stack_command_from_policy(_analysis(z=0.20, area=0.0), PLAN, _args(stop_distance=0.0))
    assert reason == "fetch_to_pose_approach_command"
    assert cmd["linear_x"] > 0.0


def test_bearing_only_pose_does_not_trigger_metric_stop():
    cmd, _issues, reason = gate.stack_command_from_policy(
        _analysis(z=0.20, status="bearing_only", area=0.0), PLAN, _args(stop_distance=0.40)
    )
    assert reason == "fetch_to_pose_approach_command"


def test_area_stop_still_works_when_no_pose():
    cmd, _issues, reason = gate.stack_command_from_policy(_analysis(z=None, area=0.60), PLAN, _args(stop_distance=0.40))
    assert reason == "target_inside_stack_forward_stop_area"
    assert cmd == {"linear_x": 0.0, "angular_z": 0.0}


def test_distance_reason_is_a_safe_terminal_stop():
    assert "target_inside_stack_forward_stop_distance" in gate.SAFE_TERMINAL_ZERO_STOP_REASONS


def _calib_file(tmp_path):
    import json
    summary = {
        "object_size_m": 0.0427,
        "fits": {"equiv_diameter_px": {"pass": True, "K_px_m": 9.62, "sigma_s_px": 1.7,
                                       "max_calibrated_range_m": 0.9, "object_size_m": 0.0427}},
    }
    p = tmp_path / "calibration_summary.json"
    p.write_text(json.dumps(summary), encoding="utf-8")
    return str(p)


def test_attach_object_pose_populates_for_yolo_when_configured(tmp_path):
    args = SimpleNamespace(calibration=_calib_file(tmp_path), stack_forward_stop_distance_m=0.40)
    analysis = {"detected": True, "target_profile": "yolo_onnx:sports ball",
                "bbox": {"x0": 150, "y0": 100, "x1": 175, "y1": 124}, "center_error": 0.0, "image_width": 320}
    gate.attach_object_pose(analysis, args)
    assert "object_pose" in analysis
    assert analysis["object_pose"]["pose_status"] in ("metric", "bearing_only")
    assert analysis["object_pose"]["z_m_forward"] is not None


def test_attach_object_pose_noop_when_disabled():
    args = SimpleNamespace(calibration="", stack_forward_stop_distance_m=0.0)
    analysis = {"detected": True, "target_profile": "yolo_onnx",
                "bbox": {"x0": 150, "y0": 100, "x1": 175, "y1": 124}, "center_error": 0.0}
    gate.attach_object_pose(analysis, args)
    assert "object_pose" not in analysis


def test_attach_object_pose_skips_color_backend(tmp_path):
    args = SimpleNamespace(calibration=_calib_file(tmp_path), stack_forward_stop_distance_m=0.40)
    analysis = {"detected": True, "target_profile": "bright",
                "bbox": {"x0": 150, "y0": 100, "x1": 175, "y1": 124}, "center_error": 0.0}
    gate.attach_object_pose(analysis, args)
    assert "object_pose" not in analysis
