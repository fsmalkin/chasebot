param(
    [ValidateSet("run", "up", "down", "logs", "ps")]
    [string]$Action = "run",
    [string]$ProjectName = "",
    [switch]$Build,
    [switch]$NoDetach,
    [string]$RuntimeTarget = "robot_fidelity_orin",
    [string]$SimLane = "jetty_gate",
    [string]$InferenceBackend = "tensorrt_int8",
    [string]$CoreRosDistro = "kilted"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "run_compose_profile.ps1"

& $scriptPath `
    -Profile "uat" `
    -Action $Action `
    -ProjectName $ProjectName `
    -Build:$Build `
    -NoDetach:$NoDetach `
    -RuntimeTarget $RuntimeTarget `
    -SimLane $SimLane `
    -InferenceBackend $InferenceBackend `
    -CoreRosDistro $CoreRosDistro `
    -BridgeRosDistro "jazzy" `
    -ComposeService "uat-orchestrator"
