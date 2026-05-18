from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.audit import write_audit_log
from app.models import Application, Company, Job
from app.schemas import ApplicationCreate, ApplicationUpdate, JobCreate


def get_or_create_company(db: Session, name: str) -> Company:
    normalized_name = name.strip()
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
    job = Job(
        company_id=company.id,
        title=payload.title.strip(),
        source=payload.source,
        source_url=str(payload.source_url) if payload.source_url else None,
        location=payload.location,
        work_mode=payload.work_mode,
        seniority=payload.seniority,
        description=payload.description,
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
    statement = select(Job).options(joinedload(Job.company), selectinload(Job.raw_jobs)).order_by(Job.created_at.desc())
    return list(db.scalars(statement))


def get_job(db: Session, job_id: UUID) -> Job | None:
    statement = select(Job).options(joinedload(Job.company), selectinload(Job.raw_jobs)).where(Job.id == job_id)
    return db.scalar(statement)


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
