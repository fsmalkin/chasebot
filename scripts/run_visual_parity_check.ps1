param(
    [string]$SessionId = "",
    [string]$HeadlessSummaryPath = "",
    [string]$GuiSummaryPath = "",
    [string]$OutputPath = "",
    [double]$MaxTargetImprovementDeltaM = 0.80,
    [switch]$AllowCrossSession
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-SessionId {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return ""
    }
    if ($Value -notmatch '^\d{8}T\d{6}Z$') {
        throw "SessionId must match YYYYMMDDTHHMMSSZ."
    }
    return $Value
}

function Resolve-RepoPath {
    param([string]$PathValue, [string]$RepoRoot)
    if ([string]::IsNullOrWhiteSpace($PathValue)) { return "" }
    $normalized = [regex]::Replace($PathValue, '\\\\+', '\')
    if ($normalized -match '^[A-Za-z]:\\') { return $normalized }
    if ($normalized -match '^/mnt/([a-zA-Z])/(.*)$') {
        $drive = $matches[1].ToUpperInvariant()
        $rest = $matches[2] -replace '/', '\'
        return "$drive`:\$rest"
    }
    if ($normalized.StartsWith("/workspaces/chasecar/")) {
        $rest = $normalized.Substring("/workspaces/chasecar/".Length).Replace('/', '\')
        return Join-Path $RepoRoot $rest
    }
    return Join-Path $RepoRoot $normalized
}

function Load-JsonFile {
    param([string]$PathValue)
    if (-not (Test-Path -LiteralPath $PathValue)) {
        throw "JSON file not found: $PathValue"
    }
    return (Get-Content -LiteralPath $PathValue -Raw | ConvertFrom-Json)
}

function Get-PropValue {
    param(
        [object]$Object,
        [string[]]$Path,
        [object]$Default = $null
    )
    $current = $Object
    foreach ($segment in $Path) {
        if ($null -eq $current) { return $Default }
        if ($current -is [System.Collections.IDictionary]) {
            if (-not $current.Contains($segment)) { return $Default }
            $current = $current[$segment]
            continue
        }
        $prop = $current.PSObject.Properties[$segment]
        if ($null -eq $prop) { return $Default }
        $current = $prop.Value
    }
    if ($null -eq $current) { return $Default }
    return $current
}

function To-Bool {
    param([object]$Value)
    if ($null -eq $Value) { return $false }
    if ($Value -is [bool]) { return [bool]$Value }
    if ($Value -is [int] -or $Value -is [long]) { return ([int]$Value -ne 0) }
    $text = $Value.ToString().Trim().ToLowerInvariant()
    return ($text -in @("true", "1", "yes"))
}

function To-Double {
    param([object]$Value, [double]$Default = 0.0)
    if ($null -eq $Value) { return $Default }
    $parsed = 0.0
    if ([double]::TryParse($Value.ToString(), [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$parsed)) {
        return $parsed
    }
    return $Default
}

function Find-LatestFile {
    param([string]$RootDir, [string]$FileName)
    if (-not (Test-Path -LiteralPath $RootDir)) { return "" }
    $candidates = Get-ChildItem -LiteralPath $RootDir -Directory -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending
    foreach ($dir in $candidates) {
        $path = Join-Path $dir.FullName $FileName
        if (Test-Path -LiteralPath $path) {
            return $path
        }
    }
    return ""
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$requestedSessionId = Resolve-SessionId -Value $SessionId

$resolvedHeadlessPath = Resolve-RepoPath -PathValue $HeadlessSummaryPath -RepoRoot $repoRoot
$resolvedGuiPath = Resolve-RepoPath -PathValue $GuiSummaryPath -RepoRoot $repoRoot

if ([string]::IsNullOrWhiteSpace($resolvedHeadlessPath)) {
    if (-not [string]::IsNullOrWhiteSpace($requestedSessionId)) {
        $candidate = Join-Path $repoRoot "artifacts/session/$requestedSessionId/pre_llm_headless_summary.json"
        if (Test-Path -LiteralPath $candidate) { $resolvedHeadlessPath = $candidate }
    }
    if ([string]::IsNullOrWhiteSpace($resolvedHeadlessPath)) {
        $resolvedHeadlessPath = Find-LatestFile -RootDir (Join-Path $repoRoot "artifacts/session") -FileName "pre_llm_headless_summary.json"
    }
}
if ([string]::IsNullOrWhiteSpace($resolvedGuiPath)) {
    if (-not [string]::IsNullOrWhiteSpace($requestedSessionId)) {
        $candidate = Join-Path $repoRoot "artifacts/session/$requestedSessionId/pre_llm_gui_rehearsal_summary.json"
        if (Test-Path -LiteralPath $candidate) { $resolvedGuiPath = $candidate }
    }
    if ([string]::IsNullOrWhiteSpace($resolvedGuiPath)) {
        $resolvedGuiPath = Find-LatestFile -RootDir (Join-Path $repoRoot "artifacts/session") -FileName "pre_llm_gui_rehearsal_summary.json"
    }
}

if ([string]::IsNullOrWhiteSpace($resolvedHeadlessPath)) { throw "Unable to resolve headless summary path." }
if ([string]::IsNullOrWhiteSpace($resolvedGuiPath)) { throw "Unable to resolve GUI rehearsal summary path." }

$headlessSummary = Load-JsonFile -PathValue $resolvedHeadlessPath
$guiSummary = Load-JsonFile -PathValue $resolvedGuiPath

$headlessRunId = [string](Get-PropValue -Object $headlessSummary -Path @("run_id") -Default "")
$guiRunId = [string](Get-PropValue -Object $guiSummary -Path @("run_id") -Default "")
$effectiveSessionId = if (-not [string]::IsNullOrWhiteSpace($requestedSessionId)) {
    $requestedSessionId
}
elseif (-not [string]::IsNullOrWhiteSpace($guiRunId)) {
    $guiRunId
}
elseif (-not [string]::IsNullOrWhiteSpace($headlessRunId)) {
    $headlessRunId
}
else {
    (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
}
$effectiveSessionId = Resolve-SessionId -Value $effectiveSessionId

$resolvedOutputPath = if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    Join-Path $repoRoot "artifacts/session/$effectiveSessionId/parity_summary.json"
}
else {
    Resolve-RepoPath -PathValue $OutputPath -RepoRoot $repoRoot
}
New-Item -ItemType Directory -Path (Split-Path -Parent $resolvedOutputPath) -Force | Out-Null

$laneResultsRaw = Get-PropValue -Object $headlessSummary -Path @("lane_results") -Default @()
$laneResults = if ($laneResultsRaw -is [System.Array]) { @($laneResultsRaw) } elseif ($null -eq $laneResultsRaw) { @() } else { @($laneResultsRaw) }
$headlessLane = @($laneResults | Where-Object { [string](Get-PropValue -Object $_ -Path @("lane") -Default "") -eq "fidelity" } | Select-Object -First 1)[0]
if ($null -eq $headlessLane) {
    $headlessLane = @($laneResults | Select-Object -First 1)[0]
}

$headlessReadinessPath = Resolve-RepoPath -PathValue ([string](Get-PropValue -Object $headlessLane -Path @("artifacts", "readiness_report") -Default "")) -RepoRoot $repoRoot
$headlessReadiness = $null
if (-not [string]::IsNullOrWhiteSpace($headlessReadinessPath) -and (Test-Path -LiteralPath $headlessReadinessPath)) {
    $headlessReadiness = Load-JsonFile -PathValue $headlessReadinessPath
}

$stepsRaw = Get-PropValue -Object $headlessReadiness -Path @("steps") -Default @()
$steps = if ($stepsRaw -is [System.Array]) { @($stepsRaw) } elseif ($null -eq $stepsRaw) { @() } else { @($stepsRaw) }
$coordinateStep = @($steps | Where-Object { [string](Get-PropValue -Object $_ -Path @("id") -Default "") -eq "coordinate" } | Select-Object -First 1)[0]
$snapshotStep = @($steps | Where-Object { [string](Get-PropValue -Object $_ -Path @("id") -Default "") -eq "snapshot" } | Select-Object -First 1)[0]
$navStep = @($steps | Where-Object { [string](Get-PropValue -Object $_ -Path @("id") -Default "") -eq "nav2" } | Select-Object -First 1)[0]

$coordinateSummaryPath = Resolve-RepoPath -PathValue ([string](Get-PropValue -Object $coordinateStep -Path @("artifact_dir") -Default "")) -RepoRoot $repoRoot
$snapshotSummaryPath = Resolve-RepoPath -PathValue ([string](Get-PropValue -Object $snapshotStep -Path @("artifact_dir") -Default "")) -RepoRoot $repoRoot
$navSummaryPath = Resolve-RepoPath -PathValue ([string](Get-PropValue -Object $navStep -Path @("artifact_dir") -Default "")) -RepoRoot $repoRoot
if (-not [string]::IsNullOrWhiteSpace($coordinateSummaryPath)) { $coordinateSummaryPath = Join-Path $coordinateSummaryPath "summary.json" }
if (-not [string]::IsNullOrWhiteSpace($snapshotSummaryPath)) { $snapshotSummaryPath = Join-Path $snapshotSummaryPath "snapshot_summary.json" }
if (-not [string]::IsNullOrWhiteSpace($navSummaryPath)) { $navSummaryPath = Join-Path $navSummaryPath "nav_summary.json" }

$coordinateSummary = if (Test-Path -LiteralPath $coordinateSummaryPath) { Load-JsonFile -PathValue $coordinateSummaryPath } else { $null }
$snapshotSummary = if (Test-Path -LiteralPath $snapshotSummaryPath) { Load-JsonFile -PathValue $snapshotSummaryPath } else { $null }
$navSummary = if (Test-Path -LiteralPath $navSummaryPath) { Load-JsonFile -PathValue $navSummaryPath } else { $null }

$m2Outcome = Get-PropValue -Object $guiSummary -Path @("final_outcomes", "milestone2") -Default $null
$m3OutcomesRaw = Get-PropValue -Object $guiSummary -Path @("final_outcomes", "milestone3") -Default @()
$m3Outcomes = if ($m3OutcomesRaw -is [System.Array]) { @($m3OutcomesRaw) } elseif ($null -eq $m3OutcomesRaw) { @() } else { @($m3OutcomesRaw) }

$headlessExecutionLane = [string](Get-PropValue -Object $headlessReadiness -Path @("execution_lane") -Default (Get-PropValue -Object $headlessSummary -Path @("execution_lane") -Default ""))
$headlessCoreRos = [string](Get-PropValue -Object $headlessReadiness -Path @("container_core_ros_distro") -Default (Get-PropValue -Object $headlessSummary -Path @("core_ros_distro") -Default ""))
$guiExecutionLane = [string](Get-PropValue -Object $guiSummary -Path @("execution_lane") -Default "")
$guiCoreRos = [string](Get-PropValue -Object $guiSummary -Path @("core_ros_distro") -Default "")

$headlessPass = To-Bool (Get-PropValue -Object $headlessSummary -Path @("pre_llm_ready") -Default $false)
$guiPass = To-Bool (Get-PropValue -Object $guiSummary -Path @("pass") -Default $false)

$headDetectionRate = To-Double (Get-PropValue -Object $coordinateSummary -Path @("detection_success_rate") -Default 0.0)
$headDetectionPipelineAlive = To-Bool (Get-PropValue -Object $coordinateSummary -Path @("pass") -Default $false)
$head3dActive = ($headDetectionRate -gt 0.0)
$headNavActionReady = (To-Double (Get-PropValue -Object $navSummary -Path @("goal_accept_count") -Default 0.0) -ge 1.0)
$headCmdVelRate = To-Double (Get-PropValue -Object $navSummary -Path @("cmd_vel_stats", "rate_hz") -Default 0.0)
$headCmdVelActive = ($headCmdVelRate -gt 0.1)
$headTargetImprovement = To-Double (Get-PropValue -Object $navSummary -Path @("target_progress", "distance_improvement_m") -Default 0.0)
$headTargetFinalDistance = To-Double (Get-PropValue -Object $navSummary -Path @("target_progress", "end_distance_m") -Default 0.0)
$headTargetProgressPass = To-Bool (Get-PropValue -Object $navSummary -Path @("target_progress", "pass") -Default $false)

$m2DemoSummary = Get-PropValue -Object $m2Outcome -Path @("demo_summary") -Default $null
$guiDetectionPipelineAlive = To-Bool (Get-PropValue -Object $m2DemoSummary -Path @("process_health", "detector_running") -Default $false)
$gui3dActive = To-Bool (Get-PropValue -Object $m2DemoSummary -Path @("capture", "ball_position_3d_seen") -Default $false)

$m3CheckCount = 0
$m3PassCount = 0
$m3NavReadyAll = $true
$m3CmdVelAll = $true
$m3MotionAll = $true
$m3ImprovementValues = @()
$m3FinalDistanceValues = @()
$m3CmdVelRates = @()
foreach ($m3 in $m3Outcomes) {
    $m3Demo = Get-PropValue -Object $m3 -Path @("demo_summary") -Default $null
    if ($null -eq $m3Demo) { continue }
    $m3CheckCount += 1
    if (To-Bool (Get-PropValue -Object $m3 -Path @("pass") -Default $false)) {
        $m3PassCount += 1
    }
    $navReady = To-Bool (Get-PropValue -Object $m3Demo -Path @("nav2", "action_server_ready") -Default $false)
    $cmdCount = To-Double (Get-PropValue -Object $m3Demo -Path @("motion", "cmd_vel_message_count") -Default 0.0)
    $windowS = [Math]::Max((To-Double (Get-PropValue -Object $m3Demo -Path @("motion", "window_s") -Default 90.0)), 1.0)
    $cmdRate = ($cmdCount / $windowS)
    $motionPass = To-Bool (Get-PropValue -Object $m3Demo -Path @("motion", "pass") -Default $false)
    $targetProgressOk = To-Bool (Get-PropValue -Object $m3Demo -Path @("motion", "target_progress_ok") -Default $false)
    $startDistance = To-Double (Get-PropValue -Object $m3Demo -Path @("motion", "target_start_distance_m") -Default 0.0)
    $endDistance = To-Double (Get-PropValue -Object $m3Demo -Path @("motion", "target_end_distance_m") -Default 0.0)
    $improvement = $startDistance - $endDistance

    if (-not $navReady) { $m3NavReadyAll = $false }
    if ($cmdCount -le 0) { $m3CmdVelAll = $false }
    if (-not ($motionPass -and $targetProgressOk)) { $m3MotionAll = $false }
    $m3ImprovementValues += $improvement
    $m3FinalDistanceValues += $endDistance
    $m3CmdVelRates += $cmdRate
}

$guiNavReady = ($m3CheckCount -gt 0 -and $m3NavReadyAll)
$guiCmdVelActive = ($m3CheckCount -gt 0 -and $m3CmdVelAll)
$guiMotionPass = ($m3CheckCount -gt 0 -and $m3MotionAll -and $m3PassCount -eq $m3CheckCount)
$guiAvgImprovement = if ($m3ImprovementValues.Count -gt 0) { ($m3ImprovementValues | Measure-Object -Average).Average } else { 0.0 }
$guiAvgFinalDistance = if ($m3FinalDistanceValues.Count -gt 0) { ($m3FinalDistanceValues | Measure-Object -Average).Average } else { 0.0 }
$guiAvgCmdVelRate = if ($m3CmdVelRates.Count -gt 0) { ($m3CmdVelRates | Measure-Object -Average).Average } else { 0.0 }

$sessionIdMatch = ($headlessRunId -eq $guiRunId -and $guiRunId -eq $effectiveSessionId)
if ($AllowCrossSession.IsPresent) {
    $sessionIdMatch = $true
}
$laneMatch = ($headlessExecutionLane -eq "container_kilted" -and $guiExecutionLane -eq "container_kilted")
$coreRosMatch = ($headlessCoreRos -eq "kilted" -and $guiCoreRos -eq "kilted")
$detectionPipelineMatch = ($headDetectionPipelineAlive -and $guiDetectionPipelineAlive)
$topic3dMatch = ($head3dActive -and $gui3dActive)
$navActionMatch = ($headNavActionReady -and $guiNavReady)
$motionEvidenceMatch = ($headCmdVelActive -and $guiCmdVelActive -and $headTargetProgressPass -and $guiMotionPass)
$graphMatch = ($detectionPipelineMatch -and $topic3dMatch -and $navActionMatch -and $motionEvidenceMatch)

$targetImprovementDelta = [Math]::Abs($headTargetImprovement - $guiAvgImprovement)
$finalDistanceDelta = [Math]::Abs($headTargetFinalDistance - $guiAvgFinalDistance)
$cmdVelRateDelta = [Math]::Abs($headCmdVelRate - $guiAvgCmdVelRate)
$metricParity = ($targetImprovementDelta -le $MaxTargetImprovementDeltaM)

$requiredFiles = @(
    $resolvedHeadlessPath,
    $resolvedGuiPath,
    $headlessReadinessPath,
    $coordinateSummaryPath,
    $snapshotSummaryPath,
    $navSummaryPath
) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
$missingFiles = @($requiredFiles | Where-Object { -not (Test-Path -LiteralPath $_) })

$checks = [ordered]@{
    session_id_match = $sessionIdMatch
    lane_match = $laneMatch
    core_ros_match = $coreRosMatch
    headless_ready = $headlessPass
    gui_ready = $guiPass
    detection_pipeline_alive = $detectionPipelineMatch
    ball_position_3d_active = $topic3dMatch
    nav_action_server_ready = $navActionMatch
    motion_evidence = $motionEvidenceMatch
    metric_parity = $metricParity
}

$failureClass = ""
if ($missingFiles.Count -gt 0) {
    $failureClass = "missing_artifact"
}
elseif (-not $sessionIdMatch) {
    $failureClass = "session_id_mismatch"
}
elseif (-not $laneMatch) {
    $failureClass = "lane_mismatch"
}
elseif (-not $coreRosMatch) {
    $failureClass = "core_ros_mismatch"
}
elseif (-not $headlessPass) {
    $failureClass = "headless_not_ready"
}
elseif (-not $guiPass) {
    $failureClass = "gui_not_ready"
}
elseif (-not $detectionPipelineMatch) {
    $failureClass = "detection_pipeline_mismatch"
}
elseif (-not $topic3dMatch) {
    $failureClass = "topic_3d_mismatch"
}
elseif (-not $navActionMatch) {
    $failureClass = "nav_action_mismatch"
}
elseif (-not $motionEvidenceMatch) {
    $failureClass = "target_distance_not_improving"
}
elseif (-not $metricParity) {
    $failureClass = "metric_divergence"
}

$pass = ([string]::IsNullOrWhiteSpace($failureClass))

$result = [ordered]@{
    run_id = $effectiveSessionId
    generated_utc = (Get-Date).ToUniversalTime().ToString("o")
    pass = $pass
    failure_class = if ($pass) { "" } else { $failureClass }
    lane_match = $laneMatch
    graph_match = $graphMatch
    checks = $checks
    paths = [ordered]@{
        headless_summary = $resolvedHeadlessPath
        gui_summary = $resolvedGuiPath
        headless_readiness = $headlessReadinessPath
        coordinate_summary = $coordinateSummaryPath
        snapshot_summary = $snapshotSummaryPath
        nav_summary = $navSummaryPath
        parity_summary = $resolvedOutputPath
    }
    session = [ordered]@{
        headless_run_id = $headlessRunId
        gui_run_id = $guiRunId
        expected_run_id = $effectiveSessionId
    }
    runtime = [ordered]@{
        headless_execution_lane = $headlessExecutionLane
        gui_execution_lane = $guiExecutionLane
        headless_core_ros_distro = $headlessCoreRos
        gui_core_ros_distro = $guiCoreRos
    }
    metrics = [ordered]@{
        headless = [ordered]@{
            detection_success_rate = $headDetectionRate
            nav_goal_accept_count = To-Double (Get-PropValue -Object $navSummary -Path @("goal_accept_count") -Default 0.0)
            cmd_vel_rate_hz = $headCmdVelRate
            target_improvement_m = $headTargetImprovement
            target_final_distance_m = $headTargetFinalDistance
        }
        gui = [ordered]@{
            milestone3_target_count = $m3CheckCount
            cmd_vel_rate_hz_avg = $guiAvgCmdVelRate
            target_improvement_m_avg = $guiAvgImprovement
            target_final_distance_m_avg = $guiAvgFinalDistance
        }
        deltas = [ordered]@{
            target_improvement_delta_m = $targetImprovementDelta
            final_distance_delta_m = $finalDistanceDelta
            cmd_vel_rate_delta_hz = $cmdVelRateDelta
            max_target_improvement_delta_m = $MaxTargetImprovementDeltaM
        }
    }
    evidence = [ordered]@{
        missing_files = $missingFiles
    }
}

$result | ConvertTo-Json -Depth 10 | Set-Content -Path $resolvedOutputPath -Encoding UTF8
Write-Host "PARITY_SUMMARY=$resolvedOutputPath"
Write-Host "PARITY_PASS=$pass"
if ($pass) { exit 0 }
exit 2
