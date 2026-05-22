from __future__ import annotations

from app.models import Job


INCOMPLETE_DESCRIPTION_STATUSES = {"missing", "partial_from_email", "failed"}
COMPLETE_DESCRIPTION_STATUSES = {
    "resolved_from_ats",
    "resolved_from_company_site",
    "manually_provided",
    "manually_provided_url",
}
PARTIAL_LINKEDIN_NOTES = "LinkedIn Gmail alert contains partial metadata only."


def description_text_for_analysis(job: Job) -> str:
    return job.resolved_description or job.description or ""


def description_is_complete(job: Job) -> bool:
    if job.description_status in COMPLETE_DESCRIPTION_STATUSES:
        return bool((job.resolved_description or job.description or "").strip())
    if job.description_status in INCOMPLETE_DESCRIPTION_STATUSES:
        return False
    return bool((job.resolved_description or job.description or "").strip()) and len(
        (job.resolved_description or job.description or "").strip()
    ) >= 300


def incomplete_description_reason(job: Job) -> str:
    if job.fetch_status == "needs_manual_review":
        return "This job needs manual review before final scoring. Accept a resolver candidate, add an official public job URL, or paste the full official job description."
    if job.description_status == "partial_from_email":
        return "This job only has partial metadata from a LinkedIn email alert. Add an official public job URL or paste the full official description before final scoring, CV tailoring, or message drafting."
    if job.description_status == "failed":
        return "Job description resolution failed. Retry the resolver, add an official public job URL, or paste the full official job description."
    return "This job does not have a complete resolved job description yet."


def description_quality_for_text(text: str) -> str:
    cleaned = text.strip()
    if len(cleaned) >= 300:
        return "high"
    if len(cleaned) >= 120:
        return "medium"
    return "low"
