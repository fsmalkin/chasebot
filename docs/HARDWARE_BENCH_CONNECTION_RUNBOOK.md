# Hardware Bench Connection Runbook

Last researched: 2026-06-16.

This runbook starts at the physical bench: power, network, Intel RealSense D415,
and first remote access. The exit condition is simple: Codex can reach the
Jetson over SSH and run the no-motion preflight from
`scripts/check_robot_direct_access.ps1`.

## What We Are Building

The first useful hardware state is direct, safe command access:

1. Jetson Orin Nano boots from known storage.
2. The operator can log in locally.
3. Network access works.
4. SSH works from the Windows machine.
5. The D415 is connected by USB and visible to Linux.
6. Codex can run no-motion checks.

Wheel movement, motor power, and autonomous control stay out of scope for this
runbook.

## Fresh Out-Of-Box Expectation

A new Jetson normally has no Chasecar beacon, no Tailscale identity, and no SSH
account that Codex can use. The first live goal is local first boot:

1. Boot the Jetson with monitor, keyboard, mouse, and network.
2. Create or recover the Linux user account.
3. Confirm the Jetson has an IP address.
4. Enable SSH.
5. Hand Codex the host/IP and username for the no-motion access preflight.

The Wi-Fi dongle may reconnect automatically only if the image was configured
beforehand. Treat remote discovery as a quick check; treat local first boot as
the normal path for new hardware.

## Parts On The Bench

Gather these before power-on:

- Jetson Orin Nano Developer Kit.
- Included 19 V Jetson power supply.
- Boot storage: microSD card or NVMe SSD already prepared for Jetson Linux.
- DisplayPort monitor, DisplayPort cable or DisplayPort-to-HDMI adapter, USB
  keyboard, and USB mouse.
- Ethernet cable for the first network path.
- Existing USB Wi-Fi dongle, if it is already attached to the robot.
- Intel RealSense D415.
- USB 3 data cable for the D415. The D415 side is USB Type-C. Use a certified
  USB Type-C cable or a reliable USB-C-to-USB-A 3.x data cable. Charger-only
  cables are a common failure mode.
- Optional: phone or laptop camera for photos of cable state and LED state.

## Physical Safety Setup

Before connecting power:

1. Put the robot on a stable table.
2. Lift the wheels or disconnect motor power if the hardware layout allows it.
3. Keep a hand-reachable power disconnect available.
4. Route the D415 cable with enough slack for table movement and camera strain
   relief.
5. Keep the robot pointed away from people and fragile objects.

Stop immediately if any board, cable, or regulator gets hot, smells unusual,
shows visible damage, or makes unexpected noise.

## Step 1: Identify Jetson Ports

Use the Jetson Orin Nano Developer Kit layout as the map:

- DC power jack: use the included 19 V power supply.
- Power indicator LED: confirms board power.
- DisplayPort: the only display output.
- USB 3.2 Type-A ports: good first choice for keyboard, mouse, and D415.
- USB-C port: data/recovery/device mode.
- Gigabit Ethernet: preferred first network path.

Decision:

- Use DisplayPort plus keyboard/mouse for the first boot if you have them.
- Use Ethernet for the first network path if the robot can reach your router or
  switch.
- Treat headless serial as an advanced fallback.

## Step 2: First Power-On Without The D415

Leave the D415 unplugged for the first boot. This keeps the first failure
surface small.

1. Insert the boot microSD or confirm the NVMe SSD is installed.
2. Connect DisplayPort monitor.
3. Connect USB keyboard and mouse.
4. Connect Ethernet.
5. Connect the included 19 V power supply.
6. Confirm the power LED turns on.
7. Wait for the first-boot or login screen.

Evidence to capture:

- Photo of the power/cable layout.
- Whether the power LED turned on.
- What appeared on the monitor.
- Jetson username created or already known.

Stop here on power LED failure, blank display, or repeated boot loops.

## Step 3: Local Login And OS Snapshot

On the Jetson terminal:

```bash
hostname
whoami
uname -a
cat /etc/os-release
df -h
free -h
```

If available:

```bash
nvpmodel -q
tegrastats
```

Record:

- Username.
- Hostname.
- Jetson Linux or Ubuntu version.
- Storage free space.
- Whether `tegrastats` works.

## Step 4: Bring Up Network

Start with Ethernet:

```bash
ip addr show
hostname -I
ping -c 3 1.1.1.1
ping -c 3 github.com
```

Record the IPv4 address from `hostname -I`. If Ethernet is unavailable, connect
Wi-Fi through the desktop network UI and rerun the commands.

Decision:

- Same LAN: use the LAN IPv4 address for the first SSH test.
- Different networks or mobile access: install Tailscale after SSH is stable
  locally, then use the Tailscale IPv4 address.

Existing USB Wi-Fi dongle path:

- Leave the dongle attached for first inspection.
- If the Jetson has already been configured for your Wi-Fi, it may join the
  network automatically after boot.
- Check the router client list for names containing `jetson`, `ubuntu`,
  `nvidia`, or `chasecar`.
- From Windows, scan the local subnet for SSH candidates:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/find_robot_ssh_candidates.ps1
```

If your network is not the Windows machine's default /24 subnet, pass it
explicitly:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/find_robot_ssh_candidates.ps1 -Subnets 192.168.1.0/24
```

For each candidate, try a hostname-only command with a username you know or a
username from the Jetson first-boot screen:

```powershell
ssh <user>@<candidate-ip> hostname
```

The scanner only checks whether TCP port 22 is open. It does not identify the
robot by itself, and it sends no credentials.

## Step 4A: Login, Default Account, And Reset Decision

Current NVIDIA setup guides finish first boot by creating a username, password,
and computer name. Treat that created account as the normal login. A universal
default username/password is not part of the current official Orin Nano setup
path.

Try this order:

1. Use the username/password written down during the Jetson first boot.
2. Check labels, old project notes, SD card notes, or the image provider's
   documentation for a pre-created account.
3. Try only credentials that came with the image or robot kit.
4. When login recovery fails, reimage or reinstall Jetson Linux, then create a
   fresh known account during first boot.

Reset/reimage boundary:

- Reimaging is the cleanest way to get known credentials.
- Reimaging erases the selected target storage, so confirm whether valuable
  files exist on the current microSD/NVMe first.
- The USB thumbdrive can be used as NVIDIA Jetson installation media. The
  current JetPack 7.2 path uses it to install Jetson Linux onto target storage
  rather than to boot a full live desktop environment.

## Step 5: Enable SSH

On the Jetson:

```bash
sudo apt update
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
systemctl status ssh --no-pager
hostname -I
```

From Windows PowerShell:

```powershell
ssh <jetson-user>@<jetson-ip>
```

If password login works, keep the session open and continue to SSH key setup.

## Step 6: Add A Windows SSH Key For Codex

On Windows PowerShell, check for an existing public key:

```powershell
Get-ChildItem $env:USERPROFILE\.ssh\*.pub
```

If there is no key:

```powershell
ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\chasecar_hw_v0 -C "chasecar-hw-v0"
```

Show the public key:

```powershell
Get-Content $env:USERPROFILE\.ssh\chasecar_hw_v0.pub
```

On the Jetson, append that one-line public key to `authorized_keys`:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
nano ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

From Windows, test key login:

```powershell
ssh -i $env:USERPROFILE\.ssh\chasecar_hw_v0 <jetson-user>@<jetson-ip> hostname
```

If you want the standard `ssh <user>@<host>` command to use this key, add a
Windows SSH config entry:

```powershell
notepad $env:USERPROFILE\.ssh\config
```

Example:

```text
Host chasecar-jetson
    HostName <jetson-ip-or-tailscale-ip>
    User <jetson-user>
    IdentityFile ~/.ssh/chasecar_hw_v0
```

Then test:

```powershell
ssh chasecar-jetson hostname
```

## Step 7: Optional Tailscale Access

Use Tailscale when the Windows machine and Jetson are not always on the same
LAN, or when you want mobile-friendly dashboard URLs later.

On the Jetson:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
tailscale ip -4
tailscale status
```

Follow the authentication URL printed by `sudo tailscale up`. Record the
Tailscale IPv4 address.

From Windows:

```powershell
ssh <jetson-user>@<tailscale-ip> hostname
```

If you created an SSH config entry, update `HostName` to the Tailscale IP after
the Tailscale test passes.

## Step 8: USB Thumbdrive Beacon Option After First Login

A USB thumbdrive can accelerate future discovery after the first local login.
Linux systems should not autorun arbitrary USB scripts for safety, so the
practical sequence is:

1. Prepare the thumbdrive on Windows.
2. Plug it into the Jetson after local login.
3. Run the installer once.
4. Reboot the Jetson.
5. Listen for the beacon from Windows.

Prepare the thumbdrive from this worktree:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/prepare_robot_beacon_usb.ps1 -UsbRoot <drive-root>
```

Example:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/prepare_robot_beacon_usb.ps1 -UsbRoot E:\
```

On the Jetson, open the USB drive, open `chasecar-beacon`, and run the
first-boot probe:

```bash
bash first_boot_probe.sh
```

Send the output to Codex. The probe sends no motion commands and reports
hostname, IP address, SSH status, USB devices, RealSense tool status, and
Tailscale status.

After Codex confirms the network and SSH state, install the optional boot-time
beacon:

```bash
bash install_beacon_service.sh
```

The installed service emits:

- UDP beacon on port `45454`.
- HTTP JSON endpoint on port `8765`.
- Local JSON snapshot at `/tmp/chasecar_beacon.json`.

From Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/find_robot_beacon.ps1 -TimeoutSeconds 30
```

If a beacon appears, use the reported IP and user with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_robot_direct_access.ps1 -RobotHost <reported-ip> -RobotUser <reported-user>
```

Cold-boot boundary:

- After this service is installed once, later Jetson boots can emit the beacon
  automatically.
- A fresh thumbdrive by itself is best treated as an installer and payload
  shuttle. Turning it into the full boot device is a later Jetson boot-media
  task, because the NVIDIA path involves boot media, firmware, and target
  storage decisions.

## Step 9: Connect The D415

Keep the robot still and wheels lifted.

1. Leave the Jetson powered on and logged in.
2. Plug the D415 USB Type-C side into the D415.
3. Plug the other end into a Jetson USB 3.2 Type-A port or the Jetson USB-C host
   data port.
4. Use a direct Jetson port for first bring-up.
5. Add temporary strain relief so cable movement keeps the camera stable.

On the Jetson:

```bash
lsusb
dmesg | tail -n 80
```

Look for an Intel or RealSense USB device. On missing camera output:

1. Try another Jetson USB 3.2 Type-A port.
2. Flip the USB-C plug at the D415 side.
3. Try a different certified USB 3 data cable.
4. Remove hubs or extension cables.
5. Reboot once with the D415 already connected.

Evidence:

- Photo of the D415 cable path.
- `lsusb` output.
- `dmesg` tail after plug-in.

## Step 10: Install Or Verify RealSense Tools

First check whether the tools are already present:

```bash
command -v rs-enumerate-devices || true
command -v realsense-viewer || true
```

If tools are missing and the Jetson has internet access, use the RealSense
Ubuntu package path first:

```bash
sudo mkdir -p /etc/apt/keyrings
curl -sSf https://librealsense.realsenseai.com/Debian/librealsenseai.asc | gpg --dearmor | sudo tee /etc/apt/keyrings/librealsenseai.gpg > /dev/null
sudo apt-get install -y apt-transport-https
echo "deb [signed-by=/etc/apt/keyrings/librealsenseai.gpg] https://librealsense.realsenseai.com/Debian/apt-repo $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/librealsense.list
sudo apt-get update
sudo apt-get install -y librealsense2-utils librealsense2-dev
```

Reconnect the D415, then run:

```bash
rs-enumerate-devices
```

If package installation fails because of the Jetson kernel, pause and capture
the error. The Jetson-specific RealSense path may require choosing between
native kernel drivers and the RSUSB backend. Treat that as a separate software
fix instead of changing random kernel settings during bench bring-up.

## Step 11: Run Codex Direct-Access Preflight

Once Windows can SSH into the Jetson, give Codex:

```text
robot host/IP:
robot username:
known repo path on robot, if any:
SSH key already set up, or password prompt OK?
```

Codex runs:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_robot_direct_access.ps1 -RobotHost <robot-host-or-ip> -RobotUser <robot-user>
```

If the repo path is known:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_robot_direct_access.ps1 -RobotHost <robot-host-or-ip> -RobotUser <robot-user> -RobotRepoPath <path-on-robot>
```

Pass criteria:

- `direct_access_ready=true`
- `motion_commands_sent=false`
- SSH identity and tooling checks pass.
- `ros_command_ready=true` if ROS is already installed and visible.
- `runtime_update_ready=true` if the repo/runtime path already exists.

## Troubleshooting Table

| Symptom | First checks |
| --- | --- |
| Jetson power LED stays off | Confirm included 19 V supply, DC barrel seated, outlet works. |
| No display | Use the Jetson DisplayPort output. Try a DisplayPort-to-HDMI adapter from that port. |
| No network IP | Check Ethernet link light, router DHCP list, `ip addr show`, then try Wi-Fi UI. |
| SSH refused | Install/start `openssh-server`, confirm `systemctl status ssh`, use the current IP. |
| SSH password works but key fails | Check `~/.ssh` permissions, `authorized_keys` permissions, and the exact public key line. |
| D415 absent from `lsusb` | Try another USB 3 port, certified data cable, flipped USB-C plug, and no hub. |
| D415 appears but RealSense tools fail | Capture `rs-enumerate-devices` and `dmesg`; pause before kernel or SDK changes. |
| Tailscale command missing | Install Tailscale only after LAN SSH works, then authenticate with `sudo tailscale up`. |

## Evidence Template

```text
Bench date:
Operator:
Jetson username:
Jetson hostname:
LAN IP:
Tailscale IP:
SSH config host:
D415 lsusb line:
RealSense tool result:
Photos captured:
Codex preflight artifact:
Open blockers:
```

## Sources

- NVIDIA Jetson Orin Nano Developer Kit Quick Start Guide: https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/quick_start.html
- NVIDIA Jetson Orin Nano Developer Kit Hardware Layout: https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/hardware_layout.html
- Intel RealSense D400 Series Datasheet: https://realsenseai.com/wp-content/uploads/2024/10/Intel-RealSense-D400-Series-Datasheet-October-2024.pdf
- Intel RealSense D415 Product Brief: https://simplecore.intel.com/realsensehub/wp-content/uploads/sites/63/D415_Series_ProductBrief_111207.pdf
- RealSense Linux Ubuntu installation: https://dev.realsenseai.com/installation/linux-ubuntu-installation-from-source/
- RealSense Linux distribution packages: https://github.com/realsenseai/librealsense/blob/master/doc/distribution_linux.md
- RealSense Jetson installation notes: https://github.com/realsenseai/librealsense/blob/master/doc/installation_jetson.md
- Ubuntu OpenSSH server guide: https://ubuntu.com/server/docs/how-to/security/openssh-server/
- Tailscale Linux install guide: https://tailscale.com/docs/install/linux
