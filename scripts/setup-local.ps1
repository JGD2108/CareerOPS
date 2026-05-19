$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"
$StorageDir = Join-Path $RepoRoot "storage"

function Copy-ExampleFile {
    param(
        [string]$ExamplePath,
        [string]$TargetPath
    )

    if (-not (Test-Path $TargetPath)) {
        Copy-Item $ExamplePath $TargetPath
        Write-Host "Created $TargetPath"
    }
}

function Wait-ForDatabase {
    Write-Host "Waiting for PostgreSQL..."
    for ($i = 0; $i -lt 45; $i++) {
        docker compose exec -T db pg_isready -U careerops -d careerops *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "PostgreSQL is ready."
            return
        }
        Start-Sleep -Seconds 2
    }
    throw "PostgreSQL did not become ready. Check Docker Desktop and run: docker compose logs db"
}

Set-Location $RepoRoot

New-Item -ItemType Directory -Force -Path (Join-Path $StorageDir "secrets") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $StorageDir "logs") | Out-Null
Copy-ExampleFile (Join-Path $BackendDir ".env.example") (Join-Path $BackendDir ".env")
Copy-ExampleFile (Join-Path $FrontendDir ".env.example") (Join-Path $FrontendDir ".env")

docker compose up -d db
Wait-ForDatabase

Set-Location $BackendDir
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python.exe -m alembic upgrade head

Set-Location $FrontendDir
npm install

Set-Location $RepoRoot
Write-Host ""
Write-Host "CareerOps local setup is ready."
Write-Host "Add Gmail OAuth JSON to storage\secrets\gmail_credentials.json when you want inbox sync."
Write-Host "Start the desktop app with: .\scripts\start-desktop.ps1"
