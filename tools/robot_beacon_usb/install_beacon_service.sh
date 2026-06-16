#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/chasecar-beacon"
SERVICE_PATH="/etc/systemd/system/chasecar-beacon.service"
RUN_USER="${SUDO_USER:-$USER}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required before installing the Chasecar beacon." >&2
  exit 1
fi

sudo mkdir -p "$INSTALL_DIR"
sudo cp "$SCRIPT_DIR/chasecar_beacon.py" "$INSTALL_DIR/chasecar_beacon.py"
sudo chmod 755 "$INSTALL_DIR/chasecar_beacon.py"

sudo tee "$SERVICE_PATH" >/dev/null <<SERVICE
[Unit]
Description=Chasecar no-motion robot discovery beacon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
ExecStart=/usr/bin/python3 $INSTALL_DIR/chasecar_beacon.py --udp-port 45454 --http-port 8765
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable --now chasecar-beacon.service
sudo systemctl --no-pager status chasecar-beacon.service || true

echo "CHASECAR_BEACON_INSTALLED=1"
echo "Local snapshot: /tmp/chasecar_beacon.json"
echo "UDP port: 45454"
echo "HTTP port: 8765"
hostname -I | sed 's/^/LAN_IPS=/'
if command -v tailscale >/dev/null 2>&1; then
  tailscale ip -4 2>/dev/null | sed 's/^/TAILSCALE_IP=/'
fi
