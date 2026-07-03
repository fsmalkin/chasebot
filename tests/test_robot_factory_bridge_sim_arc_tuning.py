import sim_arc_tuning as sim


def test_robot_does_not_move_below_static_stiction_from_rest():
    constants = sim.SimConstants()
    robot = sim.RobotKinematics(constants)

    for _ in range(50):
        robot.step(0.20, 0.0, constants.dt_s)

    assert abs(robot.x) < 1.0e-12
    assert abs(robot.y) < 1.0e-12
    assert abs(robot.yaw) < 1.0e-12


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
