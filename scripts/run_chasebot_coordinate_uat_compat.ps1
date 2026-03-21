param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ArgsList
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "[compat] chasebot coordinate UAT entrypoint is deprecated; forwarding to chasecar." -ForegroundColor Yellow
$target = Join-Path $PSScriptRoot "run_chasecar_coordinate_uat.ps1"
& $target @ArgsList
