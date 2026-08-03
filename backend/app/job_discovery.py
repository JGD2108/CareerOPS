from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app import crud
from app.audit import write_audit_log
from app.job_availability import derive_availability_from_payload, extract_job_source_dates
from app.job_controls import is_excluded_company_name, is_job_dismissed
from app.job_fit import ensure_job_score
from app.models import Application, ApplicationStatus, Company, DiscoveryRun, DiscoverySource, Job, RawJob
from app.profile_ingestion import get_profile
from app.schemas import (
    ApplicationCreate,
    DiscoverySourceCreate,
    DiscoverySourceUpdate,
    JobCreate,
    JobDiscoveryFilters,
    JobDiscoverySourceConfig,
)


GREENHOUSE_BASE_URL = "https://boards-api.greenhouse.io/v1/boards"
LEVER_BASE_URL = "https://api.lever.co/v0/postings"
ASHBY_BASE_URL = "https://api.ashbyhq.com/posting-api/job-board"
SMARTRECRUITERS_BASE_URL = "https://api.smartrecruiters.com/v1/companies"
WORKDAY_BASE_URL = "https://{tenant}.wd5.myworkdayjobs.com/wday/cxs/{tenant}/jobs"


@dataclass
class NormalizedDiscoveredJob:
    source: str
    source_company_key: str
    external_job_id: str
    company_name: str
    title: str
    description: str
    location: str | None
    work_mode: str | None
    seniority: str | None
    job_url: str | None
    posted_at: datetime | None
    application_deadline: datetime | None
    availability_status: str
    availability_reason: str | None
    raw_payload: dict


def _normalize_text(value: str | None) -> str:
    return (value or "").strip().lower()


def _match_any(value: str, candidates: list[str]) -> bool:
    normalized_value = _normalize_text(value)
    if not candidates:
        return True
    return any(_normalize_text(candidate) in normalized_value for candidate in candidates)


def _derive_seniority(title: str, description: str) -> str | None:
    combined = f"{title} {description}".lower()
    if re.search(r"\b(intern|internship)\b", combined):
        return "Intern"
    if re.search(r"\b(junior|entry level|entry-level)\b", combined):
        return "Junior"
    if re.search(r"\bmid\b", combined):
        return "Mid"
    if re.search(r"\b(senior|staff|principal|lead)\b", combined):
        return "Senior+"
    return None


def _derive_work_mode(location: str | None, raw_value: str | None) -> str | None:
    combined = f"{location or ''} {raw_value or ''}".lower()
    if "hybrid" in combined:
        return "Hybrid"
    if "remote" in combined:
        return "Remote"
    if combined.strip():
        return "Onsite"
    return None


def _passes_filters(job: NormalizedDiscoveredJob, filters: JobDiscoveryFilters) -> bool:
    haystack = " ".join(
        [
            job.title,
            job.description,
            job.location or "",
            job.seniority or "",
            job.work_mode or "",
        ]
    )
    if filters.role_keywords and not _match_any(haystack, filters.role_keywords):
        return False
    if filters.locations and not _match_any(job.location or "", filters.locations):
        return False
    if filters.seniority_terms and not _match_any(job.seniority or haystack, filters.seniority_terms):
        return False
    if filters.work_modes and not _match_any(job.work_mode or "", filters.work_modes):
        return False
    return True


def _greenhouse_jobs(payload: dict, source_config: JobDiscoverySourceConfig) -> list[NormalizedDiscoveredJob]:
    jobs = []
    company_name = source_config.company_name_override or source_config.company_key
    for item in payload.get("jobs", []):
        description = item.get("content") or ""
        location_name = (item.get("location") or {}).get("name")
        posted_at, application_deadline = extract_job_source_dates(item)
        availability_status, availability_reason = derive_availability_from_payload(item, description)
        jobs.append(
            NormalizedDiscoveredJob(
                source="greenhouse",
                source_company_key=source_config.company_key,
                external_job_id=str(item.get("id")),
                company_name=company_name,
                title=item.get("title", "").strip(),
                description=description,
                location=location_name,
                work_mode=_derive_work_mode(location_name, description),
                seniority=_derive_seniority(item.get("title", ""), description),
                job_url=item.get("absolute_url"),
                posted_at=posted_at,
                application_deadline=application_deadline,
                availability_status=availability_status,
                availability_reason=availability_reason,
                raw_payload=item,
            )
        )
    return jobs


def _lever_jobs(payload: list[dict], source_config: JobDiscoverySourceConfig) -> list[NormalizedDiscoveredJob]:
    jobs = []
    company_name = source_config.company_name_override or source_config.company_key
    for item in payload:
        description = item.get("descriptionPlain") or item.get("description") or ""
        categories = item.get("categories") or {}
        location_name = categories.get("location")
        posted_at, application_deadline = extract_job_source_dates(item)
        availability_status, availability_reason = derive_availability_from_payload(item, description)
        jobs.append(
            NormalizedDiscoveredJob(
                source="lever",
                source_company_key=source_config.company_key,
                external_job_id=str(item.get("id") or item.get("hostedUrl") or item.get("text")),
                company_name=company_name,
                title=item.get("text", "").strip(),
                description=description,
                location=location_name,
                work_mode=_derive_work_mode(location_name, categories.get("commitment")),
                seniority=_derive_seniority(item.get("text", ""), description),
                job_url=item.get("hostedUrl"),
                posted_at=posted_at,
                application_deadline=application_deadline,
                availability_status=availability_status,
                availability_reason=availability_reason,
                raw_payload=item,
            )
        )
    return jobs


def _ashby_jobs(payload: dict, source_config: JobDiscoverySourceConfig) -> list[NormalizedDiscoveredJob]:
    jobs = []
    company_name = source_config.company_name_override or source_config.company_key
    for item in payload.get("jobs", []):
        description = item.get("descriptionPlain") or item.get("descriptionHtml") or ""
        location_name = item.get("location")
        posted_at, application_deadline = extract_job_source_dates(item)
        availability_status, availability_reason = derive_availability_from_payload(item, description)
        jobs.append(
            NormalizedDiscoveredJob(
                source="ashby",
                source_company_key=source_config.company_key,
                external_job_id=str(item.get("jobUrl") or item.get("applyUrl") or item.get("title")),
                company_name=company_name,
                title=item.get("title", "").strip(),
                description=description,
                location=location_name,
                work_mode=_derive_work_mode(location_name, item.get("workplaceType")),
                seniority=_derive_seniority(item.get("title", ""), description),
                job_url=item.get("jobUrl") or item.get("applyUrl"),
                posted_at=posted_at,
                application_deadline=application_deadline,
                availability_status=availability_status,
                availability_reason=availability_reason,
                raw_payload=item,
            )
        )
    return jobs


def _smartrecruiters_jobs(payload: dict, source_config: JobDiscoverySourceConfig) -> list[NormalizedDiscoveredJob]:
    jobs = []
    company_name = source_config.company_name_override or source_config.company_key
    for item in payload.get("content", []):
        description = item.get("jobAd") or item.get("description") or item.get("summary") or ""
        if isinstance(description, dict):
            description = description.get("text") or description.get("html") or description.get("description") or ""

        location_value = item.get("location") or {}
        if isinstance(location_value, dict):
            location_name = (
                location_value.get("city")
                or location_value.get("country")
                or location_value.get("label")
                or location_value.get("text")
            )
        else:
            location_name = location_value

        title = (item.get("name") or item.get("title") or "").strip()
        posted_at, application_deadline = extract_job_source_dates(item)
        availability_status, availability_reason = derive_availability_from_payload(item, description)
        jobs.append(
            NormalizedDiscoveredJob(
                source="smartrecruiters",
                source_company_key=source_config.company_key,
                external_job_id=str(item.get("id") or item.get("refNum") or item.get("uuid") or title),
                company_name=company_name,
                title=title,
                description=description,
                location=location_name,
                work_mode=_derive_work_mode(location_name, item.get("type")),
                seniority=_derive_seniority(title, description),
                job_url=item.get("applyUrl") or item.get("url") or item.get("jobUrl"),
                posted_at=posted_at,
                application_deadline=application_deadline,
                availability_status=availability_status,
                availability_reason=availability_reason,
                raw_payload=item,
            )
        )
    return jobs


def _workday_jobs(payload: dict, source_config: JobDiscoverySourceConfig) -> list[NormalizedDiscoveredJob]:
    jobs = []
    company_name = source_config.company_name_override or source_config.company_key
    for item in payload.get("jobPostings", []) or payload.get("jobs", []):
        title = (item.get("title") or item.get("jobTitle") or item.get("heading") or "").strip()
        description = item.get("jobDescription") or item.get("description") or item.get("snippet") or ""
        if isinstance(description, dict):
            description = description.get("text") or description.get("html") or description.get("description") or ""

        location_name = (
            item.get("locationsText")
            or item.get("locationText")
            or item.get("location")
            or item.get("country")
            or item.get("city")
        )
        if isinstance(location_name, list):
            location_name = ", ".join(str(part) for part in location_name if part)

        external_job_id = str(item.get("externalPath") or item.get("jobPostingId") or title)
        job_url = item.get("externalPath") or item.get("applyUrl") or item.get("url")
        if job_url and job_url.startswith("/"):
            job_url = f"https://{source_config.company_key}.wd5.myworkdayjobs.com{job_url}"
        posted_at, application_deadline = extract_job_source_dates(item)
        availability_status, availability_reason = derive_availability_from_payload(item, description)

        jobs.append(
            NormalizedDiscoveredJob(
                source="workday",
                source_company_key=source_config.company_key,
                external_job_id=external_job_id,
                company_name=company_name,
                title=title,
                description=description,
                location=location_name,
                work_mode=_derive_work_mode(location_name, description),
                seniority=_derive_seniority(title, description),
                job_url=job_url,
                posted_at=posted_at,
                application_deadline=application_deadline,
                availability_status=availability_status,
                availability_reason=availability_reason,
                raw_payload=item,
            )
        )
    return jobs


def _fetch_jobs(client: httpx.Client, source_config: JobDiscoverySourceConfig, include_description: bool) -> list[NormalizedDiscoveredJob]:
    source = source_config.source.lower()
    if source == "greenhouse":
        response = client.get(
            f"{GREENHOUSE_BASE_URL}/{source_config.company_key}/jobs",
            params={"content": str(include_description).lower()},
        )
        response.raise_for_status()
        return _greenhouse_jobs(response.json(), source_config)
    if source == "lever":
        response = client.get(
            f"{LEVER_BASE_URL}/{source_config.company_key}",
            params={"mode": "json"},
        )
        response.raise_for_status()
        return _lever_jobs(response.json(), source_config)
    if source == "ashby":
        response = client.get(
            f"{ASHBY_BASE_URL}/{source_config.company_key}",
            params={"includeCompensation": "false"},
        )
        response.raise_for_status()
        return _ashby_jobs(response.json(), source_config)
    if source == "smartrecruiters":
        response = client.get(f"{SMARTRECRUITERS_BASE_URL}/{source_config.company_key}/postings")
        response.raise_for_status()
        return _smartrecruiters_jobs(response.json(), source_config)
    if source == "workday":
        response = client.get(WORKDAY_BASE_URL.format(tenant=source_config.company_key))
        response.raise_for_status()
        return _workday_jobs(response.json(), source_config)
    raise ValueError(f"Unsupported discovery source: {source_config.source}")


def _get_existing_raw_job(db: Session, source: str, source_company_key: str, external_job_id: str) -> RawJob | None:
    return db.scalar(
        select(RawJob).where(
            RawJob.source == source,
            RawJob.source_company_key == source_company_key,
            RawJob.external_job_id == external_job_id,
        )
    )


def _find_normalized_job(db: Session, discovered_job: NormalizedDiscoveredJob) -> Job | None:
    if discovered_job.job_url:
        existing = db.scalar(
            select(Job).where(Job.source == discovered_job.source, Job.source_url == discovered_job.job_url)
        )
        if existing:
            return existing

    company = db.scalar(select(Company).where(Company.name == discovered_job.company_name))
    if not company:
        return None
    return db.scalar(
        select(Job).where(
            Job.company_id == company.id,
            Job.title == discovered_job.title,
            Job.source == discovered_job.source,
        )
    )


def _create_normalized_job(db: Session, discovered_job: NormalizedDiscoveredJob) -> Job:
    return crud.create_job(
        db,
        JobCreate(
            title=discovered_job.title,
            company_name=discovered_job.company_name,
            description=discovered_job.description,
            source_url=discovered_job.job_url,
            location=discovered_job.location,
            work_mode=discovered_job.work_mode,
            seniority=discovered_job.seniority,
            source=discovered_job.source,
            posted_at=discovered_job.posted_at,
            application_deadline=discovered_job.application_deadline,
            availability_status=discovered_job.availability_status,
            availability_reason=discovered_job.availability_reason,
        ),
    )


def _create_application_if_needed(db: Session, job_id: UUID, create_applications: bool) -> tuple[Application | None, bool]:
    if not create_applications:
        return None, False
    existing_application = db.scalar(select(Application).where(Application.job_id == job_id))
    if existing_application:
        return existing_application, False
    application = crud.create_application(
        db,
        ApplicationCreate(
            job_id=job_id,
            status=ApplicationStatus.FOUND,
            notes="Created from job discovery run.",
        ),
    )
    return application, True


def list_raw_jobs(db: Session) -> list[RawJob]:
    statement = select(RawJob).options(joinedload(RawJob.normalized_job)).order_by(RawJob.discovered_at.desc())
    return list(db.scalars(statement))


def create_discovery_source(db: Session, payload: DiscoverySourceCreate) -> DiscoverySource:
    existing = db.scalar(
        select(DiscoverySource).where(
            DiscoverySource.source == payload.source.lower(),
            DiscoverySource.company_key == payload.company_key,
        )
    )
    if existing:
        raise ValueError("A discovery source with this source/company_key already exists.")

    source = DiscoverySource(
        source=payload.source.lower(),
        company_key=payload.company_key,
        company_name_override=payload.company_name_override,
        role_keywords=payload.role_keywords,
        locations=payload.locations,
        seniority_terms=payload.seniority_terms,
        work_modes=payload.work_modes,
        include_description=payload.include_description,
        create_applications=payload.create_applications,
        is_active=payload.is_active,
    )
    db.add(source)
    db.flush()
    write_audit_log(
        db,
        event_type="discovery_source.created",
        entity_type="discovery_source",
        entity_id=source.id,
        details={"source": source.source, "company_key": source.company_key},
    )
    db.commit()
    db.refresh(source)
    return source


def list_discovery_sources(db: Session) -> list[DiscoverySource]:
    return list(db.scalars(select(DiscoverySource).order_by(DiscoverySource.created_at.desc())))


def update_discovery_source(db: Session, source_id: UUID, payload: DiscoverySourceUpdate) -> DiscoverySource | None:
    source = db.get(DiscoverySource, source_id)
    if not source:
        return None

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(source, field, value)

    write_audit_log(
        db,
        event_type="discovery_source.updated",
        entity_type="discovery_source",
        entity_id=source.id,
        details=changes,
    )
    db.commit()
    db.refresh(source)
    return source


def list_discovery_runs(db: Session, limit: int = 20) -> list[DiscoveryRun]:
    return list(db.scalars(select(DiscoveryRun).order_by(DiscoveryRun.started_at.desc()).limit(limit)))


def active_discovery_source_count(db: Session) -> int:
    return len(list(db.scalars(select(DiscoverySource.id).where(DiscoverySource.is_active.is_(True)))))


def run_saved_discovery_sources(db: Session, trigger_type: str = "manual") -> dict:
    saved_sources = list(
        db.scalars(select(DiscoverySource).where(DiscoverySource.is_active.is_(True)).order_by(DiscoverySource.created_at.asc()))
    )
    if not saved_sources:
        raise ValueError("No active discovery sources are configured.")

    run = DiscoveryRun(
        trigger_type=trigger_type,
        status="running",
        source_count=len(saved_sources),
        raw_jobs_saved=0,
        normalized_jobs_created=0,
        applications_created=0,
        deduplicated_jobs=0,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        aggregate_result = {
            "raw_jobs_saved": 0,
            "normalized_jobs_created": 0,
            "applications_created": 0,
            "deduplicated_jobs": 0,
            "auto_scored_jobs": 0,
            "matched_jobs": [],
        }
        matched_jobs_by_id: dict[UUID, Job] = {}

        for source in saved_sources:
            result = discover_jobs(
                db,
                sources=[
                    JobDiscoverySourceConfig(
                        source=source.source,
                        company_key=source.company_key,
                        company_name_override=source.company_name_override,
                    )
                ],
                filters=JobDiscoveryFilters(
                    role_keywords=list(source.role_keywords),
                    locations=list(source.locations),
                    seniority_terms=list(source.seniority_terms),
                    work_modes=list(source.work_modes),
                ),
                include_description=source.include_description,
                create_applications=source.create_applications,
            )
            for key in (
                "raw_jobs_saved",
                "normalized_jobs_created",
                "applications_created",
                "deduplicated_jobs",
                "auto_scored_jobs",
            ):
                aggregate_result[key] += result[key]
            for job in result["matched_jobs"]:
                matched_jobs_by_id[job.id] = job

        aggregate_result["matched_jobs"] = list(matched_jobs_by_id.values())
        result = aggregate_result
        run.status = "completed"
        run.raw_jobs_saved = result["raw_jobs_saved"]
        run.normalized_jobs_created = result["normalized_jobs_created"]
        run.applications_created = result["applications_created"]
        run.deduplicated_jobs = result["deduplicated_jobs"]
        run.finished_at = datetime.now(timezone.utc)
        write_audit_log(
            db,
            event_type="job_discovery.saved_sources_run",
            entity_type="job_discovery_run",
            entity_id=run.id,
            details={"trigger_type": trigger_type, "source_count": len(saved_sources)},
        )
        db.commit()
        db.refresh(run)
        return result
    except Exception as error:
        run.status = "failed"
        run.error_message = str(error)
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise


def discover_jobs(
    db: Session,
    *,
    sources: list[JobDiscoverySourceConfig],
    filters: JobDiscoveryFilters,
    include_description: bool,
    create_applications: bool,
) -> dict:
    raw_jobs_saved = 0
    normalized_jobs_created = 0
    applications_created = 0
    deduplicated_jobs = 0
    auto_scored_jobs = 0
    matched_jobs: list[Job] = []
    profile_available = get_profile(db) is not None

    with httpx.Client(timeout=30.0, headers={"User-Agent": "CareerOpsAgent/0.1"}) as client:
        for source_config in sources:
            discovered_jobs = _fetch_jobs(client, source_config, include_description)
            for discovered_job in discovered_jobs:
                if is_excluded_company_name(discovered_job.company_name):
                    continue
                if not _passes_filters(discovered_job, filters):
                    continue
                if is_job_dismissed(
                    db,
                    source=discovered_job.source,
                    source_company_key=discovered_job.source_company_key,
                    external_job_id=discovered_job.external_job_id,
                    source_url=discovered_job.job_url,
                    company_name=discovered_job.company_name,
                    title=discovered_job.title,
                ):
                    continue

                raw_job = _get_existing_raw_job(
                    db,
                    discovered_job.source,
                    discovered_job.source_company_key,
                    discovered_job.external_job_id,
                )
                if not raw_job:
                    raw_job = RawJob(
                        source=discovered_job.source,
                        source_company_key=discovered_job.source_company_key,
                        external_job_id=discovered_job.external_job_id,
                        company_name=discovered_job.company_name,
                        title=discovered_job.title,
                        location=discovered_job.location,
                        job_url=discovered_job.job_url,
                        raw_payload=discovered_job.raw_payload,
                    )
                    db.add(raw_job)
                    db.flush()
                    raw_jobs_saved += 1

                normalized_job = raw_job.normalized_job or _find_normalized_job(db, discovered_job)
                if normalized_job:
                    deduplicated_jobs += 1
                else:
                    normalized_job = _create_normalized_job(db, discovered_job)
                    normalized_jobs_created += 1
                    matched_jobs.append(normalized_job)

                raw_job.normalized_job_id = normalized_job.id
                _, created_application = _create_application_if_needed(db, normalized_job.id, create_applications)
                if created_application:
                    applications_created += 1
                if profile_available and ensure_job_score(db, normalized_job.id):
                    auto_scored_jobs += 1

    db.commit()
    write_audit_log(
        db,
        event_type="job_discovery.completed",
        entity_type="job_discovery",
        entity_id=None,
        details={
            "source_count": len(sources),
            "raw_jobs_saved": raw_jobs_saved,
            "normalized_jobs_created": normalized_jobs_created,
            "applications_created": applications_created,
            "deduplicated_jobs": deduplicated_jobs,
            "auto_scored_jobs": auto_scored_jobs,
        },
    )
    db.commit()

    if not matched_jobs:
        matched_jobs = list(
            db.scalars(
                select(Job)
                .options(joinedload(Job.company))
                .order_by(Job.created_at.desc())
                .limit(max(normalized_jobs_created, 10))
            )
        )
    else:
        for job in matched_jobs:
            db.refresh(job)

    return {
        "raw_jobs_saved": raw_jobs_saved,
        "normalized_jobs_created": normalized_jobs_created,
        "applications_created": applications_created,
        "deduplicated_jobs": deduplicated_jobs,
        "auto_scored_jobs": auto_scored_jobs,
        "matched_jobs": matched_jobs,
    }
