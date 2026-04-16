param(
    [string]$DashboardUrl = $(if ($env:CHASECAR_DASHBOARD_URL) { $env:CHASECAR_DASHBOARD_URL } else { "http://127.0.0.1:8860" }),
    [int]$RunsPerLane = 3,
    [string]$CampaignId = "",
    [string]$Provider = $(if ($env:CHASECAR_LLM_PROVIDER) { $env:CHASECAR_LLM_PROVIDER } else { "openai" }),
    [string]$ExecutionMode = "dashboard_scenario",
    [string]$PreferredSurfaceProfile = "short_turf"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$args = @(
    (Join-Path $repoRoot "scripts\corral_surface_calibration_runner.py"),
    "--dashboard-url", $DashboardUrl,
    "--runs-per-lane", $RunsPerLane.ToString(),
    "--provider", $Provider,
    "--execution-mode", $ExecutionMode,
    "--preferred-surface-profile", $PreferredSurfaceProfile
)

if ($CampaignId.Trim()) {
    $args += @("--campaign-id", $CampaignId.Trim())
}

python @args
exit $LASTEXITCODE
