# CareerOps Agent Deployment Guide

This guide describes the production path. The app is currently safest as a single-user private deployment because it handles personal documents, Gmail data, and job application records.

## Required Secrets

Backend:

```text
DATABASE_URL=postgresql+psycopg://...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5-mini
OPENAI_PROFILE_MODEL=gpt-5-mini
OPENAI_EMAIL_MODEL=gpt-5-nano
OPENAI_JOB_MODEL=gpt-5-nano
OPENAI_CV_MODEL=gpt-5-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
GMAIL_CREDENTIALS_FILE=/storage/secrets/gmail_credentials.json
GMAIL_TOKEN_FILE=/storage/secrets/gmail_token.json
GMAIL_OAUTH_REDIRECT_URI=https://your-backend-domain.example/api/v1/gmail/oauth/callback
CORS_ORIGINS=https://your-frontend-domain.example
LOCAL_STORAGE_DIR=/storage
APP_AUTH_ENABLED=true
APP_API_KEY=generate-a-long-random-secret
```

Frontend:

```text
VITE_API_BASE_URL=https://your-backend-domain.example/api/v1
VITE_CAREEROPS_API_KEY=same-value-as-APP_API_KEY
```

## Local Docker Run

```powershell
docker compose up --build
```

Open:

- Frontend: http://127.0.0.1:5173
- Backend: http://127.0.0.1:8000/health
- API docs: http://127.0.0.1:8000/docs

Run migrations inside the backend container:

```powershell
docker compose exec backend alembic upgrade head
```

Build embeddings after the profile is extracted:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/knowledge-base/embeddings/rebuild" `
  -ContentType "application/json" `
  -Body '{"include_jobs":true,"job_limit":100}'
```

## Gmail OAuth Notes

For local/private use, use a Google OAuth Desktop client and store:

```text
storage/secrets/gmail_credentials.json
storage/secrets/gmail_token.json
```

For cloud deployment, do not commit these files. Use mounted secrets, encrypted storage, or provider secret volumes.

Gmail scopes:

- `gmail.readonly`
- `gmail.compose`

CareerOps never sends email automatically.

In the local dashboard, use **Setup -> Gmail OAuth -> Authenticate Gmail** for the desktop flow, or **Open web OAuth URL** for the redirect-based flow.

For cloud deployment:

1. Create a Google OAuth client of type **Web application**.
2. Add this authorized redirect URI:

```text
https://your-backend-domain.example/api/v1/gmail/oauth/callback
```

3. Set `GMAIL_OAUTH_REDIRECT_URI` to that same URL.
4. Store the downloaded OAuth JSON as your backend secret file.
5. Open the dashboard and click **Open web OAuth URL**.

## Suggested Cloud Deployment

Backend options:

- Render web service
- Railway service
- AWS ECS/Fargate

Database:

- Managed PostgreSQL with pgvector support
- Neon, Supabase, Railway Postgres, Render Postgres, or AWS RDS with pgvector where available

Frontend:

- Vercel static/Vite deployment
- Render static site
- Railway static frontend

Storage:

- Start with local persistent disk for private deployment.
- Move generated CVs and documents to S3/GCS before public use.

Scheduler:

- Local/private: APScheduler built into FastAPI.
- Cloud: GitHub Actions cron, Cloud Scheduler, EventBridge, or provider cron calling backend endpoints.

## Production Checklist

- [ ] App-level authentication enabled.
- [ ] Secrets are configured outside Git.
- [ ] Database migrations run successfully.
- [ ] `CORS_ORIGINS` only includes trusted frontend domains.
- [ ] Gmail OAuth app has approved testers or verification.
- [ ] Logs do not expose CV text, access tokens, or raw email bodies unnecessarily.
- [ ] Backups enabled for PostgreSQL.
- [ ] Generated CV artifacts stored in private storage.
- [ ] CI passes for backend tests and frontend build.
