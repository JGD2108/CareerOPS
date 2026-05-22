# CareerOps Agent

CareerOps Agent is a human-in-the-loop multi-agent system for higher-quality job applications.

The system will help discover relevant roles, analyze job fit against a verified candidate profile, generate honest tailored CV drafts, prepare recruiter/application messages, monitor recruiter emails, and maintain an application tracker.

## Guiding Rules

- The system never invents experience, skills, companies, metrics, titles, or responsibilities.
- Candidate data must come from provided sources such as CV, LinkedIn export, portfolio, GitHub, or manual profile documents.
- The system never applies to jobs or sends emails automatically.
- Every generated CV, message, score, and recommendation must be traceable to evidence.
- Credentials and personal data must be handled through environment variables and secrets.

## Current Status

CareerOps is now a local-first desktop MVP. The app runs as an Electron desktop shell, FastAPI runs on your machine, and PostgreSQL/pgvector runs in Docker.

- Electron desktop app with React/Vite UI.
- FastAPI backend running locally on `127.0.0.1:8000`.
- PostgreSQL/pgvector running locally through Docker.
- Document ingestion for CV, LinkedIn exports, LaTeX templates, PDF, DOCX, TXT, and Markdown.
- LangGraph/OpenAI-backed agents for profile ingestion, email triage, and CV planning.
- Job discovery through Greenhouse, Lever, Ashby, and safe LinkedIn/Gmail alert ingestion.
- Job description resolution for incomplete Gmail/LinkedIn alert jobs using public Greenhouse, Lever, and Ashby postings with conservative confidence thresholds.
- Gmail monitoring with incremental sync, classification, source traceability, and draft generation gates.
- Job scoring with evidence, risks, and recommendations.
- LaTeX/PDF CV generation using verified profile evidence only.
- Message drafts and application tracker with human approval.
- Daily summaries, audit logs, and next actions.
- Initial pytest coverage, Dockerfiles, CI workflow, architecture docs, and local desktop runbook.
- pgvector semantic matching with OpenAI `text-embedding-3-small` embeddings.

## Local Desktop Quick Start

```powershell
git clone https://github.com/JGD2108/CareerOPS.git
cd CareerOPS
powershell -ExecutionPolicy Bypass -File .\scripts\setup-local.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start-desktop.ps1
```

This starts:

- Docker PostgreSQL/pgvector on `localhost:5433`
- FastAPI on `http://127.0.0.1:8000`
- Vite on `http://127.0.0.1:5173`
- Electron as the desktop app window

Stop local services:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop-local.ps1
```

## Manual Local Development

Use this if you want each service in its own terminal.

```powershell
docker compose up -d db

cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Then start the desktop UI:

```powershell
cd frontend
npm install
npm run desktop:dev
```

Useful local URLs:

- API health: http://127.0.0.1:8000/health
- API docs: http://127.0.0.1:8000/docs
- Vite UI: http://127.0.0.1:5173

## Run Tests

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pytest -q
```

Frontend:

```powershell
cd frontend
npm run lint
npm run build
npm run desktop:build
```

`desktop:build` creates an unpacked local executable at `dist-desktop\win-unpacked\CareerOps Agent.exe`.

## Gmail OAuth Local Setup

1. Put the desktop OAuth JSON at `storage/secrets/gmail_credentials.json`.
2. In Google Cloud, add this authorized redirect URI:
   `http://127.0.0.1:8000/api/v1/gmail/oauth/callback`
3. Open the Electron app.
4. Click **Continue with Google**.
5. Complete the Google flow in the browser.
6. Return to CareerOps. The app polls local FastAPI and unlocks when the token is stored.

CareerOps uses Gmail readonly/compose scopes and does not send email automatically.

## Job Description Resolution

LinkedIn is used only as a Gmail discovery signal. Google Auth does not grant LinkedIn access, and CareerOps does not collect LinkedIn credentials, store LinkedIn cookies, automate LinkedIn login, solve CAPTCHAs, or scrape authenticated LinkedIn pages.

When a LinkedIn Gmail alert contains only a title, company, location, and URL, the job is marked `partial_from_email`. Final scoring, CV tailoring, and message drafting stay blocked until a complete description is resolved or pasted manually.

The resolver checks configured public ATS sources first:

- Greenhouse public board API
- Lever public postings API
- Ashby public job board API

Resolution uses deterministic matching across title, company, location, work mode, active/open status, and source reliability. Matches at `0.90+` confidence can be accepted automatically. Matches from `0.70` to `0.89` require a very strong title/company/location match; otherwise the job is marked for manual review. Every attempt is stored in `job_description_resolution_attempts`.

Phase 3 adds two human-in-the-loop fallbacks after ATS resolution fails:

- `POST /api/v1/jobs/{job_id}/manual-url` accepts a user-provided official public job URL, rejects LinkedIn and auth/session/token URLs, fetches public HTML with timeouts and a descriptive user agent, blocks login/CAPTCHA-like pages, extracts readable text, and stores successful descriptions as `manually_provided_url` from `manual_url`.
- The company careers resolver tries a small set of URLs under the company website domain when a company website is known. It does not crawl broadly or use third-party reposting pages. It rejects generic listing pages unless the target role text is specific enough.

Medium-confidence candidates are shown for manual review with source, title, company, location, URL, confidence, and evidence. The user can accept the candidate, reject it, paste a description manually, or add an official job URL. LinkedIn remains Gmail-only discovery; there is no LinkedIn login automation, authenticated scraping, cookie use, Selenium, CAPTCHA bypass, or job-description scraping from LinkedIn.

The final complete states for downstream actions are `resolved_from_ats`, `resolved_from_company_site`, `manually_provided`, and `manually_provided_url`. `needs_manual_review` is a fetch/attempt state, not a complete description state. Final scoring, CV tailoring, and message generation require complete description evidence; preliminary scoring is the only exception. See `docs/job-description-resolution-qa.md` for local QA scenarios and safe seed data.

## Semantic Matching

After extracting the candidate profile:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/knowledge-base/embeddings/rebuild" `
  -ContentType "application/json" `
  -Body '{"include_jobs":true,"job_limit":100}'
```

This uses `text-embedding-3-small` to keep costs low.

## Documentation

- Architecture: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Local desktop runbook: [`docs/LOCAL_DESKTOP.md`](docs/LOCAL_DESKTOP.md)
- Gap tracking: [`docs/gap-tracking.md`](docs/gap-tracking.md)
- Task board: [`docs/task-board.md`](docs/task-board.md)

## Commit Convention

Use short, explicit commits:

- `feat: add job tracker model`
- `fix: handle empty profile source`
- `docs: document gmail oauth setup`
- `test: add scoring rules tests`
- `chore: update local dev config`

## Task Board

The working task board lives in [`docs/task-board.md`](docs/task-board.md).
