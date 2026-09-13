"""Add append-only alert audit events.

Revision ID: 20260912_0005
Revises: 20260912_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260912_0005"
down_revision: str | None = "20260912_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_alerts_created_id",
        "alerts",
        ["created_at", "id"],
        unique=False,
    )
    op.create_table(
        "alert_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("alert_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=False),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_reference", sa.String(length=120), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "actor_type IN ('SYSTEM', 'CLIENT')",
            name=op.f("ck_alert_events_actor_type_valid"),
        ),
        sa.CheckConstraint(
            "event_type IN ('CREATED', 'REFRESHED', 'ESCALATED', "
            "'ACKNOWLEDGED', 'VERIFIED', 'RESOLVED')",
            name=op.f("ck_alert_events_event_type_valid"),
        ),
        sa.CheckConstraint(
            "from_status IN ('ACTIVE', 'ACKNOWLEDGED', 'VERIFIED', 'RESOLVED')",
            name=op.f("ck_alert_events_from_status_valid"),
        ),
        sa.CheckConstraint(
            "to_status IN ('ACTIVE', 'ACKNOWLEDGED', 'VERIFIED', 'RESOLVED')",
            name=op.f("ck_alert_events_to_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alerts.id"],
            name=op.f("fk_alert_events_alert_id_alerts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alert_events")),
    )
    op.create_index(
        "ix_alert_events_alert_created",
        "alert_events",
        ["alert_id", "created_at"],
        unique=False,
    )

    # Preserve a starting audit record if alerts were created before this migration ran.
    op.execute(
        """
        INSERT INTO alert_events (
            id, alert_id, event_type, from_status, to_status,
            actor_type, actor_reference, note, created_at
        )
        SELECT
            gen_random_uuid(), id, 'CREATED', status, status,
            'SYSTEM', 'migration-backfill', 'Backfilled for pre-existing alert', created_at
        FROM alerts
        """
    )


def downgrade() -> None:
    op.drop_index("ix_alert_events_alert_created", table_name="alert_events")
    op.drop_table("alert_events")
    op.drop_index("ix_alerts_created_id", table_name="alerts")
