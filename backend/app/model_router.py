from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ModelUsageLog


CHEAP_TASKS = {"status_classification", "extraction", "summarization", "duplicate_detection"}
STRONG_TASKS = {"ambiguous_status_interpretation", "recruiter_message", "complex_next_action"}


def model_for_task(task_type: str) -> str:
    settings = get_settings()
    if task_type in CHEAP_TASKS:
        return settings.openai_job_model
    if task_type in STRONG_TASKS:
        return settings.openai_model
    return settings.openai_job_model


def estimate_model_cost(model: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
    if input_tokens is None and output_tokens is None:
        return None
    total_tokens = (input_tokens or 0) + (output_tokens or 0)
    if total_tokens <= 0:
        return None
    # Conservative local estimate only; actual billing should come from provider usage where available.
    per_million = 0.05 if "nano" in model else 0.25 if "mini" in model else 1.00
    return round((total_tokens / 1_000_000) * per_million, 6)


def log_model_usage(
    db: Session,
    *,
    task_type: str,
    model: str,
    agent_run_id: UUID | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> ModelUsageLog:
    record = ModelUsageLog(
        agent_run_id=agent_run_id,
        task_type=task_type,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost=estimate_model_cost(model, input_tokens, output_tokens),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
