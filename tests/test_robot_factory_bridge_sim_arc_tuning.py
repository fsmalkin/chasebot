import math

import sim_arc_tuning as sim


def test_robot_does_not_move_below_static_stiction_from_rest():
    constants = sim.SimConstants()
    robot = sim.RobotKinematics(constants)

    for _ in range(50):
        robot.step(0.20, 0.0, constants.dt_s)

    assert abs(robot.x) < 1.0e-12
    assert abs(robot.y) < 1.0e-12
    assert abs(robot.yaw) < 1.0e-12


def test_bridge_mapping_scales_cmd_vel_before_motor_stiction():
    constants = sim.SimConstants()

    left, right = sim.bridge_cmd_vel_to_motors(0.193, 0.0, constants)

    assert left == right
    assert left < constants.static_stiction_cmd
    assert round(left, 3) == 0.113


def test_fixed_sim_reproduces_real_old_arc_stall_from_left_edge():
    half_hfov = math.radians(62.0) / 2.0
    bearing = -0.90 * half_hfov
    target_forward_z = sim.K_PX_M / 19.0
    placement = sim.Placement(range_m=target_forward_z / math.cos(bearing), bearing_right_rad=bearing)
    constants = sim.SimConstants(
        perception_latency_s=0.0,
        actuation_latency_s=0.0,
        dropout_probability=0.0,
        pixel_noise_sigma=0.0,
        forward_budget=40,
        max_steps=80,
    )

    episode = sim.run_episode(
        placement,
        mode="arc",
        kp=0.50,
        kd=0.15,
        slew=2.00,
        seed=1783138082,
        constants=constants,
    )

    assert episode["stop_reason"] == "forward_budget_exhausted"
    assert episode["success"] is False
    assert abs(episode["net_forward_progress_m"]) <= 0.005
    assert abs(episode["final_equiv_diameter_px"] - episode["initial_equiv_diameter_px"]) <= 0.25
    assert episode["max_abs_motor_cmd"] < constants.static_stiction_cmd
    assert episode["max_abs_effective_motor"] == 0.0


def test_perception_latency_shifts_first_applied_response_later():
    placement = sim.Placement(range_m=1.0, bearing_right_rad=0.15)
    fast = sim.SimConstants(perception_latency_s=0.0, dropout_probability=0.0, pixel_noise_sigma=0.0)
    delayed = sim.SimConstants(perception_latency_s=0.20, dropout_probability=0.0, pixel_noise_sigma=0.0)

    fast_ep = sim.run_episode(placement, mode="arc", seed=7, constants=fast)
    delayed_ep = sim.run_episode(placement, mode="arc", seed=7, constants=delayed)

    assert fast_ep["first_command_t"] is not None
    assert delayed_ep["first_command_t"] is not None
    assert delayed_ep["first_command_t"] > fast_ep["first_command_t"]


def test_gain_sweep_is_seed_deterministic_for_small_grid():
    kwargs = {
        "seed": 1234,
        "episodes": 3,
        "kp_values": [0.7, 0.9],
        "kd_values": [0.0, 0.25],
        "slew_values": [1.5],
        "constants": sim.SimConstants(dropout_probability=0.0, pixel_noise_sigma=0.0),
    }

    first = sim.run_gain_sweep(**kwargs)
    second = sim.run_gain_sweep(**kwargs)

    assert first["recommended"] == second["recommended"]
    assert first["top5"] == second["top5"]
    assert first["pulse_baseline"] == second["pulse_baseline"]
