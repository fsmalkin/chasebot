param(
    [string]$Distro = "Ubuntu-24.04",

    [string]$WorkspacePath = "~/ros2_ws",

    [string]$RuntimeSourceDir = "chasecar_runtime",

    [string]$RosDistro = "auto",

    [string]$RobotHost = "192.168.1.11",

    [int]$Port = 8765,

    [double]$LinearScale = 3.0,

    [double]$AngularScale = 3.0,

    [double]$MaxBridgeLinearX = 0.36,

    [double]$MaxBridgeAngularZ = 1.0,

    [double]$CommandDurationS = 0.20,

    [double]$PostRateHz = 5.0,

    [double]$StaleStopS = 0.45,

    [string]$SummaryPath = "artifacts/session/factory_bridge_cmd_vel_relay/relay_summary.json",

    [switch]$RequireMotionEnabled,

    [switch]$DryRun,

    [switch]$SkipSync
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-RosDistro {
    param(
        [Parameter(Mandatory = $true)][string]$Distro,
        [string]$Requested = "auto"
    )
    if ($Requested -and $Requested -ne "auto") {
        return $Requested
    }

    $resolveCmd = @'
if [ -f /opt/ros/kilted/setup.bash ]; then
  echo kilted
elif [ -f /opt/ros/lyrical/setup.bash ]; then
  echo lyrical
elif [ -f /opt/ros/jazzy/setup.bash ]; then
  echo jazzy
elif [ -f /opt/ros/humble/setup.bash ]; then
  echo humble
elif [ -d /opt/ros ]; then
  ls -1 /opt/ros | head -n1
fi
'@
    $resolveCmd = $resolveCmd.Replace("`r`n", "`n")
    $detectedRaw = wsl -d $Distro -- bash -lc $resolveCmd 2>$null
    $detected = ($detectedRaw | Out-String).Trim()
    if ([string]::IsNullOrWhiteSpace($detected)) {
        throw "Unable to resolve ROS distro in $Distro. Install ROS first or pass -RosDistro explicitly."
    }
    return $detected
}

function Convert-ToBashLiteral {
    param([Parameter(Mandatory = $true)][string]$Value)
    return "'" + ($Value -replace "'", "'\''") + "'"
}

if (-not $SkipSync) {
    $syncScript = Join-Path $PSScriptRoot "sync_runtime_workspace.ps1"
    & $syncScript -Distro $Distro -WorkspacePath $WorkspacePath -RuntimeSourceDir $RuntimeSourceDir -SkipBuild -RosDistro $RosDistro
}

$rosResolved = Resolve-RosDistro -Distro $Distro -Requested $RosDistro
$baseUrl = "http://${RobotHost}:${Port}"
$runtimePathExpr = $WorkspacePath
if ($runtimePathExpr.StartsWith("~/")) {
    $runtimePathExpr = "`$HOME/" + $runtimePathExpr.Substring(2)
} elseif ($runtimePathExpr -eq "~") {
    $runtimePathExpr = "`$HOME"
}

$argsList = @(
    "python3",
    "ros2_scripts/factory_bridge_cmd_vel_relay.py",
    "--base-url", $baseUrl,
    "--summary-path", $SummaryPath,
    "--linear-scale", $LinearScale.ToString("R", [Globalization.CultureInfo]::InvariantCulture),
    "--angular-scale", $AngularScale.ToString("R", [Globalization.CultureInfo]::InvariantCulture),
    "--max-bridge-linear-x", $MaxBridgeLinearX.ToString("R", [Globalization.CultureInfo]::InvariantCulture),
    "--max-bridge-angular-z", $MaxBridgeAngularZ.ToString("R", [Globalization.CultureInfo]::InvariantCulture),
    "--command-duration-s", $CommandDurationS.ToString("R", [Globalization.CultureInfo]::InvariantCulture),
    "--post-rate-hz", $PostRateHz.ToString("R", [Globalization.CultureInfo]::InvariantCulture),
    "--stale-stop-s", $StaleStopS.ToString("R", [Globalization.CultureInfo]::InvariantCulture)
)

if ($RequireMotionEnabled) {
    $argsList += "--require-motion-enabled"
}
if ($DryRun) {
    $argsList += "--dry-run"
}

$quotedArgs = ($argsList | ForEach-Object { Convert-ToBashLiteral -Value ([string]$_) }) -join " "

$bash = @"
set -eo pipefail
WORKSPACE="$runtimePathExpr"
RUNTIME_PATH="`$WORKSPACE/src/$RuntimeSourceDir"
source "/opt/ros/$rosResolved/setup.bash"
cd "`$RUNTIME_PATH"
if [ -f "`$WORKSPACE/install/setup.bash" ]; then
  source "`$WORKSPACE/install/setup.bash"
fi
echo "FACTORY_BRIDGE_CMD_VEL_RELAY_BASE_URL=$baseUrl"
echo "FACTORY_BRIDGE_CMD_VEL_RELAY_SUMMARY=$SummaryPath"
exec $quotedArgs
"@

$bash = $bash.Replace("`r`n", "`n")
wsl -d $Distro -- bash -lc $bash
