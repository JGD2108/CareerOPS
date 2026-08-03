# CareerOps Deploy Checklist

Use this checklist when deploying the private MVP.

## 1. Backend on Render

Use the repository root as the Render Blueprint source. Render reads `render.yaml`, builds the Docker backend from `backend/Dockerfile`, creates the managed PostgreSQL database, mounts `/storage`, and asks you for every variable marked with `sync: false`.

Required backend values:

```text
DATABASE_URL=
OPENAI_API_KEY=
APP_AUTH_ENABLED=true
APP_API_KEY=
CORS_ORIGINS=
CORS_ORIGIN_REGEX=^https://frontend-[a-z0-9-]+-jgd2108s-projects\.vercel\.app$
FRONTEND_APP_URL=
GMAIL_CREDENTIALS_JSON=
GMAIL_OAUTH_REDIRECT_URI=
LOCAL_STORAGE_DIR=/storage
GMAIL_CREDENTIALS_FILE=/storage/secrets/gmail_credentials.json
GMAIL_TOKEN_FILE=/storage/secrets/gmail_token.json
ENABLE_BROWSER_JOB_CHECKS=false
OPENAI_EMAIL_MODEL=gpt-5-nano
OPENAI_JOB_MODEL=gpt-5-nano
OPENAI_PROFILE_MODEL=gpt-5-mini
OPENAI_CV_MODEL=gpt-5-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
```

Generate `APP_API_KEY` locally:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Render variable values:

```text
OPENAI_API_KEY=<your OpenAI project API key>
APP_API_KEY=<generated private app key>
GMAIL_CREDENTIALS_JSON=<web OAuth client JSON from Google Cloud, compact one-line JSON>
GMAIL_OAUTH_REDIRECT_URI=https://YOUR_RENDER_BACKEND/api/v1/gmail/oauth/callback
CORS_ORIGINS=https://YOUR_VERCEL_FRONTEND
CORS_ORIGIN_REGEX=^https://frontend-[a-z0-9-]+-jgd2108s-projects\.vercel\.app$
FRONTEND_APP_URL=https://YOUR_VERCEL_FRONTEND
```

## 2. Google Cloud Gmail OAuth

Create an OAuth client:

- Type: Web application
- Authorized redirect URI:

```text
https://YOUR_BACKEND_DOMAIN/api/v1/gmail/oauth/callback
```

Set:

```text
GMAIL_OAUTH_REDIRECT_URI=https://YOUR_BACKEND_DOMAIN/api/v1/gmail/oauth/callback
GMAIL_CREDENTIALS_JSON=<paste the web OAuth client JSON as one line>
FRONTEND_APP_URL=https://YOUR_FRONTEND_DOMAIN
```

Keep scopes:

- `https://www.googleapis.com/auth/gmail.readonly`
- `https://www.googleapis.com/auth/gmail.compose`

## 3. Frontend on Vercel

Create a Vercel project from the same GitHub repository and set the root directory to:

```text
frontend
```

Framework preset:

```text
Vite
```

Build command:

```text
npm run build
```

Output directory:

```text
dist
```

Required frontend values:

```text
VITE_API_BASE_URL=https://YOUR_BACKEND_DOMAIN/api/v1
```

Do not set `VITE_CAREEROPS_API_KEY`. The deployed frontend signs in through `/api/v1/auth/login` and receives an HttpOnly session cookie.

After frontend deploy, update backend:

```text
CORS_ORIGINS=https://YOUR_FRONTEND_DOMAIN
CORS_ORIGIN_REGEX=^https://frontend-[a-z0-9-]+-jgd2108s-projects\.vercel\.app$
```

## 4. After Deploy

1. Open `https://YOUR_BACKEND_DOMAIN/health`.
2. Open `https://YOUR_FRONTEND_DOMAIN`.
3. Sign in with the private `APP_API_KEY`.
4. In Setup, click **Open web OAuth URL**.
5. Complete Google OAuth.
6. Sync Gmail.
7. Sync LinkedIn via Gmail.
8. Rebuild profile/job embeddings.
9. Score one job.
10. Generate one CV PDF.
