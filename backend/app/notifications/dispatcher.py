import asyncio
import logging
from collections.abc import Iterable

from app.notifications.base import NotificationProvider
from app.schemas.notification import NotificationDeliveryResult, NotificationEvent

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    def __init__(self, providers: Iterable[NotificationProvider]) -> None:
        self._providers = tuple(providers)

    async def dispatch(self, event: NotificationEvent) -> list[NotificationDeliveryResult]:
        return list(
            await asyncio.gather(*(self._send(provider, event) for provider in self._providers))
        )

    @staticmethod
    async def _send(
        provider: NotificationProvider,
        event: NotificationEvent,
    ) -> NotificationDeliveryResult:
        try:
            return await provider.send(event)
        except Exception as error:
            logger.exception(
                "notification provider failed",
                extra={
                    "provider": provider.name,
                    "channel": provider.channel.value,
                    "alert_id": str(event.alert_id),
                    "event_id": str(event.event_id),
                },
            )
            return NotificationDeliveryResult(
                provider=provider.name,
                channel=provider.channel,
                delivered=False,
                error=str(error),
            )
