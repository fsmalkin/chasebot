#!/usr/bin/env bash
set -euo pipefail

export ACCEPT_EULA=Y
export PRIVACY_CONSENT=Y

if [[ -x "/isaac-sim/runheadless.native.sh" ]]; then
  cd /isaac-sim
  exec ./runheadless.native.sh --allow-root
fi

if [[ -x "./runheadless.native.sh" ]]; then
  exec ./runheadless.native.sh --allow-root
fi

echo "[sim-isaac] Isaac headless launcher not found in image. Keeping container alive for bridge-only workflows."
exec sleep infinity
