from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.audit import write_audit_log
from app.models import (
    Action,
    ActionStatus,
    ActionType,
    Application,
    ApplicationStatus,
    Email,
    EmailCategory,
    Job,
)
from app.schemas import ActionCreateRequest


TERMINAL_ACTION_STATUSES = {ActionStatus.COMPLETED, ActionStatus.DISMISSED}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _open_actions_by_key(db: Session, application_id: UUID) -> dict[str, Action]:
    actions = list(
        db.scalars(
            select(Action)
            .where(Action.application_id == application_id, Action.status == ActionStatus.OPEN)
            .order_by(Action.created_at.desc())
        )
    )
    return {action.action_key: action for action in actions}


def _all_actions(db: Session, application_id: UUID) -> list[Action]:
    return list(db.scalars(select(Action).where(Action.application_id == application_id).order_by(Action.created_at.desc())))


def get_application_with_context(db: Session, application_id: UUID) -> Application | None:
    return db.scalar(
        select(Application)
        .options(
            joinedload(Application.job).joinedload(Job.company),
            joinedload(Application.emails),
            joinedload(Application.actions),
        )
        .where(Application.id == application_id)
    )


def list_actions(db: Session, *, status: ActionStatus | None = None) -> list[Action]:
    statement = select(Action).options(joinedload(Action.application)).order_by(
        Action.due_at.asc().nullslast(), Action.created_at.desc()
    )
    if status:
        statement = statement.where(Action.status == status)
    return list(db.scalars(statement))


def list_application_actions(db: Session, application_id: UUID) -> list[Action]:
    return _all_actions(db, application_id)


def create_manual_action(
    db: Session,
    application_id: UUID,
    payload: ActionCreateRequest,
) -> Action | None:
    application = db.get(Application, application_id)
    if not application:
        return None

    action = Action(
        application_id=application_id,
        email_id=None,
        action_key=f"manual:{application_id}:{uuid4()}",
        action_type=payload.action_type,
        status=ActionStatus.OPEN,
        title=payload.title.strip(),
        details=payload.details.strip() if payload.details else None,
        priority=payload.priority.strip().lower() or "normal",
        due_at=payload.due_at,
    )
    db.add(action)
    db.flush()
    write_audit_log(
        db,
        event_type="action.created_manual",
        entity_type="action",
        entity_id=action.id,
        details={
            "application_id": str(application_id),
            "action_type": action.action_type,
            "priority": action.priority,
            "due_at": action.due_at.isoformat() if action.due_at else None,
        },
    )
    db.commit()
    db.refresh(action)
    return action


def update_action_status(
    db: Session,
    action_id: UUID,
    *,
    status: ActionStatus,
    notes: str | None = None,
) -> Action | None:
    action = db.get(Action, action_id)
    if not action:
        return None

    action.status = status
    if status == ActionStatus.COMPLETED:
        action.completed_at = _utcnow()
    if notes:
        action.details = f"{action.details or ''}\n\nNote: {notes}".strip()

    write_audit_log(
        db,
        event_type="action.updated",
        entity_type="action",
        entity_id=action.id,
        details={"status": status, "notes": notes},
    )
    db.commit()
    db.refresh(action)
    return action


def _dismiss_stale_actions(open_actions: dict[str, Action], desired_keys: set[str]) -> None:
    now = _utcnow()
    for key, action in open_actions.items():
        if key.startswith("manual:"):
            continue
        if key not in desired_keys:
            action.status = ActionStatus.DISMISSED
            action.completed_at = now


def _ensure_action(
    db: Session,
    open_actions: dict[str, Action],
    *,
    application_id: UUID,
    action_key: str,
    action_type: ActionType,
    title: str,
    details: str,
    priority: str,
    due_at: datetime | None,
    email_id: UUID | None = None,
) -> Action:
    existing = open_actions.get(action_key)
    if not existing:
        existing = db.scalar(select(Action).where(Action.action_key == action_key))
    if existing:
        existing.application_id = application_id
        existing.action_type = action_type
        existing.title = title
        existing.details = details
        existing.priority = priority
        existing.due_at = due_at
        existing.email_id = email_id
        if existing.status == ActionStatus.DISMISSED:
            existing.status = ActionStatus.OPEN
        return existing

    action = Action(
        application_id=application_id,
        email_id=email_id,
        action_key=action_key,
        action_type=action_type,
        status=ActionStatus.OPEN,
        title=title,
        details=details,
        priority=priority,
        due_at=due_at,
    )
    db.add(action)
    db.flush()
    write_audit_log(
        db,
        event_type="action.created",
        entity_type="action",
        entity_id=action.id,
        details={"action_key": action_key, "action_type": action_type},
    )
    return action


def _email_action_spec(email: Email) -> tuple[str, ActionType, str, str, str, datetime | None] | None:
    now = _utcnow()
    if email.category == EmailCategory.INTERVIEW_INVITATION:
        return (
            f"email:{email.id}:interview",
            ActionType.SCHEDULE_INTERVIEW,
            "Respond to interview invitation",
            f"Reply to the interview invitation from {email.company_name or email.from_email}.",
            "high",
            now + timedelta(days=1),
        )
    if email.category == EmailCategory.CODING_ASSESSMENT:
        return (
            f"email:{email.id}:assessment",
            ActionType.COMPLETE_ASSESSMENT,
            "Complete coding assessment",
            f"Review the assessment email from {email.company_name or email.from_email} and complete the task.",
            "high",
            now + timedelta(days=3),
        )
    if email.category == EmailCategory.RECRUITER_FOLLOW_UP:
        return (
            f"email:{email.id}:recruiter_follow_up",
            ActionType.RESPOND_TO_RECRUITER,
            "Respond to recruiter follow-up",
            f"Review the recruiter follow-up from {email.company_name or email.from_email} and create a follow-up reply in the same language.",
            "normal",
            now + timedelta(days=2),
        )
    if email.category == EmailCategory.DOCUMENTS_REQUESTED:
        return (
            f"email:{email.id}:documents",
            ActionType.SEND_DOCUMENTS,
            "Send requested documents",
            f"Prepare and send the requested documents for {email.company_name or email.from_email}.",
            "high",
            now + timedelta(days=1),
        )
    if email.category == EmailCategory.FORM_PENDING:
        return (
            f"email:{email.id}:form",
            ActionType.COMPLETE_FORM,
            "Complete required form",
            f"Finish the requested form linked to {email.company_name or email.from_email}.",
            "high",
            now + timedelta(days=1),
        )
    if email.category == EmailCategory.OFFER:
        return (
            f"email:{email.id}:offer",
            ActionType.REVIEW_OFFER,
            "Review offer details",
            f"Review the offer email from {email.company_name or email.from_email} and record your decision.",
            "high",
            now + timedelta(days=2),
        )
    if email.category == EmailCategory.REJECTION:
        return (
            f"email:{email.id}:rejection",
            ActionType.ARCHIVE_REJECTION,
            "Archive rejection and capture notes",
            f"Update the tracker and archive the rejection from {email.company_name or email.from_email}.",
            "normal",
            now + timedelta(days=2),
        )
    return None


def sync_next_actions(db: Session, application_id: UUID) -> dict | None:
    application = get_application_with_context(db, application_id)
    if not application:
        return None

    open_actions = _open_actions_by_key(db, application_id)
    desired_keys: set[str] = set()

    # Keep status aligned with email evidence when applicable.
    latest_email = max(
        application.emails,
        key=lambda item: item.received_at or item.created_at,
        default=None,
    )
    if latest_email:
        if latest_email.category == EmailCategory.INTERVIEW_INVITATION:
            application.status = ApplicationStatus.INTERVIEW
        elif latest_email.category == EmailCategory.CODING_ASSESSMENT:
            application.status = ApplicationStatus.ASSESSMENT
        elif latest_email.category == EmailCategory.RECRUITER_FOLLOW_UP:
            application.status = ApplicationStatus.RECRUITER_REPLIED
        elif latest_email.category == EmailCategory.REJECTION:
            application.status = ApplicationStatus.REJECTED
        elif latest_email.category == EmailCategory.OFFER:
            application.status = ApplicationStatus.OFFER

    # Status-driven actions.
    if application.status == ApplicationStatus.CV_GENERATED:
        key = "application:submit"
        desired_keys.add(key)
        _ensure_action(
            db,
            open_actions,
            application_id=application.id,
            action_key=key,
            action_type=ActionType.SUBMIT_APPLICATION,
            title="Submit application manually",
            details="The application package is ready. Submit it manually and then mark it as applied.",
            priority="high",
            due_at=_utcnow() + timedelta(days=1),
        )
    elif application.status == ApplicationStatus.APPLIED and application.applied_at:
        if application.applied_at <= _utcnow() - timedelta(days=7):
            key = "application:follow_up"
            desired_keys.add(key)
            _ensure_action(
                db,
                open_actions,
                application_id=application.id,
                action_key=key,
                action_type=ActionType.SEND_FOLLOW_UP,
                title="Send follow-up",
                details="No reply has been tracked for 7+ days. Consider a concise follow-up.",
                priority="normal",
                due_at=_utcnow() + timedelta(days=1),
                email_id=latest_email.id if latest_email else None,
            )

    # Email-driven actions.
    for email in application.emails:
        spec = _email_action_spec(email)
        if not spec:
            continue
        action_key, action_type, title, details, priority, due_at = spec
        desired_keys.add(action_key)
        _ensure_action(
            db,
            open_actions,
            application_id=application.id,
            action_key=action_key,
            action_type=action_type,
            title=title,
            details=details,
            priority=priority,
            due_at=due_at,
            email_id=email.id,
        )

    _dismiss_stale_actions(open_actions, desired_keys)
    write_audit_log(
        db,
        event_type="next_actions.synced",
        entity_type="application",
        entity_id=application.id,
        details={"desired_action_count": len(desired_keys)},
    )
    db.commit()
    db.refresh(application)
    return {
        "application_id": application.id,
        "status": application.status,
        "actions": list_application_actions(db, application.id),
    }
