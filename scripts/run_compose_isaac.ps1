param(
    [ValidateSet("up", "down", "logs", "ps")]
    [string]$Action = "up",
    [string]$ProjectName = "",
    [switch]$Build,
    [switch]$NoDetach,
    [string]$RuntimeTarget = "workstation_balanced",
    [string]$InferenceBackend = "tensorrt_int8",
    [string]$CoreRosDistro = "kilted",
    [string]$BridgeRosDistro = "jazzy"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "run_compose_profile.ps1"

& $scriptPath `
    -Profile "isaac" `
    -Action $Action `
    -ProjectName $ProjectName `
    -Build:$Build `
    -NoDetach:$NoDetach `
    -RuntimeTarget $RuntimeTarget `
    -SimLane "isaac_fidelity" `
    -InferenceBackend $InferenceBackend `
    -CoreRosDistro $CoreRosDistro `
    -BridgeRosDistro $BridgeRosDistro
