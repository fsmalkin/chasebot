# Route Policy Port Notes

- Port: `tools/robot_factory_bridge/onboard_route_policy.py` mirrors the sim route classifier for Jetson-safe Python 3.6 use.
- The IRL stack can already estimate ball distance from `z = 9.621 / equiv_px`, ball bearing from tracker `center_error`, detection confidence, and observation staleness.
- Those map to scene perception plus part of `robot_ball_distance_m` / relative bearing.
- The laptop control server now publishes an ArUco delivery observation as
  `/status.target`, including camera-frame `x_m` / `y_m` / `z_m`, bearing,
  observation time, calibration provenance, and estimate limits. Printed-marker
  range validation is pending; see `docs/notes/aruco-target-feed.md`.
- Corridor blockage and clearance are not available from the mono camera stack today.
- Lateral and yaw error relative to the ball-target line can now be derived
  after the laptop target observation is transported into the onboard scene
  descriptor and aligned with the BallTracker timestamp.
- Until that transport, timestamp alignment, and corridor policy exist, this
  port remains a parity-proven policy module rather than a complete autonomous
  route owner.
