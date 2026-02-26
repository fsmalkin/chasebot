param(
    [string]$ExpectedDistro = "Ubuntu-24.04"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

Write-Host "Chasecar Docker Host Bootstrap Preflight" -ForegroundColor Cyan
Write-Host ""

function Check-Step {
    param(
        [string]$Label,
        [scriptblock]$Probe
    )
    Write-Host $Label -ForegroundColor Yellow
    try {
        & $Probe
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK]" -ForegroundColor Green
        }
        else {
            Write-Host "  [WARN] Exit code: $LASTEXITCODE" -ForegroundColor Red
        }
    }
    catch {
        Write-Host "  [WARN] $($_.Exception.Message)" -ForegroundColor Red
    }
    Write-Host ""
}

Check-Step -Label "[1/6] Docker CLI" -Probe {
    docker version
}

Check-Step -Label "[2/6] Docker Compose plugin" -Probe {
    docker compose version
}

Check-Step -Label "[3/6] Docker engine info" -Probe {
    docker info
}

Check-Step -Label "[4/6] GPU visibility (nvidia-smi)" -Probe {
    nvidia-smi
}

Check-Step -Label "[5/6] WSL health and distro list" -Probe {
    wsl --status
    wsl --list --verbose
}

Check-Step -Label "[6/6] NVIDIA runtime support in Docker" -Probe {
    docker info --format '{{json .Runtimes}}'
}

Write-Host "Recommended next steps:" -ForegroundColor Cyan
Write-Host "1) Copy compose/.env.example -> .env and set your local values."
Write-Host "2) Build gate lane: docker compose --profile gate build"
Write-Host "3) Build isaac bridge lane: docker compose --profile isaac build bridge-jazzy"
Write-Host "4) Bring up gate lane: scripts/run_compose_gate.ps1 -Action up -Build"
