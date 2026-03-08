#!/usr/bin/env python3
"""Launch a same-session Gazebo GUI under Xvfb and expose it via noVNC."""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start a streamed Gazebo world viewer.")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--duration-s", type=float, default=180.0)
    parser.add_argument("--display", default=":99")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=800)
    parser.add_argument("--vnc-port", type=int, default=5900)
    parser.add_argument("--web-port", type=int, default=6080)
    parser.add_argument("--public-url", required=True)
    parser.add_argument("--render-engine", default="ogre")
    return parser.parse_args()


def port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        try:
            sock.connect((host, port))
            return True
        except OSError:
            return False


def nonblank_image(path: Path) -> bool:
    if not path.exists() or path.stat().st_size <= 0:
        return False
    frame = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if frame is None:
        return False
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return bool(np.std(gray) >= 5.0 and np.mean(gray) >= 5.0)


def spawn(cmd: list[str], env: dict[str, str], stdout_path: Path, stderr_path: Path) -> subprocess.Popen:
    stdout_handle = stdout_path.open("ab")
    stderr_handle = stderr_path.open("ab")
    return subprocess.Popen(cmd, env=env, stdout=stdout_handle, stderr=stderr_handle)


def stop_processes(processes: list[subprocess.Popen]) -> None:
    for proc in reversed(processes):
        try:
            proc.terminate()
        except Exception:
            continue
    time.sleep(1.0)
    for proc in reversed(processes):
        try:
            if proc.poll() is None:
                proc.kill()
        except Exception:
            continue


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    live_dir = output_dir / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = live_dir / "world_stream.jpg"
    video_path = output_dir / "world_stream.mp4"
    state_path = output_dir / "world_stream_state.json"
    summary_path = output_dir / "world_stream_summary.json"
    gui_config_path = output_dir / "world_viewer_gui.config"
    gui_config_path.write_text(
        f"""<?xml version="1.0"?>
<window>
  <width>{args.width}</width>
  <height>{args.height}</height>
</window>
<plugin filename="MinimalScene" name="3D View">
  <gz-gui>
    <title>3D View</title>
    <property type="bool" key="showTitleBar">false</property>
    <property type="string" key="state">docked</property>
  </gz-gui>
  <engine>{args.render_engine}</engine>
  <scene>scene</scene>
  <ambient_light>0.4 0.4 0.4</ambient_light>
  <background_color>0.8 0.8 0.8</background_color>
  <camera_pose>-6 0 6 0 0.5 0</camera_pose>
</plugin>
""",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["DISPLAY"] = args.display
    env["QT_QPA_PLATFORM"] = "xcb"
    env["QT_X11_NO_MITSHM"] = "1"
    env["LIBGL_ALWAYS_SOFTWARE"] = "1"
    env["MESA_GL_VERSION_OVERRIDE"] = "3.3"
    env["GALLIUM_DRIVER"] = "llvmpipe"
    partition = env.get("GAZEBO_PARTITION") or env.get("GZ_PARTITION") or env.get("IGN_PARTITION") or ""
    same_session_partition = bool(partition) and partition == args.session_id

    stop_requested = False
    processes: list[subprocess.Popen] = []

    def request_stop(*_args: object) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    processes.append(
        spawn(
            ["Xvfb", args.display, "-screen", "0", f"{args.width}x{args.height}x24", "-ac", "+extension", "GLX", "-noreset"],
            env,
            logs_dir / "xvfb.out.log",
            logs_dir / "xvfb.err.log",
        )
    )
    time.sleep(1.0)
    processes.append(spawn(["fluxbox"], env, logs_dir / "fluxbox.out.log", logs_dir / "fluxbox.err.log"))
    time.sleep(1.0)
    processes.append(
        spawn(
            ["gz", "sim", "-g", "--gui-config", str(gui_config_path), "--render-engine-gui", args.render_engine],
            env,
            logs_dir / "world_viewer.out.log",
            logs_dir / "world_viewer.err.log",
        )
    )
    time.sleep(2.0)
    processes.append(
        spawn(
            ["x11vnc", "-display", args.display, "-rfbport", str(args.vnc_port), "-forever", "-shared", "-nopw", "-xkb"],
            env,
            logs_dir / "x11vnc.out.log",
            logs_dir / "x11vnc.err.log",
        )
    )
    time.sleep(1.0)
    novnc_web = "/usr/share/novnc"
    processes.append(
        spawn(
            ["websockify", "--web", novnc_web, str(args.web_port), f"127.0.0.1:{args.vnc_port}"],
            env,
            logs_dir / "websockify.out.log",
            logs_dir / "websockify.err.log",
        )
    )
    processes.append(
        spawn(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-video_size",
                f"{args.width}x{args.height}",
                "-framerate",
                "10",
                "-f",
                "x11grab",
                "-i",
                args.display,
                "-pix_fmt",
                "yuv420p",
                "-vcodec",
                "libx264",
                "-preset",
                "ultrafast",
                str(video_path),
            ],
            env,
            logs_dir / "ffmpeg.out.log",
            logs_dir / "ffmpeg.err.log",
        )
    )

    started = time.monotonic()
    world_ready = False
    nonblank = False
    interactive = False

    while not stop_requested and time.monotonic() - started < max(args.duration_s, 1.0):
        interactive = port_open("127.0.0.1", args.web_port)
        if interactive and not world_ready:
            capture = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-video_size",
                    f"{args.width}x{args.height}",
                    "-f",
                    "x11grab",
                    "-i",
                    args.display,
                    "-frames:v",
                    "1",
                    str(screenshot_path),
                ],
                env=env,
                capture_output=True,
                text=True,
                timeout=10.0,
                check=False,
            )
            if capture.returncode == 0:
                nonblank = nonblank_image(screenshot_path)
                world_ready = nonblank

        state = {
            "session_id": args.session_id,
            "partition": partition,
            "world_surface": "streamed_sim",
            "world_stream_url": args.public_url,
            "world_stream_ready": world_ready,
            "world_stream_nonblank": nonblank,
            "world_stream_interactive": interactive,
            "same_session_partition": same_session_partition,
            "screenshot_path": str(screenshot_path),
            "video_path": str(video_path),
        }
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        time.sleep(1.0)

    stop_processes(processes)

    video_ok = video_path.exists() and video_path.stat().st_size > 0
    summary = {
        "session_id": args.session_id,
        "partition": partition,
        "world_surface": "streamed_sim",
        "world_stream_url": args.public_url,
        "world_stream_ready": world_ready,
        "world_stream_nonblank": nonblank,
        "world_stream_interactive": interactive,
        "same_session_partition": same_session_partition,
        "screenshot_path": str(screenshot_path),
        "video_path": str(video_path),
        "pass": world_ready and nonblank and interactive and same_session_partition and video_ok,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"WORLD_STREAM_STATE={state_path}")
    print(f"WORLD_STREAM_SUMMARY={summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
