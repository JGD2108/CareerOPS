from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.gmail_integration import sync_career_gmail_messages
from app.db import get_db
from app.config import get_settings
import logging

logging.basicConfig()
logging.getLogger('apscheduler').setLevel(logging.INFO)

scheduler = AsyncIOScheduler()

async def scheduled_gmail_sync():
    """
    A scheduled job to sync Gmail messages.
    """
    logging.info("Running scheduled Gmail sync...")
    settings = get_settings()
    if not settings.user_id:
        logging.warning("User ID not set, skipping scheduled Gmail sync.")
        return

    db_gen = get_db()
    db = next(db_gen)
    try:
        await sync_career_gmail_messages(user_id=settings.user_id, db=db)
        logging.info("Scheduled Gmail sync completed successfully.")
    except Exception as e:
        logging.error(f"Error during scheduled Gmail sync: {e}", exc_info=True)
    finally:
        next(db_gen, None)

def start_scheduler():
    """
    Starts the scheduler and adds the Gmail sync job.
    """
    # Schedule the job to run every 15 minutes
    scheduler.add_job(scheduled_gmail_sync, 'interval', minutes=15)
    scheduler.start()
    logging.info("Scheduler started.")

def stop_scheduler():
    """
    Stops the scheduler.
    """
    scheduler.shutdown()
    logging.info("Scheduler stopped.")
