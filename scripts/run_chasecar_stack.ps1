param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ArgsList
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$target = Join-Path $PSScriptRoot "run_canonical_stack.ps1"
Write-Host "Launching chasecar canonical stack entrypoint..." -ForegroundColor Cyan
& $target @ArgsList
