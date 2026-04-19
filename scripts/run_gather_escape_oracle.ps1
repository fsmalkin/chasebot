param(
    [string]$CampaignId = "",
    [string]$ScenarioId = "corral_single_ball_place",
    [ValidateSet("control_v1", "deep_escape_v1")]
    [string]$SearchProfile = "deep_escape_v1"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$args = @(
    (Join-Path $repoRoot "scripts\gather_escape_oracle.py"),
    "--scenario-id", $ScenarioId,
    "--search-profile", $SearchProfile
)
if ($CampaignId.Trim()) {
    $args += @("--campaign-id", $CampaignId.Trim())
}

& python @args
$exitCode = $LASTEXITCODE
exit $exitCode
