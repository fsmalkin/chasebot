# ArUco Delivery-Target Feed

## Status

The laptop control server now detects the delivery marker in the same camera
frames used for the spectator ball feed. `/status` publishes the marker as a
separate `target` observation. Synthetic OpenCV 5 tests cover centered pose,
off-axis bearing, marker-ID filtering, and status serialization. A printed
marker and live camera frame remain the physical validation gate.

The detector stays on the laptop. The Jetson Nano keeps its existing OpenCV
4.1.1 install and onboard fetch loop.

## Marker Contract

Print ArUco `DICT_4X4_50` marker ID `0` so the black marker square measures
`0.10 m` on each side. Keep a white margin around the square. The control
server accepts these environment overrides before launch:

| Variable | Default | Purpose |
| --- | --- | --- |
| `CHASECAR_ARUCO_DICTIONARY` | `DICT_4X4_50` | OpenCV predefined dictionary |
| `CHASECAR_ARUCO_MARKER_ID` | `0` | Delivery marker selected when several markers are visible |
| `CHASECAR_ARUCO_MARKER_SIZE_M` | `0.10` | Printed black-square side length in meters |
| `CHASECAR_ARUCO_FOCAL_PX` | `225.317` | Empirical focal estimate at 320 px image width |

## `/status` Contract

`target` is `null` when the configured marker is absent from the latest
processed frame. `target_ts` is the Unix timestamp of the current target
observation. `target_err` reports ArUco initialization or per-frame failures
without interrupting ball detection.

The target object contains:

| Field | Meaning |
| --- | --- |
| `id`, `dictionary`, `marker_size_m` | Marker identity and metric-size assumption |
| `corners_px`, `center_px`, `side_px` | Image geometry |
| `center_error` | Normalized horizontal error; positive is camera-right |
| `bearing_rad`, `bearing_deg` | Horizontal target bearing; positive is camera-right |
| `x_m`, `y_m`, `z_m` | Camera-frame translation: right, down, forward |
| `distance_m` | Euclidean camera-to-marker distance |
| `rvec_rad` | OpenCV marker rotation vector |
| `pose_status`, `pose_method` | `metric` through square-marker PnP, or `bearing_only` fallback |
| `calibration`, `limits` | Calibration provenance and evidence boundaries |
| `observed_ts` | Timestamp of the camera frame that produced the observation |

The metric pose uses square-marker IPPE PnP. Intrinsics come from the bench
golf-ball apparent-size calibration: focal length `225.317 px` at 320 px image
width, centered principal point, and assumed-zero lens distortion. The server
scales focal length with image width. Delivery experiments should treat the
pose as a bounded monocular estimate until a printed-marker range check or a
full camera calibration quantifies its error.

## Physical Validation Gate

The first live check is perception-only:

1. Print the configured marker at the exact measured size.
2. Place it in the robot camera view while the bridge remains locked.
3. Confirm the blue marker outline appears on `/camera.jpg`.
4. Confirm `/status.target` reports ID `0`, the expected bearing sign, and a
   plausible `z_m` at two measured ranges.
5. Record the measured-versus-estimated range error before planner wiring.

This check requires no `GO`, `RESET`, jog, motion enablement, or robot-side
package installation.
