from __future__ import annotations

from datetime import datetime, time, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AgentRun,
    AgentRunStatus,
    Application,
    ApplicationStatus,
    ApplicationStatusCheckEvent,
    PortalCheckConfidence,
    PortalCredential,
    PublicJobStatus,
)
from app.portal_status_checker import PublicStatusCheckResult, check_public_job_url


ACTIVE_APPLICATION_STATUSES = {
    ApplicationStatus.APPLIED,
    ApplicationStatus.RECRUITER_REPLIED,
    ApplicationStatus.INTERVIEW,
    ApplicationStatus.ASSESSMENT,
}


def _utc_day_start() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime.combine(now.date(), time.min, tzinfo=timezone.utc)


def _application_source_url(application: Application) -> str | None:
    if application.job and application.job.source_url:
        return application.job.source_url
    if application.portal_credentials:
        return application.portal_credentials[0].portal_url
    return None


def _credentials_need_user_action(credential: PortalCredential | None) -> bool:
    return bool(credential and credential.mfa_enabled)


def _best_daily_credential(application: Application) -> PortalCredential | None:
    for credential in application.portal_credentials:
        if credential.daily_check_allowed:
            return credential
    return None


def list_status_check_events(db: Session, application_id: UUID, limit: int = 50) -> list[ApplicationStatusCheckEvent]:
    stmt = (
        select(ApplicationStatusCheckEvent)
        .where(ApplicationStatusCheckEvent.application_id == application_id)
        .order_by(ApplicationStatusCheckEvent.checked_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def _record_event(
    db: Session,
    application: Application,
    result: PublicStatusCheckResult,
    agent_run_id: UUID | None = None,
    credentials_used: bool = False,
    user_action_required: bool | None = None,
    evidence_override: str | None = None,
) -> ApplicationStatusCheckEvent:
    previous_status = application.latest_portal_status
    resolved_user_action_required = result.user_action_required if user_action_required is None else user_action_required
    event = ApplicationStatusCheckEvent(
        application_id=application.id,
        agent_run_id=agent_run_id,
        source_url=result.final_url or result.source_url,
        previous_status=previous_status,
        new_status=result.status.value,
        public_job_status=result.status,
        evidence_summary=evidence_override or result.evidence_summary,
        confidence=result.confidence,
        login_required=result.login_required,
        credentials_used=credentials_used,
        user_action_required=resolved_user_action_required,
        checked_at=datetime.now(timezone.utc),
        event_metadata={
            "provider": result.provider,
            "redirected": result.redirected,
            "http_status_code": result.http_status_code,
        },
    )
    db.add(event)

    if result.confidence in {PortalCheckConfidence.MEDIUM, PortalCheckConfidence.HIGH}:
        application.latest_portal_status = result.status.value
        application.latest_portal_confidence = result.confidence.value
        application.latest_portal_checked_at = event.checked_at
        application.portal_login_required = result.login_required
        application.portal_user_action_required = resolved_user_action_required

    return event


def check_application_portal_status(
    db: Session,
    application_id: UUID,
    agent_run_id: UUID | None = None,
) -> ApplicationStatusCheckEvent | None:
    application = db.get(Application, application_id)
    if not application:
        return None

    source_url = _application_source_url(application)
    if not source_url:
        result = PublicStatusCheckResult(
            source_url="",
            final_url="",
            status=PublicJobStatus.UNKNOWN,
            confidence=PortalCheckConfidence.LOW,
            evidence_summary="No official job or portal URL is stored for this application.",
        )
        event = _record_event(db, application, result, agent_run_id=agent_run_id)
        db.commit()
        db.refresh(event)
        return event

    result = check_public_job_url(source_url)
    credential = _best_daily_credential(application)
    credentials_used = False
    user_action_required = result.user_action_required
    evidence_override = None

    if result.status in {PublicJobStatus.LOGIN_REQUIRED, PublicJobStatus.UNKNOWN} and credential:
        credential.last_checked_at = datetime.now(timezone.utc)
        if _credentials_need_user_action(credential):
            user_action_required = True
            evidence_override = (
                "This portal requires login and MFA is marked as enabled. "
                "The agent stopped and needs user action before checking private status."
            )
        else:
            credentials_used = True
            evidence_override = (
                "Public information was insufficient. Saved portal credentials are available and permitted for daily checks; "
                "private portal automation will only proceed for supported portals without MFA or CAPTCHA."
            )

    event = _record_event(
        db,
        application,
        result,
        agent_run_id=agent_run_id,
        credentials_used=credentials_used,
        user_action_required=user_action_required,
        evidence_override=evidence_override,
    )
    db.commit()
    db.refresh(event)
    return event


def run_daily_portal_status_checks(db: Session, limit: int = 100) -> AgentRun:
    run = AgentRun(
        agent_type="portal_status_checker",
        trigger_type="scheduled",
        status=AgentRunStatus.RUNNING,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    day_start = _utc_day_start()
    stmt = (
        select(Application)
        .where(Application.status.in_(ACTIVE_APPLICATION_STATUSES))
        .where(
            (Application.latest_portal_checked_at.is_(None))
            | (Application.latest_portal_checked_at < day_start)
        )
        .order_by(Application.updated_at.desc())
        .limit(limit)
    )
    applications = list(db.scalars(stmt))
    changes = 0

    try:
        for application in applications:
            previous = application.latest_portal_status
            event = check_application_portal_status(db, application.id, agent_run_id=run.id)
            if event and previous != event.new_status:
                changes += 1
        run.status = AgentRunStatus.SUCCEEDED
        run.applications_checked = len(applications)
        run.changes_detected = changes
        run.finished_at = datetime.now(timezone.utc)
    except Exception as error:
        run.status = AgentRunStatus.FAILED
        run.error_message = str(error)
        run.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run
