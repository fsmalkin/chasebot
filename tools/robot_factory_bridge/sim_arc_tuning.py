#!/usr/bin/env python3
"""Offline arc-drive tuning harness for the JetBot Mini onboard fetch loop.

This is an honest lightweight model calibrated to measured bench constants,
not a fit to motion logs. It imports the real onboard controller helpers and
wraps them in a kinematic simulator with stiction, command refresh/expiry,
actuation latency, camera projection, delayed perception, pixel noise, and
dropout.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np


THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[1]
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import chasecar_onboard_fetch as onboard  # noqa: E402


STATIC_STICTION_CMD = 0.30
ROLLING_STICTION_CMD = 0.18
TURN_ANGULAR_Z = 2.3
BRIDGE_MAX_LINEAR_X = 0.6
BRIDGE_MAX_ANGULAR_Z = 2.5
BRIDGE_MAX_MOTOR_SPEED = 0.35
BRIDGE_TURN_GAIN = 1.0
WHEELBASE_M = 0.13
MAX_LINEAR_SPEED_MPS = 0.46
COMMAND_EXPIRY_S = 0.45
REFRESH_HZ = 10.0
PERCEPTION_HZ = 15.0
CONTROLLER_HZ = 8.0
PERCEPTION_LATENCY_S = 0.08
CAMERA_WIDTH_PX = 320
HFOV_DEG = 62.0
PIXEL_NOISE_SIGMA = 1.5
DROPOUT_PROBABILITY = 0.10
K_PX_M = 9.621
STANDOFF_M = 0.35
ACTUATION_LATENCY_S = 0.05
DT_S = 0.02
MAX_TIME_S = 12.0
FORWARD_BUDGET = 180
MAX_STEPS = 260

DEFAULT_KP_VALUES = [0.30, 0.50, 0.70, 0.90, 1.10]
DEFAULT_KD_VALUES = [0.00, 0.10, 0.15, 0.25]
DEFAULT_SLEW_VALUES = [1.00, 1.50, 2.00]
DEFAULT_TURN_GATE_VALUES = [0.22, 0.35, 0.45, 0.55]
DEFAULT_EPISODES = 16
DEFAULT_SEED = 20260703


@dataclass(frozen=True)
class SimConstants:
    static_stiction_cmd: float = STATIC_STICTION_CMD
    rolling_stiction_cmd: float = ROLLING_STICTION_CMD
    turn_angular_z: float = TURN_ANGULAR_Z
    bridge_max_linear_x: float = BRIDGE_MAX_LINEAR_X
    bridge_max_angular_z: float = BRIDGE_MAX_ANGULAR_Z
    bridge_max_motor_speed: float = BRIDGE_MAX_MOTOR_SPEED
    bridge_turn_gain: float = BRIDGE_TURN_GAIN
    wheelbase_m: float = WHEELBASE_M
    max_linear_speed_mps: float = MAX_LINEAR_SPEED_MPS
    command_expiry_s: float = COMMAND_EXPIRY_S
    refresh_hz: float = REFRESH_HZ
    perception_hz: float = PERCEPTION_HZ
    controller_hz: float = CONTROLLER_HZ
    perception_latency_s: float = PERCEPTION_LATENCY_S
    reuse_latest_observation: bool = False
    camera_width_px: int = CAMERA_WIDTH_PX
    hfov_deg: float = HFOV_DEG
    pixel_noise_sigma: float = PIXEL_NOISE_SIGMA
    dropout_probability: float = DROPOUT_PROBABILITY
    k_px_m: float = K_PX_M
    standoff_m: float = STANDOFF_M
    actuation_latency_s: float = ACTUATION_LATENCY_S
    dt_s: float = DT_S
    max_time_s: float = MAX_TIME_S
    forward_budget: int = FORWARD_BUDGET
    max_steps: int = MAX_STEPS


@dataclass(frozen=True)
class Placement:
    range_m: float
    bearing_right_rad: float

    @property
    def ball_xy(self) -> tuple[float, float]:
        return (
            self.range_m * math.cos(self.bearing_right_rad),
            -self.range_m * math.sin(self.bearing_right_rad),
        )


def clamp(value: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(value)))


def bridge_cmd_vel_to_motors(linear_x: float, angular_z: float, constants: SimConstants) -> tuple[float, float]:
    """Mirror factory bridge cmd_vel mapping before wheel stiction.

    Source: tools/robot_factory_bridge/chasecar_factory_bridge.py:1130-1149.
    """
    max_linear = max(0.001, abs(float(constants.bridge_max_linear_x)))
    max_angular = max(0.001, abs(float(constants.bridge_max_angular_z)))
    linear_unit = clamp(float(linear_x) / max_linear, -1.0, 1.0)
    angular_unit = clamp(float(angular_z) / max_angular, -1.0, 1.0)

    left = linear_unit - (float(constants.bridge_turn_gain) * angular_unit)
    right = linear_unit + (float(constants.bridge_turn_gain) * angular_unit)
    max_abs = max(1.0, abs(left), abs(right))
    left = left / max_abs
    right = right / max_abs

    max_speed = clamp(abs(float(constants.bridge_max_motor_speed)), 0.0, 1.0)
    left = clamp(left, -1.0, 1.0) * max_speed
    right = clamp(right, -1.0, 1.0) * max_speed
    return clamp(left, -1.0, 1.0), clamp(right, -1.0, 1.0)


class RobotKinematics:
    def __init__(self, constants: SimConstants):
        self.c = constants
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.left_motor_cmd = 0.0
        self.right_motor_cmd = 0.0
        self.left_eff = 0.0
        self.right_eff = 0.0

    def _wheel_effective(self, cmd: float, previous: float) -> float:
        threshold = self.c.rolling_stiction_cmd if abs(previous) > 1.0e-6 else self.c.static_stiction_cmd
        if abs(cmd) < threshold:
            return 0.0
        return float(cmd)

    def step(self, linear_x: float, angular_z: float, dt: float) -> tuple[float, float]:
        left_cmd, right_cmd = bridge_cmd_vel_to_motors(linear_x, angular_z, self.c)
        self.left_motor_cmd = left_cmd
        self.right_motor_cmd = right_cmd
        self.left_eff = self._wheel_effective(left_cmd, self.left_eff)
        self.right_eff = self._wheel_effective(right_cmd, self.right_eff)

        max_motor = max(0.001, abs(float(self.c.bridge_max_motor_speed)))
        v = self.c.max_linear_speed_mps * (self.left_eff + self.right_eff) / (2.0 * max_motor)
        omega = self.c.turn_angular_z * (self.right_eff - self.left_eff) / (2.0 * max_motor)
        self.x += v * math.cos(self.yaw) * dt
        self.y += v * math.sin(self.yaw) * dt
        self.yaw = normalize_angle(self.yaw + omega * dt)
        return v, omega


class CommandPipeline:
    def __init__(self, constants: SimConstants):
        self.c = constants
        self.setpoint = (0.0, 0.0)
        self.last_set_t = -999.0
        self.next_refresh_t = 0.0
        self.queue: list[tuple[float, float, float, float]] = []
        self.applied = (0.0, 0.0)
        self.applied_until = -999.0

    def set(self, linear_x: float, angular_z: float, t: float) -> None:
        self.setpoint = (float(linear_x), float(angular_z))
        self.last_set_t = float(t)

    def zero(self, t: float) -> None:
        self.set(0.0, 0.0, t)

    def command_at(self, t: float) -> tuple[float, float]:
        period = 1.0 / self.c.refresh_hz
        while self.next_refresh_t <= t + 1.0e-9:
            age = self.next_refresh_t - self.last_set_t
            if age <= self.c.command_expiry_s:
                lx, az = self.setpoint
            else:
                lx, az = 0.0, 0.0
            self.queue.append((self.next_refresh_t + self.c.actuation_latency_s, lx, az, self.next_refresh_t))
            self.next_refresh_t += period

        ready = [item for item in self.queue if item[0] <= t + 1.0e-9]
        self.queue = [item for item in self.queue if item[0] > t + 1.0e-9]
        for _apply_t, lx, az, publish_t in ready:
            self.applied = (lx, az)
            self.applied_until = publish_t + self.c.command_expiry_s
        if t > self.applied_until:
            return 0.0, 0.0
        return self.applied


class PerceptionPipeline:
    def __init__(self, constants: SimConstants, rng: np.random.Generator, ball_xy: tuple[float, float]):
        self.c = constants
        self.rng = rng
        self.ball_xy = ball_xy
        self.next_capture_t = 0.0
        self.samples: list[tuple[float, dict[str, Any]]] = []

    def _project(self, robot: RobotKinematics) -> dict[str, Any]:
        dx = self.ball_xy[0] - robot.x
        dy = self.ball_xy[1] - robot.y
        range_m = math.hypot(dx, dy)
        forward = math.cos(robot.yaw) * dx + math.sin(robot.yaw) * dy
        left = -math.sin(robot.yaw) * dx + math.cos(robot.yaw) * dy
        right = -left
        if forward <= 0.05:
            return {"detected": False}
        bearing_right = math.atan2(right, forward)
        half_hfov = math.radians(self.c.hfov_deg) / 2.0
        center_error = bearing_right / half_hfov
        if abs(center_error) > 1.08:
            return {"detected": False}
        if float(self.rng.random()) < self.c.dropout_probability:
            return {"detected": False}
        sigma_center = self.c.pixel_noise_sigma / (self.c.camera_width_px / 2.0)
        noisy_center = center_error + float(self.rng.normal(0.0, sigma_center))
        noisy_size = self.c.k_px_m / max(range_m, 1.0e-6) + float(self.rng.normal(0.0, self.c.pixel_noise_sigma))
        return {
            "detected": True,
            "confidence": 0.92,
            "center_error": max(-1.2, min(1.2, noisy_center)),
            "equiv_diameter_px": max(1.0, noisy_size),
        }

    def maybe_capture(self, t: float, robot: RobotKinematics) -> None:
        period = 1.0 / self.c.perception_hz
        while self.next_capture_t <= t + 1.0e-9:
            self.samples.append((self.next_capture_t + self.c.perception_latency_s, self._project(robot)))
            self.next_capture_t += period

    def observations_ready(self, t: float) -> list[dict[str, Any]]:
        ready = [sample for deliver_t, sample in self.samples if deliver_t <= t + 1.0e-9]
        self.samples = [(deliver_t, sample) for deliver_t, sample in self.samples if deliver_t > t + 1.0e-9]
        return ready


def normalize_angle(a: float) -> float:
    while a > math.pi:
        a -= 2.0 * math.pi
    while a < -math.pi:
        a += 2.0 * math.pi
    return a


def true_center_error(robot: RobotKinematics, ball_xy: tuple[float, float], constants: SimConstants) -> float | None:
    dx = ball_xy[0] - robot.x
    dy = ball_xy[1] - robot.y
    forward = math.cos(robot.yaw) * dx + math.sin(robot.yaw) * dy
    if forward <= 0.0:
        return None
    left = -math.sin(robot.yaw) * dx + math.cos(robot.yaw) * dy
    right = -left
    return math.atan2(right, forward) / (math.radians(constants.hfov_deg) / 2.0)


def true_forward_range(robot: RobotKinematics, ball_xy: tuple[float, float]) -> float:
    dx = ball_xy[0] - robot.x
    dy = ball_xy[1] - robot.y
    return math.cos(robot.yaw) * dx + math.sin(robot.yaw) * dy


def true_range(robot: RobotKinematics, ball_xy: tuple[float, float]) -> float:
    """Physical robot-to-ball range, independent of camera heading."""
    dx = ball_xy[0] - robot.x
    dy = ball_xy[1] - robot.y
    return math.hypot(dx, dy)


def generate_placements(seed: int, episodes: int) -> list[Placement]:
    rng = np.random.default_rng(int(seed))
    placements = []
    for _i in range(int(episodes)):
        distance = float(rng.uniform(0.5, 2.5))
        bearing = math.radians(float(rng.uniform(-25.0, 25.0)))
        placements.append(Placement(distance, bearing))
    return placements


def make_cfg(constants: SimConstants) -> dict[str, Any]:
    return onboard.default_config(
        k_px_m=constants.k_px_m,
        standoff_m=constants.standoff_m,
        center_deadband=0.12,
        turn_angular_z=constants.turn_angular_z,
        approach_linear_x=0.55,
        min_confidence=0.20,
        lost_limit=12,
        forward_budget=constants.forward_budget,
        max_steps=constants.max_steps,
    )


def _arc_args(kp: float, kd: float, slew: float, turn_gate: float = 0.22) -> SimpleNamespace:
    return SimpleNamespace(kp=float(kp), kd=float(kd), slew=float(slew), turn_gate=float(turn_gate), coast_s=0.8)


def _legacy_compute_arc_drive_command(
    err: float,
    err_rate: float,
    cfg: dict[str, Any],
    kp: float,
    kd: float,
    slew: float,
    dt: float,
    prev_lx: float,
    prev_az: float,
) -> tuple[float, float, float, float]:
    turn_scale = float(cfg["turn_angular_z"])
    angular_target = -(float(kp) * float(err) + float(kd) * float(err_rate)) * turn_scale
    angular_target = max(-2.5, min(2.5, angular_target))
    if abs(float(err)) < (float(cfg["center_deadband"]) / 2.0):
        angular_target = 0.0
    linear_target = float(cfg["approach_linear_x"]) * max(0.35, 1.0 - abs(float(err)))
    linear = onboard.slew_value(prev_lx, linear_target, slew, dt)
    angular = onboard.slew_value(prev_az, angular_target, slew, dt)
    return linear, angular, linear_target, angular_target


def _legacy_decide_arc_fetch_action(
    obs: dict[str, Any],
    state: dict[str, Any],
    cfg: dict[str, Any],
    tracker: Any,
    args: SimpleNamespace,
    t_now: float,
    prev_lx: float,
    prev_az: float,
    prev_cmd_t: float,
) -> tuple[dict[str, Any], dict[str, Any], float, float, float]:
    if onboard.detection_usable(obs, cfg):
        est = tracker.update(obs, t_now)
    else:
        est = tracker.predict(t_now)
    if est is None or float(est.get("fresh_s", 999.0)) > float(args.coast_s):
        d = onboard.decide_fetch_action(obs, state, cfg)
        return d, obs, prev_lx, prev_az, prev_cmd_t

    servo_obs = dict(obs)
    servo_obs["detected"] = True
    servo_obs[cfg["size_key"]] = float(est["equiv_diameter_px"])
    servo_obs["equiv_diameter_px"] = float(est["equiv_diameter_px"])
    servo_obs["center_error"] = float(est["center_error"])
    servo_obs["center_rate"] = float(est["center_rate"])
    servo_obs["confidence"] = max(float(obs.get("confidence", 0.0) or 0.0), float(cfg["min_confidence"]))
    servo_obs["coasting"] = bool(est["coasting"])
    servo_obs["fresh_s"] = round(float(est["fresh_s"]), 3)

    step = int(state.get("step", 0))
    if step >= int(cfg["max_steps"]):
        return {"action": onboard.ACT_STOP, "reason": "max_steps_reached"}, servo_obs, prev_lx, prev_az, prev_cmd_t
    size_px = float(servo_obs.get(cfg["size_key"], 0.0) or 0.0)
    if size_px <= 0.0:
        return onboard.decide_fetch_action(obs, state, cfg), obs, prev_lx, prev_az, prev_cmd_t
    z_m = float(cfg["k_px_m"]) / size_px
    if z_m <= float(cfg["standoff_m"]):
        return {"action": onboard.ACT_STOP, "reason": "standoff_reached", "z_m": round(z_m, 4)}, servo_obs, prev_lx, prev_az, prev_cmd_t
    if int(state.get("forward_steps", 0)) >= int(cfg["forward_budget"]):
        return {"action": onboard.ACT_STOP, "reason": "forward_budget_exhausted", "z_m": round(z_m, 4)}, servo_obs, prev_lx, prev_az, prev_cmd_t

    dt = max(0.01, float(t_now) - float(prev_cmd_t))
    lx, az, lx_target, az_target = _legacy_compute_arc_drive_command(
        servo_obs["center_error"], servo_obs.get("center_rate", 0.0), cfg,
        args.kp, args.kd, args.slew, dt, prev_lx, prev_az)
    d = {"action": onboard.ACT_FORWARD, "reason": "arc_approach", "linear_x": lx, "angular_z": az,
         "target_linear_x": round(lx_target, 4), "target_angular_z": round(az_target, 4),
         "z_m": round(z_m, 4), "coasting": bool(est["coasting"]),
         "center_error": round(float(servo_obs["center_error"]), 5),
         "arc_regime": "legacy"}
    return d, servo_obs, lx, az, float(t_now)


def _unbounded_turn_decide_arc_fetch_action(
    obs: dict[str, Any],
    state: dict[str, Any],
    cfg: dict[str, Any],
    tracker: Any,
    args: SimpleNamespace,
    t_now: float,
    prev_lx: float,
    prev_az: float,
    prev_cmd_t: float,
) -> tuple[dict[str, Any], dict[str, Any], float, float, float]:
    """Snapshot the pre-repair two-regime controller for failure reproduction.

    This deliberately preserves the July 9 hard-floor behavior: cached frames
    are treated as fresh, and an in-place turn continues while the tracker
    coasts. Keep it simulator-only so the observed overshoot remains a durable
    regression witness after the onboard controller is repaired.
    """
    if onboard.detection_usable(obs, cfg):
        est = tracker.update(obs, t_now)
    else:
        est = tracker.predict(t_now)
    if est is None or float(est.get("fresh_s", 999.0)) > float(args.coast_s):
        d = onboard.decide_fetch_action(obs, state, cfg)
        return d, obs, prev_lx, prev_az, prev_cmd_t

    servo_obs = dict(obs)
    servo_obs["detected"] = True
    servo_obs[cfg["size_key"]] = float(est["equiv_diameter_px"])
    servo_obs["equiv_diameter_px"] = float(est["equiv_diameter_px"])
    servo_obs["center_error"] = float(est["center_error"])
    servo_obs["center_rate"] = float(est["center_rate"])
    servo_obs["confidence"] = max(float(obs.get("confidence", 0.0) or 0.0), float(cfg["min_confidence"]))
    servo_obs["coasting"] = bool(est["coasting"])
    servo_obs["fresh_s"] = round(float(est["fresh_s"]), 3)

    step = int(state.get("step", 0))
    if step >= int(cfg["max_steps"]):
        return {"action": onboard.ACT_STOP, "reason": "max_steps_reached"}, servo_obs, prev_lx, prev_az, prev_cmd_t
    size_px = float(servo_obs.get(cfg["size_key"], 0.0) or 0.0)
    if size_px <= 0.0:
        return onboard.decide_fetch_action(obs, state, cfg), obs, prev_lx, prev_az, prev_cmd_t
    z_m = float(cfg["k_px_m"]) / size_px
    if z_m <= float(cfg["standoff_m"]):
        return {"action": onboard.ACT_STOP, "reason": "standoff_reached", "z_m": round(z_m, 4)}, servo_obs, prev_lx, prev_az, prev_cmd_t
    if int(state.get("forward_steps", 0)) >= int(cfg["forward_budget"]):
        return {"action": onboard.ACT_STOP, "reason": "forward_budget_exhausted", "z_m": round(z_m, 4)}, servo_obs, prev_lx, prev_az, prev_cmd_t

    dt = max(0.01, float(t_now) - float(prev_cmd_t))
    lx, az, lx_target, az_target = onboard.compute_arc_drive_command(
        servo_obs["center_error"], servo_obs.get("center_rate", 0.0), cfg,
        args.kp, args.kd, args.slew, dt, prev_lx, prev_az, args.turn_gate)
    d = {"action": onboard.ACT_FORWARD, "reason": "arc_approach", "linear_x": lx, "angular_z": az,
         "target_linear_x": round(lx_target, 4), "target_angular_z": round(az_target, 4),
         "z_m": round(z_m, 4), "coasting": bool(est["coasting"]),
         "center_error": round(float(servo_obs["center_error"]), 5),
         "arc_regime": "turn" if abs(float(servo_obs["center_error"])) > float(args.turn_gate) else "forward",
         "turn_gate": round(float(args.turn_gate), 4),
         "linear_floor": round(onboard.arc_forward_linear_floor(), 4)}
    return d, servo_obs, lx, az, float(t_now)


def run_episode(
    placement: Placement,
    mode: str = "arc",
    kp: float = 0.9,
    kd: float = 0.25,
    slew: float = 1.5,
    turn_gate: float = 0.22,
    seed: int = 0,
    constants: SimConstants | None = None,
) -> dict[str, Any]:
    c = constants or SimConstants()
    rng = np.random.default_rng(int(seed))
    ball_xy = placement.ball_xy
    robot = RobotKinematics(c)
    commands = CommandPipeline(c)
    perception = PerceptionPipeline(c, rng, ball_xy)
    cfg = make_cfg(c)
    state = {"step": 0, "forward_steps": 0, "lost_count": 0}
    tracker = onboard.BallTracker()
    args = _arc_args(kp, kd, slew, turn_gate)
    arc_lx = 0.0
    arc_az = 0.0
    arc_cmd_t = 0.0
    controller_blocked_until = 0.0
    next_controller_t = 0.0
    latest_observation: dict[str, Any] | None = None
    discard_after_turn = False
    setpoint_hold_until = -999.0
    stop_reason = "timeout"
    initial_z_m = true_range(robot, ball_xy)
    first_command_t = None
    centered_once = False
    last_center_sign = 0
    overshoots = 0
    trace: list[dict[str, float]] = []

    t = 0.0
    while t <= c.max_time_s + 1.0e-9:
        perception.maybe_capture(t, robot)
        lx_apply, az_apply = commands.command_at(t)
        _v, _omega = robot.step(lx_apply, az_apply, c.dt_s)
        ce_true = true_center_error(robot, ball_xy, c)
        z_true = true_range(robot, ball_xy)
        trace.append(
            {
                "t": round(t, 4),
                "center_error": float(ce_true) if ce_true is not None else 999.0,
                "z_m": float(z_true),
                "linear_x": float(lx_apply),
                "angular_z": float(az_apply),
                "left_motor_cmd": float(robot.left_motor_cmd),
                "right_motor_cmd": float(robot.right_motor_cmd),
                "left_motor_eff": float(robot.left_eff),
                "right_motor_eff": float(robot.right_eff),
            }
        )
        if first_command_t is None and (abs(lx_apply) > 1.0e-6 or abs(az_apply) > 1.0e-6):
            first_command_t = t
        if ce_true is not None:
            if not centered_once and abs(ce_true) < cfg["center_deadband"]:
                centered_once = True
            sign = 1 if ce_true > 0.0 else -1 if ce_true < 0.0 else 0
            if centered_once and sign and last_center_sign and sign != last_center_sign:
                overshoots += 1
            if sign:
                last_center_sign = sign

        if z_true <= c.standoff_m:
            stop_reason = "standoff_reached"
            commands.zero(t)
            break

        observations = perception.observations_ready(t)
        if observations:
            latest_observation = observations[-1]
        controller_due = bool(observations)
        if c.reuse_latest_observation:
            controller_due = latest_observation is not None and t >= next_controller_t - 1.0e-9
            if t >= next_controller_t - 1.0e-9:
                period = 1.0 / max(0.1, float(c.controller_hz))
                while next_controller_t <= t + 1.0e-9:
                    next_controller_t += period
        if (controller_due and latest_observation is not None and t >= controller_blocked_until
                and discard_after_turn):
            discard_after_turn = False
            controller_blocked_until = t + 0.15
        elif controller_due and latest_observation is not None and t >= controller_blocked_until:
            obs = latest_observation
            if mode == "arc":
                decision, _policy_obs, arc_lx, arc_az, arc_cmd_t = onboard.decide_arc_fetch_action(
                    obs, state, cfg, tracker, args, t, arc_lx, arc_az, arc_cmd_t
                )
            elif mode == "arc_unbounded_turn":
                decision, _policy_obs, arc_lx, arc_az, arc_cmd_t = _unbounded_turn_decide_arc_fetch_action(
                    obs, state, cfg, tracker, args, t, arc_lx, arc_az, arc_cmd_t
                )
            elif mode == "arc_legacy":
                decision, _policy_obs, arc_lx, arc_az, arc_cmd_t = _legacy_decide_arc_fetch_action(
                    obs, state, cfg, tracker, args, t, arc_lx, arc_az, arc_cmd_t
                )
            else:
                decision = onboard.decide_fetch_action(obs, state, cfg)
            state["step"] += 1
            if mode in ("arc", "arc_legacy", "arc_unbounded_turn") and decision.get("reason") == "arc_approach":
                state["lost_count"] = 0
            else:
                state["lost_count"] = decision.get("lost_count", 0 if obs.get("detected") else state["lost_count"])

            action = decision["action"]
            if action == onboard.ACT_STOP:
                stop_reason = str(decision.get("reason", "stop"))
                commands.zero(t)
                break
            if action == onboard.ACT_TURN:
                err = abs(float(obs.get("center_error") or 0.0))
                turn_dur = float(decision.get("pulse_s", onboard.turn_pulse_duration(err)))
                commands.set(0.0, decision["angular_z"], t)
                controller_blocked_until = t + turn_dur + 0.30
                setpoint_hold_until = t + turn_dur
                discard_after_turn = True
            elif action == onboard.ACT_FORWARD:
                commands.set(decision.get("linear_x", 0.0), decision.get("angular_z", 0.0), t)
                if not (mode in ("arc", "arc_unbounded_turn") and decision.get("arc_regime") == "turn"):
                    state["forward_steps"] += 1
            elif action == onboard.ACT_HOLD and state.get("lost_count", 0) > 1:
                commands.zero(t)

        if t > setpoint_hold_until and setpoint_hold_until > 0.0:
            commands.zero(t)
            setpoint_hold_until = -999.0

        t += c.dt_s

    angular_tail = [row["angular_z"] for row in trace if row["t"] >= max(0.0, trace[-1]["t"] - 2.0)]
    oscillation_power = float(np.var(angular_tail)) if angular_tail else 0.0
    final_z_m = float(trace[-1]["z_m"])
    initial_size_px = c.k_px_m / max(float(initial_z_m), 1.0e-6)
    final_size_px = c.k_px_m / max(final_z_m, 1.0e-6)
    max_abs_motor_cmd = max(
        max(abs(row["left_motor_cmd"]), abs(row["right_motor_cmd"]))
        for row in trace
    )
    max_abs_effective_motor = max(
        max(abs(row["left_motor_eff"]), abs(row["right_motor_eff"]))
        for row in trace
    )
    return {
        "mode": mode,
        "kp": float(kp),
        "kd": float(kd),
        "slew": float(slew),
        "turn_gate": float(turn_gate),
        "seed": int(seed),
        "range_m": round(placement.range_m, 4),
        "bearing_deg": round(math.degrees(placement.bearing_right_rad), 4),
        "stop_reason": stop_reason,
        "success": bool(stop_reason == "standoff_reached"),
        "time_s": round(float(trace[-1]["t"]), 4),
        "overshoot_count": int(overshoots),
        "oscillation_power": round(oscillation_power, 8),
        "first_command_t": None if first_command_t is None else round(float(first_command_t), 4),
        "initial_z_m": round(float(initial_z_m), 5),
        "final_z_m": round(final_z_m, 5),
        "net_forward_progress_m": round(float(initial_z_m) - final_z_m, 5),
        "initial_equiv_diameter_px": round(initial_size_px, 5),
        "final_equiv_diameter_px": round(final_size_px, 5),
        "max_abs_motor_cmd": round(float(max_abs_motor_cmd), 5),
        "max_abs_effective_motor": round(float(max_abs_effective_motor), 5),
    }


def summarize_episodes(label: str, episodes: list[dict[str, Any]]) -> dict[str, Any]:
    successes = [ep for ep in episodes if ep["success"]]
    fail_rate = 1.0 - (float(len(successes)) / float(len(episodes) or 1))
    times = [float(ep["time_s"]) for ep in successes]
    overshoots = [float(ep["overshoot_count"]) for ep in episodes]
    osc = [float(ep["oscillation_power"]) for ep in episodes]
    return {
        "label": label,
        "episodes": len(episodes),
        "successes": len(successes),
        "failure_rate": round(fail_rate, 6),
        "mean_time_to_standoff_s": round(float(np.mean(times)), 6) if times else None,
        "mean_overshoot_count": round(float(np.mean(overshoots)) if overshoots else 0.0, 6),
        "mean_oscillation_power": round(float(np.mean(osc)) if osc else 0.0, 8),
    }


def score_summary(summary: dict[str, Any]) -> float:
    time_value = summary.get("mean_time_to_standoff_s")
    time_s = 99.0 if time_value is None else float(time_value)
    return (
        100.0 * float(summary["failure_rate"])
        + 2.0 * time_s
        + 4.0 * float(summary["mean_overshoot_count"])
        + 8.0 * float(summary["mean_oscillation_power"])
    )


def run_gain_sweep(
    seed: int = DEFAULT_SEED,
    episodes: int = DEFAULT_EPISODES,
    kp_values: list[float] | None = None,
    kd_values: list[float] | None = None,
    slew_values: list[float] | None = None,
    turn_gate_values: list[float] | None = None,
    constants: SimConstants | None = None,
) -> dict[str, Any]:
    c = constants or SimConstants()
    placements = generate_placements(seed, episodes)
    kp_values = kp_values or list(DEFAULT_KP_VALUES)
    kd_values = kd_values or list(DEFAULT_KD_VALUES)
    slew_values = slew_values or list(DEFAULT_SLEW_VALUES)
    turn_gate_values = turn_gate_values or list(DEFAULT_TURN_GATE_VALUES)
    rows = []
    for kp in kp_values:
        for kd in kd_values:
            for slew in slew_values:
                for turn_gate in turn_gate_values:
                    eps = [
                        run_episode(p, "arc", kp, kd, slew, turn_gate, seed + i * 37, c)
                        for i, p in enumerate(placements)
                    ]
                    summary = summarize_episodes(
                        "arc kp=%.2f kd=%.2f slew=%.2f turn_gate=%.2f" % (kp, kd, slew, turn_gate),
                        eps,
                    )
                    summary.update({"mode": "arc", "kp": kp, "kd": kd, "slew": slew,
                                    "turn_gate": turn_gate, "score": round(score_summary(summary), 6)})
                    rows.append(summary)
    rows.sort(key=lambda row: (row["score"], row["failure_rate"], row["mean_time_to_standoff_s"]))

    pulse_eps = [
        run_episode(p, "pulse", 0.9, 0.25, 1.5, 0.22, seed + i * 37, c)
        for i, p in enumerate(placements)
    ]
    pulse = summarize_episodes("pulse defaults", pulse_eps)
    pulse.update({"mode": "pulse", "kp": None, "kd": None, "slew": None, "turn_gate": None,
                  "score": round(score_summary(pulse), 6)})
    default = next(
        (
            row for row in rows
            if abs(row["kp"] - 0.3) < 1.0e-9
            and abs(row["kd"] - 0.1) < 1.0e-9
            and abs(row["slew"] - 1.0) < 1.0e-9
            and abs(row["turn_gate"] - 0.55) < 1.0e-9
        ),
        None,
    )
    if default is None:
        default_eps = [
            run_episode(p, "arc", 0.3, 0.1, 1.0, 0.55, seed + i * 37, c)
            for i, p in enumerate(placements)
        ]
        default = summarize_episodes("arc current defaults", default_eps)
        default.update({"mode": "arc", "kp": 0.3, "kd": 0.1, "slew": 1.0,
                        "turn_gate": 0.55, "score": round(score_summary(default), 6)})
    return {
        "type": "arc_tuning_report",
        "seed": int(seed),
        "episodes_per_gain": int(episodes),
        "constants": constants_dict(c),
        "recommended": rows[0],
        "current_defaults": default,
        "pulse_baseline": pulse,
        "top5": rows[:5],
        "all_arc": rows,
    }


def constants_dict(c: SimConstants) -> dict[str, Any]:
    return {
        "static_stiction_cmd": c.static_stiction_cmd,
        "rolling_stiction_cmd": c.rolling_stiction_cmd,
        "turn_angular_z": c.turn_angular_z,
        "bridge_mapping_source": "tools/robot_factory_bridge/chasecar_factory_bridge.py:1130-1149",
        "bridge_max_linear_x": c.bridge_max_linear_x,
        "bridge_max_angular_z": c.bridge_max_angular_z,
        "bridge_max_motor_speed": c.bridge_max_motor_speed,
        "bridge_turn_gain": c.bridge_turn_gain,
        "wheelbase_m": c.wheelbase_m,
        "max_linear_speed_mps": c.max_linear_speed_mps,
        "command_expiry_s": c.command_expiry_s,
        "refresh_hz": c.refresh_hz,
        "perception_hz": c.perception_hz,
        "perception_latency_s": c.perception_latency_s,
        "camera_width_px": c.camera_width_px,
        "hfov_deg": c.hfov_deg,
        "pixel_noise_sigma": c.pixel_noise_sigma,
        "dropout_probability": c.dropout_probability,
        "k_px_m": c.k_px_m,
        "standoff_m": c.standoff_m,
        "actuation_latency_s": c.actuation_latency_s,
        "dt_s": c.dt_s,
        "max_time_s": c.max_time_s,
        "forward_budget": c.forward_budget,
        "max_steps": c.max_steps,
    }


def write_artifacts(report: dict[str, Any], root: Path | None = None) -> Path:
    stamp = time.strftime("%Y%m%dT%H%M%S")
    out_root = root or (REPO_ROOT / "artifacts" / "session" / ("arc_tuning_%s" % stamp))
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_root / "scorecard.md").write_text(render_scorecard(report), encoding="utf-8")
    return out_root


def render_scorecard(report: dict[str, Any]) -> str:
    constants = report["constants"]
    def fmt(value: Any) -> str:
        if value is None:
            return "n/a"
        return "%.3f" % float(value)

    lines = [
        "# Arc Drive Tuning Scorecard",
        "",
        "This is an offline kinematic model calibrated to measured bench constants, not fitted to run data.",
        "",
        "## Constants",
        "",
    ]
    for key in sorted(constants):
        lines.append("- %s: `%s`" % (key, constants[key]))
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "- recommended: `kp=%.2f kd=%.2f slew=%.2f turn_gate=%.2f` score=`%.3f`"
            % (
                report["recommended"]["kp"],
                report["recommended"]["kd"],
                report["recommended"]["slew"],
                report["recommended"]["turn_gate"],
                report["recommended"]["score"],
            ),
            "- current defaults: `kp=%.2f kd=%.2f slew=%.2f turn_gate=%.2f` score=`%.3f`"
            % (
                report["current_defaults"]["kp"],
                report["current_defaults"]["kd"],
                report["current_defaults"]["slew"],
                report["current_defaults"]["turn_gate"],
                report["current_defaults"]["score"],
            ),
            "- pulse baseline score: `%.3f`" % report["pulse_baseline"]["score"],
            "",
            "## Top 5 Arc Gain Sets",
            "",
            "| rank | kp | kd | slew | turn gate | fail rate | time s | overshoots | osc power | score |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for rank, row in enumerate(report["top5"], start=1):
        lines.append(
            "| %d | %.2f | %.2f | %.2f | %.2f | %.3f | %s | %.3f | %.6f | %.3f |"
            % (
                rank,
                row["kp"],
                row["kd"],
                row["slew"],
                row["turn_gate"],
                row["failure_rate"],
                fmt(row["mean_time_to_standoff_s"]),
                row["mean_overshoot_count"],
                row["mean_oscillation_power"],
                row["score"],
            )
        )
    lines.extend(
        [
            "",
            "## Pulse A/B Baseline",
            "",
            "- pulse failure_rate=`%.3f`, mean_time_s=`%s`, mean_overshoots=`%.3f`, oscillation_power=`%.6f`"
            % (
                report["pulse_baseline"]["failure_rate"],
                fmt(report["pulse_baseline"]["mean_time_to_standoff_s"]),
                report["pulse_baseline"]["mean_overshoot_count"],
                report["pulse_baseline"]["mean_oscillation_power"],
            ),
            "- recommended arc failure_rate=`%.3f`, mean_time_s=`%s`, mean_overshoots=`%.3f`, oscillation_power=`%.6f`"
            % (
                report["recommended"]["failure_rate"],
                fmt(report["recommended"]["mean_time_to_standoff_s"]),
                report["recommended"]["mean_overshoot_count"],
                report["recommended"]["mean_oscillation_power"],
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--episodes", type=int, default=DEFAULT_EPISODES)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)

    report = run_gain_sweep(seed=args.seed, episodes=args.episodes)
    if not args.no_write:
        out_dir = write_artifacts(report, Path(args.out_dir) if args.out_dir else None)
        report["artifact_dir"] = str(out_dir)
    print(json.dumps({"recommended": report["recommended"], "pulse_baseline": report["pulse_baseline"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
