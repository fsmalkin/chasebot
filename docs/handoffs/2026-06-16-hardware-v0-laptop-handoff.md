# Hardware V0 Laptop Handoff

Use this handoff when continuing the first hardware bring-up from a Codex thread
on the laptop or another machine physically near the robot.

## Goal

Get Codex to safe direct access on the Jetson as quickly as possible:

1. Prepare a USB thumbdrive with no-motion helper scripts.
2. Boot or log into the Jetson locally.
3. Run the first-boot probe from the thumbdrive.
4. Use the reported IP and username for Codex SSH preflight.
5. Stop before movement commands until lifted-wheel and deadman checks pass.

## Repo State

Branch:

```text
codex/hw-irl-v0-bringup
```

Primary files:

- `docs/HARDWARE_FIRST_BOOT_STEP_CARD.md`
- `docs/HARDWARE_BENCH_CONNECTION_RUNBOOK.md`
- `docs/HARDWARE_V0_DEPLOYMENT_PLAN.md`
- `scripts/prepare_robot_beacon_usb.ps1`
- `scripts/check_robot_direct_access.ps1`
- `scripts/find_robot_ssh_candidates.ps1`
- `scripts/find_robot_beacon.ps1`
- `tools/robot_beacon_usb/`

## Laptop Codex Prompt

Paste this into the laptop Codex thread after checking out the branch:

```text
We are continuing Chasecar Hardware V0 bring-up from branch codex/hw-irl-v0-bringup.
Work one step at a time in chat.
The robot is new out of the box. Do not assume SSH, Tailscale, or beacon is installed.
First task: prepare the USB thumbdrive with scripts/prepare_robot_beacon_usb.ps1, then walk me through running tools/robot_beacon_usb/first_boot_probe.sh on the Jetson after local login.
No motion commands are allowed. The first acceptable Codex command against the robot is scripts/check_robot_direct_access.ps1 after the Jetson prints an IP address and username.
```

## Laptop Sequence

1. Confirm the branch:

```powershell
git status -sb
```

2. Detect the USB thumbdrive:

```powershell
Get-Volume | Select-Object DriveLetter,FileSystemLabel,DriveType,FileSystem,SizeRemaining,Size | Sort-Object DriveLetter | Format-Table -AutoSize
Get-Disk | Select-Object Number,FriendlyName,BusType,OperationalStatus,PartitionStyle,Size | Sort-Object Number | Format-Table -AutoSize
```

3. Prepare the thumbdrive once a removable drive letter is visible:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/prepare_robot_beacon_usb.ps1 -UsbRoot <drive-letter>:
```

4. On the Jetson, after local login, run:

```bash
cd /media/$USER/*/chasecar-beacon 2>/dev/null || cd /run/media/$USER/*/chasecar-beacon
bash first_boot_probe.sh
```

5. Send the probe output to Codex.

6. Codex tries no-motion SSH preflight:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_robot_direct_access.ps1 -RobotHost <jetson-ip> -RobotUser <jetson-user> -AllowPasswordPrompt
```

## Boundaries

- The USB helper sends no movement commands.
- The first-boot probe only prints host, network, SSH, USB, RealSense, and
  Tailscale state.
- The optional beacon service is installed only after local login and operator
  confirmation.
- Motion commands start only after the controller/deadman/lifted-wheel checks
  in the hardware plan pass.

## Current Known State

Remote desktop session on `D:\dev\chasecar-hw-v0` could not see the local
thumbdrive because the user was connected to a remote machine. Network scans
from that remote machine found no Jetson SSH host, no Tailscale Jetson, and no
beacon, which is expected for new out-of-box hardware.
