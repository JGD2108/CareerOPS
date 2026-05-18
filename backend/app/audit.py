from uuid import UUID

from sqlalchemy.orm import Session

from app.models import AuditLog


def write_audit_log(
    db: Session,
    *,
    event_type: str,
    entity_type: str,
    entity_id: UUID | None = None,
    actor: str = "system",
    details: dict | None = None,
) -> AuditLog:
    audit_log = AuditLog(
        actor=actor,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    db.add(audit_log)
    return audit_log
