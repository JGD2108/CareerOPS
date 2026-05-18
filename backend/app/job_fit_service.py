from sqlalchemy.orm import Session

from app import crud
from app.models import ApplicationStatus
from app.schemas import ApplicationCreate, JobFitAnalyzeRequest
from app.job_fit import score_job_fit


def analyze_manual_job(db: Session, payload: JobFitAnalyzeRequest) -> dict:
    job = crud.create_job(db, payload)
    score = score_job_fit(db, job.id)
    application = None

    if payload.create_application:
        application = crud.create_application(
            db,
            ApplicationCreate(
                job_id=job.id,
                status=ApplicationStatus.FOUND,
                notes="Created from one-step job fit analysis.",
            ),
        )

    return {
        "job": job,
        "score": score,
        "application": application,
    }
