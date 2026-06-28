from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_TOOLS_DIR = REPO_ROOT / "tools" / "robot_factory_bridge"
if str(BRIDGE_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_TOOLS_DIR))

import chasecar_bridge_visual_fetch_controller as ctrl  # noqa: E402

CFG = ctrl.default_config()  # standoff 0.40m, k 9.62 -> standoff at equiv ~24px


def obs(detected=True, equiv=12.0, ce=0.0, conf=0.9):
    return {"detected": detected, "equiv_diameter_px": equiv, "center_error": ce, "confidence": conf}


def state(step=0, fwd=0, lost=0):
    return {"step": step, "forward_steps": fwd, "lost_count": lost}


def test_forward_when_centered_and_beyond_standoff():
    d = ctrl.decide_fetch_action(obs(equiv=12.0, ce=0.05), state(), CFG)  # z~0.80
    assert d["action"] == ctrl.ACT_FORWARD
    assert d["linear_x"] > 0.0


def test_turn_toward_center_sign():
    right = ctrl.decide_fetch_action(obs(equiv=12.0, ce=0.4), state(), CFG)
    left = ctrl.decide_fetch_action(obs(equiv=12.0, ce=-0.4), state(), CFG)
    assert right["action"] == ctrl.ACT_TURN and right["angular_z"] < 0.0
    assert left["action"] == ctrl.ACT_TURN and left["angular_z"] > 0.0


def test_stop_at_standoff():
    d = ctrl.decide_fetch_action(obs(equiv=30.0, ce=0.0), state(), CFG)  # z~0.32 <= 0.40
    assert d["action"] == ctrl.ACT_STOP and d["reason"] == "standoff_reached"


def test_standoff_takes_priority_over_offcenter():
    # already at standoff AND off-center -> still stop (don't keep maneuvering closer)
    d = ctrl.decide_fetch_action(obs(equiv=30.0, ce=0.5), state(), CFG)
    assert d["action"] == ctrl.ACT_STOP and d["reason"] == "standoff_reached"


def test_forward_budget_is_a_hard_stop():
    d = ctrl.decide_fetch_action(obs(equiv=12.0, ce=0.0), state(fwd=CFG["forward_budget"]), CFG)
    assert d["action"] == ctrl.ACT_STOP and d["reason"] == "forward_budget_exhausted"


def test_hold_when_not_detected_under_limit():
    d = ctrl.decide_fetch_action(obs(detected=False), state(lost=1), CFG)
    assert d["action"] == ctrl.ACT_HOLD and d["lost_count"] == 2


def test_stop_when_lost_over_limit():
    d = ctrl.decide_fetch_action(obs(detected=False), state(lost=CFG["lost_limit"]), CFG)
    assert d["action"] == ctrl.ACT_STOP and d["reason"] == "lost_target"


def test_stop_at_max_steps():
    d = ctrl.decide_fetch_action(obs(), state(step=CFG["max_steps"]), CFG)
    assert d["action"] == ctrl.ACT_STOP and d["reason"] == "max_steps_reached"


def test_zero_size_holds():
    d = ctrl.decide_fetch_action(obs(equiv=0.0), state(), CFG)
    assert d["action"] == ctrl.ACT_HOLD


def test_low_confidence_detection_is_treated_as_miss():
    d = ctrl.decide_fetch_action(obs(equiv=12.0, ce=0.0, conf=0.10), state(lost=0), CFG)
    assert d["action"] == ctrl.ACT_HOLD
    assert d["reason"] == "low_confidence"
    assert d["lost_count"] == 1  # accrues toward lost_target, never acts on it


def test_low_confidence_flicker_eventually_stops():
    # sustained low-confidence flicker must trip lost_target, not drive forward forever
    d = ctrl.decide_fetch_action(obs(equiv=12.0, ce=0.0, conf=0.10), state(lost=CFG["lost_limit"]), CFG)
    assert d["action"] == ctrl.ACT_STOP and d["reason"] == "lost_target"


def test_never_forward_unless_detected_centered_and_confident():
    # property sweep: forward only when detected, confident, centered, beyond standoff, budget left
    for det in (True, False):
        for conf in (0.0, 0.1, 0.5):
            for equiv in (0.0, 12.0, 30.0):
                for ce in (-0.5, 0.0, 0.3):
                    for fwd in (0, CFG["forward_budget"]):
                        d = ctrl.decide_fetch_action(obs(det, equiv, ce, conf), state(fwd=fwd), CFG)
                        if d["action"] == ctrl.ACT_FORWARD:
                            z = CFG["k_px_m"] / equiv
                            assert det is True
                            assert conf >= CFG["min_confidence"]
                            assert abs(ce) <= CFG["center_deadband"]
                            assert z > CFG["standoff_m"]
                            assert fwd < CFG["forward_budget"]
