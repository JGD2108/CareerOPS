from __future__ import annotations

import os
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings, resolve_config_path
from app.db import SessionLocal
from app.job_discovery import active_discovery_source_count, run_saved_discovery_sources


settings = get_settings()
_scheduler: BackgroundScheduler | None = None


def _scheduler_lock_path() -> Path:
    lock_path = resolve_config_path(settings.scheduler_lock_file)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    return lock_path


def _acquire_scheduler_lock() -> bool:
    lock_path = _scheduler_lock_path()
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False

    with os.fdopen(fd, "w", encoding="utf-8") as lock_file:
        lock_file.write(str(os.getpid()))
    return True


def _release_scheduler_lock() -> None:
    lock_path = _scheduler_lock_path()
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def _safe_run_saved_discovery_sources() -> None:
    if not _acquire_scheduler_lock():
        return

    try:
        with SessionLocal() as db:
            run_saved_discovery_sources(db, trigger_type="scheduled")
    finally:
        _release_scheduler_lock()


def _should_start_scheduler() -> bool:
    if not settings.enable_job_discovery_scheduler:
        return False
    # Avoid double-starting in parent reload process.
    if os.environ.get("RUN_MAIN") == "false":
        return False
    return True


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None or not _should_start_scheduler():
        return

    _scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)
    _scheduler.add_job(
        _safe_run_saved_discovery_sources,
        CronTrigger(
            hour=settings.discovery_schedule_hour,
            minute=settings.discovery_schedule_minute,
            timezone=settings.scheduler_timezone,
        ),
        id="daily_job_discovery",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def scheduler_status() -> dict:
    with SessionLocal() as db:
        source_count = active_discovery_source_count(db)
    return {
        "enabled": settings.enable_job_discovery_scheduler,
        "running": _scheduler is not None and _scheduler.running,
        "timezone": settings.scheduler_timezone,
        "schedule_hour": settings.discovery_schedule_hour,
        "schedule_minute": settings.discovery_schedule_minute,
        "active_source_count": source_count,
    }
