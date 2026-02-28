param(
    [ValidateSet("up", "down", "logs", "ps")]
    [string]$Action = "up",
    [string]$ProjectName = "",
    [switch]$Build,
    [switch]$NoDetach,
    [string]$RuntimeTarget = "robot_fidelity_orin",
    [string]$InferenceBackend = "tensorrt_int8",
    [string]$CoreRosDistro = "kilted",
    [Nullable[bool]]$IncludeNav2Bringup = $null,
    [Nullable[bool]]$IncludeBridge = $null,
    [Nullable[bool]]$IncludeCmdVelRelay = $null
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "run_compose_profile.ps1"
$originalNav2 = $null
$originalBridge = $null
$originalRelay = $null
if ($PSBoundParameters.ContainsKey("IncludeNav2Bringup")) {
    $originalNav2 = $env:GATE_INCLUDE_NAV2_BRINGUP
    $env:GATE_INCLUDE_NAV2_BRINGUP = ($(if ([bool]$IncludeNav2Bringup) { "true" } else { "false" }))
}
if ($PSBoundParameters.ContainsKey("IncludeBridge")) {
    $originalBridge = $env:GATE_INCLUDE_BRIDGE
    $env:GATE_INCLUDE_BRIDGE = ($(if ([bool]$IncludeBridge) { "true" } else { "false" }))
}
if ($PSBoundParameters.ContainsKey("IncludeCmdVelRelay")) {
    $originalRelay = $env:GATE_INCLUDE_CMD_VEL_RELAY
    $env:GATE_INCLUDE_CMD_VEL_RELAY = ($(if ([bool]$IncludeCmdVelRelay) { "true" } else { "false" }))
}

try {
    & $scriptPath `
        -Profile "gate" `
        -Action $Action `
        -ProjectName $ProjectName `
        -Build:$Build `
        -NoDetach:$NoDetach `
        -RuntimeTarget $RuntimeTarget `
        -SimLane "jetty_gate" `
        -InferenceBackend $InferenceBackend `
        -CoreRosDistro $CoreRosDistro `
        -BridgeRosDistro "jazzy"
}
finally {
    if ($PSBoundParameters.ContainsKey("IncludeNav2Bringup")) {
        if ($null -eq $originalNav2) {
            Remove-Item Env:\GATE_INCLUDE_NAV2_BRINGUP -ErrorAction SilentlyContinue
        }
        else {
            $env:GATE_INCLUDE_NAV2_BRINGUP = $originalNav2
        }
    }
    if ($PSBoundParameters.ContainsKey("IncludeBridge")) {
        if ($null -eq $originalBridge) {
            Remove-Item Env:\GATE_INCLUDE_BRIDGE -ErrorAction SilentlyContinue
        }
        else {
            $env:GATE_INCLUDE_BRIDGE = $originalBridge
        }
    }
    if ($PSBoundParameters.ContainsKey("IncludeCmdVelRelay")) {
        if ($null -eq $originalRelay) {
            Remove-Item Env:\GATE_INCLUDE_CMD_VEL_RELAY -ErrorAction SilentlyContinue
        }
        else {
            $env:GATE_INCLUDE_CMD_VEL_RELAY = $originalRelay
        }
    }
}
