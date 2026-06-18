param(
    [string]$RobotHost = "192.168.1.11",

    [string]$RobotUser = "jetson",

    [int]$Port = 8765,

    [string]$CampaignId = ("factory_bridge_motion_rehearsal_{0}" -f (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")),

    [string]$PlanFile = "",

    [double]$MaxMotorSpeed = 0.20,

    [switch]$Turn90Proof,

    [switch]$ExecuteMotion,

    [switch]$ConfirmHeldInAir,

    [switch]$ConfirmFloorClear,

    [switch]$SkipPreflight,

    [switch]$PlanOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$artifactRoot = Join-Path $repoRoot ("artifacts/session/{0}/factory_bridge_motion_rehearsal" -f $CampaignId)
$deployScript = Join-Path $repoRoot "scripts/deploy_robot_factory_bridge.ps1"
$preflightScript = Join-Path $repoRoot "tools/robot_factory_bridge/chasecar_bridge_preflight.py"
$runnerScript = Join-Path $repoRoot "tools/robot_factory_bridge/chasecar_bridge_behavior_runner.py"
$clientScript = Join-Path $repoRoot "tools/robot_factory_bridge/chasecar_bridge_client.py"
$turn90Plan = Join-Path $repoRoot "tools/robot_factory_bridge/plans/turn_90_camera_proof_v1.json"

function New-StepResult {
    param(
        [string]$Name,
        [bool]$Pass,
        [int]$ExitCode,
        [string]$Output,
        [string]$ArtifactDir = ""
    )
    return [ordered]@{
        name = $Name
        pass = $Pass
        exit_code = $ExitCode
        artifact_dir = $ArtifactDir
        output = $Output
    }
}

function Invoke-CheckedCommand {
    param(
        [string]$Name,
        [string[]]$Command,
        [string]$ArtifactDir = ""
    )
    Write-Host "[$Name] $($Command -join ' ')" -ForegroundColor Cyan
    $exe = $Command[0]
    $commandArgs = @($Command | Select-Object -Skip 1)
    $output = & $exe @commandArgs 2>&1 | Out-String
    $exitCode = [int]$LASTEXITCODE
    $passed = $exitCode -eq 0
    if (-not $passed) {
        Write-Host $output
        throw "Step '$Name' failed with exit code $exitCode."
    }
    return New-StepResult -Name $Name -Pass $passed -ExitCode $exitCode -Output $output -ArtifactDir $ArtifactDir
}

function Invoke-OptionalHealth {
    param([string]$Name)
    $output = & python $clientScript --base-url "http://${RobotHost}:$Port" --pretty health 2>&1 | Out-String
    return New-StepResult -Name $Name -Pass ($LASTEXITCODE -eq 0) -ExitCode ([int]$LASTEXITCODE) -Output $output
}

$summary = [ordered]@{
    generated_utc = (Get-Date).ToUniversalTime().ToString("o")
    type = "factory_bridge_motion_rehearsal"
    robot_host = $RobotHost
    robot_user = $RobotUser
    port = $Port
    campaign_id = $CampaignId
    artifact_root = $artifactRoot
    plan_file = $PlanFile
    turn_90_proof = [bool]$Turn90Proof
    max_motor_speed = $MaxMotorSpeed
    execute_motion = [bool]$ExecuteMotion
    confirm_held_in_air = [bool]$ConfirmHeldInAir
    confirm_floor_clear = [bool]$ConfirmFloorClear
    skip_preflight = [bool]$SkipPreflight
    plan_only = [bool]$PlanOnly
    pass = $false
    issues = @()
    notes = @()
    steps = @()
}

New-Item -ItemType Directory -Force -Path $artifactRoot | Out-Null

if ($ExecuteMotion -and -not $ConfirmHeldInAir) {
    if (-not ($Turn90Proof -and $ConfirmFloorClear)) {
        throw "Refusing motion rehearsal without -ConfirmHeldInAir, or -Turn90Proof plus -ConfirmFloorClear for a floor turn."
    }
}

if ($Turn90Proof -and [string]::IsNullOrWhiteSpace($PlanFile)) {
    if (-not (Test-Path -LiteralPath $turn90Plan)) {
        throw "Turn-90 proof plan not found: $turn90Plan"
    }
    $PlanFile = $turn90Plan
    $summary.plan_file = $PlanFile
}

if ($PlanOnly) {
    $summary.pass = $true
    $summary.notes += "plan_only_no_robot_commands_run"
    $summaryPath = Join-Path $artifactRoot "motion_rehearsal_summary.json"
    $summary | ConvertTo-Json -Depth 8 | Set-Content -Path $summaryPath -Encoding UTF8
    Write-Host "FACTORY_BRIDGE_MOTION_REHEARSAL_SUMMARY=$summaryPath"
    $summary | ConvertTo-Json -Depth 8
    exit 0
}

$planArgs = @()
if (-not [string]::IsNullOrWhiteSpace($PlanFile)) {
    $planArgs += @("--plan-file", $PlanFile)
}

try {
    $healthModeDir = Join-Path $artifactRoot "health_mode"
    $summary.steps += Invoke-CheckedCommand -Name "start_health_mode" -Command @(
        "powershell", "-ExecutionPolicy", "Bypass", "-File", $deployScript,
        "-RobotHost", $RobotHost, "-RobotUser", $RobotUser, "-Port", [string]$Port,
        "-Start", "-Camera"
    ) -ArtifactDir $healthModeDir

    if (-not $SkipPreflight) {
        $preflightDir = Join-Path $artifactRoot "safe_preflight"
        $summary.steps += Invoke-CheckedCommand -Name "safe_preflight" -Command @(
            "python", $preflightScript,
            "--base-url", "http://${RobotHost}:$Port",
            "--artifact-dir", $preflightDir
        ) -ArtifactDir $preflightDir
    }

    $planRefusalDir = Join-Path $artifactRoot "plan_refusal"
    $planRefusalCommand = @(
        "python", $runnerScript,
        "--base-url", "http://${RobotHost}:$Port",
        "--mode", "plan-refusal",
        "--artifact-dir", $planRefusalDir
    ) + $planArgs
    $summary.steps += Invoke-CheckedCommand -Name "plan_refusal" -Command $planRefusalCommand -ArtifactDir $planRefusalDir

    if ($ExecuteMotion) {
        $motionModeDir = Join-Path $artifactRoot "motion_mode"
        $summary.steps += Invoke-CheckedCommand -Name "start_motion_mode" -Command @(
            "powershell", "-ExecutionPolicy", "Bypass", "-File", $deployScript,
            "-RobotHost", $RobotHost, "-RobotUser", $RobotUser, "-Port", [string]$Port,
            "-Start", "-Camera", "-EnableMotion", "-MaxMotorSpeed", [string]$MaxMotorSpeed
        ) -ArtifactDir $motionModeDir

        $motionRunDir = Join-Path $artifactRoot "held_in_air_motion"
        $motionStepName = "held_in_air_motion"
        if ($Turn90Proof) {
            $motionRunDir = Join-Path $artifactRoot "floor_turn_90_camera_proof"
            $motionStepName = "floor_turn_90_camera_proof"
        }
        $motionCommand = @(
            "python", $runnerScript,
            "--base-url", "http://${RobotHost}:$Port",
            "--mode", "tiny-turn",
            "--execute-motion",
            "--confirm-operator-ready",
            "--artifact-dir", $motionRunDir
        ) + $planArgs
        if ($Turn90Proof) {
            $motionCommand += @("--require-visual-motion")
        }
        $summary.steps += Invoke-CheckedCommand -Name $motionStepName -Command $motionCommand -ArtifactDir $motionRunDir
    }

    $summary.pass = $true
} catch {
    $summary.issues += [string]$_.Exception.Message
    $summary.pass = $false
} finally {
    try {
        $returnDir = Join-Path $artifactRoot "return_health_mode"
        $summary.steps += Invoke-CheckedCommand -Name "return_health_mode" -Command @(
            "powershell", "-ExecutionPolicy", "Bypass", "-File", $deployScript,
            "-RobotHost", $RobotHost, "-RobotUser", $RobotUser, "-Port", [string]$Port,
            "-Start", "-Camera"
        ) -ArtifactDir $returnDir
    } catch {
        $summary.issues += "return_health_mode_failed:$($_.Exception.Message)"
        $summary.pass = $false
    }

    Start-Sleep -Seconds 2
    $summary.steps += Invoke-OptionalHealth -Name "final_health"
    $summaryPath = Join-Path $artifactRoot "motion_rehearsal_summary.json"
    $summary | ConvertTo-Json -Depth 12 | Set-Content -Path $summaryPath -Encoding UTF8
    Write-Host "FACTORY_BRIDGE_MOTION_REHEARSAL_SUMMARY=$summaryPath"
    $summary | ConvertTo-Json -Depth 8
}

if ($summary.pass) {
    exit 0
}
exit 1
