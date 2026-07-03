# Route Policy Port Notes

- Port: `tools/robot_factory_bridge/onboard_route_policy.py` mirrors the sim route classifier for Jetson-safe Python 3.6 use.
- The IRL stack can already estimate ball distance from `z = 9.621 / equiv_px`, ball bearing from tracker `center_error`, detection confidence, and observation staleness.
- Those map to scene perception plus part of `robot_ball_distance_m` / relative bearing.
- Target pose is still missing onboard; delivery-target work needs a fiducial or equivalent target detector.
- Corridor blockage and clearance are not available from the mono camera stack today.
- Lateral error and yaw error relative to the ball-target line require both ball and target estimates.
- Until target/corridor fields exist, this port is a parity-proven policy module, not a complete autonomous route owner.
