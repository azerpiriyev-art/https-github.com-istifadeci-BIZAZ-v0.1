$ErrorActionPreference = "Stop"

$projectRoot = "C:\Projects\BIZAZ-v0.1"
$localBackupDir = Join-Path $projectRoot "backups"
$secondaryBackupDir = "D:\BIZAZ-Backups"

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupName = "bizaz-$timestamp.dump"
$checksumName = "bizaz-$timestamp.sha256"

$localBackup = Join-Path $localBackupDir $backupName
$localChecksum = Join-Path $localBackupDir $checksumName

$secondaryBackup = Join-Path $secondaryBackupDir $backupName
$secondaryChecksum = Join-Path $secondaryBackupDir $checksumName

New-Item -ItemType Directory -Force -Path $localBackupDir | Out-Null
New-Item -ItemType Directory -Force -Path $secondaryBackupDir | Out-Null

Write-Host "=== BIZAZ AUTOMATED BACKUP ==="
Write-Host "START:" (Get-Date)

$containerDump = "/tmp/$backupName"

Write-Host "1. PostgreSQL dump"

docker compose exec -T db `
    pg_dump `
    -U bizaz `
    -d bizaz `
    -Fc `
    -f $containerDump

if ($LASTEXITCODE -ne 0) {
    throw "pg_dump failed."
}

Write-Host "2. Copy backup from container"

docker cp "bizaz-postgres:$containerDump" $localBackup

if ($LASTEXITCODE -ne 0) {
    throw "docker cp failed."
}

Write-Host "3. Remove temporary container file"

docker compose exec -T db `
    rm -f $containerDump

Write-Host "4. Validate backup"

docker run `
    --rm `
    -v "${localBackupDir}:/backup" `
    postgres:16-alpine `
    pg_restore `
    --list `
    "/backup/$backupName" `
    > $null

if ($LASTEXITCODE -ne 0) {
    throw "Backup archive validation failed."
}

Write-Host "5. SHA256"

$hash = Get-FileHash $localBackup -Algorithm SHA256

"$($hash.Hash)  $backupName" |
    Set-Content $localChecksum -Encoding ASCII

Write-Host "SHA256:" $hash.Hash

Write-Host "6. Copy verified backup to secondary storage"

Copy-Item $localBackup $secondaryBackup -Force
Copy-Item $localChecksum $secondaryChecksum -Force

Write-Host "7. Verify secondary copy"

$secondaryHash = Get-FileHash $secondaryBackup -Algorithm SHA256

if ($secondaryHash.Hash -ne $hash.Hash) {
    throw "Secondary backup SHA256 mismatch."
}

Write-Host "SECONDARY_SHA256_MATCH: True"

Write-Host "8. Retention - remove backups older than 30 days"

$cutoff = (Get-Date).AddDays(-30)

Get-ChildItem "$localBackupDir\*.dump" -File |
    Where-Object { $_.LastWriteTime -lt $cutoff } |
    Remove-Item -Force

Get-ChildItem "$localBackupDir\*.sha256" -File |
    Where-Object { $_.LastWriteTime -lt $cutoff } |
    Remove-Item -Force

Get-ChildItem "$secondaryBackupDir\*.dump" -File |
    Where-Object { $_.LastWriteTime -lt $cutoff } |
    Remove-Item -Force

Get-ChildItem "$secondaryBackupDir\*.sha256" -File |
    Where-Object { $_.LastWriteTime -lt $cutoff } |
    Remove-Item -Force

Write-Host "9. Cleanup complete"

Write-Host "BACKUP_FILE:" $localBackup
Write-Host "BACKUP_SIZE:" (Get-Item $localBackup).Length
Write-Host "BACKUP_SHA256:" $hash.Hash
Write-Host "END:" (Get-Date)

Write-Host "BACKUP_STATUS: SUCCESS"
