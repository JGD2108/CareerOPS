from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.audit import write_audit_log
from app.models import (
    Application,
    ApplicationStatus,
    CVVersion,
    CVVersionStatus,
    Email,
    EmailCategory,
    Job,
    JobScore,
    MessageDraft,
    MessageDraftStatus,
)


TERMINAL_APPLICATION_STATUSES = {
    ApplicationStatus.APPLIED,
    ApplicationStatus.RECRUITER_REPLIED,
    ApplicationStatus.INTERVIEW,
    ApplicationStatus.ASSESSMENT,
    ApplicationStatus.REJECTED,
    ApplicationStatus.OFFER,
}


def get_application(db: Session, application_id: UUID) -> Application | None:
    return db.scalar(
        select(Application)
        .options(joinedload(Application.job).joinedload(Job.company))
        .where(Application.id == application_id)
    )


def list_application_artifact_state(db: Session, job_id: UUID) -> dict:
    has_score = db.scalar(select(JobScore.id).where(JobScore.job_id == job_id).limit(1)) is not None
    approved_cv = db.scalar(
        select(CVVersion.id)
        .where(CVVersion.job_id == job_id, CVVersion.status == CVVersionStatus.APPROVED)
        .limit(1)
    )
    approved_message_count = db.scalar(
        select(MessageDraft.id)
        .where(MessageDraft.job_id == job_id, MessageDraft.status == MessageDraftStatus.APPROVED)
        .limit(1)
    )
    return {
        "has_score": has_score,
        "has_approved_cv": approved_cv is not None,
        "has_approved_message": approved_message_count is not None,
    }


def build_application_summary(application: Application, artifact_state: dict) -> dict:
    ready_to_apply = artifact_state["has_score"] and artifact_state["has_approved_cv"] and artifact_state["has_approved_message"]
    next_steps = []
    current_action = "Keep building the application package."

    if not artifact_state["has_score"]:
        next_steps.append("Score the job against the candidate profile.")
        current_action = "Score this job before deciding whether to pursue it."
    if not artifact_state["has_approved_cv"]:
        next_steps.append("Approve a tailored CV version for this job.")
        current_action = "Review and approve a tailored CV for this role."
    if not artifact_state["has_approved_message"]:
        next_steps.append("Approve at least one recruiter/application message draft.")
        current_action = "Review and approve at least one message draft."
    if ready_to_apply and application.status not in TERMINAL_APPLICATION_STATUSES:
        next_steps.append("Application is ready for manual submission.")
        current_action = "Submit the application manually, then mark it as applied."
    if application.status == ApplicationStatus.APPLIED:
        current_action = "Monitor recruiter replies and follow up if needed."
    elif application.status == ApplicationStatus.RECRUITER_REPLIED:
        current_action = "Reply to the recruiter and update the tracker with the outcome."
    elif application.status == ApplicationStatus.INTERVIEW:
        current_action = "Prepare for the interview and track scheduling details."
    elif application.status == ApplicationStatus.ASSESSMENT:
        current_action = "Complete the assessment before the deadline."
    elif application.status == ApplicationStatus.REJECTED:
        current_action = "Archive the application and capture lessons learned."
    elif application.status == ApplicationStatus.OFFER:
        current_action = "Review the offer details and record your decision."

    return {
        "application_id": application.id,
        "job_id": application.job_id,
        "status": application.status,
        "job_title": application.job.title if application.job else None,
        "company_name": application.job.company.name if application.job and application.job.company else None,
        "artifact_state": artifact_state,
        "ready_to_apply": ready_to_apply,
        "current_action": current_action,
        "next_steps": next_steps,
        "notes": application.notes,
        "applied_at": application.applied_at,
        "created_at": application.created_at,
        "updated_at": application.updated_at,
    }


def sync_application_status(db: Session, application_id: UUID) -> Application | None:
    application = get_application(db, application_id)
    if not application:
        return None
    if application.status in TERMINAL_APPLICATION_STATUSES and application.status != ApplicationStatus.REJECTED:
        return application

    artifact_state = list_application_artifact_state(db, application.job_id)
    new_status = application.status
    has_linked_rejection = (
        db.scalar(
            select(Email.id).where(
                Email.application_id == application.id,
                Email.category == EmailCategory.REJECTION,
            ).limit(1)
        )
        is not None
    )
    if application.status == ApplicationStatus.REJECTED and has_linked_rejection:
        return application
    if application.status == ApplicationStatus.REJECTED and application.applied_at:
        new_status = ApplicationStatus.APPLIED
    if artifact_state["has_approved_cv"]:
        new_status = ApplicationStatus.CV_GENERATED
    elif artifact_state["has_score"]:
        new_status = ApplicationStatus.REVIEWED
    else:
        new_status = ApplicationStatus.FOUND
    if application.applied_at:
        new_status = ApplicationStatus.APPLIED

    if new_status != application.status:
        previous_status = application.status
        application.status = new_status
        write_audit_log(
            db,
            event_type="application.synced",
            entity_type="application",
            entity_id=application.id,
            details={"previous_status": previous_status, "new_status": new_status},
        )
        db.commit()
        db.refresh(application)
    return application


def mark_application_applied(
    db: Session,
    application_id: UUID,
    notes: str | None = None,
    applied_at: datetime | None = None,
) -> Application | None:
    application = get_application(db, application_id)
    if not application:
        return None

    previous_status = application.status
    application.status = ApplicationStatus.APPLIED
    new_applied_at = applied_at or datetime.now(timezone.utc)
    if application.applied_at:
        application.applied_at = min(application.applied_at, new_applied_at)
    else:
        application.applied_at = new_applied_at
    if notes:
        application.notes = notes

    write_audit_log(
        db,
        event_type="application.marked_applied",
        entity_type="application",
        entity_id=application.id,
        details={
            "previous_status": previous_status,
            "new_status": application.status,
            "applied_at": application.applied_at.isoformat(),
        },
    )
    db.commit()
    db.refresh(application)
    return application
