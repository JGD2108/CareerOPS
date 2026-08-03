from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.job_page_scraper import scrape_job_page_with_selenium
from app.models import Job

settings = get_settings()

OPEN_PAGE_PATTERNS = (
    "apply now",
    "easy apply",
    "submit application",
    "apply for this job",
    "job details",
    "fill out the form",
    "send your cv",
    "send your cv in english",
)
UNAVAILABLE_PAGE_PATTERNS = (
    "no longer accepting applications",
    "job is no longer available",
    "job posting has expired",
    "this job has expired",
    "job unavailable",
    "position has been filled",
    "applications are closed",
    "this position is no longer accepting applications",
    "job you are looking for is no longer available",
)
LOGIN_PATTERNS = (
    "sign in",
    "join now",
    "create account",
)


def _parse_datetime_value(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        try:
            if value > 10_000_000_000:
                value = value / 1000
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        except ValueError:
            pass
        for pattern in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%b %d, %Y", "%B %d, %Y"):
            try:
                return datetime.strptime(cleaned, pattern).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def extract_job_source_dates(raw_payload: dict | None) -> tuple[datetime | None, datetime | None]:
    payload = raw_payload or {}
    posted_candidates = (
        payload.get("updated_at"),
        payload.get("updatedAt"),
        payload.get("createdAt"),
        payload.get("publishedDate"),
        payload.get("releasedDate"),
        payload.get("postedDate"),
        payload.get("datePosted"),
        payload.get("publicationDate"),
        payload.get("postedOn"),
    )
    deadline_candidates = (
        payload.get("applicationDeadline"),
        payload.get("deadline"),
        payload.get("closingDate"),
        payload.get("expireAt"),
        payload.get("expirationDate"),
    )
    posted_at = next((value for item in posted_candidates if (value := _parse_datetime_value(item))), None)
    deadline = next((value for item in deadline_candidates if (value := _parse_datetime_value(item))), None)
    return posted_at, deadline


def derive_availability_from_payload(raw_payload: dict | None, description: str | None) -> tuple[str, str | None]:
    haystack = " ".join(
        [
            str(raw_payload or {}),
            description or "",
        ]
    ).lower()
    if any(marker in haystack for marker in ("closed", "expired", "filled", "unavailable", "no longer accepting")):
        return "closed", "The source payload already suggests this role is closed or expired."
    return "unknown", None


def classify_availability_from_response(url: str, status_code: int, final_url: str, body_text: str) -> tuple[str, str]:
    lowered = body_text.lower()
    final_url_lower = final_url.lower()
    if status_code >= 400:
        return "closed", f"The job page returned HTTP {status_code}."
    if any(pattern in lowered for pattern in OPEN_PAGE_PATTERNS):
        return "open", "The job page still exposes application or job detail actions."
    if any(pattern in lowered for pattern in UNAVAILABLE_PAGE_PATTERNS):
        return "closed", "The job page says the role is no longer available."
    if "linkedin.com" in final_url_lower and "/jobs/view/" not in final_url_lower and any(
        pattern in lowered for pattern in LOGIN_PATTERNS
    ):
        return "unknown", "LinkedIn redirected to a login wall, so public apply availability could not be confirmed."
    if final_url_lower != url.lower() and any(pattern in lowered for pattern in LOGIN_PATTERNS):
        return "unknown", "The source link redirected to a login or account wall."
    return "unknown", "The page loaded, but the app could not confirm whether applications are still open."


def verify_job_availability(db: Session, job_id: UUID) -> Job | None:
    job = db.get(Job, job_id)
    if not job:
        return None

    job.availability_checked_at = datetime.now(timezone.utc)
    if not job.source_url:
        job.availability_status = "unknown"
        job.availability_reason = "This job does not have a source link to verify."
        db.commit()
        db.refresh(job)
        return job

    if settings.enable_browser_job_checks and "linkedin.com" not in job.source_url.lower():
        selenium_result = scrape_job_page_with_selenium(job.source_url)
        if selenium_result:
            if selenium_result.description and len(selenium_result.description) > len(job.description or ""):
                job.description = selenium_result.description
            if selenium_result.location:
                job.location = selenium_result.location
            if selenium_result.posted_at:
                job.posted_at = selenium_result.posted_at
            if selenium_result.application_deadline:
                job.application_deadline = selenium_result.application_deadline
            job.availability_status = selenium_result.availability_status
            job.availability_reason = selenium_result.availability_reason
            raw_payload = dict(job.raw_payload or {})
            raw_payload.update(
                {
                    "scraper": selenium_result.scraper,
                    "scraped_source_url": selenium_result.source_url,
                    "scraped_final_url": selenium_result.final_url,
                }
            )
            job.raw_payload = raw_payload
            db.commit()
            db.refresh(job)
            return job

    try:
        with httpx.Client(
            timeout=20.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0 Safari/537.36"
                )
            },
            follow_redirects=True,
        ) as client:
            response = client.get(job.source_url)
    except Exception as error:
        job.availability_status = "unknown"
        job.availability_reason = f"Availability check failed: {error}"
        db.commit()
        db.refresh(job)
        return job

    body_text = re.sub(r"\s+", " ", response.text or "")[:12000]
    availability_status, availability_reason = classify_availability_from_response(
        job.source_url,
        response.status_code,
        str(response.url),
        body_text,
    )
    job.availability_status = availability_status
    job.availability_reason = availability_reason
    db.commit()
    db.refresh(job)
    return job
