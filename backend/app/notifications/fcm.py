from app.schemas.notification import (
    NotificationChannel,
    NotificationDeliveryResult,
    NotificationEvent,
)
from app.services.fcm_delivery_service import FcmDeliveryService


class FcmNotificationProvider:
    name = "firebase-admin"
    channel = NotificationChannel.FCM

    def __init__(self, delivery_service: FcmDeliveryService) -> None:
        self._delivery_service = delivery_service

    async def send(self, event: NotificationEvent) -> NotificationDeliveryResult:
        result = await self._delivery_service.deliver_event(event)
        delivered = result.sent > 0
        if result.subscriptions == 0:
            error = "no active FCM subscriptions"
        elif not delivered:
            error = f"no immediate delivery; retrying={result.retrying}, failed={result.failed}"
        else:
            error = None
        return NotificationDeliveryResult(
            provider=self.name,
            channel=self.channel,
            delivered=delivered,
            error=error,
        )
