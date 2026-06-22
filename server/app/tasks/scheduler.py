from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.services.reminder_engine import scan_due_reminders as run_due_reminders

scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)


def scan_due_reminders() -> None:
    run_due_reminders()


def start_scheduler() -> None:
    if scheduler.running:
        return

    scheduler.add_job(
        scan_due_reminders,
        "cron",
        hour=settings.reminder_scan_hour,
        minute=settings.reminder_scan_minute,
        id="daily-reminder-scan",
        replace_existing=True,
    )
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
