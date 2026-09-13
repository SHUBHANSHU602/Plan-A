import asyncio
import os
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import async_session_factory, engine
from app.db.transaction import TransactionManager
from app.main import app
from app.repositories.notification import (
    AlertDeliveryRepository,
    NotificationSubscriptionRepository,
)
from app.schemas.alert import AlertEventType
from app.schemas.notification import NotificationEvent
from app.services.fcm_delivery_service import FcmDeliveryService

pytestmark = pytest.mark.integration

if os.getenv("RUN_DATABASE_TESTS") != "1":
    pytest.skip("database integration tests are disabled", allow_module_level=True)

cell_id = uuid4()
cell_code = f"notification-cell-{cell_id}"
registration_id = f"integration-installation-{uuid4()}"


class FakePushClient:
    def __init__(self) -> None:
        self.registration_ids = []

    async def send(self, installation_id, _event):
        self.registration_ids.append(installation_id)
        return "projects/test/messages/integration"


async def seed_cell() -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                INSERT INTO risk_cells (
                    id, cell_code, geometry, elevation_m, slope_deg, aspect_deg
                )
                VALUES (
                    :id, :cell_code,
                    ST_GeomFromText(
                        'POLYGON((84.00 24.00, 84.02 24.00, 84.02 24.02, '
                        '84.00 24.02, 84.00 24.00))',
                        4326
                    ),
                    213, 50.76, 22.93
                )
                """
            ),
            {"id": cell_id, "cell_code": cell_code},
        )


async def assert_notification_delivery_pipeline() -> None:
    subscription_id = None
    try:
        await seed_cell()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            subscription = await client.post(
                "/api/v1/notifications/subscriptions",
                json={
                    "registration_id": registration_id,
                    "platform": "WEB",
                    "subscriber_reference": "integration-dashboard",
                },
            )
            refreshed = await client.post(
                "/api/v1/notifications/subscriptions",
                json={
                    "registration_id": registration_id,
                    "platform": "WEB",
                    "subscriber_reference": "integration-dashboard",
                },
            )
            assert subscription.status_code == 201
            assert refreshed.json()["id"] == subscription.json()["id"]
            assert "registration_id" not in subscription.json()
            subscription_id = UUID(subscription.json()["id"])

            prediction = await client.post(
                "/api/v1/predict",
                json={"cell_code": cell_code, "rainfall_mm": 115.34},
            )
            assert prediction.status_code == 201
            alert = prediction.json()["alert"]
            event = NotificationEvent(
                event_id=UUID(alert["event_id"]),
                alert_id=UUID(alert["alert_id"]),
                event_type=AlertEventType(alert["action"]),
                occurred_at=datetime.fromisoformat(alert["event_created_at"]),
                payload={
                    "cell_code": cell_code,
                    "severity": alert["severity"],
                    "status": "ACTIVE",
                    "title": alert["title"],
                    "message": alert["message"],
                },
            )

            fake_client = FakePushClient()
            async with async_session_factory() as session:
                delivery_service = FcmDeliveryService(
                    subscription_repository=NotificationSubscriptionRepository(session),
                    delivery_repository=AlertDeliveryRepository(session),
                    transaction=TransactionManager(session),
                    client=fake_client,
                    max_attempts=get_settings().fcm_max_attempts,
                    retry_base_seconds=get_settings().fcm_retry_base_seconds,
                )
                result = await delivery_service.deliver_event(event)

            deliveries = await client.get(
                "/api/v1/notifications/deliveries",
                params={"alert_id": str(event.alert_id)},
            )

        assert result.sent == 1
        assert fake_client.registration_ids == [registration_id]
        assert deliveries.status_code == 200
        assert deliveries.json()["items"][0]["status"] == "SENT"
        assert deliveries.json()["items"][0]["attempt_count"] == 1
        assert (
            deliveries.json()["items"][0]["provider_message_id"]
            == "projects/test/messages/integration"
        )
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM risk_cells WHERE id = :cell_id"),
                {"cell_id": cell_id},
            )
            if subscription_id is not None:
                await connection.execute(
                    text("DELETE FROM notification_subscriptions WHERE id = :id"),
                    {"id": subscription_id},
                )
        await engine.dispose()


def test_notification_delivery_is_persisted_end_to_end() -> None:
    asyncio.run(assert_notification_delivery_pipeline())
