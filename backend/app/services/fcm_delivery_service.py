from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.db.transaction import TransactionManager
from app.notifications.fcm_client import PushClient, PushDeliveryError
from app.repositories.notification import (
    AlertDeliveryRepository,
    NotificationSubscriptionRepository,
)
from app.schemas.delivery import DeliveryStatus, StoredNotificationPayload
from app.schemas.notification import NotificationEvent


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class DeliveryBatchResult:
    subscriptions: int
    sent: int
    retrying: int
    failed: int


class FcmDeliveryService:
    def __init__(
        self,
        subscription_repository: NotificationSubscriptionRepository,
        delivery_repository: AlertDeliveryRepository,
        transaction: TransactionManager,
        client: PushClient,
        max_attempts: int,
        retry_base_seconds: int,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._delivery_repository = delivery_repository
        self._transaction = transaction
        self._client = client
        self._max_attempts = max_attempts
        self._retry_base_seconds = retry_base_seconds
        self._clock = clock

    async def deliver_event(self, event: NotificationEvent) -> DeliveryBatchResult:
        try:
            subscriptions = await self._subscription_repository.list_active()
            delivery_ids = [
                await self._delivery_repository.enqueue(
                    event,
                    subscription.id,
                    "firebase-admin",
                    self._clock(),
                )
                for subscription in subscriptions
            ]
            await self._transaction.commit()
        except Exception:
            await self._transaction.rollback()
            raise

        return await self._attempt_batch(delivery_ids, len(subscriptions))

    async def retry_due(self, limit: int = 100) -> DeliveryBatchResult:
        try:
            delivery_ids = await self._delivery_repository.list_due_ids(self._clock(), limit)
            await self._transaction.commit()
        except Exception:
            await self._transaction.rollback()
            raise
        return await self._attempt_batch(delivery_ids, len(delivery_ids))

    async def _attempt_batch(
        self,
        delivery_ids: list[UUID],
        subscription_count: int,
    ) -> DeliveryBatchResult:
        sent = 0
        retrying = 0
        failed = 0
        for delivery_id in delivery_ids:
            status = await self._attempt(delivery_id)
            if status == DeliveryStatus.SENT:
                sent += 1
            elif status == DeliveryStatus.RETRY:
                retrying += 1
            elif status in (DeliveryStatus.FAILED, DeliveryStatus.INVALID_TARGET):
                failed += 1
        return DeliveryBatchResult(
            subscriptions=subscription_count,
            sent=sent,
            retrying=retrying,
            failed=failed,
        )

    async def _attempt(self, delivery_id: UUID) -> DeliveryStatus | None:
        now = self._clock()
        try:
            delivery = await self._delivery_repository.get_due_for_update(delivery_id, now)
            if delivery is None:
                await self._transaction.commit()
                return None

            delivery.attempt_count += 1
            event = NotificationEvent.model_validate(
                StoredNotificationPayload.model_validate(delivery.payload).model_dump()
            )
            subscription = None
            if delivery.subscription_id is not None:
                subscription = await self._subscription_repository.get(delivery.subscription_id)
            if subscription is None or not subscription.active:
                delivery.status = DeliveryStatus.INVALID_TARGET.value
                delivery.last_error = "notification subscription is missing or inactive"
                delivery.next_attempt_at = None
                await self._transaction.commit()
                return DeliveryStatus.INVALID_TARGET

            try:
                message_id = await self._client.send(subscription.registration_id, event)
            except PushDeliveryError as error:
                status = await self._record_failure(delivery, subscription.id, error, now)
                await self._transaction.commit()
                return status

            delivery.status = DeliveryStatus.SENT.value
            delivery.provider_message_id = message_id
            delivery.last_error = None
            delivery.next_attempt_at = None
            delivery.sent_at = now
            await self._transaction.commit()
            return DeliveryStatus.SENT
        except Exception:
            await self._transaction.rollback()
            raise

    async def _record_failure(
        self,
        delivery,
        subscription_id: UUID,
        error: PushDeliveryError,
        now: datetime,
    ) -> DeliveryStatus:
        delivery.provider_message_id = None
        delivery.sent_at = None
        delivery.last_error = str(error)[:500]

        if error.invalid_target:
            delivery.status = DeliveryStatus.INVALID_TARGET.value
            delivery.next_attempt_at = None
            await self._subscription_repository.deactivate(subscription_id, now)
            return DeliveryStatus.INVALID_TARGET

        if error.retryable and delivery.attempt_count < self._max_attempts:
            delay = self._retry_base_seconds * (2 ** (delivery.attempt_count - 1))
            delivery.status = DeliveryStatus.RETRY.value
            delivery.next_attempt_at = now + timedelta(seconds=delay)
            return DeliveryStatus.RETRY

        delivery.status = DeliveryStatus.FAILED.value
        delivery.next_attempt_at = None
        return DeliveryStatus.FAILED
