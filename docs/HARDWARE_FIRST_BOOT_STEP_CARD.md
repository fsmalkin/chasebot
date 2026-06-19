# Hardware First Boot Step Card

Use this card for the live bench session. The goal is one safe step at a time:
local login first, network second, Codex SSH access third.

## Current Step

Set up local console access.

1. Leave any extra USB camera unplugged.
2. Put the robot on a stable table.
3. Lift the wheels or disconnect motor power if the layout makes that easy.
4. Connect a monitor through the display port available on the active board.
5. Connect USB keyboard and mouse.
6. Leave the existing USB Wi-Fi dongle attached.
7. Connect Ethernet if it is easy to reach.
8. Connect Jetson power.

Tell Codex what appears on the monitor:

```text
first-boot setup / login screen / desktop / terminal / blank screen / error
```

## If First-Boot Setup Appears

Create a known local account and record:

```text
username:
password:
computer name / hostname:
```

## If A Login Screen Appears

Try only credentials that came with the robot, image, or project notes. Record:

```text
username tried:
result:
hostname shown, if visible:
```

If login recovery fails, use the reimage path in
`docs/HARDWARE_BENCH_CONNECTION_RUNBOOK.md`.

## First Terminal Command After Login

Run this on the Jetson:

```bash
hostname; whoami; hostname -I; ip -brief addr
```

Send Codex the output. Codex will then try SSH from Windows.

If the USB thumbdrive is mounted and the `chasecar-beacon` folder is visible,
you can run the richer no-motion probe instead:

```bash
cd /media/$USER/*/chasecar-beacon 2>/dev/null || cd /run/media/$USER/*/chasecar-beacon
bash first_boot_probe.sh
```

Send Codex the full output.

## First Codex Command After IP Is Known

Codex runs this from `D:\dev\chasecar-hw-v0`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_robot_direct_access.ps1 -RobotHost <jetson-ip> -RobotUser <jetson-user> -AllowPasswordPrompt
```

This command sends no movement commands.

## Stop Conditions

Stop and report the exact symptom on:

- Power LED failure.
- Blank monitor after two minutes.
- Boot loop.
- Hot electronics or unusual smell.
- Login unknown.
- No IP address after Ethernet or Wi-Fi setup.
