param(
    [ValidateSet("manifest", "export", "build", "all")]
    [string]$Mode = "all",

    [string]$ModelPath = "yolov8m.pt",
    [string]$OnnxPath = "runtime/tensorrt/onnx/ball_detector.onnx",
    [string]$ConfigPath = "runtime/tensorrt/calibration/calibration_config.yaml",
    [string]$CalibrationImages = "runtime/tensorrt/calibration/images",
    [string]$ManifestPath = "runtime/tensorrt/calibration/calibration_manifest.json"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    if ($Mode -in @("manifest", "all")) {
        python scripts/generate_int8_calibration_manifest.py --images $CalibrationImages --output $ManifestPath
    }

    if ($Mode -in @("export", "all")) {
        python scripts/export_yolo_onnx.py --model $ModelPath --output $OnnxPath
    }

    if ($Mode -in @("build", "all")) {
        python scripts/build_tensorrt_engine.py --config $ConfigPath --onnx $OnnxPath
    }
}
finally {
    Pop-Location
}
