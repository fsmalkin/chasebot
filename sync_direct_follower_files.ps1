param(
    [string]$Distro = "Ubuntu-22.04",
    [string]$WorkspaceRoot = "~/ros2_ws/src"
)

$ErrorActionPreference = "Stop"

function Convert-ToWslPath {
    param([string]$WindowsPath)

    $normalized = $WindowsPath -replace "\\", "/"
    if ($normalized -match "^([A-Za-z]):/(.*)$") {
        $drive = $matches[1].ToLowerInvariant()
        $rest = $matches[2]
        return "/mnt/$drive/$rest"
    }

    return $normalized
}

function Invoke-Wsl {
    param(
        [string]$DistroName,
        [string]$Command
    )
    wsl -d $DistroName -- bash -lc $Command
}

function Resolve-TargetPackagePath {
    param(
        [string]$DistroName,
        [string]$Workspace
    )

    $detectCmd = @"
if [ -d $Workspace/chasecar ]; then
  echo $Workspace/chasecar
elif [ -d $Workspace/chasebot_description ]; then
  echo $Workspace/chasebot_description
else
  echo $Workspace/chasecar
fi
"@

    return (Invoke-Wsl -DistroName $DistroName -Command $detectCmd).Trim()
}

Write-Host "Syncing direct follower files to WSL..." -ForegroundColor Green

$repoRoot = (Resolve-Path -Path $PSScriptRoot).Path
$repoRootWsl = Convert-ToWslPath -WindowsPath $repoRoot
$targetPackage = Resolve-TargetPackagePath -DistroName $Distro -Workspace $WorkspaceRoot
$targetScripts = "$targetPackage/ros2_scripts"

Write-Host "Repo root (Windows): $repoRoot"
Write-Host "Repo root (WSL): $repoRootWsl"
Write-Host "Target package path: $targetPackage"

Invoke-Wsl -DistroName $Distro -Command "mkdir -p '$targetScripts'"

$files = @(
    "ros2_scripts/yolo_3d_direct_follower.py",
    "ros2_scripts/test_direct_follower.py",
    "ros2_scripts/test_nav2_lifecycle_debug.py",
    "ros2_scripts/test_nav2_minimal_individual.py"
)

foreach ($relativeFile in $files) {
    $source = "$repoRootWsl/$relativeFile"
    $fileName = [System.IO.Path]::GetFileName($relativeFile)
    $destination = "$targetScripts/$fileName"

    Write-Host "Copying $relativeFile ..."
    Invoke-Wsl -DistroName $Distro -Command "cp '$source' '$destination'"
    Invoke-Wsl -DistroName $Distro -Command "chmod +x '$destination'"
}

Write-Host "`nVerifying copied files..." -ForegroundColor Yellow
Invoke-Wsl -DistroName $Distro -Command "ls -la '$targetScripts' | grep -E '(direct_follower|nav2_lifecycle|nav2_minimal)'"

Write-Host "`nSync complete." -ForegroundColor Green
Write-Host "Next step: run test_direct_follower.py from your WSL workspace package path." -ForegroundColor Cyan
