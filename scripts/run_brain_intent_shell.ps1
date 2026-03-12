param(
    [string]$ProjectName = "",
    [ValidateSet("robot_fidelity_orin", "robot_fidelity", "workstation_balanced", "workstation_max")]
    [string]$RuntimeTarget = "robot_fidelity_orin",
    [string]$SimLane = "jetty_gate",
    [ValidateSet("tensorrt_int8")]
    [string]$InferenceBackend = "tensorrt_int8",
    [string]$CoreRosDistro = "kilted",
    [ValidateSet("compat", "balanced", "max")]
    [string]$GatePerfProfile = "compat",
    [ValidateSet("auto", "cuda:0", "cpu")]
    [string]$InferenceDevice = "cuda:0",
    [string]$WorldFile = "yolo_test_world_v6_clean_uat.world",
    [double]$WaitTimeoutSeconds = 25.0,
    [double]$StepTimeoutSeconds = 1.0,
    [double]$PublishIntervalSeconds = 0.25,
    [switch]$Build
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runId = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$sessionDir = Join-Path $repoRoot "artifacts/session/$runId"
New-Item -ItemType Directory -Path $sessionDir -Force | Out-Null
$reportPath = Join-Path $sessionDir "brain_intent_shell_summary.json"

if ([string]::IsNullOrWhiteSpace($ProjectName)) {
    $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddHHmmss")
    $ProjectName = "chasecar_gate_brainshell_$stamp"
}

$dockerCmd = Resolve-DockerCli
$dockerBinDir = Split-Path -Parent $dockerCmd
if ($dockerBinDir -and -not (($env:Path -split ';') -contains $dockerBinDir)) {
    $env:Path = "$dockerBinDir;$env:Path"
}

$reportContainerPath = "/workspaces/chasecar/artifacts/session/$runId/brain_intent_shell_summary.json"
$gateUp = $false

try {
    if ($Build) {
        & (Join-Path $PSScriptRoot "run_compose_gate.ps1") `
            -Action up `
            -ProjectName $ProjectName `
            -RuntimeTarget $RuntimeTarget `
            -SimLane $SimLane `
            -InferenceBackend $InferenceBackend `
            -CoreRosDistro $CoreRosDistro `
            -IncludeNav2Bringup 1 `
            -IncludeBridge 0 `
            -IncludeCmdVelRelay 1 `
            -GatePerfProfile $GatePerfProfile `
            -InferenceDevice $InferenceDevice `
            -WorldFile $WorldFile `
            -Build
    }
    else {
        & (Join-Path $PSScriptRoot "run_compose_gate.ps1") `
            -Action up `
            -ProjectName $ProjectName `
            -RuntimeTarget $RuntimeTarget `
            -SimLane $SimLane `
            -InferenceBackend $InferenceBackend `
            -CoreRosDistro $CoreRosDistro `
            -IncludeNav2Bringup 1 `
            -IncludeBridge 0 `
            -IncludeCmdVelRelay 1 `
            -GatePerfProfile $GatePerfProfile `
            -InferenceDevice $InferenceDevice `
            -WorldFile $WorldFile
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Gate bring-up failed for project '$ProjectName'."
    }
    $gateUp = $true

    Push-Location $repoRoot
    try {
        $containerIdRaw = & $dockerCmd compose -p $ProjectName --profile gate ps -q sim-gate 2>$null
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to query sim-gate container for project '$ProjectName'."
        }
        $containerId = ""
        $candidate = $containerIdRaw | Select-Object -First 1
        if ($candidate) {
            $containerId = $candidate.ToString().Trim()
        }
        if ([string]::IsNullOrWhiteSpace($containerId)) {
            throw "No sim-gate container found for project '$ProjectName'."
        }

        $script = @'
set -eo pipefail
if [ -f /opt/ros/$ROS_DISTRO/setup.bash ]; then
  source /opt/ros/$ROS_DISTRO/setup.bash
fi
if [ -f /root/ros2_ws/install/setup.bash ]; then
  source /root/ros2_ws/install/setup.bash
fi
cd /workspaces/chasecar
python3 scripts/brain_intent_shell_runner.py \
  --contract runtime/contracts/llm_control_contract.yaml \
  --output "__REPORT_PATH__" \
  --wait-timeout-s __WAIT_TIMEOUT__ \
  --step-timeout-s __STEP_TIMEOUT__ \
  --publish-interval-s __PUBLISH_INTERVAL__ \
  --use-sim-time
'@
        $script = $script.Replace("__REPORT_PATH__", $reportContainerPath)
        $script = $script.Replace("__WAIT_TIMEOUT__", $WaitTimeoutSeconds.ToString([System.Globalization.CultureInfo]::InvariantCulture))
        $script = $script.Replace("__STEP_TIMEOUT__", $StepTimeoutSeconds.ToString([System.Globalization.CultureInfo]::InvariantCulture))
        $script = $script.Replace("__PUBLISH_INTERVAL__", $PublishIntervalSeconds.ToString([System.Globalization.CultureInfo]::InvariantCulture))
        $script = $script.Replace("`r`n", "`n")

        & $dockerCmd exec $containerId bash -lc $script
        $runnerExit = $LASTEXITCODE
        if ($runnerExit -ne 0) {
            throw "Brain intent shell runner failed with exit code $runnerExit."
        }
    }
    finally {
        Pop-Location
    }

    if (-not (Test-Path -LiteralPath $reportPath)) {
        throw "Brain intent shell report not found at '$reportPath'."
    }

    $report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
    Write-Host "BRAIN_INTENT_SHELL_REPORT=$reportPath"
    Write-Host "BRAIN_INTENT_SHELL_PASS=$($report.pass)"
}
finally {
    if ($gateUp) {
        & (Join-Path $PSScriptRoot "run_compose_gate.ps1") `
            -Action down `
            -ProjectName $ProjectName `
            -RuntimeTarget $RuntimeTarget `
            -SimLane $SimLane `
            -InferenceBackend $InferenceBackend `
            -CoreRosDistro $CoreRosDistro `
            -IncludeNav2Bringup 1 `
            -IncludeBridge 0 `
            -IncludeCmdVelRelay 1 | Out-Null

        & (Join-Path $PSScriptRoot "run_compose_uat.ps1") `
            -Action down `
            -ProjectName $ProjectName `
            -RuntimeTarget $RuntimeTarget `
            -SimLane $SimLane `
            -InferenceBackend $InferenceBackend `
            -CoreRosDistro $CoreRosDistro | Out-Null
    }
}
