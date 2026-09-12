"""Add prediction context to risk snapshots.

Revision ID: 20260912_0002
Revises: 20260912_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260912_0002"
down_revision: str | None = "20260912_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "risk_snapshots",
        sa.Column("rainfall_mm", sa.Float(), nullable=True),
    )
    op.add_column(
        "risk_snapshots",
        sa.Column("risk_level", sa.String(length=16), nullable=True),
    )
    op.execute(
        """
        UPDATE risk_snapshots
        SET risk_level = CASE
            WHEN probability >= 0.80 THEN 'CRITICAL'
            WHEN probability >= 0.65 THEN 'HIGH'
            WHEN probability >= 0.40 THEN 'MEDIUM'
            ELSE 'LOW'
        END
        """
    )
    op.alter_column("risk_snapshots", "risk_level", nullable=False)
    op.create_check_constraint(
        op.f("ck_risk_snapshots_rainfall_non_negative"),
        "risk_snapshots",
        "rainfall_mm IS NULL OR rainfall_mm >= 0",
    )
    op.create_check_constraint(
        op.f("ck_risk_snapshots_risk_level_valid"),
        "risk_snapshots",
        "risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
    )
    op.create_index(
        "ix_risk_snapshots_level_recorded",
        "risk_snapshots",
        ["risk_level", "recorded_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_risk_snapshots_level_recorded", table_name="risk_snapshots")
    op.drop_constraint(
        op.f("ck_risk_snapshots_risk_level_valid"),
        "risk_snapshots",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_risk_snapshots_rainfall_non_negative"),
        "risk_snapshots",
        type_="check",
    )
    op.drop_column("risk_snapshots", "risk_level")
    op.drop_column("risk_snapshots", "rainfall_mm")
