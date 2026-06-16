param(
    [Parameter(Mandatory = $true)]
    [string]$RobotHost,

    [string]$RobotUser = "jetson",

    [string]$RemoteDir = "/home/jetson/chasecar_factory_bridge",

    [int]$Port = 8765
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$target = "$RobotUser@$RobotHost"
$stopUri = "http://${RobotHost}:$Port/stop"

try {
    Invoke-RestMethod -Method Post -Uri $stopUri -Body "{}" -ContentType "application/json" -TimeoutSec 2 | Out-Null
    Write-Host "ROBOT_FACTORY_BRIDGE_API_STOP=1"
} catch {
    Write-Host "ROBOT_FACTORY_BRIDGE_API_STOP=unavailable"
}

$remote = @(
    "set +e",
    "if [ -f '$RemoteDir/bridge.pid' ]; then pid=`$(cat '$RemoteDir/bridge.pid' 2>/dev/null); if [ -n `"`$pid`" ]; then kill `"`$pid`" 2>/dev/null || true; fi; rm -f '$RemoteDir/bridge.pid'; fi",
    "python3 -c 'from jetbotmini import Robot; r=Robot(); r.stop()' 2>/dev/null || true",
    "echo ROBOT_FACTORY_BRIDGE_STOPPED=1"
) -join "; "

& ssh -o BatchMode=yes -o ConnectTimeout=8 $target $remote
if ($LASTEXITCODE -ne 0) {
    throw "Remote bridge stop command failed."
}
