param(
    [Parameter(Mandatory = $true)]
    [string]$RobotHost,

    [int]$Port = 8765,

    [double]$Speed = 0.35,

    [double]$PulseSeconds = 0.4,

    [double]$PreDelaySeconds = 8.0,

    [string]$CampaignId = ("factory_bridge_lifted_wheel_{0}" -f (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")),

    [switch]$ConfirmHeldInAir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $ConfirmHeldInAir) {
    throw "Refusing wheel test without -ConfirmHeldInAir."
}

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$artifactRoot = Join-Path $repoRoot ("artifacts/session/{0}/factory_bridge_lifted_wheel" -f $CampaignId)
New-Item -ItemType Directory -Force -Path $artifactRoot | Out-Null

$baseUri = "http://${RobotHost}:$Port"
$health = Invoke-RestMethod -Uri "$baseUri/health" -TimeoutSec 3
if (-not [bool]$health.motion_enabled) {
    throw "Bridge health reports motion_enabled=false. Restart with -EnableMotion before lifted-wheel testing."
}

Write-Host "Holding delay: $PreDelaySeconds seconds" -ForegroundColor Yellow
Start-Sleep -Seconds $PreDelaySeconds

$responses = New-Object System.Collections.Generic.List[object]
$steps = @(
    @{ label = "left_forward"; left = $Speed; right = 0.0; duration_s = $PulseSeconds },
    @{ label = "right_forward"; left = 0.0; right = $Speed; duration_s = $PulseSeconds },
    @{ label = "both_forward"; left = $Speed; right = $Speed; duration_s = ($PulseSeconds + 0.1) }
)

foreach ($step in $steps) {
    $payload = @{
        source = "lifted_wheel_test:$($step.label)"
        left = [double]$step.left
        right = [double]$step.right
        duration_s = [double]$step.duration_s
    } | ConvertTo-Json
    $response = Invoke-RestMethod -Method Post -Uri "$baseUri/motors" -Body $payload -ContentType "application/json" -TimeoutSec 3
    $responses.Add($response)
    Start-Sleep -Milliseconds ([int](([double]$step.duration_s + 0.35) * 1000))
    Invoke-RestMethod -Method Post -Uri "$baseUri/stop" -Body "{}" -ContentType "application/json" -TimeoutSec 3 | Out-Null
    Start-Sleep -Milliseconds 250
}

$finalStop = Invoke-RestMethod -Method Post -Uri "$baseUri/stop" -Body "{}" -ContentType "application/json" -TimeoutSec 3
$summary = [ordered]@{
    generated_utc = (Get-Date).ToUniversalTime().ToString("o")
    type = "factory_bridge_lifted_wheel_test"
    robot_host = $RobotHost
    port = $Port
    speed = $Speed
    pulse_seconds = $PulseSeconds
    pre_delay_seconds = $PreDelaySeconds
    confirm_held_in_air = [bool]$ConfirmHeldInAir
    steps = $steps
    responses = @($responses)
    final_stop = $finalStop
}

$summaryPath = Join-Path $artifactRoot "summary.json"
$summary | ConvertTo-Json -Depth 10 | Set-Content -Path $summaryPath -Encoding UTF8
Write-Host "FACTORY_BRIDGE_LIFTED_WHEEL_SUMMARY=$summaryPath"
$summary | ConvertTo-Json -Depth 5
