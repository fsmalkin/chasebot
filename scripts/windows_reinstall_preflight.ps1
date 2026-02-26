param(
    [string]$ExpectedDistro = "Ubuntu-24.04",
    [string]$ExpectedRosDistro = "auto"
)

$ErrorActionPreference = "Continue"

Write-Host "Chasecar Windows Reinstall Preflight" -ForegroundColor Cyan
Write-Host "Repo: $((Resolve-Path "$PSScriptRoot\..").Path)"
Write-Host ""

Write-Host "[1/5] Git status" -ForegroundColor Yellow
git -C "$PSScriptRoot\.." status --short --branch
Write-Host ""

Write-Host "[2/5] WSL command health (read-only)" -ForegroundColor Yellow
$wslStatus = wsl --status 2>&1
if ($LASTEXITCODE -eq 0) {
    $wslStatus
}
else {
    Write-Host "wsl --status failed:" -ForegroundColor Red
    $wslStatus
}
Write-Host ""

Write-Host "[3/5] ROS toolchain quick check (read-only)" -ForegroundColor Yellow
$expectedSetup = ""
if ($ExpectedRosDistro -and $ExpectedRosDistro -ne "auto") {
    $expectedSetup = "/opt/ros/$ExpectedRosDistro/setup.bash"
}
$rosCheckParts = @(
    "if [ -f '$expectedSetup' ]; then source '$expectedSetup'; elif [ -f /opt/ros/jazzy/setup.bash ]; then source /opt/ros/jazzy/setup.bash; elif [ -f /opt/ros/humble/setup.bash ]; then source /opt/ros/humble/setup.bash; fi; if command -v ros2 >/dev/null 2>&1; then echo '[OK] ros2 found'; ros2 --help >/dev/null 2>&1 && echo '[OK] ros2 executable healthy'; else echo '[MISSING] ros2 not found'; fi",
    "if [ -d /opt/ros ]; then echo '[OK] /opt/ros exists'; ls /opt/ros; else echo '[MISSING] /opt/ros not found'; fi",
    "if [ -f /opt/ros/jazzy/setup.bash ]; then echo '[OK] jazzy setup found'; elif [ -f /opt/ros/humble/setup.bash ]; then echo '[OK] humble setup found'; else echo '[MISSING] neither jazzy nor humble setup found'; fi"
)
if (-not [string]::IsNullOrWhiteSpace($expectedSetup)) {
    $rosCheckParts += "if [ -f '$expectedSetup' ]; then echo '[OK] explicit setup path exists: $expectedSetup'; else echo '[MISSING] explicit setup path missing: $expectedSetup'; fi"
}
$rosCheckCmd = ($rosCheckParts -join "; ")
$rosCheck = wsl -d $ExpectedDistro -- bash -lc $rosCheckCmd 2>&1
$rosCheck
Write-Host ""

Write-Host "[4/5] Critical repo files" -ForegroundColor Yellow
$critical = @(
    "CMakeLists.txt",
    "ros2_config/launch/jetbot_yolo_nav2_complete.launch.py",
    "ros2_scripts/sync_manager.py",
    "sync_direct_follower_files.ps1",
    "start_chasecar_gazebo.sh"
)
foreach ($file in $critical) {
    if (Test-Path (Join-Path "$PSScriptRoot\.." $file)) {
        Write-Host "[OK] $file"
    }
    else {
        Write-Host "[MISSING] $file" -ForegroundColor Red
    }
}
Write-Host ""

Write-Host "[5/5] Suggested next commands (manual)" -ForegroundColor Yellow
Write-Host "1) In an elevated PowerShell (if WSL is broken):"
Write-Host "   wsl --install --no-distribution"
Write-Host "2) Install distro (if missing):"
Write-Host "   wsl --install -d $ExpectedDistro"
Write-Host "3) Sync follower files:"
Write-Host "   .\sync_direct_follower_files.ps1 -Distro $ExpectedDistro"
Write-Host "4) Run Gazebo starter from WSL:"
Write-Host "   bash start_chasecar_gazebo.sh"
