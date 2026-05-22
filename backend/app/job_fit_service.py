import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import crud
from app.models import ApplicationStatus
from app.schemas import (
    ApplicationCreate,
    JobCreate,
    JobDescriptionIngestRequest,
    JobDescriptionUpdateRequest,
    JobFitAnalyzeRequest,
)
from app.job_fit import score_job_fit
from app.job_description_state import description_quality_for_text


_TITLE_LABEL_RE = re.compile(
    r"^\s*(?:job\s*title|title|role|position|cargo|puesto|posici[oó]n|vacante)\s*[:\-]\s*(?P<value>.+)$",
    re.IGNORECASE,
)
_COMPANY_LABEL_RE = re.compile(
    r"^\s*(?:company|empresa|organizaci[oó]n|compa[nñ][ií]a)\s*[:\-]\s*(?P<value>.+)$",
    re.IGNORECASE,
)
_LOCATION_LABEL_RE = re.compile(
    r"^\s*(?:location|ubicaci[oó]n|lugar|sede)\s*[:\-]\s*(?P<value>.+)$",
    re.IGNORECASE,
)
_WORK_MODE_RE = re.compile(r"\b(remote|hybrid|onsite|remoto|h[ií]brido|presencial)\b", re.IGNORECASE)


def _clean_inferred_value(value: str | None, *, fallback: str) -> str:
    if not value:
        return fallback
    value = re.sub(r"\s+", " ", value).strip(" -:|")
    return value[:255] if value else fallback


def _is_likely_heading(line: str) -> bool:
    lowered = line.strip().lower()
    if len(line) < 4 or len(line) > 140:
        return False
    rejected = {
        "about us",
        "about the job",
        "job description",
        "description",
        "responsibilities",
        "requirements",
        "qualifications",
        "sobre nosotros",
        "descripción",
        "descripcion",
        "responsabilidades",
        "requisitos",
    }
    if lowered in rejected:
        return False
    return bool(re.search(r"[a-záéíóúñ]", lowered))


def _infer_job_fields(payload: JobDescriptionIngestRequest | JobDescriptionUpdateRequest) -> dict[str, str | None]:
    title = payload.title
    company_name = payload.company_name
    location = payload.location
    work_mode = payload.work_mode

    lines = [line.strip() for line in payload.description.splitlines() if line.strip()]
    for line in lines[:35]:
        if not title:
            title_match = _TITLE_LABEL_RE.match(line)
            if title_match:
                title = title_match.group("value")
        if not company_name:
            company_match = _COMPANY_LABEL_RE.match(line)
            if company_match:
                company_name = company_match.group("value")
        if not location:
            location_match = _LOCATION_LABEL_RE.match(line)
            if location_match:
                location = location_match.group("value")
        if not work_mode:
            work_mode_match = _WORK_MODE_RE.search(line)
            if work_mode_match:
                work_mode = work_mode_match.group(1)

    if not title:
        title = next((line for line in lines[:12] if _is_likely_heading(line)), None)

    return {
        "title": _clean_inferred_value(title, fallback="Manual job description"),
        "company_name": _clean_inferred_value(company_name, fallback="Company not specified"),
        "location": _clean_inferred_value(location, fallback="") or None,
        "work_mode": _clean_inferred_value(work_mode, fallback="") or None,
    }


def _reply_info(job_title: str, company_name: str) -> str:
    if company_name.lower() in {"company not specified", "unknown company", "manual job description"}:
        company_name = "your team"
    return (
        f"Hi, I found the {job_title} role at {company_name} and wanted to reach out directly.\n\n"
        "My background is strongest in backend/API development, data workflows, and AI-enabled products. "
        "I am tailoring my CV to the role description and would appreciate the chance to share it or learn who the best contact is.\n\n"
        "Best,\n"
        "Jose David Gomez"
    )


def _looks_spanish(text: str) -> bool:
    lowered = text.lower()
    spanish_markers = (
        "ingeniero",
        "desarrollador",
        "empresa",
        "requisitos",
        "responsabilidades",
        "experiencia en",
        "modalidad",
        "ubicación",
        "remoto",
        "híbrido",
        "postulación",
    )
    return sum(1 for marker in spanish_markers if marker in lowered) >= 2


def _reply_info_for_description(job_title: str, company_name: str, description: str) -> str:
    if company_name.lower() in {"company not specified", "unknown company", "manual job description"}:
        company_name = "el equipo" if _looks_spanish(description) else "your team"
    if _looks_spanish(description):
        return (
            f"Hola equipo de reclutamiento de {company_name},\n\n"
            f"Ya apliqué a la vacante de {job_title} y quería dar seguimiento a mi postulación. "
            "Quería preguntar si hay algún siguiente paso recomendado o información adicional que pueda compartir para fortalecer mi candidatura.\n\n"
            "Si hay alguna habilidad, proyecto o evidencia concreta que les gustaría revisar para diferenciar mi perfil, con gusto la preparo.\n\n"
            "Saludos,\n"
            "Jose David Gomez"
        )
    return (
        f"Hi {company_name} recruiting team,\n\n"
        f"I already applied for the {job_title} role and wanted to follow up on my application. "
        "Could you let me know if there are any recommended next steps or additional information I can share to strengthen my candidacy?\n\n"
        "If there is a specific skill, project, or evidence you would like me to emphasize to differentiate my profile, I would be glad to prepare it.\n\n"
        "Best,\n"
        "Jose David Gomez"
    )


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


def ingest_job_description(db: Session, payload: JobDescriptionIngestRequest) -> dict:
    inferred = _infer_job_fields(payload)
    job_payload = JobCreate(
        title=str(inferred["title"]),
        company_name=str(inferred["company_name"]),
        description=payload.description,
        source="manual_job_description",
        source_url=payload.source_url,
        location=payload.location or inferred["location"],
        work_mode=payload.work_mode or inferred["work_mode"],
        seniority=payload.seniority,
    )
    job = crud.create_job(db, job_payload)
    score = score_job_fit(db, job.id)
    application = None

    if payload.create_application:
        application = crud.create_application(
            db,
            ApplicationCreate(
                job_id=job.id,
                status=ApplicationStatus.FOUND,
                notes="Created from pasted job description.",
            ),
        )

    return {
        "job": job,
        "score": score,
        "application": application,
        "reply_info": _reply_info_for_description(
            job.title,
            job.company.name if job.company else str(inferred["company_name"]),
            payload.description,
        ),
    }


def update_job_from_description(db: Session, job_id, payload: JobDescriptionUpdateRequest) -> dict | None:
    job = crud.get_job(db, job_id)
    if not job:
        return None

    inferred = _infer_job_fields(payload)
    inferred_company_name = str(inferred["company_name"])
    should_replace_company = inferred_company_name.lower() != "company not specified"
    job.title = str(inferred["title"])
    if should_replace_company:
        job.company = crud.get_or_create_company(db, inferred_company_name)
    job.description = payload.description
    job.resolved_description = payload.description
    job.resolved_description_url = str(payload.source_url) if payload.source_url else job.source_url
    job.resolved_description_html = None
    job.description_status = "manually_provided"
    job.description_quality = description_quality_for_text(payload.description)
    job.description_source = "manual_paste"
    job.fetch_status = "success"
    job.resolution_confidence = 1.0 if job.description_quality == "high" else 0.8
    job.resolution_notes = "Full job description pasted manually by the user."
    job.resolved_at = datetime.now(timezone.utc)
    if payload.source_url:
        job.source_url = str(payload.source_url)
    if payload.location or inferred["location"]:
        job.location = payload.location or inferred["location"]
    if payload.work_mode or inferred["work_mode"]:
        job.work_mode = payload.work_mode or inferred["work_mode"]
    if payload.seniority:
        job.seniority = payload.seniority
    job.raw_payload = {
        **(job.raw_payload or {}),
        "description": payload.description,
        "title": job.title,
        "company_name": job.company.name if job.company else inferred_company_name,
        "source_url": str(payload.source_url) if payload.source_url else job.source_url,
        "updated_from_application_description": True,
    }
    db.commit()
    db.refresh(job)

    score = score_job_fit(db, job.id) if payload.rescore else None
    return {
        "job": job,
        "score": score,
        "application": None,
        "reply_info": _reply_info_for_description(
            job.title,
            job.company.name if job.company else inferred_company_name,
            payload.description,
        ),
    }
