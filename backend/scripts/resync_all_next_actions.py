from __future__ import annotations

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Application
from app.next_action_agent import sync_next_actions


def run() -> None:
    db = SessionLocal()
    try:
        application_ids = list(db.scalars(select(Application.id)))
        synced = 0
        for application_id in application_ids:
            if sync_next_actions(db, application_id):
                synced += 1
        print({"applications_checked": len(application_ids), "applications_synced": synced})
    finally:
        db.close()


if __name__ == "__main__":
    run()
