from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.audit import write_audit_log
from app.job_description_state import description_is_complete, incomplete_description_reason
from app.models import (
    CVVersion,
    CVVersionStatus,
    CandidateProfile,
    Job,
    JobScore,
    MessageDraft,
    MessageDraftStatus,
    MessageDraftType,
)
from app.profile_ingestion import get_profile


def _candidate_display_name(profile: CandidateProfile) -> str:
    if profile.display_name and profile.display_name.strip():
        return profile.display_name.strip()
    raise ValueError("Candidate profile display name is required before generating message drafts.")


def _latest_score(db: Session, job_id: UUID) -> JobScore | None:
    return db.scalar(select(JobScore).where(JobScore.job_id == job_id).order_by(JobScore.created_at.desc()))


def _approved_cv(db: Session, job_id: UUID) -> CVVersion | None:
    return db.scalar(
        select(CVVersion)
        .where(CVVersion.job_id == job_id, CVVersion.status == CVVersionStatus.APPROVED)
        .order_by(CVVersion.reviewed_at.desc().nullslast(), CVVersion.created_at.desc())
    )


def _company_name(job: Job) -> str:
    return job.company.name if job.company else "your team"


def _top_skills(score: JobScore, limit: int = 4) -> list[str]:
    seen = []
    for item in score.matched_skills:
        skill = item.get("profile_skill")
        if skill and skill.rstrip(".") not in seen:
            seen.append(skill.rstrip("."))
    return seen[:limit]


def _evidence(score: JobScore, limit: int = 5) -> list[dict]:
    return [
        {
            "claim": item.get("claim"),
            "source": item.get("source"),
            "evidence_text": item.get("evidence_text"),
        }
        for item in score.evidence[:limit]
    ]


def _linkedin_message(profile: CandidateProfile, job: Job, score: JobScore) -> tuple[str | None, str]:
    skills = ", ".join(_top_skills(score, 3))
    company = _company_name(job)
    body = (
        f"Hi, I saw the {job.title} role at {company} and it looks closely aligned with my backend and AI workflow work. "
        f"My recent experience includes {skills}, with production-oriented backend/API and automation projects. "
        "I put together a tailored CV draft for this role and would be glad to share it if useful. "
        "Thanks for your time."
    )
    return None, body


def _application_email(profile: CandidateProfile, job: Job, score: JobScore) -> tuple[str, str]:
    skills = ", ".join(_top_skills(score, 4))
    company = _company_name(job)
    candidate_name = _candidate_display_name(profile)
    subject = f"Application for {job.title} - {candidate_name}"
    body = (
        f"Hi {company} team,\n\n"
        f"I am applying for the {job.title} role. My background is strongest in backend/API development, data workflows, "
        f"and applied AI systems, with evidence in {skills}.\n\n"
        "I have prepared a tailored CV draft for this role based only on my verified project and experience history. "
        "I would be happy to provide any additional information.\n\n"
        "Best,\n"
        f"{candidate_name}"
    )
    return subject, body


def _short_cover_letter(profile: CandidateProfile, job: Job, score: JobScore) -> tuple[str, str]:
    skills = ", ".join(_top_skills(score, 5))
    company = _company_name(job)
    candidate_name = _candidate_display_name(profile)
    subject = f"Cover letter draft - {job.title}"
    body = (
        f"Dear {company} team,\n\n"
        f"I am interested in the {job.title} role because it connects with the work I have been building across backend systems, "
        f"data workflows, and AI-enabled products. My verified experience includes {skills}.\n\n"
        "In my recent work, I have focused on building practical systems: backend modules, database-backed workflows, API integrations, "
        "automation, and AI/data projects with traceable outputs. I am especially interested in roles where I can combine software engineering "
        "discipline with AI-assisted workflow design while keeping implementation reliable and well documented.\n\n"
        "Thank you for considering my application.\n\n"
        f"Sincerely,\n{candidate_name}"
    )
    return subject, body


def _render_message(draft_type: MessageDraftType, profile: CandidateProfile, job: Job, score: JobScore) -> tuple[str | None, str]:
    if draft_type == MessageDraftType.LINKEDIN:
        return _linkedin_message(profile, job, score)
    if draft_type == MessageDraftType.APPLICATION_EMAIL:
        return _application_email(profile, job, score)
    if draft_type == MessageDraftType.SHORT_COVER_LETTER:
        return _short_cover_letter(profile, job, score)
    raise ValueError(f"Draft type is not supported yet: {draft_type}")


def generate_message_drafts(
    db: Session,
    job_id: UUID,
    *,
    draft_types: list[MessageDraftType],
    tone: str,
    language: str,
) -> list[MessageDraft] | None:
    job = db.scalar(select(Job).options(joinedload(Job.company)).where(Job.id == job_id))
    profile = get_profile(db)
    score = _latest_score(db, job_id)
    approved_cv = _approved_cv(db, job_id)
    if not job or not profile or not score:
        return None
    if not description_is_complete(job):
        raise ValueError(incomplete_description_reason(job))
    if score.extracted_requirements.get("preliminary"):
        raise ValueError("Cannot generate final message drafts from a preliminary job score.")
    if not approved_cv:
        raise ValueError("An approved CV version is required before generating message drafts.")
    if language.lower() != "english":
        raise ValueError("Only English deterministic drafts are supported in this MVP.")

    drafts = []
    for draft_type in draft_types:
        subject, body = _render_message(draft_type, profile, job, score)
        draft = MessageDraft(
            job_id=job.id,
            candidate_profile_id=profile.id,
            cv_version_id=approved_cv.id,
            draft_type=draft_type,
            status=MessageDraftStatus.DRAFT,
            subject=subject,
            body=body,
            tone=tone,
            language=language,
            evidence=_evidence(score),
            approval_required=True,
        )
        db.add(draft)
        drafts.append(draft)

    db.flush()
    write_audit_log(
        db,
        event_type="message_drafts.generated",
        entity_type="job",
        entity_id=job.id,
        details={"draft_count": len(drafts), "cv_version_id": str(approved_cv.id)},
    )
    db.commit()
    for draft in drafts:
        db.refresh(draft)
    return drafts


def list_message_drafts(db: Session, job_id: UUID) -> list[MessageDraft]:
    return list(
        db.scalars(select(MessageDraft).where(MessageDraft.job_id == job_id).order_by(MessageDraft.created_at.desc()))
    )


def review_message_draft(
    db: Session,
    message_draft_id: UUID,
    *,
    status: MessageDraftStatus,
    review_notes: str | None = None,
) -> MessageDraft | None:
    draft = db.get(MessageDraft, message_draft_id)
    if not draft:
        return None
    if status not in {MessageDraftStatus.APPROVED, MessageDraftStatus.REJECTED}:
        raise ValueError("Message draft review status must be approved or rejected.")

    draft.status = status
    draft.review_notes = review_notes
    draft.reviewed_at = datetime.now(timezone.utc)
    write_audit_log(
        db,
        event_type="message_draft.reviewed",
        entity_type="message_draft",
        entity_id=draft.id,
        details={"status": status, "review_notes": review_notes},
    )
    db.commit()
    db.refresh(draft)
    return draft
