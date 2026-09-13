from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.dependencies import (
    get_delivery_query_service,
    get_notification_subscription_service,
)
from app.schemas.delivery import (
    AlertDeliveryListResponse,
    NotificationSubscriptionCreate,
    NotificationSubscriptionResponse,
)
from app.services.delivery_query_service import DeliveryQueryService
from app.services.notification_subscription_service import (
    NotificationSubscriptionNotFoundError,
    NotificationSubscriptionService,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post(
    "/subscriptions",
    response_model=NotificationSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_notification_subscription(
    request: NotificationSubscriptionCreate,
    service: Annotated[
        NotificationSubscriptionService,
        Depends(get_notification_subscription_service),
    ],
) -> NotificationSubscriptionResponse:
    return await service.register(request)


@router.delete("/subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_notification_subscription(
    subscription_id: UUID,
    service: Annotated[
        NotificationSubscriptionService,
        Depends(get_notification_subscription_service),
    ],
) -> Response:
    try:
        await service.deactivate(subscription_id)
    except NotificationSubscriptionNotFoundError as error:
        raise HTTPException(
            status_code=404, detail="notification subscription not found"
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/deliveries", response_model=AlertDeliveryListResponse)
async def list_alert_deliveries(
    alert_id: UUID,
    service: Annotated[DeliveryQueryService, Depends(get_delivery_query_service)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> AlertDeliveryListResponse:
    return await service.list_for_alert(alert_id, limit)
