# CareerOps Agent Task Board

## Phase 0 - Preparation

- [x] Create base repository structure
- [x] Add FastAPI backend skeleton
- [x] Add PostgreSQL Docker Compose setup
- [x] Add environment variable template
- [x] Add health check endpoint
- [x] Add database health check endpoint
- [x] Add README and commit conventions
- [x] Verify backend locally
- [x] Verify PostgreSQL connection locally

## Phase 1 - Data Model and Base Tracker

- [x] Choose SQLAlchemy + Alembic migration layout
- [x] Create core tables
- [x] Add CRUD endpoints for manual jobs
- [x] Add base application tracker states
- [x] Add audit log helper
- [x] Run migrations locally
- [x] Create and read a manual job through the API

## Phase 2 - Profile Ingestion Agent

- [x] Add document upload endpoint
- [x] Extract text from PDF, TEX, Markdown, and TXT sources
- [x] Store uploaded sources in documents table with checksum
- [x] Register LinkedIn PDF as a document source
- [x] Register LaTeX CV template/current CV as a document source
- [x] Create structured profile extraction tables
- [x] Extract candidate profile with source-backed evidence

## Phase 3 - Job Fit MVP

- [x] Add job_scores table
- [x] Create rule-based job description parser
- [x] Compare extracted requirements against profile skills
- [x] Save score, reasons, risks, recommendation, and evidence
- [x] Score a real/manual job through the API
- [x] Add one-step job fit analysis endpoint
- [x] Test one-step job fit flow with example payload

## Phase 4 - Candidate Knowledge Base

- [x] Add controlled skill alias table
- [x] Add alias rebuild endpoint
- [x] Use aliases during job fit scoring
- [x] Add evidence lookup endpoint for claims
- [x] Verify alias-based matching with a sample job

## Phase 5 - CV Tailoring Agent

- [x] Add cv_versions table for generated CV artifacts and plans
- [x] Create approval-required CV tailoring plan generator
- [x] Select existing skills, bullets, and projects with evidence
- [x] Add honesty guardrails for missing requirements
- [x] Verify tailoring plan against a scored job
- [x] Generate LaTeX tailoring preview from a plan
- [x] Verify generated LaTeX preview file exists and is readable
- [x] Generate controlled final LaTeX draft from source template
- [x] Verify generated final LaTeX draft exists and keeps guardrails
- [x] Compile generated final LaTeX draft to PDF locally
- [x] Add CV version review fields
- [x] Add approve/reject endpoint for CV versions
- [x] Verify CV approval and rejection flow

## Phase 6 - Message Agent

- [x] Add message_drafts table
- [x] Require approved CV before generating message drafts
- [x] Generate LinkedIn, application email, and short cover letter drafts
- [x] Store message drafts with evidence and approval_required
- [x] Verify message draft generation against an approved CV
- [x] Add approve/reject endpoint for message drafts
- [x] Verify message draft approval and rejection flow

## Application Tracker Extension

- [x] Add application tracker detail view
- [x] Sync application status from score, approved CV, and approved messages
- [x] Preserve terminal statuses from automatic overwrite
- [x] Verify tracker sync and ready-to-apply signals
- [x] Add mark-as-applied action with applied timestamp
- [x] Add current-action guidance based on application state

## Phase 7 - Job Discovery Agent

- [x] Add raw_jobs table for source payload storage
- [x] Add public API connectors for Greenhouse, Lever, and Ashby
- [x] Add filtering by role keywords, locations, seniority, and work mode
- [x] Deduplicate normalized jobs against existing records
- [x] Add discovery endpoint and raw job listing endpoint
- [x] Add saved discovery source configuration
- [x] Add discovery run history
- [x] Verify live discovery against Lever public demo jobs
- [x] Verify live discovery against Ashby public jobs page
- [x] Verify live discovery against Greenhouse example board
- [x] Add scheduler for recurring discovery runs

## Phase 8 - Gmail Integration

- [x] Add raw_emails and emails tables
- [x] Add Gmail local OAuth configuration paths
- [x] Add Gmail status endpoint
- [x] Add Gmail auth flow for local desktop OAuth
- [x] Add Gmail inbox sync endpoint
- [x] Add normalized email classification
- [x] Add local reply draft generation from normalized emails
- [x] Add mock email ingest flow for local testing
- [x] Verify normalized email persistence and draft creation with mock input
- [x] Verify live Gmail auth with user credentials
- [x] Verify live Gmail inbox sync with user account
- [x] Verify Gmail draft creation in the user's mailbox

## Phase 9 - Next Action Agent

- [x] Add actions table
- [x] Add action listing and update endpoints
- [x] Add next-action sync endpoint per application
- [x] Generate actions from interview, assessment, recruiter follow-up, documents, forms, rejection, and offer emails
- [x] Update application status from key email categories during next-action sync
- [x] Add follow-up and manual-submit rules for application state
- [x] Verify action creation from a real interview-related email
- [x] Verify action completion flow and open-action backlog update

## Phase 10 - Notification Agent

- [x] Add notification_summaries table
- [x] Add daily summary generation endpoint
- [x] Add daily summary history endpoint
- [x] Include new jobs, top matches, important emails, open actions, and pending applications
- [x] Persist rendered summary text plus structured content
- [x] Verify daily summary generation against real project data

## Phase 11 - Dashboard

- [x] Scaffold React + TypeScript frontend with Vite
- [x] Add Tailwind CSS through the Vite plugin
- [x] Build a dashboard-first shell instead of a landing page
- [x] Connect jobs, applications, profile, emails, actions, and daily summary endpoints
- [x] Add graceful fallbacks when backend routes are temporarily unavailable
- [x] Add operational views for Overview, Jobs, Applications, Inbox, and Profile
- [x] Verify production build locally
- [x] Verify frontend lint locally
- [x] Add dedicated job detail and score evidence screens
- [x] Add CV and draft review surfaces in the web UI
- [x] Add action mutations directly from the dashboard
- [x] Add richer email-to-application linking workflows

## Notes

- Input mode for initial job discovery: manual job descriptions first.
- Candidate profile source received: LinkedIn PDF at `C:/Users/Jdela/Downloads/Profile (11).pdf`.
- CV template format: LaTeX.
- Candidate profile extraction starts in Phase 2, after storage and traceability tables exist.
