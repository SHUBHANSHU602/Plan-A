from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.db.transaction import TransactionManager
from app.repositories.operations import RainfallObservationRepository
from app.repositories.risk import RiskCellRepository
from app.schemas.operations import ObservationStatus
from app.schemas.prediction import PredictionRequest
from app.services.risk_service import RiskService


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class RainfallProcessingResult:
    claimed: int
    processed: int
    retrying: int
    failed: int


class RainfallProcessingService:
    def __init__(
        self,
        observation_repository: RainfallObservationRepository,
        cell_repository: RiskCellRepository,
        risk_service: RiskService,
        transaction: TransactionManager,
        max_attempts: int,
        retry_seconds: int,
        claim_timeout_seconds: int,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._observation_repository = observation_repository
        self._cell_repository = cell_repository
        self._risk_service = risk_service
        self._transaction = transaction
        self._max_attempts = max_attempts
        self._retry_seconds = retry_seconds
        self._claim_timeout = timedelta(seconds=claim_timeout_seconds)
        self._clock = clock

    async def process_due(self, limit: int) -> RainfallProcessingResult:
        now = self._clock()
        try:
            ids = await self._observation_repository.list_due_ids(
                now,
                now - self._claim_timeout,
                limit,
            )
            await self._transaction.commit()
        except Exception:
            await self._transaction.rollback()
            raise

        processed = retrying = failed = claimed = 0
        for observation_id in ids:
            outcome = await self._process_one(observation_id)
            if outcome is None:
                continue
            claimed += 1
            if outcome == ObservationStatus.PROCESSED:
                processed += 1
            elif outcome == ObservationStatus.PENDING:
                retrying += 1
            else:
                failed += 1
        return RainfallProcessingResult(claimed, processed, retrying, failed)

    async def _process_one(self, observation_id) -> ObservationStatus | None:
        now = self._clock()
        try:
            observation = await self._observation_repository.claim(
                observation_id,
                now,
                now - self._claim_timeout,
            )
            if observation is None:
                await self._transaction.commit()
                return None
            await self._transaction.commit()

            cell = await self._cell_repository.get_by_id(observation.cell_id)
            if cell is None:
                raise RuntimeError("rainfall observation references a missing risk cell")
            prediction = await self._risk_service.predict(
                PredictionRequest(
                    cell_code=cell.cell_code,
                    rainfall_mm=observation.rainfall_mm,
                )
            )
            observation = await self._observation_repository.get(observation_id)
            observation.status = ObservationStatus.PROCESSED.value
            observation.processed_snapshot_id = prediction.snapshot_id
            observation.processed_at = self._clock()
            observation.claimed_at = None
            observation.next_attempt_at = None
            await self._transaction.commit()
            return ObservationStatus.PROCESSED
        except Exception as error:
            await self._transaction.rollback()
            observation = await self._observation_repository.get(observation_id)
            if observation is None:
                await self._transaction.commit()
                return ObservationStatus.FAILED
            observation.last_error = str(error)[:500]
            observation.claimed_at = None
            if observation.attempt_count < self._max_attempts:
                observation.status = ObservationStatus.PENDING.value
                observation.next_attempt_at = self._clock() + timedelta(
                    seconds=self._retry_seconds * (2 ** (observation.attempt_count - 1))
                )
                outcome = ObservationStatus.PENDING
            else:
                observation.status = ObservationStatus.FAILED.value
                observation.next_attempt_at = None
                outcome = ObservationStatus.FAILED
            await self._transaction.commit()
            return outcome
