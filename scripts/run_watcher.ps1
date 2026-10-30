$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$envFile = Join-Path $projectRoot ".env"
$logDirectory = Join-Path $projectRoot "logs"
$logFile = Join-Path $logDirectory "scheduled-migration.log"

foreach ($path in @($python, $envFile)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required file not found: $path"
    }
}

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
Set-Location -LiteralPath $projectRoot
$startedAt = Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"
"[$startedAt] Scheduled migration started" | Add-Content -LiteralPath $logFile
& $python -m app 2>&1 | Tee-Object -FilePath $logFile -Append
$exitCode = $LASTEXITCODE
$finishedAt = Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"
"[$finishedAt] Scheduled migration exited with code $exitCode" | Add-Content -LiteralPath $logFile
exit $exitCode
