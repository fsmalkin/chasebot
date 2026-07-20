param(
    [string]$DashboardUrl = "http://127.0.0.1:8860",
    [string]$ComposeProject = "",
    [string]$CampaignId = "",
    [int]$Runs = 3,
    [double]$SampleDurationS = 12.0,
    [double]$PollPeriodS = 0.12,
    [string]$SurfaceProfile = "calibrated_golf_turf",
    [string]$WorldFile = "yolo_test_world_v6_calibrated_golf_turf.world",
    [string]$BallModelSdf = "ros2_config/calibrated_golf_ball.sdf",
    [string]$RampFixtureSdf = "ros2_config/ball_roll_ramp_fixture.sdf",
    [switch]$KeepModels
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$argsList = @(
    "scripts/passive_ball_roll_calibration_runner.py",
    "--dashboard-url", $DashboardUrl,
    "--runs", $Runs.ToString(),
    "--sample-duration-s", $SampleDurationS.ToString("0.###"),
    "--poll-period-s", $PollPeriodS.ToString("0.###"),
    "--surface-profile", $SurfaceProfile,
    "--world-file", $WorldFile,
    "--ball-model-sdf", $BallModelSdf,
    "--ramp-fixture-sdf", $RampFixtureSdf
)
if (-not [string]::IsNullOrWhiteSpace($ComposeProject)) {
    $argsList += @("--compose-project", $ComposeProject)
}
if (-not [string]::IsNullOrWhiteSpace($CampaignId)) {
    $argsList += @("--campaign-id", $CampaignId)
}
if ($KeepModels) {
    $argsList += "--keep-models"
}

Push-Location $repoRoot
try {
    python @argsList
}
finally {
    Pop-Location
}
