$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$fixture = Join-Path $projectRoot ('scratch/restore_points/restore_test_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
$testRoot = Join-Path $fixture 'workspace'
$checkpoint = Join-Path $fixture 'checkpoint'
New-Item -ItemType Directory -Path $testRoot,(Join-Path $checkpoint 'source') | Out-Null
# Generated disposable text fixtures, never production app source.
$old = Join-Path $checkpoint 'source/stable.txt'
$target = Join-Path $testRoot 'stable.txt'
$added = Join-Path $testRoot 'new.txt'
'stable baseline' | Set-Content -LiteralPath $old -Encoding utf8
'optimized version' | Set-Content -LiteralPath $target -Encoding utf8
'new feature' | Set-Content -LiteralPath $added -Encoding utf8
$before = (Get-FileHash -LiteralPath $old -Algorithm SHA256).Hash
$after = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
$addedHash = (Get-FileHash -LiteralPath $added -Algorithm SHA256).Hash
@{workspace=$testRoot} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $checkpoint 'manifest.json') -Encoding utf8
@{files=@(
    @{path='stable.txt'; beforeHash=$before; afterHash=$after},
    @{path='new.txt'; beforeHash=$null; afterHash=$addedHash}
)} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $checkpoint 'live-speed-changes.json') -Encoding utf8
$restore = Join-Path $PSScriptRoot 'restore_live_speed.ps1'
$dry = (& $restore -Checkpoint $checkpoint) | ConvertFrom-Json
if (-not $dry.ready -or $dry.fileCount -ne 2) { throw 'Dry run failed' }
if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $after) { throw 'Dry run wrote a file' }

# Later edits must block the entire restore, including otherwise-safe files.
'later user change' | Set-Content -LiteralPath $added -Encoding utf8
$blocked = $false
try { & $restore -Checkpoint $checkpoint -Apply | Out-Null }
catch { if ($_.Exception.Message -match 'later edits') { $blocked=$true } else { throw } }
if (-not $blocked) { throw 'Conflict was not blocked' }
if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $after) { throw 'Partial restore on conflict' }
'new feature' | Set-Content -LiteralPath $added -Encoding utf8
$result = (& $restore -Checkpoint $checkpoint -Apply) | ConvertFrom-Json
if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $before) { throw 'Stable file not restored' }
if (Test-Path -LiteralPath $added) { throw 'New file not quarantined' }
if ((Get-FileHash -LiteralPath (Join-Path $result.recovery 'new.txt') -Algorithm SHA256).Hash -ne $addedHash) { throw 'New file not recoverable' }
if ((Get-FileHash -LiteralPath (Join-Path $result.recovery 'stable.txt') -Algorithm SHA256).Hash -ne $after) { throw 'Replaced file not recoverable' }
$again = (& $restore -Checkpoint $checkpoint) | ConvertFrom-Json
if ($again.fileCount -ne 0) { throw 'Restore not idempotent' }
Write-Output 'PASS: dry run, all-file conflict guard, exact restore, recoverable quarantine, idempotence.'
Write-Output "Disposable test artifacts retained at $fixture"
