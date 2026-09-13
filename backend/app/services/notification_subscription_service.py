from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from app.db.transaction import TransactionManager
from app.models.notification import NotificationSubscription
from app.repositories.notification import NotificationSubscriptionRepository
from app.schemas.delivery import (
    NotificationSubscriptionCreate,
    NotificationSubscriptionResponse,
    SubscriptionPlatform,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


class NotificationSubscriptionNotFoundError(Exception):
    pass


class NotificationSubscriptionService:
    def __init__(
        self,
        repository: NotificationSubscriptionRepository,
        transaction: TransactionManager,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._repository = repository
        self._transaction = transaction
        self._clock = clock

    async def register(
        self, request: NotificationSubscriptionCreate
    ) -> NotificationSubscriptionResponse:
        try:
            subscription = await self._repository.create_or_refresh(
                registration_id=request.registration_id,
                platform=request.platform.value,
                subscriber_reference=request.subscriber_reference,
                now=self._clock(),
            )
            await self._transaction.commit()
        except Exception:
            await self._transaction.rollback()
            raise
        return self._to_response(subscription)

    async def deactivate(self, subscription_id: UUID) -> None:
        try:
            found = await self._repository.deactivate(subscription_id, self._clock())
            if not found:
                raise NotificationSubscriptionNotFoundError(str(subscription_id))
            await self._transaction.commit()
        except Exception:
            await self._transaction.rollback()
            raise

    @staticmethod
    def _to_response(subscription: NotificationSubscription) -> NotificationSubscriptionResponse:
        return NotificationSubscriptionResponse(
            id=subscription.id,
            platform=SubscriptionPlatform(subscription.platform),
            subscriber_reference=subscription.subscriber_reference,
            active=subscription.active,
            last_seen_at=subscription.last_seen_at,
            created_at=subscription.created_at,
            updated_at=subscription.updated_at,
        )
