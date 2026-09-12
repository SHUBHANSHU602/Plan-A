"""Add persisted alerts and open-alert deduplication.

Revision ID: 20260912_0004
Revises: 20260912_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260912_0004"
down_revision: str | None = "20260912_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cell_id", sa.Uuid(), nullable=False),
        sa.Column("latest_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("current_probability", sa.Float(), nullable=False),
        sa.Column("peak_probability", sa.Float(), nullable=False),
        sa.Column(
            "drivers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "exposure",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("occurrence_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_emitted_at", sa.DateTime(timezone=True), nullable=False),
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
            "current_probability >= 0 AND current_probability <= 1",
            name=op.f("ck_alerts_current_probability_range"),
        ),
        sa.CheckConstraint(
            "occurrence_count >= 1",
            name=op.f("ck_alerts_occurrence_count_positive"),
        ),
        sa.CheckConstraint(
            "peak_probability >= 0 AND peak_probability <= 1",
            name=op.f("ck_alerts_peak_probability_range"),
        ),
        sa.CheckConstraint(
            "severity IN ('HIGH', 'CRITICAL')",
            name=op.f("ck_alerts_severity_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'ACKNOWLEDGED', 'VERIFIED', 'RESOLVED')",
            name=op.f("ck_alerts_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["cell_id"],
            ["risk_cells.id"],
            name=op.f("fk_alerts_cell_id_risk_cells"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["latest_snapshot_id"],
            ["risk_snapshots.id"],
            name=op.f("fk_alerts_latest_snapshot_id_risk_snapshots"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alerts")),
    )
    op.create_index(
        "ix_alerts_status_severity_last_seen",
        "alerts",
        ["status", "severity", "last_seen_at"],
        unique=False,
    )
    op.create_index(
        "uq_alerts_open_cell",
        "alerts",
        ["cell_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('ACTIVE', 'ACKNOWLEDGED', 'VERIFIED')"),
    )


def downgrade() -> None:
    op.drop_index("uq_alerts_open_cell", table_name="alerts")
    op.drop_index("ix_alerts_status_severity_last_seen", table_name="alerts")
    op.drop_table("alerts")
