"""Add rainfall observation queue and simulation runs.

Revision ID: 20260912_0007
Revises: 20260912_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260912_0007"
down_revision: str | None = "20260912_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rainfall_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cell_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_event_id", sa.String(length=128), nullable=False),
        sa.Column("rainfall_mm", sa.Float(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="PENDING", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
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
            name=op.f("ck_rainfall_observations_attempt_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "rainfall_mm >= 0",
            name=op.f("ck_rainfall_observations_rainfall_nonnegative"),
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'PROCESSED', 'FAILED')",
            name=op.f("ck_rainfall_observations_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["cell_id"],
            ["risk_cells.id"],
            ondelete="CASCADE",
            name=op.f("fk_rainfall_observations_cell_id_risk_cells"),
        ),
        sa.ForeignKeyConstraint(
            ["processed_snapshot_id"],
            ["risk_snapshots.id"],
            ondelete="SET NULL",
            name=op.f("fk_rainfall_observations_processed_snapshot_id_risk_snapshots"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rainfall_observations")),
        sa.UniqueConstraint(
            "source", "source_event_id", name=op.f("uq_rainfall_observations_source_event")
        ),
    )
    op.create_index(
        "ix_rainfall_observations_due",
        "rainfall_observations",
        ["status", "next_attempt_at"],
        unique=False,
    )

    op.create_table(
        "simulation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cell_id", sa.Uuid(), nullable=False),
        sa.Column("baseline_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("result_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("alert_id", sa.Uuid(), nullable=True),
        sa.Column("baseline_rainfall_mm", sa.Float(), nullable=False),
        sa.Column("rainfall_multiplier", sa.Float(), nullable=False),
        sa.Column("simulated_rainfall_mm", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="PENDING", nullable=False),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "baseline_rainfall_mm >= 0",
            name=op.f("ck_simulation_runs_baseline_rainfall_nonnegative"),
        ),
        sa.CheckConstraint(
            "rainfall_multiplier > 0",
            name=op.f("ck_simulation_runs_rainfall_multiplier_positive"),
        ),
        sa.CheckConstraint(
            "simulated_rainfall_mm >= 0",
            name=op.f("ck_simulation_runs_simulated_rainfall_nonnegative"),
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'COMPLETED', 'FAILED')",
            name=op.f("ck_simulation_runs_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alerts.id"],
            ondelete="SET NULL",
            name=op.f("fk_simulation_runs_alert_id_alerts"),
        ),
        sa.ForeignKeyConstraint(
            ["baseline_snapshot_id"],
            ["risk_snapshots.id"],
            ondelete="SET NULL",
            name=op.f("fk_simulation_runs_baseline_snapshot_id_risk_snapshots"),
        ),
        sa.ForeignKeyConstraint(
            ["cell_id"],
            ["risk_cells.id"],
            ondelete="CASCADE",
            name=op.f("fk_simulation_runs_cell_id_risk_cells"),
        ),
        sa.ForeignKeyConstraint(
            ["result_snapshot_id"],
            ["risk_snapshots.id"],
            ondelete="SET NULL",
            name=op.f("fk_simulation_runs_result_snapshot_id_risk_snapshots"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_simulation_runs")),
    )
    op.create_index(
        "ix_simulation_runs_cell_created",
        "simulation_runs",
        ["cell_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_simulation_runs_cell_created", table_name="simulation_runs")
    op.drop_table("simulation_runs")
    op.drop_index("ix_rainfall_observations_due", table_name="rainfall_observations")
    op.drop_table("rainfall_observations")
