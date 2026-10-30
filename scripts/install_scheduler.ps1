$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$envFile = Join-Path $projectRoot ".env"
$runner = Join-Path $PSScriptRoot "run_watcher.ps1"
$taskName = "Apollo RPA Data Migration"
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

foreach ($path in @($python, $envFile, $runner)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required file not found: $path"
    }
}

$taskRun = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$runner`""
& schtasks.exe /Create /SC MINUTE /MO 5 /TN $taskName /TR $taskRun /RU $currentUser /RL LIMITED /IT /F
if ($LASTEXITCODE -ne 0) {
    throw "Task Scheduler could not create the recurring task (exit code $LASTEXITCODE)."
}

Write-Host "Scheduled task installed: $taskName (every five minutes while $currentUser is logged in)."
