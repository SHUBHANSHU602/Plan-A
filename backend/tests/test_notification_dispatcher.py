import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from app.notifications.dispatcher import NotificationDispatcher
from app.schemas.alert import AlertEventType
from app.schemas.notification import (
    NotificationChannel,
    NotificationDeliveryResult,
    NotificationEvent,
)


def make_event() -> NotificationEvent:
    return NotificationEvent(
        event_id=uuid4(),
        alert_id=uuid4(),
        event_type=AlertEventType.CREATED,
        occurred_at=datetime.now(UTC),
        payload={"cell_code": "A17"},
    )


class SuccessfulProvider:
    name = "successful"
    channel = NotificationChannel.DASHBOARD

    async def send(self, _event):
        return NotificationDeliveryResult(
            provider=self.name,
            channel=self.channel,
            delivered=True,
        )


class FailingProvider:
    name = "failing"
    channel = NotificationChannel.FCM

    async def send(self, _event):
        raise RuntimeError("provider unavailable")


async def assert_provider_failures_are_isolated() -> None:
    dispatcher = NotificationDispatcher([SuccessfulProvider(), FailingProvider()])

    results = await dispatcher.dispatch(make_event())

    assert [result.provider for result in results] == ["successful", "failing"]
    assert results[0].delivered is True
    assert results[1].delivered is False
    assert results[1].error == "provider unavailable"


def test_provider_failures_are_isolated() -> None:
    asyncio.run(assert_provider_failures_are_isolated())
