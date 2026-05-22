# CareerOps Backend

FastAPI backend for CareerOps Agent.

## Run Locally

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

## Endpoints

- `GET /health`: app health check.
- `GET /health/db`: verifies PostgreSQL connectivity.
- `POST /api/v1/jobs`: creates a manual job.
- `GET /api/v1/jobs`: lists saved jobs.
- `POST /api/v1/applications`: creates an application tracker entry.
- `PATCH /api/v1/applications/{id}`: updates tracker status or notes.
- `POST /api/v1/documents/upload`: uploads a CV, LinkedIn PDF, template, or manual source.
- `GET /api/v1/documents`: lists uploaded sources.
- `POST /api/v1/documents/import-local`: imports a local file only when it lives under an approved folder from `LOCAL_DOCUMENT_ALLOWED_ROOTS`.
- `POST /api/v1/profile/extract`: extracts structured profile data from the latest CV source.
- `GET /api/v1/profile`: returns the structured profile and evidence.
- `POST /api/v1/jobs/{job_id}/score`: scores a job against the structured profile.
- `GET /api/v1/jobs/{job_id}/scores`: lists previous scores for a job.
- `POST /api/v1/job-fit/analyze`: creates a manual job and immediately scores it.
- `POST /api/v1/knowledge-base/aliases/rebuild`: rebuilds controlled skill aliases from verified skills.
- `GET /api/v1/knowledge-base/aliases`: lists controlled aliases.
- `POST /api/v1/knowledge-base/evidence`: checks whether a claim has profile evidence.
- `POST /api/v1/jobs/{job_id}/cv-tailoring-plan`: creates an approval-required CV tailoring plan.
- `GET /api/v1/jobs/{job_id}/cv-tailoring-plans`: lists CV tailoring plans for a job.
- `POST /api/v1/cv-versions/{cv_version_id}/latex-preview`: generates a LaTeX preview from a CV tailoring plan.
- `POST /api/v1/cv-versions/{cv_version_id}/final-latex`: generates a controlled final LaTeX CV draft.
- `PATCH /api/v1/cv-versions/{cv_version_id}/review`: approves or rejects a generated CV version.
- `POST /api/v1/jobs/{job_id}/message-drafts`: generates recruiter/application message drafts from an approved CV.
- `GET /api/v1/jobs/{job_id}/message-drafts`: lists message drafts for a job.
- `PATCH /api/v1/message-drafts/{message_draft_id}/review`: approves or rejects a message draft.
- `GET /api/v1/applications/{application_id}`: returns tracker state plus readiness signals.
- `POST /api/v1/applications/{application_id}/sync`: updates the tracker status from approved artifacts.
- `PATCH /api/v1/applications/{application_id}/mark-applied`: marks a manually submitted application as applied.
- `POST /api/v1/job-discovery/discover`: runs ad hoc discovery against public job board APIs.
- `GET /api/v1/raw-jobs`: lists saved raw job payloads.
- `POST /api/v1/discovery-sources`: saves a reusable discovery source configuration.
- `GET /api/v1/discovery-sources`: lists saved discovery sources.
- `PATCH /api/v1/discovery-sources/{source_id}`: updates a saved discovery source.
- `POST /api/v1/job-discovery/run-saved`: runs discovery using all active saved sources.
- `GET /api/v1/job-discovery/runs`: lists recent discovery runs.
- `GET /api/v1/job-discovery/scheduler`: returns scheduler status and active source count.
- `GET /api/v1/gmail/status`: checks whether Gmail credentials and token are available locally.
- `POST /api/v1/gmail/auth`: runs the Gmail desktop OAuth flow and stores the token locally.
- `POST /api/v1/gmail/sync`: reads Gmail inbox messages using the configured query.
- `GET /api/v1/emails`: lists normalized email records.
- `GET /api/v1/raw-emails`: lists raw Gmail payloads.
- `POST /api/v1/emails/mock-ingest`: ingests a simulated email for local testing.
- `POST /api/v1/emails/{email_id}/draft-reply`: creates a local recruiter reply draft and can also create a Gmail draft.
- `PATCH /api/v1/emails/{email_id}/link`: links or unlinks a normalized email to an application and can sync next actions.
- `POST /api/v1/applications/{application_id}/next-actions/sync`: derives next actions from tracker state and emails.
- `GET /api/v1/applications/{application_id}/actions`: lists actions for one application.
- `GET /api/v1/actions`: lists actions globally, optionally filtered by status.
- `PATCH /api/v1/actions/{action_id}`: marks an action completed or dismissed.
- `POST /api/v1/notifications/daily-summary`: generates and stores a daily summary snapshot.
- `GET /api/v1/notifications/daily-summary`: lists recent generated summary snapshots.

## Migrations

```powershell
alembic upgrade head
```

## Upload a Document Source

```powershell
python scripts/upload_document.py linkedin "C:\Users\Jdela\Downloads\Profile (11).pdf"
```

## Analyze a Job in One Step

```powershell
python scripts/analyze_job.py examples/job_payload.json
```

## Generate a CV Tailoring Preview

```powershell
python scripts/generate_cv_preview.py <job_id>
```

## Generate a Controlled Final CV LaTeX Draft

```powershell
python scripts/generate_final_cv_tex.py <job_id>
```

## Generate Message Drafts

```powershell
python scripts/generate_messages.py <job_id>
```

## Create a Saved Discovery Source

```powershell
python scripts/create_discovery_source.py examples/discovery_source_payload.json
```

## Run Discovery From Saved Sources

```powershell
python scripts/run_saved_discovery.py
```

## Enable the Daily Scheduler

Set these values in `backend/.env`:

```text
ENABLE_JOB_DISCOVERY_SCHEDULER=true
DISCOVERY_SCHEDULE_HOUR=8
DISCOVERY_SCHEDULE_MINUTE=0
SCHEDULER_TIMEZONE=America/Bogota
```

Then restart FastAPI:

```powershell
uvicorn app.main:app --reload
```

The scheduler now uses a lock file so duplicate local processes do not run the same saved discovery job at the same time. You can override the lock location with `SCHEDULER_LOCK_FILE`.

## Local Desktop Security Notes

- `APP_API_KEY` is no longer intended to be embedded in the Vite bundle.
- For the desktop/local loopback flow, keep `ALLOW_LOOPBACK_AUTH_BYPASS=true` so Electron and localhost clients can talk to FastAPI without shipping a static secret to the browser bundle.
- For stricter non-local environments, set `ALLOW_LOOPBACK_AUTH_BYPASS=false` and provide `APP_API_KEY` out of band.

## Local Document Import Guardrails

- `POST /api/v1/documents/import-local` only accepts `.pdf`, `.docx`, `.txt`, `.md`, and `.tex`.
- Files must live under one of the comma-separated roots in `LOCAL_DOCUMENT_ALLOWED_ROOTS`.
- The default allowlist is `~/Documents,~/Desktop,~/Downloads,../storage`.

## Gmail Setup (Local Desktop OAuth)

1. In Google Cloud, create or pick a project and enable the Gmail API:
   [Gmail API Python quickstart](https://developers.google.com/gmail/api/quickstart/python?hl=en)
2. Configure the OAuth consent screen.
3. Create an OAuth client with **Application type = Desktop app**.
4. Download the OAuth client JSON and place it at:

```text
storage/secrets/gmail_credentials.json
```

5. Copy `.env.example` to `.env` if you have not already, then confirm:

```text
GMAIL_CREDENTIALS_FILE=../storage/secrets/gmail_credentials.json
GMAIL_TOKEN_FILE=../storage/secrets/gmail_token.json
```

6. Run the auth script:

```powershell
python scripts/gmail_auth.py
```

7. After approval in the browser, sync Gmail:

```powershell
python scripts/gmail_sync.py
```

## Gmail Scope Notes

This phase uses:

- `https://www.googleapis.com/auth/gmail.readonly`
- `https://www.googleapis.com/auth/gmail.compose`

Google classifies these as restricted Gmail scopes:
[Choose Gmail API scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)

For personal/local testing, this is fine. For a public production app, Google may require additional verification and security review depending on how data is stored and transmitted.

## Local Email Flow Without Credentials

You can test the phase without Google credentials:

```powershell
python scripts/mock_email_ingest.py
```
