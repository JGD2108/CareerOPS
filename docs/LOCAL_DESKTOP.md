# CareerOps Local Desktop Runbook

This runbook is the clone-and-run path for CareerOps Agent on Windows.

## Requirements

- Windows 10/11
- Docker Desktop
- Python 3.12 or compatible Python 3
- Node.js 20+
- Git
- Optional: a local LaTeX installation if you want PDF generation outside Docker

## First Run

```powershell
git clone https://github.com/JGD2108/CareerOPS.git
cd CareerOPS
powershell -ExecutionPolicy Bypass -File .\scripts\setup-local.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start-desktop.ps1
```

The setup script creates:

- `backend\.env`
- `frontend\.env`
- `storage\secrets`
- `storage\logs`
- Python virtual environment in `backend\.venv`
- Node dependencies in `frontend\node_modules`
- PostgreSQL schema through Alembic

## Daily Run

```powershell
cd CareerOPS
powershell -ExecutionPolicy Bypass -File .\scripts\start-desktop.ps1
```

## Stop

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop-local.ps1
```

## Gmail OAuth

1. Create a Google Cloud OAuth client of type Desktop app or Web app.
2. If using Web app OAuth, add:

```text
http://127.0.0.1:8000/api/v1/gmail/oauth/callback
```

3. Save the downloaded JSON as:

```text
storage\secrets\gmail_credentials.json
```

4. Or start CareerOps and upload the JSON directly from the onboarding screen with `Load OAuth JSON`.

5. Click `Continue with Google`.

The Google flow opens in the system browser. The Electron app keeps polling local FastAPI and unlocks when `storage\secrets\gmail_token.json` is written.

## OpenAI API

Add your key to:

```text
backend\.env
```

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5-mini
OPENAI_PROFILE_MODEL=gpt-5-mini
OPENAI_EMAIL_MODEL=gpt-5-nano
OPENAI_JOB_MODEL=gpt-5-nano
OPENAI_CV_MODEL=gpt-5-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

The expensive steps are profile extraction and CV generation. Inbox triage and job parsing use cheaper models.

## Local URLs

- FastAPI health: `http://127.0.0.1:8000/health`
- FastAPI docs: `http://127.0.0.1:8000/docs`
- Vite dev UI: `http://127.0.0.1:5173`

Electron is the primary UI.

## Troubleshooting

If Docker is not running:

```powershell
docker compose up -d db
docker compose logs db
```

If the backend does not start:

```powershell
Get-Content .\storage\logs\backend-error.log
```

If the app says Google is not configured, confirm this file exists:

```powershell
Test-Path .\storage\secrets\gmail_credentials.json
```

If profile extraction fails, confirm the CV was uploaded as source type `Base CV` and `OPENAI_API_KEY` exists in `backend\.env`.

## Packaging

The unpacked desktop app can be built with:

```powershell
cd frontend
npm run desktop:build
```

The executable output goes to:

```text
dist-desktop\win-unpacked\CareerOps Agent.exe
```

For now, the desktop app still expects local FastAPI and Docker PostgreSQL to be running. Use `scripts\start-desktop.ps1` for development and daily use.

If you want to try a Windows installer later, use:

```powershell
cd frontend
npm run desktop:installer
```

That may require Windows Developer Mode or elevated permissions because some electron-builder helper archives contain symlinks.
