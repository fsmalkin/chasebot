param(
    [string]$CampaignId = "",
    [string]$ScenarioId = "corral_single_ball_place",
    [string]$CampaignSummaryPath = "",
    [int]$RunIndex = 0
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$args = @(
    (Join-Path $repoRoot "scripts\gather_manual_drive_sign_parity_audit.py"),
    "--scenario-id", $ScenarioId,
    "--run-index", $RunIndex.ToString()
)
if ($CampaignId.Trim()) {
    $args += @("--campaign-id", $CampaignId.Trim())
}
if ($CampaignSummaryPath.Trim()) {
    $args += @("--campaign-summary-path", $CampaignSummaryPath.Trim())
}

& python @args
$exitCode = $LASTEXITCODE
exit $exitCode
