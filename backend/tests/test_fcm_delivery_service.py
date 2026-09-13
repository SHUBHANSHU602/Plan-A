import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from app.notifications.fcm_client import PushDeliveryError
from app.schemas.alert import AlertEventType
from app.schemas.delivery import DeliveryStatus
from app.schemas.notification import NotificationEvent
from app.services.fcm_delivery_service import FcmDeliveryService

NOW = datetime(2026, 9, 12, 12, 0, tzinfo=UTC)


def make_event() -> NotificationEvent:
    return NotificationEvent(
        event_id=uuid4(),
        alert_id=uuid4(),
        event_type=AlertEventType.CREATED,
        occurred_at=NOW,
        payload={"title": "Critical Landslide Risk", "message": "Elevated risk."},
    )


class StubSubscriptionRepository:
    def __init__(self) -> None:
        self.subscription = SimpleNamespace(
            id=uuid4(),
            registration_id="installation-id-long-enough-12345",
            active=True,
        )
        self.deactivated = []

    async def list_active(self):
        return [self.subscription] if self.subscription.active else []

    async def get(self, subscription_id):
        return self.subscription if self.subscription.id == subscription_id else None

    async def deactivate(self, subscription_id, _now):
        self.deactivated.append(subscription_id)
        self.subscription.active = False
        return True


class StubDeliveryRepository:
    def __init__(self) -> None:
        self.deliveries = {}

    async def enqueue(self, event, subscription_id, provider, now):
        delivery = SimpleNamespace(
            id=uuid4(),
            alert_id=event.alert_id,
            alert_event_id=event.event_id,
            subscription_id=subscription_id,
            provider=provider,
            channel="FCM",
            status=DeliveryStatus.PENDING.value,
            payload=event.model_dump(mode="json"),
            attempt_count=0,
            next_attempt_at=now,
            provider_message_id=None,
            last_error=None,
            sent_at=None,
        )
        self.deliveries[delivery.id] = delivery
        return delivery.id

    async def get_due_for_update(self, delivery_id, now):
        delivery = self.deliveries[delivery_id]
        if delivery.status not in (DeliveryStatus.PENDING.value, DeliveryStatus.RETRY.value):
            return None
        if delivery.next_attempt_at is not None and delivery.next_attempt_at > now:
            return None
        return delivery

    async def list_due_ids(self, now, limit):
        return [
            delivery.id
            for delivery in self.deliveries.values()
            if delivery.status in (DeliveryStatus.PENDING.value, DeliveryStatus.RETRY.value)
            and (delivery.next_attempt_at is None or delivery.next_attempt_at <= now)
        ][:limit]


class StubTransaction:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class SequencePushClient:
    def __init__(self, outcomes) -> None:
        self.outcomes = list(outcomes)
        self.tokens = []

    async def send(self, token, _event):
        self.tokens.append(token)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def make_service(client, subscriptions, deliveries, clock=lambda: NOW):
    return FcmDeliveryService(
        subscription_repository=subscriptions,
        delivery_repository=deliveries,
        transaction=StubTransaction(),
        client=client,
        max_attempts=3,
        retry_base_seconds=30,
        clock=clock,
    )


async def assert_successful_delivery_is_audited() -> None:
    subscriptions = StubSubscriptionRepository()
    deliveries = StubDeliveryRepository()
    client = SequencePushClient(["projects/demo/messages/123"])
    service = make_service(client, subscriptions, deliveries)

    result = await service.deliver_event(make_event())
    delivery = next(iter(deliveries.deliveries.values()))

    assert result.sent == 1
    assert delivery.status == DeliveryStatus.SENT.value
    assert delivery.provider_message_id == "projects/demo/messages/123"
    assert delivery.attempt_count == 1
    assert delivery.sent_at == NOW


def test_successful_delivery_is_audited() -> None:
    asyncio.run(assert_successful_delivery_is_audited())


async def assert_transient_failure_retries_with_backoff() -> None:
    current_time = [NOW]
    subscriptions = StubSubscriptionRepository()
    deliveries = StubDeliveryRepository()
    client = SequencePushClient(
        [
            PushDeliveryError("FCM unavailable", retryable=True),
            "projects/demo/messages/456",
        ]
    )
    service = make_service(client, subscriptions, deliveries, clock=lambda: current_time[0])

    first = await service.deliver_event(make_event())
    delivery = next(iter(deliveries.deliveries.values()))
    assert first.retrying == 1
    assert delivery.status == DeliveryStatus.RETRY.value
    assert delivery.next_attempt_at == NOW + timedelta(seconds=30)

    current_time[0] = NOW + timedelta(seconds=30)
    retried = await service.retry_due()

    assert retried.sent == 1
    assert delivery.status == DeliveryStatus.SENT.value
    assert delivery.attempt_count == 2


def test_transient_failure_retries_with_exponential_backoff() -> None:
    asyncio.run(assert_transient_failure_retries_with_backoff())


async def assert_retry_budget_is_bounded() -> None:
    current_time = [NOW]
    subscriptions = StubSubscriptionRepository()
    deliveries = StubDeliveryRepository()
    client = SequencePushClient(
        [
            PushDeliveryError("FCM unavailable", retryable=True),
            PushDeliveryError("FCM unavailable", retryable=True),
            PushDeliveryError("FCM unavailable", retryable=True),
        ]
    )
    service = make_service(client, subscriptions, deliveries, clock=lambda: current_time[0])

    await service.deliver_event(make_event())
    current_time[0] = NOW + timedelta(seconds=30)
    await service.retry_due()
    current_time[0] = NOW + timedelta(seconds=90)
    final = await service.retry_due()
    delivery = next(iter(deliveries.deliveries.values()))

    assert final.failed == 1
    assert delivery.status == DeliveryStatus.FAILED.value
    assert delivery.attempt_count == 3
    assert delivery.next_attempt_at is None


def test_retry_budget_is_bounded() -> None:
    asyncio.run(assert_retry_budget_is_bounded())


async def assert_invalid_target_is_deactivated() -> None:
    subscriptions = StubSubscriptionRepository()
    deliveries = StubDeliveryRepository()
    client = SequencePushClient(
        [PushDeliveryError("unregistered", retryable=False, invalid_target=True)]
    )
    service = make_service(client, subscriptions, deliveries)

    result = await service.deliver_event(make_event())
    delivery = next(iter(deliveries.deliveries.values()))

    assert result.failed == 1
    assert delivery.status == DeliveryStatus.INVALID_TARGET.value
    assert subscriptions.deactivated == [subscriptions.subscription.id]
    assert subscriptions.subscription.active is False


def test_invalid_target_is_deactivated() -> None:
    asyncio.run(assert_invalid_target_is_deactivated())
