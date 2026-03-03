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
    [ValidateSet("auto", "vcxsrv", "wslg", "none")]
    [string]$DisplayMode = "auto",
    [string]$DisplayAddress = "",
    [string]$QtQpaPlatform = "xcb",
    [string]$QtX11NoMitShm = "1",
    [string]$LibglAlwaysIndirect = "1",
    [object]$Headless = $null,
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
$originalHeadless = $env:GATE_HEADLESS
$originalWorldFile = $env:WORLD_FILE
$originalDisplayMode = $env:GATE_DISPLAY_MODE
$originalDisplay = $env:GATE_DISPLAY
$originalQtQpaPlatform = $env:GATE_QPA_PLATFORM
$originalQtX11NoMitShm = $env:GATE_QT_X11_NO_MITSHM
$originalLibglAlwaysIndirect = $env:GATE_LIBGL_ALWAYS_INDIRECT
$env:GATE_PERF_PROFILE = $GatePerfProfile
$env:GATE_INFERENCE_DEVICE = $InferenceDevice
if ($PSBoundParameters.ContainsKey("DisplayMode")) {
    $env:GATE_DISPLAY_MODE = $DisplayMode
}
if ($PSBoundParameters.ContainsKey("DisplayAddress")) {
    if ([string]::IsNullOrWhiteSpace($DisplayAddress)) {
        Remove-Item Env:\GATE_DISPLAY -ErrorAction SilentlyContinue
    }
    else {
        $env:GATE_DISPLAY = $DisplayAddress
    }
}
if ($PSBoundParameters.ContainsKey("QtQpaPlatform")) {
    if ([string]::IsNullOrWhiteSpace($QtQpaPlatform)) {
        Remove-Item Env:\GATE_QPA_PLATFORM -ErrorAction SilentlyContinue
    }
    else {
        $env:GATE_QPA_PLATFORM = $QtQpaPlatform
    }
}
if ($PSBoundParameters.ContainsKey("QtX11NoMitShm")) {
    if ([string]::IsNullOrWhiteSpace($QtX11NoMitShm)) {
        Remove-Item Env:\GATE_QT_X11_NO_MITSHM -ErrorAction SilentlyContinue
    }
    else {
        $env:GATE_QT_X11_NO_MITSHM = $QtX11NoMitShm
    }
}
if ($PSBoundParameters.ContainsKey("LibglAlwaysIndirect")) {
    if ([string]::IsNullOrWhiteSpace($LibglAlwaysIndirect)) {
        Remove-Item Env:\GATE_LIBGL_ALWAYS_INDIRECT -ErrorAction SilentlyContinue
    }
    else {
        $env:GATE_LIBGL_ALWAYS_INDIRECT = $LibglAlwaysIndirect
    }
}
if ($PSBoundParameters.ContainsKey("Headless")) {
    $resolved = Resolve-NullableBool -Value $Headless -ParamName "Headless"
    if ($null -ne $resolved) {
        $env:GATE_HEADLESS = ($(if ($resolved) { "true" } else { "false" }))
    }
}
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
    if ($PSBoundParameters.ContainsKey("Headless")) {
        if ($null -eq $originalHeadless) {
            Remove-Item Env:\GATE_HEADLESS -ErrorAction SilentlyContinue
        }
        else {
            $env:GATE_HEADLESS = $originalHeadless
        }
    }
    if (-not [string]::IsNullOrWhiteSpace($WorldFile)) {
        if ($null -eq $originalWorldFile) {
            Remove-Item Env:\WORLD_FILE -ErrorAction SilentlyContinue
        }
        else {
            $env:WORLD_FILE = $originalWorldFile
        }
    }
    if ($PSBoundParameters.ContainsKey("DisplayMode")) {
        if ($null -eq $originalDisplayMode) {
            Remove-Item Env:\GATE_DISPLAY_MODE -ErrorAction SilentlyContinue
        }
        else {
            $env:GATE_DISPLAY_MODE = $originalDisplayMode
        }
    }
    if ($PSBoundParameters.ContainsKey("DisplayAddress")) {
        if ($null -eq $originalDisplay) {
            Remove-Item Env:\GATE_DISPLAY -ErrorAction SilentlyContinue
        }
        else {
            $env:GATE_DISPLAY = $originalDisplay
        }
    }
    if ($PSBoundParameters.ContainsKey("QtQpaPlatform")) {
        if ($null -eq $originalQtQpaPlatform) {
            Remove-Item Env:\GATE_QPA_PLATFORM -ErrorAction SilentlyContinue
        }
        else {
            $env:GATE_QPA_PLATFORM = $originalQtQpaPlatform
        }
    }
    if ($PSBoundParameters.ContainsKey("QtX11NoMitShm")) {
        if ($null -eq $originalQtX11NoMitShm) {
            Remove-Item Env:\GATE_QT_X11_NO_MITSHM -ErrorAction SilentlyContinue
        }
        else {
            $env:GATE_QT_X11_NO_MITSHM = $originalQtX11NoMitShm
        }
    }
    if ($PSBoundParameters.ContainsKey("LibglAlwaysIndirect")) {
        if ($null -eq $originalLibglAlwaysIndirect) {
            Remove-Item Env:\GATE_LIBGL_ALWAYS_INDIRECT -ErrorAction SilentlyContinue
        }
        else {
            $env:GATE_LIBGL_ALWAYS_INDIRECT = $originalLibglAlwaysIndirect
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
