from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_TOOLS_DIR = REPO_ROOT / "tools" / "robot_factory_bridge"
if str(BRIDGE_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_TOOLS_DIR))

import chasecar_factory_bridge as bridge  # noqa: E402


def test_camera_backend_defaults_to_gstreamer_for_current_hardware():
    args = bridge.parse_args([])

    assert args.camera_backend == "gstreamer"
    assert args.camera_gstreamer_sensor_id == 0
    assert args.camera_v4l2_device == "/dev/video0"
    assert args.camera_v4l2_raw_width == 3264
    assert args.camera_v4l2_raw_height == 2464
    assert args.camera_v4l2_pixelformat == "RG10"


def test_strict_bool_accepts_explicit_values_only():
    assert bridge.strict_bool(True) is True
    assert bridge.strict_bool("false") is False
    assert bridge.strict_bool(1) is True

    try:
        bridge.strict_bool("maybe")
    except ValueError as exc:
        assert "boolean_value_required" in str(exc)
    else:
        raise AssertionError("expected ambiguous boolean to fail")


def test_motion_control_disables_runtime_motion_and_stops():
    args = bridge.parse_args(["--dry-run", "--enable-motion"])
    robot_bridge = bridge.BridgeState(args)
    try:
        enabled = robot_bridge.set_motion_enabled(True, "test_enable")
        disabled = robot_bridge.set_motion_enabled(False, "test_disable")
    finally:
        robot_bridge.close()

    assert enabled["motion_enabled"] is True
    assert disabled["motion_enabled"] is False
    assert disabled["left_motor"] == 0.0
    assert disabled["right_motor"] == 0.0
    assert disabled["last_stop_reason"] == "motion_control_disabled:test_disable"


def test_camera_backend_accepts_v4l2_bayer_fallback_args():
    args = bridge.parse_args(
        [
            "--camera-backend",
            "v4l2_bayer",
            "--camera-v4l2-device",
            "/dev/video1",
            "--camera-v4l2-raw-width",
            "640",
            "--camera-v4l2-raw-height",
            "480",
            "--camera-v4l2-pixelformat",
            "RG10",
        ]
    )

    assert args.camera_backend == "v4l2_bayer"
    assert args.camera_v4l2_device == "/dev/video1"
    assert args.camera_v4l2_raw_width == 640
    assert args.camera_v4l2_raw_height == 480
    assert args.camera_v4l2_pixelformat == "RG10"


def test_gstreamer_command_uses_argus_camera_and_multifilesink(tmp_path):
    adapter = bridge.CameraAdapter(
        enabled=False,
        width=320,
        height=240,
        jpeg_fps=5.0,
        jpeg_quality=55,
        backend="gstreamer",
    )
    adapter.gstreamer_dir = str(tmp_path)

    command = adapter.build_gstreamer_command()

    assert command[:4] == ["gst-launch-1.0", "-q", "nvarguscamerasrc", "sensor-id=0"]
    assert "video/x-raw(memory:NVMM),width=320,height=240,framerate=5/1" in command
    assert "jpegenc" in command
    assert "quality=55" in command
    assert "multifilesink" in command
    assert "location=%s" % str(tmp_path / "camera_%06d.jpg") in command
    assert "max-files=4" in command


def test_gstreamer_reader_accepts_new_jpeg_and_updates_status(tmp_path):
    adapter = bridge.CameraAdapter(enabled=False, backend="gstreamer")
    adapter.gstreamer_dir = str(tmp_path)
    frame = tmp_path / "camera_000001.jpg"
    frame.write_bytes(b"\xff\xd8jpeg-bytes\xff\xd9")

    assert adapter.read_latest_gstreamer_frame_once() is True
    assert adapter.read_latest_gstreamer_frame_once() is False

    status = adapter.status()
    assert status["backend"] == "gstreamer"
    assert status["cached_bytes"] == len(b"\xff\xd8jpeg-bytes\xff\xd9")
    assert status["frame_count"] == 1
    assert status["encode_count"] == 1


def test_gstreamer_reader_rejects_non_jpeg(tmp_path):
    adapter = bridge.CameraAdapter(enabled=False, backend="gstreamer")
    adapter.gstreamer_dir = str(tmp_path)
    frame = tmp_path / "camera_000001.jpg"
    frame.write_bytes(b"not-a-jpeg")

    try:
        adapter.read_latest_gstreamer_frame_once()
    except RuntimeError as exc:
        assert "gstreamer_frame_not_jpeg" in str(exc)
    else:
        raise AssertionError("expected non-jpeg frame to fail")


def test_v4l2_bayer_commands_use_configured_raw_capture_surface():
    adapter = bridge.CameraAdapter(
        enabled=False,
        backend="v4l2_bayer",
        v4l2_device="/dev/video1",
        v4l2_raw_width=640,
        v4l2_raw_height=480,
        v4l2_pixelformat="RG10",
    )

    assert adapter.build_v4l2_set_format_command() == [
        "v4l2-ctl",
        "--device=/dev/video1",
        "--set-fmt-video=width=640,height=480,pixelformat=RG10",
    ]
    assert adapter.build_v4l2_stream_command("/tmp/frame.raw") == [
        "v4l2-ctl",
        "--device=/dev/video1",
        "--stream-mmap",
        "--stream-count=1",
        "--stream-to=/tmp/frame.raw",
    ]


def test_v4l2_bayer_bytes_convert_to_jpeg():
    adapter = bridge.CameraAdapter(
        enabled=False,
        backend="v4l2_bayer",
        width=4,
        height=4,
        jpeg_quality=60,
        v4l2_raw_width=4,
        v4l2_raw_height=4,
    )
    raw = np.array(
        [
            [10, 20, 30, 40],
            [50, 60, 70, 80],
            [90, 100, 110, 120],
            [130, 140, 150, 160],
        ],
        dtype="<u2",
    )

    jpeg = adapter.v4l2_bayer_bytes_to_jpeg(raw.tobytes())

    assert jpeg.startswith(b"\xff\xd8")
    assert jpeg.endswith(b"\xff\xd9")


def test_v4l2_bayer_bytes_reject_short_frame():
    adapter = bridge.CameraAdapter(
        enabled=False,
        backend="v4l2_bayer",
        v4l2_raw_width=4,
        v4l2_raw_height=4,
    )

    try:
        adapter.v4l2_bayer_bytes_to_jpeg(np.zeros((2, 2), dtype="<u2").tobytes())
    except RuntimeError as exc:
        assert "v4l2_bayer_short_frame" in str(exc)
    else:
        raise AssertionError("expected short raw frame to fail")
