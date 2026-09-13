import logging

from app.api.dependencies import (
    build_fcm_delivery_service,
    build_rainfall_processing_service,
    firebase_client,
)
from app.core.config import get_settings
from app.db.session import async_session_factory

logger = logging.getLogger(__name__)


async def process_rainfall_observations() -> None:
    settings = get_settings()
    async with async_session_factory() as session:
        result = await build_rainfall_processing_service(session).process_due(
            settings.scheduler_batch_size
        )
    if result.claimed:
        logger.info(
            "rainfall processing cycle completed",
            extra={
                "claimed": result.claimed,
                "processed": result.processed,
                "retrying": result.retrying,
                "failed": result.failed,
            },
        )


async def retry_notification_deliveries() -> None:
    if firebase_client is None:
        return
    settings = get_settings()
    async with async_session_factory() as session:
        result = await build_fcm_delivery_service(session).retry_due(settings.scheduler_batch_size)
    if result.subscriptions:
        logger.info(
            "notification retry cycle completed",
            extra={
                "attempted": result.subscriptions,
                "sent": result.sent,
                "retrying": result.retrying,
                "failed": result.failed,
            },
        )
