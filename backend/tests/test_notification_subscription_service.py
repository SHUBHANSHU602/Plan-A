import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.schemas.delivery import NotificationSubscriptionCreate, SubscriptionPlatform
from app.services.notification_subscription_service import (
    NotificationSubscriptionNotFoundError,
    NotificationSubscriptionService,
)

NOW = datetime(2026, 9, 12, 12, 0, tzinfo=UTC)


class StubRepository:
    def __init__(self) -> None:
        self.subscription = None
        self.registration = None

    async def create_or_refresh(self, **kwargs):
        self.registration = kwargs
        self.subscription = SimpleNamespace(
            id=uuid4(),
            platform=kwargs["platform"],
            subscriber_reference=kwargs["subscriber_reference"],
            active=True,
            last_seen_at=kwargs["now"],
            created_at=kwargs["now"],
            updated_at=kwargs["now"],
        )
        return self.subscription

    async def deactivate(self, subscription_id, now):
        if self.subscription is None or self.subscription.id != subscription_id:
            return False
        self.subscription.active = False
        self.subscription.deactivated_at = now
        return True


class StubTransaction:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


async def assert_registration_and_deactivation() -> None:
    repository = StubRepository()
    transaction = StubTransaction()
    service = NotificationSubscriptionService(repository, transaction, clock=lambda: NOW)
    request = NotificationSubscriptionCreate(
        registration_id="  installation-id-long-enough-12345  ",
        platform=SubscriptionPlatform.WEB,
        subscriber_reference="  district-dashboard  ",
    )

    response = await service.register(request)
    await service.deactivate(response.id)

    assert repository.registration["registration_id"] == "installation-id-long-enough-12345"
    assert repository.registration["subscriber_reference"] == "district-dashboard"
    assert response.model_dump().get("registration_id") is None
    assert repository.subscription.active is False
    assert transaction.commits == 2


def test_registration_hides_token_and_deactivation_is_soft() -> None:
    asyncio.run(assert_registration_and_deactivation())


async def assert_missing_subscription_rolls_back() -> None:
    transaction = StubTransaction()
    service = NotificationSubscriptionService(StubRepository(), transaction, clock=lambda: NOW)

    with pytest.raises(NotificationSubscriptionNotFoundError):
        await service.deactivate(uuid4())

    assert transaction.rollbacks == 1


def test_missing_subscription_is_reported() -> None:
    asyncio.run(assert_missing_subscription_rolls_back())
