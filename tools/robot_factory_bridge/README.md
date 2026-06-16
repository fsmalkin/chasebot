# Robot Factory Bridge

This bridge lets Chasecar talk to the factory Yahboom/JetBot Mini runtime while the robot image stays intact.

The bridge runs as one Python process on the robot. It exposes HTTP endpoints for health, stop, camera snapshot, direct motor pulses, and Chasecar-style `cmd_vel` commands. Motion starts only when the process is launched with `--enable-motion`.

The default motor backend uses the same Yahboom I2C command format as the factory web app: direction and speed bytes for the left and right motors in one write.

Safety defaults:

- `--enable-motion` is required before `/motors` or `/cmd_vel` can move wheels.
- `--deadman-timeout-s 0.5` stops the motors if commands stop arriving.
- `--max-command-duration-s 1.0` bounds each command.
- `--max-motor-speed 0.35` clamps wheel power during early bring-up.

Basic flow:

1. Deploy and start health mode:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/deploy_robot_factory_bridge.ps1 -RobotHost 192.168.1.11 -RobotUser jetson -Start
   ```

2. Restart with motion enabled for lifted-wheel tests:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/deploy_robot_factory_bridge.ps1 -RobotHost 192.168.1.11 -RobotUser jetson -Start -EnableMotion
   ```

3. Run the lifted-wheel test only while the operator holds the robot clear of the floor:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/test_robot_factory_bridge_lifted_wheels.ps1 -RobotHost 192.168.1.11 -ConfirmHeldInAir
   ```

4. Stop the bridge:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/stop_robot_factory_bridge.ps1 -RobotHost 192.168.1.11 -RobotUser jetson
   ```

Rollback is delete-only: stop the process and remove `/home/jetson/chasecar_factory_bridge`.
