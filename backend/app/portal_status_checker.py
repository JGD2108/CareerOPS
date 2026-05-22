from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse

import httpx

from app.models import PortalCheckConfidence, PublicJobStatus


OFFICIAL_ATS_HOST_MARKERS = {
    "greenhouse": ("greenhouse.io", "greenhouse-mail.io"),
    "lever": ("lever.co", "jobs.lever.co"),
    "ashby": ("ashbyhq.com", "jobs.ashbyhq.com"),
    "workday": ("myworkdayjobs.com", "workdayjobs.com"),
    "smartrecruiters": ("smartrecruiters.com",),
    "icims": ("icims.com",),
    "taleo": ("taleo.net",),
    "successfactors": ("successfactors.com", "sapsf.com"),
}

LINKEDIN_HOST_MARKERS = ("linkedin.com", "lnkd.in")

OPEN_MARKERS = (
    "apply now",
    "apply for this job",
    "submit application",
    "start your application",
    "complete application",
    "job details",
    "job description",
)

NO_LONGER_ACCEPTING_MARKERS = (
    "no longer accepting applications",
    "this position is no longer accepting applications",
    "applications are closed",
    "application period has closed",
)

CLOSED_MARKERS = (
    "job posting has expired",
    "this job has expired",
    "position has been filled",
    "role has been filled",
    "job is closed",
    "this requisition has been closed",
)

REMOVED_MARKERS = (
    "job is no longer available",
    "job you are looking for is no longer available",
    "job unavailable",
    "posting is no longer available",
    "page not found",
    "404",
)

LOGIN_REQUIRED_MARKERS = (
    "sign in to view",
    "login to view",
    "log in to view",
    "candidate home",
    "candidate portal",
    "sign into your account",
    "sign in to your account",
    "email address and password",
)

USER_ACTION_MARKERS = (
    "multi-factor authentication",
    "multifactor authentication",
    "two-factor authentication",
    "verification code",
    "captcha",
    "i'm not a robot",
    "suspicious login",
)


@dataclass(frozen=True)
class PublicStatusCheckResult:
    source_url: str
    final_url: str
    status: PublicJobStatus
    confidence: PortalCheckConfidence
    evidence_summary: str
    login_required: bool = False
    user_action_required: bool = False
    provider: str | None = None
    redirected: bool = False
    http_status_code: int | None = None


def normalize_page_text(body_text: str | None) -> str:
    return re.sub(r"\s+", " ", body_text or "").strip().lower()


def detect_provider(url: str | None) -> str | None:
    if not url:
        return None
    host = urlparse(url).netloc.lower()
    for provider, markers in OFFICIAL_ATS_HOST_MARKERS.items():
        if any(marker in host for marker in markers):
            return provider
    if any(marker in host for marker in LINKEDIN_HOST_MARKERS):
        return "linkedin"
    return None


def is_linkedin_url(url: str | None) -> bool:
    return detect_provider(url) == "linkedin"


def has_user_action_wall(body_text: str | None) -> bool:
    text = normalize_page_text(body_text)
    return any(marker in text for marker in USER_ACTION_MARKERS)


def has_login_wall(body_text: str | None) -> bool:
    text = normalize_page_text(body_text)
    if any(marker in text for marker in LOGIN_REQUIRED_MARKERS):
        return True
    return bool(re.search(r"<form[^>]+(?:login|signin|sign-in|password)", body_text or "", flags=re.IGNORECASE))


def classify_public_job_page(
    source_url: str,
    status_code: int,
    final_url: str,
    body_text: str | None,
) -> PublicStatusCheckResult:
    provider = detect_provider(final_url) or detect_provider(source_url)
    redirected = source_url.rstrip("/") != final_url.rstrip("/")
    text = normalize_page_text(body_text)

    if is_linkedin_url(source_url) or is_linkedin_url(final_url):
        return PublicStatusCheckResult(
            source_url=source_url,
            final_url=final_url,
            status=PublicJobStatus.UNKNOWN,
            confidence=PortalCheckConfidence.HIGH,
            evidence_summary="LinkedIn URLs are stored as references only; the agent does not scrape or automate LinkedIn.",
            provider="linkedin",
            redirected=redirected,
            http_status_code=status_code,
        )

    if status_code in {401, 403}:
        return PublicStatusCheckResult(
            source_url=source_url,
            final_url=final_url,
            status=PublicJobStatus.LOGIN_REQUIRED,
            confidence=PortalCheckConfidence.HIGH,
            evidence_summary=f"The page returned HTTP {status_code}, which indicates authentication is required.",
            login_required=True,
            provider=provider,
            redirected=redirected,
            http_status_code=status_code,
        )

    if status_code in {404, 410}:
        return PublicStatusCheckResult(
            source_url=source_url,
            final_url=final_url,
            status=PublicJobStatus.REMOVED,
            confidence=PortalCheckConfidence.HIGH,
            evidence_summary=f"The page returned HTTP {status_code}, so the posting appears removed.",
            provider=provider,
            redirected=redirected,
            http_status_code=status_code,
        )

    if status_code >= 500:
        return PublicStatusCheckResult(
            source_url=source_url,
            final_url=final_url,
            status=PublicJobStatus.UNKNOWN,
            confidence=PortalCheckConfidence.LOW,
            evidence_summary=f"The page returned HTTP {status_code}; retry later before changing application status.",
            provider=provider,
            redirected=redirected,
            http_status_code=status_code,
        )

    if has_user_action_wall(body_text):
        return PublicStatusCheckResult(
            source_url=source_url,
            final_url=final_url,
            status=PublicJobStatus.LOGIN_REQUIRED,
            confidence=PortalCheckConfidence.HIGH,
            evidence_summary="The portal showed MFA, CAPTCHA, or suspicious-login verification. User action is required.",
            login_required=True,
            user_action_required=True,
            provider=provider,
            redirected=redirected,
            http_status_code=status_code,
        )

    if has_login_wall(body_text):
        return PublicStatusCheckResult(
            source_url=source_url,
            final_url=final_url,
            status=PublicJobStatus.LOGIN_REQUIRED,
            confidence=PortalCheckConfidence.HIGH,
            evidence_summary="The portal requires login before the application status can be viewed.",
            login_required=True,
            provider=provider,
            redirected=redirected,
            http_status_code=status_code,
        )

    if any(marker in text for marker in NO_LONGER_ACCEPTING_MARKERS):
        return PublicStatusCheckResult(
            source_url=source_url,
            final_url=final_url,
            status=PublicJobStatus.NO_LONGER_ACCEPTING_APPLICATIONS,
            confidence=PortalCheckConfidence.HIGH,
            evidence_summary="The page says it is no longer accepting applications.",
            provider=provider,
            redirected=redirected,
            http_status_code=status_code,
        )

    if any(marker in text for marker in CLOSED_MARKERS):
        return PublicStatusCheckResult(
            source_url=source_url,
            final_url=final_url,
            status=PublicJobStatus.CLOSED,
            confidence=PortalCheckConfidence.HIGH,
            evidence_summary="The page says the role is closed, expired, or filled.",
            provider=provider,
            redirected=redirected,
            http_status_code=status_code,
        )

    if any(marker in text for marker in REMOVED_MARKERS):
        return PublicStatusCheckResult(
            source_url=source_url,
            final_url=final_url,
            status=PublicJobStatus.REMOVED,
            confidence=PortalCheckConfidence.MEDIUM,
            evidence_summary="The page text suggests the posting is no longer available.",
            provider=provider,
            redirected=redirected,
            http_status_code=status_code,
        )

    if redirected and provider is None:
        return PublicStatusCheckResult(
            source_url=source_url,
            final_url=final_url,
            status=PublicJobStatus.REDIRECTED,
            confidence=PortalCheckConfidence.MEDIUM,
            evidence_summary="The source URL redirected to another page and no reliable open/closed signal was found.",
            provider=provider,
            redirected=True,
            http_status_code=status_code,
        )

    if any(marker in text for marker in OPEN_MARKERS):
        return PublicStatusCheckResult(
            source_url=source_url,
            final_url=final_url,
            status=PublicJobStatus.OPEN,
            confidence=PortalCheckConfidence.MEDIUM,
            evidence_summary="The page still exposes job details or application actions.",
            provider=provider,
            redirected=redirected,
            http_status_code=status_code,
        )

    return PublicStatusCheckResult(
        source_url=source_url,
        final_url=final_url,
        status=PublicJobStatus.UNKNOWN,
        confidence=PortalCheckConfidence.LOW,
        evidence_summary="The page loaded, but no reliable status signal was found.",
        provider=provider,
        redirected=redirected,
        http_status_code=status_code,
    )


def check_public_job_url(url: str, timeout_seconds: float = 20.0) -> PublicStatusCheckResult:
    if is_linkedin_url(url):
        return classify_public_job_page(url, 0, url, "")

    try:
        with httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "CareerOpsAgent/0.1 (+local desktop app; respectful status checker; "
                    "no LinkedIn scraping)"
                )
            },
        ) as client:
            response = client.get(url)
    except Exception as error:
        return PublicStatusCheckResult(
            source_url=url,
            final_url=url,
            status=PublicJobStatus.UNKNOWN,
            confidence=PortalCheckConfidence.LOW,
            evidence_summary=f"Public page check failed: {error}",
            provider=detect_provider(url),
        )

    return classify_public_job_page(
        source_url=url,
        status_code=response.status_code,
        final_url=str(response.url),
        body_text=response.text[:12000],
    )
