from __future__ import annotations

import hashlib
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DismissedJob, Job, RawJob
from app.text_normalization import normalize_display_text


def _normalized(value: str | None) -> str:
    return normalize_display_text(value, fallback=(value or "").strip()) or ""


def is_excluded_company_name(company_name: str | None) -> bool:
    normalized = _normalized(company_name).casefold().strip(" '\"")
    return normalized in {"hired"}


def build_job_fingerprints(
    *,
    source: str,
    source_company_key: str | None,
    external_job_id: str | None,
    source_url: str | None,
    company_name: str | None,
    title: str | None,
) -> list[str]:
    fingerprints: list[str] = []

    def add_fingerprint(prefix: str, payload: str) -> None:
        digest = hashlib.sha256(f"{prefix}|{payload}".encode("utf-8")).hexdigest()
        if digest not in fingerprints:
            fingerprints.append(digest)

    normalized_source = source.strip().lower()
    normalized_company_key = (source_company_key or "").strip().lower()
    normalized_source_url = (source_url or "").strip().lower()
    normalized_company_name = _normalized(company_name)
    normalized_title = _normalized(title)

    if external_job_id:
        add_fingerprint("external-id", f"{normalized_source}|{normalized_company_key}|{external_job_id.strip()}")
    if normalized_source_url:
        add_fingerprint("source-url", f"{normalized_source}|{normalized_source_url}")
    if normalized_company_name and normalized_title:
        add_fingerprint("company-title", f"{normalized_source}|{normalized_company_name}|{normalized_title}")

    return fingerprints


def is_job_dismissed(
    db: Session,
    *,
    source: str,
    source_company_key: str | None,
    external_job_id: str | None,
    source_url: str | None,
    company_name: str | None,
    title: str | None,
) -> bool:
    fingerprints = build_job_fingerprints(
        source=source,
        source_company_key=source_company_key,
        external_job_id=external_job_id,
        source_url=source_url,
        company_name=company_name,
        title=title,
    )
    if not fingerprints:
        return False
    return db.scalar(select(DismissedJob.id).where(DismissedJob.fingerprint.in_(fingerprints))) is not None


def suppress_job(
    db: Session,
    *,
    source: str,
    source_company_key: str | None,
    external_job_id: str | None,
    source_url: str | None,
    company_name: str | None,
    title: str | None,
    reason: str | None,
    seen_fingerprints: set[str] | None = None,
) -> None:
    for fingerprint in build_job_fingerprints(
        source=source,
        source_company_key=source_company_key,
        external_job_id=external_job_id,
        source_url=source_url,
        company_name=company_name,
        title=title,
    ):
        if seen_fingerprints is not None and fingerprint in seen_fingerprints:
            continue
        if seen_fingerprints is not None:
            seen_fingerprints.add(fingerprint)
        with db.no_autoflush:
            existing = db.scalar(select(DismissedJob).where(DismissedJob.fingerprint == fingerprint))
        if existing:
            continue
        db.add(
            DismissedJob(
                fingerprint=fingerprint,
                source=source,
                source_company_key=source_company_key,
                external_job_id=external_job_id,
                source_url=source_url,
                company_name=company_name,
                title=title,
                reason=reason,
            )
        )


def suppress_job_and_raw_variants(db: Session, job: Job, *, reason: str | None = None) -> None:
    raw_jobs: Iterable[RawJob] = job.raw_jobs or []
    seen_fingerprints: set[str] = set()
    for raw_job in raw_jobs:
        suppress_job(
            db,
            source=raw_job.source,
            source_company_key=raw_job.source_company_key,
            external_job_id=raw_job.external_job_id,
            source_url=raw_job.job_url,
            company_name=raw_job.company_name,
            title=raw_job.title,
            reason=reason,
            seen_fingerprints=seen_fingerprints,
        )

    suppress_job(
        db,
        source=job.source,
        source_company_key=None,
        external_job_id=None,
        source_url=job.source_url,
        company_name=job.company.name if job.company else None,
        title=job.title,
        reason=reason,
        seen_fingerprints=seen_fingerprints,
    )
