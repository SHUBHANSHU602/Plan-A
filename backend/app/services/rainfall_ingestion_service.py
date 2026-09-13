from collections.abc import Callable
from datetime import UTC, datetime

from app.db.transaction import TransactionManager
from app.repositories.operations import RainfallObservationRepository
from app.repositories.risk import RiskCellRepository
from app.schemas.operations import (
    ObservationStatus,
    RainfallObservationCreate,
    RainfallObservationResponse,
)
from app.services.risk_service import RiskCellNotFoundError


def utc_now() -> datetime:
    return datetime.now(UTC)


class RainfallIngestionService:
    def __init__(
        self,
        cell_repository: RiskCellRepository,
        observation_repository: RainfallObservationRepository,
        transaction: TransactionManager,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._cell_repository = cell_repository
        self._observation_repository = observation_repository
        self._transaction = transaction
        self._clock = clock

    async def enqueue(self, request: RainfallObservationCreate) -> RainfallObservationResponse:
        try:
            cell = await self._cell_repository.get_by_code(request.cell_code)
            if cell is None:
                raise RiskCellNotFoundError(request.cell_code)
            observation = await self._observation_repository.enqueue(
                cell.id,
                request,
                self._clock(),
            )
            if (
                observation.cell_id != cell.id
                or observation.rainfall_mm != request.rainfall_mm
                or observation.observed_at != request.observed_at
            ):
                raise RainfallObservationConflictError(
                    "source_event_id was already used with a different payload"
                )
            await self._transaction.commit()
        except Exception:
            await self._transaction.rollback()
            raise
        return RainfallObservationResponse(
            id=observation.id,
            cell_id=observation.cell_id,
            cell_code=cell.cell_code,
            source=observation.source,
            source_event_id=observation.source_event_id,
            rainfall_mm=observation.rainfall_mm,
            observed_at=observation.observed_at,
            status=ObservationStatus(observation.status),
            attempt_count=observation.attempt_count,
            next_attempt_at=observation.next_attempt_at,
            processed_snapshot_id=observation.processed_snapshot_id,
            last_error=observation.last_error,
            created_at=observation.created_at,
        )


class RainfallObservationConflictError(Exception):
    pass
