param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ArgsList
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$target = Join-Path $PSScriptRoot "run_coordinate_uat.ps1"
Write-Host "Launching chasecar coordinate UAT entrypoint..." -ForegroundColor Cyan
& $target @ArgsList
