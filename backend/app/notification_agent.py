from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.audit import write_audit_log
from app.models import (
    Action,
    ActionStatus,
    Application,
    Email,
    Job,
    JobRecommendation,
    JobScore,
    NotificationChannel,
    NotificationSummary,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _start_of_window(days: int) -> datetime:
    return _utcnow() - timedelta(days=days)


def _top_matches(db: Session, limit: int = 5) -> list[JobScore]:
    return list(
        db.scalars(
            select(JobScore)
            .options(joinedload(JobScore.job).joinedload(Job.company))
            .where(JobScore.recommendation.in_([JobRecommendation.APPLY_NOW, JobRecommendation.REVIEW]))
            .order_by(JobScore.score.desc(), JobScore.created_at.desc())
            .limit(limit)
        )
    )


def _recent_jobs(db: Session, days: int = 1) -> list[Job]:
    return list(
        db.scalars(
            select(Job)
            .options(joinedload(Job.company))
            .where(Job.created_at >= _start_of_window(days))
            .order_by(Job.created_at.desc())
        )
    )


def _important_emails(db: Session, days: int = 7, limit: int = 10) -> list[Email]:
    return list(
        db.scalars(
            select(Email)
            .where(
                Email.received_at >= _start_of_window(days),
                Email.requires_reply.is_(True),
            )
            .order_by(Email.received_at.desc().nullslast(), Email.created_at.desc())
            .limit(limit)
        )
    )


def _open_actions(db: Session, limit: int = 20) -> list[Action]:
    return list(
        db.scalars(
            select(Action)
            .options(joinedload(Action.application).joinedload(Application.job).joinedload(Job.company))
            .where(Action.status == ActionStatus.OPEN)
            .order_by(Action.priority.desc(), Action.due_at.asc().nullslast(), Action.created_at.desc())
            .limit(limit)
        )
    )


def _pending_applications(db: Session, limit: int = 10) -> list[Application]:
    return list(
        db.scalars(
            select(Application)
            .options(joinedload(Application.job).joinedload(Job.company))
            .where(Application.status.in_(["Found", "Reviewed", "CV Generated", "Applied", "Recruiter Replied", "Interview", "Assessment"]))
            .order_by(Application.updated_at.desc())
            .limit(limit)
        )
    )


def _render_summary(content: dict) -> str:
    lines = []
    lines.append(f"CareerOps daily summary - {content['generated_at']}")
    lines.append("")
    lines.append(f"New jobs found: {content['counts']['new_jobs']}")
    lines.append(f"Top matches tracked: {content['counts']['top_matches']}")
    lines.append(f"Important emails: {content['counts']['important_emails']}")
    lines.append(f"Open actions: {content['counts']['open_actions']}")
    lines.append(f"Pending applications: {content['counts']['pending_applications']}")
    lines.append("")

    lines.append("Top matches:")
    if content["top_matches"]:
        for item in content["top_matches"]:
            lines.append(f"- {item['company']} | {item['title']} | score {item['score']} | {item['recommendation']}")
    else:
        lines.append("- None")

    lines.append("")
    lines.append("Important emails:")
    if content["important_emails"]:
        for item in content["important_emails"]:
            lines.append(f"- {item['company_name'] or item['from_email']} | {item['subject']} | {item['category']}")
    else:
        lines.append("- None")

    lines.append("")
    lines.append("Urgent actions:")
    if content["open_actions"]:
        for item in content["open_actions"]:
            lines.append(f"- {item['title']} | {item['company']} | priority {item['priority']} | due {item['due_at'] or 'n/a'}")
    else:
        lines.append("- None")

    return "\n".join(lines)


def generate_daily_summary(db: Session, *, channel: NotificationChannel = NotificationChannel.API) -> NotificationSummary:
    recent_jobs = _recent_jobs(db)
    top_matches = _top_matches(db)
    important_emails = _important_emails(db)
    open_actions = _open_actions(db)
    pending_applications = _pending_applications(db)

    content = {
        "generated_at": _utcnow().isoformat(),
        "counts": {
            "new_jobs": len(recent_jobs),
            "top_matches": len(top_matches),
            "important_emails": len(important_emails),
            "open_actions": len(open_actions),
            "pending_applications": len(pending_applications),
        },
        "top_matches": [
            {
                "job_id": str(score.job_id),
                "title": score.job.title if score.job else None,
                "company": score.job.company.name if score.job and score.job.company else None,
                "score": score.score,
                "recommendation": score.recommendation,
            }
            for score in top_matches
        ],
        "important_emails": [
            {
                "email_id": str(email.id),
                "company_name": email.company_name,
                "from_email": email.from_email,
                "subject": email.subject,
                "category": email.category,
            }
            for email in important_emails
        ],
        "open_actions": [
            {
                "action_id": str(action.id),
                "title": action.title,
                "company": action.application.job.company.name if action.application and action.application.job and action.application.job.company else None,
                "priority": action.priority,
                "due_at": action.due_at.isoformat() if action.due_at else None,
            }
            for action in open_actions
        ],
        "pending_applications": [
            {
                "application_id": str(application.id),
                "title": application.job.title if application.job else None,
                "company": application.job.company.name if application.job and application.job.company else None,
                "status": application.status,
            }
            for application in pending_applications
        ],
    }

    rendered_text = _render_summary(content)
    summary = NotificationSummary(
        summary_date=_utcnow(),
        channel=channel,
        content=content,
        rendered_text=rendered_text,
    )
    db.add(summary)
    db.flush()
    write_audit_log(
        db,
        event_type="notification_summary.generated",
        entity_type="notification_summary",
        entity_id=summary.id,
        details={"channel": channel, "counts": content["counts"]},
    )
    db.commit()
    db.refresh(summary)
    return summary


def list_notification_summaries(db: Session, limit: int = 20) -> list[NotificationSummary]:
    return list(db.scalars(select(NotificationSummary).order_by(NotificationSummary.created_at.desc()).limit(limit)))
