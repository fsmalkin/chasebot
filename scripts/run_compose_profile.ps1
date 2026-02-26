param(
    [ValidateSet("gate", "isaac", "uat")]
    [string]$Profile,

    [ValidateSet("up", "down", "logs", "ps", "run")]
    [string]$Action = "up",

    [string]$ProjectName = "",

    [switch]$Build,

    [switch]$NoDetach,

    [string]$RuntimeTarget = "robot_fidelity_orin",

    [string]$SimLane = "jetty_gate",

    [string]$InferenceBackend = "tensorrt_int8",

    [string]$CoreRosDistro = "kilted",

    [string]$BridgeRosDistro = "jazzy",

    [string]$ComposeService = "uat-orchestrator"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectName)) {
    $timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddHHmmss")
    $ProjectName = "chasecar_${Profile}_$timestamp"
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$env:COMPOSE_PROJECT_NAME = $ProjectName
$env:RUNTIME_TARGET = $RuntimeTarget
$env:SIM_LANE = $SimLane
$env:INFERENCE_BACKEND = $InferenceBackend
$env:CORE_ROS_DISTRO = $CoreRosDistro
$env:BRIDGE_ROS_DISTRO = $BridgeRosDistro

$cmd = @("compose", "--profile", $Profile)

switch ($Action) {
    "up" {
        $cmd += "up"
        if ($Build) {
            $cmd += "--build"
        }
        if (-not $NoDetach) {
            $cmd += "-d"
        }
    }
    "down" {
        $cmd += @("down", "--remove-orphans")
    }
    "logs" {
        $cmd += @("logs", "--tail", "200")
    }
    "ps" {
        $cmd += "ps"
    }
    "run" {
        $cmd += @("run", "--rm", $ComposeService)
    }
}

Write-Host "Compose profile runner" -ForegroundColor Cyan
Write-Host "  Project:   $ProjectName"
Write-Host "  Profile:   $Profile"
Write-Host "  Action:    $Action"
Write-Host "  Runtime:   $RuntimeTarget"
Write-Host "  Sim lane:  $SimLane"
Write-Host "  Inference: $InferenceBackend"
Write-Host "  ROS core:  $CoreRosDistro"
Write-Host "  ROS bridge:$BridgeRosDistro"
Write-Host ""

$dockerCmd = $null
$dockerResolved = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerResolved) {
    $dockerCmd = $dockerResolved.Source
}
if (-not $dockerCmd) {
    $fallbackDocker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    if (Test-Path -LiteralPath $fallbackDocker) {
        $dockerCmd = $fallbackDocker
    }
}
if (-not $dockerCmd) {
    throw "Unable to locate docker CLI. Install Docker Desktop or add docker.exe to PATH."
}

$dockerBinDir = Split-Path -Parent $dockerCmd
if ($dockerBinDir -and -not (($env:Path -split ';') -contains $dockerBinDir)) {
    $env:Path = "$dockerBinDir;$env:Path"
}

Push-Location $repoRoot
try {
    & $dockerCmd @cmd
}
finally {
    Pop-Location
}
