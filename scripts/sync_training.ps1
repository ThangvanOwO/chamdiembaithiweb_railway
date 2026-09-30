# Windows PowerShell 5.1 and PowerShell 7. No passwords/tokens in this script.
[CmdletBinding()]
param(
    [string]$VpsIp = '52.220.123.56',
    [string]$Key = "$env:USERPROFILE\.ssh\LightsailDefaultKey-ap-southeast-1.pem",
    [string]$OutputDirectory = (Join-Path (Split-Path $PSScriptRoot -Parent) 'Traing')
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Key -PathType Leaf)) { throw "SSH key not found: $Key" }
if ($VpsIp -notmatch '^[a-zA-Z0-9.-]+$') { throw 'Invalid VPS host.' }
$outputRoot = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$zip = Join-Path $outputRoot "reviewed_$stamp.zip"
& ssh -i $Key -o BatchMode=yes "ubuntu@$VpsIp" 'cd /home/ubuntu/gradeflow && mkdir -p scratch/training_sync && docker compose --env-file .env.vps -f docker-compose.vps.yml exec -T web python manage.py export_training_dataset --output /app/media/training_exports/reviewed.zip && docker compose --env-file .env.vps -f docker-compose.vps.yml cp web:/app/media/training_exports/reviewed.zip /home/ubuntu/gradeflow/scratch/training_sync/reviewed.zip && chmod 600 /home/ubuntu/gradeflow/scratch/training_sync/reviewed.zip'
if ($LASTEXITCODE -ne 0) { throw 'VPS export failed; no data was replaced locally.' }
& scp -i $Key -o BatchMode=yes "ubuntu@${VpsIp}:/home/ubuntu/gradeflow/scratch/training_sync/reviewed.zip" $zip
if ($LASTEXITCODE -ne 0) { throw 'Download failed.' }
# Keep versioned snapshots; never delete a previous dataset.
$snapshot = Join-Path $outputRoot "reviewed_$stamp"
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($zip)
try {
    foreach ($entry in $archive.Entries) {
        $destination = [IO.Path]::GetFullPath((Join-Path $snapshot $entry.FullName))
        if (-not $destination.StartsWith($snapshot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Unsafe path in dataset archive.'
        }
    }
} finally { $archive.Dispose() }
[IO.Compression.ZipFile]::ExtractToDirectory($zip, $snapshot)
$manifest = Get-Content -LiteralPath (Join-Path $snapshot 'manifest.json') -Raw | ConvertFrom-Json
$count = @($manifest.samples).Count
Set-Content -LiteralPath (Join-Path $outputRoot 'LATEST.txt') -Value $snapshot -Encoding UTF8
Write-Host "Downloaded $count reviewed question samples to $snapshot"
