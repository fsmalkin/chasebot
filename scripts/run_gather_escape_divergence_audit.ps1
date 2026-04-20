param(
    [string]$CampaignId = "",
    [string]$ScenarioId = "corral_single_ball_place",
    [string]$CampaignSummaryPath = "",
    [int]$RunIndex = 0,
    [switch]$RunLiveProbeIfRequired,
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

$repoRoot = Split-Path -Parent $PSScriptRoot
$resolvedCampaignId = if ($CampaignId.Trim()) { $CampaignId.Trim() } else { Get-CurrentUtcStamp }
$resolvedCampaignSummaryPath = if ($CampaignSummaryPath.Trim()) {
    Resolve-RepoPath -RepoRoot $repoRoot -PathText $CampaignSummaryPath.Trim()
} else {
    Resolve-RepoPath -RepoRoot $repoRoot -PathText "artifacts/session/live_plus45_short_horizon_v2_20260419/gather_mission_repeatability/campaign_run_summary.json"
}

$auditArgs = @(
    (Join-Path $repoRoot "scripts\gather_escape_divergence_audit.py"),
    "--campaign-id", $resolvedCampaignId,
    "--scenario-id", $ScenarioId,
    "--campaign-summary-path", $resolvedCampaignSummaryPath,
    "--run-index", $RunIndex.ToString()
)
$auditResult = Invoke-PythonScript -Arguments $auditArgs
$summaryPath = Get-MarkerValue -Text $auditResult.Text -Marker "GATHER_ESCAPE_DIVERGENCE_AUDIT_SUMMARY="

if (-not $RunLiveProbeIfRequired) {
    exit $auditResult.ExitCode
}
if (-not $summaryPath) {
    exit $auditResult.ExitCode
}

$resolvedSummaryPath = Resolve-Path -LiteralPath $summaryPath -ErrorAction SilentlyContinue
if (-not $resolvedSummaryPath) {
    exit $auditResult.ExitCode
}

$summary = Get-Content -Path $resolvedSummaryPath.Path -Raw | ConvertFrom-Json
if (-not $summary.live_probe_required) {
    exit $auditResult.ExitCode
}

$sourceCampaignSummary = Get-Content -Path $resolvedCampaignSummaryPath -Raw | ConvertFrom-Json
$probeCampaignId = "${resolvedCampaignId}_live_probe"
$probeCampaignRoot = Join-Path $repoRoot "artifacts\session\$probeCampaignId\gather_escape_divergence_live_probe"
$probeLogsRoot = Join-Path $probeCampaignRoot "logs"
New-Item -ItemType Directory -Path $probeLogsRoot -Force | Out-Null

$preProbeSummaryPath = Join-Path (Split-Path -Parent $resolvedSummaryPath.Path) "divergence_summary_pre_probe.json"
$preProbeScorecardPath = Join-Path (Split-Path -Parent $resolvedSummaryPath.Path) "scorecard_pre_probe.md"
Copy-Item -LiteralPath $resolvedSummaryPath.Path -Destination $preProbeSummaryPath -Force
$scorecardPath = Join-Path (Split-Path -Parent $resolvedSummaryPath.Path) "scorecard.md"
if (Test-Path $scorecardPath) {
    Copy-Item -LiteralPath $scorecardPath -Destination $preProbeScorecardPath -Force
}

$motionProbeJsonPath = Join-Path $probeCampaignRoot "motion_probe.json"
$motionProbeStdoutPath = Join-Path $probeLogsRoot "motion_probe.stdout.log"
$motionProbeStderrPath = Join-Path $probeLogsRoot "motion_probe.stderr.log"
$motionProbeArgs = @(
    (Join-Path $repoRoot "scripts\motion_probe.py"),
    "--duration-s", ([string]([Math]::Max($MotionProbeDurationS, 10.0))),
    "--json-out", $motionProbeJsonPath,
    "--use-sim-time"
)
$motionProbeProcess = $null
try {
    $motionProbeProcess = Start-Process `
        -FilePath "python" `
        -ArgumentList $motionProbeArgs `
        -RedirectStandardOutput $motionProbeStdoutPath `
        -RedirectStandardError $motionProbeStderrPath `
        -PassThru `
        -NoNewWindow
} catch {
    Write-Warning "Unable to start motion_probe.py for the optional live probe: $($_.Exception.Message)"
}

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

$probeResult = Invoke-PythonScript -Arguments $probeArgs

if ($motionProbeProcess) {
    try {
        $waitTimeoutMs = [int](([Math]::Max($MotionProbeDurationS, 10.0) + 15.0) * 1000.0)
        $null = $motionProbeProcess.WaitForExit($waitTimeoutMs)
        if (-not $motionProbeProcess.HasExited) {
            Stop-Process -Id $motionProbeProcess.Id -Force
        }
    } catch {
        Write-Warning "Unable to stop the motion probe process cleanly: $($_.Exception.Message)"
    }
}

$probeSummaryPath = Get-MarkerValue -Text $probeResult.Text -Marker "GATHER_MISSION_REPEATABILITY_SUMMARY="
if (-not $probeSummaryPath) {
    exit $probeResult.ExitCode
}

$rerunArgs = @(
    (Join-Path $repoRoot "scripts\gather_escape_divergence_audit.py"),
    "--campaign-id", $resolvedCampaignId,
    "--scenario-id", $ScenarioId,
    "--campaign-summary-path", $probeSummaryPath,
    "--run-index", "0"
)
$rerunResult = Invoke-PythonScript -Arguments $rerunArgs
exit $rerunResult.ExitCode
