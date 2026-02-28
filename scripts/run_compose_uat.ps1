param(
    [ValidateSet("run", "up", "down", "logs", "ps")]
    [string]$Action = "run",
    [string]$ProjectName = "",
    [switch]$Build,
    [switch]$NoDetach,
    [string]$RuntimeTarget = "robot_fidelity_orin",
    [string]$SimLane = "jetty_gate",
    [string]$InferenceBackend = "tensorrt_int8",
    [string]$CoreRosDistro = "kilted",
    [ValidateSet("prepare", "coordinate", "snapshot", "orientation", "nav2", "multi_target", "first_uat", "full_replay", "pre_llm")]
    [string]$UatMode = "prepare",
    [ValidateSet("sim_gate", "gate_stack", "uat_orchestrator")]
    [string]$UatExecutionContext = "sim_gate",
    [int]$StepTimeoutSeconds = 900,
    [int]$Nav2DurationSeconds = 120,
    [int]$MultiTargetGoalTimeoutSeconds = 55,
    [int]$SnapshotTimeoutSeconds = 12,
    [double]$SnapshotMinMeanAbsDiff = 1.5,
    [ValidateSet("compat", "balanced", "max")]
    [string]$UatProfile = "compat",
    [string]$UatInferenceDevice = "cuda:0",
    [string]$MultiTargetConfig = "ros2_config/config/multi_target_nav2.yaml"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$env:CHASECAR_UAT_MODE = $UatMode
$env:CHASECAR_STEP_TIMEOUT_S = [Math]::Max($StepTimeoutSeconds, 30).ToString()
$env:CHASECAR_NAV2_DURATION_S = [Math]::Max($Nav2DurationSeconds, 30).ToString()
$env:CHASECAR_MULTI_TARGET_GOAL_TIMEOUT_S = [Math]::Max($MultiTargetGoalTimeoutSeconds, 10).ToString()
$env:CHASECAR_SNAPSHOT_TIMEOUT_S = [Math]::Max($SnapshotTimeoutSeconds, 5).ToString()
$env:CHASECAR_SNAPSHOT_MIN_MEAN_ABS_DIFF = [Math]::Max([double]$SnapshotMinMeanAbsDiff, 0.0).ToString("0.###", [System.Globalization.CultureInfo]::InvariantCulture)
$env:CHASECAR_MULTI_TARGET_CONFIG = $MultiTargetConfig
$env:CHASECAR_UAT_PROFILE = $UatProfile
$env:CHASECAR_UAT_INFERENCE_DEVICE = $UatInferenceDevice

function Resolve-DockerCli {
    $dockerResolved = Get-Command docker -ErrorAction SilentlyContinue
    if ($dockerResolved) {
        return $dockerResolved.Source
    }
    $fallbackDocker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    if (Test-Path -LiteralPath $fallbackDocker) {
        return $fallbackDocker
    }
    throw "Unable to locate docker CLI."
}

function Get-OrCreateProjectName {
    param([string]$ProvidedName)
    if (-not [string]::IsNullOrWhiteSpace($ProvidedName)) {
        return $ProvidedName
    }
    $timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddHHmmss")
    return "chasecar_uat_$timestamp"
}

$resolvedProjectName = Get-OrCreateProjectName -ProvidedName $ProjectName

if ($Action -eq "run" -and $UatExecutionContext -ne "uat_orchestrator") {
    if ([string]::IsNullOrWhiteSpace($ProjectName)) {
        throw "ProjectName is required when -UatExecutionContext is sim_gate or gate_stack because UAT runs against an existing gate project."
    }

    $targetService = if ($UatExecutionContext -eq "sim_gate") { "sim-gate" } else { "gate-stack" }

    $dockerCmd = Resolve-DockerCli
    $dockerBinDir = Split-Path -Parent $dockerCmd
    if ($dockerBinDir -and -not (($env:Path -split ';') -contains $dockerBinDir)) {
        $env:Path = "$dockerBinDir;$env:Path"
    }

    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    Write-Host "UAT runner" -ForegroundColor Cyan
    Write-Host "  Context:   $UatExecutionContext"
    Write-Host "  Service:   $targetService"
    Write-Host "  Project:   $resolvedProjectName"
    Write-Host "  Mode:      $UatMode"
    Write-Host "  Runtime:   $RuntimeTarget"
    Write-Host "  Sim lane:  $SimLane"
    Write-Host "  Inference: $InferenceBackend"
    Write-Host "  ROS core:  $CoreRosDistro"
    Write-Host ""

    Push-Location $repoRoot
    try {
        $containerIdRaw = & $dockerCmd compose -p $resolvedProjectName --profile gate ps -q $targetService 2>$null
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to query $targetService container for project '$resolvedProjectName'."
        }
        $containerId = ""
        $candidate = $containerIdRaw | Select-Object -First 1
        if ($candidate) {
            $containerId = $candidate.ToString().Trim()
        }
        if ([string]::IsNullOrWhiteSpace($containerId)) {
            throw "No $targetService container found for project '$resolvedProjectName'. Start gate lane first."
        }

        $running = (& $dockerCmd inspect -f "{{.State.Running}}" $containerId 2>$null | Out-String).Trim().ToLowerInvariant()
        if ($running -ne "true") {
            throw "$targetService container '$containerId' is not running."
        }

        $script = @'
set -euo pipefail
export CHASECAR_UAT_MODE="__UAT_MODE__"
export CHASECAR_RUNTIME_TARGET="__RUNTIME_TARGET__"
export CHASECAR_SIM_LANE="__SIM_LANE__"
export CHASECAR_INFERENCE_BACKEND="__INFERENCE_BACKEND__"
export CHASECAR_STEP_TIMEOUT_S="__STEP_TIMEOUT_S__"
export CHASECAR_NAV2_DURATION_S="__NAV2_DURATION_S__"
export CHASECAR_MULTI_TARGET_GOAL_TIMEOUT_S="__MULTI_TARGET_GOAL_TIMEOUT_S__"
export CHASECAR_SNAPSHOT_TIMEOUT_S="__SNAPSHOT_TIMEOUT_S__"
export CHASECAR_SNAPSHOT_MIN_MEAN_ABS_DIFF="__SNAPSHOT_MIN_MEAN_ABS_DIFF__"
export CHASECAR_MULTI_TARGET_CONFIG="__MULTI_TARGET_CONFIG__"
export CHASECAR_UAT_PROFILE="__UAT_PROFILE__"
export CHASECAR_UAT_INFERENCE_DEVICE="__UAT_INFERENCE_DEVICE__"
export REPO_ROOT="/workspaces/chasecar"
bash /workspaces/chasecar/uat/orchestrator/run_uat_orchestrator.sh
'@
        $script = $script.Replace("__UAT_MODE__", $UatMode).
            Replace("__RUNTIME_TARGET__", $RuntimeTarget).
            Replace("__SIM_LANE__", $SimLane).
            Replace("__INFERENCE_BACKEND__", $InferenceBackend).
            Replace("__STEP_TIMEOUT_S__", $env:CHASECAR_STEP_TIMEOUT_S).
            Replace("__NAV2_DURATION_S__", $env:CHASECAR_NAV2_DURATION_S).
            Replace("__MULTI_TARGET_GOAL_TIMEOUT_S__", $env:CHASECAR_MULTI_TARGET_GOAL_TIMEOUT_S).
            Replace("__SNAPSHOT_TIMEOUT_S__", $env:CHASECAR_SNAPSHOT_TIMEOUT_S).
            Replace("__SNAPSHOT_MIN_MEAN_ABS_DIFF__", $env:CHASECAR_SNAPSHOT_MIN_MEAN_ABS_DIFF).
            Replace("__MULTI_TARGET_CONFIG__", $env:CHASECAR_MULTI_TARGET_CONFIG).
            Replace("__UAT_PROFILE__", $UatProfile).
            Replace("__UAT_INFERENCE_DEVICE__", $UatInferenceDevice)
        $script = $script.Replace("`r`n", "`n")

        & $dockerCmd exec $containerId bash -lc $script
        exit $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}
else {
    $scriptPath = Join-Path $PSScriptRoot "run_compose_profile.ps1"
    & $scriptPath `
        -Profile "uat" `
        -Action $Action `
        -ProjectName $resolvedProjectName `
        -Build:$Build `
        -NoDetach:$NoDetach `
        -RuntimeTarget $RuntimeTarget `
        -SimLane $SimLane `
        -InferenceBackend $InferenceBackend `
        -CoreRosDistro $CoreRosDistro `
        -BridgeRosDistro "jazzy" `
        -ComposeService "uat-orchestrator"
}
