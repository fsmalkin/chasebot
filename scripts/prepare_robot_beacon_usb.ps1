param(
    [Parameter(Mandatory = $true)]
    [string]$UsbRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$source = Join-Path $repoRoot "tools\robot_beacon_usb"
$targetRoot = (Resolve-Path -LiteralPath $UsbRoot).Path
$target = Join-Path $targetRoot "chasecar-beacon"

if (-not (Test-Path -LiteralPath $source -PathType Container)) {
    throw "Beacon source folder missing: $source"
}

New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item -Path (Join-Path $source "*") -Destination $target -Recurse -Force

$notePath = Join-Path $targetRoot "CHASECAR_BEACON_README.txt"
@"
Chasecar Robot Beacon USB

On the Jetson:
1. Open this USB drive.
2. Open the chasecar-beacon folder.
3. Open a terminal in that folder.
4. Run the no-motion first boot probe:

   bash first_boot_probe.sh

5. Send the output to Codex.

6. After Codex confirms the network and SSH state, install the optional boot beacon:

   bash install_beacon_service.sh

After beacon install, the Jetson emits a no-motion discovery beacon at every boot.
From Windows in the Chasecar worktree, run:

   powershell -ExecutionPolicy Bypass -File scripts/find_robot_beacon.ps1 -TimeoutSeconds 30
"@ | Set-Content -Path $notePath -Encoding UTF8

Write-Host "CHASECAR_BEACON_USB_READY=$target"
Write-Host "CHASECAR_BEACON_USB_NOTE=$notePath"
