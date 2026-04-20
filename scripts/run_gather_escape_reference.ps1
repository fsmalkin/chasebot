param(
    [string]$CampaignId = "",
    [string]$ScenarioId = "corral_single_ball_place",
    [ValidateSet("reference_v1")]
    [string]$SearchProfile = "reference_v1"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$args = @(
    (Join-Path $repoRoot "scripts\gather_escape_reference.py"),
    "--scenario-id", $ScenarioId,
    "--search-profile", $SearchProfile
)
if ($CampaignId.Trim()) {
    $args += @("--campaign-id", $CampaignId.Trim())
}

& python @args
$exitCode = $LASTEXITCODE
exit $exitCode
