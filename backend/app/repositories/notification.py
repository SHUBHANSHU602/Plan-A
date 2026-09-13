import hashlib
from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import AlertDelivery, NotificationSubscription
from app.schemas.delivery import DeliveryStatus
from app.schemas.notification import NotificationEvent


class NotificationSubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_or_refresh(
        self,
        *,
        registration_id: str,
        platform: str,
        subscriber_reference: str,
        now: datetime,
    ) -> NotificationSubscription:
        registration_id_hash = hashlib.sha256(registration_id.encode()).hexdigest()
        statement = (
            insert(NotificationSubscription)
            .values(
                registration_id=registration_id,
                registration_id_hash=registration_id_hash,
                platform=platform,
                subscriber_reference=subscriber_reference,
                active=True,
                last_seen_at=now,
                deactivated_at=None,
            )
            .on_conflict_do_update(
                constraint="uq_notification_subscriptions_registration_id_hash",
                set_={
                    "registration_id": registration_id,
                    "platform": platform,
                    "subscriber_reference": subscriber_reference,
                    "active": True,
                    "last_seen_at": now,
                    "deactivated_at": None,
                    "updated_at": now,
                },
            )
            .returning(NotificationSubscription)
        )
        return (await self._session.scalars(statement)).one()

    async def get(self, subscription_id: UUID) -> NotificationSubscription | None:
        return await self._session.get(NotificationSubscription, subscription_id)

    async def deactivate(self, subscription_id: UUID, now: datetime) -> bool:
        subscription = await self.get(subscription_id)
        if subscription is None:
            return False
        subscription.active = False
        subscription.deactivated_at = now
        return True

    async def list_active(self) -> list[NotificationSubscription]:
        statement = select(NotificationSubscription).where(
            NotificationSubscription.active.is_(True)
        )
        return list(await self._session.scalars(statement))


class AlertDeliveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(
        self,
        event: NotificationEvent,
        subscription_id: UUID,
        provider: str,
        now: datetime,
    ) -> UUID:
        statement = (
            insert(AlertDelivery)
            .values(
                alert_id=event.alert_id,
                alert_event_id=event.event_id,
                subscription_id=subscription_id,
                provider=provider,
                channel="FCM",
                status=DeliveryStatus.PENDING.value,
                payload=event.model_dump(mode="json"),
                next_attempt_at=now,
            )
            .on_conflict_do_nothing(constraint="uq_alert_deliveries_event_subscription_provider")
            .returning(AlertDelivery.id)
        )
        delivery_id = await self._session.scalar(statement)
        if delivery_id is not None:
            return delivery_id

        existing = await self._session.scalar(
            select(AlertDelivery.id).where(
                AlertDelivery.alert_event_id == event.event_id,
                AlertDelivery.subscription_id == subscription_id,
                AlertDelivery.provider == provider,
            )
        )
        if existing is None:
            raise RuntimeError("delivery conflict did not resolve to an existing row")
        return existing

    async def get_due_for_update(
        self,
        delivery_id: UUID,
        now: datetime,
    ) -> AlertDelivery | None:
        statement = (
            select(AlertDelivery)
            .where(
                AlertDelivery.id == delivery_id,
                AlertDelivery.status.in_(
                    (DeliveryStatus.PENDING.value, DeliveryStatus.RETRY.value)
                ),
                or_(
                    AlertDelivery.next_attempt_at.is_(None),
                    AlertDelivery.next_attempt_at <= now,
                ),
            )
            .with_for_update(skip_locked=True)
        )
        return await self._session.scalar(statement)

    async def list_due_ids(self, now: datetime, limit: int) -> list[UUID]:
        statement = (
            select(AlertDelivery.id)
            .where(
                AlertDelivery.status.in_(
                    (DeliveryStatus.PENDING.value, DeliveryStatus.RETRY.value)
                ),
                or_(
                    AlertDelivery.next_attempt_at.is_(None),
                    AlertDelivery.next_attempt_at <= now,
                ),
            )
            .order_by(AlertDelivery.next_attempt_at, AlertDelivery.created_at)
            .limit(limit)
        )
        return list(await self._session.scalars(statement))

    async def list_for_alert(self, alert_id: UUID, limit: int) -> list[AlertDelivery]:
        statement = (
            select(AlertDelivery)
            .where(AlertDelivery.alert_id == alert_id)
            .order_by(AlertDelivery.created_at.desc(), AlertDelivery.id.desc())
            .limit(limit)
        )
        return list(await self._session.scalars(statement))
