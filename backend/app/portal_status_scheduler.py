from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.db import get_db
from app.portal_status_agent import run_daily_portal_status_checks


logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


def scheduled_portal_status_check() -> None:
    db_gen = get_db()
    db = next(db_gen)
    try:
        run = run_daily_portal_status_checks(db)
        logger.info(
            "Portal status checker completed run %s: checked=%s changes=%s status=%s",
            run.id,
            run.applications_checked,
            run.changes_detected,
            run.status,
        )
    except Exception:
        logger.exception("Portal status checker failed.")
    finally:
        next(db_gen, None)


def start_scheduler() -> None:
    settings = get_settings()
    if not settings.enable_portal_status_scheduler:
        logger.info("Portal status scheduler disabled.")
        return
    if scheduler.running:
        return

    scheduler.add_job(
        scheduled_portal_status_check,
        "cron",
        hour=settings.portal_status_schedule_hour,
        minute=settings.portal_status_schedule_minute,
        timezone=settings.scheduler_timezone,
        id="portal_status_daily_check",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Portal status scheduler started.")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Portal status scheduler stopped.")
