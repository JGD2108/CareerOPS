# AI Agents Improvement Plan (2 weeks)

## Goal
Improve the current agent system without losing the existing strengths: LangGraph orchestration, local-first operation, human-in-the-loop review, and traceable outputs.

## Priorities
1. Inbox triage precision
2. Candidate profile reliability
3. Job fit quality and explainability
4. CV tailoring honesty and evidence quality
5. Job discovery filtering and deduplication

## Constraints
- Keep LangGraph.
- Keep semi-automatic review for risky actions.
- Minimize API cost.
- Preserve traceability for every model-generated claim.
- Prefer local-first workflows and deterministic fallbacks.

## Success metrics
- Inbox triage precision for job-related emails >= 90%
- False positive rate for non-job emails <= 5%
- Profile extraction evidence coverage >= 95%
- Job fit explanations backed by evidence for all scored jobs
- CV tailoring plans rejected for unsupported claims = 0
- Job discovery duplicate rate <= 3%
- Average model calls per workflow reduced week over week

## Week 1 — Stabilize and measure

### Day 1 — Baseline and evaluation harness
- Define labeled samples for inbox triage, profile extraction, job fit, and CV tailoring.
- Create a small golden set of real examples with expected outputs.
- Add an evaluation script that scores precision, recall, evidence coverage, and cost per run.
- Acceptance: the same dataset can be re-run locally and produces a repeatable report.

### Day 1 — Results (run)
- Evaluation artifacts: `backend/evals/agent_report.json` and captures in `backend/evals/captures/`.
- Inbox triage: 12 samples — precision 1.0, recall 1.0, category accuracy 1.0 on the golden set.
- Profile extraction: 4 samples processed (dataset-only; predictions captured for later comparison).
 - Evaluation artifacts: `backend/evals/agent_report.json` and captures in `backend/evals/captures/`.
 - Inbox triage: 12 samples — precision 1.0, recall 1.0, category accuracy 1.0 on the golden set.
 - Profile extraction: 4 samples processed (dataset-only; predictions captured for later comparison).
 - Model capture summary (latest run): 166 model calls captured, estimated total tokens ~758,559 (captures stored under `evals/captures/`).
 - Deterministic reclassification: processed 100 recent unlinked emails and updated 31 records (fast, zero-cost cleanup).
 - LLM triage run: triaged 50 recent unlinked emails (captures created); sample captures show LinkedIn digests classified as `other` with reasoning.
 - Tests: backend test suite passed locally (15 tests).

### Day 2 — Inbox triage hardening
- Split inbox routing into explicit categories: job, application, recruiter, follow-up, noise.
- Add stronger negative rules for LinkedIn alerts, newsletters, promotions, and generic notifications.
- Keep LinkedIn job alerts out of the user inbox unless they map to an actual application workflow.
- Acceptance: inbox triage returns only job/application-related emails on the golden set.

### Day 3 — Inbox observability
- Add structured logs for triage decisions, confidence, evidence, and final route.
- Store a lightweight audit trail for every rejected or downgraded email.
- Add a small dashboard or API endpoint for recent triage outcomes.
- Acceptance: every inbox decision can be explained from stored evidence.

### Day 4 — Profile ingestion guardrails
- Separate raw extraction from normalized profile facts.
- Require source-backed evidence for skills, roles, tools, and achievements.
- Add a reject/flag state for unsupported profile claims.
- Acceptance: profile facts can be traced back to a source snippet.

### Day 5 — Job fit scoring cleanup
- Make scoring explainable with explicit factors: match, gap, seniority, location, work mode.
- Add a deterministic fallback scorer when the model is uncertain.
- Record why a job was scored high or low.
- Acceptance: every score includes a stable reason list and evidence links.

## Week 2 — Improve quality and rollout safety

### Day 6 — CV tailoring constraints
- Enforce no-new-facts policy in tailoring.
- Require evidence for every rewritten bullet and summary claim.
- Add a hard stop when required evidence is missing.
- Acceptance: tailoring plans never invent experience or skills.

### Day 7 — Message drafting quality
- Standardize templates for recruiter replies, application emails, and follow-ups.
- Add tone controls: concise, formal, friendly, or assertive.
- Keep drafts short and aligned to the candidate profile.
- Acceptance: drafts are review-ready and consistent across the same input class.

### Day 8 — Job discovery filtering
- Tighten source normalization and deduplication rules.
- Improve keyword, location, seniority, and work-mode filtering.
- Add a second-pass dedupe check before saving new jobs.
- Acceptance: duplicate and irrelevant discovered jobs drop measurably.

### Day 9 — Human review workflow
- Add explicit approval gates for profile edits, CV changes, and outgoing messages.
- Surface evidence and model rationale in the review UI.
- Add a clear reject path with reasons.
- Acceptance: reviewers can approve or reject without opening raw logs.

### Day 10 — Rollout and validation
- Run the evaluation harness on the golden set.
- Compare cost, precision, and evidence coverage against baseline.
- Fix regressions before enabling the new routing or scoring behavior by default.
- Acceptance: report shows measurable improvement with no critical regressions.

## Recommended implementation order
1. Inbox triage
2. Profile ingestion
3. Job fit
4. CV tailoring
5. Job discovery
6. Message drafting

## Engineering rules
- Prefer deterministic filters before model calls.
- Cache repeated lookups and embeddings.
- Keep prompts small and task-specific.
- Use structured outputs everywhere possible.
- Log evidence IDs, not just free text.
- Keep approval gates for high-impact actions.

## Deliverables at the end of 2 weeks
- A repeatable evaluation harness.
- Better inbox precision and fewer false positives.
- More reliable profile facts.
- Better job fit explanations.
- Safer CV tailoring and message generation.
- Cleaner job discovery and deduplication.
- Reviewable audit trails for the major agents.
