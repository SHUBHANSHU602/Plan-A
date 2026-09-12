from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

OPEN_ALERT_PREDICATE = "status IN ('ACTIVE', 'ACKNOWLEDGED', 'VERIFIED')"


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('HIGH', 'CRITICAL')",
            name="severity_valid",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'ACKNOWLEDGED', 'VERIFIED', 'RESOLVED')",
            name="status_valid",
        ),
        CheckConstraint(
            "current_probability >= 0 AND current_probability <= 1",
            name="current_probability_range",
        ),
        CheckConstraint(
            "peak_probability >= 0 AND peak_probability <= 1",
            name="peak_probability_range",
        ),
        CheckConstraint("occurrence_count >= 1", name="occurrence_count_positive"),
        Index(
            "uq_alerts_open_cell",
            "cell_id",
            unique=True,
            postgresql_where=text(OPEN_ALERT_PREDICATE),
        ),
        Index("ix_alerts_status_severity_last_seen", "status", "severity", "last_seen_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    cell_id: Mapped[UUID] = mapped_column(ForeignKey("risk_cells.id", ondelete="CASCADE"))
    latest_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("risk_snapshots.id", ondelete="SET NULL")
    )
    severity: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", server_default="ACTIVE")
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(String(500))
    current_probability: Mapped[float] = mapped_column(Float)
    peak_probability: Mapped[float] = mapped_column(Float)
    drivers: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    exposure: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_emitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
