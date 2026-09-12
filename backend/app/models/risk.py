from datetime import datetime
from uuid import UUID, uuid4

from geoalchemy2 import Geometry
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RiskCell(Base):
    __tablename__ = "risk_cells"
    __table_args__ = (Index("ix_risk_cells_geometry", "geometry", postgresql_using="gist"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    cell_code: Mapped[str] = mapped_column(String(64), unique=True)
    geometry: Mapped[object] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=False)
    )
    elevation_m: Mapped[float | None] = mapped_column(Float)
    slope_deg: Mapped[float | None] = mapped_column(Float)
    aspect_deg: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    snapshots: Mapped[list["RiskSnapshot"]] = relationship(
        back_populates="cell",
        cascade="all, delete-orphan",
    )


class RiskSnapshot(Base):
    __tablename__ = "risk_snapshots"
    __table_args__ = (
        CheckConstraint(
            "probability >= 0 AND probability <= 1",
            name="probability_range",
        ),
        CheckConstraint(
            "predicted_class IN (0, 1)",
            name="predicted_class_binary",
        ),
        CheckConstraint(
            "rainfall_mm IS NULL OR rainfall_mm >= 0",
            name="rainfall_non_negative",
        ),
        CheckConstraint(
            "risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="risk_level_valid",
        ),
        Index("ix_risk_snapshots_cell_recorded", "cell_id", "recorded_at"),
        Index("ix_risk_snapshots_level_recorded", "risk_level", "recorded_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    cell_id: Mapped[UUID] = mapped_column(ForeignKey("risk_cells.id", ondelete="CASCADE"))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    probability: Mapped[float] = mapped_column(Float)
    predicted_class: Mapped[int] = mapped_column(SmallInteger)
    rainfall_mm: Mapped[float | None] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(16))
    drivers: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    cell: Mapped[RiskCell] = relationship(back_populates="snapshots")
