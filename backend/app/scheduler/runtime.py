from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import Settings
from app.scheduler.jobs import process_rainfall_observations, retry_notification_deliveries


def create_scheduler(settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        process_rainfall_observations,
        "interval",
        seconds=settings.rainfall_processing_interval_seconds,
        id="process-rainfall-observations",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=settings.rainfall_processing_interval_seconds,
        replace_existing=True,
    )
    if settings.fcm_enabled:
        scheduler.add_job(
            retry_notification_deliveries,
            "interval",
            seconds=settings.notification_retry_interval_seconds,
            id="retry-notification-deliveries",
            coalesce=True,
            max_instances=1,
            misfire_grace_time=settings.notification_retry_interval_seconds,
            replace_existing=True,
        )
    return scheduler
