param(
    [ValidateSet("up", "down", "logs", "ps")]
    [string]$Action = "up",
    [string]$ProjectName = "",
    [switch]$Build,
    [switch]$NoDetach,
    [string]$RuntimeTarget = "robot_fidelity_orin",
    [string]$InferenceBackend = "tensorrt_int8",
    [string]$CoreRosDistro = "kilted",
    [ValidateSet("compat", "balanced", "max")]
    [string]$GatePerfProfile = "compat",
    [ValidateSet("auto", "cuda:0", "cpu")]
    [string]$InferenceDevice = "cuda:0",
    [string]$WorldFile = "",
    [object]$IncludeNav2Bringup = $null,
    [object]$IncludeBridge = $null,
    [object]$IncludeCmdVelRelay = $null
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-NullableBool {
    param(
        [object]$Value,
        [string]$ParamName
    )
    if ($null -eq $Value) { return $null }
    if ($Value -is [bool]) { return [bool]$Value }
    if ($Value -is [int] -or $Value -is [long]) {
        if ([int]$Value -eq 0) { return $false }
        if ([int]$Value -eq 1) { return $true }
    }
    $text = $Value.ToString().Trim().ToLowerInvariant()
    switch ($text) {
        "true" { return $true }
        "false" { return $false }
        "1" { return $true }
        "0" { return $false }
        "yes" { return $true }
        "no" { return $false }
        default { throw "Invalid boolean value '$Value' for parameter '$ParamName'." }
    }
}

$scriptPath = Join-Path $PSScriptRoot "run_compose_profile.ps1"
$originalNav2 = $null
$originalBridge = $null
$originalRelay = $null
$originalPerfProfile = $env:GATE_PERF_PROFILE
$originalInferenceDevice = $env:GATE_INFERENCE_DEVICE
$originalWorldFile = $env:WORLD_FILE
$env:GATE_PERF_PROFILE = $GatePerfProfile
$env:GATE_INFERENCE_DEVICE = $InferenceDevice
if (-not [string]::IsNullOrWhiteSpace($WorldFile)) {
    $env:WORLD_FILE = $WorldFile
}
if ($PSBoundParameters.ContainsKey("IncludeNav2Bringup")) {
    $resolved = Resolve-NullableBool -Value $IncludeNav2Bringup -ParamName "IncludeNav2Bringup"
    $originalNav2 = $env:GATE_INCLUDE_NAV2_BRINGUP
    $env:GATE_INCLUDE_NAV2_BRINGUP = ($(if ($resolved) { "true" } else { "false" }))
}
if ($PSBoundParameters.ContainsKey("IncludeBridge")) {
    $resolved = Resolve-NullableBool -Value $IncludeBridge -ParamName "IncludeBridge"
    $originalBridge = $env:GATE_INCLUDE_BRIDGE
    $env:GATE_INCLUDE_BRIDGE = ($(if ($resolved) { "true" } else { "false" }))
}
if ($PSBoundParameters.ContainsKey("IncludeCmdVelRelay")) {
    $resolved = Resolve-NullableBool -Value $IncludeCmdVelRelay -ParamName "IncludeCmdVelRelay"
    $originalRelay = $env:GATE_INCLUDE_CMD_VEL_RELAY
    $env:GATE_INCLUDE_CMD_VEL_RELAY = ($(if ($resolved) { "true" } else { "false" }))
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
    if ($null -eq $originalPerfProfile) {
        Remove-Item Env:\GATE_PERF_PROFILE -ErrorAction SilentlyContinue
    }
    else {
        $env:GATE_PERF_PROFILE = $originalPerfProfile
    }
    if ($null -eq $originalInferenceDevice) {
        Remove-Item Env:\GATE_INFERENCE_DEVICE -ErrorAction SilentlyContinue
    }
    else {
        $env:GATE_INFERENCE_DEVICE = $originalInferenceDevice
    }
    if (-not [string]::IsNullOrWhiteSpace($WorldFile)) {
        if ($null -eq $originalWorldFile) {
            Remove-Item Env:\WORLD_FILE -ErrorAction SilentlyContinue
        }
        else {
            $env:WORLD_FILE = $originalWorldFile
        }
    }
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
