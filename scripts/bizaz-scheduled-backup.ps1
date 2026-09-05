$ErrorActionPreference = "Stop"

$projectRoot = "C:\Projects\BIZAZ-v0.1"
$logDir = Join-Path $projectRoot "backup-logs"
$backupScript = Join-Path $projectRoot "scripts\bizaz-backup.ps1"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logFile = Join-Path $logDir "backup-$timestamp.log"

try {
    Set-Location $projectRoot

    "============================================================" | Out-File $logFile -Encoding UTF8
    "BIZAZ SCHEDULED BACKUP" | Out-File $logFile -Append -Encoding UTF8
    "START: $(Get-Date)" | Out-File $logFile -Append -Encoding UTF8
    "============================================================" | Out-File $logFile -Append -Encoding UTF8

    & $backupScript *>&1 |
        Tee-Object -FilePath $logFile -Append

    if ($LASTEXITCODE -ne 0) {
        throw "Backup engine returned exit code $LASTEXITCODE."
    }

    "BACKUP_STATUS: SUCCESS" | Out-File $logFile -Append -Encoding UTF8
}
catch {
    "BACKUP_STATUS: FAILED" | Out-File $logFile -Append -Encoding UTF8
    "ERROR: $($_.Exception.Message)" | Out-File $logFile -Append -Encoding UTF8
    exit 1
}
finally {
    "END: $(Get-Date)" | Out-File $logFile -Append -Encoding UTF8
    "============================================================" | Out-File $logFile -Append -Encoding UTF8
}
