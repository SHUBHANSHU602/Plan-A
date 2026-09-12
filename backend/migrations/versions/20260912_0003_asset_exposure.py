"""Add geospatial infrastructure assets.

Revision ID: 20260912_0003
Revises: 20260912_0002
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260912_0003"
down_revision: str | None = "20260912_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("asset_type", sa.String(length=24), nullable=False),
        sa.Column("criticality", sa.SmallInteger(), server_default="3", nullable=False),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geography(
                geometry_type="GEOMETRY",
                srid=4326,
                spatial_index=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "properties",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "asset_type IN ('VILLAGE', 'ROAD', 'HOSPITAL', 'SCHOOL', 'BRIDGE', 'RAILWAY')",
            name=op.f("ck_assets_asset_type_valid"),
        ),
        sa.CheckConstraint(
            "criticality >= 1 AND criticality <= 5",
            name=op.f("ck_assets_criticality_range"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assets")),
        sa.UniqueConstraint("asset_code", name=op.f("uq_assets_asset_code")),
    )
    op.create_index(
        "ix_assets_geometry",
        "assets",
        ["geometry"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_index(
        "ix_assets_type_criticality",
        "assets",
        ["asset_type", "criticality"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_assets_type_criticality", table_name="assets")
    op.drop_index("ix_assets_geometry", table_name="assets", postgresql_using="gist")
    op.drop_table("assets")
