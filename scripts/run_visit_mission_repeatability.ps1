param(
    [string]$DashboardUrl = $(if ($env:CHASECAR_DASHBOARD_URL) { $env:CHASECAR_DASHBOARD_URL } else { "http://127.0.0.1:8860" }),
    [string]$ScenarioId = "visit_single_ball_proof",
    [string]$ScenarioLabel = "Visit Single Ball",
    [int]$Runs = 3,
    [double]$HiddenStartSettleS = 3.0,
    [switch]$KeepVisitedTargets
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$args = @(
    (Join-Path $repoRoot "scripts\visit_mission_repeatability_runner.py"),
    "--dashboard-url", $DashboardUrl,
    "--scenario-id", $ScenarioId,
    "--scenario-label", $ScenarioLabel,
    "--runs", $Runs.ToString(),
    "--hidden-start-settle-s", $HiddenStartSettleS.ToString("0.0###############")
)

if ($KeepVisitedTargets.IsPresent) {
    $args += "--keep-visited-targets"
}

python @args
exit $LASTEXITCODE
