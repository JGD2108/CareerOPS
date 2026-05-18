# CareerOps Agent Gap Tracking

Updated: 2026-05-18

This table tracks the audit gaps against the current implementation. It is intentionally strict: a feature is only "closed" when it exists in code and has a way to verify it locally.

| Priority | Gap | Current status | Evidence in repo | Next action |
| --- | --- | --- | --- | --- |
| Critical | Remove invented CV fallback content | Closed | `backend/app/cv_tailoring.py` keeps source-backed content; `backend/tests/test_cv_rendering.py` checks metric-backed rendering. | Expand tests with a full generated CV fixture. |
| Critical | Remove invented message fallback identity | Closed | Message generation uses stored profile data and raises when required identity data is missing. | Add API-level tests for draft generation once the test database fixture exists. |
| Critical | Write `profile_sources` records | Closed, needs stronger granularity | `backend/app/profile_ingestion.py` and `backend/app/langgraph_agents.py` create `ProfileSource` rows tied to uploaded documents. | Add chunk offsets or line references for PDF/text extraction. |
| Critical | Read DOCX documents | Closed | `backend/app/documents.py` supports uploaded/imported documents beyond plain text and PDF. | Add test fixture for DOCX extraction. |
| High | Real LangGraph agents | Partial | `backend/app/langgraph_agents.py` orchestrates profile ingestion, email triage, and CV tailoring. | Add a job discovery/scoring graph and expose agent traces in the dashboard. |
| High | Embeddings and pgvector retrieval | Closed for MVP | `semantic_embeddings` table uses pgvector, profile/job backfill endpoints exist, and job score can include semantic evidence when vectors exist. Verified with 61 profile embeddings and a job embedding. | Add scheduled/automatic embedding refresh after new profile/job ingestion. |
| High | Tests | Partial | `backend/tests` now covers email classification, LinkedIn alert parsing, job-fit parsing, and CV rendering. CI runs `pytest -q`. | Add database-backed API tests and document extraction fixtures. |
| High | Docker and CI/CD | Partial | Backend/frontend Dockerfiles, `docker-compose.yml` app services, and `.github/workflows/ci.yml` are present. | Validate Docker image build in a clean environment and add deploy workflow after provider selection. |
| High | Frontend API URL for production | Closed | `frontend/src/App.tsx` reads `VITE_API_BASE_URL` with localhost fallback; `frontend/.env.example` documents it. | Add deployment-specific env values during deploy. |
| Medium | CV audit trail in UI | Partial | CV versions store `changes`; dashboard now shows top change reasons and sources. | Add full evidence drill-down per bullet/skill. |
| Medium | Gmail drafts | Partial | Gmail classification and suggested actions exist; automatic sending is intentionally blocked. | Create Gmail draft creation behind explicit user approval. |
| Medium | Approval UI | Partial | The app exposes review/approve state, but generated artifacts need clearer approve/reject controls. | Add a dedicated review panel for CVs, drafts, and actions. |
| Medium | Job discovery from LinkedIn | Safe alternative implemented | Direct LinkedIn scraping/API is not implemented because it can violate platform rules. LinkedIn job alert emails are parsed through Gmail, deduplicated, stored, traced, and auto-scored. | Add more email fixtures for Spanish/English LinkedIn variants. |
| Medium | App authentication before deploy | Partial | Optional single-user API key auth exists via `APP_AUTH_ENABLED`, `APP_API_KEY`, and frontend `VITE_CAREEROPS_API_KEY`. | For public use, replace with full OAuth/session auth. |
| Medium | Gmail authentication UX | Closed for local MVP | Dashboard Setup includes a Gmail OAuth button that calls the local desktop OAuth flow and refreshes Gmail status. | For cloud deployment, add a web OAuth redirect flow. |
| Low | Portfolio documentation | Partial | README, `ARCHITECTURE.md`, `DEPLOYMENT.md`, task board, and gap tracking exist. | Add demo script and interview talking points. |

## Current Rule

CareerOps must never apply to jobs, send email, or claim candidate experience without explicit user approval and source-backed evidence.
