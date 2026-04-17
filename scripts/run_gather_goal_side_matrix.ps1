param(
    [string]$DashboardUrl = $(if ($env:CHASECAR_DASHBOARD_URL) { $env:CHASECAR_DASHBOARD_URL } else { "http://127.0.0.1:8860" }),
    [string]$CampaignId = "",
    [string]$Provider = $(if ($env:CHASECAR_LLM_PROVIDER) { $env:CHASECAR_LLM_PROVIDER } else { "openai" }),
    [string]$ExecutionMode = "direct",
    [string]$PromotionGateMode = "pass_only",
    [string]$WorldFile = "yolo_test_world_v6_clean_uat_short_turf.world",
    [string]$SurfaceProfile = "short_turf",
    [int]$RunsPerCase = 1
)

$ErrorActionPreference = "Stop"

function Get-CurrentUtcStamp {
    return [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
}

function New-GoalSideTargetLayout {
    param(
        [double]$AngleDeg,
        [string]$CaseLabel
    )

    $zoneWorldX = 2.40
    $zoneWorldY = 0.00
    $spawnRadiusM = 3.048
    $radians = [Math]::PI * $AngleDeg / 180.0
    $forwardM = [Math]::Round($zoneWorldX + ($spawnRadiusM * [Math]::Cos($radians)), 6)
    $lateralM = [Math]::Round($zoneWorldY + ($spawnRadiusM * [Math]::Sin($radians)), 6)

    return @{
        targets = @(
            @{
                id = "ball_1"
                label = $CaseLabel
                start_visible = $false
                forward_m = $forwardM
                lateral_m = $lateralM
                z_m = 0.05
                visit_tolerance_m = 0.35
                min_dwell_s = 1.0
            }
        )
    }
}

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][object]$Value
    )

    $json = $Value | ConvertTo-Json -Depth 10 -Compress
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $json, $utf8NoBom)
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

$repoRoot = Split-Path -Parent $PSScriptRoot
$campaignIdValue = if ($CampaignId.Trim()) { $CampaignId.Trim() } else { Get-CurrentUtcStamp }
$campaignRoot = Join-Path $repoRoot "artifacts\session\$campaignIdValue\gather_goal_side_matrix"
$logsRoot = Join-Path $campaignRoot "logs"
$layoutsRoot = Join-Path $campaignRoot "target_layouts"

New-Item -ItemType Directory -Path $logsRoot -Force | Out-Null
New-Item -ItemType Directory -Path $layoutsRoot -Force | Out-Null

$cases = @(
    @{ case_id = "plus45"; angle_deg = 45.0; label = "Ball 1 (+45)"; },
    @{ case_id = "zero"; angle_deg = 0.0; label = "Ball 1 (0)"; },
    @{ case_id = "minus45"; angle_deg = -45.0; label = "Ball 1 (-45)"; },
    @{ case_id = "backside180"; angle_deg = 180.0; label = "Ball 1 (180 backside)"; }
)

$caseResults = @()
foreach ($case in $cases) {
    $layoutPath = Join-Path $layoutsRoot ($case.case_id + ".json")
    $layoutPayload = New-GoalSideTargetLayout -AngleDeg ([double]$case.angle_deg) -CaseLabel $case.label
    Write-JsonFile -Path $layoutPath -Value $layoutPayload

    $caseCampaignId = "$campaignIdValue" + "_" + $case.case_id
    $caseStdoutPath = Join-Path $logsRoot ($case.case_id + ".stdout.log")
    $caseStderrPath = Join-Path $logsRoot ($case.case_id + ".stderr.log")
    $caseLogPath = Join-Path $logsRoot ($case.case_id + ".log")
    $args = @(
        (Join-Path $repoRoot "scripts\gather_mission_repeatability_runner.py"),
        "--dashboard-url", $DashboardUrl,
        "--scenario-id", "corral_single_ball_place",
        "--scenario-label", "Corral Single Ball Place",
        "--runs", $RunsPerCase.ToString(),
        "--campaign-id", $caseCampaignId,
        "--provider", $Provider,
        "--execution-mode", $ExecutionMode,
        "--promotion-gate-mode", $PromotionGateMode,
        "--world-file", $WorldFile,
        "--surface-profile", $SurfaceProfile,
        "--target-layout-json", $layoutPath
    )

    & python @args 1> $caseStdoutPath 2> $caseStderrPath
    $caseExitCode = $LASTEXITCODE
    $stdoutText = if (Test-Path $caseStdoutPath) { Get-Content -Path $caseStdoutPath -Raw } else { "" }
    $stderrText = if (Test-Path $caseStderrPath) { Get-Content -Path $caseStderrPath -Raw } else { "" }
    $output = ($stdoutText + $(if ($stderrText) { "`n$stderrText" } else { "" }))
    Set-Content -Path $caseLogPath -Value $output -Encoding UTF8
    $summaryPath = Get-MarkerValue -Text $output -Marker "GATHER_MISSION_REPEATABILITY_SUMMARY="
    $repeatabilitySummary = @{}
    if ($summaryPath) {
        $resolvedSummaryPath = Resolve-Path $summaryPath -ErrorAction SilentlyContinue
        if ($resolvedSummaryPath) {
            $repeatabilitySummary = Get-Content -Path $resolvedSummaryPath.Path -Raw | ConvertFrom-Json
        }
    }

    $runs = @()
    if ($repeatabilitySummary.runs) {
        $runs = @($repeatabilitySummary.runs)
    }
    $caseResults += [ordered]@{
        case_id = $case.case_id
        angle_deg = [double]$case.angle_deg
        label = $case.label
        target_layout_path = $layoutPath
        repeatability_campaign_id = $caseCampaignId
        repeatability_summary_path = $summaryPath
        repeatability_scorecard_path = if ($summaryPath) { Join-Path (Split-Path -Parent $summaryPath) "scorecard.md" } else { "" }
        repeatability_return_code = $caseExitCode
        pass_count = if ($repeatabilitySummary.pass_count -ne $null) { [int]$repeatabilitySummary.pass_count } else { 0 }
        promotion_gate_pass = if ($repeatabilitySummary.promotion_gate_pass -ne $null) { [bool]$repeatabilitySummary.promotion_gate_pass } else { $false }
        approach_side_pass_count = if ($repeatabilitySummary.approach_side_pass_count -ne $null) { [int]$repeatabilitySummary.approach_side_pass_count } else { 0 }
        approach_side_fail_count = if ($repeatabilitySummary.approach_side_fail_count -ne $null) { [int]$repeatabilitySummary.approach_side_fail_count } else { 0 }
        staging_pose_reached_count = if ($repeatabilitySummary.staging_pose_reached_count -ne $null) { [int]$repeatabilitySummary.staging_pose_reached_count } else { 0 }
        entered_goal_side_before_capture_count = if ($repeatabilitySummary.entered_goal_side_before_capture_count -ne $null) { [int]$repeatabilitySummary.entered_goal_side_before_capture_count } else { 0 }
        first_contact_push_alignment_avg_deg = if ($repeatabilitySummary.first_contact_push_alignment_avg_deg -ne $null) { [double]$repeatabilitySummary.first_contact_push_alignment_avg_deg } else { 0.0 }
        push_direction_yaw_avg_deg = if ($repeatabilitySummary.push_direction_yaw_avg_deg -ne $null) { [double]$repeatabilitySummary.push_direction_yaw_avg_deg } else { 0.0 }
        stage_time_avg_s = if ($repeatabilitySummary.stage_time_avg_s -ne $null) { [double]$repeatabilitySummary.stage_time_avg_s } else { 0.0 }
        output_log_path = $caseLogPath
        stdout_log_path = $caseStdoutPath
        stderr_log_path = $caseStderrPath
        runs = $runs
    }
}

$casePassCount = @($caseResults | Where-Object { $_.promotion_gate_pass }).Count
$summary = [ordered]@{
    generated_utc = [DateTime]::UtcNow.ToString("o")
    type = "gather_goal_side_matrix"
    campaign_id = $campaignIdValue
    scenario_id = "corral_single_ball_place"
    scenario_label = "Corral Single Ball Place"
    world_file = $WorldFile
    surface_profile = $SurfaceProfile
    execution_mode = $ExecutionMode
    promotion_gate_mode = $PromotionGateMode
    required_green_cases = @($cases).Count
    case_pass_count = $casePassCount
    promotion_gate_pass = ($casePassCount -eq @($cases).Count)
    requested_runs_per_case = $RunsPerCase
    requested_world_file = $WorldFile
    requested_surface_profile = $SurfaceProfile
    requested_target_layout_strategy = "short_turf goal-side matrix (+45, 0, -45, 180 backside)"
    campaign_root = $campaignRoot
    cases = $caseResults
}

Write-JsonFile -Path (Join-Path $campaignRoot "campaign_summary.json") -Value $summary

$scorecardLines = @(
    "# Gather Goal-Side Matrix Scorecard",
    "",
    ('- Campaign: `{0}`' -f $campaignIdValue),
    ('- Scenario: `{0}`' -f 'corral_single_ball_place'),
    ('- Surface profile: `{0}`' -f $SurfaceProfile),
    ('- World file: `{0}`' -f $WorldFile),
    ('- Promotion gate: `{0}`' -f $(if ($summary.promotion_gate_pass) { 'PASS' } else { 'FAIL' })),
    ('- Case pass count: `{0}/{1}`' -f $casePassCount, @($cases).Count),
    "",
    "## Cases",
    ""
)

foreach ($case in $caseResults) {
    $scorecardLines += (
        '- `{0}` angle={1:0.###}deg pass={2} approach={3}/{4} staging={5} goal_side={6} align_avg={7:0.000}deg yaw_avg={8:0.000}deg stage_avg={9:0.000}s summary={10}' -f
        $case.case_id,
        [double]$case.angle_deg,
        [bool]$case.promotion_gate_pass,
        [int]$case.approach_side_pass_count,
        [int]$case.approach_side_fail_count,
        [int]$case.staging_pose_reached_count,
        [int]$case.entered_goal_side_before_capture_count,
        [double]$case.first_contact_push_alignment_avg_deg,
        [double]$case.push_direction_yaw_avg_deg,
        [double]$case.stage_time_avg_s,
        [string]$case.repeatability_summary_path
    )
}

Set-Content -Path (Join-Path $campaignRoot "scorecard.md") -Value ($scorecardLines -join [Environment]::NewLine) -Encoding UTF8
$campaignSummaryPath = Join-Path $campaignRoot "campaign_summary.json"
Write-Host "GATHER_GOAL_SIDE_MATRIX_SUMMARY=$campaignSummaryPath"
Write-Host ($summary | ConvertTo-Json -Depth 10)
exit $(if ($summary.promotion_gate_pass) { 0 } else { 2 })
