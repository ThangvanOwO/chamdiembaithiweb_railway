param(
    [string]$Checkpoint = 'D:\chamtrac nghien v2\scratch\restore_points\before_live_speed_20260912_234959',
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
$checkpointRoot = (Resolve-Path -LiteralPath $Checkpoint).Path
$baseline = Get-Content -LiteralPath (Join-Path $checkpointRoot 'manifest.json') -Raw | ConvertFrom-Json
$changes = Get-Content -LiteralPath (Join-Path $checkpointRoot 'live-speed-changes.json') -Raw | ConvertFrom-Json
$projectRoot = (Resolve-Path -LiteralPath $baseline.workspace).Path

function Resolve-ContainedFile([string]$Root, [string]$Relative) {
    $resolved = [IO.Path]::GetFullPath((Join-Path $Root $Relative))
    if (-not $resolved.StartsWith($Root.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path outside expected directory: $Relative"
    }
    # Refuse junctions/symlinks anywhere on the target path.
    $ancestor = $resolved
    while ($ancestor.Length -gt $Root.Length) {
        if ((Test-Path -LiteralPath $ancestor) -and
            ((Get-Item -LiteralPath $ancestor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Reparse point requires manual review: $ancestor"
        }
        $ancestor = Split-Path $ancestor
    }
    return $resolved
}

# Preflight ALL files before any write. Later unrelated edits are never lost.
$operations = foreach ($entry in $changes.files) {
    $target = Resolve-ContainedFile $projectRoot $entry.path
    $exists = Test-Path -LiteralPath $target -PathType Leaf
    $currentHash = if ($exists) { (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash } else { $null }
    if (($entry.beforeHash -and $currentHash -eq $entry.beforeHash) -or
        (-not $entry.beforeHash -and -not $exists)) { continue }
    if ($currentHash -ne $entry.afterHash) {
        throw "STOP: later edits detected in $($entry.path). Review/merge only this optimization; do not overwrite."
    }
    $original = $null
    if ($entry.beforeHash) {
        $original = Resolve-ContainedFile $checkpointRoot ('source/' + $entry.path)
        if ((Get-FileHash -LiteralPath $original -Algorithm SHA256).Hash -ne $entry.beforeHash) {
            throw "Backup verification failed: $($entry.path)"
        }
    }
    [pscustomobject]@{path=$entry.path; target=$target; original=$original; beforeHash=$entry.beforeHash}
}

if (-not $Apply) {
    [pscustomobject]@{mode='VERIFY ONLY'; ready=$true; fileCount=@($operations).Count; files=@($operations.path)} | ConvertTo-Json -Depth 5
    return
}

# Recoverable per-file operations only, no recursive delete and no git reset.
$recovery = Join-Path $checkpointRoot ('replaced_by_restore_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
New-Item -ItemType Directory -Path $recovery | Out-Null
foreach ($operation in $operations) {
    $saved = Resolve-ContainedFile $recovery $operation.path
    New-Item -ItemType Directory -Force -Path (Split-Path $saved) | Out-Null
    if ($operation.original) {
        Copy-Item -LiteralPath $operation.target -Destination $saved
        Copy-Item -LiteralPath $operation.original -Destination $operation.target
        if ((Get-FileHash -LiteralPath $operation.target -Algorithm SHA256).Hash -ne $operation.beforeHash) {
            throw "Restore verification failed: $($operation.path). Recovery: $recovery"
        }
    } else {
        Move-Item -LiteralPath $operation.target -Destination $saved
    }
}
[pscustomobject]@{mode='RESTORED'; fileCount=@($operations).Count; recovery=$recovery} | ConvertTo-Json
