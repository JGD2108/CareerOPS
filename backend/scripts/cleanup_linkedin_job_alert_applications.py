from __future__ import annotations

from sqlalchemy import delete, func, select

from app.db import SessionLocal
from app.models import Application, Job


def main(*, apply: bool = False) -> None:
    db = SessionLocal()
    try:
        count_stmt = (
            select(func.count(Application.id))
            .join(Job, Application.job_id == Job.id)
            .where(Job.source == "linkedin_email_alert")
        )
        to_delete = int(db.scalar(count_stmt) or 0)
        if not apply:
            print({"mode": "dry_run", "applications_to_delete": to_delete})
            return

        delete_stmt = (
            delete(Application)
            .where(
                Application.job_id.in_(
                    select(Job.id).where(Job.source == "linkedin_email_alert")
                )
            )
        )
        result = db.execute(delete_stmt)
        db.commit()
        print(
            {
                "mode": "apply",
                "applications_deleted": int(result.rowcount or 0),
            }
        )
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    main(apply=args.apply)
