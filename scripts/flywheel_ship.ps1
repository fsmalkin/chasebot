# Flywheel stage 2: train -> gate -> install -> export -> engine build on robot -> smoke.
# Run AFTER the owner audits the label montage from flywheel_prepare.py ("ship it").
# Stops the :8791 dashboard during training (GPU commit limit) and restarts it.
param(
    [int]$Epochs = 60,
    [string]$RobotHost = "192.168.1.11",
    [string]$RobotUser = "jetson"
)

$ErrorActionPreference = "Stop"
$repo = "D:\dev\chasebot-hw-v0"
$ft = Join-Path $repo "tools\robot_factory_bridge\finetune"
$stamp = Get-Date -Format "yyyyMMddTHHmmss"
$work = Join-Path $repo "artifacts\finetune_dataset\train_$stamp"

# every clean labeled set ever produced (poisoned sets carry a _POISONED suffix)
$labeled = Get-ChildItem (Join-Path $repo "artifacts\finetune_dataset") -Directory |
    Where-Object { $_.Name -match '^(labeled_zeroshot|labeled_hardwood|labeled_inbox|labeled_boot)' -and $_.Name -notmatch 'POISONED' } |
    ForEach-Object { $_.FullName }
if (-not $labeled) { throw "no labeled datasets found" }
Write-Output "training on: $($labeled -join ', ')"

$dash = (Get-NetTCPConnection -LocalPort 8791 -State Listen -ErrorAction SilentlyContinue).OwningProcess
if ($dash) { Stop-Process -Id $dash -Force -Confirm:$false; Write-Output "dashboard stopped for training" }

try {
    Set-Location (Join-Path $repo "runtime\yolo")
    python (Join-Path $ft "train_ball.py") --labeled @labeled --work $work --epochs $Epochs --workers 2
    if ($LASTEXITCODE -ne 0) { throw "training failed" }
    $best = Join-Path $work "runs\ball\weights\best.pt"

    python (Join-Path $ft "acceptance_gate.py") --model $best
    if ($LASTEXITCODE -ne 0) { throw "GATE FAILED - candidate NOT deployed (see anchors/false_positives above)" }

    Copy-Item $best (Join-Path $repo "runtime\yolo\golfball_finetune.pt") -Force
    python -c "from ultralytics import YOLO; YOLO(r'$repo\runtime\yolo\golfball_finetune.pt').export(format='onnx', opset=11, imgsz=640, simplify=True)"
    if ($LASTEXITCODE -ne 0) { throw "onnx export failed" }
}
finally {
    Set-Location $repo
    Start-Process -WindowStyle Hidden -FilePath python -ArgumentList "tools\robot_factory_bridge\chasecar_bridge_control_server.py" -WorkingDirectory $repo -RedirectStandardOutput artifacts\control_server_stdout.log -RedirectStandardError artifacts\control_server_stderr.log
    Write-Output "dashboard restarted"
}

scp -o BatchMode=yes -o ConnectTimeout=15 (Join-Path $repo "runtime\yolo\golfball_finetune.onnx") "${RobotUser}@${RobotHost}:/home/jetson/chasecar_onboard/golfball_candidate.onnx"
ssh -o BatchMode=yes -o ConnectTimeout=15 "${RobotUser}@${RobotHost}" "cp -f /home/jetson/chasecar_onboard/golfball_finetune_fp16.engine /home/jetson/chasecar_onboard/golfball_prev.engine.bak 2>/dev/null; nohup /usr/src/tensorrt/bin/trtexec --onnx=/home/jetson/chasecar_onboard/golfball_candidate.onnx --fp16 --saveEngine=/home/jetson/chasecar_onboard/golfball_finetune_fp16.engine --workspace=1024 > /home/jetson/chasecar_onboard/trt_build.log 2>&1 &"
Write-Output "engine build launched on robot (~15-25 min); polling..."

$deadline = (Get-Date).AddMinutes(40)
while ((Get-Date) -lt $deadline) {
    Start-Sleep 30
    $v = ssh -o BatchMode=yes -o ConnectTimeout=10 "${RobotUser}@${RobotHost}" "grep -c '&&&& PASSED' /home/jetson/chasecar_onboard/trt_build.log 2>/dev/null; grep -c '&&&& FAILED' /home/jetson/chasecar_onboard/trt_build.log 2>/dev/null"
    if ($v -and $v[0] -ge 1) { Write-Output "ENGINE BUILD PASSED"; break }
    if ($v -and $v.Count -ge 2 -and $v[1] -ge 1) { throw "engine build FAILED on robot (see trt_build.log); previous engine restored from .bak" }
}

ssh -o BatchMode=yes -o ConnectTimeout=15 "${RobotUser}@${RobotHost}" "python3 /home/jetson/chasecar_onboard/chasecar_onboard_fetch.py --detector trt --dry-run --dry-run-frames 3 2>&1 | tail -1"
Write-Output "FLYWHEEL SHIP COMPLETE: new model live on robot + dashboard. GO when ready."
