from __future__ import annotations

import base64
import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parsedate_to_datetime, parseaddr
from pathlib import Path
from typing import Any
from uuid import UUID

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app import crud
from app.audit import write_audit_log
from app.config import get_settings
from app.job_fit import ensure_job_score
from app.models import (
    Application,
    ApplicationStatus,
    Company,
    Email,
    EmailCategory,
    Job,
    MessageDraft,
    MessageDraftStatus,
    MessageDraftType,
    RawEmail,
    RawJob,
)
from app.application_tracker import mark_application_applied
from app.next_action_agent import sync_next_actions
from app.profile_ingestion import get_profile
from app.schemas import ApplicationCreate, JobCreate


settings = get_settings()

# Based on Gmail docs, we use the narrowest practical pair for this phase:
# gmail.readonly to read message content and gmail.compose to create drafts.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


@dataclass
class GmailStatus:
    credentials_file_exists: bool
    token_file_exists: bool
    authenticated: bool
    scopes: list[str]


@dataclass
class NormalizedEmailPayload:
    gmail_message_id: str
    gmail_thread_id: str
    history_id: str | None
    label_ids: list[str]
    company_name: str | None
    from_name: str | None
    from_email: str
    subject: str | None
    snippet: str | None
    body_text: str | None
    category: EmailCategory
    urgency: str
    requires_reply: bool
    suggested_action: str
    received_at: datetime | None
    raw_payload: dict[str, Any]


def _credentials_path() -> Path:
    path = Path(settings.gmail_credentials_file).resolve()
    _write_secret_json_if_needed(path, settings.gmail_credentials_json)
    return path


def _token_path() -> Path:
    path = Path(settings.gmail_token_file).resolve()
    _write_secret_json_if_needed(path, settings.gmail_token_json)
    return path


def _write_secret_json_if_needed(path: Path, raw_json: str | None) -> None:
    if not raw_json or path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw_json, encoding="utf-8")


def _oauth_state_path() -> Path:
    return _token_path().with_name("gmail_oauth_state.txt")


def gmail_status() -> GmailStatus:
    credentials_path = _credentials_path()
    token_path = _token_path()
    creds = None
    authenticated = False
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            authenticated = bool(creds and (creds.valid or creds.refresh_token))
        except Exception:
            authenticated = False
    return GmailStatus(
        credentials_file_exists=credentials_path.exists(),
        token_file_exists=token_path.exists(),
        authenticated=authenticated,
        scopes=SCOPES,
    )


def ensure_gmail_authenticated(interactive: bool = False) -> Credentials:
    credentials_path = _credentials_path()
    token_path = _token_path()
    token_path.parent.mkdir(parents=True, exist_ok=True)

    if not credentials_path.exists():
        raise ValueError(f"Gmail credentials file not found at {credentials_path}")

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    if creds and creds.valid:
        return creds

    if not interactive:
        raise ValueError("Gmail token not found or expired. Run Gmail auth first.")

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    creds = flow.run_local_server(port=0)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def authenticate_gmail() -> GmailStatus:
    ensure_gmail_authenticated(interactive=True)
    return gmail_status()


def start_gmail_web_oauth() -> dict[str, str]:
    credentials_path = _credentials_path()
    if not credentials_path.exists():
        raise ValueError(f"Gmail credentials file not found at {credentials_path}")
    if settings.gmail_oauth_redirect_uri.startswith("http://127.0.0.1") or settings.gmail_oauth_redirect_uri.startswith("http://localhost"):
        os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

    flow = Flow.from_client_secrets_file(
        str(credentials_path),
        scopes=SCOPES,
        redirect_uri=settings.gmail_oauth_redirect_uri,
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    state_path = _oauth_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(state, encoding="utf-8")
    return {"authorization_url": authorization_url, "state": state, "redirect_uri": settings.gmail_oauth_redirect_uri}


def complete_gmail_web_oauth(*, code: str, state: str | None) -> GmailStatus:
    credentials_path = _credentials_path()
    state_path = _oauth_state_path()
    if state_path.exists():
        expected_state = state_path.read_text(encoding="utf-8").strip()
        if expected_state and state != expected_state:
            raise ValueError("Invalid Gmail OAuth state. Start the OAuth flow again.")
    if settings.gmail_oauth_redirect_uri.startswith("http://127.0.0.1") or settings.gmail_oauth_redirect_uri.startswith("http://localhost"):
        os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

    flow = Flow.from_client_secrets_file(
        str(credentials_path),
        scopes=SCOPES,
        state=state,
        redirect_uri=settings.gmail_oauth_redirect_uri,
    )
    flow.fetch_token(code=code)
    token_path = _token_path()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(flow.credentials.to_json(), encoding="utf-8")
    if state_path.exists():
        state_path.unlink()
    return gmail_status()


def _gmail_service(interactive: bool = False):
    creds = ensure_gmail_authenticated(interactive=interactive)
    return build("gmail", "v1", credentials=creds)


def _headers_map(payload: dict) -> dict[str, str]:
    return {item["name"]: item["value"] for item in payload.get("headers", [])}


def _decode_base64url(data: str | None) -> str:
    if not data:
        return ""
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding).decode("utf-8", errors="replace")


def _extract_body_text(payload: dict) -> str:
    mime_type = payload.get("mimeType")
    body = payload.get("body") or {}
    if mime_type == "text/plain":
        return _decode_base64url(body.get("data"))
    if mime_type == "text/html":
        html = _decode_base64url(body.get("data"))
        return re.sub(r"<[^>]+>", " ", html)

    text_parts = []
    for part in payload.get("parts", []) or []:
        extracted = _extract_body_text(part)
        if extracted.strip():
            text_parts.append(extracted)
    return "\n".join(text_parts).strip()


def _extract_company_name(from_email: str, from_name: str | None) -> str | None:
    if from_name and "recruit" not in from_name.lower():
        return from_name.strip()
    domain = from_email.split("@")[-1].lower()
    generic_domains = [
        "greenhouse-mail.io",
        "icims.com",
        "ashbyhq.com",
        "mail2world.com",
        "lever.co",
    ]
    if any(item in domain for item in generic_domains):
        return None
    if domain.endswith("gmail.com") or domain.endswith("outlook.com"):
        return from_name.strip() if from_name else None
    company = domain.split(".")[0].replace("-", " ").replace("_", " ").strip()
    return company.title() if company else None


def _has_any(content: str, terms: list[str]) -> bool:
    return any(term in content for term in terms)


def _classify_email(subject: str | None, body_text: str | None, from_email: str) -> tuple[EmailCategory, str, bool, str]:
    content = " ".join([subject or "", body_text or "", from_email]).lower()
    sender = from_email.lower()

    if "linkedin.com" in sender and _has_any(
        content,
        [
            "your application was sent",
            "your application has been sent",
            "application was sent to",
            "your application to",
            "you applied to",
            "application submitted",
            "applied for",
        ],
    ):
        return EmailCategory.APPLICATION_CONFIRMATION, "normal", False, "Imported as a LinkedIn application confirmation and marked applied when the role can be parsed."

    if "jobalerts-noreply@linkedin.com" in sender or _has_any(content, ["job alert", "new jobs match your preferences", "linkedin job alerts", "view job: https://www.linkedin.com/comm/jobs/view"]):
        return EmailCategory.JOB_ALERT, "normal", False, "Review the job alert and score any relevant roles before applying."

    if "newsletter" in (subject or "").lower():
        return EmailCategory.OTHER, "normal", False, "Ignore newsletter content for CareerOps unless manually reviewed."
    if _has_any(content, ["your resume has been received", "should your qualifications and experience meet"]):
        return EmailCategory.OTHER, "normal", False, "Application receipt detected; review manually if you want to add it to the tracker."

    low_value_senders = [
        "disneyplus@",
        "mail2.disneyplus.com",
        "us-news.comms.adidas.com",
        "deliver.ieee.org",
        "ieee-iec@",
        "newsletter",
        "no-reply",
        "noreply",
    ]
    marketing_or_security_terms = [
        "shop the",
        "new jersey",
        "display images",
        "unsubscribe",
        "promotional",
        "newsletter",
        "career-boosting resources",
        "nuevo inicio de sesión",
        "new login",
        "security alert",
        "verification code",
        "password reset",
    ]
    if _has_any(sender, low_value_senders) or _has_any(content, marketing_or_security_terms):
        actionable_terms = [
            "recruiter",
            "talent acquisition",
            "hiring team",
            "next step",
            "technical interview",
            "phone screen",
            "coding assessment",
            "offer letter",
        ]
        if not _has_any(content, actionable_terms):
            return EmailCategory.OTHER, "normal", False, "Ignore for CareerOps unless it is manually linked to an application."

    if _has_any(content, ["offer letter", "job offer", "offer details", "compensation package"]):
        return EmailCategory.OFFER, "high", True, "Review the offer and draft a thoughtful response."
    if _has_any(content, ["technical interview", "interview invitation", "schedule an interview", "schedule a call", "phone screen", "your availability", "calendar invite"]):
        return EmailCategory.INTERVIEW_INVITATION, "high", True, "Reply with availability and prepare for the interview."
    if _has_any(content, ["assessment", "coding challenge", "take-home", "hackerrank", "codility"]):
        return EmailCategory.CODING_ASSESSMENT, "high", True, "Review the assessment instructions and confirm your plan."
    if _has_any(
        content,
        [
            "unfortunately",
            "regret to inform",
            "not moving forward",
            "will not be moving forward",
            "you were not selected",
            "not selected for",
            "not be selected for",
            "decided to move forward with other candidates",
            "pursue other candidates",
            "no longer under consideration",
            "unable to offer",
            "we have decided",
            "no continuaremos",
            "no avanzaremos",
            "no has sido seleccionado",
            "lamentamos informarte",
            "rechazada",
            "rechazado",
        ],
    ):
        return EmailCategory.REJECTION, "normal", False, "Update the tracker to rejected and archive the thread."
    if _has_any(content, ["document", "paperwork", "share your resume", "provide id", "visa", "transcript"]):
        return EmailCategory.DOCUMENTS_REQUESTED, "high", True, "Prepare the requested documents and draft a reply."
    if _has_any(content, ["complete the form", "application form", "questionnaire", "fill out"]):
        return EmailCategory.FORM_PENDING, "high", True, "Complete the requested form and confirm back."
    if _has_any(content, ["following up", "wanted to follow up", "checking in", "recruiter", "talent acquisition"]):
        return EmailCategory.RECRUITER_FOLLOW_UP, "normal", True, "Draft a recruiter reply and decide whether to continue."
    return EmailCategory.OTHER, "normal", False, "Review manually and decide whether action is needed."


def _clean_alert_text(value: str) -> str:
    value = re.sub(r"[\u034f\u200b-\u200f\u202a-\u202e]", " ", value)
    return re.sub(r"\s+", " ", value).strip(" -|•\t\r\n")


def _normalize_role_text(value: str) -> str:
    normalized = value.lower().replace("/", " ")
    normalized = normalized.replace("-", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def _extract_company_hints(subject: str | None, snippet: str | None, body_text: str | None) -> set[str]:
    raw_content = " ".join([subject or "", snippet or "", body_text or ""])
    hints: set[str] = set()
    patterns = [
        r"\bapplying at\s+(?P<company>[A-Z][A-Za-z0-9&()'\- ]{1,80}?)(?:[.,!:\n]|$|\sand\s|\svia\s)",
        r"\brole at\s+(?P<company>[A-Z][A-Za-z0-9&()'\- ]{1,80}?)(?:[.,!:\n]|$|\sand\s|\svia\s)",
        r"\binterest in\s+[A-Za-z0-9&()'\- /.,]{1,120}?\s+at\s+(?P<company>[A-Z][A-Za-z0-9&()'\- ]{1,80}?)(?:[.,!:\n]|$|\sand\s|\svia\s)",
        r"\bat\s+(?P<company>[A-Z][A-Za-z0-9&()'\- ]{1,80}?)(?:[.,!:\n]|$|\sand\s|\svia\s)",
        r"\bwith\s+(?P<company>[A-Z][A-Za-z0-9&()'\- ]{1,80}?)(?:[.,!:\n]|$|\sand\s|\svia\s)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, raw_content):
            hints.add(_normalize_role_text(match.group("company")))
    return {hint for hint in hints if hint and len(hint) >= 3}


def _target_role_keywords() -> list[str]:
    return [
        _normalize_role_text(keyword)
        for keyword in settings.target_role_keywords.split(",")
        if keyword.strip()
    ]


def _is_target_role(title: str) -> bool:
    normalized_title = _normalize_role_text(title)
    keywords = _target_role_keywords()
    if any(keyword and keyword in normalized_title for keyword in keywords):
        return True
    if "full stack" in normalized_title or "fullstack" in normalized_title:
        return True

    has_engineering_noun = any(
        term in normalized_title
        for term in ["engineer", "engineering", "developer", "desarrollador", "ingeniero", "programador"]
    )
    if not has_engineering_noun:
        return False

    return any(
        term in normalized_title
        for term in [
            "software",
            "backend",
            "back end",
            "full stack",
            "fullstack",
            "data",
            "datos",
            "python",
        ]
    )


def _extract_linkedin_job_alerts(email_record: Email) -> list[dict[str, str | None]]:
    if email_record.category != EmailCategory.JOB_ALERT:
        return []

    content = "\n".join(
        item for item in [email_record.subject, email_record.snippet, email_record.body_text] if item
    )
    urls = re.findall(r"https?://(?:www\.)?linkedin\.com/(?:comm/)?jobs/view/[^\s<>)\"]+", content)
    candidates: list[dict[str, str | None]] = []
    seen: set[tuple[str, str]] = set()

    for line in content.splitlines():
        cleaned = _clean_alert_text(line)
        lowered = cleaned.lower()
        if not cleaned or len(cleaned) > 180:
            continue
        if lowered.startswith(("posted on", "view job", "recommended for you", "your saved job", "new jobs similar to")):
            continue
        if "is still available" in lowered or "saved job" in lowered or " expiring " in f" {lowered} ":
            continue
        match = re.search(r"(?P<title>[A-Za-z0-9][A-Za-z0-9+/.,()#&:\- ]{4,120}?)\s+at\s+(?P<company>[A-Za-z0-9][A-Za-z0-9&.,()'\- ]{1,80})$", cleaned)
        if not match:
            continue
        title = _clean_alert_text(match.group("title"))
        company = _clean_alert_text(match.group("company"))
        if not _is_target_role(title):
            continue
        key = (title.lower(), company.lower())
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "title": title,
                "company": company,
                "url": urls[len(candidates)] if len(candidates) < len(urls) else None,
            }
        )

    return candidates


def _existing_linkedin_job(db: Session, *, title: str, company: str, source_url: str | None, source: str) -> Job | None:
    if source_url:
        existing = db.scalar(select(Job).where(Job.source == source, Job.source_url == source_url))
        if existing:
            return existing

    company_record = db.scalar(select(Company).where(Company.name == company))
    if not company_record:
        return None
    return db.scalar(
        select(Job).where(
            Job.company_id == company_record.id,
            Job.title == title,
            Job.source == source,
        )
    )


def _create_or_get_linkedin_job(
    db: Session,
    *,
    title: str,
    company: str,
    source_url: str | None,
    source: str,
    email_record: Email,
    application_status: ApplicationStatus | None,
) -> tuple[Job, bool, bool, Application | None]:
    existing_job = _existing_linkedin_job(db, title=title, company=company, source_url=source_url, source=source)
    job_created = False
    if existing_job:
        normalized_job = existing_job
    else:
        description = (
            f"LinkedIn email source.\n\nRole: {title}\nCompany: {company}\n\n"
            f"Email subject: {email_record.subject or 'No subject'}\n"
            f"Snippet: {_clean_alert_text(email_record.snippet or '')}"
        )
        normalized_job = crud.create_job(
            db,
            JobCreate(
                title=title,
                company_name=company,
                description=description,
                source_url=source_url,
                source=source,
            ),
        )
        job_created = True

    normalized_job.raw_payload = {
        **(normalized_job.raw_payload or {}),
        "source_kind": source,
        "source_email_id": str(email_record.id),
        "raw_email_id": str(email_record.raw_email_id),
        "gmail_message_id": email_record.raw_email.gmail_message_id,
        "gmail_thread_id": email_record.raw_email.gmail_thread_id,
        "email_subject": email_record.subject,
        "email_from": email_record.from_email,
        "email_received_at": email_record.received_at.isoformat() if email_record.received_at else None,
        "source_url": source_url,
    }

    application_created = False
    application: Application | None = None
    if application_status:
        application = db.scalar(select(Application).where(Application.job_id == normalized_job.id))
        if not application:
            application = crud.create_application(
                db,
                ApplicationCreate(
                    job_id=normalized_job.id,
                    status=ApplicationStatus.FOUND,
                    notes="Created from LinkedIn email activity. Review source email before further action.",
                ),
            )
            application_created = True
        if application and application_status == ApplicationStatus.APPLIED:
            if application.status in {
                ApplicationStatus.FOUND,
                ApplicationStatus.REVIEWED,
                ApplicationStatus.CV_GENERATED,
                ApplicationStatus.APPLIED,
            }:
                mark_application_applied(
                    db,
                    application.id,
                    notes="Marked applied from LinkedIn application confirmation email.",
                    applied_at=email_record.received_at,
                )
            elif application.applied_at is None:
                application.applied_at = email_record.received_at

    return normalized_job, job_created, application_created, application


def _auto_score_job_if_possible(db: Session, job_id: UUID) -> bool:
    if not get_profile(db):
        return False
    return ensure_job_score(db, job_id) is not None


def ingest_linkedin_job_alert(db: Session, email_record: Email) -> dict[str, Any]:
    created_or_existing_jobs: list[Job] = []
    auto_scored_jobs = 0
    seen_external_ids: set[str] = set()
    for candidate in _extract_linkedin_job_alerts(email_record):
        title = candidate["title"]
        company = candidate["company"]
        if not title or not company:
            continue

        source_url = candidate["url"]
        external_job_id = None
        if source_url:
            id_match = re.search(r"/view/(\d+)", source_url)
            external_job_id = id_match.group(1) if id_match else source_url
        if not external_job_id:
            digest_input = f"{email_record.raw_email.gmail_message_id}:{title}:{company}"
            external_job_id = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()[:24]
        if external_job_id in seen_external_ids:
            continue
        seen_external_ids.add(external_job_id)

        with db.no_autoflush:
            existing_raw_job = db.scalar(
                select(RawJob).where(
                    RawJob.source == "linkedin_email_alert",
                    RawJob.source_company_key == "linkedin",
                    RawJob.external_job_id == external_job_id,
                )
            )
        if existing_raw_job and existing_raw_job.normalized_job:
            if _auto_score_job_if_possible(db, existing_raw_job.normalized_job.id):
                auto_scored_jobs += 1
            created_or_existing_jobs.append(existing_raw_job.normalized_job)
            continue
        normalized_job, _, _, application = _create_or_get_linkedin_job(
            db,
            title=title,
            company=company,
            source_url=source_url,
            source="linkedin_email_alert",
            email_record=email_record,
            application_status=ApplicationStatus.FOUND,
        )
        if application:
            email_record.application_id = application.id

        raw_job = existing_raw_job or RawJob(
            source="linkedin_email_alert",
            source_company_key="linkedin",
            external_job_id=external_job_id,
            company_name=company,
            title=title,
            location=None,
            job_url=source_url,
            raw_payload={
                "email_id": str(email_record.id),
                "raw_email_id": str(email_record.raw_email_id),
                "gmail_message_id": email_record.raw_email.gmail_message_id,
                "gmail_thread_id": email_record.raw_email.gmail_thread_id,
                "subject": email_record.subject,
                "snippet": email_record.snippet,
            },
        )
        raw_job.normalized_job_id = normalized_job.id
        db.add(raw_job)
        if _auto_score_job_if_possible(db, normalized_job.id):
            auto_scored_jobs += 1

        created_or_existing_jobs.append(normalized_job)

    if created_or_existing_jobs:
        write_audit_log(
            db,
            event_type="gmail.linkedin_job_alert_ingested",
            entity_type="email",
            entity_id=email_record.id,
            details={"jobs_found": len(created_or_existing_jobs), "auto_scored_jobs": auto_scored_jobs},
        )
        db.commit()
    return {"jobs": created_or_existing_jobs, "auto_scored_jobs": auto_scored_jobs}


def _extract_linkedin_application_confirmations(email_record: Email) -> list[dict[str, str | None]]:
    if email_record.category != EmailCategory.APPLICATION_CONFIRMATION:
        return []

    content = "\n".join(
        item for item in [email_record.subject, email_record.snippet, email_record.body_text] if item
    )
    cleaned_content = _clean_alert_text(content)
    urls = re.findall(r"https?://(?:www\.)?linkedin\.com/(?:comm/)?jobs/view/[^\s<>)\"]+", cleaned_content)
    patterns = [
        r"your application to (?P<title>[A-Za-z0-9][A-Za-z0-9+/.,()#&:\- ]{3,120}?) at (?P<company>[A-Za-z0-9][A-Za-z0-9&.,()'\- ]{1,80})(?:[.!]|$)",
        r"you applied to (?P<title>[A-Za-z0-9][A-Za-z0-9+/.,()#&:\- ]{3,120}?) at (?P<company>[A-Za-z0-9][A-Za-z0-9&.,()'\- ]{1,80})(?:[.!]|$)",
        r"application (?:for|to) (?P<title>[A-Za-z0-9][A-Za-z0-9+/.,()#&:\- ]{3,120}?) at (?P<company>[A-Za-z0-9][A-Za-z0-9&.,()'\- ]{1,80})(?:[.!]|$)",
        r"(?P<title>[A-Za-z0-9][A-Za-z0-9+/.,()#&:\- ]{4,120}?) at (?P<company>[A-Za-z0-9][A-Za-z0-9&.,()'\- ]{1,80})(?:[.!]|$)",
    ]

    candidates: list[dict[str, str | None]] = []
    seen: set[tuple[str, str]] = set()

    for line in content.splitlines():
        cleaned = _clean_alert_text(line)
        match = re.search(
            r"application (?:was|has been) sent to (?P<company>[A-Za-z0-9][A-Za-z0-9&.,()'\- ]{1,80})$",
            cleaned,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        title = "LinkedIn application confirmation - role not available"
        company = _clean_alert_text(match.group("company"))
        key = (title.lower(), company.lower())
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "title": title,
                "company": company,
                "url": urls[len(candidates)] if len(candidates) < len(urls) else None,
            }
        )

    for cleaned_line in [_clean_alert_text(line) for line in content.splitlines()]:
        if not cleaned_line or len(cleaned_line) > 260:
            continue
        for pattern in patterns:
            match = re.search(pattern, cleaned_line, flags=re.IGNORECASE)
            if not match:
                continue
            title = _clean_alert_text(match.group("title"))
            company = _clean_alert_text(match.group("company"))
            title = re.sub(r"^(your application (?:was|has been) sent to|application submitted for)\s+", "", title, flags=re.IGNORECASE)
            if not title or not company or len(title) < 3 or len(title) > 160:
                continue
            key = (title.lower(), company.lower())
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                {
                    "title": title,
                    "company": company,
                    "url": urls[len(candidates)] if len(candidates) < len(urls) else None,
                }
            )

    return candidates


def ingest_linkedin_application_confirmation(db: Session, email_record: Email) -> dict[str, int]:
    result = {"jobs_imported": 0, "applications_created": 0, "applications_marked_applied": 0, "jobs_auto_scored": 0}
    seen_external_ids: set[str] = set()
    for candidate in _extract_linkedin_application_confirmations(email_record):
        title = candidate["title"]
        company = candidate["company"]
        if not title or not company:
            continue

        source_url = candidate["url"]
        external_job_id = None
        if source_url:
            id_match = re.search(r"/view/(\d+)", source_url)
            external_job_id = id_match.group(1) if id_match else source_url
        if not external_job_id:
            digest_input = f"{email_record.raw_email.gmail_message_id}:{title}:{company}:applied"
            external_job_id = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()[:24]
        if external_job_id in seen_external_ids:
            continue
        seen_external_ids.add(external_job_id)

        with db.no_autoflush:
            existing_raw_job = db.scalar(
                select(RawJob).where(
                    RawJob.source == "linkedin_application_email",
                    RawJob.source_company_key == "linkedin",
                    RawJob.external_job_id == external_job_id,
                )
            )
        if existing_raw_job and existing_raw_job.normalized_job:
            normalized_job = existing_raw_job.normalized_job
            application_created = False
            if _auto_score_job_if_possible(db, normalized_job.id):
                result["jobs_auto_scored"] += 1
        else:
            normalized_job, job_created, application_created, application = _create_or_get_linkedin_job(
                db,
                title=title,
                company=company,
                source_url=source_url,
                source="linkedin_application_email",
                email_record=email_record,
                application_status=ApplicationStatus.APPLIED,
            )
            result["jobs_imported"] += int(job_created)

        raw_job = existing_raw_job or RawJob(
            source="linkedin_application_email",
            source_company_key="linkedin",
            external_job_id=external_job_id,
            company_name=company,
            title=title,
            location=None,
            job_url=source_url,
            raw_payload={
                "email_id": str(email_record.id),
                "raw_email_id": str(email_record.raw_email_id),
                "gmail_message_id": email_record.raw_email.gmail_message_id,
                "gmail_thread_id": email_record.raw_email.gmail_thread_id,
                "subject": email_record.subject,
                "snippet": email_record.snippet,
                "activity": "application_confirmation",
            },
        )
        raw_job.normalized_job_id = normalized_job.id
        db.add(raw_job)
        if _auto_score_job_if_possible(db, normalized_job.id):
            result["jobs_auto_scored"] += 1

        application = db.scalar(select(Application).where(Application.job_id == normalized_job.id))
        if application:
            email_record.application_id = application.id
            if application.status in {
                ApplicationStatus.FOUND,
                ApplicationStatus.REVIEWED,
                ApplicationStatus.CV_GENERATED,
                ApplicationStatus.APPLIED,
            } and (application.status != ApplicationStatus.APPLIED or application.applied_at != email_record.received_at):
                mark_application_applied(
                    db,
                    application.id,
                    notes="Marked applied from LinkedIn application confirmation email.",
                    applied_at=email_record.received_at,
                )
            elif application.applied_at is None:
                application.applied_at = email_record.received_at
            result["applications_marked_applied"] += int(application.status == ApplicationStatus.APPLIED)
        result["applications_created"] += int(application_created)

    if sum(result.values()):
        write_audit_log(
            db,
            event_type="gmail.linkedin_application_confirmations_ingested",
            entity_type="email",
            entity_id=email_record.id,
            details=result,
        )
        db.commit()
    return result


def _parse_received_at(headers: dict[str, str]) -> datetime | None:
    value = headers.get("Date")
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def normalize_gmail_message(message: dict[str, Any]) -> NormalizedEmailPayload:
    payload = message.get("payload", {})
    headers = _headers_map(payload)
    from_name, from_email = parseaddr(headers.get("From", ""))
    subject = headers.get("Subject")
    body_text = _extract_body_text(payload)
    category, urgency, requires_reply, suggested_action = _classify_email(subject, body_text, from_email)
    company_name = _extract_company_name(from_email, from_name)

    return NormalizedEmailPayload(
        gmail_message_id=message["id"],
        gmail_thread_id=message["threadId"],
        history_id=message.get("historyId"),
        label_ids=message.get("labelIds", []),
        company_name=company_name,
        from_name=from_name or None,
        from_email=from_email,
        subject=subject,
        snippet=message.get("snippet"),
        body_text=body_text,
        category=category,
        urgency=urgency,
        requires_reply=requires_reply,
        suggested_action=suggested_action,
        received_at=_parse_received_at(headers),
        raw_payload=message,
    )


def _match_application(db: Session, company_name: str | None) -> Application | None:
    if not company_name:
        return None
    return db.scalar(
        select(Application)
        .join(Job, Application.job_id == Job.id)
        .join(Company, Job.company_id == Company.id)
        .where(Company.name.ilike(f"%{company_name}%"))
        .order_by(Application.updated_at.desc())
    )


def _match_application_by_email_content(
    db: Session,
    *,
    company_name: str | None,
    subject: str | None,
    snippet: str | None,
    body_text: str | None,
    received_at: datetime | None,
    category: EmailCategory,
) -> Application | None:
    raw_content = " ".join([subject or "", snippet or "", body_text or ""])
    content = _normalize_role_text(raw_content)
    normalized_company_name = _normalize_role_text(company_name) if company_name else ""
    company_hints = _extract_company_hints(subject, snippet, body_text)
    company_signal_present = bool(normalized_company_name or company_hints)
    applications = list(
        db.scalars(
            select(Application)
            .join(Job, Application.job_id == Job.id)
            .join(Company, Job.company_id == Company.id)
            .order_by(Application.updated_at.desc())
        )
    )
    best_match: tuple[int, Application] | None = None
    for application in applications:
        job = application.job
        company = _normalize_role_text(job.company.name if job.company else "")
        title = _normalize_role_text(job.title)
        score = 0
        company_matched = False
        if company and any(hint in company or company in hint for hint in company_hints):
            score += 40
            company_matched = True
        if normalized_company_name:
            if normalized_company_name and (normalized_company_name in company or company in normalized_company_name):
                score += 25
                company_matched = True
        elif company and company in content:
            score += 20
            company_matched = True
        if company_signal_present and not company_matched:
            continue
        if title and title in content:
            score += 35
        else:
            title_terms = [term for term in title.split() if len(term) >= 4]
            overlapping_terms = [term for term in title_terms if term in content]
            if len(overlapping_terms) >= 2:
                score += 15
        if title.startswith("linkedin application confirmation") and company and company in content:
            score += 10
        if received_at:
            reference_date = application.applied_at or application.updated_at or application.created_at
            if reference_date:
                delta_days = abs((received_at - reference_date).days)
                if delta_days <= 14:
                    score += 20
                elif delta_days <= 45:
                    score += 10
                elif delta_days <= 120:
                    score += 5
                if application.applied_at and application.applied_at > received_at:
                    score -= 15
        if category == EmailCategory.REJECTION and application.status == ApplicationStatus.REJECTED:
            score += 5
        if score and (best_match is None or score > best_match[0]):
            best_match = (score, application)

    return best_match[1] if best_match and best_match[0] >= 25 else None


def _persist_normalized_email(db: Session, normalized: NormalizedEmailPayload) -> Email:
    raw_email = db.scalar(select(RawEmail).where(RawEmail.gmail_message_id == normalized.gmail_message_id))
    if not raw_email:
        raw_email = RawEmail(
            gmail_message_id=normalized.gmail_message_id,
            gmail_thread_id=normalized.gmail_thread_id,
            history_id=normalized.history_id,
            label_ids=normalized.label_ids,
            raw_payload=normalized.raw_payload,
        )
        db.add(raw_email)
        db.flush()
    else:
        raw_email.history_id = normalized.history_id
        raw_email.label_ids = normalized.label_ids
        raw_email.raw_payload = normalized.raw_payload
        raw_email.synced_at = datetime.now(timezone.utc)

    email_record = db.scalar(select(Email).where(Email.raw_email_id == raw_email.id))
    application = _match_application_by_email_content(
        db,
        company_name=normalized.company_name,
        subject=normalized.subject,
        snippet=normalized.snippet,
        body_text=normalized.body_text,
        received_at=normalized.received_at,
        category=normalized.category,
    )
    if not email_record:
        email_record = Email(
            raw_email_id=raw_email.id,
            application_id=application.id if application else None,
            company_name=normalized.company_name,
            from_name=normalized.from_name,
            from_email=normalized.from_email,
            subject=normalized.subject,
            snippet=normalized.snippet,
            body_text=normalized.body_text,
            category=normalized.category,
            urgency=normalized.urgency,
            requires_reply=normalized.requires_reply,
            suggested_action=normalized.suggested_action,
            received_at=normalized.received_at,
        )
        db.add(email_record)
    else:
        email_record.application_id = application.id if application else email_record.application_id
        email_record.company_name = normalized.company_name
        email_record.from_name = normalized.from_name
        email_record.from_email = normalized.from_email
        email_record.subject = normalized.subject
        email_record.snippet = normalized.snippet
        email_record.body_text = normalized.body_text
        email_record.category = normalized.category
        email_record.urgency = normalized.urgency
        email_record.requires_reply = normalized.requires_reply
        email_record.suggested_action = normalized.suggested_action
        email_record.received_at = normalized.received_at

    return email_record


def list_emails(db: Session) -> list[Email]:
    return list(
        db.scalars(
            select(Email)
            .options(joinedload(Email.raw_email))
            .order_by(Email.received_at.desc().nullslast(), Email.created_at.desc())
        )
    )


def list_raw_emails(db: Session) -> list[RawEmail]:
    return list(db.scalars(select(RawEmail).order_by(RawEmail.synced_at.desc())))


def apply_email_effects(db: Session, email_record: Email) -> None:
    if email_record.category == EmailCategory.JOB_ALERT:
        ingest_linkedin_job_alert(db, email_record)
    if email_record.category == EmailCategory.APPLICATION_CONFIRMATION:
        ingest_linkedin_application_confirmation(db, email_record)
    if email_record.category == EmailCategory.REJECTION and email_record.application_id:
        application = db.get(Application, email_record.application_id)
        if application and application.status != ApplicationStatus.REJECTED:
            previous_status = application.status
            application.status = ApplicationStatus.REJECTED
            write_audit_log(
                db,
                event_type="application.rejected_from_email",
                entity_type="application",
                entity_id=application.id,
                details={
                    "previous_status": previous_status,
                    "email_id": str(email_record.id),
                    "subject": email_record.subject,
                },
            )
    if email_record.application_id and email_record.category in {
        EmailCategory.INTERVIEW_INVITATION,
        EmailCategory.CODING_ASSESSMENT,
        EmailCategory.RECRUITER_FOLLOW_UP,
        EmailCategory.REJECTION,
        EmailCategory.OFFER,
        EmailCategory.DOCUMENTS_REQUESTED,
        EmailCategory.FORM_PENDING,
    }:
        sync_next_actions(db, email_record.application_id)


def link_email_to_application(
    db: Session,
    email_id: UUID,
    *,
    application_id: UUID | None,
    sync_actions: bool = True,
) -> Email | None:
    email_record = db.get(Email, email_id)
    if not email_record:
        return None

    linked_application: Application | None = None
    if application_id is not None:
        linked_application = db.get(Application, application_id)
        if not linked_application:
            raise ValueError("Application not found.")

    email_record.application_id = linked_application.id if linked_application else None
    if linked_application:
        email_record.company_name = linked_application.job.company.name if linked_application.job.company else email_record.company_name

    write_audit_log(
        db,
        event_type="email.application_linked" if linked_application else "email.application_unlinked",
        entity_type="email",
        entity_id=email_record.id,
        details={
            "application_id": str(linked_application.id) if linked_application else None,
            "sync_next_actions": sync_actions,
        },
    )
    db.commit()
    db.refresh(email_record)

    if linked_application and sync_actions:
        sync_next_actions(db, linked_application.id)
        db.refresh(email_record)

    return email_record


def sync_gmail_messages(
    db: Session,
    *,
    query: str = "category:primary newer_than:30d",
    max_results: int = 25,
    skip_existing: bool = True,
) -> list[Email]:
    service = _gmail_service(interactive=False)
    result = service.users().messages().list(
        userId="me",
        labelIds=["INBOX"],
        q=query,
        maxResults=max_results,
        includeSpamTrash=False,
    ).execute()
    messages = result.get("messages", [])
    persisted: list[Email] = []
    for item in messages:
        if skip_existing and db.scalar(select(RawEmail.id).where(RawEmail.gmail_message_id == item["id"])):
            continue
        full_message = service.users().messages().get(userId="me", id=item["id"], format="full").execute()
        normalized = normalize_gmail_message(full_message)
        email_record = _persist_normalized_email(db, normalized)
        db.flush()
        apply_email_effects(db, email_record)
        persisted.append(email_record)

    write_audit_log(
        db,
        event_type="gmail.sync_completed",
        entity_type="gmail",
        details={
            "query": query,
            "max_results": max_results,
            "skip_existing": skip_existing,
            "messages_seen": len(messages),
            "new_messages_synced": len(persisted),
        },
    )
    db.commit()
    for email_record in persisted:
        db.refresh(email_record)
    return persisted


def reclassify_stored_emails(db: Session) -> list[Email]:
    emails = list(db.scalars(select(Email).order_by(Email.received_at.asc().nullsfirst(), Email.created_at.asc())))
    for email_record in emails:
        category, urgency, requires_reply, suggested_action = _classify_email(
            email_record.subject,
            email_record.body_text or email_record.snippet,
            email_record.from_email,
        )
        matched_application = _match_application_by_email_content(
            db,
            company_name=email_record.company_name,
            subject=email_record.subject,
            snippet=email_record.snippet,
            body_text=email_record.body_text,
            received_at=email_record.received_at,
            category=category,
        )
        if matched_application:
            email_record.application_id = matched_application.id
        elif email_record.application_id:
            linked_application = db.get(Application, email_record.application_id)
            linked_company = _normalize_role_text(
                linked_application.job.company.name if linked_application and linked_application.job and linked_application.job.company else ""
            )
            explicit_company_signals = _extract_company_hints(
                email_record.subject,
                email_record.snippet,
                email_record.body_text,
            )
            normalized_company_name = _normalize_role_text(email_record.company_name) if email_record.company_name else ""
            if (
                linked_application
                and (
                    (explicit_company_signals and not any(hint in linked_company or linked_company in hint for hint in explicit_company_signals))
                    or (normalized_company_name and linked_company and normalized_company_name not in linked_company and linked_company not in normalized_company_name)
                )
            ):
                email_record.application_id = None
        email_record.category = category
        email_record.urgency = urgency
        email_record.requires_reply = requires_reply
        email_record.suggested_action = suggested_action
        apply_email_effects(db, email_record)

    write_audit_log(
        db,
        event_type="gmail.emails_reclassified",
        entity_type="gmail",
        details={"emails_reclassified": len(emails)},
    )
    db.commit()
    for email_record in emails:
        db.refresh(email_record)
    return emails


def sync_linkedin_activity(db: Session, *, newer_than_days: int = 90, max_results: int = 50) -> dict[str, int]:
    before_job_ids = set(db.scalars(select(Job.id).where(Job.source.in_(["linkedin_email_alert", "linkedin_application_email"]))))
    before_application_ids = set(
        db.scalars(
            select(Application.id)
            .join(Job, Application.job_id == Job.id)
            .where(Job.source.in_(["linkedin_email_alert", "linkedin_application_email"]))
        )
    )
    before_applied_ids = set(
        db.scalars(
            select(Application.id)
            .join(Job, Application.job_id == Job.id)
            .where(
                Job.source == "linkedin_application_email",
                Application.status == ApplicationStatus.APPLIED,
            )
        )
    )
    before_scored_ids = set(db.scalars(select(Job.id).join(Job.scores).where(Job.source.in_(["linkedin_email_alert", "linkedin_application_email"]))))

    queries = [
        f"from:jobalerts-noreply@linkedin.com newer_than:{newer_than_days}d",
        f"from:jobs-noreply@linkedin.com newer_than:{newer_than_days}d",
        f"from:notifications-noreply@linkedin.com newer_than:{newer_than_days}d",
    ]
    synced_email_ids: set[UUID] = set()
    for query in queries:
        for email_record in sync_gmail_messages(db, query=query, max_results=max_results, skip_existing=True):
            synced_email_ids.add(email_record.id)

    reclassified = []
    if synced_email_ids:
        reclassified = list(db.scalars(select(Email).where(Email.id.in_(synced_email_ids))))
    linkedin_emails = [
        email_record
        for email_record in reclassified
        if "linkedin.com" in email_record.from_email.lower()
    ]

    after_job_ids = set(db.scalars(select(Job.id).where(Job.source.in_(["linkedin_email_alert", "linkedin_application_email"]))))
    after_application_ids = set(
        db.scalars(
            select(Application.id)
            .join(Job, Application.job_id == Job.id)
            .where(Job.source.in_(["linkedin_email_alert", "linkedin_application_email"]))
        )
    )
    after_applied_ids = set(
        db.scalars(
            select(Application.id)
            .join(Job, Application.job_id == Job.id)
            .where(
                Job.source == "linkedin_application_email",
                Application.status == ApplicationStatus.APPLIED,
            )
        )
    )
    after_scored_ids = set(db.scalars(select(Job.id).join(Job.scores).where(Job.source.in_(["linkedin_email_alert", "linkedin_application_email"]))))

    result = {
        "emails_synced": len(synced_email_ids),
        "emails_reclassified": len(linkedin_emails),
        "job_alerts": sum(1 for email_record in linkedin_emails if email_record.category == EmailCategory.JOB_ALERT),
        "application_confirmations": sum(
            1 for email_record in linkedin_emails if email_record.category == EmailCategory.APPLICATION_CONFIRMATION
        ),
        "jobs_imported": len(after_job_ids - before_job_ids),
        "applications_created": len(after_application_ids - before_application_ids),
        "applications_marked_applied": len(after_applied_ids - before_applied_ids),
        "jobs_auto_scored": len(after_scored_ids - before_scored_ids),
    }
    write_audit_log(
        db,
        event_type="gmail.linkedin_activity_synced",
        entity_type="linkedin_activity",
        details={**result, "newer_than_days": newer_than_days, "max_results": max_results},
    )
    db.commit()
    return result


def mock_ingest_email(
    db: Session,
    *,
    from_header: str,
    subject: str,
    body_text: str,
    snippet: str | None = None,
) -> Email:
    mock_message = {
        "id": f"mock-{abs(hash((from_header, subject, body_text))) }",
        "threadId": f"mock-thread-{abs(hash((subject, from_header))) }",
        "historyId": "0",
        "labelIds": ["INBOX"],
        "snippet": snippet or body_text[:120],
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": from_header},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")},
            ],
            "body": {
                "data": base64.urlsafe_b64encode(body_text.encode("utf-8")).decode("utf-8").rstrip("="),
            },
        },
    }
    email_record = _persist_normalized_email(db, normalize_gmail_message(mock_message))
    write_audit_log(
        db,
        event_type="gmail.mock_ingested",
        entity_type="email",
        entity_id=email_record.id,
        details={"from_header": from_header, "subject": subject},
    )
    db.commit()
    db.refresh(email_record)
    return email_record


def _default_reply_body(email_record: Email) -> str:
    company = email_record.company_name or "your team"
    if email_record.category == EmailCategory.INTERVIEW_INVITATION:
        return (
            f"Hi,\n\nThank you for reaching out about the interview opportunity with {company}. "
            "I appreciate it and would be glad to continue. Please share the available time slots and I will confirm promptly.\n\nBest regards,"
        )
    if email_record.category == EmailCategory.CODING_ASSESSMENT:
        return (
            "Hi,\n\nThank you for sharing the assessment details. I received them and will review the instructions carefully before proceeding. "
            "I will follow up if I have any clarifying questions.\n\nBest regards,"
        )
    if email_record.category == EmailCategory.DOCUMENTS_REQUESTED:
        return (
            "Hi,\n\nThank you for the note. I received the document request and I am preparing the requested items now. "
            "I will send them back shortly.\n\nBest regards,"
        )
    if email_record.category == EmailCategory.FORM_PENDING:
        return (
            "Hi,\n\nThank you for the reminder. I received the form request and will complete it shortly. "
            "I will confirm once it is submitted.\n\nBest regards,"
        )
    return (
        "Hi,\n\nThank you for reaching out. I received your message and appreciate the follow-up. "
        "I am reviewing the details and will respond with the needed information shortly.\n\nBest regards,"
    )


def create_reply_draft(
    db: Session,
    email_id: UUID,
    *,
    create_gmail_draft: bool = False,
) -> MessageDraft | None:
    email_record = db.get(Email, email_id)
    if not email_record:
        return None
    if not email_record.application:
        raise ValueError("Email is not linked to an application yet.")

    profile = get_profile(db)
    if not profile:
        raise ValueError("Candidate profile not found.")

    subject = email_record.subject or ""
    reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    body = _default_reply_body(email_record)
    local_draft = MessageDraft(
        job_id=email_record.application.job_id,
        candidate_profile_id=profile.id,
        cv_version_id=None,
        draft_type=MessageDraftType.RECRUITER_REPLY,
        status=MessageDraftStatus.DRAFT,
        subject=reply_subject,
        body=body,
        tone="natural-professional",
        language="english",
        evidence=[
            {
                "email_id": str(email_record.id),
                "category": email_record.category,
                "subject": email_record.subject,
            }
        ],
        approval_required=True,
    )
    db.add(local_draft)

    if create_gmail_draft:
        service = _gmail_service(interactive=False)
        message = EmailMessage()
        message["To"] = email_record.from_email
        message["Subject"] = reply_subject
        message.set_content(body)

        use_gmail_threading = not email_record.raw_email.gmail_message_id.startswith("mock-") and not email_record.raw_email.gmail_thread_id.startswith("mock-thread-")
        if use_gmail_threading:
            message["In-Reply-To"] = email_record.raw_email.gmail_message_id
            message["References"] = email_record.raw_email.gmail_message_id

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        draft_message = {"raw": raw}
        if use_gmail_threading:
            draft_message["threadId"] = email_record.raw_email.gmail_thread_id
        draft_payload = {"message": draft_message}
        draft = service.users().drafts().create(userId="me", body=draft_payload).execute()
        email_record.gmail_draft_id = draft.get("id")

    write_audit_log(
        db,
        event_type="gmail.reply_draft_created",
        entity_type="email",
        entity_id=email_record.id,
        details={"message_draft_type": MessageDraftType.RECRUITER_REPLY, "gmail_draft_created": create_gmail_draft},
    )
    db.commit()
    db.refresh(local_draft)
    db.refresh(email_record)
    return local_draft
