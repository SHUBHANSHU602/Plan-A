from collections.abc import Callable
from datetime import UTC, datetime

from app.db.transaction import TransactionManager
from app.models.operations import SimulationRun
from app.repositories.operations import SimulationRunRepository
from app.repositories.risk import RiskCellRepository, RiskSnapshotRepository
from app.schemas.operations import RainfallSimulationRequest, RainfallSimulationResponse
from app.schemas.prediction import PredictionRequest
from app.services.risk_service import RiskCellNotFoundError, RiskService


def utc_now() -> datetime:
    return datetime.now(UTC)


class SimulationBaselineNotFoundError(Exception):
    pass


class SimulatedRainfallLimitError(Exception):
    pass


class SimulationService:
    def __init__(
        self,
        cell_repository: RiskCellRepository,
        snapshot_repository: RiskSnapshotRepository,
        run_repository: SimulationRunRepository,
        risk_service: RiskService,
        transaction: TransactionManager,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._cell_repository = cell_repository
        self._snapshot_repository = snapshot_repository
        self._run_repository = run_repository
        self._risk_service = risk_service
        self._transaction = transaction
        self._clock = clock

    async def simulate(self, request: RainfallSimulationRequest) -> RainfallSimulationResponse:
        cell = await self._cell_repository.get_by_code(request.cell_code)
        if cell is None:
            raise RiskCellNotFoundError(request.cell_code)
        latest = await self._snapshot_repository.get_latest_for_cell(cell.id)
        if request.baseline_rainfall_mm is None and (latest is None or latest.rainfall_mm is None):
            raise SimulationBaselineNotFoundError(request.cell_code)

        baseline = (
            request.baseline_rainfall_mm
            if request.baseline_rainfall_mm is not None
            else latest.rainfall_mm
        )
        simulated = baseline * request.rainfall_multiplier
        if simulated > 5_000:
            raise SimulatedRainfallLimitError("simulated rainfall exceeds the 5000 mm safety limit")

        try:
            run = await self._run_repository.add(
                SimulationRun(
                    cell_id=cell.id,
                    baseline_snapshot_id=latest.id if latest else None,
                    baseline_rainfall_mm=baseline,
                    rainfall_multiplier=request.rainfall_multiplier,
                    simulated_rainfall_mm=simulated,
                    status="PENDING",
                )
            )
            await self._transaction.commit()
            run_id = run.id
        except Exception:
            await self._transaction.rollback()
            raise

        try:
            prediction = await self._risk_service.predict(
                PredictionRequest(cell_code=cell.cell_code, rainfall_mm=simulated)
            )
        except Exception as error:
            run = await self._run_repository.get(run_id)
            if run is None:
                raise RuntimeError("simulation run disappeared during prediction") from error
            run.status = "FAILED"
            run.error = str(error)[:500]
            run.completed_at = self._clock()
            await self._transaction.commit()
            raise

        run.status = "COMPLETED"
        run.result_snapshot_id = prediction.snapshot_id
        run.alert_id = prediction.alert.alert_id if prediction.alert else None
        run.completed_at = self._clock()
        await self._transaction.commit()
        return RainfallSimulationResponse(
            run_id=run.id,
            baseline_snapshot_id=run.baseline_snapshot_id,
            baseline_rainfall_mm=baseline,
            rainfall_multiplier=request.rainfall_multiplier,
            simulated_rainfall_mm=simulated,
            prediction=prediction,
        )
