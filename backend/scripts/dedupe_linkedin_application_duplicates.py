from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Action, Application, Email, Job, RawJob
from app.text_normalization import normalize_text_block


def _norm(value: str | None) -> str:
    return normalize_text_block(value or "").strip().lower()


def run() -> None:
    db = SessionLocal()
    try:
        raw_jobs = list(
            db.scalars(
                select(RawJob)
                .where(RawJob.source == "linkedin_application_email")
                .order_by(RawJob.created_at.asc())
            )
        )
        groups: dict[tuple[str, str], list[RawJob]] = defaultdict(list)
        for raw in raw_jobs:
            key = (_norm(raw.company_name), _norm(raw.title))
            if key == ("", ""):
                continue
            groups[key].append(raw)

        duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}
        rewired_emails = 0
        rewired_actions = 0
        deleted_apps = 0
        deleted_jobs = 0
        deleted_raw_jobs = 0

        for _, raws in duplicate_groups.items():
            canonical_raw = raws[0]
            canonical_job = canonical_raw.normalized_job_id and db.get(Job, canonical_raw.normalized_job_id)
            if not canonical_job:
                continue
            canonical_app = db.scalar(select(Application).where(Application.job_id == canonical_job.id))

            for raw in raws[1:]:
                dupe_job = raw.normalized_job_id and db.get(Job, raw.normalized_job_id)
                if not dupe_job or dupe_job.id == canonical_job.id:
                    db.delete(raw)
                    deleted_raw_jobs += 1
                    continue

                dupe_app = db.scalar(select(Application).where(Application.job_id == dupe_job.id))
                if dupe_app and canonical_app:
                    email_rows = list(db.scalars(select(Email).where(Email.application_id == dupe_app.id)))
                    for email in email_rows:
                        email.application_id = canonical_app.id
                        rewired_emails += 1
                    action_rows = list(db.scalars(select(Action).where(Action.application_id == dupe_app.id)))
                    for action in action_rows:
                        action.application_id = canonical_app.id
                        rewired_actions += 1

                if dupe_app and (not canonical_app):
                    dupe_app.job_id = canonical_job.id
                    canonical_app = dupe_app
                elif dupe_app:
                    db.delete(dupe_app)
                    deleted_apps += 1

                db.delete(raw)
                deleted_raw_jobs += 1
                db.delete(dupe_job)
                deleted_jobs += 1

        db.commit()
        print(
            {
                "duplicate_groups": len(duplicate_groups),
                "rewired_emails": rewired_emails,
                "rewired_actions": rewired_actions,
                "deleted_raw_jobs": deleted_raw_jobs,
                "deleted_jobs": deleted_jobs,
                "deleted_applications": deleted_apps,
            }
        )
    finally:
        db.close()


if __name__ == "__main__":
    run()
