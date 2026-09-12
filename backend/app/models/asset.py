from datetime import datetime
from uuid import UUID, uuid4

from geoalchemy2 import Geography
from sqlalchemy import CheckConstraint, DateTime, Index, SmallInteger, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint(
            "asset_type IN ('VILLAGE', 'ROAD', 'HOSPITAL', 'SCHOOL', 'BRIDGE', 'RAILWAY')",
            name="asset_type_valid",
        ),
        CheckConstraint(
            "criticality >= 1 AND criticality <= 5",
            name="criticality_range",
        ),
        Index("ix_assets_geometry", "geometry", postgresql_using="gist"),
        Index("ix_assets_type_criticality", "asset_type", "criticality"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    asset_code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    asset_type: Mapped[str] = mapped_column(String(24))
    criticality: Mapped[int] = mapped_column(SmallInteger, default=3, server_default="3")
    geometry: Mapped[object] = mapped_column(
        Geography(geometry_type="GEOMETRY", srid=4326, spatial_index=False)
    )
    properties: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
