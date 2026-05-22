from __future__ import annotations

from sqlalchemy import select

from app.db import SessionLocal
from app.gmail_integration import ingest_linkedin_application_confirmation
from app.models import Email, EmailCategory


def run() -> None:
    db = SessionLocal()
    try:
        emails = list(
            db.scalars(
                select(Email)
                .where(
                    Email.category == EmailCategory.APPLICATION_CONFIRMATION,
                    Email.from_email.ilike("%linkedin%"),
                )
                .order_by(Email.created_at.asc())
            )
        )
        processed = 0
        changed = 0
        for email in emails:
            processed += 1
            result = ingest_linkedin_application_confirmation(db, email)
            if any(result.values()):
                changed += 1
        db.commit()
        print({"emails_processed": processed, "emails_with_changes": changed})
    finally:
        db.close()


if __name__ == "__main__":
    run()
