#!/usr/bin/env python3
"""Manage the Xpra-based operator live-view session."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable
from urllib.error import URLError
from urllib.request import urlopen


DISPLAY_NAME = ":100"
DEFAULT_PORT = 14500
DEFAULT_BACKEND = "xpra"
DEFAULT_TIMEOUT_S = 60.0
MONITOR_INTERVAL_S = 1.0
ROS_SETUP_CANDIDATES = (
    "/opt/ros/kilted/setup.bash",
    "/opt/ros/jazzy/setup.bash",
    "/opt/ros/rolling/setup.bash",
)
STOP_REQUESTED = False


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def request_stop(_signum: int, _frame: Any) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True


def install_signal_handlers() -> None:
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, request_stop)
        except Exception:
            continue


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def terminate_pid(pid: int, timeout_s: float = 8.0) -> None:
    if pid <= 0:
        return
    if not pid_alive(pid):
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except Exception:
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            return
    deadline = time.time() + max(timeout_s, 1.0)
    while time.time() < deadline:
        if not pid_alive(pid):
            return
        time.sleep(0.25)
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except Exception:
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass


def locate_xpra() -> str:
    for candidate in ("xpra", "/usr/bin/xpra", "/usr/local/bin/xpra"):
        found = shutil.which(candidate)
        if found:
            return found
    raise FileNotFoundError("xpra command not found")


def locate_shell() -> str:
    for candidate in ("/bin/bash", "/usr/bin/bash", "bash"):
        found = shutil.which(candidate)
        if found:
            return found
    raise FileNotFoundError("bash command not found")


def ros_setup_line() -> str:
    for candidate in ROS_SETUP_CANDIDATES:
        if Path(candidate).exists():
            return f'source "{candidate}"'
    return 'source "/opt/ros/kilted/setup.bash"'


def ws_setup_line() -> str:
    return 'if [ -f "/root/ros2_ws/install/setup.bash" ]; then source "/root/ros2_ws/install/setup.bash"; fi'


def http_ok(url: str, timeout_s: float = 3.0) -> bool:
    try:
        with urlopen(url, timeout=timeout_s) as response:
            return 200 <= int(getattr(response, "status", 200)) < 400
    except URLError:
        return False
    except Exception:
        return False


def first_http_url(port: int) -> str:
    candidates = (
        f"http://127.0.0.1:{port}/",
        f"http://127.0.0.1:{port}/index.html",
    )
    for candidate in candidates:
        if http_ok(candidate):
            return candidate
    return candidates[0]


def display_env() -> Dict[str, str]:
    env = dict(os.environ)
    env["DISPLAY"] = DISPLAY_NAME
    env.setdefault("QT_QPA_PLATFORM", "xcb")
    env.setdefault("QT_X11_NO_MITSHM", "1")
    env.setdefault("LIBGL_ALWAYS_INDIRECT", "1")
    return env


def gz_gui_config_text() -> str:
    return """<?xml version="1.0"?>
<window>
  <width>1000</width>
  <height>845</height>
</window>
<plugin filename="MinimalScene" name="3D View">
  <gz-gui>
    <title>3D View</title>
    <property type="bool" key="showTitleBar">false</property>
    <property type="string" key="state">docked</property>
  </gz-gui>
  <engine>ogre</engine>
  <scene>scene</scene>
  <ambient_light>0.4 0.4 0.4</ambient_light>
  <background_color>0.8 0.8 0.8</background_color>
  <camera_pose>-4.0 -1.4 2.6 0 0.95 0.40</camera_pose>
</plugin>
<plugin filename="TransportSceneManager" name="Scene Manager">
  <gz-gui>
    <property key="resizable" type="bool">false</property>
    <property key="width" type="double">5</property>
    <property key="height" type="double">5</property>
    <property key="state" type="string">floating</property>
    <property key="showTitleBar" type="bool">false</property>
  </gz-gui>
</plugin>
<plugin filename="InteractiveViewControl" name="Interactive view control">
  <gz-gui>
    <property key="resizable" type="bool">false</property>
    <property key="width" type="double">5</property>
    <property key="height" type="double">5</property>
    <property key="state" type="string">floating</property>
    <property key="showTitleBar" type="bool">false</property>
  </gz-gui>
</plugin>
<plugin filename="CameraTracking" name="Camera Tracking">
  <gz-gui>
    <property key="resizable" type="bool">false</property>
    <property key="width" type="double">5</property>
    <property key="height" type="double">5</property>
    <property key="state" type="string">floating</property>
    <property key="showTitleBar" type="bool">false</property>
  </gz-gui>
</plugin>
<plugin filename="MarkerManager" name="Marker manager">
  <gz-gui>
    <property key="resizable" type="bool">false</property>
    <property key="width" type="double">5</property>
    <property key="height" type="double">5</property>
    <property key="state" type="string">floating</property>
    <property key="showTitleBar" type="bool">false</property>
  </gz-gui>
</plugin>
"""


def app_definitions(output_dir: Path) -> Dict[str, Dict[str, Any]]:
    config_path = output_dir / "operator_view_gz_gui.config"
    config_path.write_text(gz_gui_config_text(), encoding="utf-8")
    shell = locate_shell()
    return {
        "gz_gui": {
            "name": "gz_gui",
            "topic": "",
            "command": [
                shell,
                "-lc",
                f'{ros_setup_line()} && {ws_setup_line()} && export DISPLAY="{DISPLAY_NAME}" && exec gz gui -c "{config_path}" -v 3',
            ],
            "log_path": str(output_dir / "gz_gui.log"),
        },
        "raw_viewer": {
            "name": "raw_viewer",
            "topic": "/d415/color/image_raw",
            "command": [
                shell,
                "-lc",
                f'{ros_setup_line()} && {ws_setup_line()} && export DISPLAY="{DISPLAY_NAME}" && exec ros2 run rqt_image_view rqt_image_view /d415/color/image_raw',
            ],
            "log_path": str(output_dir / "raw_viewer.log"),
        },
        "debug_viewer": {
            "name": "debug_viewer",
            "topic": "/yolo/debug_image",
            "command": [
                shell,
                "-lc",
                f'{ros_setup_line()} && {ws_setup_line()} && export DISPLAY="{DISPLAY_NAME}" && exec ros2 run rqt_image_view rqt_image_view /yolo/debug_image',
            ],
            "log_path": str(output_dir / "debug_viewer.log"),
        },
    }


def process_payload(pid: int, command: str, log_path: str, role: str = "") -> Dict[str, Any]:
    return {
        "pid": pid,
        "alive": pid_alive(pid),
        "command": command,
        "log_path": log_path,
        "role": role,
    }


def load_state(output_dir: Path) -> Dict[str, Any]:
    return read_json(output_dir / "operator_view_state.json")


def collect_apps(state: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    apps = state.get("apps", {})
    if not isinstance(apps, dict):
        apps = {}
    return {
        "gz_gui": dict(apps.get("gz_gui", {})) if isinstance(apps.get("gz_gui", {}), dict) else {},
        "raw_viewer": dict(apps.get("raw_viewer", {})) if isinstance(apps.get("raw_viewer", {}), dict) else {},
        "debug_viewer": dict(apps.get("debug_viewer", {})) if isinstance(apps.get("debug_viewer", {}), dict) else {},
    }


def app_alive(app: Dict[str, Any]) -> bool:
    try:
        pid = int(app.get("pid", 0) or 0)
    except Exception:
        pid = 0
    return pid_alive(pid)


def summarize_state(output_dir: Path, *, default_session_id: str = "", default_port: int = DEFAULT_PORT, default_dashboard_url: str = "") -> Dict[str, Any]:
    state = load_state(output_dir)
    apps = collect_apps(state)
    port = int(state.get("port", default_port) or default_port)
    backend = str(state.get("backend", DEFAULT_BACKEND) or DEFAULT_BACKEND)
    dashboard_url = str(state.get("dashboard_url", default_dashboard_url) or default_dashboard_url)
    endpoint_url = first_http_url(port)
    endpoint_ready = http_ok(endpoint_url)
    gz_ok = app_alive(apps["gz_gui"])
    raw_ok = app_alive(apps["raw_viewer"])
    dbg_ok = app_alive(apps["debug_viewer"])
    any_running = endpoint_ready or gz_ok or raw_ok or dbg_ok

    if endpoint_ready and gz_ok and raw_ok and dbg_ok:
        status = "ready"
        failure_class = ""
        ready = True
    elif any_running:
        status = "running"
        failure_class = ""
        if not endpoint_ready:
            failure_class = "xpra_http_unavailable"
        elif not gz_ok:
            failure_class = "gz_gui_not_running"
        elif not raw_ok:
            failure_class = "raw_viewer_not_running"
        elif not dbg_ok:
            failure_class = "debug_viewer_not_running"
        ready = False
    else:
        status = "stopped"
        failure_class = state.get("failure_class", "operator_view_not_running") or "operator_view_not_running"
        ready = False

    session_id = str(state.get("session_id", default_session_id) or default_session_id)
    log_path = str(state.get("log_path", str(output_dir / "operator_view.log")) or str(output_dir / "operator_view.log"))
    payload = {
        "session_id": session_id,
        "backend": backend,
        "url": endpoint_url if endpoint_ready else str(state.get("url", endpoint_url) or endpoint_url),
        "port": port,
        "ready": ready,
        "status": status,
        "failure_class": failure_class,
        "apps": {
            "gz_gui": apps["gz_gui"],
            "raw_viewer": apps["raw_viewer"],
            "debug_viewer": apps["debug_viewer"],
        },
        "apps.gz_gui": gz_ok,
        "apps.raw_viewer": raw_ok,
        "apps.debug_viewer": dbg_ok,
        "latest_heartbeat_utc": utc_now(),
        "log_path": log_path,
        "dashboard_url": dashboard_url,
        "display": DISPLAY_NAME,
    }
    return payload


def write_state(output_dir: Path, state: Dict[str, Any]) -> None:
    write_json(output_dir / "operator_view_state.json", state)


def start_process(command: Iterable[str], log_path: Path) -> subprocess.Popen[Any]:
    ensure_dir(log_path.parent)
    log_file = log_path.open("a", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            list(command),
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
            close_fds=True,
        )
    finally:
        log_file.close()
    return proc


def cleanup_existing(output_dir: Path) -> None:
    state = load_state(output_dir)
    apps = collect_apps(state)
    for app in (apps["debug_viewer"], apps["raw_viewer"], apps["gz_gui"]):
        try:
            terminate_pid(int(app.get("pid", 0) or 0))
        except Exception:
            pass
    try:
        terminate_pid(int(state.get("xpra_pid", 0) or 0))
    except Exception:
        pass


def launch_operator_view(args: argparse.Namespace) -> Dict[str, Any]:
    global STOP_REQUESTED
    STOP_REQUESTED = False
    install_signal_handlers()
    output_dir = ensure_dir(Path(args.output_dir).resolve())
    log_path = output_dir / "operator_view.log"
    cleanup_existing(output_dir)

    baseline = {
        "session_id": args.session_id,
        "backend": DEFAULT_BACKEND,
        "url": f"http://127.0.0.1:{args.port}/",
        "port": args.port,
        "ready": False,
        "status": "starting",
        "failure_class": "",
        "apps": {
            "gz_gui": {},
            "raw_viewer": {},
            "debug_viewer": {},
        },
        "apps.gz_gui": False,
        "apps.raw_viewer": False,
        "apps.debug_viewer": False,
        "latest_heartbeat_utc": utc_now(),
        "log_path": str(log_path),
        "dashboard_url": args.dashboard_url,
        "display": DISPLAY_NAME,
        "xpra_pid": 0,
    }
    write_state(output_dir, baseline)

    xpra = locate_xpra()
    port = int(args.port)
    xpra_cmd = [
        xpra,
        "start",
        DISPLAY_NAME,
        "--bind-tcp=0.0.0.0:%d" % port,
        "--tcp-auth=none",
        "--ws-auth=none",
        "--html=on",
        "--daemon=no",
    ]
    xpra_proc = start_process(xpra_cmd, log_path)

    wait_deadline = time.time() + 20.0
    endpoint_url = f"http://127.0.0.1:{port}/"
    while time.time() < wait_deadline and not STOP_REQUESTED:
        if xpra_proc.poll() is not None:
            state = summarize_state(output_dir, default_session_id=args.session_id, default_port=port, default_dashboard_url=args.dashboard_url)
            state["status"] = "error"
            state["failure_class"] = "xpra_start_failed"
            state["xpra_pid"] = xpra_proc.pid
            write_state(output_dir, state)
            return state
        if http_ok(endpoint_url):
            break
        time.sleep(0.5)

    if STOP_REQUESTED:
        return stop_command(argparse.Namespace(output_dir=str(output_dir)))
    if not http_ok(endpoint_url):
        terminate_pid(xpra_proc.pid)
        state = summarize_state(output_dir, default_session_id=args.session_id, default_port=port, default_dashboard_url=args.dashboard_url)
        state["status"] = "error"
        state["failure_class"] = "xpra_http_unavailable"
        state["xpra_pid"] = xpra_proc.pid
        write_state(output_dir, state)
        return state

    apps = app_definitions(output_dir)
    launched: Dict[str, subprocess.Popen[Any]] = {}
    for name in ("gz_gui", "raw_viewer", "debug_viewer"):
        app = apps[name]
        proc = start_process(app["command"], Path(app["log_path"]))
        launched[name] = proc

    app_deadline = time.time() + DEFAULT_TIMEOUT_S
    while time.time() < app_deadline and not STOP_REQUESTED:
        current = {
            "session_id": args.session_id,
            "backend": DEFAULT_BACKEND,
            "url": first_http_url(port),
            "port": port,
            "ready": False,
            "status": "starting",
            "failure_class": "",
            "apps": {
                "gz_gui": process_payload(
                    launched["gz_gui"].pid,
                    "gz gui -c operator_view_gz_gui.config -v 3",
                    apps["gz_gui"]["log_path"],
                    "gz_gui",
                ),
                "raw_viewer": process_payload(
                    launched["raw_viewer"].pid,
                    "ros2 run rqt_image_view rqt_image_view /d415/color/image_raw",
                    apps["raw_viewer"]["log_path"],
                    "raw_viewer",
                ),
                "debug_viewer": process_payload(
                    launched["debug_viewer"].pid,
                    "ros2 run rqt_image_view rqt_image_view /yolo/debug_image",
                    apps["debug_viewer"]["log_path"],
                    "debug_viewer",
                ),
            },
            "apps.gz_gui": pid_alive(launched["gz_gui"].pid),
            "apps.raw_viewer": pid_alive(launched["raw_viewer"].pid),
            "apps.debug_viewer": pid_alive(launched["debug_viewer"].pid),
            "latest_heartbeat_utc": utc_now(),
            "log_path": str(log_path),
            "dashboard_url": args.dashboard_url,
            "display": DISPLAY_NAME,
            "xpra_pid": xpra_proc.pid,
        }
        if http_ok(current["url"]) and current["apps.gz_gui"] and current["apps.raw_viewer"] and current["apps.debug_viewer"]:
            current["ready"] = True
            current["status"] = "ready"
            current["failure_class"] = ""
            write_state(output_dir, current)
            break
        write_state(output_dir, current)
        if any(proc.poll() is not None for proc in launched.values()):
            break
        time.sleep(0.5)
    else:
        current = {}

    if STOP_REQUESTED:
        return stop_command(argparse.Namespace(output_dir=str(output_dir)))

    current = summarize_state(output_dir, default_session_id=args.session_id, default_port=port, default_dashboard_url=args.dashboard_url)
    current["xpra_pid"] = xpra_proc.pid
    write_state(output_dir, current)
    if not current.get("ready", False):
        terminate_pid(launched["debug_viewer"].pid)
        terminate_pid(launched["raw_viewer"].pid)
        terminate_pid(launched["gz_gui"].pid)
        terminate_pid(xpra_proc.pid)
        failure = summarize_state(output_dir, default_session_id=args.session_id, default_port=port, default_dashboard_url=args.dashboard_url)
        failure["status"] = "error"
        if not failure.get("failure_class"):
            failure["failure_class"] = "operator_view_start_timeout"
        failure["xpra_pid"] = xpra_proc.pid
        write_state(output_dir, failure)
        return failure

    while not STOP_REQUESTED:
        current = summarize_state(output_dir, default_session_id=args.session_id, default_port=port, default_dashboard_url=args.dashboard_url)
        current["xpra_pid"] = xpra_proc.pid
        write_state(output_dir, current)
        if current.get("status") == "stopped":
            return current
        time.sleep(MONITOR_INTERVAL_S)

    return stop_command(argparse.Namespace(output_dir=str(output_dir)))


def status_command(args: argparse.Namespace) -> Dict[str, Any]:
    output_dir = Path(args.output_dir).resolve()
    payload = summarize_state(output_dir)
    write_state(output_dir, payload)
    return payload


def stop_command(args: argparse.Namespace) -> Dict[str, Any]:
    output_dir = Path(args.output_dir).resolve()
    state = load_state(output_dir)
    apps = collect_apps(state)
    for name in ("debug_viewer", "raw_viewer", "gz_gui"):
        try:
            terminate_pid(int(apps.get(name, {}).get("pid", 0) or 0))
        except Exception:
            pass
    try:
        terminate_pid(int(state.get("xpra_pid", 0) or 0))
    except Exception:
        pass
    payload = summarize_state(output_dir)
    for key in ("gz_gui", "raw_viewer", "debug_viewer"):
        app = dict(payload.get("apps", {}).get(key, {})) if isinstance(payload.get("apps", {}), dict) else {}
        app["pid"] = 0
        app["alive"] = False
        payload.setdefault("apps", {})[key] = app
    payload["ready"] = False
    payload["status"] = "stopped"
    payload["failure_class"] = ""
    payload["apps.gz_gui"] = False
    payload["apps.raw_viewer"] = False
    payload["apps.debug_viewer"] = False
    payload["latest_heartbeat_utc"] = utc_now()
    write_state(output_dir, payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the Xpra operator live view.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="Start the operator view session")
    start_parser.add_argument("--session-id", required=True)
    start_parser.add_argument("--output-dir", required=True)
    start_parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    start_parser.add_argument("--dashboard-url", required=True)

    status_parser = subparsers.add_parser("status", help="Report the current operator view state")
    status_parser.add_argument("--output-dir", required=True)

    stop_parser = subparsers.add_parser("stop", help="Stop the operator view session")
    stop_parser.add_argument("--output-dir", required=True)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "start":
            payload = launch_operator_view(args)
        elif args.command == "status":
            payload = status_command(args)
        elif args.command == "stop":
            payload = stop_command(args)
        else:
            parser.error(f"unknown command: {args.command}")
            return 2
    except Exception as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
