from typing import Protocol

from app.schemas.notification import (
    NotificationChannel,
    NotificationDeliveryResult,
    NotificationEvent,
)


class NotificationProvider(Protocol):
    name: str
    channel: NotificationChannel

    async def send(self, event: NotificationEvent) -> NotificationDeliveryResult: ...
