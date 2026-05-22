from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, joinedload, selectinload

from app.audit import write_audit_log
from app.job_description_state import description_quality_for_text
from app.job_controls import suppress_job_and_raw_variants
from app.models import (
    Action,
    Application,
    ApplicationStatus,
    ApplicationStatusCheckEvent,
    CVVersion,
    Company,
    Email,
    Job,
    JobScore,
    MessageDraft,
    PortalCredential,
    RawJob,
)
from app.schemas import ApplicationCreate, ApplicationUpdate, JobCreate
from app.text_normalization import normalize_display_text


def get_or_create_company(db: Session, name: str) -> Company:
    normalized_name = normalize_display_text(name, fallback=name.strip()) or name.strip()
    company = db.scalar(select(Company).where(Company.name == normalized_name))
    if company:
        return company

    company = Company(name=normalized_name)
    db.add(company)
    db.flush()
    write_audit_log(
        db,
        event_type="company.created",
        entity_type="company",
        entity_id=company.id,
        details={"name": company.name},
    )
    return company


def create_job(db: Session, payload: JobCreate) -> Job:
    company = get_or_create_company(db, payload.company_name)
    description = normalize_display_text(payload.description, fallback=payload.description) or payload.description
    description_quality = description_quality_for_text(description)
    resolved_description = description if description_quality in {"medium", "high"} else None
    if payload.source in {"greenhouse", "lever", "ashby"} and resolved_description:
        description_status = "resolved_from_ats"
        description_source = payload.source
        fetch_status = "success"
        resolution_confidence = 1.0
        resolution_notes = "Description came from the public ATS discovery payload."
    elif payload.source in {"manual", "manual_job_description"} and resolved_description:
        description_status = "manually_provided"
        description_source = "manual_paste"
        fetch_status = "success"
        resolution_confidence = 1.0 if description_quality == "high" else 0.8
        resolution_notes = "Description was provided manually."
    else:
        description_status = "missing"
        description_source = None
        fetch_status = "pending"
        resolution_confidence = None
        resolution_notes = None
    job = Job(
        company_id=company.id,
        title=normalize_display_text(payload.title, fallback=payload.title.strip()) or payload.title.strip(),
        source=payload.source,
        source_url=str(payload.source_url) if payload.source_url else None,
        location=normalize_display_text(payload.location),
        work_mode=normalize_display_text(payload.work_mode),
        seniority=normalize_display_text(payload.seniority),
        description=description,
        posted_at=payload.posted_at,
        application_deadline=payload.application_deadline,
        availability_status=payload.availability_status,
        availability_reason=payload.availability_reason,
        description_status=description_status,
        description_quality=description_quality if resolved_description else "unknown",
        description_source=description_source,
        fetch_status=fetch_status,
        resolved_description=resolved_description,
        resolved_description_url=str(payload.source_url) if payload.source_url and resolved_description else None,
        resolution_confidence=resolution_confidence,
        resolution_notes=resolution_notes,
        raw_payload=payload.model_dump(mode="json"),
    )
    db.add(job)
    db.flush()
    write_audit_log(
        db,
        event_type="job.created",
        entity_type="job",
        entity_id=job.id,
        details={"title": job.title, "company": company.name, "source": job.source},
    )
    db.commit()
    db.refresh(job)
    return job


def list_jobs(db: Session) -> list[Job]:
    statement = (
        select(Job)
        .options(joinedload(Job.company), selectinload(Job.raw_jobs), selectinload(Job.applications))
        .order_by(Job.created_at.desc())
    )
    jobs = list(db.scalars(statement))
    for job in jobs:
        _normalize_job_for_display(job)
    return [job for job in jobs if not _has_applied_application(job)]


def _has_applied_application(job: Job) -> bool:
    return any(application.status == ApplicationStatus.APPLIED for application in job.applications)


def get_job(db: Session, job_id: UUID) -> Job | None:
    statement = select(Job).options(joinedload(Job.company), selectinload(Job.raw_jobs)).where(Job.id == job_id)
    job = db.scalar(statement)
    if job:
        _normalize_job_for_display(job)
    return job


def delete_job(db: Session, job_id: UUID) -> dict[str, str] | None:
    statement = select(Job).options(joinedload(Job.company), selectinload(Job.raw_jobs)).where(Job.id == job_id)
    job = db.scalar(statement)
    if not job:
        return None

    suppress_job_and_raw_variants(db, job, reason="Removed by the user from the workspace.")

    application_ids = list(db.scalars(select(Application.id).where(Application.job_id == job_id)))
    if application_ids:
        db.execute(
            update(Email).where(Email.application_id.in_(application_ids)).values(application_id=None)
        )
        db.execute(delete(Action).where(Action.application_id.in_(application_ids)))
        db.execute(delete(Application).where(Application.id.in_(application_ids)))

    db.execute(delete(JobScore).where(JobScore.job_id == job_id))
    db.execute(delete(MessageDraft).where(MessageDraft.job_id == job_id))
    db.execute(delete(CVVersion).where(CVVersion.job_id == job_id))
    db.execute(delete(RawJob).where(RawJob.normalized_job_id == job_id))

    deleted_job = {
        "deleted_job_id": str(job.id),
        "title": job.title,
        "company": job.company.name if job.company else "Unknown company",
    }
    write_audit_log(
        db,
        event_type="job.deleted",
        entity_type="job",
        entity_id=job.id,
        details=deleted_job,
    )
    db.delete(job)
    db.commit()
    return deleted_job


def _normalize_job_for_display(job: Job) -> None:
    job.title = normalize_display_text(job.title, fallback=job.title) or job.title
    job.location = normalize_display_text(job.location)
    job.work_mode = normalize_display_text(job.work_mode)
    job.seniority = normalize_display_text(job.seniority)
    job.description = normalize_display_text(job.description, fallback=job.description) or job.description
    if job.company:
        job.company.name = normalize_display_text(job.company.name, fallback=job.company.name) or job.company.name


def create_application(db: Session, payload: ApplicationCreate) -> Application | None:
    job = db.get(Job, payload.job_id)
    if not job:
        return None

    application = Application(job_id=payload.job_id, status=payload.status, notes=payload.notes)
    db.add(application)
    db.flush()
    write_audit_log(
        db,
        event_type="application.created",
        entity_type="application",
        entity_id=application.id,
        details={"job_id": str(application.job_id), "status": application.status},
    )
    db.commit()
    db.refresh(application)
    return application


def list_applications(db: Session) -> list[Application]:
    statement = select(Application).order_by(Application.created_at.desc())
    return list(db.scalars(statement))


def update_application(db: Session, application_id: UUID, payload: ApplicationUpdate) -> Application | None:
    application = db.get(Application, application_id)
    if not application:
        return None

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(application, field, value)

    write_audit_log(
        db,
        event_type="application.updated",
        entity_type="application",
        entity_id=application.id,
        details=changes,
    )
    db.commit()
    db.refresh(application)
    return application


def delete_application(db: Session, application_id: UUID) -> dict[str, str] | None:
    application = db.get(Application, application_id)
    if not application:
        return None

    db.execute(update(Email).where(Email.application_id == application_id).values(application_id=None))
    db.execute(delete(Action).where(Action.application_id == application_id))
    db.execute(delete(PortalCredential).where(PortalCredential.application_id == application_id))
    db.execute(delete(ApplicationStatusCheckEvent).where(ApplicationStatusCheckEvent.application_id == application_id))

    deleted_application = {
        "deleted_application_id": str(application.id),
        "job_id": str(application.job_id),
        "status": str(application.status),
    }
    write_audit_log(
        db,
        event_type="application.deleted",
        entity_type="application",
        entity_id=application.id,
        details=deleted_application,
    )
    db.delete(application)
    db.commit()
    return deleted_application
