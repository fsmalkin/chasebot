#!/usr/bin/env python3
"""Emit a no-motion Chasecar robot discovery beacon."""

from __future__ import annotations

import argparse
import getpass
import http.server
import json
import socket
import subprocess
import threading
import time
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any


STATE: dict[str, Any] = {}
STATE_LOCK = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_text(command: list[str]) -> str:
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=3)
    except Exception:
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def split_ips(text: str) -> list[str]:
    return [part.strip() for part in text.split() if part.strip()]


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    hostname = socket.gethostname()
    lan_ips = split_ips(run_text(["hostname", "-I"]))
    tailscale_ips = split_ips(run_text(["tailscale", "ip", "-4"]))
    return {
        "type": "chasecar_robot_beacon",
        "generated_utc": utc_now(),
        "hostname": hostname,
        "user": getpass.getuser(),
        "lan_ips": lan_ips,
        "tailscale_ips": tailscale_ips,
        "ssh_targets": [f"{getpass.getuser()}@{ip}" for ip in [*tailscale_ips, *lan_ips]],
        "http_port": int(args.http_port),
        "udp_port": int(args.udp_port),
        "motion_commands_sent": False,
        "note": "No-motion discovery beacon only.",
    }


class BeaconHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
        if self.path not in ("/", "/beacon.json"):
            self.send_response(404)
            self.end_headers()
            return
        with STATE_LOCK:
            payload = dict(STATE)
        data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, _format: str, *_args: Any) -> None:
        return


def start_http_server(port: int) -> None:
    server = http.server.ThreadingHTTPServer(("0.0.0.0", port), BeaconHandler)
    server.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit Chasecar robot discovery beacon.")
    parser.add_argument("--udp-port", type=int, default=45454)
    parser.add_argument("--http-port", type=int, default=8765)
    parser.add_argument("--interval-s", type=float, default=5.0)
    parser.add_argument("--snapshot-path", default="/tmp/chasecar_beacon.json")
    args = parser.parse_args()

    http_thread = threading.Thread(target=start_http_server, args=(args.http_port,), daemon=True)
    http_thread.start()

    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    snapshot_path = Path(args.snapshot_path)
    while True:
        payload = build_payload(args)
        with STATE_LOCK:
            STATE.clear()
            STATE.update(payload)
        snapshot_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        data = json.dumps(payload, sort_keys=True).encode("utf-8")
        udp.sendto(data, ("255.255.255.255", int(args.udp_port)))
        time.sleep(max(float(args.interval_s), 1.0))


if __name__ == "__main__":
    raise SystemExit(main())
