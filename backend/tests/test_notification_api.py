from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_delivery_query_service,
    get_notification_subscription_service,
)
from app.main import app
from app.schemas.delivery import (
    AlertDeliveryListResponse,
    NotificationSubscriptionResponse,
    SubscriptionPlatform,
)
from app.services.notification_subscription_service import (
    NotificationSubscriptionNotFoundError,
)

client = TestClient(app)


def test_subscription_api_never_returns_registration_id() -> None:
    now = datetime.now(UTC)
    expected = NotificationSubscriptionResponse(
        id=uuid4(),
        platform=SubscriptionPlatform.WEB,
        subscriber_reference="district-dashboard",
        active=True,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
    )

    class StubService:
        async def register(self, _request):
            return expected

    app.dependency_overrides[get_notification_subscription_service] = lambda: StubService()
    try:
        response = client.post(
            "/api/v1/notifications/subscriptions",
            json={
                "registration_id": "installation-id-long-enough-12345",
                "platform": "WEB",
                "subscriber_reference": "district-dashboard",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json() == expected.model_dump(mode="json")
    assert "registration_id" not in response.json()


def test_delivery_query_is_scoped_to_alert() -> None:
    alert_id = uuid4()

    class StubService:
        async def list_for_alert(self, received_alert_id, limit):
            assert received_alert_id == alert_id
            assert limit == 25
            return AlertDeliveryListResponse(items=[])

    app.dependency_overrides[get_delivery_query_service] = lambda: StubService()
    try:
        response = client.get(
            "/api/v1/notifications/deliveries",
            params={"alert_id": str(alert_id), "limit": 25},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_missing_subscription_returns_404() -> None:
    class StubService:
        async def deactivate(self, _subscription_id):
            raise NotificationSubscriptionNotFoundError

    app.dependency_overrides[get_notification_subscription_service] = lambda: StubService()
    try:
        response = client.delete(f"/api/v1/notifications/subscriptions/{uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
