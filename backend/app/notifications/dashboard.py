from app.realtime.alert_hub import AlertWebSocketHub
from app.schemas.notification import (
    NotificationChannel,
    NotificationDeliveryResult,
    NotificationEvent,
)


class DashboardNotificationProvider:
    name = "dashboard-websocket"
    channel = NotificationChannel.DASHBOARD

    def __init__(self, hub: AlertWebSocketHub) -> None:
        self._hub = hub

    async def send(self, event: NotificationEvent) -> NotificationDeliveryResult:
        delivered_count = await self._hub.broadcast(event)
        return NotificationDeliveryResult(
            provider=self.name,
            channel=self.channel,
            delivered=delivered_count > 0,
            error=None if delivered_count > 0 else "no connected dashboard clients",
        )
