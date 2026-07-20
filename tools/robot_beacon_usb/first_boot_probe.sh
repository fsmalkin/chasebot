#!/usr/bin/env bash
set -euo pipefail

echo "CHASECAR_FIRST_BOOT_PROBE=1"
echo "generated_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "hostname=$(hostname 2>/dev/null || true)"
echo "user=$(whoami 2>/dev/null || true)"
echo "kernel=$(uname -a 2>/dev/null || true)"

if [ -f /etc/os-release ]; then
  . /etc/os-release
  echo "os_name=${PRETTY_NAME:-unknown}"
fi

echo ""
echo "== Network =="
hostname -I 2>/dev/null | sed 's/^/hostname_I=/'
ip -brief addr 2>/dev/null || true

echo ""
echo "== SSH Service =="
if command -v systemctl >/dev/null 2>&1; then
  systemctl is-enabled ssh 2>/dev/null | sed 's/^/ssh_enabled=/' || echo "ssh_enabled=unknown"
  systemctl is-active ssh 2>/dev/null | sed 's/^/ssh_active=/' || echo "ssh_active=unknown"
else
  echo "systemctl=missing"
fi

echo ""
echo "== Tools =="
for cmd in git python3 ros2 tailscale rs-enumerate-devices; do
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "$cmd=$(command -v "$cmd")"
  else
    echo "$cmd=MISSING"
  fi
done

echo ""
echo "== USB Devices =="
if command -v lsusb >/dev/null 2>&1; then
  lsusb
else
  echo "lsusb=MISSING"
fi

echo ""
echo "== D415 / RealSense Quick Check =="
if command -v rs-enumerate-devices >/dev/null 2>&1; then
  rs-enumerate-devices | head -n 120
else
  echo "rs-enumerate-devices=MISSING"
fi

echo ""
echo "== Tailscale =="
if command -v tailscale >/dev/null 2>&1; then
  tailscale ip -4 2>/dev/null | sed 's/^/tailscale_ip=/'
  tailscale status 2>/dev/null | head -n 20
else
  echo "tailscale=MISSING"
fi

echo ""
echo "== Next Command =="
echo "Send this output to Codex. If hostname_I contains an IP, Codex can try SSH next."
