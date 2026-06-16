# Chasecar Robot Beacon USB

This folder is meant to be copied to a USB thumbdrive and run once from the
Jetson. It installs a small no-motion systemd service that emits a network
beacon after boot.

## On The Jetson

For a first local login, run the no-motion probe first:

```bash
bash first_boot_probe.sh
```

Send the output to Codex. After SSH and network basics are understood, install
the optional boot-time beacon:

```bash
bash install_beacon_service.sh
```

The installer copies `chasecar_beacon.py` to `/opt/chasecar-beacon`, installs
`chasecar-beacon.service`, enables it, and starts it.

## What It Emits

- UDP broadcast on port `45454`.
- HTTP JSON endpoint on port `8765`.
- Local JSON snapshot at `/tmp/chasecar_beacon.json`.

The beacon includes hostname, user, LAN IPs, Tailscale IPs when available, and a
timestamp. It sends no robot movement commands.

## On Windows

From the Chasecar worktree:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/find_robot_beacon.ps1 -TimeoutSeconds 30
```

When the beacon appears, use its IP with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_robot_direct_access.ps1 -RobotHost <ip> -RobotUser <user>
```
