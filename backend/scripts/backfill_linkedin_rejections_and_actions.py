from __future__ import annotations

from sqlalchemy import select

from app.db import SessionLocal
from app.gmail_integration import reclassify_stored_emails
from app.models import Application, Email, EmailCategory
from app.next_action_agent import sync_next_actions


def run() -> None:
    db = SessionLocal()
    try:
        reclassified = reclassify_stored_emails(db)
        linkedin_rejections = [
            email
            for email in reclassified
            if "linkedin" in (email.from_email or "").lower() and email.category == EmailCategory.REJECTION
        ]

        application_ids = set(
            db.scalars(
                select(Application.id)
                .join(Email, Email.application_id == Application.id)
                .where(Email.id.in_([email.id for email in linkedin_rejections]))
            )
        )

        synced = 0
        for application_id in application_ids:
            if sync_next_actions(db, application_id):
                synced += 1

        print(
            {
                "emails_reclassified_total": len(reclassified),
                "linkedin_rejections_found": len(linkedin_rejections),
                "applications_resynced": synced,
            }
        )
    finally:
        db.close()


if __name__ == "__main__":
    run()
