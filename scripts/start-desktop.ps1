$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"
$StorageDir = Join-Path $RepoRoot "storage"
$BackendLog = Join-Path $StorageDir "logs\backend.log"
$BackendErrorLog = Join-Path $StorageDir "logs\backend-error.log"

function Test-HttpOk {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 300
    } catch {
        return $false
    }
}

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

function Stop-ComposeBackend {
    $backendContainerId = docker compose ps -q backend
    if ($backendContainerId) {
        Write-Host "Stopping Docker backend so the desktop app uses the local FastAPI code..."
        docker compose stop backend | Out-Null
    }
}

function Wait-ForBackend {
    Write-Host "Waiting for FastAPI..."
    for ($i = 0; $i -lt 45; $i++) {
        if (Test-HttpOk "http://127.0.0.1:8000/health") {
            Write-Host "FastAPI is ready."
            return
        }
        Start-Sleep -Seconds 1
    }
    throw "FastAPI did not start. See storage\logs\backend-error.log"
}

Set-Location $RepoRoot
New-Item -ItemType Directory -Force -Path (Join-Path $StorageDir "logs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $StorageDir "secrets") | Out-Null
Copy-ExampleFile (Join-Path $BackendDir ".env.example") (Join-Path $BackendDir ".env")
Copy-ExampleFile (Join-Path $FrontendDir ".env.example") (Join-Path $FrontendDir ".env")

docker compose up -d db
Stop-ComposeBackend
Wait-ForDatabase

if (-not (Test-Path (Join-Path $BackendDir ".venv\Scripts\python.exe"))) {
    Write-Host "Python environment not found. Running setup first..."
    & (Join-Path $PSScriptRoot "setup-local.ps1")
}

Set-Location $BackendDir
.\.venv\Scripts\python.exe -m alembic upgrade head

$StartedBackend = $null
if (-not (Test-HttpOk "http://127.0.0.1:8000/health")) {
    Write-Host "Starting FastAPI on http://127.0.0.1:8000"
    $StartedBackend = Start-Process `
        -FilePath (Join-Path $BackendDir ".venv\Scripts\python.exe") `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory $BackendDir `
        -RedirectStandardOutput $BackendLog `
        -RedirectStandardError $BackendErrorLog `
        -WindowStyle Hidden `
        -PassThru
}

Wait-ForBackend

try {
    Set-Location $FrontendDir
    if (-not (Test-Path "node_modules")) {
        npm install
    }
    npm run desktop:dev
} finally {
    Set-Location $RepoRoot
    if ($StartedBackend -and -not $StartedBackend.HasExited) {
        Stop-Process -Id $StartedBackend.Id -Force
    }
}
