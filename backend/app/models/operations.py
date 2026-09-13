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
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RainfallObservation(Base):
    __tablename__ = "rainfall_observations"
    __table_args__ = (
        CheckConstraint("rainfall_mm >= 0", name="rainfall_nonnegative"),
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'PROCESSED', 'FAILED')",
            name="status_valid",
        ),
        CheckConstraint("attempt_count >= 0", name="attempt_count_nonnegative"),
        UniqueConstraint(
            "source",
            "source_event_id",
            name="uq_rainfall_observations_source_event",
        ),
        Index("ix_rainfall_observations_due", "status", "next_attempt_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    cell_id: Mapped[UUID] = mapped_column(ForeignKey("risk_cells.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(64))
    source_event_id: Mapped[str] = mapped_column(String(128))
    rainfall_mm: Mapped[float] = mapped_column(Float)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="PENDING", server_default="PENDING")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("risk_snapshots.id", ondelete="SET NULL")
    )
    last_error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SimulationRun(Base):
    __tablename__ = "simulation_runs"
    __table_args__ = (
        CheckConstraint("baseline_rainfall_mm >= 0", name="baseline_rainfall_nonnegative"),
        CheckConstraint("rainfall_multiplier > 0", name="rainfall_multiplier_positive"),
        CheckConstraint("simulated_rainfall_mm >= 0", name="simulated_rainfall_nonnegative"),
        CheckConstraint("status IN ('PENDING', 'COMPLETED', 'FAILED')", name="status_valid"),
        Index("ix_simulation_runs_cell_created", "cell_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    cell_id: Mapped[UUID] = mapped_column(ForeignKey("risk_cells.id", ondelete="CASCADE"))
    baseline_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("risk_snapshots.id", ondelete="SET NULL")
    )
    result_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("risk_snapshots.id", ondelete="SET NULL")
    )
    alert_id: Mapped[UUID | None] = mapped_column(ForeignKey("alerts.id", ondelete="SET NULL"))
    baseline_rainfall_mm: Mapped[float] = mapped_column(Float)
    rainfall_multiplier: Mapped[float] = mapped_column(Float)
    simulated_rainfall_mm: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", server_default="PENDING")
    error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
