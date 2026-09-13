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
        Index("ix_alerts_created_id", "created_at", "id"),
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


class AlertEvent(Base):
    __tablename__ = "alert_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('CREATED', 'REFRESHED', 'ESCALATED', "
            "'ACKNOWLEDGED', 'VERIFIED', 'RESOLVED')",
            name="event_type_valid",
        ),
        CheckConstraint(
            "from_status IN ('ACTIVE', 'ACKNOWLEDGED', 'VERIFIED', 'RESOLVED')",
            name="from_status_valid",
        ),
        CheckConstraint(
            "to_status IN ('ACTIVE', 'ACKNOWLEDGED', 'VERIFIED', 'RESOLVED')",
            name="to_status_valid",
        ),
        CheckConstraint(
            "actor_type IN ('SYSTEM', 'CLIENT')",
            name="actor_type_valid",
        ),
        Index("ix_alert_events_alert_created", "alert_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    alert_id: Mapped[UUID] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(24))
    from_status: Mapped[str] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    actor_type: Mapped[str] = mapped_column(String(16))
    actor_reference: Mapped[str] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
