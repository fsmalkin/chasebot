param(
    [int]$Port = 8860,
    [string]$BindHost = "127.0.0.1"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    $env:CHASECAR_DASHBOARD_CONTROL_MODE = "host_powershell"
    python scripts/dashboard_service.py --host $BindHost --port $Port
}
finally {
    Pop-Location
}
