param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ArgsList
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "[compat] chasebot entrypoint is deprecated; forwarding to chasecar canonical stack." -ForegroundColor Yellow
$target = Join-Path $PSScriptRoot "run_chasecar_stack.ps1"
& $target @ArgsList
