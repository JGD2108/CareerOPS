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

CareerOps is now a local MVP that covers phases 0-11 and has started phase 12/13 hardening:

- FastAPI backend with PostgreSQL/pgvector-ready schema.
- React/Vite dashboard.
- Document ingestion for CV, LinkedIn exports, LaTeX templates, PDF, DOCX, TXT, and Markdown.
- LangGraph/OpenAI-backed agents for profile ingestion, email triage, and CV planning.
- Job discovery through Greenhouse, Lever, Ashby, and safe LinkedIn/Gmail alert ingestion.
- Gmail monitoring with incremental sync, classification, source traceability, and draft generation gates.
- Job scoring with evidence, risks, and recommendations.
- LaTeX/PDF CV generation using verified profile evidence only.
- Message drafts and application tracker with human approval.
- Daily summaries, audit logs, and next actions.
- Initial pytest coverage, Dockerfiles, CI workflow, architecture docs, and deploy guide.
- Optional single-user API key auth for private deployments.
- pgvector semantic matching with OpenAI `text-embedding-3-small` embeddings.

## Local Development

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

Open:

- API health: http://127.0.0.1:8000/health
- API docs: http://127.0.0.1:8000/docs
- Dashboard: http://127.0.0.1:5173

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
```

## Gmail OAuth From Dashboard

1. Put the desktop OAuth JSON at `storage/secrets/gmail_credentials.json`.
2. Open the dashboard setup page.
3. Click **Authenticate Gmail** for local desktop OAuth, or **Open web OAuth URL** for redirect-based OAuth.
4. Complete the Google flow in the browser.
5. Return to CareerOps and run **Sync Gmail** or **Sync LinkedIn via Gmail**.

CareerOps uses Gmail readonly/compose scopes and does not send email automatically.

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

## Docker Run

```powershell
docker compose up --build
docker compose exec backend alembic upgrade head
```

## Documentation

- Architecture: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Deployment: [`DEPLOYMENT.md`](DEPLOYMENT.md)
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
