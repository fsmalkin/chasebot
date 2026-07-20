param(
    [Parameter(Mandatory = $true)]
    [string]$RobotHost,

    [string]$RobotUser = "jetson",

    [string]$RemoteDir = "/home/jetson/chasecar_factory_bridge",

    [int]$Port = 8765,

    [double]$DeadmanTimeoutS = 0.5,

    [double]$MaxCommandDurationS = 1.0,

    [double]$MaxMotorSpeed = 0.35,

    [double]$MaxLinearX = 0.6,

    [double]$MaxAngularZ = 2.5,

    [double]$TurnGain = 0.7,

    [int]$CameraWidth = 320,

    [int]$CameraHeight = 240,

    [double]$CameraFps = 5.0,

    [int]$CameraJpegQuality = 55,

    [ValidateSet("gstreamer", "jetbotmini", "v4l2_bayer")]
    [string]$CameraBackend = "gstreamer",

    [int]$CameraGstreamerSensorId = 0,

    [string]$CameraV4l2Device = "/dev/video0",

    [int]$CameraV4l2RawWidth = 3264,

    [int]$CameraV4l2RawHeight = 2464,

    [string]$CameraV4l2Pixelformat = "RG10",

    [switch]$Start,

    [switch]$EnableMotion,

    [switch]$Camera
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$sourcePath = Join-Path $repoRoot "tools/robot_factory_bridge/chasecar_factory_bridge.py"
if (-not (Test-Path -LiteralPath $sourcePath)) {
    throw "Bridge source not found: $sourcePath"
}

$target = "$RobotUser@$RobotHost"
$remoteScript = "$RemoteDir/chasecar_factory_bridge.py"

Write-Host "[deploy] mkdir ${target}:$RemoteDir" -ForegroundColor Cyan
& ssh -o BatchMode=yes -o ConnectTimeout=8 $target "mkdir -p '$RemoteDir'"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create remote bridge directory."
}

Write-Host "[deploy] scp bridge script" -ForegroundColor Cyan
& scp -q -o BatchMode=yes -o ConnectTimeout=8 $sourcePath "$target`:$remoteScript"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to copy bridge script."
}

& ssh -o BatchMode=yes -o ConnectTimeout=8 $target "chmod +x '$remoteScript'; python3 '$remoteScript' --self-test"
if ($LASTEXITCODE -ne 0) {
    throw "Remote bridge self-test failed."
}

if (-not $Start) {
    Write-Host "ROBOT_FACTORY_BRIDGE_DEPLOYED=$remoteScript"
    Write-Host "Start later with: python3 $remoteScript --host 0.0.0.0 --port $Port"
    exit 0
}

$motionArg = if ($EnableMotion) { "--enable-motion" } else { "" }
$cameraArg = if ($Camera) { "--camera --camera-width $CameraWidth --camera-height $CameraHeight --camera-fps $CameraFps --camera-jpeg-quality $CameraJpegQuality --camera-backend $CameraBackend --camera-gstreamer-sensor-id $CameraGstreamerSensorId --camera-v4l2-device '$CameraV4l2Device' --camera-v4l2-raw-width $CameraV4l2RawWidth --camera-v4l2-raw-height $CameraV4l2RawHeight --camera-v4l2-pixelformat $CameraV4l2Pixelformat" } else { "" }
$startCommand = @(
    "set -e",
    "cd '$RemoteDir'",
    "if [ -f bridge.pid ]; then old_pid=`$(cat bridge.pid 2>/dev/null || true); if [ -n `"`$old_pid`" ]; then pkill -TERM -P `"`$old_pid`" 2>/dev/null || true; kill `"`$old_pid`" 2>/dev/null || true; sleep 0.3; pkill -KILL -P `"`$old_pid`" 2>/dev/null || true; kill -KILL `"`$old_pid`" 2>/dev/null || true; fi; rm -f bridge.pid; fi",
    "pkill -TERM -f '^python3 .*/chasecar_factory_bridge.py' 2>/dev/null || true",
    "sleep 0.3",
    "pkill -KILL -f '^python3 .*/chasecar_factory_bridge.py' 2>/dev/null || true",
    "pkill -TERM -f '[g]st-launch-1.0 .*chasecar_bridge_camera_' 2>/dev/null || true",
    "sleep 0.2",
    "pkill -KILL -f '[g]st-launch-1.0 .*chasecar_bridge_camera_' 2>/dev/null || true",
    "nohup python3 '$remoteScript' --host 0.0.0.0 --port $Port --deadman-timeout-s $DeadmanTimeoutS --max-command-duration-s $MaxCommandDurationS --max-motor-speed $MaxMotorSpeed --max-linear-x $MaxLinearX --max-angular-z $MaxAngularZ --turn-gain $TurnGain $motionArg $cameraArg > bridge.log 2>&1 < /dev/null & echo `$! > bridge.pid",
    "sleep 1",
    "cat bridge.pid"
) -join "; "

Write-Host "[start] ${target}:$Port motion_enabled=$([bool]$EnableMotion) camera=$([bool]$Camera)" -ForegroundColor Cyan
$pidOutput = & ssh -o BatchMode=yes -o ConnectTimeout=8 $target $startCommand
if ($LASTEXITCODE -ne 0) {
    throw "Failed to start remote bridge."
}

$healthUri = "http://${RobotHost}:$Port/health"
$health = $null
$expectedMotionEnabled = [bool]$EnableMotion
for ($i = 0; $i -lt 10; $i++) {
    try {
        $health = Invoke-RestMethod -Uri $healthUri -TimeoutSec 2
        if ([bool]$health.motion_enabled -eq $expectedMotionEnabled) {
            break
        }
    } catch {
    }
    Start-Sleep -Milliseconds 500
}

if (($null -eq $health) -or ([bool]$health.motion_enabled -ne $expectedMotionEnabled)) {
    & ssh -o BatchMode=yes -o ConnectTimeout=8 $target "tail -80 '$RemoteDir/bridge.log' 2>/dev/null || true"
    $actualMotionEnabled = if ($null -eq $health) { "<no-health>" } else { [bool]$health.motion_enabled }
    throw "Bridge did not reach expected health at $healthUri. expected motion_enabled=$expectedMotionEnabled actual motion_enabled=$actualMotionEnabled"
}

Write-Host "ROBOT_FACTORY_BRIDGE_PID=$($pidOutput | Select-Object -Last 1)"
Write-Host "ROBOT_FACTORY_BRIDGE_HEALTH=$healthUri"
Write-Host "ROBOT_FACTORY_BRIDGE_DASHBOARD=http://${RobotHost}:$Port/dashboard"
$health | ConvertTo-Json -Depth 8
