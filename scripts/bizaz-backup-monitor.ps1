$ErrorActionPreference = "Stop"

$projectRoot = "C:\Projects\BIZAZ-v0.1"
$monitorDir = Join-Path $projectRoot "backup-monitoring"
$statusFile = Join-Path $monitorDir "status.txt"
$alertFile = Join-Path $monitorDir "alert.txt"

New-Item -ItemType Directory -Force -Path $monitorDir | Out-Null

$alerts = @()

$taskInfo = Get-ScheduledTaskInfo -TaskName "BIZAZ - Daily PostgreSQL Backup"

$latestBackup = Get-ChildItem (Join-Path $projectRoot "backups\*.dump") -File |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

$latestLog = Get-ChildItem (Join-Path $projectRoot "backup-logs\backup-*.log") -File |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

$dbContainer = docker inspect -f "{{.State.Status}}" bizaz-postgres 2>$null

if ($dbContainer -ne "running") {
    $alerts += "DATABASE_UNAVAILABLE"
}

if ($taskInfo.LastTaskResult -ne 0) {
    $alerts += "TASK_FAILURE"
}

if ($null -ne $latestLog) {
    $failedMarker = Select-String -Path $latestLog.FullName -Pattern "BACKUP_STATUS: FAILED" -Quiet

    if ($failedMarker) {
        $alerts += "BACKUP_FAILURE_LOG"
    }
}

$backupAgeMinutes = $null

if ($null -eq $latestBackup) {
    $alerts += "NO_BACKUP_FOUND"
}

if ($null -ne $latestBackup) {
    $backupAgeMinutes = ((Get-Date) - $latestBackup.LastWriteTime).TotalMinutes

    if ($backupAgeMinutes -gt 1440) {
        $alerts += "BACKUP_OLDER_THAN_24H"
    }
}

if ($alerts.Count -eq 0) {
    $statusText = @(
        "BIZAZ BACKUP MONITORING"
        "STATUS: OK"
        "TIME: $(Get-Date)"
        "DATABASE_STATUS: RUNNING"
        "TASK_LAST_RESULT: $($taskInfo.LastTaskResult)"
        "LATEST_BACKUP: $($latestBackup.Name)"
        "BACKUP_AGE_MINUTES: $([math]::Round($backupAgeMinutes,2))"
        "LATEST_LOG: $($latestLog.Name)"
    )

    $statusText | Set-Content $statusFile -Encoding UTF8

    if (Test-Path $alertFile) {
        Remove-Item $alertFile -Force
    }

    Write-Host "MONITORING_STATUS: OK"
    Write-Host "ALERT_COUNT: 0"
}

if ($alerts.Count -gt 0) {
    $latestBackupName = "NONE"
    if ($null -ne $latestBackup) {
        $latestBackupName = $latestBackup.Name
    }

    $latestLogName = "NONE"
    if ($null -ne $latestLog) {
        $latestLogName = $latestLog.Name
    }

    $alertAge = "N/A"
    if ($null -ne $backupAgeMinutes) {
        $alertAge = [math]::Round($backupAgeMinutes,2)
    }

    $alertText = @(
        "BIZAZ BACKUP MONITORING"
        "STATUS: ALERT"
        "TIME: $(Get-Date)"
        "ALERT_COUNT: $($alerts.Count)"
        "ALERTS: $($alerts -join ', ')"
        "DATABASE_STATUS: $dbContainer"
        "TASK_LAST_RESULT: $($taskInfo.LastTaskResult)"
        "LATEST_BACKUP: $latestBackupName"
        "BACKUP_AGE_MINUTES: $alertAge"
        "LATEST_LOG: $latestLogName"
    )

    $alertText | Set-Content $alertFile -Encoding UTF8

    if (Test-Path $statusFile) {
        Remove-Item $statusFile -Force
    }

    Write-Host "MONITORING_STATUS: ALERT"
    Write-Host "ALERT_COUNT: $($alerts.Count)"
    Write-Host "ALERTS: $($alerts -join ', ')"
    Write-Host "DATABASE_STATUS: $dbContainer"
}

Write-Host "MONITORING_COMPLETE"
