param(
    [string]$ExpectedDistro = "Ubuntu-22.04"
)

$ErrorActionPreference = "Continue"

Write-Host "Chasecar Windows Reinstall Preflight" -ForegroundColor Cyan
Write-Host "Repo: $((Resolve-Path "$PSScriptRoot\..").Path)"
Write-Host ""

Write-Host "[1/4] Git status" -ForegroundColor Yellow
git -C "$PSScriptRoot\.." status --short --branch
Write-Host ""

Write-Host "[2/4] WSL command health (read-only)" -ForegroundColor Yellow
$wslStatus = wsl --status 2>&1
if ($LASTEXITCODE -eq 0) {
    $wslStatus
}
else {
    Write-Host "wsl --status failed:" -ForegroundColor Red
    $wslStatus
}
Write-Host ""

Write-Host "[3/4] Critical repo files" -ForegroundColor Yellow
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

Write-Host "[4/4] Suggested next commands (manual)" -ForegroundColor Yellow
Write-Host "1) In an elevated PowerShell (if WSL is broken):"
Write-Host "   wsl --install --no-distribution"
Write-Host "2) Install distro (if missing):"
Write-Host "   wsl --install -d $ExpectedDistro"
Write-Host "3) Sync follower files:"
Write-Host "   .\sync_direct_follower_files.ps1 -Distro $ExpectedDistro"
Write-Host "4) Run Gazebo starter from WSL:"
Write-Host "   bash start_chasecar_gazebo.sh"
