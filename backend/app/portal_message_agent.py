from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.model_router import log_model_usage, model_for_task
from app.models import Application, CandidateProfile, MessageDraft, MessageDraftStatus, MessageDraftType
from app.profile_ingestion import get_profile


def _profile_experience_line(profile: CandidateProfile | None) -> str:
    if not profile or not profile.experiences:
        return "my background in software and data work"
    experience = profile.experiences[0]
    title = experience.title or "software/data"
    company = experience.company or "previous teams"
    return f"my experience as {title} at {company}"


def _interest_reason(application: Application) -> str:
    job = application.job
    if not job:
        return "the role appears aligned with my background"
    source_text = " ".join(
        str(part)
        for part in (
            job.title,
            job.description[:600] if job.description else "",
            job.work_mode,
            job.seniority,
        )
        if part
    ).lower()
    if "data" in source_text:
        return "the opportunity to work on data quality, pipelines, and reliable analytics"
    if "backend" in source_text or "api" in source_text:
        return "the opportunity to build reliable backend systems and APIs"
    if "ai" in source_text or "machine learning" in source_text:
        return "the opportunity to apply AI engineering in a practical product context"
    return "the role's alignment with my technical background and growth goals"


def generate_portal_follow_up_draft(db: Session, application_id: UUID) -> MessageDraft | None:
    application = db.get(Application, application_id)
    if not application or not application.job:
        return None

    profile = get_profile(db)
    if not profile:
        raise ValueError("Candidate profile not found. Build the profile before drafting recruiter follow-ups.")

    company_name = application.company_name or application.job.company.name if application.job.company else "your team"
    role_title = application.job_title or application.job.title
    subject = f"Following up on {role_title}"
    body = (
        f"Hi {company_name} team,\n\n"
        f"I hope you are doing well. I wanted to briefly follow up on my application for the {role_title} role. "
        f"I am especially interested in { _interest_reason(application) }, and I believe { _profile_experience_line(profile) } "
        "could be useful for the hiring team.\n\n"
        "Could you let me know whether the role is still active or if there is any update on the hiring process?\n\n"
        "Best,\n"
        f"{profile.display_name or 'Jose'}"
    )

    draft = MessageDraft(
        job_id=application.job_id,
        candidate_profile_id=profile.id,
        cv_version_id=None,
        draft_type=MessageDraftType.FOLLOW_UP,
        status=MessageDraftStatus.DRAFT,
        subject=subject,
        body=body,
        tone="natural-professional",
        language="english",
        evidence=[
            {
                "source": "portal_status_checker",
                "application_id": str(application.id),
                "latest_portal_status": application.latest_portal_status or "UNKNOWN",
            }
        ],
        approval_required=True,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    model = model_for_task("recruiter_message")
    log_model_usage(
        db,
        task_type="recruiter_message",
        model=model,
        input_tokens=0,
        output_tokens=len(body.split()),
    )
    return draft
