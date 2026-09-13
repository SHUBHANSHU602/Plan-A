from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationSubscription(Base):
    __tablename__ = "notification_subscriptions"
    __table_args__ = (
        CheckConstraint("platform IN ('WEB', 'ANDROID', 'IOS')", name="platform_valid"),
        UniqueConstraint(
            "registration_id_hash",
            name="uq_notification_subscriptions_registration_id_hash",
        ),
        Index("ix_notification_subscriptions_active", "active", "last_seen_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    registration_id: Mapped[str] = mapped_column(Text)
    registration_id_hash: Mapped[str] = mapped_column(String(64))
    platform: Mapped[str] = mapped_column(String(16))
    subscriber_reference: Mapped[str] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AlertDelivery(Base):
    __tablename__ = "alert_deliveries"
    __table_args__ = (
        CheckConstraint("channel IN ('FCM')", name="channel_valid"),
        CheckConstraint(
            "status IN ('PENDING', 'RETRY', 'SENT', 'FAILED', 'INVALID_TARGET')",
            name="status_valid",
        ),
        CheckConstraint("attempt_count >= 0", name="attempt_count_nonnegative"),
        UniqueConstraint(
            "alert_event_id",
            "subscription_id",
            "provider",
            name="uq_alert_deliveries_event_subscription_provider",
        ),
        Index("ix_alert_deliveries_due", "status", "next_attempt_at"),
        Index("ix_alert_deliveries_alert_created", "alert_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    alert_id: Mapped[UUID] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"))
    alert_event_id: Mapped[UUID] = mapped_column(ForeignKey("alert_events.id", ondelete="CASCADE"))
    subscription_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("notification_subscriptions.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(64))
    channel: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24), default="PENDING", server_default="PENDING")
    payload: Mapped[dict] = mapped_column(JSONB)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    last_error: Mapped[str | None] = mapped_column(String(500))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
