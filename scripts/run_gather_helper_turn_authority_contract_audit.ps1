param(
    [string]$CampaignId = "",
    [string]$ScenarioId = "corral_single_ball_place",
    [string]$CampaignSummaryPath = "",
    [int]$RunIndex = 0
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$args = @(
    (Join-Path $repoRoot "scripts\gather_helper_turn_authority_contract_audit.py"),
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
