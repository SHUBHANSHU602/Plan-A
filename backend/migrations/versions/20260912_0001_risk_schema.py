"""Create PostGIS risk cells and snapshots.

Revision ID: 20260912_0001
Revises:
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260912_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "risk_cells",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cell_code", sa.String(length=64), nullable=False),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(
                geometry_type="POLYGON",
                srid=4326,
                spatial_index=False,
            ),
            nullable=False,
        ),
        sa.Column("elevation_m", sa.Float(), nullable=True),
        sa.Column("slope_deg", sa.Float(), nullable=True),
        sa.Column("aspect_deg", sa.Float(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_cells")),
        sa.UniqueConstraint("cell_code", name=op.f("uq_risk_cells_cell_code")),
    )
    op.create_index(
        "ix_risk_cells_geometry",
        "risk_cells",
        ["geometry"],
        unique=False,
        postgresql_using="gist",
    )

    op.create_table(
        "risk_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cell_id", sa.Uuid(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("probability", sa.Float(), nullable=False),
        sa.Column("predicted_class", sa.SmallInteger(), nullable=False),
        sa.Column(
            "drivers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "predicted_class IN (0, 1)",
            name=op.f("ck_risk_snapshots_predicted_class_binary"),
        ),
        sa.CheckConstraint(
            "probability >= 0 AND probability <= 1",
            name=op.f("ck_risk_snapshots_probability_range"),
        ),
        sa.ForeignKeyConstraint(
            ["cell_id"],
            ["risk_cells.id"],
            name=op.f("fk_risk_snapshots_cell_id_risk_cells"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_snapshots")),
    )
    op.create_index(
        "ix_risk_snapshots_cell_recorded",
        "risk_snapshots",
        ["cell_id", "recorded_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_risk_snapshots_recorded_at"),
        "risk_snapshots",
        ["recorded_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_risk_snapshots_recorded_at"), table_name="risk_snapshots")
    op.drop_index("ix_risk_snapshots_cell_recorded", table_name="risk_snapshots")
    op.drop_table("risk_snapshots")
    op.drop_index("ix_risk_cells_geometry", table_name="risk_cells", postgresql_using="gist")
    op.drop_table("risk_cells")
