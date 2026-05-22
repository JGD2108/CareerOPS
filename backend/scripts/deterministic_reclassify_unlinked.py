from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select
from app.db import SessionLocal
from app.gmail_integration import _classify_email
from app.models import Email


def main(limit: int = 100) -> int:
    db = SessionLocal()
    try:
        emails = list(db.scalars(select(Email).where(Email.application_id.is_(None)).order_by(Email.received_at.desc()).limit(limit)))
        updated = 0
        for email in emails:
            cat, urgency, requires_reply, suggested_action = _classify_email(email.subject, email.body_text or email.snippet or "", email.from_email)
            if email.category != cat or email.urgency != urgency or email.requires_reply != requires_reply:
                email.category = cat
                email.urgency = urgency
                email.requires_reply = requires_reply
                email.suggested_action = suggested_action
                db.add(email)
                updated += 1
        if updated:
            db.commit()
        print(f"Processed {len(emails)} emails, updated {updated}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
