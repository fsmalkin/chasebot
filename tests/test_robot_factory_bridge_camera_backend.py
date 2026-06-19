from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_TOOLS_DIR = REPO_ROOT / "tools" / "robot_factory_bridge"
if str(BRIDGE_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_TOOLS_DIR))

import chasecar_factory_bridge as bridge  # noqa: E402


def test_camera_backend_defaults_to_gstreamer_for_current_hardware():
    args = bridge.parse_args([])

    assert args.camera_backend == "gstreamer"
    assert args.camera_gstreamer_sensor_id == 0


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
