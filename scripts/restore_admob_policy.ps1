param([switch]$Apply)

$ErrorActionPreference = 'Stop'
$workspaceRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$workspacePrefix = $workspaceRoot.TrimEnd('\') + '\'
$backupRoot = Join-Path $workspaceRoot 'scratch\admob_policy_before_20261002_103523'
$manifestPath = Join-Path $backupRoot 'restore-files.json'
$files = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json

# Validate every target before copying any file. Never discard later edits.
foreach ($file in $files) {
    $target = [IO.Path]::GetFullPath((Join-Path $workspaceRoot $file.RelativePath))
    $source = [IO.Path]::GetFullPath((Join-Path $backupRoot $file.RelativePath))
    if (-not $target.StartsWith($workspacePrefix, [StringComparison]::OrdinalIgnoreCase) -or
        -not $source.StartsWith($backupRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path outside backup/workspace: $($file.RelativePath)"
    }
    if (-not (Test-Path -LiteralPath $source -PathType Leaf) -or
        (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $file.BeforeHash) {
        throw "Backup is missing or changed: $($file.RelativePath)"
    }
    if (-not (Test-Path -LiteralPath $target -PathType Leaf) -or
        (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $file.AfterHash) {
        throw "Later changes detected; inspect before restoring: $($file.RelativePath)"
    }
}

foreach ($file in $files) {
    if ($Apply) {
        Copy-Item -LiteralPath (Join-Path $backupRoot $file.RelativePath) -Destination (Join-Path $workspaceRoot $file.RelativePath) -Force
    }
    Write-Output "$($file.RelativePath)"
}
if ($Apply) {
    Write-Output 'Restored source files only. Rebuild local Docker/Android separately; VPS is unchanged.'
} else {
    Write-Output 'Preview only. Add -Apply to restore exactly these files; camera files are excluded.'
}
