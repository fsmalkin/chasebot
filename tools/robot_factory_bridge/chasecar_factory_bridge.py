#!/usr/bin/env python3
"""Small HTTP bridge for the factory Yahboom/JetBot Mini runtime.

The bridge keeps Chasecar logic outside the robot image and adapts commands to
the factory `jetbotmini` motor/camera APIs. It is intentionally manual: copy it
to the robot, run it in the foreground or with nohup, and remove the file to
return to the factory state.
"""

import argparse
import base64
import http.server
import json
import math
import os
import socketserver
import sys
import threading
import time
import traceback
import urllib.parse


VERSION = "0.1.0"


DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Chasecar Robot Bridge</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f6f8;
      --panel: #ffffff;
      --ink: #15191f;
      --muted: #657080;
      --line: #d9dee7;
      --green: #147a46;
      --red: #b42318;
      --amber: #946200;
      --blue: #2457a6;
      --shadow: 0 1px 3px rgba(15, 23, 42, 0.10);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 18px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
      position: sticky;
      top: 0;
      z-index: 2;
    }
    h1 {
      margin: 0;
      font-size: 18px;
      line-height: 1.2;
      letter-spacing: 0;
    }
    main {
      display: grid;
      grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
      gap: 14px;
      padding: 14px;
      max-width: 1280px;
      margin: 0 auto;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 14px;
    }
    h2 {
      margin: 0 0 10px;
      font-size: 15px;
      letter-spacing: 0;
    }
    .status-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }
    .chip {
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 13px;
      font-weight: 650;
      background: #eef1f6;
      color: var(--ink);
      border: 1px solid var(--line);
    }
    .chip.good { background: #e8f5ee; color: var(--green); border-color: #b9dfc9; }
    .chip.bad { background: #fff0ed; color: var(--red); border-color: #f0bbb2; }
    .chip.warn { background: #fff7df; color: var(--amber); border-color: #ead38a; }
    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-top: 12px;
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      min-height: 64px;
      background: #fbfcfe;
    }
    .label {
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }
    .value {
      font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
      font-size: 14px;
      overflow-wrap: anywhere;
    }
    .camera-wrap {
      aspect-ratio: 4 / 3;
      width: 100%;
      background: #0b0d10;
      border-radius: 8px;
      overflow: hidden;
      border: 1px solid #252a32;
      display: grid;
      place-items: center;
      color: #cbd3df;
      min-height: 240px;
    }
    #camera {
      display: block;
      width: 100%;
      height: 100%;
      object-fit: contain;
    }
    .controls {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }
    button {
      min-height: 42px;
      border-radius: 6px;
      border: 1px solid var(--line);
      background: #ffffff;
      color: var(--ink);
      font-weight: 650;
      cursor: pointer;
    }
    button:hover { border-color: #9aa6b6; background: #f9fafc; }
    button.primary { background: var(--blue); border-color: var(--blue); color: white; }
    button.danger { background: var(--red); border-color: var(--red); color: white; }
    .events {
      display: grid;
      gap: 8px;
      max-height: 420px;
      overflow: auto;
      padding-right: 2px;
    }
    .event {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px;
      background: #fbfcfe;
    }
    .event strong {
      display: block;
      font-size: 13px;
      margin-bottom: 3px;
    }
    .event code {
      display: block;
      color: var(--muted);
      font-size: 12px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    textarea {
      width: 100%;
      min-height: 72px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px;
      font: inherit;
    }
    .stack { display: grid; gap: 14px; }
    @media (max-width: 820px) {
      main { grid-template-columns: 1fr; }
      header { align-items: flex-start; flex-direction: column; }
      .controls { grid-template-columns: 1fr; }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Chasecar Robot Bridge</h1>
    <div class="status-row" id="topStatus">
      <span class="chip warn">Connecting</span>
    </div>
  </header>
  <main>
    <div class="stack">
      <section>
        <h2>Camera</h2>
        <div class="camera-wrap" id="cameraWrap">
          <span id="cameraPlaceholder">Camera waiting</span>
          <img id="camera" alt="Robot camera" hidden>
        </div>
      </section>
      <section>
        <h2>Status</h2>
        <div class="grid">
          <div class="metric"><div class="label">Motion</div><div class="value" id="motion">-</div></div>
          <div class="metric"><div class="label">Motor Backend</div><div class="value" id="backend">-</div></div>
          <div class="metric"><div class="label">Left / Right</div><div class="value" id="motors">-</div></div>
          <div class="metric"><div class="label">Last Stop</div><div class="value" id="stopReason">-</div></div>
          <div class="metric"><div class="label">Commands</div><div class="value" id="commands">-</div></div>
          <div class="metric"><div class="label">Camera</div><div class="value" id="cameraMetric">-</div></div>
          <div class="metric"><div class="label">Uptime</div><div class="value" id="uptime">-</div></div>
        </div>
      </section>
    </div>
    <div class="stack">
      <section>
        <h2>Operator Input</h2>
        <div class="controls">
          <button class="primary" data-event="held_in_air">Held in air</button>
          <button data-event="set_down">Set down</button>
          <button data-event="wheels_moved">Wheels moved</button>
          <button data-event="no_wheel_movement">No movement</button>
          <button data-event="camera_ok">Camera OK</button>
          <button data-event="looks_unsafe">Looks unsafe</button>
          <button class="danger" id="stopButton">STOP</button>
        </div>
        <div style="margin-top: 10px;">
          <textarea id="note" placeholder="Add an operator note"></textarea>
          <button style="margin-top: 8px; width: 100%;" id="noteButton">Save note</button>
        </div>
      </section>
      <section>
        <h2>Recent Events</h2>
        <div class="events" id="events"></div>
      </section>
    </div>
  </main>
  <script>
    const topStatus = document.getElementById("topStatus");
    const camera = document.getElementById("camera");
    const cameraPlaceholder = document.getElementById("cameraPlaceholder");
    const eventsEl = document.getElementById("events");
    let cameraEnabled = false;

    function chip(text, cls) {
      return `<span class="chip ${cls || ""}">${text}</span>`;
    }
    function fixed(value) {
      if (typeof value !== "number") return "-";
      return value.toFixed(3);
    }
    async function postJson(path, body) {
      const response = await fetch(path, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(body || {})
      });
      if (!response.ok) throw new Error(`${path} ${response.status}`);
      return await response.json();
    }
    async function refreshState() {
      try {
        const state = await (await fetch("/health", {cache: "no-store"})).json();
        cameraEnabled = Boolean(state.camera && state.camera.enabled);
        topStatus.innerHTML = [
          chip(state.ok ? "Bridge OK" : "Bridge issue", state.ok ? "good" : "bad"),
          chip(state.motion_enabled ? "Motion enabled" : "Motion disabled", state.motion_enabled ? "bad" : "good"),
          chip(cameraEnabled ? "Camera enabled" : "Camera off", cameraEnabled ? "good" : "warn")
        ].join("");
        document.getElementById("motion").textContent = state.motion_enabled ? "enabled" : "disabled";
        document.getElementById("backend").textContent =
          state.motor_adapter ? state.motor_adapter.backend : "-";
        document.getElementById("motors").textContent =
          `${fixed(state.left_motor)} / ${fixed(state.right_motor)}`;
        document.getElementById("stopReason").textContent = state.last_stop_reason || "-";
        document.getElementById("commands").textContent = String(state.commands_received || 0);
        if (state.camera && state.camera.enabled) {
          const fps = typeof state.camera.cached_fps === "number" ? state.camera.cached_fps.toFixed(1) : "-";
          const age = typeof state.camera.frame_age_s === "number" ? state.camera.frame_age_s.toFixed(2) : "-";
          document.getElementById("cameraMetric").textContent = `${fps} fps / ${age}s old`;
        } else {
          document.getElementById("cameraMetric").textContent = "off";
        }
        document.getElementById("uptime").textContent = `${fixed(state.uptime_s)}s`;
      } catch (error) {
        topStatus.innerHTML = chip("Bridge offline", "bad");
      }
    }
    async function refreshEvents() {
      try {
        const payload = await (await fetch("/events", {cache: "no-store"})).json();
        eventsEl.innerHTML = (payload.events || []).slice().reverse().map(event => {
          const body = JSON.stringify(event.payload || {}, null, 2);
          return `<div class="event"><strong>${event.kind} #${event.seq}</strong><code>${event.utc || ""}\n${body}</code></div>`;
        }).join("") || `<div class="event"><strong>No events yet</strong><code></code></div>`;
      } catch (error) {
        eventsEl.innerHTML = `<div class="event"><strong>Event fetch failed</strong><code>${String(error)}</code></div>`;
      }
    }
    function refreshCamera() {
      if (!cameraEnabled) {
        camera.hidden = true;
        cameraPlaceholder.hidden = false;
        cameraPlaceholder.textContent = "Camera off";
        return;
      }
      camera.hidden = false;
      cameraPlaceholder.hidden = true;
      camera.src = `/camera.jpg?t=${Date.now()}`;
    }
    document.querySelectorAll("button[data-event]").forEach(button => {
      button.addEventListener("click", async () => {
        await postJson("/operator_event", {event: button.dataset.event});
        await refreshEvents();
      });
    });
    document.getElementById("stopButton").addEventListener("click", async () => {
      await postJson("/stop", {source: "dashboard_stop"});
      await postJson("/operator_event", {event: "stop_pressed"});
      await refreshState();
      await refreshEvents();
    });
    document.getElementById("noteButton").addEventListener("click", async () => {
      const note = document.getElementById("note").value.trim();
      if (!note) return;
      await postJson("/operator_event", {event: "operator_note", note});
      document.getElementById("note").value = "";
      await refreshEvents();
    });
    refreshState();
    refreshEvents();
    setInterval(refreshState, 750);
    setInterval(refreshEvents, 1200);
    setInterval(refreshCamera, 500);
  </script>
</body>
</html>
"""


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def finite_float(value, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return number


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class DryRunRobot(object):
    def __init__(self):
        self.left = 0.0
        self.right = 0.0

    def set_motors(self, left, right):
        self.left = float(left)
        self.right = float(right)

    def stop(self):
        self.set_motors(0.0, 0.0)


class YahboomI2CRobot(object):
    def __init__(self, bus_number=1, address=0x1B):
        import smbus

        self.bus = smbus.SMBus(int(bus_number))
        self.address = int(address)
        self.left = 0.0
        self.right = 0.0

    @staticmethod
    def motor_bytes(value):
        value = clamp(finite_float(value), -1.0, 1.0)
        direction = 1 if value >= 0 else 0
        speed = int(round(abs(value) * 255.0))
        return direction, clamp(speed, 0, 255)

    def set_motors(self, left, right):
        left_direction, left_speed = self.motor_bytes(left)
        right_direction, right_speed = self.motor_bytes(right)
        self.bus.write_i2c_block_data(
            self.address,
            0x01,
            [left_direction, left_speed, right_direction, right_speed],
        )
        self.left = float(left)
        self.right = float(right)

    def stop(self):
        self.bus.write_i2c_block_data(self.address, 0x01, [1, 0, 1, 0])
        self.left = 0.0
        self.right = 0.0


class JetbotMiniRobot(object):
    def __init__(self):
        from jetbotmini import Robot

        self.robot = Robot()

    def set_motors(self, left, right):
        self.robot.set_motors(float(left), float(right))

    def stop(self):
        self.robot.stop()


class RobotAdapter(object):
    def __init__(self, dry_run=False, backend="yahboom_i2c", i2c_bus=1, i2c_address=0x1B):
        self.dry_run = bool(dry_run)
        self.backend = str(backend)
        self.i2c_bus = int(i2c_bus)
        self.i2c_address = int(i2c_address)
        self.robot = None
        self.error = None
        self.load()

    def load(self):
        if self.dry_run:
            self.robot = DryRunRobot()
            return
        try:
            if self.backend == "yahboom_i2c":
                self.robot = YahboomI2CRobot(
                    bus_number=self.i2c_bus,
                    address=self.i2c_address,
                )
            elif self.backend == "jetbotmini":
                self.robot = JetbotMiniRobot()
            else:
                raise RuntimeError("unknown_motor_backend:%s" % self.backend)
        except Exception as exc:
            self.error = repr(exc)
            raise

    def set_motors(self, left, right):
        self.robot.set_motors(float(left), float(right))

    def stop(self):
        self.robot.stop()

    def status(self):
        return {
            "backend": self.backend,
            "dry_run": self.dry_run,
            "i2c_bus": self.i2c_bus,
            "i2c_address": "0x%02X" % self.i2c_address,
            "error": self.error,
        }


class CameraAdapter(object):
    def __init__(
        self,
        enabled=False,
        dry_run=False,
        width=320,
        height=240,
        jpeg_quality=55,
        jpeg_fps=5.0,
    ):
        self.enabled = bool(enabled)
        self.dry_run = bool(dry_run)
        self.width = int(width)
        self.height = int(height)
        self.jpeg_quality = int(clamp(int(jpeg_quality), 10, 95))
        self.jpeg_fps = max(0.2, float(jpeg_fps))
        self.camera = None
        self.error = None
        self.latest_jpeg = None
        self.latest_jpeg_monotonic = 0.0
        self.frame_count = 0
        self.encode_count = 0
        self.status_start_monotonic = time.monotonic()
        self.thread = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        if self.enabled:
            self.start()

    def snapshot_jpeg(self):
        if not self.enabled:
            raise RuntimeError("camera_disabled")
        if self.dry_run:
            return base64.b64decode(
                b"/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
                b"////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////"
                b"////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAH/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAEFAqf/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/ASP/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/ASP/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAY/Aqf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/IX//2gAMAwEAAgADAAAAEP/EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQMBAT8QH//EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQIBAT8QH//EABQQAQAAAAAAAAAAAAAAAAAAABD/2gAIAQEAAT8QH//Z"
            )

        self.start()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            with self.lock:
                if self.latest_jpeg:
                    return self.latest_jpeg
                error = self.error
            if error:
                raise RuntimeError(error)
            time.sleep(0.05)
        with self.lock:
            if self.latest_jpeg:
                return self.latest_jpeg
            if self.error:
                raise RuntimeError(self.error)
        raise RuntimeError("camera_frame_unavailable")

    def start(self):
        if self.thread is not None and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._capture_loop)
        self.thread.daemon = True
        self.thread.start()

    def _capture_loop(self):
        if self.dry_run:
            try:
                jpeg = self.snapshot_jpeg()
                with self.lock:
                    self.latest_jpeg = jpeg
                    self.latest_jpeg_monotonic = time.monotonic()
                    self.frame_count += 1
                    self.encode_count += 1
            except Exception as exc:
                with self.lock:
                    self.error = repr(exc)
            return

        interval_s = 1.0 / max(0.2, self.jpeg_fps)
        while not self.stop_event.is_set():
            started = time.monotonic()
            try:
                if self.camera is None:
                    from jetbotmini import Camera, bgr8_to_jpeg

                    self._bgr8_to_jpeg = bgr8_to_jpeg
                    self.camera = Camera.instance(width=self.width, height=self.height)
                    time.sleep(0.4)
                jpeg = self._bgr8_to_jpeg(self.camera.value, quality=self.jpeg_quality)
                with self.lock:
                    self.latest_jpeg = jpeg
                    self.latest_jpeg_monotonic = time.monotonic()
                    self.frame_count += 1
                    self.encode_count += 1
                    self.error = None
            except Exception as exc:
                with self.lock:
                    self.error = repr(exc)
                time.sleep(0.5)
            elapsed = time.monotonic() - started
            time.sleep(max(0.01, interval_s - elapsed))

    def status(self):
        now = time.monotonic()
        with self.lock:
            error = self.error
            frame_age_s = (
                max(0.0, now - self.latest_jpeg_monotonic)
                if self.latest_jpeg_monotonic > 0
                else None
            )
            cached_bytes = len(self.latest_jpeg) if self.latest_jpeg else 0
            frame_count = int(self.frame_count)
            encode_count = int(self.encode_count)
            cached_fps = frame_count / max(now - self.status_start_monotonic, 0.001)
        return {
            "enabled": self.enabled,
            "loaded": self.camera is not None,
            "error": error,
            "width": self.width,
            "height": self.height,
            "jpeg_quality": self.jpeg_quality,
            "target_fps": self.jpeg_fps,
            "cached_fps": round(cached_fps, 3),
            "frame_count": frame_count,
            "encode_count": encode_count,
            "frame_age_s": frame_age_s,
            "cached_bytes": cached_bytes,
        }


class BridgeState(object):
    def __init__(self, args):
        self.args = args
        self.lock = threading.RLock()
        self.robot = RobotAdapter(
            dry_run=args.dry_run,
            backend=args.motor_backend,
            i2c_bus=args.motor_i2c_bus,
            i2c_address=args.motor_i2c_address,
        )
        self.camera = CameraAdapter(
            enabled=args.camera,
            dry_run=args.dry_run,
            width=args.camera_width,
            height=args.camera_height,
            jpeg_quality=args.camera_jpeg_quality,
            jpeg_fps=args.camera_fps,
        )
        self.started_monotonic = time.monotonic()
        self.event_log_path = args.event_log_path
        self.events = []
        self.event_seq = 0
        self.last_command_monotonic = 0.0
        self.command_deadline_monotonic = 0.0
        self.commands_received = 0
        self.last_command = None
        self.left_motor = 0.0
        self.right_motor = 0.0
        self.last_stop_reason = "startup"
        self.stop("startup")

    def now_age(self):
        if self.last_command_monotonic <= 0:
            return None
        return max(0.0, time.monotonic() - self.last_command_monotonic)

    def status(self):
        with self.lock:
            return {
                "ok": True,
                "version": VERSION,
                "dry_run": bool(self.args.dry_run),
                "motion_enabled": bool(self.args.enable_motion),
                "deadman_timeout_s": float(self.args.deadman_timeout_s),
                "max_command_duration_s": float(self.args.max_command_duration_s),
                "max_motor_speed": float(self.args.max_motor_speed),
                "max_linear_x": float(self.args.max_linear_x),
                "max_angular_z": float(self.args.max_angular_z),
                "turn_gain": float(self.args.turn_gain),
                "motor_adapter": self.robot.status(),
                "uptime_s": round(time.monotonic() - self.started_monotonic, 3),
                "commands_received": int(self.commands_received),
                "event_count": int(self.event_seq),
                "last_command_age_s": self.now_age(),
                "last_command": self.last_command,
                "left_motor": self.left_motor,
                "right_motor": self.right_motor,
                "last_stop_reason": self.last_stop_reason,
                "camera": self.camera.status(),
            }

    def record_event(self, kind, payload=None):
        with self.lock:
            return self._record_event_locked(kind, payload)

    def _record_event_locked(self, kind, payload=None):
        self.event_seq += 1
        event = {
            "seq": self.event_seq,
            "kind": str(kind),
            "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "uptime_s": round(time.monotonic() - self.started_monotonic, 3),
            "payload": payload or {},
        }
        self.events.append(event)
        self.events = self.events[-100:]
        if self.event_log_path:
            try:
                parent = os.path.dirname(os.path.abspath(self.event_log_path))
                if parent and not os.path.isdir(parent):
                    os.makedirs(parent)
                with open(self.event_log_path, "a") as handle:
                    handle.write(json.dumps(event, sort_keys=True) + "\n")
            except Exception:
                traceback.print_exc()
        return event

    def recent_events(self):
        with self.lock:
            return list(self.events)

    def stop(self, reason):
        with self.lock:
            self.robot.stop()
            self.left_motor = 0.0
            self.right_motor = 0.0
            self.command_deadline_monotonic = 0.0
            self.last_stop_reason = str(reason)
            self._record_event_locked("stop", {"reason": str(reason)})

    def cmd_vel_to_motors(self, linear_x, angular_z):
        max_linear = max(0.001, abs(float(self.args.max_linear_x)))
        max_angular = max(0.001, abs(float(self.args.max_angular_z)))
        linear_unit = clamp(float(linear_x) / max_linear, -1.0, 1.0)
        angular_unit = clamp(float(angular_z) / max_angular, -1.0, 1.0)

        left = linear_unit - (float(self.args.turn_gain) * angular_unit)
        right = linear_unit + (float(self.args.turn_gain) * angular_unit)
        max_abs = max(1.0, abs(left), abs(right))
        left = left / max_abs
        right = right / max_abs
        return self.scale_motor_units(left, right)

    def scale_motor_units(self, left, right):
        max_speed = clamp(abs(float(self.args.max_motor_speed)), 0.0, 1.0)
        left = clamp(finite_float(left), -1.0, 1.0) * max_speed
        right = clamp(finite_float(right), -1.0, 1.0) * max_speed
        left *= float(self.args.left_sign)
        right *= float(self.args.right_sign)
        return clamp(left, -1.0, 1.0), clamp(right, -1.0, 1.0)

    def clamp_motor_values(self, left, right):
        max_speed = clamp(abs(float(self.args.max_motor_speed)), 0.0, 1.0)
        left = clamp(finite_float(left), -max_speed, max_speed)
        right = clamp(finite_float(right), -max_speed, max_speed)
        left *= float(self.args.left_sign)
        right *= float(self.args.right_sign)
        return clamp(left, -1.0, 1.0), clamp(right, -1.0, 1.0)

    def apply_prepared_motors(self, left, right, duration_s, source):
        if not self.args.enable_motion:
            self.stop("motion_disabled")
            raise RuntimeError("motion_disabled")
        with self.lock:
            duration_s = finite_float(duration_s, self.args.deadman_timeout_s)
            duration_s = clamp(duration_s, 0.0, float(self.args.max_command_duration_s))
            now = time.monotonic()
            self.robot.set_motors(left, right)
            self.left_motor = left
            self.right_motor = right
            self.last_command_monotonic = now
            self.command_deadline_monotonic = now + duration_s if duration_s > 0 else 0.0
            self.commands_received += 1
            self.last_command = {
                "source": str(source),
                "left": left,
                "right": right,
                "duration_s": duration_s,
            }
            self._record_event_locked("motor_command", self.last_command)
            return self.status()

    def apply_motors(self, left, right, duration_s, source):
        left, right = self.clamp_motor_values(left, right)
        return self.apply_prepared_motors(left, right, duration_s, source)

    def apply_cmd_vel(self, linear_x, angular_z, duration_s, source):
        left, right = self.cmd_vel_to_motors(linear_x, angular_z)
        status = self.apply_prepared_motors(left, right, duration_s, source)
        status["cmd_vel"] = {"linear_x": linear_x, "angular_z": angular_z}
        return status

    def enforce_deadman_once(self):
        with self.lock:
            now = time.monotonic()
            moving = abs(self.left_motor) > 0.0001 or abs(self.right_motor) > 0.0001
            if not moving:
                return
            stale = self.last_command_monotonic > 0 and (
                now - self.last_command_monotonic > float(self.args.deadman_timeout_s)
            )
            expired = self.command_deadline_monotonic > 0 and now >= self.command_deadline_monotonic
            if stale:
                self.stop("deadman_timeout")
            elif expired:
                self.stop("command_duration_elapsed")

    def deadman_loop(self):
        while True:
            try:
                self.enforce_deadman_once()
            except Exception:
                traceback.print_exc()
                try:
                    self.stop("deadman_error")
                except Exception:
                    pass
            time.sleep(0.05)


class BridgeHandler(http.server.BaseHTTPRequestHandler):
    server_version = "ChasecarFactoryBridge/%s" % VERSION

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - - [%s] %s\n" % (
            self.client_address[0],
            self.log_date_time_string(),
            fmt % args,
        ))

    @property
    def bridge(self):
        return self.server.bridge

    def write_json(self, payload, status=200):
        data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/dashboard", "/ui"):
            data = DASHBOARD_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if parsed.path in ("/", "/health", "/state"):
            self.write_json(self.bridge.status())
            return
        if parsed.path == "/events":
            self.write_json({"ok": True, "events": self.bridge.recent_events()})
            return
        if parsed.path == "/camera.jpg":
            try:
                jpeg = self.bridge.camera.snapshot_jpeg()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Cache-Control", "no-store, max-age=0")
                self.send_header("Content-Length", str(len(jpeg)))
                self.end_headers()
                self.wfile.write(jpeg)
            except Exception as exc:
                self.write_json({"ok": False, "error": repr(exc)}, status=503)
            return
        self.write_json({"ok": False, "error": "not_found"}, status=404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        try:
            payload = self.read_json()
            if parsed.path == "/stop":
                source = payload.get("source", "api_stop")
                self.bridge.stop(source)
                self.write_json(self.bridge.status())
                return
            if parsed.path == "/operator_event":
                event = self.bridge.record_event(
                    "operator:%s" % payload.get("event", "event"),
                    payload,
                )
                self.write_json({"ok": True, "event": event, "state": self.bridge.status()})
                return
            if parsed.path == "/motors":
                status = self.bridge.apply_motors(
                    finite_float(payload.get("left")),
                    finite_float(payload.get("right")),
                    finite_float(payload.get("duration_s"), self.bridge.args.deadman_timeout_s),
                    payload.get("source", "api_motors"),
                )
                self.write_json(status)
                return
            if parsed.path == "/cmd_vel":
                status = self.bridge.apply_cmd_vel(
                    finite_float(payload.get("linear_x")),
                    finite_float(payload.get("angular_z")),
                    finite_float(payload.get("duration_s"), self.bridge.args.deadman_timeout_s),
                    payload.get("source", "api_cmd_vel"),
                )
                self.write_json(status)
                return
            self.write_json({"ok": False, "error": "not_found"}, status=404)
        except RuntimeError as exc:
            self.bridge.record_event("motion_refused", {"error": str(exc), "path": parsed.path})
            self.write_json({"ok": False, "error": str(exc), "state": self.bridge.status()}, status=423)
        except Exception as exc:
            traceback.print_exc()
            try:
                self.bridge.stop("api_error")
            except Exception:
                pass
            self.write_json({"ok": False, "error": repr(exc), "state": self.bridge.status()}, status=500)


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Run the Chasecar factory robot bridge.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--enable-motion", action="store_true")
    parser.add_argument("--camera", action="store_true")
    parser.add_argument("--camera-width", type=int, default=320)
    parser.add_argument("--camera-height", type=int, default=240)
    parser.add_argument("--camera-fps", type=float, default=5.0)
    parser.add_argument("--camera-jpeg-quality", type=int, default=55)
    parser.add_argument("--deadman-timeout-s", type=float, default=0.5)
    parser.add_argument("--max-command-duration-s", type=float, default=1.0)
    parser.add_argument("--max-motor-speed", type=float, default=0.35)
    parser.add_argument("--max-linear-x", type=float, default=0.6)
    parser.add_argument("--max-angular-z", type=float, default=2.5)
    parser.add_argument("--turn-gain", type=float, default=0.7)
    parser.add_argument("--left-sign", type=float, default=1.0)
    parser.add_argument("--right-sign", type=float, default=1.0)
    parser.add_argument("--motor-backend", choices=["yahboom_i2c", "jetbotmini"], default="yahboom_i2c")
    parser.add_argument("--motor-i2c-bus", type=int, default=1)
    parser.add_argument("--motor-i2c-address", type=lambda value: int(value, 0), default=0x1B)
    parser.add_argument("--event-log-path", default="operator_events.jsonl")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def run_self_test():
    args = parse_args(["--dry-run", "--enable-motion", "--event-log-path", ""])
    bridge = BridgeState(args)
    left, right = bridge.cmd_vel_to_motors(0.6, 0.0)
    assert abs(left - 0.35) < 1e-6
    assert abs(right - 0.35) < 1e-6
    left, right = bridge.cmd_vel_to_motors(0.0, 2.5)
    assert abs(left + 0.245) < 1e-6
    assert abs(right - 0.245) < 1e-6
    bridge.apply_motors(1.0, -1.0, 0.1, "self_test")
    assert bridge.left_motor == 0.35
    assert bridge.right_motor == -0.35
    time.sleep(0.15)
    bridge.enforce_deadman_once()
    assert bridge.left_motor == 0.0
    assert bridge.right_motor == 0.0
    print("SELF_TEST_OK=1")


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    if args.self_test:
        run_self_test()
        return 0

    bridge = BridgeState(args)
    deadman_thread = threading.Thread(target=bridge.deadman_loop)
    deadman_thread.daemon = True
    deadman_thread.start()

    server = ThreadingHTTPServer((args.host, args.port), BridgeHandler)
    server.bridge = bridge
    print("CHASECAR_FACTORY_BRIDGE_READY=1 host=%s port=%s motion_enabled=%s camera=%s" % (
        args.host,
        args.port,
        bool(args.enable_motion),
        bool(args.camera),
    ))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        bridge.stop("shutdown")
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
