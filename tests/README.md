# Test Scope

The fast CI gate covers Python syntax, Jetson Python 3.6 compatibility for
`chasecar_onboard_fetch.py`, the onboard synthetic selftest, dashboard STOP
helper regressions, and PowerShell parse errors.

It does not cover GPU inference, TensorRT engines, model downloads, robot SSH,
factory bridge integration, camera readiness, physical motion, or bench safety.
Green CI means the code is eligible for supervised bench validation, not that
the robot has been validated.
