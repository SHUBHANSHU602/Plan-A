from uuid import UUID

from app.repositories.notification import AlertDeliveryRepository
from app.schemas.delivery import (
    AlertDeliveryListResponse,
    AlertDeliveryResponse,
    DeliveryStatus,
)


class DeliveryQueryService:
    def __init__(self, repository: AlertDeliveryRepository) -> None:
        self._repository = repository

    async def list_for_alert(self, alert_id: UUID, limit: int) -> AlertDeliveryListResponse:
        deliveries = await self._repository.list_for_alert(alert_id, limit)
        return AlertDeliveryListResponse(
            items=[
                AlertDeliveryResponse(
                    id=item.id,
                    alert_id=item.alert_id,
                    alert_event_id=item.alert_event_id,
                    subscription_id=item.subscription_id,
                    provider=item.provider,
                    channel=item.channel,
                    status=DeliveryStatus(item.status),
                    attempt_count=item.attempt_count,
                    next_attempt_at=item.next_attempt_at,
                    provider_message_id=item.provider_message_id,
                    last_error=item.last_error,
                    sent_at=item.sent_at,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
                for item in deliveries
            ]
        )
