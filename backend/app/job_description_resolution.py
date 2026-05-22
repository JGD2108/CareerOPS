from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import re
import urllib.parse
import urllib.robotparser
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.audit import write_audit_log
from app.job_description_state import description_is_complete, description_quality_for_text
from app.job_discovery import JobDiscoverySourceConfig, NormalizedDiscoveredJob, _fetch_jobs
from app.job_matching import JobMatchResult, match_job_to_posting
from app.models import DiscoverySource, Job, JobDescriptionResolutionAttempt
from app.text_normalization import normalize_display_text


SUPPORTED_ATS_SOURCES = {"greenhouse", "lever", "ashby"}
ELIGIBLE_RESOLUTION_STATUSES = {"missing", "partial_from_email", "failed"}
BLOCKED_HOST_PARTS = {
    "linkedin.com",
    "lnkd.in",
    "facebook.com",
    "glassdoor.com",
}
LOGIN_PATH_MARKERS = ("login", "signin", "sign-in", "auth", "sso", "oauth", "account")
SENSITIVE_QUERY_MARKERS = ("token", "session", "auth", "access_token", "id_token", "jwt", "key", "code")
CAPTCHA_MARKERS = ("captcha", "recaptcha", "hcaptcha", "cloudflare challenge", "verify you are human", "bot detection")
SAFE_USER_AGENT = "CareerOpsAgent/0.1 public-job-description-resolver (+local human-in-the-loop)"
MAX_HTML_BYTES = 1_000_000


class PublicHTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, _attrs) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg", "canvas", "iframe"}:
            self._skip_depth += 1
        if tag.lower() in {"p", "li", "br", "div", "section", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg", "canvas", "iframe"} and self._skip_depth:
            self._skip_depth -= 1
        if tag.lower() in {"p", "li", "div", "section"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            text = data.strip()
            if text:
                self.parts.append(text)


def _job_with_context(db: Session, job_id: UUID) -> Job | None:
    return db.scalar(
        select(Job)
        .options(joinedload(Job.company), selectinload(Job.raw_jobs), selectinload(Job.description_resolution_attempts))
        .where(Job.id == job_id)
    )


def save_manual_job_description(
    db: Session,
    job_id: UUID,
    *,
    description: str,
    source_url: str | None = None,
    notes: str | None = None,
) -> tuple[Job, JobDescriptionResolutionAttempt] | None:
    job = _job_with_context(db, job_id)
    if not job:
        return None

    cleaned_description = normalize_display_text(description, fallback=description) or description
    quality = description_quality_for_text(cleaned_description)
    resolved_url = source_url or job.resolved_description_url or job.source_url
    now = datetime.now(timezone.utc)

    job.description = cleaned_description
    job.resolved_description = cleaned_description
    job.resolved_description_html = None
    job.resolved_description_url = resolved_url
    job.resolved_at = now
    job.description_status = "manually_provided"
    job.description_quality = quality
    job.description_source = "manual_paste"
    job.fetch_status = "success"
    job.resolution_confidence = 1.0 if quality == "high" else 0.8
    job.resolution_notes = notes or "Full job description pasted manually by the user."
    job.raw_payload = {
        **(job.raw_payload or {}),
        "manual_description": {
            "source": "manual_paste",
            "source_url": resolved_url,
            "updated_at": now.isoformat(),
            "quality": quality,
        },
    }

    attempt = JobDescriptionResolutionAttempt(
        id=uuid4(),
        job_id=job.id,
        attempted_source="manual_paste",
        attempted_url=resolved_url,
        status="success",
        confidence=job.resolution_confidence,
        reason=job.resolution_notes,
        attempt_metadata={"description_length": len(cleaned_description), "quality": quality},
        created_at=now,
    )
    db.add(attempt)
    db.flush()

    write_audit_log(
        db,
        event_type="job_description.manual_description_saved",
        entity_type="job",
        entity_id=job.id,
        actor="user",
        details={
            "attempt_id": str(attempt.id),
            "description_status": job.description_status,
            "description_quality": job.description_quality,
            "description_source": job.description_source,
            "source_url": resolved_url,
        },
    )
    db.commit()
    db.refresh(job)
    db.refresh(attempt)
    return job, attempt


def _clean_description(description: str) -> str:
    cleaned = normalize_display_text(description, fallback=description) or description
    return cleaned.strip()


def _extract_text_from_html(html: str) -> str:
    parser = PublicHTMLTextExtractor()
    parser.feed(html)
    text = "\n".join(parser.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return _clean_description(text)


def _url_host(url: str) -> str:
    return (urllib.parse.urlparse(url).hostname or "").lower()


def _validate_public_job_url(url: str) -> tuple[bool, str]:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        return False, "Only absolute http or https URLs are supported."
    if any(marker in host for marker in BLOCKED_HOST_PARTS):
        return False, "LinkedIn, social, and blocked job-board URLs are reference-only and cannot be fetched."
    lowered_path = parsed.path.lower()
    lowered_query = parsed.query.lower()
    if any(marker in lowered_path for marker in LOGIN_PATH_MARKERS):
        return False, "Login or authentication URLs are not accepted."
    if any(marker in lowered_query for marker in SENSITIVE_QUERY_MARKERS):
        return False, "URLs with auth, session, or token-like query parameters are not accepted."
    return True, "URL is eligible for public fetch."


def _looks_blocked(text: str, html: str, status_code: int) -> str | None:
    if status_code in {401, 403}:
        return f"URL returned HTTP {status_code}."
    lowered = f"{text[:4000]}\n{html[:4000]}".lower()
    if any(marker in lowered for marker in CAPTCHA_MARKERS):
        return "Page appears to contain a CAPTCHA or bot challenge."
    if "sign in" in lowered or "log in" in lowered or "login required" in lowered:
        return "Page appears to require login."
    return None


def _description_text_quality(job: Job, text: str) -> tuple[bool, str, float, dict]:
    cleaned = _clean_description(text)
    lowered = cleaned.lower()
    title_tokens = [token for token in re.findall(r"[a-z0-9]+", job.title.lower()) if len(token) > 2]
    company = _company_name(job) or ""
    company_tokens = [token for token in re.findall(r"[a-z0-9]+", company.lower()) if len(token) > 2]
    job_markers = {
        "responsibilities",
        "requirements",
        "qualifications",
        "experience",
        "skills",
        "apply",
        "role",
        "position",
        "about the job",
        "what you will do",
        "we are looking",
    }
    marker_hits = sum(1 for marker in job_markers if marker in lowered)
    title_hits = sum(1 for token in set(title_tokens) if token in lowered)
    company_hits = sum(1 for token in set(company_tokens) if token in lowered)
    length_score = min(len(cleaned) / 1800, 1.0)
    title_score = min(title_hits / max(len(set(title_tokens)), 1), 1.0)
    company_score = min(company_hits / max(len(set(company_tokens)), 1), 1.0) if company_tokens else 0.65
    marker_score = min(marker_hits / 4, 1.0)
    confidence = round(length_score * 0.35 + title_score * 0.30 + company_score * 0.15 + marker_score * 0.20, 3)
    evidence = {
        "description_length": len(cleaned),
        "title_token_hits": title_hits,
        "company_token_hits": company_hits,
        "job_marker_hits": marker_hits,
    }
    if len(cleaned) < 350:
        return False, "Extracted page text is too short to be a reliable job description.", confidence, evidence
    if title_score < 0.35:
        return False, "Extracted text does not look like the target role.", confidence, evidence
    if marker_hits < 2 and len(cleaned) < 900:
        return False, "Page looks like a generic or low-detail careers page.", confidence, evidence
    return True, "Public page contains a plausible target job description.", max(confidence, 0.72), evidence


def _robots_allows(client: httpx.Client, url: str) -> tuple[bool, str]:
    parsed = urllib.parse.urlparse(url)
    robots_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "/robots.txt", "", "", ""))
    try:
        response = client.get(robots_url, timeout=5.0)
    except Exception:
        return True, "robots.txt unavailable; proceeding with one conservative public fetch."
    if response.status_code >= 400:
        return True, "robots.txt unavailable; proceeding with one conservative public fetch."
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(response.text.splitlines())
    allowed = parser.can_fetch(SAFE_USER_AGENT, url)
    return allowed, "robots.txt allows fetch." if allowed else "robots.txt disallows fetch."


def _fetch_public_job_page(job: Job, url: str, *, respect_robots: bool = True) -> dict:
    valid, reason = _validate_public_job_url(url)
    if not valid:
        return {"status": "rejected", "reason": reason, "confidence": 0.0}
    with httpx.Client(
        timeout=httpx.Timeout(8.0, connect=4.0),
        follow_redirects=True,
        headers={"User-Agent": SAFE_USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
    ) as client:
        if respect_robots:
            allowed, robots_reason = _robots_allows(client, url)
            if not allowed:
                return {"status": "rejected", "reason": robots_reason, "confidence": 0.0}
        try:
            response = client.get(url)
        except Exception as error:
            return {"status": "error", "reason": "Public page fetch failed.", "error_message": str(error)}
    content_type = response.headers.get("content-type", "")
    if "html" not in content_type.lower():
        return {"status": "rejected", "reason": "URL did not return public HTML.", "confidence": 0.0}
    body = response.content[:MAX_HTML_BYTES]
    html = body.decode(response.encoding or "utf-8", errors="replace")
    text = _extract_text_from_html(html)
    blocked_reason = _looks_blocked(text, html, response.status_code)
    if blocked_reason:
        return {"status": "rejected", "reason": blocked_reason, "confidence": 0.0}
    ok, quality_reason, confidence, evidence = _description_text_quality(job, text)
    if not ok:
        return {"status": "rejected", "reason": quality_reason, "confidence": confidence, "metadata": evidence}
    quality = description_quality_for_text(text)
    return {
        "status": "success",
        "reason": quality_reason,
        "description": text,
        "description_html": html,
        "final_url": str(response.url),
        "quality": "high" if quality == "high" and confidence >= 0.86 else "medium",
        "confidence": confidence,
        "metadata": evidence,
    }


def _company_name(job: Job) -> str | None:
    return job.company.name if job.company else None


def _source_config_from_discovery_source(source: DiscoverySource) -> JobDiscoverySourceConfig:
    return JobDiscoverySourceConfig(
        source=source.source,
        company_key=source.company_key,
        company_name_override=source.company_name_override,
    )


def _direct_source_configs(job: Job) -> list[JobDiscoverySourceConfig]:
    configs = []
    for raw_job in job.raw_jobs:
        if raw_job.source in SUPPORTED_ATS_SOURCES:
            configs.append(
                JobDiscoverySourceConfig(
                    source=raw_job.source,
                    company_key=raw_job.source_company_key,
                    company_name_override=raw_job.company_name,
                )
            )
    if job.source in SUPPORTED_ATS_SOURCES:
        company_key = None
        for raw_job in job.raw_jobs:
            if raw_job.source == job.source:
                company_key = raw_job.source_company_key
                break
        if company_key:
            configs.append(
                JobDiscoverySourceConfig(
                    source=job.source,
                    company_key=company_key,
                    company_name_override=_company_name(job),
                )
            )
    return configs


def _saved_source_configs(db: Session, job: Job) -> list[JobDiscoverySourceConfig]:
    company_name = (_company_name(job) or "").strip().lower()
    if not company_name:
        return []
    sources = list(
        db.scalars(
            select(DiscoverySource).where(
                DiscoverySource.source.in_(SUPPORTED_ATS_SOURCES),
                DiscoverySource.is_active.is_(True),
            )
        )
    )
    configs = []
    for source in sources:
        candidates = {
            (source.company_name_override or "").strip().lower(),
            source.company_key.strip().lower(),
        }
        if company_name in candidates or any(candidate and candidate in company_name for candidate in candidates):
            configs.append(_source_config_from_discovery_source(source))
    return configs


def _dedupe_configs(configs: list[JobDiscoverySourceConfig]) -> list[JobDiscoverySourceConfig]:
    seen = set()
    deduped = []
    for config in configs:
        key = (config.source.lower(), config.company_key.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(config)
    return deduped


def _company_careers_candidate_urls(job: Job) -> list[str]:
    if not job.company or not job.company.website_url:
        return []
    valid, _reason = _validate_public_job_url(job.company.website_url)
    if not valid:
        return []
    parsed = urllib.parse.urlparse(job.company.website_url)
    base = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    slug = re.sub(r"[^a-z0-9]+", "-", job.title.lower()).strip("-")
    paths = [parsed.path if parsed.path and parsed.path != "/" else "", "/careers", "/jobs", "/careers/jobs"]
    if slug:
        paths.extend([f"/careers/{slug}", f"/jobs/{slug}", f"/careers/jobs/{slug}"])
    urls = []
    for path in paths:
        url = urllib.parse.urljoin(base, path)
        if url not in urls:
            urls.append(url)
    return urls[:7]


def _write_attempt(
    db: Session,
    job: Job,
    *,
    source: str,
    attempted_url: str | None,
    status: str,
    confidence: float | None,
    reason: str,
    raw_response_ref: str | None = None,
    error_message: str | None = None,
    metadata: dict | None = None,
) -> JobDescriptionResolutionAttempt:
    attempt = JobDescriptionResolutionAttempt(
        id=uuid4(),
        job_id=job.id,
        attempted_source=source,
        attempted_url=attempted_url,
        status=status,
        confidence=confidence,
        reason=reason,
        raw_response_ref=raw_response_ref,
        error_message=error_message,
        attempt_metadata=metadata,
        created_at=datetime.now(timezone.utc),
    )
    db.add(attempt)
    db.flush()
    return attempt


def _apply_success(
    job: Job,
    posting: NormalizedDiscoveredJob,
    match: JobMatchResult,
) -> None:
    description = _clean_description(posting.description)
    now = datetime.now(timezone.utc)
    job.description = description
    job.resolved_description = description
    job.resolved_description_html = posting.raw_payload.get("descriptionHtml") or posting.raw_payload.get("content")
    job.resolved_description_url = posting.job_url
    job.resolved_at = now
    job.description_status = "resolved_from_ats"
    job.description_quality = "high"
    job.description_source = posting.source
    job.fetch_status = "success"
    job.resolution_confidence = match.confidence
    job.resolution_notes = f"Resolved from {posting.source} public ATS posting. {match.reason}."
    job.location = job.location or posting.location
    job.work_mode = job.work_mode or posting.work_mode
    job.seniority = job.seniority or posting.seniority
    job.posted_at = job.posted_at or posting.posted_at
    job.application_deadline = job.application_deadline or posting.application_deadline
    job.raw_payload = {
        **(job.raw_payload or {}),
        "description_resolution": {
            "source": posting.source,
            "source_company_key": posting.source_company_key,
            "external_job_id": posting.external_job_id,
            "resolved_description_url": posting.job_url,
            "resolved_at": now.isoformat(),
            "confidence": match.confidence,
            "evidence": match.evidence,
        },
    }


def _apply_public_page_success(
    job: Job,
    *,
    description: str,
    description_html: str | None,
    resolved_url: str,
    source: str,
    status: str,
    quality: str,
    confidence: float,
    notes: str,
    metadata: dict | None = None,
) -> None:
    cleaned = _clean_description(description)
    now = datetime.now(timezone.utc)
    job.description = cleaned
    job.resolved_description = cleaned
    job.resolved_description_html = description_html
    job.resolved_description_url = resolved_url
    job.resolved_at = now
    job.description_status = status
    job.description_quality = quality
    job.description_source = source
    job.fetch_status = "success"
    job.resolution_confidence = confidence
    job.resolution_notes = notes
    job.raw_payload = {
        **(job.raw_payload or {}),
        "description_resolution": {
            "source": source,
            "resolved_description_url": resolved_url,
            "resolved_at": now.isoformat(),
            "confidence": confidence,
            "evidence": metadata or {},
        },
    }


def resolve_manual_job_url(db: Session, job_id: UUID, *, url: str) -> tuple[Job, JobDescriptionResolutionAttempt] | None:
    job = _job_with_context(db, job_id)
    if not job:
        return None
    if description_is_complete(job) and job.description_quality == "high":
        attempt = _write_attempt(
            db,
            job,
            source="manual_url",
            attempted_url=url,
            status="rejected",
            confidence=job.resolution_confidence,
            reason=(
                "This job already has a high-quality resolved description. "
                "Edit or replace the description manually only when you intentionally want to change it."
            ),
        )
        db.commit()
        db.refresh(job)
        db.refresh(attempt)
        return job, attempt
    fetched = _fetch_public_job_page(job, url, respect_robots=True)
    status = fetched.get("status", "error")
    if status != "success":
        attempt = _write_attempt(
            db,
            job,
            source="manual_url",
            attempted_url=url,
            status=status,
            confidence=fetched.get("confidence"),
            reason=fetched.get("reason", "Manual URL could not be resolved."),
            error_message=fetched.get("error_message"),
            metadata=fetched.get("metadata"),
        )
        job.fetch_status = "needs_manual_review" if status == "rejected" else "error"
        job.resolution_notes = fetched.get("reason", "Manual URL could not be resolved.")
        db.commit()
        db.refresh(job)
        db.refresh(attempt)
        return job, attempt

    notes = "Resolved from a user-provided public official job URL."
    _apply_public_page_success(
        job,
        description=fetched["description"],
        description_html=fetched.get("description_html"),
        resolved_url=fetched.get("final_url") or url,
        source="manual_url",
        status="manually_provided_url",
        quality=fetched.get("quality", "medium"),
        confidence=fetched.get("confidence", 0.8),
        notes=notes,
        metadata=fetched.get("metadata"),
    )
    attempt = _write_attempt(
        db,
        job,
        source="manual_url",
        attempted_url=url,
        status="success",
        confidence=job.resolution_confidence,
        reason=notes,
        metadata=fetched.get("metadata"),
    )
    write_audit_log(
        db,
        event_type="job_description.manual_url_resolved",
        entity_type="job",
        entity_id=job.id,
        actor="user",
        details={"attempt_id": str(attempt.id), "resolved_description_url": job.resolved_description_url},
    )
    db.commit()
    db.refresh(job)
    db.refresh(attempt)
    return job, attempt


def _candidate_from_attempt(attempt: JobDescriptionResolutionAttempt) -> NormalizedDiscoveredJob | None:
    metadata = attempt.attempt_metadata or {}
    description = metadata.get("candidate_description")
    if not description:
        return None
    return NormalizedDiscoveredJob(
        source=str(metadata.get("candidate_source") or attempt.attempted_source),
        source_company_key=str(metadata.get("company_key") or ""),
        external_job_id=str(attempt.raw_response_ref or attempt.id),
        company_name=str(metadata.get("posting_company") or ""),
        title=str(metadata.get("posting_title") or ""),
        description=str(description),
        location=metadata.get("posting_location"),
        work_mode=None,
        seniority=None,
        job_url=attempt.attempted_url,
        posted_at=None,
        application_deadline=None,
        availability_status="open",
        availability_reason=None,
        raw_payload={"accepted_from_attempt_id": str(attempt.id)},
    )


def accept_resolution_candidate(db: Session, job_id: UUID, attempt_id: UUID) -> tuple[Job, JobDescriptionResolutionAttempt] | None:
    job = _job_with_context(db, job_id)
    attempt = db.get(JobDescriptionResolutionAttempt, attempt_id)
    if not job or not attempt or attempt.job_id != job.id:
        return None
    posting = _candidate_from_attempt(attempt)
    if not posting:
        raise ValueError("Resolution attempt does not contain an attachable candidate description.")
    confidence = attempt.confidence or 0.75
    match = JobMatchResult(
        confidence=confidence,
        accepted=True,
        needs_review=False,
        reason=attempt.reason or "User accepted candidate description.",
        evidence=(attempt.attempt_metadata or {}).get("evidence", {}),
    )
    _apply_success(job, posting, match)
    job.resolution_notes = f"User accepted candidate description from {posting.source}."
    accepted_attempt = _write_attempt(
        db,
        job,
        source=f"{attempt.attempted_source}_accepted",
        attempted_url=attempt.attempted_url,
        status="success",
        confidence=confidence,
        reason=job.resolution_notes,
        raw_response_ref=str(attempt.id),
        metadata={"accepted_attempt_id": str(attempt.id)},
    )
    write_audit_log(
        db,
        event_type="job_description.candidate_accepted",
        entity_type="job",
        entity_id=job.id,
        actor="user",
        details={"attempt_id": str(attempt.id), "accepted_attempt_id": str(accepted_attempt.id)},
    )
    db.commit()
    db.refresh(job)
    db.refresh(accepted_attempt)
    return job, accepted_attempt


def reject_resolution_candidate(db: Session, job_id: UUID, attempt_id: UUID) -> JobDescriptionResolutionAttempt | None:
    job = _job_with_context(db, job_id)
    attempt = db.get(JobDescriptionResolutionAttempt, attempt_id)
    if not job or not attempt or attempt.job_id != job.id:
        return None
    rejected = _write_attempt(
        db,
        job,
        source=f"{attempt.attempted_source}_rejected",
        attempted_url=attempt.attempted_url,
        status="rejected",
        confidence=attempt.confidence,
        reason="User rejected candidate description.",
        raw_response_ref=str(attempt.id),
        metadata={"rejected_attempt_id": str(attempt.id)},
    )
    db.commit()
    db.refresh(rejected)
    return rejected


def _result(job: Job, status: str, notes: str, attempts: list[JobDescriptionResolutionAttempt]) -> dict:
    return {
        "job_id": str(job.id),
        "status": status,
        "description_status": job.description_status,
        "description_source": job.description_source,
        "description_quality": job.description_quality,
        "resolved_description_url": job.resolved_description_url,
        "confidence": job.resolution_confidence,
        "notes": notes,
        "attempts": attempts,
    }


def resolve_job_description(db: Session, job_id: UUID) -> dict | None:
    job = _job_with_context(db, job_id)
    if not job:
        return None
    if description_is_complete(job) and job.description_quality == "high":
        attempts = sorted(job.description_resolution_attempts, key=lambda item: item.created_at, reverse=True)
        return _result(job, "success", "Job already has a high-quality resolved description.", attempts)

    configs = _dedupe_configs(_direct_source_configs(job) + _saved_source_configs(db, job))
    attempts: list[JobDescriptionResolutionAttempt] = []
    best_review: tuple[NormalizedDiscoveredJob, JobMatchResult] | None = None
    if not configs:
        job.fetch_status = "needs_manual_review"
        job.resolution_notes = "No saved Greenhouse, Lever, or Ashby source is configured for this company."
        attempt = _write_attempt(
            db,
            job,
            source="ats",
            attempted_url=None,
            status="not_found",
            confidence=0.0,
            reason=job.resolution_notes,
        )
        attempts.append(attempt)
        best_review = None
        status = "not_found"
    else:
        status = "not_found"

    if configs:
      with httpx.Client(timeout=10.0, headers={"User-Agent": "CareerOpsAgent/0.1 job-description-resolver"}) as client:
        for config in configs:
            source = config.source.lower()
            try:
                postings = _fetch_jobs(client, config, include_description=True)
            except Exception as error:
                attempts.append(
                    _write_attempt(
                        db,
                        job,
                        source=source,
                        attempted_url=None,
                        status="error",
                        confidence=None,
                        reason=f"Failed to fetch {source} postings.",
                        error_message=str(error),
                        metadata={"company_key": config.company_key},
                    )
                )
                continue

            if not postings:
                attempts.append(
                    _write_attempt(
                        db,
                        job,
                        source=source,
                        attempted_url=None,
                        status="not_found",
                        confidence=0.0,
                        reason=f"No {source} postings returned for {config.company_key}.",
                        metadata={"company_key": config.company_key},
                    )
                )
                continue

            best_for_source: tuple[NormalizedDiscoveredJob, JobMatchResult] | None = None
            for posting in postings:
                if not _clean_description(posting.description) or len(_clean_description(posting.description)) < 120:
                    continue
                match = match_job_to_posting(job, posting)
                if best_for_source is None or match.confidence > best_for_source[1].confidence:
                    best_for_source = (posting, match)

            if not best_for_source:
                attempts.append(
                    _write_attempt(
                        db,
                        job,
                        source=source,
                        attempted_url=None,
                        status="not_found",
                        confidence=0.0,
                        reason=f"No {source} posting with a usable description matched the job.",
                        metadata={"company_key": config.company_key, "postings_seen": len(postings)},
                    )
                )
                continue

            posting, match = best_for_source
            if match.accepted:
                _apply_success(job, posting, match)
                attempt = _write_attempt(
                    db,
                    job,
                    source=source,
                    attempted_url=posting.job_url,
                    status="success",
                    confidence=match.confidence,
                    reason=job.resolution_notes or match.reason,
                    raw_response_ref=posting.external_job_id,
                    metadata={
                        "company_key": config.company_key,
                        "posting_title": posting.title,
                        "posting_company": posting.company_name,
                        "posting_location": posting.location,
                        "evidence": match.evidence,
                    },
                )
                attempts.append(attempt)
                write_audit_log(
                    db,
                    event_type="job_description.resolved_from_ats",
                    entity_type="job",
                    entity_id=job.id,
                    details={
                        "attempt_id": str(attempt.id),
                        "source": source,
                        "confidence": match.confidence,
                        "resolved_description_url": posting.job_url,
                    },
                )
                db.commit()
                db.refresh(job)
                db.refresh(attempt)
                return _result(job, "success", job.resolution_notes or "Description resolved.", attempts)

            if match.needs_review and (best_review is None or match.confidence > best_review[1].confidence):
                best_review = (posting, match)

            attempts.append(
                _write_attempt(
                    db,
                    job,
                    source=source,
                    attempted_url=posting.job_url,
                    status="needs_manual_review" if match.needs_review else "not_found",
                    confidence=match.confidence,
                    reason=f"Best {source} candidate was not auto-attached. {match.reason}.",
                    raw_response_ref=posting.external_job_id,
                    metadata={
                        "company_key": config.company_key,
                        "candidate_source": posting.source,
                        "posting_title": posting.title,
                        "posting_company": posting.company_name,
                        "posting_location": posting.location,
                        "candidate_description": _clean_description(posting.description),
                        "evidence": match.evidence,
                    },
                )
            )

    if best_review:
        posting, match = best_review
        job.fetch_status = "needs_manual_review"
        job.resolution_confidence = match.confidence
        job.resolution_notes = (
            f"Found possible {posting.source} match but confidence is below automatic attach threshold. {match.reason}."
        )
        status = "needs_manual_review"
    else:
        job.fetch_status = "not_found"
        job.resolution_confidence = 0.0
        job.resolution_notes = "No reliable Greenhouse, Lever, or Ashby match was found."
        status = "not_found"

    if status == "not_found":
        for candidate_url in _company_careers_candidate_urls(job):
            fetched = _fetch_public_job_page(job, candidate_url, respect_robots=True)
            attempt = _write_attempt(
                db,
                job,
                source="company_careers",
                attempted_url=candidate_url,
                status=fetched.get("status", "error"),
                confidence=fetched.get("confidence"),
                reason=fetched.get("reason", "Company careers page could not be resolved."),
                error_message=fetched.get("error_message"),
                metadata=fetched.get("metadata"),
            )
            attempts.append(attempt)
            if fetched.get("status") == "success":
                _apply_public_page_success(
                    job,
                    description=fetched["description"],
                    description_html=fetched.get("description_html"),
                    resolved_url=fetched.get("final_url") or candidate_url,
                    source="company_careers",
                    status="resolved_from_company_site",
                    quality=fetched.get("quality", "medium"),
                    confidence=fetched.get("confidence", 0.78),
                    notes="Resolved from a public page on the company's official domain.",
                    metadata=fetched.get("metadata"),
                )
                write_audit_log(
                    db,
                    event_type="job_description.resolved_from_company_site",
                    entity_type="job",
                    entity_id=job.id,
                    details={
                        "attempt_id": str(attempt.id),
                        "confidence": job.resolution_confidence,
                        "resolved_description_url": job.resolved_description_url,
                    },
                )
                db.commit()
                db.refresh(job)
                for item in attempts:
                    db.refresh(item)
                return _result(job, "success", job.resolution_notes or "", attempts)

        if attempts and any(item.attempted_source == "company_careers" for item in attempts):
            job.fetch_status = "needs_manual_review"
            job.resolution_notes = "ATS resolution failed and company careers lookup did not find a specific public job page."
            status = "needs_manual_review"
    db.commit()
    db.refresh(job)
    for attempt in attempts:
        db.refresh(attempt)
    return _result(job, status, job.resolution_notes or "", attempts)


def list_resolution_attempts(db: Session, job_id: UUID) -> list[JobDescriptionResolutionAttempt]:
    return list(
        db.scalars(
            select(JobDescriptionResolutionAttempt)
            .where(JobDescriptionResolutionAttempt.job_id == job_id)
            .order_by(JobDescriptionResolutionAttempt.created_at.desc())
        )
    )


def resolve_pending_descriptions(db: Session, *, limit: int = 10) -> dict:
    safe_limit = max(1, min(limit, 25))
    jobs = list(
        db.scalars(
            select(Job)
            .where(
                Job.description_status.in_(ELIGIBLE_RESOLUTION_STATUSES)
                | Job.fetch_status.in_({"pending", "error", "not_found"})
            )
            .order_by(Job.created_at.asc())
            .limit(safe_limit)
        )
    )
    summary = {
        "processed_count": 0,
        "resolved_count": 0,
        "needs_manual_review_count": 0,
        "not_found_count": 0,
        "error_count": 0,
        "results": [],
    }
    for job in jobs:
        summary["processed_count"] += 1
        try:
            result = resolve_job_description(db, job.id)
        except Exception as error:
            summary["error_count"] += 1
            result = {"job_id": str(job.id), "status": "error", "notes": str(error)}
        if result:
            if result["status"] == "success":
                summary["resolved_count"] += 1
            elif result["status"] == "needs_manual_review":
                summary["needs_manual_review_count"] += 1
            elif result["status"] == "not_found":
                summary["not_found_count"] += 1
            elif result["status"] == "error":
                summary["error_count"] += 1
            summary["results"].append(result)
    return summary
