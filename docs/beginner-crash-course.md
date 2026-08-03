# CareerOps Beginner Crash Course

This guide is for a complete beginner who wants a fast but solid understanding of the project in 4 to 5 hours.

Goal: finish with a clear mental model of what the system does, how data moves through it, where the agents live, and how to explain the architecture in an interview.

## Before You Start

You do not need to understand every line of code.

You do need to understand:

- what each layer does
- where the main workflows start
- where AI is used
- where deterministic logic is used
- where human approval is required

## Stack In One Minute

CareerOps is a local-first desktop MVP for job search operations.

- `Electron + React/Vite`: desktop UI shell and frontend
- `FastAPI`: backend API
- `PostgreSQL + pgvector`: app data and semantic search
- `LangGraph + OpenAI`: profile ingestion, email triage, and CV planning workflows
- `Gmail + public job board APIs`: external signals

Read this first:

1. [README.md](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/README.md:1>)
2. [ARCHITECTURE.md](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/ARCHITECTURE.md:1>)

## 4-5 Hour Study Plan

### Block 1 - Big Picture (35 minutes)

Read these sections only:

- [README.md](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/README.md:1>)
- [ARCHITECTURE.md](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/ARCHITECTURE.md:5>)
- [ARCHITECTURE.md](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/ARCHITECTURE.md:14>)
- [ARCHITECTURE.md](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/ARCHITECTURE.md:67>)

At the end of this block, you should be able to say:

"This project helps a candidate discover jobs, score fit, tailor a CV, classify recruiter emails, and track next actions. It is local-first and human-in-the-loop, so the AI can draft and recommend, but it does not apply or send emails automatically."

### Block 2 - Run The System Mentally (25 minutes)

Read:

- [docs/LOCAL_DESKTOP.md](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/docs/LOCAL_DESKTOP.md:1>)
- [backend/README.md](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/backend/README.md:1>)

Focus on these facts:

- the frontend talks to FastAPI
- FastAPI talks to PostgreSQL and external services
- the API docs live at `http://127.0.0.1:8000/docs`
- the backend health endpoint is `/health`

You are not trying to memorize commands. You are trying to understand how the app is assembled.

### Block 3 - Learn The Layers (50 minutes)

Read these files in this order:

1. [backend/app/main.py](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/backend/app/main.py:1>)
2. [backend/app/api.py](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/backend/app/api.py:1>)
3. [frontend/src/lib/api.ts](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/frontend/src/lib/api.ts:1>)
4. [backend/app/models.py](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/backend/app/models.py:1>)
5. [backend/app/config.py](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/backend/app/config.py:1>)

What to learn from each file:

- `main.py`: how FastAPI starts and mounts the router
- `api.py`: the system entrypoints by domain
- `frontend/src/lib/api.ts`: how the frontend calls the backend
- `models.py`: the core business entities
- `config.py`: environment variables, model names, feature flags

Checkpoint:

You should now understand that the UI does not call agents directly. It calls HTTP endpoints, and those endpoints trigger backend workflows.

### Block 4 - Understand The Agent Architecture (65 minutes)

Read these files carefully:

1. [backend/app/langgraph_agents.py](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/backend/app/langgraph_agents.py:1>)
2. [backend/app/ai_client.py](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/backend/app/ai_client.py:1>)
3. [backend/app/ai_schemas.py](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/backend/app/ai_schemas.py:1>)
4. [backend/app/model_router.py](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/backend/app/model_router.py:1>)

Key ideas to capture:

- LangGraph is the workflow orchestrator, not the model itself.
- The project uses typed state and ordered nodes.
- The model returns structured JSON, not free-form text.
- Pydantic schemas constrain the output shape.
- The system persists results only after validation and normalization.

Two workflows to understand first:

- profile ingestion
- email triage

You should be able to explain this sentence:

"The LLM is one step inside a controlled backend workflow. It does not own the whole process."

### Block 5 - Follow The Main Business Flows (70 minutes)

Read these files:

1. [backend/app/job_discovery.py](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/backend/app/job_discovery.py:1>)
2. [backend/app/job_fit.py](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/backend/app/job_fit.py:1>)
3. [backend/app/cv_tailoring.py](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/backend/app/cv_tailoring.py:1>)
4. [backend/app/next_action_agent.py](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/backend/app/next_action_agent.py:1>)
5. [backend/app/notification_agent.py](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/backend/app/notification_agent.py:1>)

For each file, answer the same five questions:

1. What is the input?
2. What processing happens?
3. What tables are read or written?
4. Is the logic deterministic, AI-based, or hybrid?
5. Where is the human approval gate?

This is the core of the project.

### Block 6 - Semantic Search And Evidence (25 minutes)

Read:

- [backend/app/semantic_embeddings.py](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/backend/app/semantic_embeddings.py:1>)

Understand:

- why embeddings are stored
- why `pgvector` is used
- how semantic matches support job scoring
- why semantic retrieval complements, but does not replace, deterministic matching

### Block 7 - Interview Preparation (30 minutes)

Prepare short answers for these questions:

1. What problem does CareerOps solve?
2. Why is this a multi-agent system?
3. What does LangGraph do here?
4. How do you reduce hallucinations?
5. Why use both deterministic logic and AI?
6. Why keep a human in the loop?

Use the code, not generic AI answers.

## The Three Most Important Workflows

If time runs short, master these three:

### 1. Profile Ingestion

Entry:

- `POST /api/v1/agents/profile/run`

Main code:

- [backend/app/langgraph_agents.py](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/backend/app/langgraph_agents.py:657>)

What happens:

- load document
- extract structured profile with AI
- normalize fields
- save profile records and evidence

### 2. Email Triage

Entry:

- `POST /api/v1/agents/emails/{email_id}/triage`

Main code:

- [backend/app/langgraph_agents.py](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/backend/app/langgraph_agents.py:669>)

What happens:

- load email
- classify with cheap model first
- escalate to stronger model when needed
- persist category and action hints
- sync next actions if linked to an application

### 3. CV Tailoring

Entry:

- `POST /api/v1/jobs/{job_id}/cv-tailoring-plan`

Main code:

- [backend/app/cv_tailoring.py](</mnt/c/Users/Jdela/OneDrive - University of South Florida/Documentos/New project/backend/app/cv_tailoring.py:681>)

What happens:

- require completed job description
- require a scored job
- use verified profile evidence only
- create a plan with `do_not_claim` guardrails
- require approval before final downstream use

## What Makes This Project Technically Good

These are the ideas worth repeating in an interview:

- It separates orchestration from model inference.
- It uses structured outputs instead of raw text.
- It stores evidence and audit logs.
- It uses model routing for cost control.
- It blocks risky autonomous actions.
- It combines rules, retrieval, and LLMs instead of overusing a single technique.

## What You Can Ignore On The First Pass

Skip deep detail on your first 4-5 hour pass:

- every Alembic migration
- every frontend component
- every test file
- Gmail OAuth setup details
- deployment and packaging

Those are second-pass topics.

## Final Self-Test

If you can answer these from memory, the crash course worked:

1. What are the main runtime components?
2. Where do frontend requests go first?
3. Where are the agents orchestrated?
4. How is profile data validated before saving?
5. How does the system prevent unsupported CV claims?
6. Where do next actions come from?
7. Why does this project use `pgvector`?

## Optional Second Pass

If you have another 2-3 hours later, do this:

- skim `backend/tests`
- inspect `frontend/src/App.tsx` and major UI sections
- open `/docs` in FastAPI and map 10 important endpoints to backend functions
- write your own one-page architecture summary
