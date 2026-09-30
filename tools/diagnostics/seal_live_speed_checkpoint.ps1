param([string]$Checkpoint = 'D:\chamtrac nghien v2\scratch\restore_points\before_live_speed_20260912_234959')
$ErrorActionPreference = 'Stop'
$checkpointRoot = (Resolve-Path -LiteralPath $Checkpoint).Path
$baseline = Get-Content -LiteralPath (Join-Path $checkpointRoot 'manifest.json') -Raw | ConvertFrom-Json
$allowlist = @(
    'gradeflow_app/lib/screens/live_camera_screen.dart',
    'gradeflow_app/lib/screens/scan_screen.dart',
    'gradeflow_app/lib/services/live_speed/capture_engine.dart',
    'gradeflow_app/lib/services/live_speed/engine_preference.dart',
    'gradeflow_app/lib/services/live_speed/native_still_detector.dart',
    'gradeflow_app/lib/services/live_speed/native_still_detector_stub.dart',
    'gradeflow_app/test/live_speed_test.dart',
    'gradeflow_app/tool/live_speed_fallback_test.dart'
)
$manifestPath = Join-Path $checkpointRoot 'live-speed-changes.json'
if (Test-Path -LiteralPath $manifestPath) { throw 'Already sealed. Review later changes before creating a new seal.' }
$files = foreach ($relative in $allowlist) {
    $original = $baseline.sourceFiles | Where-Object path -EQ $relative
    [pscustomobject]@{
        path=$relative
        beforeHash=if ($original.existed) { $original.sha256 } else { $null }
        afterHash=(Get-FileHash -LiteralPath (Join-Path $baseline.workspace $relative) -Algorithm SHA256).Hash
    }
}
[ordered]@{created=(Get-Date -Format o); files=@($files)} | ConvertTo-Json -Depth 5 |
    Set-Content -LiteralPath $manifestPath -Encoding utf8
Write-Output "Sealed $($files.Count) app/test files. Diagnostics/docs intentionally remain available after rollback."
