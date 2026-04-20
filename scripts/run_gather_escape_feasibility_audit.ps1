param(
    [string]$CampaignId = "",
    [string]$ScenarioId = "corral_single_ball_place"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$args = @(
    (Join-Path $repoRoot "scripts\gather_escape_feasibility_audit.py"),
    "--scenario-id", $ScenarioId
)
if ($CampaignId.Trim()) {
    $args += @("--campaign-id", $CampaignId.Trim())
}

& python @args
$exitCode = $LASTEXITCODE
exit $exitCode
