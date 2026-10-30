$taskName = "Apollo RPA Data Migration"
& schtasks.exe /Delete /TN $taskName /F 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Scheduled task removed: $taskName"
} else {
    Write-Host "Scheduled task is not installed: $taskName"
}
