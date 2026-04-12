param(
    [int]$Workers = 2,
    [int]$RunsPerWorker = 1,
    [string]$CampaignId = "",
    [int]$DashboardPortStart = 8870,
    [int]$DashboardPortEnd = 8909,
    [int]$RosDomainIdStart = 180,
    [ValidateSet("robot_fidelity_orin", "workstation_balanced", "workstation_max")]
    [string]$RuntimeTarget = "workstation_max",
    [string]$WorldFile = "yolo_test_world_v6_clean_uat_fast.world",
    [ValidateSet("compat", "balanced", "max")]
    [string]$GatePerfProfile = "max",
    [double]$HiddenStartSettleS = 3.0,
    [double]$MaxTargetRuntimeS = 240.0,
    [double]$SearchTimeoutS = 45.0,
    [double]$ApproachTimeoutS = 120.0,
    [switch]$NoKeepVisitedTargets
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$args = @(
    (Join-Path $repoRoot "scripts\route_planning_parallel_soak_runner.py"),
    "--workers", $Workers.ToString(),
    "--runs-per-worker", $RunsPerWorker.ToString(),
    "--dashboard-port-start", $DashboardPortStart.ToString(),
    "--dashboard-port-end", $DashboardPortEnd.ToString(),
    "--ros-domain-id-start", $RosDomainIdStart.ToString(),
    "--runtime-target", $RuntimeTarget,
    "--world-file", $WorldFile,
    "--gate-perf-profile", $GatePerfProfile,
    "--hidden-start-settle-s", $HiddenStartSettleS.ToString("0.0###############", [System.Globalization.CultureInfo]::InvariantCulture),
    "--max-target-runtime-s", $MaxTargetRuntimeS.ToString("0.0###############", [System.Globalization.CultureInfo]::InvariantCulture),
    "--search-timeout-s", $SearchTimeoutS.ToString("0.0###############", [System.Globalization.CultureInfo]::InvariantCulture),
    "--approach-timeout-s", $ApproachTimeoutS.ToString("0.0###############", [System.Globalization.CultureInfo]::InvariantCulture)
)

if (-not [string]::IsNullOrWhiteSpace($CampaignId)) {
    $args += @("--campaign-id", $CampaignId)
}

if ($NoKeepVisitedTargets.IsPresent) {
    $args += "--no-keep-visited-targets"
}
else {
    $args += "--keep-visited-targets"
}

python @args
exit $LASTEXITCODE
