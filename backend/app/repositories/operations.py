from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operations import RainfallObservation, SimulationRun
from app.schemas.operations import ObservationStatus, RainfallObservationCreate


class RainfallObservationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(
        self,
        cell_id: UUID,
        request: RainfallObservationCreate,
        now: datetime,
    ) -> RainfallObservation:
        statement = (
            insert(RainfallObservation)
            .values(
                cell_id=cell_id,
                source=request.source,
                source_event_id=request.source_event_id,
                rainfall_mm=request.rainfall_mm,
                observed_at=request.observed_at,
                status=ObservationStatus.PENDING.value,
                next_attempt_at=now,
            )
            .on_conflict_do_nothing(constraint="uq_rainfall_observations_source_event")
            .returning(RainfallObservation)
        )
        observation = (await self._session.scalars(statement)).one_or_none()
        if observation is not None:
            return observation
        existing = await self._session.scalar(
            select(RainfallObservation).where(
                RainfallObservation.source == request.source,
                RainfallObservation.source_event_id == request.source_event_id,
            )
        )
        if existing is None:
            raise RuntimeError("observation conflict did not resolve to an existing row")
        return existing

    async def list_due_ids(self, now: datetime, stale_before: datetime, limit: int) -> list[UUID]:
        statement = (
            select(RainfallObservation.id)
            .where(
                or_(
                    (RainfallObservation.status == ObservationStatus.PENDING.value)
                    & or_(
                        RainfallObservation.next_attempt_at.is_(None),
                        RainfallObservation.next_attempt_at <= now,
                    ),
                    (RainfallObservation.status == ObservationStatus.PROCESSING.value)
                    & (RainfallObservation.claimed_at <= stale_before),
                )
            )
            .order_by(RainfallObservation.observed_at, RainfallObservation.id)
            .limit(limit)
        )
        return list(await self._session.scalars(statement))

    async def claim(
        self,
        observation_id: UUID,
        now: datetime,
        stale_before: datetime,
    ) -> RainfallObservation | None:
        statement = (
            select(RainfallObservation)
            .where(
                RainfallObservation.id == observation_id,
                or_(
                    (RainfallObservation.status == ObservationStatus.PENDING.value)
                    & or_(
                        RainfallObservation.next_attempt_at.is_(None),
                        RainfallObservation.next_attempt_at <= now,
                    ),
                    (RainfallObservation.status == ObservationStatus.PROCESSING.value)
                    & (RainfallObservation.claimed_at <= stale_before),
                ),
            )
            .with_for_update(skip_locked=True)
        )
        observation = await self._session.scalar(statement)
        if observation is None:
            return None
        observation.status = ObservationStatus.PROCESSING.value
        observation.claimed_at = now
        observation.attempt_count += 1
        observation.last_error = None
        return observation

    async def get(self, observation_id: UUID) -> RainfallObservation | None:
        return await self._session.get(RainfallObservation, observation_id)


class SimulationRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, run: SimulationRun) -> SimulationRun:
        self._session.add(run)
        await self._session.flush()
        await self._session.refresh(run)
        return run

    async def get(self, run_id: UUID) -> SimulationRun | None:
        return await self._session.get(SimulationRun, run_id)
