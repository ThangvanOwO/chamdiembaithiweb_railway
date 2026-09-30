param([string]$Workspace = 'D:\chamtrac nghien v2')
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath $Workspace).Path
$checkpoint = Join-Path $projectRoot ('scratch/restore_points/before_live_speed_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Path $checkpoint | Out-Null
# Save tracked files (including dirty versions) and untracked source/config/tests.
# Do not copy generated caches, other cloned apps, datasets or the backup itself.
$paths = @(& git -C $projectRoot -c core.quotePath=false ls-files --cached)
$extra = @(& git -C $projectRoot -c core.quotePath=false ls-files --others --exclude-standard)
$paths += $extra | Where-Object {
    $_ -notmatch '^(scratch|duan_clone|apk_thamkhao|anh_san_pham)/' -and
    $_ -match '\.(dart|py|ps1|bat|md|json|yaml|yml|toml|txt|xml|gradle|kts|properties|html|css|js|cpp|h|cmake|lock)$'
}
$manifest = foreach ($relative in ($paths | Sort-Object -Unique)) {
    $source = Join-Path $projectRoot $relative
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        [pscustomobject]@{path=$relative; existed=$false; sha256=$null}
        continue
    }
    $destination = Join-Path $checkpoint ('source/' + $relative)
    New-Item -ItemType Directory -Force -Path (Split-Path $destination) | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination
    $hash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
    if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -ne $hash) { throw "Backup mismatch: $relative" }
    [pscustomobject]@{path=$relative; existed=$true; sha256=$hash}
}
$apkRelative = 'gradeflow_app/build/app/outputs/flutter-apk/gradeflow-academic-ui-v1-2008-arm64.apk'
$apkSource = Join-Path $projectRoot $apkRelative
if (-not (Test-Path -LiteralPath $apkSource)) { throw 'Stable APK not found' }
$apkBackup = Join-Path $checkpoint 'stable-2008-arm64.apk'
Copy-Item -LiteralPath $apkSource -Destination $apkBackup
$apkHash = (Get-FileHash -LiteralPath $apkSource -Algorithm SHA256).Hash
if ((Get-FileHash -LiteralPath $apkBackup -Algorithm SHA256).Hash -ne $apkHash) { throw 'APK backup mismatch' }
$state = [ordered]@{
    created=(Get-Date -Format o); workspace=$projectRoot
    gitHead=(& git -C $projectRoot rev-parse HEAD)
    gitStatus=@(& git -C $projectRoot -c core.quotePath=false status --short)
    sourceFiles=@($manifest); apk=@{path='stable-2008-arm64.apk'; sha256=$apkHash}
    note='Source checkpoint, not a database/media backup. Restore only the live-speed changed-file allowlist; preserve later unrelated edits.'
}
$state | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $checkpoint 'manifest.json') -Encoding utf8
[pscustomobject]@{checkpoint=$checkpoint; sourceEntries=$manifest.Count; apkSha256=$apkHash} | ConvertTo-Json
