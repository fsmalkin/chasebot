param(
    [string]$CampaignId = "",
    [string]$ScenarioId = "corral_single_ball_place",
    [string]$SourceCampaignSummaryPath = "",
    [int]$RunIndex = 0,
    [string]$DashboardUrl = $(if ($env:CHASECAR_DASHBOARD_URL) { $env:CHASECAR_DASHBOARD_URL } else { "http://127.0.0.1:8860" }),
    [string]$Provider = $(if ($env:CHASECAR_LLM_PROVIDER) { $env:CHASECAR_LLM_PROVIDER } else { "openai" }),
    [double]$MotionProbeDurationS = 45.0
)

$ErrorActionPreference = "Stop"

function Get-CurrentUtcStamp {
    return [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
}

function Get-MarkerValue {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$Marker
    )

    $escapedMarker = [Regex]::Escape($Marker)
    $match = [Regex]::Match($Text, "$escapedMarker(?<value>[^\r\n]+)")
    if ($match.Success) {
        return $match.Groups["value"].Value.Trim()
    }
    return ""
}

function Resolve-RepoPath {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$PathText
    )

    if (-not $PathText.Trim()) {
        return ""
    }
    if ([System.IO.Path]::IsPathRooted($PathText)) {
        $resolvedPath = Resolve-Path -LiteralPath $PathText -ErrorAction SilentlyContinue
        if ($resolvedPath) {
            return $resolvedPath.Path
        }
        return $PathText
    }
    $candidate = Join-Path $RepoRoot $PathText
    $resolvedCandidate = Resolve-Path -LiteralPath $candidate -ErrorAction SilentlyContinue
    if ($resolvedCandidate) {
        return $resolvedCandidate.Path
    }
    return $candidate
}

function Invoke-PythonScript {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $output = & python @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    foreach ($line in @($output)) {
        Write-Host $line
    }
    return @{
        Output = @($output)
        ExitCode = $exitCode
        Text = (@($output) -join [Environment]::NewLine)
    }
}

function Get-DashboardState {
    param(
        [Parameter(Mandatory = $true)][string]$DashboardUrl,
        [int]$TimeoutSec = 5
    )

    try {
        return Invoke-RestMethod -Method Get -Uri ($DashboardUrl.TrimEnd("/") + "/api/state") -TimeoutSec $TimeoutSec
    } catch {
        return $null
    }
}

function Resolve-ContainerRepoPath {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$HostPath
    )

    $resolvedRepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
    $resolvedHostPath = Resolve-RepoPath -RepoRoot $RepoRoot -PathText $HostPath
    if (-not $resolvedHostPath.StartsWith($resolvedRepoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Host path is not inside repo root: $resolvedHostPath"
    }
    $relativePath = $resolvedHostPath.Substring($resolvedRepoRoot.Length).TrimStart("\", "/")
    $relativePath = $relativePath.Replace("\", "/")
    return "/workspaces/chasecar/$relativePath"
}

function Wait-For-FreshReadyComposeProject {
    param(
        [Parameter(Mandatory = $true)][string]$DashboardUrl,
        [string]$PreviousEnvironmentState = "",
        [int]$TimeoutSec = 90,
        [System.Diagnostics.Process]$ObservedProcess = $null
    )

    $deadline = (Get-Date).AddSeconds([Math]::Max($TimeoutSec, 10))
    $requireTransition = $PreviousEnvironmentState.Trim().ToLowerInvariant() -eq "environment_ready"
    $sawTransition = -not $requireTransition
    while ((Get-Date) -lt $deadline) {
        if ($ObservedProcess -and $ObservedProcess.HasExited -and -not $sawTransition) {
            break
        }
        $state = Get-DashboardState -DashboardUrl $DashboardUrl -TimeoutSec 5
        if ($state) {
            $environmentState = [string]$state.environment_state
            $composeProject = [string]$state.compose_project
            if (-not $sawTransition) {
                if ($environmentState.Trim().ToLowerInvariant() -ne "environment_ready") {
                    $sawTransition = $true
                }
            } elseif ($environmentState.Trim().ToLowerInvariant() -eq "environment_ready" -and $composeProject.Trim()) {
                return $state
            }
        }
        Start-Sleep -Milliseconds 250
    }
    return $null
}

function Get-GateStackContainerName {
    param(
        [Parameter(Mandatory = $true)][string]$ComposeProject
    )

    if (-not $ComposeProject.Trim()) {
        return ""
    }
    $containerNames = docker ps `
        --filter "label=com.docker.compose.project=$ComposeProject" `
        --filter "label=com.docker.compose.service=gate-stack" `
        --format "{{.Names}}"
    foreach ($containerName in @($containerNames)) {
        $trimmed = [string]$containerName
        if ($trimmed.Trim()) {
            return $trimmed.Trim()
        }
    }
    return ""
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$resolvedCampaignId = if ($CampaignId.Trim()) { $CampaignId.Trim() } else { Get-CurrentUtcStamp }
$resolvedSourceCampaignSummaryPath = if ($SourceCampaignSummaryPath.Trim()) {
    Resolve-RepoPath -RepoRoot $repoRoot -PathText $SourceCampaignSummaryPath.Trim()
} else {
    Resolve-RepoPath -RepoRoot $repoRoot -PathText "artifacts/session/live_plus45_short_horizon_v2_20260419/gather_mission_repeatability/campaign_run_summary.json"
}

$sourceAuditArgs = @(
    (Join-Path $repoRoot "scripts\gather_manual_drive_sign_parity_audit.py"),
    "--campaign-id", $resolvedCampaignId,
    "--scenario-id", $ScenarioId,
    "--campaign-summary-path", $resolvedSourceCampaignSummaryPath,
    "--run-index", $RunIndex.ToString()
)
$sourceAuditResult = Invoke-PythonScript -Arguments $sourceAuditArgs
$sourceAuditSummaryPath = Get-MarkerValue -Text $sourceAuditResult.Text -Marker "GATHER_MANUAL_DRIVE_SIGN_PARITY_AUDIT_SUMMARY="
if (-not $sourceAuditSummaryPath) {
    exit $sourceAuditResult.ExitCode
}

$resolvedSourceAuditSummaryPath = Resolve-RepoPath -RepoRoot $repoRoot -PathText $sourceAuditSummaryPath
$sourceAuditSummary = Get-Content -LiteralPath $resolvedSourceAuditSummaryPath -Raw | ConvertFrom-Json
$nextAction = if ($sourceAuditSummary.next_action) { $sourceAuditSummary.next_action } else { $null }
if (-not $nextAction -or [string]$nextAction.decision -ne "probe_odom_world_sign_chain" -or -not [bool]$nextAction.live_probe_required) {
    exit $sourceAuditResult.ExitCode
}

$probeOutputRoot = Join-Path $repoRoot "artifacts\session\$resolvedCampaignId\probe_odom_world_sign_chain"
$probeLogsRoot = Join-Path $probeOutputRoot "logs"
New-Item -ItemType Directory -Path $probeLogsRoot -Force | Out-Null
$runtimeProbeJsonPath = Join-Path $probeOutputRoot "runtime_probe.json"
$runtimeProbeStdoutPath = Join-Path $probeLogsRoot "runtime_probe.stdout.log"
$runtimeProbeStderrPath = Join-Path $probeLogsRoot "runtime_probe.stderr.log"
$runtimeProbeContainerScriptPath = Join-Path $probeLogsRoot "runtime_probe_container.sh"
$probeRunnerStdoutPath = Join-Path $probeLogsRoot "gather_repeatability.stdout.log"
$probeRunnerStderrPath = Join-Path $probeLogsRoot "gather_repeatability.stderr.log"

$runtimeProbeArgs = @(
    (Join-Path $repoRoot "scripts\odom_world_sign_chain_runtime_probe.py"),
    "--duration-s", ([string]([Math]::Max($MotionProbeDurationS, 10.0))),
    "--json-out", $runtimeProbeJsonPath,
    "--use-sim-time"
)
$runtimeProbeProcess = $null

$sourceCampaignSummary = Get-Content -LiteralPath $resolvedSourceCampaignSummaryPath -Raw | ConvertFrom-Json
$probeCampaignId = "${resolvedCampaignId}_live_probe"
$requestedWorldFile = [string]$sourceCampaignSummary.requested_world_file
$requestedSurfaceProfile = [string]$sourceCampaignSummary.requested_surface_profile
$requestedTargetLayoutJson = Resolve-RepoPath -RepoRoot $repoRoot -PathText ([string]$sourceCampaignSummary.requested_target_layout_json)
$requestedExecutionMode = if ([string]$sourceCampaignSummary.execution_mode) { [string]$sourceCampaignSummary.execution_mode } else { "direct" }

$probeArgs = @(
    (Join-Path $repoRoot "scripts\gather_mission_repeatability_runner.py"),
    "--dashboard-url", $DashboardUrl,
    "--scenario-id", $ScenarioId,
    "--runs", "1",
    "--campaign-id", $probeCampaignId,
    "--provider", $Provider,
    "--execution-mode", $requestedExecutionMode,
    "--promotion-gate-mode", "pass_only",
    "--gather-control-family", "short_horizon_v2"
)
if ($requestedWorldFile.Trim()) {
    $probeArgs += @("--world-file", $requestedWorldFile.Trim())
}
if ($requestedSurfaceProfile.Trim()) {
    $probeArgs += @("--surface-profile", $requestedSurfaceProfile.Trim())
}
if ($requestedTargetLayoutJson.Trim()) {
    $probeArgs += @("--target-layout-json", $requestedTargetLayoutJson.Trim())
}

$initialDashboardState = Get-DashboardState -DashboardUrl $DashboardUrl -TimeoutSec 5
$initialEnvironmentState = if ($initialDashboardState) { [string]$initialDashboardState.environment_state } else { "" }

try {
    $probeProcess = Start-Process `
        -FilePath "python" `
        -ArgumentList $probeArgs `
        -RedirectStandardOutput $probeRunnerStdoutPath `
        -RedirectStandardError $probeRunnerStderrPath `
        -PassThru `
        -NoNewWindow
} catch {
    throw "Unable to start gather_mission_repeatability_runner.py: $($_.Exception.Message)"
}

$readyProbeState = Wait-For-FreshReadyComposeProject `
    -DashboardUrl $DashboardUrl `
    -PreviousEnvironmentState $initialEnvironmentState `
    -TimeoutSec ([int]([Math]::Max($MotionProbeDurationS + 60.0, 90.0))) `
    -ObservedProcess $probeProcess

if ($readyProbeState) {
    $probeComposeProject = [string]$readyProbeState.compose_project
    $gateStackContainerName = Get-GateStackContainerName -ComposeProject $probeComposeProject
    if ($gateStackContainerName) {
        $containerRuntimeProbeJsonPath = Resolve-ContainerRepoPath -RepoRoot $repoRoot -HostPath $runtimeProbeJsonPath
        $containerRuntimeProbeLauncherPath = Resolve-ContainerRepoPath -RepoRoot $repoRoot -HostPath $runtimeProbeContainerScriptPath
        $runtimeProbeContainerScriptLines = @(
            "#!/usr/bin/env bash",
            "set -eo pipefail",
            "source /opt/ros/kilted/setup.bash",
            "if [ -f /root/ros2_ws/install/setup.bash ]; then source /root/ros2_ws/install/setup.bash; fi",
            "python3 /workspaces/chasecar/scripts/odom_world_sign_chain_runtime_probe.py --duration-s $([Math]::Max($MotionProbeDurationS, 10.0)) --json-out $containerRuntimeProbeJsonPath --use-sim-time"
        )
        [System.IO.File]::WriteAllText(
            $runtimeProbeContainerScriptPath,
            (($runtimeProbeContainerScriptLines -join "`n") + "`n"),
            [System.Text.Encoding]::ASCII
        )
        try {
            $runtimeProbeProcess = Start-Process `
                -FilePath "docker" `
                -ArgumentList @("exec", $gateStackContainerName, "bash", $containerRuntimeProbeLauncherPath) `
                -RedirectStandardOutput $runtimeProbeStdoutPath `
                -RedirectStandardError $runtimeProbeStderrPath `
                -PassThru `
                -NoNewWindow
        } catch {
            Write-Warning "Unable to start odom_world_sign_chain_runtime_probe.py in container ${gateStackContainerName}: $($_.Exception.Message)"
        }
    } else {
        Write-Warning "No gate-stack container was found for compose project ${probeComposeProject}; runtime sign probe will fall back to host Python."
    }
}

if (-not $runtimeProbeProcess) {
    try {
        $runtimeProbeProcess = Start-Process `
            -FilePath "python" `
            -ArgumentList $runtimeProbeArgs `
            -RedirectStandardOutput $runtimeProbeStdoutPath `
            -RedirectStandardError $runtimeProbeStderrPath `
            -PassThru `
            -NoNewWindow
    } catch {
        Write-Warning "Unable to start odom_world_sign_chain_runtime_probe.py on the host: $($_.Exception.Message)"
    }
}

$probeWaitTimeoutMs = [int](([Math]::Max($MotionProbeDurationS, 10.0) + 180.0) * 1000.0)
$null = $probeProcess.WaitForExit($probeWaitTimeoutMs)
if (-not $probeProcess.HasExited) {
    try {
        Stop-Process -Id $probeProcess.Id -Force
    } catch {
        Write-Warning "Unable to stop gather_mission_repeatability_runner.py cleanly: $($_.Exception.Message)"
    }
}
$probeStdout = if (Test-Path -LiteralPath $probeRunnerStdoutPath) { Get-Content -LiteralPath $probeRunnerStdoutPath } else { @() }
$probeStderr = if (Test-Path -LiteralPath $probeRunnerStderrPath) { Get-Content -LiteralPath $probeRunnerStderrPath } else { @() }
foreach ($line in @($probeStdout + $probeStderr)) {
    Write-Host $line
}
$probeResult = @{
    ExitCode = if ($probeProcess.HasExited) { $probeProcess.ExitCode } else { 1 }
    Text = ((@($probeStdout + $probeStderr)) -join [Environment]::NewLine)
}

if ($runtimeProbeProcess) {
    try {
        $waitTimeoutMs = [int](([Math]::Max($MotionProbeDurationS, 10.0) + 15.0) * 1000.0)
        $null = $runtimeProbeProcess.WaitForExit($waitTimeoutMs)
        if (-not $runtimeProbeProcess.HasExited) {
            Stop-Process -Id $runtimeProbeProcess.Id -Force
        }
    } catch {
        Write-Warning "Unable to stop the runtime probe process cleanly: $($_.Exception.Message)"
    }
}

$probeSummaryPath = Get-MarkerValue -Text $probeResult.Text -Marker "GATHER_MISSION_REPEATABILITY_SUMMARY="
if (-not $probeSummaryPath) {
    exit $probeResult.ExitCode
}

$resolvedProbeSummaryPath = Resolve-RepoPath -RepoRoot $repoRoot -PathText $probeSummaryPath
$analyzerArgs = @(
    (Join-Path $repoRoot "scripts\probe_odom_world_sign_chain.py"),
    "--campaign-id", $resolvedCampaignId,
    "--scenario-id", $ScenarioId,
    "--campaign-summary-path", $resolvedProbeSummaryPath,
    "--source-campaign-summary-path", $resolvedSourceCampaignSummaryPath,
    "--source-audit-summary-path", $resolvedSourceAuditSummaryPath,
    "--runtime-probe-json-path", $runtimeProbeJsonPath,
    "--runtime-probe-stdout-path", $runtimeProbeStdoutPath,
    "--runtime-probe-stderr-path", $runtimeProbeStderrPath,
    "--run-index", "0"
)
$analyzerResult = Invoke-PythonScript -Arguments $analyzerArgs
exit $analyzerResult.ExitCode
