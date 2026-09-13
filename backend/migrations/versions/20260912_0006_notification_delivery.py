"""Add notification subscriptions and delivery audit.

Revision ID: 20260912_0006
Revises: 20260912_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260912_0006"
down_revision: str | None = "20260912_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("registration_id", sa.Text(), nullable=False),
        sa.Column("registration_id_hash", sa.String(length=64), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("subscriber_reference", sa.String(length=120), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "platform IN ('WEB', 'ANDROID', 'IOS')",
            name=op.f("ck_notification_subscriptions_platform_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_subscriptions")),
        sa.UniqueConstraint(
            "registration_id_hash",
            name=op.f("uq_notification_subscriptions_registration_id_hash"),
        ),
    )
    op.create_index(
        "ix_notification_subscriptions_active",
        "notification_subscriptions",
        ["active", "last_seen_at"],
        unique=False,
    )

    op.create_table(
        "alert_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("alert_id", sa.Uuid(), nullable=False),
        sa.Column("alert_event_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="PENDING", nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name=op.f("ck_alert_deliveries_attempt_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "channel IN ('FCM')",
            name=op.f("ck_alert_deliveries_channel_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RETRY', 'SENT', 'FAILED', 'INVALID_TARGET')",
            name=op.f("ck_alert_deliveries_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["alert_event_id"],
            ["alert_events.id"],
            name=op.f("fk_alert_deliveries_alert_event_id_alert_events"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alerts.id"],
            name=op.f("fk_alert_deliveries_alert_id_alerts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["notification_subscriptions.id"],
            name=op.f("fk_alert_deliveries_subscription_id_notification_subscriptions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alert_deliveries")),
        sa.UniqueConstraint(
            "alert_event_id",
            "subscription_id",
            "provider",
            name=op.f("uq_alert_deliveries_event_subscription_provider"),
        ),
    )
    op.create_index(
        "ix_alert_deliveries_alert_created",
        "alert_deliveries",
        ["alert_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_alert_deliveries_due",
        "alert_deliveries",
        ["status", "next_attempt_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_alert_deliveries_due", table_name="alert_deliveries")
    op.drop_index("ix_alert_deliveries_alert_created", table_name="alert_deliveries")
    op.drop_table("alert_deliveries")
    op.drop_index("ix_notification_subscriptions_active", table_name="notification_subscriptions")
    op.drop_table("notification_subscriptions")
