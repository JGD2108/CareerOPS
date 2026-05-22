# Agent evaluation harness

Use this folder to keep the golden sets for the agent improvement plan.

## Run the baseline

```powershell
cd backend
.\.venv\Scripts\python.exe scripts/evaluate_agents.py
```

## Write a JSON report

```powershell
cd backend
.\.venv\Scripts\python.exe scripts/evaluate_agents.py --output evals/agent_report.json
```

The current Day 1 harness evaluates inbox triage against a small golden set and
tracks profile extraction samples for the next step.

## Run the LangGraph profile evaluator

This is optional and uses the OpenAI API key configured for the local backend.

```powershell
cd backend
.\.venv\Scripts\python.exe scripts/evaluate_agents.py --run-profile-ai
```

That report adds:

- profile extraction overall score
- evidence coverage
- skill recall
- project recall
- communication-style recall
- work-preferences recall
