import math

import sim_arc_tuning as sim


def _july9_far_left_repro():
    """Trace-calibrated hard-floor setup from onboard_1652159798."""
    half_hfov = math.radians(62.0) / 2.0
    bearing = -0.792578 * half_hfov
    placement = sim.Placement(range_m=0.5916, bearing_right_rad=bearing)
    constants = sim.SimConstants(
        perception_hz=2.0,
        controller_hz=8.333,
        reuse_latest_observation=True,
        perception_latency_s=0.20,
        actuation_latency_s=0.05,
        dropout_probability=0.0,
        pixel_noise_sigma=0.0,
        max_time_s=5.0,
        forward_budget=40,
        max_steps=140,
    )
    return placement, constants


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
        mode="arc_legacy",
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


def test_pure_pivot_cannot_satisfy_standoff_by_rotating_away():
    constants = sim.SimConstants()
    robot = sim.RobotKinematics(constants)
    ball_xy = (0.55, -0.22)
    initial_range = sim.true_range(robot, ball_xy)

    for _ in range(50):
        robot.step(0.0, 2.3, constants.dt_s)

    assert math.isclose(sim.true_range(robot, ball_xy), initial_range, abs_tol=1.0e-12)
    assert sim.true_forward_range(robot, ball_xy) < initial_range


def test_sim_reproduces_july9_hard_floor_unbounded_turn_lost_target():
    placement, constants = _july9_far_left_repro()

    episode = sim.run_episode(
        placement,
        mode="arc_unbounded_turn",
        kp=0.30,
        kd=0.10,
        slew=1.00,
        turn_gate=0.55,
        seed=1,
        constants=constants,
    )

    assert episode["stop_reason"] == "lost_target"
    assert episode["success"] is False
    assert episode["final_z_m"] > constants.standoff_m


def test_bounded_arc_turn_reacquires_under_july9_frame_reuse():
    placement, constants = _july9_far_left_repro()

    episode = sim.run_episode(
        placement,
        mode="arc",
        kp=0.30,
        kd=0.10,
        slew=1.00,
        turn_gate=0.55,
        seed=1,
        constants=constants,
    )

    assert episode["stop_reason"] == "standoff_reached"
    assert episode["success"] is True
    assert episode["final_z_m"] <= constants.standoff_m


def test_bounded_arc_turn_reacquires_both_edges_with_nominal_camera_delay():
    half_hfov = math.radians(62.0) / 2.0
    constants = sim.SimConstants(
        perception_hz=5.0,
        controller_hz=8.333,
        reuse_latest_observation=True,
        perception_latency_s=0.20,
        actuation_latency_s=0.05,
        dropout_probability=0.0,
        pixel_noise_sigma=0.0,
        max_time_s=8.0,
        forward_budget=80,
        max_steps=180,
    )

    for center_error in (-0.792578, 0.792578):
        episode = sim.run_episode(
            sim.Placement(range_m=0.80, bearing_right_rad=center_error * half_hfov),
            mode="arc",
            kp=0.30,
            kd=0.10,
            slew=1.00,
            turn_gate=0.55,
            seed=1,
            constants=constants,
        )

        assert episode["stop_reason"] == "standoff_reached"
        assert episode["success"] is True
        assert episode["final_z_m"] <= constants.standoff_m


def test_corrected_arc_reaches_standoff_from_both_edge_starts():
    constants = sim.SimConstants(
        perception_latency_s=0.0,
        actuation_latency_s=0.0,
        dropout_probability=0.0,
        pixel_noise_sigma=0.0,
        forward_budget=40,
        max_steps=140,
    )
    half_hfov = math.radians(62.0) / 2.0
    target_forward_z = sim.K_PX_M / 19.0

    for err in (-0.90, 0.90):
        bearing = err * half_hfov
        placement = sim.Placement(range_m=target_forward_z / math.cos(bearing), bearing_right_rad=bearing)
        episode = sim.run_episode(
            placement,
            mode="arc",
            kp=0.30,
            kd=0.10,
            slew=1.00,
            turn_gate=0.55,
            seed=42,
            constants=constants,
        )

        assert episode["stop_reason"] == "standoff_reached"
        assert episode["success"] is True
        assert episode["net_forward_progress_m"] > 0.12


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
