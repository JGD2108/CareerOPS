$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

$backendProcesses = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -like "*uvicorn*" -and
        $_.CommandLine -like "*app.main:app*" -and
        $_.CommandLine -like "*8000*"
    }

foreach ($process in $backendProcesses) {
    Stop-Process -Id $process.ProcessId -Force
    Write-Host "Stopped FastAPI process $($process.ProcessId)"
}

docker compose stop db
Write-Host "Stopped PostgreSQL container."
